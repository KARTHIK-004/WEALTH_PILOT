"""RMSE, MAE, directional accuracy, and Diebold-Mariano forecast-comparison
metrics for return forecasts. Volatility evaluation (GARCH vs. realized
volatility) uses only RMSE/MAE, per PROJECT_PLAN.md — directional accuracy
and DM comparisons are defined for return forecasts, not applied to
incompatible volatility-vs-volatility comparisons without care (DM here is
only ever run between two return-forecast error series on the exact same
dates, never mixing a return-error series with a volatility-error series).
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Share of forecasts whose SIGN matches the realized return's sign —
    evaluated against a 50% coin flip, per PROJECT_PLAN.md section 2.4.
    Zero-valued true/predicted returns are treated as a sign mismatch
    (conservative — never counted as a "lucky" correct call), including the
    case where BOTH are exactly zero: `np.sign(0) == np.sign(0)` would
    otherwise count that as a match, so it is excluded explicitly."""
    true_sign = np.sign(y_true)
    pred_sign = np.sign(y_pred)
    is_match = (true_sign == pred_sign) & (true_sign != 0) & (pred_sign != 0)
    return float(np.mean(is_match))


def diebold_mariano(errors_a: np.ndarray, errors_b: np.ndarray, loss: str = "squared") -> dict:
    """DM test comparing model A vs model B's 1-step-ahead forecast errors
    on the SAME dates. Positive DM statistic -> A's losses are larger
    (worse) than B's on average. Uses the Harvey-Leybourne-Newbold (1997)
    small-sample correction, standard practice for finite samples.
    """
    if loss == "squared":
        loss_a, loss_b = errors_a**2, errors_b**2
    elif loss == "absolute":
        loss_a, loss_b = np.abs(errors_a), np.abs(errors_b)
    else:
        raise ValueError(f"unknown loss '{loss}'")

    d = loss_a - loss_b
    n = len(d)
    d_mean = np.mean(d)
    d_var = np.var(d, ddof=1)

    if d_var == 0 or n < 2:
        return {"dm_statistic": 0.0, "p_value": 1.0, "n_obs": int(n), "note": "zero variance or too few observations"}

    dm_stat = d_mean / np.sqrt(d_var / n)
    # Harvey-Leybourne-Newbold small-sample correction (h=1 horizon).
    correction = np.sqrt((n + 1) / n)
    dm_stat_corrected = dm_stat * correction
    p_value = 2 * (1 - stats.t.cdf(np.abs(dm_stat_corrected), df=n - 1))

    return {"dm_statistic": float(dm_stat_corrected), "p_value": float(p_value), "n_obs": int(n)}
