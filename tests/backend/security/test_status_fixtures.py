"""The frontend's security-status fixtures are exactly what the real route returns today (no hand-written mock can drift).

`scripts/export_security_fixtures.py` runs the actual route, encryption service and ledger verifier on a throwaway SQLite file with a
random key; nothing in a response depends on the key or on a timestamp, so the saved files are deterministic.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def exporter():
    spec = importlib.util.spec_from_file_location("export_security_fixtures", ROOT / "scripts" / "export_security_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_security_fixtures"] = module
    spec.loader.exec_module(module)
    return module


def test_the_saved_fixtures_are_exactly_what_the_backend_returns_today(exporter):
    fixtures = exporter.generate()
    assert set(fixtures) == set(exporter.NAMES) and len(fixtures) == 5
    for name, payload in fixtures.items():
        saved = (exporter.FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")
        assert saved == exporter.render(payload), f"fixture {name} drifted from the backend; run scripts/export_security_fixtures.py"


def test_the_fixtures_cover_every_state_the_page_must_render(exporter):
    fixtures = exporter.generate()
    assert fixtures["security-operational"]["encryption"]["status"] == "operational"
    assert fixtures["security-operational"]["ledger"]["verification"] == "valid"
    assert fixtures["security-empty-ledger"]["ledger"]["verification"] == "empty"
    assert fixtures["security-not-configured"]["encryption"]["status"] == "not_configured"
    assert fixtures["security-ledger-invalid"]["ledger"]["verification"] == "invalid"
    assert fixtures["security-self-test-failed"]["encryption"]["status"] == "failed"


def test_no_fixture_contains_a_hash_an_identifier_a_key_or_note_text(exporter):
    for name, payload in exporter.generate().items():
        text = exporter.render(payload)
        assert not re.search(r"[0-9a-f]{64}", text, re.I), name
        assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text, re.I), name
        assert not re.search(r"[A-Za-z0-9+/]{43}=", text), name
        assert "Synthetic fixture note" not in text and "fixture-key" not in text, name
