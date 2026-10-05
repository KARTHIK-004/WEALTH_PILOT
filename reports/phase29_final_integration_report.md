# Phase 29 — Final Integration & Validation Report

> **Note added in Phase 30 (the body of this report is otherwise unchanged).**
> Two statements below are superseded. (1) §8 says `frontend/src/types/api.ts`
> was byte-identical to a fresh generation; after that check, the `lookup`
> endpoint's docstring was edited, so the file was stale by one comment until
> Phase 30 regenerated it (no type changed). (2) §17's limitation that the
> Goals page shows a negative contribution gap with no explanatory text is
> resolved: Phase 30 shows the unchanged value plus "Contribution exceeds the
> calculated requirement." See `reports/phase30_analytics_visualization_report.md`.

## 1. Status

**COMPLETE.** Every §21 completion criterion is satisfied (see §19). The
final isolated backend regression run on the final code state passed:
763 passed, 3 skipped, 0 failed (§13).

## 2. Objective

Prove that the WealthPilot AI system works coherently as one integrated
application after Phase 28 — login → customer association → profile →
financial inputs → questionnaire → goals → analysis (LangGraph: risk,
financial health, emergency fund, goals, market, portfolio/savings-first,
compliance, recommendation, explanation) → SSE activity → frontend
rendering — using real persisted data and the existing APIs. Not to add
financial intelligence, retrain anything, or change approved rules.

## 3. Baseline

Phase 28 was treated as the baseline and re-verified rather than trusted.

| Baseline item | Evidence gathered in Phase 29 |
|---|---|
| A. `financial_inputs` table, all fields independently nullable | Dev and test databases: columns `monthly_essential_expenses`, `current_liquid_assets`, `contribution_amount`, `annual_return_rate`, `annual_inflation_rate`, `contribution_periods_per_year` all `NULL`-able; `customer_id` UNIQUE + FK to `customers`. Live GET for 29100/29096 returns every field `null` (never 0). |
| B. `GET`/`PUT /api/profiles/{id}/financial-inputs` | Present in the live OpenAPI schema; live GET verified for all four personas; PUT merge/clear/validation covered by the 9 API tests in `test_profiles.py`; RFC 7807 verified live (404 / 422). |
| C. Emergency fund via `_build_graph_dependencies` → unmodified `core/goals.py` | 29098: required 18,000 / current 40,000 / shortfall 0 / sufficient `true`. 29099: required 15,000 / current 4,000 / shortfall 11,000 / sufficient `false`. 29100: `sufficient: null`, reason "not supplied". |
| D. `GoalAssumptions` only when all required fields exist | 29100 (no inputs): every goal reports "no GoalAssumptions … supplied"; test `test_no_goal_assumptions_means_no_returns_series_but_emergency_inputs_still_flow`. Recorded as ADR-028. |
| E. Savings-first for unknown/insufficient EF | 29099 (known insufficient) and 29100 (unknown) both route to `savings_first_node`; neither runs the optimizer. |
| F. Portfolio only for sufficient EF | 29098 → real MVO (QQQ 55% / AGG ~0% / GLD 45%); 29099/29100 → `strategy: savings_first`, `weights: null`. |
| G. Compliance exemption only for `weights is None` AND savings-first | 29099: PASS, 0 of 5 rules triggered. 29100: REJECT via the one genuinely applicable rule. Boundary (savings-first proposal that *does* supply invalid weights is still rejected): `test_savings_first_with_inconsistent_weights_is_still_fully_validated`. |
| H. Recommendation statuses | Live: `approved` (29098), `savings_first` (29099). See §18 on `blocked_rejected`/`failed`. |
| I. Persona outcomes | 29098 approved · 29099 savings_first · 29100 rejected · 29096 pending_information — all obtained live, none forced. |

## 4. End-to-End Data Flow

Trace of `POST /api/analysis`, from the source (not from documentation). Node
runtime order inside the graph is: `customer_analyzer → risk_analyst →
[information_request → END] → financial_health_analyst → [reprofile] →
goal_analyst → market_analyst → portfolio_manager | savings_first →
compliance_analyst → approved | rejected` (any unexpected node exception →
`failed`).

