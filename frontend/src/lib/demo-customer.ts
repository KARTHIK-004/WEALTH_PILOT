/**
 * Phase 24, extended by the Live Analysis Flow phase — resolves the demo
 * account's associated customer, using only real, already-existing
 * persistence APIs (`POST /api/profiles`, `POST`/`GET
 * /api/profiles/{id}/questionnaire`, `POST /api/profiles/{id}/goals`,
 * `GET /api/profiles/lookup`) — never a fabricated financial result, never
 * a second data layer.
 *
 * **Two demo identities, one resolution order.** `PRIMARY_DEMO_CUSTOMER_NAME`
 * ("WealthPilot Demo — Complete") is a real, FAR-Trans-linked persona the
 * backend seed script (`backend/scripts/seed_demo_data.py`) creates ahead
 * of time — its `risk_inputs.external_customer_id` linkage is set by one
 * direct database write that ONLY that script performs, because no public
 * schema exposes that field (see the seed script's own module docstring).
 * The frontend can never create this linkage itself, so it can only FIND
 * an already-seeded "Complete" persona, never fabricate one — attempting
 * to create a same-named substitute would silently produce a customer that
 * LOOKS complete but has no real transaction history behind it, which is
 * exactly the kind of misleading result this project never allows.
 * `DEMO_CUSTOMER_NAME` ("WealthPilot Demo Customer") is Phase 24's
 * original, always-creatable-from-scratch canonical customer (no FAR-Trans
 * linkage by design — the "no history available" case) and remains the
 * fallback when the "Complete" persona has not been seeded in this
 * environment, so a fresh, unseeded database keeps working exactly as
 * Phase 24 originally built it.
 *
 * `resolveDemoCustomer()` therefore: (1) looks up
 * "WealthPilot Demo — Complete" by exact name via `GET
 * /api/profiles/lookup` (Live Analysis Flow phase — see that endpoint's
 * own docstring for why a name-lookup was the smallest necessary API
 * addition, documented in full in
 * `reports/live_analysis_flow_fix_report.md`) and uses it whenever it is
 * seeded; (2) otherwise reuses a locally-remembered id if it still
 * resolves to either known demo name; (3) otherwise finds-or-creates the
 * Phase 24 canonical customer, exactly as before. Phase 31 reordered (1)
 * and (2): previously the remembered id came first, so a browser that had
 * ever resolved to the blank fallback customer kept landing on it even
 * after "Complete" was seeded. With "Complete" seeded, resolution is now
 * the same customer for every browser; only the unseeded fallback path
 * remains idempotent per browser (a disclosed Phase 24 limitation).
 */
import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type ProfileCreateRequest = components["schemas"]["ProfileCreateRequest"]
type GoalCreate = components["schemas"]["GoalCreate"]

export const DEMO_CUSTOMER_NAME = "WealthPilot Demo Customer"
export const PRIMARY_DEMO_CUSTOMER_NAME = "WealthPilot Demo — Complete"
/** The full-pipeline demo persona (WPDEMO-E, `seed_demo_data.py setup`): a seeded, FAR-Trans-linked customer with twelve reported months, so every page shows real results. */
export const FULL_PIPELINE_DEMO_NAME = "WealthPilot Demo — Full Pipeline"
/** The family demo's primary member (`seed_demo_data.py setup-family`): an
 * existing seeded persona who is the primary of "WealthPilot Demo Family". */
export const FAMILY_DEMO_PRIMARY_NAME = "WealthPilot Demo — Savings"

const STORAGE_KEY = "wealthpilot-demo-customer-id"
const FAMILY_STORAGE_KEY = "wealthpilot-family-demo-customer-id"

/** A plausible, clearly-labeled demo profile — every field is a real
 * `ProfileCreateRequest` field; `customer_type`/`investment_capacity` use
 * the same real, evidenced FAR-Trans category values
 * `create-user-page.tsx` already offers (see that file's own docstring
 * for the `reports/phase2_data_quality_report.md` citation) — nothing
 * invented. No `goals` embedded here: the demo customer is created the
 * same way the real Create User flow creates one, then enriched via the
 * separate Phase 23 goal endpoint, mirroring real onboarding rather than
 * a shortcut. */
const DEMO_PROFILE: ProfileCreateRequest = {
  name: DEMO_CUSTOMER_NAME,
  age: 31,
  income: 960000,
  employment_status: "Full-time",
  customer_type: "Mass",
  investment_capacity: "CAP_GT300K",
}

