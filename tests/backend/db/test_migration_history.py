"""Alembic migration history — structural checks that need NO database.

These read `backend/alembic/versions/` through Alembic's own `ScriptDirectory`,
so they run even when the hosted database is unreachable. They prove the
revision graph is a single linear chain ending at the expected head; they do
NOT prove any database has been upgraded (that needs `alembic current` against
a reachable database, which is recorded separately in each phase report).
"""

from __future__ import annotations

import ast
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[3] / "backend"

PHASE_33_REVISION = "d2be70d8b07f"
PHASE_35_REVISION = "a7c41e9b6f30"
PHASE_36_REVISION = "c3e8f2a9d154"
B1_REVISION = "e5b1c7d93a20"  # Research Enhancement Track, Phase B1
SECURITY_REVISION = "f7a2d4b6c810"  # Sensitive-data protection prototype (ADR-047)


def _scripts() -> ScriptDirectory:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(config)


def test_there_is_exactly_one_head():
    """A second head would mean two migrations both claim to be "latest"."""
    assert _scripts().get_heads() == [SECURITY_REVISION]


def test_the_revision_chain_is_linear():
    scripts = _scripts()
    for revision in scripts.walk_revisions():
        down = revision.down_revision
        assert down is None or isinstance(down, str), f"{revision.revision} is a merge point"
        assert not revision.branch_labels, f"{revision.revision} carries a branch label"


def test_phase_35_revises_the_phase_33_head():
    assert _scripts().get_revision(PHASE_35_REVISION).down_revision == PHASE_33_REVISION


