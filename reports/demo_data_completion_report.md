# Demo Data Phase — Completion Report

## 1. Objective

Build a genuinely complete, deterministic, synthetic demonstration
dataset that lets WealthPilot AI's real, unmodified end-to-end pipeline
be demonstrated: synthetic customer → profile → questionnaire → goals →
persisted data → real `POST /api/analysis` → LangGraph → risk → financial
health → goals → market → portfolio → compliance → recommendation →
Gemini explanation where reachable → Agent Activity/SSE — with every
result produced by the real, approved system, never hard-coded.

## 2. Existing Architecture Inspected

Read in full or targeted depth this phase: `backend/wealthpilot/agents/
nodes.py` (every node's exact input requirements), `backend/wealthpilot/
api/services/analysis_service.py` (the live orchestration —
`PipelineRun.events()`, `GraphDependencies` construction), `backend/
wealthpilot/agents/recommendation.py` (`build_recommendation_input`'s
portfolio-candidate gating), `backend/wealthpilot/core/compliance.py`
(every rule-check function's exact fail-closed behavior), `config/
compliance_rules.yaml`, `backend/wealthpilot/data/preprocessing.py`
(`load_far_trans_tables`, confirming raw-CSV-only reads),
`backend/wealthpilot/db/models.py` (full schema, confirming `Transaction`
is imported nowhere outside `data/ingestion.py`), `backend/wealthpilot/
api/schemas.py` (`ProfileCreateRequest`/`GoalCreate` — no
`risk_inputs` exposure), and `reports/phase19_final_evaluation_report.md`,
`phase21_create_user_report.md`, `phase22_onboarding_report.md`,
`phase23_persistence_report.md`, `phase24_demo_account_report.md`,
`phase25_final_ux_report.md`.

## 3. Dependency Map

```
Customer (customers row: name/age/income/employment_status/
          customer_type/investment_capacity/risk_inputs/data_source)
  │
  ├─ customer_analyzer_node: reads Customer + FinancialGoal rows only.
  │
  ├─ risk_analyst_node: needs feature_row =
  │     engineer_features_for_customer(external_customer_id)
  │   external_customer_id = Customer.risk_inputs["external_customer_id"]
  │   → reads ONLY raw CSVs (datasets/raw/FAR-Trans/*.csv), NEVER the
  │     `transactions` database table (confirmed: `Transaction`, the
  │     SQLAlchemy model, is imported nowhere in wealthpilot/ except the
  │     one-time data/ingestion.py loader).
  │   → GATE: confidence < 0.50 (or no feature row) → information_request
  │     → terminal `pending_information`.
  │
  ├─ financial_health_node (behaviour-drift/anomaly): ALSO needs
  │   external_customer_id, ALSO reads only the raw CSV transactions
  │   table, needs ≥4 months of monthly trading-panel data.
  │   expense_persona/savings_rate: ALWAYS None for every customer,
  │   permanently — FAR-Trans has no income/expense fields, and the
  │   Kaggle expense-clustering population is a separate, unlinked
  │   dataset. No data of any kind changes this.
  │
  ├─ goal_analyst_node: needs `assumptions` (GoalAssumptions),
  │   `historical_returns`, `monthly_essential_expenses`,
  │   `current_liquid_assets`. NONE of these are EVER supplied by
  │   `analysis_service.py::PipelineRun.events()` — its `GraphDependencies`
  │   only sets `session`/`portfolio_strategy`. Every goal ALWAYS shows
  │   `unavailable_reason`, and `emergency_fund.sufficient` is ALWAYS
  │   `None`, for every customer, unconditionally.
  │
  ├─ market_analyst_node: reads models/metrics.json (pre-computed,
  │   customer-independent). Always available.
  │
  ├─ route_after_market (agents/graph.py): → portfolio_manager ONLY if
  │   `emergency_fund.sufficient is True`. Since it is always `None`
  │   (never `True`), this branch is NEVER taken — for any customer.
  │
  ├─ portfolio_manager_node: live-callable, reads real `market_data`
  │   (unmodified Phase 6 data) — but structurally unreachable via the
  │   live API today (see above).
  │
  ├─ savings_first_node: the path ALWAYS taken instead, for every
  │   customer that clears the risk-confidence gate.
  │
  ├─ compliance_analyst_node → core/compliance.py's
  │   `_check_emergency_fund_savings_first` (REJECT severity): explicitly
  │   `if p.emergency_fund_sufficient is None: return triggered=True`.
  │   Since it is ALWAYS None live, this rule ALWAYS triggers REJECT —
  │   for every customer, unconditionally, regardless of risk category,
  │   goals, questionnaire, or portfolio strategy.
  │   → route_after_compliance: REJECT → terminal `rejected`.
  │
  └─ recommendation_engine_node / explanation_node: called ONLY when
      overall_status == "approved" — which the above makes IMPOSSIBLE for
      any customer through the current, unmodified live orchestration.
```

**This is the single, precise, verified "blocking dependency" governing
this entire phase** — see §4.

## 4. Demo Customer Population

Three new synthetic identities plus Phase 24's preserved canonical
customer — full detail (profile, questionnaire, goals, real results) in
`reports/demo_dataset_catalog.md`. Summary:

| Persona | Customer ID | Real risk result | Actual state |
|---|---|---|---|
| WealthPilot Demo Customer (Phase 24) | 29096 | unavailable (no FAR-Trans linkage) | `pending_information` |
| WealthPilot Demo — Complete | 29098 | Aggressive, 91.3% confidence | `rejected` |
| WealthPilot Demo — Savings | 29099 | Balanced, 76.4% confidence | `rejected` |
| WealthPilot Demo — Compliance | 29100 | Conservative, 77.7% confidence | `rejected` |

**"DEMO COMPLETE" (approved) and "DEMO SAVINGS" (approved with
`recommendation.status == "savings_first"`) are NOT achievable without
modifying approved logic** — verified both by static code analysis (§3)
and empirically: a real, independent test call against a known real
FAR-Trans customer (confidence 0.51) returned `REJECT` with all 5 rules
`triggered=true` (4 for "portfolio weights were not provided," 1 for
"emergency-fund status was not provided"), confirming the code-level
finding before any demo persona was even created. Per this phase's own
explicit instruction, this was reported rather than forced, and no file
under `api/services/analysis_service.py`, `agents/graph.py`, `agents/
recommendation.py`, or `core/compliance.py` was modified to work around
it.

## 5. Data-Generation Methodology

Every persona was created through the REAL, unmodified public API,
exactly mirroring what a real user's onboarding does:

1. `POST /api/profiles` (Phase 21) — creates the `Customer` row.
2. One direct, minimal database write: `UPDATE customers SET risk_inputs
   = '{"external_customer_id": "..."}' WHERE id = <just-created id>` —
   the ONE field no API endpoint exposes (it is an internal
   data-provenance field, set only by `data/ingestion.py` for FAR-Trans's
   real population; no Pydantic schema anywhere includes it). This is the
   single genuinely-necessary direct database write this phase performs.
3. `GET /api/questionnaire` → `POST /api/profiles/{id}/questionnaire`
   (Phase 23) — 25 real answers per persona, each a fixed, position-based
   selection (first / middle / last option of each question — never a
   function of the option's own text, never converted into or read as a
   score).
4. `POST /api/profiles/{id}/goals` (Phase 23) — 2 real goals per persona.
5. `POST /api/analysis` (Phase 15) — the real pipeline runs; its actual
   result is what is recorded (§4, and in full in the catalog).

**Why `external_customer_id` linkage, and not synthetic `transactions`
database rows**: confirmed by inspection (§3) that the live risk/
behaviour pipeline reads exclusively from the immutable raw FAR-Trans
CSVs, never the application's own `transactions` table — so synthetic DB
transaction rows would be completely inert for this purpose, decorative
data with zero effect on any model result. The ONLY mechanism the
existing, approved architecture provides for a NEW customer identity to
receive a genuine, model-computed risk/behaviour result is exactly the
one the system already uses for its entire real population. This is
disclosed prominently, not hidden: each persona's *identity* (name,
profile, questionnaire, goals) is 100% synthetic and clearly labeled;
its risk-relevant data source is one real, already-present, anonymized
FAR-Trans customer (FAR-Trans transactional data carries no personal
information — Phase 2's own audit already established this), never a
fabricated history and never copied personal data.

## 6. Profile Data

All three new personas use only real `ProfileCreateRequest` fields (no
invented field): `name`, `age`, `income`, `employment_status`,
`customer_type` (using real, evidenced FAR-Trans values — "Premium",
"Mass", "Professional"), `investment_capacity` (using real values —
"CAP_80K_300K", "CAP_30K_80K"). No risk category, portfolio, or emergency
-fund field was ever set on a profile (none exist on this schema).

## 7. Questionnaire Data

25 real questions/options per persona, fetched live from `GET
/api/questionnaire`, never hard-coded. Each persona uses a different,
fixed, position-based selection rule (see §5) so the three questionnaires
are intentionally different from one another, exactly as this phase's own
instruction requested, while remaining a pure "which real option" choice
— never a score, never mapped to a risk category anywhere in this
phase's code.

## 8. Goal Data

2 real `GoalCreate`-schema goals per persona (goal_type, target_amount,
target_date, current_savings, priority — no other field exists on this
schema, none was invented). No feasibility, Monte Carlo probability, or
required contribution was computed or stored anywhere — the real API
response confirms all three fields are `null` with `unavailable_reason`
set, exactly matching the pre-existing, already-disclosed gap in
`goal_analyst_node`'s live wiring (§3).

## 9. Transaction Data

**No new database `transactions` rows were created.** See §5's
explanation: the live pipeline never reads that table, so populating it
would be purely decorative and, per this phase's own "credible if
inspected" standard, arguably confusing (an evaluator could reasonably
ask whose transaction history is actually being used). Each persona's
real, risk-relevant transaction history is the EXISTING, already-present,
real FAR-Trans data belonging to its linked `external_customer_id` — not
generated by this phase, immutable, and untouched by it.

## 10. Risk Inputs

`risk_inputs.external_customer_id` for each persona was chosen by
`backend/scripts/find_demo_risk_candidates.py` (preserved for
reproducibility) — a read-only tool that runs the EXACT SAME, unmodified
`engineer_features()` (Phase 3) and the EXACT SAME trained artifacts
(`models/risk/{preprocessor,rf}_v1.pkl`, Phase 4) the live pipeline uses,
in the batch shape `engineer_features()` was itself designed for, scanning
the real FAR-Trans population for customers with risk-model confidence
≥ 0.50 and ≥ 4 months of trading history (so behaviour-drift detection
also produces a real, non-"unavailable" result). Candidates were then
picked across three different predicted risk categories for genuine,
non-fabricated variety.

## 11. Behaviour Inputs

Not separately constructed — behaviour-drift/anomaly detection reads the
SAME real, linked FAR-Trans transaction history risk classification uses
(§3/§10), so choosing candidates with ≥ 4 months of history (§10) was
sufficient to make this stage also produce a real result for all three
personas (confirmed: `behaviour_drift_flag: false`,
`isolation_forest_anomaly: false` for all three — an honest finding, not
a designed one).

## 12. Financial-Health Inputs

Not applicable / permanently unavailable for every customer in this
system, by design (§3) — FAR-Trans has no income/expense/liquid-asset
fields, and the Kaggle expense-clustering model operates on a separate,
unlinked population. No demo persona attempts to work around this; each
one's `expense_persona` correctly shows `null` with the same
already-approved `unavailable_reason` text every other customer shows.

## 13. Market-Data Usage

Read-only, via `market_analyst_node` → `models/metrics.json` (Phase 6's
own pre-computed regime results) — no new market data, no change to
forecasting models, GARCH/LSTM/GRU/ARIMA, or regime-classification logic.
All three personas show the same real 5-instrument regime snapshot (this
node's output does not vary by customer).

## 14. Idempotency

`scripts/seed_demo_data.py setup` was run three times consecutively
against the same environment. First run: created 3 customers + 75
questionnaire answers (25×3) + 6 goals (2×3) + 3 analysis runs. Second and
third runs: each reused the existing customer (matched by exact name),
skipped questionnaire/goal creation (both already non-empty), and
returned the SAME cached `analysis_id` for each persona (132/133/134
unchanged across all 3 runs — the existing profile-hash-based analysis
cache correctly recognized no input had changed). A direct database count
after the third run confirmed exactly 1 row per persona name, with zero
duplicates.

## 15. Reset Safety

`scripts/seed_demo_data.py reset` matches ONLY the exact names literally
present in its own `DEMO_PERSONAS` list — never a prefix or substring
match — so it can never reach a differently-named row by accident, and
"WealthPilot Demo Customer" (Phase 24's own, differently-named canonical
customer, never in that list) can never be matched or deleted by it.
Child rows (`questionnaire_answers`, `financial_goals`, `agent_logs`,
`analysis_runs`, `risk_assessments`, `recommendations`) are deleted before
the `customers` row itself. This safety property is covered by an
automated test (`test_reset_style_deletion_matches_only_exact_names`,
`test_reset_style_deletion_never_targets_phase24_canonical_name`) rather
than asserted only in prose.

## 16. Data-Quality Results

Directly queried against the live database after seeding (all passed):
zero duplicate `(customer_id, question_number)` questionnaire-answer
pairs; zero orphaned `questionnaire_answers`/`financial_goals` rows; zero
invalid `option_key` values (all match `^[a-e]$`); zero goals with a
non-positive `target_amount` or a `target_date` on/before today; zero
customers with a future `created_at` or a null required field; exactly
one row per persona name (§14); `data_source = "user-entered"` for all
three (the real API's own, unmodified default).

## 17. Leakage Audit

No new leakage risk was introduced: no new transaction was created (§9),
and the feature-engineering function used to select/verify candidates
(§10) is the SAME, already Phase-3-leakage-audited `engineer_features()`
— unmodified, called in exactly the shape its own docstring describes.
Each linked `external_customer_id`'s risk label and features come from
the same point-in-time-correct pipeline every real FAR-Trans customer
already uses; nothing about this phase changes how or when that
computation happens.

## 18. Model Integrity Audit

`find models -type f -newer <baseline>` → empty, confirmed after seeding.
No model artifact (`models/risk/`, `models/behaviour/`, `models/market/`,
`models/portfolio/`) was modified, retrained, or re-saved. No training
script was run.

## 19. Database Integrity Audit

Alembic revision unchanged (`8fed3799c0c5`, the Phase 23 head — confirmed
via a direct `SELECT version_num FROM alembic_version` before and after
seeding). No migration was created or run. No table or column was added.
Real customer records (ids other than the 4 listed in §4) were not
queried for writes and were not touched by any operation this phase
performed — every write this phase made was scoped to a `WHERE id = ...`
targeting only a just-created row, or `WHERE name = ANY(<exact demo
names>)`.

## 20. Real Analysis Execution

`POST /api/analysis` was executed for real against all three new personas
(§4/§14) — full JSON results captured and cross-checked into the catalog.
No response field was ever modified after receipt.

## 21. SSE Execution

`GET /api/analysis/stream` was captured live for "WealthPilot Demo —
Complete" (profile 29098) — full 10-event trace reproduced verbatim in
`reports/demo_dataset_catalog.md` §2. Every event carries only
`node`/`status`/`duration_ms`/`summary`/`model_version`; no prompt, no
chain-of-thought, no agent transcript appears anywhere in the capture.

## 22. Risk Results

Aggressive 91.3% / Balanced 76.4% / Conservative 77.7% confidence across
the three new personas — all real, `models/risk/rf_v1.pkl` outputs,
none fabricated (full class-probability tables in the catalog).

## 23. Financial-Health Results

All three: `behaviour_drift_flag: false`, `isolation_forest_anomaly:
false` — real `models/behaviour/iforest_v1.pkl` outputs, an honest
finding (no drift/anomaly detected for any of the three chosen real
candidates), not a designed result.

## 24. Goal Results

All goals (6 total across the 3 new personas) show `unavailable_reason:
"no GoalAssumptions (contribution/return/inflation) supplied"` — the
correct, honest, unmodified behavior of `goal_analyst_node` given the
live API's own permanent gap (§3) — never fabricated.

## 25. Portfolio Results

`null` for all three — the MVO/HRP/1-N optimizer was never reached (§3),
and this phase made no attempt to force it.

## 26. Compliance Results

`REJECT` for all three, each with the identical, real 5-rule breakdown
(4 rules citing missing portfolio weights, 1 citing missing
emergency-fund status) — captured verbatim in the catalog for all three,
and independently confirmed against a fourth, non-demo real customer
before any persona was created (§4).

## 27. Recommendation Results

`null` for all three (never computed — gated behind `overall_status ==
"approved"`, which never occurs). No recommendation row was written to
the `recommendations` table for any of these customers (confirmed by the
same logic that gates `persist_recommendation`'s own call site).

## 28. Gemini Result

Not reached for any customer this phase (§27) — Gemini's explanation node
is gated behind the same unreachable "approved" status. No fake
explanation was generated or stored; this is disclosed plainly rather
than worked around.

## 29. Frontend Verification

**Zero frontend files were modified this phase** (confirmed via an mtime
check against the entire `frontend/src/` tree). Phase 24's existing "Use
Demo Account" flow and `lib/demo-customer.ts` were re-verified working,
unaffected: the canonical customer (29096) was re-confirmed present
exactly once and still produces `pending_information`. No new demo UI, no
customer-switching interface, and no hard-coded demo result was added
anywhere in the frontend. **Not verified — reason: no headless-browser
tool is available in this environment** — no click-through UI test was
performed or is claimed; verification was via real API calls, a real SSE
capture, direct database queries, and source-level review of the
unmodified frontend.

## 30. Backend Test Result

Full `pytest` suite: **726 passed, 3 skipped, 0 failed** (1017.29s) — the
Phase 25 baseline of 713 plus 13 new tests added this phase
(`tests/backend/api/test_seed_demo_data.py`, covering the seed script's
pure logic, an integration-style create/link/persist flow via the
existing `client`/`db_session` fixtures, idempotency-guard behavior, and
reset-safety exact-name-matching). An intermediate full run produced 50
errors clustered in `tests/backend/db/test_models.py`/`tests/backend/
data/test_ingestion.py`; all 17 of those tests were confirmed to pass
cleanly both individually and as a batch when re-run outside the full
~700-test run, and a subsequent complete re-run of the entire suite came
back fully clean — consistent with a transient, full-suite-duration
resource/connection artifact in this environment (the same class of
issue already documented once in `reports/phase25_final_ux_report.md`
§32), not a logic defect in any test or in this phase's own code (zero
backend application files were modified — §19).

## 31. TypeScript Result

`npx tsc -b` — **0 errors** (re-run after confirming zero frontend files
changed).

## 32. Build Result

`npx vite build` — succeeds, byte-identical output to the Phase 25
baseline (958.90 kB, gzip 294.82 kB, same chunk hash) — direct
confirmation of zero frontend impact.

## 33. Lint Result

`npx oxlint` — **0 errors**, 8 warnings — identical set to Phase 25, none
new.

## 34. Security Audit

A grep of every new file (`backend/scripts/{find_demo_risk_candidates,
seed_demo_data}.py`, `tests/backend/api/test_seed_demo_data.py`,
`scripts/seed_demo_data.sh`) for API-key patterns, credentialed database
URLs, and similar found zero matches. No demo persona contains a real
email address, phone number, government ID, or financial account
identifier — every profile field is a plausible but entirely fabricated
number (age, income) or a real-but-non-personal FAR-Trans category
value. The Phase 20 demo credentials are unchanged.

## 35. Viva Runbook

`docs/demo_runbook.md` — an exact, verified sequence (Login → Demo
Account → Dashboard → switch to each new persona via the existing header
profile control → Risk Assessment → Start Analysis/Agent Activity →
Financial Health → Goals → Portfolio → Recommendation → Why This
Recommendation → Scenario Simulator → Create User end-to-end), plus talking
points and an explicit "what not to say" section (never claim "approved,"
never claim the optimizer ran, never claim browser verification that
wasn't performed).

## 36. Actual Limitations

- **[SUPERSEDED by Phase 28 — `reports/phase28_financial_input_savings_first_report.md`]**
  No customer — demo or real — can reach an "approved" recommendation
  through the current, unmodified live API** (§3/§4). This is the central
  finding of this phase, verified both by code inspection (two
  independent, redundant gates: `agents/graph.py::route_after_market` and
  `agents/recommendation.py::build_recommendation_input`, plus
  `core/compliance.py`'s fail-closed `emergency_fund_savings_first` rule)
  and empirically (a real customer test call, plus all three new
  personas). Fixing this would require modifying `analysis_service.py`
  to supply `monthly_essential_expenses`/`current_liquid_assets` —
  explicitly out of this phase's scope and not attempted. **This
  limitation was real and accurately described at the time this report
  was written. Phase 28 later added a real, explicit financial-input data
  contract (`GET`/`PUT /api/profiles/{id}/financial-inputs`) and a
  companion compliance-rule fix, and two of this phase's own demo
  personas ("Complete", "Savings") now genuinely reach `approved` — see
  the Phase 28 report and the updated `reports/demo_dataset_catalog.md`
  for current, live-verified results. This section is left intact rather
  than rewritten, as a record of what was true and why, at this phase's
  own point in the project's history.**
- **Demo personas' risk-relevant data source is a real, existing,
  anonymized FAR-Trans customer, not a self-contained synthetic
  transaction history** — a necessary consequence of the risk pipeline
  reading exclusively from immutable raw data (§5/§9), disclosed
  prominently rather than hidden.
- **The database `transactions` table remains unpopulated for all three
  new personas** — confirmed inert for this system's live pipeline
  (§9), so this is a deliberate, documented choice, not an oversight.
- Every already-disclosed, pre-existing limitation from Phase 19/21-25
  (no browser-based visual verification in this environment, no
  frontend test runner, the single-chunk JS bundle) remains unchanged and
  is not repeated in full here.
- The one transient 50-test full-suite flake (§30) is disclosed, not
  hidden, and was resolved by a clean, complete re-run.

## 37. Exact Statement of What Was NOT Modified

Not modified, at any point in this phase (all confirmed via mtime checks
against a pre-phase baseline): Phase 3 feature engineering, Phase 4 risk
model, Phase 5 expense/behaviour models, Phase 6 market models, Phase 7
goal mathematics, Phase 8 portfolio optimization, Phase 9 compliance
rules/logic, Phase 10 agent nodes, Phase 11 LangGraph, Phase 12 AutoGen,
Phase 13 Gemini, Phase 14 recommendation engine, Phase 15 API
architecture/routes, Phase 20 authentication, Phase 21 Create User flow,
Phase 22 onboarding pages, Phase 23 persistence endpoints, Phase 24 demo
-account mechanism/frontend code, Phase 25 UX. No database migration, no
new table, no new column. No raw FAR-Trans/Kaggle data, no `market_data`
row, no serialized model artifact, no training script, no training run.
The ONLY changes this phase made: three new files
(`backend/scripts/find_demo_risk_candidates.py`,
`backend/scripts/seed_demo_data.py`, `scripts/seed_demo_data.sh`), one new
test file (`tests/backend/api/test_seed_demo_data.py`), three new
documentation files (this report, `reports/demo_dataset_catalog.md`,
`docs/demo_runbook.md`), and application data: 3 new `customers` rows (and
their `questionnaire_answers`/`financial_goals`/`analysis_runs`/
`agent_logs` children) plus one already-existing `risk_inputs` field
populated by direct SQL on each of those 3 new rows only.
