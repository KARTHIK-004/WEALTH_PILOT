"""scripts/run_isolated_db_tests.py and scripts/isolated_db/ -- the isolated-database runner's safety guard, preflight, command construction and pytest plugin.

Fully offline: every URL here is fake (a made-up host and password), `--env-file` points at a temporary file so the real `.env` is never read, and nothing connects to a database.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import run_isolated_db_tests as runner  # noqa: E402
from isolated_db import guard, pytest_plugin  # noqa: E402
from isolated_db.guard import Target, UnsafeTargetError, resolve_target  # noqa: E402

HOST = "ep-fake-host-123.c-2.us-east-2.aws.neon.tech"
PASSWORD = "Zq9fakePassword77"
TEST_URL = f"postgresql://fakeuser:{PASSWORD}@{HOST}/neondb_test?sslmode=require"
DEV_URL = f"postgresql://fakeuser:{PASSWORD}@{HOST}/neondb?sslmode=require"


def code_only(relative: str) -> str:
    """The file's executable code, lower-cased, without docstrings or comments (so wording in documentation cannot satisfy or trip a safety check)."""
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree).lower()


def env(**over):
    base = {"TEST_DATABASE_URL": TEST_URL, "DATABASE_URL": DEV_URL}
    base.update(over)
    return {k: v for k, v in base.items() if v is not None}


# ------------------------------------------------------------------ guard: what is accepted

def test_the_expected_test_database_on_the_dev_host_is_accepted_and_shows_no_secret():
    target = resolve_target(TEST_URL, DEV_URL)
    assert target == Target(host=HOST, database="neondb_test")
    for text in (target.describe(), repr(target), str(target)):
        assert PASSWORD not in text and "fakeuser" not in text and "postgresql://" not in text


def test_an_explicit_expected_host_replaces_the_development_url():
    assert resolve_target(TEST_URL, None, HOST).database == "neondb_test"
    with pytest.raises(UnsafeTargetError, match="differs from the expected host"):
        resolve_target(TEST_URL, DEV_URL, "ep-another.c-2.us-east-2.aws.neon.tech")


# ------------------------------------------------------------------ guard: what is refused (before any write)

@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_or_empty_configuration_is_refused(value):
    with pytest.raises(UnsafeTargetError, match="not set"):
        resolve_target(value, DEV_URL)


def test_the_development_database_is_refused_by_name():
    with pytest.raises(UnsafeTargetError, match="development database 'neondb'"):
        resolve_target(DEV_URL, DEV_URL)


@pytest.mark.parametrize("name", ["postgres", "neondb_test2", "NEONDB_TEST", "wealthpilot_test", "neondb_testing"])
def test_any_other_database_name_is_refused(name):
    with pytest.raises(UnsafeTargetError, match="exactly 'neondb_test'"):
        resolve_target(TEST_URL.replace("/neondb_test", f"/{name}"), DEV_URL)


@pytest.mark.parametrize("path", ["", "/", "/neondb_test/extra"])
def test_a_missing_or_multi_part_database_path_is_refused(path):
    url = f"postgresql://u:{PASSWORD}@{HOST}{path}"
    with pytest.raises(UnsafeTargetError, match="exactly one database"):
        resolve_target(url, DEV_URL)


@pytest.mark.parametrize("host", ["localhost", "db.example.com", "evil-neon.tech.example.org", "neon.tech"])
def test_unknown_hosts_are_refused(host):
    with pytest.raises(UnsafeTargetError, match="not a known Neon host"):
        resolve_target(f"postgresql://u:{PASSWORD}@{host}/neondb_test", DEV_URL)


def test_a_known_neon_host_that_is_not_the_expected_one_is_refused():
    other = TEST_URL.replace(HOST, "ep-other-456.c-2.us-east-2.aws.neon.tech")
    with pytest.raises(UnsafeTargetError, match="differs from the expected host"):
        resolve_target(other, DEV_URL)


