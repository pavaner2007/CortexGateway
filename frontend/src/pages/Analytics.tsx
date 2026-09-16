import { useState } from 'react'
import AdminLayout from '../components/layout/AdminLayout'
import TimeseriesChart from '../components/charts/TimeseriesChart'
import CostChart from '../components/charts/CostChart'
import LatencyChart from '../components/charts/LatencyChart'
import Badge from '../components/common/Badge'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { useTimeseries, useCosts, useLatency, useErrors, useFallbacks, useBudgetEvents } from '../hooks/useAnalytics'
import { dateRangeToParams, dateRangeToBucket, type DateRange } from '../types/analytics'

const RANGES: { label: string; value: DateRange }[] = [
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
  { label: 'Month', value: 'month' },
]

const COST_GROUPS = ['provider', 'model', 'team'] as const
type CostGroup = typeof COST_GROUPS[number]

export default function Analytics() {
  const [range, setRange] = useState<DateRange>('7d')
  const [costGroup, setCostGroup] = useState<CostGroup>('provider')

  const params = dateRangeToParams(range)
  const bucket = dateRangeToBucket(range)

  const tsQuery = useTimeseries({ ...params, bucket }, 60_000)
  const costsQuery = useCosts({ ...params, group_by: costGroup })
  const latencyQuery = useLatency(params)
  const errorsQuery = useErrors(params)
  const fallbacksQuery = useFallbacks(params)
  const budgetEventsQuery = useBudgetEvents(params)

  const tsData = tsQuery.data?.data ?? []

  const costsData = costsQuery.data?.data ?? []
  const totalCost = costsData.reduce((s, d) => s + d.total_cost, 0)
  const totalTokensFromCosts = costsData.reduce((s, d) => s + d.total_tokens, 0)

  return (
    <AdminLayout
      title="Analytics"
      subtitle="Historical request analytics"
      action={
        <div className="flex items-center gap-1 p-1 glass-card rounded-xl">
          {RANGES.map(r => (
            <button
              key={r.value}
              id={`analytics-range-${r.value}`}
              onClick={() => setRange(r.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                range === r.value
                  ? 'bg-brand-500/30 text-brand-300 border border-brand-500/40'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      }
    >
      {/* Requests */}
      <section className="mb-6">
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Requests Over Time</h2>
          {tsQuery.isError ? (
            <ErrorState message="Could not load request data" onRetry={() => tsQuery.refetch()} />
          ) : (
            <TimeseriesChart data={tsData} loading={tsQuery.isLoading} bucket={bucket} />
          )}
        </div>
      </section>

      {/* Costs */}
      <section className="mb-6">
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-300">Cost Analytics</h2>
              <p className="text-xs text-slate-600 mt-0.5">
                Total: ${totalCost.toFixed(6)} · {totalTokensFromCosts.toLocaleString()} tokens
              </p>
            </div>
            <div className="flex gap-1">
              {COST_GROUPS.map(g => (
                <button
                  key={g}
                  onClick={() => setCostGroup(g)}
                  className={`px-2 py-1 rounded text-xs transition-colors ${
                    costGroup === g
                      ? 'bg-brand-500/20 text-brand-400'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
          {costsQuery.isError ? (
            <ErrorState message="Could not load cost data" onRetry={() => costsQuery.refetch()} />
          ) : (
            <CostChart data={costsQuery.data?.data ?? []} loading={costsQuery.isLoading} groupBy={costGroup} />
          )}
        </div>
      </section>

      {/* Latency */}
      <section className="mb-6">
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Latency (p50 / p95 / p99)</h2>
          {latencyQuery.isError ? (
            <ErrorState message="Could not load latency data" onRetry={() => latencyQuery.refetch()} />
          ) : (
            <LatencyChart data={latencyQuery.data?.data ?? []} loading={latencyQuery.isLoading} />
          )}
        </div>
      </section>

      {/* Errors + Fallbacks + Budget Events */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Errors */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Errors</h2>
          {errorsQuery.isLoading ? (
            <div className="animate-pulse space-y-2">{[1,2,3].map(i => <div key={i} className="h-8 bg-white/5 rounded" />)}</div>
          ) : errorsQuery.isError ? (
            <ErrorState message="Could not load errors" />
          ) : (errorsQuery.data?.data ?? []).length === 0 ? (
            <EmptyState title="No errors 🎉" />
          ) : (
            <div className="space-y-2">
              {(errorsQuery.data?.data ?? []).slice(0, 8).map((e, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div>
                    <span className="text-xs text-slate-400">{e.provider ?? '?'}</span>
                    {e.error_code && (
                      <Badge variant="error" className="ml-2">{e.error_code}</Badge>
                    )}
                  </div>
                  <span className="text-xs font-semibold text-rose-400">{e.count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Fallbacks */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Failovers</h2>
          {fallbacksQuery.isLoading ? (
            <div className="animate-pulse space-y-2">{[1,2].map(i => <div key={i} className="h-8 bg-white/5 rounded" />)}</div>
          ) : fallbacksQuery.isError ? (
            <ErrorState message="Could not load fallbacks" />
          ) : (fallbacksQuery.data?.data ?? []).length === 0 ? (
            <EmptyState title="No failovers" />
          ) : (
            <div className="space-y-2">
              {(fallbacksQuery.data?.data ?? []).map((f, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">
                    {f.from_provider ?? '?'} → {f.to_provider ?? '?'}
                  </span>
                  <Badge variant="warning">{f.count}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Budget Events */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Budget Events</h2>
          {budgetEventsQuery.isLoading ? (
            <div className="animate-pulse space-y-2">{[1,2].map(i => <div key={i} className="h-8 bg-white/5 rounded" />)}</div>
          ) : budgetEventsQuery.isError ? (
            <ErrorState message="Could not load budget events" />
          ) : (budgetEventsQuery.data?.data ?? []).length === 0 ? (
            <EmptyState title="No budget events" />
          ) : (
            <div className="space-y-2">
              {(budgetEventsQuery.data?.data ?? []).map((e, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <div>
                    <span className="text-slate-400">{e.budget_action ?? '?'}</span>
                    {e.budget_policy_applied && (
                      <Badge variant="warning" className="ml-2">{e.budget_policy_applied}</Badge>
                    )}
                  </div>
                  <span className="font-semibold text-amber-400">{e.event_count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AdminLayout>
  )
}
