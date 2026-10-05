# Phase 6 — Market Analysis Report

Trained 2026-09-14T09:08:46+00:00 (run start; final instrument, GLD, finished at trained_at above — `total_time_seconds` = 3734s ≈ 62.2 min for the full 5-instrument run). Model version `v1`.

## 1. Status

**COMPLETE.**

## 2. Data source

- **Provider**: `yfinance==0.2.66` (upgraded from 0.2.49 mid-phase — see §15 Limitations for why).
- **Retrieval timestamp**: 2026-09-14T09:08:46+00:00 (UTC; logged per-run in `metrics.json["market"]["retrieval_timestamp"]`).
- **Requested start date**: 2022-01-01 (`DATA_START`). End date: whatever the most recent trading day is at fetch time — no fixed end date, so the window grows on every re-run.
- OHLCV columns only (`open, high, low, close, volume`); `auto_adjust=False` so `close` is the raw close, not split/dividend-adjusted — consistent across all 5 instruments.

## 3. Market instruments

| Ticker | Description | Role |
|---|---|---|
| `^IXIC` | NASDAQ Composite | Broad equity index |
| `^NDX` | NASDAQ-100 | Large-cap equity index |
| `QQQ` | Invesco QQQ Trust | NASDAQ-100 ETF (tradable proxy for `^NDX`) |
| `AGG` | iShares Core U.S. Aggregate Bond ETF | Bond proxy |
| `GLD` | SPDR Gold Shares | Gold proxy |

