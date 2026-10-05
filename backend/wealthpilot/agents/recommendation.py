"""Phase 14 — Recommendation Engine orchestration / node layer.

Standalone, like Phase 12 (`agents/debate.py`) and Phase 13
(`agents/explanation.py`) — not wired into `agents/graph.py`. BUILD_PLAN.md
section 9's own topology diagram has no distinct "Recommendation" node
either (Portfolio Manager -> AutoGen -> Compliance -> Gemini Explanation ->
API response), and this phase's own instructions (section 26) only require
graph integration when the authoritative workflow "explicitly requires"
it and say to ask if the topology is ambiguous rather than redesign Phase
11 — the smallest-blast-radius choice consistent with Phase 12/13's own
precedent is to stay standalone here too and let Phase 15 (API layer) call
this module directly, exactly as it will call `run_strategy_debate` and
`run_explanation`. `recommendation_engine_node` still matches the
Phase 10-13 `(state, config) -> dict` node contract so wiring it in later
is a mechanical addition, not a redesign.

**The pure four-layer decision logic lives in `core/recommendation.py`**
(never here) — this module's only job is:

1. Read `AgentState` into the bounded `RecommendationInput`
   `core.recommendation.build_recommendation` expects.
2. Obtain a `PortfolioCandidate` for whichever strategy Layer 3's
   risk-conditioning selects, when it is not already sitting in
   `state.portfolio_result` (see `_obtain_portfolio_candidate`).
3. Persist an `approved`/`savings_first` result to the existing
   `recommendations` table, exactly as it is today — no schema change
   (see `persist_recommendation`).

**On obtaining "already-computed Phase 8 strategies" for a strategy other
than whichever one already happens to be in `state.portfolio_result`**:
`agents/nodes.py::portfolio_manager_node` defaults to `strategy="mvo"` for
every customer (Phase 10; `agents/graph.py`'s `GraphDependencies.
portfolio_strategy` also defaults to `"mvo"`) — Phase 14's risk-conditioned
selection (Conservative/Income -> HRP, Balanced -> 1/N, Aggressive -> MVO)
is new, so a Conservative customer's `state.portfolio_result` may already
hold the WRONG strategy for this phase's purposes. Rather than invent a
second, parallel way to compute portfolio weights (forbidden — section
28/29: "do not introduce new financial calculations... do not call
MVO/HRP/1/N optimization again merely to generate a recommendation"), this
module calls the exact same, unmodified `portfolio_manager_node` function
again with the correct `strategy` argument when needed — the identical
mechanism `agents/graph.py`'s own `_portfolio_manager` wrapper already
uses, with the identical unmodified `core.optimizer` formulas, bounds, and
risk bands (never a new calculation). This is "selecting among
already-computed [i.e. already-approved, unmodified] Phase 8 strategies,"
not generating a new portfolio — the specification's own escape clause
("unless the authoritative Phase 14 design explicitly requires it") is
exactly this case, since Layer 3 cannot mean anything for a
non-Aggressive customer without it.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from wealthpilot.agents import nodes as N
from wealthpilot.agents.state import AgentState
from wealthpilot.core.recommendation import (
    RISK_BASE_STRATEGY,
    PortfolioCandidate,
    Recommendation,
    RecommendationInput,
    RecommendationProvenance,
    RecommendationRationale,
    build_recommendation,
)
from wealthpilot.db.models import Recommendation as RecommendationRow

PRIMARY_REGIME_INSTRUMENT = "QQQ"  # the risk-band-defining asset (RISK_LEVEL_QQQ_BANDS) — see module docstring


def _obtain_portfolio_candidate(state: AgentState, session: Session, strategy: str) -> PortfolioCandidate | None:
    """Returns the already-computed `PortfolioResult` for `strategy`,
    reusing `state.portfolio_result` directly when it already matches, or
    calling the existing, unmodified `portfolio_manager_node` again
    otherwise (see module docstring)."""
    portfolio_result = state.portfolio_result
    if portfolio_result is None or portfolio_result.strategy != strategy or not portfolio_result.weights:
        delta = N.portfolio_manager_node(state, session, strategy=strategy)
        portfolio_result = delta.portfolio_result

    if portfolio_result is None or not portfolio_result.weights:
        return None

    return PortfolioCandidate(
        strategy=portfolio_result.strategy,
        weights=portfolio_result.weights,
        asset_universe=portfolio_result.asset_universe,
        expected_return=portfolio_result.expected_return,
        expected_volatility=portfolio_result.expected_volatility,
        sharpe_ratio=portfolio_result.sharpe_ratio,
        config_version=portfolio_result.config_version,
        data_source=portfolio_result.data_source,
    )


def _primary_market_regime(state: AgentState) -> str | None:
    if state.market_analysis is None:
        return None
    for instrument in state.market_analysis.instruments:
        if instrument.ticker == PRIMARY_REGIME_INSTRUMENT:
            return instrument.latest_regime
    return None


def build_recommendation_input(state: AgentState, session: Session) -> RecommendationInput:
    """Extracts real, already-computed values from `AgentState` — never
    raw customer text, never AutoGen/Gemini output (neither is read here
    at all; see `core/recommendation.py`'s module docstring)."""
    risk_category = state.risk_assessment.risk_category if state.risk_assessment else None
    ef_sufficient = state.emergency_fund.sufficient if state.emergency_fund else None
    goal_feasibilities = [g.feasibility for g in (state.goal_results or []) if g.feasibility]

    portfolio_candidate = None
    # Only bother obtaining a portfolio candidate when Layers 1/2 would not
    # short-circuit anyway and Layer 3 resolves to a known strategy —
    # avoids an unnecessary optimizer call for a REJECT/savings-first case.
    if (
        state.compliance_result is not None
        and state.compliance_result.decision != "REJECT"
        and ef_sufficient is True
        and risk_category in RISK_BASE_STRATEGY
    ):
        strategy = RISK_BASE_STRATEGY[risk_category]
        portfolio_candidate = _obtain_portfolio_candidate(state, session, strategy)

    return RecommendationInput(
        compliance=state.compliance_result,
        emergency_fund_sufficient=ef_sufficient,
        emergency_fund_shortfall=state.emergency_fund.shortfall if state.emergency_fund else None,
        risk_category=risk_category,
        risk_model_version=state.risk_assessment.model_version if state.risk_assessment else None,
        goal_feasibilities=goal_feasibilities,
        market_regime=_primary_market_regime(state),
        market_model_version=state.market_analysis.model_version if state.market_analysis else None,
        portfolio_candidate=portfolio_candidate,
    )


def persist_recommendation(session: Session, customer_id: int, recommendation: Recommendation) -> RecommendationRow | None:
    """Persists `approved`/`savings_first` results only — `blocked_rejected`
    and `failed` never produce a row (section 5: "REJECT... no final
    recommendation"; section 19: a recommendation that cannot safely be
    determined is never silently stored as if it were one).

    Uses the EXISTING `recommendations` table exactly as it is today — no
    migration, no new column. `confidence` is left `NULL`: the approved
    four-layer rule defines no confidence score, and this project never
    invents one (section 20). The free-text `recommendation` column holds
    a JSON serialization of the structured decision, not hand-written
    prose — inventing natural-language phrasing here would step into
    Gemini's explanation role (section 16: the two are "strictly
    separate"), so this column stays a structured, traceable record of
    exactly what `core.recommendation.build_recommendation` decided.

    Flushes (so the row is queryable/gets its `id` within the current
    transaction) but does not commit — the caller owns the transaction
    boundary, matching every other DB-writing entry point in this project.
    """
    if recommendation.status not in ("approved", "savings_first"):
        return None
    if recommendation.risk_category is None:
        # Not representable by the existing NOT-NULL risk_category column
        # (section 23: "persist if representable by the existing schema").
        return None

    row = RecommendationRow(
        customer_id=customer_id,
        recommendation=json.dumps(recommendation.model_dump(mode="json")),
        risk_category=recommendation.risk_category,
        portfolio_allocation=recommendation.weights or {},
        confidence=None,
        model_version=recommendation.provenance.phase14_version,
        data_source=", ".join(recommendation.data_sources) if recommendation.data_sources else "core.recommendation",
    )
    session.add(row)
    session.flush()
    return row


def recommendation_engine_node(state: AgentState, session: Session, config=None) -> dict:
    """Graph-compatible `(state, session, config) -> dict` wrapper —
    `session` is an explicit dependency (matching `portfolio_manager_node`'s
    own signature) rather than pulled from `config.configurable` the way
    Phase 12/13's LLM credentials are, since this module needs it for both
    obtaining a missing portfolio candidate and persistence."""
    if not isinstance(state, AgentState):
        raise TypeError("recommendation_engine_node expects a wealthpilot.agents.state.AgentState")

    if state.compliance_result is None:
        result = Recommendation(
            status="failed",
            compliance_decision="REJECT",
            rationale=RecommendationRationale(
                reasons=["invalid_recommendation_input: state has no compliance_result"]
            ),
            blocking_reason="No compliance result is available.",
            provenance=RecommendationProvenance(),
        )
        return {"recommendation_result": result.model_dump()}

    recommendation_input = build_recommendation_input(state, session)
    recommendation = build_recommendation(recommendation_input)

    if recommendation.status in ("approved", "savings_first"):
        persist_recommendation(session, state.customer_id, recommendation)

    return {"recommendation_result": recommendation.model_dump()}
