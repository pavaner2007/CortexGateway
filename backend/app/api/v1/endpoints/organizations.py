"""
Cortex Gateway — Organization Endpoints (Phase 5).

POST /api/v1/organizations             — Create organization (admin only)
GET  /api/v1/organizations/{org_id}   — Get organization (authenticated)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_request_context, require_admin
from app.auth.exceptions import AuthorizationError
from app.auth.schemas import OrganizationCreate, OrganizationResponse, RequestContext
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.database.session import get_db_dependency

router = APIRouter()


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
    description="Create a new organization. Requires admin role.",
    tags=["Organizations"],
    responses={
        201: {"description": "Organization created"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
    },
)
async def create_organization(
    body: OrganizationCreate,
    context: RequestContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_dependency),
) -> OrganizationResponse:
    """Create a new organization (admin only)."""
    service = AuthService(session=session, pepper=get_settings().api_key_pepper)
    org = await service.create_organization(name=body.name, slug=body.slug)
    return OrganizationResponse.model_validate(org)


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    summary="Get Organization",
    description="Retrieve organization details. The authenticated key must belong to this organization.",
    tags=["Organizations"],
    responses={
        200: {"description": "Organization details"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Organization not found"},
    },
)
async def get_organization(
    org_id: str,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_dependency),
) -> OrganizationResponse:
    """Retrieve an organization. Access restricted to the caller's own organization."""
    # Cross-organization isolation: only allow access to own organization
    if context.organization_id != org_id:
        raise AuthorizationError("Access denied.")

    service = AuthService(session=session, pepper=get_settings().api_key_pepper)
    org = await service.get_organization(org_id)
    if org is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "NOT_FOUND", "message": "Organization not found."}},
        )
    return OrganizationResponse.model_validate(org)
