"""Deterministic tests for wealthpilot.data.preprocessing, using small
hand-built fixture tables (not the real 388k-row FAR-Trans data) so every
expected number can be checked exactly.

This file was rewritten after a temporal-leakage audit found that the
original implementation computed every feature from a customer's FULL
transaction/price history regardless of when their target risk label was
observed — see reports/phase3_leakage_audit.md for the full audit and the
real-data numbers. The fixtures here are deliberately built so that a leaky
implementation and a point-in-time-correct implementation would produce
DIFFERENT numbers, so these tests fail loudly if leakage is ever
reintroduced.

Fixture scenario:
- C1: genuine Conservative label at 2020-06-01 (-> target_date), then a
  LATER non-genuine Predicted_Balanced row at 2021-01-01 with a DIFFERENT
  investmentCapacity — tests that customer_type/investment_capacity are
  taken from the target row, not the latest row. C1 has two transactions
  BEFORE target_date and one AFTER — the after one must be invisible to
  every feature.
- C2: genuine Aggressive label at 2019-01-01, but their only transaction is
  AFTER that date — must be dropped from the output entirely (nothing
  point-in-time-safe to compute).
- C3: genuine Balanced label at 2020-01-10, with one transaction on
  2020-01-05 in an ISIN whose price history includes both pre- and
  post-target-date prices with very different volatility/drawdown
  characteristics on each side — proves realized_volatility/max_drawdown
  use only the pre-target-date prices.
"""

import numpy as np
import pandas as pd

from wealthpilot.data.preprocessing import (
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_preprocessing_pipeline,
    engineer_features,
    target_dates,
)


def _customers_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "customerID": "C1",
                "customerType": "Mass",
                "riskLevel": "Conservative",
                "investmentCapacity": "CAP_LT30K",
                "lastQuestionnaireDate": pd.Timestamp("2020-06-01"),
                "timestamp": pd.Timestamp("2020-06-01"),
            },
            {
                "customerID": "C1",
                "customerType": "Mass",
                "riskLevel": "Predicted_Balanced",
                "investmentCapacity": "CAP_GT300K",  # deliberately different
                "lastQuestionnaireDate": pd.Timestamp("2021-01-01"),
                "timestamp": pd.Timestamp("2021-01-01"),
            },
            {
                "customerID": "C2",
                "customerType": "Premium",
                "riskLevel": "Aggressive",
                "investmentCapacity": "CAP_GT300K",
                "lastQuestionnaireDate": pd.Timestamp("2019-01-01"),
                "timestamp": pd.Timestamp("2019-01-01"),
            },
            {
                "customerID": "C3",
                "customerType": "Mass",
                "riskLevel": "Balanced",
                "investmentCapacity": "CAP_30K_80K",
                "lastQuestionnaireDate": pd.Timestamp("2020-01-10"),
                "timestamp": pd.Timestamp("2020-01-10"),
            },
        ]
    )


def _transactions_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # C1: two Buy of ISIN_STOCK BEFORE target_date (2020-06-01), via
            # Internet Banking, plus one Sell of ISIN_BOND AFTER target_date
            # via Branch. The post-target Sell must be fully invisible.
            {"customerID": "C1", "ISIN": "ISIN_STOCK", "transactionID": "T1", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-02-01"), "totalValue": 100.0, "units": 10.0,
             "channel": "Internet Banking", "marketID": "M1"},
            {"customerID": "C1", "ISIN": "ISIN_STOCK", "transactionID": "T2", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-03-01"), "totalValue": 100.0, "units": 10.0,
             "channel": "Internet Banking", "marketID": "M1"},
            {"customerID": "C1", "ISIN": "ISIN_BOND", "transactionID": "T3", "transactionType": "Sell",
             "timestamp": pd.Timestamp("2021-06-01"), "totalValue": 999.0, "units": 5.0,
             "channel": "Branch", "marketID": "M1"},
            # C2: single Buy AFTER their target_date (2019-01-01) -> must be dropped entirely.
            {"customerID": "C2", "ISIN": "ISIN_STOCK", "transactionID": "T4", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2019-05-01"), "totalValue": 500.0, "units": 20.0,
             "channel": "Phone Banking", "marketID": "M1"},
            # C3: single Buy BEFORE target_date (2020-01-10).
            {"customerID": "C3", "ISIN": "ISIN_VOLATILE", "transactionID": "T5", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-01-05"), "totalValue": 200.0, "units": 10.0,
             "channel": "Internet Banking", "marketID": "M1"},
        ]
    )


def _assets_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ISIN": "ISIN_STOCK", "assetName": "Stock A", "assetShortName": "A",
             "assetCategory": "Stock", "assetSubCategory": "", "marketID": "M1",
             "sector": "Technology", "industry": "Software", "timestamp": "2018-01-02"},
            {"ISIN": "ISIN_BOND", "assetName": "Bond A", "assetShortName": "B",
             "assetCategory": "Bond", "assetSubCategory": "", "marketID": "M1",
             "sector": "", "industry": "", "timestamp": "2018-01-02"},
            {"ISIN": "ISIN_VOLATILE", "assetName": "Volatile A", "assetShortName": "V",
             "assetCategory": "Stock", "assetSubCategory": "", "marketID": "M1",
             "sector": "Energy", "industry": "", "timestamp": "2018-01-02"},
        ]
    )


