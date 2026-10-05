"""Shared utilities for Phase 6 market analysis.

**Instruments** (^IXIC, ^NDX, QQQ specified by PROJECT_PLAN.md; AGG bond
proxy and GLD gold proxy decided explicitly with the user 2026-09-14, since
PROJECT_PLAN.md only said "appropriate bond/gold proxy" without naming
tickers).

**Data source**: yfinance only (`yfinance==0.2.66` — bumped from the
originally-pinned 0.2.49 this phase; see backend/pyproject.toml for why).
FAR-Trans's close_prices.csv is close-only and is never used here or
treated as OHLCV.

**Return definition**: simple returns (`pct_change()`), matching the
precedent already established in Phase 3's
`backend/wealthpilot/data/preprocessing.py` (`_risk_exposure_features`),
inspected before choosing rather than picked independently.

**Forecast horizon**: 1 trading day ahead — decided explicitly with the
user, matching PROJECT_PLAN.md's own naive-baseline framing ("tomorrow's
closing price as today's").

**Walk-forward configuration**: decided explicitly with the user —
~504 trading days (2 years) initial training window, 5-trading-day embargo,
~63-trading-day (3-month) test windows, expanding chronologically. Data is
fetched from 2022-01-01 (not the full available history back to 2015) —
this specific total-history choice was left to implementation judgment when
the window/embargo/horizon framework was approved; it caps the walk-forward
run at roughly 10 windows per asset (50 fits per model family across all 5
assets) to stay within CPU-only compute (PROJECT_PLAN.md's "Compute"
section anticipates LSTM/GRU taking "a few minutes per asset" — a run large
enough to take hours would contradict that expectation), while still being
genuine, multi-window, chronological validation.
"""

from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import statsmodels
import yfinance as yf
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models" / "market"
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"
REPORTS_DIR = REPO_ROOT / "reports"

RANDOM_STATE = 42

INSTRUMENTS = {
    "^IXIC": "NASDAQ Composite",
    "^NDX": "NASDAQ-100",
    "QQQ": "Invesco QQQ Trust (NASDAQ-100 ETF)",
    "AGG": "iShares Core U.S. Aggregate Bond ETF (bond proxy)",
    "GLD": "SPDR Gold Shares (gold proxy)",
}

DATA_START = "2022-01-01"
FORECAST_HORIZON_DAYS = 1

# Walk-forward configuration (all in trading days).
INITIAL_TRAIN_DAYS = 504
EMBARGO_DAYS = 5
TEST_WINDOW_DAYS = 63


def fetch_ohlcv(ticker: str, start: str = DATA_START) -> pd.DataFrame:
    """Read-only fetch from yfinance. Returns a DataFrame indexed by date
    with columns open/high/low/close/volume (lowercase, matching the
    market_data DB schema)."""
    df = yf.download(ticker, start=start, progress=False, auto_adjust=False)
    if df.empty:
        raise RuntimeError(f"yfinance returned no data for {ticker} from {start}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.index.name = "date"
    return df


def upsert_market_data(session: Session, ticker: str, ohlcv: pd.DataFrame, source: str = "yfinance") -> int:
    """Idempotent upsert into the market_data table, keyed on the existing
    (ticker, date) unique constraint from Phase 1 — no new migration
    needed. Re-running this with the same data is a no-op (ON CONFLICT
    DO UPDATE with the same values); re-running with refreshed data updates
    existing rows rather than duplicating them.
    """
    from wealthpilot.db.models import MarketData

    rows = [
        {
            "ticker": ticker,
            "date": idx.date(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]) if pd.notna(row["volume"]) else None,
            "source": source,
        }
        for idx, row in ohlcv.iterrows()
    ]
    if not rows:
        return 0

    stmt = pg_insert(MarketData).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "date"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "source": stmt.excluded.source,
        },
    )
    session.execute(stmt)
    session.flush()
    return len(rows)


def walk_forward_windows(
    n_obs: int,
    initial_train: int = INITIAL_TRAIN_DAYS,
    embargo: int = EMBARGO_DAYS,
    test_window: int = TEST_WINDOW_DAYS,
) -> list[dict]:
    """Expanding-window walk-forward split with an embargo gap.

    Window i: train = [0, train_end_i), embargo = [train_end_i,
    train_end_i + embargo), test = [train_end_i + embargo, train_end_i +
    embargo + test_window). The train END expands by test_window each
    cycle; train START is always 0 (expanding, not rolling).
    """
    windows = []
    train_end = initial_train
    while train_end + embargo + test_window <= n_obs:
        test_start = train_end + embargo
        test_end = test_start + test_window
        windows.append(
            {
                "train_start": 0,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
            }
        )
        train_end += test_window
    return windows


def library_versions() -> dict[str, str]:
    import arch
    import tensorflow as tf
    import xgboost  # noqa: F401 -- not used here, kept for a consistent version report shape

    return {
        "python": platform.python_version(),
        "yfinance": yf.__version__,
        "scikit-learn": sklearn.__version__,
        "statsmodels": statsmodels.__version__,
        "arch": arch.__version__,
        "tensorflow": tf.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }


def retrieval_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
