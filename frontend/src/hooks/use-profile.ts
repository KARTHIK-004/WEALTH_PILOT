import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api-client"

/** `GET /api/profiles/{id}` — demographic/goal-entry data only. */
export function useProfileQuery(profileId: number | null) {
  return useQuery({
    queryKey: ["profile", profileId],
    queryFn: () => api.getProfile(profileId as number),
    enabled: profileId !== null,
  })
}
