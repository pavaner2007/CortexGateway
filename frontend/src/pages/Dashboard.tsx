import { useState } from 'react'
import AdminLayout from '../components/layout/AdminLayout'
import KpiCard from '../components/cards/KpiCard'
import TimeseriesChart from '../components/charts/TimeseriesChart'
import CostChart from '../components/charts/CostChart'
import ErrorState from '../components/common/ErrorState'
import { useTimeseries, useCosts, useLatency } from '../hooks/useAnalytics'
import { dateRangeToParams, dateRangeToBucket, type DateRange } from '../types/analytics'
import { useAuth } from '../auth/AuthContext'

const RANGES: { label: string; value: DateRange }[] = [
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
  { label: 'Month', value: 'month' },
]

export default function Dashboard() {
  const [range, setRange] = useState<DateRange>('24h')
  const { session } = useAuth()
  const params = dateRangeToParams(range)
  const bucket = dateRangeToBucket(range)

  const tsQuery = useTimeseries({ ...params, bucket }, 60_000)
  const costsQuery = useCosts({ ...params, group_by: 'provider' })
  const latencyQuery = useLatency(params)

  const tsData = tsQuery.data?.data ?? []
  const totalRequests = tsData.reduce((s, d) => s + d.request_count, 0)
  const totalErrors = tsData.reduce((s, d) => s + d.error_count, 0)
  const totalCost = tsData.reduce((s, d) => s + d.total_cost, 0)
  const avgLatency = latencyQuery.data?.data[0]?.avg_latency_ms ?? null
  const errorRate = totalRequests > 0 ? ((totalErrors / totalRequests) * 100).toFixed(1) : '0.0'

  return (
    <AdminLayout
      title="Dashboard"
      subtitle="Gateway overview"
      action={
        <div className="flex items-center gap-1 p-1 glass-card rounded-xl">
          {RANGES.map(r => (
            <button
              key={r.value}
              id={`range-${r.value}`}
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
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="Total Requests"
          value={totalRequests.toLocaleString()}
          loading={tsQuery.isLoading}
          icon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          }
        />
        <KpiCard
          label="Total Errors"
          value={totalErrors.toLocaleString()}
          loading={tsQuery.isLoading}
          icon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M12 3a9 9 0 100 18A9 9 0 0012 3z" />
            </svg>
          }
        />
        <KpiCard
          label="Error Rate"
          value={`${errorRate}%`}
          loading={tsQuery.isLoading}
          trend={parseFloat(errorRate) > 5 ? 'down' : 'neutral'}
          icon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
            </svg>
          }
        />
        <KpiCard
          label="Avg Latency"
          value={avgLatency !== null ? `${avgLatency.toFixed(0)}ms` : '—'}
          loading={latencyQuery.isLoading}
          icon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <KpiCard
          label={`Cost (${range})`}
          value={`$${totalCost.toFixed(6)}`}
          loading={tsQuery.isLoading}
          icon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1" />
            </svg>
          }
        />
        <KpiCard
          label="Org"
          value={session?.organization_id?.slice(0, 8) ?? '—'}
          icon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          }
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Requests Over Time</h2>
          {tsQuery.isError ? (
            <ErrorState message="Could not load request data" onRetry={() => tsQuery.refetch()} />
          ) : (
            <TimeseriesChart data={tsData} loading={tsQuery.isLoading} bucket={bucket} />
          )}
        </div>

        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Cost by Provider</h2>
          {costsQuery.isError ? (
            <ErrorState message="Could not load cost data" onRetry={() => costsQuery.refetch()} />
          ) : (
            <CostChart data={costsQuery.data?.data ?? []} loading={costsQuery.isLoading} groupBy="provider" />
          )}
        </div>
      </div>
    </AdminLayout>
  )
}
