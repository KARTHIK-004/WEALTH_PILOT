# WealthPilot AI Development Rules

The detailed development rulebook. `CLAUDE.md` is the concise entry
point; this file is where its rules are spelled out in full, with the
reasoning and the exact boundary of each one. When `CLAUDE.md` and this
file appear to disagree, `CLAUDE.md` and `docs/PROJECT_PLAN.md` win on
architecture (their own stated authority — see `docs/DECISIONS.md`'s
introduction and `CLAUDE.md` itself); this file should be corrected to
match, not treated as an override.

---

## Rule 1 — Read Before Coding

Before any non-trivial change: read the relevant section of
`docs/PROJECT_PLAN.md` (methodology/spec), `docs/MASTER_PROMPT.md`
(feature/page checklist), `docs/ARCHITECTURE.md` (current wiring),
`docs/MEMORY.md` (current state), and the most relevant recent
`reports/*.md`. Do not re-derive architecture from source code that a
document already describes accurately — but do verify against source
when a document might be stale (see Rule 29).

## Rule 2 — Scope Discipline

Implement only what was asked. Do not refactor unrelated code, redesign
unrelated UI, replace an approved library, or "clean up" a file you
happened to open for an unrelated one-line change. If you find an
unrelated issue, document it (in your response, or in `docs/MEMORY.md`
under Known Limitations/Blockers) — do not silently fix it.

## Rule 3 — Existing Code First

Before writing a new function, hook, component, or query, search for an
existing one that already does it. Reuse `LoadingState`/`ErrorState`/
`SectionUnavailable`/`NoProfileSelected` on the frontend; reuse
`core/goals.py`/`core/optimizer.py`/`core/compliance.py` functions on the
backend rather than reimplementing their logic inline in a node, route,
or service.

## Rule 4 — No Duplicate Implementations

Never build a second, parallel way to compute or fetch something that
already exists — a second financial formula, a second risk classifier
call path, a second "get the current customer" mechanism. If an existing
function is close but not quite right, extend or make it public
(`agents/nodes.py::load_portfolio_returns` was made public in Phase 28
specifically to avoid a second copy of its logic) rather than copy-paste.

## Rule 5 — Backend Numerical Authority

Every financial number is computed exactly once, in
`backend/wealthpilot/core/` or a trained model under `models/`. If a
number is needed anywhere else, it is added as an API field — never
recomputed, approximated, or derived client-side. See `docs/DECISIONS.md`
ADR-014.

## Rule 6 — Frontend Display-Only

React never calculates: risk, financial health, goal feasibility, Monte
Carlo probability, required contribution, emergency-fund status,
portfolio weights, compliance decisions, or recommendation strategy. It
may: format currency/percentages/dates, validate a form field's shape
(required, numeric, obviously-out-of-range), and manage UI/navigation
state. A form that submits raw user input (e.g. the Financial Inputs
card, Phase 28) still submits exactly what the user typed — never a
value derived from a formula.

## Rule 7 — ML Training Isolation

Training happens only in `training/<family>/`, invoked explicitly by a
human running a script — never inside a FastAPI request, a LangGraph
node, an agent, or a test (tests load already-trained fixture artifacts
or call pure functions, never call `.fit()` on production data as a side
effect). Serialized artifacts live under `models/<family>/`, loaded once
at startup (`api/lifespan.py`) and cached in-process.

## Rule 8 — Data Leakage Prevention

Never use information that would not have been available at prediction
time: no future transactions, no future market data, no fitting a
preprocessor on data that includes the test/validation fold, no target
information leaking into a feature. This applies even to a "static"
per-entity classification framing — a customer-level label still requires
point-in-time-correct features, not just row-level target exclusion.

## Rule 9 — Time-Series Rules

