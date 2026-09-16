import { Link } from 'react-router-dom'
import AdminLayout from '../components/layout/AdminLayout'
import { SkeletonTable } from '../components/common/Skeleton'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import Badge from '../components/common/Badge'
import { useTeams } from '../hooks/useTeams'
import { useAuth } from '../auth/AuthContext'

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function Teams() {
  const { session } = useAuth()
  const orgId = session?.organization_id ?? ''
  const { data, isLoading, isError, refetch } = useTeams(orgId)

  const teams = data?.teams ?? []

  return (
    <AdminLayout title="Teams" subtitle={`Organization ${orgId.slice(0,8)}…`}>
      {isLoading ? (
        <div className="glass-card p-5"><SkeletonTable rows={4} /></div>
      ) : isError ? (
        <ErrorState message="Could not load teams" onRetry={refetch} />
      ) : teams.length === 0 ? (
        <EmptyState title="No teams found" description="Create your first team via the API" />
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5">
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Team</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Slug</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Created</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {teams.map(t => (
                <tr key={t.id} className="hover:bg-white/3 transition-colors">
                  <td className="px-5 py-3">
                    <Link
                      to={`/teams/${t.id}`}
                      className="font-medium text-brand-400 hover:text-brand-300 transition-colors"
                    >
                      {t.name}
                    </Link>
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant="neutral">{t.slug}</Badge>
                  </td>
                  <td className="px-5 py-3 text-slate-400">{fmt(t.created_at)}</td>
                  <td className="px-5 py-3 font-mono text-xs text-slate-600">{t.id.slice(0, 8)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AdminLayout>
  )
}
