"""Phase 6 market-analysis orchestrator.

For each of the 5 instruments: fetch OHLCV via yfinance, ingest into
PostgreSQL (idempotent upsert), compute returns, run all 5 model families
across every walk-forward window, aggregate evaluation metrics (RMSE/MAE/
directional accuracy for return models; RMSE/MAE for GARCH's volatility
forecasts), run Diebold-Mariano comparisons against the naive baseline,
classify market regimes, save final artifacts, and write
models/metrics.json + reports/phase6_market_analysis_report.md.

Run with: python -m training.market.train
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from training.market.common import (
    DATA_START,
    EMBARGO_DAYS,
    FORECAST_HORIZON_DAYS,
    INITIAL_TRAIN_DAYS,
    INSTRUMENTS,
    MODELS_DIR,
    METRICS_PATH,
    RANDOM_STATE,
    REPORTS_DIR,
    TEST_WINDOW_DAYS,
    fetch_ohlcv,
    library_versions,
    retrieval_timestamp,
    upsert_market_data,
    walk_forward_windows,
)
from training.market.dl_models import fit_and_forecast
from training.market.evaluate import diebold_mariano, directional_accuracy, mae, rmse
from training.market.models import arima_forecast, garch_forecast, naive_forecast, select_arima_order
from training.market.preprocessing import (
    compute_realized_volatility_target,
    compute_returns,
    validate_chronological_order,
)
from training.market.regime import classify_regimes, compute_regime_features

MODEL_VERSION = "v1"


def run_asset(ticker: str) -> dict:
    ohlcv = fetch_ohlcv(ticker)
    validate_chronological_order(ohlcv.index)

    returns_with_dates = compute_returns(ohlcv).dropna()
    returns = returns_with_dates.reset_index(drop=True)
    n_missing_days = int(ohlcv[["open", "high", "low", "close"]].isna().any(axis=1).sum())

    vol_target = compute_realized_volatility_target(returns)
    regime_features = compute_regime_features(returns)

    windows = walk_forward_windows(len(returns))

    per_model_forecasts = {"naive": [], "arima": [], "garch": [], "lstm": [], "gru": []}
    per_model_actuals = {"naive": [], "arima": [], "garch": [], "lstm": [], "gru": []}
    arima_orders, lstm_lengths, gru_lengths = [], [], []
    regime_history = []
    final_lstm_artifact, final_gru_artifact = None, None

    for w in windows:
        train = returns.iloc[w["train_start"] : w["train_end"]]
        test_actual = returns.iloc[w["test_start"] : w["test_end"]].to_numpy()
        n_test = len(test_actual)

        naive_fc = naive_forecast(train, n_test)
        per_model_forecasts["naive"].append(naive_fc)
        per_model_actuals["naive"].append(test_actual)

        arima_fc, order = arima_forecast(train, n_test)
        arima_orders.append(order)
        per_model_forecasts["arima"].append(arima_fc)
        per_model_actuals["arima"].append(test_actual)

        garch_fc = garch_forecast(train, n_test)
        vol_actual = vol_target.iloc[w["test_start"] : w["test_end"]].to_numpy()
        per_model_forecasts["garch"].append(garch_fc)
        per_model_actuals["garch"].append(vol_actual)

        context = returns.iloc[w["train_start"] : w["test_end"]]
        lstm_result = fit_and_forecast("lstm", train, context, n_test)
        lstm_lengths.append(lstm_result["window_length"])
        per_model_forecasts["lstm"].append(lstm_result["forecast"])
        per_model_actuals["lstm"].append(test_actual)
        final_lstm_artifact = lstm_result  # keep the LAST window's fit as the production artifact

        gru_result = fit_and_forecast("gru", train, context, n_test)
        gru_lengths.append(gru_result["window_length"])
        per_model_forecasts["gru"].append(gru_result["forecast"])
        per_model_actuals["gru"].append(test_actual)
        final_gru_artifact = gru_result

        regimes, thresholds = classify_regimes(regime_features, w["train_end"])
        window_regimes = regimes.iloc[w["test_start"] : w["test_end"]]
        regime_history.append({"window": w, "thresholds": thresholds, "regimes": window_regimes})

    metrics = {}
    for model_name in ["naive", "arima", "lstm", "gru"]:
        y_true = np.concatenate(per_model_actuals[model_name])
        y_pred = np.concatenate(per_model_forecasts[model_name])
        valid = ~(np.isnan(y_true) | np.isnan(y_pred))
        metrics[model_name] = {
            "rmse": rmse(y_true[valid], y_pred[valid]),
            "mae": mae(y_true[valid], y_pred[valid]),
            "directional_accuracy": directional_accuracy(y_true[valid], y_pred[valid]),
            "n_observations": int(valid.sum()),
        }

    garch_true = np.concatenate(per_model_actuals["garch"])
    garch_pred = np.concatenate(per_model_forecasts["garch"])
    garch_valid = ~(np.isnan(garch_true) | np.isnan(garch_pred))
    metrics["garch"] = {
        "rmse": rmse(garch_true[garch_valid], garch_pred[garch_valid]),
        "mae": mae(garch_true[garch_valid], garch_pred[garch_valid]),
        "n_observations": int(garch_valid.sum()),
        "target": "20-day rolling realized volatility (std of simple returns)",
    }

    naive_errors = np.concatenate(per_model_actuals["naive"]) - np.concatenate(per_model_forecasts["naive"])
    dm_results = {}
    for model_name in ["arima", "lstm", "gru"]:
        model_errors = np.concatenate(per_model_actuals[model_name]) - np.concatenate(per_model_forecasts[model_name])
        valid = ~(np.isnan(naive_errors) | np.isnan(model_errors))
        dm_results[f"naive_vs_{model_name}"] = diebold_mariano(naive_errors[valid], model_errors[valid])

    all_regimes = pd.concat([rh["regimes"] for rh in regime_history])
    regime_distribution = all_regimes.value_counts(dropna=True).to_dict()
    latest_regime = all_regimes.dropna().iloc[-1] if all_regimes.dropna().size > 0 else None

    return {
        "ticker": ticker,
        "ohlcv": ohlcv,
        "n_windows": len(windows),
        "n_missing_ohlc_days": n_missing_days,
        "date_range": [str(ohlcv.index.min().date()), str(ohlcv.index.max().date())],
        "arima_orders": [list(o) for o in arima_orders],
        "lstm_window_lengths": lstm_lengths,
        "gru_window_lengths": gru_lengths,
        "metrics": metrics,
        "diebold_mariano": dm_results,
        "regime_distribution": {str(k): int(v) for k, v in regime_distribution.items()},
        "latest_regime": str(latest_regime) if latest_regime is not None else None,
        "final_lstm_artifact": final_lstm_artifact,
        "final_gru_artifact": final_gru_artifact,
    }


def main() -> None:
    from wealthpilot.config import get_settings
    from wealthpilot.db.session import get_engine
    from sqlalchemy.orm import Session

    t_start = time.time()
    settings = get_settings()
    engine = get_engine(settings.database_url)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}

    for ticker, name in INSTRUMENTS.items():
        print(f"=== {ticker} ({name}) ===", flush=True)
        t0 = time.time()
        result = run_asset(ticker)
        print(f"{ticker}: {result['n_windows']} windows in {time.time()-t0:.1f}s, "
              f"metrics={ {k: round(v.get('rmse', 0), 6) for k, v in result['metrics'].items()} }", flush=True)

        # A fresh session is opened per ticker (not once for the whole loop)
        # because each ticker's naive/ARIMA/GARCH/LSTM/GRU walk-forward run
        # takes several minutes of pure CPU work with zero DB activity —
        # Neon's serverless Postgres was observed dropping a connection left
        # idle that long, so a single shared session across all 5 tickers is
        # unreliable. Committing per ticker also checkpoints progress so a
        # later ticker's failure doesn't discard earlier tickers' results.
        with Session(engine) as session:
            n_upserted = upsert_market_data(session, ticker, result["ohlcv"])
            session.commit()
        print(f"{ticker}: upserted {n_upserted} market_data rows", flush=True)

        safe_ticker = ticker.replace("^", "")
        if result["final_lstm_artifact"] and result["final_lstm_artifact"].get("model") is not None:
            result["final_lstm_artifact"]["model"].save(MODELS_DIR / f"lstm_{safe_ticker}_{MODEL_VERSION}.keras")
            joblib.dump(result["final_lstm_artifact"]["scaler"], MODELS_DIR / f"lstm_{safe_ticker}_scaler_{MODEL_VERSION}.pkl")
        if result["final_gru_artifact"] and result["final_gru_artifact"].get("model") is not None:
            result["final_gru_artifact"]["model"].save(MODELS_DIR / f"gru_{safe_ticker}_{MODEL_VERSION}.keras")
            joblib.dump(result["final_gru_artifact"]["scaler"], MODELS_DIR / f"gru_{safe_ticker}_scaler_{MODEL_VERSION}.pkl")

        all_results[ticker] = {k: v for k, v in result.items() if k not in ("ohlcv", "final_lstm_artifact", "final_gru_artifact")}

        # Metrics are re-written after EVERY ticker (not just at the end) so
        # that a crash partway through the run still leaves a usable,
        # up-to-date metrics.json for whatever instruments finished.
        _write_metrics_json(all_results, t_start)

    print("done", flush=True)


def _write_metrics_json(all_results: dict, t_start: float) -> None:

    # Save a representative ARIMA/GARCH config summary as JSON (the actual
    # fitted statsmodels/arch objects are refit cheaply per-window and not
    # individually serialized — the walk-forward artifact IS the documented
    # order-selection methodology + per-window results, matching the
    # "fit only on training data, refit per fold" pattern already used for
    # Phase 3's preprocessing).
    config_path = MODELS_DIR / f"naive_arima_garch_config_{MODEL_VERSION}.json"
    config_path.write_text(
        json.dumps(
            {
                "naive": {"method": "constant return = 0"},
                "arima": {"order_selection": "AIC grid search, training data only, per window"},
                "garch": {"specification": "GARCH(1,1), zero mean, normal errors, returns scaled x100"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    regime_config_path = MODELS_DIR / f"regime_{MODEL_VERSION}.json"
    regime_config_path.write_text(
        json.dumps(
            {
                "window": 20,
                "volatility_percentile": 66,
                "trend_percentile": 66,
                "methodology": "training-window-only percentile thresholds, computed per walk-forward window",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    metrics_payload = {
        "market": {
            "model_version": MODEL_VERSION,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "data_source": "yfinance==" + library_versions()["yfinance"],
            "retrieval_timestamp": retrieval_timestamp(),
            "instruments": INSTRUMENTS,
            "data_start_requested": DATA_START,
            "target_definition": {
                "return": "simple return, close.pct_change()",
                "volatility": "20-day rolling realized volatility (std of simple returns)",
            },
            "forecast_horizon_days": FORECAST_HORIZON_DAYS,
            "walk_forward": {
                "initial_train_days": INITIAL_TRAIN_DAYS,
                "embargo_days": EMBARGO_DAYS,
                "test_window_days": TEST_WINDOW_DAYS,
                "methodology": "expanding window (train start fixed at 0, train end grows by "
                "test_window_days each cycle), fixed embargo gap between train end and test start",
            },
            "random_state": RANDOM_STATE,
            "library_versions": library_versions(),
            "results_by_instrument": all_results,
            "total_time_seconds": time.time() - t_start,
        }
    }

    existing = json.loads(METRICS_PATH.read_text(encoding="utf-8")) if METRICS_PATH.exists() else {}
    existing.update(metrics_payload)
    METRICS_PATH.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
