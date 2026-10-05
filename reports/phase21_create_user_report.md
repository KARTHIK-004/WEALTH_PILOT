# Phase 21 — Create New User / Customer Onboarding

## 1. Objective

Add a dedicated `Create New User` page so the application flow becomes
`Login → Create New User → Customer Profile → Dashboard` (with Questionnaire/
Goals explicitly deferred to Phase 22), replacing the previous dead end
where a new customer had no real way to create their own profile. This
phase implements profile creation only — no questionnaire, no goal
creation, no financial-history fabrication, and no ML/AI/compliance logic
was touched.

## 2. Existing API Used

`POST /api/profiles` (`backend/wealthpilot/api/routers/profiles.py:30`),
inspected directly before writing any frontend code — not assumed. It
writes a `Customer` row (`data_source="user-entered"`, set by the backend,
never client-supplied) and, if any `goals` are supplied, `FinancialGoal`
rows via the same endpoint; this phase deliberately never populates
`goals` (Phase 22's responsibility). `GET /api/profiles/{id}` (already
consumed by the existing, untouched `ProfilePage`) is the authoritative
display path — this phase does not add a second way to render a profile.

The frontend's centralized `api.createProfile()` (`lib/api-client.ts:84`)
already existed, fully typed against the generated schema, unused until
this phase — no API client change was needed.

## 3. Profile Schema

Read directly from `backend/wealthpilot/api/schemas.py:64-76`
(`ProfileCreateRequest`/`ProfileCreateResponse`) and cross-checked against
the generated `frontend/src/types/api.ts:418-439` — identical, as expected
for a generated file:

