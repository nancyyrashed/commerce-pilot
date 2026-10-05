import argparse
import json
import re
import time

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from src.agent_graph import MAX_ATTEMPTS
from src.agent_nodes import (
    execute_sql_node,
    generate_sql_node,
    inspect_schema_node,
)
from src.database_tools import run_query


PROJECT_ROOT = Path(__file__).resolve().parent.parent

QUESTIONS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "eval_questions.json"
)

REFERENCE_QUERIES_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "reference_queries.json"
)

RESULTS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "answerable_results.json"
)


DEFAULT_CASE_DELAY_SECONDS = 8.0
DEFAULT_PROVIDER_RETRIES = 3
DEFAULT_PROVIDER_RETRY_DELAY_SECONDS = 3.0


def is_provider_error(error):
    """
    Identify temporary LLM-provider or network failures.

    Provider/infrastructure failures should be retried and should not
    count as model accuracy failures if they cannot be completed.
    """

    error_name = type(error).__name__.lower()
    message = str(error).lower()

    provider_error_names = (
        "apiconnectionerror",
        "ratelimiterror",
        "apitimeouterror",
        "connecterror",
        "readtimeout",
        "connecttimeout",
    )

    provider_error_messages = (
        "connection error",
        "rate limit",
        "429",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
        "server disconnected",
    )

    return (
        any(
            name in error_name
            for name in provider_error_names
        )
        or any(
            marker in message
            for marker in provider_error_messages
        )
    )


def load_answerable_cases():
    """
    Load only evaluation cases that are expected to be answerable
    through SQL.
    """

    with QUESTIONS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        questions = json.load(file)

    return [
        case
        for case in questions
        if case["expected_behavior"] == "answer"
    ]


def load_reference_queries():
    """
    Load the hand-written reference SQL queries.

    Supports reference files where each case is stored either as a
    direct SQL string or as an object containing an SQL field.
    """

    with REFERENCE_QUERIES_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    references = {}

    if isinstance(data, dict):

        for case_id, value in data.items():

            if isinstance(value, str):
                references[case_id] = value
                continue

            if isinstance(value, dict):
                sql = (
                    value.get("sql")
                    or value.get("reference_sql")
                    or value.get("query")
                )

                if not sql:
                    raise ValueError(
                        f"Reference SQL missing for {case_id}"
                    )

                references[case_id] = sql
                continue

            raise ValueError(
                f"Unsupported reference format for {case_id}"
            )

        return references

    if isinstance(data, list):

        for item in data:
            case_id = item["id"]

            sql = (
                item.get("sql")
                or item.get("reference_sql")
                or item.get("query")
            )

            if not sql:
                raise ValueError(
                    f"Reference SQL missing for {case_id}"
                )

            references[case_id] = sql

        return references

    raise ValueError(
        "Unsupported reference_queries.json format."
    )


def normalize_text(value):
    """
    Normalize harmless formatting differences in categorical text.

    Examples:

        "Late"     -> "late"
        "late"     -> "late"

        "On-time"  -> "on_time"
        "on_time"  -> "on_time"
        "on time"  -> "on_time"

    This prevents cosmetic text-label differences from causing an
    otherwise correct analytical result to fail.
    """

    value = value.strip().lower()

    # Treat whitespace, hyphens, and underscores as equivalent
    # separators.
    value = re.sub(
        r"[\s_-]+",
        "_",
        value,
    )

    return value


def normalize_value(value):
    """
    Convert a database value into a stable comparable representation.

    Numeric values are rounded to two decimal places because differences
    beyond two decimal places are not meaningful for this benchmark.

    Text values are normalized for capitalization and separator style.
    """

    if value is None:
        return (
            "none",
            None,
        )

    # bool must be checked before int because bool is a subclass of int.
    if isinstance(value, bool):
        return (
            "bool",
            value,
        )

    if isinstance(value, Decimal):
        return (
            "number",
            value.quantize(
                Decimal("0.01")
            ),
        )

    if isinstance(value, int):
        return (
            "number",
            Decimal(value).quantize(
                Decimal("0.01")
            ),
        )

    if isinstance(value, float):
        return (
            "number",
            Decimal(
                str(value)
            ).quantize(
                Decimal("0.01")
            ),
        )

    if isinstance(value, datetime):
        # Treat a midnight datetime as equivalent to the same calendar
        # date. PostgreSQL DATE_TRUNC('month', ...) commonly returns a
        # timestamp at 00:00:00, while another valid query may CAST it
        # to DATE.
        if value.time() == datetime.min.time():
            return (
                "date",
                value.date().isoformat(),
            )

        return (
            "datetime",
            value.isoformat(),
        )

    if isinstance(value, date):
        return (
            "date",
            value.isoformat(),
        )

    if isinstance(value, str):
        return (
            "text",
            normalize_text(value),
        )

    return (
        "other",
        str(value),
    )


