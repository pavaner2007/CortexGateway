"""
Cortex Gateway — Model Registry Endpoints (Phase 9A).

Routes:
    GET    /api/v1/models                 — list models (admin)
    POST   /api/v1/models                 — create model (admin)
    GET    /api/v1/models/{model_id}      — get model (admin)
    PATCH  /api/v1/models/{model_id}      — update model (admin)
    DELETE /api/v1/models/{model_id}      — delete model (admin)

Security:
  - All routes require an authenticated admin API key.
  - Member keys receive 403.
  - Duplicate (provider, model_name) → 409.
  - Missing entry → 404.

Side effects:
  - After any mutation (POST/PATCH/DELETE) the shared ModelMetadataCatalog
    is immediately refreshed so routing picks up changes without waiting
    for the 60-second background refresh.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.schemas import RequestContext
from app.database.session import get_db_dependency
from app.model_registry.exceptions import (
    ModelAlreadyExistsError,
    ModelNotFoundError,
)
from app.model_registry.schemas import (
    ModelRegistryCreate,
    ModelRegistryListResponse,
    ModelRegistryResponse,
    ModelRegistryUpdate,
)
from app.model_registry.service import ModelRegistryService

router = APIRouter(tags=["Model Registry"])


def _get_registry_service(
    session: AsyncSession = Depends(get_db_dependency),
) -> ModelRegistryService:
    return ModelRegistryService(session=session)


async def _trigger_catalog_refresh(session: AsyncSession) -> None:
    """
    Refresh the in-process ModelMetadataCatalog from DB immediately after
    a mutation so routing picks up the change without waiting for the
    background refresh cycle.
    """
    try:
        from app.routing.metadata import _shared_catalog
        await _shared_catalog.load_from_db(session)
    except Exception:
        # Refresh failure is non-fatal — background task will catch up
        pass


@router.get(
    "/models",
    response_model=ModelRegistryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Model Registry",
    description="List all entries in the model registry. Requires admin role.",
    responses={
        200: {"description": "List of model entries"},
        403: {"description": "Admin role required"},
    },
)
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    enabled_only: bool = Query(True, description="Return only enabled models"),
    _context: RequestContext = Depends(require_admin),
    service: ModelRegistryService = Depends(_get_registry_service),
) -> ModelRegistryListResponse:
    """List model registry entries with optional provider filter."""
    entries = await service.list_models(provider=provider, enabled_only=enabled_only)
    return ModelRegistryListResponse(
        models=[ModelRegistryResponse.from_orm(e) for e in entries],
        total=len(entries),
    )


@router.post(
    "/models",
    response_model=ModelRegistryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Model",
    description="Add a new model to the registry. Requires admin role.",
    responses={
        201: {"description": "Model registered"},
        403: {"description": "Admin role required"},
        409: {"description": "Model already registered for this provider"},
        422: {"description": "Validation error (unknown capability, negative cost, etc.)"},
    },
)
async def create_model(
    body: ModelRegistryCreate,
    _context: RequestContext = Depends(require_admin),
    service: ModelRegistryService = Depends(_get_registry_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> ModelRegistryResponse:
    """Register a new model in the registry (admin only)."""
    try:
        entry = await service.create_model(body)
    except ModelAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        )
    await _trigger_catalog_refresh(session)
    return ModelRegistryResponse.from_orm(entry)


@router.get(
    "/models/{model_id}",
    response_model=ModelRegistryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Model",
    description="Retrieve a single model registry entry by ID. Requires admin role.",
    responses={
        200: {"description": "Model entry"},
        403: {"description": "Admin role required"},
        404: {"description": "Model not found"},
    },
)
async def get_model(
    model_id: str,
    _context: RequestContext = Depends(require_admin),
    service: ModelRegistryService = Depends(_get_registry_service),
) -> ModelRegistryResponse:
    """Get a single model registry entry (admin only)."""
    try:
        entry = await service.get_model(model_id)
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        )
    return ModelRegistryResponse.from_orm(entry)


@router.patch(
    "/models/{model_id}",
    response_model=ModelRegistryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Model",
    description="Partially update a model registry entry. Requires admin role.",
    responses={
        200: {"description": "Model updated"},
        403: {"description": "Admin role required"},
        404: {"description": "Model not found"},
        422: {"description": "Validation error"},
    },
)
async def update_model(
    model_id: str,
    body: ModelRegistryUpdate,
    _context: RequestContext = Depends(require_admin),
    service: ModelRegistryService = Depends(_get_registry_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> ModelRegistryResponse:
    """Update model metadata (admin only)."""
    try:
        entry = await service.update_model(model_id, body)
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        )
    await _trigger_catalog_refresh(session)
    return ModelRegistryResponse.from_orm(entry)


@router.delete(
    "/models/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Model",
    description="Remove a model from the registry. Requires admin role.",
    responses={
        204: {"description": "Model deleted"},
        403: {"description": "Admin role required"},
        404: {"description": "Model not found"},
    },
)
async def delete_model(
    model_id: str,
    _context: RequestContext = Depends(require_admin),
    service: ModelRegistryService = Depends(_get_registry_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> Response:
    """Remove a model from the registry (admin only)."""
    try:
        await service.delete_model(model_id)
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        )
    await _trigger_catalog_refresh(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
