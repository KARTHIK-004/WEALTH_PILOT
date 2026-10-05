/**
 * RFC 7807 Problem Details — the shape `backend/wealthpilot/api/errors.py`
 * returns for every error response (`application/problem+json`).
 *
 * Not present in the generated `types/api.ts`: FastAPI's OpenAPI export
 * only documents a route's declared success `response_model` plus its
 * built-in 422 validation-error schema — it has no way to know about a
 * hand-raised domain exception's response shape, since that mapping lives
 * in `api/errors.py`'s exception handlers, not in a route's return type.
 * Hand-written here for exactly that reason (Phase 15 report section 5;
 * Phase 16 section 9: "only if the generated API types do not already
 * provide one").
 */
export interface ProblemDetails {
  type: string
  title: string
  status: number
  detail: string
  instance?: string
}

export function isProblemDetails(value: unknown): value is ProblemDetails {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    "title" in value &&
    "status" in value &&
    "detail" in value &&
    typeof (value as ProblemDetails).status === "number"
  )
}