def _close_prices_fixture() -> pd.DataFrame:
    stock_dates = pd.date_range("2020-01-01", periods=5, freq="D")
    stock = pd.DataFrame({"ISIN": "ISIN_STOCK", "timestamp": stock_dates, "closePrice": [10, 11, 9, 12, 12]})
    bond_dates = pd.date_range("2020-01-01", periods=5, freq="D")
    bond = pd.DataFrame({"ISIN": "ISIN_BOND", "timestamp": bond_dates, "closePrice": [100, 100, 101, 100, 99]})

    # ISIN_VOLATILE: calm BEFORE 2020-01-10 (target_date), then a huge crash
    # AFTER it. A leaky implementation (using the full series) would show a
    # large drawdown; the point-in-time-correct value must show none of it.
    pre_target = pd.date_range("2020-01-01", periods=10, freq="D")  # up to 2020-01-10
    post_target = pd.date_range("2020-01-11", periods=5, freq="D")
    volatile = pd.DataFrame(
        {
            "ISIN": "ISIN_VOLATILE",
            "timestamp": list(pre_target) + list(post_target),
            "closePrice": [50, 50.5, 50, 49.5, 50, 50.2, 50, 49.8, 50, 50,  # calm
                            40, 25, 15, 10, 5],  # crash, all AFTER target_date
        }
    )
    return pd.concat([stock, bond, volatile], ignore_index=True)


def test_target_dates_match_each_customers_genuine_labeled_row():
    dates = target_dates(_customers_fixture())
    assert dates["C1"] == pd.Timestamp("2020-06-01")
    assert dates["C2"] == pd.Timestamp("2019-01-01")
    assert dates["C3"] == pd.Timestamp("2020-01-10")


def test_label_is_latest_genuine_not_latest_row():
    features = engineer_features(
        _customers_fixture(), _transactions_fixture(), _assets_fixture(), _close_prices_fixture()
    )
    # C1's latest row overall (2021-01-01) is Predicted_Balanced (not
    # genuine) — the label must still be Conservative, from the earlier
    # genuine row, per CLAUDE.md rule 7.
    assert features.loc["C1", "risk_level"] == "Conservative"
    assert features.loc["C3", "risk_level"] == "Balanced"


def test_customer_with_zero_pre_target_transactions_is_dropped():
    features = engineer_features(
        _customers_fixture(), _transactions_fixture(), _assets_fixture(), _close_prices_fixture()
    )
    # C2's only transaction (2019-05-01) is AFTER their target_date (2019-01-01).
    assert "C2" not in features.index


def test_post_target_date_transaction_is_excluded_from_every_behavioural_feature():
    features = engineer_features(
        _customers_fixture(), _transactions_fixture(), _assets_fixture(), _close_prices_fixture()
    )
    c1 = features.loc["C1"]

    # If the post-target Sell of ISIN_BOND (999.0, Branch) were visible:
    # pct_value_bond would be > 0, pct_channel_branch would be > 0, and
    # position_size_mean would include 999.0. None of that may appear.
    assert c1["pct_value_bond"] == pytest_approx(0.0)
    assert c1["pct_value_stock"] == pytest_approx(1.0)
    assert c1["pct_channel_branch"] == pytest_approx(0.0)
    assert c1["pct_channel_internet"] == pytest_approx(1.0)

    # Only the two pre-target Buys (100.0 each) may contribute.
    assert c1["position_size_mean"] == pytest_approx(100.0)
    assert c1["position_size_std"] == pytest_approx(0.0)
    assert c1["largest_trade_pct_of_total"] == pytest_approx(0.5)


def test_investment_capacity_comes_from_target_row_not_latest_row():
    features = engineer_features(
        _customers_fixture(), _transactions_fixture(), _assets_fixture(), _close_prices_fixture()
    )
    # C1's target row (2020-06-01, Conservative) has CAP_LT30K; their LATER
    # row (2021-01-01, Predicted_Balanced) has CAP_GT300K. Using the latter
    # would leak a post-target-date profile change into the features.
    assert features.loc["C1", "investment_capacity"] == "CAP_LT30K"


