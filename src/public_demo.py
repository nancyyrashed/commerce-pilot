"""
Lightweight safeguards for the public CommercePilot demo.

These controls are intentionally dependency-free:

- per-IP request rate limiting
- short-lived answer caching
- bounded in-memory storage

The controls are process-local. In a horizontally scaled deployment,
each application instance maintains its own limiter and cache.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, defaultdict, deque
from typing import Any


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

RATE_LIMIT_REQUESTS = int(
    os.getenv("PUBLIC_RATE_LIMIT_REQUESTS", "10")
)

RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("PUBLIC_RATE_LIMIT_WINDOW_SECONDS", "600")
)

CACHE_TTL_SECONDS = int(
    os.getenv("ANSWER_CACHE_TTL_SECONDS", "900")
)

CACHE_MAX_ENTRIES = int(
    os.getenv("ANSWER_CACHE_MAX_ENTRIES", "128")
)


# ---------------------------------------------------------
# Per-IP rate limiter
# ---------------------------------------------------------

_rate_limit_lock = threading.Lock()

_request_history: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(client_id: str) -> tuple[bool, int]:
    """
    Check whether a client may make another request.

    Returns:
        (allowed, retry_after_seconds)
    """

    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    with _rate_limit_lock:
        history = _request_history[client_id]

        # Remove requests that are outside the current window.
        while history and history[0] <= window_start:
            history.popleft()

        if len(history) >= RATE_LIMIT_REQUESTS:
            retry_after = max(
                1,
                int(
                    RATE_LIMIT_WINDOW_SECONDS
                    - (now - history[0])
                ),
            )

            return False, retry_after

        history.append(now)

        return True, 0


# ---------------------------------------------------------
# Answer cache
# ---------------------------------------------------------

_cache_lock = threading.Lock()

_answer_cache: OrderedDict[
    str,
    tuple[float, Any],
] = OrderedDict()


def normalize_question(question: str) -> str:
    """
    Normalize equivalent user questions into a stable cache key.
    """

    return " ".join(question.strip().lower().split())


def get_cached_answer(question: str) -> Any | None:
    """
    Return a cached answer when it exists and has not expired.
    """

    key = normalize_question(question)
    now = time.monotonic()

    with _cache_lock:
        cached = _answer_cache.get(key)

        if cached is None:
            return None

        created_at, value = cached

        if now - created_at > CACHE_TTL_SECONDS:
            del _answer_cache[key]
            return None

        # Move recently used entries to the end.
        _answer_cache.move_to_end(key)

        return value


def cache_answer(
    question: str,
    value: Any,
) -> None:
    """
    Cache a successful CommercePilot response.
    """

    key = normalize_question(question)

    with _cache_lock:
        _answer_cache[key] = (
            time.monotonic(),
            value,
        )

        _answer_cache.move_to_end(key)

        # Keep the cache bounded.
        while len(_answer_cache) > CACHE_MAX_ENTRIES:
            _answer_cache.popitem(last=False)


def clear_public_demo_state() -> None:
    """
    Clear rate-limit and cache state.

    Primarily useful for automated tests.
    """

    with _rate_limit_lock:
        _request_history.clear()

    with _cache_lock:
        _answer_cache.clear()