Selection rationale (approved 2026-09-13 via `AskUserQuestion`, recorded in `training/market/common.py`'s module docstring): PROJECT_PLAN.md named NASDAQ-family equities explicitly but left the bond/gold proxy unspecified — AGG/GLD were chosen as the most liquid, widely-used single-ticker ETF proxies for each asset class rather than inventing a synthetic index.

## 4. Date coverage

All 5 instruments: **2022-01-03 to 2026-09-11**, **1,177 trading days** each. Identical coverage across instruments (yfinance returned no ticker-specific gaps beyond the shared market calendar).

## 5. Data-quality findings

- `n_missing_ohlc_days` (any of open/high/low/close null on a returned row): **0 for all 5 instruments.**
- No forward-filling or interpolation anywhere in the pipeline — `compute_returns` uses `pct_change()` directly on whatever rows yfinance returns, so a real exchange holiday (never inserted as a row) simply isn't a return observation, and a hypothetical missing trading day would surface as `n_missing_ohlc_days > 0` rather than being silently patched.
- Chronological order and duplicate-date checks (`validate_chronological_order`) ran against the real fetched data for all 5 instruments with no violations.

## 6. Return and volatility target definitions

- **Return target**: simple return, `close.pct_change()` — **not** log return (matches the precedent set in Phase 3's FAR-Trans return features).
- **Volatility target**: 20-day rolling realized volatility, `returns.rolling(20, min_periods=20).std()` — trailing-only by construction (`pandas.rolling`), so a value at date *t* never depends on returns after *t* (verified in `test_realized_volatility_target_uses_only_trailing_window`).
- **Forecast horizon**: 1 trading day (`FORECAST_HORIZON_DAYS = 1`), approved 2026-09-13.
- Models never target price levels — enforced by construction (every model consumes/produces `returns`, never `close`).

## 7. Preprocessing

- `training/market/preprocessing.py`: `compute_returns`, `compute_realized_volatility_target`, `validate_chronological_order`.
- No scaling/normalization at the returns-computation stage — scaling is local to the LSTM/GRU path only (see §11), fit per walk-forward window on that window's training slice.
- No preprocessing step reads beyond the current row's trailing window; verified by the leakage tests in §17.

## 8. Walk-forward validation methodology

Expanding window, never shuffled, never `KFold`/`StratifiedKFold`/random split:

| Parameter | Value |
|---|---|
| Initial training window | 504 trading days (~2 years) |
| Embargo gap | 5 trading days |
| Test window | 63 trading days (~1 quarter) |
| Train start | Fixed at index 0 for every window (expanding, not rolling) |
| Train end | Grows by `test_window_days` (63) each cycle |

With 1,177 observations this produces **10 windows** per instrument (`630` total test-day observations per instrument: `10 × 63`). Sizing was approved 2026-09-13 as an explicit walk-forward-config decision, chosen to yield roughly 10 windows given the ~4.5-year real data span.

## 9. Embargo methodology

A fixed 5-day gap is inserted between each window's `train_end` and `test_start` — those 5 days belong to neither the training nor the test set for that window (`test_train_and_test_never_overlap_and_test_never_precedes_train` proves train/embargo/test are pairwise disjoint and strictly ordered for every window). This absorbs the 1-day forecast horizon plus a safety margin so no test-window feature can leak backward into training through short lookback windows.

## 10. Model results by instrument

RMSE reported in return units (e.g. `0.0133` ≈ 1.33% daily return RMSE). GARCH's RMSE/MAE are against the volatility target (different units/scale from the return-forecast rows — never compared directly to naive/ARIMA/LSTM/GRU's numbers).

### Return-forecast models (naive / ARIMA / LSTM / GRU)

| Ticker | Model | RMSE | MAE | Directional accuracy |
|---|---|---|---|---|
| ^IXIC | naive | 0.013319 | 0.010081 | 0.0000 |
| ^IXIC | arima | 0.013308 | 0.010075 | 0.5683 |
| ^IXIC | lstm  | 0.013375 | 0.010122 | 0.5365 |
| ^IXIC | gru   | 0.013350 | 0.010111 | 0.5492 |
| ^NDX  | naive | 0.013358 | 0.010192 | 0.0000 |
| ^NDX  | arima | 0.013340 | 0.010178 | 0.5762 |
| ^NDX  | lstm  | 0.013421 | 0.010229 | 0.5238 |
| ^NDX  | gru   | 0.013384 | 0.010208 | 0.5460 |
| QQQ   | naive | 0.013305 | 0.010152 | 0.0000 |
| QQQ   | arima | 0.013287 | 0.010137 | 0.5746 |
| QQQ   | lstm  | 0.013340 | 0.010177 | 0.5381 |
| QQQ   | gru   | 0.013325 | 0.010169 | 0.5508 |
| AGG   | naive | 0.003117 | 0.002391 | 0.0000 |
| AGG   | arima | 0.003121 | 0.002396 | 0.4730 |
| AGG   | lstm  | 0.003129 | 0.002401 | 0.4825 |
| AGG   | gru   | 0.003140 | 0.002408 | 0.4698 |
| GLD   | naive | 0.013881 | 0.008991 | 0.0000 |
| GLD   | arima | 0.013863 | 0.008980 | 0.5667 |
| GLD   | lstm  | 0.013895 | 0.009001 | 0.5317 |
| GLD   | gru   | 0.013822 | 0.008954 | 0.5476 |

**Naive's directional accuracy is 0.0000 for every instrument by construction, not by poor performance**: naive always forecasts exactly `0`, and `directional_accuracy` (per its documented, conservative rule — see §16) counts a zero-valued prediction as a sign mismatch even against a zero-valued actual, since a `0` forecast carries no directional information to be "correct" about. Naive's RMSE/MAE — not its directional accuracy — are the fair comparison against the other models, and on that basis naive is statistically indistinguishable from ARIMA/LSTM/GRU on every instrument (§12).

### GARCH (volatility target: 20-day rolling realized volatility)

| Ticker | RMSE | MAE |
|---|---|---|
| ^IXIC | 0.009197 | 0.007823 |
| ^NDX  | 0.009127 | 0.007767 |
| QQQ   | 0.009145 | 0.007798 |
| AGG   | 0.001038 | 0.000842 |
| GLD   | 0.006079 | 0.004818 |

No naive volatility-forecast baseline was implemented to compare GARCH against (out of the specified scope — see §15). GARCH's numbers are reported in isolation, on their own target/units.

## 11. Model configuration detail

- **Naive**: constant `0` forecast, ignores training data entirely (`test_naive_forecast_ignores_training_data_content`).
- **ARIMA**: order selected per window by AIC grid search over `p∈[0,3), d∈[0,2), q∈[0,3)`, training data only. Selected order was **(0,0,0)** (pure white noise, no AR/MA/differencing structure) in all 10 windows for `^IXIC`, `^NDX`, and `QQQ`. `AGG` and `GLD` occasionally selected `(2,0,0)` or `(2,0,2)` in some windows — see full per-window list in `models/metrics.json["market"]["results_by_instrument"][ticker]["arima_orders"]`. A (0,0,0) selection is itself an honest, expected finding for near-efficient daily equity-index returns, not a bug.
- **GARCH(1,1)**: zero mean, normal innovations, training returns scaled ×100 before fitting for numerical stability (arch library convention), forecast variance scaled back down by ÷100² and square-rooted to volatility on the original return scale.
- **LSTM / GRU**: sequence length swept over `{20, 40, 60}` per window; the length with the lowest validation loss on that window's training split is used for the test window. Actual selections varied across windows and instruments (e.g. `^IXIC` LSTM: `[40,20,20,20,60,40,40,40,60,20]`) — full per-window lengths in `metrics.json`. `StandardScaler` fit on the training window only, applied to test-window inputs. Test-window evaluation is a **rolling 1-step-ahead** procedure: each day's prediction conditions on the real (realized) trailing `window_length`-day sequence, never on the model's own prior forecast.

## 12. Diebold-Mariano comparisons (vs. naive baseline)

Harvey-Leybourne-Newbold small-sample-corrected DM test, squared-error loss, all 630 test-day observations per instrument per comparison.

| Ticker | Comparison | DM statistic | p-value | Significant (p<0.05)? |
|---|---|---|---|---|
| ^IXIC | naive vs arima | 0.7834 | 0.4337 | No |
| ^IXIC | naive vs lstm  | -1.1787 | 0.2389 | No |
| ^IXIC | naive vs gru   | -0.7349 | 0.4627 | No |
| ^NDX  | naive vs arima | 1.0343 | 0.3014 | No |
| ^NDX  | naive vs lstm  | -1.2081 | 0.2274 | No |
| ^NDX  | naive vs gru   | -0.6076 | 0.5437 | No |
| QQQ   | naive vs arima | 1.0337 | 0.3017 | No |
| QQQ   | naive vs lstm  | -0.7920 | 0.4287 | No |
| QQQ   | naive vs gru   | -0.4901 | 0.6242 | No |
| AGG   | naive vs arima | -0.5229 | 0.6012 | No |
| AGG   | naive vs lstm  | -1.0463 | 0.2958 | No |
| AGG   | naive vs gru   | -1.8254 | 0.0684 | No |
| GLD   | naive vs arima | 0.5432 | 0.5872 | No |
| GLD   | naive vs lstm  | -0.1163 | 0.9075 | No |
| GLD   | naive vs gru   | 0.9556 | 0.3396 | No |

**No comparison, for any instrument, reaches statistical significance at p<0.05.** No model was retuned or re-run to try to force a different outcome — this is the result of the single, pre-specified methodology run once per instrument.

## 13. Market regime classification

Methodology: rolling 20-day realized volatility and rolling 20-day mean return computed for every day; classification thresholds are the 66th percentile of each, computed **only** from each window's training slice, then applied unchanged to that window's test days. Precedence: Volatile (vol > threshold) → Trending (not Volatile and |trend| > threshold) → Range-bound otherwise. Full methodology and rationale documented in `training/market/regime.py`'s module docstring.

| Ticker | Range-bound | Trending | Volatile | Latest regime |
|---|---|---|---|---|
| ^IXIC | 422 | 106 | 102 | Range-bound |
| ^NDX  | 437 | 94  | 99  | Volatile |
| QQQ   | 436 | 92  | 102 | Volatile |
| AGG   | 574 | 45  | 11  | Range-bound |
| GLD   | 145 | 127 | 358 | Volatile |

Counts are across all 630 test-period days per instrument (pooled across the 10 windows). AGG (bonds) is overwhelmingly Range-bound (91%) with almost no Volatile days (2%) — consistent with lower bond-market volatility. GLD (gold) is majority Volatile (57%) — consistent with pronounced gold-price swings over 2022-2026. This regime label is a standalone classification output only; it was never used anywhere in Phase 6 to compute a portfolio weight, allocation, or optimizer input.

## 14. Best-performing model

**No model significantly outperforms the naive (zero-return) baseline for 1-day-ahead return forecasting, on any of the 5 instruments.** ARIMA has a marginally lower point-estimate RMSE than naive on 4 of 5 instruments (all but AGG), and LSTM/GRU are marginally worse than naive on most instruments, but every Diebold-Mariano comparison is statistically insignificant (§12) — these differences are consistent with noise, not genuine predictive skill. This is an honest result consistent with near-efficient markets at a 1-day horizon and was not tuned or re-run to manufacture a different conclusion, per the explicit instruction not to artificially tune models until a complex model wins.

GARCH is reported on its own (volatility) target with no baseline comparator implemented (§15) and so is not part of this "best model" comparison.

## 15. Known limitations

1. **yfinance 0.2.49 → 0.2.66 upgrade required mid-phase.** 0.2.49's cookie/crumb auth bootstrap failed outright (`JSONDecodeError` on all 5 tickers); confirmed via raw `urllib` requests that the network and Yahoo endpoints were fine. Upgraded to the latest 0.2.x patch (not the newer 1.x major) after explicit approval; all 5 tickers verified working post-upgrade.
2. **No naive volatility-forecast baseline for GARCH.** GARCH's RMSE/MAE against realized volatility are reported in isolation, with no naive comparator (e.g., "forecast = training-window std") — this wasn't in the originally specified scope, so nothing was invented to fill the gap; flagged here rather than silently reported as if a comparison had been made.
3. **ARIMA/GARCH objects are not individually serialized.** Only a JSON summary of the order-selection/specification methodology is saved (`naive_arima_garch_config_v1.json`) — the per-window fitted statsmodels/arch objects are cheap to refit and were not pickled, consistent with the "fit only on training data, refit per fold" pattern already used in Phase 3's preprocessing. LSTM/GRU, which are far more expensive to refit, ARE fully serialized (§16).
4. **One training run crashed mid-way and had to be restarted.** The original run held a single SQLAlchemy session open across the entire ~62-minute, 5-instrument loop; Neon's serverless Postgres dropped the connection after ~9 minutes of CPU-bound training with no DB activity, crashing the process after only 2 of 5 instruments (`^IXIC`, `^NDX`) had trained (and `^NDX`'s results were lost since they were never committed). Fixed by opening a fresh session per ticker and committing (and re-writing `metrics.json`) after every instrument instead of once at the end — this was re-verified end-to-end on the restarted, successful run reported here. No modeling methodology changed; this was an infrastructure fix only.
5. **1,177 trading days (~4.5 years) is a fixed real-data span, not a fixed calendar cutoff** — `DATA_START=2022-01-01` was an implementation-judgment detail (approved 2026-09-13) chosen to yield roughly 10 walk-forward windows; a future re-run will pick up additional recent trading days and windows automatically.

