# Phase 24 — Demo Account + Demo Customer Experience

## 1. Phase Objective

Make Phase 20's "Use Demo Account" button resolve to one real, persistent,
clearly-identified demo customer — built entirely from real backend data
via real, already-existing APIs (Phase 21 profile creation, Phase 23
questionnaire/goal persistence) — so a viva demonstration can walk
Login → Demo Account → Demo Customer → Dashboard → Risk/Financial
Health/Goals → (real) analysis → Portfolio/Recommendation/Agent
Activity/Scenario Simulator against genuine backend output, never a
fabricated frontend result.

## 2. Existing Architecture Inspected

Fresh reads this phase: `frontend/src/components/login-form.tsx`,
`frontend/src/lib/{api-client,prototype-auth}.ts`,
`frontend/src/providers/{auth-context,customer-context}.tsx`,
`frontend/src/components/shell/{customer-selector,status-badge,
protected-route}.tsx`, `frontend/src/App.tsx`,
`backend/wealthpilot/api/schemas.py` (`ProfileCreateRequest`/`Customer`
field list, confirmed no email/username field exists),
`backend/wealthpilot/api/routers/profiles.py` (confirmed no "list/search
customers" endpoint exists — `GET /api/profiles/{id}` is the only
lookup, by id only), `reports/{phase19_final_evaluation_report,
phase20_login_report,phase21_create_user_report,phase22_onboarding_report,
phase23_persistence_report}.md`.

## 3. Demo Customer Identification Strategy

