"""
Cortex Gateway — Analytics Query Service (Phase 7).

All queries are:
  - Scoped to the caller's organization_id — never trust URL params for org.
  - Aggregated in PostgreSQL — no Python-side row loading for aggregation.
  - Bounded by max_page_size to prevent unbounded queries.
  - Protected against SQL injection: group_by uses a whitelist, never
    interpolated directly into SQL column names.

Date semantics: from (inclusive) → to (exclusive), both UTC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, text, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.models import RequestLog

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50

# Whitelist for group_by — keys that map to actual column expressions.
# Never interpolate user input directly into SQL identifiers.
_GROUP_BY_COLUMNS = {
    "provider": RequestLog.provider,
    "model": RequestLog.model,
    "team": RequestLog.team_id,
}


def _apply_common_filters(
    stmt,
    *,
    organization_id: str,
    team_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
):
    """Apply organization scoping + optional filters to a SQLAlchemy statement."""
    stmt = stmt.where(RequestLog.organization_id == organization_id)
    if team_id:
        stmt = stmt.where(RequestLog.team_id == team_id)
    if provider:
        stmt = stmt.where(RequestLog.provider == provider)
    if model:
        stmt = stmt.where(RequestLog.model == model)
    if status:
        stmt = stmt.where(RequestLog.status == status)
    if from_dt:
        stmt = stmt.where(RequestLog.created_at >= from_dt)
    if to_dt:
        stmt = stmt.where(RequestLog.created_at < to_dt)
    return stmt


class AnalyticsService:
    """Read-only analytics queries against RequestLog."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── GET /api/v1/analytics/requests ───────────────────────────────────────

    async def list_requests(
        self,
        *,
        organization_id: str,
        team_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Tuple[List[RequestLog], int]:
        """Return paginated request logs and total count for the org."""
        page_size = min(page_size, MAX_PAGE_SIZE)
        offset = (page - 1) * page_size

        base = select(RequestLog)
        base = _apply_common_filters(
            base,
            organization_id=organization_id,
            team_id=team_id,
            provider=provider,
            model=model,
            status=status,
            from_dt=from_dt,
            to_dt=to_dt,
        )

        # Count query
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        # Data query
        data_stmt = (
            base.order_by(RequestLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self._session.execute(data_stmt)).scalars().all()
        return list(rows), total

    # ── GET /api/v1/analytics/costs ──────────────────────────────────────────

    async def aggregate_costs(
        self,
        *,
        organization_id: str,
        group_by: str = "provider",
        team_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregate costs grouped by provider, model, or team."""
        if group_by not in _GROUP_BY_COLUMNS:
            group_by = "provider"

        group_col = _GROUP_BY_COLUMNS[group_by]

        stmt = select(
            group_col.label("group_key"),
            func.coalesce(func.sum(RequestLog.actual_cost), 0.0).label("total_cost"),
            func.count(RequestLog.id).label("request_count"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
        ).group_by(group_col)

        stmt = _apply_common_filters(
            stmt,
            organization_id=organization_id,
            team_id=team_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )
        stmt = stmt.order_by(func.sum(RequestLog.actual_cost).desc().nullslast())

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "group_key": str(r.group_key) if r.group_key else "unknown",
                "total_cost": float(r.total_cost or 0),
                "request_count": int(r.request_count),
                "total_tokens": int(r.total_tokens or 0),
            }
            for r in rows
        ]

    # ── GET /api/v1/analytics/latency ────────────────────────────────────────

    async def aggregate_latency(
        self,
        *,
        organization_id: str,
        provider: Optional[str] = None,
        team_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregate latency statistics per provider using PostgreSQL percentile_cont."""
        # We group by provider; filter to rows with latency data
        stmt = select(
            RequestLog.provider,
            func.count(RequestLog.id).label("request_count"),
            func.avg(RequestLog.latency_ms).label("avg_latency_ms"),
            func.percentile_cont(0.50).within_group(
                RequestLog.latency_ms.asc()
            ).label("p50"),
            func.percentile_cont(0.95).within_group(
                RequestLog.latency_ms.asc()
            ).label("p95"),
            func.percentile_cont(0.99).within_group(
                RequestLog.latency_ms.asc()
            ).label("p99"),
        ).where(
            RequestLog.latency_ms.isnot(None)
        ).group_by(RequestLog.provider)

        stmt = _apply_common_filters(
            stmt,
            organization_id=organization_id,
            provider=provider,
            team_id=team_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )
        stmt = stmt.order_by(RequestLog.provider)

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "provider": r.provider,
                "request_count": int(r.request_count),
                "avg_latency_ms": round(float(r.avg_latency_ms), 2) if r.avg_latency_ms else None,
                "p50_latency_ms": round(float(r.p50), 2) if r.p50 else None,
                "p95_latency_ms": round(float(r.p95), 2) if r.p95 else None,
                "p99_latency_ms": round(float(r.p99), 2) if r.p99 else None,
            }
            for r in rows
        ]

    # ── GET /api/v1/analytics/errors ─────────────────────────────────────────

    async def aggregate_errors(
        self,
        *,
        organization_id: str,
        provider: Optional[str] = None,
        team_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Count errors grouped by provider + error_code, sorted by frequency."""
        stmt = select(
            RequestLog.provider,
            RequestLog.error_code,
            func.count(RequestLog.id).label("count"),
        ).where(
            RequestLog.error_code.isnot(None)
        ).group_by(
            RequestLog.provider, RequestLog.error_code
        )

        stmt = _apply_common_filters(
            stmt,
            organization_id=organization_id,
            provider=provider,
            team_id=team_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )
        stmt = stmt.order_by(func.count(RequestLog.id).desc())

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "provider": r.provider,
                "error_code": r.error_code,
                "count": int(r.count),
            }
            for r in rows
        ]

    # ── GET /api/v1/analytics/fallbacks ──────────────────────────────────────

    async def aggregate_fallbacks(
        self,
        *,
        organization_id: str,
        team_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Count failovers by from_provider → to_provider pair."""
        stmt = select(
            RequestLog.failover_from_provider,
            RequestLog.failover_to_provider,
            func.count(RequestLog.id).label("count"),
        ).where(
            RequestLog.failover_triggered == True  # noqa: E712
        ).group_by(
            RequestLog.failover_from_provider,
            RequestLog.failover_to_provider,
        )

        stmt = _apply_common_filters(
            stmt,
            organization_id=organization_id,
            team_id=team_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )
        stmt = stmt.order_by(func.count(RequestLog.id).desc())

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "from_provider": r.failover_from_provider,
                "to_provider": r.failover_to_provider,
                "count": int(r.count),
            }
            for r in rows
        ]

    # ── GET /api/v1/analytics/budget-events ──────────────────────────────────

    async def aggregate_budget_events(
        self,
        *,
        organization_id: str,
        team_id: Optional[str] = None,
        policy: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Count budget events (blocked/warned/downgraded) by action + policy."""
        stmt = select(
            RequestLog.budget_action,
            RequestLog.budget_policy_applied,
            func.count(RequestLog.id).label("event_count"),
        ).where(
            RequestLog.budget_action.isnot(None),
            RequestLog.budget_action != "none",
        ).group_by(
            RequestLog.budget_action,
            RequestLog.budget_policy_applied,
        )

        stmt = _apply_common_filters(
            stmt,
            organization_id=organization_id,
            team_id=team_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )
        if policy:
            stmt = stmt.where(
                RequestLog.budget_policy_applied == policy.upper()
            )
        stmt = stmt.order_by(func.count(RequestLog.id).desc())

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "budget_action": r.budget_action,
                "budget_policy_applied": r.budget_policy_applied,
                "event_count": int(r.event_count),
            }
            for r in rows
        ]

    # ── GET /api/v1/analytics/timeseries ─────────────────────────────────────

    async def timeseries(
        self,
        *,
        organization_id: str,
        bucket: str = "day",
        team_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Time-bucketed request/cost/error counts using PostgreSQL date_trunc."""
        valid_buckets = {"hour", "day", "week"}
        if bucket not in valid_buckets:
            bucket = "day"

        # Use PostgreSQL date_trunc for time bucketing
        bucket_expr = func.date_trunc(bucket, RequestLog.created_at).label("ts")

        stmt = select(
            bucket_expr,
            func.count(RequestLog.id).label("request_count"),
            func.sum(
                case((RequestLog.status == "success", 1), else_=0)
            ).label("success_count"),
            func.sum(
                case((RequestLog.status == "failure", 1), else_=0)
            ).label("error_count"),
            func.coalesce(func.sum(RequestLog.actual_cost), 0.0).label("total_cost"),
            func.avg(RequestLog.latency_ms).label("avg_latency_ms"),
        ).group_by(bucket_expr)

        stmt = _apply_common_filters(
            stmt,
            organization_id=organization_id,
            team_id=team_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )
        stmt = stmt.order_by(bucket_expr)

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "timestamp": r.ts.isoformat() if r.ts else "",
                "request_count": int(r.request_count),
                "success_count": int(r.success_count or 0),
                "error_count": int(r.error_count or 0),
                "total_cost": float(r.total_cost or 0),
                "avg_latency_ms": round(float(r.avg_latency_ms), 2) if r.avg_latency_ms else None,
            }
            for r in rows
        ]
