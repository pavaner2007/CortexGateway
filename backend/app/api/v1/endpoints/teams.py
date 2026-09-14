"""
Cortex Gateway — Team Endpoints (Phase 5).

POST /api/v1/organizations/{org_id}/teams  — Create team (admin only)
GET  /api/v1/organizations/{org_id}/teams  — List teams (admin only)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.exceptions import AuthorizationError
from app.auth.schemas import RequestContext, TeamCreate, TeamListResponse, TeamResponse
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.database.session import get_db_dependency

router = APIRouter()


@router.post(
    "/organizations/{org_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Team",
    description="Create a new team within an organization. Requires admin role.",
    tags=["Teams"],
    responses={
        201: {"description": "Team created"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required or cross-org access denied"},
    },
)
async def create_team(
    org_id: str,
    body: TeamCreate,
    context: RequestContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_dependency),
) -> TeamResponse:
    """Create a team within an organization (admin only, own org only)."""
    # Cross-organization isolation
    if context.organization_id != org_id:
        raise AuthorizationError("Access denied.")

    service = AuthService(session=session, pepper=get_settings().api_key_pepper)
    team = await service.create_team(
        organization_id=org_id,
        name=body.name,
        slug=body.slug,
    )
    return TeamResponse.model_validate(team)


@router.get(
    "/organizations/{org_id}/teams",
    response_model=TeamListResponse,
    summary="List Teams",
    description="List all teams in an organization. Requires admin role.",
    tags=["Teams"],
    responses={
        200: {"description": "List of teams"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required or cross-org access denied"},
    },
)
async def list_teams(
    org_id: str,
    context: RequestContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_dependency),
) -> TeamListResponse:
    """List all teams in an organization (admin only, own org only)."""
    # Cross-organization isolation
    if context.organization_id != org_id:
        raise AuthorizationError("Access denied.")

    service = AuthService(session=session, pepper=get_settings().api_key_pepper)
    teams = await service.list_teams(organization_id=org_id)
    return TeamListResponse(teams=[TeamResponse.model_validate(t) for t in teams])