No shuffled train/test splits on time-ordered data. Use expanding-window
walk-forward validation with an embargo gap. Market models target
returns/volatility, never raw price levels. Filter FAR-Trans's
`Predicted_*`/`Not_Available` rows before training (they are another
model's output, not ground truth — CLAUDE.md rule 7).

## Rule 10 — Financial Logic

Never invent a financial formula, threshold, or methodology decision that
isn't specified in `docs/PROJECT_PLAN.md`/`docs/MASTER_PROMPT.md` or
already implemented in `core/`. When the spec is silent or ambiguous on a
genuinely consequential methodology point (example: Phase 28's choice of
which historical-return series to bootstrap Monte Carlo from, when no
customer-specific portfolio exists yet), resolve it using only
already-approved building blocks, and document the reasoning plainly
rather than silently picking a number. When genuinely blocked, ask.

## Rule 11 — Compliance

Compliance is binding and fail-closed: a rule whose required input is
missing is `triggered=True` at its own severity, never silently skipped
or treated as PASS. `enforce_gate` raises on REJECT; nothing catches it.
Rule conditions are Python functions registered by name in
`_RULE_REGISTRY` and referenced from `config/compliance_rules.yaml` by
that name — the YAML itself is loaded with `yaml.safe_load` only and
never supplies an executable expression. Do not weaken a rule's
condition, remove a rule, or change severities/precedence without an
explicit, scoped instruction to do so (see `docs/DECISIONS.md` ADR-018
for the one precedent of a narrow, explicitly-authorized compliance
change and how it was scoped).

## Rule 12 — Recommendation Precedence

Compliance > Savings-first > Risk > Goal > Market. A downstream layer may
only select among options the layer above it still permits; it may never
override a REJECT or force a non-savings-first allocation when the
emergency fund is insufficient. See `docs/DECISIONS.md` ADR-016.

## Rule 13 — Missing Data

Distinguish "genuinely zero," "unknown/not yet provided," "unavailable
(structural — will never exist for this customer, e.g. `expense_persona`
for a FAR-Trans customer)," and "not evaluated (upstream node never
ran)." Represent "not yet provided"/"unavailable" as `null` plus an
`*_unavailable_reason` string — never as `0`, never guessed, never
silently defaulted. This applies in the database (nullable columns, no
default-to-zero), the API (`Optional` Pydantic fields), and the frontend
(`SectionUnavailable`, never a blank chart rendered as if it were a real
zero).

## Rule 14 — Agent Boundaries

`agents/nodes.py` functions are pure `(AgentState, ...explicit deps) ->
AgentStateDelta` — no node mutates `state`, retrains a model, calls an
LLM, or implements graph routing. `agents/graph.py` wires nodes together
and routes; it contains no financial/ML logic of its own — it only calls
`core/`/`agents/nodes.py` functions and applies deltas via `apply_delta`.
Per-run dependencies (DB session, `GoalAssumptions`, `historical_returns`,
portfolio strategy) are threaded through `GraphDependencies` /
`RunnableConfig`, never bolted onto `AgentState` itself.

## Rule 15 — Gemini Boundaries

Gemini (`agents/explanation.py`) receives a fully-computed dict and
writes prose; it never calculates a number, selects a strategy, or
overrides compliance. Its structured output is validated against the
source dict field-by-field; any mismatch, missing field, timeout, or API
failure produces a templated, non-generative fallback
(`validation_passed: false`), never a raw exception and never a
plausible-sounding fabricated number. Gemini is only invoked when
`overall_status == "approved"`.

## Rule 16 — AutoGen Boundaries

`agents/debate.py`'s three bounded personas critique an already-computed,
already-compliant proposal. Debate output is bounded critique text, never
a source of a financial number, and is validated the same way explanation
output is (Rule 15).

## Rule 17 — LangGraph Boundaries

The compiled graph (`agents/graph.py::build_analysis_graph`) is the only
place node sequencing/routing is decided. No other module (API route,
service, script) re-implements or bypasses that routing to "shortcut" to
a result. `_safe_call` converts any unexpected node exception into a
structured `processing_failure` — a node's own internal error handling
must never let the graph silently continue as if nothing happened.

## Rule 18 — API Rules

Request/response models are Pydantic v2 schemas in `api/schemas.py`,
deliberately separate from internal `agents/state.py`/`core/*.py` models
(the public contract must not leak internal-only concepts — DB sessions,
model objects, AutoGen transcripts, Gemini prompts). Errors return RFC
7807 problem-details, never a bare 500 or an unstructured error string.
Every analysis-adjacent response carries `model_version` and
`data_source`. Frontend TypeScript types are generated from the live
OpenAPI schema (`npm run generate-types`), never hand-written — see
`docs/DECISIONS.md` ADR-006.

## Rule 19 — Database Rules

Any schema change ships as an Alembic migration
(`alembic revision --autogenerate`, reviewed before applying), applied to
both `DATABASE_URL` and `TEST_DATABASE_URL`. Prefer reusing an existing
table/column over adding a new one; when a new table genuinely is needed,
follow the established one-table-per-persistence-concern pattern
(`financial_goals`, `questionnaire_answers`, `financial_inputs`) rather
than widening `customers`. Every per-customer table/route is scoped by
`customer_id`/`profile_id` — see Rule 21.

## Rule 20 — Authentication

The prototype authentication system (`frontend/src/lib/prototype-auth.ts`,
`providers/auth-context.tsx`) is intentionally minimal — see
`docs/DECISIONS.md` ADR-020. Do not build out JWT/OAuth, server sessions,
password hashing, or role/admin features unless explicitly instructed;
doing so silently would contradict this project's own documented,
disclosed prototype-auth scope.

## Rule 21 — Customer Isolation

Every per-customer database query is scoped by the customer's id at the
ORM/query level, never filtered client-side after an unscoped fetch. No
UI control anywhere lets an authenticated user select, switch to, or view
a different customer's data — see `docs/DECISIONS.md` ADR-021. The
authenticated session's associated customer id is the single source of
truth every protected page reads (`providers/customer-context.tsx`).

## Rule 22 — Demo Data

Demo personas are synthetic identity + real pipeline output — never a
hand-inserted result (`docs/DECISIONS.md` ADR-022). New demo data is
created/updated through the real public API
(`backend/scripts/seed_demo_data.py`), with exactly one documented
exception (`risk_inputs.external_customer_id`, which has no public API by
design). Never hard-code a demo customer's numeric id into frontend page
components; resolve by name via the demo-account mechanism
(`lib/demo-customer.ts`) or the read-only lookup endpoint.

## Rule 23 — UI Rules

Use shadcn/ui primitives; do not hand-roll a component the CLI already
provides. Every API-dependent page/section handles loading, empty,
unavailable (with reason), error, and success states — see
`docs/DESIGN.md`. Never hide missing information behind a blank or
zero-looking state.

## Rule 24 — Accessibility

Preserve keyboard navigation, visible focus states, `aria-label`/
`aria-current` where already established, and accessible error messaging
(`FieldError`, `role="alert"` where used). A UI change must not regress
an existing accessibility property even when accessibility isn't the
change's main point.

## Rule 25 — Security

Never commit a secret (API key, password, database credential, token).
Secrets live only in `.env` (gitignored) and are read via
`pydantic-settings`; never echo a secret's value in a response, a log
line, a report, or a commit message. Never expose Gemini/AutoGen
chain-of-thought, prompts, or a raw exception message to the frontend —
see `docs/SECURITY.md`.

## Rule 26 — Testing

Backend: `pytest tests/ -v` (isolated — see Rule 30 on why `-q`/piped
through `tail` on a long run hides real-time progress; prefer
unbuffered output when the run is long). Frontend: `npx tsc -b`,
`npm run build`, `npx oxlint`. Add tests alongside code, not after,
covering the actual new behavior (a new endpoint gets isolation/validation
tests; a new orchestration wiring gets a real, unmocked graph-level test
where feasible — see `tests/backend/agents/test_financial_inputs_integration.py`
for the established pattern of preferring real data over mocks when
verifying a genuinely new live code path). Never claim a task complete
while a required regression test is failing, without first determining
whether the failure is a real regression or a known transient artifact
(see `docs/TEST_PLAN.md` §"Transient Failures").

## Rule 27 — Documentation

Update `docs/MEMORY.md` when current implementation state changes
materially. Add a new ADR to `docs/DECISIONS.md` when an architectural
decision is made or superseded — never silently edit an accepted ADR's
substance. Leave historical `reports/*.md` intact; add a superseded-by
pointer note inside an old report rather than rewriting its content when
a later phase changes what it described (see the notes added to
`reports/demo_data_completion_report.md` and
`reports/live_analysis_flow_fix_report.md` after Phase 28).

## Rule 28 — Phase Discipline

Work is planned and executed phase-by-phase. Implement only the
requested phase's scope; test; verify; document; report in the exact
format the phase's own prompt requested; then STOP. Do not automatically
continue into the next phase, even an obviously-related one, without
explicit approval — a bare "continue" from the user resumes in-progress
work, it is not approval to start new work.

## Rule 29 — No Silent Architecture Changes

If documentation and the actual, verified source code disagree, do not
silently pick one. Identify the conflict, determine whether it reflects
an intentional implementation change that documentation never caught up
to, and update `docs/MEMORY.md` (current state) and/or
`docs/DECISIONS.md` (if the architectural decision itself changed) to
resolve it — with the conflict and its resolution stated plainly, not
buried. Never rewrite a historical report to make the conflict disappear.

## Rule 30 — Completion Standard

A task is not complete until: the requested change is implemented within
its stated scope; the relevant test suite(s) pass (or a failure is
diagnosed as a known transient artifact, verified by isolated re-run);
`docs/MEMORY.md` is updated if state materially changed; and a report is
delivered in whatever exact format the task specified. "It compiles" is
not completion. "I made the change" without verifying tests is not
completion. Do not claim more than what was actually verified — e.g.
never claim browser-based visual verification occurred when no such tool
was available; state the limitation plainly instead.

## Rule 31 — Household Membership (Phase 32)

A household is identity and membership only — it carries **no financial
data** in Phase 32 and never feeds `POST /api/analysis`
(`docs/DECISIONS.md` ADR-031). The rules below are enforced by the database
itself (`households`/`household_members` constraints) and again by
`api/services/household_service.py`:

- **One active household per customer.** `UNIQUE(customer_id)`; a customer
  already in a household cannot be added to another (409). There is no soft
  delete: removing a member deletes the row, so every row is an active
  membership.
- **One primary per household.** A partial unique index allows at most one
  `role = 'primary'` row per household; the creating customer is that member,
  created in the same transaction as the household, so a household is never
  without one. A second primary is refused (409).
- **Primary means `self`.** A primary member has `relationship = 'self'`, and
  `self` is reserved for the primary: any other primary/`self` combination is a
  422. `relationship = 'self'` with `role = 'dependent'` is never allowed.
- **Dependents.** `role = 'dependent'` is allowed for any non-`self`
  relationship, and `is_dependent` is always exactly `role = 'dependent'`.
- **The primary cannot be removed.** There is no ownership transfer in Phase
  32, so removing the primary is a 409 even when other members exist.
- **Only the primary adds or removes members**; any member may view. A
  non-member gets 403, an unknown household 404, an unknown customer 404.
- **The same customer cannot appear twice in a household**, and controlled
  vocabularies (relationship: self, spouse, parent, child, sibling, other;
  role: primary, member, dependent) are enforced by CHECK constraints and API
  validation (422).
- **Membership is not account access.** The authenticated customer stays the
  active user; no household route lets anyone view, edit or switch into another
  member's customer data, and no UI may present it as customer switching
  (Rule 21 is unchanged).
- **No household deletion API** and no household financial fields on
  `households`/`household_members` themselves. The household's own financial
  records arrived in Phase 33 as four separate tables — see Rule 32.

## Rule 32 — Household Financial Data (Phase 33)

A household stores its own income, expenses, assets and liabilities in four
independent tables (`household_incomes`, `household_expenses`,
`household_assets`, `household_liabilities`), each owned by a household through
`household_id` alone. This is **stored source data only**
(`docs/DECISIONS.md` ADR-032):

- **The Phase 33 CRUD layer calculates nothing.** No total, ratio, score or
  derived figure may be added to those four tables, their services, their
  routes or their schemas. Aggregation arrived in Phase 34 as a separate,
  read-only derived layer with its own specified methodology — see Rule 33 —
  and it is the only place household arithmetic may live.
- **It never enters the individual pipeline.** `POST /api/analysis`, the
  individual `financial_inputs` contract, risk classification, goal
  feasibility, emergency-fund evaluation, portfolio construction and compliance
  are unchanged and unaffected; a regression test compares each demo persona's
  analysis body before and after household financial data exists.
- **A record belongs to the household, not to a member.** None of the four
  tables has a `customer_id` column, and `household_id` comes from the URL path,
  never from a request body — it is absent from every update schema, and
  `extra="forbid"` turns an attempt to send it into a 422.
- **Any member reads; only the primary writes.** Same `X-Customer-Id` identity
  and the same status codes as Rule 31 (401 absent, 403 non-member or
  non-primary mutation, 404 unknown household). A record id that belongs to a
  different household is a **404**, never a 403 — the status code must not
  reveal that the record exists.
- **Controlled vocabularies**, enforced by CHECK constraints and mirrored as
  Pydantic `Literal` types that a test keeps in step: frequency (monthly,
  yearly, one_time); expense category (housing, food, utilities,
  transportation, education, healthcare, insurance, debt_payment, childcare,
  entertainment, other); asset type (cash, bank_account, fixed_deposit,
  investment, real_estate, vehicle, retirement, other); liability type
  (mortgage, personal_loan, education_loan, vehicle_loan, credit_card, other).
  Income `source` is free text by design — it is the household's own
  description, not a category.
- **NULL is not zero** (Rule 12 applies unchanged). A liability's
  `monthly_payment` is nullable and renders as "Not provided"; an expense's
  `is_essential` has no default because it is the household's judgement.
  Income and expense amounts must be `> 0`; an asset's `current_value` and a
  liability's `outstanding_amount` allow `>= 0`, because a repaid loan or an
  emptied account is a real zero.
- **Updates are partial merges** (`exclude_unset`, matching
  `FinancialInputsUpdate`), and deleting a household cascades to its financial
  records — there is still no household deletion route.

## Rule 33 — Household Financial Aggregation (Phase 34)

Phase 34 adds the first household-level interpretation of the Rule 32 source
records: a deterministic, **read-only** summary. All of its arithmetic lives in
one pure module, `core/household_finance.py`, and is exposed by exactly one
endpoint, `GET /api/households/{household_id}/financial-summary`
(`docs/DECISIONS.md` ADR-033):

- **Where the arithmetic may live.** In `core/household_finance.py` and nowhere
  else. Not in a route handler, not in a service (the service maps and
  serializes only), not in SQL, not in a response schema, and never in React.
  Every displayed number is computed exactly once.
- **Nothing is persisted.** A summary is recomputed from the source records on
  every request, so it cannot drift from them. No table, column or migration
  was added, and no total is written back to `households`.
- **Monthly normalization**: `monthly` contributes its amount, `yearly`
  contributes `amount / 12`, and `one_time` is **never** converted into a
  recurring figure — no amortization period may be invented and a one-time
  amount is never assumed to repeat. One-time income and expenses are reported
  separately and are excluded from cash flow.
- **Active records only** take part in monetary aggregates; an inactive record
  stays stored and still counts in `record_count`. Assets and liabilities have
  no `is_active` column and none may be invented.
- **Unknown is not zero, uniformly.** An aggregate is `null` unless at least one
  record contributes to it — including within a resource, so a household whose
  only income is one-time has *unknown* recurring income. A recorded `0` is a
  known fact and must stay visibly distinct from `null`, all the way to the
  screen. A `NULL` `monthly_payment` contributes nothing rather than 0. Each
  section carries `available` plus an `unavailable_reason` sentence.
- **Derived views need both inputs**: monthly cash flow (income − expenses) and
  net position (assets − outstanding liabilities) are `null` when either side is
  unknown, never computed against an assumed zero. Net position excludes income
  and expenses.
- **Emergency fund** reuses `core/goals.py`'s semantics — the same
  `EMERGENCY_FUND_TARGET_MONTHS` constant (6) and the same `current >= required`
  comparison — over the household's recurring essential expenses and liquid
  assets, with an added `unknown` state. A test asserts it agrees with
  `assess_emergency_fund`. It is **informational**: it produces no
  savings-first verdict, recommendation or compliance decision.
- **Decimal in, float out.** Aggregate in `Decimal`, never round inside the
  engine, and convert once at the service boundary, as Phase 33 already does.
- **What must NOT be added here**: a savings rate, a debt-to-income ratio, any
  score, rating, ranking or percentage-complete metric, a contribution capacity
  derived from income minus expenses (`GoalAssumptions.contribution_amount` is
  a user-supplied input, not a derived one), household goal feasibility, Monte
  Carlo, a household risk profile, a household portfolio, a household
  recommendation, or any currency conversion.
- **It never enters the individual pipeline.** No household figure reaches
  `POST /api/analysis`, `analysis_service.py`, the risk model, the goal engine,
  the optimizer, compliance, LangGraph, AutoGen or Gemini. Regression tests
  compare the analysis response before and after.

## Rule 34 — Household Financial Metadata (Phase 35)

Phase 35 added optional **factual metadata** to the Rule 32 tables and nothing
else (`docs/DECISIONS.md` ADR-034):

- `notes` (all four tables, <= 500 chars), `description` (assets and
  liabilities, <= 200 chars) and `interest_rate` (liabilities, `Numeric(6, 4)`,
  CHECK `>= 0`). All nullable with no default: an absent value is `null`, never
  `0` or `""`, and a recorded `0` interest rate is a known fact.
- **Metadata never enters a calculation.** The `core/household_finance.py`
  input records have no field for it; do not add one. No debt ratio, schedule,
  payoff date or interest figure may be derived from `interest_rate`.
- **The activity rule is still `is_active`.** Do not add `effective_date` /
  `end_date` semantics without a new ADR superseding ADR-033's activity rule and
  a stated target-date convention — the engine must never read the clock.
- **ADR-032 constraints are unchanged**: `amount > 0`; `monthly_payment`
  nullable. Do not relax them.
- **Rates are decimals end to end** (the Phase 28 convention): entered as
  `0.0425`, sent verbatim, displayed with `formatPercent`. No scaling in React.
- **Hostile text is data.** Notes and descriptions are stored and returned
  verbatim through parameterized SQL and rendered as escaped text by React; no
  custom sanitizer is layered on top.

## Rule 35 — Household Goals (Phase 36)

`household_goals` (ADR-035) stores a household's goals as **facts**:

- **Separate from individual goals, always.** Never read, write, convert or
  merge `financial_goals` from household code, and never let a household goal
  reach `POST /api/analysis`.
- **No goal math.** Do not compute an inflation-adjusted target, required
  contribution, contribution gap, probability or feasibility for a household
  goal — the `GoalAssumptions` inputs `core/goals.py` requires do not exist
  for a household. Adding them is a separate, explicit decision with its own
  ADR; `core/goals.py` itself must not change to accommodate households.
- **One emergency-fund figure.** An `emergency_fund` goal's `target_amount` is
  the household's stated target. The calculated requirement lives only in the
  Phase 34 summary; never compute or store a second one.
- **Null is not zero**: `current_savings` is nullable; a recorded `0` is a fact.
- **No ranking or priority**: list by `id`; no priority field, no "best goal".
- **Authorization is Phase 33's**: any member reads (list and get-one), only the
  primary creates/updates/deletes, a goal id of another household is a 404.
- **Required fields cannot be cleared with `null`** (422), and numbers are
  finite and within their column's storage limit (422) — never a database 500.

## Rule 36 — Sensitive-Data Protection Prototype (ADR-047)

`wealthpilot/security/`, `protected_records` and `audit_ledger_events` are an academic security prototype
(`docs/THREAT_MODEL.md`):

- **Describe it exactly.** The ledger is a *local hash-chained audit log*. Never call it a blockchain,
  decentralized, consensus-backed, immutable, tamper-proof or production-ready. The UI label is exactly
  "Academic prototype — not a real blockchain." Never describe a successful local verification as proof the database was
  not tampered with, and never claim encryption covers data it does not cover: only `protected_records` is encrypted;
  every other table is plaintext until a reviewed migration says otherwise.
- **Keys cross one boundary.** Key material is read only by `KeyProvider` implementations and used only by
  `EncryptionService`. It never reaches the database, source control, the frontend, a response, a log, the ledger, an
  exception message, an agent, an LLM prompt or a test file (tests generate random keys at run time). No default key, no
  plaintext fallback: a missing or invalid key fails closed. An environment variable is not a managed KMS; do not say so.
- **Encrypt, then persist; authorize, then decrypt.** Cryptography is AES-256-GCM with a fresh random nonce per operation, a
  versioned envelope and associated data binding the record id, owner and purpose. Do not add a second cipher or a
  hand-rolled scheme; add a new envelope version instead.
- **Every protected route authorizes the acting identity against the path profile** (401/403) and scopes every query by
  `customer_id`; an unknown, malformed and foreign record id are one identical 404. This is the prototype's asserted
  identity (ADR-020/031), not authentication; do not build a second auth system without an explicit instruction.
- **The ledger holds no sensitive content.** Event types come from a closed allow-list, a record is referenced only by its
  random UUID, and there is no field for an amount, name, e-mail, text, token or key. Success events are written in the same
  transaction as the data change (an audit failure aborts the operation). Hashing and verification share one canonical
  serialization; changing it is a new schema version.
- **User text is never echoed or logged.** New routes that accept it join `USER_TEXT_ROUTE_MARKERS` in `api/errors.py`.
- **No blockchain code, wallet, cryptocurrency, tokenization, smart contract or public-chain upload.** Vendor code, if it
  ever exists, sits behind `LedgerAnchor` and sees only a `LedgerCommitment` (sequence + head hash).
- **A new migration touches only new tables** and ships with the DB-free migration-history test; existing data is never
  encrypted or rewritten implicitly.