| # | Step | Source (file::function) | Input → output | Failure behaviour | Persisted? | Numeric origin |
|---|---|---|---|---|---|---|
| 1 | Request schema | `api/routers/analysis.py::run_analysis`, `api/schemas.py::AnalysisRequest` | `{profile_id, portfolio_strategy?}` → validated model | 422 RFC 7807 | No | None |
| 2 | Customer lookup | `api/services/analysis_service.py::get_or_run_analysis` | `profile_id` → `Customer` + goals | `CustomerNotFoundError` → 404 RFC 7807 | Read only | None |
| 3 | Financial-input lookup + cache key | `get_or_run_analysis`, `compute_profile_hash` | `FinancialInputs` row (or none) + `ANALYSIS_PIPELINE_VERSION` → SHA-256 profile hash; a completed `AnalysisRun` with the same hash is returned without recomputation | none-row = all-unknown (never 0) | Read only | None |
| 4 | Graph dependency construction | `analysis_service.py::_build_graph_dependencies`, `_build_goal_assumptions`, `_historical_returns_for_goal_analysis`, `_compound_to_period_returns` | inputs → `GraphDependencies(goal_assumptions?, historical_returns?, monthly_essential_expenses?, current_liquid_assets?, strategy)`; returns series only built when assumptions exist, compounded to the goal's period frequency | empty `market_data` → returns `None` (feasibility stays unavailable) | No | Deterministic (`market_data`, customer inputs) |
| 5 | LangGraph execution | `analysis_service.py::PipelineRun.events` → `agents/graph.py::build_analysis_graph` | `AgentState` streamed node by node via `apply_delta` | `_safe_call` → structured `processing_failure` → `failed` | In memory only | Deterministic |
| 6 | Emergency fund | `agents/nodes.py::goal_analyst_node` → `core/goals.py::assess_emergency_fund` | expenses × 6 vs liquid assets → required/current/shortfall/sufficient | either input missing → `sufficient: null` + reason | No | Deterministic (`core/goals.py`) |
| 7 | Goal analysis | `goal_analyst_node` → `analyze_goal_funding`, `run_goal_monte_carlo`, `classify_feasibility` | goals + `GoalAssumptions` + period returns → required contribution, gap, MC probability (10,000 sims, seed 42), Feasible ≥0.80 / At Risk 0.50–0.79 / Not Feasible <0.50 | no assumptions → per-goal `unavailable_reason` | No | Deterministic |
| 8 | Risk | `graph._risk_analyst` → `nodes.risk_analyst_node` | FAR-Trans features (raw CSVs via `external_customer_id`) → `models/risk/rf_v1.pkl` class + probabilities; confidence < 0.50/None → `information_request` → `pending_information` | no linkage → risk unavailable | No (no `risk_assessments` row is written: Phase 4 defines no `risk_score`; table has 0 rows) | Trained model |
| 9 | Financial health | `nodes.financial_health_node` | monthly panel → z-score drift + Isolation Forest (`models/behaviour`) | too little history → unavailable; `expense_persona`/`savings_rate` always `null` (structural) | No | Trained model / deterministic |
| 10 | Market | `nodes.market_analyst_node` | reads `models/metrics.json["market"]` → regime per instrument | file/section missing → `unavailable_reason` | No | Pre-computed offline (Phase 6) |
| 11 | Portfolio / savings-first | `graph.route_after_market` → `nodes.portfolio_manager_node` (`core/optimizer.py`) or `nodes.savings_first_node` | EF sufficient → MVO/HRP/1-N weights; else savings-first result with `weights: null` | empty `market_data` → unavailable result + `missing_data` error | No | Deterministic |
| 12 | Compliance | `nodes.compliance_analyst_node` → `core/compliance.py::evaluate_compliance` (5 rules, `config/compliance_rules.yaml`) | proposal → PASS/WARN/REJECT + per-rule results; REJECT → terminal `rejected` | missing required data → rule triggered (fail-closed) | No | Deterministic |
| 13 | Recommendation | `analysis_service.py` (only if `approved`) → `agents/recommendation.py::recommendation_engine_node` → `core/recommendation.py` | Compliance > Savings-first > Risk > Goal > Market → status + strategy + rationale | — | **Yes** — one `recommendations` row via `persist_recommendation` | Deterministic |
| 14 | Explanation | `agents/explanation.py::explanation_node` (only if `approved`) | computed dict → Gemini prose, validated against source; otherwise templated fallback (`validation_passed: false`) | any Gemini/parse/validation failure → fallback; never a fabricated number | No | **Prose only — no numbers originate from Gemini** |
| 15 | Persistence | `_persist_run_artifacts`, `_persist_risk_assessment`, `get_or_run_analysis` | `agent_logs` rows (one per event), `AnalysisRun.result` JSON + `completed`; committed by `api/dependencies.py::get_session` | exception → rollback | **Yes** | — |
| 16 | API response | `build_analysis_result` → `AnalysisResult.model_validate` | stored/computed state → public schema (pure serialization) | validation error → RFC 7807 | — | Copied verbatim |

