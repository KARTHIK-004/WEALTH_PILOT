/**
 * What the "Financial behaviour overview" shows, SELECTED from the backend's `behaviour.findings` and the reported month labels. Pure TypeScript with no React or DOM, unit-tested by `npm test`.
 *
 * Every number and sentence is the backend's (`derive_findings` over `compute_behaviour_features`); this module only picks the income, spending and savings trend findings and the savings-rate
 * finding by their codes, formats a month label and a date range, and lists what the backend could not calculate. It never calculates a change, a ratio or a percentage.
 */
import { DIRECTION_LABELS, type Finding } from "./behaviour-insights.ts"

export const OVERVIEW_TITLE = "Financial behaviour overview"
export const OVERVIEW_EXPLANATION =
  "Your financial behaviour is calculated from the monthly records you provide. It describes your numbers and does not change your risk profile, investments or recommendations."

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

/** "2026-03" becomes "Mar 2026". A value that is not YYYY-MM is returned unchanged. */
export function monthLabel(period: string): string {
  const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(period)
  return match ? `${MONTHS[Number(match[2]) - 1]} ${match[1]}` : period
}

/** The first and last reported month ("Mar 2026 to Aug 2026"), or just the one month, or null for none. YYYY-MM sorts correctly as text. */
export function dateRange(periods: readonly string[]): string | null {
  if (periods.length === 0) return null
  const sorted = [...periods].sort()
  const first = monthLabel(sorted[0])
  const last = monthLabel(sorted[sorted.length - 1])
  return first === last ? first : `${first} to ${last}`
}

export interface TrendRow {
  code: string
  label: string
  /** The backend's direction as a word, or null when the backend gave none (the change could not be measured). */
  directionLabel: string | null
  /** The backend's own sentence, unchanged. */
  statement: string
  available: boolean
}

export const TREND_ROWS: readonly { code: string; label: string }[] = [
  { code: "income_trend", label: "Income" },
  { code: "expenses_trend", label: "Spending" },
  { code: "savings_trend", label: "Savings" },
]

export function overviewTrends(findings: readonly Finding[]): TrendRow[] {
  return TREND_ROWS.flatMap(({ code, label }) => {
    const finding = findings.find((f) => f.code === code)
    if (!finding) return []
    const available = finding.status === "observed"
    return [{ code, label, available, statement: finding.statement, directionLabel: available && finding.direction ? DIRECTION_LABELS[finding.direction] : null }]
  })
}

export interface SavingsRate {
  /** The backend's ratio as a fraction (formatted by the caller), or null. */
  ratio: number | null
  statement: string
}

/** The backend's savings-to-income ratio for the latest reported month, or null when there is no such finding. */
export function savingsRate(findings: readonly Finding[]): SavingsRate | null {
  const finding = findings.find((f) => f.code === "savings_to_income_ratio")
  if (!finding) return null
  const ratio = finding.status === "observed" && typeof finding.values?.ratio === "number" ? finding.values.ratio : null
  return { ratio, statement: finding.statement }
}

/** The finding codes whose absence the overview explains. */
const EXPLAINED_CODES: readonly string[] = ["income_trend", "expenses_trend", "savings_trend", "savings_to_income_ratio", "expense_to_income_ratio"]

/** The backend's own reasons (its sentences, unchanged) for the overview values it could not calculate, in its order; plus its data-quality notes. */
export function missingDataNotes(findings: readonly Finding[]): string[] {
  const unavailable = findings.filter((f) => f.status === "unavailable" && EXPLAINED_CODES.includes(f.code)).map((f) => f.statement)
  const quality = findings.filter((f) => f.category === "data_quality").map((f) => f.statement)
  return [...unavailable, ...quality]
}
