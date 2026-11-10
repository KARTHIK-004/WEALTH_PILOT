import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api-client"

/** `GET /api/profiles/{id}/security-status` -- the backend runs a real encryption round trip and a full audit-chain
 * verification on every call, so nothing is cached as "still true": `staleTime: 0`, `gcTime: 0`, no retry. The response
 * holds no note text, key or audit event. */
export function useSecurityStatusQuery(profileId: number | null) {
  return useQuery({
    queryKey: ["security-status", profileId],
    queryFn: () => api.getSecurityStatus(profileId as number),
    enabled: profileId !== null,
    gcTime: 0,
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  })
}
