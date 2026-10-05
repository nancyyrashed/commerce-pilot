from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """
    Request body for the CommercePilot ask endpoint.
    """

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural-language business question for CommercePilot.",
    )


class AskResponse(BaseModel):
    """
    API response returned by the CommercePilot ask endpoint.

    This extends the agent result with request timing measured
    by the FastAPI layer.
    """

    answer: str
    sql: str | None
    tables_used: list[str]
    attempts: int
    row_count: int
    success: bool
    error: str | None
    duration_ms: float