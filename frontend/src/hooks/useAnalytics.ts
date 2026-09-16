import { useQuery } from '@tanstack/react-query'
import {
  getTimeseries,
  getCosts,
  getLatency,
  getErrors,
  getFallbacks,
  getBudgetEvents,
  getRequests,
  getProviders,
} from '../api/analytics'
import type {
  TimeseriesParams,
  CostsParams,
  LatencyParams,
  ErrorsParams,
  FallbacksParams,
  BudgetEventsParams,
  RequestsParams,
} from '../api/analytics'

export const analyticsKeys = {
  timeseries: (p: TimeseriesParams) => ['analytics', 'timeseries', p] as const,
  costs: (p: CostsParams) => ['analytics', 'costs', p] as const,
  latency: (p: LatencyParams) => ['analytics', 'latency', p] as const,
  errors: (p: ErrorsParams) => ['analytics', 'errors', p] as const,
  fallbacks: (p: FallbacksParams) => ['analytics', 'fallbacks', p] as const,
  budgetEvents: (p: BudgetEventsParams) => ['analytics', 'budget-events', p] as const,
  requests: (p: RequestsParams) => ['analytics', 'requests', p] as const,
  providers: () => ['providers'] as const,
}

export function useTimeseries(params: TimeseriesParams, refetchInterval?: number) {
  return useQuery({
    queryKey: analyticsKeys.timeseries(params),
    queryFn: () => getTimeseries(params),
    staleTime: 30_000,
    refetchInterval,
  })
}

export function useCosts(params: CostsParams) {
  return useQuery({
    queryKey: analyticsKeys.costs(params),
    queryFn: () => getCosts(params),
    staleTime: 60_000,
  })
}

export function useLatency(params: LatencyParams) {
  return useQuery({
    queryKey: analyticsKeys.latency(params),
    queryFn: () => getLatency(params),
    staleTime: 60_000,
  })
}

export function useErrors(params: ErrorsParams) {
  return useQuery({
    queryKey: analyticsKeys.errors(params),
    queryFn: () => getErrors(params),
    staleTime: 60_000,
  })
}

export function useFallbacks(params: FallbacksParams) {
  return useQuery({
    queryKey: analyticsKeys.fallbacks(params),
    queryFn: () => getFallbacks(params),
    staleTime: 60_000,
  })
}

export function useBudgetEvents(params: BudgetEventsParams) {
  return useQuery({
    queryKey: analyticsKeys.budgetEvents(params),
    queryFn: () => getBudgetEvents(params),
    staleTime: 60_000,
  })
}

export function useRequests(params: RequestsParams) {
  return useQuery({
    queryKey: analyticsKeys.requests(params),
    queryFn: () => getRequests(params),
    staleTime: 30_000,
  })
}

export function useProviders(refetchInterval?: number) {
  return useQuery({
    queryKey: analyticsKeys.providers(),
    queryFn: getProviders,
    staleTime: 30_000,
    refetchInterval,
  })
}
