import { useState } from "react"

import { DemoFamilyView } from "@/components/financial-health/demo-family-behaviour"
import { useDemoFamilyQuery } from "@/hooks/use-demo-financial-behaviour"
import { DEMO_EXAMPLES, DEMO_EXAMPLE_TEXT } from "@/lib/demo-mode"
import { clearAll, editDraft, resultsAreStale, submitDraft, type InputState } from "@/lib/user-text-input"

/**
 * Family demonstration body of "Financial Behaviour & Sentiment" (development only, `?demo=family`). It starts with the fictional example note already read for the primary member, owns the same
 * input state as the real card (the same pure typing / submit / clear rules), and shows only what `POST /api/demo/family-financial-behaviour` returned. The text lives only in this component's
 * state and the in-memory query key; nothing is written to browser storage, a URL or the console. A failed request is an error, never replaced by demo data.
 */
export function DemoFamilyCard() {
  const [input, setInput] = useState<InputState>({ draft: DEMO_EXAMPLE_TEXT, submitted: DEMO_EXAMPLE_TEXT })
  const demo = useDemoFamilyQuery(input.submitted)
  const pending = demo.isFetching

  function handleSubmit() {
    const outcome = submitDraft(input, pending)
    if (outcome.rejected) return
    setInput(outcome.state)
    if (outcome.refetch) void demo.refetch()
  }

  return (
    <DemoFamilyView
      draft={input.draft}
      hasSubmittedText={input.submitted !== null}
      stale={resultsAreStale(input)}
      pending={pending}
      loading={demo.isLoading}
      error={demo.error}
      data={demo.data}
      examples={DEMO_EXAMPLES}
      onUseExample={(text) => setInput((current) => editDraft(current, text))}
      onDraftChange={(value) => setInput((current) => editDraft(current, value))}
      onSubmit={handleSubmit}
      onClear={() => setInput(clearAll())}
      onRetry={() => void demo.refetch()}
    />
  )
}
