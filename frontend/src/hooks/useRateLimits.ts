import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRateLimits, setRateLimits, deleteRateLimits } from '../api/rateLimits'
import type { TeamRateLimitSet } from '../types/rateLimits'

export const rateLimitKeys = {
  team: (teamId: string) => ['ratelimits', teamId] as const,
}

export function useRateLimits(teamId: string) {
  return useQuery({
    queryKey: rateLimitKeys.team(teamId),
    queryFn: () => getRateLimits(teamId),
    staleTime: 30_000,
    enabled: !!teamId,
  })
}

export function useSetRateLimits(teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TeamRateLimitSet) => setRateLimits(teamId, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: rateLimitKeys.team(teamId) }) },
  })
}

export function useDeleteRateLimits(teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => deleteRateLimits(teamId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: rateLimitKeys.team(teamId) }) },
  })
}
