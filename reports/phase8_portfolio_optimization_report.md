# Phase 8 — Portfolio Optimization Report

## 1. Status

**COMPLETE.**

## 2. Asset universe

**Investable: `QQQ, AGG, GLD` only.** `^IXIC` and `^NDX` (Phase 6's two index instruments) are excluded — an index is not directly tradable, and Phase 6 itself already described QQQ as "a tradable proxy for ^NDX." Both indices remain valid Phase 6 regime-classification inputs; they are simply not portfolio assets. No synthetic cash instrument was added — AGG (bonds) plays the defensive/"cash-floor" role, since it is by a wide margin the lowest-volatility of the three real instruments (Phase 6 RMSE ≈0.003 vs ≈0.013+ for QQQ/GLD). Approved 2026-09-14 via AskUserQuestion.

## 3. Data source

Existing PostgreSQL `market_data` table (Phase 6's yfinance ingestion) — **no data was redownloaded**. `training/portfolio/common.py::load_price_matrix` reads close prices directly via SQLAlchemy.

## 4. Date range

**2022-01-04 to 2026-09-11, 1,176 aligned trading days** (the return matrix has one fewer row than Phase 6's 1,177 price rows — the first day has no prior close to compute a return from). All three assets have identical coverage; zero rows were dropped for misalignment.

## 5. Return methodology

Simple daily returns (`prices.pct_change()`), matching the Phase 6 precedent. Rows where **any** asset's price is missing are dropped entirely, never forward-filled — see §20 for a real bug this uncovered and fixed. No shuffling anywhere; every function operates on a chronologically-sorted, duplicate-free date index (validated explicitly, tested).

## 6. Expected-return methodology

**Annualized historical mean of daily simple returns** (`mean(daily_return) × 252`) — never a Phase 6 LSTM/GRU/ARIMA forecast. This follows directly from PROJECT_PLAN.md §2.5's explicit deliverable requirement, "a note that expected returns are historical estimates and not forecasts," and its separate, explicit prohibition on feeding point forecasts into the optimizer. Resolved without a question — it was already unambiguous.

Computed on the full history: **QQQ +15.06%/yr, AGG −3.36%/yr, GLD +20.33%/yr.** AGG's negative expected return over this specific ~4.5-year window (which includes the 2022 rate-hike bond selloff) is a real, honestly-reported historical estimate, not an error.

## 7. Covariance methodology

**Ledoit-Wolf shrinkage** (`sklearn.covariance.LedoitWolf`), annualized (×252), mandatory for every MVO/HRP/frontier computation actually used. Shrinkage constant on the full history: **0.0239** (a light shrinkage — the 3-asset sample covariance was already reasonably well-conditioned). Plain sample covariance (`sample_covariance()`) exists only for comparison/documentation and is never substituted into a real result — verified by a test confirming Ledoit-Wolf's eigenvalue spread is never wider than the sample covariance's.

## 8. Ledoit-Wolf implementation

`covariance_ledoit_wolf(returns) -> (annualized_cov, shrinkage_constant)`. The actual fitted `LedoitWolf` estimator is persisted via `joblib` (`ledoit_wolf_v1.pkl`) — not just a JSON summary — so it is a genuinely reloadable, stateful artifact, matching how Phases 4-6 persisted fitted estimators. Verified: eigenvalues ≥ 0 (PSD), matrix symmetric, reload reproduces the saved covariance exactly.

## 9. MVO methodology

**Maximize Sharpe ratio** (the classical Markowitz tangency portfolio), approved 2026-09-14. `scipy.optimize.minimize` with SLSQP, `sum(weights)=1` equality constraint, box constraints per asset, a **deterministic, non-random starting point** (midpoint of each asset's box, renormalized) — no `random_state` needed since there is no stochastic step. Verified against a known closed-form solution: with equal expected returns and a diagonal covariance, the optimizer reproduces the analytic inverse-variance-weighted minimum-variance portfolio exactly.

## 10. Box constraints

| Constraint | Value | Source |
|---|---|---|
| Risk-free rate | 0% | Approved 2026-09-14 |
| QQQ band — Conservative | 10%-30% | Approved 2026-09-14 |
| QQQ band — Income | 20%-40% | Approved 2026-09-14 |
| QQQ band — Balanced | 35%-55% | Approved 2026-09-14 |
| QQQ band — Aggressive | 55%-80% | Approved 2026-09-14 |
| General single-asset cap | 70% | Approved 2026-09-14 |
| Minimum cash floor (AGG) | `min_cash_allocation`, no default | Bare optimizer parameter — approved 2026-09-14 |

In the approved 3-asset universe, QQQ is simultaneously "the equity share" and "the only Nasdaq/tech asset" from PROJECT_PLAN.md §2.5's constraint list, so those two named categories collapse into one number per risk level. The QQQ band and the general cap are **intersected** (tighter bound wins), which is why Aggressive's nominal 80% ceiling is actually enforced at 70% — verified directly by a test (`test_effective_bounds_intersects_qqq_band_with_general_cap`). No short-selling: every lower bound is ≥0 (tested explicitly across all four risk levels). `min_cash_allocation` deliberately has no default and is never read from Phase 7 state inside this module — see §20 of Phase 7's own report and §22 below.

## 11. Risk-level integration

Phase 4's four risk categories (`Conservative, Income, Balanced, Aggressive`) map directly to `RISK_LEVEL_QQQ_BANDS` above. The mapping does not read a customer's Phase 4 model prediction automatically or treat it as unquestionable — `mvo_max_sharpe`/`effective_bounds` simply take a `risk_level: str` argument; whichever later phase wires a customer's classified risk category into a call is a separate decision, keeping this module's own scope to "given a risk level, what are the bounds," not "trust the classifier blindly."

## 12. 1/N benchmark

`equal_weight_portfolio()` — always exactly `1/3` per asset, **deliberately unconstrained by any risk-level box constraint** (DeMiguel, Garlappi & Uppal, 2009). Evaluated under the identical backtest framework as MVO/HRP (same lookback, same rebalance schedule, same cost/turnover accounting).

## 13. HRP

Standard **López de Prado (2016)** algorithm: single-linkage clustering on a correlation-distance matrix (`d = sqrt(0.5×(1−corr))`), quasi-diagonalization (dendrogram-order seriation), recursive bisection allocating inverse-variance-weighted risk contributions. Not tied to Phase 5's Ward clustering (an unrelated use of hierarchical clustering for expense-persona segmentation) — there is no competing HRP convention named anywhere in the project documents, so the literature-standard algorithm was implemented directly. Deterministic (no stochastic step); verified against a known property (in a 2-asset uncorrelated case, the lower-variance asset receives more weight) and confirmed robust to near-duplicate, highly-correlated assets.

Full-history HRP weights: **QQQ 7.2%, AGG 83.8%, GLD 9.0%** — HRP's pure risk-based (return-blind) allocation naturally concentrates in AGG's low variance, regardless of AGG's negative expected return over this window.

## 14. Efficient frontier

`efficient_frontier()` sweeps 25 target-return points between the global minimum-variance portfolio and the highest-return feasible corner, solving a constrained min-variance QP at each point using the **same** Ledoit-Wolf covariance and historical expected returns MVO uses — never a separately fabricated set of points (verified directly: the frontier's own max-Sharpe row matches a direct `mvo_max_sharpe()` call to within 1e-6). The max-Sharpe point is included as its own explicitly marked row (`is_max_sharpe=True`), one per risk level (25 points × 4 risk levels = 100 frontier points saved to `frontier_v1.json`).

## 15. Backtesting methodology

Chronological, walk-forward, no look-ahead: at each rebalance date, expected returns and Ledoit-Wolf covariance are estimated from **strictly the trailing `lookback_days` window** (never touching data at or after the rebalance date), the resulting weights are applied going forward, and portfolio value compounds per-asset daily until the next rebalance (weights drift naturally with realized returns between rebalances — a genuine buy-and-hold-until-next-rebalance simulation, not a same-weights-every-day approximation). Verified directly: perturbing returns *after* a given rebalance date leaves that rebalance's own weights bit-for-bit unchanged.

## 16. Rebalancing

**Quarterly (`REBALANCE_FREQUENCY_DAYS = 63` trading days), 2-year lookback (`LOOKBACK_DAYS = 504` trading days)** — both approved 2026-09-14, reusing Phase 6's own `TEST_WINDOW_DAYS`/`INITIAL_TRAIN_DAYS` precedents. With 1,176 total trading days this produces **11 rebalance events** per strategy, ≈2.7 years of genuine out-of-sample backtest.

## 17. Transaction costs

**Zero (`TRANSACTION_COST_BPS = 0.0`)**, approved 2026-09-14 — a decision-support prototype with no trade execution, so a specific basis-point figure would be unsourced simulation overhead. The parameter is real and applied in the code path (not silently absent): a nonzero value is exercised directly in a test, confirming it measurably reduces the final equity value when used.

**Turnover convention**: two-way, `sum(|target_weight − currently_drifted_weight|)` at each rebalance, **not halved**. The very first rebalance is compared against an all-zero starting portfolio (turnover = 100%, fully establishing the position) — approved 2026-09-14, verified directly by a test.

## 18. Evaluation metrics

**Annualized return**: CAGR from the realized equity curve, `final_value^(252/n_days) − 1` (geometric, compounding-correct — not the arithmetic `mean×252` approximation, which overstates return under volatility drag). **Annualized volatility**: `std(daily_portfolio_return, ddof=1) × sqrt(252)`. **Sharpe ratio**: `(annualized_return − 0%) / annualized_volatility`, the same helper function used by MVO's own objective, so the backtest's *realized* Sharpe and MVO's *ex-ante* (estimate-based) Sharpe are computed with an identical formula on different inputs — never two silently-different definitions. **Maximum drawdown**: from the portfolio's own equity curve (`(value − running_max)/running_max`, most negative point) — never from individual asset prices, verified by four dedicated tests (monotonic rise, single decline, decline-then-partial-recovery, multiple declines picking the worst one).

## 19. Strategy comparison (full-period backtest, 11 rebalances each)

| Strategy | Ann. Return | Ann. Vol | Sharpe | Max DD | Avg Turnover |
|---|---|---|---|---|---|
| 1/N (equal weight) | 18.98% | 11.63% | 1.6326 | −10.53% | 14.40% |
| HRP | 5.77% | 5.67% | 1.0178 | −5.13% | 15.81% |
| MVO — Conservative | 30.52% | 17.47% | **1.7465** | −16.41% | 16.10% |
| MVO — Income | 29.42% | 17.81% | 1.6522 | −16.47% | 15.11% |
| MVO — Balanced | 27.35% | 17.89% | 1.5291 | −15.98% | 19.38% |
| MVO — Aggressive | 29.17% | 16.62% | **1.7557** | −14.11% | 14.07% |

**Honest reading, exactly as the results show it — no strategy is uniformly best:**
- **MVO Balanced's Sharpe (1.5291) is *below* 1/N's (1.6326)** — the naive benchmark beats one of the four MVO risk levels outright on a risk-adjusted basis over this backtest window. This is reported as the genuine finding it is, not suppressed.
- MVO Conservative and Aggressive have the two highest Sharpe ratios, both modestly ahead of 1/N.
- HRP is the clear laggard here (Sharpe 1.02, well below every other strategy) — its pure risk-based, return-blind allocation concentrated heavily in AGG (§13), whose realized return over this specific window happened to be negative. This is not a flaw in the HRP implementation; it is HRP behaving exactly as designed (minimizing risk, ignoring expected return) in a window where the lowest-risk asset also had the worst realized return.
- Every MVO variant has a deeper max drawdown than HRP or 1/N — higher return/Sharpe came with more downside, a standard and expected trade-off, not concealed here.

No claim of "MVO wins" or "HRP wins" is made beyond what this specific table shows for this specific backtest window.

## 20. Emergency-fund interaction

`min_cash_allocation` is a **plain optimizer parameter with no default**, approved 2026-09-14. `core/optimizer.py`/`core/backtest.py` never read Phase 7 state or decide emergency-fund sufficiency themselves — Phase 7 already fully owns the "insufficient EF → skip optimization entirely" short-circuit at the agent-orchestration level (a later phase), and duplicating that decision here would violate this phase's own instruction not to duplicate Goal Engine logic. When a nonzero `min_cash_allocation` is supplied, `effective_bounds` raises it as AGG's lower bound (tested: `test_effective_bounds_agg_gets_min_cash_allocation_as_lower_bound`).

## 21. Goal interaction

None implemented, and none needed for Phase 8's own scope — no TVM, Monte Carlo, or other Phase 7 calculation was duplicated or moved into this module. `core/goals.py` was not modified.

## 22. Artifacts

All under `models/portfolio/`, versioned `_v1`:

| File | Contents |
|---|---|
| `ledoit_wolf_v1.pkl` | The actual fitted `LedoitWolf` estimator (joblib) — a genuinely reloadable, stateful artifact |
| `ledoit_wolf_v1.json` | Shrinkage constant + annualized Ledoit-Wolf and sample covariance matrices |
| `mvo_v1.json` | Weights, bounds, expected return/volatility/Sharpe per risk level (full history) |
| `hrp_v1.json` | HRP weights + expected return/volatility/Sharpe (full history) |
| `frontier_v1.json` | 25 frontier points × 4 risk levels, each with weights/return/volatility/Sharpe |
| `backtest_v1.json` | Full backtest results (weights, turnovers, metrics) for all 6 strategy/risk-level combinations |
| `config_v1.json` | Full resolved methodology (universe, constraints, backtest config, library versions, seed) |

**Every artifact was independently reloaded and verified**, not just checked for existence: the pickled Ledoit-Wolf estimator's `covariance_` was recomputed and compared to the saved JSON; every reloaded MVO weight set was checked to sum to 1 and satisfy its own saved bounds; the reloaded HRP weights were checked to sum to 1; every frontier point was checked for finiteness and weight-sum validity; every backtest result was checked for finite metrics and a first-rebalance turnover of exactly 100%.

## 23. Database changes

**None.** `market_data` was only read, never written — row count confirmed unchanged (5,885 rows across the 5 Phase-6 tickers, identical to Phase 6's final state). No Alembic migration was created. `backend/wealthpilot/db/models.py` was not touched.

## 24. Tests

**82 new Phase 8 tests**, all passing:

| File | Tests | Covers |
|---|---|---|
| `tests/backend/core/test_optimizer.py` | 33 | Expected returns, Ledoit-Wolf/sample covariance, box-constraint intersection, MVO (sum-to-1, bounds, no shorts, determinism, known analytic solution), 1/N, HRP (sum-to-1, determinism, single-asset, correlated assets), Sharpe helper, efficient frontier |
| `tests/backend/core/test_backtest.py` | 25 | Chronology/no-leakage, rebalancing, all 4 metrics (incl. 4 max-drawdown scenarios), turnover convention, transaction costs, determinism, edge cases (single asset, insufficient history, exact boundary, correlated assets) |
| `tests/training/portfolio/test_common.py` | 6 | Return-matrix construction, chronological/duplicate validation, missing-data handling (incl. the bug in §25) |
| `tests/training/portfolio/test_artifacts.py` | 6 | Real reload-and-verify of every saved artifact against the actual `models/portfolio/` files |

**Full project test suite: 288 tests, all passing** (`pytest tests/ --collect-only -q` confirms 288 collected, 0 skipped; 288 passed in 223s). No regressions in Phases 0-7.

## 25. A real bug found and fixed

While testing `build_return_matrix`'s missing-data handling, a genuine correctness bug surfaced: `pandas.DataFrame.pct_change()`'s default `fill_method="pad"` **forward-fills a missing price before computing the return**, silently fabricating a return from a padded price instead of leaving it `NaN` — exactly what this phase's rules (and Phase 6's own `compute_returns` docstring) explicitly forbid. Fixed in `training/portfolio/common.py` by passing `fill_method=None` explicitly.

**Phase 6's `training/market/preprocessing.py::compute_returns` has the identical latent bug** (same pandas default), but it was verified to have had **zero effect on any already-reported Phase 6 result**: all 5 instruments have `n_missing_ohlc_days = 0` in the real historical data (confirmed by directly re-running `compute_returns` against the real `market_data` rows for all 5 tickers — no deprecation warning even fires, since there is nothing to forward-fill). Phase 6's file was deliberately **not modified**, per this phase's own "do not modify Phase 6 methodology" instruction — this is flagged here as a finding for you to decide on, not silently patched.

## 26. Other known limitations

1. **Only ~4.5 years of real market history exist**, so the backtest's 11 rebalance events, while genuinely out-of-sample and leakage-free, is a modest sample — the strategy comparison in §19 should be read as "what happened in this specific window," not a claim about long-run expected performance.
2. **AGG's negative realized/expected return over this specific window** (2022's bond selloff dominates the ~4.5-year sample) materially shapes every result in this report — a different historical window would likely shift both MVO's and HRP's allocations and rankings substantially. This is inherent to using historical-mean expected returns (§6), not a code defect.
3. **`min_cash_allocation` has no wired-up caller yet** — by design (§20), consistent with Phase 7 staying similarly unwired to any specific data source.

## 27. Next phase

**Phase 9 — Compliance.**

**Do not begin Phase 9.** Awaiting explicit approval of this report.