## 16. Artifacts

All under `models/market/`, versioned `_v1`, gitignored except `models/metrics.json`:

| File pattern | Count | Contents |
|---|---|---|
| `lstm_{TICKER}_v1.keras` | 5 | Final window's fitted LSTM model per instrument |
| `lstm_{TICKER}_scaler_v1.pkl` | 5 | Matching `StandardScaler`, fit on that window's training returns only |
| `gru_{TICKER}_v1.keras` | 5 | Final window's fitted GRU model per instrument |
| `gru_{TICKER}_scaler_v1.pkl` | 5 | Matching `StandardScaler` |
| `naive_arima_garch_config_v1.json` | 1 | Naive/ARIMA/GARCH methodology summary |
| `regime_v1.json` | 1 | Regime classification thresholds/methodology |

**All 20 LSTM/GRU model+scaler pairs were independently reloaded** (`tf.keras.models.load_model` + `joblib.load`, in a fresh process, outside the training script) **and used to produce a real, finite prediction** — not just checked for file existence. Sample verification output (scaler mean/scale + one sample prediction per artifact) confirmed for all 5 tickers × 2 architectures.

## 17. Database changes

- Table: `market_data` (pre-existing schema from Phase 0/1, `UniqueConstraint("ticker", "date")` — no migration needed).
- **5,885 rows** total: 1,177 rows × 5 tickers, upserted via `INSERT ... ON CONFLICT (ticker, date) DO UPDATE`.
- **Idempotency directly re-verified**: re-ran `upsert_market_data` for `GLD` after the full run completed — row count unchanged (1,177 before, 1,177 after).
- No other table touched by Phase 6 code.

