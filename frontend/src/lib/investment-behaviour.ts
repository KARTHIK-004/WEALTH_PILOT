/**
 * "Investment behaviour": how recent investing compares with the person's own history, in five plain statuses. Pure TypeScript with no React or DOM, unit-tested by `npm test`.
 *
 * It SELECTS and LABELS what the backend already returned and calculates nothing: the month-over-month investment finding (`investment_contribution_trend`, its direction decided by the
 * backend) and the behaviour model's own flags from the stored analysis (`behaviour_drift_flag`, `isolation_forest_anomaly`). "Unusual" is claimed ONLY when the backend model flagged it; with no
 * comparison history the status is "not enough history", never "unusual" and never a guess. Nothing here changes a risk score, a recommendation or an allocation.
 */
import type { Finding } from "@/lib/behaviour-insights"

export type InvestmentStatus = "consistent" | "increasing" | "decreasing" | "unusual" | "not_enough_history"

export interface InvestmentBehaviour {
  status: InvestmentStatus
  /** The status in one or two words. */
  label: string
  /** One sentence in everyday words. */
  detail: string
  /** The backend's own sentence behind a trend status, unchanged (null when the status does not rest on one). */
  fromRecords: string | null
}

export const NOT_ENOUGH_HISTORY_DETAIL = "Not enough investment history to compare."
export const STATUS_LABELS: Record<InvestmentStatus, string> = {
  consistent: "Consistent",
  increasing: "Increasing",
  decreasing: "Decreasing",
  unusual: "Unusual",
  not_enough_history: "Not enough history",
}

export interface InvestmentInput {
  findings: readonly Finding[] | undefined
  /** The behaviour model's flag from the stored analysis: true unusual, false not, null/undefined not available. */
  driftFlag?: boolean | null
  anomalyFlag?: boolean | null
}

export function investmentBehaviour({ findings, driftFlag, anomalyFlag }: InvestmentInput): InvestmentBehaviour {
  const trend = findings?.find((f) => f.code === "investment_contribution_trend")
  const result = (status: InvestmentStatus, detail: string, fromRecords: string | null = null): InvestmentBehaviour => ({ status, label: STATUS_LABELS[status], detail, fromRecords })
  if (driftFlag === true || anomalyFlag === true) return result("unusual", "Your recent investing pattern differs from your own earlier history.")
  if (trend?.status === "observed" && trend.direction) {
    if (trend.direction === "increased") return result("increasing", "Your latest monthly investment is higher than the month before.", trend.statement)
    if (trend.direction === "decreased") return result("decreasing", "Your latest monthly investment is lower than the month before.", trend.statement)
    return result("consistent", "Your latest monthly investment is the same as the month before.", trend.statement)
  }
  if (driftFlag === false && anomalyFlag === false) return result("consistent", "Your recent investing pattern is consistent with your earlier history.")
  return result("not_enough_history", NOT_ENOUGH_HISTORY_DETAIL, trend?.status === "unavailable" ? trend.statement : null)
}
