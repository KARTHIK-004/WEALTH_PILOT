"""Isolation Forest artifact round-trip — actually reloads and re-scores,
not just checks the file exists."""

import json

import joblib
import numpy as np
import pandas as pd

from training.behaviour.detection import fit_isolation_forest


def test_isolation_forest_round_trip(tmp_path):
    rng = np.random.default_rng(42)
    panel = pd.DataFrame(
        {
            "trade_count": rng.normal(10, 2, 100),
            "buy_value": rng.normal(1000, 200, 100),
            "pct_equity": rng.uniform(0, 1, 100),
            "pct_bond": rng.uniform(0, 1, 100),
            "pct_mtf": rng.uniform(0, 1, 100),
        }
    )
    model, original_scores = fit_isolation_forest(panel, contamination=0.05)

    model_path = tmp_path / "iforest.pkl"
    joblib.dump(model, model_path)
    loaded_model = joblib.load(model_path)

    X = panel[["trade_count", "buy_value", "pct_equity", "pct_bond", "pct_mtf"]].to_numpy()
    loaded_scores = loaded_model.score_samples(X)

    np.testing.assert_allclose(loaded_scores, original_scores)
    np.testing.assert_array_equal(loaded_model.predict(X), model.predict(X))


def test_thresholds_json_round_trip(tmp_path):
    thresholds = {
        "z_score_alert_threshold": 2.0,
        "rolling_window_months": 12,
        "min_prior_months": 3,
        "cusum_k": 0.5,
        "cusum_h": 5.0,
        "isolation_forest_contamination": 0.05,
    }
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps(thresholds, indent=2), encoding="utf-8")

    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded == thresholds
