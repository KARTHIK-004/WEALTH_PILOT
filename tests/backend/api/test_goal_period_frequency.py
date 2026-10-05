"""Phase 29 — regression guards for two integration defects found by the
end-to-end validation pass.

1. **Frequency mismatch** (Phase 28 baseline): `run_goal_monte_carlo` draws
   ONE return per contribution period, but Phase 28 handed it the raw
   DAILY blended-return series. With the default 12 periods/year that
   applied a ~0.04% daily return once per month, understating growth ~20x,
   so every goal showed a 0.0% success probability ("Not Feasible") even
   where the deterministic TVM showed the plan ahead of the required
   contribution. `_compound_to_period_returns` now aligns the series to
   `GoalAssumptions.contribution_periods_per_year`.
2. **`savings_first` SSE summary** always said "Emergency fund
   insufficient", including when sufficiency was UNKNOWN.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from wealthpilot.agents.state import AgentState, EmergencyFundResult
from wealthpilot.api.services.analysis_service import (
    _build_graph_dependencies,
    _compound_to_period_returns,
    _node_summary,
)
from wealthpilot.core.goals import GoalAssumptions, GoalInput, analyze_goal_funding, run_goal_monte_carlo
from wealthpilot.db.models import FinancialInputs


# ---------------------------------------------------------------------------
# _compound_to_period_returns (pure)
# ---------------------------------------------------------------------------


def test_monthly_compounding_uses_21_day_blocks_exactly():
    daily = np.full(63, 0.01)  # 63 = 3 blocks of 21
    out = _compound_to_period_returns(daily, 12)
    assert out is not None
    assert len(out) == 3
    assert np.allclose(out, 1.01**21 - 1.0, rtol=0, atol=1e-12)


def test_quarterly_and_annual_periods_use_63_and_252_day_blocks():
    daily = np.full(252, 0.001)
    quarterly = _compound_to_period_returns(daily, 4)
    annual = _compound_to_period_returns(daily, 1)
    assert len(quarterly) == 4 and np.allclose(quarterly, 1.001**63 - 1.0, atol=1e-12)
    assert len(annual) == 1 and np.allclose(annual, 1.001**252 - 1.0, atol=1e-12)


def test_oldest_remainder_is_dropped_so_recent_history_is_fully_used():
    daily = np.concatenate([[0.5], np.full(21, 0.01)])  # one oldest outlier + exactly one block
    out = _compound_to_period_returns(daily, 12)
    assert len(out) == 1
    assert out[0] == pytest.approx(1.01**21 - 1.0, abs=1e-12)  # the 0.5 outlier is NOT in the block


def test_series_too_short_for_one_period_returns_none_not_a_guess():
    assert _compound_to_period_returns(np.full(20, 0.01), 12) is None
    assert _compound_to_period_returns(np.array([]), 12) is None


def test_very_high_frequency_degrades_to_block_of_one_not_zero():
    daily = np.array([0.01, -0.02, 0.03])
    out = _compound_to_period_returns(daily, 1000)  # round(252/1000) == 0 -> clamped to 1
    assert np.allclose(out, daily)


# ---------------------------------------------------------------------------
# The defect, reproduced end to end against the real goal engine
# ---------------------------------------------------------------------------


def test_daily_series_collapsed_a_feasible_goal_to_zero_percent_and_compounding_fixes_it():
    # Zero-volatility series: every bootstrap draw is identical, so the
    # Monte Carlo is deterministic and the assertions below are exact
    # properties rather than thresholds tuned to a noisy sample.
    daily = np.full(1176, 0.0005)  # ~13.4%/yr when compounded over a year
    goal = GoalInput(customer_id=1, goal_type="Retirement", target_amount=400_000, current_savings=35_000, target_date=date(2050, 1, 1))
    assumptions = GoalAssumptions(contribution_amount=1000, annual_return_rate=0.07, annual_inflation_rate=0.03)
    funding = analyze_goal_funding(goal, assumptions, date(2026, 9, 20))
    assert funding.contribution_gap < 0  # deterministic TVM: plan is AHEAD of the required contribution

    def p_success(returns):
        return run_goal_monte_carlo(
            current_savings=35_000,
            periodic_contribution=1000,
            n_periods=funding.periods_remaining,
            target_amount=funding.inflation_adjusted_target_amount,
            historical_returns=returns,
        ).success_probability

    assert p_success(daily) == 0.0  # the Phase 28 behaviour: a daily return applied once per month
    assert p_success(_compound_to_period_returns(daily, 12)) == 1.0  # period-aligned: agrees with the TVM


# ---------------------------------------------------------------------------
# _build_graph_dependencies wiring (synthetic market_data, TEST_DATABASE_URL)
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_market(monkeypatch):
    frame = pd.DataFrame(0.001, index=pd.date_range("2024-01-01", periods=504, freq="B"), columns=["QQQ", "AGG", "GLD"])
    monkeypatch.setattr("wealthpilot.agents.nodes.load_portfolio_returns", lambda session: frame)
    return frame


def _inputs(customer_id, **overrides):
    values = dict(
        customer_id=customer_id, monthly_essential_expenses=2000, current_liquid_assets=9000,
        contribution_amount=500, annual_return_rate=0.06, annual_inflation_rate=0.03, contribution_periods_per_year=12,
    )
    values.update(overrides)
    return FinancialInputs(**values)


def test_deps_use_period_frequency_returns_for_monthly_goals(db_session, make_customer, synthetic_market):
    customer = make_customer()
    db_session.add(_inputs(customer.id))
    db_session.flush()
    deps = _build_graph_dependencies(db_session, customer.id, None)
    assert len(deps.historical_returns) == 504 // 21
    assert np.allclose(deps.historical_returns, 1.001**21 - 1.0, atol=1e-12)


def test_deps_follow_the_customers_own_contribution_frequency(db_session, make_customer, synthetic_market):
    customer = make_customer()
    db_session.add(_inputs(customer.id, contribution_periods_per_year=4))
    db_session.flush()
    deps = _build_graph_dependencies(db_session, customer.id, None)
    assert len(deps.historical_returns) == 504 // 63


def test_deps_default_to_monthly_when_frequency_not_supplied(db_session, make_customer, synthetic_market):
    customer = make_customer()
    db_session.add(_inputs(customer.id, contribution_periods_per_year=None))
    db_session.flush()
    deps = _build_graph_dependencies(db_session, customer.id, None)
    assert deps.goal_assumptions.contribution_periods_per_year == 12  # GoalAssumptions' own default
    assert len(deps.historical_returns) == 504 // 21


def test_no_goal_assumptions_means_no_returns_series_but_emergency_inputs_still_flow(db_session, make_customer, synthetic_market):
    customer = make_customer()
    db_session.add(_inputs(customer.id, annual_return_rate=None))  # GoalAssumptions cannot be built
    db_session.flush()
    deps = _build_graph_dependencies(db_session, customer.id, None)
    assert deps.goal_assumptions is None
    assert deps.historical_returns is None
    assert deps.monthly_essential_expenses == 2000.0 and deps.current_liquid_assets == 9000.0


def test_empty_market_data_leaves_returns_unavailable_never_fabricated(db_session, make_customer, monkeypatch):
    def _raise(session):
        raise RuntimeError("no market_data rows")

    monkeypatch.setattr("wealthpilot.agents.nodes.load_portfolio_returns", _raise)
    customer = make_customer()
    db_session.add(_inputs(customer.id))
    db_session.flush()
    deps = _build_graph_dependencies(db_session, customer.id, None)
    assert deps.goal_assumptions is not None
    assert deps.historical_returns is None


# ---------------------------------------------------------------------------
# Cache key: a computation fix must invalidate stale cached results
# ---------------------------------------------------------------------------


def test_profile_hash_changes_with_the_pipeline_version(make_customer, monkeypatch):
    from wealthpilot.api.services import analysis_service
    from wealthpilot.api.services.analysis_service import compute_profile_hash

    customer = make_customer()
    same_a = compute_profile_hash(customer, [], None, None)
    same_b = compute_profile_hash(customer, [], None, None)
    assert same_a == same_b  # deterministic for unchanged inputs and version

    monkeypatch.setattr(analysis_service, "ANALYSIS_PIPELINE_VERSION", "some-later-version")
    assert compute_profile_hash(customer, [], None, None) != same_a


# ---------------------------------------------------------------------------
# savings_first SSE summary
# ---------------------------------------------------------------------------


def test_savings_first_summary_says_insufficient_only_when_known_insufficient():
    known = AgentState(customer_id=1, emergency_fund=EmergencyFundResult(sufficient=False, shortfall=100.0))
    assert "insufficient" in _node_summary("savings_first", known)


def test_savings_first_summary_does_not_claim_insufficient_when_unknown():
    unknown = AgentState(customer_id=1, emergency_fund=EmergencyFundResult(sufficient=None, unavailable_reason="not supplied"))
    text = _node_summary("savings_first", unknown)
    assert "insufficient" not in text
    assert "could not be confirmed" in text
    assert "could not be confirmed" in _node_summary("savings_first", AgentState(customer_id=1))
