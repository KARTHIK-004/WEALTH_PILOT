# WealthPilot AI — Current Project Memory

The current, verified state of the project. Not a historical narrative —
that lives in `reports/`. Update this file whenever current architecture
or state changes materially; keep entries short and current, not a log.

## Current Phase
Phase 36 (Household Goals & Emergency-Fund Planning) is the most recently
completed phase — see `reports/phase36_household_goals_report.md` — and Phase 35
(Household Financial Data Persistence & Management) immediately before it
(`reports/phase35_household_financial_persistence_report.md`).

- **Phase 35** found that the four household financial tables, their sixteen
  CRUD routes and the summary's use of them already existed (Phases 33/34). With
  the owner's agreement it added only optional factual metadata — `notes` on all
  four, `description` on assets and liabilities, `interest_rate` on liabilities —
  kept `is_active` as the activity rule, and kept ADR-032's `amount > 0` and
  nullable `monthly_payment` (ADR-034).
- **Phase 36** added `household_goals`: a household's goals as stored facts,
  separate from the individual `financial_goals`, with no goal math (the
  assumptions `core/goals.py` needs do not exist for a household) and the
  emergency-fund requirement still computed only by the Phase 34 summary
  (ADR-035).

Neither phase changed `core/`, `agents/`, any model, the individual goals or
financial inputs, or `POST /api/analysis`. No implementation phase is in
progress and no further phase is authorized.

## Overall Project Status

All planned phases through Phase 36 are implemented, tested, and
documented. The full backend regression suite passes in isolation (see
"Current Test Status"). The frontend type-checks, builds, and lints
cleanly. The system reaches all four terminal analysis states (approved,
approved/savings-first, rejected, pending_information) through real,
unmodified pipeline execution, verified live against real demo customers.
Verified at source level only (no browser tool exists here): the frontend
journeys.

## Completed Phases

Phase 0 (foundation) through Phase 25 (final UX/viva polish), each with
its own numbered report in `reports/`, plus four additional,
non-numbered-in-filename phases completed after Phase 25 and before
Phase 28: the Demo Data phase (`reports/demo_data_completion_report.md`),
the Live Analysis Flow phase (`reports/live_analysis_flow_fix_report.md`),
the Post-Login Profile Flow fix
(`reports/post_login_profile_flow_report.md`), Phase 28 itself
(`reports/phase28_financial_input_savings_first_report.md`), Phase 29
(`reports/phase29_final_integration_report.md`), Phase 30
(`reports/phase30_analytics_visualization_report.md`), and Phase 31
(`reports/phase31_final_demo_readiness_report.md`), Phase 32
(`reports/phase32_household_foundation_report.md`), Phase 33
(`reports/phase33_household_financial_data_report.md`), Phase 34
(`reports/phase34_household_financial_aggregation_report.md`), Phase 35
(`reports/phase35_household_financial_persistence_report.md`), and Phase 36
(`reports/phase36_household_goals_report.md`). See `TASKS.md` for the itemized
checklist.

## Current Architecture

Matches `docs/ARCHITECTURE.md` in full as of this writing — no known
drift between that document and source at the time this memory entry was
written.

## Current Backend State

FastAPI app (`backend/wealthpilot/api/main.py`) with routers for
profiles (including Phase 28's financial-inputs endpoints and the
Live-Analysis-Flow-phase name-lookup endpoint), analysis, scenarios, qa,
health. `analysis_service.py::_build_graph_dependencies` (Phase 28) wires
real financial inputs into every analysis run. `core/compliance.py` has
the Phase 28 savings-first weight exemption. `agents/nodes.py`'s
`savings_first_node` has the Phase 28 `sufficient is None` fix, and
`load_portfolio_returns` is public (renamed from `_load_portfolio_returns`).
Phase 29 corrections in `analysis_service.py`: the goal Monte Carlo's
historical-return series is compounded to the goal's contribution period
frequency (`_compound_to_period_returns` — before this, daily returns were
applied once per month and every goal showed 0.0%; ADR-027);
`ANALYSIS_PIPELINE_VERSION` ("2") is part of the analysis cache key so a
computation fix invalidates stale cached results; the `savings_first` SSE
summary says "insufficient" only when sufficiency is known to be false and
"could not be confirmed" when it is unknown.