def test_realized_volatility_and_drawdown_use_only_pre_target_date_prices():
    features = engineer_features(
        _customers_fixture(), _transactions_fixture(), _assets_fixture(), _close_prices_fixture()
    )
    c3 = features.loc["C3"]

    # The crash in ISIN_VOLATILE happens entirely AFTER C3's target_date
    # (2020-01-10). If it leaked in, max_drawdown would be roughly
    # (5 - 50.5) / 50.5 =~ -0.90. The calm pre-target series alone has a
    # much smaller drawdown.
    assert c3["max_drawdown"] > -0.05
    assert c3["max_drawdown"] != pytest_approx(-0.90, abs=0.05)

    # And it must match hand-computing the drawdown from ONLY the first 10
    # (pre-target) ISIN_VOLATILE prices.
    pre_target_prices = pd.Series([50, 50.5, 50, 49.5, 50, 50.2, 50, 49.8, 50, 50])
    running_max = pre_target_prices.cummax()
    expected_drawdown = float(((pre_target_prices - running_max) / running_max).min())
    assert c3["max_drawdown"] == pytest_approx(expected_drawdown)


def test_no_feature_uses_price_data_after_the_customers_target_date():
    """General-purpose leakage guard: independently recompute realized
    volatility/max drawdown for every labeled customer in the fixture using
    ONLY close_prices rows with timestamp <= that customer's target_date,
    and assert the engineered features match exactly. This test does not
    reuse engineer_features' own filtering logic, so it can't pass just
    because the implementation is internally consistent with itself.
    """
    customers = _customers_fixture()
    transactions = _transactions_fixture()
    close_prices = _close_prices_fixture()

    features = engineer_features(customers, transactions, _assets_fixture(), close_prices)
    dates = target_dates(customers)

    for customer_id in features.index:
        if pd.isna(features.loc[customer_id, "risk_level"]):
            continue
        target_date = dates[customer_id]

        held_isins = transactions.loc[
            (transactions["customerID"] == customer_id) & (transactions["timestamp"] <= target_date),
            "ISIN",
        ].unique()

        vols, drawdowns = [], []
        for isin in held_isins:
            prices = close_prices[
                (close_prices["ISIN"] == isin) & (close_prices["timestamp"] <= target_date)
            ].sort_values("timestamp")
            if len(prices) == 0:
                continue
            returns = prices["closePrice"].pct_change()
            vols.append(returns.std())
            running_max = prices["closePrice"].cummax()
            dd = ((prices["closePrice"] - running_max) / running_max).min()
            drawdowns.append(dd)

        expected_vol = float(np.nanmean(vols)) if vols else np.nan
        expected_dd = float(np.nanmean(drawdowns)) if drawdowns else np.nan

        actual_vol = features.loc[customer_id, "realized_volatility"]
        actual_dd = features.loc[customer_id, "max_drawdown"]

        if np.isnan(expected_vol):
            assert np.isnan(actual_vol), f"{customer_id}: expected NaN volatility"
        else:
            assert actual_vol == pytest_approx(expected_vol), f"{customer_id}: volatility mismatch"

        if np.isnan(expected_dd):
            assert np.isnan(actual_dd), f"{customer_id}: expected NaN drawdown"
        else:
            assert actual_dd == pytest_approx(expected_dd), f"{customer_id}: drawdown mismatch"


def test_missing_sector_is_bucketed_as_unknown_not_dropped():
    """Unrelated to the leakage audit — kept from the original test suite.
    A customer whose only pre-target holding has no sector recorded in
    asset_information.csv must still get a computable top_sector_share."""
    customers = pd.DataFrame(
        [
            {
                "customerID": "C4",
                "customerType": "Mass",
                "riskLevel": "Balanced",
                "investmentCapacity": "CAP_LT30K",
                "lastQuestionnaireDate": pd.Timestamp("2020-02-01"),
                "timestamp": pd.Timestamp("2020-02-01"),
            }
        ]
    )
    transactions = pd.DataFrame(
        [
            {"customerID": "C4", "ISIN": "ISIN_BOND", "transactionID": "T9", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-01-15"), "totalValue": 50.0, "units": 5.0,
             "channel": "Branch", "marketID": "M1"},
        ]
    )
    features = engineer_features(customers, transactions, _assets_fixture(), _close_prices_fixture())

    assert features.loc["C4", "top_sector_share"] == pytest_approx(1.0)


def test_preprocessing_pipeline_fit_transform_round_trip():
    features = engineer_features(
        _customers_fixture(), _transactions_fixture(), _assets_fixture(), _close_prices_fixture()
    )
    X = features[ALL_FEATURES]

    pipeline = build_preprocessing_pipeline()
    transformed = pipeline.fit_transform(X)

    assert transformed.shape[0] == len(X)
    pipeline_2 = build_preprocessing_pipeline()
    transformed_2 = pipeline_2.fit_transform(X)
    np.testing.assert_allclose(
        transformed if not hasattr(transformed, "toarray") else transformed.toarray(),
        transformed_2 if not hasattr(transformed_2, "toarray") else transformed_2.toarray(),
    )


def test_numeric_and_categorical_feature_lists_are_disjoint_and_complete():
    assert set(NUMERIC_FEATURES) & set(CATEGORICAL_FEATURES) == set()
    assert set(ALL_FEATURES) == set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES)


def pytest_approx(value, **kwargs):
    import pytest

    return pytest.approx(value, **kwargs)
