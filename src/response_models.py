from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """
    Structured response returned by the CommercePilot agent.
    """

    # Natural-language explanation of the query result.
    answer: str

    # Final validated SQL that was executed.
    sql: str

    # Database tables referenced by the SQL query.
    tables_used: list[str] = Field(default_factory=list)

    # Number of SQL-generation attempts made.
    attempts: int

    # Number of rows returned by the database.
    row_count: int

    # Whether the agent completed the request successfully.
    success: bool

    # Final error message when the workflow cannot succeed.
    error: str | None = None