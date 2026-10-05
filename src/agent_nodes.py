import json
import logging

from decimal import Decimal
from functools import lru_cache
from time import perf_counter

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent_state import AgentState
from src.classification_models import (
    RequestClassification,
    RequestPlan,
)
from src.database_tools import (
    describe_table,
    list_tables,
    run_query,
)
from src.llm import get_llm
from src.prompts import (
    FINAL_ANSWER_SYSTEM_PROMPT,
    REQUEST_CLASSIFICATION_SYSTEM_PROMPT,
    REQUEST_PLAN_SYSTEM_PROMPT,
    SQL_SYSTEM_PROMPT,
)
from src.sql_metadata import extract_table_names


logger = logging.getLogger(__name__)


def _print_timing(
    stage_name: str,
    start_time: float,
) -> None:
    """
    Log debug timing information for one agent stage.

    Timing stays available for diagnostics without printing directly
    to standard output during normal application execution.
    """

    duration_ms = (
        perf_counter() - start_time
    ) * 1000

    logger.debug(
        "%s completed in %.2f ms",
        stage_name,
        duration_ms,
    )


def classify_request_node(
    state: AgentState,
):
    """
    Classify a request without generating SQL.

    This standalone classifier is retained for classification
    evaluation and tests.

    The production graph uses the combined
    classify_and_generate_sql_node instead.
    """

    start_time = perf_counter()

    llm = get_llm(
        reasoning_effort="low",
    )

    structured_llm = llm.with_structured_output(
        RequestClassification,
        method="json_schema",
        strict=True,
    )

    classification = structured_llm.invoke(
        [
            SystemMessage(
                content=(
                    REQUEST_CLASSIFICATION_SYSTEM_PROMPT
                )
            ),
            HumanMessage(
                content=(
                    f"User request:\n"
                    f"{state['question']}"
                )
            ),
        ]
    )

    _print_timing(
        "classify_request",
        start_time,
    )

    return {
        "request_type": (
            classification.request_type
        ),
        "direct_response": (
            classification.direct_response
        ),
    }


@lru_cache(maxsize=1)
def _get_schema_context():
    """
    Build and cache the PostgreSQL schema description.

    The CommercePilot database schema does not change while the
    application is running, so repeated requests can reuse the
    same schema context instead of querying PostgreSQL again.

    The first call reads the live schema.
    Later calls reuse the cached string.
    """

    tables = list_tables()
    schema_sections = []

    for table_name in tables:
        columns = describe_table(
            table_name
        )

        formatted_columns = ", ".join(
            (
                f"{column['column_name']} "
                f"({column['data_type']})"
            )
            for column in columns
        )

        schema_sections.append(
            f"{table_name}: "
            f"{formatted_columns}"
        )

    return "\n".join(
        schema_sections
    )


def inspect_schema_node(
    state: AgentState,
):
    """
    Return the PostgreSQL schema description.

    The schema is built from the live database on the first call
    and then cached for the lifetime of the application process.
    """

    start_time = perf_counter()

    schema_context = (
        _get_schema_context()
    )

    _print_timing(
        "inspect_schema",
        start_time,
    )

    return {
        "schema_context": schema_context,
    }


def _clean_sql_response(
    content: str,
) -> str:
    """
    Remove accidental Markdown fences around an LLM SQL response.

    The prompt asks for SQL only, but this keeps the SQL path
    tolerant if the model returns ```sql ... ``` anyway.
    """

    content = content.strip()

    if content.startswith("```"):
        lines = content.splitlines()

        # Remove the opening Markdown fence.
        lines = lines[1:]

        # Remove the closing fence when present.
        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        content = "\n".join(
            lines
        ).strip()

    return content


def classify_and_generate_sql_node(
    state: AgentState,
):
    """
    Classify the request and generate the first SQL attempt
    in a single Groq call.

    Answerable requests receive SQL immediately.

    Clarification, unanswerable, and rejected requests receive
    a direct response and no executable SQL.

    Medium reasoning is retained because this call now performs
    the SQL-generation work that previously used the standalone
    SQL-generation node.
    """

    start_time = perf_counter()

    llm = get_llm()

    structured_llm = llm.with_structured_output(
        RequestPlan,
        method="json_schema",
        strict=True,
    )

    prompt = f"""
Database schema:
{state["schema_context"]}

User request:
{state["question"]}

Classify the request first.

If it is answerable, generate the initial PostgreSQL query using
the provided schema and all CommercePilot SQL semantic rules.

If it is not answerable, return the appropriate direct response
and do not generate SQL.
"""

    plan = structured_llm.invoke(
        [
            SystemMessage(
                content=(
                    REQUEST_PLAN_SYSTEM_PROMPT
                )
            ),
            HumanMessage(
                content=prompt
            ),
        ]
    )

    generated_sql = ""

    if (
        plan.request_type == "answerable"
        and plan.sql
    ):
        generated_sql = (
            _clean_sql_response(
                plan.sql
            )
        )

    _print_timing(
        "classify_and_generate_sql",
        start_time,
    )

    return {
        "request_type": (
            plan.request_type
        ),
        "direct_response": (
            plan.direct_response
        ),
        "sql": generated_sql,
        "attempts": (
            1
            if plan.request_type == "answerable"
            else 0
        ),
        "last_error": None,
    }