Phase 32 backend (household foundation): models `Household`/`HouseholdMember`
(`db/models.py`), schemas (`api/schemas.py` — request models forbid unknown
fields so nothing financial can be sent), `api/routers/households.py`,
`api/services/household_service.py` (all rules and authorization),
`api/dependencies.py::get_acting_customer_id`, and new RFC 7807 errors
(401 identity required, 403 access denied, 404 household / member not found,
409 conflict). Only the household's primary member can add or remove members;
a member can view; the primary cannot be removed; nothing in the household code
reads or writes any financial table, and `POST /api/analysis` is untouched.

Phase 33 backend (household financial data): models `HouseholdIncome`/
`HouseholdExpense`/`HouseholdAsset`/`HouseholdLiability` (`db/models.py`), 12
new schemas (`api/schemas.py`, every request model `extra="forbid"`),
`api/routers/household_finances.py` (16 routes),
`api/services/household_finance_service.py` (one table-driven core plus
explicit per-resource functions), and one new error
(`HouseholdRecordNotFoundError`, 404).

Phase 34 backend (household aggregation): `core/household_finance.py` — a pure,
DB-free, `Decimal` engine holding ALL household arithmetic (monthly
normalization, one-time separation, active-only aggregation, cash flow, net
position and an emergency fund reusing `core/goals.py`'s 6-month constant and
comparison) — plus `api/services/household_summary_service.py` (loads four
scoped queries, maps engine output to the schema, no arithmetic of its own),
`api/routers/household_summary.py` (one read-only GET) and nine new response
schemas. Nothing derived is persisted; a summary is recomputed per request. No
migration, table or column was added, and `analysis_service.py`, `core/goals.py`
and every model remain untouched. `household_service.py` gained
`require_member`/`require_primary_member` helpers, reusing the Phase 32
membership checks unchanged. **The service layer contains no arithmetic**: it
lists, creates, merges partial updates and deletes records, and returns them as
stored. Nothing in `core/`, `agents/`, `analysis_service.py` or any ML code was
touched.

## Current Frontend State

Public-page colors (2026-10-02): Home, About and their shared navbar/footer use
exactly the dashboard's semantic tokens (neutral `primary`); the former
`--brand` token and the public-only `.public-theme` override were both removed,
so the app has one color system (`docs/DESIGN.md` section 32). New public pages
use the same tokens with no override.

About This Project page (2026-10-02): public `/about` (`pages/about-page.tsx`,
`components/about/`, `docs/DESIGN.md` section 31) — static project explanation
built only from documented results (metrics.json, phase reports); linked from the
Home navbar/footer and a "Project" group in the app sidebar.

Plain-language dashboard (2026-10-01, frontend presentation only):
`lib/terminology.ts` maps raw API values to plain labels (tickers, strategies,
capacity bands, metrics, statuses, compliance rules, analysis steps); raw
values, method names, versions and artifact paths are kept in collapsed
`TechnicalDetails` sections, with `HelpTip` tooltips for terms (`docs/DESIGN.md`
section 30). API values and numbers are unchanged. Also fixed: Base UI
`SelectValue` showed raw values (`default`/`mvo`, `unspecified`) — the
Scenario Simulator and Create Profile selects now pass `items`; the create-user
capacity labels now come from the shared mapping (€, was `$`); and a
pre-existing 768px horizontal overflow (the header's page title could not
shrink, widening the content column) is fixed with `min-w-0` on `SidebarInset`
and the header title; the household section's tab row now scrolls sideways at
phone width instead of clipping its last tabs.

