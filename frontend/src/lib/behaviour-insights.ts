/**
 * What the "What your records show" panel lists, chosen from the BACKEND's `behaviour.findings` (ADR-043, ADR-048).
 *
 * Pure TypeScript with no React or DOM, unit-tested by `npm test`. It selects, orders and labels findings the backend already produced: the sentence (`statement`), its source fields and
 * its direction are shown exactly as returned. It never calculates a change, a ratio or a percentage, never decides whether a direction is good or bad, and never reads user text.
 */
import type { components } from "@/types/api"

export type Finding = components["schemas"]["BehaviourFindingOut"]

export interface InsightRow {
  code: string
  /** The backend's own sentence, unchanged. */
  statement: string
  category: Finding["category"]
  categoryLabel: string
  /** The backend's direction value, or null when it gives none (a ratio or an activity fact has no direction). */
  direction: NonNullable<Finding["direction"]> | null
  directionLabel: string | null
  /** The source fields the sentence rests on, as the backend names them. */
  sources: string[]
}

export const CATEGORY_LABELS: Record<Finding["category"], string> = {
  trend: "Change over time",
  activity: "How often",
  ratio: "Share of income",
  data_quality: "Data quality",
  coverage: "Coverage",
}

export const DIRECTION_LABELS: Record<NonNullable<Finding["direction"]>, string> = {
  increased: "Increased",
  decreased: "Decreased",
  unchanged: "Unchanged",
}

/** The bare "N months have been reported" finding: the panel shows the month count in its header, so the sentence is not repeated as a row. */
const isMonthCount = (f: Pick<Finding, "sources">): boolean => f.sources.length === 1 && f.sources[0] === "observation_count"

/** Observed findings, in the backend's order, without the bare month-count sentence. A finding the backend marks unavailable or not included is never shown as an insight. */
export function selectInsightRows(findings: readonly Finding[]): InsightRow[] {
  return findings
    .filter((f) => f.status === "observed" && !isMonthCount(f))
    .map((f) => ({
      code: f.code,
      statement: f.statement,
      category: f.category,
      categoryLabel: CATEGORY_LABELS[f.category] ?? f.category,
      direction: f.direction ?? null,
      directionLabel: f.direction ? (DIRECTION_LABELS[f.direction] ?? f.direction) : null,
      sources: f.sources,
    }))
}

/** The backend's own finding codes that describe SPENDING (the change in the month's spending and its share of income). Which findings these are is a naming choice, not a calculation. */
export const SPENDING_FINDING_CODES: readonly string[] = ["expenses_trend", "expense_to_income_ratio"]

/** The observed spending findings, in the backend's order, sentences unchanged. Empty when the customer has reported no months. */
export function selectSpendingRows(findings: readonly Finding[]): InsightRow[] {
  return selectInsightRows(findings).filter((row) => SPENDING_FINDING_CODES.includes(row.code))
}

/** What the backend could not or did not state, with its own reason, in its own order (shown collapsed under the insights). */
export function selectNotShown(findings: readonly Finding[]): Finding[] {
  return findings.filter((f) => f.status !== "observed")
}
