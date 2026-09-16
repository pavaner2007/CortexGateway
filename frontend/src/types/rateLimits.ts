/** Rate limit types — derived from backend TeamRateLimitResponse schema (Phase 6) */

/** GET /api/v1/teams/{team_id}/rate-limits */
export interface TeamRateLimitResponse {
  team_id: string
  effective_requests_per_minute: number
  effective_requests_per_hour: number | null
  override_requests_per_minute: number | null
  override_requests_per_hour: number | null
  global_requests_per_minute: number
  global_requests_per_hour: number | null
}

/** POST /api/v1/teams/{team_id}/rate-limits */
export interface TeamRateLimitSet {
  requests_per_minute?: number | null
  requests_per_hour?: number | null
}
