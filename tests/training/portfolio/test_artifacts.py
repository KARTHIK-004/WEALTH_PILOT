"""Phase 8 artifact round-trips against the REAL saved files under
models/portfolio/ -- reloads every artifact independently and uses it to
produce a real result, not just a file-existence check."""

import json

import joblib
import numpy as np
import pytest

from training.portfolio.common import MODELS_DIR
from wealthpilot.core.optimizer import ASSET_UNIVERSE, RISK_LEVEL_QQQ_BANDS

MODEL_VERSION = "v1"

pytestmark = pytest.mark.skipif(
    not (MODELS_DIR / f"config_{MODEL_VERSION}.json").exists(),
    reason="Phase 8 artifacts not yet produced -- run `python -m training.portfolio.train` first",
)


def test_ledoit_wolf_pickle_reloads_and_reproduces_the_saved_covariance():
    lw_path = MODELS_DIR / f"ledoit_wolf_{MODEL_VERSION}.pkl"
    json_path = MODELS_DIR / f"ledoit_wolf_{MODEL_VERSION}.json"

    estimator = joblib.load(lw_path)
    reloaded_cov = estimator.covariance_ * 252  # same annualization as training

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    saved_cov = saved["annualized_covariance"]
    for asset_i in ASSET_UNIVERSE:
        for j, asset_j in enumerate(ASSET_UNIVERSE):
            i = ASSET_UNIVERSE.index(asset_i)
            assert reloaded_cov[i, j] == pytest.approx(saved_cov[asset_i][asset_j], rel=1e-6)

    assert np.isfinite(reloaded_cov).all()
    eigvals = np.linalg.eigvalsh(reloaded_cov)
    assert (eigvals >= -1e-8).all()


def test_mvo_json_reloads_with_weights_summing_to_one_and_within_bounds():
    path = MODELS_DIR / f"mvo_{MODEL_VERSION}.json"
    results = json.loads(path.read_text(encoding="utf-8"))
    assert set(results.keys()) == set(RISK_LEVEL_QQQ_BANDS.keys())
    for risk_level, result in results.items():
        weights = result["weights"]
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)
        for asset, (lower, upper) in result["bounds"].items():
            assert lower - 1e-6 <= weights[asset] <= upper + 1e-6
        assert np.isfinite(result["sharpe_ratio"])


def test_hrp_json_reloads_with_weights_summing_to_one():
    path = MODELS_DIR / f"hrp_{MODEL_VERSION}.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    weights = result["weights"]
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(w >= -1e-9 for w in weights.values())


def test_frontier_json_reloads_with_finite_monotonic_ish_structure():
    path = MODELS_DIR / f"frontier_{MODEL_VERSION}.json"
    frontier_by_risk_level = json.loads(path.read_text(encoding="utf-8"))
    for risk_level, points in frontier_by_risk_level.items():
        assert len(points) > 0
        for point in points:
            assert np.isfinite(point["return"])
            assert np.isfinite(point["volatility"])
            assert point["volatility"] >= 0
            assert sum(point["weights"].values()) == pytest.approx(1.0, abs=1e-3)
        assert sum(p["is_max_sharpe"] for p in points) == 1


def test_backtest_json_reloads_with_all_six_strategies():
    path = MODELS_DIR / f"backtest_{MODEL_VERSION}.json"
    results = json.loads(path.read_text(encoding="utf-8"))
    expected_keys = {"equal_weight", "hrp", "mvo_conservative", "mvo_income", "mvo_balanced", "mvo_aggressive"}
    assert set(results.keys()) == expected_keys
    for key, result in results.items():
        assert np.isfinite(result["annualized_return"])
        assert np.isfinite(result["annualized_volatility"])
        assert np.isfinite(result["sharpe_ratio"])
        assert result["max_drawdown"] <= 0.0
        assert result["n_rebalances"] > 0
        assert result["turnovers"][0] == pytest.approx(1.0, abs=1e-6)  # first rebalance vs all-zero


def test_config_json_reloads_with_documented_methodology():
    path = MODELS_DIR / f"config_{MODEL_VERSION}.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    assert config["asset_universe"] == ASSET_UNIVERSE
    assert config["risk_free_rate"] == 0.0
    assert config["random_state"] == 42
    assert "library_versions" in config
    assert config["optimization_objective"] == "maximize Sharpe ratio"
