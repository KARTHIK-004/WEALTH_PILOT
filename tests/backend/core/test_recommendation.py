"""Phase 14 — pure `core.recommendation` engine tests. No DB, no LLM, no
AutoGen — every test here runs in milliseconds against plain Pydantic
objects, matching `test_compliance.py`/`test_goals.py`/`test_optimizer.py`'s
own pure-function testing style.

Covers: each individual layer, the exact approved precedence order,
boundary/tie/missing-data conditions, the two CRITICAL tests this phase's
prompt calls out by number (compliance override attempt, numerical
integrity against a fabricated AutoGen/Gemini-shaped claim), and
determinism.
"""

from __future__ import annotations

import pytest

from wealthpilot.core.compliance import ComplianceResult, RuleResult
from wealthpilot.core.recommendation import (
    GOAL_STRATEGY_PREFERENCE,
    MARKET_STRATEGY_PREFERENCE,
    RECOMMENDATION_STATUSES,
    RISK_BASE_STRATEGY,
    PortfolioCandidate,
    Recommendation,
    RecommendationInput,
    _aggregate_goal_feasibility,
    build_recommendation,
    select_strategy,
)


def _compliance(decision: str = "PASS", rules_version: str = "v1") -> ComplianceResult:
    return ComplianceResult(decision=decision, rules_version=rules_version, evaluated_at="2026-01-01T00:00:00+00:00", rule_results=[])


def _candidate(strategy: str, **overrides) -> PortfolioCandidate:
    defaults = dict(
        strategy=strategy,
        weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3},
        asset_universe=["QQQ", "AGG", "GLD"],
        expected_return=0.15,
        expected_volatility=0.18,
        sharpe_ratio=0.83,
        config_version="v1",
        data_source="market_data (PostgreSQL)",
    )
    defaults.update(overrides)
    return PortfolioCandidate(**defaults)


def _input(**overrides) -> RecommendationInput:
    defaults = dict(
        compliance=_compliance("PASS"),
        emergency_fund_sufficient=True,
        risk_category="Aggressive",
        goal_feasibilities=[],
        market_regime=None,
        portfolio_candidate=_candidate("mvo"),
    )
    defaults.update(overrides)
    return RecommendationInput(**defaults)


# ---------------------------------------------------------------------------
# Status vocabulary (approved by the user)
# ---------------------------------------------------------------------------


def test_status_vocabulary_matches_the_approved_four_values():
    assert RECOMMENDATION_STATUSES == ("approved", "savings_first", "blocked_rejected", "failed")


def test_recommendation_has_no_confidence_field():
    """Section 20: no invented confidence score anywhere in this phase."""
    assert "confidence" not in Recommendation.model_fields


# ---------------------------------------------------------------------------
# Layer 1 — Compliance gate (highest priority; CRITICAL test 37)
# ---------------------------------------------------------------------------


def test_reject_blocks_the_recommendation_regardless_of_everything_else():
    """CRITICAL (section 37): REJECT + a portfolio candidate + sufficient
    EF + a valid risk category must still produce BLOCKED, never a normal
    recommendation."""
    result = build_recommendation(_input(compliance=_compliance("REJECT")))
    assert result.status == "blocked_rejected"
    assert result.selected_strategy is None
    assert result.weights is None
    assert result.blocking_reason == "Compliance decision is REJECT."


def test_reject_wins_over_insufficient_emergency_fund_too():
    """Precedence: Compliance > Savings-first. Both conditions true at
    once must still resolve to blocked_rejected, not savings_first."""
    result = build_recommendation(_input(compliance=_compliance("REJECT"), emergency_fund_sufficient=False))
    assert result.status == "blocked_rejected"


def test_pass_and_warn_are_not_blocked():
    for decision in ("PASS", "WARN"):
        result = build_recommendation(_input(compliance=_compliance(decision)))
        assert result.status == "approved"
        assert result.compliance_decision == decision


