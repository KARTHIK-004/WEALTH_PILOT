"""Market regime classification: Trending / Volatile / Range-bound.

**Methodology** (reproducible, training-data-only threshold derivation —
no hand-picked financial thresholds, per the explicit instruction that
unspecified thresholds must be either derived this way or asked about):

1. Rolling 20-day realized volatility (std of returns) and rolling 20-day
   trend strength (mean return over the window — sign gives direction,
   magnitude gives strength) are computed for every day (both train and
   test) using only trailing data (pandas `rolling()`, backward-looking by
   construction).
2. Classification thresholds (the 66th percentile of rolling volatility,
   and the 66th percentile of |rolling trend|) are computed from the
   TRAINING window ONLY, then applied unchanged to classify both training
   and test-period days — the test period's own volatility/trend
   distribution never influences the thresholds it is judged against.
3. A day is classified, in order:
   - **Volatile** if its rolling volatility exceeds the training-derived
     66th-percentile volatility threshold (checked first — high volatility
     can co-occur with apparent trend and should dominate the label, since
     "volatile" is the more actionable/risk-relevant signal for the
     constraint-bound adjustment this regime label is meant to feed later,
     per PROJECT_PLAN.md's "adjusts constraint bounds, never the return
     estimates").
   - **Trending** if not Volatile and |rolling trend| exceeds the
     training-derived 66th-percentile |trend| threshold.
   - **Range-bound** otherwise.

This regime label is a standalone classification output. It is NEVER used
here (or anywhere in Phase 6) to compute a portfolio weight, allocation, or
any optimization input — that is explicitly Phase 8's responsibility, and
PROJECT_PLAN.md's "Critical architectural constraint" (never feed point
forecasts into the optimizer; a regime label may only adjust constraint
bounds) governs how it may be used once Phase 8 exists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REGIME_WINDOW = 20
VOLATILITY_PERCENTILE = 66
TREND_PERCENTILE = 66


def compute_regime_features(returns: pd.Series) -> pd.DataFrame:
    rolling_vol = returns.rolling(window=REGIME_WINDOW, min_periods=REGIME_WINDOW).std()
    rolling_trend = returns.rolling(window=REGIME_WINDOW, min_periods=REGIME_WINDOW).mean()
    return pd.DataFrame({"rolling_vol": rolling_vol, "rolling_trend": rolling_trend})


def classify_regimes(
    features: pd.DataFrame, train_end_idx: int
) -> tuple[pd.Series, dict]:
    """`features` must be indexed 0..n-1 (positional), covering the full
    series (train + test). `train_end_idx` marks where training data ends
    — thresholds are computed ONLY from features.iloc[:train_end_idx].
    Returns (regime_series, thresholds_dict).
    """
    train_features = features.iloc[:train_end_idx].dropna()
    vol_threshold = float(np.percentile(train_features["rolling_vol"], VOLATILITY_PERCENTILE))
    trend_threshold = float(
        np.percentile(train_features["rolling_trend"].abs(), TREND_PERCENTILE)
    )

    def classify_row(row) -> str | float:
        if pd.isna(row["rolling_vol"]) or pd.isna(row["rolling_trend"]):
            return np.nan
        if row["rolling_vol"] > vol_threshold:
            return "Volatile"
        if abs(row["rolling_trend"]) > trend_threshold:
            return "Trending"
        return "Range-bound"

    regimes = features.apply(classify_row, axis=1)
    thresholds = {"volatility_threshold": vol_threshold, "trend_threshold": trend_threshold}
    return regimes, thresholds
