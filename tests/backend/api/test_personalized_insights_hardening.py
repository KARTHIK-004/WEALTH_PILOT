"""ADR-043 hardening of `POST /api/profiles/{id}/personalized-insights`, exercised WITHOUT a database (the session is a stub that fails on any use; the two reads are synthetic): the user's
text is never echoed in ANY error, blank text is "unavailable", the limits match the frontend, metadata is exact, the endpoint is isolated from compliance/recommendation code and writes
nothing, and the frontend's generated types, client call and test fixtures cannot drift from the backend.

Nothing here measures or claims sentiment accuracy; the sentences are invented.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import logging
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.main import app
from wealthpilot.api.services import personalized_insight_service as svc
from wealthpilot.core.behaviour_findings import FINDINGS_VERSION
from wealthpilot.core.personalized_insight import COMPOSER_VERSION
from wealthpilot.core.user_text_sentiment import LIMITATIONS, MAX_TEXT_CHARS, METHOD_VERSION, VALIDATION_STATUS

ROOT = Path(__file__).resolve().parents[3]
URL = "/api/profiles/{}/personalized-insights"
MARKER = "SECRET-MARKER-5521"


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_insight_fixtures", ROOT / "scripts" / "export_insight_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_insight_fixtures"] = module
    spec.loader.exec_module(module)
    return module


exporter = load_exporter()


@pytest.fixture()
def client(monkeypatch):
    features_for, risk_for = exporter._stubs()
    monkeypatch.setattr(svc.monthly_records_service, "core_features", lambda session, cid: features_for(cid))
    monkeypatch.setattr(svc, "_risk_profile", lambda session, cid: risk_for(cid))
    app.dependency_overrides[get_session] = lambda: exporter.NoDb()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


# ------------------------------------------------------------------ the text is never echoed, in any error

@pytest.mark.parametrize("body", [
    {"text": [MARKER]}, {"text": {"nested": MARKER}}, {"text": [[MARKER, 1]]},                      # wrongly typed field holding the user's words
    [MARKER], [{"text": MARKER}], MARKER, {"text": MARKER, "text2": [MARKER]},                       # the body itself is the wrong shape (a list, a bare string)
])
def test_a_wrongly_typed_or_shaped_body_is_a_422_that_never_echoes_the_words(client, body):
    response = client.post(URL.format(1), json=body)
    assert response.status_code in (200, 422)
    assert MARKER not in response.text, response.text[:300]
    if response.status_code == 422:
        problem = response.json()
        assert problem["title"] == "Validation error" and response.headers["content-type"].startswith("application/problem+json")
        assert "input" not in problem["detail"] and "ctx" not in problem["detail"]
        assert "'loc'" in problem["detail"] and "'msg'" in problem["detail"]                       # still useful: where and what, never the value


@pytest.mark.parametrize("content", ['{"text": "' + MARKER + '" ', '{"text": ' + MARKER + "}", "not json " + MARKER, "\x00" + MARKER])
def test_a_malformed_body_never_echoes_the_words(client, content):
    response = client.post(URL.format(1), content=content.encode("utf-8", "ignore"), headers={"Content-Type": "application/json"})
    assert response.status_code in (400, 422)
    assert MARKER not in response.text


def test_other_routes_keep_the_standard_validation_detail_unchanged(client):
    """The narrow fix must not change any other route: their 422 detail still carries Pydantic's full entries, input included."""
    response = client.post("/api/profiles", json={"name": ["x"], "age": 30})
    assert response.status_code == 422 and "'input'" in response.json()["detail"]


def test_unusable_text_is_a_400_with_a_generic_reason_and_no_text(client):
    for text in (MARKER * 300, "bad\u0007" + MARKER, "\x00" + MARKER):
        response = client.post(URL.format(1), json={"text": text})
        assert response.status_code == 400 and MARKER not in response.text
        assert re.search(r"cannot be analysed: text (is longer than 1000 characters|contains control characters)\.", response.json()["detail"])
    assert client.post("/api/profiles/abc/personalized-insights", json={"text": MARKER}).status_code == 422