/** A small, realistic demo goal set — every field is a real `GoalCreate`
 * field, nothing invented (no inflation/contribution field exists on this
 * schema; see `create-user-page.tsx`/`onboarding-goals-page.tsx`). Two
 * goals are enough to demonstrate the Goals page and feed the analysis
 * pipeline without over-populating the demo profile. */
const DEMO_GOALS: GoalCreate[] = [
  { goal_type: "Home Down Payment", target_amount: 1000000, target_date: "2031-06-01", current_savings: 150000, priority: 1 },
  { goal_type: "Retirement Corpus", target_amount: 9000000, target_date: "2057-01-01", current_savings: 120000, priority: 2 },
]

function readStoredDemoCustomerId(): number | null {
  if (typeof window === "undefined") return null
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function storeDemoCustomerId(id: number): void {
  window.localStorage.setItem(STORAGE_KEY, String(id))
}

/** True iff `profileId` is the locally-remembered demo customer id — a
 * lightweight, synchronous, best-effort check for UI display only (the
 * "Demo Account" header indicator, section 13); never used as a security
 * or data-isolation boundary, which the backend already enforces on its
 * own by customer id regardless of this label. */
export function isDemoCustomerId(profileId: number | null): boolean {
  if (profileId === null) return false
  return readStoredDemoCustomerId() === profileId || isFamilyDemoCustomerId(profileId)
}

/** True iff `profileId` is the family demo's primary member as last resolved
 * by the Family Demo login -- a display label only (the header's "Family
 * Demo" badge), never an authorization or data-isolation boundary. */
export function isFamilyDemoCustomerId(profileId: number | null): boolean {
  if (profileId === null || typeof window === "undefined") return false
  return window.localStorage.getItem(FAMILY_STORAGE_KEY) === String(profileId)
}

async function findExistingDemoCustomerId(): Promise<number | null> {
  const stored = readStoredDemoCustomerId()
  if (stored === null) return null
  try {
    const profile = await api.getProfile(stored)
    return profile.name === PRIMARY_DEMO_CUSTOMER_NAME || profile.name === DEMO_CUSTOMER_NAME ? stored : null
  } catch {
    return null
  }
}

/** Looks up the already-seeded "Complete" persona by exact name — never
 * creates one (see the module docstring for why creating a substitute
 * would be misleading). Returns `null` when this environment's database
 * has not been seeded with it yet (e.g. a fresh/unseeded environment), in
 * which case `resolveDemoCustomer` falls back to the Phase 24 canonical
 * customer unchanged. */
async function findPrimaryDemoCustomerId(): Promise<number | null> {
  const { customer_id } = await api.lookupProfileByName(PRIMARY_DEMO_CUSTOMER_NAME)
  return customer_id
}

/** Submits demo questionnaire answers ONLY if this customer has none yet
 * (checked via a real `GET` first) — `POST
 * /api/profiles/{id}/questionnaire` is a per-question upsert, so this
 * guard exists to keep the answers a stable, predictable demo set rather
 * than re-submitting identical values on every login (harmless, but
 * pointless network traffic). Every question/option is read live from
 * `GET /api/questionnaire` -- nothing hard-coded. The selected option per
 * question is a fixed, position-based choice (the middle option, or the
 * first of two) purely to pick SOME real, valid answer for demo purposes
 * -- this reads nothing from and writes nothing to any risk score; it is
 * not an inference of any kind. */
async function populateDemoQuestionnaire(customerId: number): Promise<void> {
  const existing = await api.getQuestionnaireAnswers(customerId)
  if (existing.answers.length > 0) return

  const questionnaire = await api.getQuestionnaire()
  const answers = questionnaire.sections.flatMap((section) =>
    section.questions.map((question) => ({
      question_number: question.number,
      option_key: question.options[Math.floor((question.options.length - 1) / 2)].key,
    })),
  )
  if (answers.length > 0) {
    await api.submitQuestionnaireAnswers(customerId, { answers })
  }
}

/** Creates the demo goal set ONLY if this customer has none yet (checked
 * via a real `GET` first). Unlike questionnaire answers, `POST
 * /api/profiles/{id}/goals` has no upsert semantics -- every call creates
 * a new row -- so this guard is what keeps repeated "Use Demo Account"
 * logins from accumulating duplicate goals. */
async function populateDemoGoals(customerId: number): Promise<void> {
  const profile = await api.getProfile(customerId)
  if (profile.goals.length > 0) return

  for (const goal of DEMO_GOALS) {
    await api.createGoal(customerId, goal)
  }
}

/** Resolves this browser's demo customer id -- preferring the real,
 * FAR-Trans-linked "Complete" persona when this environment has it seeded,
 * falling back to finding-or-creating the Phase 24 canonical customer
 * otherwise (see the module docstring for the full resolution order) --
 * and reusing whichever one was resolved on every subsequent call. Called
 * from `components/login-form.tsx`'s `completeLogin` -- both "Sign In" and
 * "Use Demo Account" resolve through this same function (UX fix,
 * post-Phase-25: there is only one supported prototype account, so both
 * paths must reach the same associated customer; see
 * `reports/post_login_profile_flow_report.md`). */
export async function resolveDemoCustomer(): Promise<number> {
  // Phase 31: the seeded "Complete" persona wins whenever it exists, even if
  // this browser remembered the blank fallback customer from an earlier
  // login (before this, a remembered fallback id was reused forever, so a
  // browser that had ever resolved to "WealthPilot Demo Customer" could
  // never reach the approved demo). The remembered id is now used only when
  // the "Complete" persona is not seeded in this environment.
  let customerId = await findPrimaryDemoCustomerId()

  if (customerId === null) {
    customerId = await findExistingDemoCustomerId()
  }
  if (customerId === null) {
    const created = await api.createProfile(DEMO_PROFILE)
    customerId = created.customer_id
  }
  storeDemoCustomerId(customerId)

  await populateDemoQuestionnaire(customerId)
  await populateDemoGoals(customerId)
  return customerId
}

/** Thrown when this environment has not been seeded with the full-pipeline demo persona. */
export class FullPipelineDemoNotSeededError extends Error {
  constructor() {
    super("The full-pipeline demo persona has not been set up in this environment.")
    this.name = "FullPipelineDemoNotSeededError"
  }
}

/**
 * Resolves the FULL-PIPELINE demo: the seeded persona "WealthPilot Demo — Full Pipeline", found by exact name (`GET /api/profiles/lookup`). Find-only, like the family demo: the
 * frontend never creates this customer, because its FAR-Trans link (the risk model's only input) can only be set by the seed script (`seed_demo_data.py`); a same-named customer
 * made here would look complete and have no history behind it. An unseeded environment gets a clear error instead. It is a login entry point, not a switcher (ADR-021): exactly
 * one customer is active for the session, and nothing is stored in the browser beyond the usual active profile.
 */
export async function resolveFullPipelineDemoCustomer(): Promise<number> {
  const { customer_id } = await api.lookupProfileByName(FULL_PIPELINE_DEMO_NAME)
  if (customer_id === null) throw new FullPipelineDemoNotSeededError()
  return customer_id
}

/** Thrown when this environment has not been seeded with the family demo. */
export class FamilyDemoNotSeededError extends Error {
  constructor() {
    super("The family demo household has not been set up in this environment.")
    this.name = "FamilyDemoNotSeededError"
  }
}

/**
 * Resolves the FAMILY demo: the primary member of the canonical "WealthPilot
 * Demo Family" household, found by exact name through the same `GET
 * /api/profiles/lookup` the individual demo uses (never a hard-coded id).
 *
 * Find-only, exactly like the "Complete" persona above: the family is built by
 * `seed_demo_data.py setup-family` through the real household API, so the
 * frontend never creates a customer, a household or a record here -- an
 * unseeded environment gets a clear error instead of a fabricated family.
 *
 * Like every login, this resolves exactly ONE associated customer for the
 * session (ADR-021); the family demo is a second login entry point, not an
 * in-app customer switcher (ADR-036). The household view that follows shows
 * other members' identity and membership only -- never their individual
 * profile, analysis or financial data (Rule 31).
 */
export async function resolveFamilyDemoCustomer(): Promise<number> {
  const { customer_id } = await api.lookupProfileByName(FAMILY_DEMO_PRIMARY_NAME)
  if (customer_id === null) throw new FamilyDemoNotSeededError()
  const household = await api.getProfileHousehold(customer_id)
  if (household.household === null) throw new FamilyDemoNotSeededError()
  window.localStorage.setItem(FAMILY_STORAGE_KEY, String(customer_id))
  return customer_id
}
