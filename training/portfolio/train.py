"""Phase 8 portfolio-optimization orchestrator.

Loads QQQ/AGG/GLD prices from the existing `market_data` table, builds the
return matrix, computes MVO (per risk category)/1-N/HRP/efficient-frontier
results on the full history as the "current recommendation" artifacts, runs
a chronological walk-forward backtest for all three strategies, saves
artifacts under `models/portfolio/`, and merges a `"portfolio"` key into
`models/metrics.json` (preserving `risk`/`expense`/`behaviour`/`market`).

Run with: python -m training.portfolio.train
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import joblib
import numpy as np

from training.portfolio.common import (
    MODELS_DIR,
    METRICS_PATH,
    build_return_matrix,
    library_versions,
    load_price_matrix,
    retrieval_timestamp,
)
from wealthpilot.core.backtest import (
    LOOKBACK_DAYS,
    REBALANCE_FREQUENCY_DAYS,
    TRANSACTION_COST_BPS,
    run_backtest,
)
from wealthpilot.core.optimizer import (
    ASSET_UNIVERSE,
    GENERAL_SINGLE_ASSET_CAP,
    RANDOM_STATE,
    RISK_FREE_RATE,
    RISK_LEVEL_QQQ_BANDS,
    covariance_ledoit_wolf,
    effective_bounds,
    efficient_frontier,
    equal_weight_portfolio,
    expected_returns_historical,
    hrp_weights,
    mvo_max_sharpe,
    portfolio_return,
    portfolio_volatility,
    sample_covariance,
    sharpe_ratio,
)

MODEL_VERSION = "v1"
RISK_LEVELS = list(RISK_LEVEL_QQQ_BANDS.keys())


def main() -> None:
    from sqlalchemy.orm import Session

    from wealthpilot.config import get_settings
    from wealthpilot.db.session import get_engine

    t_start = time.time()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    engine = get_engine(settings.database_url)
    with Session(engine) as session:
        prices = load_price_matrix(session, ASSET_UNIVERSE)
    returns = build_return_matrix(prices)
    print(f"loaded {len(returns)} aligned trading days for {ASSET_UNIVERSE}, "
          f"{returns.index.min()} to {returns.index.max()}", flush=True)

    # --- full-history "current recommendation" artifacts ---------------
    mu = expected_returns_historical(returns)
    cov, shrinkage = covariance_ledoit_wolf(returns)
    sample_cov = sample_covariance(returns)
    print(f"expected returns (annualized): {mu.to_dict()}", flush=True)
    print(f"Ledoit-Wolf shrinkage constant: {shrinkage:.4f}", flush=True)

    mvo_results = {}
    for risk_level in RISK_LEVELS:
        bounds = effective_bounds(risk_level)
        weights = mvo_max_sharpe(mu, cov, bounds, RISK_FREE_RATE)
        ret = portfolio_return(weights, mu)
        vol = portfolio_volatility(weights, cov)
        mvo_results[risk_level] = {
            "weights": weights.to_dict(),
            "bounds": {a: list(b) for a, b in bounds.items()},
            "expected_return": ret,
            "expected_volatility": vol,
            "sharpe_ratio": sharpe_ratio(ret, vol, RISK_FREE_RATE),
        }
        print(f"MVO {risk_level}: {weights.to_dict()}", flush=True)

    equal_weights = equal_weight_portfolio(ASSET_UNIVERSE)
    equal_ret = portfolio_return(equal_weights, mu)
    equal_vol = portfolio_volatility(equal_weights, cov)
    equal_result = {
        "weights": equal_weights.to_dict(),
        "expected_return": equal_ret,
        "expected_volatility": equal_vol,
        "sharpe_ratio": sharpe_ratio(equal_ret, equal_vol, RISK_FREE_RATE),
    }

    hrp_w = hrp_weights(returns)
    hrp_ret = portfolio_return(hrp_w, mu)
    hrp_vol = portfolio_volatility(hrp_w, cov)
    hrp_result = {
        "weights": hrp_w.to_dict(),
        "expected_return": hrp_ret,
        "expected_volatility": hrp_vol,
        "sharpe_ratio": sharpe_ratio(hrp_ret, hrp_vol, RISK_FREE_RATE),
    }
    print(f"1/N: {equal_weights.to_dict()}  HRP: {hrp_w.to_dict()}", flush=True)

    frontier_by_risk_level = {}
    for risk_level in RISK_LEVELS:
        bounds = effective_bounds(risk_level)
        frontier_df = efficient_frontier(mu, cov, bounds, RISK_FREE_RATE)
        frontier_by_risk_level[risk_level] = frontier_df.to_dict(orient="records")

    # --- backtests (walk-forward, no leakage) ---------------------------
    backtest_results = {}
    for strategy, risk_level in (
        [("equal_weight", None), ("hrp", None)] + [("mvo", rl) for rl in RISK_LEVELS]
    ):
        result = run_backtest(
            returns,
            strategy=strategy,
            risk_level=risk_level,
            lookback_days=LOOKBACK_DAYS,
            rebalance_days=REBALANCE_FREQUENCY_DAYS,
            risk_free_rate=RISK_FREE_RATE,
            transaction_cost_bps=TRANSACTION_COST_BPS,
        )
        key = strategy if risk_level is None else f"mvo_{risk_level.lower()}"
        backtest_results[key] = result.to_summary_dict()
        print(f"backtest {key}: ann_return={result.annualized_return:.4f} "
              f"ann_vol={result.annualized_volatility:.4f} sharpe={result.sharpe_ratio:.4f} "
              f"max_dd={result.max_drawdown:.4f} avg_turnover={result.average_turnover:.4f}", flush=True)

    # --- artifacts --------------------------------------------------
    ledoit_wolf_path = MODELS_DIR / f"ledoit_wolf_{MODEL_VERSION}.pkl"
    from sklearn.covariance import LedoitWolf
    lw_estimator = LedoitWolf().fit(returns.to_numpy())
    joblib.dump(lw_estimator, ledoit_wolf_path)

    (MODELS_DIR / f"ledoit_wolf_{MODEL_VERSION}.json").write_text(
        json.dumps(
            {
                "shrinkage_constant": shrinkage,
                "annualized_covariance": cov.to_dict(),
                "sample_covariance_annualized": sample_cov.to_dict(),
                "assets": ASSET_UNIVERSE,
                "trading_days_per_year": 252,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (MODELS_DIR / f"mvo_{MODEL_VERSION}.json").write_text(json.dumps(mvo_results, indent=2), encoding="utf-8")
    (MODELS_DIR / f"hrp_{MODEL_VERSION}.json").write_text(json.dumps(hrp_result, indent=2), encoding="utf-8")
    (MODELS_DIR / f"frontier_{MODEL_VERSION}.json").write_text(
        json.dumps(frontier_by_risk_level, indent=2, default=str), encoding="utf-8"
    )
    (MODELS_DIR / f"backtest_{MODEL_VERSION}.json").write_text(
        json.dumps(backtest_results, indent=2, default=str), encoding="utf-8"
    )

    config = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "retrieval_timestamp": retrieval_timestamp(),
        "asset_universe": ASSET_UNIVERSE,
        "date_range": [str(returns.index.min()), str(returns.index.max())],
        "n_observations": len(returns),
        "expected_return_methodology": "annualized historical mean of daily simple returns (never a Phase 6 forecast)",
        "covariance_methodology": "Ledoit-Wolf shrinkage, annualized",
        "optimization_objective": "maximize Sharpe ratio",
        "risk_free_rate": RISK_FREE_RATE,
        "general_single_asset_cap": GENERAL_SINGLE_ASSET_CAP,
        "risk_level_qqq_bands": {k: list(v) for k, v in RISK_LEVEL_QQQ_BANDS.items()},
        "hrp_methodology": "single-linkage clustering, quasi-diagonalization, recursive bisection (Lopez de Prado 2016)",
        "backtest": {
            "lookback_days": LOOKBACK_DAYS,
            "rebalance_frequency_days": REBALANCE_FREQUENCY_DAYS,
            "transaction_cost_bps": TRANSACTION_COST_BPS,
            "turnover_convention": "two-way, sum(|target - drifted_current|), first rebalance vs all-zero",
        },
        "random_state": RANDOM_STATE,
        "library_versions": library_versions(),
    }
    (MODELS_DIR / f"config_{MODEL_VERSION}.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    # --- reload-and-verify every artifact (never just check existence) --
    reloaded_lw = joblib.load(ledoit_wolf_path)
    reloaded_cov = reloaded_lw.covariance_ * 252
    assert np.allclose(reloaded_cov, cov.to_numpy()), "reloaded Ledoit-Wolf covariance mismatch"
    reloaded_mvo = json.loads((MODELS_DIR / f"mvo_{MODEL_VERSION}.json").read_text(encoding="utf-8"))
    for risk_level, result in reloaded_mvo.items():
        w = result["weights"]
        assert abs(sum(w.values()) - 1.0) < 1e-6, f"reloaded MVO {risk_level} weights don't sum to 1"
        for asset, (lo, hi) in result["bounds"].items():
            assert lo - 1e-6 <= w[asset] <= hi + 1e-6, f"reloaded MVO {risk_level} violates bounds for {asset}"
    reloaded_hrp = json.loads((MODELS_DIR / f"hrp_{MODEL_VERSION}.json").read_text(encoding="utf-8"))
    assert abs(sum(reloaded_hrp["weights"].values()) - 1.0) < 1e-6, "reloaded HRP weights don't sum to 1"
    print("all artifacts reloaded and verified", flush=True)

    # --- metrics.json (merge, never overwrite prior phases) -------------
    metrics_payload = {
        "portfolio": {
            "model_version": MODEL_VERSION,
            "trained_at": config["trained_at"],
            "asset_universe": ASSET_UNIVERSE,
            "date_range": config["date_range"],
            "expected_return_methodology": config["expected_return_methodology"],
            "covariance_methodology": config["covariance_methodology"],
            "optimization_objective": config["optimization_objective"],
            "risk_free_rate": RISK_FREE_RATE,
            "constraints": {
                "general_single_asset_cap": GENERAL_SINGLE_ASSET_CAP,
                "risk_level_qqq_bands": config["risk_level_qqq_bands"],
            },
            "mvo": mvo_results,
            "equal_weight": equal_result,
            "hrp": hrp_result,
            "efficient_frontier_points_per_risk_level": {k: len(v) for k, v in frontier_by_risk_level.items()},
            "backtest_config": config["backtest"],
            "backtest_results": backtest_results,
            "random_state": RANDOM_STATE,
            "library_versions": library_versions(),
            "total_time_seconds": time.time() - t_start,
        }
    }
    existing = json.loads(METRICS_PATH.read_text(encoding="utf-8")) if METRICS_PATH.exists() else {}
    existing.update(metrics_payload)
    METRICS_PATH.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")

    print("done", flush=True)


if __name__ == "__main__":
    main()
