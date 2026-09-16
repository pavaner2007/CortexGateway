import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { CostGroupItem } from '../../types/analytics'
import Spinner from '../common/Spinner'
import EmptyState from '../common/EmptyState'

interface Props {
  data: CostGroupItem[]
  loading?: boolean
  groupBy?: string
}

const COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#f43f5e']

export default function CostChart({ data, loading, groupBy = 'provider' }: Props) {
  if (loading) {
    return (
      <div className="h-56 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No cost data" description="No costs recorded in this time range" />
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis
          dataKey="group_key"
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={50}
          tickFormatter={v => `$${Number(v).toFixed(4)}`}
        />
        <Tooltip
          formatter={(v) => [`$${Number(v).toFixed(6)}`, `Cost (${groupBy})`]}
          contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8 }}
          labelStyle={{ color: '#94a3b8', fontSize: 12 }}
          itemStyle={{ fontSize: 12 }}
        />
        <Bar dataKey="total_cost" name={`Cost by ${groupBy}`} radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
