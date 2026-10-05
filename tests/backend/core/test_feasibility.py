"""Goal feasibility classification thresholds (approved 2026-09-14:
Feasible >= 0.80, At Risk 0.50-0.79, Not Feasible < 0.50)."""

import pytest

from wealthpilot.core.goals import AT_RISK_THRESHOLD, FEASIBLE_THRESHOLD, classify_feasibility


def test_thresholds_match_approved_values():
    assert FEASIBLE_THRESHOLD == 0.80
    assert AT_RISK_THRESHOLD == 0.50


def test_high_probability_is_feasible():
    assert classify_feasibility(0.95) == "Feasible"
    assert classify_feasibility(0.80) == "Feasible"  # boundary is inclusive


def test_mid_probability_is_at_risk():
    assert classify_feasibility(0.79) == "At Risk"
    assert classify_feasibility(0.50) == "At Risk"  # boundary is inclusive
    assert classify_feasibility(0.65) == "At Risk"


def test_low_probability_is_not_feasible():
    assert classify_feasibility(0.49) == "Not Feasible"
    assert classify_feasibility(0.0) == "Not Feasible"


def test_boundary_just_below_feasible_threshold():
    assert classify_feasibility(0.7999) == "At Risk"


def test_boundary_just_below_at_risk_threshold():
    assert classify_feasibility(0.4999) == "Not Feasible"


def test_probability_of_exactly_one_is_feasible():
    assert classify_feasibility(1.0) == "Feasible"


def test_rejects_probability_outside_unit_interval():
    with pytest.raises(ValueError):
        classify_feasibility(1.5)
    with pytest.raises(ValueError):
        classify_feasibility(-0.1)


def test_classification_is_deterministic():
    for _ in range(5):
        assert classify_feasibility(0.63) == "At Risk"
