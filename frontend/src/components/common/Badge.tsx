type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'purple'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  error:   'bg-rose-500/15 text-rose-400 border-rose-500/30',
  info:    'bg-sky-500/15 text-sky-400 border-sky-500/30',
  neutral: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  purple:  'bg-purple-500/15 text-purple-400 border-purple-500/30',
}

export default function Badge({ children, variant = 'neutral', className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  )
}

export function statusVariant(status: string): BadgeVariant {
  if (status === 'success') return 'success'
  if (status === 'rate_limited') return 'warning'
  if (status === 'budget_blocked') return 'warning'
  if (status === 'failure' || status === 'timeout') return 'error'
  return 'neutral'
}

export function policyVariant(policy: string): BadgeVariant {
  if (policy === 'BLOCK') return 'error'
  if (policy === 'WARN') return 'warning'
  if (policy === 'DOWNGRADE') return 'info'
  return 'neutral'
}
