"""
Rate limiting.

A simple in-memory sliding-window limiter keyed by client IP. Sufficient
for a single-process deployment (Streamlit Community Cloud / Render free
tier); swap for a Redis-backed limiter if scaling to multiple workers.
"""

import time
from collections import defaultdict, deque

from fastapi import Request

from backend.config.settings import get_settings
from backend.utils.exceptions import RateLimitExceededError
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

_request_log: dict[str, deque] = defaultdict(deque)


def check_rate_limit(request: Request) -> None:
    """
    FastAPI dependency. Raises RateLimitExceededError (mapped to HTTP 429)
    if the client has exceeded RATE_LIMIT_REQUESTS within RATE_LIMIT_WINDOW_SECONDS.
    """
    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window_start = now - settings.RATE_LIMIT_WINDOW_SECONDS

    timestamps = _request_log[client_key]
    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()

    if len(timestamps) >= settings.RATE_LIMIT_REQUESTS:
        logger.warning("Rate limit exceeded for client %s", client_key)
        raise RateLimitExceededError(
            f"Rate limit exceeded: max {settings.RATE_LIMIT_REQUESTS} requests per "
            f"{settings.RATE_LIMIT_WINDOW_SECONDS} seconds. Please slow down."
        )

    timestamps.append(now)
