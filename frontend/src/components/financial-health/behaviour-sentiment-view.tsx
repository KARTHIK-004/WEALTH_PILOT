import { Info, LineChart, MessageSquareText } from "lucide-react"
import type { ReactNode } from "react"

import { BehaviourInsightsPanel } from "@/components/financial-health/behaviour-insights-panel"
import { PlainSentimentSummary } from "@/components/financial-health/behaviour-sections"
import { RiskAssessmentPanel } from "@/components/financial-health/risk-assessment-panel"
import { SentimentInputPanel } from "@/components/financial-health/sentiment-input-panel"
import { SentimentResultsPanel } from "@/components/financial-health/sentiment-results-panel"
import { TransformerResearchPanel } from "@/components/financial-health/transformer-research-panel"
import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { OPTIONAL_NOTE_STATEMENT, type ModelState } from "@/lib/plain-sentiment"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]

/** The one-sentence explanation of the feature, shown under the page title. */
export const BEHAVIOUR_DESCRIPTION =
  "What your reported months show and, if you choose to write something, how your words read. This only explains: it changes nothing about your risk profile, your allocation or your recommendations."

export interface BehaviourSentimentViewProps {
  /** The text in the box. */
  draft: string
  /** True when a text has been submitted, so the visible results describe it and Clear has something to forget. */
  hasSubmittedText: boolean
  /** True when the visible results were not computed from the current box content. */
  stale: boolean
  /** A request is in flight (a second submit is refused while this is true). */
  pending: boolean
  /** The first load of the section, with no response yet. */
  loading: boolean
  /** A failed request: shown instead of any results, never alongside stale ones. */
  error: unknown
  /** The backend's response; undefined while loading or after an error. */
  data: Insight | undefined
  onDraftChange: (value: string) => void
  onSubmit: () => void
  onClear: () => void
  onRetry: () => void
  /**
   * Simple-English mode (the Financial Behaviour page): the reading is stated in everyday words first and the detailed technical reading (method, model status, confidence, intensity, every
   * label) moves inside an optional "Detailed reading" disclosure. Off by default, so every other use of this view is unchanged.
   */
  plainLanguage?: boolean
  /** Only the optional note and its reading (no records column): the Financial Behaviour page shows the records in its own sections. Implies nothing unless `plainLanguage` is set. */
  noteOnly?: boolean
  /** The backend's own model status, when known (used for the "model-based feature is disabled" sentence). */
  modelState?: ModelState
}

/** The two kinds of information on this page, stated side by side so they are never confused. */
function Intro() {
  return (
    <div className="grid gap-4 rounded-xl border p-4 md:grid-cols-2" role="group" aria-label="What this page shows">
      <div className="flex items-start gap-3">
        <LineChart className="text-muted-foreground mt-0.5 size-5 shrink-0" aria-hidden="true" />
        <div className="space-y-0.5">
          <p className="text-sm font-medium">Observed from your records</p>
          <p className="text-muted-foreground text-sm">Changes and ratios in the months you reported, worked out by the system. These describe your numbers.</p>
        </div>
      </div>
      <div className="flex items-start gap-3">
        <MessageSquareText className="text-muted-foreground mt-0.5 size-5 shrink-0" aria-hidden="true" />
        <div className="space-y-0.5">
          <p className="text-sm font-medium">Expressed in your own words (optional)</p>
          <p className="text-muted-foreground text-sm">An automatic suggestion about how text you choose to write reads. It is a suggestion, not a fact about you.</p>
        </div>
      </div>
    </div>
  )
}

