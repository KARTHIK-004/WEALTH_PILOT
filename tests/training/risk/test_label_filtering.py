"""Regression tests: Predicted_*/Not_Available must never reach training.

`engineer_features()` (Phase 3) already filters to genuine labels only, so
under normal operation a non-genuine value can never reach
`load_training_table()`. These tests exercise the defensive check in
`load_training_table()` itself directly (by monkeypatching what
`engineer_features` returns), so a future regression in Phase 3's filtering
is still caught here, not silently trusted.
"""

import pandas as pd
import pytest

import training.risk.common as common


def _fake_features(risk_levels):
    return pd.DataFrame(
        {
            **{col: [0.0] * len(risk_levels) for col in common.ALL_FEATURES if col not in ("customer_type", "investment_capacity")},
            "customer_type": ["Mass"] * len(risk_levels),
            "investment_capacity": ["CAP_LT30K"] * len(risk_levels),
            "risk_level": risk_levels,
        },
        index=[f"C{i}" for i in range(len(risk_levels))],
    )


def test_load_training_table_accepts_only_genuine_labels(monkeypatch):
    monkeypatch.setattr(
        common, "engineer_features", lambda *a, **k: _fake_features(["Conservative", "Income", None])
    )
    monkeypatch.setattr(common, "load_far_trans_tables", lambda: {"customers": None, "transactions": None, "assets": None, "close_prices": None})

    X, y = common.load_training_table()
    assert len(y) == 2
    assert set(y) == {"Conservative", "Income"}


def test_load_training_table_rejects_predicted_star(monkeypatch):
    monkeypatch.setattr(
        common, "engineer_features", lambda *a, **k: _fake_features(["Conservative", "Predicted_Balanced"])
    )
    monkeypatch.setattr(common, "load_far_trans_tables", lambda: {"customers": None, "transactions": None, "assets": None, "close_prices": None})

    with pytest.raises(AssertionError, match="Predicted_Balanced"):
        common.load_training_table()


def test_load_training_table_rejects_not_available(monkeypatch):
    monkeypatch.setattr(
        common, "engineer_features", lambda *a, **k: _fake_features(["Conservative", "Not_Available"])
    )
    monkeypatch.setattr(common, "load_far_trans_tables", lambda: {"customers": None, "transactions": None, "assets": None, "close_prices": None})

    with pytest.raises(AssertionError, match="Not_Available"):
        common.load_training_table()
