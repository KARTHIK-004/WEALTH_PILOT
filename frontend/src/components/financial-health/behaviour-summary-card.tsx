import { ArrowRight, MessageSquareText } from "lucide-react"
import { Link } from "react-router"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { usePersonalizedInsightQuery } from "@/hooks/use-personalized-insight"
import { BEHAVIOUR_PAGE_PATH, summariseBehaviour } from "@/lib/behaviour-summary"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]

export interface BehaviourSummaryViewProps {
  data: Insight | undefined
  loading: boolean
  error: unknown
  onRetry: () => void
}

/**
 * The compact summary on Financial Health: DISPLAY ONLY, from the backend's records-only response. It has no text box and never holds or sends user text; the detailed input, the
 * reading of the user's words, the limitations and every behaviour finding live on the dedicated "Financial Behaviour & Sentiment" page, which the link opens.
 */
export function BehaviourSummaryView({ data, loading, error, onRetry }: BehaviourSummaryViewProps) {
  const summary = data ? summariseBehaviour(data) : null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquareText className="text-muted-foreground size-4" aria-hidden="true" /> Financial behaviour &amp; sentiment
        </CardTitle>
        <CardDescription>A short summary of what your reported months show. Open the full page to write about your finances and see how your words read.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3" aria-live="polite" aria-busy={loading}>
        {error ? (
          <ErrorState error={error} onRetry={onRetry} />
        ) : loading && !data ? (
          <LoadingState label="Summarising your reported months" />
        ) : summary ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                {summary.months} reported month{summary.months === 1 ? "" : "s"}
              </Badge>
              {summary.latestPeriod ? <span className="text-muted-foreground text-xs">latest {summary.latestPeriod}</span> : null}
            </div>
            {!summary.hasRecords ? (
              <SectionUnavailable
                title="No monthly records yet"
                message="Add the months you can in your monthly records and the changes in your income, expenses and savings will appear here. Nothing is assumed in the meantime."
              />
            ) : summary.facts.length === 0 ? (
              <SectionUnavailable title="Nothing to describe yet" message="The months reported so far do not give enough to describe a change or a ratio." />
            ) : (
              <ul className="space-y-1.5 text-sm" aria-label="Observed from your records">
                {summary.facts.map((fact) => (
                  <li key={fact.text}>{fact.text}</li>
                ))}
              </ul>
            )}
            {summary.moreFacts ? <p className="text-muted-foreground text-xs">More findings are on the full page.</p> : null}
            {summary.assessmentStatement ? <p className="text-sm">{summary.assessmentStatement}</p> : <p className="text-muted-foreground text-sm">No risk assessment is on file for this profile yet.</p>}
          </>
        ) : null}
      </CardContent>
      <CardFooter>
        {/* A real link styled as a button (as on the home page): rendering a Button as a Link would announce it to assistive technology as a button, not a link. */}
        <Link to={BEHAVIOUR_PAGE_PATH} className={buttonVariants({ variant: "outline" })}>
          Open Financial Behaviour &amp; Sentiment <ArrowRight aria-hidden="true" />
        </Link>
      </CardFooter>
    </Card>
  )
}

export function BehaviourSummaryCard({ profileId }: { profileId: number }) {
  const insight = usePersonalizedInsightQuery(profileId, null)
  return <BehaviourSummaryView data={insight.data} loading={insight.isLoading} error={insight.error} onRetry={() => void insight.refetch()} />
}
