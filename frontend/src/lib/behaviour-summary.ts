/**
 * What the compact "Financial behaviour & sentiment" summary on Financial Health shows, chosen from the BACKEND's records-only response (`POST .../personalized-insights` with no text).
 * Pure TypeScript with no React or DOM, unit-tested by `npm test`. It selects and labels existing backend statements; it never calculates a figure, never reads or sends user text, and never
 * infers a sentiment (the summary has no text box: writing about your finances happens on the dedicated page).
 */

export const BEHAVIOUR_PAGE_PATH = "/financial-behaviour"
export const SUMMARY_MAX_FACTS = 3

export interface SummaryStatement {
  kind: string
  text: string
  sources: string[]
}

export interface SummaryInsight {
  behaviour: { observation_count: number; latest_period: string | null }
  statements: SummaryStatement[]
  risk_profile: { category: string } | null
}

export interface BehaviourSummary {
  months: number
  latestPeriod: string | null
  hasRecords: boolean
  /** Up to SUMMARY_MAX_FACTS observed facts, in the backend's order, without the bare "N months have been reported" line (the month count is shown separately). */
  facts: SummaryStatement[]
  /** More observed facts exist than the summary shows, so the page link is where the rest is. */
  moreFacts: boolean
  /** The backend's own sentence about the stored assessment, or null when none is on file. */
  assessmentStatement: string | null
}

const isMonthCount = (s: SummaryStatement): boolean => s.sources.length === 1 && s.sources[0] === "observation_count"

export function summariseBehaviour(data: SummaryInsight): BehaviourSummary {
  const observed = data.statements.filter((s) => s.kind === "behaviour_fact" && !isMonthCount(s))
  const months = data.behaviour.observation_count
  return {
    months,
    latestPeriod: data.behaviour.latest_period,
    hasRecords: months > 0,
    facts: observed.slice(0, SUMMARY_MAX_FACTS),
    moreFacts: observed.length > SUMMARY_MAX_FACTS,
    assessmentStatement: data.statements.find((s) => s.kind === "risk_assessment")?.text ?? null,
  }
}
