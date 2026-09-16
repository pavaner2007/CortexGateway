import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listTeams, listApiKeys, createApiKey, revokeApiKey } from '../api/teams'
import type { APIKeyCreate } from '../types/auth'

// Query keys
export const teamKeys = {
  all: (orgId: string) => ['teams', orgId] as const,
  keys: (teamId: string) => ['apikeys', teamId] as const,
}

export function useTeams(organizationId: string) {
  return useQuery({
    queryKey: teamKeys.all(organizationId),
    queryFn: () => listTeams(organizationId),
    staleTime: 30_000,
    enabled: !!organizationId,
  })
}

export function useApiKeys(teamId: string) {
  return useQuery({
    queryKey: teamKeys.keys(teamId),
    queryFn: () => listApiKeys(teamId),
    staleTime: 30_000,
    enabled: !!teamId,
  })
}

export function useCreateApiKey(teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: APIKeyCreate) => createApiKey(teamId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: teamKeys.keys(teamId) })
    },
  })
}

export function useRevokeApiKey(teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => revokeApiKey(teamId, keyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: teamKeys.keys(teamId) })
    },
  })
}
