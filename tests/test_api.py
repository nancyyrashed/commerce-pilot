from fastapi.testclient import TestClient

import src.public_demo as public_demo
from src.api import app
from src.api_models import AskResponse
from src.response_models import AgentResponse


client = TestClient(app)


def setup_function():
    """
    Start every API test with empty public-demo state.

    This prevents cached answers and rate-limit history from one
    test affecting another test.
    """

    public_demo.clear_public_demo_state()


def teardown_function():
    """
    Clear public-demo state after every API test.
    """

    public_demo.clear_public_demo_state()


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


def test_ask_uses_cached_response_without_running_agent(
    monkeypatch,
):
    """
    A cache hit should return the cached answer without calling
    the CommercePilot agent again.
    """

    cached_response = AskResponse(
        answer="There are 99,441 orders.",
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
        duration_ms=5000.0,
    )

    monkeypatch.setattr(
        "src.api.get_cached_answer",
        lambda _question: cached_response,
    )

    def fake_run_agent(_question):
        raise AssertionError(
            "run_agent() should not be called "
            "when the response is cached."
        )

    monkeypatch.setattr(
        "src.api.run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/api/ask",
        json={
            "question": (
                "How many orders are in the dataset?"
            ),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == (
        "There are 99,441 orders."
    )

    assert data["success"] is True

    # The API should replace the old cached duration with the
    # timing for this current cache-hit request.
    assert data["duration_ms"] >= 0
    assert data["duration_ms"] != 5000.0


def test_ask_caches_successful_response(
    monkeypatch,
):
    """
    A successful CommercePilot result should be stored in the
    answer cache for future identical questions.
    """

    question = (
        "How many orders are in the dataset?"
    )

    def fake_run_agent(_question):
        return AgentResponse(
            answer="There are 99,441 orders.",
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

    cached_calls = []

    def fake_cache_answer(
        cached_question,
        cached_response,
    ):
        cached_calls.append(
            (
                cached_question,
                cached_response,
            )
        )

    monkeypatch.setattr(
        "src.api.run_agent",
        fake_run_agent,
    )

    monkeypatch.setattr(
        "src.api.cache_answer",
        fake_cache_answer,
    )

    response = client.post(
        "/api/ask",
        json={
            "question": question,
        },
    )

    assert response.status_code == 200

    assert len(cached_calls) == 1

    cached_question, cached_response = (
        cached_calls[0]
    )

    assert cached_question == question
    assert cached_response.success is True
    assert cached_response.answer == (
        "There are 99,441 orders."
    )


def test_ask_returns_429_for_public_demo_rate_limit(
    monkeypatch,
):
    """
    A client that exceeds the public-demo request limit should
    receive HTTP 429 before the agent is executed.
    """

    monkeypatch.setattr(
        "src.api.check_rate_limit",
        lambda _client_id: (
            False,
            37,
        ),
    )

    def fake_run_agent(_question):
        raise AssertionError(
            "run_agent() should not be called "
            "when the client is rate limited."
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
        headers={
            "X-Forwarded-For": (
                "203.0.113.10"
            ),
        },
    )

    assert response.status_code == 429

    assert response.json() == {
        "detail": (
            "Too many requests from this "
            "client. Please try again shortly."
        )
    }

    assert (
        response.headers["retry-after"]
        == "37"
    )


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
            "question": (
                "How many orders are there?"
            ),
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
            "Origin": (
                "http://localhost:5173"
            ),
            "Access-Control-Request-Method": (
                "POST"
            ),
            "Access-Control-Request-Headers": (
                "content-type"
            ),
        },
    )

    assert response.status_code == 200

    assert (
        response.headers[
            "access-control-allow-origin"
        ]
        == "http://localhost:5173"
    )