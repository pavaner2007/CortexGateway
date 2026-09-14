"""
Cortex Gateway — API Key Endpoints (Phase 5).

POST /api/v1/teams/{team_id}/keys                    — Create key (admin)
GET  /api/v1/teams/{team_id}/keys                    — List key metadata (admin)
POST /api/v1/teams/{team_id}/keys/{key_id}/revoke    — Revoke key (admin)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.exceptions import AuthorizationError
from app.auth.schemas import (
    APIKeyCreate,
    APIKeyCreatedResponse,
    APIKeyListResponse,
    APIKeyResponse,
    RequestContext,
)
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.database.session import get_db_dependency

router = APIRouter()


@router.post(
    "/teams/{team_id}/keys",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API Key",
    description=(
        "Create a new API key for a team. Requires admin role. "
        "The plaintext key is returned ONCE — store it securely."
    ),
    tags=["API Keys"],
    responses={
        201: {"description": "API key created — plaintext shown once"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required or cross-team access denied"},
    },
)
async def create_api_key(
    team_id: str,
    body: APIKeyCreate,
    context: RequestContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_dependency),
) -> APIKeyCreatedResponse:
    """Create an API key for a team (admin only, own team only)."""
    # Cross-team isolation
    if context.team_id != team_id:
        raise AuthorizationError("Access denied.")

    service = AuthService(session=session, pepper=get_settings().api_key_pepper)
    api_key, plaintext = await service.create_api_key(
        team_id=team_id,
        name=body.name,
        role=body.role,
        expires_at=body.expires_at,
    )

    return APIKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key=plaintext,
        key_prefix=api_key.key_prefix,
        role=api_key.role,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get(
    "/teams/{team_id}/keys",
    response_model=APIKeyListResponse,
    summary="List API Keys",
    description="List API key metadata for a team. Requires admin role. key_hash is never returned.",
    tags=["API Keys"],
    responses={
        200: {"description": "List of key metadata"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required or cross-team access denied"},
    },
)
async def list_api_keys(
    team_id: str,
    context: RequestContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_dependency),
) -> APIKeyListResponse:
    """List API keys for a team (admin only, own team only)."""
    # Cross-team isolation
    if context.team_id != team_id:
        raise AuthorizationError("Access denied.")

    service = AuthService(session=session, pepper=get_settings().api_key_pepper)
    keys = await service.list_api_keys(team_id=team_id)
    return APIKeyListResponse(
        keys=[APIKeyResponse.model_validate(k) for k in keys]
    )


@router.post(
    "/teams/{team_id}/keys/{key_id}/revoke",
    response_model=APIKeyResponse,
    summary="Revoke API Key",
    description="Soft-revoke an API key. Requires admin role. The key immediately becomes invalid.",
    tags=["API Keys"],
    responses={
        200: {"description": "Key revoked"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required or cross-team access denied"},
        404: {"description": "Key not found in this team"},
    },
)
async def revoke_api_key(
    team_id: str,
    key_id: str,
    context: RequestContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_dependency),
) -> APIKeyResponse:
    """Revoke an API key (admin only, own team only)."""
    # Cross-team isolation
    if context.team_id != team_id:
        raise AuthorizationError("Access denied.")

    service = AuthService(session=session, pepper=get_settings().api_key_pepper)
    key = await service.revoke_api_key(key_id=key_id, team_id=team_id)

    if key is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "NOT_FOUND", "message": "API key not found in this team."}},
        )

    return APIKeyResponse.model_validate(key)
