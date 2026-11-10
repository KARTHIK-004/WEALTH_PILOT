"""`scripts/local_synthetic_backend.py` (the throwaway SQLite launcher used for local demos and browser checks): the PostgreSQL-only PARTIAL unique index
`uq_household_members_one_primary` ("one PRIMARY member per household") must keep its predicate on SQLite. Without it SQLite builds a plain UNIQUE index on `household_id`,
which means "one member per household": a second member could never be added, so no demo household could have two members (ADR-051). Each test runs the launcher in its own process
(`--prepare-only`, a file in pytest's temp directory), so no engine, environment variable or metadata of this test process is touched. No network, no hosted database."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import Column, Index, Integer, MetaData, String, Table, text

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "scripts" / "local_synthetic_backend.py"
INDEX = "uq_household_members_one_primary"
sys.path.insert(0, str(ROOT / "scripts"))

import local_synthetic_backend as launcher  # noqa: E402


def prepare(db: Path) -> None:
    done = subprocess.run([sys.executable, str(LAUNCHER), "--db", str(db), "--prepare-only"], capture_output=True, text=True, timeout=180, cwd=ROOT)
    assert done.returncode == 0, done.stderr[-800:]


def index_sql(db: Path) -> str:
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (INDEX,)).fetchone()[0]


def test_a_predicate_of_a_postgresql_partial_index_is_given_to_sqlite():
    metadata = MetaData()
    table = Table("t", metadata, Column("id", Integer, primary_key=True), Column("group_id", Integer), Column("role", String))
    Index("one_primary", table.c.group_id, unique=True, postgresql_where=text("role = 'primary'"))
    Index("plain", table.c.group_id)
    assert launcher.apply_sqlite_partial_indexes(metadata) == 1                  # only the partial one is changed; applying twice changes nothing more
    assert launcher.apply_sqlite_partial_indexes(metadata) == 0
    by_name = {i.name: i for i in table.indexes}
    assert str(by_name["one_primary"].dialect_options["sqlite"]["where"]) == "role = 'primary'" and by_name["plain"].dialect_options["sqlite"]["where"] is None


def test_the_launcher_creates_the_household_index_with_its_predicate(tmp_path):
    db = tmp_path / "launch.db"
    prepare(db)
    sql = index_sql(db)
    assert "UNIQUE" in sql and "WHERE" in sql.upper() and "role = 'primary'" in sql


def test_a_file_made_by_an_older_launcher_is_repaired_and_keeps_its_rows(tmp_path):
    db = tmp_path / "old.db"
    prepare(db)
    with sqlite3.connect(db) as conn:                                              # what the earlier launcher made: a plain unique index over household_id
        conn.execute(f"DROP INDEX {INDEX}")
        conn.execute(f"CREATE UNIQUE INDEX {INDEX} ON household_members (household_id)")
        conn.execute("INSERT INTO households (id, name) VALUES (1, 'kept')")
    assert "WHERE" not in index_sql(db).upper()
    prepare(db)                                                                    # starting the launcher again rebuilds the index
    assert "role = 'primary'" in index_sql(db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT name FROM households").fetchall() == [("kept",)]


def test_the_partial_index_allows_many_members_and_one_primary_only(tmp_path):
    db = tmp_path / "rules.db"
    prepare(db)
    with sqlite3.connect(db) as conn:
        columns = [r[1] for r in conn.execute("PRAGMA table_info(household_members)")]
        assert {"household_id", "customer_id", "relationship", "role", "is_dependent"} <= set(columns)
        conn.execute("INSERT INTO households (id, name) VALUES (1, 'h')")
        for customer_id in (1, 2, 3):
            conn.execute("INSERT INTO customers (id, name, data_source) VALUES (?, ?, ?)", (customer_id, f"c{customer_id}", "synthetic_test_fixture"))

        def member(customer_id: int, relationship: str, role: str) -> None:
            conn.execute("INSERT INTO household_members (household_id, customer_id, relationship, role, is_dependent) VALUES (1, ?, ?, ?, ?)",
                         (customer_id, relationship, role, 1 if role == "dependent" else 0))

        member(1, "self", "primary")
        member(2, "spouse", "member")                                             # a second member of the same household
        member(3, "child", "dependent")                                           # and a third
        try:
            conn.execute("INSERT INTO household_members (household_id, customer_id, relationship, role, is_dependent) VALUES (1, 4, 'self', 'primary', 0)")
        except sqlite3.IntegrityError:
            pass
        else:  # pragma: no cover - only reached if a second primary is accepted
            raise AssertionError("a second primary was accepted")