## 18. Tests

**51 Phase 6 tests, all passing** (`tests/training/market/`):

| File | Tests | Covers |
|---|---|---|
| `test_preprocessing.py` | 7 | Simple (not log) returns, no forward-fill, chronological/duplicate validation, trailing-only realized volatility |
| `test_walkforward.py` | 7 | Expanding windows, embargo enforcement, window sizing, no train/test overlap, edge cases |
| `test_models.py` | 9 | Naive determinism, ARIMA order selection/determinism, GARCH positivity/determinism/scale |
| `test_dl_models.py` | 6 | Chronological sequence construction, training-only scaler fitting, sequence-length selection, insufficient-data handling, rolling forecast uses real (not self-predicted) context |
| `test_evaluate.py` | 11 | RMSE/MAE correctness, directional accuracy incl. the zero-handling edge case, DM statistic/significance/symmetry |
| `test_regime.py` | 7 | Training-only threshold derivation, classification precedence, NaN handling, reproducibility |
| `test_artifacts.py` | 4 | LSTM/GRU/config/regime-JSON round-trips with real reload + prediction |

**Full project test suite: 123 tests, all passing** (`pytest tests/ --collect-only -q` confirms 123 collected, 0 skipped/deselected; 123 passed in 212s). No regressions in Phases 0-5.

