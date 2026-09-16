/**
 * Cortex Gateway — Centralized API Client
 *
 * Handles:
 *   - Base URL from VITE_API_URL
 *   - Authorization: Bearer token from sessionStorage
 *   - JSON serialization
 *   - Error parsing
 *   - 401 → clear session + redirect to /login
 *   - 403 → throw authorization error (do NOT log out)
 *
 * SECURITY: The API key is never logged, printed, or put in URLs.
 */

import { SESSION_KEY, type Session } from '../types/auth'

export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

function getToken(): string | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const session: Session = JSON.parse(raw)
    return session.apiKey ?? null
  } catch {
    return null
  }
}

function handle401(): never {
  // Clear session and redirect without exposing key
  sessionStorage.removeItem(SESSION_KEY)
  window.location.href = '/login'
  throw new ApiRequestError(401, 'AUTHENTICATION_FAILED', 'Session expired. Please log in again.')
}

async function parseError(res: Response): Promise<ApiRequestError> {
  let code = 'REQUEST_FAILED'
  let message = `Request failed with status ${res.status}`
  try {
    const body = await res.json()
    if (body?.error?.code) code = body.error.code
    if (body?.error?.message) message = body.error.message
    else if (body?.detail) message = body.detail
  } catch {
    // Body is not JSON — use default message
  }
  return new ApiRequestError(res.status, code, message)
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  /** If true, uses this token instead of reading from sessionStorage */
  token?: string
  /** If true, do NOT attach Authorization header */
  unauthenticated?: boolean
}

export async function apiRequest<T>(
  path: string,
  { method = 'GET', body, token, unauthenticated = false }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (!unauthenticated) {
    const authToken = token ?? getToken()
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(15_000),
  })

  if (res.status === 401) {
    if (!unauthenticated) {
      handle401()
    }
    throw await parseError(res)
  }

  if (!res.ok) {
    throw await parseError(res)
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as unknown as T
  }

  return res.json() as Promise<T>
}