# ---------------------------------------------------------------------------
# Layer 2 — Emergency fund / savings-first (CRITICAL test 38)
# ---------------------------------------------------------------------------


def test_insufficient_emergency_fund_produces_savings_first():
    """CRITICAL (section 38): normal investment recommendation must not
    be generated when the emergency fund is insufficient."""
    result = build_recommendation(_input(emergency_fund_sufficient=False))
    assert result.status == "savings_first"
    assert result.selected_strategy is None
    assert result.weights is None


def test_unavailable_emergency_fund_is_treated_as_insufficient():
    """Matches `agents/graph.py::route_after_market`'s already-approved
    Phase 11 routing exactly: None is NOT sufficient."""
    result = build_recommendation(_input(emergency_fund_sufficient=None))
    assert result.status == "savings_first"


def test_savings_first_never_touches_the_portfolio_candidate():
    result = build_recommendation(_input(emergency_fund_sufficient=False, portfolio_candidate=_candidate("mvo")))
    assert result.weights is None
    assert result.selected_strategy is None


# ---------------------------------------------------------------------------
# Layer 3 — risk-conditioned base strategy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "risk_category,expected_strategy",
    [("Conservative", "hrp"), ("Income", "hrp"), ("Balanced", "equal_weight"), ("Aggressive", "mvo")],
)
def test_each_risk_category_selects_its_approved_base_strategy(risk_category, expected_strategy):
    result = build_recommendation(_input(risk_category=risk_category, portfolio_candidate=_candidate(expected_strategy)))
    assert result.status == "approved"
    assert result.selected_strategy == expected_strategy
    assert result.rationale.risk_based_strategy == expected_strategy


def test_unknown_risk_category_fails_safely():
    result = build_recommendation(_input(risk_category="Speculative", portfolio_candidate=None))
    assert result.status == "failed"
    assert result.blocking_reason == "Risk category is unavailable."


def test_missing_risk_category_fails_safely():
    """Section 19: missing data must never be guessed."""
    result = build_recommendation(_input(risk_category=None, portfolio_candidate=None))
    assert result.status == "failed"
    assert result.selected_strategy is None


# ---------------------------------------------------------------------------
# Layer 4 — goal/market preferences (never override) — the worked example
# ---------------------------------------------------------------------------


def test_the_approved_worked_example_conservative_not_feasible_trending():
    """Verbatim from the approved decision contract: Conservative +
    Not Feasible + Trending -> risk base HRP, goal preference MVO, market
    preference MVO -> final strategy HRP. 'Do NOT increase risk merely
    because a goal is Not Feasible.'"""
    result = build_recommendation(
        _input(
            risk_category="Conservative",
            goal_feasibilities=["Not Feasible"],
            market_regime="Trending",
            portfolio_candidate=_candidate("hrp"),
        )
    )
    assert result.status == "approved"
    assert result.selected_strategy == "hrp"
    assert result.rationale.goal_preference == "mvo"
    assert result.rationale.goal_preference_aligned is False
    assert result.rationale.market_preference == "mvo"
    assert result.rationale.market_preference_aligned is False


def test_strongest_alignment_everything_agrees():
    """Aggressive -> MVO base; Feasible goal also prefers... 1/N, and
    Trending market prefers MVO. Pick a combination where ALL signals
    genuinely agree with the base to exercise the "aligned" path."""
    result = build_recommendation(
        _input(
            risk_category="Aggressive",
            goal_feasibilities=["At Risk"],  # At Risk -> mvo, matches Aggressive base
            market_regime="Trending",  # Trending -> mvo, matches Aggressive base
            portfolio_candidate=_candidate("mvo"),
        )
    )
    assert result.selected_strategy == "mvo"
    assert result.rationale.goal_preference_aligned is True
    assert result.rationale.market_preference_aligned is True


