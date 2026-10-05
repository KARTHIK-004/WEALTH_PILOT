import { useMutation } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type ProfileCreateRequest = components["schemas"]["ProfileCreateRequest"]

/** `POST /api/profiles` — a mutation, not a query, since it is an
 * explicit user-triggered creation (matches `useScenarioCompare`'s own
 * pattern). No profile field is computed here; the request body is typed
 * straight from the generated schema and passed through to the
 * centralized API client unmodified. */
export function useCreateProfile() {
  return useMutation({
    mutationFn: (body: ProfileCreateRequest) => api.createProfile(body),
  })
}
