"""Shared utilities for Phase 8: loading `market_data` into an aligned
return matrix. Mirrors `training/market/common.py`'s module layout.

Uses the existing PostgreSQL `market_data` table populated in Phase 6 —
never redownloads or fabricates market data (rule enforced by this phase's
own instructions).
"""

from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models" / "portfolio"
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"
REPORTS_DIR = REPO_ROOT / "reports"


def load_price_matrix(session: Session, tickers: list[str]) -> pd.DataFrame:
    """Pivots `market_data` close prices into a date-indexed, ticker-column
    DataFrame. Column order matches `tickers` exactly."""
    from wealthpilot.db.models import MarketData

    stmt = (
        select(MarketData.ticker, MarketData.date, MarketData.close)
        .where(MarketData.ticker.in_(tickers))
        .order_by(MarketData.ticker, MarketData.date)
    )
    rows = session.execute(stmt).all()
    if not rows:
        raise RuntimeError(f"no market_data rows found for tickers {tickers}")

    df = pd.DataFrame(rows, columns=["ticker", "date", "close"])
    prices = df.pivot(index="date", columns="ticker", values="close").astype(float).sort_index()
    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        raise RuntimeError(f"market_data has no rows for {missing}")
    return prices[tickers]


def build_return_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Chronological, aligned, simple daily returns. Rows where ANY asset
    is missing are dropped entirely (never forward-filled or imputed) so
    every remaining row is a genuine, fully-aligned trading day across all
    assets."""
    if not prices.index.is_monotonic_increasing:
        raise ValueError("prices index must be chronologically sorted")
    if prices.index.has_duplicates:
        raise ValueError("prices index has duplicate dates")
    # fill_method=None is required: pandas' default (fill_method="pad")
    # forward-fills missing prices BEFORE computing pct_change, silently
    # fabricating a return from a padded price instead of leaving it NaN.
    return prices.pct_change(fill_method=None).dropna(how="any")


def library_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
    }


def retrieval_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