def test_a_server_error_never_contains_the_text(client, monkeypatch):
    monkeypatch.setattr(svc, "derive_findings", lambda features: (_ for _ in ()).throw(RuntimeError("boom " + MARKER)))
    response = TestClient(app, raise_server_exceptions=False).post(URL.format(1), json={"text": MARKER})
    assert response.status_code == 500 and MARKER not in response.text and "boom" not in response.text
    assert response.json()["detail"] == "An unexpected error occurred."


# ------------------------------------------------------------------ missing, blank and boundary text

@pytest.mark.parametrize("body", [{}, {"text": None}, {"text": ""}, {"text": "   "}, {"text": "\n\t \r\n"}])
def test_missing_or_blank_text_is_unavailable_never_neutral(client, body):
    sentiment = client.post(URL.format(1), json=body).json()["user_sentiment"]
    assert (sentiment["status"], sentiment["sentiment"], sentiment["emotional_tone"], sentiment["confidence"]) == ("unavailable", None, None, None)
    assert sentiment["topics"] == [] and sentiment["preferences"] == [] and sentiment["evidence"] == [] and sentiment["unavailable_reason"]


def test_the_length_boundary_matches_the_documented_limit_and_the_frontend_is_never_looser(client):
    assert MAX_TEXT_CHARS == 1000
    assert client.post(URL.format(1), json={"text": "a" * 1000}).status_code == 200
    assert client.post(URL.format(1), json={"text": "a" * 1001}).status_code == 400
    assert client.post(URL.format(1), json={"text": "\U0001F600" * 1000}).status_code == 200              # counted in characters, not bytes or UTF-16 units
    assert client.post(URL.format(1), json={"text": "\U0001F600" * 1001}).status_code == 400
    # The backend counts AFTER collapsing runs of whitespace, so it accepts some raw texts the frontend (which counts as typed) refuses; the reverse can never happen.
    assert client.post(URL.format(1), json={"text": "a" + " " * 1500 + "b"}).status_code == 200


def test_tabs_newlines_and_unicode_are_accepted_and_every_control_character_is_refused(client):
    assert client.post(URL.format(1), json={"text": "I want to save\tmore\nand ₹ matters हिन्दी"}).status_code == 200
    for code in (*range(0, 9), 11, 12, *range(14, 32), 127):
        assert client.post(URL.format(1), json={"text": f"safe{chr(code)}text"}).status_code == 400, code


# ------------------------------------------------------------------ metadata is accurate; nothing else changes

def test_versions_data_source_and_validation_status_are_exact(client):
    body = client.post(URL.format(1), json={"text": "I want to invest safely."}).json()
    assert body["model_version"] == f"{COMPOSER_VERSION}|{FINDINGS_VERSION}|{METHOD_VERSION}" == "personalized_insight_v2|behaviour_findings_v1|user_text_rules_v1"
    assert body["data_source"] == svc.DATA_SOURCE == "monthly_financial_records+risk_assessments+user_text"
    sentiment = body["user_sentiment"]
    assert (sentiment["method"], sentiment["model_version"], sentiment["validation_status"], sentiment["confidence"], sentiment["confidence_band"]) == (
        "rules_baseline", METHOD_VERSION, VALIDATION_STATUS, None, "unavailable") and VALIDATION_STATUS == "UNVALIDATED_BASELINE"
    assert sentiment["limitations"] == list(LIMITATIONS) and any("English only" in item for item in sentiment["limitations"])
    assert body["analysis_timestamp"].endswith(("Z", "+00:00")) and body["purpose"] and "not financial advice" in body["purpose"].lower()


def test_unavailable_debt_and_goal_progress_stay_unavailable_and_are_never_zero(client):
    findings = {f["code"]: f for f in client.post(URL.format(1), json={}).json()["behaviour"]["findings"]}
    for code in ("debt_burden", "goal_progress"):
        assert findings[code]["status"] == "not_included" and findings[code]["values"] == {} and findings[code]["direction"] is None
    empty = {f["code"]: f for f in client.post(URL.format(2), json={}).json()["behaviour"]["findings"]}
    assert all(f["status"] in ("unavailable", "not_included") for f in empty.values())                        # no record means nothing is observed
    counts = {"observation_count", "known_months"}                                                             # these are genuine counts of reported months (a known zero), not missing amounts
    assert all(set(f["values"]) <= counts for f in empty.values())
    for code in ("expenses_trend", "savings_trend", "expense_to_income_ratio", "savings_to_income_ratio", "investment_contribution_to_income_ratio", "debt_burden", "goal_progress"):
        assert empty[code]["values"] == {} and empty[code]["direction"] is None, code                           # no amount, ratio or change is invented as 0