def normalize_row(row):
    """
    Normalize one result row while intentionally ignoring SQL aliases.

    The benchmark is intended to measure the analytical result rather
    than whether the model chose exactly the same column aliases as the
    hand-written reference SQL.

    Counter is used so duplicate values within a row are still handled
    correctly.
    """

    return Counter(
        normalize_value(value)
        for value in row.values()
    )


def row_contains_reference_values(
    reference_row,
    generated_row,
):
    """
    Check whether a generated row contains every value required by the
    corresponding reference row.

    Extra generated columns are allowed.

    Example:

    Reference:
        seller_id
        percentage

    Generated:
        seller_id
        sales_value
        percentage

    The extra sales_value column should not cause the result to fail.
    """

    for value, required_count in reference_row.items():

        if (
            generated_row[value]
            < required_count
        ):
            return False

    return True


def results_match(
    reference_rows,
    generated_rows,
):
    """
    Compare reference and generated query results semantically.

    Evaluation rules:

    - Row order does not matter.
    - SQL column aliases do not matter.
    - Extra generated columns are allowed.
    - The number of rows must match.
    - Numeric values are compared at two decimal places.
    - Cosmetic categorical-label differences are ignored.
    - Every reference row must match exactly one generated row.

    A small bipartite matching search is used instead of a greedy
    comparison so duplicate or similar rows are handled correctly.
    """

    if len(reference_rows) != len(
        generated_rows
    ):
        return False

    normalized_reference = [
        normalize_row(row)
        for row in reference_rows
    ]

    normalized_generated = [
        normalize_row(row)
        for row in generated_rows
    ]

    # Stores the reference row currently assigned to each generated row.
    generated_matches = [
        None
        for _ in normalized_generated
    ]

    def try_match(
        reference_index,
        visited_generated,
    ):
        """
        Attempt to assign one reference row to one compatible generated
        row.

        Existing assignments may be moved when necessary.
        """

        reference_row = (
            normalized_reference[
                reference_index
            ]
        )

        for (
            generated_index,
            generated_row,
        ) in enumerate(
            normalized_generated
        ):

            if (
                generated_index
                in visited_generated
            ):
                continue

            if not row_contains_reference_values(
                reference_row,
                generated_row,
            ):
                continue

            visited_generated.add(
                generated_index
            )

            previous_reference = (
                generated_matches[
                    generated_index
                ]
            )

            if (
                previous_reference is None
                or try_match(
                    previous_reference,
                    visited_generated,
                )
            ):
                generated_matches[
                    generated_index
                ] = reference_index

                return True

        return False

    # Match rows containing the most information first.
    reference_order = sorted(
        range(
            len(
                normalized_reference
            )
        ),
        key=lambda index: -sum(
            normalized_reference[
                index
            ].values()
        ),
    )

    for reference_index in reference_order:

        if not try_match(
            reference_index,
            set(),
        ):
            return False

    return True


def generate_sql_with_provider_retry(
    state,
    provider_retries,
    retry_delay,
):
    """
    Call the SQL-generation node while retrying temporary Groq/network
    errors.

    Provider failures are different from invalid SQL execution attempts.
    """

    for provider_attempt in range(
        provider_retries + 1
    ):

        try:
            return generate_sql_node(
                state
            )

        except Exception as error:

            if not is_provider_error(
                error
            ):
                raise

            if (
                provider_attempt
                >= provider_retries
            ):
                raise

            retry_number = (
                provider_attempt + 1
            )

            print(
                "  Temporary provider error. "
                f"Retrying "
                f"({retry_number}/"
                f"{provider_retries})..."
            )

            time.sleep(
                retry_delay
                * retry_number
            )


