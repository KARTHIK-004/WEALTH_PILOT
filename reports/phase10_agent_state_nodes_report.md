# Phase 10 — Agent State / Nodes Report

## 1. Status

**COMPLETE.**

## 2. State architecture

`backend/wealthpilot/agents/state.py` — one typed `AgentState` Pydantic model (BUILD_PLAN.md section 9: "One typed `AgentState` Pydantic model, defined before any node is written"), plus `AgentStateDelta` (all fields optional) and `apply_delta(state, delta) -> AgentState`, the only sanctioned way to combine the two. `apply_delta` always returns a **new** object via `model_copy` — `state` itself is never mutated (manual verification item, tested directly). A delta field left `None` leaves the corresponding state field untouched, so a node that didn't compute something can never accidentally blank out a previous node's result; `errors` accumulates across deltas rather than being replaced.

**No hidden chain-of-thought anywhere** — verified by a test asserting none of `AgentState`, `AgentStateDelta`, or any nested model has a field named `reasoning`/`chain_of_thought`/`hidden_thoughts`/`internal_reasoning`/`scratchpad*`/`private_reasoning`. Every field is a structured input, a validated result, a concise status value, or provenance metadata.

## 3. State fields

| Field | Type | Notes |
|---|---|---|
| `customer_id` | `int` | required |
| `analysis_run_id` | `str \| None` | correlation id only — Phase 10 never writes `analysis_runs` itself (see §17) |
| `customer_profile` | `CustomerProfile \| None` | lean projection of `customers` + `financial_goals` rows, not the full ORM object |
| `risk_assessment` | `RiskAssessmentResult \| None` | Phase 4 |
| `financial_health` | `FinancialHealthResult \| None` | Phase 5 |
| `goal_results` | `list[GoalAnalysisResult] \| None` | Phase 7, per goal |
| `emergency_fund` | `EmergencyFundResult \| None` | Phase 7 |
| `market_analysis` | `MarketAnalysisResult \| None` | Phase 6 |
| `portfolio_result` | `PortfolioResult \| None` | Phase 8 |
| `compliance_result` | `ComplianceResult \| None` | Phase 9's own type, reused directly (not re-wrapped) |
| `blocked`, `block_reason` | `bool`, `str \| None` | **derived only** — see §9 |
| `errors` | `list[NodeError]` | accumulates |
| `created_at`, `updated_at` | `str` (ISO 8601) | |

Every optional numeric/categorical result field carries a companion `unavailable_reason: str | None` — `None` means genuinely unavailable, never a fabricated stand-in value.

## 4. Node list

`backend/wealthpilot/agents/nodes.py` — all 10 nodes BUILD_PLAN.md section 8's table specifies for this phase (excluding AutoGen Strategy Debate and Gemini Explanation, explicitly Phase 12/13):

1. `customer_analyzer_node`
2. `risk_analyst_node` (+ `engineer_features_for_customer` helper)
3. `information_request_node`
4. `financial_health_node`
5. `reprofile_node`
6. `goal_analyst_node`
7. `market_analyst_node`
8. `portfolio_manager_node`
9. `savings_first_node`
10. `compliance_analyst_node`

## 5. Node responsibilities

**Customer Analyzer** — loads `customers` + `financial_goals` DB rows for one `customer_id`, normalizes into `CustomerProfile`. No feature engineering, no model call.