def test_an_unconfirmable_host_is_ambiguous_and_refused():
    for dev in (None, "", "  "):
        with pytest.raises(UnsafeTargetError, match="cannot confirm the expected host"):
            resolve_target(TEST_URL, dev)


@pytest.mark.parametrize("query", ["dbname=neondb", "host=db.example.com", "hostaddr=10.0.0.1", "service=prod", "sslmode=require&DBNAME=neondb"])
def test_a_query_string_that_could_override_host_or_database_is_refused(query):
    with pytest.raises(UnsafeTargetError, match="ambiguous"):
        resolve_target(f"postgresql://u:{PASSWORD}@{HOST}/neondb_test?{query}", DEV_URL)


def test_several_hosts_unparsable_and_non_postgres_urls_are_refused():
    with pytest.raises(UnsafeTargetError, match="several hosts"):
        resolve_target(f"postgresql://u:{PASSWORD}@{HOST},other.neon.tech/neondb_test", DEV_URL)
    with pytest.raises(UnsafeTargetError, match="must be a PostgreSQL URL"):
        resolve_target(f"mysql://u:{PASSWORD}@{HOST}/neondb_test", DEV_URL)
    with pytest.raises(UnsafeTargetError, match="parseable"):
        resolve_target(f"postgresql://u:{PASSWORD}@{HOST}:notaport/neondb_test", DEV_URL)
    with pytest.raises(UnsafeTargetError, match="no host"):
        resolve_target("postgresql:///neondb_test", DEV_URL)
    with pytest.raises(UnsafeTargetError, match="DATABASE_URL"):
        resolve_target(TEST_URL, "not a url")


def test_no_error_message_ever_contains_the_password_or_a_url():
    bad = [(DEV_URL, DEV_URL), (TEST_URL.replace(HOST, "db.example.com"), DEV_URL), (f"postgresql://u:{PASSWORD}@{HOST}/neondb_test?dbname=x", DEV_URL), (f"mysql://u:{PASSWORD}@x/y", DEV_URL)]
    for test_url, dev in bad:
        with pytest.raises(UnsafeTargetError) as info:
            resolve_target(test_url, dev)
        message = str(info.value)
        assert PASSWORD not in message and "postgresql://" not in message and "fakeuser" not in message


def test_redact_removes_urls_and_given_secrets():
    text = f"failed for {TEST_URL} using {PASSWORD}"
    cleaned = guard.redact(text, PASSWORD)
    assert PASSWORD not in cleaned and "postgresql://" not in cleaned and "<url>" in cleaned


# ------------------------------------------------------------------ keepalive, fixtures, engine guard

def test_keepalive_arguments_are_configurable_validated_and_can_be_disabled():
    args = guard.keepalive_connect_args()
    assert args["keepalives"] == 1 and args["tcp_user_timeout"] == 30000 and args["connect_timeout"] == 20
    assert guard.keepalive_connect_args(keepalives_idle=45)["keepalives_idle"] == 45
    assert guard.keepalive_connect_args(False) == {}
    with pytest.raises(ValueError):
        guard.keepalive_connect_args(not_a_setting=1)
    with pytest.raises(ValueError):
        guard.keepalive_connect_args(keepalives_count=0)


def test_development_database_fixtures_are_recognised_and_ordinary_ones_are_not():
    assert guard.uses_development_database(["client", "real_client"]) and guard.uses_development_database(["real_session"])
    assert not guard.uses_development_database(["client", "db_session", "make_customer", "db_connection"])


def test_only_the_resolved_target_may_become_an_engine():
    target = Target(HOST, "neondb_test")
    guard.check_engine_target(HOST, "neondb_test", target)
    for host, database in ((HOST, "neondb"), ("other.neon.tech", "neondb_test"), (None, "neondb_test"), (HOST, None)):
        with pytest.raises(UnsafeTargetError, match="BLOCKED"):
            guard.check_engine_target(host, database, target)


