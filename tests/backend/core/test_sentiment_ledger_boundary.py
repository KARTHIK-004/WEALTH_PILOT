"""The blockchain / ledger boundary of the sentiment feature (sentiment phase, Phase 10). Static and database-free: nothing in the sentiment, insight or model-loading code can reach the
audit ledger or an anchor, nothing in the security package can reach them, and the ledger's own event shape has no field that could carry raw text, evidence, preferences, labels or a
risk profile. The only permitted future anchor payload is a ledger identifier, a sequence number, the head hash and (if the protocol needs it) a timestamp."""
from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

from wealthpilot.security import ledger

PACKAGE = Path(__file__).resolve().parents[3] / "backend" / "wealthpilot"
TRAINING = Path(__file__).resolve().parents[3] / "training" / "sentiment"
SENTIMENT_MODULES = [PACKAGE / "core" / "user_text_sentiment.py", PACKAGE / "core" / "personalized_insight.py", PACKAGE / "core" / "behaviour_findings.py", PACKAGE / "core" / "sentiment_model.py",
                     PACKAGE / "api" / "services" / "personalized_insight_service.py", PACKAGE / "api" / "routers" / "personalized_insights.py", *sorted(TRAINING.glob("*.py"))]
SENSITIVE_WORDS = ("sentiment", "preference", "evidence", "text", "label", "risk", "profile", "emotion", "topic", "prediction", "probab")


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def test_no_sentiment_insight_or_model_code_imports_the_security_package():
    for path in SENTIMENT_MODULES:
        for imported in imports_of(path):
            assert not imported.startswith("wealthpilot.security"), (path.name, imported)


def test_no_sentiment_insight_or_model_code_names_a_ledger_or_an_anchor():
    for path in SENTIMENT_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        words = {n.id.lower() for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr.lower() for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not any("ledger" in w or "anchor" in w or "blockchain" in w for w in words), path.name


def test_the_security_package_does_not_import_sentiment_or_insight_code():
    ours = ("user_text_sentiment", "personalized_insight", "behaviour_findings", "sentiment_model", "training.sentiment")
    for path in (PACKAGE / "security").glob("*.py"):
        assert not any(name in imported for imported in imports_of(path) for name in ours), path.name


def test_a_ledger_event_has_no_field_that_could_carry_sentiment_text_or_personal_data():
    event_fields = {f.name for f in dataclasses.fields(ledger.LedgerEvent)}
    head_fields = {f.name for f in dataclasses.fields(ledger.LedgerHead)}
    payload_parameters = set(inspect.signature(ledger.canonical_payload).parameters)
    assert payload_parameters == {"sequence", "event_type", "occurred_at", "record_ref", "schema_version"}
    for name in event_fields | head_fields | payload_parameters:
        assert not any(word in name.lower() for word in SENSITIVE_WORDS), name


def test_the_ledger_append_signature_accepts_only_an_event_type_and_an_opaque_reference():
    parameters = list(inspect.signature(ledger.LocalHashChainLedger.append).parameters)
    assert parameters == ["self", "session", "event_type", "record_ref"]
