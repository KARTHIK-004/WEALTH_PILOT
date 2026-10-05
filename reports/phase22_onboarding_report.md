# Phase 22 — Questionnaire + Goals Onboarding

## 1. Phase Objective

Extend the onboarding experience so a user can create a profile (Phase
21), see the real MiFID-II questionnaire, add planned financial goals, and
continue to the Dashboard — using only existing backend contracts. No new
backend endpoint, database field, scoring formula, or financial
calculation was added anywhere.

## 2. Existing Architecture Inspected

Before writing any code: `backend/wealthpilot/api/schemas.py` (full file),
every router in `backend/wealthpilot/api/routers/` plus `api/sse.py` (a
fresh `@router.(get|post)` grep across all of them, not assumed from an
earlier phase's memory), `backend/wealthpilot/db/models.py`'s `Customer`/
`FinancialGoal` tables, `backend/wealthpilot/api/services/
questionnaire_service.py` (the actual questionnaire parser), the generated
`frontend/src/types/api.ts`, `frontend/src/lib/api-client.ts`,
`frontend/src/providers/{auth-context,customer-context}.tsx`,
`frontend/src/pages/{create-user-page,goals-page,profile-page}.tsx`,
`frontend/src/App.tsx`, and `frontend/src/components/ui/*` (to see what
already existed before adding anything).

## 3. Questionnaire API Contract Used

`GET /api/questionnaire` → `QuestionnaireResponse { sections:
QuestionnaireSection[] }`, `QuestionnaireSection { name, questions:
Question[] }`, `Question { number, text, options: QuestionOption[] }`,
`QuestionOption { key, text }` — read directly from `schemas.py` and
cross-checked against `types/api.ts` (identical, as expected for a
generated file). **No field on any of these marks a question "required."**
Live-verified this phase against a running backend: 5 sections, 25
questions total, e.g. question 1 = "What age group do you belong to?"
with options a-e — real data, not assumed. `frontend/src/hooks/
use-questionnaire.ts` (new) wraps this in a `useQuery`, matching every
other read hook's pattern (`use-profile.ts`, `use-analysis.ts`).
`onboarding-questionnaire-page.tsx` renders every section/question/option
directly from this response — nothing is hard-coded.

## 4. Whether Questionnaire Persistence Existed

**No.** A fresh grep of every router file this phase (`analysis.py`,
`health.py`, `profiles.py`, `qa.py`, `scenarios.py`, `sse.py`) found
exactly the same 9 routes established since Phase 15 — no
questionnaire-answer write endpoint of any kind. Per this phase's own
explicit instruction for this outcome, no backend endpoint was created, no
database change was made, and no persistence was invented. The
questionnaire page keeps answers in local `useState` only and displays a
permanent, prominent `Alert` stating plainly that answers are not saved
and that risk category is determined separately by the real risk model —
**never** a "Saved successfully" message, since no save operation exists.

## 5. Goal API/Schema Used

`GoalCreate { goal_type: str (1-100 chars), target_amount: float (>0),
target_date: date, current_savings: float (default 0, ≥0), priority: int
(default 1, ≥1) }` — read directly from `schemas.py` and cross-checked
against `db/models.py`'s `financial_goals` table (identical columns, no
`inflation`/`contribution` field in either). No field was invented; none
of `inflation`, `contribution`, `future value`, or similar (mentioned only
as "possible" fields in the phase brief) exist in the real schema, so none
were added to the form.