`GET /api/analysis/stream` (`api/sse.py`) drains the same
`PipelineRun.events()` generator; it does not use the cache and does not
write `analysis_runs`/`agent_logs` (only step 13's recommendation row, for
an approved run).

## 5. Demo Persona Validation

All results below come from real `POST /api/analysis` responses (in-process
`TestClient(app)` against the real database — no server was started) and
real `GET /api/analysis/stream` captures. After the two fixes in §18 every
persona recomputed, so the current ids are 165–168 (superseding 150–153).

### 29098 — Complete (analysis 165) — `approved`
Risk **Aggressive**, confidence 0.9126 (model `v1`, source `models/risk`).
Financial health: drift `false`, anomaly `false`, `expense_persona` `null`
(structural). Emergency fund: required 18,000, current 40,000, shortfall 0,
**sufficient**. Goals: Retirement — required 887.40, gap −112.60,
**94.11% → Feasible**; House Purchase — required 1,146.88, gap +146.88,
**50.28% → At Risk**. Market (`v1`, `yfinance==0.2.66`): ^IXIC Range-bound,
^NDX Volatile, QQQ Volatile, AGG Range-bound, GLD Volatile. Portfolio: **MVO**,
QQQ 0.55 / AGG ≈0 / GLD 0.45, expected return 17.43%, volatility 16.41%,
Sharpe 1.062. Compliance: **PASS, 0 of 5 rules triggered**. Recommendation:
`approved`, strategy `mvo`, same weights, rationale cites risk-conditioned
MVO, goal preference "At Risk → MVO (matches)", and market preference
overridden by risk suitability; provenance `phase14 v1 / risk v1 / market v1 /
portfolio v1 / compliance rules v1`. Explanation: `completed`,
`validation_passed: false` — the templated fallback (see §17).

