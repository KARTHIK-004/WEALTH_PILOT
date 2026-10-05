"""Market regime classification: training-only threshold derivation, no
future leakage, and correct classification precedence."""

import numpy as np
import pandas as pd
import pytest

from training.market.regime import classify_regimes, compute_regime_features


def test_regime_features_use_only_trailing_window():
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0, 0.01, 100))
    features = compute_regime_features(returns)
    assert features["rolling_vol"].iloc[:19].isna().all()  # needs 20 obs
    assert not pd.isna(features["rolling_vol"].iloc[19])


def test_thresholds_computed_only_from_training_slice():
    """Changing feature values AFTER train_end_idx must not change the
    thresholds -- proof classification thresholds never see test data."""
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0, 0.01, 300))
    features = compute_regime_features(returns)

    features_b = features.copy()
    features_b.iloc[250:] = features_b.iloc[250:] * 100  # huge change, test-period only

    _, thresholds_a = classify_regimes(features, train_end_idx=200)
    _, thresholds_b = classify_regimes(features_b, train_end_idx=200)

    assert thresholds_a == thresholds_b


def test_classification_precedence_volatile_before_trending():
    """A day with BOTH high volatility and high trend magnitude must be
    labelled Volatile, never Trending -- volatility is checked first."""
    features = pd.DataFrame(
        {
            "rolling_vol": [0.001] * 50 + [0.001] * 40 + [10.0],  # last row: extreme vol AND extreme trend
            "rolling_trend": [0.0001] * 50 + [0.0001] * 40 + [10.0],
        }
    )
    regimes, _ = classify_regimes(features, train_end_idx=90)
    assert regimes.iloc[-1] == "Volatile"


def test_classification_produces_trending_when_only_trend_is_extreme():
    rng = np.random.default_rng(1)
    low_vol_low_trend = pd.DataFrame(
        {"rolling_vol": rng.normal(0.01, 0.001, 90), "rolling_trend": rng.normal(0.0, 0.0005, 90)}
    )
    extreme_trend_row = pd.DataFrame({"rolling_vol": [0.01], "rolling_trend": [5.0]})
    features = pd.concat([low_vol_low_trend, extreme_trend_row], ignore_index=True)
    regimes, _ = classify_regimes(features, train_end_idx=90)
    assert regimes.iloc[-1] == "Trending"


def test_classification_produces_range_bound_when_neither_extreme():
    rng = np.random.default_rng(2)
    features = pd.DataFrame(
        {"rolling_vol": rng.normal(0.01, 0.0005, 100), "rolling_trend": rng.normal(0.0, 0.0002, 100)}
    )
    regimes, thresholds = classify_regimes(features, train_end_idx=90)
    # With normally distributed, low-magnitude features, most days should
    # fall below both thresholds and be Range-bound.
    counts = regimes.value_counts()
    assert counts.get("Range-bound", 0) > 0


def test_nan_rows_produce_nan_regime_not_a_fabricated_label():
    features = pd.DataFrame({"rolling_vol": [np.nan, np.nan, 0.01], "rolling_trend": [np.nan, np.nan, 0.001]})
    regimes, _ = classify_regimes(features, train_end_idx=3)
    assert pd.isna(regimes.iloc[0])
    assert pd.isna(regimes.iloc[1])


def test_thresholds_are_reproducible_given_same_training_data():
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0, 0.01, 300))
    features = compute_regime_features(returns)
    _, thresholds_1 = classify_regimes(features, train_end_idx=200)
    _, thresholds_2 = classify_regimes(features, train_end_idx=200)
    assert thresholds_1 == thresholds_2
