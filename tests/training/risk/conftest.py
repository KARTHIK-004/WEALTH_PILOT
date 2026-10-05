"""Shared synthetic training data for fast Phase 4 tests.

Deliberately NOT the real FAR-Trans data (21,528 rows, several minutes per
model family to train) — these tests check training *mechanics*
(label filtering, preprocessing isolation, artifact round-trips,
determinism, metrics-output shape) on a small, fast, fully-controlled
synthetic table with the same schema `engineer_features()` produces.
"""

import numpy as np
import pandas as pd
import pytest

from wealthpilot.data.preprocessing import ALL_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES


@pytest.fixture()
def synthetic_training_table():
    rng = np.random.default_rng(42)
    n = 200
    labels = rng.choice(
        ["Conservative", "Income", "Balanced", "Aggressive"], size=n, p=[0.25, 0.3, 0.3, 0.15]
    )

    data = {col: rng.random(n) for col in NUMERIC_FEATURES}
    data["active_months"] = rng.integers(1, 24, size=n)
    data["customer_type"] = rng.choice(["Mass", "Premium"], size=n)
    data["investment_capacity"] = rng.choice(["CAP_LT30K", "CAP_30K_80K"], size=n)

    X = pd.DataFrame(data)[ALL_FEATURES]
    y = pd.Series(labels, name="risk_level")
    return X, y
