"""Naive baseline, ARIMA, and GARCH(1,1) — fit once per walk-forward
window on that window's training returns, then forecast the ENTIRE test
window in one multi-step call. This is standard, well-supported practice
for both `statsmodels` ARIMA and `arch` GARCH (`.forecast(steps=...)` /
`.forecast(horizon=...)`), and is honestly documented: multi-step forecasts
from a single fit converge toward the model's unconditional mean/long-run
variance over the horizon — expected, not a bug — rather than being
re-conditioned on realized data day-by-day (which LSTM/GRU do instead;
see dl_models.py, natural for sequence models and not natural for ARIMA/
GARCH without repeated re-fitting, which the walk-forward window boundaries
are what governs refitting frequency here, not daily).

Every forecast function takes ONLY the training slice of a window plus the
number of steps requested — never sees test-period data.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from arch import arch_model
from statsmodels.tsa.arima.model import ARIMA

ARIMA_ORDER_GRID = [(p, d, q) for p in range(3) for d in range(2) for q in range(3)]


def naive_forecast(train_returns: pd.Series, n_steps: int) -> np.ndarray:
    """PROJECT_PLAN.md section 2.4: 'Naive random walk | Return = 0' — the
    exact return-space equivalent of the classic price-level naive baseline
    (tomorrow's price = today's price). Constant, no state, no training
    data dependency beyond existing (kept as an argument for interface
    consistency with the other model functions)."""
    return np.zeros(n_steps)


def select_arima_order(train_returns: pd.Series) -> tuple[int, int, int]:
    """AIC-selected (p,d,q) over a small grid, TRAINING DATA ONLY —
    PROJECT_PLAN.md section 6.1: 'Order selected by AIC over a (p,d,q) grid'.
    """
    best_order = None
    best_aic = np.inf
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for order in ARIMA_ORDER_GRID:
            try:
                fitted = ARIMA(train_returns.to_numpy(), order=order).fit()
                if fitted.aic < best_aic:
                    best_aic = fitted.aic
                    best_order = order
            except Exception:
                continue
    if best_order is None:
        best_order = (1, 0, 0)  # last-resort fallback if every grid point fails to converge
    return best_order


def arima_forecast(train_returns: pd.Series, n_steps: int, order: tuple[int, int, int] | None = None):
    """Fit on training returns only; multi-step forecast for n_steps.
    Returns (forecast_array, order_used)."""
    if order is None:
        order = select_arima_order(train_returns)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = ARIMA(train_returns.to_numpy(), order=order).fit()
        forecast = fitted.forecast(steps=n_steps)
    return np.asarray(forecast), order


def garch_forecast(train_returns: pd.Series, n_steps: int):
    """GARCH(1,1) on training returns only. `arch` numerically prefers
    returns scaled to roughly O(1-10) (percentage points, not decimals) —
    documented here rather than left implicit: returns are multiplied by
    100 before fitting and the resulting variance forecast is divided by
    100^2 to convert back to the original (decimal-return) scale.
    Volatility target = conditional standard deviation of returns (sqrt of
    conditional variance), matching `preprocessing.compute_realized_
    volatility_target`'s definition (std of returns), so forecast and
    evaluation target are on the same scale and never compared to price
    levels.
    """
    scaled_returns = train_returns.to_numpy() * 100
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = arch_model(scaled_returns, vol="GARCH", p=1, q=1, mean="Zero", dist="normal")
        fitted = model.fit(disp="off")
        forecast = fitted.forecast(horizon=n_steps, reindex=False)
    variance_scaled = forecast.variance.to_numpy().flatten()
    volatility = np.sqrt(variance_scaled) / 100  # back to decimal-return scale
    return volatility
