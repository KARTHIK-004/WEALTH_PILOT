/**
 * Centralized presentation-formatting helpers (Phase 17 section 26):
 * "formatting must not change the underlying numerical value... do not
 * perform financial calculations merely to format values." Every
 * function here does exactly one thing to an ALREADY-AUTHORITATIVE
 * number from the API — round for display, add a `%`/currency symbol,
 * format a date string — and never combines two source values into a
 * new derived figure (a goal's contribution gap divided by its target,
 * an emergency fund's current amount divided by its required amount,
 * etc. are never computed here or anywhere in this codebase's frontend).
 *
 * Currency: `close_prices.csv` (`docs/PROJECT_PLAN.md` Part 0) is
 * documented as "in euros," and no API field specifies a different
 * currency for goal/portfolio amounts — the backend's own numbers are
 * unchanged by the display choice below.
 *
 * Display currency (2026-10-03, by explicit instruction, for the demo
 * presentation): amounts are shown with the ₹ (INR) symbol and Indian
 * digit grouping instead of €/EUR. This is a presentation relabel only —
 * every number is still the backend's own already-computed value,
 * formatted with `Intl.NumberFormat("en-IN", ...)` exactly as the EUR
 * formatter it replaces formatted with `"en-IE"`; nothing here converts,
 * rescales or reinterprets the value at a different exchange rate.
 */

const CURRENCY_FORMATTER = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
})

const DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "numeric",
})

/** A plain currency amount, already computed by the backend — this only
 * adds the ₹ symbol and thousands separators, never changes the value. */
export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "Not available"
  return CURRENCY_FORMATTER.format(value)
}

/** A fraction already in [0, 1] from the API (e.g. `confidence: 0.83`,
 * `monte_carlo_success_probability: 0.68`) — multiplying by 100 for a
 * "%" suffix is the exact `0.55 → 55%` example section 26 itself
 * approves as formatting, not calculation. */
export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "Not available"
  return `${(value * 100).toFixed(digits)}%`
}

/** An ISO date string from the API, formatted for readability only —
 * the underlying date is never altered. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not available"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not available"
  return DATE_FORMATTER.format(date)
}

/** Title-cases a snake_case/lower status string for display
 * (`blocked_rejected` -> "Blocked Rejected") — text transformation, not
 * a value change. */
export function formatStatusLabel(value: string | null | undefined): string {
  if (!value) return "Unknown"
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}
