import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import type { LatencyGroupItem } from '../../types/analytics'
import Spinner from '../common/Spinner'
import EmptyState from '../common/EmptyState'

interface Props {
  data: LatencyGroupItem[]
  loading?: boolean
}

export default function LatencyChart({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="h-56 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No latency data" description="No requests with latency metrics in this range" />
  }

  const formatted = data.map(d => ({
    provider: d.provider ?? 'unknown',
    'Avg': d.avg_latency_ms ?? 0,
    'p50': d.p50_latency_ms ?? 0,
    'p95': d.p95_latency_ms ?? 0,
    'p99': d.p99_latency_ms ?? 0,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={formatted} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis
          dataKey="provider"
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={50}
          tickFormatter={v => `${v}ms`}
        />
        <Tooltip
          formatter={(v) => [`${Number(v).toFixed(1)}ms`]}
          contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8 }}
          labelStyle={{ color: '#94a3b8', fontSize: 12 }}
          itemStyle={{ fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: '#64748b', paddingTop: 8 }} />
        <Bar dataKey="Avg" fill="#6366f1" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
        <Bar dataKey="p50" fill="#8b5cf6" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
        <Bar dataKey="p95" fill="#f59e0b" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
        <Bar dataKey="p99" fill="#f43f5e" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
