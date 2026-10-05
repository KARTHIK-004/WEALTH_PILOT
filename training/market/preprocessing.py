"""Return and volatility target construction.

Simple returns (`close.pct_change()`), per the Phase 3 precedent (see
common.py module docstring). Models never target price levels (CLAUDE.md
rule 6).

Missing observations (e.g. a market holiday yfinance doesn't return a row
for) are never forward-filled or fabricated — a missing date is simply
absent from the return series, which `pct_change()` handles correctly
since it operates on whatever rows exist, not on a fixed calendar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_returns(ohlcv: pd.DataFrame) -> pd.Series:
    """Simple daily returns from close prices. First observation is NaN
    (no prior close to compare to) — dropped by callers, not zero-filled.
    """
    return ohlcv["close"].pct_change().rename("return")


def compute_realized_volatility_target(returns: pd.Series, window: int = 20) -> pd.Series:
    """Rolling `window`-day realized volatility (std of simple returns) —
    the evaluation target for GARCH's volatility forecasts. Uses only
    trailing data (pandas' rolling() is backward-looking by construction:
    the value at date t uses returns[t-window+1 : t], never a future
    return), so this itself introduces no look-ahead. Reported at 1-day
    resolution but represents the trailing month, per standard practice —
    documented rather than left implicit.
    """
    return returns.rolling(window=window, min_periods=window).std().rename("realized_volatility")


def validate_chronological_order(index: pd.DatetimeIndex) -> None:
    if not index.is_monotonic_increasing:
        raise ValueError("Market data index is not in chronological order — refusing to proceed.")
    if index.has_duplicates:
        raise ValueError("Market data index has duplicate dates — refusing to proceed.")
