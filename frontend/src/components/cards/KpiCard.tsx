import type { ReactNode } from 'react'

interface KpiCardProps {
  label: string
  value: string | number
  subtext?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  loading?: boolean
}

export default function KpiCard({
  label,
  value,
  subtext,
  icon,
  trend,
  loading = false,
}: KpiCardProps) {
  if (loading) {
    return (
      <div className="glass-card p-5 space-y-3 animate-pulse">
        <div className="h-3 w-1/3 bg-white/5 rounded" />
        <div className="h-8 w-1/2 bg-white/5 rounded" />
        <div className="h-3 w-2/3 bg-white/5 rounded" />
      </div>
    )
  }

  const trendColor =
    trend === 'up' ? 'text-emerald-400' :
    trend === 'down' ? 'text-rose-400' :
    'text-slate-500'

  return (
    <div className="glass-card p-5 hover:bg-white/[0.07] transition-colors duration-200">
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider truncate">
            {label}
          </p>
          <p className="mt-1.5 text-2xl font-bold text-slate-100 tabular-nums">
            {value}
          </p>
          {subtext && (
            <p className={`mt-1 text-xs ${trendColor}`}>{subtext}</p>
          )}
        </div>
        {icon && (
          <div className="ml-3 flex-shrink-0 w-9 h-9 rounded-xl bg-brand-500/10 flex items-center justify-center text-brand-400">
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}
