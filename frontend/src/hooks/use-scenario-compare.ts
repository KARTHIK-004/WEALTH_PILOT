import { useMutation } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type ScenarioCompareRequest = components["schemas"]["ScenarioCompareRequest"]

/** `POST /api/scenarios/compare` — a mutation, not a query, since it is
 * an explicit user-triggered comparison, not passively-fetched data
 * (section 37). No scenario logic is computed here; the request body is
 * passed straight through to the typed API client. */
export function useScenarioCompare() {
  return useMutation({
    mutationFn: (body: ScenarioCompareRequest) => api.compareScenarios(body),
  })
}
