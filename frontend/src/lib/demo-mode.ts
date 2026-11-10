/**
 * Demo mode for the Financial Behaviour & Sentiment page (development only). Pure TypeScript with no React, DOM or `import.meta`, so it is unit-tested by `npm test`.
 *
 * The page shows FICTIONAL, fixed demonstration data (served by `POST /api/demo/financial-behaviour`, which the backend answers only when `DEMO_MODE_ENABLED=true`) when the address carries
 * `?demo=true` AND this build allows it (a Vite dev server, or `VITE_DEMO_MODE=true`). Anywhere else the query is ignored and the page behaves exactly as before: a production build never
 * shows fictional data, and a backend that is down or has no records is shown as exactly that, never replaced by demo data.
 */

export const DEMO_QUERY_PARAM = "demo"
export const DEMO_QUERY_VALUE = "true"
export const DEMO_PAGE_PATH = "/financial-behaviour"
export const DEMO_DISABLED_TITLE = "Demo mode is not enabled"

/** A build allows demo mode only in development or when `VITE_DEMO_MODE` is exactly the string "true". */
export function demoAllowed(env: { DEV?: boolean; VITE_DEMO_MODE?: string }): boolean {
  return env.DEV === true || env.VITE_DEMO_MODE === "true"
}

/** The two demonstrations: `?demo=true` (one fictional individual) and `?demo=family` (a fictional family). */
export type DemoKind = "individual" | "family"
export const DEMO_FAMILY_VALUE = "family"

/** Which demonstration the address asks for, or null. Only a build that allows demo mode and EXACTLY one `demo` parameter with the value `true` or `family` count; anything else is the normal page. */
export function demoKind(search: string, allowed: boolean): DemoKind | null {
  if (!allowed) return null
  const values = new URLSearchParams(search).getAll(DEMO_QUERY_PARAM)
  if (values.length !== 1) return null
  return values[0] === DEMO_QUERY_VALUE ? "individual" : values[0] === DEMO_FAMILY_VALUE ? "family" : null
}

/** True only when demo is allowed AND the query string asks for the individual demonstration with the exact value `true`. */
export function isDemoRequested(search: string, allowed: boolean): boolean {
  if (!allowed) return false
  const values = new URLSearchParams(search).getAll(DEMO_QUERY_PARAM)
  return values.length === 1 && values[0] === DEMO_QUERY_VALUE
}

export const DEMO_ADDRESS = `${DEMO_PAGE_PATH}?${DEMO_QUERY_PARAM}=${DEMO_QUERY_VALUE}`
export const DEMO_FAMILY_ADDRESS = `${DEMO_PAGE_PATH}?${DEMO_QUERY_PARAM}=${DEMO_FAMILY_VALUE}`

/** The problem title the backend sends when the demo route is switched off. */
export function isDemoDisabledProblem(title: string | undefined): boolean {
  return title === DEMO_DISABLED_TITLE
}

/** The fictional sentence the demo analyses on load; it matches `example_text` in the backend response (a test compares them). */
export const DEMO_EXAMPLE_TEXT = "I feel more confident about saving this month, but I am still watching my expenses."

/** Fictional sentences for trying the abstention rules; every one is invented and none is a real person's words. */
export const DEMO_EXAMPLES: readonly { label: string; text: string }[] = [
  { label: "Confident about saving", text: DEMO_EXAMPLE_TEXT },
  { label: "Quoted words", text: 'My friend said "I hate my debt" yesterday.' },
  { label: "Third person", text: "My brother is terrified about his mortgage." },
  { label: "Hypothetical", text: "If I lost my job I would panic about my savings." },
  { label: "Past feeling", text: "Last year I was very stressed about my loan." },
  { label: "Unrelated", text: "The weather is lovely and the football was great." },
]

/** Why a `demo` parameter did not start a demonstration: this build does not allow it, or the value is not one this page knows (or it was repeated). */
export type DemoProblem = "not_allowed" | "unknown_value"

export interface DemoRequest {
  /** The demonstration to show, or null. */
  kind: DemoKind | null
  /** Set when the address carries a `demo` parameter that did NOT start a demonstration, so the page can say so instead of silently showing the normal page. */
  problem: DemoProblem | null
}

/** The full reading of the address: no `demo` parameter is the normal page (no problem); a parameter on a build that does not allow demo mode, or with an unknown or repeated value, is a PROBLEM the page announces. */
export function demoRequest(search: string, allowed: boolean): DemoRequest {
  const values = new URLSearchParams(search).getAll(DEMO_QUERY_PARAM)
  if (values.length === 0) return { kind: null, problem: null }
  if (!allowed) return { kind: null, problem: "not_allowed" }
  const kind = demoKind(search, allowed)
  return kind ? { kind, problem: null } : { kind: null, problem: "unknown_value" }
}

/** Keeps a demonstration while the user clicks the Financial Behaviour sidebar link from inside it: the link carries the current `demo` query only on that page and only for a demonstration this build allows. Everywhere else it is the plain path. */
export function behaviourLinkTarget(pathname: string, search: string, allowed: boolean): string {
  return pathname === DEMO_PAGE_PATH && demoKind(search, allowed) !== null ? `${DEMO_PAGE_PATH}${search}` : DEMO_PAGE_PATH
}

/** Where a sign-in goes. A person who was sent to the sign-in page FROM a protected address (for example `/financial-behaviour?demo=family`) goes back to exactly that address, whichever sign-in button they
 * press; only a person who opened the sign-in page directly gets the button's own default (the family demonstration opens the household section of the profile; the others open the dashboard). */
export function destinationAfterLogin(action: "signin" | "demo" | "family" | "pipeline", from: { pathname: string; search?: string } | undefined): string {
  if (from) return from.pathname + (from.search ?? "")
  return action === "family" ? "/profile?household=open" : "/dashboard"
}
