import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_llm(
    reasoning_effort: str = "medium",
):
    """
    Create the Groq chat model used by CommercePilot.

    Different agent stages can request different reasoning levels:

    - low: lightweight tasks such as request classification
      and final-answer formatting
    - medium: SQL generation, where stronger reasoning is useful

    The default remains medium so existing callers preserve
    the previous CommercePilot behavior unless they explicitly
    request a different reasoning level.
    """

    model_name = os.environ["GROQ_MODEL"]

    return ChatGroq(
        model=model_name,
        temperature=0.0,
        max_retries=2,
        reasoning_format="hidden",
        reasoning_effort=reasoning_effort,
    )