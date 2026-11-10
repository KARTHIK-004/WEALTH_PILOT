"""pytest plugin for the isolated database runner (loaded with `-p isolated_db.pytest_plugin`; configured only through environment variables the runner sets for the child process).

1. Deselects every test whose fixtures reach the development database (`real_*`).
2. Wraps `wealthpilot.db.session.create_engine`: any engine that is not exactly the resolved test target raises, and the TEST connection gets the configured TCP keepalive arguments.
It never changes a fixture, a test or a rollback, and prints counts only (no URL, no password).
"""

from __future__ import annotations

import json
import os

from isolated_db.guard import Target, check_engine_target, redact, uses_development_database

STATE = {"engines": 0, "blocked": 0, "deselected": []}


def pytest_configure(config):
    import wealthpilot.db.session as session_module
    from sqlalchemy.engine import make_url

    target = Target(host=os.environ["WEALTHPILOT_GUARD_HOST"], database=os.environ["WEALTHPILOT_GUARD_DB"])
    connect_args = json.loads(os.environ.get("WEALTHPILOT_GUARD_CONNECT_ARGS", "{}"))
    original = session_module.create_engine

    def guarded(url, *args, **kwargs):
        parsed = url if hasattr(url, "database") else make_url(url)
        try:
            check_engine_target(parsed.host, parsed.database, target)
        except Exception:
            STATE["blocked"] += 1
            raise
        STATE["engines"] += 1
        merged = {**kwargs.get("connect_args", {}), **connect_args}
        return original(url, *args, **{**kwargs, "connect_args": merged})

    session_module.create_engine = guarded


def pytest_collection_modifyitems(config, items):
    dropped = [item for item in items if uses_development_database(item.fixturenames)]
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = [item for item in items if item not in dropped]
    STATE["deselected"] = sorted(item.nodeid for item in dropped)


def pytest_runtest_logreport(report):
    if report.failed:
        lines = [line for line in redact(report.longreprtext).splitlines() if line.strip()][-10:]
        print(f"\nISOLATED-DB FAILURE [{report.when}] {report.nodeid}")
        for line in lines:
            print("    " + line[:200])


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line(
        f"ISOLATED-DB: deselected development-database tests = {len(STATE['deselected'])}; engines created (all the resolved test target) = {STATE['engines']}; blocked engine attempts = {STATE['blocked']}"
    )
    for nodeid in STATE["deselected"]:
        terminalreporter.write_line(f"ISOLATED-DB deselected: {nodeid}")