## 19. Manual verification performed

- [x] Instruments match the approved set exactly (`^IXIC, ^NDX, QQQ, AGG, GLD`).
- [x] Return definition is simple `pct_change()`, confirmed by direct test against a hand-computed value.
- [x] Volatility target is 20-day trailing-only realized volatility, confirmed leakage-free by perturbation test.
- [x] Forecast horizon is 1 day throughout.
- [x] Embargo (5 days), initial train (504 days), test window (63 days) all match the approved config; 10 windows/instrument confirmed both by direct computation and by the actual run's logged `n_windows`.
- [x] ARIMA order selection uses AIC and training data only (per-window orders inspected — mix of `(0,0,0)` and occasional `(2,0,0)/(2,0,2)`, no hardcoded order).
- [x] GARCH scaling round-trip produces volatility on the original return scale (RMSE/MAE same order of magnitude as raw return std).
- [x] LSTM/GRU sequence length is swept over `{20,40,60}` and actually varies window-to-window (not fixed).
- [x] LSTM/GRU scaler is fit on training data only (test-only-value perturbation test).
- [x] Regime thresholds are computed from training data only per window (perturbation test) and never used to generate a portfolio weight anywhere in this phase's code.
- [x] No shuffled/K-fold/random split anywhere in `training/market/` — expanding-window walk-forward only.
- [x] `market_data` upsert is idempotent (directly re-verified post-run) and touches no other table.
- [x] Every LSTM/GRU artifact reloads in a fresh process and produces a finite prediction (20/20 verified).
- [x] `models/metrics.json` retains `risk`, `behaviour`, `expense` keys unmodified alongside the new `market` key.
- [x] Raw datasets (`datasets/raw/FAR-Trans/`, `datasets/raw/kaggle/`) untouched — modification timestamps (Sep 13 21:27-28) predate all Phase 6 work, and no Phase 6 code path reads `datasets/raw/` at all.
- [x] `random_state=42` used throughout (TensorFlow seed, present in `library_versions` log).
- [x] Library versions logged: Python 3.11.9, yfinance 0.2.66, scikit-learn 1.5.2, statsmodels 0.14.4, arch 7.1.0, TensorFlow 2.17.0, pandas 2.2.3, numpy 1.26.4.
- [x] Full project test suite (123 tests) passes with zero regressions.
- [x] DM results reported honestly, including the "no significant difference from naive" outcome, without retuning to force a different result.
- [x] Directional accuracy's zero-handling behavior audited against its own docstring during test-writing — a real discrepancy was found and fixed (see §20).
- [x] No trade execution, fund transfer, or brokerage integration anywhere in this phase.
- [x] No portfolio weight, allocation, or optimizer input computed anywhere in this phase — regime labels are a standalone classification output only.
- [x] Training is fully offline (`training/market/`) — nothing trains inside FastAPI/LangGraph/AutoGen/Gemini/React, none of which Phase 6 touched.
- [x] Training run is fully reproducible: naive/ARIMA/GARCH are deterministic given the same data; LSTM/GRU seeded via `tf.keras.utils.set_random_seed(42)`.

## 20. Code-correctness finding fixed during this phase

While writing `test_evaluate.py`, `directional_accuracy`'s own docstring ("zero-valued true/predicted returns are treated as a sign mismatch... never counted as a lucky correct call") did not match its implementation: `true_sign == pred_sign` would count a true-zero-vs-predicted-zero pair as a match, since `np.sign(0) == np.sign(0)`. Fixed in `training/market/evaluate.py` to explicitly exclude zero-sign matches (`(true_sign == pred_sign) & (true_sign != 0) & (pred_sign != 0)`), matching the already-documented, already-approved contract — not a new methodology decision. This directly affects how naive's `0.0000` directional accuracy in §10 should be read (see the note there).

## 21. Next phase

**Phase 7 — Goal Engine.**

**Do not begin Phase 7.** Awaiting explicit approval of this report.
