"""
Cortex Gateway — Request ID Middleware.

1. Reads ``X-Request-ID`` from incoming request headers.
2. Generates a UUID v4 if no header is present.
3. Stores the ID in a ``ContextVar`` so downstream code can access it without
   explicit parameter threading.
4. Injects the ID into every response as ``X-Request-ID``.

Usage (anywhere in the application)::

    from app.middleware.request_id import get_request_id
    request_id = get_request_id()
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Module-level context variable — one value per async task (i.e., per request).
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

REQUEST_ID_HEADER = "X-Request-ID"


def get_request_id() -> str:
    """Return the current request ID from the context variable."""
    return _request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that ensures every request has an associated request ID.
    The ID is:
    - Read from ``X-Request-ID`` if provided by the caller.
    - Auto-generated as a UUID v4 otherwise.
    - Stored in a ``ContextVar`` for use anywhere in the call stack.
    - Added to the response under ``X-Request-ID``.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        token = _request_id_ctx.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            _request_id_ctx.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
