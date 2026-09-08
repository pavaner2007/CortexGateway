"""
Cortex Gateway — Request / Response Logging Middleware.

Logs safe metadata for every HTTP request:
  - Timestamp (provided automatically by Loguru)
  - Request ID (from ContextVar set by RequestIDMiddleware)
  - HTTP method
  - URL path
  - HTTP status code
  - Request duration (ms)
  - Client IP (X-Forwarded-For → client host fallback)

NOT logged (by policy):
  - Request / response bodies
  - Authorization, Cookie, or other sensitive headers
  - Secrets or environment-variable values
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import logger
from app.middleware.request_id import get_request_id


def _safe_client_ip(request: Request) -> str:
    """Return the best-available client IP without exposing proxy internals."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take only the first (original client) address
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log one structured line per HTTP request after the response is produced."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        request_id = get_request_id()

        log_level = "WARNING" if response.status_code >= 400 else "INFO"

        logger.log(
            log_level,
            "{method} {path} {status} {duration}ms [{request_id}]",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration=duration_ms,
            request_id=request_id,
            client_ip=_safe_client_ip(request),
        )

        return response
