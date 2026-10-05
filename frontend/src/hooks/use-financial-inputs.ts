import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type FinancialInputsUpdate = components["schemas"]["FinancialInputsUpdate"]

/** `GET /api/profiles/{id}/financial-inputs` (Phase 28) — every field
 * `null` until the customer has submitted a `PUT`; never a fabricated
 * default. */
export function useFinancialInputsQuery(profileId: number | null) {
  return useQuery({
    queryKey: ["financial-inputs", profileId],
    queryFn: () => api.getFinancialInputs(profileId as number),
    enabled: profileId !== null,
  })
}

/** `PUT /api/profiles/{id}/financial-inputs` — an upsert/merge (omitted
 * fields keep their current stored value). Invalidates both this query
 * AND `["analysis", profileId]` on success, since financial inputs are a
 * real analysis-pipeline input as of Phase 28 (`analysis_service.py`'s
 * `_build_graph_dependencies`) — without this, a page showing the
 * analysis result could keep displaying a stale, pre-edit outcome. */
export function useUpdateFinancialInputs(profileId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: FinancialInputsUpdate) => api.updateFinancialInputs(profileId as number, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["financial-inputs", profileId] })
      queryClient.invalidateQueries({ queryKey: ["analysis", profileId] })
    },
  })
}
