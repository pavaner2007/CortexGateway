import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AdminLayout from '../components/layout/AdminLayout'
import DataTable from '../components/tables/DataTable'
import Pagination from '../components/tables/Pagination'
import Badge, { statusVariant } from '../components/common/Badge'
import ErrorState from '../components/common/ErrorState'
import Spinner from '../components/common/Spinner'
import { useRequests } from '../hooks/useAnalytics'
import type { RequestLogItem } from '../types/analytics'

function fmt(iso: string) {
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

// ── Detail Drawer ─────────────────────────────────────────────────────────────

function LogDetailDrawer({ log, onClose }: { log: RequestLogItem; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div
        className="w-full max-w-md h-full bg-surface-900 border-l border-white/10 overflow-y-auto animate-slide-up shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
          <h2 className="text-sm font-semibold text-slate-200">Request Detail</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-lg leading-none">✕</button>
        </div>
        <div className="p-5 space-y-4 text-xs">
          {[
            ['Request ID', log.request_id],
            ['Created At', fmt(log.created_at)],
            ['Status', log.status],
            ['Provider', log.provider ?? '—'],
            ['Model', log.model ?? '—'],
            ['Routing Mode', log.routing_mode ?? '—'],
            ['HTTP Status', log.http_status_code ?? '—'],
            ['Latency', log.latency_ms !== null ? `${log.latency_ms.toFixed(1)}ms` : '—'],
            ['Prompt Tokens', log.prompt_tokens ?? '—'],
            ['Completion Tokens', log.completion_tokens ?? '—'],
            ['Total Tokens', log.total_tokens ?? '—'],
            ['Est. Cost', log.estimated_cost !== null ? `$${log.estimated_cost.toFixed(8)}` : '—'],
            ['Actual Cost', log.actual_cost !== null ? `$${log.actual_cost.toFixed(8)}` : '—'],
            ['Retries', log.retry_count],
            ['Failover', log.failover_triggered ? `${log.failover_from_provider} → ${log.failover_to_provider}` : 'No'],
            ['CB State', log.circuit_breaker_state ?? '—'],
            ['Budget Policy', log.budget_policy_applied ?? '—'],
            ['Budget Action', log.budget_action ?? '—'],
            ['Error Code', log.error_code ?? '—'],
            ['Trace ID', log.trace_id ?? '—'],
            ['Team', log.team_id ?? '—'],
          ].map(([label, value]) => (
            <div key={String(label)} className="flex gap-3">
              <span className="text-slate-500 w-36 flex-shrink-0">{label}</span>
              <span className="text-slate-300 break-all font-mono">{String(value)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Logs() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedLog, setSelectedLog] = useState<RequestLogItem | null>(null)

  // Derive filter state from URL params for bookmarkability
  const page = parseInt(searchParams.get('page') ?? '1', 10)
  const statusFilter = searchParams.get('status') ?? ''
  const providerFilter = searchParams.get('provider') ?? ''

  const { data, isLoading, isError, refetch } = useRequests({
    page,
    page_size: 50,
    status: statusFilter || undefined,
    provider: providerFilter || undefined,
  })

  const logs = data?.data ?? []
  const pagination = data?.pagination ?? { page: 1, page_size: 50, total: 0 }

  function setPage(p: number) {
    setSearchParams(prev => { prev.set('page', String(p)); return prev })
  }

  const columns = [
    {
      key: 'created_at',
      label: 'Time',
      render: (r: RequestLogItem) => (
        <span className="text-slate-400 text-xs">{fmt(r.created_at)}</span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (r: RequestLogItem) => (
        <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
      ),
    },
    {
      key: 'provider',
      label: 'Provider',
      render: (r: RequestLogItem) => (
        <span className="capitalize text-slate-300">{r.provider ?? '—'}</span>
      ),
    },
    {
      key: 'model',
      label: 'Model',
      render: (r: RequestLogItem) => (
        <span className="text-slate-400 text-xs font-mono">{r.model ?? '—'}</span>
      ),
    },
    {
      key: 'latency_ms',
      label: 'Latency',
      render: (r: RequestLogItem) => (
        <span className="text-slate-300 tabular-nums text-xs">
          {r.latency_ms !== null ? `${r.latency_ms.toFixed(0)}ms` : '—'}
        </span>
      ),
    },
    {
      key: 'total_tokens',
      label: 'Tokens',
      render: (r: RequestLogItem) => (
        <span className="text-slate-400 text-xs tabular-nums">{r.total_tokens ?? '—'}</span>
      ),
    },
    {
      key: 'actual_cost',
      label: 'Cost',
      render: (r: RequestLogItem) => (
        <span className="text-slate-300 text-xs tabular-nums">
          {r.actual_cost !== null ? `$${r.actual_cost.toFixed(6)}` : '—'}
        </span>
      ),
    },
  ]

  return (
    <AdminLayout
      title="Request Logs"
      subtitle="Paginated request history"
      action={
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={e => setSearchParams(prev => { prev.set('status', e.target.value); prev.set('page', '1'); return prev })}
            className="px-2 py-1.5 text-xs bg-white/5 border border-white/10 text-slate-400 rounded-lg focus:outline-none"
          >
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="rate_limited">Rate Limited</option>
            <option value="budget_blocked">Budget Blocked</option>
            <option value="timeout">Timeout</option>
          </select>
          <select
            value={providerFilter}
            onChange={e => setSearchParams(prev => { prev.set('provider', e.target.value); prev.set('page', '1'); return prev })}
            className="px-2 py-1.5 text-xs bg-white/5 border border-white/10 text-slate-400 rounded-lg focus:outline-none"
          >
            <option value="">All providers</option>
            <option value="groq">Groq</option>
            <option value="gemini">Gemini</option>
            <option value="ollama">Ollama</option>
          </select>
          {isLoading && <Spinner size="sm" />}
        </div>
      }
    >
      <div className="glass-card overflow-hidden">
        {isError ? (
          <div className="p-5">
            <ErrorState message="Could not load logs" onRetry={refetch} />
          </div>
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={logs}
              keyFn={r => r.request_id}
              onRowClick={r => setSelectedLog(r)}
              emptyMessage={isLoading ? "Loading…" : "No requests found"}
            />
            <Pagination
              page={pagination.page}
              pageSize={pagination.page_size}
              total={pagination.total}
              onPageChange={setPage}
            />
          </>
        )}
      </div>

      {selectedLog && (
        <LogDetailDrawer log={selectedLog} onClose={() => setSelectedLog(null)} />
      )}
    </AdminLayout>
  )
}