def build_initial_state(
    question,
    schema_context,
):
    """
    Build the state used by the SQL-generation/execution evaluation
    loop.

    The answerable evaluator intentionally starts after request
    classification because classification is measured separately.
    """

    return {
        "question": question,
        "request_type": "answerable",
        "direct_response": "",
        "schema_context": schema_context,
        "sql": "",
        "query_result": [],
        "tables_used": [],
        "attempts": 0,
        "last_error": None,
        "answer": "",
    }


def generate_and_execute(
    question,
    schema_context,
    provider_retries,
    retry_delay,
):
    """
    Generate SQL and execute it through the same safe database tool used
    by CommercePilot.

    SQL execution failures are fed back to the generation node for
    repair until MAX_ATTEMPTS is reached.
    """

    state = build_initial_state(
        question=question,
        schema_context=schema_context,
    )

    while (
        state["attempts"]
        < MAX_ATTEMPTS
    ):

        generation_update = (
            generate_sql_with_provider_retry(
                state=state,
                provider_retries=provider_retries,
                retry_delay=retry_delay,
            )
        )

        state.update(
            generation_update
        )

        execution_update = (
            execute_sql_node(
                state
            )
        )

        state.update(
            execution_update
        )

        if not state.get(
            "last_error"
        ):
            break

    return state


