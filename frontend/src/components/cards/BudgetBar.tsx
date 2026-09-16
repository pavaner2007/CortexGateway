interface BudgetBarProps {
  used: number
  limit: number
  percentage: number
  policy: string
  label?: string
}

export default function BudgetBar({ used, limit, percentage, policy, label }: BudgetBarProps) {
  const clampedPct = Math.min(100, Math.max(0, percentage))

  const barColor =
    clampedPct >= 90 ? 'bg-rose-500' :
    clampedPct >= 70 ? 'bg-amber-500' :
    'bg-emerald-500'

  const statusLabel =
    clampedPct >= 90 ? 'Critical' :
    clampedPct >= 70 ? 'Warning' :
    'Healthy'

  const statusColor =
    clampedPct >= 90 ? 'text-rose-400' :
    clampedPct >= 70 ? 'text-amber-400' :
    'text-emerald-400'

  return (
    <div className="space-y-1.5">
      {label && (
        <div className="flex justify-between items-center">
          <span className="text-xs text-slate-400">{label}</span>
          <span className={`text-xs font-medium ${statusColor}`}>
            {statusLabel} · {clampedPct.toFixed(1)}%
          </span>
        </div>
      )}
      <div className="h-2 bg-white/5 rounded-full overflow-hidden" role="progressbar" aria-valuenow={clampedPct} aria-valuemin={0} aria-valuemax={100}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${clampedPct}%` }}
        />
      </div>
      <div className="flex justify-between text-[11px] text-slate-600">
        <span>Used: ${used.toFixed(4)}</span>
        <span>Limit: ${limit.toFixed(2)}</span>
      </div>
      <div className="text-[11px] text-slate-600">Policy: {policy}</div>
    </div>
  )
}
