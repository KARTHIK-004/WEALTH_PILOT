"""Phase 14 — deterministic recommendation engine (four-layer hybrid).

Pure, DB-free, LLM-free (same design as `core/compliance.py`,
`core/goals.py`, `core/optimizer.py`): `build_recommendation` takes a
plain `RecommendationInput` built from already-computed Phase 4/6/7/8/9
outputs — it never recomputes a risk category, a goal-feasibility label, a
market regime, or a portfolio weight itself, and it never touches AutoGen
or Gemini output. No FastAPI, LangGraph, AutoGen, or Gemini code exists
here or is imported here (`agents/recommendation.py` is the orchestration
layer that gathers `AgentState` into a `RecommendationInput`).

**The exact decision contract, approved by the user 2026-09-14** —
superseding the "STOP AND ASK" gate `docs/BUILD_PLAN.md` itself flagged
for this phase (neither `PROJECT_PLAN.md` nor `MASTER_PROMPT.md` nor
`BUILD_PLAN.md` specifies a numeric combination rule; this project
deliberately never invents one — CLAUDE.md: "if the spec is silent...
ask; never invent financial logic"):

    Layer 1 — Compliance gate
        Compliance REJECT -> "blocked_rejected". No recommendation row.
        No lower layer can override REJECT.

    Layer 2 — Emergency fund / savings-first
        Emergency fund insufficient OR unavailable -> "savings_first".
        Skips normal investment recommendation entirely. Reuses the
        approved Phase 7/11 savings-first result; never recomputed here.

    Layer 3 — Risk-conditioned BASE strategy (`RISK_BASE_STRATEGY`)
        Conservative -> HRP, Income -> HRP, Balanced -> 1/N ("equal_weight"
        in this codebase's naming — see `PortfolioResult.strategy` /
        `portfolio_manager_node`), Aggressive -> MVO. Selects AMONG
        already-computed Phase 8 strategies; never calculates new weights.

    Layer 4 — Goal + market TACTICAL PREFERENCES (`GOAL_STRATEGY_PREFERENCE`,
        `MARKET_STRATEGY_PREFERENCE`) — preferences only, recorded in the
        structured rationale. They can never override the Layer 3 base
        strategy (approved precedence: Compliance > Savings-first > Risk
        suitability > Goal preference > Market preference). Consequently
        the FINAL selected strategy is always exactly
        `RISK_BASE_STRATEGY[risk_category]` — Layer 4 only ever changes
        whether the rationale records "aligned" or "risk suitability
        overrides a conflicting preference," never the strategy itself
        (worked example the user gave: Conservative + Not Feasible +
        Trending -> risk base HRP, goal preference MVO, market preference
        MVO -> final strategy HRP. "Do NOT increase risk merely because a
        goal is Not Feasible.").

    Tie-breaker: the risk-conditioned base strategy always wins — this is
    already total (every risk category maps to exactly one strategy), so
    no tie can actually arise; no random selection, no LLM voting, no
    weighted scoring, no arbitrary percentage weights are used anywhere in
    this module.

**AutoGen/Gemini have zero input into this module** (section 12/13/27 of
the Phase 14 prompt; `RecommendationInput` has no field of any kind for a
debate verdict or generated prose — structural, not just documented,
exactly the same "no schema slot for it to occupy" safety pattern
`agents/debate.py`'s `DebateArgument` and `agents/explanation.py`'s
`ExplanationOutput` already use for numeric claims).

**Status vocabulary** (approved by the user): `approved`, `savings_first`,
`blocked_rejected`, `failed`. `failed` covers every case where the
recommendation genuinely cannot be safely determined (e.g. risk category
unavailable, or no already-computed portfolio candidate exists for the
selected strategy) — never guessed, never defaulted to a false PASS
(section 19/40).

**No invented confidence score** (section 20): `Recommendation` carries no
`confidence` field at all — the four-layer rule the user approved does not
define one, and CLAUDE.md/this phase's own instructions forbid a made-up
percentage. The existing `recommendations.confidence` DB column (already
nullable, added at Phase 0/1) is left `NULL` when persisting (see
`agents/recommendation.py::persist_recommendation`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wealthpilot.core.compliance import ComplianceResult

PHASE14_VERSION = "v1"

# Layer 3 -- the risk-conditioned BASE strategy. The final selected
# strategy is ALWAYS this value for a given risk category; Layer 4 (goal +
# market preferences) can never change it -- see module docstring.
RISK_BASE_STRATEGY: dict[str, str] = {
    "Conservative": "hrp",
    "Income": "hrp",
    "Balanced": "equal_weight",
    "Aggressive": "mvo",
}

# Layer 4 -- preference signals only. Recorded in the rationale; never
# capable of changing `RISK_BASE_STRATEGY`'s selection.
GOAL_STRATEGY_PREFERENCE: dict[str, str] = {
    "Feasible": "equal_weight",
    "At Risk": "mvo",
    "Not Feasible": "mvo",
}
MARKET_STRATEGY_PREFERENCE: dict[str, str] = {
    "Trending": "mvo",
    "Range-bound": "equal_weight",
    "Volatile": "hrp",
}

STRATEGY_LABELS: dict[str, str] = {"mvo": "MVO", "hrp": "HRP", "equal_weight": "1/N"}

RECOMMENDATION_STATUSES = ("approved", "savings_first", "blocked_rejected", "failed")


# ---------------------------------------------------------------------------
# Input (bounded — mirrors `core.compliance.ComplianceProposal`'s pattern)
# ---------------------------------------------------------------------------


class PortfolioCandidate(BaseModel):
    """The already-computed Phase 8 result for exactly ONE strategy —
    supplied by the caller (`agents/recommendation.py`). This module never
    computes, recomputes, or modifies a weight; it only reads this."""

    model_config = ConfigDict(protected_namespaces=())

    strategy: Literal["mvo", "hrp", "equal_weight"]
    weights: dict[str, float]
    asset_universe: list[str] = Field(default_factory=list)
    expected_return: float | None = None
    expected_volatility: float | None = None
    sharpe_ratio: float | None = None
    config_version: str | None = None
    data_source: str | None = None


class RecommendationInput(BaseModel):
    """Everything the engine needs, gathered from already-computed Phase
    4/6/7/8/9 outputs. No AutoGen/Gemini field exists here — structurally,
    not just by convention (section 12/13/27/39)."""

    compliance: ComplianceResult

    # Layer 2. `None` (unavailable) is treated identically to `False`
    # (insufficient) — matches `agents/graph.py::route_after_market`'s
    # already-approved Phase 11 routing exactly ("covers both False and
    # None/unavailable"); never recomputed here.
    emergency_fund_sufficient: bool | None = None
    emergency_fund_shortfall: float | None = None

    # Layer 3.
    risk_category: str | None = None
    risk_model_version: str | None = None

    # Layer 4 (preferences only — see module docstring).
    goal_feasibilities: list[str] = Field(default_factory=list)  # every available goal's own feasibility label, unaggregated
    market_regime: str | None = None  # the primary (QQQ) instrument's regime — see agents/recommendation.py
    market_model_version: str | None = None

    # Required only when Layers 1/2 do not short-circuit and Layer 3
    # resolves to a known strategy; `None` there is a genuine "failed"
    # case (section 19), never silently substituted.
    portfolio_candidate: PortfolioCandidate | None = None


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


class RecommendationRationale(BaseModel):
    """Structured, traceable reasons only — never hidden reasoning, never
    chain-of-thought, never a claim the source data doesn't support
    (section 21)."""

    risk_based_strategy: str | None = None
    goal_feasibility_used: str | None = None
    goal_preference: str | None = None
    goal_preference_aligned: bool | None = None
    market_regime_used: str | None = None
    market_preference: str | None = None
    market_preference_aligned: bool | None = None
    reasons: list[str] = Field(default_factory=list)


class RecommendationProvenance(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    phase14_version: str = PHASE14_VERSION
    risk_model_version: str | None = None
    market_model_version: str | None = None
    portfolio_config_version: str | None = None
    compliance_rules_version: str | None = None


class Recommendation(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: Literal["approved", "savings_first", "blocked_rejected", "failed"]
    selected_strategy: str | None = None  # "mvo" | "hrp" | "equal_weight"
    weights: dict[str, float] | None = None
    expected_return: float | None = None
    expected_volatility: float | None = None
    sharpe_ratio: float | None = None
    risk_category: str | None = None
    compliance_decision: str  # "PASS" | "WARN" | "REJECT"
    rationale: RecommendationRationale
    blocking_reason: str | None = None
    provenance: RecommendationProvenance = Field(default_factory=RecommendationProvenance)
    data_sources: list[str] = Field(default_factory=list)
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Layer 4 aggregation policy (a plumbing choice, not a financial-logic one
# — see docstring below)
# ---------------------------------------------------------------------------


def _aggregate_goal_feasibility(feasibilities: list[str]) -> str | None:
    """A real customer can have multiple goals with different feasibility
    labels, but the approved four-layer rule's own table only ever speaks
    of a single "goal feasibility" value. This picks the WORST (most
    conservative) label across all of a customer's goals — the same
    "most-severe-signal-dominates" convention `training/market/regime.py`
    already uses for its own multi-signal classification (Volatile is
    checked first because "high volatility... should dominate the
    label"). This choice never changes the SELECTED strategy (goal
    preference can never override the risk-based one — see module
    docstring); it only affects what the rationale text reports."""
    if "Not Feasible" in feasibilities:
        return "Not Feasible"
    if "At Risk" in feasibilities:
        return "At Risk"
    if "Feasible" in feasibilities:
        return "Feasible"
    return None


def select_strategy(risk_category: str, goal_feasibility: str | None, market_regime: str | None) -> RecommendationRationale:
    """Layers 3 + 4. Pure, categorical, zero portfolio numbers involved —
    the selected strategy is determined entirely by `risk_category`; goal
    and market signals only ever annotate the rationale (see module
    docstring for the full precedence argument and worked example)."""
    base = RISK_BASE_STRATEGY[risk_category]
    reasons = [f"Risk category '{risk_category}' selects {STRATEGY_LABELS[base]} (risk-conditioned base strategy)."]

    goal_pref = GOAL_STRATEGY_PREFERENCE.get(goal_feasibility) if goal_feasibility else None
    goal_aligned = None
    if goal_pref is not None:
        goal_aligned = goal_pref == base
        reasons.append(
            f"Goal feasibility '{goal_feasibility}' prefers {STRATEGY_LABELS[goal_pref]}, "
            + ("which matches the risk-based strategy." if goal_aligned else
               f"but risk suitability overrides it — the strategy remains {STRATEGY_LABELS[base]}.")
        )

    market_pref = MARKET_STRATEGY_PREFERENCE.get(market_regime) if market_regime else None
    market_aligned = None
    if market_pref is not None:
        market_aligned = market_pref == base
        reasons.append(
            f"Market regime '{market_regime}' prefers {STRATEGY_LABELS[market_pref]}, "
            + ("which matches the risk-based strategy." if market_aligned else
               f"but risk suitability overrides it — the strategy remains {STRATEGY_LABELS[base]}.")
        )

    return RecommendationRationale(
        risk_based_strategy=base,
        goal_feasibility_used=goal_feasibility,
        goal_preference=goal_pref,
        goal_preference_aligned=goal_aligned,
        market_regime_used=market_regime,
        market_preference=market_pref,
        market_preference_aligned=market_aligned,
        reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Orchestration (still pure — no I/O, no optimizer call, no LLM call)
# ---------------------------------------------------------------------------


def build_recommendation(recommendation_input: RecommendationInput) -> Recommendation:
    """Applies the four layers in the approved precedence order:
    Compliance > Savings-first > Risk suitability > Goal preference >
    Market preference. Every branch is deterministic given identical
    input — no randomness, no I/O, no LLM call anywhere in this function."""
    provenance = RecommendationProvenance(
        risk_model_version=recommendation_input.risk_model_version,
        market_model_version=recommendation_input.market_model_version,
        compliance_rules_version=recommendation_input.compliance.rules_version,
    )

    # Layer 1 -- Compliance gate. Checked FIRST, unconditionally. No lower
    # layer (savings-first, risk, goal, market, and -- structurally --
    # AutoGen/Gemini, which have no field here at all) can override this.
    if recommendation_input.compliance.decision == "REJECT":
        return Recommendation(
            status="blocked_rejected",
            compliance_decision="REJECT",
            rationale=RecommendationRationale(
                reasons=["compliance_reject_veto: no recommendation is produced for a REJECTed proposal"]
            ),
            blocking_reason="Compliance decision is REJECT.",
            provenance=provenance,
            data_sources=["core.compliance"],
        )

    # Layer 2 -- Emergency fund / savings-first. `is not True` covers both
    # `False` (insufficient) and `None` (unavailable) -- matches
    # `route_after_market`'s already-approved Phase 11 routing exactly.
    if recommendation_input.emergency_fund_sufficient is not True:
        return Recommendation(
            status="savings_first",
            risk_category=recommendation_input.risk_category,
            compliance_decision=recommendation_input.compliance.decision,
            rationale=RecommendationRationale(
                reasons=[
                    "savings_first_required: emergency fund insufficient or unavailable; "
                    "normal investment recommendation deferred (Phase 7/11 result reused, not recomputed)"
                ]
            ),
            provenance=provenance,
            data_sources=["core.goals (Phase 7 emergency-fund assessment)"],
        )

    # Layer 3/4 -- risk-conditioned base strategy + goal/market preferences.
    if recommendation_input.risk_category is None or recommendation_input.risk_category not in RISK_BASE_STRATEGY:
        return Recommendation(
            status="failed",
            compliance_decision=recommendation_input.compliance.decision,
            rationale=RecommendationRationale(
                reasons=["risk_category_unavailable: cannot select a risk-conditioned base strategy without a known risk category"]
            ),
            blocking_reason="Risk category is unavailable.",
            provenance=provenance,
        )

    goal_feasibility = _aggregate_goal_feasibility(recommendation_input.goal_feasibilities)
    rationale = select_strategy(recommendation_input.risk_category, goal_feasibility, recommendation_input.market_regime)

    candidate = recommendation_input.portfolio_candidate
    if candidate is None or candidate.strategy != rationale.risk_based_strategy:
        return Recommendation(
            status="failed",
            risk_category=recommendation_input.risk_category,
            compliance_decision=recommendation_input.compliance.decision,
            rationale=rationale,
            blocking_reason=(
                f"No already-computed portfolio result is available for the selected strategy "
                f"({rationale.risk_based_strategy})."
            ),
            provenance=provenance,
        )

    return Recommendation(
        status="approved",
        selected_strategy=candidate.strategy,
        weights=candidate.weights,
        expected_return=candidate.expected_return,
        expected_volatility=candidate.expected_volatility,
        sharpe_ratio=candidate.sharpe_ratio,
        risk_category=recommendation_input.risk_category,
        compliance_decision=recommendation_input.compliance.decision,
        rationale=rationale,
        provenance=RecommendationProvenance(
            risk_model_version=recommendation_input.risk_model_version,
            market_model_version=recommendation_input.market_model_version,
            compliance_rules_version=recommendation_input.compliance.rules_version,
            portfolio_config_version=candidate.config_version,
        ),
        data_sources=[s for s in [candidate.data_source] if s],
    )
