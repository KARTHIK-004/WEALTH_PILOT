/**
 * Centralized, typed API client — the ONLY place in this app that calls
 * `fetch()` against the WealthPilot backend (CLAUDE.md rule 3 in spirit:
 * "TypeScript types are generated, never written" applies here too —
 * every request/response type below is imported from the generated
 * `types/api.ts`, never hand-duplicated).
 *
 * Base URL comes from `VITE_API_BASE_URL` (Vite exposes only
 * `VITE_`-prefixed env vars to client code — see `.env.example`), never
 * hard-coded, and never a secret (a base URL is public configuration,
 * not a credential).
 *
 * Every non-2xx response is parsed as an RFC 7807 problem+json body
 * (`backend/wealthpilot/api/errors.py`) and thrown as an `ApiClientError`
 * — components read `error.problem.title`/`.detail` for a safe, user-
 * facing message, never a stack trace (Phase 15's own contract: no
 * stack trace/secret ever appears in a problem body to begin with).
 */
import type { components } from "@/types/api"
import { isProblemDetails, type ProblemDetails } from "@/types/problem-details"

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000"

export class ApiClientError extends Error {
  problem: ProblemDetails

  constructor(problem: ProblemDetails) {
    super(problem.detail)
    this.name = "ApiClientError"
    this.problem = problem
  }
}

/** Thrown when the backend cannot be reached at all (network failure,
 * server down) — distinct from `ApiClientError`, which means the backend
 * DID respond, just with an error. Components use this distinction to
 * show "service unavailable" vs a specific validation/not-found message. */
export class ApiUnreachableError extends Error {
  constructor(cause: unknown) {
    super("The WealthPilot API could not be reached.")
    this.name = "ApiUnreachableError"
    this.cause = cause
  }
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    })
  } catch (cause) {
    throw new ApiUnreachableError(cause)
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    if (isProblemDetails(body)) {
      throw new ApiClientError(body)
    }
    throw new ApiClientError({
      type: "about:blank",
      title: "Request failed",
      status: response.status,
      detail: `The API returned an unexpected ${response.status} response.`,
    })
  }

  if (response.status === 204) {
    return undefined as TResponse
  }
  return (await response.json()) as TResponse
}

type Schemas = components["schemas"]

/** Phase 32: every household route needs the caller's associated customer
 * (the single `useCustomer().profileId`) in `X-Customer-Id` -- the backend
 * authorizes against household membership using it. The prototype has no
 * server session, so this is an asserted identity (docs/SECURITY.md). */
const asCustomer = (actingCustomerId: number): Record<string, string> => ({
  "X-Customer-Id": String(actingCustomerId),
})

