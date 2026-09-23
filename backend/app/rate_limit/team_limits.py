"""
Cortex Gateway — Per-Team Rate Limit Overrides (Phase 6 Gap Fix).

ORM model and service for team-level rate limit configuration.

Design:
  - Separate table `team_rate_limits` with nullable override columns.
  - NULL means "use the global default from settings".
  - One row per team (unique constraint on team_id).
  - FK → teams.id with CASCADE DELETE.

Supported override fields:
  - requests_per_minute: Override for the 60-second team window.
  - requests_per_hour:   Override for the 3600-second team window.
    (hour window is only active if requests_per_hour is set)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class TeamRateLimit(Base):
    """
    Per-team rate limit overrides.

    NULL columns = inherit the global default from Settings.
    """

    __tablename__ = "team_rate_limits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable overrides — NULL means "use global default"
    requests_per_minute: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Max requests per 60-second window. NULL = global default."
    )
    requests_per_hour: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Max requests per 3600-second window. NULL = disabled (no hourly cap)."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc
    )

    __table_args__ = (
        UniqueConstraint("team_id", name="uq_team_rate_limits_team_id"),
        Index("ix_team_rate_limits_team_id", "team_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<TeamRateLimit team_id={self.team_id!r} "
            f"rpm={self.requests_per_minute!r} rph={self.requests_per_hour!r}>"
        )


class TeamRateLimitService:
    """CRUD service for per-team rate limit overrides."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, team_id: str) -> TeamRateLimit | None:
        """Return the TeamRateLimit row for team_id, or None if unset."""
        result = await self._session.execute(
            select(TeamRateLimit).where(TeamRateLimit.team_id == team_id)
        )
        return result.scalar_one_or_none()

    async def set(
        self,
        team_id: str,
        requests_per_minute: int | None,
        requests_per_hour: int | None,
    ) -> TeamRateLimit:
        """
        Create or update the rate limit override for team_id.

        Passing None for a field removes the override for that field
        (falls back to global default).
        """
        row = await self.get(team_id)
        if row is None:
            row = TeamRateLimit(
                id=_new_uuid(),
                team_id=team_id,
                requests_per_minute=requests_per_minute,
                requests_per_hour=requests_per_hour,
                created_at=_now_utc(),
                updated_at=_now_utc(),
            )
            self._session.add(row)
        else:
            row.requests_per_minute = requests_per_minute
            row.requests_per_hour = requests_per_hour
            row.updated_at = _now_utc()

        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def delete(self, team_id: str) -> bool:
        """Remove all overrides for team_id.  Returns False if row didn't exist."""
        row = await self.get(team_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True