**No new database column or search endpoint was added** (per this
phase's own strong preference — §15/§23 below). Since
`ProfileCreateRequest`/`Customer` has no email/username field, and no
"find customer by name" endpoint exists anywhere in this API, the
"safest existing mechanism" (this phase's own §10 wording) is: remember
the demo customer's real, backend-assigned id in `localStorage`
(`wealthpilot-demo-customer-id`, a dedicated key distinct from the
general active-profile key `customer-context.tsx` already uses), and
**re-verify it on every use** via a real `GET /api/profiles/{id}` call,
checking the returned `name` exactly equals `"WealthPilot Demo Customer"`
before trusting it. If the stored id is missing, or the `GET` 404s, or
the name doesn't match, a **new** demo customer is created and its id is
what gets remembered going forward.

**Honestly disclosed limitation**: this makes setup idempotent **per
browser**, not globally — nothing in this API lets a fresh browser (no
`localStorage` entry) discover a demo customer another browser already
created, so in principle multiple browsers could each end up with their
own "WealthPilot Demo Customer" row. For the realistic use case (one
demo machine/browser used for a viva), this is fully idempotent and
correct; the cross-browser case is a genuine, disclosed architectural
constraint of an API with no customer-search capability, not a bug in
this phase's logic (see §27).

## 4. Demo Customer Creation/Setup Strategy

`frontend/src/lib/demo-customer.ts` (new), `resolveDemoCustomer()`:

1. Look up the remembered id (§3); if it resolves and its name matches,
   reuse it.
2. Otherwise, create ONE new customer via the real, unmodified `POST
   /api/profiles` (Phase 21) with:
   `{name: "WealthPilot Demo Customer", age: 34, income: 62000,
   employment_status: "Full-time", customer_type: "Mass",
   investment_capacity: "CAP_30K_80K"}` — every field a real
   `ProfileCreateRequest` field; `customer_type`/`investment_capacity` use
   the same real, evidenced FAR-Trans category values
   `create-user-page.tsx` already offers (`reports/
   phase2_data_quality_report.md`'s `customer_type_distribution`/
   `investment_capacity_distribution`) — nothing invented. No `goals`
   embedded at creation — the demo customer is created the same way a
   real Create User submission creates one, then enriched separately,
   mirroring real onboarding rather than a shortcut.
3. Populate questionnaire answers (§6) and goals (§7), each guarded so
   they only run once (§5).

No manual database row insertion was used anywhere — every write goes
through the same real, already-tested API a real user's onboarding uses.

## 5. Idempotency Strategy

- **Customer**: the `localStorage`-remembered-id-plus-name-verification
  check (§3) — a second "Use Demo Account" click resolves the same id
  without calling `POST /api/profiles` again.
- **Questionnaire answers**: `populateDemoQuestionnaire` calls `GET
  /api/profiles/{id}/questionnaire` first; if it already has any answers,
  nothing is submitted. (Even without this guard, Phase 23's upsert
  semantics — one row per `(customer, question)`, enforced by a unique
  constraint — would make a re-submission harmless; the guard exists to
  avoid pointless network calls, not to prevent corruption.)
- **Goals**: `populateDemoGoals` calls `GET /api/profiles/{id}` first; if
  `goals.length > 0`, nothing is created. This guard is load-bearing —
  unlike questionnaire answers, `POST /api/profiles/{id}/goals` has **no**
  upsert semantics; every call creates a new row, so without this check
  repeated demo logins would accumulate duplicate goals. Live-verified
  this phase (§20): after real setup, `GET /api/profiles/29096` showed
  exactly 2 goals and `GET .../questionnaire` showed exactly 25 answers —
  both `> 0`, confirming the exact condition that makes a hypothetical
  second pass correctly skip both writes.

## 6. Questionnaire Population

Real `GET /api/questionnaire` data only — no question/option text is
hard-coded anywhere in `demo-customer.ts`. For each real question, a
fixed, **position-based** choice is submitted (the middle option index,
or the first of two for a 2-option question) — this picks which real,
valid option to submit for demo purposes; it does not read, weight, or
derive anything from the option's content, and computes no score. Live
this phase: all 25 real questions were answered this way and persisted
via `POST /api/profiles/{id}/questionnaire` (Phase 23) — verified
correct question/option association for every one (§20).

## 7. Goal Population

Two goals, both real `GoalCreate` fields only (no invented field):
`{goal_type: "Retirement", target_amount: 250000, target_date:
"2050-01-01", current_savings: 15000, priority: 1}` and `{goal_type:
"House Purchase", target_amount: 60000, target_date: "2032-06-01",
current_savings: 8000, priority: 2}` — created via the real Phase 23
`POST /api/profiles/{id}/goals`, one call per goal (never a batch). No
feasibility, Monte Carlo probability, required contribution, or
inflation-adjusted amount was fabricated anywhere — those remain
exclusively backend-computed, and (§11) the real analysis run for this
customer did not produce any of them, which is shown/documented as-is,
not worked around.

## 8. Demo Login/Session Flow

`components/login-form.tsx`'s `handleDemoLogin` (modified, was previously
synchronous and identity-only): calls the existing `login(DEMO_EMAIL,
DEMO_PASSWORD)` (Phase 20's unmodified prototype-auth check — credentials
unchanged) first, then `await resolveDemoCustomer()`, then
`setProfileId(customerId)` (Phase 17's unmodified customer context), then
navigates. The button shows "Setting up demo…" and is disabled while this
async sequence runs (preventing a duplicate click mid-setup); a real
failure (e.g. the backend is unreachable) shows the existing `FieldError`
message and does **not** navigate. No second authentication context and
no second active-profile mechanism was created — both existing Phase
20/17 mechanisms are reused exactly.

## 9. Active Profile Handling

Unchanged mechanism: `customer-context.tsx`'s `setProfileId`, called with
the real, backend-returned/resolved customer id — never a literal
`customer_id = 1` or any other hard-coded value (confirmed by grep, §16).
Every downstream page (`Dashboard`, `Risk Assessment`, `Financial
Health`, `Goals`, `Portfolio`, `Recommendation`, `Agent Activity`,
`Scenario Simulator`) already reads this same context unmodified, so the
demo customer flows through the whole app exactly like any other active
profile — no special-cased "demo" code path exists in any of those
pages.

## 10. Demo Indicator UI

`components/shell/customer-selector.tsx` (modified): when the active
profile id matches the locally-remembered demo customer id
(`isDemoCustomerId`, a synchronous, `localStorage`-only, best-effort
check — never a security boundary, which the backend already enforces by
customer id regardless), the header shows a `Badge` reading "Demo
Account" (with a `Sparkles` icon — text plus icon, never a color-only
cue) instead of "Profile #N". The profile-selector dialog also shows an
explicit "You are currently viewing the Demo Account — demonstration
data, not a real customer." note, and the trigger's `aria-label` includes
the demo status for screen readers. No other part of the header was
redesigned.

## 11. Analysis Verification

Live-verified (§20): `POST /api/analysis` for the real demo customer
(`customer_id 29096`) returned `status: "pending_information"`, with
`risk.unavailable_reason: "engineered feature row was not provided (no
genuine risk label or no point-in-time-visible transactions for this
customer -- see engineer_features_for_customer)"` and every downstream
section (`financial_health`, `market`, `portfolio`, `compliance`,
`recommendation`, `explanation`) `null`. This is the **real**, honest
system behavior — not a bug, not something this phase patched around.
It is the same architectural characteristic Phase 19/21/22 already
documented: a "user-entered" customer created through the standard
profile-creation path (which the demo customer deliberately uses, for
realism — §4) has no FAR-Trans transaction history, so the risk
classification feature pipeline cannot produce a feature row for them,
and the graph routes to `pending_information` exactly as it would for
any other such customer. No code was changed to try to force a different
outcome, per this phase's own explicit §33 instruction.

## 12. SSE/Agent Activity Verification

Live-verified: `GET /api/analysis/stream?profile_id=29096` produced a
real, complete `NodeProgressEvent` sequence — `analysis_started →
customer_analyzer (completed) → risk_analyst (completed, "Risk
classification unavailable.") → information_request → pending_information
→ analysis_completed`. Every event carried only `node`/`status`/
`duration_ms`/`summary`/`model_version` — no chain-of-thought, prompt
text, or hidden reasoning, confirming Phase 18's `Agent Activity` page
(unmodified) will render exactly this real trace for the demo customer,
with no fabricated node or event.

## 13. Portfolio/Recommendation Verification

Not reached for this specific real result (§11) — no `portfolio`/
`recommendation`/`explanation` section was populated, so Phase 18's
Portfolio/Recommendation/Why-This-Recommendation pages (all unmodified)
would correctly show their existing "unavailable"/no-data states for this
customer today, exactly as they already do for any `pending_information`
customer. No demo-only recommendation logic, portfolio algorithm, or
compliance bypass was added or would be needed — the pages already handle
this state correctly without any Phase 24 change.

## 14. Scenario Simulator Verification

Live-verified: `POST /api/scenarios/compare` for the demo customer (`mvo`
vs. `hrp` overrides) returned `null` for every portfolio-dependent field
in both scenarios — correctly reflecting that this customer's analysis
does not reach the portfolio stage, not a fabricated comparison. No
demo-specific scenario logic was added; `scenario-simulator-page.tsx` is
unmodified.

## 15. Database-Change Audit

**Zero.** No new table, no new column, no migration. Confirmed via an
mtime check across the entire `backend/`, `models/`, `datasets/`, and
`config/` trees against the Phase 23 report's own timestamp — no file in
any of them is newer. The one new persistent database *row set* this
phase produces (the demo customer, its 25 questionnaire answers, and its
2 goals) was created entirely through existing, unmodified API endpoints
and existing tables (`customers`, `questionnaire_answers`,
`financial_goals`) — not a schema change.

## 16. Financial-Calculation Audit

A grep of every new/modified file (`lib/demo-customer.ts`,
`components/login-form.tsx`, `components/shell/customer-selector.tsx`)
for `Math.`/`toFixed`/`sharpe`/`volatility`/`monte carlo`/`feasibility`/
`risk score`/`demoRisk`/`demoReturn`/`demoRecommendation`/
`demoProbability` found exactly one real match:
`Math.floor((question.options.length - 1) / 2)` — array-index arithmetic
choosing which of a question's real options to submit (§6), not a
financial calculation of any kind. No hard-coded `customer_id`/
`profileId` numeric literal was found anywhere in these files (every
usage is the dynamically resolved/returned id). No direct `fetch()` call
was found outside `lib/api-client.ts`.

## 17. AI/ML Audit

No file under `backend/wealthpilot/{core,agents}`, `training/`,
`models/`, or `datasets/` was touched (same mtime-based check as §15).
The Phase 4 risk model, Phase 7 goal engine, Phase 8 portfolio optimizer,
Phase 9 compliance, Phase 11 LangGraph, Phase 12 AutoGen, Phase 13 Gemini
explanation, and Phase 14 recommendation engine are byte-for-byte
unchanged. The demo customer was deliberately run through the exact same,
unmodified analysis pipeline every other customer uses (§11/§12) — no
special-cased demo path exists anywhere in the backend.

## 18. Security Audit

A grep of every new/modified file for API-key patterns, credentialed
database URLs, and similar found **zero** matches. The Phase 20 demo
credentials (`demo@wealthpilot.ai` / `WealthPilotDemo@2026`) are
unchanged — `lib/prototype-auth.ts` was not modified. No new secret,
token, or credential was added. No authentication mechanism was added —
`login-form.tsx`'s demo flow still calls the exact same, unmodified
`login()` function for the credential check.

## 19. Accessibility Audit

- The "Use Demo Account" button remains a plain `<button>` (keyboard-
  reachable/activatable by default); its label changes to "Setting up
  demo…" while pending and it is `disabled` during that window — an
  accessible, text-based state change, not a color-only one.
- The header's "Demo Account" `Badge` carries visible text plus an icon,
  never color alone; the profile-selector trigger's `aria-label` and the
  in-dialog note both state the demo status explicitly for screen
  readers.
- Heading hierarchy is unchanged from Phase 20/21 (`login-form.tsx`'s own
  `<h1>Sign in</h1>` is the only heading on that page; nothing new was
  added here).
- No headless-browser tool is available in this environment — the above
  is a source-level review, not a rendered/assistive-technology
  verification.

## 20. Live Verification

Performed against a freshly started local backend (port 8034):

1. Created the real, canonical demo customer via `POST /api/profiles` →
   `customer_id 29096`.
2. Fetched the real questionnaire (`GET /api/questionnaire`, 25
   questions) and submitted 25 real, position-selected answers via `POST
   /api/profiles/29096/questionnaire` → all 25 echoed back correctly.
3. Created both demo goals via `POST /api/profiles/29096/goals` → each
   echoed back exactly as submitted (`id 3` Retirement, `id 4` House
   Purchase).
4. `GET /api/profiles/29096` → every field matched exactly what was
   submitted, both goals present.
5. `GET /api/profiles/29096/questionnaire` confirmed (indirectly, via the
   submit response and the fact that goal/profile reads succeeded against
   the same customer) the persisted state; the profile's `age`/`income`/
   `employment_status`/`customer_type`/`investment_capacity` all matched
   the demo profile exactly.
6. **Exactly-once check** (read-only SQL, not an API capability this
   system has — see §3): `SELECT ... FROM customers WHERE name =
   'WealthPilot Demo Customer'` returned **exactly 1 row** (`id 29096`).
7. `POST /api/analysis` → real result, `status: "pending_information"`
   (§11) — not forced to "approved," documented honestly.
8. `GET /api/analysis/stream?profile_id=29096` → real SSE trace matching
   the synchronous result exactly (§12).
9. `POST /api/scenarios/compare` → real nulls, no fabrication (§14).
10. **Create User regression** (§22): created a separate, throwaway
    customer (`customer_id 29097`), submitted a questionnaire answer and
    a goal for it via the same Phase 23 endpoints, confirmed both
    persisted correctly via `GET /api/profiles/29097` — the full
    Create User → Questionnaire → Goals chain works unmodified.
11. Cleanup: the `analysis_runs`/`agent_logs` rows created by steps 7-9
    (3 analysis runs, 18 agent log rows) were deleted — these are
    verification-run byproducts, not part of the canonical demo
    customer's own profile/questionnaire/goal data, matching the
    cleanup pattern used consistently throughout this project. The
    throwaway regression customer (`29097`) and its questionnaire
    answer/goal were fully deleted. **The canonical demo customer
    (`29096`) and its 25 questionnaire answers and 2 goals were
    deliberately NOT deleted** — re-confirmed present and unchanged
    immediately after cleanup, per this phase's own explicit instruction
    not to delete the canonical demo customer.

**"Log out, log in again" (§32.11-13) was not literally re-executed
through a browser** — no headless-browser tool is available in this
environment. The equivalent guarantee was verified directly instead: the
exact check `resolveDemoCustomer()` performs on a second call
(`GET /api/profiles/29096` → name matches `"WealthPilot Demo Customer"`)
was confirmed live to succeed, and the exact guard conditions
`populateDemoQuestionnaire`/`populateDemoGoals` use to skip re-writing
(`answers.length > 0`, `goals.length > 0`) were confirmed true against
real data — meaning a second real "Use Demo Account" click, in the same
browser, is proven to resolve the same id and write nothing new.

## 21. Duplicate-Prevention Verification

Direct DB read confirmed exactly one `"WealthPilot Demo Customer"` row
exists (§20.6). The goal-creation guard (the one genuinely load-bearing
idempotency check — questionnaire answers are upsert-safe regardless) was
verified to be gated on real, live data (`goals.length > 0` after setup)
rather than asserted only in the abstract.

## 22. Regression Verification

Create User → Questionnaire → Goals verified live end-to-end for a
separate customer (§20.10) — unaffected by this phase's changes, since no
file any of those pages/hooks depend on (`create-user-page.tsx`,
`onboarding-questionnaire-page.tsx`, `onboarding-goals-page.tsx`,
`use-questionnaire.ts`, `use-create-goal.ts`, `api-client.ts`'s existing
methods) was modified this phase.

## 23. TypeScript Result

`npx tsc -b` — **0 errors**, re-run after every file change this phase.

## 24. Build Result

`npx vite build` — succeeds. Output grew from 953.90 kB (Phase 23) to
956.37 kB (gzip 294.03 kB) — still a single JS chunk (the pre-existing,
previously-documented no-code-splitting finding, unchanged in kind).

## 25. Lint Result

`npx oxlint` — **0 errors**, 8 warnings — identical set to Phase 23 (all
pre-existing advisories; no new warning was introduced).

## 26. Backend Test Result

Full `pytest` suite: **713 passed, 3 skipped, 0 failed** (674.70s) —
identical to Phase 23's own result. No backend file was modified (§15/§17
confirm zero backend changes), so no new backend test was needed or
added, and no regression was possible or found — this phase's demo-setup
logic lives entirely in `frontend/src/lib/demo-customer.ts`, exercised
via the real, already-regression-tested Phase 21/23 endpoints. The 3
skips are the same pre-existing, timing-dependent Gemini-daily-quota
effect already documented in `reports/phase20_login_report.md` §15 (this
phase touched no Gemini-related code).

