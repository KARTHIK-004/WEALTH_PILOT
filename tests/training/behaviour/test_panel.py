"""Tests for the monthly investment-activity panel construction."""

import pandas as pd

from training.behaviour.common import build_monthly_panel


def _transactions_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"customerID": "C1", "ISIN": "STOCK", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-01-05"), "totalValue": 100.0},
            {"customerID": "C1", "ISIN": "STOCK", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-01-20"), "totalValue": 50.0},
            {"customerID": "C1", "ISIN": "BOND", "transactionType": "Sell",
             "timestamp": pd.Timestamp("2020-02-10"), "totalValue": 30.0},
            {"customerID": "C2", "ISIN": "STOCK", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-01-15"), "totalValue": 200.0},
        ]
    )


def _assets_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ISIN": "STOCK", "assetCategory": "Stock", "timestamp": "2018-01-01"},
            {"ISIN": "BOND", "assetCategory": "Bond", "timestamp": "2018-01-01"},
        ]
    )


def test_panel_aggregates_correctly_per_customer_month():
    panel = build_monthly_panel(_transactions_fixture(), _assets_fixture())

    c1_jan = panel[(panel["customerID"] == "C1") & (panel["month"] == pd.Period("2020-01"))].iloc[0]
    assert c1_jan["trade_count"] == 2
    assert c1_jan["buy_value"] == 150.0
    assert c1_jan["pct_equity"] == 1.0  # both January trades were STOCK

    c1_feb = panel[(panel["customerID"] == "C1") & (panel["month"] == pd.Period("2020-02"))].iloc[0]
    assert c1_feb["trade_count"] == 1
    assert c1_feb["buy_value"] == 0.0  # the Feb transaction was a Sell, not a Buy
    assert c1_feb["pct_bond"] == 1.0


def test_panel_has_no_row_for_months_with_no_activity():
    panel = build_monthly_panel(_transactions_fixture(), _assets_fixture())
    c1_rows = panel[panel["customerID"] == "C1"]
    # C1 has transactions in Jan and Feb 2020 only -- no March row should exist.
    assert set(c1_rows["month"].astype(str)) == {"2020-01", "2020-02"}


def test_panel_handles_missing_asset_category_as_unknown_not_dropped():
    transactions = pd.DataFrame(
        [
            {"customerID": "C3", "ISIN": "UNKNOWN_ISIN", "transactionType": "Buy",
             "timestamp": pd.Timestamp("2020-01-01"), "totalValue": 100.0},
        ]
    )
    panel = build_monthly_panel(transactions, _assets_fixture())
    assert len(panel) == 1
    # No Stock/Bond/MTF match -> all three percentage columns are 0, not NaN/dropped.
    row = panel.iloc[0]
    assert row["pct_equity"] == 0.0 and row["pct_bond"] == 0.0 and row["pct_mtf"] == 0.0
