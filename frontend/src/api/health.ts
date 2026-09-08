/**
 * Health API integration.
 * Fetches data from GET /health and GET / (root) on the backend.
 */

export type DependencyStatus = 'connected' | 'disconnected'
export type OverallStatus = 'healthy' | 'degraded'
export type FetchStatus = 'idle' | 'loading' | 'success' | 'error'

export interface HealthData {
  status: OverallStatus
  database: DependencyStatus
  redis: DependencyStatus
  version: string
}

export interface RootData {
  name: string
  version: string
  status: string
  description: string
  environment: string
}

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export async function fetchHealth(): Promise<HealthData> {
  const res = await fetch(`${API_BASE}/health`, {
    signal: AbortSignal.timeout(8000),
  })
  const data = await res.json()
  // /health may return 503; we still parse the body
  return data as HealthData
}

export async function fetchRoot(): Promise<RootData> {
  const res = await fetch(`${API_BASE}/`, {
    signal: AbortSignal.timeout(8000),
  })
  if (!res.ok) throw new Error(`Backend returned ${res.status}`)
  return res.json() as Promise<RootData>
}