def test_weakest_alignment_everything_conflicts():
    """Balanced -> 1/N base; Not Feasible goal prefers MVO (conflict);
    Volatile market prefers HRP (conflict). Final strategy must still be
    the risk base."""
    result = build_recommendation(
        _input(
            risk_category="Balanced",
            goal_feasibilities=["Not Feasible"],
            market_regime="Volatile",
            portfolio_candidate=_candidate("equal_weight"),
        )
    )
    assert result.selected_strategy == "equal_weight"
    assert result.rationale.goal_preference_aligned is False
    assert result.rationale.market_preference_aligned is False


def test_mixed_signals_goal_aligned_market_conflicting():
    result = build_recommendation(
        _input(
            risk_category="Income",  # base hrp
            goal_feasibilities=[],  # no goal signal
            market_regime="Trending",  # prefers mvo -> conflicts with hrp
            portfolio_candidate=_candidate("hrp"),
        )
    )
    assert result.selected_strategy == "hrp"
    assert result.rationale.goal_preference is None
    assert result.rationale.goal_preference_aligned is None
    assert result.rationale.market_preference_aligned is False


def test_missing_goal_and_market_signals_still_resolves_via_risk_alone():
    result = build_recommendation(
        _input(risk_category="Aggressive", goal_feasibilities=[], market_regime=None, portfolio_candidate=_candidate("mvo"))
    )
    assert result.status == "approved"
    assert result.selected_strategy == "mvo"
    assert result.rationale.goal_preference is None
    assert result.rationale.market_preference is None


@pytest.mark.parametrize("feasibility,expected_pref", list(GOAL_STRATEGY_PREFERENCE.items()))
def test_select_strategy_goal_preference_table(feasibility, expected_pref):
    rationale = select_strategy("Aggressive", feasibility, None)
    assert rationale.goal_preference == expected_pref


@pytest.mark.parametrize("regime,expected_pref", list(MARKET_STRATEGY_PREFERENCE.items()))
def test_select_strategy_market_preference_table(regime, expected_pref):
    rationale = select_strategy("Aggressive", None, regime)
    assert rationale.market_preference == expected_pref


def test_goal_and_market_preferences_can_never_change_the_selected_strategy():
    """Exhaustive: for every risk category x every goal feasibility x
    every market regime, the risk-based strategy is the only thing that
    ever appears as `risk_based_strategy` (i.e. what `build_recommendation`
    actually selects)."""
    for risk_category, base in RISK_BASE_STRATEGY.items():
        for feasibility in [None, *GOAL_STRATEGY_PREFERENCE.keys()]:
            for regime in [None, *MARKET_STRATEGY_PREFERENCE.keys()]:
                rationale = select_strategy(risk_category, feasibility, regime)
                assert rationale.risk_based_strategy == base


# ---------------------------------------------------------------------------
# Goal-feasibility aggregation (a plumbing policy, not part of the
# approved financial rule itself — see core/recommendation.py docstring)
# ---------------------------------------------------------------------------


def test_goal_aggregation_picks_the_worst_case():
    assert _aggregate_goal_feasibility(["Feasible", "At Risk", "Not Feasible"]) == "Not Feasible"
    assert _aggregate_goal_feasibility(["Feasible", "At Risk"]) == "At Risk"
    assert _aggregate_goal_feasibility(["Feasible", "Feasible"]) == "Feasible"
    assert _aggregate_goal_feasibility([]) is None


# ---------------------------------------------------------------------------
# Missing / unavailable portfolio candidate
# ---------------------------------------------------------------------------


def test_missing_portfolio_candidate_fails_rather_than_guessing():
    result = build_recommendation(_input(portfolio_candidate=None))
    assert result.status == "failed"
    assert "No already-computed portfolio result" in result.blocking_reason


