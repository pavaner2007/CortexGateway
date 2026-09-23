"""
Cortex Gateway — Auth FastAPI Dependencies (Phase 5).

Provides reusable dependency functions for:
  - get_request_context()  — authenticate and return RequestContext
  - require_admin()        — enforce admin role

RequestContext is also stored in a ContextVar (same pattern as request_id)
so downstream code can access it without parameter threading.

Usage in endpoints:
    @router.post("/chat/completions")
    async def chat(
        context: RequestContext = Depends(get_request_context),
        ...
    ):
        ...

Phase 6 access pattern (rate limiting):
    from app.auth.dependencies import get_current_context
    context = get_current_context()
    team_id = context.team_id  # use for rate limiting
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import AuthenticationError, AuthorizationError
from app.auth.schemas import RequestContext
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.core.logging import logger
from app.database.session import get_db_dependency

# ── ContextVar for request context (same pattern as request_id) ───────────────
_request_context_ctx: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)


def get_current_context() -> RequestContext | None:
    """
    Return the current authenticated RequestContext from the ContextVar.

    Returns None if the request is not authenticated (e.g. public endpoints).
    Phase 6 should call this for team_id-based rate limiting.
    """
    return _request_context_ctx.get()


def set_current_context(ctx: RequestContext | None) -> None:
    """Store a RequestContext in the current async task's ContextVar."""
    _request_context_ctx.set(ctx)


# ── HTTP Bearer security scheme ───────────────────────────────────────────────
# auto_error=False so we can return our own AuthenticationError instead of
# FastAPI's default 403 response.
_bearer_scheme = HTTPBearer(auto_error=False)


# ── Primary authentication dependency ─────────────────────────────────────────

async def get_request_context(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ] = None,
    session: AsyncSession = Depends(get_db_dependency),
) -> RequestContext:
    """
    FastAPI dependency: authenticate the request and return RequestContext.

    Reads: Authorization: Bearer <api-key>

    Raises:
        AuthenticationError (→ 401) if key is missing, invalid, expired, or revoked.

    The returned RequestContext is also stored in a ContextVar so downstream
    code can access it without explicit parameter threading.
    """
    settings = get_settings()

    if credentials is None:
        logger.warning(
            "Authentication failed: missing Authorization header",
            event="auth_missing_header",
        )
        raise AuthenticationError("Authentication required. Provide a valid API key.")

    # The Authorization header value is NOT logged — only that auth was attempted
    service = AuthService(session=session, pepper=settings.api_key_pepper)

    # authenticate() raises AuthenticationError on any failure
    context = await service.authenticate(credentials.credentials)

    # Store in ContextVar for downstream access
    set_current_context(context)

    return context


# ── Admin role enforcement ─────────────────────────────────────────────────────

async def require_admin(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """
    FastAPI dependency: require admin role.

    Raises:
        AuthorizationError (→ 403) if the authenticated key has role 'member'.

    Usage:
        @router.post("/teams")
        async def create_team(context: RequestContext = Depends(require_admin)):
            ...
    """
    if context.role != "admin":
        logger.warning(
            "Authorization failed: insufficient role",
            event="auth_insufficient_role",
            required_role="admin",
            actual_role=context.role,
            team_id=context.team_id,
            key_id=context.api_key_id,
        )
        raise AuthorizationError(
            "This operation requires admin privileges."
        )
    return context
