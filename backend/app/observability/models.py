"""
Cortex Gateway — RequestLog ORM Model (Phase 7).

One row per completed client request.

Semantics:
- A request that does 2 retries + 1 failover = 1 row (aggregated).
- retry_count / failover_triggered capture reliability metadata.
- Requests rejected before provider selection (rate-limit, budget) still
  get a row; provider/model are NULL.
- Sensitive fields (prompt, completion text, API keys) are NEVER stored.

Foreign keys use ON DELETE SET NULL so deleting a team/org does not
cascade-delete the historical audit log.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class RequestLog(Base):
    """
    Persistent audit log — one row per completed client request.

    Used by:
    - Analytics APIs (GET /api/v1/analytics/*)
    - Cost attribution / budget reporting
    - Reliability post-mortems (retry/failover patterns)
    - Latency p50/p95/p99 over historical windows
    """

    __tablename__ = "request_logs"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    # Correlates with X-Request-ID header and application logs / traces.
    request_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # OpenTelemetry trace ID (hex string) — populated when OTEL_ENABLED=true.
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # ── Tenant context (Phase 5) ──────────────────────────────────────────────
    # ON DELETE SET NULL: historical logs survive org/team deletion.
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    team_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Routing (Phase 3) ─────────────────────────────────────────────────────
    # NULL for requests rejected before routing (rate-limit, budget-block).
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    routing_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ── Outcome ───────────────────────────────────────────────────────────────
    # Controlled vocabulary: success | failure | rate_limited | budget_blocked | timeout
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Performance ───────────────────────────────────────────────────────────
    # Provider-level latency from response.metadata.latency_ms
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Token usage (Phase 2 normalized) ─────────────────────────────────────
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Cost (Phase 6) ────────────────────────────────────────────────────────
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Reliability (Phase 4) ─────────────────────────────────────────────────
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failover_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Populated only when failover_triggered=True
    failover_from_provider: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    failover_to_provider: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    circuit_breaker_state: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )

    # ── Budget (Phase 6) ──────────────────────────────────────────────────────
    # Policy configured on the team budget at request time.
    budget_policy_applied: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    # What the policy did: "blocked" | "warned" | "downgraded" | "none"
    budget_action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ── Timestamp ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )

    __table_args__ = (
        # Single-column indexes for point lookups
        Index("ix_request_logs_created_at", "created_at"),
        Index("ix_request_logs_team_id", "team_id"),
        Index("ix_request_logs_organization_id", "organization_id"),
        Index("ix_request_logs_provider", "provider"),
        Index("ix_request_logs_model", "model"),
        Index("ix_request_logs_status", "status"),
        # Composite indexes for analytics range queries
        Index("ix_rl_org_created", "organization_id", "created_at"),
        Index("ix_rl_team_created", "team_id", "created_at"),
        Index("ix_rl_provider_created", "provider", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RequestLog id={self.id!r} request_id={self.request_id!r} "
            f"status={self.status!r} provider={self.provider!r}>"
        )
