from src.agent_graph import agent_graph
from src.response_models import AgentResponse


def run_agent(question: str) -> AgentResponse:
    """
    Run the complete CommercePilot workflow and return a validated,
    structured response for the application layer.
    """

    initial_state = {
        "question": question,
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

    result = agent_graph.invoke(initial_state)

    request_type = result.get(
        "request_type",
        "answerable",
    )

    # Non-SQL routes finish directly after classification.
    if request_type in {
        "clarify",
        "unanswerable",
        "reject",
    }:
        return AgentResponse(
            answer=result.get(
                "direct_response",
                "",
            ),
            sql="",
            tables_used=[],
            attempts=0,
            row_count=0,
            success=True,
            error=None,
        )

    # Normal answerable SQL route.
    success = result.get("last_error") is None

    if success:
        answer = result.get("answer", "")
        error = None

    else:
        answer = (
            "CommercePilot could not complete this query after "
            "the allowed SQL attempts."
        )

        error = result.get("last_error")

    return AgentResponse(
        answer=answer,
        sql=result.get("sql", ""),
        tables_used=result.get(
            "tables_used",
            [],
        ),
        attempts=result.get(
            "attempts",
            0,
        ),
        row_count=len(
            result.get(
                "query_result",
                [],
            )
        ),
        success=success,
        error=error,
    )