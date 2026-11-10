"""Run the real WealthPilot API against a throwaway LOCAL SQLite file, for browser and end-to-end checks with synthetic data only.

    python scripts/local_synthetic_backend.py --db <path-to-new-file>.db [--port 8000]

Why it exists: `.env` points `DATABASE_URL` / `TEST_DATABASE_URL` at the hosted Neon databases, and `uvicorn` reads it. This launcher puts a SQLite URL in the PROCESS environment before the
application is imported (process variables override `.env`), creates the tables from the SQLAlchemy models (no Alembic migration, no PostgreSQL), and serves the unchanged FastAPI app.
It also blanks `GEMINI_API_KEY` for the process, so nothing is sent to an external model. It refuses to run unless the effective database is SQLite, never reads or writes `.env`, and never contacts Neon. The file is created if missing and is yours to delete.

Limits (stated, not hidden): SQLite is not PostgreSQL. The PostgreSQL-only constructs found in the models (CHECKs using `extract(day from ...)`, `btrim` and `char_length`, and the partial unique index `uq_household_members_one_primary`) are translated or provided here, for SQLite only. The FAR-Trans and
market-data tables are EMPTY, so the parts of the analysis that need that data report it as unavailable. This is a development tool, not a test of the SQL in PostgreSQL.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def prepare_environment(db_path: Path) -> str:
    url = f"sqlite:///{db_path.resolve().as_posix()}"
    os.environ["DATABASE_URL"] = url
    os.environ["TEST_DATABASE_URL"] = url
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ["GEMINI_API_KEY"] = ""   # no external LLM call from this process: the explanation falls back to its templated restatement
    for extra in (str(REPO / "backend"), str(REPO)):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    return url


def install_sqlite_translations() -> int:
    """Translate PostgreSQL `extract(<field> from x)` inside CHECK constraints for SQLite, on this process's in-memory copy of the metadata only. The models, PostgreSQL DDL and migrations are unchanged."""
    import re

    from sqlalchemy import CheckConstraint, text

    from wealthpilot.db.models import Base

    fmt = {"year": "%Y", "month": "%m", "day": "%d"}
    pattern = re.compile(r"extract\(\s*(year|month|day)\s+from\s+([A-Za-z_][A-Za-z0-9_]*)\s*\)", re.IGNORECASE)
    changed = 0
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and "extract(" in str(constraint.sqltext).lower():
                rewritten = pattern.sub(lambda m: f"CAST(strftime('{fmt[m.group(1).lower()]}', {m.group(2)}) AS INTEGER)", str(constraint.sqltext))
                if "extract(" in rewritten.lower():
                    raise NotImplementedError(f"unsupported extract() in {constraint.name}")
                constraint.sqltext = text(rewritten)
                changed += 1
    return changed


def apply_sqlite_partial_indexes(metadata) -> int:  # noqa: ANN001
    """Give every index that is PARTIAL on PostgreSQL (`postgresql_where`) the same predicate for SQLite (`sqlite_where`). Without it SQLite builds a plain UNIQUE index over the same columns, which is a
    different (stricter) rule: `uq_household_members_one_primary` ("one PRIMARY member per household") became "one member per household", so a second member could never be added and every household had a single member.
    On this process's in-memory copy of the metadata only; the models, PostgreSQL DDL and migrations are unchanged."""
    changed = 0
    for table in metadata.tables.values():
        for index in table.indexes:
            predicate = index.dialect_options["postgresql"]["where"]
            if predicate is not None and index.dialect_options["sqlite"]["where"] is None:
                index.dialect_options["sqlite"]["where"] = predicate
                changed += 1
    return changed


def repair_sqlite_partial_indexes(engine, metadata) -> list[str]:  # noqa: ANN001
    """A throwaway file created by an earlier version of this launcher holds the plain UNIQUE index. Drop and recreate each such index with its predicate (the table's rows are kept; a UNIQUE index that is stricter than the
    partial one can only be dropped and rebuilt, never violated by existing rows). Returns the names rebuilt."""
    from sqlalchemy import text

    rebuilt: list[str] = []
    with engine.begin() as conn:
        for table in metadata.tables.values():
            for index in table.indexes:
                if index.dialect_options["postgresql"]["where"] is None or not index.name:
                    continue
                sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = :n"), {"n": index.name}).scalar()
                if sql is not None and " where " not in sql.lower():
                    conn.execute(text(f'DROP INDEX "{index.name}"'))
                    index.create(conn)
                    rebuilt.append(index.name)
    return rebuilt


def install_sqlite_functions() -> None:
    """Give every SQLite connection of this process the few PostgreSQL string functions the CHECK constraints use (`btrim`, `char_length`). PostgreSQL itself is untouched."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _register(dbapi_connection, _record):  # noqa: ANN001
        if dbapi_connection.__class__.__module__.startswith("sqlite3"):
            dbapi_connection.create_function("btrim", 1, lambda value: None if value is None else value.strip(), deterministic=True)
            dbapi_connection.create_function("btrim", 2, lambda value, chars: None if value is None else value.strip(chars), deterministic=True)
            dbapi_connection.create_function("char_length", 1, lambda value: None if value is None else len(value), deterministic=True)


def create_schema() -> list[str]:
    from sqlalchemy import inspect

    from wealthpilot.config import get_settings
    from wealthpilot.db.models import Base
    from wealthpilot.db.session import get_engine

    settings = get_settings()
    if not (settings.database_url.startswith("sqlite") and settings.test_database_url.startswith("sqlite")):
        raise SystemExit("REFUSED: the effective database is not SQLite; this launcher never runs against another database")
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        raise SystemExit("REFUSED: the engine is not SQLite")
    install_sqlite_functions()
    install_sqlite_translations()
    apply_sqlite_partial_indexes(Base.metadata)
    Base.metadata.create_all(engine)
    repair_sqlite_partial_indexes(engine, Base.metadata)
    return sorted(inspect(engine).get_table_names())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, required=True, help="path of the throwaway SQLite file (created if missing)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--prepare-only", action="store_true", help="create the schema and exit; do not serve")
    args = ap.parse_args(argv)
    if args.db.suffix != ".db" or REPO in args.db.resolve().parents and ".git" in args.db.parts:
        raise SystemExit("REFUSED: use a *.db path outside the repository's .git folder")
    url = prepare_environment(args.db)
    tables = create_schema()
    print(f"local synthetic backend: sqlite:///<file>, {len(tables)} tables; Neon is not configured for this process", flush=True)
    if args.prepare_only:
        return 0
    import uvicorn

    from wealthpilot.api.main import app

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
