import { useState, type FormEvent } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { validateApiKey } from '../api/auth'
import { ApiRequestError } from '../api/client'
import Spinner from '../components/common/Spinner'

export default function Login() {
  const { isAuthenticated, login } = useAuth()
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Already authenticated → go to dashboard
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!apiKey.trim()) return

    setError(null)
    setLoading(true)

    try {
      const me = await validateApiKey(apiKey.trim())

      if (me.role !== 'admin') {
        setError('This key does not have admin access. An admin key is required for the dashboard.')
        setLoading(false)
        return
      }

      login({
        apiKey: apiKey.trim(),
        organization_id: me.organization_id,
        team_id: me.team_id,
        api_key_id: me.api_key_id,
        role: me.role,
      })
      navigate('/dashboard', { replace: true })
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 401) {
          setError('Invalid API key. Please check and try again.')
        } else if (err.status === 403) {
          setError('This key does not have permission to access the admin dashboard.')
        } else {
          setError('Unable to connect to Cortex Gateway. Please check the server is running.')
        }
      } else {
        setError('Unable to connect. Please check the server.')
      }
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-950 px-4">
      {/* Gradient background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-brand-900/30 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-purple-900/20 blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500 to-purple-600 shadow-xl glow-brand mb-4">
            <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Cortex Gateway</h1>
          <p className="text-sm text-slate-500 mt-1">Admin Dashboard</p>
        </div>

        {/* Card */}
        <div className="glass-card p-6 shadow-2xl">
          <h2 className="text-base font-semibold text-slate-200 mb-5">Sign in</h2>

          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-4">
              <label htmlFor="api-key-input" className="block text-xs font-medium text-slate-400 mb-1.5">
                Admin API Key
              </label>
              <input
                id="api-key-input"
                type="password"
                autoComplete="current-password"
                placeholder="cxg_…"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                disabled={loading}
                className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-slate-200 placeholder-slate-600 text-sm focus:outline-none focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/30 transition-colors"
              />
            </div>

            {error && (
              <div role="alert" className="mb-4 px-3 py-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                {error}
              </div>
            )}

            <button
              id="signin-button"
              type="submit"
              disabled={loading || !apiKey.trim()}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {loading ? <Spinner size="sm" /> : null}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-700 mt-4">
          Internal admin dashboard — authorized personnel only
        </p>
      </div>
    </div>
  )
}
