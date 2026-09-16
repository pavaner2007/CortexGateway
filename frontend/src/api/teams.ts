/**
 * Teams API — wraps Phase 5 team and API key endpoints
 */
import { apiRequest } from './client'
import type {
  TeamListResponse,
  APIKeyListResponse,
  APIKeyCreatedResponse,
  APIKeyResponse,
  APIKeyCreate,
} from '../types/auth'

// ── Teams ─────────────────────────────────────────────────────────────────────

export async function listTeams(organizationId: string): Promise<TeamListResponse> {
  return apiRequest<TeamListResponse>(`/api/v1/organizations/${organizationId}/teams`)
}

// ── API Keys ──────────────────────────────────────────────────────────────────

export async function listApiKeys(teamId: string): Promise<APIKeyListResponse> {
  return apiRequest<APIKeyListResponse>(`/api/v1/teams/${teamId}/keys`)
}

/**
 * Create an API key for a team.
 * The response includes the plaintext secret — displayed ONCE, never stored.
 */
export async function createApiKey(
  teamId: string,
  body: APIKeyCreate,
): Promise<APIKeyCreatedResponse> {
  return apiRequest<APIKeyCreatedResponse>(`/api/v1/teams/${teamId}/keys`, {
    method: 'POST',
    body,
  })
}

/**
 * Revoke an API key.
 */
export async function revokeApiKey(
  teamId: string,
  keyId: string,
): Promise<APIKeyResponse> {
  return apiRequest<APIKeyResponse>(`/api/v1/teams/${teamId}/keys/${keyId}/revoke`, {
    method: 'POST',
  })
}
