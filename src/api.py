import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from groq import RateLimitError

from src.agent_service import run_agent
from src.api_models import AskRequest, AskResponse
from src.public_demo import (
    cache_answer,
    check_rate_limit,
    get_cached_answer,
)


logger = logging.getLogger(
    "commercepilot.api"
)

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

FRONTEND_DIST = (
    PROJECT_ROOT
    / "frontend"
    / "dist"
)

FRONTEND_INDEX = (
    FRONTEND_DIST
    / "index.html"
)

FRONTEND_ASSETS = (
    FRONTEND_DIST
    / "assets"
)


app = FastAPI(
    title="CommercePilot API",
    description=(
        "Backend API for the CommercePilot "
        "natural-language-to-SQL analytics agent."
    ),
    version="0.1.0",
)


# Allow the Vite development server to call FastAPI while
# developing the frontend locally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
    ],
)


# Serve Vite's compiled static assets in production.
#
# The directory is mounted only when it exists so backend tests
# and development environments do not require a frontend build
# before FastAPI can start.
if FRONTEND_ASSETS.exists():
    app.mount(
        "/assets",
        StaticFiles(
            directory=FRONTEND_ASSETS
        ),
        name="frontend-assets",
    )


def get_client_identifier(
    request: Request,
) -> str:
    """
    Return a stable identifier for the requesting client.

    Production reverse proxies such as Vercel provide the original
    client address through X-Forwarded-For. Local development falls
    back to the direct connection address.
    """

    forwarded_for = request.headers.get(
        "x-forwarded-for"
    )

    if forwarded_for:
        client_ip = (
            forwarded_for
            .split(",")[0]
            .strip()
        )

        if client_ip:
            return client_ip

    if request.client is not None:
        return request.client.host

    return "unknown"


@app.get(
    "/health",
    tags=["system"],
)
def health_check() -> dict[str, str]:
    """
    Lightweight service health check.
    """

    return {
        "status": "ok",
    }


@app.post(
    "/api/ask",
    response_model=AskResponse,
    tags=["analytics"],
)
def ask_commercepilot(
    payload: AskRequest,
    http_request: Request,
) -> AskResponse:
    """
    Process one natural-language analytics request.

    Public-demo safeguards apply a lightweight per-client rate
    limit and reuse recent successful answers when the same
    normalized question is asked again.

    Provider rate limits are returned as HTTP 429 so the frontend
    can distinguish temporary quota exhaustion from an unexpected
    server failure.
    """

    start_time = perf_counter()

    # ---------------------------------------------------------
    # Public-demo rate limit
    # ---------------------------------------------------------

    client_id = get_client_identifier(
        http_request
    )

    allowed, retry_after = check_rate_limit(
        client_id
    )

    if not allowed:
        logger.warning(
            (
                "CommercePilot public-demo rate "
                "limit reached for client=%s."
            ),
            client_id,
        )

        raise HTTPException(
            status_code=429,
            detail=(
                "Too many requests from this "
                "client. Please try again shortly."
            ),
            headers={
                "Retry-After": str(
                    retry_after
                ),
            },
        )

    # ---------------------------------------------------------
    # Answer cache
    # ---------------------------------------------------------

    cached_response = get_cached_answer(
        payload.question
    )

    if cached_response is not None:
        duration_ms = (
            perf_counter() - start_time
        ) * 1000

        logger.info(
            (
                "CommercePilot cache hit: "
                "client=%s duration_ms=%.2f"
            ),
            client_id,
            duration_ms,
        )

        # Update the request-duration field so it represents the
        # current cached request rather than the original request.
        return cached_response.model_copy(
            update={
                "duration_ms": round(
                    duration_ms,
                    2,
                ),
            }
        )

    # ---------------------------------------------------------
    # Agent execution
    # ---------------------------------------------------------

    try:
        agent_result = run_agent(
            payload.question
        )

    except RateLimitError:
        duration_ms = (
            perf_counter() - start_time
        ) * 1000

        logger.warning(
            (
                "CommercePilot request hit the "
                "Groq rate limit after %.2f ms."
            ),
            duration_ms,
        )

        raise HTTPException(
            status_code=429,
            detail=(
                "The AI service rate limit has "
                "been reached. Please try again "
                "shortly."
            ),
        )

    except Exception:
        duration_ms = (
            perf_counter() - start_time
        ) * 1000

        logger.exception(
            (
                "CommercePilot request failed "
                "unexpectedly after %.2f ms."
            ),
            duration_ms,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "CommercePilot could not process "
                "the request due to an internal "
                "error."
            ),
        )

    duration_ms = (
        perf_counter() - start_time
    ) * 1000

    response = AskResponse(
        **agent_result.model_dump(),
        duration_ms=round(
            duration_ms,
            2,
        ),
    )

    # Cache only successful agent responses. Failed executions
    # should be allowed to run again rather than preserving an
    # error result for the cache lifetime.
    if response.success:
        cache_answer(
            payload.question,
            response,
        )

    logger.info(
        (
            "CommercePilot request completed: "
            "success=%s attempts=%s rows=%s "
            "duration_ms=%.2f"
        ),
        agent_result.success,
        agent_result.attempts,
        agent_result.row_count,
        duration_ms,
    )

    return response


@app.get(
    "/",
    include_in_schema=False,
)
def serve_frontend():
    """
    Serve the compiled React application.

    In production, Vite builds the frontend into frontend/dist.
    FastAPI then serves that build so CommercePilot can run as
    a single web service.
    """

    if not FRONTEND_INDEX.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Frontend build is not available. "
                "Run 'npm run build' inside the "
                "frontend directory."
            ),
        )

    return FileResponse(
        FRONTEND_INDEX
    )