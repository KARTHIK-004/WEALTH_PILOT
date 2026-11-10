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



## ADR-041 — The Demo Dataset Is Replaced by One Meaningful Canonical Dataset (Rupees)

**Status**: Accepted (instructed by the project owner, 2026-10-06)

**Context**: The demo inputs were not a believable financial story. Incomes
were small, the family's primary and spouse were 29 and 58, the Compliance
persona had no financial information at all, the questionnaire answers were
chosen by position ("first option", "middle option"), and the CSV and README
still said EUR although the application has displayed rupees since
2026-10-03. The owner asked for one canonical set of coherent, human-plausible
inputs while leaving every calculation, model, rule and schema alone.

**Decision**:

- **Inputs only.** `demo_data/` was rewritten: realistic rupee incomes (₹8.4L
  to ₹14.4L), essential spending, savings, monthly investment and goals for the
  four personas, and a two-earner family (two net salaries, rent, school fees,
  a car loan, six assets, five goals, essential spending above ₹83,333 a month
  so the emergency target exceeds ₹5,00,000). No computed result is stored; the
  application computes them all.
- **Questionnaire answers are curated per persona** to fit the profile and the
  risk category the model assigns, instead of a position rule. The files carry
  `complete` and `answers_basis`; only the pending persona may leave questions
  unanswered (16–25). The answers are stored but no analysis step reads them.
- **Compliance persona uses the one rule an input can trigger.** Of the five
  rules in `config/compliance_rules.yaml`, four check the optimizer's own
  weights and cannot be driven by a customer input. `emergency_fund_savings_first`
  fails closed when the emergency-fund position is unknown, so persona C omits
  its monthly essential spending and easy-access savings and provides the rest.
  No rule was added, removed or changed (ADR-018 untouched).
- **Pending persona** keeps its real mechanism (no linked trading history, so no
  risk label) and its questionnaire is intentionally partial.
- **The validator checks plausibility**, not only shape: income range, essential
  spending as a share of income, a fundable monthly investment, savings that
  agree with the expected emergency-fund position, goals that are not
  placeholders, household spending within household income, and that each
  persona's inputs can actually cause its demonstrated outcome through an
  existing rule.
- **Reset and reseed.** The four old demo customers (29096, 29107–29109) and
  household 8 were deleted in one transaction after verifying each id and name,
  with the deleted row counts compared against a before-snapshot and a
  fingerprint of all 29,090 non-demo customers compared before and after. The
  data was re-created through the unchanged seed script under new ids: 29110
  (Complete), 29111 (Savings), 29112 (Compliance), 29113 (Pending) and
  household 9.
- **Currency.** The CSV's `currency` label and the demo README now say INR, as
  the UI has displayed since 2026-10-03. No currency is stored anywhere and
  nothing is converted; the research datasets keep their own currency.
- **Dashboard wording.** The dashboard's two unavailable states (emergency
  savings, risk profile) now pass the same plain-language message the Financial
  Health and Risk pages already use, because the raw backend reason leaked an
  internal field name and overflowed on a phone for the Compliance persona. No
  value, calculation or API field changed.

**Consequences**:

- `demo_data/wealthpilot_complete_demo_dataset.csv` was regenerated from the
  live application (`scripts/validate_demo_dataset.py --regenerate`); nothing
  in it is typed by hand.
- The frontend's unseeded-database fallback (`lib/demo-customer.ts`) now creates
  the new Pending profile and goals; its middle-option questionnaire is a
  fallback only and is not compared with the dataset.
- Individuals have no asset or liability records in the schema, so those exist
  only for the household.
- No model, calculation, recommendation or compliance logic, schema, API
  contract or raw dataset changed.


## ADR-042 — Optional Monthly Financial Records and Behaviour Features (Research Enhancement Track B1)

**Status**: Accepted (inputs approved by the project owner, 2026-10-12)

**Context**: The research track needs the customer's own monthly income, spending,
saving and investing, which the application never stored. An individual has one
annual `income`, and a single `financial_inputs` snapshot that the goal and
emergency-fund engines read (ADR-025). Neither is a monthly observation, neither
says whether income is net or gross, and neither separates saving from investing.
Reinterpreting them would silently change existing meaning, so a new, additive,
period-aware store was needed.

**Decision**:

- **A new table, `monthly_financial_records`** (one persistence concern, ADR-025's
  pattern), one row per customer per calendar month. `period_month` is the first
  day of the month; `(customer_id, period_month)` is unique, so a month is stored
  once and a correction updates it. Existing tables, rows and the analysis cache
  key are untouched.
- **Definitions (rupees per calendar month):** `income` is money received, with an
  optional `income_basis` of `net` or `gross` that is never assumed; `expenses` is
  living costs and excludes money moved to savings or investments; `savings` is
  money newly set aside; `investment_contribution` is money newly invested. The
  three outflows are disjoint, and a transfer from savings into an investment is
  neither new savings nor new income, which prevents double counting. Expenses are
  not split into essential and discretionary; `financial_inputs.monthly_essential_expenses`
  keeps its own meaning.
- **Optional and honest:** every amount is nullable. `NULL` is "not reported", never
  0; a stored 0 is a value the customer entered. A record must hold at least one
  amount, and an income basis requires an income. Amounts are non-negative, finite,
  at most two decimal places, and must arrive as JSON numbers; strings, booleans
  and malformed formats are rejected, not coerced.
- **Corrections:** `PUT` merges; an omitted field keeps its value and an explicit
  `null` clears it. A month may be deleted. A future month, or one before 2000, is
  rejected. A missing month is simply absent; it is never filled in.
- **Currency:** none is stored, consistent with the rest of the application (the UI
  presents rupees). The feature module refuses to combine mixed currencies.
- **Features (`core/behaviour_features.py`, set `behaviour_features_v1`):** pure and
  deterministic. Ratios (expenses, savings and investments to income) use the same
  month's income and are unavailable, with a stated reason, when income or the
  numerator is missing or income is zero. A change compares the latest month with
  the immediately previous calendar month and is unavailable if that month is
  absent or either value is unknown. Consistency is the share of known months with
  an amount above zero, over the 12 months ending at the latest report, and needs
  at least 3 known months; unreported months are not counted as zero activity. A
  flag, not a correction, notes when the latest month's outflows exceed income.
  `CONSISTENCY_WINDOW_MONTHS = 12` and `MIN_CONSISTENCY_OBSERVATIONS = 3` are
  feature-construction parameters, not financial thresholds.
- **Not sentiment.** The features are ratios and changes of reported amounts. They
  do not describe emotion or psychology, and they do not imply any holding.
- **Not consumed.** No analysis step, recommendation, optimizer, compliance rule or
  model reads these records or features. `GET /api/profiles/{id}/behaviour-features`
  is read-only and carries `model_version` and `data_source`.

**Consequences**:

- Migration `e5b1c7d93a20` is additive and reversible (verified up, down and up on
  the test database; applied to both databases; no drift).
- A new formula needs an ADR (`CLAUDE.md` section 10); this is that ADR for B1's
  ratios, changes and consistency.
- The monthly records are sensitive: they are never logged by the service, never sent
  to a ledger, an external provider or an LLM, and the repository gives no encryption
  at rest, so none is claimed.
- The prototype has no per-account authorisation (ADR-020): like every
  `profile_id` route, these are scoped by customer id, not authorised.
- Using the features in any recommendation or model is a later, separately approved
  step.

## ADR-043 — Financial Behaviour Findings and Optional User-Text Sentiment (Research Enhancement Track)

**Status**: Accepted for the display-only baseline described here (project owner request, 2026-10-20). The text-reading method is an UNVALIDATED baseline; no model is approved.

**Context**: ADR-042 added the customer's own monthly records and read-only behaviour features, consumed by nothing. The next step is to explain those facts in words, and to let a
customer who chooses to write how they feel about their finances see how that reads, without letting either change a risk profile, goal or recommendation.

**Decision**:

- **Findings (`core/behaviour_findings.py`, `behaviour_findings_v1`)**: restate the ADR-042 features as observed facts. No new formula and no threshold: a direction is the sign of an
  existing month-on-month change; "above zero in k of n reported months" restates the existing consistency feature. No judgement words ("overspending", "distressed", "irregular") are
  produced, because they would need a threshold no approved document defines (`CLAUDE.md` section 10). Debt/EMI (no such amounts are stored) and goal progress (the existing goal
  engine's job) are reported `not_included`, never zero. Missing stays missing.
- **User-text reading (`core/user_text_sentiment.py`, `user_text_rules_v0`, `UNVALIDATED_BASELINE`)**: a deterministic, offline rules baseline over a small English cue list. Taxonomy:
  `sentiment` positive | negative | neutral | mixed | uncertain; `emotional_tone` concerned | hopeful (explicit cue words only); `topics`; `preferences`
  (capital_preservation, growth_seeking, liquidity_access, debt_reduction; each `unconfirmed` and `requires_confirmation`); short `evidence` phrases; `confidence` always `null`
  (uncalibrated). No text is `unavailable`, never neutral; text with no recognised cue is `uncertain`; negated cues are dropped. Emotional tone is a separate field from preferences and is
  not a risk tolerance. No model, package, network or LLM is used, so the text never leaves the process and nothing is licensed, downloaded or installed. A transformer or any trained
  model remains blocked on licensing, an independently labelled user-text validation set, and owner approval.
- **Composition (`core/personalized_insight.py`)**: behaviour is primary; text is optional and secondary. The stored risk assessment (and the questionnaire behind it) takes precedence: a
  preference inferred from text never replaces it, and two unambiguous disagreements (capital preservation vs Aggressive; growth vs Conservative or Income) are reported as a `conflict`.
  Templates only, every statement lists its source fields, the purpose states it is informational and changes nothing.
- **API**: `POST /api/profiles/{profile_id}/personalized-insights` (POST so the text is never in a URL). No database write, no schema change, no migration. The text is analysed in memory,
  never stored, logged, cached server-side or sent anywhere; unusable text (over 1,000 characters, control characters) is a 400 problem response that does not echo it. Scoped by
  `profile_id` like the other per-customer routes (ADR-024/020: data scoping, not authorisation).
- **Frontend**: a "Financial behaviour & sentiment" card on Financial Health renders the response only (no calculation, no inference); the text is held in component state and the query is
  not retained (`gcTime: 0`).
- **Not done / blocked**: persisting or confirming a preference (needs a table, an Alembic migration applied to both databases, and a retention/deletion policy); a multi-line text box
  (the shadcn textarea needs the CLI); an independently labelled user-text validation set and the Baseline A-D comparison (no labels or outcome data exist); any model.

**Consequences**:

- Nothing in `POST /api/analysis`, the optimizer, the recommendation or compliance reads these outputs (ADR-042's rule stays).
- The rules baseline's accuracy is unknown by construction; the UI and API say so, and it must never be described as validated or used to change a profile.
- The English cue list is a methodology choice recorded here, not a financial formula; changing it changes `user_text_rules_v0`.

## ADR-044 — PROPOSED: User-Text Validation Language and Emotional-Tone Policy

> Note (2026-10-23): ADR-050 supersedes ADR-043's single-pass taxonomy and the method version `user_text_rules_v0` in part (see ADR-050); this ADR's annotation proposals remain PROPOSED.

**Status**: PROPOSED (project owner, 2026-10-20). Not accepted and not implemented. ADR-043's taxonomy and `user_text_rules_v0` (`UNVALIDATED_BASELINE`) are unchanged.

**Proposed decisions** (full wording in `docs/USER_TEXT_ANNOTATION_RUBRIC.md` section 8):

- **O5**: for the initial validation, code-mixed or unsupported-language text is labelled `uncertain` and flagged `language`; no automatic translation; the group is reported separately.
- **O6**: allow multiple `emotional_tone` labels, keeping `concerned` and `hopeful` as the initial list; use `ambiguous_tone` when an emotion cannot be reliably assigned; never infer investment
  risk tolerance from emotion.

**If accepted**: a later, scoped change would let `emotional_tone` hold a list, update the schema and generated types, the card, and the tests, and supersede the one-value field in ADR-043.
Until then the one-value field stays and the rubric is the only place the proposal lives. O1-O4 and O7 (consent, de-identification, access, retention, annotators, pilot, sample size) remain open.

**Affected interfaces if O5/O6 are accepted (inspected 2026-10-20; nothing changed):**

- `core/user_text_sentiment.py`: `UserTextAnalysis.emotional_tone: str | None` (one value) and `METHOD_VERSION`.
- `core/personalized_insight.py` (the "wording suggests ..." phrase), `api/services/personalized_insight_service.py` (field mapping), `api/schemas.py::UserSentimentOut.emotional_tone: Literal["concerned","hopeful"] | None`.
- Generated `frontend/src/types/api.ts` (regenerate from OpenAPI) and `components/financial-health/behaviour-sentiment.tsx` (one badge).
- Tests: `test_user_text_sentiment.py`, `test_personalized_insights.py`, `test_user_text_rubric_examples.py`, `test_user_text_pilot_pack.py`; rubric, pilot template and `scripts/pilot_disagreements.py`.

**Future migration plan (PROPOSED, to be scoped after acceptance):**

1. *Compatibility*: additive. Keep `emotional_tone` (set only when exactly one tone is present) and add `emotional_tones: list` and `ambiguous_tone: bool`; add a `language` field for O5. Regenerate OpenAPI types; keep the old field for one release, then remove it in a new ADR.
2. *Versioning*: bump `METHOD_VERSION` (for example `user_text_rules_v1`); `VALIDATION_STATUS` stays `UNVALIDATED_BASELINE` until the approved evaluation (O7) is run.
3. *O5 detection*: the baseline cannot identify an unsupported language today (no language-ID method or package is approved); it returns `uncertain` only when no English cue matches, and can still assign a label from English cue words embedded in code-mixed text (so O5's "label `uncertain`" cannot hold for the baseline without an added rule). Detecting and flagging `language: unsupported` needs its own decision (a transparent rule, or annotator-set only in the validation data).
4. *Emotions outside the list* (the pilot has "relieved", "angry"): record them as `other_emotion` in the validation data without forcing them into `concerned`/`hopeful`; count and report them. Extending the list is a rubric change.
5. *Multi-label agreement and evaluation*: per-label binary agreement (Cohen's kappa per label) or a set-based statistic (Krippendorff's alpha with a set distance); per-label precision and recall with intervals; exact-set match reported separately. The choice belongs to O7.
6. *Reporting*: the unsupported/code-mixed group is reported separately with its share of the data; no pooled accuracy.
7. *Tests*: contract tests for both fields, a test that `emotional_tone` equals the only tone, a test that no tone feeds `risk_profile` or a conflict rule, and OpenAPI/type regeneration checks.

## ADR-045 — Demo-Manifest Training-Data Guard: Explicit Boundary (GDELT Excluded)

**Status**: Accepted (implemented 2026-10-20 on the owner's instruction to fix the underlying cause of two failing manifest tests).

**Context**: `demo_data/manifest.json` records a `training_data_guard`: SHA-256 hashes of the immutable raw TRAINING datasets (FAR-Trans, Kaggle; `demo_data/README.md` section 12, ADR-038 era), and the validator fails if any recorded file changes. The generator hashed every
file under `datasets/raw/`. After the GDELT sentiment track added `datasets/raw/gdelt/` (547 files), `test_regenerating_the_manifest_is_byte_stable` and `test_the_manifest_guards_every_raw_training_file` failed: the committed manifest did not list them.
That tree is not training data: it is a research acquisition area the sentiment pipeline writes to during normal use (a live SQLite manifest with `-wal`/`-shm` sidecars, run logs, a temp folder, filtered output) and it keeps its own provenance (`run_config.yaml`) and manifest.

**Decision**: The guard covers every file under `datasets/raw/` EXCEPT the sources named in `GUARD_EXCLUDED_RAW_SOURCES` (`backend/scripts/validate_demo_data.py`), currently only `gdelt`. Exclusion by name keeps the guard fail-closed: any NEW raw source is guarded until it is deliberately added to the list.
`guarded_raw_files()` is the single definition of scope; the manifest generator, validator and test use the same boundary. Manifest generation stays deterministic and byte-stable; no raw data was copied, hashed into the manifest or modified, and `manifest.json` itself did not need regenerating.

**Consequences**: The GDELT tree is outside this guard by design; its integrity belongs to the sentiment pipeline's own provenance and freeze manifests. Tests pin the boundary (the exact exclusion set, a new raw source is guarded, a GDELT working-file change does not trip the guard, a guarded-file change does).
Widening the exclusion list is a deliberate, reviewed change.

## ADR-046 — Dedicated "Financial Behaviour & Sentiment" Page; Compact Summary on Financial Health

**Status**: Accepted (project owner instruction, 2026-10-21).

**Context**: ADR-043 put the whole feature (text box, reading of the user's words, limitations, behaviour findings) in one long card on Financial Health. `components/shell/nav-items.ts` records that the sidebar lists only pages the original plan defines, so a new page needs an explicit decision.

**Decision**: A new protected page `/financial-behaviour` ("Financial Behaviour & Sentiment", sidebar entry "Behaviour & Sentiment" right after Financial Health) holds the detailed experience, reusing the existing card, hook and generated types unchanged. Financial Health keeps a compact summary card (`BehaviourSummaryCard`) built from the SAME records-only
backend response (the endpoint is called with no text): month count, up to three observed facts, the assessment sentence and a link to the page. The summary has no text box and never holds or sends text. Everything shown is still the backend's response; nothing is calculated or inferred in the frontend. The card on the page is keyed by profile and the text lives only in component state, so a profile change starts empty;
nothing is persisted. The backend endpoint, schemas, generated types, `user_text_rules_v0` and the risk assessment's authority are unchanged. The shared `Button` rendered as a `Link` exposes a link to assistive technology as a button, so the new link is a plain link styled with `buttonVariants`.

**Consequences**: Two places read the same endpoint (the summary on Financial Health, the full card on the page) and share the query cache key for the no-text request. The mobile sidebar sheet now closes when a page is chosen. Tests: `frontend/tests/behaviour-summary.test.ts`, the component cases in `behaviour-sentiment-view.cases.tsx`, and `npm run test:mutations`.

## ADR-047 — Sensitive-Data Protection Prototype: Encrypted Protected Notes and a Local Hash-Chained Audit Ledger (Not a Blockchain)

**Status**: Accepted (project owner instruction, 2026-10-21). Academic prototype; production-hardening items are listed in `docs/THREAT_MODEL.md` §14.

**Context**: The project stores customer financial data in plaintext in PostgreSQL (`docs/THREAT_MODEL.md` §2 inventory). The owner asked for a security extension: encryption at rest, explicit key-management boundaries, authentication/authorization checks, private off-chain storage, a verifiable append-only audit trail, and an interface a future permissioned-blockchain integration could implement. The prototype has no server-side authentication (ADR-020) and its only server-visible identity is the client-asserted `X-Customer-Id` header (ADR-031).

**Decision**:
1. **New package `wealthpilot/security/`** with four parts: `keys` (the `KeyProvider` boundary and a development `EnvironmentKeyProvider`), `crypto` (`EncryptionService`, AES-256-GCM, versioned envelopes, associated data = version, algorithm, key id, purpose, record id, owner id), `ledger` (`AuditLedger` protocol and `LocalHashChainLedger`), and `anchor` (the `LedgerAnchor` adapter contract and an `UnconfiguredAnchor` that is connected to nothing). Nothing in `core/`, `agents/`, `data/` or `training/` imports it (tested).
2. **Protect a new record type, not existing columns.** `protected_records` (a customer-written private note) is stored only as an envelope; `audit_ledger_events` is the ledger. One Alembic migration (`f7a2d4b6c810`) creates exactly these two tables and touches no existing table. Existing sensitive data stays plaintext and is documented, and shown in the UI, as unprotected. A future in-place migration plan is written down (`THREAT_MODEL.md` §11) but not authorized or performed.
3. **Reuse the existing identity mechanism; build no second auth system.** Every protected route requires `X-Customer-Id` to equal the path `profile_id` (401/403), looks records up by `(id, customer_id)`, and answers an unknown, malformed or foreign record id with one identical 404. This is **not** authentication: a caller who asserts the owner's id is indistinguishable from the owner. The documentation says so in plain words.
4. **Use the `cryptography` library** (already installed as a dependency of `google-auth`; pinned explicitly in `pyproject.toml`). No other dependency was added; no blockchain, wallet or SDK dependency exists or may be added behind the anchor interface without a new ADR.
5. **Ledger semantics**: schema-versioned canonical JSON, SHA-256 chained from a 64-zero genesis, sequence assigned under a PostgreSQL advisory lock with UNIQUE backstops, written in the same transaction as the data change (fail closed); `access_denied` is committed separately, best-effort. Events carry only type, UTC time, an opaque UUID reference, schema version and the two hashes.
6. **Honesty requirements** that bind every future change: the ledger is described as a *local hash-chained audit log* and the UI label is exactly "Academic prototype — not a real blockchain."; it is never called decentralized, consensus-backed, immutable or production-ready; a successful local verification is never described as proof of no tampering; encryption is never described as covering data it does not cover.

**Consequences**:
- Confidentiality of protected notes holds against a reader of the database or a backup who lacks the key; it does **not** hold against an API caller who asserts another customer's identity (ADR-020's disclosed limit, restated, not fixed).
- The audit chain detects edits, reordering and mid-chain removal; it cannot detect a privileged full rewrite or removal of the newest events unless an externally recorded head is supplied to `verify` (no implementation records one).
- The development key provider is not a KMS; there is no re-encryption tool, no key escrow and no recovery from key loss.
- The migration must be applied to `DATABASE_URL` as well as `TEST_DATABASE_URL`; only the latter was applied (through the guarded isolated runner) while developing. Clarification (2026-10-22): until it is applied, every protected-note and security-status route answers a plain 503 ("the migration ... has not been applied") and creates and saves nothing, instead of an anonymous 500; the check is made once per database after the identity check and never creates a table.
- `GET /api/profiles/{id}/security-status` runs a full chain verification per call (O(n)) and a real encryption round trip; a hostile caller can add `access_denied` events at will (no rate limiting).

**Alternatives rejected**: encrypting existing columns in place (rewrites user records and breaks engines that compute on them, no safe rollback); building JWT/OAuth to make authorization "real" (explicitly out of scope, ADR-020); a real blockchain or smart contract (not requested for the prototype, adds cost and cannot be verified here); Fernet (AES-128-CBC+HMAC) or a bespoke scheme (the owner asked for AES-256-GCM-style AEAD with bound context); a separate ledger database (adds infrastructure the prototype does not otherwise need — listed as a hardening item).

## ADR-048 — Financial Behaviour & Sentiment Page Redesign: Two-Column Dashboard, Text Area Input

**Status**: Accepted (project owner instruction, 2026-10-22). Frontend only: no backend, schema, classifier or generated-type change.

**Context**: ADR-043/046 put the whole feature in one long card with a single-line input; the owner's 2026-10-20 note kept the single-line input and deferred a multi-line one because the shadcn text area needed the CLI. The owner now asked for a polished dashboard-style page with a text area, clearly separating observed behaviour from sentiment inferred from optional text.

**Decision**:
1. **Layout.** An intro that states the two kinds of information side by side; then, from the `lg` breakpoint, a 5/7 two-column grid -- records (insight cards) and the stored risk assessment on the left, the text box and its reading on the right -- stacking in the same order on narrower screens. Four labelled regions (level-two headings), one page title, no per-card repeat of it (the `showHeader` prop was removed).
2. **Insights** come from `behaviour.findings` (observed only, backend order, month-count sentence shown as the header chip): sentence, source fields, category and the backend's `direction` are shown as returned. Nothing is calculated, ranked or judged good or bad.
3. **Text area** is the shadcn primitive added with `npx shadcn@latest add textarea` (the only new source file under `components/ui`; no dependency added). The 1,000-character rule and every validation rule are unchanged (tab and line feed were already allowed; the backend collapses whitespace). No `maxlength` attribute, so an over-long paste is reported by the counter and message, not silently cut. Enter inserts a line break; Ctrl/Cmd+Enter submits through the same guarded `submitDraft` as the button.
4. **Readings that found nothing** (`uncertain`, or a value the UI does not know) are marked inconclusive (dashed border, muted text, the words "Not a confirmed reading.") and never shown as neutral; a found tone has a solid, filled headline. Meaning is carried by words and icons, not colour.
5. **The stored assessment** has its own region and is never presented as updated by the text; on a conflict the page says the stored assessment stays the authority.
6. **Unchanged**: the endpoint, hook (`gcTime: 0`, no retry), query key, response types, `user_text_rules_v0` (UNVALIDATED_BASELINE), profile-keyed card, Clear semantics, and the privacy rules (text only in component state and an in-memory query; never in storage, a URL, a log or analytics).

**Consequences**:
- This supersedes only the 2026-10-20 "single-line input stays" note for this feature's input; the other owner decisions (preference confirmation and persistence deferred, O1-O7 unresolved) are untouched.
- The status sentence ("Your records, your words and your risk assessment are all shown") and the old combined results region were removed; their information is carried by the separate panels.
- The mutation runner now fails on a stale mutation: a missing target previously threw inside the loader and was counted as a "kill". Every mutation is verified to exist (line endings normalised) before the run. This exposed that several earlier mutations (route/navigation entries, one summary mutation) had never been applied; they were re-pointed and all now genuinely detect their change.

## ADR-049 — Full-Pipeline Demo Persona (WPDEMO-E), Monthly Records in the Demo Package, Stored-Assessment Fallback, Local Market-Data Loader

**Status**: Accepted (project owner instruction, 2026-10-23).

**Context**: A profile created in the UI, or persona D, stops at "information request": the risk model needs a FAR-Trans history, which no public API can link. A fully populated demonstration therefore needs a seeded, linked persona. Investigating that also found (a) the portfolio stage and goal Monte Carlo need `market_data`, which a throwaway local database lacks (so even persona A was `rejected`, because compliance fails closed on missing weights), (b) the demo package had no monthly records, so the behaviour findings were empty, and (c) the Behaviour & Sentiment endpoint read its "stored risk assessment" only from `risk_assessments`, a table the pipeline never writes (its `risk_score` is NOT NULL and no ordinal score exists), so the panel was empty for every real user.

**Decision**:
1. **Persona E** ("WealthPilot Demo — Full Pipeline", `WPDEMO-E`), added to the demo package with the existing conventions (profile, questionnaire, financial inputs, goals, expected results). Linked to the genuine FAR-Trans customer `F7D82BE85FF183D757BA` (label `Balanced`, 52 months of history), chosen with `find_demo_risk_candidates.py` and checked against `customer_information.csv`. No label, transaction or result is invented, and the persona files carry no computed value. Personas A–D are unchanged.
2. **Monthly records** become an optional package directory (`monthly_records/`, persona E only), validated (consecutive months, `MonthlyRecordUpdate` payloads, spending within income, income consistent with the profile) and seeded idempotently through the public API, writing only months not already stored.
3. **Stored-assessment fallback**: `personalized_insight_service._risk_profile` keeps the `risk_assessments` row when one exists and otherwise uses the risk result of the customer's latest analysis run; none means `null`. The response shape, `data_source` string and classifier are unchanged. `risk_profile.source` ("stored risk assessment of the latest analysis") is now literally accurate.
4. **`scripts/load_local_market_data.py`** loads public QQQ/AGG/GLD prices into a named SQLite file with the project's own `fetch_ohlcv` (inserting only missing rows; a gitignored snapshot allows an offline rebuild). It never reads settings or `.env`.
5. **Sign-in entry** "Use Full Pipeline Demo", find-only like the family demo (ADR-036), so the persona is selectable without an in-app switcher (ADR-021).
6. `seed_demo_data.py verify` parses the JSON column text that SQLite returns (the local demo database); PostgreSQL behaviour is unchanged.

**Consequences / limits**:
- The aggregate CSV (`wealthpilot_complete_demo_dataset.csv`) is exported from the live application's own database (ids and figures come from it) and was deliberately NOT regenerated; it still covers A–D and E joins it when the owner regenerates it against the live database.
- E's allocation and goal figures depend on the market prices loaded; a live download differs from the data the Phase 6 models were evaluated on (`models/metrics.json`). The written (Gemini) explanation needs a configured key: the offline launcher blanks it, so locally the explanation reports `configuration_failure` and the plain-language view is built from the computed values.
- `seed_demo_data.py reset` uses PostgreSQL-only SQL; a local SQLite demo is reset by deleting its file.
- No migration, no schema change, no change to a formula, the risk model, compliance or an API contract.

**Alternatives rejected**: using persona A alone (no monthly records, so the behaviour page stays empty); writing a `risk_assessments` row with a placeholder score (fabricates a number); regenerating the CSV from a local database (rewrites A–D's rows); loading prices into a hosted database; fabricating a link or transactions for an ordinary profile.

## ADR-050 — Multi-Stage Interpretation of Optional User Text (Rules Baseline v1, Abstention, Structured Conflicts)

**Status**: Accepted (project owner instruction, 2026-10-23). Supersedes ADR-043's single-pass taxonomy in part; ADR-043's privacy rules, `UNVALIDATED_BASELINE` status and "display only" rule are unchanged. ADR-044's annotation policy (O5, O6) is still only PROPOSED.

**Context**: `user_text_rules_v0` matched cue words anywhere in the text. It had no notion of financial relevance, so "I feel nervous today" or any sentence with one English cue word received a label; it did not detect the language (a Hindi sentence with the word "excited" was read as positive); negation was a three-word window that also hid topics; it could not tell the user's own view from a quotation, another person's feeling or a past feeling; it forced `uncertain`/`neutral` instead of declining; and a disagreement with the stored assessment was one prose string.

**Decision** — one pipeline in the existing flow (`core/user_text_sentiment.py` -> `core/personalized_insight.py` -> `api/services/personalized_insight_service.py` -> the existing route, schemas and page; nothing duplicated, no new route):

1. **Stages** (each can stop the reading; a stopped reading is an ABSTENTION, not a guess): input validation / privacy (control characters, 1,000 characters, whitespace; unchanged) -> language and text quality -> financial relevance (`relevant | unrelated | ambiguous`, fixed lexicon, counted over the user's OWN clauses) -> clause analysis (quoted spans, other people's views by pronoun / relationship word, past feelings, negation) -> sentiment and emotional tone -> topics -> explicit preferences -> confidence / abstention. Deterministic and pure; no I/O, no logger, no LLM, no new dependency.
2. **Taxonomy** (a superset; the old values keep their meaning): sentiment adds `insufficient_evidence` (= abstained); emotional tone adds `frustrated`, `calm`, `neutral`, `unknown`; topics add `market`, `retirement`, `emergency_fund`; preferences add `balanced_growth`; `financial_relevance`, `abstain_reason`, `interpretation_state` (`valid | weak | abstained | unavailable`), `confidence_band`, `fallback_used`, `privacy_status` are new fields. Preference `status` allows `confirmed | rejected | not_inferred` in the schema, but only `unconfirmed` is ever produced because confirmations are not stored. **Emotional tone is not risk tolerance**: "I am nervous about the market" is `concerned` with no preference.
3. **Abstention policy, as configuration constants in `core/user_text_sentiment.py` (rule-of-thumb gates of an UNVALIDATED baseline, not tuned on data and not calibrated; each has a boundary test; changing one is a classifier change)**: `MIN_WORDS = 3`; `MIN_LETTER_RATIO = 0.5`; `MAX_NON_LATIN_SHARE = 0.2`; `MIN_TOKENS_FOR_LANGUAGE_CHECK = 6` with `MIN_ENGLISH_FUNCTION_SHARE = 0.15` (language is confirmed from script and common English function words, never from cue words); relevance needs two finance-lexicon terms, or one plus a first-person subject, or a goal word plus a stance verb plus a first-person subject; `MIN_SIGNALS_ALONE = 2` / `MIN_SIGNALS_WITH_TOPIC = 1` separate a `valid` from a `weak` interpretation. A negated cue is dropped and its opposite is never concluded (a reading with only a negated cue is `uncertain`, `weak`). A generic word ("safe", "growth", "pay off") is a preference only after a first-person stance verb ("want", "need" ...). Opposing explicit preferences (capital preservation and growth) are both withheld, with a stated limitation.
4. **Method honesty**: `method = rules_baseline`, `model_version = user_text_rules_v1`, `validation_status = UNVALIDATED_BASELINE`, `confidence = null`, `confidence_band = unavailable`. **No trained or validated model exists in this repository.** `SentimentModel` / `ModelReading` is the seam for an approved one: it must run locally on the in-memory text; it supplies its own `abstain_below` and band cut-offs from ITS validation (this module invents none); `confidence` is exposed only when the model marks the probability calibrated; `method` is then `hybrid` (the model supplies the sentiment label, the rules still supply tone, topics and preferences). A model that raises or returns anything outside the contract is a failure: the rules baseline answers and `fallback_used = true` (the exception is dropped, never logged or returned). `get_sentiment_model()` returns `None`.
5. **Authority** (unchanged order, now in the response): 1 stored questionnaire / risk assessment, 2 compliance, 3 savings-first, 4 goals, 5 market context, 6 sentiment and stated preference (informational only). `risk_profile.remains_authoritative` is always `true`; a disagreement (capital preservation vs Aggressive; growth vs Conservative or Income) is a structured `conflict` (`inferred_preference`, `stored_category`, `authoritative_source`, `preference_status = unconfirmed`, `action = confirm_or_correct`); the category, weights, recommendation and compliance inputs are never touched. The insight path imports nothing from the analysis, recommendation or compliance code (tested).
6. **API**: the same route, `POST /api/profiles/{id}/personalized-insights`, the same nested `user_sentiment`, no text in a URL, RFC 7807 errors unchanged (400 for unusable text, route-scoped no-echo 422). Fields are added, none removed; `method` now holds `rules_baseline | trained_model | hybrid | unavailable` and `model_version` holds the former `method` string; `COMPOSER_VERSION = personalized_insight_v2`, `DATA_SOURCE` unchanged. Generated TypeScript types were regenerated from the OpenAPI schema.
7. **Privacy** (unchanged guarantees, now tested end to end): the text is never persisted, logged, cached, put in a URL, a header, response metadata, an error message, an audit event or a ledger / blockchain payload, and no external service sees it. Evidence phrases are bounded (100 characters, at most 6 items) and sanitised (links, e-mail addresses and long digit runs are masked).
8. **Frontend**: the existing page only; sections for behaviour, relevance, sentiment, emotional tone, topics, possible preferences, evidence, confidence ("Not available"), method, validation status, limitations, risk-profile authority, conflicts and confirmation guidance; five distinct presentations (valid, weak, abstained, unavailable, fallback); the required messages word for word. Nothing is stored in the browser.
9. **Unchanged**: `docs/USER_TEXT_ANNOTATION_RUBRIC.md` and the pilot pack are the frozen v0 annotation scheme; the production taxonomy is now a superset of it (a test pins the difference exactly), and the abstention classes are not asked of annotators.

**Consequences / limits**: the baseline is still unvalidated and its accuracy unknown; keyword relevance can misjudge a word with two meanings; the language check is conservative and declines some terse English; third-person detection knows pronouns and relationship words, not names; no sarcasm or deep context; a retained cue list is a methodology choice, not a financial formula; a preference cannot yet be confirmed (no table; needs a reviewed Alembic migration on both databases and a retention policy).

**Alternatives rejected**: an LLM or hosted sentiment API (the text would leave the process; ADR-043); a pretrained transformer or a language-detection / sentiment package (licence, download, new dependency, still unvalidated for this domain); forcing a label with a low confidence (a number nobody calibrated); inferring the opposite of a negated cue; treating a feeling as a risk preference.

**Decisions still required from the project owner**: (a) accept or amend the configuration values and the finance / off-topic / stance lexicons; (b) whether the annotation rubric should adopt the extended taxonomy (and O5 / O6) before any evaluation; (c) approval and licensing of any trained model, and the labelled data to validate it; (d) whether to store confirmed / rejected preferences; (e) a policy for code-mixed and Indian-English text; (f) whether opposing preferences should be withheld (current) or both shown.

## ADR-051 — Full-Pipeline Household (WPDEMO-HHE), Partner Persona WPDEMO-F, Honest Debt and Spending States, SQLite Partial Index

**Status**: Accepted (project owner instruction, 2026-10-24).

**Context**: The full-pipeline demo account (ADR-049) still showed "0 reported months", "Spending pattern not available", "Debt & Commitments not available" and no household. Diagnosis (each verified, see `reports/full_pipeline_household_report.md`):
(1) **Monthly records / behaviour**: with a correctly seeded database the exact sign-in path shows all twelve months; the page empties for persona A (the default "Sign In" persona), which has no months by design, or for a database where `setup` was not run after persona E gained its months. Not a query or caching defect, but a saved month did not refresh the behaviour findings query (`personalized-insight`); (2) **Household Finance**: missing synthetic seed data (E belonged to no household, and a household member must be an existing customer); (3) **Debt & Commitments**: a genuinely unsupported feature for an individual (ADR-033: loans and EMIs exist only as household liabilities), shown with a misleading "Not available"; (4) **Spending**: the "spending pattern" is the Kaggle expense-persona model, structurally never applied to a FAR-Trans customer (ADR-010) — unsupported by design, while an individual's spending is one monthly total; (5) **Local SQLite demo**: `local_synthetic_backend.py` created `uq_household_members_one_primary` as a plain UNIQUE index (SQLite ignores `postgresql_where`), so a household could never have a second member and `setup-family` failed locally.

**Decision**:
1. **Persona F** ("WealthPilot Demo — Full Pipeline Partner", `WPDEMO-F`): a light, synthetic, seed-owned customer — profile, partial questionnaire, no financial inputs (`null` + reason), one goal, no risk link — so it honestly stays `pending_information` (as D). It exists only so the household has a real second member.
2. **Household `WPDEMO-HHE`** ("WealthPilot Demo — Full Pipeline Household"): E primary (self), F spouse, with income, expenses (EMIs recorded as `debt_payment`), assets, liabilities (loans with EMI and interest rate, a credit card at a stated 0) and goals, all coherent with E's records (documented in `demo_data/README.md`; the validator checks EMIs against debt-payment expenses). Seeded through the public household API; the summary is computed by the existing `core/household_finance.py` and never stored.
3. **Seed**: `setup` builds the household after the personas; `verify` / `reset` cover it; the `*-family` modes take `--household family|pipeline`. Idempotent; never overwrites an edited record; no migration, no schema change, no new endpoint.
4. **Honest states**: Financial Health's "Debt & Commitments" says "Not recorded for an individual" and points a household member to the household's liabilities (their figures are not shown there); "Spending and expenses" additionally shows the backend's spending findings from the reported months (a separate, loading / error / empty-aware block), still stating that no category breakdown exists for an individual and that the spending pattern is unavailable with its reason.
5. **Cache**: saving or deleting a monthly record also invalidates the `personalized-insight` query of that profile.
6. **Local SQLite**: the launcher applies `sqlite_where` to partial indexes and repairs a file made by the earlier launcher; the pipeline test fixture does the same for its own metadata.
7. Unchanged: risk, compliance, goal and portfolio logic; the analysis path (a test shows each persona's analysis is identical after the household exists); sentiment never touches risk.

**Consequences / limits**: the aggregate CSV (`wealthpilot_complete_demo_dataset.csv`) is exported from the live database and was not regenerated (still A-D); an individual still has no debt record (adding one would need a schema, an ADR and a decision about the individual pipeline); the expense-persona model stays unavailable for FAR-Trans customers; household amounts are rupee demo values, not training data.

**Alternatives rejected**: a one-member household (no real composition); putting E into the family household (B + C) or making persona A/D its partner (alters existing personas); showing household liabilities on the individual Debt card (mixes individual and household figures, ADR-033); hard-coding months, categories or totals in the UI; applying the Kaggle expense model to E (ADR-010); a migration for individual debts.

## ADR-052 — Pretrained Transformer Sentiment Classifier: Gated Integration, Offline Training and Evaluation, Visible Fallback

**Status**: Accepted as an INTEGRATION and a GATE (project owner instruction, 2026-10-26). **No Transformer model is active or validated.** The deep-learning packages, the model weights and an approved labelled dataset do not exist in this repository; installing or downloading any of them needs the owner's approval (`reports/sentiment_transformer_dependency_request.md`). Extends ADR-050; the rules baseline stays the method until a validated model exists.

**Context**: ADR-050's pipeline already has a seam for a trained model (`SentimentModel` / `ModelReading`). The request is to make that a real, locally executed, pretrained Transformer sentiment CLASSIFIER (optionally fine-tuned), with confidence, abstention and fallback. This is a classification task on a pretrained model — not a new general-purpose language model, and nothing here generates text. Facts established: `torch`, `transformers`, `tokenizers` and `safetensors` are not installed and are outside the approved stack (CLAUDE.md section 5); only TensorFlow 2.17 / Keras are, and the `transformers` v5 line drops TensorFlow and Flax support (v4 is the long-term-support branch), so PyTorch is the realistic backend; no weights are present; no labelled dataset is approved (the project's own pilot pack is unannotated by design); the only public financial-sentiment set named in the research (Financial PhraseBank) is listed by its dataset card as CC BY-NC-SA 3.0 (non-commercial, share-alike, inherited by derived weights) and is news sentiment, not personal-finance sentiment.

**Decision** — everything that can be built, tested and documented without installing or downloading anything was built; everything else is gated:
1. **Inference service** `core/sentiment_model.py` implements the existing seam: lazy, cached, CPU-only, token- and wall-clock-bounded, loads ONLY from a directory strictly inside `models/sentiment/` (no `..`, no symlink, safetensors only, `trust_remote_code=False`, `local_files_only=True`), verifies a metadata file with the SHA-256 of every file, label map / `config.json` / tokenizer vocabulary agreement, the configured version, and the evidence behind any `validated` claim. Failures are FIXED reason codes (`dependencies_missing`, `artifact_missing`, `artifact_corrupt`, `artifact_incompatible`, `path_not_allowed`, `not_validated`, `version_mismatch`, `load_failed`, `inference_failed`, `timeout`, `invalid_output`, `invalid_configuration`, `below_threshold`) — never text, a path or a stack trace. Its real backend (`TransformersBackend`) is **not exercised** here.
2. **Validated-only primary**: a model is the primary reading only when its metadata says `validated` AND carries a held-out test split, a duplicate-leakage check, a documented dataset licence, a metrics file and a CALIBRATED temperature with a documented minimum confidence and band cut-offs. Otherwise the loader answers `not_validated` and the rules baseline answers. Raw softmax is never called calibrated: `confidence` exists only for a calibrated model; `class_probabilities` always carry `confidence_calibration_status`.
3. **Policy in `analyse_user_text`** (ADR-050's gates all run first; the model never runs on an abstained text): it reads only the user's own current clauses (quotes, other people's views and past feelings left out); a rules safeguard for a negated-only expression is never overridden; opposite model / rules polarities yield `uncertain` (weak) with both readings exposed (`rules_baseline`, `disagreement`) and a caveat; a non-opposite disagreement uses the model's label and keeps the rules reading beside it; tone, topics, preferences, evidence, relevance and the stored-assessment conflict stay deterministic. Below its own threshold, invalid or failed, or unusable: the rules baseline answers with `fallback_used = true` and a `fallback_reason` — or, if `SENTIMENT_MODEL_ALLOW_FALLBACK=false`, the text is not interpreted (`model_unavailable`). A model that is simply switched off (the default) is not a "fallback": the rules baseline is the method. (This replaces ADR-050's rule that a below-threshold model reading abstains.)
4. **Intensity**: `sentiment_intensity` is null (`intensity_available = false`) unless the artifact has a VALIDATED regression head; a classifier probability is never turned into an intensity. The regression head is NOT trained: it needs a dataset with documented continuous intensity labels, separate training and MAE / RMSE reporting (`training/sentiment/metrics.regression_metrics`); `--with-regression` is refused.
5. **Offline training package** `training/sentiment/` (never imported by the backend; checked): approved-manifest gate, UTF-8 JSON Lines loader that normalises text exactly like user text, label mapping, duplicate / conflicting-label removal, group-aware deterministic split with a leakage check, fine-tuning entry point, temperature scaling on the validation split, ECE and reliability table on the test split, abstention threshold and band cut-offs derived from the OWNER's precision / coverage targets (required arguments; nothing invented), artifact writer that re-verifies with the application's own loader, and an evaluation CLI that scores `rules_baseline` and artifacts on the held-out test split without choosing a winner. Tested end to end with a fake trainer and invented data.
6. **Configuration** (all default off): `SENTIMENT_MODEL_ENABLED`, `_NAME`, `_PATH`, `_VERSION`, `_MIN_CONFIDENCE` (may only RAISE the artifact's calibrated minimum), `_ALLOW_FALLBACK`, `_MAX_TOKENS` (required when on), `_DEVICE` (`cpu` only), `_TIMEOUT_SECONDS`. `GET /api/sentiment-model/status` reports `disabled | ready | unavailable` with the reason; it returns no path, secret or text.
7. **API**: the same route and nested `user_sentiment`; fields added (`model_name`, `class_probabilities`, `confidence_calibration_status`, `sentiment_intensity`, `intensity_available`, `rules_baseline`, `disagreement`, `fallback_reason`, new abstain reason `model_unavailable`); probabilities, confidence and intensity are rounded to 4 decimals for display by the backend. **Frontend**: method labels "Validated model analysis" / "Rules baseline fallback" / "Model unavailable", the reason, probabilities, calibration status, intensity ("Not available" when null), the rules reading beside a model reading, the disagreement alert; the frontend rounds and computes nothing.
8. **Privacy / authority unchanged and re-tested**: the text is never logged, stored, in a URL, an error, an audit event or a ledger / blockchain payload, and never sent to an external service by the application; no agent, node or graph reads sentiment; the stored assessment stays authoritative. The ONLY network access anywhere is the one-time download of a base model's weights by `fine_tune_with_torch` when the owner approves training.

**Consequences / limits**: no model candidate has been evaluated (FinBERT, RoBERTa-base and DistilRoBERTa-base are identifiers only; their licences are unverified); no accuracy, macro-F1, calibration or regression metric exists; `TransformersBackend` and `fine_tune_with_torch` have never run; the model reads reworded own-clauses (full stops replace clause boundaries); a timed-out inference keeps running in its worker thread until it ends (one worker, so later requests queue behind it — they time out too rather than overload the CPU); a domain gap (news vs personal-finance text) is expected and only a labelled personal-finance set can measure it.

**Alternatives rejected**: installing the packages and downloading weights now (outside the approved stack and the standing no-download rule; also nothing could be validated without a dataset); a TensorFlow / `tf-keras` Transformers path (deprecated upstream); building or training a language model from scratch (not the task, no data); an LLM or hosted API (the text would leave the process; ADR-043); using FinBERT's own softmax as "confidence"; trusting a model without an evidence-bearing metadata file; training inside an API request, a node or at start-up.

**Decisions required from the project owner**: (a) approve the packages (name, version, licence, size, security) in the request report, or choose another stack; (b) approve and supply a licensed, labelled dataset of PERSONAL-finance statements (or accept a news dataset as a development aid only, with its non-commercial / share-alike terms); (c) the precision and coverage targets for the abstention threshold and the 'high' band; (d) which candidates to evaluate and the criteria for choosing (macro-F1, per-class recall, calibration, coverage, size); (e) whether an intensity head is wanted, and a dataset with intensity labels; (f) approval of the one-time weight download; (g) the minimum test-set size for 'validated' (default structural minimum 200).

> **Addendum to ADR-052 (2026-10-27) — approval package prepared; nothing activated.** `reports/sentiment_transformer_dependency_request.md` (addendum) and `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md` (addendum) now hold, as PROPOSALS and unresolved decisions: the exact dependency pins proposed by the owner (`torch==2.6.0` CPU, `transformers==4.57.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`) with evidence labels (verified / owner-supplied / estimate), the security requirements and where each is or is not yet enforced (the exact model revision is NOT yet enforced), a static candidate register (FinBERT, `cardiffnlp/twitter-roberta-base-sentiment-latest`, a RoBERTa-family base), the dataset register (Financial PhraseBank: development-only candidate, CC BY-NC-SA 3.0), a proposed independent 300-statement held-out set, the annotation protocol, the evaluation plan and a 16-item approval checklist in which every item is UNRESOLVED except "keep intensity regression deferred". ADR-052 is unchanged and still accurate: the rules baseline `user_text_rules_v1` is the only active method, no Transformer is installed, no weights or datasets are downloaded, no model is validated, and no production activation is allowed. No runtime code, dependency manifest, configuration or schema changed in this phase.

> **Addendum to ADR-052 (2026-10-27) — integration hardening of the Transformer seam; nothing activated.** Under a separate owner approval (`reports/sentiment_model_approval_record.md`, "Approval recorded 2026-10-27 (seventh brief)"): (1) `fine_tune_with_torch` no longer passes the obsolete `safe_serialization` argument (transformers 5.x writes safetensors only; the argument was silently ignored); (2) artifacts record `tokenizer.length` (= `len(tokenizer)`, separate from `vocab_size`) and `TransformersBackend` refuses a tokenizer of any other length, and an artifact with a missing or malformed length, with the **existing** code `artifact_incompatible` — a new reason code was deliberately NOT added because the codes are enumerated in the public API schema, the generated TypeScript types and the frontend message map; the length is not compared with `config.vocab_size` (padded embedding matrices are valid); (3) the trainer requires a caller-supplied immutable base-model `revision` (a 40-character commit hash; no revision and no Hub model is defaulted), loads with `use_safetensors=True` and `trust_remote_code=False`, and offline unless `--allow-hub-download` is given; (4) no **documented** switch for the library's Hub conversion exists in the installed transformers 5.12.1 (the one found in its source is undocumented), so none is set; the documented parameters of (3) are the protection and a test pins the installed behaviour. Tested with local randomly initialised stand-ins only (the stand-in module is skipped where the packages are absent). Open decisions: whether to record the base-model revision in the artifact metadata (a schema change), whether a more specific reason code is wanted (an API change), and whether to check at artifact time that the tokenizer is not longer than `config.vocab_size`. R6 to R14 remain UNRESOLVED; no model, revision, licence or dataset is approved; `SENTIMENT_MODEL_ENABLED` stays false.

> **Addendum to ADR-052 (2026-10-28) — owner decision record for the remaining blockers; nothing changed in code.** `reports/sentiment_model_approval_record.md` ("Owner decision record (eighth brief)") records: D7 APPROVED (retain the existing public failure code `artifact_incompatible` for tokenizer-length mismatches; no new API code); D8 (base-model revision, tokenizer source, extended library versions, manifest hash and a metadata schema version in every artifact) and D9 (reject `len(tokenizer) > config.vocab_size`) UNRESOLVED, with decision texts prepared and the engineering recommendation to approve both, but no schema or check changed; D10 BLOCKED (Hub conversion is an observed Transformers 5.12.1 property, not a guarantee; no undocumented switch is added; one of a documented mechanism, a local conversion-free workflow or a separate security approval is required before any real download); D11 BLOCKED (the eight-item network approval is unsupplied; `local_files_only=True` default, `trust_remote_code=False` and pinned revisions stay mandatory); D12 BLOCKED (any real training environment needs a separate approval to install the S1 set; `backend/pyproject.toml` untouched until production activation); D13 BLOCKED (separate project `certifi`/`pip` task, not started; no Hugging Face download until remediated or risk-accepted). R6 to R14 remain UNRESOLVED; `user_text_rules_v1` remains the production method; `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-28) — D8 and D9 approved and implemented: artifact provenance and the tokenizer/embedding invariant; nothing activated.** The owner approved D8 and D9 (`reports/sentiment_model_approval_record.md`, "Decisions recorded 2026-10-28 (ninth brief)"). **D8:** every trained artifact now carries `metadata_schema_version` 1 (the only supported version; missing or unknown is refused, no migration code exists, artifacts are never edited in place), the exact model identifier and its immutable 40-character lowercase revision, the tokenizer's identifier and revision, `tokenizer.length`, the versions of torch / transformers / tokenizers / safetensors (provenance only, never compared with the installed libraries) and `manifest_sha256` (SHA-256 of the canonical JSON of the `files` map, one shared function; malformed is `artifact_incompatible`, a well-formed mismatch is `artifact_corrupt`). The trainer records what it actually loaded; the revision rule has a single definition in the loader module. An artifact written before these fields fails closed as `artifact_incompatible`. **D9:** `len(tokenizer) > config.vocab_size` is refused with `artifact_incompatible` at artifact verification and, before any text is processed, in the backend constructor; equality is not required (padded embedding matrices are valid). No new public API code was added (D7); nothing in the API schema, frontend, settings, `backend/pyproject.toml` or any environment changed; no real identifier, revision, checkpoint or dataset was used (tests use synthetic hashes). Tests: 608 passed, 3 skipped in the project environment, eight deliberate defects detected; the library-dependent stand-in module was updated but not re-run (no installation in this phase). D10 to D13 remain BLOCKED, R6 to R14 UNRESOLVED, `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-28) — the library-dependent regression check of D8 and D9 passed in the disposable S1 environment; nothing activated.** Under the owner's tenth-brief authorisation (A2 still limited to isolated verification), the disposable environment was recreated from the unchanged hash-pinned S1 list and the updated stand-in tests ran offline against randomly initialised local models and hand-written tokenizers: 381 passed, 1 skipped, 0 failed (stand-in 34, training seam 62, artifact provenance 184, tokenizer integrity 60, loader guards 41 with the earlier symlink skip). Verified against the real libraries: the provenance arguments and schema version 1, the manifest hash, equal / shorter / padded tokenizer lengths accepted, longer refused (writer and backend), safetensors-only output, refusal of pickle / `.bin` / `.pt` / `.pt2`, `trust_remote_code=False`, `local_files_only=True`, and zero socket, Hub, `torch.load`, pickle or Hugging Face cache activity. The environment and caches were deleted; the repository and the project environment are unchanged. The implementation is ready for the separate R6/R7 licence-and-revision approval phase but not for any download: D10 to D13 remain BLOCKED, R6 to R14 UNRESOLVED, `user_text_rules_v1` remains the production method and `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-28) — R6/R7 approval preparation; nothing decided.** The README statement that the stand-in tests had not been re-run is corrected to the result of the 2026-10-28 disposable-environment check (381 passed, 1 skipped, 0 failed; local randomly initialised stand-in models and hand-written tokenizers only). A decision matrix for `ProsusAI/finbert` (R6) and one RoBERTa-family candidate (R7, recorded as `FacebookAI/roberta-base`, which has no sentiment head) and eleven owner decision fields (P1 to P11: approval, licence reading, exact revision, permitted files, destination, network boundary, SHA-256 and provenance record, cleanup and rollback, evaluation-only versus training use, and the separate R14 activation decision) are recorded in `reports/sentiment_model_approval_record.md` from already-recorded evidence only. Every licence statement is a model-card claim from the 2026-10-20 metadata read, not verified permission; the recorded FinBERT revision is not approved. No Hugging Face query, download, dataset access or installation took place. R6 and R7 remain UNRESOLVED, D10 to D13 BLOCKED, R8 to R14 UNRESOLVED, `user_text_rules_v1` active and `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-28) — R6/R7 selection phase: no selection supplied, nothing decided.** The twelfth brief asked for owner decisions on R6 (FinBERT: approve, reject or keep unresolved, with seven licence and provenance items to accept or reject) and R7 (one of `FacebookAI/roberta-base`, `cardiffnlp/twitter-roberta-base-sentiment-latest`, `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`, or unresolved) but gave no value for any of them. No decision is inferred from a brief's wording or a model-card label, so **R6 and R7 remain UNRESOLVED and no candidate is selected or rejected.** `reports/sentiment_model_approval_record.md` now holds the complete decision form (R6-0 to R6-9, a three-candidate R7 matrix built only from the 2026-10-20 recorded evidence, fields F1 to F14 per selected candidate, and the approvals required before a metadata query and before a download), so one owner reply can resolve it. The recorded FinBERT revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` stays a proposal. A metadata query is not implied by any selection and needs its own approval; D10 to D13 must be resolved before any real checkpoint access even if R6 or R7 is approved. No Hugging Face access, download, dataset, user text or installation; no runtime, manifest or configuration change. D7 to D9 approved, D10 to D13 BLOCKED, R8 to R14 UNRESOLVED, `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-28) — R6/R7 decision form resolved conservatively; nothing approved or rejected.** On the owner's thirteenth brief the decision form was recorded exactly as instructed: R6-0 to R6-9 KEEP UNRESOLVED; R7 KEEP UNRESOLVED; R7-A, R7-B and R7-C NOT SELECTED (not rejected); F1 to F14 KEEP UNRESOLVED for every candidate; R8 to R14 KEEP UNRESOLVED; D10 to D13 BLOCKED; D7 to D9 approved as before. The stated reason is that current evidence cannot support accepting any model licence, training-data licence, tokenizer licence, commercial-use position, revision, permitted-file list or download boundary, and no candidate is approved until those are resolved from authoritative sources. The recorded revisions stay proposals. No metadata-only query is authorised; the inputs that would reopen the form (R6-0, R6-1 to R6-7, R6-9, the single R7 choice, that candidate's licence and data terms, the full parameters of a metadata query, and the confirmation that a query authorises no file, tokenizer, weight or dataset access) are listed in `reports/sentiment_model_approval_record.md`. No external access of any kind; no code, configuration, manifest or production change; `user_text_rules_v1` remains active and `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-050 (2026-10-28) — hypothetical and conditional statements are not a current view.** A probe of the rules baseline found that "If the market crashes I would be very worried" was read as a current negative feeling and "If I had more money I would want higher returns" as a current growth preference. Clause analysis (stage 4) now marks a clause hypothetical when it carries a conditional marker (`if`, `unless`, `suppose`, `imagine`, `assuming`, `in case`, `provided that`, `as long as`, `were I`, `had I`, `should` + a subject), a wish construction, or a conditional-mood phrase (`would / might / could be, feel, get ...`), or when it is the consequent of such a clause in the same sentence (carried across a comma; ended by a sentence end or a contrast word). Indirect questions ("tell me if I should worry") and idioms ("if possible") are not conditions. Like a past feeling, a hypothetical clause yields no cue, evidence, tone or preference; the response adds one string to the existing `limitations` list; a text whose only cues were hypothetical is `uncertain` / `weak` with tone `unknown`; topics are still reported as mentions; a trained model is never shown a hypothetical clause when a current clause exists and cannot turn a hypothetical-only text into a label. Consequence: the rule is conservative (a clause with a marker is dropped as a whole, so "I feel safe even if prices fall" is not read as a current feeling). No schema, enum, error code or generated type changed; `user_text_rules_v1` keeps its method version because the output taxonomy is unchanged and the method is still unvalidated. 20 new tests and an 8-mutation check cover it. Hypothetical statements are not yet in the annotation rubric or the proposed coverage list (owner action recorded in the approval record). `SENTIMENT_MODEL_ENABLED=false`, the rules baseline stays active, and no model, dataset or package was touched.

> **Addendum to ADR-052 (2026-10-29) — rubric rules 11 and 12, and offline evaluation-statistics support; nothing activated.** On the owner's instruction (recorded before the edit) the draft annotation rubric gained rule 11 (hypothetical, conditional, wish and counterfactual statements are not the person's current sentiment, tone or preference) and rule 12 (how to label a text containing such a clause, with six illustrative examples; a condition that only qualifies a statement true now does not make it hypothetical). The rubric is still `v0-draft`, not frozen, not validated and not received by any annotator; its SHA-256 is now `c77179950111c4ffaedf1564e5ee6466f6f38c753d012e1930672c1b77808fd3` and the annotator excerpt's `a7bc2d328c55e9bddece4023ebd609c2713b6a1e3df679ba0ddd83f6bac9cd9b`, rebuilt with `scripts/build_dry_run_package.py` (the old values were `24a8f252e11911c402ced17df08b8da957372cdda2df0d5c7936e8ce52573eb9` and `01aeab41874de5818372b82caf9e0cc79ad0f83a25282f215444836f2449a69c`). The rubric keeps "I feel safe even if prices fall" as a current clause while the rules baseline drops it (ADR-050 addendum); the baseline was not changed and the disagreement is documented. `training/sentiment/metrics.py` gained offline, deterministic evaluation statistics (Wilson and stratified percentile-bootstrap intervals, annotator agreement, per-class and per-group breakdowns, coverage / abstention, calibration bins, a paired comparison with the rules baseline) behind a required `StatisticsPlan` (proposed, unapproved values) and `EvidenceBasis` (synthetic or unapproved data is `not_validation_evidence`; nothing is ever called validated, no target or pass / fail is encoded, and nothing is connected to activation). Standard library plus the approved `numpy` only. Methods, values, support thresholds, the agreement statistic, multi-label agreement, significance testing and wiring remain owner decisions. No model, dataset, user text, package, network call or production change; `user_text_rules_v1` stays active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED.

> **Addendum to ADR-050 (2026-10-29) — rubric rule 13; the rubric / baseline "even if" alignment is deliberately left UNRESOLVED.** The owner named three outcomes for the one place where the draft annotation rubric and the production baseline disagree (a current clause qualified by "even if": `ALIGN_BASELINE_TO_RUBRIC`, `ALIGN_RUBRIC_TO_BASELINE`, `KEEP_DOCUMENTED_DIFFERENCE`) and said to keep the decision unresolved, changing neither code nor rubric, if no choice was supplied. None was, so rule 12 and `core/user_text_sentiment.py` are unchanged. Verifying every category against the baseline found a second disagreement (a current clause joined to a conditional clause by "and" with no comma is lost; with a comma it is labelled), that a past-feeling-only text is read as neutral and weak while a quotation-only or other-person-only text is declined, that the baseline reports no topic from a quotation or another person's clause, and that it has no `hedged` flag. Rule 13 was added to the draft rubric (quotations, other people's statements and past feelings give no current sentiment, tone or preference; a current view elsewhere is labelled alone; every unsettled case is `rubric_unclear`); it prescribes no label and adds no example, and its first draft's sentence about topics was removed so as not to create a new disagreement. The nine open annotation-policy questions are items AP1 to AP9 of the validation decision sheet with blank owner entries. The rubric is still `v0-draft` (rubric SHA-256 `5a5be11cbe06f0685c91d17670c814c42b1373202d852a70e8d905ed1fbc48a2`, excerpt `cc465ffdaad2f4452987df62955146c5664bd929817878d6c5018ba999f93f22`, rebuilt only by `scripts/build_dry_run_package.py`). Production behaviour, `user_text_rules_v1` and `SENTIMENT_MODEL_ENABLED=false` are unchanged.

> **Addendum to ADR-052 (2026-10-29) — statistical-policy decision matrix prepared; no value approved; evaluation-script integration designed, not built.** The candidates the owner named (95% level, 2,000 bootstrap resamples, seed 42, subgroup support 20, macro-F1 0.80, accepted-prediction precision 0.85) and the earlier proposals (class supports and quotas, held-out size, agreement statistics) are recorded as candidates in a matrix of 34 rows in `reports/sentiment_model_approval_record.md`, each with its source, what `metrics.py` does today and a blank owner decision; the questions with no candidate (agreement floor, multi-label agreement, ECE method and ceiling, coverage and abstention limits, per-class recall floor, the interval policy for targets, the no-winner policy, significance testing, the label set, and whether a report may ever say "validated") are listed as unresolved. Because the brief makes the policy-dependent metric changes conditional on approval, `training/sentiment/metrics.py` is unchanged. The integration of `evaluate_sentiment_model.py` is a seven-step design (frozen manifest, hash verification, an `EvidenceBasis` derived from the manifest alone, the existing group-aware split, the rules baseline and an approved model, one JSON report, no target-dependent exit code) with its blockers stated; nothing is connected. A new guard test keeps the "nothing decided" state from drifting. No dependency is needed by any proposed method; any `scipy.stats` use would need a dependency approval. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED.

> **Addendum to ADR-050 (2026-10-29) — annotation-policy decisions AP1 to AP9 and the comma-less rule; the production baseline is not changed.** The owner decided: quotations, other people's statements and past feelings give `NO_CURRENT_VIEW`; a current statement qualified by "even if" is `KEEP_DOCUMENTED_DIFFERENCE` (rubric rule 12 and the baseline both stay, comparison not claimed, reported as a separate group); hypothetical-only text is `UNCERTAIN_WEAK`; mixed current and hypothetical text is `LABEL_CURRENT_ONLY`; a negated hypothetical is `NO_CURRENT_VIEW`; a hedged want is current and a conditional one is not (`HEDGED_CURRENT_CONDITIONAL_NOT_CURRENT`); topics in non-current wording are `TAG_TOPIC_ONLY`; and a conditional clause joined by "and" without a comma is `RETAIN_DOCUMENTED_BASELINE_BEHAVIOR`. None authorises a change to `core/user_text_sentiment.py`, so the baseline stays as is, and the draft rubric (still `v0-draft`, not frozen; SHA-256 `bcd6b56da929e984faabba825b3377a78a610862d7b0b19e5a6b43e19738b7c0`, annotator excerpt `a7032ef0b3c6bd747d312a74ab433826bb0025468fba4eb1d717877933e38c6e`, rebuilt only by `scripts/build_dry_run_package.py`) was made consistent with the decisions: rule 13 tags topics and labels a text with nothing current `uncertain`, and section 7 lists the documented differences (a past-only text, topics in quotations and other people's clauses and the `hedged` flag are flagged for the owner to confirm).

> **Addendum to ADR-052 (2026-10-29) — evaluation policy approved and enforced offline as gates; the frozen-set plumbing built; nothing connected, nothing activated.** After two explicit owner answers (approve every stated value; adopt the assistant's proposal for the items with none), 26 statistical-policy decisions are recorded in `reports/sentiment_model_approval_record.md`: level 0.95, 2,000 resamples, seed 42, stratified percentile bootstrap (the kappa interval stays a non-stratified item bootstrap), supports 75 per primary class, 20 per subgroup and 300 held-out, primary labels positive / negative / neutral, `COHEN_KAPPA` with no floor, specific agreement and alpha reported, multi-label agreement deferred, pre-adjudication agreement primary, 10 bins and report-only ECE, coverage 0.70 and abstention 0.30, macro-F1 0.80, accepted-prediction precision 0.85, no recall floor, no significance test, and a validation-wording rule. `training/sentiment/metrics.py` now holds these values in two mappings only, behind `StatisticsPlan.owner_approved()` and `EvaluationPolicy.owner_approved()` (`approved=True` refused for any other value) and evaluates them as GATES in `assess_against_policy`, never as activation rules: the output is `validated`, `not_validation_evidence`, `descriptive_only` or `insufficient_support`, ranks and selects nothing, and states that activation (R14) also needs a lower-bound rule that is not approved. `EvidenceBasis` requires eight conditions. A new `frozen_evaluation.py` verifies an approved frozen set (hashes, counts, three splits, exact and near-duplicate exclusion) and builds the evidence basis; its manifest schema is a proposal awaiting the owner's confirmation, and neither it nor the statistics are connected to `evaluate_sentiment_model.py`, a model or a dataset. 61 in-memory mutations of this code and its predecessors are all detected. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED.

> **Addendum to ADR-050 (2026-10-29) — AP8 `CONTEXT_DEPENDENT`: the one production-baseline change for polite forms.** The owner approved a change limited to polite-form handling. A polite clause ("would like" / "would prefer") whose same-sentence successor is a bare condition (`if`, `unless`, `provided that`, `as long as`, `assuming`, `in case`, optionally preceded by "and" or "only") is now conditional and gives no preference; a successor with a want of its own is not a bare condition, so a current want beside a conditional one is kept. Unchanged on purpose: a non-polite want with a trailing condition, "would love", "would rather", the comma-less form (`RETAIN_DOCUMENTED_BASELINE_BEHAVIOR`), the relevance gate (a short sentence without a finance word is still declined) and the method label `user_text_rules_v1`. Rule 12 of the draft rubric (still `v0-draft`, not frozen; SHA-256 `346c5dce27bd37f493decc4d55876adc6dbdf6008e48f10c318f74e217896e8e`, excerpt `d98ece044dde43c36b1337d8e4df7cc7015f2b84d1c36402447f2601f180e778`, rebuilt only by the official builder) carries the same wording. A further documented difference, (f), is on record: a current preference plus a hypothetical clause gives baseline sentiment `uncertain` with the preference kept, where the rubric labels the current clause alone.

> **Addendum to ADR-052 (2026-10-29) — remaining evaluation-policy decisions recorded; frozen-manifest schema confirmed and wired to local fixtures; nothing activated.** After the owner confirmed the recorded readings and approved five recommended choices, the record holds: no lower-bound activation rule (intervals are reported, never gated, and a report alone never recommends activation; R14 decides); multi-label agreement deferred (topics and preferences stay descriptive); the kappa interval stays a non-stratified item bootstrap; the macro-F1 gate is decided by the strict view with the selective view reported beside it; and the frozen-manifest schema approved with the owner's extra fields (purpose, licence and provenance, content / label / rubric / annotator-manifest hashes, split assignments, group metadata, duplicate results, primary label set, annotation and adjudication metadata, evidence-basis status, creation timestamp, immutable manifest hash). `EvaluationPolicy` carries the four newly decided options and accepts only those values. `frozen_evaluation.py` implements the schema (personal-data markers refused, the manifest's own hash and all file and recomputed record hashes verified before any evaluation, declared evidence status compared with the computed one) and `evaluate_sentiment_model.py` reaches it only through `load_frozen_evaluation` / `evaluate_frozen`: the evidence basis comes from the verified manifest alone, a model artifact is refused, the report holds no record text or id, nothing is ranked or selected, and the exit status never depends on a target. No real manifest, dataset, model or route exists or is connected. 80 in-memory mutations of the new and earlier code are detected. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED.

> **Addendum to ADR-052 (2026-10-29) — consolidated approval form issued; Phases 2 to 7 not started.** *(Answered in part later the same day: see the next addendum.)* Every remaining step of the real-checkpoint plan is behind a hard gate that nobody has opened (model licences and revisions, a metadata query, network and environment approvals D10 to D13, dataset rights and annotation R8 to R13, activation R14), so the work was limited to the independent parts: one consolidated approval form (`reports/sentiment_consolidated_approval_form.md`, all entries blank, recommendations labelled as not answers, a phase map), a threat-model analysis of the real-checkpoint path (`docs/THREAT_MODEL.md` section 18) and a verification of what the current code can do. Findings: the base-model download is implicit inside training and has no file allow-list, per-file hash record, host or redirect enforcement or destination parameter, so the specified download phase needs a verified fetch step (and D10 path B) before it can be met; no metadata-query tool exists; a labels-only predictions file cannot be calibrated; whether independently authored fictional text counts as non-synthetic decides whether `validated` is reachable. No Hugging Face contact, download, installation, dataset, annotation or activation took place. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED.

> **Addendum to ADR-052 (2026-10-29) — consolidated approval form answered in part: E1 and E2 approved, R14 unresolved, no phase unlocked.** The owner approved **E1** (a verified download / fetch step with a file allow-list, per-file SHA-256 verification, host and redirect checks, an explicit destination and rollback; the fetch step only, not the metadata-query tool, not the trainer local-directory parameter, not any network use) and **E2** (calibration requires probability-bearing predictions; labels-only predictions stay descriptive-only and can never produce `validated`), and explicitly left **R14** unresolved. The brief supplied no value for the models, the per-model licence, provenance, revision, file, host, hash and usage items, the metadata query, D10 to D13, R8 to R13 or the remaining code and format approvals, and a recommendation is not an answer, so those 49 entries stay `KEEP UNRESOLVED` and D10 to D13 stay `BLOCKED`. Every phase from 2 to 7 therefore remains locked; E1 and E2 authorise building, with fakes and without network use, and nothing was built. A guard test holds the form to the recorded state and to the dependency rules (rejected, blocked or unresolved items never unlock a phase; no download without an approved model with all its items, the metadata, D10 to D13, the cache location and E1; no evaluation without D1 to D20, a frozen manifest and the earlier phases; no activation without a separate F1 approval). `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, R6 to R14 UNRESOLVED.

> **Addendum to ADR-052 (2026-10-29) — Phase 2 gate presented again: no value supplied, Phase 2 stays locked; query constrained to read-only metadata.** *(The dependency question it raises was settled in the next addendum.)* The owner listed the outcomes for A1, A2, the fourteen A3 items and B1 to B10 but chose none and supplied no value, and said not to infer anything from recommendations, earlier proposals, model-card labels or silence, so all of them stay `KEEP UNRESOLVED` and no candidate unlocks Phase 2. Two statements in the brief are recorded: the metadata query is read-only and downloads no weights, tokenizer files, model configuration files, datasets or training artifacts (the form's B3 candidate, which listed `config`, was corrected; a label order can therefore only be read after an approved download); and an approved candidate with any unresolved A3 item does not unlock Phase 2. A dependency question is raised and not decided: Phase 2 exists to read the revision, files and licences, yet the gate requires them to be approved first, so either the owner supplies them from their own reading (Phase 2 then verifies them) or approves an explicit rule making them provisional. Guard tests (95) hold the form to the recorded state and to the dependency rules, including that metadata authorisation authorises no file access or download. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED, E1 and E2 approved only as future build authorisations.

> **Addendum to ADR-052 (2026-10-29) — Phase 2 circularity resolved by Option 2; restricted metadata-only query approved; Phase 2 still locked; nothing queried.** The owner decided that A3.1 to A3.8 (licences, training-data terms, commercial-use restrictions, attribution and share-alike, suitability limits, exact immutable revision, permitted file list) are PROVISIONAL for the selected candidate until Phase 2 metadata verification, which may verify, confirm or reject them; a provisional item authorises no download, tokenizer or config access, dataset access, training or inference, so all eight must be confirmed before Phase 4; A3.9 to A3.13 must be approved before Phase 2 unlocks. B1 and B3 to B10 were approved as a metadata-only query: anonymous and read-only, the one selected model identifier only, API metadata / model-card text / licence metadata / file listing / immutable revision metadata / redirect metadata only (no weights, tokenizer files, `config.json`, datasets, training artifacts or generated files), at most 10 requests, `huggingface.co` only (an unnamed redirect endpoint counts as an unapproved host), no redirect to a file-download host, sanitized metadata stored only in the approval report, with seven stop conditions. B2 stays unresolved because no candidate is selected, and the query tool does not exist (E1 covers the fetch step only), so Phase 2 stays locked: 0 requests, no host contacted, no field queried. A guard test (52) holds the form to the recorded state and the dependency rules. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED.

> **Addendum to ADR-052 (2026-10-29) - the approved E1 / E2 / B9 capabilities built offline; nothing queried, downloaded or installed; production unchanged.** Under the owner's build authorisations E1 and E2 and the restricted B9 query, `training/sentiment/hub_fetch.py` (standard library only, injected transport, explicit `FetchPolicy`, three metadata URL kinds, redirects only to policy hosts, fixed error codes, sanitised records, per-file SHA-256, rollback, destination outside the repository, pickle-capable formats refused) and probability-bearing predictions in `evaluate_sentiment_model.py` (all records or none; validated classes, range, sum and argmax; no content echoed; the rules baseline carries no probabilities) were written and tested with a scripted transport and a loopback server only. `test_hub_fetch.py` (97 tests, 25 of 25 deliberate defects detected), `test_user_text_robustness.py` (12 tests: seeded arbitrary input never breaks the rules-baseline contract) and the E2 tests (19 new, in `test_evaluate_frozen_mode.py`) were added. The tool has never contacted a real host; no model, dataset, revision or licence is approved; Phase 2 and every later phase stay locked; `user_text_rules_v1` remains the production method and `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-29) - Phase 2 unlocked for `ProsusAI/finbert` and executed once; stopped; nothing else changed.** The owner's second reply (recorded in `reports/sentiment_consolidated_approval_form.md`) selected one candidate, recorded B2, A3.9 to A3.13 and E5 and gave provisional A3.1 to A3.8 values, which unlocked Phase 2 only. The restricted metadata query ran once: 2 anonymous requests to `huggingface.co`, no redirect, revision equal to the proposed `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`, licence tag `cc-by-nc-sa-4.0`, no file or model-card request. The tool stopped at the file listing (`malformed_response`; probable cause a leading-dot file name, fixed offline with a separate listing-only name pattern - the download path keeps the strict one). No provisional field was confirmed or rejected, no file was downloaded, no package installed, no dataset or user text accessed. Phase 2 is incomplete; Phases 3 to 8 remain locked; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`. The earlier addendum's statement that the tool had never contacted a real host is superseded by this one for the metadata query (the download path is still unexecuted).

> **Addendum to ADR-052 (2026-10-29) - Phase 2 metadata verification completed by an owner-approved re-run; nothing else changed.** The re-run (3 requests, 5 of 10 in total, `huggingface.co` only, anonymous, no redirect, no stop) obtained the file listing and the model-card text for `ProsusAI/finbert` at the proposed revision, and each provisional field was recorded as CONFIRMED / UNRESOLVED / INSUFFICIENT EVIDENCE in the consolidated form (none REJECTED; these are verification results, not approvals). Nothing was downloaded; no file other than metadata was requested; no package, dataset or user text; Phases 3 to 8 remain locked; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-29) - owner decisions for Phase 3; Phase 3 not started.** The owner chose Path B (a local conversion-free workflow) for the D10 gate, anonymous HTTPS to `https://huggingface.co` only for D11, a disposable Python 3.11 CPU environment for D12, and temporary-cache and environment paths under `C:\Users\Administrator\.copilot\`; for D13 the owner decided to complete TASK-CERT-1 before any model download, which keeps D13 BLOCKED until the task is done. The owner also rejected A3.5b (share-alike scope) until the legal scope is verified and accepted FinBERT only as an offline research candidate. Nothing was created or installed; no code changed; the Path B trainer change is documented, not applied. `user_text_rules_v1` remains active and `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-29) - Path B loader prepared offline; S1 set discrepancy resolved by the record; no change applied.** A standalone, unwired module (`training/sentiment/local_model_dir.py`) now implements the Path B checks (exact five-file directory, verified manifest, per-file SHA-256, safetensors only, `local_files_only=True`, `trust_remote_code=False`, probability-bearing output in the E2 format) with synthetic-fixture tests only; the trainer, evaluation script, backend and settings are unchanged and the wiring awaits the owner's approval. The recorded S1 set is the executed 35-wheel list (`setuptools==81.0.0`); the early 84.2.1 table is marked superseded. TASK-CERT-1 remains BLOCKED. `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-29) - S1 executed in a disposable environment; Path B wired offline; TASK-CERT-1 stopped.** Under the owner's execution approvals the exact 35-wheel S1 list (`setuptools==81.0.0`) was retrieved from PyPI, verified and installed with `--require-hashes` in a disposable environment, validated (CPU-only, `pip check`, imports, stand-in, artifact, tokenizer, model-safety and Path B tests; zero network, Hub, pickle and `torch.load` calls under guard) and deleted. TASK-CERT-1 stopped before any change because the approved lock holds no `pip` wheel; the project environment is unchanged. `local_model_dir.py` is wired into the offline trainer and the offline evaluation script (verified local directory only, never a Hub identifier); no route, API schema, setting or dependency manifest changed. A3.2 and A3.3 unresolved, A3.5b rejected, D1 to D20, E3, E4, R14 unresolved. `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-29) - TASK-CERT-1 completed.** After a hash-checked inspection of `pip-26.2.2-py3-none-any.whl` (its vendored `certifi` is 2026.10.19, the first fixed release), the project environment's `pip` was upgraded 26.2.1 to 26.2.2 and `certifi` 2026.7.22 to 2026.10.23 together, hash-pinned and with no other change; the check suite and 1301 tests passed; a byte-verified offline rollback backup is kept. D13 (C4) is satisfied. No Hugging Face contact, no model, dataset or user text. `user_text_rules_v1` remains active; `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 and ADR-050 (2026-10-30) - participant-register validator, D13 calibration and schema-2 frozen metadata implemented offline; no decision changed.** `training/sentiment/participant_register.py` validates a participant / annotation register (anonymous codes, exactly two annotators, one adjudicator, one evaluator and at least one de-identification verifier, independence attestations, role-checked access authorizations with scope and dates, a deletion authorization, synthetic or consented status with consent metadata, no production service, no personal data or credential, errors that never echo a value or field name); it cannot verify independence, which stays the owner's attestation. `metrics.py` fits the D13 temperature on the calibration split only, on log-probabilities (so no logit is invented), applies it to held-out probabilities only and reports 10-bin strict and accepted-only calibration, descriptive-only below 20 scored examples and never `validated` or a recommendation (ADR-050's rules baseline stays labels-only and uncalibrated). The frozen manifest is schema 2 (register, verifier, consent and calibration-split hashes, temperature-policy version, data status, duplicate policy, approved group dimensions) with the register as a sixth verified input. A3.3, D1, D2, D5, D14, D16, D19, D20, E3 and R14 remain unresolved and A3.5b rejected; no real data, register or manifest exists; production stays `user_text_rules_v1` with `SENTIMENT_MODEL_ENABLED=false`.

> **Addendum to ADR-052 (2026-10-30) - deletion policy enforced in the register validator; guards against fixtures passing as evidence; no decision changed.** Following the owner's brief, `participant_register.py` requires a `deletion_authorization` authorized by the project owner, with raw text and temporary annotation files kept only until the evaluation, the audit verification and the R14 decision, only hashes, aggregate metrics and decision records retained afterwards, a rollback that restores metadata and aggregate records only, and completion verified and recorded. New tests assert that every fixture is visibly invented, that no FROZEN manifest or participant register exists outside the tests, and that neither an agreement result alone nor a calibration alone produces `validated`. E3 is approved for schema-2 offline implementation only; a real manifest still needs D1, D2, D5, D16, D20 and the other dataset approvals. A3.3, D1, D2, D5, D16, D20 and R14 remain unresolved and A3.5b rejected.

> **Addendum to ADR-050 and ADR-052 (2026-10-30) - phase closure.** The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved. The rules baseline `user_text_rules_v1` (ADR-050) remains the production method with `SENTIMENT_MODEL_ENABLED=false`; ADR-052's gated Transformer path stays implemented, tested on synthetic fixtures and random local stand-ins only, and unused. Owner values: A3.3 unresolved; A3.5b rejected until the legal scope is verified; D1, D2, D16 and R14 unresolved; D5 kept `v0-draft`; D20 rejected for this phase; E3 schema-2 offline implementation only; E4 keep all six documented differences. Reopening any of them is a new phase with a new explicit approval request. Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model downloaded: no; real dataset created: no; real evaluation run: no; production activation: no; intensity regression: disabled; blockchain / ledger sentiment payload: none.

## ADR-053 — Research-Only Comparison of Two Pretrained Sentiment Classifiers (FinBERT, Twitter-RoBERTa)

**Date:** 2026-11-03. **Status:** Accepted for implementation; the models themselves are BLOCKED (licence, weight format) and nothing is installed, downloaded, trained or evaluated.

**Context.** The owner asked for a pretrained-only prototype: run `ProsusAI/finbert` and `cardiffnlp/twitter-roberta-base-sentiment-latest` as independent classifiers, compare them with each other and
with the rules baseline, and show the result, with no human annotation, no new dataset and no fine-tuning. ADR-052's path serves ONE fine-tuned, validated, calibrated artifact and refuses anything
unvalidated; it is unchanged and cannot express this use.

**Decision.** Add `backend/wealthpilot/core/sentiment/` as a separate, research-only, display-only path. (1) Off by default (`SENTIMENT_TRANSFORMERS_ENABLED=false`). (2) The two candidates, their exact
revisions and their licence/format status are CODE constants (`registry.py`), changed only by a reviewed commit with an ADR, never by environment or metadata. (3) A candidate runs only if its licence is
`license_verified` AND its weights are published as safetensors; findings of 2026-11-03: FinBERT is `cc-by-nc-sa-4.0` (share-alike rejected by the owner, A3.5) and Twitter-RoBERTa publishes no
safetensors file at the reviewed revision and has no recorded approval, so **neither may run**. (4) Local, revision-pinned, SHA-256-verified artifacts under `models/sentiment_pretrained/<key>/` only;
no pickle-capable file; labels mapped by name from `config.json`; CPU; one worker; timeout; 30 s failure back-off; fixed reason codes. (5) The two results are never averaged or tie-broken; disagreement
yields `uncertain`; the rules reading is the fallback and a visible comparison partner. (6) The output is an optional `transformer_research` object composed after, and never read by, the insight
composition; it carries no confidence and no intensity; scores are labelled uncalibrated. (7) `GET /api/sentiment-model/status` gains additive per-candidate fields.

**Consequences.** The feature is implemented and tested with stand-in backends only (TESTED_WITH_MOCKS); no real inference has occurred and no accuracy, calibration or superiority claim is possible.
Production remains `user_text_rules_v1`; D20, A3.3, A3.5 and all dataset/activation gates are unchanged. Enabling a candidate needs: the owner's licence decision, approval of the four packages and a
pinned download, a registry change with an ADR, then a separate opt-in smoke test.

**Rejected alternatives.** Averaging or voting across models (different architectures, uncalibrated scores); an LLM tie-breaker (forbidden); loading `pytorch_model.bin` (pickle-capable); reading licence
status from a file or variable (would let configuration override a legal finding); fine-tuning or an intensity head (needs approved labelled data); defaulting an unknown label to neutral.

## ADR-054 — Review of Replacement Pretrained Sentiment Candidates (Both Blocked; Active Pair Unchanged)

**Date:** 2026-11-03. **Status:** Accepted. ADR-053 is unchanged and remains the history of why FinBERT and Twitter-RoBERTa cannot run.

**Context.** The owner proposed replacing the blocked pair with `tooshlegacy/distilbert-financial-tweet-sentiment` (financial) and `Horizon-Labs/multilingual-sentiment-small` (general), on condition that both
pass a licence and provenance gate. Both were reviewed from the public repository metadata and raw files; no weight was downloaded and no package installed.

**Findings (verdicts use the owner's vocabulary; none is `approved_for_research_inference`).**
- `tooshlegacy/distilbert-financial-tweet-sentiment` @ `ba66b6a858cc775dc9e78d773c437b7e984fd5fc` — **`blocked_by_provenance`**. Apache-2.0 appears only as a metadata tag: the repository has no LICENSE or NOTICE file and names no author or
  organisation. Base `distilbert-base-uncased` is Apache-2.0. It was fine-tuned on `zeroshot/twitter-financial-news-sentiment` (MIT declared), whose tweets were "collected using the Twitter API", with annotators recorded only as "other" and no
  terms-of-service or redistribution statement: the same unresolved tweet-provenance issue that blocked the CardiffNLP candidate. No Financial PhraseBank and no share-alike wording were found. Safetensors present (sha256 `97fcaa54...6ac0`).
  Labels `0 Bearish, 1 Bullish, 2 Neutral`.
- `Horizon-Labs/multilingual-sentiment-small` @ `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` — **`blocked_by_approval`**. A standard Apache-2.0 LICENSE and a NOTICE exist; the base `jhu-clsp/mmBERT-small` is MIT; `SHA256SUMS` agrees with the Hub's recorded hash
  for `model.safetensors` (`f0d0b6d2...2dd1`). The open items are owner decisions, not defects: it was trained on FineWeb/FineWeb-2 web-crawl snippets (ODC-BY covers the dataset, not the rights in the underlying pages) plus synthetic text written by an
  LLM (Qwen/Qwen3.8-27B, Apache-2.0 declared), with **soft labels from that LLM and no human annotation**; the real/synthetic split is not stated; the card's claim "trained only on openly licensed text" cannot be verified from the repository; and its config
  uses transformers 5.x format (v5 keys such as `rope_parameters`) while the proposed pin is 4.57.1 (compatibility unverified), and version 5 reportedly drops TensorFlow support that the installed TensorFlow 2.17 workflow relies on. Labels `0 negative, 1 neutral, 2 positive`.

**Decision.** (1) The replacement is NOT performed: the instruction was conditional on both passing. The active registry (`registry.py`) still lists FinBERT and Twitter-RoBERTa, both gated off, so runtime behaviour is unchanged. (2) All four reviews are recorded as
code constants (`core/sentiment/reviews.py`) and exposed read-only on `GET /api/sentiment-model/status` (`reviewed_candidates`), so a verdict cannot be changed by configuration. (3) The normaliser accepts the financial-tweet vocabulary
(`Bullish` -> positive, `Bearish` -> negative, case-insensitive) and returns the model's own spelling as the native label; mixed vocabularies (for example `bullish` and `positive` together) and unknown labels are refused.
(4) Nothing is installed or downloaded.

**If the owner approves a candidate later** the change set is bounded: add its `Candidate` to `registry.py` with `license_verified` (reviewed commit), generalise the `finbert` / `roberta` keys to role keys (`financial` / `general`) in `inference_service.py`, `schemas.py`, the TypeScript labels and fixtures, regenerate the API types, approve and install the dependencies, download the pinned safetensors with `scripts/write_pretrained_manifest.py` for the manifest, and write the opt-in real-weights smoke test.

**Consequences.** No change to production (`user_text_rules_v1`), D20, A3.3, A3.5, F1/R14. The model-card metrics for the financial candidate are self-reported on its own tweet validation split; they are not WealthPilot evidence and are not shown anywhere in the product.

> **Addendum to ADR-054 (2026-11-04) — scoped owner decision for the Horizon multilingual model.** The project owner decided that `Horizon-Labs/multilingual-sentiment-small` at revision `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` **may be considered for RESEARCH INFERENCE ONLY**, accepting its disclosed web-crawl and LLM-generated training data and the absence of human-validated labels. Its review verdict therefore changes from `blocked_by_approval` to `approved_for_research_inference` (`core/sentiment/reviews.py`, `HORIZON_OWNER_DECISION`). **Not authorised:** production activation, dataset creation or collection, fine-tuning or training, automatic model downloads, redistribution, commercial use, any human-validation, accuracy or calibration claim, any financial-decision impact; package installation, weight download, running inference and the registry change each still need their own approval. **Unchanged:** A3.3 (general training-data terms), A3.5 rejected, D20 rejected, F1/R14, all dataset gates; `tooshlegacy/distilbert-financial-tweet-sentiment` stays `blocked_by_provenance` and the financial slot is empty. Compatibility findings (2026-11-04, read from public sources, nothing executed): `transformers` 4.57.1 is NOT compatible with this config (it would silently ignore `rope_parameters` and use `local_rope_theta` 10000 instead of 160000); `transformers` 5.17.0 is required, so the ADR-052 pins (tokenizers 0.22.1, safetensors 0.6.2) are superseded for this model; the earlier statement that version 5 "reportedly drops TensorFlow" is not supported by what was read (5.17.0 declares no TensorFlow dependency) and is withdrawn; ONNX Runtime is plausible but unverifiable without the artifact and needs an artifact-policy extension. Plan and proposed pins: `docs/sentiment/horizon_runtime_plan.md`. The active registry is unchanged; production remains `user_text_rules_v1` with `SENTIMENT_TRANSFORMERS_ENABLED=false`.

> **Addendum to ADR-054 (2026-11-04) — Stage A executed.** With the owner's Stage A approval, the Horizon model (`e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`) was installed and run **only in an isolated environment outside the repository and outside the project `.venv`**: transformers 5.17.0, tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 1.33.0, torch 2.15.0+cpu, numpy 1.26.4 (the application's version), installed from the hash-pinned lock `docs/sentiment/stage_a/requirements-stage-a.lock.txt` (resolver dry-run first; 35 packages; `pip check` clean). The eight approved files were downloaded at the exact revision and verified against the repository's `SHA256SUMS`. Real CPU inference completed on eight fictional sentences: **INFERENCE_VERIFIED for the reference implementation, in the isolated environment only**; native labels `0 negative, 1 neutral, 2 positive`; the raw output is logits and exactly one softmax reproduces the library pipeline (no double softmax); results are bitwise stable across repeats; 16 to 23 ms per sentence on CPU; peak memory about 1.1 GB. This is a smoke test: **no accuracy, calibration, human-validation or superiority claim is made.** Unchanged: the active registry, `SENTIMENT_TRANSFORMERS_ENABLED=false`, production `user_text_rules_v1`, the application `.venv` and TensorFlow, A3.3 / A3.5 / D20 / F1. Stage B (in-application runtime, registry change, in-app smoke test) is not authorised. Report: `reports/sentiment_transformer_stage_a_report.md`.

## ADR-055 — Role-Based Research Slots, Adapter Lifecycle Guards, Horizon Left Unregistered

**Date:** 2026-11-05. **Status:** Accepted. Supersedes the rigid two-slot (`finbert` / `roberta`) shape of ADR-053 for the never-enabled `transformer_research` response; ADR-053 and ADR-054 remain the history of why those candidates cannot run.

**Context.** Both ADR-053 candidates are blocked, the financial replacement is blocked by provenance, and the owner approved Horizon for RESEARCH INFERENCE ONLY (ADR-054 addendum). Stage A verified the model by direct loading; Stage B2.1 (with the setuptools 81.0.0 recovery) verified that TensorFlow and PyTorch coexist in the project `.venv`. Nothing authorises registering Horizon or activating any Transformer in production.

**Decision.**
1. **Role slots replace fixed model slots.** The comparison has two roles, `financial` and `general`. A `Candidate` (`core/sentiment/registry.py`) carries `registration` in {`registered`, `pending_owner_approval`, `historical`}. `runnable_in_principle` = licence verified AND safetensors AND registered. Horizon is `pending_owner_approval`, so **no slot has a registered model**; the slots report `no_candidate_approved` (financial) and `registration_pending` (general). An empty slot is not a failure and nothing is substituted into it.
2. **Horizon is NOT registered, no flag changes, `user_text_rules_v1` stays the production method.** Registering it is a one-line code change that needs an explicit owner decision; it is listed as a blocker in `SENTIMENT_GOVERNANCE_STATUS.md`.
3. **Comparison semantics.** One answering model is compared with the rules-based reading (agree -> its label; differ -> `uncertain`/`rules_disagree`; rules abstained -> model label; rules "weak" -> `uncertain`/`context_safeguard`); no model answering falls back to the rules-based label. Two answering models: agreement or `models_disagree`. Still no confidence or intensity field; probabilities are one uncalibrated softmax.
4. **Lifecycle guards (`core/sentiment/adapter.py`).** The status path (`candidate_status`) never loads, hashes or verifies. A per-candidate non-blocking lock returns `loading` to concurrent callers (the first caller loads synchronously; no background thread, no lifespan hook, no startup warming). A timeout opens a 30 s circuit breaker that returns `timeout` immediately. Unexpected exceptions map to fixed reasons (`load_failed` for OSError/MemoryError, else `internal_error`) and never carry a message to the client. `build_transformer_research` never raises; on any internal failure it returns `internal_error` slots and the rules-based reading. An optional `SENTIMENT_TRANSFORMERS_THREADS` (1-64, blank = untouched) is applied inside the one guarded torch module.
5. **English-only gate retained.** Text the rules gate marks `unsupported_language` (including Tamil and code-mixed text) never reaches a model; the multilingual claim of the model is NOT used (no multilingual approval, no evidence).
6. **Breaking change** to the `transformer_research` object shape (`models` list keyed by slot, `model_versions` slot -> revision, `overall_*`, `model_vs_rules`). It was never enabled in production, so no consumer exists; the TypeScript types, fixtures and the panel were regenerated. `GET /api/sentiment-model/status` gained `research_slots`, `research_models`, `transformers_enabled`, `production_method` and `production_activation` (all read from code constants, no weights loaded).

**Not authorised and not done.** Production activation (F1/R14), registering Horizon, enabling the flag, committing or pushing, copying model files into `models/`, fine-tuning, dataset creation, any accuracy, calibration or human-validation claim, any effect of sentiment on risk, goals, portfolio, recommendations or compliance, B2.2.

**Consequences.** The real adapter path has been verified only with mocks and fault injection; `INFERENCE_VERIFIED` through the adapter requires the opt-in `test_horizon_real_weights_smoke.py` after the owner approves placing the verified files (Stage B). Stage A / B2.1 verified the model by direct loading only.

## ADR-056 — Horizon Registered as the `general` Research Candidate; Verified Artifacts Placed Locally (R1, R2)

**Date:** 2026-11-07. **Status:** Accepted. Implements the decision that ADR-055 left to the owner. ADR-054 (research-inference approval) and ADR-055 (role slots) are unchanged.

**Context.** The owner instructed three actions: R1 register Horizon as the `general` research candidate, R2 place the exact approved artifacts in the approved location and run the application-adapter smoke test, R3 diagnose the intermittent native crash in `tests/training`. Nothing else was authorised: not production activation, not a financial-domain use, not datasets, training, human evaluation, or any previously rejected governance item (D20, A3.5; A3.3, E3, F1 unresolved).

**Decision.**
1. `HORIZON.registration = REGISTERED` (revision `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`, role `general`). The `financial` slot remains empty. Registered means "may run when the research flag is on and its verified files exist". `SENTIMENT_TRANSFORMERS_ENABLED` and `SENTIMENT_MODEL_ENABLED` stay `false`; `user_text_rules_v1` stays the production method; `production_activation` stays `not_activated`.
2. The eight approved files (LICENSE, NOTICE, SHA256SUMS, config.json, special_tokens_map.json, tokenizer.json, tokenizer_config.json, model.safetensors) were copied from the Stage A directory to `models/sentiment_pretrained/horizon/`, re-hashed against the repository `SHA256SUMS` and the Stage A record, and a `pretrained_manifest.json` was written with `scripts/write_pretrained_manifest.py` (`tokenizer_length` 256000, the offline `len(tokenizer)`). `.gitignore` now ignores `models/sentiment_pretrained/` in full: weights, tokenizer and manifest are never tracked, committed or pushed.
3. The opt-in smoke test `tests/backend/core/test_horizon_real_weights_smoke.py` now uses the real registered constant and exercises the application's adapter and service on fixed fictional sentences, with the Stage A logits as a cross-check, a single-softmax check, privacy, concurrency, timeout and failure-isolation checks. It is a smoke observation, not an accuracy evaluation.
4. Unit tests are made hermetic: an autouse fixture substitutes an empty directory whenever the default (real) model directory would be used, so no unit test can load the real weights by accident.
5. The public owner-decision text is extended with a dated update; the 2026-11-04 text is not edited.

**Not authorised and not done.** Production activation (F1/R14), any financial-domain claim, any accuracy, calibration or human-validation claim, committing or pushing model files, dataset creation, training, multilingual use (non-English text still abstains before the model), B2.2.

**Consequences.** With the flag on and the files present, the `general` slot answers and the combined reading follows the ADR-055 rules (agree, differ, rules abstained, rules safeguard). With the flag off (default) the slot reports `disabled` and the rules reading answers. If the directory is missing or fails verification, the slot reports a fixed reason and the rules reading answers.
