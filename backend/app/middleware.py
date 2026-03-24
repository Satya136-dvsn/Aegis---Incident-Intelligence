"""
Aegis Backend — Custom Middleware

Request-ID injection for distributed tracing,
request timing, and structured logging per request.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Inject a unique ``X-Request-ID`` header into every response.

    If the client provides one, it is reused; otherwise a UUID4 is generated.
    The ID is also bound to structlog context for the lifetime of the request.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind the ID to structlog so every log line within this request
        # automatically includes it — crucial for production debugging.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        await logger.ainfo(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        return response
