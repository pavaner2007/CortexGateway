import { type ReactNode } from 'react'

type Variant = 'healthy' | 'degraded' | 'loading' | 'error' | 'neutral'

interface StatusCardProps {
  id?: string
  title: string
  value: ReactNode
  description?: string
  variant?: Variant
  icon: ReactNode
  badge?: string
}

const variantStyles: Record<Variant, string> = {
  healthy:  'border-emerald-500/30 bg-emerald-500/5',
  degraded: 'border-amber-500/30  bg-amber-500/5',
  error:    'border-rose-500/30   bg-rose-500/5',
  loading:  'border-white/10      bg-white/5',
  neutral:  'border-white/10      bg-white/5',
}

const dotVariant: Record<Variant, string> = {
  healthy:  'status-dot--healthy',
  degraded: 'status-dot--degraded',
  error:    'status-dot--error',
  loading:  'status-dot--loading',
  neutral:  'bg-slate-500',
}

export default function StatusCard({
  id,
  title,
  value,
  description,
  variant = 'neutral',
  icon,
  badge,
}: StatusCardProps) {
  return (
    <div
      id={id}
      className={[
        'glass-card border p-5 flex flex-col gap-4 transition-all duration-300',
        'hover:border-brand-500/30 hover:bg-white/[0.07] group animate-slide-up',
        variantStyles[variant],
      ].join(' ')}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-brand-400 group-hover:bg-brand-600/15 transition-colors duration-200">
            {icon}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p>
            {badge && (
              <span className="inline-block mt-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-brand-600/20 text-brand-400 border border-brand-500/20">
                {badge}
              </span>
            )}
          </div>
        </div>
        <span className={['status-dot', dotVariant[variant]].join(' ')} />
      </div>

      <div>
        <div className="text-2xl font-bold text-slate-100 leading-tight">
          {value}
        </div>
        {description && (
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{description}</p>
        )}
      </div>
    </div>
  )
}
