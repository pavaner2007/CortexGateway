import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import type { TimeseriesBucket } from '../../types/analytics'
import Spinner from '../common/Spinner'
import EmptyState from '../common/EmptyState'

interface Props {
  data: TimeseriesBucket[]
  loading?: boolean
  bucket?: string
}

function formatTs(ts: string, bucket: string) {
  const d = new Date(ts)
  if (bucket === 'hour') {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export default function TimeseriesChart({ data, loading, bucket = 'day' }: Props) {
  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No request data" description="No traffic in this time range" />
  }

  const formatted = data.map(d => ({
    ...d,
    ts: formatTs(d.timestamp, bucket),
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={formatted} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gradRequests" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradErrors" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis
          dataKey="ts"
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={40}
        />
        <Tooltip
          contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8 }}
          labelStyle={{ color: '#94a3b8', fontSize: 12 }}
          itemStyle={{ fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: '#64748b', paddingTop: 8 }} />
        <Area
          type="monotone"
          dataKey="request_count"
          name="Requests"
          stroke="#6366f1"
          strokeWidth={2}
          fill="url(#gradRequests)"
          dot={false}
        />
        <Area
          type="monotone"
          dataKey="error_count"
          name="Errors"
          stroke="#f43f5e"
          strokeWidth={2}
          fill="url(#gradErrors)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
