import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type QuestionnaireAnswersSubmitRequest = components["schemas"]["QuestionnaireAnswersSubmitRequest"]

/** `GET /api/questionnaire` — the real, existing MiFID-II questionnaire
 * dataset (Phase 15's own parser of `datasets/raw/FAR-Trans/
 * questionnaires.csv`). Sections/questions/options are never hard-coded
 * in React; this hook is the only place this endpoint is called from. */
export function useQuestionnaireQuery() {
  return useQuery({
    queryKey: ["questionnaire"],
    queryFn: () => api.getQuestionnaire(),
  })
}

/** `GET /api/profiles/{id}/questionnaire` (Phase 23) — this profile's
 * previously persisted answers, if any, so the questionnaire page can
 * preselect them. Returns `{ answers: [] }` for a profile that has never
 * submitted anything, not an error. */
export function useQuestionnaireAnswersQuery(profileId: number | null) {
  return useQuery({
    queryKey: ["questionnaire-answers", profileId],
    queryFn: () => api.getQuestionnaireAnswers(profileId as number),
    enabled: profileId !== null,
  })
}

/** `POST /api/profiles/{id}/questionnaire` (Phase 23) — persists the
 * customer's current answer set. Re-submitting a question the customer
 * already answered updates that row server-side (never a duplicate); this
 * hook does no scoring or inference of its own, it only forwards the
 * submitted `{question_number, option_key}` pairs and re-syncs the cached
 * answers query with the server's authoritative response. */
export function useSubmitQuestionnaireAnswers(profileId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: QuestionnaireAnswersSubmitRequest) => api.submitQuestionnaireAnswers(profileId as number, body),
    onSuccess: (data) => {
      queryClient.setQueryData(["questionnaire-answers", profileId], data)
    },
  })
}
