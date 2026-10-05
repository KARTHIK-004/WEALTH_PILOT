"""Phase 11 — LangGraph orchestration.

Connects the already-implemented Phase 10 nodes into a compiled
`StateGraph(AgentState)`. This module contains NO new financial/ML logic —
every node wrapper below calls exactly one `agents/nodes.py` function and
applies its delta via `apply_delta` (`core/compliance.py`, `core/goals.py`,
and `core/optimizer.py` are never imported here directly). No AutoGen, no
Gemini, no FastAPI — those are Phases 12/13/15.

**Dependency threading.** LangGraph node functions take `(state, config)`;
per-run dependencies a Phase 10 node needs beyond `state` itself (a DB
`Session`, `GoalAssumptions`, a Monte Carlo return series, essential-
expense/liquid-asset figures, which portfolio strategy to run) are passed
through `RunnableConfig`'s `configurable` dict (`GraphDependencies`,
converted to a plain dict by `run_analysis_graph`) — the idiomatic LangGraph
mechanism for this, not a new field bolted onto `AgentState` (section 5:
"do not duplicate AgentState").

**`apply_delta` is never bypassed** (section 5/19): every node wrapper
calls exactly `apply_delta(state, phase10_node_fn(...))` and returns the
resulting FULL state as a dict. LangGraph's own default merge behaviour
then reduces to a trivial full replace, so `apply_delta`'s own semantics
(new-object-only, field preservation, error accumulation, compliance-
derived `blocked`) are always what actually happened — never LangGraph's
generic dict-merge substituting for them.

**Processing failures never silently continue** (section 20): `_safe_call`
catches any unexpected exception from a Phase 10 node and converts it into
a structured `NodeError(error_type="processing_failure")` rather than
crashing the graph or letting execution continue as if nothing happened.
Every conditional-routing function checks for a processing failure FIRST,
before its own normal routing logic, and routes straight to the `failed`
terminal node if one is present.

**Graph topology** (BUILD_PLAN.md section 9, the deterministic subset this
phase owns — see the module-level `TOPOLOGY` string for the rendered
diagram and `reports/phase11_langgraph_report.md` for the full reasoning
behind every routing decision, including the three approved 2026-09-14):

- Risk confidence routing threshold: `RISK_CONFIDENCE_THRESHOLD = 0.50`
  (approved) — `None` confidence (feature row unavailable) is treated as
  the extreme case of low confidence, routing to Information Request the
  same way, not a separate condition.
- Re-profile is a ONE-TIME branch: `financial_health --(drift)--> reprofile
  --> goal_analyst`, never looping back to `financial_health` itself or to
  a separate `risk_analyst` graph node — resolving an internal
  inconsistency between BUILD_PLAN.md's free-hand diagram ("Re-profile ->
  Risk Analyst") and its own node table ("Re-profile" row, Next node:
  "Goal Analyst") in favour of the more precise, structured table. This
  also trivially satisfies section 40's loop-safety requirement: there is
  no cycle in this graph at all.
- Emergency-fund routing treats `sufficient is None` (unavailable) the
  same as `sufficient is False` (approved 2026-09-14) — both route to
  Savings-first, the more conservative reading of "do not recommend
  aggressive investment allocation when essential liquidity requirements
  are not satisfied" (MASTER_PROMPT.md section 14).
- **No REJECT retry loop** (approved 2026-09-14) — BUILD_PLAN.md's fuller
  diagram describes one ("capped at N retries") but names no N anywhere,
  and Portfolio Manager is fully deterministic with no mechanism for a
  retried attempt to differ from the first (no node contract lets a
  violated rule adjust inputs), so a loop would just deterministically
  reproduce the identical REJECT until an arbitrary cap. REJECT is a
  single, direct terminal edge — matching this phase's own section 9
  routing sketch and section 42 manual-verification checklist, neither of
  which mention a retry counter.
- AutoGen Strategy Debate (Phase 12) and Gemini Explanation (Phase 13) do
  not exist yet — the PASS/WARN path terminates at this graph's own
  `approved` node, the natural insertion point a later phase will extend
  from (never replaced by a placeholder explanation node here, per
  section 8's explicit prohibition).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal

import numpy as np
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from wealthpilot.agents import nodes as N
from wealthpilot.agents.state import AgentState, AgentStateDelta, NodeError, apply_delta
from wealthpilot.core.goals import GoalAssumptions

RISK_CONFIDENCE_THRESHOLD = 0.50  # approved 2026-09-14

NODE_CUSTOMER_ANALYZER = "customer_analyzer"
NODE_RISK_ANALYST = "risk_analyst"
NODE_INFORMATION_REQUEST = "information_request"
NODE_FINANCIAL_HEALTH = "financial_health_analyst"  # not "financial_health" -- collides with the AgentState field name
NODE_REPROFILE = "reprofile"
NODE_GOAL_ANALYST = "goal_analyst"
NODE_MARKET_ANALYST = "market_analyst"
NODE_PORTFOLIO_MANAGER = "portfolio_manager"
NODE_SAVINGS_FIRST = "savings_first"
NODE_COMPLIANCE_ANALYST = "compliance_analyst"
NODE_APPROVED = "approved"
NODE_BLOCKED = "rejected"  # not "blocked" -- collides with the AgentState field name
NODE_PENDING_INFORMATION = "pending_information"
NODE_FAILED = "failed"

TOPOLOGY = """
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
                                       END [rejected]                                END [approved]

