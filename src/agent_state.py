from typing import Any, Literal, TypedDict


class AgentState(TypedDict):
    """
    Shared state carried through the CommercePilot LangGraph workflow.
    """

    # Original natural-language question from the user.
    question: str

    # Classification assigned before SQL generation.
    #
    # answerable:
    #   The database contains enough information to answer the question.
    #
    # clarify:
    #   The question is ambiguous and needs more information from the user.
    #
    # unanswerable:
    #   The requested information is not available in the dataset.
    #
    # reject:
    #   The request attempts a prohibited or unsafe database operation.
    request_type: Literal[
        "answerable",
        "clarify",
        "unanswerable",
        "reject",
    ]

    # Direct response used when SQL should not be generated.
    #
    # Examples:
    # - clarification question
    # - explanation of missing dataset information
    # - rejection of a prohibited database action
    direct_response: str

    # Database/schema information gathered for SQL generation.
    schema_context: str

    # SQL produced by the LLM.
    sql: str

    # Rows returned by PostgreSQL after safe execution.
    query_result: list[dict[str, Any]]

    # Database tables used by the generated SQL.
    tables_used: list[str]

    # Number of SQL-generation/execution attempts made.
    attempts: int

    # Most recent validation or database error.
    last_error: str | None

    # Natural-language answer produced after a successful query.
    answer: str