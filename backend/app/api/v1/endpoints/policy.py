"""
Cortex Gateway — Team Policy Endpoints (Phase 9C).

Routes:
    GET    /api/v1/teams/{team_id}/policy   — read effective policy (admin)
    PUT    /api/v1/teams/{team_id}/policy   — upsert team policy (admin)
    DELETE /api/v1/teams/{team_id}/policy   — remove team override (admin)

Security:
  - All routes require an authenticated admin API key.
  - team_id is validated against the authenticated admin's organisation to
    prevent cross-org access.  Members always receive 403.
  - Policy input is strictly validated by Pydantic before DB write.

Body format (PUT):
  JSON  — Content-Type: application/json
  YAML  — Content-Type: application/x-yaml  (parsed server-side)
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.schemas import RequestContext
from app.database.session import get_db_dependency
from app.policy.resolver import PolicyResolver
from app.policy.schemas import (
    GLOBAL_DEFAULT_POLICY,
    BudgetPolicySection,
    CachePolicy,
    FallbackPolicy,
    ResolvedPolicy,
    RoutingPolicy,
    TeamPolicyInput,
)
from app.policy.service import PolicyService

router = APIRouter(tags=["Policy Management"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_policy_service(
    session: AsyncSession = Depends(get_db_dependency),
) -> PolicyService:
    return PolicyService(session=session)


async def _resolve_team(
    team_id: str,
    context: RequestContext,
    session: AsyncSession,
) -> None:
    """Validate team_id belongs to the caller's organisation."""
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


# ── Response schema ────────────────────────────────────────────────────────────


class PolicyResponse(BaseModel):
    """API response for GET / PUT policy endpoints."""

    team_id: str
    policy: Dict[str, Any]
    source: Literal["global", "team"]
    updated_at: Optional[str] = None


def _to_response(
    team_id: str,
    resolved: ResolvedPolicy,
    updated_at: Optional[str] = None,
) -> PolicyResponse:
    return PolicyResponse(
        team_id=team_id,
        policy=resolved.model_dump(exclude={"source"}),
        source=resolved.source,
        updated_at=updated_at,
    )


# ── Parse helpers ─────────────────────────────────────────────────────────────


async def _parse_policy_body(request: Request) -> TeamPolicyInput:
    """
    Parse PUT body as JSON or YAML, then validate with Pydantic.

    Raises HTTP 422 for:
      - Malformed JSON / YAML
      - Invalid field values (unknown routing strategy, invalid budget action …)
      - Unknown top-level section names (extra="forbid")
    """
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    raw_body = await request.body()

    if content_type == "application/x-yaml":
        try:
            data = yaml.safe_load(raw_body)
        except yaml.YAMLError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Malformed YAML: {exc}",
            )
    else:
        # Default: JSON (application/json or unspecified)
        import json
        try:
            data = json.loads(raw_body)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Malformed JSON: {exc}",
            )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Policy body must be a JSON/YAML object.",
        )

    try:
        return TeamPolicyInput.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        )


# ── GET ───────────────────────────────────────────────────────────────────────


@router.get(
    "/teams/{team_id}/policy",
    response_model=PolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Team Policy",
    description=(
        "Return the effective policy for a team. "
        "If no override exists, the global default is returned with source='global'. "
        "Requires admin role."
    ),
    responses={
        200: {"description": "Effective policy"},
        403: {"description": "Admin role required or team not in your org"},
    },
)
async def get_policy(
    team_id: str,
    context: RequestContext = Depends(require_admin),
    service: PolicyService = Depends(_get_policy_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> PolicyResponse:
    """Return the effective policy for a team (admin only)."""
    await _resolve_team(team_id, context, session)

    resolver = PolicyResolver(session)
    resolved = await resolver.resolve(team_id)

    # Fetch updated_at from model if team has an override
    model = await service.get_policy_model(team_id)
    updated_at = model.updated_at.isoformat() if model else None

    return _to_response(team_id, resolved, updated_at)


# ── PUT ───────────────────────────────────────────────────────────────────────


@router.put(
    "/teams/{team_id}/policy",
    response_model=PolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Team Policy",
    description=(
        "Create or replace the policy for a team. "
        "Accepts JSON or YAML (Content-Type: application/x-yaml). "
        "Partial policies are supported — unspecified sections inherit from the global default. "
        "Requires admin role."
    ),
    responses={
        200: {"description": "Policy saved"},
        403: {"description": "Admin role required or team not in your org"},
        422: {"description": "Invalid policy"},
    },
)
async def put_policy(
    team_id: str,
    request: Request,
    context: RequestContext = Depends(require_admin),
    service: PolicyService = Depends(_get_policy_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> PolicyResponse:
    """Upsert a team policy (admin only)."""
    await _resolve_team(team_id, context, session)

    policy_input = await _parse_policy_body(request)
    model = await service.upsert_policy(team_id=team_id, policy_input=policy_input)

    # Resolve the effective policy to return (merges with global default)
    resolver = PolicyResolver(session)
    resolved = await resolver.resolve(team_id)

    return _to_response(team_id, resolved, model.updated_at.isoformat())


# ── DELETE ────────────────────────────────────────────────────────────────────


@router.delete(
    "/teams/{team_id}/policy",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Team Policy",
    description=(
        "Remove the team's policy override. "
        "Future requests will use the global default policy. "
        "Requires admin role."
    ),
    responses={
        204: {"description": "Policy deleted — team reverts to global default"},
        403: {"description": "Admin role required or team not in your org"},
        404: {"description": "No policy configured for this team"},
    },
)
async def delete_policy(
    team_id: str,
    context: RequestContext = Depends(require_admin),
    service: PolicyService = Depends(_get_policy_service),
    session: AsyncSession = Depends(get_db_dependency),
) -> Response:
    """Delete the team's policy override (admin only)."""
    await _resolve_team(team_id, context, session)

    deleted = await service.delete_policy(team_id=team_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No policy configured for team {team_id!r}.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
