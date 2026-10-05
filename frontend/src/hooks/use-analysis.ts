import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api-client"

/**
 * `POST /api/analysis` — the one shared query every Phase 17 page reads
 * risk/financial-health/goals/compliance/recommendation data from,
 * keyed only by `profileId` (section 43/45: one request per customer,
 * reused across pages via TanStack Query's cache, so the Dashboard and
 * the Risk Assessment page are always looking at the exact same
 * authoritative result — never two independent calls that could drift
 * apart). The endpoint itself returns a cached result when the
 * customer's profile hash is unchanged (Phase 15's own design), so
 * revisiting a page after the cache goes stale still resolves quickly.
 */
export function useAnalysisQuery(profileId: number | null) {
  return useQuery({
    queryKey: ["analysis", profileId],
    queryFn: () => api.runAnalysis({ profile_id: profileId as number }),
    enabled: profileId !== null,
  })
}