export const api = {
  getHealth: () => request<Schemas["HealthResponse"]>("/api/health"),

  getQuestionnaire: () => request<Schemas["QuestionnaireResponse"]>("/api/questionnaire"),

  createProfile: (body: Schemas["ProfileCreateRequest"]) =>
    request<Schemas["ProfileCreateResponse"]>("/api/profiles", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getProfile: (profileId: number) =>
    request<Schemas["ProfileResponse"]>(`/api/profiles/${profileId}`),

  lookupProfileByName: (name: string) =>
    request<Schemas["ProfileLookupResponse"]>(`/api/profiles/lookup?${new URLSearchParams({ name })}`),

  getFinancialInputs: (profileId: number) =>
    request<Schemas["FinancialInputsResponse"]>(`/api/profiles/${profileId}/financial-inputs`),

  updateFinancialInputs: (profileId: number, body: Schemas["FinancialInputsUpdate"]) =>
    request<Schemas["FinancialInputsResponse"]>(`/api/profiles/${profileId}/financial-inputs`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getQuestionnaireAnswers: (profileId: number) =>
    request<Schemas["QuestionnaireAnswersResponse"]>(`/api/profiles/${profileId}/questionnaire`),

  submitQuestionnaireAnswers: (profileId: number, body: Schemas["QuestionnaireAnswersSubmitRequest"]) =>
    request<Schemas["QuestionnaireAnswersResponse"]>(`/api/profiles/${profileId}/questionnaire`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createGoal: (profileId: number, body: Schemas["GoalCreate"]) =>
    request<Schemas["GoalOut"]>(`/api/profiles/${profileId}/goals`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getProfileHousehold: (profileId: number) =>
    request<Schemas["ProfileHouseholdResponse"]>(`/api/profiles/${profileId}/household`, {
      headers: asCustomer(profileId),
    }),

  createHousehold: (actingCustomerId: number, body: Schemas["HouseholdCreateRequest"]) =>
    request<Schemas["HouseholdOut"]>("/api/households", {
      method: "POST",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  getHouseholdMembers: (householdId: number, actingCustomerId: number) =>
    request<Schemas["HouseholdMembersResponse"]>(`/api/households/${householdId}/members`, {
      headers: asCustomer(actingCustomerId),
    }),

  addHouseholdMember: (householdId: number, actingCustomerId: number, body: Schemas["HouseholdMemberCreateRequest"]) =>
    request<Schemas["HouseholdMemberOut"]>(`/api/households/${householdId}/members`, {
      method: "POST",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  removeHouseholdMember: (householdId: number, actingCustomerId: number, memberId: number) =>
    request<void>(`/api/households/${householdId}/members/${memberId}`, {
      method: "DELETE",
      headers: asCustomer(actingCustomerId),
    }),

  // Phase 33 -- household financial data (income, expenses, assets,
  // liabilities). Every call carries the same `X-Customer-Id` identity the
  // Phase 32 household routes use; the backend authorizes against household
  // membership (any member may read, only the primary may mutate). Nothing
  // here aggregates anything -- these return the stored records as they are.

  // Phase 36 -- household goals: stored facts only (name, type, target amount
  // and date, current savings, notes, active). Same `X-Customer-Id` identity and
  // membership authorization as the other household routes; nothing here
  // derives a projection, contribution or feasibility.

  listHouseholdGoals: (householdId: number, actingCustomerId: number) =>
    request<Schemas["HouseholdGoalResponse"][]>(`/api/households/${householdId}/goals`, {
      headers: asCustomer(actingCustomerId),
    }),

  createHouseholdGoal: (householdId: number, actingCustomerId: number, body: Schemas["HouseholdGoalCreate"]) =>
    request<Schemas["HouseholdGoalResponse"]>(`/api/households/${householdId}/goals`, {
      method: "POST",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  updateHouseholdGoal: (householdId: number, actingCustomerId: number, goalId: number, body: Schemas["HouseholdGoalUpdate"]) =>
    request<Schemas["HouseholdGoalResponse"]>(`/api/households/${householdId}/goals/${goalId}`, {
      method: "PUT",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  deleteHouseholdGoal: (householdId: number, actingCustomerId: number, goalId: number) =>
    request<void>(`/api/households/${householdId}/goals/${goalId}`, {
      method: "DELETE",
      headers: asCustomer(actingCustomerId),
    }),

  // Phase 34 -- the household's read-only financial summary. Every figure in
  // the response is already computed by the backend; nothing derived from it
  // is ever recalculated in the frontend.

  getHouseholdFinancialSummary: (householdId: number, actingCustomerId: number) =>
    request<Schemas["HouseholdFinancialSummaryResponse"]>(`/api/households/${householdId}/financial-summary`, {
      headers: asCustomer(actingCustomerId),
    }),

  listHouseholdIncome: (householdId: number, actingCustomerId: number) =>
    request<Schemas["HouseholdIncomeResponse"][]>(`/api/households/${householdId}/income`, {
      headers: asCustomer(actingCustomerId),
    }),

  createHouseholdIncome: (householdId: number, actingCustomerId: number, body: Schemas["HouseholdIncomeCreate"]) =>
    request<Schemas["HouseholdIncomeResponse"]>(`/api/households/${householdId}/income`, {
      method: "POST",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  updateHouseholdIncome: (householdId: number, actingCustomerId: number, incomeId: number, body: Schemas["HouseholdIncomeUpdate"]) =>
    request<Schemas["HouseholdIncomeResponse"]>(`/api/households/${householdId}/income/${incomeId}`, {
      method: "PUT",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  deleteHouseholdIncome: (householdId: number, actingCustomerId: number, incomeId: number) =>
    request<void>(`/api/households/${householdId}/income/${incomeId}`, {
      method: "DELETE",
      headers: asCustomer(actingCustomerId),
    }),

  listHouseholdExpenses: (householdId: number, actingCustomerId: number) =>
    request<Schemas["HouseholdExpenseResponse"][]>(`/api/households/${householdId}/expenses`, {
      headers: asCustomer(actingCustomerId),
    }),

  createHouseholdExpense: (householdId: number, actingCustomerId: number, body: Schemas["HouseholdExpenseCreate"]) =>
    request<Schemas["HouseholdExpenseResponse"]>(`/api/households/${householdId}/expenses`, {
      method: "POST",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  updateHouseholdExpense: (householdId: number, actingCustomerId: number, expenseId: number, body: Schemas["HouseholdExpenseUpdate"]) =>
    request<Schemas["HouseholdExpenseResponse"]>(`/api/households/${householdId}/expenses/${expenseId}`, {
      method: "PUT",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  deleteHouseholdExpense: (householdId: number, actingCustomerId: number, expenseId: number) =>
    request<void>(`/api/households/${householdId}/expenses/${expenseId}`, {
      method: "DELETE",
      headers: asCustomer(actingCustomerId),
    }),

  listHouseholdAssets: (householdId: number, actingCustomerId: number) =>
    request<Schemas["HouseholdAssetResponse"][]>(`/api/households/${householdId}/assets`, {
      headers: asCustomer(actingCustomerId),
    }),

  createHouseholdAsset: (householdId: number, actingCustomerId: number, body: Schemas["HouseholdAssetCreate"]) =>
    request<Schemas["HouseholdAssetResponse"]>(`/api/households/${householdId}/assets`, {
      method: "POST",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  updateHouseholdAsset: (householdId: number, actingCustomerId: number, assetId: number, body: Schemas["HouseholdAssetUpdate"]) =>
    request<Schemas["HouseholdAssetResponse"]>(`/api/households/${householdId}/assets/${assetId}`, {
      method: "PUT",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  deleteHouseholdAsset: (householdId: number, actingCustomerId: number, assetId: number) =>
    request<void>(`/api/households/${householdId}/assets/${assetId}`, {
      method: "DELETE",
      headers: asCustomer(actingCustomerId),
    }),

  listHouseholdLiabilities: (householdId: number, actingCustomerId: number) =>
    request<Schemas["HouseholdLiabilityResponse"][]>(`/api/households/${householdId}/liabilities`, {
      headers: asCustomer(actingCustomerId),
    }),

  createHouseholdLiability: (householdId: number, actingCustomerId: number, body: Schemas["HouseholdLiabilityCreate"]) =>
    request<Schemas["HouseholdLiabilityResponse"]>(`/api/households/${householdId}/liabilities`, {
      method: "POST",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  updateHouseholdLiability: (householdId: number, actingCustomerId: number, liabilityId: number, body: Schemas["HouseholdLiabilityUpdate"]) =>
    request<Schemas["HouseholdLiabilityResponse"]>(`/api/households/${householdId}/liabilities/${liabilityId}`, {
      method: "PUT",
      headers: asCustomer(actingCustomerId),
      body: JSON.stringify(body),
    }),

  deleteHouseholdLiability: (householdId: number, actingCustomerId: number, liabilityId: number) =>
    request<void>(`/api/households/${householdId}/liabilities/${liabilityId}`, {
      method: "DELETE",
      headers: asCustomer(actingCustomerId),
    }),

  runAnalysis: (body: Schemas["AnalysisRequest"]) =>
    request<Schemas["AnalysisResult"]>("/api/analysis", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getAnalysis: (analysisId: number) =>
    request<Schemas["AnalysisResult"]>(`/api/analysis/${analysisId}`),

  compareScenarios: (body: Schemas["ScenarioCompareRequest"]) =>
    request<Schemas["ScenarioCompareResponse"]>("/api/scenarios/compare", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  askQuestion: (body: Schemas["QARequest"]) =>
    request<Schemas["QAResponse"]>("/api/qa", {
      method: "POST",
      body: JSON.stringify(body),
    }),
}

export function analysisStreamUrl(profileId: number, portfolioStrategy?: string): string {
  const params = new URLSearchParams({ profile_id: String(profileId) })
  if (portfolioStrategy) params.set("portfolio_strategy", portfolioStrategy)
  return `${API_BASE_URL}/api/analysis/stream?${params.toString()}`
}
