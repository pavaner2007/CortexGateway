"""
Cortex Gateway — Per-Team Rate Limit Management Endpoints (Phase 6 Gap Fix).

Routes:
    POST   /api/v1/teams/{team_id}/rate-limits  — set custom limits (admin)
    GET    /api/v1/teams/{team_id}/rate-limits  — view current limits (admin)
    DELETE /api/v1/teams/{team_id}/rate-limits  — remove overrides (admin)

Behavior:
    - GET always returns effective limits (override + global defaults side-by-side).
    - POST/PUT sets overrides; omitting a field (None) removes that specific override.
    - DELETE removes the team override row entirely; team reverts to global defaults.
    - Non-admin → 403.
    - Cross-org team access → 403.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.schemas import RequestContext
from app.config.settings import get_settings
from app.database.session import get_db_dependency
from app.rate_limit.team_limits import TeamRateLimitService

router = APIRouter(tags=["Rate Limit Management"])


# ── Schemas ────────────────────────────────────────────────────────────────────


class TeamRateLimitSet(BaseModel):
    """Request body for setting per-team rate limit overrides."""

    requests_per_minute: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Max requests per 60-second window for this team. "
            "Omit or set null to revert to the global default."
        ),
        examples=[200],
    )
    requests_per_hour: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Max requests per 3600-second window for this team. "
            "Omit or set null to disable the hourly cap."
        ),
        examples=[3000],
    )


class TeamRateLimitResponse(BaseModel):
    """Effective rate limits for a team (override merged with global defaults)."""

    team_id: str
    # Effective values (resolved — never null)
    effective_requests_per_minute: int = Field(
        description="Resolved limit — team override if set, else global default."
    )
    effective_requests_per_hour: int | None = Field(
        description="Resolved hourly limit — team override if set, else None (no hourly cap)."
    )
    # Raw overrides (null = not overridden)
    override_requests_per_minute: int | None = Field(
        description="Raw per-team override for requests_per_minute. Null = global default in use."
    )
    override_requests_per_hour: int | None = Field(
        description="Raw per-team override for requests_per_hour. Null = hourly cap disabled."
    )
    # Global defaults for context
    global_requests_per_minute: int = Field(
        description="Global default requests-per-minute from settings."
    )
    global_requests_per_hour: int | None = Field(
        default=None,
        description="Global default requests-per-hour from settings (None = no hourly cap globally)."
    )

    class Config:
        from_attributes = True


# ── Dependency helpers ─────────────────────────────────────────────────────────


def _get_rate_limit_service(
    session: AsyncSession = Depends(get_db_dependency),
) -> TeamRateLimitService:
    return TeamRateLimitService(session=session)


async def _resolve_team(
    team_id: str,
    context: RequestContext,
    session: AsyncSession,
) -> None:
    """Validate team belongs to the authenticated admin's org."""
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


def _build_response(team_id: str, row, settings) -> TeamRateLimitResponse:
    """Merge the DB override row (may be None) with global defaults."""
    override_rpm = row.requests_per_minute if row else None
    override_rph = row.requests_per_hour if row else None

    global_rpm = settings.rate_limit_team_requests  # global default (per minute)

    return TeamRateLimitResponse(
        team_id=team_id,
        effective_requests_per_minute=override_rpm if override_rpm is not None else global_rpm,
        effective_requests_per_hour=override_rph,  # None = no hourly cap
        override_requests_per_minute=override_rpm,
        override_requests_per_hour=override_rph,
        global_requests_per_minute=global_rpm,
        global_requests_per_hour=None,  # no global hourly cap setting
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get(
    "/teams/{team_id}/rate-limits",
    response_model=TeamRateLimitResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Team Rate Limits",
    description=(
        "View current effective rate limits for a team, including both the "
        "team-level overrides and the global fallback defaults. Requires admin role."
    ),
    responses={
        200: {"description": "Effective rate limits for the team"},
        403: {"description": "Admin role required or team not in your org"},
    },
)
async def get_team_rate_limits(
    team_id: str,
    context: RequestContext = Depends(require_admin),
    service: TeamRateLimitService = Depends(_get_rate_limit_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> TeamRateLimitResponse:
    """Return the effective rate limits for a team (admin only)."""
    await _resolve_team(team_id, context, session)
    row = await service.get(team_id)
    settings = get_settings()
    return _build_response(team_id, row, settings)


@router.post(
    "/teams/{team_id}/rate-limits",
    response_model=TeamRateLimitResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Team Rate Limits",
    description=(
        "Create or replace per-team rate limit overrides. Pass null (or omit) "
        "for a field to remove that override and revert to the global default. "
        "Requires admin role."
    ),
    responses={
        200: {"description": "Rate limit override saved"},
        403: {"description": "Admin role required or team not in your org"},
        422: {"description": "Validation error (e.g. negative limit)"},
    },
)
async def set_team_rate_limits(
    team_id: str,
    body: TeamRateLimitSet,
    context: RequestContext = Depends(require_admin),
    service: TeamRateLimitService = Depends(_get_rate_limit_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> TeamRateLimitResponse:
    """Set (upsert) per-team rate limit overrides (admin only)."""
    await _resolve_team(team_id, context, session)
    row = await service.set(
        team_id=team_id,
        requests_per_minute=body.requests_per_minute,
        requests_per_hour=body.requests_per_hour,
    )
    settings = get_settings()
    return _build_response(team_id, row, settings)


@router.delete(
    "/teams/{team_id}/rate-limits",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Team Rate Limits",
    description=(
        "Remove all per-team rate limit overrides. The team will revert to "
        "the global default limits. Requires admin role."
    ),
    responses={
        204: {"description": "Overrides removed (team reverts to global defaults)"},
        403: {"description": "Admin role required or team not in your org"},
        404: {"description": "No overrides configured for this team"},
    },
)
async def delete_team_rate_limits(
    team_id: str,
    context: RequestContext = Depends(require_admin),
    service: TeamRateLimitService = Depends(_get_rate_limit_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> Response:
    """Remove per-team rate limit overrides (admin only)."""
    await _resolve_team(team_id, context, session)
    deleted = await service.delete(team_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rate limit overrides configured for team {team_id!r}.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
