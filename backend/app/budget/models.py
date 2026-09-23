"""
Cortex Gateway — Budget ORM Model (Phase 6).

SQLAlchemy 2.x declarative model for team-level budgets.

Design constraints:
  - One active budget per team (enforced by UNIQUE constraint on team_id
    when enabled=True; multiple disabled/expired budgets are allowed).
  - FK cascade: deleting a team cascades to its budget rows.
  - `reserved` tracks amounts pre-reserved by in-flight requests to prevent
    concurrent overspending. It is always reconciled after request completion.
  - Period rollover is lazy (checked on access, not scheduled).

Supported periods:
  daily   — 24-hour rolling window
  weekly  — 7-day rolling window
  monthly — calendar-month window (28–31 days depending on month)

Policy values (enforced by BudgetService):
  BLOCK      — reject requests that would exceed the budget
  WARN       — allow but log a structured warning
  DOWNGRADE  — redirect to a cheaper provider/model within budget
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Budget(Base):
    """
    Team-level spending budget.

    Lifecycle:
        1. Admin creates budget via POST /api/v1/teams/{team_id}/budget.
        2. On each request, BudgetService checks and reserves estimated_cost.
        3. After provider response, BudgetService reconciles actual_cost.
        4. On period expiry (period_end < utcnow), next request triggers rollover.
    """

    __tablename__ = "budgets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_new_uuid
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Limit ─────────────────────────────────────────────────────────────────
    limit_amount: Mapped[float] = mapped_column(Float, nullable=False)
    current_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reserved: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Amount reserved by in-flight requests, not yet reconciled.",
    )

    # ── Period ────────────────────────────────────────────────────────────────
    # Allowed values: 'daily' | 'weekly' | 'monthly'
    period: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ── Policy ────────────────────────────────────────────────────────────────
    # Allowed values: 'BLOCK' | 'WARN' | 'DOWNGRADE'
    policy: Mapped[str] = mapped_column(String(20), nullable=False, default="BLOCK")

    # ── Flags ─────────────────────────────────────────────────────────────────
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    team: Mapped[Team] = relationship("Team")  # type: ignore[name-defined]

    __table_args__ = (
        # One active budget per team
        UniqueConstraint(
            "team_id",
            name="uq_budgets_team_id_enabled",
        ),
        Index("ix_budgets_team_id", "team_id"),
        Index("ix_budgets_period_end", "period_end"),
    )

    @property
    def remaining_amount(self) -> float:
        """Available budget = limit - used - reserved."""
        return max(0.0, self.limit_amount - self.current_usage - self.reserved)

    @property
    def usage_percentage(self) -> float:
        """Usage as a percentage of the limit (0–100+)."""
        if self.limit_amount <= 0:
            return 0.0
        return round((self.current_usage / self.limit_amount) * 100, 2)

    @property
    def is_period_expired(self) -> bool:
        """True if the current period has ended and needs rollover."""
        return datetime.now(UTC) >= self.period_end

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Budget id={self.id!r} team={self.team_id!r} "
            f"limit={self.limit_amount} used={self.current_usage} "
            f"policy={self.policy!r}>"
        )
