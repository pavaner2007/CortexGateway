"""
Cortex Gateway — Analytics API Pydantic Schemas (Phase 7).

All analytics responses use UTC datetimes.
Date range semantics: from=inclusive, to=exclusive.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ── Shared ────────────────────────────────────────────────────────────────────


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int


# ── GET /api/v1/analytics/requests ───────────────────────────────────────────


class RequestLogItem(BaseModel):
    """One row of the request log — metadata only, no sensitive content."""

    request_id: str
    team_id: str | None = None
    organization_id: str | None = None
    provider: str | None = None
    model: str | None = None
    routing_mode: str | None = None
    status: str
    http_status_code: int | None = None
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None
    actual_cost: float | None = None
    retry_count: int = 0
    failover_triggered: bool = False
    failover_from_provider: str | None = None
    failover_to_provider: str | None = None
    circuit_breaker_state: str | None = None
    budget_policy_applied: str | None = None
    budget_action: str | None = None
    error_code: str | None = None
    trace_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestsAnalyticsResponse(BaseModel):
    data: list[RequestLogItem]
    pagination: PaginationMeta


# ── GET /api/v1/analytics/costs ──────────────────────────────────────────────


class CostGroupItem(BaseModel):
    group_key: str = Field(description="The group value (provider name, model, or team_id)")
    total_cost: float
    request_count: int
    total_tokens: int


class CostsAnalyticsResponse(BaseModel):
    group_by: str
    from_: str | None = Field(None, alias="from")
    to: str | None = None
    data: list[CostGroupItem]

    model_config = {"populate_by_name": True}


# ── GET /api/v1/analytics/latency ────────────────────────────────────────────


class LatencyGroupItem(BaseModel):
    provider: str | None = None
    request_count: int
    avg_latency_ms: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None


class LatencyAnalyticsResponse(BaseModel):
    data: list[LatencyGroupItem]


# ── GET /api/v1/analytics/errors ─────────────────────────────────────────────


class ErrorGroupItem(BaseModel):
    provider: str | None = None
    error_code: str | None = None
    count: int


class ErrorsAnalyticsResponse(BaseModel):
    data: list[ErrorGroupItem]


# ── GET /api/v1/analytics/fallbacks ──────────────────────────────────────────


class FallbackGroupItem(BaseModel):
    from_provider: str | None = None
    to_provider: str | None = None
    count: int


class FallbacksAnalyticsResponse(BaseModel):
    data: list[FallbackGroupItem]


# ── GET /api/v1/analytics/budget-events ──────────────────────────────────────


class BudgetEventItem(BaseModel):
    budget_action: str | None = None
    budget_policy_applied: str | None = None
    event_count: int


class BudgetEventsAnalyticsResponse(BaseModel):
    data: list[BudgetEventItem]


# ── GET /api/v1/analytics/timeseries ─────────────────────────────────────────


class TimeseriesBucket(BaseModel):
    timestamp: str = Field(description="Bucket start timestamp (ISO-8601 UTC)")
    request_count: int
    success_count: int
    error_count: int
    total_cost: float
    avg_latency_ms: float | None = None


class TimeseriesAnalyticsResponse(BaseModel):
    bucket: str = Field(description="Bucket size: hour | day | week")
    data: list[TimeseriesBucket]
