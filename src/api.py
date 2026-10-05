import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from groq import RateLimitError

from src.agent_service import run_agent
from src.api_models import AskRequest, AskResponse


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
    request: AskRequest,
) -> AskResponse:
    """
    Process one natural-language analytics request.

    Provider rate limits are returned as HTTP 429 so the frontend
    can distinguish temporary quota exhaustion from an unexpected
    server failure.
    """

    start_time = perf_counter()

    try:
        agent_result = run_agent(
            request.question
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

    return AskResponse(
        **agent_result.model_dump(),
        duration_ms=round(
            duration_ms,
            2,
        ),
    )


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