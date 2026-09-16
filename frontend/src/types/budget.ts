/** Budget types — derived from backend BudgetResponse schema (Phase 6) */

export type BudgetPeriod = 'daily' | 'weekly' | 'monthly'
export type BudgetPolicy = 'BLOCK' | 'WARN' | 'DOWNGRADE'

/** GET /api/v1/teams/{team_id}/budget */
export interface BudgetResponse {
  id: string
  team_id: string
  limit_amount: number
  current_usage: number
  period: BudgetPeriod
  period_start: string
  period_end: string
  policy: BudgetPolicy
  enabled: boolean
  remaining_amount: number
  usage_percentage: number
  created_at: string
  updated_at: string
}

/** POST /api/v1/teams/{team_id}/budget */
export interface BudgetCreate {
  limit_amount: number
  period: BudgetPeriod
  policy: BudgetPolicy
  enabled: boolean
}

/** PATCH /api/v1/teams/{team_id}/budget */
export interface BudgetUpdate {
  limit_amount?: number | null
  policy?: BudgetPolicy | null
  enabled?: boolean | null
}
