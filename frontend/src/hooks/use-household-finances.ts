import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type Schemas = components["schemas"]

/** The household's record lists: the four financial resources (Phase 33) and
 * its goals (Phase 36). Each is an independent list of stored records —
 * nothing here totals, sums, projects or derives anything. */
export type FinanceResource = "income" | "expenses" | "assets" | "liabilities" | "goals"

export type FinanceRecord =
  | Schemas["HouseholdIncomeResponse"]
  | Schemas["HouseholdExpenseResponse"]
  | Schemas["HouseholdAssetResponse"]
  | Schemas["HouseholdLiabilityResponse"]
  | Schemas["HouseholdGoalResponse"]

type CreateBody =
  | Schemas["HouseholdIncomeCreate"]
  | Schemas["HouseholdExpenseCreate"]
  | Schemas["HouseholdAssetCreate"]
  | Schemas["HouseholdLiabilityCreate"]
  | Schemas["HouseholdGoalCreate"]

type UpdateBody =
  | Schemas["HouseholdIncomeUpdate"]
  | Schemas["HouseholdExpenseUpdate"]
  | Schemas["HouseholdAssetUpdate"]
  | Schemas["HouseholdLiabilityUpdate"]
  | Schemas["HouseholdGoalUpdate"]

/** One place mapping a resource to its four client calls, so every category
 * behaves identically (the backend enforces the same rules for all four). */
const CALLS = {
  income: {
    list: api.listHouseholdIncome,
    create: api.createHouseholdIncome,
    update: api.updateHouseholdIncome,
    remove: api.deleteHouseholdIncome,
  },
  expenses: {
    list: api.listHouseholdExpenses,
    create: api.createHouseholdExpense,
    update: api.updateHouseholdExpense,
    remove: api.deleteHouseholdExpense,
  },
  assets: {
    list: api.listHouseholdAssets,
    create: api.createHouseholdAsset,
    update: api.updateHouseholdAsset,
    remove: api.deleteHouseholdAsset,
  },
  liabilities: {
    list: api.listHouseholdLiabilities,
    create: api.createHouseholdLiability,
    update: api.updateHouseholdLiability,
    remove: api.deleteHouseholdLiability,
  },
  goals: {
    list: api.listHouseholdGoals,
    create: api.createHouseholdGoal,
    update: api.updateHouseholdGoal,
    remove: api.deleteHouseholdGoal,
  },
} as const

/** `GET /api/households/{id}/{resource}` — the records exactly as stored. */
export function useHouseholdFinanceQuery(
  resource: FinanceResource,
  householdId: number | null,
  actingCustomerId: number | null,
) {
  return useQuery({
    queryKey: ["household-finance", resource, householdId, actingCustomerId],
    queryFn: () => CALLS[resource].list(householdId as number, actingCustomerId as number) as Promise<FinanceRecord[]>,
    enabled: householdId !== null && actingCustomerId !== null,
  })
}

function useInvalidate(resource: FinanceResource, householdId: number | null) {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ["household-finance", resource, householdId] })
    // Phase 34: the financial summary is derived from these records, so a
    // change here makes the stored summary stale. The backend recomputes it;
    // the frontend only refetches.
    queryClient.invalidateQueries({ queryKey: ["household-summary", householdId] })
  }
}

/** `POST` — primary member only (the backend returns 403 otherwise). */
export function useCreateHouseholdFinanceRecord(resource: FinanceResource, householdId: number | null, actingCustomerId: number | null) {
  const invalidate = useInvalidate(resource, householdId)
  return useMutation({
    mutationFn: (body: CreateBody) =>
      (CALLS[resource].create as (h: number, c: number, b: CreateBody) => Promise<FinanceRecord>)(
        householdId as number,
        actingCustomerId as number,
        body,
      ),
    onSuccess: invalidate,
  })
}

/** `PUT` — sends only the fields that changed; the backend merges them. */
export function useUpdateHouseholdFinanceRecord(resource: FinanceResource, householdId: number | null, actingCustomerId: number | null) {
  const invalidate = useInvalidate(resource, householdId)
  return useMutation({
    mutationFn: ({ recordId, body }: { recordId: number; body: UpdateBody }) =>
      (CALLS[resource].update as (h: number, c: number, r: number, b: UpdateBody) => Promise<FinanceRecord>)(
        householdId as number,
        actingCustomerId as number,
        recordId,
        body,
      ),
    onSuccess: invalidate,
  })
}

/** `DELETE` — primary member only. */
export function useDeleteHouseholdFinanceRecord(resource: FinanceResource, householdId: number | null, actingCustomerId: number | null) {
  const invalidate = useInvalidate(resource, householdId)
  return useMutation({
    mutationFn: (recordId: number) => CALLS[resource].remove(householdId as number, actingCustomerId as number, recordId),
    onSuccess: invalidate,
  })
}