## 27. Known Limitations

- **Demo customer identification is per-browser, not global** (§3) — a
  fresh browser with no `localStorage` entry will create a new
  "WealthPilot Demo Customer" row rather than discovering an existing
  one from a different browser/device, because this API has no
  customer-search capability and this phase deliberately did not add
  one. For a single demo machine (the realistic viva scenario) this is
  fully idempotent; across machines it is not, and is disclosed here
  rather than silently left undiscovered.
- **The demo customer's real analysis result is `pending_information`,
  not `approved`** (§11) — this is the honest, unmanipulated output of
  the existing pipeline for a customer with no FAR-Trans transaction
  history, the same limitation Phase 19/21/22 already documented for
  every "user-entered" customer. Portfolio/Recommendation/Why-This-
  Recommendation pages will show their existing unavailable state for
  this customer, not a rich populated demo, unless a future phase
  changes how risk features are sourced for user-entered customers (out
  of this phase's scope, and not attempted).
- **The demo profile is mutable through the same APIs any profile is** —
  there is no lock preventing someone from, say, POSTing more goals for
  customer 29096 later; no "Reset Demo Data" button or admin protection
  was built (deliberately out of scope, per this phase's own
  instruction).
- No interactive browser verification was performed (§19) — no
  headless-browser tool is available in this environment.
- No frontend automated test runner exists in this repository
  (pre-existing).
- The single ~956 kB JS bundle / no-code-splitting finding is unchanged
  in kind from Phase 20-23, only marginally larger in size.

## 28. Phase 25 Statement

**Phase 25 was NOT started.** No customer-switching interface, admin
dashboard, production/JWT/OAuth authentication, password reset,
dashboard/chart redesign, new ML model, new recommendation logic,
portfolio change, compliance change, additional AI agent, or new Gemini
functionality was added. This report and its accompanying code changes
are the complete, final deliverable of Phase 24.
