"""
Cortex Gateway — Team Policy ORM Model (Phase 9C).

One row per team (UNIQUE constraint on team_id).
The policy column is JSONB — validated by Pydantic at write time.

Budget.policy (Phase 6) is now a deprecated compatibility field.
Runtime behaviour is governed by this table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class TeamPolicyModel(Base):
    """
    Persistent team policy record.

    Lifecycle:
        1. Admin creates / upserts via PUT /api/v1/teams/{team_id}/policy.
        2. PolicyResolver loads this row (or uses global default if absent).
        3. ResolvedPolicy is produced once per request and passed downstream.
        4. Admin may DELETE to revert team to global default.
    """

    __tablename__ = "team_policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Normalized JSONB — validated by TeamPolicyInput Pydantic schema before storage.
    policy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Soft-disable without deleting the row (reserved for future use).
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc
    )

    # Relationships
    team: Mapped[Team] = relationship("Team")  # type: ignore[name-defined]

    __table_args__ = (
        UniqueConstraint("team_id", name="uq_team_policies_team_id"),
        Index("ix_team_policies_team_id", "team_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TeamPolicyModel team={self.team_id!r} enabled={self.enabled}>"
