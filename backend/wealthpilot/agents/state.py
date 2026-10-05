"""Phase 10 — typed shared agent state.

`AgentState` is the single canonical Pydantic model every node reads from
and writes to (BUILD_PLAN.md section 9: "One typed `AgentState` Pydantic
model, defined before any node is written"). This module contains NO node
logic and NO LangGraph/AutoGen/Gemini code — Phase 11 will later compile a
`StateGraph` around the nodes in `agents/nodes.py`, which read/write this
state; that compilation does not happen here.

**No hidden chain-of-thought anywhere in this file.** Every field is
either a structured input, a validated numerical/categorical result, a
concise status/decision value, or provenance metadata. There is no
`reasoning`/`scratchpad`/`internal_notes`-shaped field on any model here,
and none should ever be added — CLAUDE.md's "never stream chain-of-thought"
rule applies to state as much as to the SSE stream it will eventually back.

**Provenance.** Every result that comes from a trained model or a
versioned deterministic engine carries `model_version` and `data_source`
(CLAUDE.md: "Every response carries `model_version` and `data_source`"),
reusing the exact strings each phase already established (e.g. Phase 4/5's
`"v1"`, Phase 6-9's `"v1"`) — never a new, parallel versioning scheme.

**Missing/unavailable data.** Every optional numeric/categorical result
field is `None` when genuinely unavailable, paired with a concise
`*_unavailable_reason: str | None` field explaining why — never a
fabricated value substituting for missing FAR-Trans expense/savings data
or an incorrectly-applied Kaggle-population value (CLAUDE.md rule 7 in
spirit; Phase 5/7's own "do not invent" precedent).

**Immutability.** `AgentState` is never mutated in place. Every node
returns an `AgentStateDelta` (all fields optional — "touch only what you
own"); `apply_delta()` is the ONLY sanctioned way to combine a state with a
delta, and it always returns a NEW `AgentState` via `model_copy`, never
touching the original. `errors` accumulates (delta errors are appended,
never replacing prior ones); every other field is only overwritten when
the delta actually supplies a non-`None` value for it, so a node that
didn't touch a field can never accidentally blank out a previous node's
result.

**Compliance is structurally explicit, not just a message.** `blocked` and
`block_reason` are never independently settable on a delta — `apply_delta`
derives them itself, authoritatively, from `compliance_result.decision`
whenever a delta supplies a new `compliance_result`. This is the state-side
half of Phase 9's binding-gate contract: a REJECT can't reach `blocked`
half-applied or be silently left as `False` by a node that forgot to set
it explicitly.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from wealthpilot.core.compliance import ComplianceResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _ProvenanceModel(BaseModel):
    """Base for any state model carrying a `model_version` field —
    `model_` is Pydantic's own protected attribute namespace, so this
    silences the resulting (harmless, but noisy) warning rather than
    renaming the field away from the project's established
    `model_version`/`data_source` provenance convention."""

    model_config = ConfigDict(protected_namespaces=())


# ---------------------------------------------------------------------------
# Customer profile
# ---------------------------------------------------------------------------


class GoalSummary(BaseModel):
    """Lean projection of one `financial_goals` row — not the full ORM
    object (section 5: "do not duplicate entire database objects
    unnecessarily")."""

    id: int
    goal_type: str
    target_amount: float
    current_savings: float
    target_date: date
    priority: int


class CustomerProfile(BaseModel):
    customer_id: int
    name: str
    age: int | None = None
    income: float | None = None
    employment_status: str | None = None
    customer_type: str | None = None
    investment_capacity: str | None = None
    goals: list[GoalSummary] = Field(default_factory=list)
    data_source: str
    loaded_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Risk assessment (Phase 4)
# ---------------------------------------------------------------------------


class RiskAssessmentResult(_ProvenanceModel):
    risk_category: str | None = None  # one of GENUINE_RISK_LEVELS, never Predicted_*/Not_Available
    risk_score: int | None = None  # not computed by Phase 4 (no ordinal score was ever defined there)
    confidence: float | None = None
    class_probabilities: dict[str, float] | None = None
    model_version: str
    data_source: str
    unavailable_reason: str | None = None


# ---------------------------------------------------------------------------
# Financial health (Phase 5)
# ---------------------------------------------------------------------------


class FinancialHealthResult(_ProvenanceModel):
    # Always None for a FAR-Trans customer: the expense-persona clustering
    # model was trained on the Kaggle population only, and applying it to a
    # FAR-Trans customer would be exactly the cross-population linkage
    # section 13/27 forbid.
    expense_persona: str | None = None
    expense_persona_unavailable_reason: str | None = None

    # Always None: FAR-Trans has no income/expense fields at all (Phase 5
    # finding) -- never fabricated, never backfilled from Kaggle.
    savings_rate: float | None = None
    expense_ratio: float | None = None

    behaviour_drift_flag: bool | None = None
    isolation_forest_anomaly: bool | None = None
    isolation_forest_score: float | None = None

    model_version: str | None = None
    data_source: str | None = None
    unavailable_reason: str | None = None


# ---------------------------------------------------------------------------
# Goal analysis (Phase 7)
# ---------------------------------------------------------------------------


class GoalAnalysisResult(BaseModel):
    goal_id: int
    goal_type: str
    nominal_target_amount: float
    inflation_adjusted_target_amount: float | None = None
    required_periodic_contribution: float | None = None
    contribution_gap: float | None = None
    already_achieved: bool | None = None
    monte_carlo_success_probability: float | None = None
    feasibility: str | None = None  # Feasible / At Risk / Not Feasible
    unavailable_reason: str | None = None


class EmergencyFundResult(BaseModel):
    required_amount: float | None = None
    current_amount: float | None = None
    shortfall: float | None = None
    sufficient: bool | None = None
    savings_first_required: bool | None = None
    unavailable_reason: str | None = None


# ---------------------------------------------------------------------------
# Market analysis (Phase 6)
# ---------------------------------------------------------------------------


class InstrumentRegime(BaseModel):
    ticker: str
    latest_regime: str | None = None
    date_range: list[str] | None = None


class MarketAnalysisResult(_ProvenanceModel):
    instruments: list[InstrumentRegime] = Field(default_factory=list)
    model_version: str | None = None
    data_source: str | None = None
    trained_at: str | None = None
    unavailable_reason: str | None = None


# ---------------------------------------------------------------------------
# Portfolio (Phase 8)
# ---------------------------------------------------------------------------


class PortfolioResult(_ProvenanceModel):
    strategy: str | None = None  # "mvo" | "equal_weight" | "hrp"
    risk_level: str | None = None
    weights: dict[str, float] | None = None
    asset_universe: list[str] = Field(default_factory=list)
    constraints: dict | None = None
    expected_return: float | None = None
    expected_volatility: float | None = None
    sharpe_ratio: float | None = None
    config_version: str | None = None
    data_source: str | None = None
    unavailable_reason: str | None = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NodeError(BaseModel):
    node_name: str
    error_type: str  # "validation" | "missing_data" | "processing_failure"
    message: str
    occurred_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------


class AgentState(BaseModel):
    customer_id: int
    analysis_run_id: str | None = None

    customer_profile: CustomerProfile | None = None
    risk_assessment: RiskAssessmentResult | None = None
    financial_health: FinancialHealthResult | None = None
    goal_results: list[GoalAnalysisResult] | None = None
    emergency_fund: EmergencyFundResult | None = None
    market_analysis: MarketAnalysisResult | None = None
    portfolio_result: PortfolioResult | None = None
    compliance_result: ComplianceResult | None = None

    # Derived-only (see apply_delta) -- never set directly by a node.
    blocked: bool = False
    block_reason: str | None = None

    errors: list[NodeError] = Field(default_factory=list)

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class AgentStateDelta(BaseModel):
    """What one node returns. Every field is optional -- a node only
    supplies the fields it actually computed; every other field is left
    `None` and therefore leaves the corresponding `AgentState` field
    untouched when applied (see `apply_delta`). `blocked`/`block_reason`
    are deliberately NOT fields here -- they are derived, never
    node-supplied (see the module docstring)."""

    customer_profile: CustomerProfile | None = None
    risk_assessment: RiskAssessmentResult | None = None
    financial_health: FinancialHealthResult | None = None
    goal_results: list[GoalAnalysisResult] | None = None
    emergency_fund: EmergencyFundResult | None = None
    market_analysis: MarketAnalysisResult | None = None
    portfolio_result: PortfolioResult | None = None
    compliance_result: ComplianceResult | None = None
    new_errors: list[NodeError] = Field(default_factory=list)


_DELTA_FIELDS = (
    "customer_profile",
    "risk_assessment",
    "financial_health",
    "goal_results",
    "emergency_fund",
    "market_analysis",
    "portfolio_result",
    "compliance_result",
)


def apply_delta(state: AgentState, delta: AgentStateDelta) -> AgentState:
    """The only sanctioned way to combine a state with a node's delta.
    Always returns a NEW `AgentState` (via `model_copy`) -- `state` itself
    is never mutated. Fields left `None` on the delta are left untouched on
    the result; `errors` accumulates rather than replaces.
    """
    updates: dict = {}
    for field in _DELTA_FIELDS:
        value = getattr(delta, field)
        if value is not None:
            updates[field] = value

    if delta.new_errors:
        updates["errors"] = [*state.errors, *delta.new_errors]

    if delta.compliance_result is not None:
        if delta.compliance_result.decision == "REJECT":
            violated = [
                rr.message for rr in delta.compliance_result.rule_results if rr.triggered and rr.severity == "REJECT"
            ]
            updates["blocked"] = True
            updates["block_reason"] = "; ".join(violated) if violated else "compliance REJECTed"
        else:
            updates["blocked"] = False
            updates["block_reason"] = None

    updates["updated_at"] = _now()
    return state.model_copy(update=updates)
