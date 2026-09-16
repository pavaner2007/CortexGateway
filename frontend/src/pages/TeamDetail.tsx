import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import AdminLayout from '../components/layout/AdminLayout'
import Badge, { policyVariant } from '../components/common/Badge'
import BudgetBar from '../components/cards/BudgetBar'
import ConfirmDialog from '../components/common/ConfirmDialog'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import Spinner from '../components/common/Spinner'
import { SkeletonCard, SkeletonTable } from '../components/common/Skeleton'
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '../hooks/useTeams'
import { useBudget, useUpdateBudget } from '../hooks/useBudget'
import { useRateLimits, useSetRateLimits } from '../hooks/useRateLimits'
import type { BudgetPolicy } from '../types/budget'
import { ApiRequestError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
}

function safeMsg(err: unknown): string {
  if (err instanceof ApiRequestError) return err.message
  return 'An error occurred'
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function TeamDetail() {
  const { teamId } = useParams<{ teamId: string }>()
  const { session } = useAuth()
  const isOwnTeam = session?.team_id === teamId

  if (!teamId) return null

  return (
    <AdminLayout
      title="Team Details"
      subtitle={`Team ${teamId.slice(0, 8)}…`}
      action={
        <Link to="/teams" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
          ← All Teams
        </Link>
      }
    >
      <div className="space-y-6">
        <ApiKeysSection teamId={teamId} isOwnTeam={isOwnTeam} />
        <BudgetSection teamId={teamId} />
        <RateLimitSection teamId={teamId} />
      </div>
    </AdminLayout>
  )
}

// ── API Keys Section ──────────────────────────────────────────────────────────

function ApiKeysSection({ teamId, isOwnTeam }: { teamId: string; isOwnTeam: boolean }) {
  const { data, isLoading, isError, refetch } = useApiKeys(teamId)
  const createMut = useCreateApiKey(teamId)
  const revokeMut = useRevokeApiKey(teamId)

  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyRole, setNewKeyRole] = useState<'admin' | 'member'>('member')
  const [showCreate, setShowCreate] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)

  async function handleCreate() {
    if (!newKeyName.trim()) return
    setCreateError(null)
    try {
      const res = await createMut.mutateAsync({ name: newKeyName.trim(), role: newKeyRole })
      setCreatedKey(res.key) // shown ONCE
      setNewKeyName('')
      setShowCreate(false)
    } catch (e) {
      setCreateError(safeMsg(e))
    }
  }

  async function handleRevoke() {
    if (!revokeTarget) return
    try {
      await revokeMut.mutateAsync(revokeTarget)
    } catch {
      // handled by mutation state
    }
    setRevokeTarget(null)
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">API Keys</h2>
          {!isOwnTeam && (
            <p className="text-xs text-amber-400 mt-0.5">
              ⚠ Key management only available for your own team
            </p>
          )}
        </div>
        {isOwnTeam && (
          <button
            id="create-key-button"
            onClick={() => setShowCreate(v => !v)}
            className="px-3 py-1.5 text-xs font-medium bg-brand-500/20 text-brand-400 border border-brand-500/30 rounded-lg hover:bg-brand-500/30 transition-colors"
          >
            {showCreate ? 'Cancel' : '+ New Key'}
          </button>
        )}
      </div>

      {/* Create key form */}
      {showCreate && (
        <div className="px-5 py-4 border-b border-white/5 bg-white/3 space-y-3">
          <div className="flex gap-3">
            <div className="flex-1">
              <label htmlFor="new-key-name" className="block text-xs text-slate-400 mb-1">Key Name</label>
              <input
                id="new-key-name"
                type="text"
                value={newKeyName}
                onChange={e => setNewKeyName(e.target.value)}
                placeholder="e.g. Production App"
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-200 placeholder-slate-600 text-sm focus:outline-none focus:border-brand-500/50 transition-colors"
              />
            </div>
            <div>
              <label htmlFor="new-key-role" className="block text-xs text-slate-400 mb-1">Role</label>
              <select
                id="new-key-role"
                value={newKeyRole}
                onChange={e => setNewKeyRole(e.target.value as 'admin' | 'member')}
                className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm focus:outline-none focus:border-brand-500/50"
              >
                <option value="member">member</option>
                <option value="admin">admin</option>
              </select>
            </div>
          </div>
          {createError && <p className="text-xs text-rose-400">{createError}</p>}
          <button
            onClick={handleCreate}
            disabled={createMut.isPending || !newKeyName.trim()}
            className="flex items-center gap-2 px-4 py-2 text-xs font-medium bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white rounded-lg transition-colors"
          >
            {createMut.isPending && <Spinner size="sm" />}
            Create Key
          </button>
        </div>
      )}

      {/* One-time key display */}
      {createdKey && (
        <div className="px-5 py-4 border-b border-white/5 bg-emerald-500/5 border-l-2 border-l-emerald-500">
          <p className="text-xs font-semibold text-emerald-400 mb-1">
            ⚠ Copy this key now — it will not be shown again
          </p>
          <code className="block text-xs font-mono text-slate-300 break-all bg-white/5 p-2 rounded mt-1">
            {createdKey}
          </code>
          <button
            onClick={() => setCreatedKey(null)}
            className="mt-2 text-xs text-slate-500 hover:text-slate-300"
          >
            I've copied it — dismiss
          </button>
        </div>
      )}

      {/* Key list */}
      {isLoading ? (
        <div className="p-5"><SkeletonTable rows={3} /></div>
      ) : isError ? (
        <div className="p-5"><ErrorState message="Could not load API keys" onRetry={refetch} /></div>
      ) : (data?.keys ?? []).length === 0 ? (
        <div className="p-5"><EmptyState title="No API keys" description="Create the first key for this team" /></div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5">
              {['Name', 'Prefix', 'Role', 'Status', 'Last Used', 'Expires', 'Action'].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {(data?.keys ?? []).map(k => (
              <tr key={k.id} className="hover:bg-white/3 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-200">{k.name}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-400">{k.key_prefix}</td>
                <td className="px-4 py-3"><Badge variant={k.role === 'admin' ? 'purple' : 'neutral'}>{k.role}</Badge></td>
                <td className="px-4 py-3">
                  {k.revoked_at
                    ? <Badge variant="error">Revoked</Badge>
                    : <Badge variant="success">Active</Badge>
                  }
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">{fmt(k.last_used_at)}</td>
                <td className="px-4 py-3 text-slate-400 text-xs">{fmt(k.expires_at) === '—' ? 'Never' : fmt(k.expires_at)}</td>
                <td className="px-4 py-3">
                  {!k.revoked_at && isOwnTeam && (
                    <button
                      onClick={() => setRevokeTarget(k.id)}
                      className="text-xs text-rose-400 hover:text-rose-300 transition-colors"
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ConfirmDialog
        open={!!revokeTarget}
        title="Revoke API Key"
        message="This key will immediately become invalid. This action cannot be undone."
        confirmLabel="Revoke Key"
        destructive
        onConfirm={handleRevoke}
        onCancel={() => setRevokeTarget(null)}
      />
    </div>
  )
}

// ── Budget Section ────────────────────────────────────────────────────────────

function BudgetSection({ teamId }: { teamId: string }) {
  const { data, isLoading, isError, error, refetch } = useBudget(teamId)
  const updateMut = useUpdateBudget(teamId)

  const [editing, setEditing] = useState(false)
  const [limitInput, setLimitInput] = useState('')
  const [policyInput, setPolicyInput] = useState<BudgetPolicy>('BLOCK')
  const [enabledInput, setEnabledInput] = useState(true)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [confirmSave, setConfirmSave] = useState(false)

  function startEdit() {
    if (!data) return
    setLimitInput(String(data.limit_amount))
    setPolicyInput(data.policy as BudgetPolicy)
    setEnabledInput(data.enabled)
    setEditing(true)
    setUpdateError(null)
  }

  async function handleSave() {
    setConfirmSave(false)
    const limit = parseFloat(limitInput)
    if (isNaN(limit) || limit <= 0) {
      setUpdateError('Limit must be a positive number')
      return
    }
    setUpdateError(null)
    try {
      await updateMut.mutateAsync({ limit_amount: limit, policy: policyInput, enabled: enabledInput })
      setEditing(false)
    } catch (e) {
      setUpdateError(safeMsg(e))
    }
  }

  const is404 = error instanceof ApiRequestError && error.status === 404

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-slate-200">Budget</h2>
        {data && !editing && (
          <button onClick={startEdit} className="text-xs text-brand-400 hover:text-brand-300">Edit</button>
        )}
        {editing && (
          <div className="flex gap-2">
            <button onClick={() => setEditing(false)} className="text-xs text-slate-500">Cancel</button>
            <button
              onClick={() => setConfirmSave(true)}
              disabled={updateMut.isPending}
              className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
            >
              {updateMut.isPending && <Spinner size="sm" />}
              Save
            </button>
          </div>
        )}
      </div>

      {isLoading ? (
        <SkeletonCard />
      ) : isError && !is404 ? (
        <ErrorState message="Could not load budget" onRetry={refetch} />
      ) : is404 || !data ? (
        <EmptyState title="No budget configured" description="Create a budget via the API or CLI" />
      ) : editing ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="budget-limit" className="block text-xs text-slate-400 mb-1">Limit (USD)</label>
              <input
                id="budget-limit"
                type="number"
                min="0.01"
                step="0.01"
                value={limitInput}
                onChange={e => setLimitInput(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm focus:outline-none focus:border-brand-500/50"
              />
            </div>
            <div>
              <label htmlFor="budget-policy" className="block text-xs text-slate-400 mb-1">Policy</label>
              <select
                id="budget-policy"
                value={policyInput}
                onChange={e => setPolicyInput(e.target.value as BudgetPolicy)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm focus:outline-none focus:border-brand-500/50"
              >
                <option value="BLOCK">BLOCK</option>
                <option value="WARN">WARN</option>
                <option value="DOWNGRADE">DOWNGRADE</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Enabled</label>
              <label className="flex items-center gap-2 cursor-pointer mt-2">
                <input
                  type="checkbox"
                  checked={enabledInput}
                  onChange={e => setEnabledInput(e.target.checked)}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm text-slate-300">{enabledInput ? 'Yes' : 'No'}</span>
              </label>
            </div>
          </div>
          {updateError && <p className="text-xs text-rose-400">{updateError}</p>}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-slate-500">Limit</p>
              <p className="text-base font-semibold text-slate-200">${data.limit_amount.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Used</p>
              <p className="text-base font-semibold text-slate-200">${data.current_usage.toFixed(4)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Remaining</p>
              <p className="text-base font-semibold text-emerald-400">${data.remaining_amount.toFixed(4)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Policy</p>
              <Badge variant={policyVariant(data.policy)}>{data.policy}</Badge>
            </div>
          </div>
          <BudgetBar
            used={data.current_usage}
            limit={data.limit_amount}
            percentage={data.usage_percentage}
            policy={data.policy}
            label={`${data.period} budget`}
          />
        </div>
      )}

      <ConfirmDialog
        open={confirmSave}
        title="Save Budget Changes"
        message="Updating the budget limit or policy may immediately affect production traffic."
        confirmLabel="Save Changes"
        onConfirm={handleSave}
        onCancel={() => setConfirmSave(false)}
      />
    </div>
  )
}

// ── Rate Limits Section ───────────────────────────────────────────────────────

function RateLimitSection({ teamId }: { teamId: string }) {
  const { data, isLoading, isError, refetch } = useRateLimits(teamId)
  const setMut = useSetRateLimits(teamId)

  const [editing, setEditing] = useState(false)
  const [rpmInput, setRpmInput] = useState('')
  const [rphInput, setRphInput] = useState('')
  const [mutError, setMutError] = useState<string | null>(null)

  function startEdit() {
    if (!data) return
    setRpmInput(String(data.override_requests_per_minute ?? ''))
    setRphInput(String(data.override_requests_per_hour ?? ''))
    setEditing(true)
    setMutError(null)
  }

  async function handleSave() {
    const rpm = rpmInput ? parseInt(rpmInput) : null
    const rph = rphInput ? parseInt(rphInput) : null
    if (rpm !== null && (isNaN(rpm) || rpm <= 0)) {
      setMutError('RPM must be a positive integer')
      return
    }
    if (rph !== null && (isNaN(rph) || rph <= 0)) {
      setMutError('RPH must be a positive integer')
      return
    }
    setMutError(null)
    try {
      await setMut.mutateAsync({ requests_per_minute: rpm, requests_per_hour: rph })
      setEditing(false)
    } catch (e) {
      setMutError(safeMsg(e))
    }
  }

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-slate-200">Rate Limits</h2>
        {data && !editing && (
          <div className="flex gap-2">
            <button onClick={startEdit} className="text-xs text-brand-400 hover:text-brand-300">Edit</button>
          </div>
        )}
        {editing && (
          <div className="flex gap-2">
            <button onClick={() => setEditing(false)} className="text-xs text-slate-500">Cancel</button>
            <button
              onClick={handleSave}
              disabled={setMut.isPending}
              className="flex items-center gap-1 text-xs text-emerald-400"
            >
              {setMut.isPending && <Spinner size="sm" />}
              Save
            </button>
          </div>
        )}
      </div>

      {isLoading ? (
        <SkeletonCard />
      ) : isError ? (
        <ErrorState message="Could not load rate limits" onRetry={refetch} />
      ) : !data ? null : editing ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="rl-rpm" className="block text-xs text-slate-400 mb-1">
                Requests / minute (leave blank to use global default)
              </label>
              <input
                id="rl-rpm"
                type="number"
                min="1"
                value={rpmInput}
                onChange={e => setRpmInput(e.target.value)}
                placeholder={String(data.global_requests_per_minute)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm focus:outline-none focus:border-brand-500/50"
              />
            </div>
            <div>
              <label htmlFor="rl-rph" className="block text-xs text-slate-400 mb-1">
                Requests / hour (leave blank to disable)
              </label>
              <input
                id="rl-rph"
                type="number"
                min="1"
                value={rphInput}
                onChange={e => setRphInput(e.target.value)}
                placeholder="none"
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm focus:outline-none focus:border-brand-500/50"
              />
            </div>
          </div>
          {mutError && <p className="text-xs text-rose-400">{mutError}</p>}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-slate-500 mb-1">Effective RPM</p>
            <p className="text-lg font-semibold text-slate-200">{data.effective_requests_per_minute}</p>
            {data.override_requests_per_minute !== null && (
              <Badge variant="purple" className="mt-1">Override</Badge>
            )}
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Effective RPH</p>
            <p className="text-lg font-semibold text-slate-200">
              {data.effective_requests_per_hour ?? '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Global RPM Default</p>
            <p className="text-sm text-slate-400">{data.global_requests_per_minute}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Override Active</p>
            <Badge variant={data.override_requests_per_minute !== null ? 'info' : 'neutral'}>
              {data.override_requests_per_minute !== null ? 'Yes' : 'No (global default)'}
            </Badge>
          </div>
        </div>
      )}
    </div>
  )
}
