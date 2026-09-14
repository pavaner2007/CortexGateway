"""
Cortex Gateway — Budget Management Endpoints (Phase 6).

Routes:
    POST   /api/v1/teams/{team_id}/budget   — create budget (admin)
    GET    /api/v1/teams/{team_id}/budget   — read budget (admin)
    PATCH  /api/v1/teams/{team_id}/budget   — update budget (admin)
    DELETE /api/v1/teams/{team_id}/budget   — delete budget (admin)

Security:
  - All routes require an authenticated admin API key.
  - team_id from the URL is validated against the authenticated org to prevent
    cross-team access. Members always receive 403.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.schemas import RequestContext
from app.budget.exceptions import BudgetConfigurationError
from app.budget.schemas import BudgetCreate, BudgetResponse, BudgetUpdate
from app.budget.service import BudgetService
from app.database.session import get_db_dependency

router = APIRouter(tags=["Budget Management"])


def _get_budget_service(
    session: AsyncSession = Depends(get_db_dependency),
) -> BudgetService:
    return BudgetService(session=session)


async def _resolve_team(
    team_id: str,
    context: RequestContext,
    session: AsyncSession,
) -> None:
    """
    Validate that team_id belongs to the authenticated admin's organization.

    Admins can manage any team in their own organization.
    Cross-org access is rejected with 403.
    """
    from sqlalchemy import select
    from app.auth.models import Team

    result = await session.execute(
        select(Team).where(
            Team.id == team_id,
            Team.organization_id == context.organization_id,
        )
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team not found in your organization.",
        )


@router.post(
    "/teams/{team_id}/budget",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Team Budget",
    description="Create a spending budget for a team. Requires admin role.",
    responses={
        201: {"description": "Budget created successfully"},
        403: {"description": "Admin role required or team not in your org"},
        409: {"description": "Budget already exists for this team"},
    },
)
async def create_budget(
    team_id: str,
    body: BudgetCreate,
    context: RequestContext = Depends(require_admin),
    service: BudgetService = Depends(_get_budget_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> BudgetResponse:
    """Create a new spending budget for a team (admin only)."""
    await _resolve_team(team_id, context, session)
    try:
        budget = await service.create_budget(team_id=team_id, data=body)
    except BudgetConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        )
    return BudgetResponse.from_orm_with_derived(budget)


@router.get(
    "/teams/{team_id}/budget",
    response_model=BudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Team Budget",
    description="Retrieve the active budget for a team. Requires admin role.",
    responses={
        200: {"description": "Budget details"},
        403: {"description": "Admin role required or team not in your org"},
        404: {"description": "No budget configured for this team"},
    },
)
async def get_budget(
    team_id: str,
    context: RequestContext = Depends(require_admin),
    service: BudgetService = Depends(_get_budget_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> BudgetResponse:
    """Retrieve the team's active budget (admin only)."""
    await _resolve_team(team_id, context, session)
    budget = await service.get_budget(team_id=team_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No budget configured for team {team_id!r}.",
        )
    return BudgetResponse.from_orm_with_derived(budget)


@router.patch(
    "/teams/{team_id}/budget",
    response_model=BudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Team Budget",
    description="Update limit, policy, or enabled flag of a team budget. Requires admin role.",
    responses={
        200: {"description": "Budget updated"},
        403: {"description": "Admin role required or team not in your org"},
        404: {"description": "No budget configured for this team"},
    },
)
async def update_budget(
    team_id: str,
    body: BudgetUpdate,
    context: RequestContext = Depends(require_admin),
    service: BudgetService = Depends(_get_budget_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> BudgetResponse:
    """Update an existing team budget (admin only)."""
    await _resolve_team(team_id, context, session)
    try:
        budget = await service.update_budget(team_id=team_id, data=body)
    except BudgetConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        )
    return BudgetResponse.from_orm_with_derived(budget)


@router.delete(
    "/teams/{team_id}/budget",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Team Budget",
    description="Delete the active budget for a team. Requires admin role.",
    responses={
        204: {"description": "Budget deleted"},
        403: {"description": "Admin role required or team not in your org"},
        404: {"description": "No budget configured for this team"},
    },
)
async def delete_budget(
    team_id: str,
    context: RequestContext = Depends(require_admin),
    service: BudgetService = Depends(_get_budget_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> Response:
    """Delete the team's budget (admin only)."""
    await _resolve_team(team_id, context, session)
    deleted = await service.delete_budget(team_id=team_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No budget configured for team {team_id!r}.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