**Risk Analyst** — classifies risk category using the ALREADY-TRAINED Phase 4 model (`models/risk/rf_v1.pkl` — Phase 4's selected `best_model`, `random_forest` — + `preprocessor_v1.pkl`), never retrained, never a different model selection. Takes an explicit `feature_row` rather than computing it internally (see §10 for why). Output is restricted to `GENUINE_RISK_LEVELS` only — verified directly against real data that the classifier never produces `Predicted_*`/`Not_Available`.

**Information Request** — produces structured follow-up questions from the current risk assessment. Does **not** decide the confidence threshold that would trigger it — that's Phase 11's conditional-routing constant, not invented here (an explicit STOP-condition item, resolved by scoping it out rather than guessing a number).

**Financial Health Analyst** — behaviour-change detection only: Phase 5's ALREADY-TRAINED Isolation Forest (`models/behaviour/iforest_v1.pkl`, never refit) + rolling z-score, computed live from the customer's own transaction history. `expense_persona` is **always** `None` with an explicit reason (Kaggle-only model, different unlinked population); `savings_rate`/`expense_ratio` are **always** `None` (FAR-Trans has no income/expense fields) — neither is ever fabricated or backfilled from Kaggle.

**Re-profile** — a thin wrapper re-invoking `risk_analyst_node` itself; not a second risk-scoring implementation (verified directly: identical output to a direct call, modulo the ~1e-16 float non-determinism RandomForest's `n_jobs=-1` already exhibited in Phase 4's own tests).

**Goal Analyst** — calls Phase 7's `analyze_goal_funding`/`run_goal_monte_carlo`/`classify_feasibility`/`assess_emergency_fund`/`savings_first_required` only; no TVM/Monte Carlo/emergency-fund math is duplicated (verified directly: the node's `required_periodic_contribution` matches a direct Phase 7 call exactly). `GoalAssumptions`, `historical_returns`, `monthly_essential_expenses`, `current_liquid_assets` remain explicit, optional inputs with no invented default — consistent with Phase 7's own no-default design.

**Market Analyst** — reads Phase 6's ALREADY-COMPUTED regime results from `models/metrics.json["market"]`; never re-runs Phase 6's training (a full walk-forward run takes ~1 hour and refetches yfinance data — unsuitable for a node call) and never introduces a new forecast. Verified directly: every regime value returned matches `metrics.json` exactly.

**Portfolio Manager** — calls Phase 8's `core.optimizer` LIVE (cheap, pure, deterministic — unlike Market Analyst) on a freshly-read `market_data` return matrix, using the customer's risk category for `strategy="mvo"`. Never redesigns MVO/HRP/1-N; every threshold (QQQ bands, 70% cap) is read directly from `wealthpilot.core.optimizer`'s own constants — verified directly against `RISK_LEVEL_QQQ_BANDS`. Does **not** itself decide "optimize or defer" for an insufficient emergency fund — see §9.

**Savings-first** — reuses `state.emergency_fund` (Phase 7's own output) directly; produces no portfolio weights at all, matching PROJECT_PLAN.md's "skipping optimization entirely."

**Compliance Analyst** — calls Phase 9's `evaluate_compliance` only; builds a `ComplianceProposal` strictly from already-computed state fields. Verified directly: `state.portfolio_result.weights` is byte-identical before and after this node runs, even on a REJECTing proposal.

## 6. Node dependencies

```
customer_analyzer_node
      |
risk_analyst_node ------------------- (low confidence) --> information_request_node
      |
financial_health_node ---------------- (significant drift) --> reprofile_node -> risk_analyst_node
      |
goal_analyst_node
      |
market_analyst_node
      |
portfolio_manager_node --------------- (EF insufficient) --> savings_first_node
      |
compliance_analyst_node
```

Every node above is independently callable and independently tested. **Phase 10 builds every node in this diagram; it does not decide which branch runs for a given state** — the "low confidence," "significant drift," and "EF insufficient" conditional routing is explicitly Phase 11's job (BUILD_PLAN.md section 9's conditional-routing list), not implemented here.

## 7. Provenance

