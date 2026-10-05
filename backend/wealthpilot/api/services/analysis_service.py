"""Phase 15 — analysis orchestration service.

Calls the existing Phase 11 compiled LangGraph (`agents/graph.py`), then
— only when the graph's own terminal state is `approved` (never after a
compliance REJECT, low-confidence `pending_information` halt, or an
unexpected `failed` processing error) — the existing, unmodified Phase 14
`recommendation_engine_node` and Phase 13 `explanation_node`. This module
invents no node sequencing of its own: the ORDER (graph, then
recommendation, then explanation) mirrors the dependency chain each of
those phases already declared (Phase 14 needs a compliance result +
portfolio candidate that only exist once the graph has run to compliance;
Phase 13 needs the same). `agents/graph.py` itself is never modified or
reimplemented — this service is the "later integration point" Phase
12/13/14's own reports each said would eventually call them (section 27:
"Phase 14 is currently standalone... FastAPI calls Phase 14").

**Why recommendation/explanation are skipped (not called at all, not
called-and-hidden) outside the `approved` path**: section 24's SSE
contract requires "do not emit downstream recommendation/explanation
progress after the binding REJECT... do not fabricate completion events
for nodes that did not execute" — the plainest way to satisfy "did not
execute" for both the SSE stream AND the synchronous JSON response
(section 10: REJECT must not produce a recommendation at all) is to
genuinely not invoke them, not merely omit their event/field afterward.

**Streaming design**: `PipelineRun.events()` is a generator that both
`api/routers/analysis.py` (POST /api/analysis, draining it fully then
reading `.state`/`.recommendation_result`/`.explanation_result`) and
`api/sse.py` (GET /api/analysis/stream, forwarding each yielded event as
an SSE frame as it arrives) consume — the SAME execution path backs both
endpoints, so there is exactly one place sequencing/timing nodes, not two
independently-written orchestrations that could drift apart.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator, Literal

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from wealthpilot.agents.graph import (
    RISK_CONFIDENCE_THRESHOLD,
    GraphDependencies,
    build_analysis_graph,
)
from wealthpilot.agents.recommendation import recommendation_engine_node
from wealthpilot.agents.explanation import explanation_node
from wealthpilot.agents.state import AgentState
from wealthpilot.api.errors import CustomerNotFoundError
from wealthpilot.api.schemas import AnalysisResult
from wealthpilot.db.models import AgentLog, AnalysisRun, Customer, FinancialGoal, FinancialInputs, RiskAssessment

OverallStatus = Literal["approved", "rejected", "pending_information", "failed"]

# BUILD_PLAN.md section 21's approved safe-progress vocabulary.
NODE_ANALYSIS_STARTED = "analysis_started"
NODE_RECOMMENDATION = "recommendation"
NODE_EXPLANATION = "explanation"
NODE_ANALYSIS_COMPLETED = "analysis_completed"

# Part of the analysis cache key (`compute_profile_hash`). The profile hash
# covers a customer's INPUTS, but not how the pipeline turns inputs into
# results -- so a fix to that computation would otherwise leave every
# previously cached result serving the old, wrong answer indefinitely.
# Bump this whenever a change alters what the pipeline COMPUTES for
# unchanged inputs. History: "1" = original (through Phase 28);
# "2" = Phase 29 (goal Monte Carlo returns aligned to the contribution
# period frequency -- earlier cached goal feasibility was an artifact).
ANALYSIS_PIPELINE_VERSION = "2"


@dataclass
class NodeEvent:
    """One safe, public progress event -- node name, status, duration,
    a concise human-readable summary, and provenance only. NEVER a
    reasoning trace, a prompt, or an AutoGen/Gemini transcript (section
    23) -- every `summary` below is a short templated sentence built from
    already-computed structured fields, not free text."""

    node: str
    status: str  # "started" | "completed" | "failed"
    duration_ms: int | None = None
    summary: str | None = None
    model_version: str | None = None


def compute_profile_hash(
    customer: Customer,
    goals: list[FinancialGoal],
    portfolio_strategy: str | None = None,
    financial_inputs: FinancialInputs | None = None,
) -> str:
    """A stable hash of the customer/goal INPUT fields the analysis
    pipeline actually reads, plus any explicit `portfolio_strategy`
    override -- not a financial calculation, a cache key. No exact
    algorithm is specified anywhere in the authoritative docs beyond
    "cache graph results server-side on a profile hash" (CLAUDE.md), so
    plain SHA-256 over a canonical JSON payload was chosen as the
    simplest reasonable implementation, not a formula that could be
    "wrong" in a financial sense. The override is included because it can
    change what the graph's OWN compliance check evaluates (e.g. forcing
    a non-risk-appropriate strategy through `portfolio_manager_node` to
    see whether it still passes compliance -- BUILD_PLAN.md section 12's
    "optional overrides" / the scenario-simulator use case) -- omitting
    it from the hash would make a second call with a DIFFERENT override
    silently return the first call's cached, now-stale result. `financial_inputs`
    (Phase 28) is included for the identical reason: it is a real pipeline
    input as of this phase (see `_build_graph_dependencies`), so editing it
    via `PUT /api/profiles/{id}/financial-inputs` must invalidate any
    previously cached analysis result rather than silently keep serving a
    stale one computed before the edit."""
    payload = {
        "pipeline_version": ANALYSIS_PIPELINE_VERSION,
        "customer_id": customer.id,
        "age": customer.age,
        "income": float(customer.income) if customer.income is not None else None,
        "employment_status": customer.employment_status,
        "customer_type": customer.customer_type,
        "investment_capacity": customer.investment_capacity,
        "risk_inputs": customer.risk_inputs,
        "portfolio_strategy_override": portfolio_strategy,
        "financial_inputs": (
            {
                "monthly_essential_expenses": float(financial_inputs.monthly_essential_expenses)
                if financial_inputs.monthly_essential_expenses is not None else None,
                "current_liquid_assets": float(financial_inputs.current_liquid_assets)
                if financial_inputs.current_liquid_assets is not None else None,
                "contribution_amount": float(financial_inputs.contribution_amount)
                if financial_inputs.contribution_amount is not None else None,
                "annual_return_rate": float(financial_inputs.annual_return_rate)
                if financial_inputs.annual_return_rate is not None else None,
                "annual_inflation_rate": float(financial_inputs.annual_inflation_rate)
                if financial_inputs.annual_inflation_rate is not None else None,
                "contribution_periods_per_year": financial_inputs.contribution_periods_per_year,
            }
            if financial_inputs is not None else None
        ),
        "goals": sorted(
            [
                {
                    "id": g.id,
                    "goal_type": g.goal_type,
                    "target_amount": float(g.target_amount),
                    "target_date": g.target_date.isoformat(),
                    "current_savings": float(g.current_savings),
                    "priority": g.priority,
                }
                for g in goals
            ],
            key=lambda g: g["id"],
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _overall_status(state: AgentState) -> OverallStatus:
    """Derives the run's terminal status from the SAME conditions
    `agents/graph.py`'s own routing functions already check -- reusing
    `RISK_CONFIDENCE_THRESHOLD` directly rather than re-deriving a
    threshold, and `state.blocked` (which `apply_delta` itself already
    derives from the compliance decision) rather than re-reading
    `compliance_result.decision` a second, independent way."""
    if any(e.error_type == "processing_failure" for e in state.errors):
        return "failed"
    ra = state.risk_assessment
    if ra is None or ra.confidence is None or ra.confidence < RISK_CONFIDENCE_THRESHOLD:
        return "pending_information"
    if state.blocked:
        return "rejected"
    return "approved"


def _node_summary(node: str, state: AgentState) -> str:
    """A short, safe, human-readable summary per node -- built only from
    already-computed structured fields already present on `state`, never
    free text, never a reasoning trace."""
    if node == "customer_analyzer":
        return "Customer profile loaded." if state.customer_profile else "Customer profile could not be loaded."
    if node == "risk_analyst":
        ra = state.risk_assessment
        if ra and ra.risk_category:
            return f"Risk category: {ra.risk_category} (confidence {ra.confidence:.2f})." if ra.confidence is not None else f"Risk category: {ra.risk_category}."
        return "Risk classification unavailable."
    if node == "information_request":
        return "Risk confidence below threshold -- more information requested."
    if node == "financial_health_analyst":
        fh = state.financial_health
        if fh and fh.behaviour_drift_flag is not None:
            return f"Behaviour drift flagged: {fh.behaviour_drift_flag}."
        return "Financial health analysis unavailable."
    if node == "reprofile":
        return "Risk re-profiled after significant behaviour drift."
    if node == "goal_analyst":
        n = len(state.goal_results or [])
        return f"{n} goal(s) evaluated."
    if node == "market_analyst":
        ma = state.market_analysis
        n = len(ma.instruments) if ma else 0
        return f"Market regime read for {n} instrument(s)."
    if node == "portfolio_manager":
        pr = state.portfolio_result
        return f"Portfolio strategy: {pr.strategy}." if pr and pr.strategy else "Portfolio optimization unavailable."
    if node == "savings_first":
        # Phase 29: state-accurate. Previously this always said
        # "insufficient", including when the emergency fund's sufficiency
        # was genuinely UNKNOWN (no financial inputs supplied) -- an
        # unsupported claim shown live on the Agent Activity page.
        ef = state.emergency_fund
        if ef is not None and ef.sufficient is False:
            return "Emergency fund insufficient -- savings-first recommendation, optimization skipped."
        return "Emergency fund sufficiency could not be confirmed -- savings-first recommendation, optimization skipped."
    if node == "compliance_analyst":
        cr = state.compliance_result
        return f"Compliance decision: {cr.decision}." if cr else "Compliance evaluation unavailable."
    if node in ("approved", "rejected", "pending_information", "failed"):
        return f"Analysis terminated: {node}."
    return node


def _node_model_version(node: str, state: AgentState) -> str | None:
    if node == "risk_analyst" and state.risk_assessment:
        return state.risk_assessment.model_version
    if node == "financial_health_analyst" and state.financial_health:
        return state.financial_health.model_version
    if node == "market_analyst" and state.market_analysis:
        return state.market_analysis.model_version
    if node == "portfolio_manager" and state.portfolio_result:
        return state.portfolio_result.config_version
    if node == "compliance_analyst" and state.compliance_result:
        return state.compliance_result.rules_version
    return None


def _compound_to_period_returns(daily_returns: np.ndarray, periods_per_year: int) -> np.ndarray | None:
    """Phase 29 fix — aligns a DAILY return series to the goal engine's
    period frequency. `core/goals.py::run_goal_monte_carlo` draws one
    return per contribution PERIOD (`n_periods` draws, each applied as
    `balance*(1+r) + contribution`), so its `historical_returns` must be
    per-period returns at the same `contribution_periods_per_year` as
    `GoalAssumptions`. Phase 28 passed the raw DAILY series straight in;
    with the default 12 periods/year that applied a ~0.04% daily return
    once per MONTH, so growth was understated ~20x and every goal
    collapsed to a 0.0% success probability ("Not Feasible") even where
    the deterministic TVM showed the plan ahead of the required
    contribution (verified: a 400k retirement goal, contribution gap
    -112.60, gave 0.0% as supplied vs 94.1% once compounded to monthly
    periods; see `reports/phase29_final_integration_report.md`).

    Definitional aggregation only, no new formula and no new constant:
    consecutive, non-overlapping blocks of `k = round(TRADING_DAYS_PER_YEAR
    / periods_per_year)` trading days (`core.optimizer.TRADING_DAYS_PER_YEAR`,
    the same unit-conversion constant Phase 8 annualizes with) are
    compounded, `prod(1 + r) - 1`. The oldest remainder that does not fill
    a block is dropped so the most recent history is always fully used.
    Returns `None` (goal feasibility then honestly stays unavailable)
    when the series is too short to form even one period."""
    from wealthpilot.core.optimizer import TRADING_DAYS_PER_YEAR

    k = max(1, round(TRADING_DAYS_PER_YEAR / periods_per_year))
    n_blocks = len(daily_returns) // k
    if n_blocks == 0:
        return None
    usable = np.asarray(daily_returns, dtype=float)[len(daily_returns) - n_blocks * k :]
    return np.prod(1.0 + usable.reshape(n_blocks, k), axis=1) - 1.0


def _historical_returns_for_goal_analysis(session: Session, periods_per_year: int) -> np.ndarray | None:
    """Phase 28 — sources Monte Carlo's `historical_returns` input from the
    SAME real, already-approved `market_data` table Phase 8's portfolio
    optimizer already reads (`agents/nodes.py::load_portfolio_returns`),
    never a new data source. A single period-return series is needed (the
    goal engine bootstraps from one distribution, not per-asset), and no
    customer-specific portfolio strategy exists yet at this point in the
    graph (`goal_analyst` runs before `portfolio_manager` -- see
    `agents/graph.py`'s `TOPOLOGY`), so there is no "this customer's own
    portfolio" series to use. The equal-weighted blend of the approved
    `ASSET_UNIVERSE` was chosen as the least-arbitrary defensible choice:
    it reuses `core.optimizer.equal_weight_portfolio` (an already-approved
    Phase 8 strategy, not a new one) applied to the exact same return
    matrix `portfolio_manager_node` itself reads -- a mechanical blend of
    already-approved building blocks, not a new financial formula. Phase
    29: the blended DAILY series is then compounded to
    `periods_per_year`-frequency period returns
    (`_compound_to_period_returns`) -- Phase 28 omitted this step, which
    was a frequency-mismatch defect. Returns `None` (never a fabricated
    array) when `market_data` is empty, exactly like
    `portfolio_manager_node`'s own graceful handling of the same
    condition."""
    from wealthpilot.agents.nodes import load_portfolio_returns
    from wealthpilot.core.optimizer import equal_weight_portfolio

    try:
        returns = load_portfolio_returns(session)
    except RuntimeError:
        return None
    weights = equal_weight_portfolio(list(returns.columns))
    return _compound_to_period_returns(returns.dot(weights).to_numpy(), periods_per_year)


def _build_goal_assumptions(financial_inputs: FinancialInputs | None):
    """Constructs `core.goals.GoalAssumptions` ONLY when every one of its
    own required fields (`contribution_amount`, `annual_return_rate`,
    `annual_inflation_rate` -- see that model's own docstring: "have NO
    default anywhere in Phase 7 by design") is actually known -- never a
    partially-filled or defaulted assumption. `contribution_periods_per_year`
    is the one field `GoalAssumptions` itself already defaults (to 12,
    monthly) when not supplied, so this only overrides that default when
    the customer's own stored value is present."""
    from wealthpilot.core.goals import GoalAssumptions

    if financial_inputs is None:
        return None
    if (
        financial_inputs.contribution_amount is None
        or financial_inputs.annual_return_rate is None
        or financial_inputs.annual_inflation_rate is None
    ):
        return None
    kwargs = dict(
        contribution_amount=float(financial_inputs.contribution_amount),
        annual_return_rate=float(financial_inputs.annual_return_rate),
        annual_inflation_rate=float(financial_inputs.annual_inflation_rate),
    )
    if financial_inputs.contribution_periods_per_year is not None:
        kwargs["contribution_periods_per_year"] = financial_inputs.contribution_periods_per_year
    return GoalAssumptions(**kwargs)


def _build_graph_dependencies(session: Session, customer_id: int, portfolio_strategy: str | None) -> GraphDependencies:
    """The Phase 28 fix: constructs `GraphDependencies` with every
    legitimately-available input, instead of only `session`/
    `portfolio_strategy` (the gap `reports/live_analysis_flow_fix_report.md`
    §2 documented). Every value here comes from either the customer's own
    `financial_inputs` row (Phase 28's new, explicit data contract --
    `None` fields stay `None`, never defaulted) or the existing,
    unmodified `market_data` table -- never invented, never a second
    calculation of anything `core/goals.py` already owns."""
    financial_inputs = session.scalar(select(FinancialInputs).where(FinancialInputs.customer_id == customer_id))
    goal_assumptions = _build_goal_assumptions(financial_inputs)
    return GraphDependencies(
        session=session,
        portfolio_strategy=portfolio_strategy or "mvo",
        goal_assumptions=goal_assumptions,
        # Only consumed by `goal_analyst_node` when assumptions exist, and it
        # must be at the SAME per-period frequency as those assumptions
        # (Phase 29 fix -- see `_compound_to_period_returns`).
        historical_returns=(
            _historical_returns_for_goal_analysis(session, goal_assumptions.contribution_periods_per_year)
            if goal_assumptions is not None
            else None
        ),
        monthly_essential_expenses=(
            float(financial_inputs.monthly_essential_expenses)
            if financial_inputs is not None and financial_inputs.monthly_essential_expenses is not None
            else None
        ),
        current_liquid_assets=(
            float(financial_inputs.current_liquid_assets)
            if financial_inputs is not None and financial_inputs.current_liquid_assets is not None
            else None
        ),
    )


@dataclass
class PipelineRun:
    session: Session
    customer_id: int
    portfolio_strategy: str | None = None

    state: AgentState | None = field(default=None, init=False)
    overall_status: OverallStatus | None = field(default=None, init=False)
    recommendation_result: dict | None = field(default=None, init=False)
    explanation_result: dict | None = field(default=None, init=False)

    def events(self) -> Iterator[NodeEvent]:
        yield NodeEvent(node=NODE_ANALYSIS_STARTED, status="started")

        deps = _build_graph_dependencies(self.session, self.customer_id, self.portfolio_strategy)
        compiled = build_analysis_graph()
        state = AgentState(customer_id=self.customer_id)

        t_prev = time.monotonic()
        for step in compiled.stream(state, config={"configurable": deps.as_configurable()}, stream_mode="updates"):
            t_now = time.monotonic()
            duration_ms = int((t_now - t_prev) * 1000)
            t_prev = t_now
            for node_name, state_dict in step.items():
                state = AgentState.model_validate(state_dict)
                yield NodeEvent(
                    node=node_name,
                    status="completed",
                    duration_ms=duration_ms,
                    summary=_node_summary(node_name, state),
                    model_version=_node_model_version(node_name, state),
                )

        self.state = state
        self.overall_status = _overall_status(state)

        if self.overall_status == "approved":
            t0 = time.monotonic()
            rec_delta = recommendation_engine_node(state, self.session)
            duration_ms = int((time.monotonic() - t0) * 1000)
            self.recommendation_result = rec_delta["recommendation_result"]
            rec = self.recommendation_result
            yield NodeEvent(
                node=NODE_RECOMMENDATION,
                status="completed",
                duration_ms=duration_ms,
                summary=f"Recommendation status: {rec['status']}"
                + (f" ({rec['selected_strategy']})." if rec.get("selected_strategy") else "."),
                model_version=rec.get("provenance", {}).get("phase14_version"),
            )

            t0 = time.monotonic()
            expl_delta = explanation_node(state)
            duration_ms = int((time.monotonic() - t0) * 1000)
            self.explanation_result = expl_delta["explanation_result"]
            expl = self.explanation_result
            yield NodeEvent(
                node=NODE_EXPLANATION,
                status="completed",
                duration_ms=duration_ms,
                summary=f"Explanation status: {expl['status']}.",
                model_version=None,
            )

        yield NodeEvent(node=NODE_ANALYSIS_COMPLETED, status=self.overall_status)


def _persist_run_artifacts(session: Session, customer_id: int, events: list[NodeEvent]) -> None:
    """Writes `agent_logs` (one row per safe progress event, matching
    BUILD_PLAN.md section 12's "DB interaction" column for POST
    /api/analysis) -- never writes hidden reasoning, since `NodeEvent`
    itself never carries any."""
    for event in events:
        session.add(
            AgentLog(
                customer_id=customer_id,
                agent_name=event.node,
                action="node_execution",
                status=event.status,
                result=event.summary,
                duration_ms=event.duration_ms,
                model_version=event.model_version,
            )
        )
    session.flush()


def _persist_risk_assessment(session: Session, customer_id: int, state: AgentState) -> None:
    """Writes one `risk_assessments` row when representable. Phase 4 never
    produces an ordinal `risk_score` (already documented in Phase 10's own
    `RiskAssessmentResult.risk_score` docstring: "not computed by Phase 4
    -- no ordinal score was ever defined there"), but the existing
    `risk_assessments.risk_score` column is `NOT NULL` with no default --
    writing a fabricated placeholder value would violate this project's
    own "never invent a number" rule, so this row is simply skipped
    (never written) whenever `risk_score` is unavailable, exactly the same
    "skip persistence rather than fabricate" pattern Phase 14's own
    `persist_recommendation` already established for an unrepresentable
    `risk_category`."""
    ra = state.risk_assessment
    if ra is None or ra.risk_category is None or ra.risk_score is None or ra.confidence is None:
        return
    session.add(
        RiskAssessment(
            customer_id=customer_id,
            risk_category=ra.risk_category,
            risk_score=ra.risk_score,
            confidence=ra.confidence,
            class_probabilities=ra.class_probabilities or {},
            model_version=ra.model_version,
        )
    )
    session.flush()


def get_or_run_analysis(session: Session, customer_id: int, portfolio_strategy: str | None = None) -> AnalysisRun:
    """The single entry point `POST /api/analysis` calls. Returns a cached
    `AnalysisRun` row when one already exists for the customer's current
    profile hash (BUILD_PLAN.md section 12: "returns cached result if the
    profile hash matches"); otherwise runs the full pipeline once and
    persists it."""
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={customer_id}")

    goals = list(customer.financial_goals)
    financial_inputs = session.scalar(select(FinancialInputs).where(FinancialInputs.customer_id == customer_id))
    profile_hash = compute_profile_hash(customer, goals, portfolio_strategy, financial_inputs)

    existing = session.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.customer_id == customer_id, AnalysisRun.profile_hash == profile_hash, AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc())
    )
    if existing is not None:
        return existing

    run = AnalysisRun(customer_id=customer_id, profile_hash=profile_hash, status="running")
    session.add(run)
    session.flush()

    pipeline = PipelineRun(session=session, customer_id=customer_id, portfolio_strategy=portfolio_strategy)
    events = list(pipeline.events())

    _persist_run_artifacts(session, customer_id, events)
    if pipeline.state is not None:
        _persist_risk_assessment(session, customer_id, pipeline.state)

    result = build_analysis_result(run.id, customer_id, pipeline)
    run.result = json.loads(AnalysisResult.model_validate(result).model_dump_json())
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    session.flush()
    return run