def test_mismatched_portfolio_candidate_strategy_fails_rather_than_using_the_wrong_one():
    """Defensive integrity check: a candidate for the WRONG strategy (e.g.
    caller bug) must never be silently substituted for the selected one."""
    result = build_recommendation(_input(risk_category="Aggressive", portfolio_candidate=_candidate("hrp")))
    assert result.status == "failed"
    assert "mvo" in result.blocking_reason


# ---------------------------------------------------------------------------
# CRITICAL numerical-integrity test (section 39)
# ---------------------------------------------------------------------------


def test_authoritative_weights_pass_through_unchanged_no_recalculation():
    weights = {"QQQ": 0.55, "AGG": 0.30, "GLD": 0.15}
    result = build_recommendation(
        _input(risk_category="Aggressive", portfolio_candidate=_candidate("mvo", weights=weights))
    )
    assert result.weights == weights  # exact, unmodified pass-through


def test_recommendation_input_has_no_autogen_or_gemini_field():
    """Structural, not just documented: there is no schema slot anywhere
    in this module for a debate verdict or generated prose to occupy."""
    for name in RecommendationInput.model_fields:
        assert "autogen" not in name.lower()
        assert "gemini" not in name.lower()
        assert "debate" not in name.lower()
        assert "explanation" not in name.lower()


def test_an_attempted_autogen_override_field_is_silently_ignored_and_has_zero_effect():
    """CRITICAL (section 39, adapted to this module's actual inputs, since
    there is no debate/explanation field to 'override' with in the first
    place): even constructing the input with an extraneous
    AutoGen/Gemini-shaped kwarg has no effect on the result -- Pydantic
    drops unrecognized fields, and `build_recommendation` never reads one
    even if it existed."""
    weights = {"QQQ": 0.55, "AGG": 0.30, "GLD": 0.15}
    tampered = RecommendationInput(
        compliance=_compliance("PASS"),
        emergency_fund_sufficient=True,
        risk_category="Aggressive",
        portfolio_candidate=_candidate("mvo", weights=weights),
        autogen_verdict="APPROVE_OVERRIDE_TO_QQQ_0.80",  # type: ignore[call-arg]
        gemini_says="safe to proceed, use QQQ 0.80",  # type: ignore[call-arg]
    )
    result = build_recommendation(tampered)
    assert result.weights == weights
    assert result.status == "approved"


# ---------------------------------------------------------------------------
# CRITICAL determinism test (section 41)
# ---------------------------------------------------------------------------


def test_identical_input_always_produces_identical_output():
    payload = _input(
        risk_category="Balanced",
        goal_feasibilities=["At Risk"],
        market_regime="Volatile",
        portfolio_candidate=_candidate("equal_weight"),
    )
    results = [build_recommendation(payload).model_dump(exclude={"evaluated_at"}) for _ in range(5)]
    assert all(r == results[0] for r in results)


# ---------------------------------------------------------------------------
# Provenance (section 22)
# ---------------------------------------------------------------------------


def test_provenance_preserves_underlying_component_versions():
    result = build_recommendation(
        _input(
            compliance=_compliance("PASS", rules_version="v3"),
            risk_category="Aggressive",
            risk_model_version="v2",
            market_model_version="v5",
            portfolio_candidate=_candidate("mvo", config_version="v9"),
        )
    )
    assert result.provenance.compliance_rules_version == "v3"
    assert result.provenance.risk_model_version == "v2"
    assert result.provenance.market_model_version == "v5"
    assert result.provenance.portfolio_config_version == "v9"
    assert result.provenance.phase14_version == "v1"


# ---------------------------------------------------------------------------
# Exhaustive decision-table test (Final Implementation Prompt, section 38):
# every risk x goal x market combination, verifying risk base always wins,
# plus REJECT / insufficient-EF / unavailable-EF terminating before normal
# strategy selection is even considered.
# ---------------------------------------------------------------------------

_RISK_CATEGORIES = ("Conservative", "Income", "Balanced", "Aggressive")
_GOAL_STATES = ("Feasible", "At Risk", "Not Feasible")
_MARKET_REGIMES = ("Trending", "Range-bound", "Volatile")


