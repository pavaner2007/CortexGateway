/**
 * Rate Limits API — wraps Phase 6 rate-limit management endpoints
 */
import { apiRequest } from './client'
import type { TeamRateLimitResponse, TeamRateLimitSet } from '../types/rateLimits'

export async function getRateLimits(teamId: string): Promise<TeamRateLimitResponse> {
  return apiRequest<TeamRateLimitResponse>(`/api/v1/teams/${teamId}/rate-limits`)
}

export async function setRateLimits(
  teamId: string,
  body: TeamRateLimitSet,
): Promise<TeamRateLimitResponse> {
  return apiRequest<TeamRateLimitResponse>(`/api/v1/teams/${teamId}/rate-limits`, {
    method: 'POST',
    body,
  })
}

export async function deleteRateLimits(teamId: string): Promise<void> {
  return apiRequest<void>(`/api/v1/teams/${teamId}/rate-limits`, { method: 'DELETE' })
}
