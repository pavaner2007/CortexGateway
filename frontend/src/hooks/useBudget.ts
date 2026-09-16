import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getBudget, createBudget, updateBudget, deleteBudget } from '../api/budgets'
import type { BudgetCreate, BudgetUpdate } from '../types/budget'

export const budgetKeys = {
  team: (teamId: string) => ['budget', teamId] as const,
}

export function useBudget(teamId: string) {
  return useQuery({
    queryKey: budgetKeys.team(teamId),
    queryFn: () => getBudget(teamId),
    staleTime: 30_000,
    enabled: !!teamId,
    retry: (count, err: unknown) => {
      // Don't retry on 404 (no budget configured)
      const e = err as { status?: number }
      if (e?.status === 404) return false
      return count < 2
    },
  })
}

export function useCreateBudget(teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: BudgetCreate) => createBudget(teamId, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: budgetKeys.team(teamId) }) },
  })
}

export function useUpdateBudget(teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: BudgetUpdate) => updateBudget(teamId, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: budgetKeys.team(teamId) }) },
  })
}

export function useDeleteBudget(teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => deleteBudget(teamId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: budgetKeys.team(teamId) }) },
  })
}