@pytest.mark.parametrize("risk_category", _RISK_CATEGORIES)
@pytest.mark.parametrize("goal_state", _GOAL_STATES)
@pytest.mark.parametrize("market_regime", _MARKET_REGIMES)
def test_exhaustive_decision_table_risk_base_always_wins(risk_category, goal_state, market_regime):
    """4 risk x 3 goal x 3 market = 36 combinations. For every one, the
    final selected strategy must equal exactly `RISK_BASE_STRATEGY[risk_category]`,
    never the goal or market preference when they differ."""
    expected = RISK_BASE_STRATEGY[risk_category]
    result = build_recommendation(
        _input(
            risk_category=risk_category,
            goal_feasibilities=[goal_state],
            market_regime=market_regime,
            portfolio_candidate=_candidate(expected),
        )
    )
    assert result.status == "approved"
    assert result.selected_strategy == expected


@pytest.mark.parametrize(
    "precondition_kwargs,expected_status",
    [
        ({"compliance": _compliance("REJECT")}, "blocked_rejected"),
        ({"emergency_fund_sufficient": False}, "savings_first"),
        ({"emergency_fund_sufficient": None}, "savings_first"),
    ],
)
def test_reject_and_emergency_fund_states_terminate_before_strategy_selection(precondition_kwargs, expected_status):
    """These three conditions must short-circuit BEFORE Layer 3/4 strategy
    selection runs at all -- even with a fully valid risk/goal/market/
    portfolio-candidate combination supplied alongside them."""
    result = build_recommendation(
        _input(
            risk_category="Aggressive",
            goal_feasibilities=["At Risk"],
            market_regime="Trending",
            portfolio_candidate=_candidate("mvo"),
            **precondition_kwargs,
        )
    )
    assert result.status == expected_status
    assert result.selected_strategy is None


# ---------------------------------------------------------------------------
# Critical example tests (Final Implementation Prompt, section 39) --
# verbatim from the prompt's own worked examples.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "risk_category,goal_state,market_regime,expected_strategy",
    [
        ("Conservative", "Not Feasible", "Trending", "hrp"),
        ("Conservative", "Feasible", "Range-bound", "hrp"),
        ("Income", "Feasible", "Range-bound", "hrp"),
        ("Balanced", "Feasible", "Range-bound", "equal_weight"),
        ("Balanced", "Not Feasible", "Trending", "equal_weight"),
        ("Aggressive", "Feasible", "Trending", "mvo"),
        ("Aggressive", "Not Feasible", "Volatile", "mvo"),
    ],
)
def test_critical_example_tests_from_the_prompt(risk_category, goal_state, market_regime, expected_strategy):
    result = build_recommendation(
        _input(
            risk_category=risk_category,
            goal_feasibilities=[goal_state],
            market_regime=market_regime,
            portfolio_candidate=_candidate(expected_strategy),
        )
    )
    assert result.status == "approved"
    assert result.selected_strategy == expected_strategy


# ---------------------------------------------------------------------------
# Safety invariants (Final Implementation Prompt, section 40) -- one test
# per numbered invariant, for direct traceability back to the prompt.
# ---------------------------------------------------------------------------


def test_invariant_1_reject_implies_no_recommendation():
    result = build_recommendation(_input(compliance=_compliance("REJECT")))
    assert result.selected_strategy is None
    assert result.weights is None


def test_invariant_2_reject_implies_no_persistable_status():
    """`agents/recommendation.py::persist_recommendation` only ever
    persists 'approved'/'savings_first' -- see the node-layer tests for the
    actual DB-level proof; here we confirm the status value itself, which
    is what that persistence gate keys off of."""
    result = build_recommendation(_input(compliance=_compliance("REJECT")))
    assert result.status == "blocked_rejected"
    assert result.status not in ("approved", "savings_first")


