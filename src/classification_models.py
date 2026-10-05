from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestClassification(BaseModel):
    """
    Structured decision returned by CommercePilot's standalone
    request classifier.

    This model is retained for the classification evaluation
    workflow and any tests that classify requests independently
    from SQL generation.
    """

    # Reject any unexpected fields returned by the model.
    model_config = ConfigDict(
        extra="forbid",
    )

    request_type: Literal[
        "answerable",
        "clarify",
        "unanswerable",
        "reject",
    ] = Field(
        description=(
            "How CommercePilot should route the user's request."
        )
    )

    direct_response: str = Field(
        description=(
            "User-facing response when SQL should not be generated. "
            "Use an empty string when request_type is 'answerable'."
        )
    )


class RequestPlan(BaseModel):
    """
    Structured result returned by CommercePilot's combined
    request-classification and initial SQL-generation step.

    Answerable requests include SQL immediately.

    Clarification, unanswerable, and rejected requests return a
    direct user-facing response and no SQL.
    """

    # Reject any unexpected fields returned by the model.
    model_config = ConfigDict(
        extra="forbid",
    )

    request_type: Literal[
        "answerable",
        "clarify",
        "unanswerable",
        "reject",
    ] = Field(
        description=(
            "How CommercePilot should route the user's request."
        )
    )

    direct_response: str = Field(
        description=(
            "User-facing response when request_type is not "
            "'answerable'. Use an empty string for answerable "
            "requests."
        )
    )

    sql: str | None = Field(
        description=(
            "Exactly one PostgreSQL SELECT query when request_type "
            "is 'answerable'. Use null for clarify, unanswerable, "
            "and reject requests."
        )
    )