### 29099 — Savings (analysis 166) — `approved` with `recommendation.status = savings_first`
Risk **Balanced**, confidence 0.7636. Emergency fund: required 15,000,
current 4,000, **shortfall 11,000**, **insufficient**. Goals: Emergency Fund
(due 2028) required 794.64 vs 400 supplied, **0.0% → Not Feasible**;
Retirement required 543.03, **88.56% → Feasible**. Portfolio:
`strategy: savings_first`, `weights: null`, reason "normal portfolio
optimization deferred: emergency-fund shortfall of 11000.00". Compliance:
**PASS, 0 rules triggered**. Recommendation: `savings_first`,
`selected_strategy: null`, no weights (rationale: "savings_first_required …
normal investment recommendation deferred"). No allocation is presented
anywhere. Explanation: `completed`, `validation_passed: false` (fallback).

### 29100 — Compliance (analysis 167) — `rejected`
Risk **Conservative**, confidence 0.7772. No financial inputs by design;
emergency fund `sufficient: null` ("not supplied … never fabricated"); goals
unavailable ("no GoalAssumptions … supplied"). Portfolio: `savings_first`
with the honest "sufficiency could not be confirmed" reason. Compliance:
**REJECT — exactly one rule triggered, `emergency_fund_savings_first`**
("required data unavailable: emergency-fund status was not provided"); the
four weight rules correctly do not trigger. Recommendation `null`,
explanation `null` — nothing downstream ran, and no financial input was
fabricated.

### 29096 — Information Required (analysis 168) — `pending_information`
No FAR-Trans linkage: risk `null` ("engineered feature row was not
provided …"), financial health/EF/market/portfolio/compliance/
recommendation/explanation all `null`, goals `[]` (customer analyzer output
only). The graph halts at `information_request`. Nothing fabricated.

## 6. Frontend Journey Validation

**No browser or headless-browser tool exists in this environment, so no
journey was executed in a browser.** Each journey below was verified by
reading the actual page/component source, `tsc`, `oxlint`, `vite build`,
and — for everything the UI displays — the live API responses in §5/§7.
This is source-level verification and is labeled as such.

| Journey | Verdict | Basis |
|---|---|---|
| 1 Login | ✅ | `login-form.tsx::completeLogin` resolves the customer for both Sign In and Demo, then navigates; no numeric-id entry, selector, or dialog anywhere (`customer-selector.tsx` deleted; `setProfileId` is called only by login, account creation, and sign-out→`null`); `AccountIdentity` shows "Demo Account" or the real name, never an id; sign-out clears auth and `profileId`. No hard-coded demo id exists in application code or tests (grep). |
| 2 Profile | ✅ | `FinancialInputsCard` seeds fields from `GET` (`null` → empty input, never `"0"`), submits only fields the user typed, validates shape only, computes nothing. |
| 3 Questionnaire | ✅ | `/onboarding/questionnaire` preselects persisted answers, forwards only `{question_number, option_key}`, navigates only on save success, and states answers do not change the risk category; no scoring code exists in the file. (Reachable via the onboarding route, not the sidebar.) |
| 4 Goals | ✅ | `goals-page.tsx` renders API fields through `formatCurrency`/`formatPercent`; `null` → "Not available"; no feasibility or Monte Carlo arithmetic. |
| 5 Analysis | ✅ | Dashboard, Risk, Financial Health, Goals, Portfolio, Recommendation, Why, Agent Activity all read the single shared `["analysis", profileId]` query; none recalculates. |
| 6 Savings-first | ✅ (after a fix) | Recommendation and Portfolio pages show "Savings-first priority … no allocation is active"; Financial Health shows the emergency-fund alert. **Fixed:** the Dashboard said "A recommendation is ready" (overall status is `approved` for savings-first too); it now says a *savings-first* recommendation is ready and no investment allocation is active. |
| 7 Rejected | ✅ (after a fix) | No allocation and no explanation are shown (recommendation and explanation are `null`; Why page says why). **Fixed:** the API's per-rule reasons were rendered by *no* page — a rejected analysis showed only a generic sentence. New display-only `ComplianceBreakdown` shows each rule's description, triggered/passed (icon + text), and the engine's own reason. |
| 8 Pending information | ✅ | `AnalysisIncompleteNotice` states additional information is required; the Why page now says the same; no risk/portfolio values are invented. |

**Frontend value → backend source audit.** Every figure the UI shows is read
from the `AnalysisResult`/profile/financial-inputs API objects: risk
(`risk.risk_category/confidence/class_probabilities`), emergency fund
(`emergency_fund.required_amount/current_amount/shortfall/sufficient`), goals
(`goals[].nominal_target_amount/inflation_adjusted_target_amount/
required_periodic_contribution/contribution_gap/monte_carlo_success_probability/
feasibility`), portfolio and recommendation strategy/weights/return/
volatility/Sharpe (the Portfolio and Recommendation pages read the
`recommendation` object — Phase 14's final pick — not the raw `portfolio`),
recommendation status/reasons, market regime (`market.instruments[]`),
compliance (`compliance.decision/rule_results`). The only arithmetic in
`frontend/src` on financial values is `value * 100` for a `[0,1]` fraction
(two `Progress` bars and `formatPercent`) — the presentation formatting the
API contract explicitly allows. A hand-written interface mirroring a schema:
none (`types/api.ts` is byte-identical to a fresh generation, §8).

## 7. SSE Validation

Captured live from `GET /api/analysis/stream` (`text/event-stream`):

- **29098 (approved), 12 frames**: `analysis_started → customer_analyzer →
  risk_analyst → financial_health_analyst → goal_analyst → market_analyst →
  portfolio_manager → compliance_analyst → approved → recommendation →
  explanation → analysis_completed(approved)`.
- **29099 (savings-first), 12 frames**: same, with `savings_first` in place of
  `portfolio_manager` and "Recommendation status: savings_first."
- **29100 (rejected), 10 frames**: `… savings_first → compliance_analyst →
  rejected → analysis_completed(rejected)` — **no recommendation or
  explanation event**, so compliance REJECT terminates downstream work.
- Every frame's data keys were exactly `duration_ms`, `model_version`, `node`,
  `status`, `summary` — no prompt, transcript, or reasoning field exists.
- One capture for 29099 ended early because the database connection dropped
  mid-`INSERT INTO recommendations`; the stream emitted only the fixed safe
  frame (`"Analysis failed" / "An unexpected error occurred."`) — the SQL,
  parameters, and traceback stayed in the server log. A re-capture was clean.
  This live incident is a confirmation of the no-raw-exception rule.
- SSE-created `recommendations` rows from these captures were deleted
  afterwards (only rows newer than the pre-capture maximum id); counts were
  restored.

## 8. API Contract Validation

The live OpenAPI schema lists 13 routes, including
`GET`/`PUT /api/profiles/{profile_id}/financial-inputs`.
`frontend/src/types/api.ts` was compared against a fresh
`openapi-typescript` generation from `app.openapi()` (called in-process, no
server) and is **byte-identical**. No API schema changed in Phase 29, so the
file was not regenerated.

## 9. Database Validation

Read-only audit of both databases: Alembic head **`8ef3f9affbe5`** in dev and
test; all 12 required tables present; no extra tables; **Alembic
`compare_metadata` reports no drift** against the models in either database;
`financial_inputs` structure exactly as designed (§3-A). No migration was
created or run in Phase 29 and no migration history was touched.
`risk_assessments` has 0 rows (by design, §4 step 8). Demo `financial_inputs`
rows: only 29098 and 29099.

## 10. Security Validation

- Secret scan (API-key/credential/connection-string/password/JWT patterns)
  across `backend`, `config`, `frontend/src`, `scripts`, `docs`, `reports`,
  `tests`, `training`, `CLAUDE.md`, `README.md`: **NOT FOUND** (after
  excluding known-benign hits: empty defaults, `type="password"` inputs,
  the demo credential constant). `.env` is untracked and gitignored. The demo
  credential appears only in `frontend/src/lib/prototype-auth.ts`.
- **Customer isolation**: live GETs for the four personas each returned their
  own `customer_id` and their own financial inputs, goals, and 25
  questionnaire answers; tests cover per-customer isolation for
  questionnaire, goals, and financial inputs. This is data-scoping, not
  authorization — the prototype has no per-account authorization (disclosed).
- **RFC 7807** verified live: unknown customer 404, invalid body 422, unknown
  analysis 404 — all `application/problem+json`.
- No hard-coded customer id in application code or tests.

## 11. Model Integrity

`find models -type f -newer <pre-Phase-29 marker>` → empty. No artifact was
modified, retrained, or re-saved.

## 12. Dataset Integrity

`find datasets -type f -newer <pre-Phase-29 marker>` → empty. No raw
FAR-Trans/Kaggle file, `market_data` row, or training dataset was modified.

## 13. Backend Tests

**Final isolated run on the final code state (`pytest tests/ -v -x
--tb=long`, nothing else touching either database):
763 passed, 3 skipped, 0 failed, 152 warnings, 1184.30s.** The output file
contains 763 `PASSED` lines and no `FAILED`/`ERROR` line. The 3 skips are
the live-Gemini tests — `test_debate_gemini_client.py::
test_gemini_model_client_produces_a_real_non_empty_response`,
`…::test_gemini_model_client_message_retrieval_and_usage_contract`, and
`test_explanation_gemini_client.py::test_call_gemini_returns_a_valid_structured_output`
— which skip because Gemini's quota is exhausted (§17). No test was
weakened, deleted, or skipped to obtain this result; 763 = 748 (Phase 28
baseline) + 14 (`test_goal_period_frequency.py`) + 1
(`test_profiles.py` lookup determinism).

Honest run history for this phase (the databases are hosted, and the network
was intermittently failing during it):

| Run | Result | Classification |
|---|---|---|
| A (pre-restart) | 722 passed, 9 failed, 20 errors | All from tracebacks: `getaddrinfo failed [Errno 11001]`, `Network is unreachable (10051)`, `Socket is not connected (10057)`, `server closed the connection unexpectedly`, then `PendingRollbackError`. A DB-free reachability probe later reproduced `WinError 10051`. Environmental. |
| B | **748 passed, 3 skipped, 0 failed** | Clean, on the code as of the start of Phase 29 (confirms the Phase 28 baseline). |
| C | stopped at 7 failures | Network jitter during the run; all 7 re-ran green in isolation. |
| D | **762 passed, 3 skipped, 0 failed**, 1225.82s | Clean, on the code after the two fixes (748 + 14 new tests). |
| E | stopped at 2 errors | Same two `test_recommendation_node.py` tests as in C (their traceback was not captured, so the exact cause is **not proven**; the network was unstable at the time, as in C); all 20 tests in that file pass in isolation. |
| F (final) | **763 passed, 3 skipped, 0 failed**, 1184.30s | Clean, fully isolated, on the final code state; the same two tests passed in this run (it ran with `-x --tb=long`, so any failure would have printed its traceback immediately). Authoritative result. |

## 14. Frontend Validation

`npx tsc -b`: **0 errors**. `npx oxlint`: **0 errors, 8 warnings** (the
unchanged pre-existing baseline in shadcn primitives/provider files).
`npm run build`: succeeds — 962.45 kB / gzip 295.66 kB (+1.74 kB for
`ComplianceBreakdown`; the pre-fix build was 960.71 kB, identical to Phase
28's). All three were re-run on the final source state after the last
frontend edit. No browser test was performed (§6).

## 15. Documentation Synchronization

Updated: `CLAUDE.md`, `TASKS.md`, `.claude/rules/testing.md`,
`docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`
(ADR-027, ADR-028; a note under ADR-026; two cross-reference errors from the
documentation pass corrected), `docs/MEMORY.md`, `docs/TEST_PLAN.md`,
`docs/demo_runbook.md`, `reports/demo_dataset_catalog.md`. Historical report
`reports/phase28_financial_input_savings_first_report.md` was **not
rewritten**: a clearly marked correction note was added at its top
superseding its "honest Not Feasible" claims. `docs/SECURITY.md` gained a
short note (§19) that the SSE endpoint emits only a fixed safe error frame,
confirmed live; `docs/RULES.md` was inspected and needed no change. The six Phase 28
decisions were checked against `DECISIONS.md`: separate table (ADR-025),
nullable-not-zero (ADR-025), all-or-nothing `GoalAssumptions` (**was not
recorded — added as ADR-028**), `market_data` as the return source
(ADR-026), savings-first legitimately has no weights and the compliance
distinction (ADR-018).

## 16. Files Changed

Classification (git has no commits, so `git diff` has no baseline; this is
from a modification-time audit against the last pre-Phase-29 write, plus my
own edit log):

**B — Required Phase 29 integration fixes**
- `backend/wealthpilot/api/services/analysis_service.py` — period-aligned goal
  returns, `ANALYSIS_PIPELINE_VERSION` in the cache key, state-accurate
  `savings_first` SSE summary.
- `backend/wealthpilot/api/routers/profiles.py` — deterministic lowest-id
  `lookup` when names are duplicated.
- `backend/scripts/seed_demo_data.py` — same `ORDER BY id LIMIT 1`.
- `frontend/src/components/shell/compliance-breakdown.tsx` (new),
  `frontend/src/pages/recommendation-page.tsx`,
  `frontend/src/pages/why-this-recommendation-page.tsx`,
  `frontend/src/pages/dashboard-page.tsx`.
- `tests/backend/api/test_goal_period_frequency.py` (new, 14 tests),
  `tests/backend/api/test_profiles.py` (+1 test).

**A — Expected documentation/validation changes**
`CLAUDE.md`, `README.md` (status line), `TASKS.md`, `.claude/rules/testing.md`, `docs/ARCHITECTURE.md`,
`docs/PRD.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`, `docs/MEMORY.md`,
`docs/SECURITY.md`, `docs/TEST_PLAN.md`, `docs/demo_runbook.md`, `reports/demo_dataset_catalog.md`,
`reports/phase28_financial_input_savings_first_report.md` (note only),
`reports/phase29_final_integration_report.md`.

**C — Unexpected changes (not made by this phase)**
1. `backend/wealthpilot/config/settings.py` — modified outside my sessions
   (observed changing three times across the work); its mtime did **not**
   change during Phase 29. Content is an ordinary `pydantic-settings` class
   with no secret values. Left untouched.
2. A second customer named "WealthPilot Demo Customer" (id **29101**, created
   2026-09-18 21:08 GMT, 2 goals + 25 answers, 1 analysis run) — see §18.

Not changed: `models/`, `datasets/`, migrations, `core/goals.py`,
`core/compliance.py`, `core/recommendation.py`, agent nodes, the API schema,
`types/api.ts`. No historical report was deleted. No credential was added.

## 17. Known Limitations

- **Live Gemini explanation could not be demonstrated.** In both approved
  demo runs the explanation is the designed templated fallback
  (`validation_passed: false`). A direct diagnosis (rolled-back session,
  nothing persisted) showed the cause: Gemini returned **`429
  RESOURCE_EXHAUSTED` — the account's quota is exhausted** — on both attempts.
  The fallback engaged correctly and no number was fabricated, but the
  *validated live-Gemini* path is exercised only by injected-fake unit tests
  and by live tests that skip when quota is unavailable.
- **No browser verification** was possible (§6).
- The three live-Gemini tests skip when Gemini is out of quota.
- Recommendation status `blocked_rejected` is never returned by
  `POST /api/analysis` (a REJECT yields analysis status `rejected` with
  `recommendation: null`); the frontend's `blocked_rejected` branches are
  therefore only reachable if the engine's output is surfaced some other way.
  Harmless, and left as is.
- Superseded `AnalysisRun` rows 150–153 (computed under the goal-frequency
  defect) remain in the database as history; the app only reads the current
  cached run via `POST /api/analysis`.
- The Goals page shows a negative contribution gap as a negative euro amount
  with no explanatory text ("negative = ahead of plan"); the demo runbook
  explains it.
- Prototype authentication limits are unchanged and disclosed.

## 18. Unexpected Findings

**Defects in the Phase 28 baseline, found by this validation and fixed:**

1. **Goal Monte Carlo used the wrong return frequency.** Every demo goal
   showed 0.0% / "Not Feasible", including a Retirement goal whose
   deterministic contribution gap was *negative* (ahead of plan). Cause:
   `run_goal_monte_carlo` draws one return per contribution period, but
   Phase 28 passed the raw **daily** series — a ~0.04% daily return applied
   once per month. Reproduced on the real data (1,176 daily observations,
   279 monthly periods): 0.0% as supplied vs 94.1% compounded to monthly.
   **My Phase 28 report called those results "honest" and "not tuned" — that
   was wrong**, and I have corrected it (top-of-report note, catalog,
   runbook, ARCHITECTURE, PRD, ADR-027). Fix: `_compound_to_period_returns`
   (definitional compounding; `core/goals.py` untouched; no new constant).
   Because the cache key covered inputs but not the computation, any
   customer analysed under the old behaviour would have kept the wrong
   result forever; `ANALYSIS_PIPELINE_VERSION` now closes that.
   The corrected signal reaches Phase 14's goal layer ("Not Feasible" →
   "At Risk" in 29098's rationale) without changing any selected strategy or
   terminal status.
2. **No page rendered compliance rule reasons**, so a rejected analysis could
   not show *why*. Also: my previous-task documentation had claimed the
   Recommendation page showed a rule breakdown; that was inaccurate until now
   (DESIGN §25 corrected).
3. **The `savings_first` SSE summary always said "insufficient"**, including
   for 29100 whose sufficiency is unknown — an unsupported claim on the Agent
   Activity page.
4. **`GET /api/profiles/lookup` was nondeterministic when names repeat** (a
   duplicate exists — below). Now lowest-id-wins, with a test.

**Observations outside this phase's control:**

- **Duplicate demo customer 29101.** Created 2026-09-18 21:08 GMT (02:38 IST
  on the 19th) — the same minute I first saw `settings.py` changing — by the
  Phase 24 "Use Demo Account" flow running in a browser whose `localStorage`
  did not hold the demo id (Phase 24's documented per-browser idempotency
  limit; not something my scripts do). It is app-created data, so it was not
  deleted. In a seeded environment "Use Demo Account" now resolves to
  "Complete" by name and cannot create another.
- **Network instability** during the test runs (§13).
- A test-DB connection drop mid-`INSERT` surfaced through SSE as the fixed safe
  frame, as designed (§7).

## 19. Final Assessment

Completion criteria (Phase 29 prompt §21):

| Criterion | Met? | Evidence |
|---|---|---|
| Phase 28 baseline verified as one system | Yes | §3, §5 (live API), §7 (live SSE) |
| Four personas produce their designed outcomes through the real API | Yes | §5 |
| No fabricated financial value; NULL never 0 | Yes | §3, §5, §6 |
| Compliance unweakened; REJECT stops downstream work | Yes | §5 (29100), §7 (no recommendation/explanation event); `core/compliance.py` untouched |
| Frontend never computes a financial number | Yes (source-level) | §6 audit; only `value * 100` formatting exists |
| Frontend journeys | Verified at **source level only** — no browser tool exists, none was claimed | §6 |
| SSE for approved / savings-first / rejected | Yes | §7 |
| API/OpenAPI contract, generated types identical | Yes | §8 |
| Database at head, no drift, no new migration | Yes | §9 |
| Secret scan | NOT FOUND | §10 |
| Model artifacts and datasets unmodified | Yes | §11, §12 |
| Full backend suite in isolation, no failure | Yes | 763 passed, 3 skipped, 0 failed (§13) |
| Frontend tsc / oxlint / build | Yes | §14 |
| Documentation synchronized, historical reports preserved | Yes | §15 |
| Every changed file explained (A/B/C), nothing unexplained | Yes | §16 |
| No Phase 30 started or invented | Yes | `TASKS.md` lists none |

Assessment: the Phase 28 baseline was **not** fully correct — the goal
Monte Carlo defect (§18) meant every demo goal was reporting 0.0%. That was
a proven integration defect, fixed within Phase 29's allowed scope (no
financial formula, ML model, compliance rule, or recommendation rule was
changed), guarded by deterministic regression tests, and propagated to
already-cached analyses through the cache key. After the fixes, the system
behaves as one coherent whole. What remains unproven, and is stated as
such: (1) the live *validated-Gemini* explanation path (quota exhausted —
fallback engaged correctly); (2) any in-browser rendering behaviour.

## 20. Git Status

`git status --short` shows every top-level path as `??` (untracked); the
repository has **0 commits**, so there is nothing staged and no diff
baseline. Nothing was committed by this phase.