def inspect_schema_once():
    """
    Inspect the database schema once and reuse it across the benchmark.

    This avoids repeating the same deterministic database work for every
    evaluation question.
    """

    state = {
        "question": "",
        "request_type": "answerable",
        "direct_response": "",
        "schema_context": "",
        "sql": "",
        "query_result": [],
        "tables_used": [],
        "attempts": 0,
        "last_error": None,
        "answer": "",
    }

    result = inspect_schema_node(
        state
    )

    return result[
        "schema_context"
    ]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate CommercePilot on answerable "
            "text-to-SQL questions."
        )
    )

    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help=(
            "Skip the first N answerable "
            "evaluation cases."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Evaluate only the first N remaining "
            "answerable cases."
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_CASE_DELAY_SECONDS,
        help=(
            "Seconds to wait between evaluation "
            "cases."
        ),
    )

    parser.add_argument(
        "--provider-retries",
        type=int,
        default=DEFAULT_PROVIDER_RETRIES,
        help=(
            "Number of retries for temporary "
            "provider/network failures."
        ),
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=(
            DEFAULT_PROVIDER_RETRY_DELAY_SECONDS
        ),
        help=(
            "Base number of seconds to wait "
            "between provider retries."
        ),
    )

    args = parser.parse_args()

    cases = load_answerable_cases()
    references = load_reference_queries()

    cases = cases[
        args.start:
    ]

    if args.limit is not None:
        cases = cases[
            : args.limit
        ]

    print(
        "Inspecting database schema once..."
    )

    schema_context = (
        inspect_schema_once()
    )

    print(
        f"Evaluating {len(cases)} "
        "answerable cases...\n"
    )

    results = []

    passed = 0
    failed = 0
    infrastructure_errors = 0

    for index, case in enumerate(
        cases,
        start=1,
    ):
        case_id = case["id"]
        question = case["question"]

        expected_tables = (
            case.get(
                "expected_tables",
                [],
            )
        )

        print(
            f"[{index}/{len(cases)}] "
            f"{case_id}: "
            f"{question}"
        )

        reference_sql = (
            references.get(
                case_id
            )
        )

        if not reference_sql:
            raise ValueError(
                "No reference SQL found for "
                f"{case_id}"
            )

        try:
            # Execute the hand-written reference SQL.
            reference_execution = (
                run_query(
                    reference_sql
                )
            )

            reference_rows = (
                reference_execution[
                    "rows"
                ]
            )

            # Generate and execute the model SQL.
            generated_state = (
                generate_and_execute(
                    question=question,
                    schema_context=schema_context,
                    provider_retries=(
                        args.provider_retries
                    ),
                    retry_delay=(
                        args.retry_delay
                    ),
                )
            )

            generated_sql = (
                generated_state.get(
                    "sql",
                    "",
                )
            )

            generated_rows = (
                generated_state.get(
                    "query_result",
                    [],
                )
            )

            tables_used = (
                generated_state.get(
                    "tables_used",
                    [],
                )
            )

            attempts = (
                generated_state.get(
                    "attempts",
                    0,
                )
            )

            last_error = (
                generated_state.get(
                    "last_error"
                )
            )

            execution_succeeded = (
                last_error is None
            )

            expected_tables_used = (
                set(
                    expected_tables
                ).issubset(
                    set(
                        tables_used
                    )
                )
            )

            result_values_match = False

            if execution_succeeded:
                result_values_match = (
                    results_match(
                        reference_rows,
                        generated_rows,
                    )
                )

            correct = (
                execution_succeeded
                and expected_tables_used
                and result_values_match
            )

            result_record = {
                "id": case_id,
                "category": case[
                    "category"
                ],
                "question": question,
                "correct": correct,
                "scored": True,
                "infrastructure_error": False,
                "execution_succeeded": (
                    execution_succeeded
                ),
                "attempts": attempts,
                "generated_sql": (
                    generated_sql
                ),
                "tables_used": (
                    tables_used
                ),
                "expected_tables": (
                    expected_tables
                ),
                "expected_tables_used": (
                    expected_tables_used
                ),
                "reference_row_count": len(
                    reference_rows
                ),
                "generated_row_count": len(
                    generated_rows
                ),
                "error": last_error,
            }

            if correct:
                passed += 1

                print(
                    "  PASS"
                )

            else:
                failed += 1

                print(
                    "  FAIL"
                )

                if not execution_succeeded:
                    print(
                        "  SQL execution failed."
                    )

                    print(
                        f"  Error: {last_error}"
                    )

                elif not expected_tables_used:
                    print(
                        "  Expected table(s) "
                        "were not used."
                    )

                    print(
                        "  Expected: "
                        f"{expected_tables}"
                    )

                    print(
                        "  Used:     "
                        f"{tables_used}"
                    )

                elif not result_values_match:
                    print(
                        "  Generated result "
                        "does not match the "
                        "reference result."
                    )

                print(
                    f"  SQL: {generated_sql}"
                )

        except Exception as error:
            infrastructure_error = (
                is_provider_error(
                    error
                )
            )

            if infrastructure_error:
                infrastructure_errors += 1

                print(
                    "  INFRASTRUCTURE ERROR "
                    "(excluded from accuracy)"
                )

            else:
                failed += 1

                print(
                    "  FAIL"
                )

            print(
                f"  Error: {error}"
            )

            result_record = {
                "id": case_id,
                "category": case[
                    "category"
                ],
                "question": question,
                "correct": False,
                "scored": (
                    not infrastructure_error
                ),
                "infrastructure_error": (
                    infrastructure_error
                ),
                "execution_succeeded": False,
                "attempts": 0,
                "generated_sql": "",
                "tables_used": [],
                "expected_tables": (
                    expected_tables
                ),
                "expected_tables_used": False,
                "reference_row_count": 0,
                "generated_row_count": 0,
                "error": str(
                    error
                ),
            }

        results.append(
            result_record
        )

        print()

        if (
            index < len(cases)
            and args.delay > 0
        ):
            time.sleep(
                args.delay
            )

    scored_cases = (
        passed + failed
    )

    accuracy = (
        passed / scored_cases
        if scored_cases
        else 0.0
    )

    output = {
        "summary": {
            "total_cases": len(
                cases
            ),
            "scored_cases": (
                scored_cases
            ),
            "passed": passed,
            "failed": failed,
            "infrastructure_errors": (
                infrastructure_errors
            ),
            "execution_accuracy": (
                accuracy
            ),
        },
        "results": results,
    }

    with RESULTS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        "Evaluation complete."
    )

    print(
        f"Total cases: "
        f"{len(cases)}"
    )

    print(
        f"Scored cases: "
        f"{scored_cases}"
    )

    print(
        f"Passed: {passed}"
    )

    print(
        f"Failed: {failed}"
    )

    print(
        "Infrastructure errors: "
        f"{infrastructure_errors}"
    )

    if scored_cases:
        print(
            "Execution accuracy: "
            f"{accuracy:.2%}"
        )

    else:
        print(
            "Execution accuracy: "
            "not available"
        )

    print(
        "Results saved to: "
        f"{RESULTS_FILE}"
    )


if __name__ == "__main__":
    main()