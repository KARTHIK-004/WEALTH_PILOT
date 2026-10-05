"""Phase 8 — chronological portfolio backtest.

Pure, DB-free (same design as `core/optimizer.py` and Phase 7's
`core/goals.py`): takes a plain return matrix, returns a plain result.

At every rebalance date the strategy is re-estimated using ONLY the
trailing `lookback_days` window strictly before that date (no future
leakage — CLAUDE.md rule 6), the resulting weights are applied going
forward to the next `rebalance_days` of realized returns (buy-and-hold
between rebalances: daily portfolio value compounds per-asset, so weights
drift naturally with realized returns until the next rebalance resets
them), and turnover is measured against wherever the portfolio has
actually drifted to by that point — not against the previous rebalance's
original target.

Documented methodology decisions (approved via AskUserQuestion on
2026-09-14, alongside Phase 8's other methodology questions):

- **Rebalance frequency**: quarterly, `REBALANCE_FREQUENCY_DAYS = 63`
  trading days — matches Phase 6's own `TEST_WINDOW_DAYS`.
- **Lookback window**: 2 years, `LOOKBACK_DAYS = 504` trading days —
  matches Phase 6's own `INITIAL_TRAIN_DAYS`. Chosen (over a longer
  window) because only ~4.5 years / 1,177 trading days of real data exist
  (Phase 6), and a 2-year lookback leaves ~2.7 years / ~11 rebalance
  events of genuine out-of-sample backtest instead of a much thinner
  sample.
- **Transaction costs**: zero (`TRANSACTION_COST_BPS = 0.0`) — this is a
  decision-support prototype with no trade execution (rule 10), so a
  specific basis-point cost figure would be unsourced simulation overhead.
  The parameter still exists and is actually applied in the code path (not
  silently absent), so the zero is a documented, deliberate value, not an
  oversight — a nonzero value is exercised directly in tests.
- **Turnover convention**: two-way, `sum(|target_weight - current_drifted_weight|)`
  at each rebalance, NOT halved. The very first rebalance is compared
  against an all-zero starting portfolio, so its turnover is 100% (fully
  establishing the initial position).
- **Annualized return**: CAGR from the realized equity curve,
  `(final_value / 1.0) ** (252 / n_days) - 1` — the geometric, compounding-
  correct definition matching what the backtest actually realized, not the
  arithmetic `mean(daily_return) * 252` approximation (which overstates
  return under volatility drag).
- **Maximum drawdown**: computed from the portfolio's own equity curve
  (`(value - running_max) / running_max`, most negative point), never from
  individual asset prices.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from wealthpilot.core.optimizer import (
    RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    covariance_ledoit_wolf,
    effective_bounds,
    equal_weight_portfolio,
    expected_returns_historical,
    hrp_weights,
    mvo_max_sharpe,
    sharpe_ratio,
)

REBALANCE_FREQUENCY_DAYS = 63
LOOKBACK_DAYS = 504
TRANSACTION_COST_BPS = 0.0

STRATEGIES = ("mvo", "equal_weight", "hrp")


@dataclass
class BacktestResult:
    strategy: str
    risk_level: str | None
    equity_curve: pd.Series
    rebalance_dates: list
    rebalance_weights: list[dict[str, float]]
    turnovers: list[float]
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    average_turnover: float
    total_transaction_cost: float
    n_rebalances: int
    lookback_days: int
    rebalance_frequency_days: int
    transaction_cost_bps: float

    def to_summary_dict(self) -> dict:
        """JSON-safe summary (equity curve/dates dropped to keep the
        artifact compact; weights and metrics are kept in full)."""
        return {
            "strategy": self.strategy,
            "risk_level": self.risk_level,
            "n_rebalances": self.n_rebalances,
            "lookback_days": self.lookback_days,
            "rebalance_frequency_days": self.rebalance_frequency_days,
            "transaction_cost_bps": self.transaction_cost_bps,
            "annualized_return": self.annualized_return,
            "annualized_volatility": self.annualized_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "average_turnover": self.average_turnover,
            "total_transaction_cost": self.total_transaction_cost,
            "final_equity_value": float(self.equity_curve.iloc[-1]) if len(self.equity_curve) else 1.0,
            "rebalance_dates": [str(d) for d in self.rebalance_dates],
            "rebalance_weights": self.rebalance_weights,
            "turnovers": self.turnovers,
        }


def _resolve_target_weights(
    strategy: str,
    train_returns: pd.DataFrame,
    assets: list[str],
    risk_level: str | None,
    risk_free_rate: float,
    min_cash_allocation: float,
) -> pd.Series:
    if strategy == "equal_weight":
        return equal_weight_portfolio(assets)
    if strategy == "hrp":
        return hrp_weights(train_returns)
    if strategy == "mvo":
        if risk_level is None:
            raise ValueError("risk_level is required for strategy='mvo'")
        mu = expected_returns_historical(train_returns)
        cov, _ = covariance_ledoit_wolf(train_returns)
        bounds = effective_bounds(risk_level, assets=assets, min_cash_allocation=min_cash_allocation)
        return mvo_max_sharpe(mu, cov, bounds, risk_free_rate)
    raise ValueError(f"unknown strategy {strategy!r}; expected one of {STRATEGIES}")


def run_backtest(
    returns: pd.DataFrame,
    strategy: str,
    risk_level: str | None = None,
    lookback_days: int = LOOKBACK_DAYS,
    rebalance_days: int = REBALANCE_FREQUENCY_DAYS,
    risk_free_rate: float = RISK_FREE_RATE,
    transaction_cost_bps: float = TRANSACTION_COST_BPS,
    min_cash_allocation: float = 0.0,
) -> BacktestResult:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; expected one of {STRATEGIES}")
    if lookback_days <= 0 or rebalance_days <= 0:
        raise ValueError("lookback_days and rebalance_days must be positive")
    assets = list(returns.columns)
    if len(assets) == 0:
        raise ValueError("returns must have at least one asset column")

    n_obs = len(returns)
    if n_obs <= lookback_days:
        raise ValueError(
            f"not enough observations ({n_obs}) for lookback_days={lookback_days}; "
            "no rebalance date has a full trailing lookback window"
        )

    rebalance_indices = list(range(lookback_days, n_obs, rebalance_days))
    if not rebalance_indices:
        raise ValueError("no rebalance dates fall within the available data")

    current_weights = pd.Series(0.0, index=assets)  # all-zero starting portfolio (approved convention)
    portfolio_value = 1.0

    daily_values: list[float] = []
    daily_dates: list = []
    rebalance_weights_log: list[dict[str, float]] = []
    rebalance_dates_log: list = []
    turnovers: list[float] = []
    total_transaction_cost = 0.0

    for k, reb_idx in enumerate(rebalance_indices):
        train = returns.iloc[reb_idx - lookback_days : reb_idx]  # strictly trailing, no future leakage
        target = _resolve_target_weights(strategy, train, assets, risk_level, risk_free_rate, min_cash_allocation)
        target = target.reindex(assets).fillna(0.0)

        turnover = float((target - current_weights).abs().sum())
        turnovers.append(turnover)
        rebalance_weights_log.append(target.to_dict())
        rebalance_dates_log.append(returns.index[reb_idx])

        cost = turnover * (transaction_cost_bps / 10_000.0)
        total_transaction_cost += cost * portfolio_value
        portfolio_value *= 1.0 - cost

        next_reb_idx = rebalance_indices[k + 1] if k + 1 < len(rebalance_indices) else n_obs
        period_returns = returns.iloc[reb_idx:next_reb_idx]

        position_values = target * portfolio_value
        for date, day_returns in period_returns.iterrows():
            position_values = position_values * (1.0 + day_returns.reindex(position_values.index).fillna(0.0))
            day_total = float(position_values.sum())
            daily_values.append(day_total)
            daily_dates.append(date)

        if len(period_returns) > 0:
            portfolio_value = float(position_values.sum())
            current_weights = position_values / portfolio_value if portfolio_value > 0 else target
        else:
            current_weights = target

    equity_curve = pd.Series(daily_values, index=daily_dates)
    n_days = len(equity_curve)
    if n_days == 0:
        raise RuntimeError("backtest produced no evaluation days")

    daily_portfolio_returns = equity_curve.pct_change().dropna()
    final_value = float(equity_curve.iloc[-1])
    annualized_return = final_value ** (TRADING_DAYS_PER_YEAR / n_days) - 1.0
    annualized_volatility = float(daily_portfolio_returns.std(ddof=1)) * np.sqrt(TRADING_DAYS_PER_YEAR) if n_days > 1 else 0.0
    sr = sharpe_ratio(annualized_return, annualized_volatility, risk_free_rate)

    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown = float(drawdown.min())

    return BacktestResult(
        strategy=strategy,
        risk_level=risk_level,
        equity_curve=equity_curve,
        rebalance_dates=rebalance_dates_log,
        rebalance_weights=rebalance_weights_log,
        turnovers=turnovers,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sr,
        max_drawdown=max_drawdown,
        average_turnover=float(np.mean(turnovers)),
        total_transaction_cost=total_transaction_cost,
        n_rebalances=len(rebalance_indices),
        lookback_days=lookback_days,
        rebalance_frequency_days=rebalance_days,
        transaction_cost_bps=transaction_cost_bps,
    )
