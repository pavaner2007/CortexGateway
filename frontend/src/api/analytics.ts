/**
 * Analytics API — wraps all Phase 7 analytics endpoints
 */
import { apiRequest } from './client'
import type {
  RequestsAnalyticsResponse,
  CostsAnalyticsResponse,
  LatencyAnalyticsResponse,
  ErrorsAnalyticsResponse,
  FallbacksAnalyticsResponse,
  BudgetEventsAnalyticsResponse,
  TimeseriesAnalyticsResponse,
  ProviderListResponse,
} from '../types/analytics'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function qs(params: object): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params as Record<string, unknown>)) {
    if (v !== undefined && v !== null && v !== '') {
      p.set(k, String(v))
    }
  }
  const str = p.toString()
  return str ? `?${str}` : ''
}

// ── Paginated request log ─────────────────────────────────────────────────────

export interface RequestsParams {
  team_id?: string
  provider?: string
  model?: string
  status?: string
  request_id?: string
  from?: string
  to?: string
  page?: number
  page_size?: number
}

export async function getRequests(params: RequestsParams = {}): Promise<RequestsAnalyticsResponse> {
  return apiRequest<RequestsAnalyticsResponse>(`/api/v1/analytics/requests${qs(params)}`)
}

// ── Cost analytics ────────────────────────────────────────────────────────────

export interface CostsParams {
  group_by?: 'provider' | 'model' | 'team'
  team_id?: string
  from?: string
  to?: string
}

export async function getCosts(params: CostsParams = {}): Promise<CostsAnalyticsResponse> {
  return apiRequest<CostsAnalyticsResponse>(`/api/v1/analytics/costs${qs(params)}`)
}

// ── Latency analytics ─────────────────────────────────────────────────────────

export interface LatencyParams {
  provider?: string
  team_id?: string
  from?: string
  to?: string
}

export async function getLatency(params: LatencyParams = {}): Promise<LatencyAnalyticsResponse> {
  return apiRequest<LatencyAnalyticsResponse>(`/api/v1/analytics/latency${qs(params)}`)
}

// ── Error analytics ───────────────────────────────────────────────────────────

export interface ErrorsParams {
  provider?: string
  team_id?: string
  from?: string
  to?: string
}

export async function getErrors(params: ErrorsParams = {}): Promise<ErrorsAnalyticsResponse> {
  return apiRequest<ErrorsAnalyticsResponse>(`/api/v1/analytics/errors${qs(params)}`)
}

// ── Fallback analytics ────────────────────────────────────────────────────────

export interface FallbacksParams {
  team_id?: string
  from?: string
  to?: string
}

export async function getFallbacks(params: FallbacksParams = {}): Promise<FallbacksAnalyticsResponse> {
  return apiRequest<FallbacksAnalyticsResponse>(`/api/v1/analytics/fallbacks${qs(params)}`)
}

// ── Budget event analytics ────────────────────────────────────────────────────

export interface BudgetEventsParams {
  team_id?: string
  policy?: string
  from?: string
  to?: string
}

export async function getBudgetEvents(
  params: BudgetEventsParams = {},
): Promise<BudgetEventsAnalyticsResponse> {
  return apiRequest<BudgetEventsAnalyticsResponse>(`/api/v1/analytics/budget-events${qs(params)}`)
}

// ── Timeseries ────────────────────────────────────────────────────────────────

export interface TimeseriesParams {
  bucket?: 'hour' | 'day' | 'week'
  team_id?: string
  from?: string
  to?: string
}

export async function getTimeseries(
  params: TimeseriesParams = {},
): Promise<TimeseriesAnalyticsResponse> {
  return apiRequest<TimeseriesAnalyticsResponse>(`/api/v1/analytics/timeseries${qs(params)}`)
}

// ── Providers (unauthenticated) ───────────────────────────────────────────────

export async function getProviders(): Promise<ProviderListResponse> {
  return apiRequest<ProviderListResponse>('/api/v1/providers', { unauthenticated: true })
}
