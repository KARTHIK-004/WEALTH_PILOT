"""Artifact round-trip and cluster-profiling tests — actually reload and
use the saved scaler+model, not just check that files exist."""

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from training.expense.train import profile_clusters


def _fixture_features():
    import pandas as pd

    rng = np.random.default_rng(42)
    n = 60
    return pd.DataFrame(
        {
            "expense_to_income_ratio": rng.uniform(0.3, 0.9, n),
            "savings_to_income_ratio": rng.uniform(0.1, 10, n),
            "debt_to_income_ratio": rng.uniform(0, 1, n),
            "emi_to_income_ratio": rng.uniform(0, 2, n),
        },
        index=[f"U{i}" for i in range(n)],
    )


def test_scaler_and_kmeans_round_trip(tmp_path):
    features = _fixture_features()
    scaler = StandardScaler().fit(features)
    X_scaled = scaler.transform(features)
    model = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X_scaled)

    scaler_path = tmp_path / "scaler.pkl"
    model_path = tmp_path / "kmeans.pkl"
    joblib.dump(scaler, scaler_path)
    joblib.dump(model, model_path)

    loaded_scaler = joblib.load(scaler_path)
    loaded_model = joblib.load(model_path)

    X_reloaded = loaded_scaler.transform(features)
    predictions = loaded_model.predict(X_reloaded)

    assert len(predictions) == len(features)
    assert set(predictions) <= {0, 1, 2}
    # Loaded artifacts must reproduce the exact original labels.
    np.testing.assert_array_equal(predictions, model.labels_)


def test_profile_clusters_uses_actual_computed_statistics_not_fabricated():
    features = _fixture_features()
    scaler = StandardScaler().fit(features)
    X_scaled = scaler.transform(features)
    model = KMeans(n_clusters=2, random_state=42, n_init=10).fit(X_scaled)

    profiles = profile_clusters(features, model.labels_)

    assert set(profiles.keys()) == {"0", "1"}
    total_size = sum(p["size"] for p in profiles.values())
    assert total_size == len(features)

    # Every profile's mean must match a direct, independent recomputation
    # from the raw features — not a fabricated or placeholder value.
    for cluster_id_str, profile in profiles.items():
        cluster_id = int(cluster_id_str)
        mask = model.labels_ == cluster_id
        expected_mean = features[mask]["expense_to_income_ratio"].mean()
        assert profile["mean"]["expense_to_income_ratio"] == pytest_approx(expected_mean)
        assert profile["descriptive_label"]  # non-empty, derived from real data


def pytest_approx(value, **kwargs):
    import pytest

    return pytest.approx(value, **kwargs)
