"""
Cortex Gateway — Analytics REST Endpoints (Phase 7).

All endpoints:
  - Require an authenticated API key (admin role only).
  - Scope all queries to the caller's organization_id (from RequestContext).
    organization_id is NEVER taken from query parameters.
  - Support optional team_id filter (cross-org teams return empty data).
  - Support date range: from (inclusive), to (exclusive) ISO-8601 UTC.
  - Use database-side aggregation — no large row loads into Python.

Endpoints:
  GET /api/v1/analytics/requests          Paginated request log
  GET /api/v1/analytics/costs             Cost breakdown by provider/model/team
  GET /api/v1/analytics/latency           p50/p95/p99 latency by provider
  GET /api/v1/analytics/errors            Error counts by provider + error_code
  GET /api/v1/analytics/fallbacks         Failover counts by from→to provider
  GET /api/v1/analytics/budget-events     Budget action event counts
  GET /api/v1/analytics/timeseries        Time-bucketed request/cost/error counts
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_request_context, require_admin
from app.auth.schemas import RequestContext
from app.database.session import get_db_dependency
from app.observability.analytics_schemas import (
    BudgetEventsAnalyticsResponse,
    CostsAnalyticsResponse,
    CostGroupItem,
    ErrorsAnalyticsResponse,
    FallbacksAnalyticsResponse,
    LatencyAnalyticsResponse,
    PaginationMeta,
    RequestsAnalyticsResponse,
    TimeseriesAnalyticsResponse,
)
from app.observability.analytics_service import AnalyticsService, MAX_PAGE_SIZE

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _get_analytics_service(
    session: AsyncSession = Depends(get_db_dependency),
) -> AnalyticsService:
    return AnalyticsService(session=session)


# ── GET /api/v1/analytics/requests ───────────────────────────────────────────


@router.get(
    "/requests",
    response_model=RequestsAnalyticsResponse,
    summary="Paginated Request Log",
    description=(
        "Return paginated request log entries for the authenticated organization. "
        "Requires admin role. Scoped to caller's org automatically."
    ),
)
async def get_requests(
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    model: Optional[str] = Query(None, description="Filter by model name"),
    status: Optional[str] = Query(None, description="Filter by status (success/failure/rate_limited/budget_blocked/timeout)"),
    request_id: Optional[str] = Query(None, description="Filter by exact request_id (for detail lookup)"),
    from_: Optional[datetime] = Query(None, alias="from", description="Start datetime (UTC, inclusive)"),
    to: Optional[datetime] = Query(None, description="End datetime (UTC, exclusive)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE, description=f"Results per page (max {MAX_PAGE_SIZE})"),
    context: RequestContext = Depends(require_admin),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> RequestsAnalyticsResponse:
    rows, total = await service.list_requests(
        organization_id=context.organization_id,
        team_id=team_id,
        provider=provider,
        model=model,
        status=status,
        request_id=request_id,
        from_dt=from_,
        to_dt=to,
        page=page,
        page_size=page_size,
    )
    from app.observability.analytics_schemas import RequestLogItem
    return RequestsAnalyticsResponse(
        data=[RequestLogItem.model_validate(r) for r in rows],
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )


# ── GET /api/v1/analytics/costs ──────────────────────────────────────────────


@router.get(
    "/costs",
    response_model=CostsAnalyticsResponse,
    summary="Aggregated Cost Analytics",
    description=(
        "Return cost aggregates grouped by provider, model, or team. "
        "Requires admin role."
    ),
)
async def get_costs(
    group_by: str = Query("provider", description="Aggregation dimension: provider | model | team"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    from_: Optional[datetime] = Query(None, alias="from", description="Start datetime (UTC, inclusive)"),
    to: Optional[datetime] = Query(None, description="End datetime (UTC, exclusive)"),
    context: RequestContext = Depends(require_admin),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> CostsAnalyticsResponse:
    data = await service.aggregate_costs(
        organization_id=context.organization_id,
        group_by=group_by,
        team_id=team_id,
        from_dt=from_,
        to_dt=to,
    )
    return CostsAnalyticsResponse(
        group_by=group_by,
        **{"from": from_.isoformat() if from_ else None},
        to=to.isoformat() if to else None,
        data=[CostGroupItem(**d) for d in data],
    )


# ── GET /api/v1/analytics/latency ────────────────────────────────────────────


@router.get(
    "/latency",
    response_model=LatencyAnalyticsResponse,
    summary="Latency Analytics (p50/p95/p99)",
    description=(
        "Return latency statistics per provider (avg, p50, p95, p99). "
        "Requires admin role."
    ),
)
async def get_latency(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    from_: Optional[datetime] = Query(None, alias="from", description="Start datetime (UTC, inclusive)"),
    to: Optional[datetime] = Query(None, description="End datetime (UTC, exclusive)"),
    context: RequestContext = Depends(require_admin),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> LatencyAnalyticsResponse:
    from app.observability.analytics_schemas import LatencyGroupItem
    data = await service.aggregate_latency(
        organization_id=context.organization_id,
        provider=provider,
        team_id=team_id,
        from_dt=from_,
        to_dt=to,
    )
    return LatencyAnalyticsResponse(data=[LatencyGroupItem(**d) for d in data])


# ── GET /api/v1/analytics/errors ─────────────────────────────────────────────


@router.get(
    "/errors",
    response_model=ErrorsAnalyticsResponse,
    summary="Error Analytics",
    description=(
        "Return error counts by provider and error code, sorted by frequency. "
        "Requires admin role."
    ),
)
async def get_errors(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    from_: Optional[datetime] = Query(None, alias="from", description="Start datetime (UTC, inclusive)"),
    to: Optional[datetime] = Query(None, description="End datetime (UTC, exclusive)"),
    context: RequestContext = Depends(require_admin),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> ErrorsAnalyticsResponse:
    from app.observability.analytics_schemas import ErrorGroupItem
    data = await service.aggregate_errors(
        organization_id=context.organization_id,
        provider=provider,
        team_id=team_id,
        from_dt=from_,
        to_dt=to,
    )
    return ErrorsAnalyticsResponse(data=[ErrorGroupItem(**d) for d in data])


# ── GET /api/v1/analytics/fallbacks ──────────────────────────────────────────


@router.get(
    "/fallbacks",
    response_model=FallbacksAnalyticsResponse,
    summary="Fallback / Failover Analytics",
    description=(
        "Return failover counts grouped by from_provider → to_provider. "
        "Requires admin role."
    ),
)
async def get_fallbacks(
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    from_: Optional[datetime] = Query(None, alias="from", description="Start datetime (UTC, inclusive)"),
    to: Optional[datetime] = Query(None, description="End datetime (UTC, exclusive)"),
    context: RequestContext = Depends(require_admin),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> FallbacksAnalyticsResponse:
    from app.observability.analytics_schemas import FallbackGroupItem
    data = await service.aggregate_fallbacks(
        organization_id=context.organization_id,
        team_id=team_id,
        from_dt=from_,
        to_dt=to,
    )
    return FallbacksAnalyticsResponse(data=[FallbackGroupItem(**d) for d in data])


# ── GET /api/v1/analytics/budget-events ──────────────────────────────────────


@router.get(
    "/budget-events",
    response_model=BudgetEventsAnalyticsResponse,
    summary="Budget Event Analytics",
    description=(
        "Return budget action event counts (blocked/warned/downgraded) by policy. "
        "Requires admin role."
    ),
)
async def get_budget_events(
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    policy: Optional[str] = Query(None, description="Filter by policy: BLOCK | WARN | DOWNGRADE"),
    from_: Optional[datetime] = Query(None, alias="from", description="Start datetime (UTC, inclusive)"),
    to: Optional[datetime] = Query(None, description="End datetime (UTC, exclusive)"),
    context: RequestContext = Depends(require_admin),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> BudgetEventsAnalyticsResponse:
    from app.observability.analytics_schemas import BudgetEventItem
    data = await service.aggregate_budget_events(
        organization_id=context.organization_id,
        team_id=team_id,
        policy=policy,
        from_dt=from_,
        to_dt=to,
    )
    return BudgetEventsAnalyticsResponse(data=[BudgetEventItem(**d) for d in data])


# ── GET /api/v1/analytics/timeseries ─────────────────────────────────────────


@router.get(
    "/timeseries",
    response_model=TimeseriesAnalyticsResponse,
    summary="Time-Bucketed Analytics",
    description=(
        "Return request/cost/error counts in time buckets (hour/day/week). "
        "Suitable for trend charts in Phase 8 dashboards. "
        "Requires admin role."
    ),
)
async def get_timeseries(
    bucket: str = Query("day", description="Time bucket size: hour | day | week"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    from_: Optional[datetime] = Query(None, alias="from", description="Start datetime (UTC, inclusive)"),
    to: Optional[datetime] = Query(None, description="End datetime (UTC, exclusive)"),
    context: RequestContext = Depends(require_admin),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> TimeseriesAnalyticsResponse:
    from app.observability.analytics_schemas import TimeseriesBucket
    data = await service.timeseries(
        organization_id=context.organization_id,
        bucket=bucket,
        team_id=team_id,
        from_dt=from_,
        to_dt=to,
    )
    return TimeseriesAnalyticsResponse(
        bucket=bucket,
        data=[TimeseriesBucket(**d) for d in data],
    )
