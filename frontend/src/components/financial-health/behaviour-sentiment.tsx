import { useState } from "react"

import { BehaviourSentimentView } from "@/components/financial-health/behaviour-sentiment-view"
import { usePersonalizedInsightQuery } from "@/hooks/use-personalized-insight"
import type { ModelState } from "@/lib/plain-sentiment"
import { INITIAL_INPUT_STATE, clearAll, editDraft, resultsAreStale, submitDraft, type InputState } from "@/lib/user-text-input"

/**
 * "Financial Behaviour & Sentiment" page body -- DISPLAY ONLY (ADR-043, ADR-048).
 *
 * Owns the input state and the query; everything shown comes from the backend response (`POST /api/profiles/{id}/personalized-insights`) through the view. The text lives only in this
 * component's state and in the query key, which the hook drops as soon as nothing observes it (`gcTime: 0`): unmounting the card, switching profile (the page keys the card by profile)
 * or pressing Clear leaves no copy of the text in the cache, and nothing is written to browser storage, a URL, the console or any analytics. The rules for what may be sent, the
 * duplicate-submit guard and the "results no longer match the box" check are in `@/lib/user-text-input` (unit-tested without a DOM).
 */
export function BehaviourSentimentCard({ profileId, plainLanguage = false, noteOnly = false, modelState }: { profileId: number; plainLanguage?: boolean; noteOnly?: boolean; modelState?: ModelState }) {
  const [input, setInput] = useState<InputState>(INITIAL_INPUT_STATE)
  const insight = usePersonalizedInsightQuery(profileId, input.submitted)
  const pending = insight.isFetching

  function handleSubmit() {
    const outcome = submitDraft(input, pending)
    if (outcome.rejected) return
    setInput(outcome.state)
    if (outcome.refetch) void insight.refetch()
  }

  return (
    <BehaviourSentimentView
      draft={input.draft}
      hasSubmittedText={input.submitted !== null}
      stale={resultsAreStale(input)}
      pending={pending}
      loading={insight.isLoading}
      error={insight.error}
      data={insight.data}
      onDraftChange={(value) => setInput((current) => editDraft(current, value))}
      onSubmit={handleSubmit}
      onClear={() => setInput(clearAll())}
      onRetry={() => void insight.refetch()}
      plainLanguage={plainLanguage}
      noteOnly={noteOnly}
      modelState={modelState}
    />
  )
}