def test_the_plugin_deselects_only_development_database_tests_and_changes_no_fixture():
    deselected = []
    config = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=lambda items: deselected.extend(items)))
    keep = SimpleNamespace(nodeid="a::t1", fixturenames=["client", "db_session"])
    drop = SimpleNamespace(nodeid="a::t2", fixturenames=["real_client", "real_db_session"])
    items = [keep, drop]
    pytest_plugin.pytest_collection_modifyitems(config, items)
    assert items == [keep] and deselected == [drop] and pytest_plugin.STATE["deselected"] == ["a::t2"]
    source = code_only("scripts/isolated_db/pytest_plugin.py")
    assert "rollback" not in source and "monkeypatch" not in source and "begin(" not in source and "fixture" not in source.replace("fixturenames", "")   # no fixture is redefined


def test_the_existing_rollback_fixtures_are_still_the_only_database_path():
    for conftest in ("tests/backend/conftest.py", "tests/backend/api/conftest.py"):
        text = (ROOT / conftest).read_text(encoding="utf-8")
        assert "outer_transaction.rollback()" in text and "create_savepoint" in text, conftest
    assert "settings.test_database_url" in (ROOT / "tests/backend/api/conftest.py").read_text(encoding="utf-8")


# ------------------------------------------------------------------ the CLI: preflight and command construction

def run_main(tmp_path, capsys, argv, environ):
    code = runner.main(["--env-file", str(tmp_path / "missing.env"), *argv], environ=environ)
    return code, capsys.readouterr().out


def test_preflight_reports_host_and_database_without_credentials_and_runs_nothing(tmp_path, capsys, monkeypatch):
    calls = []
    real_run = runner.subprocess.run
    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or real_run(cmd, **kw))   # only the settings probe may run
    code, out = run_main(tmp_path, capsys, ["--preflight"], env())
    assert code == 0, out
    assert f"host={HOST} database=neondb_test" in out and "resolve to the same host and database: True" in out and "preflight only: nothing executed" in out
    assert PASSWORD not in out and "postgresql://" not in out and "fakeuser" not in out
    assert len(calls) == 1 and calls[0][1] == "-c"                                                          # just the settings probe; no pytest, no alembic


@pytest.mark.parametrize("environ, reason", [
    (env(TEST_DATABASE_URL=None), "not set"),
    (env(TEST_DATABASE_URL=DEV_URL), "development database"),
    (env(TEST_DATABASE_URL=TEST_URL.replace(HOST, "db.example.com")), "not a known Neon host"),
    (env(DATABASE_URL=None), "cannot confirm the expected host"),
])
def test_unsafe_or_missing_configuration_stops_before_anything_runs(tmp_path, capsys, monkeypatch, environ, reason):
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("nothing may run when the target is unsafe"))
    code, out = run_main(tmp_path, capsys, [], environ)
    assert code == 2 and "PREFLIGHT FAILED" in out and reason in out
    assert PASSWORD not in out and "postgresql://" not in out


def test_the_env_file_is_read_but_the_process_environment_wins(tmp_path):
    values = guard.parse_env_file(f'# comment\nTEST_DATABASE_URL="{TEST_URL}"\nDATABASE_URL={DEV_URL}\n')
    target, url = runner.resolve_from({}, values, None)
    assert target.database == "neondb_test" and url == TEST_URL
    with pytest.raises(UnsafeTargetError, match="development database"):
        runner.resolve_from({"TEST_DATABASE_URL": DEV_URL}, values, None)


