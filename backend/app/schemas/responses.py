"""
Cortex Gateway — Shared Response Schemas.

Pydantic v2 models used across multiple endpoints.
These are intentionally lean; additional schemas belong in their
respective feature modules introduced in later phases.
"""

from typing import Literal, Optional

from pydantic import BaseModel


class RootResponse(BaseModel):
    """Response body for ``GET /``."""

    name: str
    version: str
    status: str
    description: str
    environment: str


class VersionResponse(BaseModel):
    """Response body for ``GET /version``."""

    version: str


class HealthResponse(BaseModel):
    """
    Response body for ``GET /health``.

    - ``status`` is ``"healthy"`` only when all dependencies are connected.
    - ``status`` is ``"degraded"`` when one or more dependencies are unavailable.
    """

    status: Literal["healthy", "degraded"]
    database: Literal["connected", "disconnected"]
    redis: Literal["connected", "disconnected"]
    version: str


class ErrorDetail(BaseModel):
    """Inner error object used by ``ErrorResponse``."""

    code: str
    message: str
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """
    Consistent JSON error envelope returned by global exception handlers.

    Example::

        {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "...",
                "request_id": "abc-123"
            }
        }
    """

    error: ErrorDetail