def test_the_stored_assessment_is_reported_and_never_overridden_by_the_text(client):
    body = client.post(URL.format(1), json={"text": "I want to invest safely and avoid losing my savings."}).json()
    assert body["risk_profile"]["category"] == "Aggressive"                                                   # unchanged by a capital-preservation wish
    assert [c["code"] for c in body["conflicts"]] == ["capital_preservation"]
    assert not any(k in body for k in ("recommendation", "allocation", "portfolio", "risk_score", "risk_tolerance"))
    assert not any(k in body["user_sentiment"] for k in ("risk_tolerance", "risk_profile", "risk_category"))


def test_the_text_is_not_logged_by_the_route_or_the_server(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post(URL.format(1), json={"text": MARKER + " I am worried."})
        client.post(URL.format(1), json={"text": [MARKER]})
        client.post(URL.format(1), json={"text": MARKER * 400})
    assert MARKER not in caplog.text and all(MARKER not in str(r.args) for r in caplog.records)


# ------------------------------------------------------------------ isolation, no persistence, no external calls

PACKAGE = ROOT / "backend" / "wealthpilot"
INSIGHT_MODULES = [PACKAGE / "core" / "user_text_sentiment.py", PACKAGE / "core" / "personalized_insight.py", PACKAGE / "core" / "behaviour_findings.py",
                   PACKAGE / "api" / "services" / "personalized_insight_service.py", PACKAGE / "api" / "routers" / "personalized_insights.py"]


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
    return found


def test_the_insight_code_does_not_reach_compliance_recommendation_agents_or_any_external_service():
    forbidden = ("wealthpilot.agents", "wealthpilot.core.compliance", "wealthpilot.core.recommendation", "wealthpilot.core.optimizer", "wealthpilot.api.services.analysis_service",
                 "google", "anthropic", "openai", "autogen", "requests", "httpx", "urllib", "socket", "aiohttp", "transformers", "torch", "sklearn", "langgraph")
    for path in INSIGHT_MODULES:
        for imported in imports_of(path):
            assert not imported.startswith(forbidden), (path.name, imported)


def test_nothing_in_the_analysis_recommendation_or_compliance_path_reads_the_insight_modules():
    ours = ("personalized_insight", "user_text_sentiment", "behaviour_findings")
    paths = [*(PACKAGE / "agents").rglob("*.py"), PACKAGE / "api" / "services" / "analysis_service.py", PACKAGE / "core" / "compliance.py", PACKAGE / "core" / "recommendation.py",
             PACKAGE / "core" / "optimizer.py", PACKAGE / "core" / "goals.py", PACKAGE / "core" / "serialization.py"]
    checked = 0
    for path in paths:
        if not path.exists():
            continue
        checked += 1
        assert not any(name in imported for imported in imports_of(path) for name in ours), path.name
    assert checked >= 8


def test_the_insight_code_has_no_logger_print_database_write_or_file_access():
    for path in INSIGHT_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not ({"print", "open", "logger", "logging"} & names), path.name
        assert not ({"add", "add_all", "commit", "flush", "delete", "merge", "execute", "bulk_save_objects", "write", "write_text", "dump"} & attrs), path.name
        assert "logging" not in imports_of(path), path.name


def test_no_table_or_migration_stores_user_text():
    models = (PACKAGE / "db" / "models.py").read_text(encoding="utf-8").lower()
    assert not any(word in models for word in ("user_text", "sentiment", "personalized_insight", "raw_text"))
    versions = (ROOT / "backend" / "alembic" / "versions")
    for path in versions.glob("*.py"):
        body = path.read_text(encoding="utf-8").lower()
        assert not any(word in body for word in ("user_text", "sentiment", "personalized_insight", "raw_text")), path.name


# ------------------------------------------------------------------ the frontend cannot drift from the backend

def openapi_schemas() -> dict:
    return app.openapi()["components"]["schemas"]


def reachable(schemas: dict, root: str) -> list[str]:
    seen, stack = [], [root]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.append(name)
        stack += re.findall(r'"#/components/schemas/([A-Za-z0-9_]+)"', json.dumps(schemas[name]))
    return seen


def ts_block(source: str, name: str) -> str:
    start = source.index(f"        {name}: {{")
    depth, i = 0, source.index("{", start)
    for j in range(i, len(source)):
        depth += source[j] == "{"
        depth -= source[j] == "}"
        if depth == 0:
            return source[i:j + 1]
    raise AssertionError(name)


def test_the_generated_types_contain_every_field_of_the_response_and_request_schemas():
    schemas = openapi_schemas()
    types = (ROOT / "frontend" / "src" / "types" / "api.ts").read_text(encoding="utf-8")
    names = reachable(schemas, "PersonalizedInsightResponse") + reachable(schemas, "PersonalizedInsightRequest")
    assert {"PersonalizedInsightResponse", "UserSentimentOut", "BehaviourFindingsOut", "InsightStatementOut", "InsightConflictOut", "RiskProfileOut", "StatedPreferenceOut", "EvidenceOut",
            "PersonalizedInsightRequest"} <= set(names)
    for name in dict.fromkeys(names):
        block = ts_block(types, name)
        for prop, spec in schemas[name].get("properties", {}).items():
            assert re.search(rf"\b{prop}\??:", block), (name, prop)
            if prop in schemas[name].get("required", []):
                assert re.search(rf"\b{prop}:", block), (name, prop, "required fields are not optional in the generated type")
        for enum in [v for spec in schemas[name].get("properties", {}).values() for v in [spec.get("enum")] if v]:
            for member in enum:
                typed = ("true" if member is True else "false" if member is False else f'"{member}"')            # a boolean constant is typed as a TypeScript literal, not a string
                assert typed in block, (name, member)                                                          # every enum member the backend can send is typed


def test_the_request_schema_is_exactly_one_optional_text_field_and_the_route_is_a_single_post():
    schemas = openapi_schemas()
    request = schemas["PersonalizedInsightRequest"]
    assert list(request["properties"]) == ["text"] and "required" not in request
    assert {t.get("type") for t in request["properties"]["text"]["anyOf"]} == {"string", "null"}
    paths = {p: ops for p, ops in app.openapi()["paths"].items() if "personalized-insights" in p}
    assert list(paths) == ["/api/profiles/{profile_id}/personalized-insights"] and list(paths["/api/profiles/{profile_id}/personalized-insights"]) == ["post"]
    assert paths["/api/profiles/{profile_id}/personalized-insights"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PersonalizedInsightResponse")


def test_the_frontend_client_calls_the_real_route_with_the_real_request_field():
    client = (ROOT / "frontend" / "src" / "lib" / "api-client.ts").read_text(encoding="utf-8")
    call = client[client.index("createPersonalizedInsight:"):]
    call = call[:call.index("}),") + 3]
    route = re.search(r"`(/api/profiles/\$\{profileId\}/personalized-insights)`", call)
    assert route and route.group(1).replace("${profileId}", "{profile_id}") in app.openapi()["paths"]
    assert 'method: "POST"' in call and "JSON.stringify({ text })" in call
    assert list(openapi_schemas()["PersonalizedInsightRequest"]["properties"]) == ["text"]


def test_the_frontend_test_fixtures_are_exactly_what_the_backend_returns_today():
    fixtures = exporter.generate()
    assert len(fixtures) >= 9
    for name, payload in fixtures.items():
        saved = (exporter.FIXTURE_DIR / f"{name}.json").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
        assert saved == exporter.render(payload), f"fixture {name} drifted from the backend; run scripts/export_insight_fixtures.py"
    scenarios = {name: p for name, p in fixtures.items()}
    assert {p["status"] for p in scenarios.values()} == {"complete", "behaviour_only", "profile_only", "unavailable"}   # every overall state is represented by a real response
    assert {p["user_sentiment"]["sentiment"] for p in scenarios.values()} >= {None, "negative", "uncertain", "positive", "neutral"}
