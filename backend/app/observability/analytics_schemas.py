"""
Cortex Gateway — Analytics API Pydantic Schemas (Phase 7).

All analytics responses use UTC datetimes.
Date range semantics: from=inclusive, to=exclusive.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

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
    team_id: Optional[str] = None
    organization_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    routing_mode: Optional[str] = None
    status: str
    http_status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    retry_count: int = 0
    failover_triggered: bool = False
    failover_from_provider: Optional[str] = None
    failover_to_provider: Optional[str] = None
    circuit_breaker_state: Optional[str] = None
    budget_policy_applied: Optional[str] = None
    budget_action: Optional[str] = None
    error_code: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestsAnalyticsResponse(BaseModel):
    data: List[RequestLogItem]
    pagination: PaginationMeta


# ── GET /api/v1/analytics/costs ──────────────────────────────────────────────


class CostGroupItem(BaseModel):
    group_key: str = Field(description="The group value (provider name, model, or team_id)")
    total_cost: float
    request_count: int
    total_tokens: int


class CostsAnalyticsResponse(BaseModel):
    group_by: str
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    data: List[CostGroupItem]

    model_config = {"populate_by_name": True}


# ── GET /api/v1/analytics/latency ────────────────────────────────────────────


class LatencyGroupItem(BaseModel):
    provider: Optional[str] = None
    request_count: int
    avg_latency_ms: Optional[float] = None
    p50_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    p99_latency_ms: Optional[float] = None


class LatencyAnalyticsResponse(BaseModel):
    data: List[LatencyGroupItem]


# ── GET /api/v1/analytics/errors ─────────────────────────────────────────────


class ErrorGroupItem(BaseModel):
    provider: Optional[str] = None
    error_code: Optional[str] = None
    count: int


class ErrorsAnalyticsResponse(BaseModel):
    data: List[ErrorGroupItem]


# ── GET /api/v1/analytics/fallbacks ──────────────────────────────────────────


class FallbackGroupItem(BaseModel):
    from_provider: Optional[str] = None
    to_provider: Optional[str] = None
    count: int


class FallbacksAnalyticsResponse(BaseModel):
    data: List[FallbackGroupItem]


# ── GET /api/v1/analytics/budget-events ──────────────────────────────────────


class BudgetEventItem(BaseModel):
    budget_action: Optional[str] = None
    budget_policy_applied: Optional[str] = None
    event_count: int


class BudgetEventsAnalyticsResponse(BaseModel):
    data: List[BudgetEventItem]


# ── GET /api/v1/analytics/timeseries ─────────────────────────────────────────


class TimeseriesBucket(BaseModel):
    timestamp: str = Field(description="Bucket start timestamp (ISO-8601 UTC)")
    request_count: int
    success_count: int
    error_count: int
    total_cost: float
    avg_latency_ms: Optional[float] = None


class TimeseriesAnalyticsResponse(BaseModel):
    bucket: str = Field(description="Bucket size: hour | day | week")
    data: List[TimeseriesBucket]
