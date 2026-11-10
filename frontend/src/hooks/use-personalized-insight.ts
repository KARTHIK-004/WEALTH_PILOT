import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api-client"

/** `POST /api/profiles/{id}/personalized-insights` -- display-only behaviour facts plus an
 * optional, unvalidated reading of text the user chose to write. The text is sent in the request
 * body (never a URL) and is held only in memory: `gcTime: 0` drops the cached entry, whose key
 * contains the text, as soon as nothing is using it. Nothing is stored by the server. */
export function usePersonalizedInsightQuery(profileId: number | null, text: string | null) {
  return useQuery({
    queryKey: ["personalized-insight", profileId, text],
    queryFn: () => api.createPersonalizedInsight(profileId as number, text),
    enabled: profileId !== null,
    gcTime: 0,
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  })
}
