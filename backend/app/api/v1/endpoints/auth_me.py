"""
Cortex Gateway — Auth Me Endpoint (Phase 8).

GET /api/v1/auth/me  — Returns the authenticated caller's context:
                        organization_id, team_id, api_key_id, role.

Purpose:
  The admin dashboard frontend needs organization_id to bootstrap subsequent
  API calls (e.g. list teams). This endpoint exposes the RequestContext fields
  that the backend already computes during authentication without adding any
  new business logic.

Security:
  - Requires any valid API key (admin OR member).
  - Returns only what is already in the authenticated RequestContext.
  - No sensitive data (no key_hash, no plaintext key, no secrets).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_request_context
from app.auth.schemas import RequestContext

router = APIRouter(tags=["Authentication"])


class MeResponse(BaseModel):
    """Authenticated caller context — safe fields only."""

    organization_id: str
    team_id: str
    api_key_id: str
    role: str


@router.get(
    "/auth/me",
    response_model=MeResponse,
    summary="Get Authenticated Context",
    description=(
        "Returns the organization_id, team_id, api_key_id, and role for the "
        "authenticated API key. Useful for the admin dashboard to discover "
        "the caller's organization without additional lookups."
    ),
    responses={
        200: {"description": "Authenticated caller context"},
        401: {"description": "Authentication required"},
    },
)
async def get_me(
    context: RequestContext = Depends(get_request_context),
) -> MeResponse:
    """Return the authenticated caller's context (any valid API key)."""
    return MeResponse(
        organization_id=context.organization_id,
        team_id=context.team_id,
        api_key_id=context.api_key_id,
        role=context.role,
    )
