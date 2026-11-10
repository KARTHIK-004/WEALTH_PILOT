"""Run WealthPilot's isolated database-backed tests against the Neon TEST database only (see docs/TEST_PLAN.md).

    python scripts/run_isolated_db_tests.py --preflight                     # resolve + report host and database; no database access, no tests
    python scripts/run_isolated_db_tests.py --preflight --check-connection   # also one read-only `select current_database()`
    python scripts/run_isolated_db_tests.py --suite api --suite db           # run selected suites (default: api, db, ingestion)
    python scripts/run_isolated_db_tests.py --suite api -- -k households     # extra pytest arguments after `--`
    python scripts/run_isolated_db_tests.py --alembic current                # read-only; ALEMBIC_TARGET=test is set for this command only
    python scripts/run_isolated_db_tests.py --alembic upgrade --confirm-migrate   # never automatic; needs the explicit flag

Safety: TEST_DATABASE_URL must resolve to database `neondb_test` on the expected Neon host, otherwise nothing runs (scripts/isolated_db/guard.py). The child process gets BOTH
TEST_DATABASE_URL and DATABASE_URL set to the test URL (so an unexpected use of DATABASE_URL still lands on the test database, never `neondb`); tests that use the development
database (`real_*` fixtures) are deselected. Nothing is printed that contains a URL or password. The runner never drops, truncates or migrates on its own.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

from isolated_db.guard import Target, UnsafeTargetError, keepalive_connect_args, parse_env_file, redact, resolve_target  # noqa: E402

SUITES = {
    "api": ("tests/backend/api",),
    "db": ("tests/backend/db",),
    "ingestion": ("tests/backend/data/test_ingestion.py",),
}
# API test files that use no database at all; skipped so "isolated database tests" means exactly that.
NOT_DATABASE_BACKED = (
    "tests/backend/api/test_health.py",
    "tests/backend/api/test_lifespan.py",
    "tests/backend/api/test_personalized_insights.py",
)
EXPECTED_HOST_ENV = "WEALTHPILOT_EXPECTED_TEST_DB_HOST"


def effective_value(name: str, environ: dict[str, str], env_file: dict[str, str]) -> str | None:
    """A process environment variable overrides .env, exactly like the application's Settings."""
    return environ.get(name) or env_file.get(name)


def resolve_from(environ: dict[str, str], env_file_values: dict[str, str], expected_host: str | None) -> tuple[Target, str]:
    test_url = effective_value("TEST_DATABASE_URL", environ, env_file_values)
    dev_url = effective_value("DATABASE_URL", environ, env_file_values)
    host = expected_host or environ.get(EXPECTED_HOST_ENV) or None
    return resolve_target(test_url, dev_url, host), test_url or ""


def pytest_command(suites: list[str], extra: list[str]) -> list[str]:
    paths: list[str] = []
    for name in suites:
        paths.extend(SUITES[name])
    ignores = [f"--ignore={p}" for p in NOT_DATABASE_BACKED]
    return [sys.executable, "-m", "pytest", "-p", "isolated_db.pytest_plugin", "-p", "no:cacheprovider", *paths, *ignores, *extra]


def child_environment(environ: dict[str, str], test_url: str, target: Target, connect_args: dict[str, int], *, alembic: bool = False) -> dict[str, str]:
    env = dict(environ)
    env["TEST_DATABASE_URL"] = test_url
    env["DATABASE_URL"] = test_url                      # an unexpected use of DATABASE_URL lands on the test database, never on neondb
    env["WEALTHPILOT_GUARD_HOST"] = target.host
    env["WEALTHPILOT_GUARD_DB"] = target.database
    env["WEALTHPILOT_GUARD_CONNECT_ARGS"] = json.dumps(connect_args)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(HERE), str(REPO), environ.get("PYTHONPATH", "")]))
    env.pop("ALEMBIC_TARGET", None)
    if alembic:
        env["ALEMBIC_TARGET"] = "test"                  # only for the alembic command
    return env


_PROBE = (
    "import os; from urllib.parse import urlsplit as u; from wealthpilot.config import get_settings as g; s=g(); a=u(s.test_database_url); b=u(s.database_url);"
    "h=os.environ['WEALTHPILOT_GUARD_HOST']; d=os.environ['WEALTHPILOT_GUARD_DB'];"
    "print(a.hostname==h and a.path.strip('/')==d and b.hostname==h and b.path.strip('/')==d)"
)