def test_invariant_3_insufficient_ef_implies_no_normal_investment_recommendation():
    result = build_recommendation(_input(emergency_fund_sufficient=False))
    assert result.status == "savings_first"
    assert result.selected_strategy is None


def test_invariant_4_unavailable_ef_implies_savings_first():
    result = build_recommendation(_input(emergency_fund_sufficient=None))
    assert result.status == "savings_first"


@pytest.mark.parametrize("risk_category", _RISK_CATEGORIES)
def test_invariant_5_final_strategy_is_always_one_of_the_three_approved_strategies(risk_category):
    expected = RISK_BASE_STRATEGY[risk_category]
    assert expected in ("mvo", "hrp", "equal_weight")
    result = build_recommendation(_input(risk_category=risk_category, portfolio_candidate=_candidate(expected)))
    assert result.selected_strategy in ("mvo", "hrp", "equal_weight")


def test_invariant_6_portfolio_weights_come_from_the_supplied_phase_8_candidate():
    weights = {"QQQ": 0.55, "AGG": 0.30, "GLD": 0.15}
    result = build_recommendation(_input(risk_category="Aggressive", portfolio_candidate=_candidate("mvo", weights=weights)))
    assert result.weights == weights


def test_invariant_7_weights_are_not_changed_by_an_attempted_autogen_or_gemini_claim():
    weights = {"QQQ": 0.55, "AGG": 0.30, "GLD": 0.15}
    tampered = RecommendationInput(
        compliance=_compliance("PASS"), emergency_fund_sufficient=True, risk_category="Aggressive",
        portfolio_candidate=_candidate("mvo", weights=weights),
        autogen_verdict="APPROVE_OVERRIDE_TO_QQQ_0.80",  # type: ignore[call-arg]
    )
    result = build_recommendation(tampered)
    assert result.weights == weights


def test_invariant_8_risk_category_comes_from_the_supplied_phase_4_value():
    result = build_recommendation(_input(risk_category="Balanced", portfolio_candidate=_candidate("equal_weight")))
    assert result.risk_category == "Balanced"


def test_invariant_9_goal_feasibility_used_comes_from_the_supplied_phase_7_values():
    result = build_recommendation(
        _input(risk_category="Aggressive", goal_feasibilities=["Not Feasible"], portfolio_candidate=_candidate("mvo"))
    )
    assert result.rationale.goal_feasibility_used == "Not Feasible"


def test_invariant_10_market_regime_used_comes_from_the_supplied_phase_6_value():
    result = build_recommendation(_input(risk_category="Aggressive", market_regime="Volatile", portfolio_candidate=_candidate("mvo")))
    assert result.rationale.market_regime_used == "Volatile"


def test_invariant_11_final_decision_is_deterministic():
    payload = _input(risk_category="Income", goal_feasibilities=["Feasible"], market_regime="Range-bound", portfolio_candidate=_candidate("hrp"))
    outputs = [build_recommendation(payload).model_dump(exclude={"evaluated_at"}) for _ in range(5)]
    assert all(o == outputs[0] for o in outputs)


def test_invariant_12_no_new_financial_calculations_occur():
    """The engine never derives expected_return/expected_volatility/
    sharpe_ratio from weights -- it only ever copies whatever the supplied
    candidate already has, including a deliberately internally-inconsistent
    candidate (proving nothing is recomputed/re-derived/validated
    against the weights)."""
    candidate = _candidate("mvo", weights={"QQQ": 1.0, "AGG": 0.0, "GLD": 0.0}, expected_return=0.02, expected_volatility=0.5, sharpe_ratio=-3.0)
    result = build_recommendation(_input(risk_category="Aggressive", portfolio_candidate=candidate))
    assert result.expected_return == 0.02
    assert result.expected_volatility == 0.5
    assert result.sharpe_ratio == -3.0
