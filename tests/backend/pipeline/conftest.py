"""End-to-end fixtures for the demo personas: the REAL application, models and FAR-Trans data on a throwaway SQLite file.

No hosted database, no network, no Gemini: the key is blanked for the module and the database is a file in pytest's temp directory. The only synthetic piece is the
`market_data` table, which holds TEST-ONLY deterministic prices (source tag `synthetic_test_fixture`) because the real prices come from Yahoo Finance and are not
committed. Assertions in this package therefore check wiring, contracts and rules, never a value that depends on the prices.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, MetaData, create_engine, event, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from seed_demo_data import ALL_DEMO_PERSONAS, PIPELINE_HOUSEHOLD, seed_persona, setup_family  # noqa: E402
from wealthpilot.api.dependencies import get_session  # noqa: E402
from wealthpilot.api.main import app  # noqa: E402
from wealthpilot.config import get_settings  # noqa: E402
from wealthpilot.db.base import Base  # noqa: E402
from wealthpilot.db.models import MarketData  # noqa: E402

_EXTRACT = re.compile(r"extract\(\s*(year|month|day)\s+from\s+([A-Za-z_][A-Za-z0-9_]*)\s*\)", re.IGNORECASE)
_FORMATS = {"year": "%Y", "month": "%m", "day": "%d"}


def sqlite_metadata() -> MetaData:
    """A COPY of the application's metadata whose PostgreSQL-only CHECKs are rewritten for SQLite. The shared metadata is not touched, so no other test sees a change."""
    copy = MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(copy)
    for table in copy.tables.values():
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and "extract(" in str(constraint.sqltext).lower():
                constraint.sqltext = text(_EXTRACT.sub(lambda m: f"CAST(strftime('{_FORMATS[m.group(1).lower()]}', {m.group(2)}) AS INTEGER)", str(constraint.sqltext)))
        for index in table.indexes:
            # An index that is PARTIAL on PostgreSQL (`uq_household_members_one_primary`: one PRIMARY member per household) must keep its predicate on SQLite, or it silently becomes
            # "one member per household" and a household can never have a second member.
            if index.dialect_options["postgresql"]["where"] is not None:
                index.dialect_options["sqlite"]["where"] = index.dialect_options["postgresql"]["where"]
    return copy


def synthetic_prices() -> list[dict]:
    """Deterministic test-only price paths for the portfolio's three tickers (never presented as real data)."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2022-01-03", periods=1000)
    drift_vol = {"QQQ": (0.0006, 0.017), "AGG": (0.0001, 0.003), "GLD": (0.0003, 0.008)}
    rows: list[dict] = []
    for ticker, (mu, sigma) in drift_vol.items():
        close = 100 * np.exp(np.cumsum(rng.normal(mu, sigma, len(dates))))
        for day, price in zip(dates, close):
            rows.append({"ticker": ticker, "date": day.date(), "open": float(price), "high": float(price), "low": float(price), "close": float(price), "volume": 1000, "source": "synthetic_test_fixture"})
    return rows


@dataclass
class World:
    client: TestClient
    engine: object
    ids: dict[str, int]          # demo key -> customer id
    results: dict[str, dict]     # demo key -> the default POST /api/analysis response
    link: object                 # the seed's one direct write (risk_inputs.external_customer_id), bound to this database
    household: dict              # the report of the full-pipeline household's first `setup_family` (household id, what was created)


def _link_through(engine):
    def link(customer_id: int, external_customer_id: str) -> None:
        with engine.begin() as conn:
            conn.execute(text("UPDATE customers SET risk_inputs = :v WHERE id = :id"), {"id": customer_id, "v": f'{{"external_customer_id": "{external_customer_id}"}}'})

    return link


@pytest.fixture(scope="module")
def world(tmp_path_factory) -> World:
    patcher = pytest.MonkeyPatch()
    patcher.setenv("GEMINI_API_KEY", "")  # nothing may be sent to an external model from this module
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path_factory.mktemp('pipeline') / 'demo.db'}", connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def _functions(dbapi_connection, _record):  # noqa: ANN001 - the string functions the CHECK constraints use
        dbapi_connection.create_function("btrim", 1, lambda v: None if v is None else v.strip(), deterministic=True)
        dbapi_connection.create_function("btrim", 2, lambda v, c: None if v is None else v.strip(c), deterministic=True)
        dbapi_connection.create_function("char_length", 1, lambda v: None if v is None else len(v), deterministic=True)

    sqlite_metadata().create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with maker() as session:
        session.execute(MarketData.__table__.insert(), synthetic_prices())
        session.commit()

    def override_session():
        db = maker()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app, raise_server_exceptions=False)
    link = _link_through(engine)
    ids, results = {}, {}
    for persona in ALL_DEMO_PERSONAS:
        ids[persona["demo_key"]] = seed_persona(client, persona, link_risk_data=link)["customer_id"]
    for key, customer_id in ids.items():
        response = client.post("/api/analysis", json={"profile_id": customer_id})
        assert response.status_code == 200, response.text
        results[key] = response.json()
    household = setup_family(client, PIPELINE_HOUSEHOLD)      # the household of E and its partner F, built AFTER the analyses so a test can show it changed none of them
    try:
        yield World(client, engine, ids, results, link, household)
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()
        patcher.undo()
        get_settings.cache_clear()