def build_analysis_result(analysis_id: int, customer_id: int, pipeline: PipelineRun) -> dict:
    """Assembles the public `AnalysisResult` shape (never internal
    `AgentState`/`Recommendation`/`ExplanationResult` objects directly --
    section 5) from whatever the pipeline actually produced. Pure
    serialization: every value here is read from an already-computed
    field, nothing is calculated."""
    state = pipeline.state
    evaluated_at = datetime.now(timezone.utc).isoformat()

    risk = None
    if state and state.risk_assessment:
        ra = state.risk_assessment
        risk = {
            "risk_category": ra.risk_category, "confidence": ra.confidence, "class_probabilities": ra.class_probabilities,
            "model_version": ra.model_version, "data_source": ra.data_source, "unavailable_reason": ra.unavailable_reason,
        }

    financial_health = None
    if state and state.financial_health:
        fh = state.financial_health
        financial_health = {
            "expense_persona": fh.expense_persona, "expense_persona_unavailable_reason": fh.expense_persona_unavailable_reason,
            "savings_rate": fh.savings_rate, "behaviour_drift_flag": fh.behaviour_drift_flag,
            "isolation_forest_anomaly": fh.isolation_forest_anomaly, "model_version": fh.model_version,
            "data_source": fh.data_source, "unavailable_reason": fh.unavailable_reason,
        }

    goals = []
    for g in (state.goal_results or []) if state else []:
        goals.append(
            {
                "goal_id": g.goal_id, "goal_type": g.goal_type, "nominal_target_amount": g.nominal_target_amount,
                "inflation_adjusted_target_amount": g.inflation_adjusted_target_amount,
                "required_periodic_contribution": g.required_periodic_contribution, "contribution_gap": g.contribution_gap,
                "already_achieved": g.already_achieved, "monte_carlo_success_probability": g.monte_carlo_success_probability,
                "feasibility": g.feasibility, "unavailable_reason": g.unavailable_reason,
            }
        )

    emergency_fund = None
    if state and state.emergency_fund:
        ef = state.emergency_fund
        emergency_fund = {
            "required_amount": ef.required_amount, "current_amount": ef.current_amount, "shortfall": ef.shortfall,
            "sufficient": ef.sufficient, "savings_first_required": ef.savings_first_required,
            "unavailable_reason": ef.unavailable_reason,
        }

    market = None
    if state and state.market_analysis:
        ma = state.market_analysis
        market = {
            "instruments": [
                {"ticker": i.ticker, "latest_regime": i.latest_regime, "date_range": i.date_range} for i in ma.instruments
            ],
            "model_version": ma.model_version, "data_source": ma.data_source, "unavailable_reason": ma.unavailable_reason,
        }

    portfolio = None
    if state and state.portfolio_result:
        pr = state.portfolio_result
        portfolio = {
            "strategy": pr.strategy, "risk_level": pr.risk_level, "weights": pr.weights, "asset_universe": pr.asset_universe,
            "expected_return": pr.expected_return, "expected_volatility": pr.expected_volatility, "sharpe_ratio": pr.sharpe_ratio,
            "config_version": pr.config_version, "data_source": pr.data_source, "unavailable_reason": pr.unavailable_reason,
        }

    compliance = None
    if state and state.compliance_result:
        cr = state.compliance_result
        compliance = {
            "decision": cr.decision, "rules_version": cr.rules_version, "evaluated_at": cr.evaluated_at,
            "rule_results": [
                {
                    "rule_id": rr.rule_id, "description": rr.description, "severity": rr.severity, "triggered": rr.triggered,
                    "passed": rr.passed, "message": rr.message, "reason": rr.reason,
                }
                for rr in cr.rule_results
            ],
        }

    explanation = None
    if pipeline.explanation_result is not None:
        er = pipeline.explanation_result
        output = er.get("output") or {}
        # `ExplanationResult.output` is a nested `ExplanationOutput` object
        # internally (agents/explanation.py) -- flattened here into the
        # public schema's top-level prose fields since that is the shape
        # the frontend pages actually consume (BUILD_PLAN.md section 13's
        # "AI Recommendation"/"Why This Recommendation" pages), not because
        # anything is recalculated: every value below is copied verbatim.
        explanation = {
            "status": er["status"],
            "summary": output.get("summary"),
            "risk_explanation": output.get("risk_explanation"),
            "financial_health_explanation": output.get("financial_health_explanation"),
            "goal_explanation": output.get("goal_explanation"),
            "portfolio_explanation": output.get("portfolio_explanation"),
            "market_explanation": output.get("market_explanation"),
            "compliance_explanation": output.get("compliance_explanation"),
            "limitations": output.get("limitations"),
            "disclaimer": output.get("disclaimer"),
            "validation_passed": er["validation_passed"],
            "failure_reason": er.get("failure_reason"),
        }

    return {
        "analysis_id": analysis_id,
        "customer_id": customer_id,
        "status": pipeline.overall_status,
        "risk": risk,
        "financial_health": financial_health,
        "goals": goals,
        "emergency_fund": emergency_fund,
        "market": market,
        "portfolio": portfolio,
        "compliance": compliance,
        "recommendation": pipeline.recommendation_result,
        "explanation": explanation,
        "evaluated_at": evaluated_at,
    }
