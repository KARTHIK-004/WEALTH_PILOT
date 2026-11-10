import type { ReactNode } from "react"

import {
  BehaviourOverviewView,
  InvestmentBehaviourView,
  RecordedMonthsSection,
  SpendingPatternView,
} from "@/components/financial-health/behaviour-sections"
import { BehaviourSentimentCard } from "@/components/financial-health/behaviour-sentiment"
import { DevDemoHint } from "@/components/financial-health/demo-request-notice"
import { CommitmentsView } from "@/components/financial-health/individual-finances"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { useProfileHouseholdQuery } from "@/hooks/use-household"
import { useMonthlyRecordsQuery } from "@/hooks/use-monthly-records"
import { usePersonalizedInsightQuery } from "@/hooks/use-personalized-insight"
import { useSentimentModelStatusQuery } from "@/hooks/use-sentiment-model-status"
import { ApiUnreachableError } from "@/lib/api-client"
import { investmentBehaviour } from "@/lib/investment-behaviour"
import { spendingPattern } from "@/lib/spending-pattern"
import type { ModelState } from "@/lib/plain-sentiment"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]
type MonthlyRecord = components["schemas"]["MonthlyRecordResponse"]
type Health = components["schemas"]["FinancialHealthSection"]

export interface FinancialBehaviourRealViewProps {
  /** The records-only insight (`POST .../personalized-insights` with no text). */
  insight: Insight | undefined
  insightLoading: boolean
  insightError: unknown
  onRetryInsight: () => void
  /** The customer's own monthly records (`GET .../monthly-financial-records`). */
  records: readonly MonthlyRecord[] | undefined
  recordsLoading: boolean
  recordsError: unknown
  onRetryRecords: () => void
  /** The stored analysis (`POST /api/analysis`, cached): its behaviour flags and spending pattern. */
  analysisLoading: boolean
  analysisError: unknown
  health: Health | null | undefined
  onRetryAnalysis: () => void
  /** The household this profile belongs to, when it does (loans and EMIs exist only as a household's own records). */
  householdName: string | null
  /** The optional-note section (the card that owns the text box and its reading). */
  note: ReactNode
  /** A development build that allows demonstration mode: a profile with no records gets a pointer to the fictional examples (a link, never data). */
  demoHint?: boolean
}

/**
 * The Financial Behaviour page body for a real profile, as pure markup: every state is decided by props, so it renders identically in the app and in the Node component tests. DISPLAY ONLY:
 * the overview, the trends, the investment status and the spending pattern are the backend's findings and model results selected and worded in `lib/`; nothing is calculated here. Zero
 * records show the overview's empty state and nothing is invented; a failed request shows its own error and no values; demo data is never used.
 */
export function FinancialBehaviourRealView(props: FinancialBehaviourRealViewProps) {
  const { insight, health } = props
  const periods = (props.records ?? []).map((r) => r.period)
  const behaviour = insight ? investmentBehaviour({ findings: insight.behaviour.findings, driftFlag: health?.behaviour_drift_flag, anomalyFlag: health?.isolation_forest_anomaly }) : undefined
  const spending = spendingPattern({
    loading: props.analysisLoading,
    error: props.analysisError ? { unreachable: props.analysisError instanceof ApiUnreachableError } : null,
    persona: health?.expense_persona,
    personaUnavailableReason: health?.expense_persona_unavailable_reason,
    history: insight?.behaviour.history,
  })
  const showInvestment = Boolean(insight) || props.insightLoading
  return (
    <div className="space-y-8">
      {props.demoHint && insight && insight.behaviour.observation_count === 0 ? <DevDemoHint /> : null}
      <BehaviourOverviewView insight={insight} periods={periods} loading={props.insightLoading} error={props.insightError} onRetry={props.onRetryInsight} />
      <RecordedMonthsSection records={props.records} loading={props.recordsLoading} error={props.recordsError} onRetry={props.onRetryRecords} />
      <div className="grid gap-6 md:grid-cols-2">
        {showInvestment ? <InvestmentBehaviourView behaviour={behaviour} loading={props.insightLoading} /> : null}
        <SpendingPatternView state={spending} onRetry={props.onRetryAnalysis} />
      </div>
      <CommitmentsView householdName={props.householdName} />
      <section aria-labelledby="note-heading" className="space-y-3">
        <h2 id="note-heading" className="text-lg font-semibold">
          Your optional written note
        </h2>
        {props.note}
      </section>
    </div>
  )
}

/** The container: reads the records-only insight, the monthly records, the stored analysis, the household and the model status, and hands them to the pure view. */
export function FinancialBehaviourReal({ profileId, demoHint = false }: { profileId: number; demoHint?: boolean }) {
  const insight = usePersonalizedInsightQuery(profileId, null)
  const records = useMonthlyRecordsQuery(profileId)
  const analysis = useAnalysisQuery(profileId)
  const household = useProfileHouseholdQuery(profileId)
  const model = useSentimentModelStatusQuery()
  const modelState: ModelState | undefined = model.data?.state
  return (
    <FinancialBehaviourRealView
      insight={insight.data}
      insightLoading={insight.isLoading}
      insightError={insight.error}
      onRetryInsight={() => void insight.refetch()}
      records={records.data?.records}
      recordsLoading={records.isLoading}
      recordsError={records.error}
      onRetryRecords={() => void records.refetch()}
      analysisLoading={analysis.isLoading}
      analysisError={analysis.error}
      health={analysis.data?.financial_health}
      onRetryAnalysis={() => void analysis.refetch()}
      householdName={household.data?.household?.name ?? null}
      demoHint={demoHint}
      note={<BehaviourSentimentCard key={profileId} profileId={profileId} plainLanguage noteOnly modelState={modelState} />}
    />
  )
}
