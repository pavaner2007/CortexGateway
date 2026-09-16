import AdminLayout from '../components/layout/AdminLayout'
import Badge from '../components/common/Badge'
import LatencyChart from '../components/charts/LatencyChart'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { SkeletonCard } from '../components/common/Skeleton'
import { useProviders, useLatency, useErrors } from '../hooks/useAnalytics'
import { dateRangeToParams } from '../types/analytics'

export default function Providers() {
  const params = dateRangeToParams('24h')
  const providersQuery = useProviders(60_000)
  const latencyQuery = useLatency(params)
  const errorsQuery = useErrors(params)

  const providers = providersQuery.data?.providers ?? []
  const latencyMap = Object.fromEntries(
    (latencyQuery.data?.data ?? []).map(d => [d.provider, d])
  )
  const errorMap: Record<string, number> = {}
  for (const e of errorsQuery.data?.data ?? []) {
    if (e.provider) {
      errorMap[e.provider] = (errorMap[e.provider] ?? 0) + e.count
    }
  }

  return (
    <AdminLayout title="Providers" subtitle="Configured LLM providers — metrics based on last 24 h traffic">
      {providersQuery.isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {[1,2,3].map(i => <SkeletonCard key={i} />)}
        </div>
      ) : providersQuery.isError ? (
        <ErrorState message="Could not load providers" onRetry={() => providersQuery.refetch()} />
      ) : providers.length === 0 ? (
        <EmptyState title="No providers configured" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {providers.map(p => {
            const lat = latencyMap[p.name]
            const errCount = errorMap[p.name] ?? 0
            const reqCount = lat?.request_count ?? 0
            const successRate = reqCount > 0
              ? (((reqCount - errCount) / reqCount) * 100).toFixed(1)
              : null

            return (
              <div key={p.name} className="glass-card p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-200 capitalize">{p.name}</h2>
                    <p className="text-xs text-slate-600 mt-0.5">LLM Provider</p>
                  </div>
                  <Badge variant={p.available ? 'success' : 'error'}>
                    {p.available ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>

                {/* Historical metrics — clearly labeled */}
                <div className="border-t border-white/5 pt-3 space-y-2">
                  <p className="text-[10px] text-slate-600 uppercase tracking-widest font-semibold">
                    Last 24 h (historical)
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-xs text-slate-500">Requests</p>
                      <p className="text-sm font-semibold text-slate-200">{reqCount.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Errors</p>
                      <p className="text-sm font-semibold text-rose-400">{errCount.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Avg Latency</p>
                      <p className="text-sm font-semibold text-slate-200">
                        {lat?.avg_latency_ms ? `${lat.avg_latency_ms.toFixed(0)}ms` : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Success Rate</p>
                      <p className="text-sm font-semibold text-slate-200">
                        {successRate !== null ? `${successRate}%` : '—'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Latency comparison chart */}
      <div className="glass-card p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-1">Latency Comparison (last 24 h)</h2>
        <p className="text-xs text-slate-600 mb-4">
          Historical latency percentiles per provider — not a live circuit breaker state
        </p>
        {latencyQuery.isError ? (
          <ErrorState message="Could not load latency data" onRetry={() => latencyQuery.refetch()} />
        ) : (
          <LatencyChart data={latencyQuery.data?.data ?? []} loading={latencyQuery.isLoading} />
        )}
      </div>
    </AdminLayout>
  )
}
