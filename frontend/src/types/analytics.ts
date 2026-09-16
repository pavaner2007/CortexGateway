/** Analytics types — derived from backend analytics_schemas.py (Phase 7) */
import type { PaginationMeta } from './api'

// ── GET /api/v1/analytics/requests ────────────────────────────────────────────

export interface RequestLogItem {
  request_id: string
  team_id: string | null
  organization_id: string | null
  provider: string | null
  model: string | null
  routing_mode: string | null
  status: string
  http_status_code: number | null
  latency_ms: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  estimated_cost: number | null
  actual_cost: number | null
  retry_count: number
  failover_triggered: boolean
  failover_from_provider: string | null
  failover_to_provider: string | null
  circuit_breaker_state: string | null
  budget_policy_applied: string | null
  budget_action: string | null
  error_code: string | null
  trace_id: string | null
  created_at: string
}

export interface RequestsAnalyticsResponse {
  data: RequestLogItem[]
  pagination: PaginationMeta
}

// ── GET /api/v1/analytics/costs ───────────────────────────────────────────────

export interface CostGroupItem {
  group_key: string
  total_cost: number
  request_count: number
  total_tokens: number
}

export interface CostsAnalyticsResponse {
  group_by: string
  from: string | null
  to: string | null
  data: CostGroupItem[]
}

// ── GET /api/v1/analytics/latency ─────────────────────────────────────────────

export interface LatencyGroupItem {
  provider: string | null
  request_count: number
  avg_latency_ms: number | null
  p50_latency_ms: number | null
  p95_latency_ms: number | null
  p99_latency_ms: number | null
}

export interface LatencyAnalyticsResponse {
  data: LatencyGroupItem[]
}

// ── GET /api/v1/analytics/errors ──────────────────────────────────────────────

export interface ErrorGroupItem {
  provider: string | null
  error_code: string | null
  count: number
}

export interface ErrorsAnalyticsResponse {
  data: ErrorGroupItem[]
}

// ── GET /api/v1/analytics/fallbacks ──────────────────────────────────────────

export interface FallbackGroupItem {
  from_provider: string | null
  to_provider: string | null
  count: number
}

export interface FallbacksAnalyticsResponse {
  data: FallbackGroupItem[]
}

// ── GET /api/v1/analytics/budget-events ──────────────────────────────────────

export interface BudgetEventItem {
  budget_action: string | null
  budget_policy_applied: string | null
  event_count: number
}

export interface BudgetEventsAnalyticsResponse {
  data: BudgetEventItem[]
}

// ── GET /api/v1/analytics/timeseries ─────────────────────────────────────────

export interface TimeseriesBucket {
  timestamp: string
  request_count: number
  success_count: number
  error_count: number
  total_cost: number
  avg_latency_ms: number | null
}

export interface TimeseriesAnalyticsResponse {
  bucket: string
  data: TimeseriesBucket[]
}

// ── GET /api/v1/providers ────────────────────────────────────────────────────

export interface ProviderInfo {
  name: string
  enabled: boolean
  available: boolean
}

export interface ProviderListResponse {
  providers: ProviderInfo[]
}

// ── Date range helper ─────────────────────────────────────────────────────────

export type DateRange = '24h' | '7d' | '30d' | 'month'

export function dateRangeToParams(range: DateRange): { from: string; to: string } {
  const now = new Date()
  const to = now.toISOString()
  const from = new Date(now)
  if (range === '24h') from.setHours(from.getHours() - 24)
  else if (range === '7d') from.setDate(from.getDate() - 7)
  else if (range === '30d') from.setDate(from.getDate() - 30)
  else {
    // 'month' = calendar month start
    from.setDate(1)
    from.setHours(0, 0, 0, 0)
  }
  return { from: from.toISOString(), to }
}

export function dateRangeToBucket(range: DateRange): 'hour' | 'day' | 'week' {
  if (range === '24h') return 'hour'
  if (range === '7d') return 'day'
  return 'day'
}
