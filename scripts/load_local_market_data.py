"""Load real, public daily prices for the portfolio's asset universe (QQQ, AGG, GLD) into a LOCAL SQLite demo database.

    python scripts/load_local_market_data.py --db <file>.db [--snapshot <file>.csv] [--refresh]

Why this exists: the portfolio stage and the goal engine's Monte Carlo both read the `market_data` table, which the project fills from Yahoo Finance (Phase 6). A throwaway local demo database
(`scripts/local_synthetic_backend.py`) starts with that table EMPTY, so the portfolio is "unavailable" and compliance, which fails closed, rejects the missing weights. This loads the same
tickers with the project's own `fetch_ohlcv` (same start date and settings as Phase 6), so the existing pipeline can compute real results.

Safety: it takes a SQLite FILE path and builds its own engine on it. It never reads `.env` or the application settings, so it cannot reach `neondb` or `neondb_test`. It inserts only rows that are
missing (an existing (ticker, date) row is never overwritten), so a second run changes nothing. Only public price data is requested; no customer data leaves the machine.

`--snapshot` keeps a CSV copy (gitignored) so the demo can be rebuilt without the network; a snapshot is used when it exists unless `--refresh` is given. The data is a live download, so it differs
from the data the Phase 6 models were evaluated on (`models/metrics.json` records that run's retrieval time); allocations are computed from whatever history is loaded, as the plan intends
("expected returns are historical estimates, not forecasts").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for extra in (str(REPO / "backend"), str(REPO)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, func, insert, select  # noqa: E402

from wealthpilot.agents.nodes import ASSET_UNIVERSE  # noqa: E402
from wealthpilot.db.models import MarketData  # noqa: E402

DEFAULT_SNAPSHOT = REPO / "datasets" / "derived" / "market_data_snapshot_v1.csv"
COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]


def fetch_all() -> pd.DataFrame:
    from training.market.common import fetch_ohlcv  # the project's own Phase 6 fetch

    frames = []
    for ticker in ASSET_UNIVERSE:
        frame = fetch_ohlcv(ticker).reset_index()
        frame.insert(0, "ticker", ticker)
        frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
        frames.append(frame[COLUMNS])
    return pd.concat(frames, ignore_index=True)


def load_frame(snapshot: Path, refresh: bool) -> tuple[pd.DataFrame, str]:
    if snapshot.exists() and not refresh:
        return pd.read_csv(snapshot), f"snapshot {snapshot.name}"
    frame = fetch_all()
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(snapshot, index=False)
    return frame, "Yahoo Finance via training.market.common.fetch_ohlcv"


def insert_missing(db_path: Path, frame: pd.DataFrame) -> dict[str, int]:
    engine = create_engine(f"sqlite:///{db_path.resolve().as_posix()}")
    MarketData.__table__.create(engine, checkfirst=True)
    added: dict[str, int] = {}
    with engine.begin() as conn:
        for ticker, rows in frame.groupby("ticker"):
            have = {d.isoformat() if hasattr(d, "isoformat") else str(d) for (d,) in conn.execute(select(MarketData.date).where(MarketData.ticker == ticker))}
            fresh = [
                {"ticker": ticker, "date": pd.Timestamp(r.date).date(), "open": float(r.open), "high": float(r.high), "low": float(r.low), "close": float(r.close),
                 "volume": None if pd.isna(r.volume) else int(r.volume), "source": "yfinance"}
                for r in rows.itertuples() if str(r.date)[:10] not in have
            ]
            if fresh:
                conn.execute(insert(MarketData), fresh)
            added[str(ticker)] = len(fresh)
        totals = {t: n for t, n in conn.execute(select(MarketData.ticker, func.count()).group_by(MarketData.ticker))}
    engine.dispose()
    print("rows added:", added, "| rows now:", totals)
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, required=True, help="the SQLite demo database FILE (never a server URL)")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--refresh", action="store_true", help="download again even if a snapshot exists")
    args = parser.parse_args()
    if args.db.suffix.lower() not in {".db", ".sqlite", ".sqlite3"} or "://" in str(args.db):
        print("refusing: --db must be a path to a local SQLite file (.db/.sqlite)")
        return 2
    frame, origin = load_frame(args.snapshot, args.refresh)
    print(f"source: {origin}; {len(frame)} rows for {sorted(frame['ticker'].unique())}; {frame['date'].min()} .. {frame['date'].max()}")
    insert_missing(args.db, frame)
    return 0


if __name__ == "__main__":
    sys.exit(main())
