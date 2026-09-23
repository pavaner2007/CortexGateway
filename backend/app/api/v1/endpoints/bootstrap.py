"""
Cortex Gateway — Bootstrap Endpoint (Phase 5).

POST /api/v1/bootstrap

One-time initialization endpoint that creates:
  1. The first Organization
  2. The first Team
  3. The first admin API Key

Protected by CORTEX_BOOTSTRAP_TOKEN environment variable.
After any organization exists, subsequent bootstrap calls are rejected
regardless of the CORTEX_BOOTSTRAP_ENABLED flag.

The admin API key plaintext is returned ONCE in the response.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import AuthenticationError
from app.auth.schemas import (
    APIKeyCreatedResponse,
    BootstrapRequest,
    BootstrapResponse,
    OrganizationResponse,
    TeamResponse,
)
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.core.logging import logger
from app.database.session import get_db_dependency

router = APIRouter()

_bearer_scheme = HTTPBearer(auto_error=False)


@router.post(
    "/bootstrap",
    response_model=BootstrapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bootstrap Initial Organization",
    description=(
        "One-time endpoint to create the first organization, team, and admin API key. "
        "Requires Authorization: Bearer <CORTEX_BOOTSTRAP_TOKEN>. "
        "Permanently disabled after the first organization is created."
    ),
    tags=["Bootstrap"],
    responses={
        201: {"description": "Bootstrap successful — admin key returned once"},
        401: {"description": "Missing or invalid bootstrap token"},
        409: {"description": "Bootstrap already completed — organization exists"},
        503: {"description": "Bootstrap is disabled"},
    },
)
async def bootstrap(
    body: BootstrapRequest,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ] = None,
    session: AsyncSession = Depends(get_db_dependency),
) -> BootstrapResponse:
    """
    Create the first organization, team, and admin API key.

    This endpoint:
    - Requires the CORTEX_BOOTSTRAP_TOKEN as a Bearer token.
    - Refuses if CORTEX_BOOTSTRAP_ENABLED=false.
    - Refuses if any organization already exists (idempotency guard).
    - Returns the admin API key plaintext ONCE.
    """
    settings = get_settings()

    # Guard: bootstrap can be disabled entirely via config
    if not settings.cortex_bootstrap_enabled:
        logger.warning("Bootstrap attempt rejected: bootstrap is disabled")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": {"code": "BOOTSTRAP_DISABLED", "message": "Bootstrap is disabled."}},
        )

    # Guard: validate bootstrap token (generic error — don't reveal token)
    _GENERIC_BOOTSTRAP_ERROR = "Invalid bootstrap token."
    if credentials is None or not credentials.credentials:
        raise AuthenticationError(_GENERIC_BOOTSTRAP_ERROR)

    import hmac
    expected = settings.cortex_bootstrap_token
    if not expected or not hmac.compare_digest(
        credentials.credentials.encode(), expected.encode()
    ):
        logger.warning("Bootstrap attempt rejected: invalid token")
        raise AuthenticationError(_GENERIC_BOOTSTRAP_ERROR)

    service = AuthService(session=session, pepper=settings.api_key_pepper)

    # Guard: only one bootstrap allowed (check if any org exists)
    if await service.organizations_exist():
        logger.warning("Bootstrap attempt rejected: organization already exists")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "BOOTSTRAP_ALREADY_COMPLETED",
                    "message": "Bootstrap has already been completed. An organization already exists.",
                }
            },
        )

    # Create organization
    org = await service.create_organization(
        name=body.organization_name,
        slug=body.organization_slug,
    )

    # Create first team
    team = await service.create_team(
        organization_id=org.id,
        name=body.team_name,
        slug=body.team_slug,
    )

    # Create admin API key
    api_key, plaintext = await service.create_api_key(
        team_id=team.id,
        name=body.admin_key_name,
        role="admin",
    )

    logger.info(
        "Bootstrap completed",
        org_id=org.id,
        org_slug=org.slug,
        team_id=team.id,
        key_id=api_key.id,
        key_prefix=api_key.key_prefix,
        # bootstrap token and plaintext key NOT logged
    )

    return BootstrapResponse(
        organization=OrganizationResponse.model_validate(org),
        team=TeamResponse.model_validate(team),
        admin_key=APIKeyCreatedResponse(
            id=api_key.id,
            name=api_key.name,
            key=plaintext,
            key_prefix=api_key.key_prefix,
            role=api_key.role,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
        ),
    )