Any unexpected node exception, at any point above, routes immediately to END [failed]
instead of continuing (checked at every conditional-routing point).
"""


# ---------------------------------------------------------------------------
# Per-run dependencies (threaded via RunnableConfig, never a state field)
# ---------------------------------------------------------------------------


@dataclass
class GraphDependencies:
    session: Session
    portfolio_strategy: Literal["mvo", "equal_weight", "hrp"] = "mvo"
    goal_assumptions: GoalAssumptions | None = None
    current_date: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    historical_returns: np.ndarray | None = None
    monthly_essential_expenses: float | None = None
    current_liquid_assets: float | None = None

    def as_configurable(self) -> dict:
        return {"deps": self}


def _deps(config: RunnableConfig) -> GraphDependencies:
    configurable = (config or {}).get("configurable", {}) or {}
    deps = configurable.get("deps")
    if deps is None:
        raise ValueError("GraphDependencies not found in config['configurable']['deps'] -- see run_analysis_graph")
    return deps


# ---------------------------------------------------------------------------
# Safe execution wrapper
# ---------------------------------------------------------------------------


def _safe_call(node_name: str, state: AgentState, thunk) -> AgentState:
    """Runs `thunk()` -- the FULL body of one graph node wrapper, including
    any preparatory lookups (e.g. `external_customer_id`,
    `engineer_features_for_customer`) as well as the Phase 10 node function
    call itself, not just the latter -- and ALWAYS applies the result via
    `apply_delta` (never bypassed). Any unexpected exception ANYWHERE in
    that sequence becomes a structured `processing_failure` NodeError
    instead of crashing the graph or silently continuing as if the node
    had succeeded. `thunk` takes no arguments (a closure) specifically so
    that every step a node wrapper performs is inside the safety net, not
    just its last line."""
    try:
        delta = thunk()
    except Exception as exc:  # noqa: BLE001 - deliberately broad: convert ANY unexpected node failure into a structured, auditable state instead of an uncontrolled crash or a silent pass-through
        delta = AgentStateDelta(
            new_errors=[
                NodeError(
                    node_name=node_name,
                    error_type="processing_failure",
                    message=f"{type(exc).__name__}: {exc}",
                )
            ]
        )
    return apply_delta(state, delta)


def _has_processing_failure(state: AgentState) -> bool:
    return any(e.error_type == "processing_failure" for e in state.errors)


# ---------------------------------------------------------------------------
# Graph node wrappers (state, config) -> dict
# ---------------------------------------------------------------------------


def _customer_analyzer(state: AgentState, config: RunnableConfig) -> dict:
    deps = _deps(config)
    new_state = _safe_call(NODE_CUSTOMER_ANALYZER, state, lambda: N.customer_analyzer_node(state, deps.session))
    return new_state.model_dump()


def _risk_analyst(state: AgentState, config: RunnableConfig) -> dict:
    deps = _deps(config)

    def _run():
        feature_row = None
        ext_id = N.external_customer_id(deps.session, state.customer_id)
        if ext_id is not None:
            feature_row = N.engineer_features_for_customer(ext_id)
        return N.risk_analyst_node(state, feature_row)

    new_state = _safe_call(NODE_RISK_ANALYST, state, _run)
    return new_state.model_dump()


def _information_request(state: AgentState, config: RunnableConfig) -> dict:
    new_state = _safe_call(NODE_INFORMATION_REQUEST, state, lambda: N.information_request_node(state))
    return new_state.model_dump()


def _financial_health(state: AgentState, config: RunnableConfig) -> dict:
    deps = _deps(config)

    def _run():
        ext_id = N.external_customer_id(deps.session, state.customer_id)
        return N.financial_health_node(state, ext_id)

    new_state = _safe_call(NODE_FINANCIAL_HEALTH, state, _run)
    return new_state.model_dump()


def _reprofile(state: AgentState, config: RunnableConfig) -> dict:
    deps = _deps(config)

    def _run():
        ext_id = N.external_customer_id(deps.session, state.customer_id)
        feature_row = N.engineer_features_for_customer(ext_id) if ext_id is not None else None
        return N.reprofile_node(state, feature_row)

    new_state = _safe_call(NODE_REPROFILE, state, _run)
    return new_state.model_dump()


def _goal_analyst(state: AgentState, config: RunnableConfig) -> dict:
    deps = _deps(config)
    new_state = _safe_call(
        NODE_GOAL_ANALYST,
        state,
        lambda: N.goal_analyst_node(
            state,
            assumptions=deps.goal_assumptions,
            current_date=deps.current_date,
            historical_returns=deps.historical_returns,
            monthly_essential_expenses=deps.monthly_essential_expenses,
            current_liquid_assets=deps.current_liquid_assets,
        ),
    )
    return new_state.model_dump()


def _market_analyst(state: AgentState, config: RunnableConfig) -> dict:
    new_state = _safe_call(NODE_MARKET_ANALYST, state, lambda: N.market_analyst_node(state))
    return new_state.model_dump()


def _portfolio_manager(state: AgentState, config: RunnableConfig) -> dict:
    deps = _deps(config)
    new_state = _safe_call(
        NODE_PORTFOLIO_MANAGER, state, lambda: N.portfolio_manager_node(state, deps.session, strategy=deps.portfolio_strategy)
    )
    return new_state.model_dump()


def _savings_first(state: AgentState, config: RunnableConfig) -> dict:
    new_state = _safe_call(NODE_SAVINGS_FIRST, state, lambda: N.savings_first_node(state))
    return new_state.model_dump()


def _compliance_analyst(state: AgentState, config: RunnableConfig) -> dict:
    is_savings_first = bool(state.portfolio_result and state.portfolio_result.strategy == "savings_first")
    new_state = _safe_call(
        NODE_COMPLIANCE_ANALYST, state, lambda: N.compliance_analyst_node(state, is_savings_first_recommendation=is_savings_first)
    )
    return new_state.model_dump()


def _terminal_passthrough(state: AgentState, config: RunnableConfig) -> dict:
    """Used for the `approved`/`blocked`/`pending_information`/`failed`
    terminal nodes -- makes each terminal reachable/observable by name in
    tests and any future execution trace, without altering state."""
    return state.model_dump()


# ---------------------------------------------------------------------------
# Conditional routing (structured state only -- no LLM, no randomness)
# ---------------------------------------------------------------------------


def route_after_risk(state: AgentState) -> str:
    if _has_processing_failure(state):
        return NODE_FAILED
    ra = state.risk_assessment
    if ra is None or ra.confidence is None or ra.confidence < RISK_CONFIDENCE_THRESHOLD:
        return NODE_INFORMATION_REQUEST
    return NODE_FINANCIAL_HEALTH


def route_after_financial_health(state: AgentState) -> str:
    if _has_processing_failure(state):
        return NODE_FAILED
    fh = state.financial_health
    if fh is not None and fh.behaviour_drift_flag is True:
        return NODE_REPROFILE
    return NODE_GOAL_ANALYST


def route_after_market(state: AgentState) -> str:
    if _has_processing_failure(state):
        return NODE_FAILED
    ef = state.emergency_fund
    if ef is not None and ef.sufficient is True:
        return NODE_PORTFOLIO_MANAGER
    return NODE_SAVINGS_FIRST  # covers both False and None/unavailable (approved 2026-09-14)


def route_after_compliance(state: AgentState) -> str:
    if _has_processing_failure(state):
        return NODE_FAILED
    cr = state.compliance_result
    if cr is not None and cr.decision == "REJECT":
        return NODE_BLOCKED
    return NODE_APPROVED


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_analysis_graph() -> CompiledStateGraph:
    """The project's canonical graph construction function. No
    database-backed checkpointer is attached (section 22): nothing in the
    authoritative documents requires cross-process persistence for Phase
    11, and `compile()`'s default in-memory execution is the appropriately
    scoped choice this section explicitly favours over adding
    infrastructure "merely because LangGraph supports it"."""
    graph = StateGraph(AgentState)

    graph.add_node(NODE_CUSTOMER_ANALYZER, _customer_analyzer)
    graph.add_node(NODE_RISK_ANALYST, _risk_analyst)
    graph.add_node(NODE_INFORMATION_REQUEST, _information_request)
    graph.add_node(NODE_FINANCIAL_HEALTH, _financial_health)
    graph.add_node(NODE_REPROFILE, _reprofile)
    graph.add_node(NODE_GOAL_ANALYST, _goal_analyst)
    graph.add_node(NODE_MARKET_ANALYST, _market_analyst)
    graph.add_node(NODE_PORTFOLIO_MANAGER, _portfolio_manager)
    graph.add_node(NODE_SAVINGS_FIRST, _savings_first)
    graph.add_node(NODE_COMPLIANCE_ANALYST, _compliance_analyst)
    graph.add_node(NODE_APPROVED, _terminal_passthrough)
    graph.add_node(NODE_BLOCKED, _terminal_passthrough)
    graph.add_node(NODE_PENDING_INFORMATION, _terminal_passthrough)
    graph.add_node(NODE_FAILED, _terminal_passthrough)

    graph.set_entry_point(NODE_CUSTOMER_ANALYZER)
    graph.add_edge(NODE_CUSTOMER_ANALYZER, NODE_RISK_ANALYST)

    graph.add_conditional_edges(
        NODE_RISK_ANALYST,
        route_after_risk,
        {NODE_INFORMATION_REQUEST: NODE_INFORMATION_REQUEST, NODE_FINANCIAL_HEALTH: NODE_FINANCIAL_HEALTH, NODE_FAILED: NODE_FAILED},
    )
    graph.add_edge(NODE_INFORMATION_REQUEST, NODE_PENDING_INFORMATION)
    graph.add_edge(NODE_PENDING_INFORMATION, END)

    graph.add_conditional_edges(
        NODE_FINANCIAL_HEALTH,
        route_after_financial_health,
        {NODE_REPROFILE: NODE_REPROFILE, NODE_GOAL_ANALYST: NODE_GOAL_ANALYST, NODE_FAILED: NODE_FAILED},
    )
    graph.add_edge(NODE_REPROFILE, NODE_GOAL_ANALYST)

    graph.add_edge(NODE_GOAL_ANALYST, NODE_MARKET_ANALYST)

    graph.add_conditional_edges(
        NODE_MARKET_ANALYST,
        route_after_market,
        {NODE_PORTFOLIO_MANAGER: NODE_PORTFOLIO_MANAGER, NODE_SAVINGS_FIRST: NODE_SAVINGS_FIRST, NODE_FAILED: NODE_FAILED},
    )
    graph.add_edge(NODE_PORTFOLIO_MANAGER, NODE_COMPLIANCE_ANALYST)
    graph.add_edge(NODE_SAVINGS_FIRST, NODE_COMPLIANCE_ANALYST)

    graph.add_conditional_edges(
        NODE_COMPLIANCE_ANALYST,
        route_after_compliance,
        {NODE_APPROVED: NODE_APPROVED, NODE_BLOCKED: NODE_BLOCKED, NODE_FAILED: NODE_FAILED},
    )
    graph.add_edge(NODE_APPROVED, END)
    graph.add_edge(NODE_BLOCKED, END)
    graph.add_edge(NODE_FAILED, END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Minimal execution interface (section 24) -- no FastAPI, no SSE here
# ---------------------------------------------------------------------------


def run_analysis_graph(initial_state: AgentState, deps: GraphDependencies) -> AgentState:
    """Accepts a validated `AgentState` + `GraphDependencies`, runs the
    compiled graph once, and returns the resulting structured state.
    Deterministic: identical `initial_state`/`deps` (and identical
    underlying DB/artifact data) always produce the same node sequence,
    routing decisions, and final state -- no randomness, no LLM, anywhere
    in graph construction or routing."""
    compiled = build_analysis_graph()
    result = compiled.invoke(initial_state, config={"configurable": deps.as_configurable()})
    return AgentState.model_validate(result)