def _upgrade_calls(revision_id: str) -> list[tuple[str, list]]:
    """Every `op.<name>(...)` call inside `upgrade()`, with its literal arguments."""
    path = Path(_scripts().get_revision(revision_id).path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    calls = []
    for node in ast.walk(upgrade):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "op":
            literals = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
            calls.append((node.func.attr, literals))
    return calls


def test_phase_35_migration_is_purely_additive():
    """Phase 35 may only ADD columns (and one CHECK on a new column). It must not
    drop, rename or alter anything that already exists, and must not create a
    table (ADR-034: the Phase 33 tables are reused, not duplicated)."""
    calls = _upgrade_calls(PHASE_35_REVISION)
    assert {name for name, _ in calls} == {"add_column", "create_check_constraint"}
    forbidden = {"drop_column", "drop_table", "drop_constraint", "alter_column", "create_table", "rename_table", "execute"}
    assert not forbidden & {name for name, _ in calls}


def test_phase_35_migration_touches_only_the_four_household_financial_tables():
    touched = {literals[0] for name, literals in _upgrade_calls(PHASE_35_REVISION) if name == "add_column"}
    assert touched == {"household_incomes", "household_expenses", "household_assets", "household_liabilities"}


def test_phase_35_new_columns_are_all_nullable():
    """A NOT NULL column added to a populated table would need a backfill -- which
    would mean inventing a value. Every Phase 35 column is optional instead."""
    path = Path(_scripts().get_revision(PHASE_35_REVISION).path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    columns = [
        node for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Column"
    ]
    assert len(columns) == 7  # notes x4, description x2, interest_rate x1
    for column in columns:
        nullable = next((kw.value.value for kw in column.keywords if kw.arg == "nullable"), None)
        assert nullable is True, ast.unparse(column)
        assert not any(kw.arg in ("server_default", "default") for kw in column.keywords), ast.unparse(column)


def test_phase_35_downgrade_reverses_every_upgrade_step():
    path = Path(_scripts().get_revision(PHASE_35_REVISION).path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
    dropped = {
        tuple(arg.value for arg in node.args[:2] if isinstance(arg, ast.Constant))
        for node in ast.walk(downgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "drop_column"
    }
    added = set()
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    for node in ast.walk(upgrade):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_column":
            table = node.args[0].value
            column_call = node.args[1]
            added.add((table, column_call.args[0].value))
    assert dropped == added


# ----------------------------------------------------------------- Phase 36


def test_phase_36_revises_the_phase_35_head():
    assert _scripts().get_revision(PHASE_36_REVISION).down_revision == PHASE_35_REVISION


def test_phase_36_migration_creates_only_household_goals():
    """Exactly one new table and its household_id index -- nothing altered,
    dropped or executed, and no other table touched."""
    calls = _upgrade_calls(PHASE_36_REVISION)
    assert {name for name, _ in calls} == {"create_table", "create_index", "f"}
    assert [literals[0] for name, literals in calls if name == "create_table"] == ["household_goals"]
    forbidden = {"add_column", "drop_column", "drop_table", "alter_column", "drop_constraint", "rename_table", "execute"}
    assert not forbidden & {name for name, _ in calls}


def test_phase_36_downgrade_drops_exactly_what_it_created():
    calls = []
    path = Path(_scripts().get_revision(PHASE_36_REVISION).path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
    for node in ast.walk(downgrade):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "op":
            calls.append((node.func.attr, [a.value for a in node.args if isinstance(a, ast.Constant)]))
    assert ("drop_table", ["household_goals"]) in calls
    assert {name for name, _ in calls} <= {"drop_table", "drop_index", "f"}


def test_the_individual_goal_table_is_never_touched_by_a_household_migration():
    """`financial_goals` belongs to the individual pipeline; no Phase 33-36
    migration may operate on it. Checked against the migration's `op.*` call
    arguments, not its text -- a docstring may legitimately NAME the table in
    order to say it is not touched."""
    for revision in (PHASE_33_REVISION, PHASE_35_REVISION, PHASE_36_REVISION):
        for name, literals in _upgrade_calls(revision):
            assert "financial_goals" not in literals, (revision, name, literals)


def test_b1_revises_the_phase_36_head():
    assert _scripts().get_revision(B1_REVISION).down_revision == PHASE_36_REVISION


def test_b1_creates_only_the_monthly_records_table_and_touches_nothing_existing():
    """B1 is additive: its `upgrade()` creates one table and one index on it,
    and operates on no existing table (checked against the `op.*` call
    arguments, not the docstring, which may name tables to say they are
    untouched)."""
    calls = [(name, literals) for name, literals in _upgrade_calls(B1_REVISION) if name != "f"]  # op.f = index-name helper
    assert [name for name, _ in calls] == ["create_table", "create_index"]
    assert calls[0][1][0] == "monthly_financial_records"
    for name, literals in calls:
        for existing in ("customers", "financial_inputs", "financial_goals", "questionnaire_answers"):
            assert existing not in literals, (name, literals)


# ----------------------------------------------------------------- Sensitive-data protection (ADR-047)


def test_security_revision_revises_the_b1_head():
    assert _scripts().get_revision(SECURITY_REVISION).down_revision == B1_REVISION


def test_security_migration_creates_only_its_two_new_tables_and_touches_no_existing_data():
    """Two new tables and one index; nothing altered, dropped, rewritten or executed. In particular no existing
    column is encrypted or rewritten by the migration (the migration-safety requirement of ADR-047)."""
    calls = _upgrade_calls(SECURITY_REVISION)
    assert [literals[0] for name, literals in calls if name == "create_table"] == ["protected_records", "audit_ledger_events"]
    assert {name for name, _ in calls} <= {"create_table", "create_index", "f"}
    forbidden = {"add_column", "drop_column", "drop_table", "alter_column", "drop_constraint", "rename_table", "execute", "bulk_insert"}
    assert not forbidden & {name for name, _ in calls}


def test_security_downgrade_drops_exactly_what_it_created():
    path = Path(_scripts().get_revision(SECURITY_REVISION).path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
    dropped = [
        node.args[0].value
        for node in ast.walk(downgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "drop_table"
    ]
    assert sorted(dropped) == ["audit_ledger_events", "protected_records"]
