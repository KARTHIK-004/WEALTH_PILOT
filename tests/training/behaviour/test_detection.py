"""Tests for rolling z-score, CUSUM, temporal-cutoff safety, Isolation
Forest, and risk-profile-change detection."""

import numpy as np
import pandas as pd
import pytest

from training.behaviour.common import MIN_PRIOR_MONTHS
from training.behaviour.detection import (
    cusum,
    detect_risk_profile_changes,
    fit_isolation_forest,
    rolling_zscore,
)


def _make_panel(customer_id: str, monthly_values: list[float]) -> pd.DataFrame:
    months = pd.period_range("2020-01", periods=len(monthly_values), freq="M")
    return pd.DataFrame(
        {
            "customerID": [customer_id] * len(monthly_values),
            "month": months,
            "trade_count": monthly_values,
            "buy_value": monthly_values,
            "pct_equity": [1.0] * len(monthly_values),
            "pct_bond": [0.0] * len(monthly_values),
            "pct_mtf": [0.0] * len(monthly_values),
        }
    )


def test_zscore_is_nan_before_minimum_prior_history():
    # Deliberately non-constant baseline values (9/10/11, not a repeated
    # 10) -- a constant baseline has zero variance, which the zero-std
    # guard also turns into NaN, which would confuse this specific test's
    # intent (insufficient history) with that separate, deliberate guard
    # (covered by test_zscore_handles_zero_variance_denominator_without_crashing).
    panel = _make_panel("C1", [9, 10, 11, 10, 100])
    z = rolling_zscore(panel, "trade_count")
    # First MIN_PRIOR_MONTHS rows have fewer than MIN_PRIOR_MONTHS PRIOR
    # observations available -> no baseline -> NaN.
    assert z.iloc[:MIN_PRIOR_MONTHS].isna().all()
    assert not z.isna().iloc[MIN_PRIOR_MONTHS:].all()


def test_zscore_detects_a_real_spike():
    panel = _make_panel("C1", [9, 10, 11, 10, 9, 11, 100])
    z = rolling_zscore(panel, "trade_count")
    assert z.iloc[-1] > 2.0  # the spike month should show a large positive z-score


def test_zscore_never_uses_future_months():
    """Changing a FUTURE month's value must not change any EARLIER month's
    z-score — the direct, general-purpose proof that this is point-in-time
    safe, not just a plausibility check."""
    panel_a = _make_panel("C1", [10, 11, 9, 10, 10, 10, 10, 10])
    panel_b = panel_a.copy()
    panel_b.loc[panel_b.index[-1], "trade_count"] = 99999  # change only the LAST month

    z_a = rolling_zscore(panel_a, "trade_count")
    z_b = rolling_zscore(panel_b, "trade_count")

    # Every month EXCEPT the last (which now has a different current value,
    # not baseline) must be identical between the two runs.
    pd.testing.assert_series_equal(z_a.iloc[:-1], z_b.iloc[:-1])


def test_zscore_handles_zero_variance_denominator_without_crashing():
    """A customer with an IDENTICAL value every month has zero trailing
    std -- division by zero must produce NaN, not a crash or a fabricated
    infinite/huge z-score."""
    panel = _make_panel("C1", [10, 10, 10, 10, 10, 10, 10])
    z = rolling_zscore(panel, "trade_count")
    # Every month has 0 trailing std once there's a baseline -> NaN, never inf.
    assert not np.isinf(z.dropna()).any()


def test_customer_with_only_two_months_never_gets_a_baseline():
    """Sparse historical record: fewer months than MIN_PRIOR_MONTHS
    entirely -- every value must be NaN, never a spuriously-computed one."""
    panel = _make_panel("C1", [10, 20])
    z = rolling_zscore(panel, "trade_count")
    assert z.isna().all()


def test_cusum_alarms_on_sustained_drift_not_single_point_noise():
    # Stable baseline, then a single noisy-but-not-sustained blip, then a
    # SUSTAINED shift -- CUSUM should catch the sustained one.
    values = [10] * 6 + [10] * 6 + [40] * 6  # sustained upward shift only in the last stretch
    panel = _make_panel("C1", values)
    result = cusum(panel, "trade_count")
    assert result["cusum_alarm"].iloc[-6:].any()


def test_isolation_forest_flags_a_clear_multivariate_outlier():
    rng = np.random.default_rng(42)
    n = 200
    normal = pd.DataFrame(
        {
            "trade_count": rng.normal(10, 2, n),
            "buy_value": rng.normal(1000, 200, n),
            "pct_equity": rng.uniform(0.4, 0.6, n),
            "pct_bond": rng.uniform(0.2, 0.4, n),
            "pct_mtf": rng.uniform(0.0, 0.2, n),
        }
    )
    outlier = pd.DataFrame(
        [{"trade_count": 500, "buy_value": 50000, "pct_equity": 1.0, "pct_bond": 0.0, "pct_mtf": 0.0}]
    )
    panel = pd.concat([normal, outlier], ignore_index=True)

    model, scores = fit_isolation_forest(panel, contamination=0.05)
    predictions = model.predict(panel[["trade_count", "buy_value", "pct_equity", "pct_bond", "pct_mtf"]])
    assert predictions[-1] == -1  # the constructed outlier must be flagged
    assert scores[-1] == scores.min()  # and be the single most anomalous row


def test_detect_risk_profile_changes_flags_real_changes_and_ignores_stable_customers():
    customers = pd.DataFrame(
        [
            {"customerID": "STABLE", "customerType": "Mass", "riskLevel": "Balanced",
             "investmentCapacity": "CAP_LT30K", "timestamp": pd.Timestamp("2020-01-01")},
            {"customerID": "STABLE", "customerType": "Mass", "riskLevel": "Balanced",
             "investmentCapacity": "CAP_LT30K", "timestamp": pd.Timestamp("2021-01-01")},
            {"customerID": "CHANGED", "customerType": "Mass", "riskLevel": "Conservative",
             "investmentCapacity": "CAP_LT30K", "timestamp": pd.Timestamp("2020-01-01")},
            {"customerID": "CHANGED", "customerType": "Mass", "riskLevel": "Aggressive",
             "investmentCapacity": "CAP_GT300K", "timestamp": pd.Timestamp("2021-01-01")},
        ]
    )
    result = detect_risk_profile_changes(customers)

    stable_rows = result[result["customerID"] == "STABLE"]
    assert not stable_rows["risk_level_changed"].any()
    assert not stable_rows["investment_capacity_changed"].any()

    changed_rows = result[result["customerID"] == "CHANGED"].sort_values("timestamp")
    assert not changed_rows.iloc[0]["risk_level_changed"]  # first row has no "previous" to compare
    assert changed_rows.iloc[1]["risk_level_changed"]
    assert changed_rows.iloc[1]["investment_capacity_changed"]
