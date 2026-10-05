# Phase 11 — LangGraph Orchestration Report

## 1. Status

**COMPLETE.**

## 2. Graph architecture

`backend/wealthpilot/agents/graph.py` — a compiled `StateGraph(AgentState)` connecting the 10 Phase 10 nodes into the deterministic subset of BUILD_PLAN.md's workflow (excluding AutoGen Strategy Debate and Gemini Explanation, which do not exist until Phases 12/13). Every graph node wrapper calls exactly one Phase 10 node function and applies its result via `apply_delta` — never bypassed, never a second mutation path. No new financial/ML logic exists anywhere in this file; `core/compliance.py`, `core/goals.py`, and `core/optimizer.py` are never imported directly here, only through `agents/nodes.py`.

**Dependency threading**: per-run dependencies a node needs beyond `state` (a DB `Session`, `GoalAssumptions`, a Monte Carlo return series, essential-expense/liquid-asset figures, portfolio strategy) are passed through LangGraph's own `RunnableConfig.configurable` mechanism (`GraphDependencies`, converted to a plain dict), never bolted onto `AgentState` as new fields.

## 3. State model used

Phase 10's `AgentState` unchanged — no second, competing schema. One small, disclosed exception: `agents/nodes.py::_external_customer_id` was renamed to `external_customer_id` (dropping the leading underscore) since Phase 11's graph wrappers need it too; the function's behavior is byte-for-byte unchanged, this is a visibility rename only, not a rewrite of Phase 10 logic.

Every node wrapper returns the **full** post-`apply_delta` state as a dict (verified directly: `AgentState → node → model_dump() → LangGraph merge → AgentState.model_validate()` round-trips real nested Pydantic models, e.g. `RiskAssessmentResult`, correctly — not plain dicts). This sidesteps needing custom LangGraph reducers per field: LangGraph's default merge becomes a trivial full-replace, and `apply_delta`'s own semantics (new-object-only, field preservation, error accumulation, compliance-derived `blocked`) are always what actually happened.

## 4. Node list

All 10 Phase 10 nodes, registered under names that don't collide with `AgentState`'s own field names (LangGraph refuses a node name equal to a state key — discovered directly while building this: `financial_health` and `blocked` both collided and were renamed to `financial_health_analyst` and `rejected`):

`customer_analyzer`, `risk_analyst`, `information_request`, `financial_health_analyst`, `reprofile`, `goal_analyst`, `market_analyst`, `portfolio_manager`, `savings_first`, `compliance_analyst`, plus four terminal marker nodes: `approved`, `rejected`, `pending_information`, `failed`.

## 5. Graph topology

```
START
  |
customer_analyzer
  |
risk_analyst --(confidence is None or < 0.50)--> information_request --> END [pending_information]
  |  (confidence >= 0.50)
financial_health_analyst --(behaviour_drift_flag is True)--> reprofile --> goal_analyst
  |  (no drift)                                                                |
  +----------------------------------------------------------------------------+
  |
goal_analyst
  |
market_analyst
  |
  +--(emergency_fund.sufficient is True)--> portfolio_manager --+
  |                                                              |
  +--(sufficient is False or None)--> savings_first -------------+
                                                                  |
                                                          compliance_analyst
                                                                  |
                                          +-----------------------+-----------------------+
                                          |                                               |
                                (decision == REJECT)                          (decision in PASS/WARN)
                                          |                                               |
                                       END [rejected]                                 END [approved]

Any unexpected node exception, at any point above, routes immediately to
END [failed] instead of continuing (checked at every conditional-routing point).
```

(This is `graph.TOPOLOGY`, printable directly from the module.)

## 6. Conditional routing

Four routing decisions, all documented reasoning — three were confirmed via `AskUserQuestion` before any code was written (2026-09-14):