def test_a_mismatching_effective_settings_probe_stops_the_run(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(runner, "effective_settings_match", lambda child: False)
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    code, out = run_main(tmp_path, capsys, [], env())
    assert code == 2 and "do not resolve to the resolved test target" in out


def test_the_pytest_command_selects_isolated_suites_and_never_the_development_database_tests():
    command = runner.pytest_command(["api", "db", "ingestion"], ["-k", "households"])
    text = " ".join(command)
    for path in ("tests/backend/api", "tests/backend/db", "tests/backend/data/test_ingestion.py"):
        assert path in command
    for name in ("test_compliance_gate_safety", "test_financial_inputs_integration", "test_graph_execution", "test_graph_safety_contracts", "test_nodes", "test_recommendation_node", "tests/backend/agents"):
        assert name not in text
    for ignored in runner.NOT_DATABASE_BACKED:
        assert f"--ignore={ignored}" in command
    assert "-p" in command and "isolated_db.pytest_plugin" in command and command[-2:] == ["-k", "households"]
    assert "tests/backend/db" not in " ".join(runner.pytest_command(["api"], []))


def test_child_environment_pins_both_urls_to_the_test_database_and_sets_alembic_only_when_asked():
    target = Target(HOST, "neondb_test")
    base = {"ALEMBIC_TARGET": "dev", "PYTHONPATH": "x"}
    plain = runner.child_environment(base, TEST_URL, target, {"keepalives": 1})
    assert plain["TEST_DATABASE_URL"] == plain["DATABASE_URL"] == TEST_URL and "ALEMBIC_TARGET" not in plain
    assert plain["WEALTHPILOT_GUARD_HOST"] == HOST and plain["WEALTHPILOT_GUARD_DB"] == "neondb_test" and "x" in plain["PYTHONPATH"]
    assert runner.child_environment(base, TEST_URL, target, {}, alembic=True)["ALEMBIC_TARGET"] == "test"


def test_a_run_launches_pytest_with_the_pinned_environment_and_never_alembic(tmp_path, capsys, monkeypatch):
    launched = []
    monkeypatch.setattr(runner, "effective_settings_match", lambda child: True)
    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: launched.append((cmd, kw)) or SimpleNamespace(returncode=0))
    code, out = run_main(tmp_path, capsys, ["--suite", "db", "--keepalive-idle", "45", "--", "-x"], env())
    assert code == 0 and len(launched) == 1
    cmd, kw = launched[0]
    assert cmd[1:3] == ["-m", "pytest"] and "tests/backend/db" in cmd and cmd[-1] == "-x" and "alembic" not in cmd
    assert kw["env"]["DATABASE_URL"] == TEST_URL and "ALEMBIC_TARGET" not in kw["env"] and '"keepalives_idle": 45' in kw["env"]["WEALTHPILOT_GUARD_CONNECT_ARGS"]
    assert PASSWORD not in out and "postgresql://" not in out


def test_alembic_upgrade_is_never_automatic_and_current_sets_the_target_only_for_itself(tmp_path, capsys, monkeypatch):
    launched = []
    monkeypatch.setattr(runner, "effective_settings_match", lambda child: True)
    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: launched.append((cmd, kw)) or SimpleNamespace(returncode=0))
    code, out = run_main(tmp_path, capsys, ["--alembic", "upgrade"], env())
    assert code == 2 and "--confirm-migrate" in out and launched == []
    code, _ = run_main(tmp_path, capsys, ["--alembic", "current"], env())
    cmd, kw = launched[-1]
    assert code == 0 and cmd[1:] == ["-m", "alembic", "current"] and kw["env"]["ALEMBIC_TARGET"] == "test" and kw["cwd"].name == "backend"
    code, _ = run_main(tmp_path, capsys, ["--alembic", "upgrade", "--preflight", "--confirm-migrate"], env())
    assert code == 0 and len(launched) == 1                                                                 # preflight never executes the migration


def test_a_real_settings_probe_agrees_with_the_resolved_target_using_only_fake_urls():
    target = Target(HOST, "neondb_test")
    child = runner.child_environment(dict(__import__("os").environ), TEST_URL, target, {})
    assert runner.effective_settings_match(child) is True
    other = dict(child, WEALTHPILOT_GUARD_DB="neondb")
    assert runner.effective_settings_match(other) is False


def test_the_runner_never_drops_truncates_or_prints_urls():
    for name in ("scripts/run_isolated_db_tests.py", "scripts/isolated_db/guard.py", "scripts/isolated_db/pytest_plugin.py"):
        text = code_only(name)
        for word in ("drop database", "drop table", "truncate", "delete from", "create database"):
            assert word not in text, (name, word)
