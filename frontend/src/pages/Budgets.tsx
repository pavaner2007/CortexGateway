import { Link } from 'react-router-dom'
import AdminLayout from '../components/layout/AdminLayout'
import BudgetBar from '../components/cards/BudgetBar'
import Badge, { policyVariant } from '../components/common/Badge'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { SkeletonCard } from '../components/common/Skeleton'
import { useTeams } from '../hooks/useTeams'
import { useBudget } from '../hooks/useBudget'
import { useAuth } from '../auth/AuthContext'
import { ApiRequestError } from '../api/client'

function TeamBudgetRow({ teamId, teamName }: { teamId: string; teamName: string }) {
  const { data, isLoading, isError, error } = useBudget(teamId)
  const is404 = error instanceof ApiRequestError && error.status === 404

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <Link
            to={`/teams/${teamId}`}
            className="font-medium text-brand-400 hover:text-brand-300 transition-colors text-sm"
          >
            {teamName}
          </Link>
          <p className="font-mono text-xs text-slate-600 mt-0.5">{teamId.slice(0, 8)}…</p>
        </div>
        {data && (
          <Badge variant={policyVariant(data.policy)}>{data.policy}</Badge>
        )}
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-2 bg-white/5 rounded w-full" />
          <div className="h-3 bg-white/5 rounded w-1/2" />
        </div>
      ) : (isError && !is404) ? (
        <p className="text-xs text-rose-400">Error loading budget</p>
      ) : (!data || is404) ? (
        <p className="text-xs text-slate-600 italic">No budget configured</p>
      ) : (
        <BudgetBar
          used={data.current_usage}
          limit={data.limit_amount}
          percentage={data.usage_percentage}
          policy={data.policy}
          label={`${data.period} · $${data.current_usage.toFixed(4)} / $${data.limit_amount.toFixed(2)}`}
        />
      )}
    </div>
  )
}

export default function Budgets() {
  const { session } = useAuth()
  const orgId = session?.organization_id ?? ''
  const { data, isLoading, isError, refetch } = useTeams(orgId)
  const teams = data?.teams ?? []

  return (
    <AdminLayout title="Budgets" subtitle="Cross-team spending overview">
      {isLoading ? (
        <div className="space-y-4">{[1, 2, 3].map(i => <SkeletonCard key={i} />)}</div>
      ) : isError ? (
        <ErrorState message="Could not load teams" onRetry={refetch} />
      ) : teams.length === 0 ? (
        <EmptyState title="No teams found" description="Create teams to manage budgets" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {teams.map(t => (
            <TeamBudgetRow key={t.id} teamId={t.id} teamName={t.name} />
          ))}
        </div>
      )}
    </AdminLayout>
  )
}
