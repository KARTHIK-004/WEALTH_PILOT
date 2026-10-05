import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

export type HouseholdFinancialSummary = components["schemas"]["HouseholdFinancialSummaryResponse"]

/**
 * `GET /api/households/{id}/financial-summary` (Phase 34) — the household's
 * aggregated income, expenses, assets, liabilities, monthly cash flow, net
 * position and emergency-fund position.
 *
 * Read-only and display-only: every number in the response was computed by the
 * backend, and nothing in the frontend adds, subtracts, totals or scores any
 * of it. The query is invalidated by the Phase 33 record mutations
 * (`use-household-finances.ts`), so an edited record produces a freshly
 * *recomputed* summary from the server rather than a locally adjusted one.
 */
export function useHouseholdSummaryQuery(householdId: number | null, actingCustomerId: number | null) {
  return useQuery({
    queryKey: ["household-summary", householdId, actingCustomerId],
    queryFn: () => api.getHouseholdFinancialSummary(householdId as number, actingCustomerId as number),
    enabled: householdId !== null && actingCustomerId !== null,
  })
}
