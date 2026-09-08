import { useCallback, useEffect, useState } from 'react'
import { type FetchStatus, type HealthData, type RootData, fetchHealth, fetchRoot } from '../api/health'
import StatusCard from '../components/StatusCard'

const POLL_INTERVAL_MS = 30_000

type DepsStatus = 'connected' | 'disconnected' | 'unknown'

function depVariant(status: DepsStatus) {
  if (status === 'connected') return 'healthy' as const
  if (status === 'disconnected') return 'degraded' as const
  return 'loading' as const
}

function overallVariant(status: string | undefined, fetchStatus: FetchStatus) {
  if (fetchStatus === 'loading') return 'loading' as const
  if (fetchStatus === 'error') return 'error' as const
  if (status === 'healthy') return 'healthy' as const
  if (status === 'degraded') return 'degraded' as const
  return 'loading' as const
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthData | null>(null)
  const [root, setRoot] = useState<RootData | null>(null)
  const [fetchStatus, setFetchStatus] = useState<FetchStatus>('idle')
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setFetchStatus('loading')
    setError(null)
    try {
      const [h, r] = await Promise.allSettled([fetchHealth(), fetchRoot()])
      if (h.status === 'fulfilled') setHealth(h.value)
      if (r.status === 'fulfilled') setRoot(r.value)
      setFetchStatus('success')
      setLastChecked(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to backend')
      setFetchStatus('error')
    }
  }, [])

  // Initial load + polling
  useEffect(() => {
    void load()
    const timer = setInterval(() => void load(), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [load])

  const db: DepsStatus = health?.database ?? 'unknown'
  const redis: DepsStatus = health?.redis ?? 'unknown'

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* ── Hero header ──────────────────────────────────────────────────── */}
      <div className="animate-slide-up">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-3xl font-extrabold">
              <span className="gradient-text">System Status</span>
            </h2>
            <p className="text-slate-400 mt-1 text-sm">
              Real-time health monitoring for all infrastructure dependencies.
            </p>
          </div>
          <button
            id="btn-refresh"
            onClick={() => void load()}
            disabled={fetchStatus === 'loading'}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-slate-400 hover:text-slate-100 hover:border-brand-500/40 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg
              className={['w-3.5 h-3.5', fetchStatus === 'loading' ? 'animate-spin' : ''].join(' ')}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {fetchStatus === 'loading' ? 'Checking…' : 'Refresh'}
          </button>
        </div>

        {/* Last checked */}
        {lastChecked && (
          <p className="text-xs text-slate-600 mt-2">
            Last checked: {lastChecked.toLocaleTimeString()} · auto-refreshes every 30s
          </p>
        )}
      </div>

      {/* ── Error banner ─────────────────────────────────────────────────── */}
      {fetchStatus === 'error' && (
        <div className="glass-card border border-rose-500/30 bg-rose-500/5 px-5 py-4 flex items-center gap-3 animate-fade-in" role="alert">
          <svg className="w-5 h-5 text-rose-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-rose-300">Backend unreachable</p>
            <p className="text-xs text-rose-400/70 mt-0.5">{error ?? 'Could not connect to the backend API.'}</p>
          </div>
        </div>
      )}

      {/* ── Status cards ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Overall status */}
        <StatusCard
          id="card-overall"
          title="Overall Status"
          value={
            fetchStatus === 'loading' && !health
              ? <span className="text-slate-500 text-base">Checking…</span>
              : fetchStatus === 'error'
                ? <span className="text-rose-400">Unreachable</span>
                : <span className="capitalize">{health?.status ?? '—'}</span>
          }
          description="Aggregate health of all monitored dependencies"
          variant={overallVariant(health?.status, fetchStatus)}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />

        {/* PostgreSQL */}
        <StatusCard
          id="card-database"
          title="PostgreSQL"
          value={
            <span className="capitalize">{db === 'unknown' ? '—' : db}</span>
          }
          description="Primary relational data store"
          variant={depVariant(db)}
          badge="asyncpg"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
            </svg>
          }
        />

        {/* Redis */}
        <StatusCard
          id="card-redis"
          title="Redis"
          value={
            <span className="capitalize">{redis === 'unknown' ? '—' : redis}</span>
          }
          description="In-memory cache and message broker"
          variant={depVariant(redis)}
          badge="async"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        />

        {/* Version */}
        <StatusCard
          id="card-version"
          title="Version"
          value={root?.version ?? health?.version ?? '—'}
          description={root?.environment ? `Environment: ${root.environment}` : 'Application version from settings'}
          variant="neutral"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
          }
        />
      </div>

      {/* ── Divider ──────────────────────────────────────────────────────── */}
      <div className="border-t border-white/5" />

      {/* ── About section ────────────────────────────────────────────────── */}
      <div className="glass-card border border-white/10 p-6 animate-slide-up">
        <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <svg className="w-4 h-4 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          About Cortex Gateway
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          {[
            {
              label: 'Application',
              value: root?.name ?? 'Cortex Gateway',
              desc: root?.description ?? 'Intelligent Multi-LLM Gateway',
            },
            {
              label: 'Backend',
              value: 'FastAPI + Python 3.12',
              desc: 'Async I/O with SQLAlchemy 2.x and asyncpg',
            },
            {
              label: 'Current Phase',
              value: 'Phase 1 — Foundation',
              desc: 'Infrastructure skeleton. Phase 2 will add multi-LLM gateway.',
            },
          ].map((item) => (
            <div key={item.label} className="p-4 rounded-xl bg-white/5 border border-white/5">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-600 mb-1">{item.label}</p>
              <p className="font-semibold text-slate-200">{item.value}</p>
              <p className="text-xs text-slate-500 mt-1">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── API Links ────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3 animate-fade-in">
        {[
          { label: 'Swagger UI', href: 'http://localhost:8000/docs', id: 'link-swagger' },
          { label: 'ReDoc', href: 'http://localhost:8000/redoc', id: 'link-redoc' },
          { label: 'Health API', href: 'http://localhost:8000/health', id: 'link-health' },
        ].map((link) => (
          <a
            key={link.id}
            id={link.id}
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-400 hover:text-slate-100 hover:border-brand-500/40 hover:bg-brand-600/10 transition-all duration-200 font-medium"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            {link.label}
          </a>
        ))}
      </div>
    </div>
  )
}
