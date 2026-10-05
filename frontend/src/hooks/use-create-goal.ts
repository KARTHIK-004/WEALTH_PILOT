import { useMutation } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type GoalCreate = components["schemas"]["GoalCreate"]

/** `POST /api/profiles/{id}/goals` (Phase 23) — creates ONE real goal for
 * an already-existing profile. A mutation per goal (not a batch call),
 * so `onboarding-goals-page.tsx` can report each goal's own real,
 * independent success/failure rather than an all-or-nothing result. */
export function useCreateGoal(profileId: number | null) {
  return useMutation({
    mutationFn: (body: GoalCreate) => api.createGoal(profileId as number, body),
  })
}
