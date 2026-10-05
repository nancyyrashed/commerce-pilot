from langgraph.graph import END, START, StateGraph

from src.agent_nodes import (
    classify_and_generate_sql_node,
    execute_sql_node,
    final_answer_node,
    generate_sql_node,
    inspect_schema_node,
    simple_result_answer_node,
)
from src.agent_state import AgentState


# Maximum number of SQL-generation attempts before stopping.
MAX_ATTEMPTS = 3


def route_after_plan(
    state: AgentState,
):
    """
    Decide whether the planned request should continue to SQL execution.

    Only answerable requests continue to SQL validation/execution.

    Clarification, unanswerable, and rejected requests stop with the
    planner's direct_response.
    """

    if state["request_type"] == "answerable":
        return "answerable"

    return "direct_response"


def route_after_execution(
    state: AgentState,
):
    """
    Decide what should happen after SQL execution.

    - Failed query with attempts remaining -> repair SQL.
    - Failed query after MAX_ATTEMPTS -> stop.
    - Successful one-row, one-column result -> deterministic fast answer.
    - Other successful results -> Groq final-answer generation.
    """

    if state.get("last_error"):

        if (
            state.get(
                "attempts",
                0,
            )
            < MAX_ATTEMPTS
        ):
            return "retry"

        return "failed"

    query_result = state.get(
        "query_result",
        [],
    )

    # A single database value can be presented safely without
    # another LLM call.
    if (
        len(query_result) == 1
        and isinstance(
            query_result[0],
            dict,
        )
        and len(query_result[0]) == 1
    ):
        return "simple_result"

    return "complex_result"


def build_agent_graph():
    """
    Build and compile the optimized CommercePilot LangGraph workflow.

    The graph uses:
    - cached schema inspection,
    - one combined classification + initial SQL LLM call,
    - deterministic formatting for simple scalar results,
    - Groq final-answer generation only for more complex results,
    - bounded SQL repair retries.
    """

    workflow = StateGraph(
        AgentState
    )

    # Register workflow nodes.
    workflow.add_node(
        "inspect_schema",
        inspect_schema_node,
    )

    workflow.add_node(
        "classify_and_generate_sql",
        classify_and_generate_sql_node,
    )

    workflow.add_node(
        "generate_sql",
        generate_sql_node,
    )

    workflow.add_node(
        "execute_sql",
        execute_sql_node,
    )

    workflow.add_node(
        "simple_result_answer",
        simple_result_answer_node,
    )

    workflow.add_node(
        "final_answer",
        final_answer_node,
    )

    # Load the schema first.
    #
    # After the first request, the schema context is served from the
    # in-process cache rather than being rebuilt from PostgreSQL.
    workflow.add_edge(
        START,
        "inspect_schema",
    )

    # Classification and initial SQL generation happen in one
    # LLM request.
    workflow.add_edge(
        "inspect_schema",
        "classify_and_generate_sql",
    )

    # Only answerable requests proceed to SQL execution.
    workflow.add_conditional_edges(
        "classify_and_generate_sql",
        route_after_plan,
        {
            "answerable": "execute_sql",
            "direct_response": END,
        },
    )

    # Route based on execution success and result complexity.
    workflow.add_conditional_edges(
        "execute_sql",
        route_after_execution,
        {
            "retry": "generate_sql",
            "simple_result": (
                "simple_result_answer"
            ),
            "complex_result": "final_answer",
            "failed": END,
        },
    )

    # Repaired SQL returns to the same safe execution path.
    workflow.add_edge(
        "generate_sql",
        "execute_sql",
    )

    # Both answer-generation paths complete the workflow.
    workflow.add_edge(
        "simple_result_answer",
        END,
    )

    workflow.add_edge(
        "final_answer",
        END,
    )

    return workflow.compile()


# Compiled graph used by the application.
agent_graph = build_agent_graph()