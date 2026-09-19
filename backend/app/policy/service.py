"""
Cortex Gateway — Policy Service (Phase 9C).

CRUD operations for team policy records.

All write operations validate the policy through Pydantic before persistence —
invalid policies are rejected before touching the database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.policy.models import TeamPolicyModel
from app.policy.schemas import TeamPolicyInput


class PolicyService:
    """Application-layer service for team policy management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_policy_model(self, team_id: str) -> Optional[TeamPolicyModel]:
        """Return the raw ORM model for a team's policy, or None if not set."""
        result = await self._session.execute(
            select(TeamPolicyModel).where(
                TeamPolicyModel.team_id == team_id,
                TeamPolicyModel.enabled == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_policy_dict(self, team_id: str) -> Optional[dict]:
        """
        Return the stored policy JSONB dict for a team, or None if not set.

        Used by PolicyResolver — avoids constructing the full ORM object when
        only the raw dict is needed for Pydantic deserialization.
        """
        model = await self.get_policy_model(team_id)
        if model is None:
            return None
        return dict(model.policy)

    # ── Upsert ────────────────────────────────────────────────────────────────

    async def upsert_policy(
        self,
        team_id: str,
        policy_input: TeamPolicyInput,
    ) -> TeamPolicyModel:
        """
        Create or replace the team's policy.

        Uses PostgreSQL INSERT … ON CONFLICT DO UPDATE (upsert) so that
        PUT is truly idempotent.  The policy dict stored is only the sections
        explicitly provided by the caller (partial representation).
        """
        # Dump only the sections that were explicitly set (exclude_none).
        policy_dict = policy_input.model_dump(exclude_none=True)

        now = datetime.now(timezone.utc)

        stmt = (
            pg_insert(TeamPolicyModel)
            .values(
                team_id=team_id,
                policy=policy_dict,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["team_id"],
                set_={
                    "policy": policy_dict,
                    "enabled": True,
                    "updated_at": now,
                },
            )
            .returning(TeamPolicyModel)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        row = result.scalar_one()
        logger.info(
            "Team policy upserted",
            team_id=team_id,
            sections=list(policy_dict.keys()),
        )
        return row

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_policy(self, team_id: str) -> bool:
        """
        Delete the team's policy override.

        Returns True if a row existed and was deleted; False if not found.
        After deletion, the team falls back to the global default on the
        next request.
        """
        model = await self.get_policy_model(team_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.commit()
        logger.info("Team policy deleted — reverting to global default", team_id=team_id)
        return True