def generate_sql_node(
    state: AgentState,
):
    """
    Generate or repair PostgreSQL for the user's question.

    In the optimized production graph, the first SQL attempt comes
    from classify_and_generate_sql_node.

    This node is retained for SQL repair after a failed execution
    and for standalone evaluation/testing where needed.
    """

    start_time = perf_counter()

    llm = get_llm()

    question = state["question"]
    schema_context = (
        state["schema_context"]
    )

    previous_sql = state.get(
        "sql",
        "",
    )
    last_error = state.get(
        "last_error"
    )

    prompt_parts = [
        (
            "Database schema:\n"
            f"{schema_context}"
        ),
        (
            "User question:\n"
            f"{question}"
        ),
    ]

    if last_error:
        prompt_parts.append(
            f"""
The previous SQL attempt failed.

Previous SQL:
{previous_sql}

Error:
{last_error}

Repair the SQL while preserving the user's intended question.
"""
        )

    prompt_parts.append(
        """
Return exactly one PostgreSQL query.
Return SQL only.
Do not include Markdown fences, explanations, or commentary.
"""
    )

    response = llm.invoke(
        [
            SystemMessage(
                content=SQL_SYSTEM_PROMPT
            ),
            HumanMessage(
                content="\n\n".join(
                    prompt_parts
                )
            ),
        ]
    )

    generated_sql = (
        _clean_sql_response(
            response.content
        )
    )

    _print_timing(
        "generate_sql",
        start_time,
    )

    return {
        "sql": generated_sql,
        "attempts": (
            state.get(
                "attempts",
                0,
            )
            + 1
        ),
        "last_error": None,
    }


def execute_sql_node(
    state: AgentState,
):
    """
    Validate and execute the SQL stored in the agent state.

    Successful execution stores the returned rows and the physical
    database tables referenced by the executed SQL.

    Validation or database errors are captured so LangGraph can
    route the workflow back to SQL generation for repair.
    """

    start_time = perf_counter()

    try:
        result = run_query(
            state["sql"]
        )

        tables_used = (
            extract_table_names(
                result["sql"]
            )
        )

        _print_timing(
            "execute_sql",
            start_time,
        )

        return {
            "sql": result["sql"],
            "query_result": (
                result["rows"]
            ),
            "tables_used": (
                tables_used
            ),
            "last_error": None,
        }

    except Exception as error:
        _print_timing(
            "execute_sql",
            start_time,
        )

        return {
            "query_result": [],
            "tables_used": [],
            "last_error": str(
                error
            ),
        }


def _humanize_column_name(
    column_name: str,
) -> str:
    """
    Convert a SQL result alias into a readable label.

    Examples:
        total_orders -> Total orders
        average_price -> Average price
        avg_review_score -> Average review score
    """

    words = (
        column_name
        .strip()
        .replace("-", "_")
        .split("_")
    )

    replacements = {
        "avg": "average",
        "cnt": "count",
        "num": "number",
    }

    readable_words = [
        replacements.get(
            word.lower(),
            word.lower(),
        )
        for word in words
        if word
    ]

    return " ".join(
        readable_words
    ).capitalize()


def _format_scalar_value(
    value,
) -> str:
    """
    Format one PostgreSQL scalar value for a concise answer.

    Numerical values receive thousands separators while their
    original precision is preserved.
    """

    if value is None:
        return "No value"

    if isinstance(
        value,
        bool,
    ):
        return (
            "True"
            if value
            else "False"
        )

    if isinstance(
        value,
        int,
    ):
        return f"{value:,}"

    if isinstance(
        value,
        (
            float,
            Decimal,
        ),
    ):
        return f"{value:,}"

    return str(
        value
    )


def simple_result_answer_node(
    state: AgentState,
):
    """
    Build a deterministic answer for a one-row, one-column result.

    Simple scalar results do not require another LLM call.

    The answer is derived directly from the SQL result column alias
    and returned database value, avoiding unsupported interpretation
    while significantly reducing latency.
    """

    start_time = perf_counter()

    rows = state.get(
        "query_result",
        [],
    )

    row = rows[0]

    column_name, value = next(
        iter(
            row.items()
        )
    )

    label = _humanize_column_name(
        column_name
    )

    formatted_value = (
        _format_scalar_value(
            value
        )
    )

    normalized_column_name = (
        column_name
        .strip()
        .lower()
    )

    percentage_aliases = (
        "percentage",
        "percent",
        "pct",
    )

    is_percentage = any(
        alias in normalized_column_name
        for alias in percentage_aliases
    )

    if is_percentage:
        formatted_value = (
            f"{formatted_value}%"
        )

    answer = (
        f"{label}: "
        f"{formatted_value}."
    )

    _print_timing(
        "simple_result_answer",
        start_time,
    )

    return {
        "answer": answer,
    }


def final_answer_node(
    state: AgentState,
):
    """
    Turn a complex successful database result into a clear
    business answer.

    Simple one-value results can bypass this LLM call through
    simple_result_answer_node.

    Complex results continue to use Groq so they can be summarized
    naturally and accurately.
    """

    start_time = perf_counter()

    llm = get_llm()

    # Convert values such as Decimal and datetime into text that can
    # safely be included in the LLM prompt.
    query_result = json.dumps(
        state.get(
            "query_result",
            [],
        ),
        default=str,
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
User question:
{state["question"]}

Executed SQL:
{state["sql"]}

Database result:
{query_result}

The SQL executed successfully.

Use the SQL only to understand how the result was calculated.
Base all numerical claims on the database result.

Answer the user's original question directly.
"""

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    FINAL_ANSWER_SYSTEM_PROMPT
                )
            ),
            HumanMessage(
                content=prompt
            ),
        ]
    )

    _print_timing(
        "final_answer",
        start_time,
    )

    return {
        "answer": (
            response.content.strip()
        ),
    }