Demo completeness audit (2026-10-01, `docs/demo_runbook.md` "Demo Completeness
Audit"): Financial Health now also shows the profile's own stored income,
essential expenses and liquid savings (display only), states that individual
debts/cash flow/net position are not recorded, and points household members to
the separate household summary. The spending pattern stays unavailable for all
demo personas (ADR-010; no Kaggle/FAR-Trans linkage). Resolved by the
2026-10-04 demo reset (ADR-040): the out-of-seed "TEST" household and the
duplicate customer were removed; see the demo-data section below for current
ids.

Public Home page (2026-10-01): `/` is a public, static landing page
(`pages/home-page.tsx`, `components/home/`, `docs/DESIGN.md` section 29) —
outside `ProtectedRoute` and `AppShell`, no API call. The Dashboard moved from
`/` to `/dashboard` (sidebar item, sidebar logo, 404 link, onboarding
"Continue to Dashboard", error-boundary reload, and the login default redirect
all updated). Home's demo buttons open `/login?demo=individual|family`, which
only focuses the matching existing demo button; authentication is unchanged.
(The accent token `--brand` added then was later removed; public pages now use the dashboard's neutral tokens.)

Ten protected pages plus Login/Create-User/two onboarding pages, all
reading a single `profileId` source of truth. The Customer Profile page
now includes a Financial Inputs card (Phase 28) alongside the existing
profile-field and goals display. No customer-switching UI exists
anywhere (removed in the post-login-flow fix). Phase 29: the
Recommendation page renders the API's per-rule compliance results via
`components/shell/compliance-breakdown.tsx` (a rejected analysis now shows
which rule triggered and the engine's own reason, not only a generic
"blocked" sentence); Why This Recommendation states why no explanation
exists for a rejected/pending result; the Dashboard's "Next step" text for
a savings-first result says a savings-first recommendation is ready and no
investment allocation is active.

Phase 30 visualization layer: `components/charts/` (Recharts, display-only —
`docs/DESIGN.md` section 16, ADR-029) holds `RiskProbabilityChart`
(Risk Assessment), `EmergencyFundChart` (Financial Health; Portfolio and
Dashboard on a savings-first result), `GoalTargetChart` (Goals),
`PortfolioAllocationChart` (Portfolio, Recommendation, Dashboard — approved
only; replaced the old `components/portfolio/allocation-chart.tsx`),
`ScenarioComparisonChart` (Scenario Simulator) and `AgentPipeline` (Agent
Activity; draws only received SSE events). Every chart plots an API value
unchanged, shows an unavailable state for `null` (never zero), and sits
beside a table/text with the same values. The Goals page shows Monte Carlo
probabilities to one decimal and a "Contribution exceeds the calculated
requirement." note when the backend's `contribution_gap` is negative. The
Portfolio page shows the Phase 29 compliance breakdown for a rejected
analysis. Not built: a portfolio risk/return or efficient-frontier chart
(the API exposes no frontier data).

Phase 31 frontend polish (targeted, no redesign): the Why This Recommendation
page separates "Explanation (wording only)" — labelled either AI-written
wording checked against the computed numbers, or a template restatement (its
fallback alert now correctly names an unavailable/out-of-quota service, not
only failed validation) — from "Deterministic factors" computed by the
backend; the Customer Profile page has a Questionnaire card linking to
`/onboarding/questionnaire` (the questionnaire's Back returns to the page
that linked to it), and every empty Financial Inputs field shows "Not
provided" (never 0); the Dashboard says "N goal(s) recorded — not yet
evaluated" instead of "No goals recorded" when analysis has not reached goals;
login/create-user/onboarding text uses em dashes; the scenario chart's
sub-titles are `<h2>` (no skipped heading level); the obsolete unused
`components/shell/page-placeholder.tsx` was removed and `App.tsx`'s stale
"Phase 16 placeholders" docstring corrected.

Phase 32 frontend: a Household card on the Customer Profile page
(`components/profile/household-card.tsx`, `hooks/use-household.ts`, household
methods in `lib/api-client.ts`) — "No household created yet." with a create
form, or the household name / your role / relationship / member count, and
behind "View Household" a member table (with a "You" badge) and, for the primary
member only, a labelled prototype add-member form (existing profile ID +
relationship + role) and two-step Remove. No arithmetic, no implicit creation,
and no customer switching.

Phase 33 frontend: "View Household" now opens a `Tabs` control whose first tab
is the Phase 32 Members table, followed by Income, Expenses, Assets and
Liabilities — all four rendered by the config-driven
`components/profile/household-finance-section.tsx` over
`hooks/use-household-finances.ts` and 16 new `lib/api-client.ts` methods. Each
tab lists the household's stored records exactly as returned, with add/edit
dialogs and two-step delete for the primary member and read-only tables for
everyone else. **There is no arithmetic in it at all** — no total, net worth,
savings, ratio or coverage figure, and each tab states in muted text what is
not being calculated; a `null` renders as "Not provided" (a liability's absent
monthly payment) while a stored `0` renders as a formatted zero. Validation is
form-shape only (required / numeric / sign), mirroring the API's own rules.

Phase 34 frontend: the expanded household card now renders
`components/profile/household-financial-summary.tsx` above those tabs, over
`hooks/use-household-summary.ts` — the recurring monthly view, one-time records,
an assets/liabilities table with net position, the emergency-fund position, and
neutral Available/Unavailable badges per area. It is display-only and contains
**no arithmetic at all**; `null` renders as "Not provided" and a stored `0` as a
formatted zero. The Phase 33 record mutations also invalidate the summary query
so an edited record yields a freshly recomputed summary from the server.

Plain-language explanations (ADR-037, not a phase): Why This Recommendation
opens on a **Simple** view (`components/explanation/plain-language-explanation.tsx`)
built only from the deterministic analysis fields, so it works for every
analysis including cached ones. The existing AI/fallback wording and
deterministic-factors card are the **Detailed** view.

**Backend part NOT applied (as of 2026-09-30).** The Gemini prompt wording,
the stricter validator (ticker attribution, derived counts, grouped amounts
such as "30,000") and the plainer fallback are prepared outside the repository.
None of them is in `agents/explanation.py`, and
`tests/backend/agents/test_explanation_readability.py` does not exist yet.

The required pre-patch full-suite run was interrupted on 2026-09-27 at 51%,
with no exit code recorded. The only failure it had printed,
`test_setup_family_is_idempotent`, had no traceback, so it is unclassified; it
passed in isolation on 2026-09-30.

Applying and validating the backend part is pending an explicit instruction.
Its known gap is real: the current validator reads "30,000" as 0.

## Current ML State

Risk (`models/risk/`), behaviour (`models/behaviour/`), expense
(`models/expense/`), market (`models/market/`) artifacts are all trained
and loaded at startup. No model was retrained, modified, or re-saved
since Phase 19's final evaluation — confirmed by `find models -newer
<baseline>` returning empty at the end of every subsequent phase,
including Phase 28.

## Current Database State

Alembic head: `c3e8f2a9d154` (`add household goals`, Phase 36), revising
`a7c41e9b6f30` (Phase 35's `add household financial metadata columns`), revising
`d2be70d8b07f` (`add household financial data tables`, Phase 33),
revising `f59ab6395383` (Phase 32's `add households and household_members`),
which revises `8ef3f9affbe5` (Phase 28's `add financial_inputs`). Tables:
`customers`, `customer_risk_snapshots`, `financial_goals`,
`questionnaire_answers`, `financial_inputs`, `transactions`, `portfolios`,
`market_data`, `recommendations`, `agent_logs`, `risk_assessments`,
`analysis_runs`, `households`, `household_members`, `household_incomes`,
`household_expenses`, `household_assets`, `household_liabilities`,
`household_goals`. Applied to both
`DATABASE_URL` and `TEST_DATABASE_URL`. `household_members` enforces, in the
database, one household per customer (`UNIQUE(customer_id)`), one primary per
household (partial unique index), primary implies `self`, `self` never a
dependent, `is_dependent` = (`role` = 'dependent'), and the controlled
relationship/role vocabularies; both foreign keys cascade. The four Phase 33
financial tables each hang off `household_id` (indexed, cascading) and carry
**no `customer_id`**; CHECK constraints enforce the controlled vocabularies and
the sign rules (income/expense `amount > 0`; `current_value >= 0`;
`outstanding_amount >= 0`; `monthly_payment IS NULL OR monthly_payment >= 0`),
with `monthly_payment` nullable and `is_essential` defaultless on purpose. No
column, view or query aggregates any of it — Phase 34's summary is derived in
Python, per request, and stored nowhere, so **Phase 34 added no migration**.
Phase 35 added seven optional metadata columns to those four tables (all
nullable, no default; `interest_rate` `Numeric(6, 4)` with a non-negative
CHECK). Phase 36 added `household_goals` (facts only, no `customer_id`,
`target_amount > 0`, nullable `current_savings`, controlled `goal_type`).
`alembic check` reports no drift on either database. The dev database holds no
household rows of any kind: every live check ran inside a transaction that was
rolled back, and row counts were confirmed unchanged afterwards.

## Current API State

`GET /api/questionnaire`, `POST /api/profiles`,
`GET /api/profiles/{id}`, `GET /api/profiles/lookup`,
`POST`/`GET /api/profiles/{id}/questionnaire`,
`POST /api/profiles/{id}/goals`,
`GET`/`PUT /api/profiles/{id}/financial-inputs`,
`POST /api/analysis`, `GET /api/analysis/{id}`,
`GET /api/analysis/stream`, `POST /api/scenarios/compare`,
`POST /api/qa`, `GET /api/health`, and (Phase 32, all requiring an
`X-Customer-Id` header, none touching finances) `POST /api/households`,
`GET /api/households/{id}`, `GET`/`POST /api/households/{id}/members`,
`DELETE /api/households/{id}/members/{member_id}`,
`GET /api/profiles/{id}/household`, and (Phase 33, same header and
authorization) `GET`/`POST /api/households/{id}/income|expenses|assets|
liabilities` plus `PUT`/`DELETE` on each `/{record_id}`, and (Phase 34)
`GET /api/households/{id}/financial-summary`, and (Phase 36)
`GET`/`POST /api/households/{id}/goals` plus `GET`/`PUT`/`DELETE` on
`/goals/{goal_id}` — 29 paths in all. There is no
household deletion route, no mutation route for calculations, and deliberately
no totals, net-worth, savings or debt-ratio route; tests pin the household route
inventory exactly and assert that `financial-summary` is the ONLY aggregate
path. `frontend/src/types/api.ts` was regenerated in Phase 36 (+313 lines, -0)
directly from `app.openapi()`, and a second generation is byte-identical.

## Current Agent State

LangGraph topology unchanged in shape since Phase 11; two Phase 28
corrections to node/rule *behavior* (not topology) are documented in
`docs/DECISIONS.md` ADR-018. AutoGen debate and Gemini explanation are
both unchanged in mechanism; Gemini explanation is now genuinely
exercised live (previously never reached for any customer pre-Phase-28).

## Current AI/LLM State

`GEMINI_MODEL`/`GEMINI_API_KEY`/`GEMINI_PROJECT_NUMBER` configured via
`.env`. Live Gemini calls have been observed falling back to the
templated, non-generative explanation under quota pressure during
Phase 28's own live verification — the pre-existing, correct fallback
behavior, not a defect.

## Current Authentication State

Prototype auth unchanged in mechanism since the post-login-flow fix: one
supported demo credential, automatic customer resolution on every
successful login (regular or demo), no manual profile-id entry anywhere.

## Current Demo State

Canonical personas (this environment's ids — regenerate via
`python backend/scripts/seed_demo_data.py verify` for a fresh
environment's actual ids):

**Reset 2026-10-04 (ADR-040):** the database was fully reset and reseeded
under new ids, removing the ADR-030 duplicate customer and a stray "TEST"
household that had accumulated. Persona A gained a third goal (House
Purchase) and the household gained a fourth goal (a long-term family
retirement fund) — both within the existing schemas. The table and family
summary below are this reset's actual, freshly-computed values (not
illustrative).

| Persona | id (this env) | Financial inputs | Actual status (analysis id) |
|---|---|---|---|
| WealthPilot Demo Customer (Phase 24) | 29096 | n/a (no FAR-Trans link) | `pending_information` (168) |
| WealthPilot Demo — Complete | 29107 | Sufficient EF + GoalAssumptions | `approved`, real MVO portfolio QQQ 55%/GLD 45%, PASS; goals: Emergency Fund Feasible 97.4%, Retirement Feasible 94.1%, House Purchase At Risk 50.6% (207) |
| WealthPilot Demo — Savings | 29108 | Known-insufficient EF + GoalAssumptions | `approved` with `recommendation.status = savings_first`, no weights, PASS; goals: Emergency Fund Not Feasible, Retirement Feasible 88.6% (208) |
| WealthPilot Demo — Compliance | 29109 | None (deliberately preserved) | `rejected`, one triggered rule `emergency_fund_savings_first` (209) |

(Ids 150–153 and 165–167 are superseded runs from before this reset; they
remain as history and are never read by the app.)

**Family demo (ADR-036):** household **"WealthPilot Demo Family"** (id 8 in
this environment), seeded by `seed_demo_data.py setup-family` through the
public household API — primary "WealthPilot Demo — Savings" (29108,
self/primary), spouse "WealthPilot Demo — Compliance" (29109, spouse/member),
5 income, 8 expense, 4 asset, 2 liability and 4 goal records (emergency fund,
home deposit, family holiday, family retirement fund). Summary: recurring
income 6,700, recurring expenses 3,365, cash flow 3,335, net position 41,700,
emergency fund required 17,820, status insufficient. The individual data of
all four personas is unchanged by it (verified before and after). Details:
`reports/family_demo_report.md`.

"Use Individual Demo" (formerly "Use Demo Account") and a regular Sign In
resolve to "WealthPilot Demo — Complete" whenever it is seeded, in every browser — Phase 31 (ADR-030)
reordered `resolveDemoCustomer` so the seeded persona wins over a remembered
blank fallback id (before this, a browser that had once landed on the blank
"WealthPilot Demo Customer" stayed there). Only when "Complete" is not seeded
does it fall back to a remembered demo id or the from-scratch canonical
customer. "Use Family Demo" resolves the family's primary, 29108, and opens
its Household section (ADR-036) — so 29108's own pages are now reachable
in-app; 29109 still is not (no switcher, by design) and its individual result
is shown via `/docs` — see `docs/final_demo_script.md` sections 15–17.

**Demo dataset (ADR-038, not a phase):** `demo_data/` is the single source
of the demo population, validated by
`python backend/scripts/validate_demo_data.py`.

- **Contents:** personas A–D (29107, 29108, 29109, 29096 here), family
  `WPDEMO-FAM` (household 8), five strategy scenarios, and expected
  contract-level states. Version 1.0.0; the manifest records counts, hashes
  and the raw-data guard. Persona A now has 3 goals and the family has 4
  (ADR-040); the manifest was regenerated accordingly.
- **Seeding:** `seed_demo_data.py` loads it. `setup` now also seeds persona D
  (find-or-create; `reset` never deletes it). Every mode takes `--in-process`.
  `verify` compares all stored values and the expected states.
- **No duplicate present.** The ADR-030 duplicate (old id 29101) and the
  stray "TEST" household were removed in the 2026-10-04 reset (ADR-040); a
  direct `GROUP BY name HAVING count(*) > 1` check over demo-named customers
  confirms none has been recreated, and re-running `setup`/`setup-family`
  a second time creates zero rows.
- Details: `demo_data/README.md`, `reports/demo_dataset_catalog.md` §10.

Final demo material: `docs/final_demo_script.md` (click-by-click, verified
numbers), `docs/final_viva_talking_points.md` (40 answers),
`docs/demo_runbook.md` (longer narrative). `reports/final_viva_facts.md` is a
Phase 19 snapshot with a superseded note — do not quote its "no customer has
reached approved" or "goal engine not wired" claims.

## Current Customer Association

`CustomerProvider`'s `profileId` (`wealthpilot-profile-id` in
`localStorage`) is the single source every protected page reads, set only
by `login-form.tsx::completeLogin`, `create-user-page.tsx::handleContinue`,
and cleared by `header.tsx`'s sign-out. Household membership (Phase 32) does
not change this: the authenticated customer stays the active user, and a
household route reads that same `profileId`, sent as `X-Customer-Id`. The
header is an asserted identity (no server session), so household authorization
stops accidental/URL-edited cross-household access, not a malicious client.

## Current Dataset State

`datasets/raw/FAR-Trans/` and `datasets/raw/kaggle/` unchanged since
ingestion; immutable per `docs/DECISIONS.md` ADR-023. Their SHA-256 hashes are
recorded in `demo_data/manifest.json` (`training_data_guard`), which
`validate_demo_data.py` checks. The synthetic demo dataset lives separately in
`demo_data/` and is never training data (ADR-038).

**Synthetic ML training dataset (ADR-039, not a phase)** in `datasets/generated/`.
The CSVs are git-ignored and regenerate byte-identically with
`python scripts/generate_wealthpilot_synthetic_dataset.py` (seed 42).

- **Size:** 100,000 customers × 76 columns, 2,642,361 transactions and 325,290
  goals.
- **Format copies:** the same population is also written in the FAR-Trans and
  Kaggle formats, which the existing loaders read unchanged.
- **Targets:**
  - `risk_label` from hidden variables;
  - `expense_segment` and `behavior_anomaly` as planted ground truth;
  - `goal_feasibility` from the production goal engine at 500 paths.
- **Validation:** `scripts/validate_synthetic_training_dataset.py`.
- **Not wired into any training script.** Using it to train a production model
  is a separate decision.
- Details: `datasets/generated/README.md`.

## Current Model Artifacts

Unchanged since Phase 19 (risk/behaviour/expense) and their respective
training phases (market/portfolio) — see "Current ML State" above.

## Current Test Status
Latest full run, after the demo dataset package (ADR-038), 2026-09-30 21:03:45–23:12:42, detached and in
isolation: **`1326 passed, 1 skipped, 158 warnings in 7732.26s (2:08:52)`, 0 failed, 0 errors, exit code 0.**
The earlier Phase 36 run below remains as history.

Full `pytest tests/ -v`, run detached and in isolation at the end of Phase 36:
**`1260 passed, 3 skipped, 152 warnings in 5977.95s (1:39:37)` — 0 failed,
0 errors, pytest exit code 0.** This is one clean, fully isolated, detached run of
`pytest tests/ -v` (1263 tests collected), started 2026-09-26 20:10:52 and exited
21:50:35. The 3 skips are the documented live-Gemini tests
(`test_debate_gemini_client.py` x2, `test_explanation_gemini_client.py` x1),
which skip when Gemini is unavailable or out of quota (CLAUDE.md section 19).

How it was reached, per `docs/TEST_PLAN.md` section 22: an earlier full run the
same day ended `1249 passed, 2 skipped, 12 errors in 21318.72s (5:55:18)`,
exit code 1. All 12 errors were in `tests/backend/api/test_household_goals.py`,
all at **test setup** (no test body ran), all at
`tests/backend/api/conftest.py:56` (`engine.connect()` in the `db_connection`
fixture): the first raised `server closed the connection unexpectedly` / `the
connection is lost`, the other eleven `[Errno 11001] getaddrinfo failed`. No
product frame appeared in any traceback, so all 12 were classified
DATABASE/NETWORK. After a DB-free probe confirmed the database reachable, exactly
those 12 were re-run in isolation, unmodified: **12 passed, 0 failed** (164.96s,
exit code 0). The clean run above was then taken fresh; the earlier run is not
used as the result. (A development server started outside this work was also
running during the clean run; the run still completed with no failure or
error.)

Before that, the most recent completed full run was Phase 32's (**838 passed,
2 skipped, 0 failed**, 37:03). Phases 33 and 34 never completed one: Phase 33's
attempts were killed by session teardowns (which is how a stale Phase 32 route
inventory went unnoticed until Phase 34), and Phase 34's was blocked when
port 5432 to the hosted database became unreachable.

Phase 35/36 targeted run (every never-before-executed Phase 35 and 36 test
file, detached, in isolation): **236 passed, 0 failed** in 30:19 — engine 61,
migration history 11, goal models 30, metadata models 11, goals API 85,
metadata API 39. One earlier Phase 35 failure was a defect in the test itself
(it deleted a household through the ORM instead of exercising the database
cascade) and was corrected before this run.

Live check against the real dev database (rolled back): **34/34** — the four
personas' full analysis responses byte-identical, their individual goals and
financial inputs unchanged, the summary reading persisted records with the
specified reference values, goals never changing the summary, and all 11
tables' row counts restored.

Frontend, at the current state of the code: `npx tsc -b` 0 errors; `npx oxlint`
0 errors, 8 baseline warnings; `npm run build` succeeds. Source-level render
checks of the Customer Profile page against real API payloads pass 20/20
(Phase 36), 17/17 (Phase 35) and 39/39 (Phase 34). No browser-based test has
been run.

## Current Build Status

Frontend production build succeeds; 1,094.83 kB (gzip 327.13 kB) single JS
chunk plus 97.80 kB CSS (a known, accepted characteristic — not code-split;
see `docs/TEST_PLAN.md` §18). By original source size the bundle is roughly
24% Recharts, 18% `@base-ui/react` (shadcn v4 primitives), 17% react-dom, 10%
react-router, 8% application code; the only duplicated bundled package is a
small nested `reselect` under recharts. Recharts arrived in Phase 30 (+84 kB).

## Current Known Limitations

See `docs/ARCHITECTURE.md` §23 and `docs/PRD.md` §39 for the full list;
summary: `expense_persona` permanently unavailable for FAR-Trans
customers (structural); prototype auth has no server session
(disclosed); no customer-switching UI (by design); no browser-based
visual testing performed to date (disclosed each time it applies) — in
particular the Phase 30 charts' drawing, label room at narrow widths and
dark-mode contrast are unverified; only their data binding was checked.
Environment-specific: the Gemini account's quota is exhausted (HTTP 429
`RESOURCE_EXHAUSTED`), so every approved analysis currently shows the
designed templated explanation (`validation_passed: false`) rather than a
validated live Gemini one — though as of Phase 32 the quota has partially
recovered: one of the three live-Gemini tests now runs and passes, while the
other two still skip; `customers.name` is not unique at the schema level (so
`GET /api/profiles/lookup` deterministically returns the lowest id when
names repeat), though the 2026-10-04 reset (ADR-040) removed the one
duplicate that had actually accumulated (old id 29101); a Python virtualenv
exists at
`frontend/.venv/` (created outside any phase's work on 2026-09-20 12:53,
gitignored, untouched); backend-authored `unavailable_reason` strings are
shown verbatim and contain developer-style wording (ASCII " -- ", one names
an internal function) — changing them is a backend text change, deferred;
the databases
are hosted, so network drops can cause bursts of test failures unrelated
to the code. **Known defects (found in Phase 36, not fixed — outside its
scope):** the Phase 33 household record endpoints return a 500 rather than a
422 for an explicit `null` on a required field in a `PUT`, and for a
non-finite (`"1e400"`) or out-of-range amount; the Phase 28
`FinancialInputsUpdate` schema also accepts non-finite values (its HTTP
behaviour was not probed). The Phase 35 `interest_rate` field and the Phase 36
goal schemas are hardened against both.

**Pre-existing finding from the final git audit (documented, not changed):** the
root `.gitignore` (last modified 2026-09-24 23:24, before Phases 35 and 36) has
no rule for `datasets/`, so `git status` now lists the ten raw files under
`datasets/raw/` as untracked, contrary to CLAUDE.md's "datasets/raw/ ...
gitignored". Neither phase touched `.gitignore` or `datasets/`: every raw file
still matches its recorded Phase 5 SHA-256 hash, and the `datasets/`
directories were last modified 2026-09-13. `.env` and both virtualenvs are
still ignored. Restoring the rule (for example `datasets/raw/*` with a tracked
`.gitkeep`) is left to the project owner, and should be done before any first
commit so the raw datasets are not committed.

## Current Blockers
None. The port-5432 block recorded during Phase 34 cleared on its own; the
database has been reachable throughout the Phase 35/36 validation.

## Pending Work

- The backend part of the plain-language explanation enhancement (ADR-037) is
  prepared but not applied or validated; see Current Frontend State above.
  Nothing else is scheduled. See `docs/PRD.md` §40 (Future Scope) for possible,
unscheduled future direction.

## Important Implementation Notes

Scenario Simulator: for the Aggressive default persona the risk-conditioned
default is already MVO; comparing it with HRP or 1/N shows both **REJECTed by
compliance** (QQQ below the Aggressive band) — real, verified behaviour, useful
in a demo. `PYTHONPATH` must include the repo root (not just `backend/`) for
`training.*` imports to resolve outside pytest's own `pythonpath = .` —
relevant when running any one-off script that imports from
`agents/nodes.py` (which imports `training.behaviour.common`). Do not run
a long-lived server (e.g. `uvicorn`) to generate the OpenAPI schema for
type regeneration — call `app.openapi()` directly in a short-lived Python
process instead (`json.dump(FastAPI_app.openapi(), f)`), then
`npx openapi-typescript <file> -o frontend/src/types/api.ts`. When
running the full backend test suite in the background for a long
duration, do not pipe through `tail` — it buffers all output until the
process exits, hiding real progress; prefer direct/unbuffered output to a
file you can `Read` incrementally. The databases are hosted (Neon), so a
network drop mid-run produces bursts of DB failures (`getaddrinfo failed`,
`Network is unreachable`, `server closed the connection unexpectedly`);
see `docs/TEST_PLAN.md` §22 for how to classify them. When a cached
analysis must be recomputed after a change to what the pipeline computes,
bump `ANALYSIS_PIPELINE_VERSION` in `analysis_service.py` rather than
deleting rows. `run_goal_monte_carlo` needs per-period returns matching
`GoalAssumptions.contribution_periods_per_year`; never pass it the raw
daily series. Recharts 3 draws no `<svg>` in a server render (its surface
mounts after a client-side size measurement), so chart *drawing* cannot be
verified without a browser; chart *data binding* was verified in Phase 30
by SSR-rendering the real page components against real API responses with
the Recharts primitives replaced by data-capturing stubs (scratch harness,
not committed; Phase 31 extended it to the whole routed app with the four
personas — 71 checks — plus a rollback-safe live API regression of every route,
56 checks). After changing any backend docstring that appears in the
OpenAPI schema, regenerate `types/api.ts` (dump `app.openapi()` to JSON,
then `npx openapi-typescript`) — Phase 29's lookup-docstring edit left it
stale by one comment until Phase 30.

## Last Verified State

This file was last verified against source and the live system at the
completion of Phase 32. If a later change is made without updating this file, treat
this section's claims as potentially stale and re-verify against source
per `docs/RULES.md` Rule 29.