| Field | Type | Constraint | Form field built |
|---|---|---|---|
| `name` | `str` | required, 1-200 chars | Text input, required, maxLength 200 |
| `age` | `int \| None` | 0-120 | Number input, min 0 / max 120 / step 1, optional |
| `income` | `float \| None` | ≥ 0 | Number input, min 0 / step 0.01, optional, labeled "Annual income" (matches `ProfilePage`'s own label) |
| `employment_status` | `str \| None` | max 100 chars | Text input, maxLength 100, optional |
| `customer_type` | `str \| None` | max 50 chars | Select, optional (see below) |
| `investment_capacity` | `str \| None` | max 50 chars | Select, optional (see below) |
| `goals` | `list[GoalCreate]` | default `[]` | **Not built** — Phase 22 |

No field was invented. `monthly income`, `monthly expenses`, `emergency
fund`, `savings rate`, and `portfolio value` were explicitly checked
against this schema and confirmed **absent** — none were added to the
form, per this phase's own explicit prohibition and Phase 19's already-
documented FAR-Trans financial-data-gap finding.

`customer_type`/`investment_capacity` are plain, length-constrained
strings in the schema — no backend enum exists to mirror. Rather than a
free-text field (typo-prone, no benefit) or an invented category list, the
Select options use the **real, evidenced category values** from
`reports/phase2_data_quality_report.md`'s own `customer_type_distribution`
(`Mass`, `Premium`, `Professional`, `Inactive`, `Legal Entity`) and
`investment_capacity_distribution` (`CAP_LT30K`, `CAP_30K_80K`,
`CAP_80K_300K`, `CAP_GT300K`, with human-readable dollar-range labels) —
`Predicted_*`/`Not_Available` variants excluded, per CLAUDE.md rule 7 (they
are another model's output, not genuine categories). This is grounded in
existing evidence, not an invented business rule.

Per section 13, **no risk-category picker was built.** Risk classification
(Conservative/Income/Balanced/Aggressive) remains exclusively a backend/ML
output; this form cannot influence it.

## 4. Create User Page

`frontend/src/pages/create-user-page.tsx`, registered at `path="create-user"`
in `App.tsx`. Deliberately:

- **Standalone**, outside `AppShell` — no sidebar, no header, matching
  `/login`'s own treatment (an onboarding action, not an analysis page).
- **Not added to the Dashboard sidebar nav** (`nav-items.ts` untouched).
- **A public route, not wrapped in `ProtectedRoute`** — this is the one
  deliberate interpretive decision this phase made explicitly, documented
  here: the phase brief's own "Final User Experience" diagram (its final
  section) draws `Create New User` as a path parallel to, not gated behind,
  `Demo Account` — both converging on `Dashboard`. Section 30's own
  instruction allows this exact case ("respect the existing authentication
  guard **unless the authoritative product flow explicitly requires public
  registration**"), and that diagram is read here as exactly that
  authorization. On a genuine, backend-confirmed `POST /api/profiles`
  success, the page grants the **same** Phase 20 prototype-auth session
  (`AuthProvider.grantSessionAfterProfileCreation()`, a small, clearly-
  documented addition to the existing context — not a second auth system,
  not a bypass of the demo-credential check on the login form itself) so
  "Continue" can reach the protected Dashboard without an extra, redundant
  login step. If this reading is wrong, the fix is a one-line change
  (wrap the route in `ProtectedRoute`) — flagged explicitly rather than
  silently assumed.

Two Cards ("Personal Information", "Financial / Investment Profile") group
the fields per the phase's own suggested structure, built from the Phase
20 `Field`/`FieldGroup`/`FieldLabel`/`FieldDescription` primitives (no new
UI library, no hand-rebuilt shadcn primitive).

## 5. Form Fields

See §3's table. Every field description explicitly says "Optional." where
the schema allows `None`, and only `name` is marked `required`. No
business rule beyond the schema's own length/range constraints was added.

## 6. API Integration

`frontend/src/hooks/use-create-profile.ts` — a `useMutation` wrapping
`api.createProfile()`, matching the existing `useScenarioCompare` pattern
exactly (same shape, same file organization). The form's submit handler
builds a `ProfileCreateRequest` object directly from local input state,
omitting (not nulling) any field left blank/unspecified, and calls
`mutation.mutate(...)` — no raw `fetch()`, no second API-calling path.

## 7. Active Customer Context

On success, `handleContinue` calls the existing `useCustomer().setProfileId
(mutation.data.customer_id)` — the exact, unmodified Phase 17 mechanism,
using the **backend-returned** id, never a client-generated one. The
customer context itself (`providers/customer-context.tsx`) was not
modified. `CustomerSelector`'s stale "Create one on the Customer Profile
page" link/text (misleading even before this phase, since `ProfilePage`
has always been display-only) was updated to point to `/create-user` — the
smallest safe fix to keep the app internally consistent, per section 23's
own instruction, not a selector redesign.

## 8. Success Flow

On `mutation.isSuccess`, the form is replaced by a success Card showing
"Profile Created Successfully" and **the actual returned** `customer_id`
(never fabricated) as "Profile ID: `<id>`". "Continue" then: sets the
active profile, grants the prototype session, and navigates to `/`
(Dashboard) — matching the phase brief's own final-flow diagram
("Profile Created → Dashboard") and its explicit fallback instruction
("If there is no defined next step yet: navigate to the existing Customer
Profile or Dashboard"). No Questionnaire/Goals page is linked to or built.

## 9. Error Handling

Reuses the existing `components/shell/error-state.tsx` unmodified (the
same component `ScenarioSimulatorPage` already uses) — RFC 7807
`application/problem+json` bodies render their `title`/`detail` only,
network unreachability is distinguished from a backend-returned error, and
neither path can show a stack trace or SQL detail (confirmed live, §11).
"Try again" resets the mutation without losing entered field values (they
live in local `useState`, untouched by a failed mutation).

## 10. Loading State

The submit button shows "Creating profile…" and is `disabled` while
`mutation.isPending`, preventing duplicate submissions from a double-click
without any added retry logic. No fake/optimistic success is ever shown —
the success Card renders only from `mutation.isSuccess`, which TanStack
Query sets only after a real 2xx response.

## 11. Accessibility

- Every input has a real `<label>` via `FieldLabel`/`htmlFor` (`Field`
  primitives from Phase 20, unmodified).
- Only `name` carries `required`; every optional field's description says
  "Optional." explicitly (not color-only, not implied).
- Native `<input type="number">` browser controls, keyboard-operable
  `Select`/`Button` primitives — no custom mouse-only interaction.
- Errors render through `ErrorState`'s `Alert` (a `role`-carrying,
  text-based, non-color-only pattern already established in Phase
  16-20).
- **Fixed this phase**: the success state initially had no real heading
  element (`CardTitle` renders a `<div>`, not `<h1>`-`<h6>`) — added a
  visually-hidden `<h1 className="sr-only">Profile Created Successfully
  </h1>` so the success state has a correct, announced heading without
  changing its visible design.
- The form state's own `<h1>Create Your Profile</h1>` is the page's only
  visible top-level heading, matching the one-h1-per-page convention
  established since Phase 17.

No headless-browser tool is available in this environment — the above is a
source-level review, not a rendered/assistive-technology verification (see
§21).

## 12. Responsive Design

Single-column, `max-w-2xl` container with `p-6 md:p-10` outer padding (no
fixed-width elements); the age/employment-status pair uses the existing
`Field` `orientation="responsive"` variant (already defined in Phase 20's
`field.tsx`, unmodified) to stack on narrow screens and sit side-by-side at
the `@md` container breakpoint. This is a structural review, not a
rendered check — browser visual verification unavailable in this
environment (see §21).

## 13. Security

A targeted grep of every Phase 21 file for API-key patterns, credentialed
database URLs, and similar found **zero** matches. No new secret, token,
or credential was added anywhere.

## 14. Financial Logic Audit

A targeted grep of every Phase 21 file for arithmetic operators used on
figures, `Math.`, `toFixed`, percentage/ratio patterns, and terms like
`sharpe`/`volatility`/`monte carlo`/`feasibility` found **zero** matches.
The only numeric handling in this phase is `Number(age)`/`Number(income)`
— parsing a raw form-input string into the exact number the backend
schema expects, not a calculation. No ratio, percentage, risk formula,
recommendation logic, portfolio logic, or goal mathematics was added.

## 15. Backend Changes

**NONE.** Confirmed via an mtime check across the entire `backend/` tree
(and `models/`, `datasets/`, `config/`) against the Phase 20 report
timestamp — zero files newer. `POST /api/profiles` was inspected, not
modified; it already supported every field this phase's form needed, so no
STOP-and-ask was required.

## 16. Database Changes

**NONE** — no migration, no schema change, no new table/column/index. A
real, live `POST /api/profiles` call was made against a running backend
during verification (§17); the one real row it created (customer_id 29091)
was deleted afterward (`DELETE FROM customers WHERE id = 29091`, 0
`financial_goals` rows existed to cascade), and a follow-up count query
confirmed 0 rows remain at that id. No pre-existing data was touched.

## 17. Tests

**Backend regression**: full `pytest` suite — **697 passed, 3 skipped, 0
failed** (636.63s). Matches the established baseline exactly (Phase 20's
698/2 split was already explained there as timing-dependent noise in 3
live-Gemini-call tests hitting a shared daily quota — the total is 700
tests either way, and 0 failures in both runs). No backend file was
modified this phase (§15), so no behavior change was possible or found.

No new automated frontend test file was added (this repository still has
no frontend test runner wired into `package.json` — pre-existing, not
introduced or resolved by this phase, same disclosure as Phases 16-20).
The 9 manual test scenarios in the phase brief were verified either by
source-level control-flow review or by a real, live API call:

- **Live-verified**: a real `POST /api/profiles` call with the exact
  payload shape the form sends (`name`, `age`, `income`,
  `employment_status`, `customer_type`, `investment_capacity`) returned
  `{"customer_id": 29091}`; `GET /api/profiles/29091` echoed every
  submitted field back exactly, confirming the round trip end-to-end. Two
  real validation-error calls (empty `name`, negative `income`) both
  returned `422` with `application/problem+json` bodies — confirming
  `ErrorState` will render them correctly, not a raw 500 or a stack trace.
- **Source-level review**: page reachability, empty-submit/invalid-field
  handling (native HTML constraints + the live-verified backend fallback),
  active-profile update after creation, reload persistence (same
  `localStorage` mechanism `customer-context.tsx` already uses, untouched),
  Customer Profile / Dashboard reflecting the new active profile (both
  pages read `useCustomer().profileId` unmodified, so a changed profile id
  flows through automatically), and confirmation that no code path in this
  page calls `api.runAnalysis`/`POST /api/analysis` anywhere.

## 18. TypeScript

`npx tsc -b` — **0 errors** (re-run after every change, including the
`Select.onValueChange`'s `string | null` signature fix and the
accessibility fix in §11).

## 19. Build

`npx vite build` — succeeds. Output grew from 924.79 kB (Phase 20) to
930.65 kB (gzip 286.41 kB) for the added onboarding page — still a single
JS chunk (the pre-existing, previously-documented no-code-splitting
finding; unchanged in kind, not something this phase's scope authorized
changing).

## 20. Lint

`npx oxlint` — **0 errors**, 8 warnings — identical set/pattern to Phase
20 (all pre-existing `only-export-components`/`set-state-in-effect`
advisories on files this phase did not introduce that pattern in).

## 21. Browser Verification

Unavailable in this environment — no headless-browser tool exists here, so
no click-through of Login → Create New User → success → Dashboard was
visually performed, and no claim of visual/mobile/tablet verification is
made. **Browser visual verification unavailable in this environment.**
What could be verified — the real API round trip, TypeScript/build/lint,
and full source-level review of every interactive path — was verified
directly, as detailed in §11/§12/§17.

## 22. Known Limitations

- **Prototype authentication only** (unchanged from Phase 20): granting a
  session after profile creation still means no password hashing, no
  server-side session, no token — the same disclosed, non-production
  caveat, now reachable via a second entry path.
- **A newly created "user-entered" profile has no FAR-Trans transaction
  history**, so it cannot receive the same risk-classification feature
  pipeline (`engineer_features_for_customer`) that FAR-Trans-sourced
  customers can. This is a pre-existing characteristic of the already-
  approved risk pipeline (unrelated to and unmodified by this phase, and
  consistent with Phase 19's own "no real customer currently reaches
  approved" finding) — noted here for completeness, not something this
  phase attempted to fix.
- **The `/create-user` public-route interpretation** (§4) is this phase's
  own explicit reading of an ambiguous instruction, not a certainty — flagged
  rather than silently assumed; reversible in one line if the intended
  design was actually the guarded default.
- No interactive browser verification was performed (§21).
- No frontend automated test runner exists in this repository
  (pre-existing).
- The single ~931 kB JS bundle / no-code-splitting finding is unchanged in
  kind, only slightly larger in size (consistent with Phase 20's own
  disclosure of this same finding).

## 23. Phase 22 Boundary

This phase implements profile creation only. It explicitly does **not**
implement: Questionnaire, questionnaire-answer persistence, goal creation
or editing, customer-switching redesign, demo-data population, financial-
health data entry, or any modification to investment-recommendation logic.
The newly created profile carries no goals, no questionnaire answers, and
no synthesized financial history — exactly the FAR-Trans-consistent, honest
state Phase 19 already established for real customers. Per the phase's own
stop condition, Phase 22 is not started here.
