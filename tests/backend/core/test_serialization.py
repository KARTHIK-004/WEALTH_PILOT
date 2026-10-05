"""Phase 7 has no persisted model artifacts or config files (pure
deterministic maths, nothing trained) -- so "serialization" here means the
output Pydantic models are safe to cross an API boundary: JSON-serializable
with no leaked numpy scalar types (which `json` cannot encode)."""

import json
from datetime import date

import numpy as np

from wealthpilot.core.goals import (
    GoalAssumptions,
    GoalInput,
    analyze_goal_funding,
    assess_emergency_fund,
    run_goal_monte_carlo,
)


def test_goal_funding_analysis_is_json_serializable():
    goal = GoalInput(
        customer_id=1, goal_type="House Purchase", target_amount=5_000_000,
        current_savings=1_000_000, target_date=date(2031, 9, 14),
    )
    assumptions = GoalAssumptions(contribution_amount=35_000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    result = analyze_goal_funding(goal, assumptions, current_date=date(2026, 9, 14))

    payload = json.loads(result.model_dump_json())
    assert payload["nominal_target_amount"] == 5_000_000
    assert isinstance(payload["already_achieved"], bool)


def test_monte_carlo_result_is_json_serializable_with_no_leaked_numpy_types():
    hist = np.random.default_rng(1).normal(0.0004, 0.01, 100)
    result = run_goal_monte_carlo(500_000, 10_000, 24, 1_000_000, hist)

    dumped = result.model_dump()
    for key, value in dumped.items():
        assert not isinstance(value, np.generic), f"{key} leaked a numpy scalar type: {type(value)}"

    payload = json.loads(result.model_dump_json())
    assert payload["n_simulations"] == 10_000


def test_emergency_fund_status_is_json_serializable():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=90_000)
    payload = json.loads(status.model_dump_json())
    assert payload["sufficient"] is False


def test_goal_input_round_trips_through_json():
    goal = GoalInput(
        customer_id=7, goal_type="Retirement", target_amount=10_000_000,
        current_savings=500_000, target_date=date(2050, 1, 1), priority=2,
    )
    restored = GoalInput.model_validate_json(goal.model_dump_json())
    assert restored == goal
