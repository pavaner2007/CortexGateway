/**
 * Budget API — wraps Phase 6 budget endpoints
 */
import { apiRequest } from './client'
import type { BudgetResponse, BudgetCreate, BudgetUpdate } from '../types/budget'

export async function getBudget(teamId: string): Promise<BudgetResponse> {
  return apiRequest<BudgetResponse>(`/api/v1/teams/${teamId}/budget`)
}

export async function createBudget(
  teamId: string,
  body: BudgetCreate,
): Promise<BudgetResponse> {
  return apiRequest<BudgetResponse>(`/api/v1/teams/${teamId}/budget`, {
    method: 'POST',
    body,
  })
}

export async function updateBudget(
  teamId: string,
  body: BudgetUpdate,
): Promise<BudgetResponse> {
  return apiRequest<BudgetResponse>(`/api/v1/teams/${teamId}/budget`, {
    method: 'PATCH',
    body,
  })
}

export async function deleteBudget(teamId: string): Promise<void> {
  return apiRequest<void>(`/api/v1/teams/${teamId}/budget`, { method: 'DELETE' })
}