def effective_settings_match(env: dict[str, str]) -> bool:
    """Ask the application's own Settings (no database access) what both URLs resolve to in the environment the children will get."""
    out = subprocess.run([sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True, cwd=REPO)
    return out.stdout.strip() == "True"


def check_connection(test_url: str, target: Target) -> str:
    """One read-only `select current_database()`; returns the name, never raises with a URL in the message."""
    import psycopg

    try:
        with psycopg.connect(test_url, connect_timeout=20) as conn:
            conn.read_only = True
            return conn.execute("select current_database()").fetchone()[0]
    except Exception as exc:  # noqa: BLE001 - report the class only; driver messages can echo connection details
        raise UnsafeTargetError(f"read-only connection check failed ({type(exc).__name__})") from None


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--suite", action="append", choices=sorted(SUITES), help="suite to run (repeatable); default: all three")
    p.add_argument("--preflight", "--dry-run", dest="preflight", action="store_true", help="resolve and report the target; run nothing")
    p.add_argument("--check-connection", action="store_true", help="also run one read-only select current_database()")
    p.add_argument("--expected-host", help=f"expected Neon host (else ${EXPECTED_HOST_ENV}, else the host of DATABASE_URL)")
    p.add_argument("--env-file", default=str(REPO / ".env"), help="env file to read (process environment variables override it)")
    p.add_argument("--no-keepalive", action="store_true", help="do not add TCP keepalive arguments")
    for name, default in (("idle", 20), ("interval", 5), ("count", 3)):
        p.add_argument(f"--keepalive-{name}", type=int, default=default)
    p.add_argument("--keepalive-user-timeout-ms", type=int, default=30000)
    p.add_argument("--alembic", choices=["current", "upgrade"], help="run an alembic command against the test target")
    p.add_argument("--confirm-migrate", action="store_true", help="required for --alembic upgrade; the runner never migrates on its own")
    p.add_argument("pytest_args", nargs="*", help="extra pytest arguments (after `--`)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    environ = dict(os.environ if environ is None else environ)
    env_path = Path(args.env_file)
    env_file_values = parse_env_file(env_path.read_text(encoding="utf-8")) if env_path.is_file() else {}
    test_url = ""
    try:
        target, test_url = resolve_from(environ, env_file_values, args.expected_host)
        connect_args = keepalive_connect_args(
            not args.no_keepalive, keepalives_idle=args.keepalive_idle, keepalives_interval=args.keepalive_interval,
            keepalives_count=args.keepalive_count, tcp_user_timeout=args.keepalive_user_timeout_ms,
        )
        if args.alembic == "upgrade" and not args.confirm_migrate:
            raise UnsafeTargetError("alembic upgrade needs --confirm-migrate; the runner never migrates on its own")
    except (UnsafeTargetError, ValueError) as exc:
        print(f"PREFLIGHT FAILED: {redact(str(exc), test_url)}")
        return 2

    suites = args.suite or sorted(SUITES)
    child = child_environment(environ, test_url, target, connect_args, alembic=bool(args.alembic))
    settings_ok = effective_settings_match(child)
    print(f"preflight: {target.describe()}")
    print(f"preflight: effective application settings resolve to the same host and database: {settings_ok}")
    print(f"preflight: keepalive on test connection: {'off' if not connect_args else {k: v for k, v in connect_args.items()}}")
    print(f"preflight: suites={suites}; development-database tests are deselected; ALEMBIC_TARGET=test only for --alembic")
    if not settings_ok:
        print("PREFLIGHT FAILED: the application's effective settings do not resolve to the resolved test target")
        return 2
    if args.check_connection:
        try:
            name = check_connection(test_url, target)
        except UnsafeTargetError as exc:
            print(f"PREFLIGHT FAILED: {redact(str(exc), test_url)}")
            return 2
        if name != target.database:
            print("PREFLIGHT FAILED: the connected database is not the resolved test database")
            return 2
        print(f"preflight: read-only connection check ok, connected database = {name}")
    if args.alembic:
        command = [sys.executable, "-m", "alembic", args.alembic] + (["head"] if args.alembic == "upgrade" else [])
        print("$ " + " ".join(["ALEMBIC_TARGET=test", *command[1:]]))
        if args.preflight:
            print("preflight only: nothing executed")
            return 0
        return subprocess.run(command, env=child, cwd=REPO / "backend").returncode
    command = pytest_command(suites, args.pytest_args)
    print("$ " + " ".join(["pytest", *command[3:]]))
    if args.preflight:
        print("preflight only: nothing executed")
        return 0
    return subprocess.run(command, env=child, cwd=REPO).returncode


if __name__ == "__main__":
    raise SystemExit(main())