1. **Risk confidence threshold = 0.50** (approved). `None` confidence (feature row unavailable) is treated as the extreme case of low confidence, not a separate condition — routes to Information Request the same way a numeric value below 0.50 would.
2. **Re-profile is a one-time branch**: `financial_health_analyst --(drift)--> reprofile --> goal_analyst`, never looping back to `financial_health_analyst` or a separate risk-analyst graph node. This resolves an internal inconsistency in BUILD_PLAN.md itself (its free-hand diagram shows "Re-profile -> Risk Analyst"; its own node table's "Next node" column says "Goal Analyst") in favour of the more precise, structured table — and trivially satisfies section 40's loop-safety requirement, since there is no cycle in this graph at all.
3. **Emergency-fund `sufficient is None` (unavailable) routes the same as `False`** (approved) — both go to Savings-first, the more conservative reading of "do not recommend aggressive investment allocation when essential liquidity requirements are not satisfied."
4. **No REJECT retry loop** (approved) — BUILD_PLAN.md's fuller diagram describes one ("capped at N retries," explicitly "finalized during Phase 11") but names no N anywhere, and Portfolio Manager is fully deterministic with no mechanism for a retried attempt to differ from the first (no node contract lets a violated rule adjust inputs) — a loop would just deterministically reproduce the identical REJECT until an arbitrary cap. REJECT is a single, direct terminal edge, matching this phase's own section 9 routing sketch and section 42 manual-verification checklist, neither of which mention a retry counter.

Every routing function is a pure function of `AgentState` only — tested directly and exhaustively (23 tests) for every branch, boundary value (`confidence == 0.50` exactly), and the `None`/missing-data edge case, with zero DB/LLM/randomness involved.

## 7. Information-request branch

BUILD_PLAN.md's own table: "Halts run pending more input." Implemented literally — on low/unavailable confidence, the graph reaches `pending_information` and stops; nothing downstream (financial health, goals, market, portfolio, compliance) executes. Verified against real data: customer_id=1's genuine ~0.369 confidence correctly halts here, with every downstream state field left `None` and `compliance_result` never computed at all (not even attempted).

## 8. Re-profile branch

Triggered by `state.financial_health.behaviour_drift_flag is True` — reusing Phase 5/10's already-computed, already-approved boolean (itself built on Phase 5's approved `Z_SCORE_ALERT_THRESHOLD = 2.0`), never a new threshold. `reprofile_node` (Phase 10, unmodified) is a thin wrapper re-invoking `risk_analyst_node`; the Phase 4 model is never retrained, no new risk category is invented.

## 9. Savings-first branch

Triggered by `state.emergency_fund.sufficient` being `False` or `None` — reusing Phase 7's own `EmergencyFundResult` (via Phase 10's `goal_analyst_node`, itself calling Phase 7's `assess_emergency_fund`/`savings_first_required` directly) without any recomputation. Verified directly: the emergency-fund figures a `savings_first`-routed run acts on match a direct Phase 7 call exactly. When this branch fires, `portfolio_manager` never executes — no MVO/HRP/1-N weights are computed for that run at all (verified directly).

## 10. Portfolio branch

`portfolio_manager` (Phase 10, unmodified) is invoked only when `emergency_fund.sufficient is True`; it calls Phase 8's `core.optimizer` with the customer's own risk category. The graph never runs the optimizer itself, never computes a weight in a routing function, never touches MVO/HRP/1-N/Ledoit-Wolf/the QQQ bands/the single-asset cap — the graph only decides *when* `portfolio_manager_node` executes.

## 11. Compliance gate

`compliance_analyst` (Phase 10, unmodified) calls Phase 9's `evaluate_compliance` exactly as before; `is_savings_first_recommendation` is derived from `state.portfolio_result.strategy == "savings_first"` (data-driven, not path-tracked) so the emergency-fund compliance rule correctly recognizes a savings-first proposal as compliant rather than incorrectly flagging it.

## 12. REJECT terminal path

`route_after_compliance` sends a REJECT decision directly to the `rejected` terminal node, then `END` — a single edge, no retry, no alternate path. Section 10's requirements verified directly: the full `ComplianceResult` (rule-level reasons, `rules_version`) and all earlier analysis (`risk_assessment`, `portfolio_result` — including the exact, unmodified weights that triggered the rejection, never "repaired") are preserved unchanged on a REJECTed state.

