# Architecture Decision Records

Permanent architectural decisions for WealthPilot AI. Each record captures
a decision that would be expensive or risky to silently reverse. Day-to-day
implementation state belongs in `docs/MEMORY.md`, not here; historical
phase-by-phase narrative belongs in `reports/`, not here. When a decision
listed here is later changed, add a new ADR that supersedes it — never
edit an accepted ADR's Decision/Consequences to hide what actually
happened; add a note under it instead.

Every record below reflects a decision genuinely made and acted upon in
this repository (`CLAUDE.md`, `docs/PROJECT_PLAN.md`,
`docs/BUILD_PLAN.md`, and the phase reports in `reports/`) — none is
invented for this documentation pass.

---

## ADR-001 — FastAPI Backend

**Status**: Accepted

**Context**: The project needs a Python API layer that can host
synchronous JSON endpoints and a streaming (SSE) endpoint for long-running
LangGraph analysis runs, with first-class Pydantic v2 integration for
request/response schemas and automatic OpenAPI schema generation (needed
for generated frontend TypeScript types — ADR-006).

**Decision**: Use FastAPI, `backend/wealthpilot/api/`.

**Consequences**: `GET /api/analysis/stream` streams over SSE
(`api/sse.py`); every other endpoint is synchronous JSON. Errors use RFC
7807 problem-details responses (`api/errors.py`), never a bare 500.

---

## ADR-002 — React 19 + Vite + TypeScript Frontend

**Status**: Accepted

**Context**: A typed, component-based SPA frontend consuming the FastAPI
backend, with fast local dev iteration.

**Decision**: React 19, Vite, TypeScript, `frontend/`.

**Consequences**: No Next.js, no server-side rendering. `no any` in
TypeScript. React Router for client-side routing (ADR-005).

---

## ADR-003 — PostgreSQL + SQLAlchemy + Alembic

**Status**: Accepted

**Context**: A relational store for customer, goal, questionnaire,
financial-input, analysis-run, and model-output data, with real
migrations (not `create_all`-only) so schema evolution is auditable.

**Decision**: PostgreSQL, SQLAlchemy ORM (`backend/wealthpilot/db/`),
Alembic migrations (`backend/alembic/`).

**Consequences**: Every schema change ships as an Alembic revision
(`alembic revision --autogenerate`), applied to both `DATABASE_URL` and
`TEST_DATABASE_URL` (`ALEMBIC_TARGET=test alembic upgrade head`). Two
separate databases exist specifically so the test suite can never touch
development data.

---

## ADR-004 — shadcn/ui + Tailwind CSS

**Status**: Accepted

**Context**: Consistent, accessible UI primitives without hand-rolling a
component library.

**Decision**: shadcn/ui components (`frontend/src/components/ui/`),
Tailwind CSS for styling.

**Consequences**: Primitives are added via `npx shadcn@latest add <name>`,
never hand-written. No second design system is introduced (see
`docs/DESIGN.md`).

---

## ADR-005 — TanStack Query + React Router

**Status**: Accepted

**Context**: Server-state caching/invalidation and client-side routing.

**Decision**: TanStack Query for all API data-fetching hooks
(`frontend/src/hooks/`), React Router for routes (`frontend/src/App.tsx`).

**Consequences**: Every page reads server state through a TanStack Query
hook, never raw `fetch` in a component. Cache keys are scoped per
customer (e.g. `["analysis", profileId]`) so pages sharing a customer
share one cache entry — the single-source-of-truth pattern documented in
`reports/post_login_profile_flow_report.md`.

---

## ADR-006 — Generated OpenAPI → TypeScript Types

**Status**: Accepted

**Context**: Keeping frontend request/response types in sync with the
actual Pydantic schemas without manual duplication drifting out of date.

**Decision**: `openapi-typescript` generates `frontend/src/types/api.ts`
from the live FastAPI OpenAPI schema (`npm run generate-types`, or
`app.openapi()` called directly in Python when no server should be
started — see `CLAUDE.md` "Working Style" and
`.claude/rules/backend.md`).

**Consequences**: `types/api.ts` is never hand-edited. A hand-written
interface mirroring a Pydantic model is a bug (CLAUDE.md rule 3).

---

## ADR-007 — Offline ML Training, Online Serving Only

**Status**: Accepted

**Context**: Training is expensive (walk-forward CV, deep-learning market
models) and must never block or run inside a request.

