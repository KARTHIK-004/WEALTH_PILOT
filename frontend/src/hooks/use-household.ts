import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type HouseholdCreateRequest = components["schemas"]["HouseholdCreateRequest"]
type HouseholdMemberCreateRequest = components["schemas"]["HouseholdMemberCreateRequest"]

/** `GET /api/profiles/{id}/household` (Phase 32) — the current customer's
 * household and their own membership, or `household: null` when they have
 * none. Reading it never creates a household. */
export function useProfileHouseholdQuery(profileId: number | null) {
  return useQuery({
    queryKey: ["household", profileId],
    queryFn: () => api.getProfileHousehold(profileId as number),
    enabled: profileId !== null,
  })
}

/** `GET /api/households/{id}/members` — only enabled once the customer is
 * known to belong to that household. */
export function useHouseholdMembersQuery(householdId: number | null, actingCustomerId: number | null) {
  return useQuery({
    queryKey: ["household-members", householdId, actingCustomerId],
    queryFn: () => api.getHouseholdMembers(householdId as number, actingCustomerId as number),
    enabled: householdId !== null && actingCustomerId !== null,
  })
}

/** `POST /api/households` — the caller becomes the household's `self`/
 * `primary` member. Nothing else is created. */
export function useCreateHousehold(profileId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: HouseholdCreateRequest) => api.createHousehold(profileId as number, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["household", profileId] }),
  })
}

/** `POST /api/households/{id}/members` (primary member only). */
export function useAddHouseholdMember(householdId: number | null, profileId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: HouseholdMemberCreateRequest) =>
      api.addHouseholdMember(householdId as number, profileId as number, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household-members", householdId] })
      queryClient.invalidateQueries({ queryKey: ["household", profileId] })
    },
  })
}

/** `DELETE /api/households/{id}/members/{memberId}` (primary member only;
 * the primary member itself can never be removed). */
export function useRemoveHouseholdMember(householdId: number | null, profileId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (memberId: number) => api.removeHouseholdMember(householdId as number, profileId as number, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household-members", householdId] })
      queryClient.invalidateQueries({ queryKey: ["household", profileId] })
    },
  })
}
