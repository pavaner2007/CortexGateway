/**
 * Auth API — login validation via GET /api/v1/auth/me
 */
import { apiRequest } from './client'
import type { MeResponse } from '../types/auth'

/**
 * Validate an API key by calling /api/v1/auth/me.
 * Throws ApiRequestError on 401/403.
 * SECURITY: token is never logged or stored in URLs.
 */
export async function validateApiKey(token: string): Promise<MeResponse> {
  return apiRequest<MeResponse>('/api/v1/auth/me', { token })
}