**Critical finding, investigated and documented rather than worked
around**: the *only* way this schema's `goals` list can be written is as
part of the *same* `POST /api/profiles` call that creates the customer —
there is no `PATCH`/`POST` endpoint to attach a goal to an *already
existing* customer. This was directly, empirically confirmed this phase
(§17): a temporary profile created *with* an embedded goal correctly
persisted it (`GET` echoed it back exactly); a temporary profile created
*without* one (matching Phase 21's actual `Create User` behavior) came back
with `"goals": []`, with no other endpoint available to add one afterward.

Section 18 of this phase's own brief pins the intended order as "Create
User [already submitted] → Questionnaire" — i.e., by design, the profile
already exists by the time a user reaches the goals step, which is exactly
the case with no available write path. Per this phase's explicit
instruction ("If you discover that a requested onboarding operation cannot
be performed because the backend has no corresponding API, STOP that
specific operation and document the limitation. Do NOT expand the phase
into backend development"), `onboarding-goals-page.tsx` lets a user build
a **local, unsaved** planning list (add/remove goals client-side, fields
and constraints matching `GoalCreate` exactly) behind a permanent, prominent
`Alert` stating plainly that these are not persisted — never a fabricated
success state, and no second `POST /api/profiles` call (which would only
create a confusing duplicate customer, not attach a goal to the existing
one).

## 6. Routes Added/Modified

**Added** (both inside `ProtectedRoute`, both outside `AppShell` — same
standalone, no-sidebar treatment as `/login`/`/create-user`):
- `/onboarding/questionnaire` → `OnboardingQuestionnairePage`
- `/onboarding/goals` → `OnboardingGoalsPage`

**Modified**: `App.tsx` (route registration only — every existing route's
path/nesting is byte-for-byte unchanged); `create-user-page.tsx` (exactly
one behavioral line: `handleContinue` now navigates to
`/onboarding/questionnaire` instead of `/`, plus one added `<OnboardingSteps
current="profile" />` line — the "small routing/link change" this phase's
own brief explicitly authorized, not a redesign).

No existing route (`/`, `/profile`, `/risk-assessment`,
`/financial-health`, `/goals`, `/portfolio`, `/recommendation`,
`/why-this-recommendation`, `/agent-activity`, `/scenarios`, `/login`,
`/create-user`) was renamed, removed, or had its element changed.

## 7. Components Added/Modified

**Added**:
- `frontend/src/pages/onboarding-questionnaire-page.tsx`
- `frontend/src/pages/onboarding-goals-page.tsx`
- `frontend/src/components/shell/onboarding-steps.tsx` — a small, static
  4-step indicator ("1. Create Profile → 2. Questionnaire → 3. Goals →
  4. Dashboard"), not a wizard framework, shared by `create-user-page.tsx`
  and the two new pages.
- `frontend/src/components/shell/onboarding-no-profile.tsx` — the
  onboarding-page equivalent of the existing `no-profile-selected.tsx`
  (that component's "select a profile from the header" copy assumes the
  `AppShell` header is visible, which it never is here).
- `frontend/src/components/ui/radio-group.tsx` — added via `npx
  shadcn@latest add radio-group` (dry-run confirmed first: one new file,
  no overwrite, `cn` dependency already present) — the correct primitive
  for the questionnaire's single-select MiFID-II options; no other UI
  library was introduced.
- `frontend/src/hooks/use-questionnaire.ts`

**Modified**: `App.tsx`, `create-user-page.tsx` (both described in §6).

**Not duplicated**: `pages/goals-page.tsx` (`/goals`, Phase 17 — displays
`AnalysisResult.goals[]`, Phase 7's Monte Carlo output for an already-run
analysis) and `pages/profile-page.tsx` (`/profile` — displays a customer's
already-persisted `financial_goals` rows) were inspected and left
untouched; the new onboarding goals page is a data-entry form, a
third, genuinely distinct concern from both.

## 8. Active Customer/Profile Handling

Both new pages read `useCustomer().profileId` (Phase 17's unmodified
context) and render `OnboardingNoProfile` — with links back to `/create-
user` and `/login`, never a silently-substituted different customer —
whenever it is `null`. No customer id is ever hard-coded, generated, or
assumed to be `1`. `create-user-page.tsx`'s `handleContinue` still sets
the active profile from the real `POST /api/profiles` response
(`mutation.data.customer_id`) before navigating onward, exactly as in
Phase 21 — unchanged.

## 9. Onboarding Flow

`Create User → Questionnaire → Goals → Dashboard`, with the same
`OnboardingSteps` indicator visible on all three onboarding-adjacent pages
so the user can see where they are. From `/login`, a Demo Account session
(which already has whatever profile `customer-context.tsx` last held) can
also reach `/onboarding/questionnaire` and `/onboarding/goals` directly —
consistent with section 6's "the currently created **or selected** active
profile" wording.

## 10. API Calls Used

- `GET /api/questionnaire` (new use in this phase, via `use-questionnaire.ts`)
- `POST /api/profiles` (Phase 21, unchanged — still the only mutation
  `create-user-page.tsx` calls)
- **No other API call was added.** Neither onboarding page calls
  `POST /api/analysis` or anything else automatically; confirmed by
  grepping both new page files for `runAnalysis`/`api.` calls — only
  `useQuestionnaireQuery` (a read) appears, and `onboarding-goals-page.tsx`
  makes no API call at all (§5).

## 11. Validation Behavior

**Questionnaire**: no validation is enforced (no question is marked
"required" by the schema, and there is no submission to block — see §4).

**Goals** (client-side only, mirroring `GoalCreate`'s own real Pydantic
constraints, not invented rules): goal name required (non-empty), target
amount required and `> 0`, target date required, current savings `≥ 0`
(default 0 if left blank), priority a whole number `≥ 1` (default 1). A
failed check shows an inline `Alert` with a specific message ("Target
amount must be greater than 0.", etc.) and does not add the goal to the
local list; no backend round-trip occurs for this validation since no
write endpoint exists to validate against.

## 12. Accessibility Checks

- Real heading hierarchy: each page has exactly one `<h1>` ("Risk &
  Investment Questionnaire" / "Your Financial Goals").
- Every questionnaire question is a `<fieldset>`/`<legend>` grouping a
  `RadioGroup`, with each option's `RadioGroupItem` paired to a `Label`
  via `htmlFor`/`id` — no `<div>` standing in for an interactive control.
- Every goal-form input has a real `FieldLabel`/`htmlFor` pair (the same
  `Field` primitives Phase 20/21 already established).
- Both permanent "not saved" notices use `Alert`/`AlertTitle`/
  `AlertDescription` — text-based, not color-only.
- Validation errors on the goals form render as text inside an `Alert`,
  not a color-only border change.
- `LoadingState` (reused unmodified from Phase 17) carries `role="status"
  aria-live="polite"` — satisfies the `aria-live` requirement for free.
- `ErrorState` (reused unmodified) surfaces RFC 7807 `title`/`detail`
  only, never a stack trace.
- Every button has a real, descriptive accessible name ("Continue to
  Goals", "Add goal", `aria-label={`Remove ${goal_type}`}` on the icon-only
  remove button).

No headless-browser tool is available in this environment — the above is
a source-level review, not a rendered/assistive-technology verification
(see §17's honest "Not verified" note).

## 13. Responsive Design Approach

Both new pages use the same `max-w-2xl` centered, `p-6 md:p-10`-padded,
single-column layout `create-user-page.tsx` already established, with the
`Field` `orientation="responsive"` variant (Phase 20's `field.tsx`,
unmodified) stacking the amount/date and savings/priority pairs on narrow
screens. This is a structural review only, not a rendered check.

## 14. Financial-Calculation Audit

A targeted grep of every Phase 22 file for `Math.`, `toFixed`, `sharpe`,
`volatility`, `monte carlo`, `feasibility`, `compound`, `annuity`,
inflation-rate patterns, and `expected return` found **zero** matches
outside doc comments explicitly stating these are *not* computed. The
only numeric handling anywhere in this phase's code is parsing raw
form-input strings into the exact numbers the (real, unmodified)
`GoalCreate` schema expects (`Number(targetAmount)`, etc.) — not a
calculation of a new value. `formatCurrency`/`formatDate` (Phase 17's
existing, unmodified formatters) are used to display the user's own
entered figures, exactly the "format an already-known value" use section
10 explicitly permits.

## 15. Mock-Data Audit

No mock/fake/sample/demo customer, goal, or questionnaire answer was
created anywhere. `useQuestionnaireQuery` only ever renders the real
`GET /api/questionnaire` response. The goals list is explicitly,
prominently labeled as local/unsaved (§4/§5) rather than disguised as a
successful submission. `create-user-page.tsx`'s existing, unmodified
`POST /api/profiles` call is still the only place any profile data is
ever actually sent to the backend.

## 16. Backend/Database Change Audit

**Zero.** Confirmed via an mtime check across the entire `backend/`,
`models/`, `datasets/`, and `config/` trees against the Phase 21 report's
own timestamp — no file in any of them is newer. No migration was created
or run. No `financial_goals`/`customers` column was added.

## 17. Live API Verification

Performed against a freshly started local backend (port 8032):

1. `POST /api/profiles` (`{"name": "Phase 22 E2E Test Profile", "age": 40,
   "income": 55000}`, no goals — matching `create-user-page.tsx`'s actual
   payload shape) → `{"customer_id": 29092}`.
2. `GET /api/questionnaire` → 200, 5 sections, 25 questions, real MiFID-II
   text confirmed (question 1: "What age group do you belong to?").
3. Questionnaire submission: **not applicable** — no write endpoint exists
   (§4), so this step was skipped rather than faked, per this phase's own
   instruction.
4. A **second** temporary profile was created *with* an embedded goal
   (`POST /api/profiles` with `goals: [{"goal_type": "Retirement",
   "target_amount": 250000, "target_date": "2045-01-01",
   "current_savings": 5000, "priority": 1}]`) → `{"customer_id": 29093}` —
   this is the direct, empirical test of §5's central finding.
5. `GET /api/profiles/29093` → the goal came back exactly as submitted
   (`id: 1, goal_type: "Retirement", target_amount: 250000.0, ...`).
   `GET /api/profiles/29092` → `"goals": []`, confirming a profile created
   the way `create-user-page.tsx` actually creates one (no goals field)
   has no way to gain a goal afterward through any endpoint this API
   exposes.
6. Data matched submitted values exactly in both cases (§17.5).
7. Both temporary customers and the one goal row were deleted directly
   from the database after verification.
8. Confirmed via a follow-up count query: **0** rows remain for either
   `customer_id` and **0** `financial_goals` rows remain for either id.

## 18. Cleanup Verification

`DELETE FROM financial_goals WHERE customer_id IN (29092, 29093)` (1 row)
then `DELETE FROM customers WHERE id IN (29092, 29093)` (2 rows), followed
by a `SELECT count(*)` on both tables scoped to those ids — both returned
**0**. No pre-existing data was touched (both ids were freshly assigned by
the database during this verification run). The backend server process
was stopped afterward.

## 19. TypeScript Verification

`npx tsc -b` — **0 errors**, re-run after every file change this phase
(including a `RadioGroup`/`Select`-style `onValueChange` type fix pattern
already established in Phase 21).

## 20. Build Verification

`npx vite build` — succeeds. Output grew from 930.65 kB (Phase 21) to
952.60 kB (gzip 292.64 kB) for the two new onboarding pages plus the
`radio-group` primitive — still a single JS chunk (the pre-existing,
previously-documented no-code-splitting finding, unchanged in kind).

## 21. Lint Verification

`npx oxlint` — **0 errors**, 8 warnings — identical set to Phase 21 (all
pre-existing `only-export-components`/`set-state-in-effect` advisories on
files this phase did not introduce that pattern in; no new warning was
introduced).

## 22. Backend Regression Test Result

Full `pytest` suite run this phase: **697 passed, 3 skipped, 0 failed**
(607.22s). Matches the established baseline exactly — no investigation of
a discrepancy was needed this time. No backend file was modified this
phase (§16), so no behavior change was possible or found.

## 23. Known Limitations

- **Questionnaire answers are not persisted anywhere** — no backend
  endpoint exists to save them. This is disclosed directly to the user in
  a permanent on-page `Alert`, not buried only in this report.
- **Goals entered during onboarding are not persisted** for a profile that
  already exists by the time the goals step runs — the only real write
  path (`POST /api/profiles`'s embedded `goals` field) only applies at
  customer-creation time, which this phase's own specified flow order
  (`Create User` submits first, `Questionnaire`/`Goals` come after) has
  already passed by the time a user reaches this step. Also disclosed
  directly on-page, not silently.
- A future phase could resolve both by adding a genuine backend write
  endpoint (e.g. `POST /api/profiles/{id}/goals` and a questionnaire-answer
  table) — deliberately **not** done in this phase, per its explicit
  "no backend changes" preference and "STOP that specific operation and
  document" instruction.
- No interactive browser verification was performed. **Not verified —
  reason: no headless-browser tool is available in this environment.** No
  claim of visual/rendered/click-through verification is made anywhere in
  this report; everything above was verified via direct source review, a
  real running backend, and real HTTP calls only.
- No frontend automated test runner exists in this repository
  (pre-existing, not introduced or resolved by this phase).
- The single ~953 kB JS bundle / no-code-splitting finding is unchanged in
  kind from Phase 20/21, only slightly larger in size.

## 24. Phase 23 Statement

**Phase 23 was NOT started.** No demo-data generation, demo-customer
population, customer-switching redesign, scenario-demo workflow,
presentation polish, chart/dashboard redesign, backend authentication,
JWT/OAuth, production accounts, new financial calculation, new ML model,
or recommendation/portfolio change was made. This report and its
accompanying code changes are the complete, final deliverable of Phase 22.
