from fastapi.testclient import TestClient

from src.api import app
from src.response_models import AgentResponse


client = TestClient(app)


def test_health_check():
    """
    The health endpoint should confirm that the API is running.
    """

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_ask_rejects_empty_question(
    monkeypatch,
):
    """
    FastAPI/Pydantic should reject an empty question before
    the CommercePilot agent is called.
    """

    def fake_run_agent(_question):
        raise AssertionError(
            "run_agent() should not be called "
            "for an invalid request."
        )

    monkeypatch.setattr(
        "src.api.run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/api/ask",
        json={
            "question": "",
        },
    )

    assert response.status_code == 422


def test_ask_returns_agent_response(
    monkeypatch,
):
    """
    A valid question should be passed to run_agent() and its
    structured result should be returned with API timing.
    """

    expected_question = (
        "How many orders are in the dataset?"
    )

    def fake_run_agent(question):
        assert question == expected_question

        return AgentResponse(
            answer=(
                "There are 99,441 orders "
                "in the dataset."
            ),
            sql=(
                "SELECT COUNT(*) AS total_orders "
                "FROM orders LIMIT 100"
            ),
            tables_used=[
                "orders",
            ],
            attempts=1,
            row_count=1,
            success=True,
            error=None,
        )

    monkeypatch.setattr(
        "src.api.run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/api/ask",
        json={
            "question": expected_question,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == (
        "There are 99,441 orders "
        "in the dataset."
    )
    assert data["sql"] == (
        "SELECT COUNT(*) AS total_orders "
        "FROM orders LIMIT 100"
    )
    assert data["tables_used"] == [
        "orders",
    ]
    assert data["attempts"] == 1
    assert data["row_count"] == 1
    assert data["success"] is True
    assert data["error"] is None

    assert isinstance(
        data["duration_ms"],
        (int, float),
    )
    assert data["duration_ms"] >= 0


def test_ask_returns_429_for_provider_rate_limit(
    monkeypatch,
):
    """
    A temporary Groq rate-limit failure should return HTTP 429
    with a safe user-facing message instead of appearing as an
    unexpected HTTP 500 server failure.

    The provider exception is mocked, so this test makes no
    external Groq request.
    """

    class FakeRateLimitError(Exception):
        pass

    def fake_run_agent(_question):
        raise FakeRateLimitError(
            "Rate limit reached."
        )

    # Replace the exception class referenced by src.api so the
    # handler can be tested without constructing a real Groq
    # HTTP response object.
    monkeypatch.setattr(
        "src.api.RateLimitError",
        FakeRateLimitError,
    )

    monkeypatch.setattr(
        "src.api.run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/api/ask",
        json={
            "question": (
                "How many orders are there?"
            ),
        },
    )

    assert response.status_code == 429

    assert response.json() == {
        "detail": (
            "The AI service rate limit has "
            "been reached. Please try again "
            "shortly."
        )
    }

    # Provider implementation details should not be exposed.
    assert "Groq" not in response.text
    assert "RateLimitError" not in response.text


def test_ask_hides_unexpected_internal_error(
    monkeypatch,
):
    """
    Unexpected internal exceptions should produce a generic
    HTTP 500 response instead of exposing implementation or
    credential details to the client.
    """

    def fake_run_agent(_question):
        raise RuntimeError(
            "DATABASE_PASSWORD=secret-value"
        )

    monkeypatch.setattr(
        "src.api.run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/api/ask",
        json={
            "question": "How many orders are there?",
        },
    )

    assert response.status_code == 500

    data = response.json()

    assert data == {
        "detail": (
            "CommercePilot could not process the "
            "request due to an internal error."
        )
    }

    assert "secret-value" not in response.text
    assert "DATABASE_PASSWORD" not in response.text


def test_cors_allows_local_vite_origin():
    """
    The local Vite development origin should be allowed
    to call the FastAPI backend during frontend development.
    """

    response = client.options(
        "/api/ask",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200

    assert (
        response.headers[
            "access-control-allow-origin"
        ]
        == "http://localhost:5173"
    )