**Decision**: Training scripts live in `training/<family>/` (risk,
expense, behaviour, market, portfolio), write versioned artifacts to
`models/<family>/` plus `models/metrics.json`. FastAPI loads artifacts
once at startup (`api/lifespan.py`'s cache-warming) and reuses them for
every request.

**Consequences**: Nothing trains inside a request, a LangGraph node, or
an agent. Model artifacts are only ever replaced by explicitly re-running
a training script, never implicitly.

---

## ADR-008 — Time-Series Validation: Expanding-Window Walk-Forward + Embargo

**Status**: Accepted

**Context**: Shuffled train/test splits leak future information into
past predictions for time-ordered data (market returns, transaction
history).

**Decision**: No shuffled splits on time series. Expanding-window
walk-forward cross-validation with an embargo gap between train and test
windows. Market models target returns/volatility, never price levels.

**Consequences**: `training/market/`'s walk-forward harness and
`tests/training/*/test_*isolation*.py`'s leakage tests enforce this.
Verified in `reports/phase3_leakage_audit.md` and re-verified per model
family in its own phase report.

---

## ADR-009 — `random_state=42` Everywhere

**Status**: Accepted

**Context**: Reproducibility across training runs and demo-data
generation.

**Decision**: `random_state=42` (or the equivalent numpy `default_rng`
seed) in every stochastic step — train/test splitting, model fitting,
Monte Carlo simulation (`core/goals.py::RANDOM_STATE`), synthetic
demo-persona questionnaire/goal selection.

**Consequences**: Identical inputs always produce identical outputs;
non-determinism in a test failure is a real signal, not expected noise.

---

## ADR-010 — FAR-Trans for Risk/Behaviour, Kaggle for Expense Segmentation — Never Linked

**Status**: Accepted

**Context**: Two independent, unlinked real/synthetic datasets each cover
a different modeling need; conflating them would fabricate a
cross-population relationship that does not exist.

**Decision**: FAR-Trans (`datasets/raw/FAR-Trans/`) trains/serves risk
classification (Phase 4) and behaviour-drift detection (Phase 5). It has
no income/expense/savings fields. The Kaggle personal-finance dataset
(`datasets/raw/kaggle/`) trains/serves expense-persona clustering (Phase
5) for its own, separate population.

**Consequences**: `expense_persona` is permanently, structurally
`unavailable` for every FAR-Trans-linked customer (real or demo) — not a
bug, a disclosed consequence of this decision. No code anywhere infers a
FAR-Trans customer's expense persona from the Kaggle model, or vice
versa.

---

## ADR-011 — LangGraph for Deterministic Orchestration

**Status**: Accepted

**Context**: The analysis pipeline (customer → risk → financial health →
goals → market → portfolio/savings-first → compliance → [recommendation →
explanation]) needs explicit, typed, auditable state transitions — not
free-form agent conversation.

**Decision**: `backend/wealthpilot/agents/graph.py`, a compiled
`StateGraph(AgentState)` (LangGraph). Every node wraps exactly one
Phase-10 node function (`agents/nodes.py`) and applies its result via
`apply_delta` (`agents/state.py`) — no financial/ML logic lives in the
graph module itself.

**Consequences**: The full node sequence and routing (risk-confidence
gate, behaviour-drift re-profile branch, emergency-fund branch,
compliance branch) is deterministic and unit-testable
(`tests/backend/agents/test_graph_execution.py`). No randomness, no LLM
call, decides graph routing.

---

## ADR-012 — AutoGen for Bounded Strategy Debate

**Status**: Accepted

**Context**: A second, independent perspective on an already-computed,
already-compliant portfolio proposal, without letting an LLM alter any
number.

**Decision**: `backend/wealthpilot/agents/debate.py` — three bounded
personas (AutoGen) critique an already-approved allocation. Standalone
module (not wired into the LangGraph graph itself — Phase 12's own
documented choice), called by later orchestration only where the design
calls for it.

**Consequences**: Debate output is never a source of a financial number;
it is bounded critique text, validated the same way explanation output is
(ADR-013).

---

## ADR-013 — Gemini for Explanation Only, With Structured-Output Validation

**Status**: Accepted

**Context**: An LLM can write clear prose about a decision-support
result, but must never be the source of a financial number
(CLAUDE.md rule 1).

**Decision**: `backend/wealthpilot/agents/explanation.py` sends Gemini a
fully-computed dict and a schema for structured prose output; the
response is validated against the source dict and rejected (with a
templated, non-generative fallback — `validation_passed: false`) on any
mismatch, missing-key, or API failure/timeout.

**Consequences**: `explanation.status` is always `"completed"` (via
either a real Gemini response or the fallback) whenever it runs at all —
never a raw exception surfaced to the API response. Every explanation
field is provably traceable to an already-computed value. Gemini API
calls are gated behind `overall_status == "approved"` in
`api/services/analysis_service.py` — never invoked for a REJECT or
pending-information result.

---

## ADR-014 — Deterministic Financial Calculations Are the Sole Authority

**Status**: Accepted

**Context**: Financial correctness must be auditable and reproducible;
neither the frontend nor an LLM may be a second, parallel source of a
number.

**Decision**: Every financial number (risk score, expense ratio, goal
funding math, Monte Carlo probability, portfolio weight, compliance
verdict, recommendation) is computed exactly once, in
`backend/wealthpilot/core/` (`goals.py`, `optimizer.py`, `compliance.py`)
or a trained model under `models/`. React (`frontend/src/`) only formats
already-computed API values; Gemini only restates them in prose
(ADR-013).

**Consequences**: If a number is needed anywhere, it is added as an API
field — never computed client-side or by an LLM. This is CLAUDE.md rules
1-2, enforced by convention and by explicit prohibition in every
frontend-touching phase's own scope.

---

## ADR-015 — Compliance Is Binding and Fail-Closed

**Status**: Accepted

**Context**: A suitability/compliance gate that could be silently
bypassed, or that guesses PASS when required data is missing, would
defeat the entire purpose of a compliance layer.

**Decision**: `backend/wealthpilot/core/compliance.py::enforce_gate`
raises `ComplianceRejectedError` on REJECT; nothing in the codebase
catches it. Rules are declared in `config/compliance_rules.yaml` (id,
description, severity, condition, message) and evaluated by
`evaluate_compliance` against a plain `ComplianceProposal` — never a
Python expression executed from YAML (`yaml.safe_load` only). A rule
whose required input is unavailable is marked `triggered=True` at its own
severity (fail-closed), not silently skipped.

**Consequences**: `agents/nodes.py::compliance_analyst_node` always runs
when the graph reaches it; `api/services/analysis_service.py` only calls
the recommendation engine and Gemini explanation when
`overall_status == "approved"`. See ADR-018 for the one narrow,
documented exception to "no weights means REJECT."

---

## ADR-016 — Recommendation Precedence: Compliance > Savings-First > Risk > Goal > Market

**Status**: Accepted

**Context**: When multiple signals disagree about the right strategy, the
order in which they're allowed to override each other must be fixed and
auditable, not ad hoc.

**Decision**: `backend/wealthpilot/core/recommendation.py`/
`agents/recommendation.py` implement this exact precedence: a compliance
REJECT blocks everything; an insufficient emergency fund forces
savings-first regardless of risk/goal/market preference; otherwise risk
category selects the base strategy (ADR-017), which goal feasibility and
market regime may only nudge within the compliance-approved envelope,
never override.

**Consequences**: `recommendation.rationale.reasons` always states which
layer decided the outcome, in plain language — verified live for both
`approved` and `savings_first` demo outcomes (`reports/
phase28_financial_input_savings_first_report.md` §14).

---

## ADR-017 — Portfolio Strategy Universe: MVO, HRP, 1/N Only

**Status**: Accepted

**Context**: A fixed, auditable mapping from risk category to strategy is
easier to explain and to compliance-check than an open-ended strategy
space.

**Decision**: Exactly three strategies exist
(`backend/wealthpilot/core/optimizer.py`): MVO (max-Sharpe, box-constrained
— Aggressive), HRP (Hierarchical Risk Parity — Conservative/Income), 1/N
(equal weight — Balanced). Asset universe: QQQ, AGG, GLD
(`ASSET_UNIVERSE`). No other strategy is implemented or planned.

**Consequences**: `RISK_LEVEL_QQQ_BANDS` and `GENERAL_SINGLE_ASSET_CAP`
(70%) are the only portfolio-shape constraints; compliance validates
against exactly these, never an inferred or ad hoc bound.

---

## ADR-018 — Savings-First Absent Weights Are Not an Invalid Portfolio (Phase 28)

**Status**: Accepted (supersedes the original, unqualified reading of
ADR-015's weight-validation rules)

**Context**: `agents/nodes.py::savings_first_node` legitimately never
produces portfolio weights ("skip optimization entirely" — Phase 10's own
documented design). The original compliance weight-validation rules
(`weights_sum_to_one`, `no_negative_weights`, `qqq_within_risk_band`,
`single_asset_cap`) fail-closed REJECTed whenever `weights is None`, with
no exception — including for this legitimate case, which meant no
customer could ever reach a clean `PASS` via the savings-first path.

**Decision**: The four weight-validation rules now recognize
`weights is None AND is_savings_first_recommendation is True` as a PASS,
via a shared `_missing_weights_outcome` helper
(`core/compliance.py`). Every other "no weights" case, and any case where
weights ARE present (even for a savings-first-flagged proposal — guarded
against inconsistency), is still validated exactly as before.

**Consequences**: A known-insufficient emergency fund can now reach
`overall_status == "approved"` with `recommendation.status ==
"savings_first"` — verified live
(`reports/phase28_financial_input_savings_first_report.md`). No rule,
severity, or id was removed; REJECT's fail-closed behavior for genuinely
missing data (`emergency_fund_savings_first` triggering on
`sufficient is None`) is completely unchanged.

---

## ADR-019 — No Trade Execution, No Fund Transfer, No Brokerage Integration

**Status**: Accepted

**Context**: This is an educational decision-support prototype, not a
licensed advisory or execution platform.

**Decision**: The system never executes a trade, transfers funds, or
integrates with a brokerage for execution — ever, at any phase.

**Consequences**: No such capability exists anywhere in
`backend/wealthpilot/` and none is planned. Every disclaimer surfaced to
the user (Gemini's own `disclaimer` field, the login page's prototype-auth
notice) states this plainly.

---

## ADR-020 — Prototype Authentication (Not Production-Grade)

**Status**: Accepted, with disclosed limitations

**Context**: A real authentication system (JWT/OAuth, server sessions,
password hashing, account management) is explicitly out of scope for an
M.Tech prototype's demonstration needs.

**Decision**: Client-side credential check only
(`frontend/src/lib/prototype-auth.ts`), one hard-coded demo credential
plus a Create-User flow that grants a session locally. No backend
session/token; no server-side authorization check on any
`/api/profiles/*` route.

**Consequences**: `localStorage` state (`wealthpilot-prototype-authenticated`,
`wealthpilot-profile-id`, `wealthpilot-demo-customer-id`) is devtools
-editable — a disclosed, accepted limitation, not a defect to silently
"fix" with a larger auth system unless explicitly requested. See
`reports/post_login_profile_flow_report.md` §17 and
`docs/SECURITY.md`.

---

## ADR-021 — One Customer Per Authenticated Session, No Switcher UI

**Status**: Accepted

**Context**: A manual "type a customer id" control invited exactly the
kind of arbitrary cross-customer access a real product must not allow,
and existed only as a workaround for an incomplete login→customer
association.

**Decision**: Every successful authentication (regular sign-in or demo)
deterministically resolves exactly one associated customer
(`frontend/src/lib/demo-customer.ts::resolveDemoCustomer`,
`components/login-form.tsx::completeLogin`) before navigating. No
in-app UI lets an authenticated user view or switch to a different
customer's data.

**Consequences**: `frontend/src/providers/customer-context.tsx`'s
`profileId` is the single source of truth every protected page reads,
set only by the login flow, account-creation flow, and sign-out (to
`null`) — never by a page-level control. Inspecting another preserved
demo persona requires the backend's own `/docs` explorer, not the
authenticated app (`reports/live_analysis_flow_fix_report.md`).

---

## ADR-022 — Demo Data Is Synthetic Identity + Real Pipeline Output

**Status**: Accepted

**Context**: A credible demo needs varied, presentable customer stories
without either using real personal data or fabricating results the real
pipeline didn't actually produce.

**Decision**: Every demo persona's *identity* (name, profile fields,
questionnaire answers, goals, financial inputs) is fabricated and clearly
labeled ("WealthPilot Demo — …"). Every *result* (risk category,
behaviour flags, goal feasibility, portfolio weights, compliance
decision, recommendation) is read from a real `POST /api/analysis`
response — never hand-inserted into the database. A demo persona's
risk-relevant transaction history is aliased to one real, anonymized,
already-present FAR-Trans customer via `risk_inputs.external_customer_id`
(the one field with no public API, set by one direct database write in
`backend/scripts/seed_demo_data.py` — the ONLY sanctioned direct write in
that script).

**Consequences**: `scripts/seed_demo_data.py verify` and the `reports/
demo_dataset_catalog.md` catalog are the source of truth for what each
persona's ACTUAL (not merely intended) pipeline result is. No target
result is ever forced; when a target proves structurally unreachable, it
is documented, not worked around (see ADR-018's own history).

---

## ADR-023 — Raw Dataset Immutability

**Status**: Accepted

**Context**: FAR-Trans and Kaggle raw files are the ground truth every
model and every demo persona's risk linkage ultimately traces back to;
mutating them would silently invalidate that traceability.

**Decision**: Nothing under `datasets/raw/` is ever modified by
application code, a training script, or a demo-seeding script. All raw
files are gitignored (`datasets/raw/**`, `.gitkeep` tracked) and treated
as read-only inputs.

**Consequences**: `data/preprocessing.py::load_far_trans_tables` and
equivalent Kaggle loaders only ever read. Any data-quality filtering
(`Predicted_*`/`Not_Available` exclusion — CLAUDE.md rule 7) happens at
feature-engineering time, never by rewriting the source file.

---

## ADR-024 — Customer Data Isolation at the API Layer

**Status**: Accepted

**Context**: Every persisted, per-customer resource (profile,
questionnaire answers, goals, financial inputs, analysis runs) must be
scoped correctly so one customer's request can never read or write
another's data.

**Decision**: Every per-customer route is path-scoped by `profile_id`
(`/api/profiles/{profile_id}/...`) and every query filters by that id at
the ORM level — never a global/unscoped query that a caller narrows
client-side.

**Consequences**: Verified by test for every persistence endpoint added
since Phase 23 (questionnaire, goals, and — Phase 28 — financial inputs),
each with its own "isolated per customer" test. This is a data-isolation
guarantee, not an authorization one — see ADR-020: the prototype has no
concept of "this authenticated user owns customer N," only "customer N's
resources are scoped to customer N."

---

## ADR-025 — One Financial-Input Data Contract Table, Not New `customers` Columns (Phase 28)

**Status**: Accepted

**Context**: Emergency-fund and goal-assumption inputs
(`monthly_essential_expenses`, `current_liquid_assets`,
`contribution_amount`, `annual_return_rate`, `annual_inflation_rate`,
`contribution_periods_per_year`) had no home anywhere in the schema.

**Decision**: A dedicated `financial_inputs` table (one row per customer,
every field independently nullable — `NULL` means "not yet provided",
never `0`), not new columns on `customers` — matching the existing
`financial_goals`/`questionnaire_answers` pattern of one table per
persistence concern.

**Consequences**: `GET`/`PUT /api/profiles/{id}/financial-inputs`
(upsert/merge semantics). `analysis_service.py::compute_profile_hash`
includes this table's content, so editing it correctly invalidates any
previously cached analysis result. See `reports/
phase28_financial_input_savings_first_report.md`.

---

## ADR-026 — Goal Monte Carlo's Historical-Return Series: Equal-Weighted `market_data` Blend (Phase 28)

**Status**: Accepted

**Context**: `core/goals.py::run_goal_monte_carlo` requires a
`historical_returns` array to bootstrap from, but no customer-specific
portfolio exists yet at the point `goal_analyst_node` runs in the graph
(it runs before `portfolio_manager_node` — see `docs/ARCHITECTURE.md`
§10), so there is no "this customer's own allocation" return series
available. No authoritative document specifies which series to use in
this situation — a genuine, if narrow, judgment call.

**Decision**: Source it from the real, already-approved `market_data`
table via `agents/nodes.py::load_portfolio_returns` (the SAME function
`portfolio_manager_node` itself uses, made public for this second caller
rather than duplicated), blended at equal weight across the approved
`ASSET_UNIVERSE` (`core/optimizer.py::equal_weight_portfolio`) to produce
one period-return series.

**Consequences**: This reuses only already-approved Phase 6/8 building
blocks (real market data, an already-approved equal-weight strategy) —
never a new data source and never a new formula. It is documented here
explicitly, rather than silently chosen, precisely because it is a
judgment call and not a directly-specified requirement; a future review
could revisit it (e.g. to use the customer's actual risk-conditioned
strategy once one is known) without that being a silent, undocumented
change. See `reports/phase28_financial_input_savings_first_report.md`
§9.

> **Note (added Phase 29):** the series choice recorded here stands, but
> Phase 28's implementation of it omitted a required frequency-alignment
> step — see ADR-027, which corrects that defect.

---

## ADR-027 — Historical Returns Are Compounded to the Goal's Period Frequency; Pipeline Version Is Part of the Cache Key (Phase 29)

**Status**: Accepted (corrects the implementation of ADR-026)

**Context**: Phase 29's end-to-end validation found every demo goal
showing a 0.0% Monte Carlo success probability ("Not Feasible"), even a
Retirement goal whose deterministic contribution gap was *negative* (plan
ahead of the required contribution). Cause: `core/goals.py::
run_goal_monte_carlo` draws one return per contribution **period**
(`balance = balance*(1+r) + contribution`, `n_periods` times), but Phase
28 passed it the raw **daily** blended series — so with the default 12
periods/year a ~0.04% daily return was applied once per month, understating
growth ~20x. Reproduced directly on the real data: same goal, 0.0% as
supplied vs 94.1% once the series was compounded to monthly periods
(1,176 daily observations, 279 monthly periods). The earlier Phase 28
statement that these "Not Feasible" results were honest was therefore wrong.

**Decision**: (1) `analysis_service.py::_compound_to_period_returns`
compounds the equal-weighted daily series into non-overlapping blocks of
`round(TRADING_DAYS_PER_YEAR / contribution_periods_per_year)` trading days
(`prod(1+r)-1`), dropping the oldest remainder so recent history is fully
used; the series is only built when `GoalAssumptions` exist, and is `None`
(feasibility stays honestly unavailable) if too short for one period.
`core/goals.py` is unmodified — this is input alignment, not a change to
any formula, and uses the existing `TRADING_DAYS_PER_YEAR` constant.
(2) `ANALYSIS_PIPELINE_VERSION` is now part of `compute_profile_hash`,
because the cache key covered a customer's *inputs* but not how the
pipeline turns them into results — without this, the corrected
computation would never reach anyone whose analysis was cached under the
old behaviour.

**Consequences**: Goal feasibility now agrees in direction with the
deterministic TVM (e.g. demo Retirement 94.1% Feasible; House Purchase
50.3% At Risk with a positive contribution gap). Phase 14's goal-preference
layer consumes the corrected signal (rationale text changed from "Not
Feasible" to "At Risk" for the Complete persona) without changing any
selected strategy or terminal status — risk suitability still decides.
Bump `ANALYSIS_PIPELINE_VERSION` whenever a change alters what the
pipeline computes for unchanged inputs. Historical `AnalysisRun` rows
computed under the defect remain in the database (analysis ids 150/151/
152/153 for the demo personas, superseded by 165-168); the frontend only
ever requests the current cached run via `POST /api/analysis`.

---

## ADR-028 — `GoalAssumptions` Are Constructed Only When Every Required Input Exists (Phase 28)

**Status**: Accepted

**Context**: `core/goals.py::GoalAssumptions` deliberately has no default
for `contribution_amount`, `annual_return_rate`, or `annual_inflation_rate`
(zero inflation or zero return are valid, explicit choices the caller must
make). `financial_inputs` stores each of these independently nullable
(ADR-025), so a customer can legitimately supply some but not all.

**Decision**: `analysis_service.py::_build_goal_assumptions` builds a
`GoalAssumptions` object only when all three are present. If any is
missing, no assumptions object is built at all — never a partially-filled
one, never a defaulted rate, never a `0` standing in for "unknown."
`contribution_periods_per_year` is the one field with an existing engine
default (12), so it is passed through only when the customer supplied it.
The emergency-fund inputs (`monthly_essential_expenses`,
`current_liquid_assets`) are independent of this and flow through on their
own.

**Consequences**: A customer who enters expenses and liquid assets but no
return/inflation assumptions still gets a real emergency-fund assessment
(and therefore a real savings-first or approved path), while each goal
honestly reports "no GoalAssumptions (contribution/return/inflation)
supplied" instead of a guessed feasibility. The historical-return series
(ADR-026/ADR-027) is likewise only built when assumptions exist.


## ADR-029 — Analytics Charts Are a Display-Only Layer in `components/charts/` (Phase 30)

**Status**: Accepted

**Context**: Phase 30 added graphs to the frontend. The project's rule
(ADR-014, CLAUDE.md section 6) is that the backend is the only numerical
authority and React only formats. A chart is the easiest place for that
rule to erode: a bar of "shortfall", a normalised donut, a "score", or a
frontier drawn from frontend-invented points would each quietly introduce
a second calculation path.

**Decision**: Every chart is a presentational component in
`frontend/src/components/charts/` that receives already-computed API values
as typed props and plots them unchanged, using Recharts (already
approved; no library was added). A chart component makes no API call and
contains no financial, ML, recommendation or compliance logic. A value the
API returns as `null` is shown as an unavailable state with the API's own
reason — never as `0`, an empty series or a zero-length bar. Each chart
keeps a textual equivalent (an existing table or stat text on the same
page) plus an `aria-label`, so no chart is the only representation of a
number and no series is identified by colour alone. Concretely:

- Risk class probabilities, emergency-fund required/current, goal target vs
  inflation-adjusted target, portfolio weights, scenario return/volatility/
  Sharpe and the SSE step list are the only things plotted; each maps to
  exactly one API field (see `docs/DESIGN.md` section 16).
- The emergency-fund **shortfall** is displayed as the backend's own
  `shortfall` value beside the chart, never as `required - current`.
- Quantities in different units are never put on one axis (goal amounts vs
  monthly contribution vs probability; return/volatility vs Sharpe).
- The Agent Activity pipeline view draws only the SSE events actually
  received, in arrival order. It holds no model of the pipeline's topology,
  so it cannot imply that a skipped stage (portfolio optimisation on a
  savings-first run, recommendation/explanation on a rejected run) ran.
- A risk/return chart and an efficient-frontier chart were deliberately
  **not** built: the API exposes a single portfolio point, not frontier
  data, and drawing a frontier would mean inventing points in the frontend.

**Consequences**: No backend, schema or migration change was needed. The
only frontend logic beyond formatting is a sign test (`contribution_gap <
0`) that selects the presentation note "Contribution exceeds the calculated
requirement." — `core/goals.py` documents the gap as required minus planned
contribution, so a negative value means the plan is ahead, and the value
itself is displayed unchanged. Recharts 3 draws no SVG during a server
render, so chart *drawing* cannot be checked without a browser; data
binding is verified instead by rendering the real page components against
real API responses with the Recharts primitives replaced by data-capturing
stubs (see `reports/phase30_analytics_visualization_report.md`).


## ADR-030 — The Seeded Primary Demo Persona Wins Over a Remembered Fallback Customer (Phase 31)

**Status**: Accepted (refines the resolution order in ADR-021's
`resolveDemoCustomer`; supersedes the "reuse the remembered id first" rule
the Live Analysis Flow phase kept from Phase 24)

**Context**: `resolveDemoCustomer` used to try the browser's remembered demo
id first and accepted it if the customer's name was *either* demo name.
A browser that had ever resolved to the blank, FAR-Trans-unlinked
"WealthPilot Demo Customer" (this environment has such a browser: it created
customer 29101) therefore kept resolving to it, even after the linked
"WealthPilot Demo — Complete" persona was seeded — so "Use Demo Account"
landed on `pending_information` instead of the primary successful demo.
Which customer the demo shows depended on that browser's history, which is
not deterministic.

**Decision**: The order is now (1) the seeded "Complete" persona, found by
exact name through `GET /api/profiles/lookup` (lowest id wins when a name
repeats, ADR-027's sibling fix in Phase 29); (2) only if it is not seeded,
a remembered id that still resolves to a known demo name; (3) only if
neither exists, find-or-create the Phase 24 canonical customer. Nothing
about the backend, the schema or the persona data changed, and the extra
duplicate customer 29101 was left in place.

**Consequences**: With the primary persona seeded, "Use Demo Account" and a
regular Sign In reach the same customer in every browser. The per-browser
idempotency limitation from Phase 24 now applies only to an unseeded
environment. The scenario is covered by a scratch check of the real
`demo-customer.ts` against a stubbed API (six scenarios, all passing);
the project has no frontend test runner and none may be added.


## ADR-031 — Household Is a Separate Entity Linked by Membership, Not a Replacement for Customer (Phase 32)

**Status**: Accepted

**Context**: The project's architecture is customer-centred: a customer's
transaction history feeds the risk and behaviour models, their goals and
financial inputs feed the goal engine, and the whole individual pipeline
(`POST /api/analysis`) is keyed by customer. A family-level view — several
people, later shared income, expenses, goals and an emergency fund — is a
legitimate next direction, but the obvious shortcuts would damage what exists:
renaming or replacing `customers` with a household, or bolting household columns
onto it, would corrupt the FAR-Trans customer architecture (the risk model's
whole training population is individual customers), invalidate the individual
analysis, and force a migration of every existing per-customer table.

**Decision**: A household is a **new entity** (`households`) linked to customers
only through a **membership** table (`household_members`):
`Customer -> Household Membership -> Household`. `customers` and every table that
references it are unchanged. A membership carries a controlled `relationship`
(self, spouse, parent, child, sibling, other), a controlled `role` (primary,
member, dependent) and a derived `is_dependent`. The rules are enforced by the
database (one household per customer; one primary per household; primary implies
`self`; `self` is never a dependent; `is_dependent` equals `role = 'dependent'`)
and again in the service; "at least one primary" is transactional (the primary is
created with the household and is never removable). The household is **contextual
only**: it carries no financial column, no route computes anything about it, and
`POST /api/analysis`, the financial-input endpoints and the recommendation
precedence are unchanged and provably unaffected (regression tests compare the
analysis body and the cache key before and after membership).

Two smaller decisions:

- **Identity for authorization.** The backend has no server session, so household
  routes take the caller's associated customer as an explicit `X-Customer-Id`
  header and authorize against membership (non-member 403, unknown household
  404, missing identity 401; only the primary adds or removes members). This is
  the existing prototype-auth model made explicit for the first routes that need
  it, not a new auth system: the header is asserted, so it stops accidental or
  URL-edited cross-household access but not a malicious client
  (`docs/SECURITY.md`).
- **Uniqueness.** `UNIQUE(customer_id)` alone gives both "one household per
  customer" and "a customer cannot appear twice in the same household"; a second
  `UNIQUE(household_id, customer_id)` would be strictly redundant, so it is
  omitted. If a later phase allows several households per customer it must add
  that constraint then.

**Consequences**: A later household financial layer (household income, expenses,
assets, liabilities, shared goals, household emergency fund) can be built on the
membership graph without touching the individual pipeline, the individual models
or the FAR-Trans customer architecture. Phase 32 deliberately implements none of
it and no household deletion route (avoiding accidental loss of future household
data). Known gaps carried forward: adding a member needs no consent from that
customer; primary ownership cannot be transferred; a customer deleted outside the
API (the demo `reset` script) cascades their membership and could leave a
household without a primary.

---

## ADR-032 — Household Financial Data Is Stored Source Data Only, Never Aggregated (Phase 33)

**Status**: Accepted

**Context**: ADR-031 deliberately gave the household no financial column, leaving
"a later household financial layer" as future work. Phase 33 is that layer's
**data foundation** and nothing more: a household needs somewhere to record its
own income, expenses, assets and liabilities. Two shortcuts were available and
both were rejected. The first was to reuse the individual `financial_inputs`
table (or add household columns to it), which would have entangled household data
with the input contract that feeds `POST /api/analysis` — the risk classifier,
goal feasibility, emergency-fund evaluation and compliance gate all read that
table, so any household row reaching it would silently change an individual
customer's analysis. The second was to ship "obvious" conveniences alongside the
storage — a totals endpoint, a household net-worth figure, a savings rate, a
debt-to-income ratio. Each of those is a **financial methodology decision** that
`docs/PROJECT_PLAN.md` does not specify, and inventing one would violate
`CLAUDE.md` §10 and the project's rule that the backend computes only formulas
that already exist in `core/`.

**Decision**: Household financial data lives in **four new, independent tables** —
`household_incomes`, `household_expenses`, `household_assets`,
`household_liabilities` — each owned by a household through `household_id` alone.
None of them carries a `customer_id`: a record belongs to the household, not to
the member who entered it (asserted by a schema test). They are **source records
only**. No total, net worth, savings rate, debt ratio, surplus or per-member
split is computed anywhere — not in the database, not in a service, not in a
route, not in React — and no summary/aggregate endpoint exists (an OpenAPI test
asserts no route path contains `summary`, `totals`, `net-worth`, `savings` or
`debt-ratio`, and a schema test asserts no response model carries a derived
field).

Within that, four smaller decisions:

- **Controlled vocabularies, free-text source.** `frequency`, expense
  `category`, `asset_type` and `liability_type` are fixed vocabularies enforced
  by a CHECK constraint and mirrored as Pydantic `Literal` types, with a test
  asserting the two never drift (the Phase 32 pattern). Income `source` is
  deliberately **free text**: an income source is the household's own
  description, and a fixed list would force a household to misfile its income.
- **NULL is not zero.** `monthly_payment` on a liability is nullable because
  "not provided" and "no monthly payment" are different facts; `is_essential` on
  an expense has **no default** because whether an expense is essential is the
  household's judgement and must never be guessed. The frontend renders a null
  as "Not provided" and a stored `0` as `0`.
- **Where the numbers may be zero.** Income and expense `amount` must be `> 0`
  (a zero-amount income or expense is a data-entry error, not a fact), while
  `current_value` and `outstanding_amount` allow `>= 0` (a fully repaid loan or
  an emptied account is a real, meaningful zero).
- **Authorization reuses Phase 32 unchanged.** Any member may read the
  household's financial records; only the primary may create, update or delete
  one. Identity is the same asserted `X-Customer-Id` header (401 when absent,
  403 for a non-member or a non-primary mutation, 404 for an unknown household).
  A record id belonging to a different household returns **404, never 403** — the
  same convention Phase 32 used for `remove_member`, so an attacker cannot use
  the status code to learn that a record exists. `household_id` is taken from the
  path and is absent from every update schema (`extra="forbid"` makes an attempt
  to send it a 422), so a record can never be re-homed into another household.

**Consequences**: The individual pipeline is provably untouched — the four demo
personas' analysis responses are byte-identical before and after household
financial data exists, and `financial_inputs` is unmodified. A future phase that
genuinely needs a household-level number (a household emergency fund, a shared
goal, a family cash-flow view) must first specify the methodology, then implement
it in `core/` as deterministic logic with its own tests, exactly as the
individual engine was built; it must not be added to a route handler, a response
schema or a React component. Until then the household financial layer is a
record book: it stores what the family entered and shows it back unchanged. The
known gaps carried forward are that a non-primary member can see the household's
full financial detail (there is no per-record visibility control), the asserted
`X-Customer-Id` header remains asserted rather than authenticated, and no
currency field exists — every amount is assumed to be in the single display
currency the rest of the prototype uses.

> **Note (Phase 34)**: the aggregation half of this ADR is superseded by
> **ADR-033**, which adds exactly one read-only aggregation endpoint and the
> deterministic engine behind it. Everything else in ADR-032 still stands
> unchanged: the four tables remain normalized source records, the Phase 33
> CRUD routes still compute nothing, `household_id` is still server-controlled,
> NULL is still not zero, and household financial data still never reaches
> `POST /api/analysis`.

---

## ADR-033 — Household Financial Aggregation Is a Read-Only Derived Layer, Not an Input to Advice (Phase 34)

**Status**: Accepted

**Context**: ADR-032 deliberately stopped at storage: Phase 33 gave a household
four normalized tables and no interpretation of them at all, on the grounds that
any total, ratio or score is a financial-methodology decision that must be
specified before it is implemented. A household that has recorded its income,
expenses, assets and liabilities could nonetheless answer nothing about itself —
not even "what does this household spend each month", because a yearly record
and a monthly record cannot be combined without a stated normalization rule.
Phase 34 supplies exactly the rules that were missing, and nothing more.

The tempting shortcuts were again the dangerous ones. Denormalizing totals onto
`households` would create a second source of truth that drifts the moment a
record is edited. Computing the sums in the route handler or in React would put
financial arithmetic outside `core/`, where it cannot be unit-tested without a
database or a browser, and would let the two halves of the system disagree. And
feeding the household's aggregated figures into `POST /api/analysis` — the
obvious "next step" — would silently change every individual customer's risk,
goal, portfolio and compliance result on the strength of numbers no model was
trained or validated against.

**Decision**: Household aggregation is a **deterministic, read-only derived
layer**. The arithmetic lives in one pure module, `core/household_finance.py`
(no database, no FastAPI, no ML, no LLM, no clock, no network), is orchestrated
by `api/services/household_summary_service.py`, and is exposed by exactly one
endpoint, `GET /api/households/{household_id}/financial-summary`. Nothing is
persisted: a summary is recomputed from the source records on every request, so
it can never go stale. Nothing is wired into the individual pipeline — no
household figure reaches `analysis_service.py`, the risk model, the goal engine,
the optimizer, the compliance gate, AutoGen, Gemini or LangGraph.

The stated semantics, each a decision rather than an obvious default:

- **Monthly normalization.** A `monthly` record contributes its amount; a
  `yearly` record contributes `amount / 12`. A `one_time` record is **never**
  converted into a recurring figure: no amortization period is invented and a
  one-time amount is never assumed to repeat. One-time income and one-time
  expenses are reported as their own separate totals.
- **Active records only.** Income and expenses carry `is_active`; only active
  records take part in any monetary aggregate, while an inactive record stays
  stored and still counts in `record_count`. Assets and liabilities have no
  `is_active` column and none was invented for them.
- **Unknown is not zero, applied uniformly.** A monetary aggregate is `null`
  unless at least one record actually contributes to it. This is one rule, not a
  special case per field: no income records means recurring income is *unknown*,
  and a household whose only income is one-time also has *unknown* recurring
  income, because nothing in this system asks a household to confirm that what
  it entered is complete. Conversely a recorded `0` is a fact — a liquid asset
  worth 0 makes the emergency-fund position known (and insufficient), and a
  liability with `outstanding_amount = 0` makes outstanding liabilities known. A
  liability whose `monthly_payment` is `NULL` contributes nothing to the payment
  total rather than counting as a payment of 0. Every section carries
  `available` plus the project's usual `unavailable_reason` sentence.
- **Derived views require both inputs.** `monthly cash flow` is
  `recurring_monthly_income - recurring_monthly_expenses` and `net_position` is
  `total_assets - total_outstanding_liabilities`; if either side is unknown the
  result is `null`, never a figure computed against an assumed zero. Net
  position deliberately excludes income and expenses, and cash flow deliberately
  excludes one-time records.
- **The emergency fund reuses the individual semantics rather than competing
  with them.** `required = EMERGENCY_FUND_TARGET_MONTHS x recurring monthly
  essential expenses`, importing the same 6-month constant from `core/goals.py`
  and applying the same `current >= required` comparison, with a test asserting
  the household result agrees with `assess_emergency_fund` on the same inputs.
  The individual implementation is untouched. The household version adds one
  state the individual engine never needs — `unknown` — because its caller may
  simply not have the numbers. It is **informational**: it produces no
  savings-first verdict, no recommendation and no compliance decision.
- **Decimal in, float out.** Money is aggregated as `Decimal` (the values come
  from `Numeric(14, 2)` columns) and is never rounded inside the engine;
  conversion to the API's float convention happens once, at the service
  boundary, exactly as Phase 33's record endpoints already do. `yearly / 12`
  therefore keeps full precision rather than being truncated to two decimals.
- **No contribution capacity, and no second goal engine.** Cash flow is reported
  as cash flow and is deliberately **not** named "savings", "savings capacity"
  or "monthly contribution": the project's documented architecture defines
  `GoalAssumptions.contribution_amount` as a user-supplied input, not something
  derived from income minus expenses, and inventing that equivalence here would
  be exactly the kind of unspecified methodology ADR-032 refused. No household
  goal feasibility, Monte Carlo, inflation adjustment or contribution gap is
  computed.
- **Single currency preserved.** No currency field and no conversion was added;
  the project's existing single-currency assumption (EUR, `docs/PROJECT_PLAN.md`
  Part 0) is unchanged.

**Consequences**: A household can now be described factually, and the numbers a
later household-advice phase will need already exist, tested, in `core/`. That
later phase can wire them into goal feasibility, a household risk view or a
household recommendation — but doing so is a separate, explicit decision needing
its own ADR, because it changes what the product *advises*, not merely what it
*reports*. Two Phase 33 guards had to be narrowed rather than deleted: the "no
aggregate route exists" assertion now pins the one permitted route by name, and
the "no derived field" schema check now names the twelve source-record schemas
explicitly instead of matching on a name substring. A third guard, Phase 32's
exact household route inventory, was found **already failing** — Phase 33 had
added eight paths without updating it, and Phase 33's full-suite run never got
far enough to reveal it; it now lists all three phases' routes explicitly. Known
gaps carried forward: any member still sees the whole household's figures; the
summary is recomputed per request from four scoped queries and is not cached,
which is correct but not free on a large household; and the `unknown` state can
surprise a household that believes it has entered everything, since the system
never asks whether a set of records is complete.

---

## ADR-034 — Household Financial Facts Gain Optional Metadata, Not Temporal Validity (Phase 35)

**Status**: Accepted

**Context**: The Phase 35 specification asked for four new household financial
tables, CRUD routes over them, and a Phase 34 summary that reads them. All
three already existed: Phase 33 (ADR-032) created `household_incomes`,
`household_expenses`, `household_assets` and `household_liabilities` with
exactly those sixteen routes, and Phase 34 (ADR-033) made the summary read
those same rows. Creating a second set of tables would have duplicated the
source of truth and orphaned both earlier phases.

The specification also proposed field changes that conflict with accepted
decisions. It asked for a required `effective_date` and optional `end_date`
with a date-window activity rule — but also said to "reuse Phase 34's
target-date convention exactly" and "not redesign temporal semantics", and
Phase 34's convention is the boolean `is_active` with no date at all, inside an
engine ADR-033 guarantees has no clock. It asked for `amount >= 0` where
ADR-032 deliberately chose `amount > 0`, and for a required `monthly_payment`
where ADR-032 made it nullable precisely because "not provided" is not "no
payment" — a distinction the same specification's own NULL-is-not-zero rule
depends on. These conflicts were put to the project owner, who chose: reuse the
existing tables, add only the genuinely missing factual fields, and keep the
existing ADR semantics.

**Decision**: Phase 35 is **additive only**. One migration (`a7c41e9b6f30`)
adds seven optional columns to the four existing tables — `notes` on all four,
`description` on assets and liabilities (matching the `description` expenses
already had), and `interest_rate` on liabilities, as `Numeric(6, 4)` to match
the rate convention of `financial_inputs`, with a non-negative CHECK. Every new
column is nullable with no default, so no existing row needed a backfill and no
value was invented.

- **No temporal validity.** `is_active` remains the activity rule and no date
  column was added. The Phase 34 engine therefore still has no clock and no
  target date, and its output is byte-identical for the same facts.
- **No constraint was weakened.** `amount > 0` and the nullable
  `monthly_payment` stand exactly as ADR-032 set them.
- **Metadata cannot reach the arithmetic.** The engine's input records in
  `core/household_finance.py` have no field for `notes`, `description` or
  `interest_rate`, so none of them can influence a summary figure even by
  accident — a test asserts this, and another asserts two households with
  identical facts but different metadata produce identical summaries.
- **`interest_rate` is recorded, never used.** No debt ratio, amortization
  schedule, payoff date or interest amount is computed from it anywhere.
- **Rates follow the Phase 28 convention**: entered as a decimal
  ("0.0425 means 4.25%"), submitted verbatim with no conversion in React, and
  displayed through the existing `formatPercent`.

**Consequences**: A household can annotate its facts, and the schema now pins a
single linear migration chain with a migration-history test that needs no
database. If date-bounded validity is ever wanted, it is a real semantic change
to Phase 34 — it needs a stated target-date convention (a request parameter,
since the engine may not read the clock) and its own ADR superseding the
activity rule of ADR-033. It is deliberately not implied by anything here.

---

## ADR-035 — Household Goals Are Stored Facts, Separate From Individual Goals, With No Goal Math (Phase 36)

**Status**: Accepted

**Context**: A household needs somewhere to record what it is saving towards —
an emergency fund, a home, education, retirement. The individual pipeline
already has goals (`financial_goals`, keyed by `customer_id`) and a complete
goal engine in `core/goals.py`: time-value-of-money funding, inflation
adjustment, a required contribution, a contribution gap, Monte Carlo
probability and a feasibility label. The obvious shortcuts were to reuse
`financial_goals` for households, or to run household goals through the same
engine. Both fail on the facts. Reusing the individual table would entangle
household goals with the individual analysis that reads it. And the engine
cannot run for a household honestly: `analyze_goal_funding` requires a
`GoalAssumptions` whose `annual_return_rate` and `annual_inflation_rate` have
**no default** by design (the engine refuses to assume them), plus a
`contribution_amount`, a current date and a historical return series. No
household has any of these. ADR-033 already forbade deriving a contribution
from household cash flow, and the household engine may not read the clock.

**Decision**: One new table, `household_goals`, owned by a household through
`household_id` alone (no `customer_id`), entirely separate from
`financial_goals` — neither is ever converted into, merged with, or allowed to
modify the other. It stores **facts only**: `name`, `goal_type`,
`target_amount`, `current_savings`, `target_date`, `notes`, `is_active`. No
derived value is stored or computed — no inflation-adjusted target, required
contribution, contribution gap, probability or feasibility — and `core/goals.py`
is unchanged. The field choices, each deliberate:

- **Mirrored from the individual goal**: `target_amount > 0` and a required
  `target_date`. `current_savings` reuses the individual goal's *name* but is
  **nullable**: the individual column defaults to `0`, which predates
  CLAUDE.md §12, and a household that has not stated its savings must read
  "not provided", not zero.
- **`goal_type` is a controlled vocabulary** (emergency_fund, house, education,
  retirement, travel, major_purchase, other) because individual goal types are
  free text and there is no canonical vocabulary to reuse; `name` carries the
  household's own free-text label, as Phase 33's income `source` does.
- **No `inflation_adjusted` flag.** The individual model has none: inflation is
  always applied through `GoalAssumptions.annual_inflation_rate`, which has no
  default. A boolean switch would be a new financial assumption.
- **No `priority`.** The individual goal carries a user-entered integer that is
  passed through as data but never used in any calculation. Mirroring it would
  add ordering semantics the phase explicitly forbids ("do not rank household
  goals"); goals are listed in `id` order.
- **`is_active`** follows the Phase 33 convention; there is no temporal
  redesign (ADR-034).
- **The emergency fund keeps one source of truth.** An `emergency_fund` goal's
  `target_amount` is the household's own stated target — an input. The
  calculated requirement (`EMERGENCY_FUND_TARGET_MONTHS` × recurring essential
  expenses) stays exactly where ADR-033 put it, in the financial summary; the
  goal never feeds back into it, and the UI shows the calculated figure beside
  the goals for reference, labelled as such.
- **Dates**: any valid calendar date is accepted, mirroring the individual goal
  API. `core/goals.py::validate_goal_for_creation` (future-dated targets only)
  is not applied by either API — an existing gap, recorded here rather than
  silently closed for one side.
- **Validation hardening in the new schemas**: an explicit `null` on a required
  field is a 422 (not a database 500), and every numeric field is finite and
  bounded by its column's storage limit (`Numeric(14, 2)` / `Numeric(6, 4)`) —
  a technical limit, not a financial rule. The same bound was applied to
  Phase 35's own `interest_rate`.

**Consequences**: Households can record their goals, isolated and
authorized exactly like their other records, without any risk to the
individual goal system or the individual analysis. Household goal *math* — a
funding projection, required contribution or feasibility — becomes possible
only once a household has explicit, user-supplied assumptions (return,
inflation, contribution) to feed `core/goals.py` unchanged; that is a separate
decision needing its own persistence and ADR. Two pre-existing defects of the
same class were found and are **not** fixed here, being outside this phase:
Phase 33's record schemas return a 500 for an explicit `null` on a required
field and for a non-finite or out-of-range amount, and Phase 28's
`FinancialInputsUpdate` accepts non-finite values.

---

## ADR-036 — A Second Demo Entry Point Resolves the Canonical Family Household (Demo Experience)

**Status**: Accepted

**Context**: The household features of Phases 32–36 are visible only to a
customer who belongs to a household. The individual demo lands on "WealthPilot
Demo — Complete" (ADR-030), which belongs to none — correctly, since the
individual demo demonstrates one customer's own analysis. A reviewer therefore
had no way to see the household features without the API explorer. ADR-021
allows exactly one associated customer per authenticated session and no in-app
switcher, so the answer could not be a control inside the app.

**Decision**: The login page offers **two demo entry points**, both using the
same prototype credential (ADR-020):

- **"Use Individual Demo"** — the existing resolution, unchanged (ADR-030): the
  seeded "Complete" persona, lands on the Dashboard. (This button was labelled
  "Use Demo Account"; only the label changed.)
- **"Use Family Demo"** — a find-only lookup (`GET /api/profiles/lookup`, never a
  hard-coded id) of "WealthPilot Demo — Savings", the primary member of the
  canonical household "WealthPilot Demo Family", landing on
  `/profile?household=open` with the Household section expanded. An unseeded
  environment gets a clear error, never a fabricated family.

The choice is made **at login**, so every session still has exactly one
customer (ADR-021 is preserved; this is not an in-app switcher). The family is
built by `backend/scripts/seed_demo_data.py setup-family`, **entirely through
the public household API**, reusing two existing personas — "Savings" as
primary (`self`/`primary`) and "WealthPilot Demo — Compliance" as spouse
(`spouse`/`member`) — so no customer record, schema, migration or direct
database write is added (the only direct write is `reset-family`, because no
household-deletion API exists by design, ADR-031). The individual-demo personas
("Complete" and "WealthPilot Demo Customer") are deliberately kept out of every
household, so the individual demo is unchanged. The household's records are
synthetic, household-level demo values: never training data, never an input
to any individual analysis, never used to infer an individual figure. The
header badge reads "Family Demo" during a family session — a label only.

**Consequences**: A reviewer can demonstrate individual analysis and household
context side by side, each from its own entry point. "Savings" (29099) is now
reachable in-app through the family demo, including its own individual pages —
its own data, which it may see; "Compliance" (29100) remains reachable only
through `/docs`. The household view shows the spouse's name, relationship and
role only, never their profile, analysis or financial data (Rule 31). No
dependent member was added: it would need a new customer record, and the
dependent role is optional for this demo. The persona `reset` now removes the
family household first, so deleting the personas never orphans it. The
household still has no risk score, portfolio or recommendation (ADR-033/035).

---

## ADR-037 — Plain-Language Explanations Are Presented From Deterministic Results; the AI Only Words Them

**Status**: Accepted. Implementation status, 2026-09-30: the frontend part (the
Simple / Detailed views) is implemented. The backend part is prepared but **not
yet applied**: the prompt wording, the stricter validation, the plainer fallback
and the grouped-amount parsing. The full-suite run required before applying it
was interrupted on 2026-09-27 at 51%, so its validation never completed. The
decision below is unchanged.

**Context**: The Why This Recommendation page showed Gemini's section prose —
or, whenever Gemini is unavailable or out of quota (the usual state of this
environment), a templated restatement such as "Behaviour drift flag: False …
Sharpe ratio 1.062…". Neither was written for a reader with no financial
background. Two facts constrained the fix. Every analysis, **its explanation
text included**, is stored in `analysis_runs.result` and served from cache while
the profile is unchanged, so changing what Gemini returns would reach no
existing analysis (including all four demo personas) unless the cache were
invalidated — recomputing every analysis and changing their ids. And adding
required fields to the explanation API schema would break the validation of
every cached result.

**Decision**: Three layers, each with one job:

- **Backend = the source of every number and decision** (unchanged): models,
  `core/` rules and the compliance gate compute everything.
- **Gemini = wording only.** Its prompt now also asks for plain language —
  short sentences, everyday words, any technical term explained in the same
  sentence, acronyms only next to their full name, and every value restated
  exactly as given, never re-rounded or converted — while every original safety
  rule stays verbatim. Its output is still validated against the source values,
  and validation is **stricter**, never looser: a percentage written beside a
  ticker must be that ticker's own weight ("45% in QQQ" is rejected when QQQ is
  55%, although 45 exists in the source), and converting a value into a derived
  count ("94 out of 100") is rejected. A thousands-grouped amount is now read as
  one number: the old pattern read "30,000" as "000" = 0, so an invented
  "₹30,000" passed whenever any source amount was 0, and an honest "4,000" was
  rejected whenever none was. The templated fallback states the same
  values in plainer words (e.g. "No unusual change in your recent investment
  behaviour was detected" instead of "Behaviour drift flag: False").
- **Frontend = presentation.** The page opens on a **Simple** view
  (`components/explanation/plain-language-explanation.tsx`) built from the
  deterministic fields every analysis — cached ones included — already carries:
  a summary chosen by the overall status, the emergency fund, each goal, the
  investment plan, why this result, important points, next steps, a glossary of
  only the terms involved, and the disclaimer. Every figure is an API value
  passed through the existing formatters; the sentences are fixed wording keyed
  on backend statuses and flags. It makes no calculation, comparison, ranking or
  recommendation of its own, and developer-worded backend reasons appear only as
  a "technical detail" line. The existing Gemini/fallback prose and
  deterministic-factors card are unchanged in a **Detailed** view; switching
  views makes no extra AI call.

**Consequences**: Every analysis, including all cached demo analyses, is readable
immediately, and no analysis is recomputed. Gemini's plainer wording and the
plainer fallback apply to analyses computed from now on. The Simple view's fixed
wording must stay a faithful statement of the backend field it is keyed on;
adding a sentence that compares two values, or that states a figure the API does
not return, would break this ADR and CLAUDE.md section 6.

---

## ADR-038 — The Demo Population Lives in `demo_data/` and Is Seeded Only Through the Existing Seed Script

**Status**: Accepted

**Context**: The demo population was written inline in
`backend/scripts/seed_demo_data.py`: three personas and the family household.
The pending-information persona ("WealthPilot Demo Customer", 29096) existed
only as constants in the frontend fallback (`lib/demo-customer.ts`). In an
environment where "Complete" is seeded, that fallback never runs, so nothing
would create persona D. The dataset also lacked:

- a machine-readable package;
- a manifest or a validator;
- recorded scenario inputs and expected outcomes.

A complete, deterministic, synthetic demo dataset was requested. It had to be
kept apart from the training data and consumed by the same application logic.

**Decision**:

- **Single source.** A top-level `demo_data/` folder is the only source of the
  demo population.
  - Files are JSON, the API's own format. Each file wraps exactly one API
    request payload (`profile`, `answers`, `financial_inputs`, `goals`,
    `records`) in dataset metadata that is never stored.
  - No numeric id is stored: personas are found by exact name.
  - No computed value is stored. The application computes every result when
    the data is seeded and analysed.
  - `expected_results/` records only contract-level states: statuses, flags
    and triggered rule ids.
- **Same seed.** The existing seed script reads the folder through
  `backend/scripts/demo_data_package.py`. There is no parallel backend. It
  stays API-only except for the one documented `risk_inputs` write.
  - Loading the data this way is proven equal to the former inline
    constants.
  - `setup` also seeds persona D: find-or-create, with the frontend fallback's
    identical values, which a test checks. `reset` never deletes D.
  - Every mode accepts `--in-process`.
  - `verify` compares every stored value exactly, and each analysis with its
    expected states.
- **Validator.** `backend/scripts/validate_demo_data.py` is static and uses no
  database.
  - It checks the files against the real API request schemas, rejecting fields
    those schemas do not define.
  - It checks references, uniqueness and the household rules.
  - It checks answers against the live questionnaire and each persona's own
    position rule.
  - It checks that no training or application code reads the folder.
  - It checks a generated manifest: no timestamp, and a content hash as the
    deterministic identifier.
  - It checks a SHA-256 guard over the raw training files.
  - It exits 1 on any failure.
- **Scenarios.** They use only the existing simulator contract, which varies
  the portfolio strategy alone. The four what-ifs that contract cannot express
  are listed with the reason, not built: lower or higher contribution,
  increased expenses, and a changed goal date.
- **No synthetic transactions.** Risk and behaviour features read only the
  FAR-Trans CSVs, so synthetic rows would be inert.

**Consequences**:

- Demo data is edited in one place, and the manifest must then be regenerated
  (`--write-manifest`); the validator enforces this.
- The dataset depends on the questionnaire definition and on the FAR-Trans
  customer ids it links to. The validator checks both.
- Persona D's values exist in two places: the dataset and `demo-customer.ts`.
  A test keeps them equal.
- The development database's pre-existing duplicate "WealthPilot Demo
  Customer" (29101, ADR-030) is reported by `verify` as a note and left in
  place.

---

## ADR-039 — A Synthetic ML Training Dataset in `datasets/generated/`, Readable by the Existing Pipelines

**Status**: Accepted (decisions confirmed by the project owner, 2026-09-30)

**Context**: A large synthetic training dataset was requested, targeting
100,000 customers, 2 million or more transactions and 300,000 or more goals,
with targets for risk, expense segmentation, behaviour anomalies and goal
feasibility. Inspection showed five conflicts with the existing architecture:

- The requested schema is not what the existing training scripts read. Risk
  and behaviour pipelines read FAR-Trans files, and expense reads the Kaggle
  file.
- It joins risk and expense data on one population. ADR-010 keeps FAR-Trans
  and Kaggle separate.
- Expense segmentation (K-Means) and behaviour detection (Isolation Forest)
  are unsupervised, so they have no targets.
- Goal feasibility has no ML model. It comes from a 10,000-path Monte Carlo.
- A 2-million-row CSV exceeds GitHub's 100 MB per-file limit.

**Decision** (each option chosen by the owner):

- **Both shapes.** The generator writes the requested joint dataset
  (customers, transactions, goals) and the same population in the FAR-Trans
  format (`far_trans_format/`) and the Kaggle format (`kaggle_format/`).
  - The existing loaders read these copies through their existing
    data-directory argument, so no training code changes.
  - All three are views of **one synthetic population**. This is not a
    linkage of the real FAR-Trans and Kaggle datasets, which stay separate as
    ADR-010 requires.
- **Planted ground truth.** `expense_segment` and `behavior_anomaly` are drawn
  from documented hidden variables *before* the observed columns they shape.
  They are for evaluating the existing unsupervised models, not new production
  targets. `risk_label` comes from hidden risk appetite, capacity and horizon
  plus label noise.
- **The production goal engine, with fewer paths.** `goal_feasibility` comes
  from `core/goals.py` (`analyze_goal_funding`, `run_goal_monte_carlo`,
  `classify_feasibility`).
  - It uses 500 paths per goal instead of 10,000, recorded in the metadata.
  - Its return series is built the way the application builds its own, using
    `_compound_to_period_returns`.
  - The emergency-fund requirement comes from `assess_emergency_fund`.
  - No financial rule is re-implemented.
- **The CSVs are git-ignored.** Only `datasets/generated/**/*.csv` is ignored.
  The generator, validator, README and metadata are tracked, and the CSVs
  regenerate byte-identically from seed 42.

**Consequences**:

- `datasets/generated/` is a new, git-ignored data location. `datasets/raw/`
  remains the only place for downloaded source data.
- The dataset is **not wired into any training script**. Training on it would
  be a new decision.
- The Kaggle-format copy holds EUR amounts under the format's fixed `_usd`
  column names. There is no conversion, and it is documented. The expense
  model uses only ratios.
- `scripts/validate_synthetic_training_dataset.py` must pass. It re-derives
  every sum and ratio, re-checks point-in-time behaviour features, re-runs a
  sample through the production goal engine, applies leakage limits, and runs
  the existing loaders and feature code on the format copies.

---

## ADR-040 — Demo Account Reset: New Canonical Ids, Anomalies Removed

**Status**: Accepted (decisions confirmed by the project owner, 2026-10-04)

**Context**: An audit of live demo data found two anomalies accumulated over
prior sessions, both already disclosed elsewhere: the ADR-030 duplicate
customer 29101 ("WealthPilot Demo Customer", created by the frontend's
own-name-lookup fallback), and a stray household (id 7, name "TEST") with no
seed-script origin. The owner approved a full reset-and-reseed over a
narrower in-place fix, keeping the proven architecture (four individual
personas + one household built from two of them, ADR-036) but assigning new
database ids rather than reusing the old ones, and removing both anomalies.

**Decision**:

- Deleted, by exact id and in dependent-table-first order (the same pattern
  `seed_demo_data.py reset`/`reset-family` already use): customer 29101,
  household 7, then the three owned personas (old ids 29098/29099/29100) and
  the old family household (old id 6). Persona D ("WealthPilot Demo
  Customer", the Phase 24 canonical fallback target) was left untouched
  throughout, at its existing id 29096.
- Reseeded through the existing `seed_demo_data.py setup`/`setup-family`
  unchanged — no new seeding mechanism. New ids: customer 29107 ("WealthPilot
  Demo — Complete"), 29108 ("WealthPilot Demo — Savings", household primary),
  29109 ("WealthPilot Demo — Compliance", household member); household id 8
  ("WealthPilot Demo Family").
- Added a third goal to persona A/29107 (House Purchase) and a fourth goal to
  the family household (a "retirement"-typed long-term family wealth goal),
  both within the existing `GoalCreate`/household-goal schemas — no schema
  change, no new field.
- Idempotency re-verified independently of the seed script's own reporting:
  a second `setup`/`setup-family` run created zero rows, and a direct
  `GROUP BY name HAVING count(*) > 1` query over demo-named customers
  confirmed no duplicate was recreated.

**Consequences**:

- Every reference to the old ids (29098/29099/29100/29101, household 6/7) in
  *active* documentation (`docs/MEMORY.md`, `docs/demo_runbook.md`,
  `docs/final_demo_script.md`, `docs/final_viva_talking_points.md`) and in
  `demo_data/wealthpilot_complete_demo_dataset.csv` was updated to the new
  ids. This ADR and ADR-030/036, which narrate what happened with the old
  ids at the time, are left as historical record and are not rewritten.
- `demo_data/manifest.json` was regenerated (`validate_demo_data.py
  --write-manifest`) after the two new goal records were added.
- No calculation, schema, model, compliance rule, or API contract changed.
  The two new goals are computed by the real goal/Monte-Carlo and household
  summary engines exactly like every other demo record.

