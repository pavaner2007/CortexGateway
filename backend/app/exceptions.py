"""
Cortex Gateway — Global Exception Handlers.

Registers three handlers on the FastAPI application:

1. ``RequestValidationError``  →  422 Unprocessable Entity
2. ``HTTPException``           →  Propagated status code
3. ``Exception`` (catch-all)   →  500 Internal Server Error

All responses share the ``{"error": {"code": ..., "message": ...,
"request_id": ...}}`` envelope so clients always get a predictable shape.

Policy:
- Never expose Python stack traces in responses.
- Never expose internal exception details to external callers.
- Never expose database connection strings or secrets.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger
from app.middleware.request_id import get_request_id
from app.schemas.responses import ErrorDetail, ErrorResponse


def _error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI application."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = get_request_id()
        # Include structured validation details but never raw internal data
        errors = exc.errors()
        readable = "; ".join(
            f"{' -> '.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', '')}"
            for e in errors
        )
        logger.warning(
            "Request validation error",
            request_id=request_id,
            path=str(request.url.path),
            errors=readable,
        )
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=readable or "Request validation failed.",
            request_id=request_id,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = get_request_id()
        # Map status code to a stable error code string
        code = str(exc.status_code)
        http_codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_SERVER_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
        }
        code = http_codes.get(exc.status_code, f"HTTP_{exc.status_code}")
        logger.warning(
            "HTTP exception",
            request_id=request_id,
            path=str(request.url.path),
            status=exc.status_code,
            detail=str(exc.detail),
        )
        return _error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            request_id=request_id,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = get_request_id()
        # Log the full exception internally but never expose it externally
        logger.exception(
            "Unhandled exception",
            request_id=request_id,
            path=str(request.url.path),
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred.",
            request_id=request_id,
        )
