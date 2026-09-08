"""
Cortex Gateway — System Endpoints.

Provides:
- ``GET /``        — Root info (name, version, status)
- ``GET /version`` — Application version from settings
- ``GET /health``  — PostgreSQL + Redis health (independent checks)

Health checks run concurrently with ``asyncio.gather``.
A degraded response (HTTP 503) is returned when any dependency is unavailable.
The application never crashes due to a failed health check.
"""

import asyncio

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.database.session import check_db_health
from app.schemas.responses import HealthResponse, RootResponse, VersionResponse
from app.utils.redis_client import check_redis_health

router = APIRouter()
settings = get_settings()


@router.get(
    "/",
    response_model=RootResponse,
    summary="Root",
    description="Returns basic application information.",
    tags=["System"],
)
async def root() -> RootResponse:
    return RootResponse(
        name=settings.app_name,
        version=settings.app_version,
        status="running",
        description=settings.app_description,
        environment=settings.environment,
    )


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Version",
    description="Returns the application version from centralized settings.",
    tags=["System"],
)
async def version() -> VersionResponse:
    return VersionResponse(version=settings.app_version)


@router.get(
    "/health",
    summary="Health Check",
    description=(
        "Independently checks PostgreSQL and Redis connectivity. "
        "Returns HTTP 200 when all dependencies are healthy, "
        "HTTP 503 when any dependency is unavailable."
    ),
    tags=["System"],
    responses={
        200: {"description": "All dependencies healthy"},
        503: {"description": "One or more dependencies unavailable"},
    },
)
async def health() -> JSONResponse:
    # Run both checks concurrently — never let one failure abort the other.
    db_status, redis_status = await asyncio.gather(
        check_db_health(),
        check_redis_health(),
        return_exceptions=False,  # exceptions are caught inside each helper
    )

    all_healthy = db_status == "connected" and redis_status == "connected"
    overall = "healthy" if all_healthy else "degraded"
    http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    body = HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        version=settings.app_version,
    )

    return JSONResponse(
        status_code=http_status,
        content=body.model_dump(),
    )
