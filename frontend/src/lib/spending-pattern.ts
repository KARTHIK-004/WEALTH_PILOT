/**
 * "Spending pattern": shown ONLY when the existing spending model produced one for this profile (`expense_persona` of the stored analysis). Pure TypeScript with no React or DOM, unit-tested by
 * `npm test`. It never infers a pattern from missing data and keeps six situations apart so that none is mistaken for another: loading, backend unavailable, no records, insufficient records,
 * the model not applicable or unavailable, and a valid result.
 */
export type SpendingKind = "loading" | "backend_unavailable" | "no_records" | "insufficient_records" | "model_unavailable" | "valid"

export const SPENDING_TITLE = "Spending pattern"
export const NOT_AVAILABLE = "Not available"
export const SPENDING_NOT_AVAILABLE_MESSAGE = "A spending pattern is shown only when the spending model can be applied to this profile."

export interface SpendingPatternState {
  kind: SpendingKind
  /** The pattern name, exactly as the model returned it (only for `valid`). */
  pattern: string | null
  /** A short line saying WHY nothing is shown (never for `valid`). */
  reason: string | null
}

export interface SpendingInput {
  /** The stored analysis is still loading. */
  loading: boolean
  /** The analysis request failed: `unreachable` is true when the backend could not be reached at all. */
  error: { unreachable: boolean } | null
  /** `financial_health.expense_persona` and its reason, when the analysis arrived. */
  persona: string | null | undefined
  personaUnavailableReason: string | null | undefined
  /** The backend's own history word for the reported months (`none`, `single_month`, `multiple_months`), when known. */
  history: "none" | "single_month" | "multiple_months" | undefined
}

export function spendingPattern(input: SpendingInput): SpendingPatternState {
  if (input.error) {
    return input.error.unreachable
      ? { kind: "backend_unavailable", pattern: null, reason: "The service could not be reached, so the spending pattern could not be checked." }
      : { kind: "model_unavailable", pattern: null, reason: "The analysis could not be completed, so the spending model result is not available." }
  }
  if (input.loading) return { kind: "loading", pattern: null, reason: null }
  if (input.persona) return { kind: "valid", pattern: input.persona, reason: null }
  if (input.history === "none") return { kind: "no_records", pattern: null, reason: "No monthly records have been added yet." }
  if (input.history === "single_month") return { kind: "insufficient_records", pattern: null, reason: "Only one month has been recorded." }
  return { kind: "model_unavailable", pattern: null, reason: input.personaUnavailableReason ?? "The spending model has not produced a result for this profile." }
}