**The critical safety-contract test** (section 37): a test-only `_ExplanationSpy` class stands in for the not-yet-built Phase 13/14 (explicitly, per section 37's instruction, without implementing either). `_maybe_explain(state, spy)` calls Phase 9's `enforce_gate(state.compliance_result)` as its very first line — exactly the same pattern proven safe in Phase 10's own gate test, now exercised through a REAL, complete graph run in addition to hand-assembled state. Both confirm: a REJECT raises `ComplianceRejectedError` before the spy is ever called (`spy.called` stays `False`); a PASS/WARN reaches the spy normally.

## 13. Error handling

`_safe_call` wraps the **entire body** of each node wrapper (all preparatory lookups — `external_customer_id`, `engineer_features_for_customer` — as well as the final Phase 10 node call) in a single try/except, converting any unexpected exception into a structured `NodeError(error_type="processing_failure")` rather than crashing the graph or silently continuing. Every conditional-routing function checks for a processing failure first, before its own normal logic, and routes straight to the `failed` terminal if one is present. `validation`/`missing_data`/`processing_failure` remain the three distinct categories Phase 10 established — nothing here turns a processing failure into a valid financial result.

**A real bug was found and fixed while writing this phase's own tests**: the first implementation only wrapped the *final* Phase 10 node-function call in the safety net, not the preparatory `external_customer_id`/`engineer_features_for_customer` lookups several wrappers perform first — an exception from those lookups (verified with a deliberately invalid `session=None`) propagated uncaught and crashed the whole graph run instead of producing a structured `processing_failure`, exactly the failure mode `_safe_call` exists to prevent. Fixed by changing `_safe_call` to accept a zero-argument closure covering a wrapper's full body, not just its last line; re-verified with the same failure-injection test, which now passes.

## 14. Provenance

`model_version`/`data_source` verified to survive unchanged through every graph transition, checked directly against real data at the end of a full run: `risk_assessment` (`"v1"`, `"models/risk"`), `financial_health` (`"v1"`, `"models/behaviour"`), `market_analysis` (Phase 6's own values, read verbatim), `portfolio_result` (`"v1"`, `"market_data (PostgreSQL)"`) when present, `compliance_result.rules_version` (`"v1"`).

## 15. Checkpointing decision

**None added.** `build_analysis_graph()` uses `compile()`'s default in-memory execution, no checkpointer attached. Nothing in the authoritative documents explicitly requires cross-process/cross-request graph persistence for Phase 11 — `AnalysisRun`'s "server-side cache of a full LangGraph run" is a later-phase (API-layer) concern per its own docstring, not forced now. This matches section 22's explicit preference: "keep graph execution appropriately scoped" over adding infrastructure "merely because LangGraph supports it."

## 16. Observability

Every terminal outcome is directly inspectable on the returned `AgentState` without any hidden-reasoning field: `compliance_result.decision` (PASS/WARN/REJECT), `blocked`/`block_reason` (derived), `errors` (node name + category + concise message for every processing failure or halt). The four terminal marker nodes (`approved`/`rejected`/`pending_information`/`failed`) make each outcome directly traceable in `compiled.get_graph()`'s own node/edge listing, usable by a later phase's tracing/logging without this phase needing to build a production logging API (explicitly out of scope).

## 17. Tests

**49 new Phase 11 tests**, all passing:

| File | Tests | Covers |
|---|---|---|
| `test_graph_construction.py` | 7 | Compilation, node-name/state-field collision guard, all 10 nodes + 4 terminals registered, entry point, threshold constant, Re-profile one-time-branch guarantee |
| `test_graph_routing.py` | 23 | Every conditional function, every branch, boundary values, `None`/missing-data cases, processing-failure priority, determinism |
| `test_graph_execution.py` | 9 | Real end-to-end runs (real DB, real customers) — pending-information halt, happy-path progression, node ordering, state/provenance preservation, determinism, the processing-failure bug fix's regression test |
| `test_graph_safety_contracts.py` | 10 | The three CRITICAL tests (sections 37/38/39): REJECT-never-reaches-explanation (hand-built AND real full-graph-run variants), REJECT preserves full analysis, savings-first skips optimization and reuses Phase 7 exactly, missing data never becomes PASS |

**Full project test suite: 449 tests, all passing** (`pytest tests/ --collect-only -q` confirms 449 collected, 0 skipped; 449 passed in 355s). No regressions in Phases 0-10.

## 18. Files created/modified

- **Created**: `backend/wealthpilot/agents/graph.py`.
- **Created**: `tests/backend/agents/test_graph_{construction,routing,execution,safety_contracts}.py`.
- **Created**: this report.
- **Modified**: `backend/wealthpilot/agents/nodes.py` — one-line rename (`_external_customer_id` → `external_customer_id`), no behavior change, disclosed in §3.
- **Untouched**: `backend/wealthpilot/agents/state.py`, `backend/wealthpilot/core/{goals,optimizer,backtest,compliance}.py`, `models/{risk,expense,behaviour,market,portfolio}/`, `models/metrics.json`, `backend/wealthpilot/db/models.py`, all Alembic migrations, `config/compliance_rules.yaml`, all raw datasets.

## 19. Database changes

**None.** The graph only reads (via the Phase 10 nodes it calls) — `customers`, `financial_goals`, `market_data`. No new table, no schema change, no write anywhere in `agents/graph.py`.

## 20. Manual verification

- [x] Authoritative documents inspected.
- [x] Phase 10 `AgentState` reused unchanged; Phase 10 nodes reused unmodified (one disclosed rename, no behavior change).
- [x] `StateGraph` implemented, compiles successfully.
- [x] Node ordering verified against real data (customer → risk → financial health → goal → market → portfolio-or-savings-first → compliance).
- [x] Conditional routing verified — 23 dedicated tests across all 4 decision points.
- [x] Information Request branch verified against real low-confidence data.
- [x] Re-profile branch verified (one-time, no cycle).
- [x] Savings-first branch verified — skips optimization, reuses Phase 7 exactly.
- [x] Portfolio branch verified — real Phase 8 MVO output flows through correctly.
- [x] Compliance branch verified — PASS/WARN/REJECT all tested.
- [x] REJECT terminates the graph; cannot reach a downstream explanation step (the critical test, both hand-built and real-full-run variants).
- [x] Missing data handled safely (fail-closed, never a fabricated PASS).
- [x] Processing failures handled safely (found and fixed a real gap in the original implementation).
- [x] No hidden reasoning, no LLM, no AutoGen, no Gemini, no Recommendation Engine, no FastAPI, no React anywhere in this phase.
- [x] No new financial methodology invented — every number traces to an already-approved Phase 4-9 constant/function.
- [x] No Kaggle/FAR-Trans synthetic linkage.
- [x] Provenance preserved end-to-end.
- [x] Previous artifacts preserved; database integrity verified; raw datasets unchanged (all checked via direct file/mtime inspection).
- [x] Full test suite passes (449/449); all previous Phase 0-10 tests still pass.
- [x] Phase 12 not started.

## 21. Known limitations

1. **`financial_goals` still has zero real rows** (Phase 1's table remains user-entered-only, per its own docstring — unchanged since Phase 10) — end-to-end runs against real customers correctly produce an empty `goal_results` list rather than an error, but the Goal Analyst branch's richer behavior (TVM/Monte Carlo/feasibility) is only exercised against hand-constructed goals in tests, not a real DB-backed one.
2. **No real customer currently has both risk confidence ≥ 0.50 AND known emergency-fund sufficiency** (FAR-Trans has no expense data at all), so the full `portfolio_manager → compliance → approved (PASS)` path is verified with real Phase 8 MVO output layered onto a hand-set `emergency_fund.sufficient=True`, not a fully organic real-data run reaching PASS end-to-end. This is an inherent FAR-Trans data-coverage limit, not a gap in the graph itself — the same limitation Phase 10's own report already disclosed.
3. **`block_reason` is built from each triggered rule's static YAML `message`, not the more specific dynamic `reason`** (e.g. "Portfolio weights do not sum to 1." rather than "required data unavailable: portfolio weights were not provided" when weights are genuinely absent, not merely miscalculated) — a Phase 9/10-era behavior, observed more clearly now through real end-to-end runs. Left unchanged rather than edited here, per this phase's explicit "do not rewrite the underlying Phase 4-10 components" boundary; noted for a future phase to consider.

## 22. Explicit Phase 12 boundary

**No AutoGen anywhere.** No Portfolio Manager/Risk Analyst/Compliance Analyst AutoGen personas, no debate, no voting, no consensus logic exists in this codebase. The Phase 10 nodes this graph orchestrates are deterministic wrappers, never AutoGen agents. The graph's PASS/WARN path terminates at its own `approved` node — the natural, unmodified insertion point Phase 12 will extend from; no placeholder debate node was created merely to connect the graph.

## 23. Next phase

**Phase 12 — AutoGen Strategy Debate.**

**Do not begin Phase 12.** Awaiting explicit approval of this report.
