"""Export REAL backend responses of `GET /api/profiles/{id}/security-status` as fixtures for the frontend tests (frontend/tests/fixtures/security-*.json).

    python scripts/export_security_fixtures.py            # (re)write the fixtures
    python scripts/export_security_fixtures.py --check    # exit 1 if the saved fixtures differ from what the backend returns now

The responses come from the actual route, service, encryption service and ledger verifier, run against a throwaway SQLite file in a temporary directory with a random
key generated for the run (no database server, no network, no secret read from the environment). Nothing in a response depends on the key or on a timestamp, so the files are
deterministic. tests/backend/security/test_status_fixtures.py fails if a fixture drifts from the backend.
"""

from __future__ import annotations

import json
import secrets
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

FIXTURE_DIR = REPO / "frontend" / "tests" / "fixtures"
NAMES = ("security-operational", "security-empty-ledger", "security-not-configured", "security-ledger-invalid", "security-self-test-failed")


def render(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def generate() -> dict[str, dict]:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session, sessionmaker

    from wealthpilot.api.dependencies import get_encryption_service, get_session
    from wealthpilot.api.main import app
    from wealthpilot.db.base import Base
    from wealthpilot.db.models import AuditLedgerEvent, Customer, ProtectedRecord
    from wealthpilot.security.crypto import EncryptionService
    from wealthpilot.security.keys import EnvironmentKeyProvider, generate_key_spec

    out: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_engine(f"sqlite:///{Path(tmp) / 'fixtures.db'}")
        Base.metadata.create_all(engine, tables=[Customer.__table__, ProtectedRecord.__table__, AuditLedgerEvent.__table__])
        with Session(engine) as db:
            db.add(Customer(name="Synthetic Fixture Customer", data_source="user-entered"))
            db.commit()
        maker = sessionmaker(bind=engine)
        service = EncryptionService(EnvironmentKeyProvider(generate_key_spec("fixture-key", secrets.token_bytes(32)), "fixture-key"))
        unconfigured = EncryptionService(EnvironmentKeyProvider("", ""))
        current = {"service": service}

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
        app.dependency_overrides[get_encryption_service] = lambda: current["service"]
        try:
            client = TestClient(app)
            headers = {"X-Customer-Id": "1"}
            status = lambda: client.get("/api/profiles/1/security-status", headers=headers).json()  # noqa: E731

            out["security-empty-ledger"] = status()
            current["service"] = unconfigured
            out["security-not-configured"] = status()
            current["service"] = service
            created = client.post("/api/profiles/1/protected-notes", json={"content": "Synthetic fixture note."}, headers=headers)
            assert created.status_code == 201, created.text
            client.get(f"/api/profiles/1/protected-notes/{created.json()['id']}", headers=headers)
            out["security-operational"] = status()
            with engine.begin() as connection:
                connection.execute(text("UPDATE audit_ledger_events SET event_type = 'protected_record.deleted' WHERE sequence = 1"))
            out["security-ledger-invalid"] = status()
            # A key that loads but a round trip that fails: the REAL route and service report it; only the probe is forced to fail.
            original_self_test = EncryptionService.self_test
            EncryptionService.self_test = lambda self: False  # type: ignore[method-assign]
            try:
                out["security-self-test-failed"] = status()
            finally:
                EncryptionService.self_test = original_self_test  # type: ignore[method-assign]
        finally:
            app.dependency_overrides.pop(get_session, None)
            app.dependency_overrides.pop(get_encryption_service, None)
            engine.dispose()
    return {name: out[name] for name in NAMES}


def main() -> int:
    fixtures = generate()
    if "--check" in sys.argv:
        stale = [name for name, payload in fixtures.items() if not (FIXTURE_DIR / f"{name}.json").is_file() or (FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8") != render(payload)]
        print("fixtures current" if not stale else f"stale fixtures: {stale}")
        return 1 if stale else 0
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, payload in fixtures.items():
        (FIXTURE_DIR / f"{name}.json").write_text(render(payload), encoding="utf-8", newline="\n")
    print(f"wrote {len(fixtures)} fixtures to {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