function Footer({ data, compact = false }: { data: Insight; compact?: boolean }) {
  return (
    <div className="space-y-3">
      {!compact && data.caveats.length > 0 ? (
        <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-xs">
          {data.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      ) : null}
      <p className="text-muted-foreground text-xs">{data.purpose}</p>
      <TechnicalDetails
        items={[
          { label: "Method versions", value: data.model_version },
          { label: "Reading method", value: data.user_sentiment.method },
          { label: "Reading model version", value: data.user_sentiment.model_version },
          { label: "Reading status", value: data.user_sentiment.validation_status },
          { label: "Data sources", value: data.data_source },
          { label: "Generated at", value: data.analysis_timestamp },
        ]}
      />
    </div>
  )
}

/**
 * The "Financial Behaviour & Sentiment" page body as pure markup: every state is decided by props, so it renders identically in the app and in the Node component tests.
 *
 * DISPLAY ONLY (ADR-043, ADR-048). Every number and sentence in `data` is calculated by the backend; this component renders it and never calculates a figure, infers a sentiment, or turns
 * `uncertain` into `neutral`. A failed request shows the error and NO results; results whose text no longer matches the box are labelled as such. Layout: on a wide screen the records and the
 * stored assessment are on the left and the text box and its reading on the right; on a narrow screen they stack in the same order.
 */
/** The technical side of one reading, shown only inside the optional disclosure: the method, the model status, and the two values that are unavailable. */
function detailedReading(data: Insight, modelState: ModelState | undefined, panel: ReactNode): ReactNode {
  const reading = data.user_sentiment
  return (
    <TechnicalDetails
      title="Detailed reading (technical)"
      items={[
        { label: "Method", value: reading.model_version },
        { label: "Reading method", value: reading.method },
        { label: "Model status", value: modelState ?? "not reported" },
        { label: "Confidence", value: reading.confidence === null || reading.confidence === undefined ? "unavailable" : String(reading.confidence) },
        { label: "Intensity", value: reading.sentiment_intensity === null || reading.sentiment_intensity === undefined ? "unavailable (null)" : String(reading.sentiment_intensity) },
      ]}
    >
      {panel}
    </TechnicalDetails>
  )
}

export function BehaviourSentimentView({ draft, hasSubmittedText, stale, pending, loading, error, data, onDraftChange, onSubmit, onClear, onRetry, plainLanguage = false, noteOnly = false, modelState }: BehaviourSentimentViewProps) {
  const waiting = loading && !data && !error
  const records = !(plainLanguage && noteOnly)
  return (
    <div className="space-y-6">
      {records ? <Intro /> : null}

      <div className={records ? "grid gap-6 lg:grid-cols-12 lg:items-start" : "space-y-6"}>
        {records ? (
        <div className="space-y-6 lg:col-span-5" aria-busy={waiting}>
          {error ? (
            <p className="text-muted-foreground rounded-xl border border-dashed p-4 text-sm">Your records and your risk assessment are not shown because the request failed.</p>
          ) : waiting ? (
            <LoadingState label="Reading your information" />
          ) : data ? (
            <>
              <BehaviourInsightsPanel behaviour={data.behaviour} />
              <RiskAssessmentPanel data={data} />
            </>
          ) : null}
        </div>

        ) : null}

        <div className={records ? "space-y-6 lg:col-span-7" : "space-y-6"}>
          {plainLanguage ? <p className="text-sm">{OPTIONAL_NOTE_STATEMENT}</p> : null}
          <SentimentInputPanel draft={draft} hasSubmittedText={hasSubmittedText} pending={pending} onDraftChange={onDraftChange} onSubmit={onSubmit} onClear={onClear} />

          <div role="region" aria-label="Sentiment results" aria-live="polite" aria-busy={pending || loading} className="space-y-4">
            {stale && data && !error ? (
              <Alert>
                <Info aria-hidden="true" />
                <AlertTitle>These results are not for the text in the box</AlertTitle>
                <AlertDescription>Press Analyse to update them. Until then they describe the text you last analysed (or your records only).</AlertDescription>
              </Alert>
            ) : null}
            {pending && data ? <p className="text-muted-foreground text-xs">Updating…</p> : null}
            {error ? (
              <ErrorState error={error} onRetry={onRetry} />
            ) : data ? (
              plainLanguage ? (
                <>
                  <PlainSentimentSummary reading={data.user_sentiment} modelState={modelState} />
                  {detailedReading(data, modelState, <SentimentResultsPanel data={data} />)}
                  <TransformerResearchPanel research={data.transformer_research} />
                </>
              ) : (
                <>
                  <SentimentResultsPanel data={data} />
                  <TransformerResearchPanel research={data.transformer_research} />
                </>
              )
            ) : null}
          </div>
        </div>
      </div>

      {data && !error ? <Footer data={data} compact={plainLanguage && noteOnly} /> : null}
    </div>
  )
}
