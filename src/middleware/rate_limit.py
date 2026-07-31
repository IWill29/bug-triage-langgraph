"""
Simple in-memory rate limiting for the triage API.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.utils.logging import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter scoped to POST /api/triage."""

    def __init__(self, app, max_requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method != "POST" or request.url.path != "/api/triage":
            return await call_next(request)

        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()

        with self._lock:
            timestamps = self._requests[client_key]
            cutoff = now - self.window_seconds
            self._requests[client_key] = [
                ts for ts in timestamps if ts >= cutoff
            ]
            if len(self._requests[client_key]) >= self.max_requests:
                logger.warning(
                    "rate_limit_exceeded",
                    client=client_key,
                    limit=self.max_requests,
                    window_seconds=self.window_seconds,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"Rate limit exceeded: "
                            f"{self.max_requests} requests per "
                            f"{self.window_seconds}s"
                        )
                    },
                )
            self._requests[client_key].append(now)

        return await call_next(request)
