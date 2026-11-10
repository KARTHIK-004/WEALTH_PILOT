import type { components } from "@/types/api"

type SecurityStatus = components["schemas"]["SecurityStatusOut"]

/** Words for the states the backend reports. Display only: the page maps a returned value to a label and never decides the state. */
export const SECURITY_DESCRIPTION =
  "What is encrypted, what is not, and the result of the checks the backend ran just now. Nothing here is estimated by this page."

export const ENCRYPTION_LABELS: Record<SecurityStatus["encryption"]["status"], string> = {
  operational: "Operating",
  not_configured: "Not configured",
  failed: "Self-test failed",
}

export const LEDGER_LABELS: Record<SecurityStatus["ledger"]["verification"], string> = {
  valid: "Internally consistent",
  empty: "No events recorded yet",
  invalid: "Verification failed",
}

export const ANCHOR_LABELS: Record<SecurityStatus["external_anchor"]["state"], string> = {
  not_configured: "Not configured",
  unreachable: "Unreachable",
  available: "Available",
}
