"""
Cortex Gateway — Auth Service (Phase 5).

Database operations for:
  - Organizations (create, get, exists)
  - Teams (create, list, get)
  - API Keys (create, list, revoke, authenticate)

AuthService is a stateless service class that receives a SQLAlchemy
AsyncSession via dependency injection — consistent with the existing
architecture pattern used by ChatService.

Security invariants:
  - Plaintext API keys NEVER pass through this class after creation.
  - key_hash values are NEVER returned; they are write-only after storage.
  - last_used_at updates are fire-and-forget to avoid adding latency.
  - Authentication errors use generic messages to avoid info leakage.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import AuthenticationError, AuthorizationError
from app.auth.models import APIKey, Organization, Team
from app.auth.schemas import RequestContext
from app.auth.security import (
    extract_key_prefix,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)
from app.core.logging import logger


class AuthService:
    """
    Application-layer service for authentication and multi-tenancy.

    All methods receive an AsyncSession and are fully async.
    No business logic lives in the ORM models — all logic is here.
    """

    def __init__(self, session: AsyncSession, pepper: str) -> None:
        self._session = session
        self._pepper = pepper

    # ── Organization Operations ────────────────────────────────────────────────

    async def organizations_exist(self) -> bool:
        """Return True if any organization has been created (bootstrap guard)."""
        result = await self._session.execute(
            select(func.count()).select_from(Organization)
        )
        count: int = result.scalar_one()
        return count > 0

    async def create_organization(self, name: str, slug: str) -> Organization:
        """Create and persist a new organization."""
        org = Organization(name=name, slug=slug)
        self._session.add(org)
        await self._session.flush()  # populate id without committing
        logger.info(
            "Organization created",
            org_id=org.id,
            slug=slug,
        )
        return org

    async def get_organization(self, org_id: str) -> Optional[Organization]:
        """Retrieve an organization by ID. Returns None if not found."""
        result = await self._session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    # ── Team Operations ────────────────────────────────────────────────────────

    async def create_team(
        self, organization_id: str, name: str, slug: str
    ) -> Team:
        """Create and persist a new team under an organization."""
        team = Team(organization_id=organization_id, name=name, slug=slug)
        self._session.add(team)
        await self._session.flush()
        logger.info(
            "Team created",
            team_id=team.id,
            org_id=organization_id,
            slug=slug,
        )
        return team

    async def get_team(self, team_id: str) -> Optional[Team]:
        """Retrieve a team by ID. Returns None if not found."""
        result = await self._session.execute(
            select(Team).where(Team.id == team_id)
        )
        return result.scalar_one_or_none()

    async def list_teams(self, organization_id: str) -> List[Team]:
        """List all teams for an organization."""
        result = await self._session.execute(
            select(Team)
            .where(Team.organization_id == organization_id)
            .order_by(Team.created_at)
        )
        return list(result.scalars().all())

    # ── API Key Operations ─────────────────────────────────────────────────────

    async def create_api_key(
        self,
        team_id: str,
        name: str,
        role: str,
        expires_at: Optional[datetime] = None,
    ) -> tuple[APIKey, str]:
        """
        Generate a new API key, store its hash, and persist to DB.

        Returns:
            (api_key_orm, plaintext_key) — the plaintext key is returned
            ONCE here and must be shown to the user immediately.
            It is NEVER stored and cannot be recovered.
        """
        plaintext = generate_api_key()
        prefix = extract_key_prefix(plaintext)
        hashed = hash_api_key(plaintext, self._pepper)

        key = APIKey(
            team_id=team_id,
            name=name,
            key_prefix=prefix,
            key_hash=hashed,
            role=role,
            expires_at=expires_at,
        )
        self._session.add(key)
        await self._session.flush()

        logger.info(
            "API key created",
            key_id=key.id,
            key_prefix=prefix,  # safe to log
            team_id=team_id,
            role=role,
            # plaintext key is NOT logged
        )
        return key, plaintext

    async def list_api_keys(self, team_id: str) -> List[APIKey]:
        """List all API keys for a team (metadata only — no key_hash in response schema)."""
        result = await self._session.execute(
            select(APIKey)
            .where(APIKey.team_id == team_id)
            .order_by(APIKey.created_at)
        )
        return list(result.scalars().all())

    async def get_api_key(self, key_id: str, team_id: str) -> Optional[APIKey]:
        """Retrieve a specific API key scoped to a team (prevents cross-team access)."""
        result = await self._session.execute(
            select(APIKey).where(
                APIKey.id == key_id,
                APIKey.team_id == team_id,
            )
        )
        return result.scalar_one_or_none()

    async def revoke_api_key(self, key_id: str, team_id: str) -> Optional[APIKey]:
        """
        Soft-revoke an API key by setting revoked_at.

        Returns the updated key, or None if not found / wrong team.
        Cross-team revocation is prevented by scoping to team_id.
        """
        key = await self.get_api_key(key_id, team_id)
        if key is None:
            return None

        key.revoked_at = datetime.now(timezone.utc)
        await self._session.flush()

        logger.info(
            "API key revoked",
            key_id=key_id,
            key_prefix=key.key_prefix,
            team_id=team_id,
        )
        return key

    # ── Authentication ─────────────────────────────────────────────────────────

    async def authenticate(self, plaintext_key: str) -> RequestContext:
        """
        Verify a plaintext API key and return the authenticated RequestContext.

        Flow:
          1. Hash the incoming key with the pepper.
          2. Look up by key_hash (indexed lookup — O(1)).
          3. constant-time verify (defense-in-depth).
          4. Check revocation and expiry.
          5. Load team → organization.
          6. Return RequestContext.

        Raises:
          AuthenticationError for any failure — generic message to avoid
          leaking whether the key exists, is expired, or is revoked.
        """
        _GENERIC_AUTH_ERROR = "Authentication required. Provide a valid API key."

        if not plaintext_key or not plaintext_key.startswith("cxg_"):
            raise AuthenticationError(_GENERIC_AUTH_ERROR)

        computed_hash = hash_api_key(plaintext_key, self._pepper)

        # Lookup by hash (indexed)
        result = await self._session.execute(
            select(APIKey)
            .where(APIKey.key_hash == computed_hash)
            .join(Team, APIKey.team_id == Team.id)
            .join(Organization, Team.organization_id == Organization.id)
        )
        api_key = result.scalar_one_or_none()

        # Constant-time defense-in-depth (hash was already used for lookup,
        # but this prevents any future refactor from removing the indexed filter)
        if api_key is None or not verify_api_key(plaintext_key, api_key.key_hash, self._pepper):
            raise AuthenticationError(_GENERIC_AUTH_ERROR)

        # Check lifecycle state — generic error avoids leaking key status
        if not api_key.is_active:
            raise AuthenticationError(_GENERIC_AUTH_ERROR)

        # Load team and organization (already joined above, but re-fetch for safety)
        team_result = await self._session.execute(
            select(Team)
            .where(Team.id == api_key.team_id)
        )
        team = team_result.scalar_one_or_none()
        if team is None:  # pragma: no cover — should never happen (FK constraint)
            raise AuthenticationError(_GENERIC_AUTH_ERROR)

        org_result = await self._session.execute(
            select(Organization)
            .where(Organization.id == team.organization_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:  # pragma: no cover — should never happen (FK constraint)
            raise AuthenticationError(_GENERIC_AUTH_ERROR)

        # Fire-and-forget last_used_at update — never blocks or fails the request
        asyncio.create_task(
            self._update_last_used(api_key.id)
        )

        logger.info(
            "API key authenticated",
            key_id=api_key.id,
            key_prefix=api_key.key_prefix,  # safe to log
            team_id=team.id,
            org_id=org.id,
            role=api_key.role,
            # plaintext key is NOT logged
        )

        return RequestContext(
            organization_id=org.id,
            team_id=team.id,
            api_key_id=api_key.id,
            role=api_key.role,
        )

    async def _update_last_used(self, key_id: str) -> None:
        """
        Update last_used_at for an API key.

        Called as a fire-and-forget asyncio task. Failure is logged but
        never propagates to the caller.
        """
        try:
            from app.database.session import get_db_session
            async with get_db_session() as session:
                await session.execute(
                    update(APIKey)
                    .where(APIKey.id == key_id)
                    .values(last_used_at=datetime.now(timezone.utc))
                )
                # session commit is handled by the context manager
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Failed to update last_used_at",
                key_id=key_id,
                error=str(exc),
            )