Every result carrying `model_version`/`data_source` reuses the exact strings each phase already established: Risk (`"v1"`, `"models/risk"`), Financial Health (`"v1"`, `"models/behaviour"`), Market (Phase 6's own `model_version`/`data_source` read verbatim from `metrics.json`), Portfolio (`"v1"`, `"market_data (PostgreSQL)"`), Compliance (Phase 9's own `rules_version`, unchanged). Provenance is recorded even on an "unavailable" result (e.g. `risk_assessment.model_version` is still `"v1"` when `feature_row` wasn't supplied) — never dropped when a node can't produce a full result.

A Pydantic quirk surfaced while writing this: fields named `model_version` collide with Pydantic's own protected `model_` attribute namespace, producing a `UserWarning`. Fixed with `model_config = ConfigDict(protected_namespaces=())` on the four affected models (`_ProvenanceModel` base class) rather than renaming the field away from the project's established convention.

## 8. Error handling

`NodeError.error_type` distinguishes exactly the categories section 16 lists: `"validation"` (e.g. an incomplete `feature_row`), `"missing_data"` (e.g. unknown `customer_id`, no transaction history, no risk assessment for Information Request), `"processing_failure"` (e.g. the classifier returning an unrecognized label — a guard that should never fire in practice, kept anyway). No node silently converts an error into a valid-looking financial result — every "unavailable" path sets both `unavailable_reason` on the result AND, where the input was genuinely invalid rather than merely absent, a `NodeError`.

## 9. Compliance gate integration

`blocked`/`block_reason` are **not** fields on `AgentStateDelta` at all — a node cannot set them directly (verified directly: `"blocked" not in AgentStateDelta.model_fields`). `apply_delta` derives them itself, authoritatively, from `compliance_result.decision` whenever a delta supplies a new `compliance_result`: REJECT sets `blocked=True` with a concatenated summary of the violated rules' messages; PASS/WARN sets `blocked=False`. This makes a REJECT structurally explicit rather than a message a caller might miss, and makes "blocked stays stuck at False because a node forgot to set it" structurally impossible.

**The explicit safety-contract test** (section 25's "most important test," `tests/backend/agents/test_compliance_gate_safety.py`): a minimal, test-only `_downstream_explanation_stub` function (standing in for the not-yet-built Phase 13 Gemini Explanation / Phase 14 Recommendation Engine) calls Phase 9's `enforce_gate(state.compliance_result)` as its very first line. Six tests prove: a REJECTing proposal raises `ComplianceRejectedError` before the stub's body executes (checked via a `reached_body` flag that must stay `False`); a PASSing proposal reaches the body normally; the exact PROJECT_PLAN.md emergency-fund-insufficient-without-savings-first scenario REJECTs; and — critically — a REAL Phase 8 Portfolio Manager output (not hand-constructed weights) still gets correctly gated end-to-end. No LangGraph was built to test this, per section 25's explicit instruction.

## 10. Missing-data handling

FAR-Trans's known gaps (no income/expense fields, no genuine feature row for every customer, no Kaggle linkage) surface as `unavailable_reason` strings, never fabricated values — this was directly exercised against **real data**: the smoke-tested customer's Financial Health result correctly reported "insufficient trading history (2 months, 4 required)" rather than a guessed drift flag. `engineer_features_for_customer` (the one genuinely new piece of glue code Phase 10 adds — see the module docstring) closes Phase 3's "no single-customer feature-engineering entrypoint" gap the only way that doesn't risk a subtle bug: by calling `engineer_features()` completely unmodified on the raw FAR-Trans tables filtered to one customer (every feature in it is a `groupby("customerID")` aggregation, so this is provably identical to filtering the full population's output afterward, not an approximation).

## 11. Security/data-safety considerations

No LLM (Gemini/OpenAI/Claude/anything), no AutoGen, no LangGraph is imported anywhere in `agents/nodes.py` — verified with an AST-based import check (not a naive substring search, which would false-positive on the module's own docstring explaining what it does *not* call). No node writes to PostgreSQL (Customer Analyzer and Portfolio Manager only `SELECT`) — verified by every test connecting read-only and by direct code review. `Customer.risk_inputs["external_customer_id"]` (a DB-internal mapping field) is read but never surfaced on `CustomerProfile`, which a test asserts directly.

## 12. Files created/modified

- **Created**: `backend/wealthpilot/agents/state.py`, `backend/wealthpilot/agents/nodes.py`.
- **Created**: `tests/backend/agents/test_{state,nodes,compliance_gate_safety}.py`.
- **Created**: this report.
- **Untouched**: `models/{risk,expense,behaviour,market,portfolio}/`, `models/metrics.json` (no "agents"/"state" section was invented — none of the three authoritative documents require one), `backend/wealthpilot/db/models.py`, all Alembic migrations, `config/compliance_rules.yaml`, `backend/wealthpilot/core/{goals,optimizer,backtest,compliance}.py`, all raw datasets.

## 13. Tests

**61 new Phase 10 tests**, all passing:

| File | Tests | Covers |
|---|---|---|
| `test_state.py` | 16 | Validation, JSON serialization/round-trip, no-hidden-reasoning field check, immutability (new-object, field-preservation, no-silent-blanking), error accumulation, derived `blocked`/`block_reason` (incl. REJECT→PASS transition, and the structural "not a delta field" guarantee) |
| `test_nodes.py` | 39 | One node at a time — real-data integration tests (a real FAR-Trans customer, real risk classification, real behaviour detection, real market regime, real MVO/HRP/1-N weights) plus synthetic missing-data/validation/edge-case tests for every node; provenance preservation; "does not duplicate business logic" tests comparing node output directly against a raw Phase 7/8 call; no-LLM/AutoGen import check |
| `test_compliance_gate_safety.py` | 6 | The end-to-end REJECT-blocks-downstream contract, including with real Phase 8 output |

**Full project test suite: 400 tests, all passing** (`pytest tests/ --collect-only -q` confirms 400 collected, 0 skipped; 400 passed in 415s). No regressions in Phases 0-9.

## 14. Manual verification

- [x] Authoritative documents inspected (CLAUDE.md, PROJECT_PLAN.md, MASTER_PROMPT.md, BUILD_PLAN.md section 8/9, all Phase 4-9 reports).
- [x] Shared state implemented, strongly typed, JSON-serializable (round-trip tested).
- [x] No hidden chain-of-thought fields anywhere (tested directly).
- [x] All 10 required nodes implemented (Customer, Risk, Information Request, Financial Health, Re-profile, Goal, Market, Portfolio, Savings-first, Compliance).
- [x] Provenance (`model_version`/`data_source`) preserved on every result, including unavailable ones.
- [x] Missing data handled explicitly (`unavailable_reason`), never fabricated — tested against real data gaps.
- [x] Compliance REJECT is binding — `blocked`/`block_reason` structurally derived, not node-settable; end-to-end gate test proves downstream is blocked.
- [x] REJECT cannot be silently converted to PASS (tested: a caller that skips checking `decision` entirely still gets blocked via `enforce_gate`).
- [x] Compliance does not modify portfolio weights (tested: byte-identical before/after, including on a REJECTing case).
- [x] No Gemini, no AutoGen, no LangGraph orchestration anywhere (AST-verified).
- [x] No Recommendation Engine, no FastAPI, no React implemented.
- [x] No new financial methodology invented — every number traces to an already-approved Phase 4/6/7/8/9 constant or function.
- [x] No fabricated FAR-Trans expense/savings data; no Kaggle/FAR-Trans linkage (tested directly).
- [x] Previous Phase 0-9 tests pass; complete project suite passes (400/400).
- [x] Database integrity verified — no schema change, no new migration, no write from any Phase 10 node.
- [x] Raw datasets unchanged (verified via mtime comparison).
- [x] Existing artifacts preserved (`models/{risk,expense,behaviour,market,portfolio}/` untouched).

## 15. Known limitations

1. **SHAP values are not computed per-customer.** Phase 4's SHAP explainability was global/training-population-level; live per-customer SHAP would need reloading a `TreeExplainer` at inference time. Deferred rather than risk an untested addition under this phase's time budget — `risk_score` is similarly always `None` (Phase 4 never defined an ordinal risk score, only the 4-class categorical prediction, so none was invented here either).
2. **`financial_goals` currently has zero rows in the database** (it is user-entered only; nothing has ever populated it, per its own Phase 1 docstring) — `goal_analyst_node` was verified against a manually-constructed `CustomerProfile` with a synthetic goal rather than a real DB-backed one, since no real goal exists yet to test against. The node's DB-facing path (`customer_analyzer_node` reading `financial_goals`) is still exercised directly and returns an empty list correctly for real customers.
3. **`engineer_features_for_customer` reloads the full raw FAR-Trans CSV tables on first call** (cached per-process afterward via `lru_cache`) rather than an optimized single-customer DB query — correct and safe (see §10), but not performance-tuned; a future phase serving many customers per process would likely want this pre-warmed at startup rather than lazily on first request.
4. **Confidence/drift/EF-sufficiency thresholds that decide ROUTING (not the values themselves) are intentionally not set here** — Information Request's confidence threshold, Re-profile's drift-significance threshold, and Portfolio Manager vs. Savings-first branching are Phase 11's conditional-routing constants, explicitly out of this phase's scope.

## 16. Explicit Phase 11 boundary

**Phase 10 does NOT implement LangGraph orchestration.** No `StateGraph` is compiled; no conditional edge exists in code; nothing routes between nodes automatically. Every node above is called directly and explicitly in tests, exactly as section 20/36 require. `agents/graph.py` does not exist yet. AutoGen (Phase 12) and Gemini (Phase 13) are not implemented, imported, or referenced anywhere in `agents/nodes.py`.

## 17. Next phase

**Phase 11 — LangGraph.**

**Do not begin Phase 11.** Awaiting explicit approval of this report.
