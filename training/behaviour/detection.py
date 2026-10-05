"""Rolling z-score, CUSUM, and Isolation Forest behaviour-change detection
on the monthly FAR-Trans investment-activity panel (common.py).

**Temporal correctness**: every baseline (trailing mean/std) used by both
z-score and CUSUM is computed from a `shift(1)` series — i.e. strictly the
months BEFORE the one being scored, via a bounded trailing window — never
including the current month or any later one. A customer's first
`MIN_PRIOR_MONTHS` active months therefore get no z-score/CUSUM value
(NaN/0, documented, not fabricated) — there is no meaningful "norm" yet.

**Isolation Forest** is fit once on the full point-in-time-safe panel
(every row's own features already use only that row's own month, per
common.py's `build_monthly_panel`) — a population-level, cross-sectional
anomaly detector, not a per-customer forecast, so there is no equivalent
notion of "leaking a specific customer's future into their own past" the
way Phase 3's per-customer target-date leakage worked; it is analogous to
how Phase 4's classifiers were fit once on a population and applied per row.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from training.behaviour.common import MIN_PRIOR_MONTHS, PANEL_FEATURES, RANDOM_STATE

ROLLING_WINDOW_MONTHS = 12
Z_SCORE_ALERT_THRESHOLD = 2.0

# CUSUM parameters: k = allowance (in std units) before drift accumulates,
# h = decision threshold (in std units) before an alarm fires. These are
# standard, textbook default choices (Montgomery, "Introduction to
# Statistical Quality Control") — 0.5*sigma allowance, 5*sigma threshold —
# not fit to this data, since CUSUM's whole point is a fixed, interpretable
# reference rule; documented here rather than left unexplained.
CUSUM_K = 0.5
CUSUM_H = 5.0


def _trailing_baseline(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Trailing mean/std from strictly PRIOR values (shift(1) + a bounded
    rolling window), requiring at least MIN_PRIOR_MONTHS prior observations."""
    shifted = series.shift(1)
    trailing_mean = shifted.rolling(window=ROLLING_WINDOW_MONTHS, min_periods=MIN_PRIOR_MONTHS).mean()
    trailing_std = shifted.rolling(window=ROLLING_WINDOW_MONTHS, min_periods=MIN_PRIOR_MONTHS).std()
    return trailing_mean, trailing_std


def rolling_zscore(panel: pd.DataFrame, value_col: str) -> pd.Series:
    """Explicit per-customer loop + concat, deliberately NOT
    `groupby().apply()`: with certain group-count/shape combinations
    (verified directly — a single-customer panel is enough to trigger it),
    pandas' `apply` misinterprets a per-row Series return as a per-group
    scalar-like result and transposes the output into one row per customer
    with month-index values as columns, instead of concatenating normally.
    A plain loop has no such ambiguity.
    """
    pieces = []
    for _customer_id, group in panel.groupby("customerID"):
        group = group.sort_values("month")
        trailing_mean, trailing_std = _trailing_baseline(group[value_col])
        z = (group[value_col] - trailing_mean) / trailing_std.replace(0, np.nan)
        pieces.append(z)
    return pd.concat(pieces).reindex(panel.index)


def cusum(panel: pd.DataFrame, value_col: str, k: float = CUSUM_K, h: float = CUSUM_H) -> pd.DataFrame:
    """Two-sided CUSUM on the same trailing-baseline-standardized series
    the z-score uses. Returns a DataFrame with `cusum_pos`, `cusum_neg`,
    and `cusum_alarm` (True where |S| exceeds h) aligned to `panel`'s index.
    Uses the same explicit loop-and-concat pattern as `rolling_zscore`, for
    the same reason.
    """
    pieces = []
    for _customer_id, group in panel.groupby("customerID"):
        group = group.sort_values("month")
        trailing_mean, trailing_std = _trailing_baseline(group[value_col])
        standardized = (group[value_col] - trailing_mean) / trailing_std.replace(0, np.nan)

        pos = np.zeros(len(group))
        neg = np.zeros(len(group))
        for i in range(len(group)):
            s = standardized.iloc[i]
            if pd.isna(s):
                pos[i] = np.nan
                neg[i] = np.nan
                continue
            prev_pos = pos[i - 1] if i > 0 and not np.isnan(pos[i - 1]) else 0.0
            prev_neg = neg[i - 1] if i > 0 and not np.isnan(neg[i - 1]) else 0.0
            pos[i] = max(0.0, prev_pos + s - k)
            neg[i] = min(0.0, prev_neg + s + k)

        alarm = (pos > h) | (neg < -h)
        pieces.append(
            pd.DataFrame({"cusum_pos": pos, "cusum_neg": neg, "cusum_alarm": alarm}, index=group.index)
        )
    return pd.concat(pieces).reindex(panel.index)


def fit_isolation_forest(
    panel: pd.DataFrame, contamination: float = 0.05, n_estimators: int = 200
) -> tuple[IsolationForest, np.ndarray]:
    """Fit on the panel's point-in-time-safe features; returns the fitted
    model and per-row anomaly scores (lower = more anomalous, matching
    sklearn's `score_samples` convention)."""
    X = panel[PANEL_FEATURES].to_numpy()
    model = IsolationForest(
        contamination=contamination, n_estimators=n_estimators, random_state=RANDOM_STATE
    )
    model.fit(X)
    scores = model.score_samples(X)
    return model, scores


def detect_risk_profile_changes(customers: pd.DataFrame) -> pd.DataFrame:
    """Direct comparison of consecutive dated customer_information.csv rows
    per customer — flags a row where riskLevel or investmentCapacity
    differs from that SAME customer's immediately preceding dated row.
    Inherently point-in-time-safe: each comparison only ever looks
    backward to the previous snapshot, never forward.
    """
    df = customers.sort_values(["customerID", "timestamp"]).copy()
    df["prev_risk_level"] = df.groupby("customerID")["riskLevel"].shift(1)
    df["prev_investment_capacity"] = df.groupby("customerID")["investmentCapacity"].shift(1)
    df["risk_level_changed"] = df["prev_risk_level"].notna() & (df["riskLevel"] != df["prev_risk_level"])
    df["investment_capacity_changed"] = df["prev_investment_capacity"].notna() & (
        df["investmentCapacity"] != df["prev_investment_capacity"]
    )
    return df
