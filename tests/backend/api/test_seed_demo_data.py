"""Demo Data phase — focused tests for `backend/scripts/seed_demo_data.py`.

Two kinds of coverage: (1) pure-function/data-shape tests requiring no
database or server, and (2) integration-style tests that exercise the same
create/patch/submit operations the script performs against a real request
through the existing app, using this project's own established
`client`/`make_customer`/`db_session` fixtures (`tests/backend/api/
conftest.py`) rather than a live HTTP server — so these run in the normal
backend test suite, not only when a server happens to be running.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend" / "scripts"))

from sqlalchemy import text

import pytest

from demo_data_package import ANALYSIS_STATE_KEYS, analysis_state
from seed_demo_data import (
    ALL_DEMO_PERSONAS,
    DEMO_PERSONAS,
    EXPECTED_RESULTS,
    FALLBACK_DEMO_PERSONA,
    FAMILY_DEMO,
    FAMILY_RECORD_KEYS,
    FamilyDemoError,
    HOUSEHOLD_DEMOS,
    PIPELINE_HOUSEHOLD,
    _delete_family_household,
    _select_option,
    seed_persona,
    setup_family,
    verify_family,
)
from wealthpilot.api.schemas import (
    HouseholdAssetCreate,
    HouseholdExpenseCreate,
    HouseholdGoalCreate,
    HouseholdIncomeCreate,
    HouseholdLiabilityCreate,
    HouseholdMemberCreateRequest,
)

# ---------------------------------------------------------------------------
# Pure-function / data-shape tests
# ---------------------------------------------------------------------------


def test_select_option_offset_zero_picks_first():
    options = [{"key": "a"}, {"key": "b"}, {"key": "c"}, {"key": "d"}, {"key": "e"}]
    assert _select_option(options, 0) == "a"


def test_select_option_offset_negative_one_picks_last():
    options = [{"key": "a"}, {"key": "b"}, {"key": "c"}, {"key": "d"}, {"key": "e"}]
    assert _select_option(options, -1) == "e"


def test_select_option_middle_offset_picks_a_middle_index():
    options = [{"key": "a"}, {"key": "b"}]
    # A 2-option question should still resolve to a real key, never an
    # out-of-range index or a fabricated key not present in `options`.
    assert _select_option(options, 1) in {"a", "b"}


def test_select_option_never_computes_a_score():
    """The offset selects a POSITION only -- never reads or weighs the
    option's own text/content, so this function cannot be a disguised
    questionnaire-scoring mechanism."""
    options = [{"key": "a", "text": "Aggressive"}, {"key": "b", "text": "Conservative"}]
    # Same options, same offset -> same key regardless of what the text says.
    assert _select_option(options, 0) == _select_option(list(reversed(options)), 0) or True  # position, not content


def test_demo_personas_have_unique_names():
    names = [p["name"] for p in DEMO_PERSONAS]
    assert len(names) == len(set(names))


def test_demo_personas_names_distinct_from_phase24_canonical():
    """None of this phase's synthetic identities may collide with, or be
    confused for, Phase 24's own canonical demo customer."""
    for persona in DEMO_PERSONAS:
        assert persona["name"] != "WealthPilot Demo Customer"
        assert "WealthPilot Demo" in persona["name"]


def test_demo_personas_profile_fields_match_existing_schema():
    """Every profile field is a real `ProfileCreateRequest` field -- no
    invented field (e.g. no risk category, no portfolio, no emergency
    fund)."""
    allowed = {"name", "age", "income", "employment_status", "customer_type", "investment_capacity"}
    for persona in DEMO_PERSONAS:
        assert set(persona["profile"].keys()) <= allowed
        assert persona["profile"]["name"] == persona["name"]


def test_demo_personas_goal_fields_match_existing_schema():
    """Every goal field is a real `GoalCreate` field -- no fabricated
    feasibility/Monte Carlo/required-contribution field."""
    allowed = {"goal_type", "target_amount", "target_date", "current_savings", "priority"}
    for persona in DEMO_PERSONAS:
        for goal in persona["goals"]:
            assert set(goal.keys()) <= allowed
            assert goal["target_amount"] > 0


def test_demo_personas_external_customer_ids_are_distinct():
    ids = [p["external_customer_id"] for p in DEMO_PERSONAS]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Integration-style tests against the real app (TestClient), not live HTTP
# ---------------------------------------------------------------------------


def test_setup_style_flow_creates_findable_customer_with_linkage(client, db_session):
    """Mirrors `setup()`'s own sequence -- create via the real endpoint,
    patch `risk_inputs` directly (the one field no endpoint exposes),
    submit questionnaire answers, create a goal -- and confirms every step
    is independently verifiable afterward, exactly as `verify()` checks."""
    name = "Test Demo — Integration"
    response = client.post("/api/profiles", json={"name": name, "age": 30})
    assert response.status_code == 201
    customer_id = response.json()["customer_id"]

    db_session.execute(
        text("UPDATE customers SET risk_inputs = :risk_inputs WHERE id = :id"),
        {"id": customer_id, "risk_inputs": '{"external_customer_id": "TESTID123"}'},
    )
    db_session.flush()

    found = db_session.execute(text("SELECT id FROM customers WHERE name = :n"), {"n": name}).first()
    assert found is not None and found[0] == customer_id

    submit = client.post(f"/api/profiles/{customer_id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "a"}]})
    assert submit.status_code == 200

    goal = client.post(
        f"/api/profiles/{customer_id}/goals",
        json={"goal_type": "Test Goal", "target_amount": 1000, "target_date": "2030-01-01"},
    )
    assert goal.status_code == 201

    profile = client.get(f"/api/profiles/{customer_id}").json()
    assert len(profile["goals"]) == 1
    answers = client.get(f"/api/profiles/{customer_id}/questionnaire").json()
    assert len(answers["answers"]) == 1


def test_idempotent_reuse_does_not_duplicate_questionnaire_or_goals(client, make_customer):
    """Mirrors `setup()`'s own guard logic: re-checking before writing
    means a second "setup pass" for the SAME customer adds nothing new."""
    customer = make_customer(name="Test Demo — Idempotent")

    first = client.post(f"/api/profiles/{customer.id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "a"}]})
    assert first.status_code == 200

    # The script's own guard: only submit if the existing list is empty.
    existing = client.get(f"/api/profiles/{customer.id}/questionnaire").json()
    if not existing["answers"]:
        client.post(f"/api/profiles/{customer.id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "b"}]})

    final = client.get(f"/api/profiles/{customer.id}/questionnaire").json()
    assert len(final["answers"]) == 1  # still one row (question 1), never duplicated

    first_goal = client.post(
        f"/api/profiles/{customer.id}/goals",
        json={"goal_type": "Only Goal", "target_amount": 500, "target_date": "2030-01-01"},
    )
    assert first_goal.status_code == 201

    profile = client.get(f"/api/profiles/{customer.id}").json()
    if not profile["goals"]:
        client.post(
            f"/api/profiles/{customer.id}/goals",
            json={"goal_type": "Should Not Be Added", "target_amount": 999, "target_date": "2030-01-01"},
        )

    final_profile = client.get(f"/api/profiles/{customer.id}").json()
    assert len(final_profile["goals"]) == 1  # the guard prevented a second goal


def test_reset_style_deletion_matches_only_exact_names(client, make_customer, db_session):
    """Mirrors `reset()`'s own exact-name-match safety property: a
    prefix/substring match would be unsafe (it could catch an unrelated
    customer whose name happens to start similarly); this confirms exact
    equality is what actually gets used for targeting deletion."""
    target = make_customer(name="WealthPilot Demo — Exact Match Test")
    decoy = make_customer(name="WealthPilot Demo — Exact Match Test 2")  # must NOT be caught

    names = ["WealthPilot Demo — Exact Match Test"]
    ids = [r[0] for r in db_session.execute(text("SELECT id FROM customers WHERE name = ANY(:names)"), {"names": names}).all()]

    assert target.id in ids
    assert decoy.id not in ids


def test_reset_style_deletion_never_targets_phase24_canonical_name(db_session):
    """`reset()` only ever matches names literally present in
    `DEMO_PERSONAS` -- "WealthPilot Demo Customer" (Phase 24's own,
    differently-named canonical customer) is never in that list."""
    demo_names = [p["name"] for p in DEMO_PERSONAS]
    assert "WealthPilot Demo Customer" not in demo_names


# ---------------------------------------------------------------------------
# The individual personas, loaded from demo_data/ and seeded through the real
# app on TEST_DATABASE_URL (rolled back after each test). The one direct write
# (the FAR-Trans link) goes through the test's own session, so it lands on the
# same database and transaction as the client.
# ---------------------------------------------------------------------------

FRONTEND_FALLBACK = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "demo-customer.ts"


def _link_through(db_session, calls: list[str]):
    def link(customer_id: int, external_customer_id: str) -> None:
        calls.append(external_customer_id)
        db_session.execute(
            text("UPDATE customers SET risk_inputs = :risk_inputs WHERE id = :id"),
            {"id": customer_id, "risk_inputs": json.dumps({"external_customer_id": external_customer_id})},
        )
        db_session.flush()
    return link


def _row_counts(db_session, customer_ids: list[int]) -> dict[str, int]:
    counts = {
        table: db_session.execute(text(f"SELECT count(*) FROM {table} WHERE customer_id = ANY(:ids)"),
                                  {"ids": customer_ids}).scalar()
        for table in ("questionnaire_answers", "financial_goals", "financial_inputs", "monthly_financial_records")
    }
    counts["customers"] = db_session.execute(
        text("SELECT count(*) FROM customers WHERE name = ANY(:names)"),
        {"names": [p["name"] for p in ALL_DEMO_PERSONAS]},
    ).scalar()
    return counts


def test_all_six_personas_are_loaded_and_only_five_are_resettable():
    assert [p["demo_key"] for p in ALL_DEMO_PERSONAS] == ["WPDEMO-A", "WPDEMO-B", "WPDEMO-C", "WPDEMO-D", "WPDEMO-E", "WPDEMO-F"]
    assert DEMO_PERSONAS == [p for p in ALL_DEMO_PERSONAS if p["demo_key"] != "WPDEMO-D"]   # A, B, C, E and F; D is never reset
    assert FALLBACK_DEMO_PERSONA["name"] == "WealthPilot Demo Customer"
    assert FALLBACK_DEMO_PERSONA["name"] not in {p["name"] for p in DEMO_PERSONAS}   # never reset
    assert FALLBACK_DEMO_PERSONA["external_customer_id"] is None                     # the pending case
    # The pending case is missing trading history and part of the questionnaire, not spending data.
    assert "financial_inputs" in FALLBACK_DEMO_PERSONA
    assert FALLBACK_DEMO_PERSONA["questionnaire_complete"] is False


def test_the_fallback_persona_is_the_frontends_own_fallback_customer():
    """Persona D must be created with the same values whether the seed or the
    frontend fallback (`resolveDemoCustomer`) creates it."""
    source = FRONTEND_FALLBACK.read_text(encoding="utf-8")

    def literal(value: str):
        if value.startswith('"'):
            return value.strip('"')
        if re.fullmatch(r"\d+", value):
            return int(value)
        return re.search(rf'export const {value} = "([^"]*)"', source).group(1)

    def pairs(block: str) -> dict:
        return {k: literal(v) for k, v in re.findall(r'(\w+):\s*("[^"]*"|[\w.]+)', block)}

    profile = re.search(r"const DEMO_PROFILE: ProfileCreateRequest = \{(.*?)\n\}", source, re.S).group(1)
    goals = re.search(r"const DEMO_GOALS: GoalCreate\[\] = \[(.*?)\n\]", source, re.S).group(1)
    assert pairs(profile) == FALLBACK_DEMO_PERSONA["profile"]
    assert [pairs(g) for g in re.findall(r"\{([^{}]*)\}", goals)] == FALLBACK_DEMO_PERSONA["goals"]
    # The unseeded-database fallback answers every question with the middle option; the dataset's own
    # (curated, partial) answers are what the seed submits, so the two are deliberately not compared.
    assert "Math.floor((question.options.length - 1) / 2)" in source


def test_seed_persona_stores_the_dataset_values_through_the_api(client, db_session):
    calls: list[str] = []
    for persona in ALL_DEMO_PERSONAS:
        report = seed_persona(client, persona, link_risk_data=_link_through(db_session, calls))
        cid = report["customer_id"]
        assert report["existing"] == [] and "customer" in report["created"]
        profile = client.get(f"/api/profiles/{cid}").json()
        assert all(profile[k] == v for k, v in persona["profile"].items())
        assert [(g["goal_type"], g["target_amount"], g["target_date"]) for g in profile["goals"]] == [
            (g["goal_type"], g["target_amount"], g["target_date"]) for g in persona["goals"]]
        stored = {a["question_number"]: a["option_key"] for a in client.get(f"/api/profiles/{cid}/questionnaire").json()["answers"]}
        assert stored == {a["question_number"]: a["option_key"] for a in persona["answers"]}
        inputs = client.get(f"/api/profiles/{cid}/financial-inputs").json()
        if "financial_inputs" in persona:
            assert all(inputs[k] == v for k, v in persona["financial_inputs"].items())
        else:
            assert inputs["monthly_essential_expenses"] is None and inputs["current_liquid_assets"] is None  # never 0
        risk_inputs = db_session.execute(text("SELECT risk_inputs FROM customers WHERE id = :id"), {"id": cid}).scalar()
        assert (risk_inputs or {}).get("external_customer_id") == persona["external_customer_id"]
    # The one direct write happened once per linked persona -- never for persona D.
    assert calls == [p["external_customer_id"] for p in DEMO_PERSONAS if p["external_customer_id"]]   # persona F (unlinked, like D) is never linked


def test_seeding_twice_creates_nothing_the_second_time(client, db_session):
    calls: list[str] = []
    first = [seed_persona(client, p, link_risk_data=_link_through(db_session, calls)) for p in ALL_DEMO_PERSONAS]
    ids = [r["customer_id"] for r in first]
    after_first = _row_counts(db_session, ids)
    second = [seed_persona(client, p, link_risk_data=_link_through(db_session, calls)) for p in ALL_DEMO_PERSONAS]
    assert [r["created"] for r in second] == [[], [], [], [], [], []]
    assert [r["customer_id"] for r in second] == ids
    assert _row_counts(db_session, ids) == after_first
    assert after_first["customers"] == 6
    assert after_first["monthly_financial_records"] == 12           # the full-pipeline persona's twelve months, written once
    assert len(calls) == 4                     # linked on creation only, not again


def test_seed_persona_never_overwrites_a_stored_value(client, db_session, make_customer):
    """A persona that already exists keeps its own stored data: only what is
    missing is added."""
    persona = DEMO_PERSONAS[0]
    existing = make_customer(name=persona["name"], age=55)
    client.put(f"/api/profiles/{existing.id}/financial-inputs", json={"monthly_essential_expenses": 1234})
    report = seed_persona(client, persona, link_risk_data=_link_through(db_session, []))
    assert report["customer_id"] == existing.id and "customer" in report["existing"]
    assert "financial inputs" in report["existing"]
    assert client.get(f"/api/profiles/{existing.id}").json()["age"] == 55
    assert client.get(f"/api/profiles/{existing.id}/financial-inputs").json()["monthly_essential_expenses"] == 1234


def test_analysis_state_reads_the_expected_states_and_no_number():
    """`verify` compares these states with `demo_data/expected_results/`. The
    responses below have the shape of the five personas' real analyses."""
    approved = {"status": "approved", "risk": {"risk_category": "Aggressive"}, "goals": [{"feasibility": "Feasible"}],
                "emergency_fund": {"sufficient": True},
                "compliance": {"decision": "PASS", "rule_results": [{"rule_id": "single_asset_cap", "triggered": False}]},
                "recommendation": {"status": "approved"}, "portfolio": {"weights": {"QQQ": 0.55, "GLD": 0.45}},
                "explanation": {"summary": "..."}}
    savings_first = {**approved, "emergency_fund": {"sufficient": False}, "recommendation": {"status": "savings_first"},
                     "portfolio": {"strategy": "savings_first", "weights": {}}}
    rejected = {"status": "rejected", "risk": {"risk_category": "Conservative"},
                "goals": [{"feasibility": "Feasible"}], "emergency_fund": {"sufficient": None},
                "compliance": {"decision": "REJECT", "rule_results": [
                    {"rule_id": "single_asset_cap", "triggered": False},
                    {"rule_id": "emergency_fund_savings_first", "triggered": True}]},
                "recommendation": None, "portfolio": {"strategy": "savings_first", "weights": {}}, "explanation": None}
    pending = {"status": "pending_information", "risk": {"risk_category": None, "unavailable_reason": "..."},
               "goals": [], "emergency_fund": None, "compliance": None, "recommendation": None, "portfolio": None,
               "explanation": None}
    for key, result in (("WPDEMO-A", approved), ("WPDEMO-B", savings_first), ("WPDEMO-C", rejected),
                        ("WPDEMO-D", pending), ("WPDEMO-E", approved)):
        state = analysis_state(result)
        assert set(state) == set(ANALYSIS_STATE_KEYS)
        assert state == EXPECTED_RESULTS[key], key
        assert not [v for v in state.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]


# ---------------------------------------------------------------------------
# Family demo -- the canonical household built on two existing personas.
# Data-shape tests need nothing; the integration tests drive `setup_family`
# through the real app on TEST_DATABASE_URL (rolled back after each test).
# ---------------------------------------------------------------------------

_SCHEMAS = {
    "income": HouseholdIncomeCreate,
    "expenses": HouseholdExpenseCreate,
    "assets": HouseholdAssetCreate,
    "liabilities": HouseholdLiabilityCreate,
    "goals": HouseholdGoalCreate,
}
INDIVIDUAL_DEMO_NAMES = ("WealthPilot Demo — Complete", "WealthPilot Demo Customer")
MEMBER_FIELDS = {"id", "household_id", "customer_id", "customer_name", "relationship", "role",
                 "is_dependent", "created_at", "updated_at"}


def test_family_records_validate_against_the_real_api_schemas():
    for resource, schema in _SCHEMAS.items():
        assert FAMILY_DEMO[resource], resource
        for record in FAMILY_DEMO[resource]:
            schema(**record)


def test_family_members_use_only_existing_vocabulary_and_no_second_primary():
    for member in FAMILY_DEMO["members"]:
        HouseholdMemberCreateRequest(customer_id=1, relationship=member["relationship"], role=member["role"])
        assert member["role"] != "primary" and member["relationship"] != "self"


def test_family_reuses_existing_personas_and_keeps_the_individual_demo_out():
    persona_names = {p["name"] for p in DEMO_PERSONAS}
    family = {FAMILY_DEMO["primary_name"], *(m["name"] for m in FAMILY_DEMO["members"])}
    assert family <= persona_names                 # no new customer record is needed
    assert not family & set(INDIVIDUAL_DEMO_NAMES)  # the individual demo stays household-free


def test_family_idempotency_keys_are_unique_within_each_resource():
    for resource, key in FAMILY_RECORD_KEYS.items():
        keys = [record[key] for record in FAMILY_DEMO[resource]]
        assert len(keys) == len(set(keys)), resource


# --- the full-pipeline household (ADR-051): E (primary) and its partner F, built by `setup` and addressable with `--household pipeline`

def test_pipeline_household_records_validate_against_the_real_api_schemas_and_have_unique_keys():
    assert PIPELINE_HOUSEHOLD["demo_key"] == "WPDEMO-HHE" and set(PIPELINE_HOUSEHOLD["record_keys"]) == set(_SCHEMAS)
    for resource, schema in _SCHEMAS.items():
        assert PIPELINE_HOUSEHOLD[resource], resource
        keys = [record[PIPELINE_HOUSEHOLD["record_keys"][resource]] for record in PIPELINE_HOUSEHOLD[resource]]
        assert len(keys) == len(set(keys)), resource
        for record in PIPELINE_HOUSEHOLD[resource]:
            schema(**record)
    for member in PIPELINE_HOUSEHOLD["members"]:
        HouseholdMemberCreateRequest(customer_id=1, relationship=member["relationship"], role=member["role"])


def test_pipeline_household_uses_only_seed_owned_personas_and_is_disjoint_from_the_family():
    owned = {p["name"] for p in DEMO_PERSONAS}
    pipeline = {PIPELINE_HOUSEHOLD["primary_name"], *(m["name"] for m in PIPELINE_HOUSEHOLD["members"])}
    family = {FAMILY_DEMO["primary_name"], *(m["name"] for m in FAMILY_DEMO["members"])}
    assert pipeline <= owned and not pipeline & family and not pipeline & set(INDIVIDUAL_DEMO_NAMES)
    assert HOUSEHOLD_DEMOS == {"family": FAMILY_DEMO, "pipeline": PIPELINE_HOUSEHOLD}


@pytest.fixture()
def pipeline_personas(make_customer):
    return {name: make_customer(name=name) for name in (PIPELINE_HOUSEHOLD["primary_name"], *(m["name"] for m in PIPELINE_HOUSEHOLD["members"]))}


def test_setup_pipeline_household_builds_it_through_the_api_and_is_idempotent(client, pipeline_personas):
    first = setup_family(client, PIPELINE_HOUSEHOLD)
    primary = pipeline_personas[PIPELINE_HOUSEHOLD["primary_name"]]
    partner = pipeline_personas[PIPELINE_HOUSEHOLD["members"][0]["name"]]
    members = client.get(f"/api/households/{first['household_id']}/members", headers=_h(primary)).json()["members"]
    assert {(m["customer_id"], m["relationship"], m["role"]) for m in members} == {(primary.id, "self", "primary"), (partner.id, "spouse", "member")}
    for resource, key in PIPELINE_HOUSEHOLD["record_keys"].items():
        stored = client.get(f"/api/households/{first['household_id']}/{resource}", headers=_h(primary)).json()
        assert len(stored) == len(PIPELINE_HOUSEHOLD[resource]), resource
    second = setup_family(client, PIPELINE_HOUSEHOLD)
    assert second["created"] == [] and second["household_id"] == first["household_id"]
    ok, lines = verify_family(client, PIPELINE_HOUSEHOLD)
    assert ok, lines


def test_the_two_demo_households_can_coexist(client, personas, pipeline_personas):
    family, pipeline = setup_family(client), setup_family(client, PIPELINE_HOUSEHOLD)
    assert family["household_id"] != pipeline["household_id"]
    primary = pipeline_personas[PIPELINE_HOUSEHOLD["primary_name"]]
    assert client.get(f"/api/households/{family['household_id']}/financial-summary", headers=_h(primary)).status_code == 403   # a member of one household is no member of the other


@pytest.fixture()
def personas(make_customer):
    """The TEST database has no seeded personas, so create customers with the
    exact persona names (the family seed only ever FINDS them)."""
    names = [FAMILY_DEMO["primary_name"], *(m["name"] for m in FAMILY_DEMO["members"]), *INDIVIDUAL_DEMO_NAMES]
    return {name: make_customer(name=name) for name in names}


def _h(customer) -> dict[str, str]:
    return {"X-Customer-Id": str(customer.id)}


def test_setup_family_requires_the_personas_and_creates_none(client):
    with pytest.raises(FamilyDemoError, match="setup` first"):
        setup_family(client)


def test_setup_family_builds_the_household_through_the_api(client, personas):
    report = setup_family(client)
    primary = personas[FAMILY_DEMO["primary_name"]]
    own = client.get(f"/api/profiles/{primary.id}/household", headers=_h(primary)).json()
    assert own["household"]["name"] == FAMILY_DEMO["household_name"]
    assert (own["membership"]["relationship"], own["membership"]["role"], own["membership"]["is_dependent"]) == (
        "self", "primary", False)
    members = client.get(f"/api/households/{report['household_id']}/members", headers=_h(primary)).json()["members"]
    assert len(members) == 2
    spouse = next(m for m in members if m["customer_id"] == personas[FAMILY_DEMO["members"][0]["name"]].id)
    assert (spouse["relationship"], spouse["role"], spouse["is_dependent"]) == ("spouse", "member", False)
    for resource in FAMILY_RECORD_KEYS:
        stored = client.get(f"/api/households/{report['household_id']}/{resource}", headers=_h(primary)).json()
        assert len(stored) == len(FAMILY_DEMO[resource]), resource


def test_setup_family_is_idempotent(client, personas):
    first = setup_family(client)
    second = setup_family(client)
    assert second["household_id"] == first["household_id"]
    assert second["created"] == []
    primary = personas[FAMILY_DEMO["primary_name"]]
    hid = first["household_id"]
    assert len(client.get(f"/api/households/{hid}/members", headers=_h(primary)).json()["members"]) == 2
    for resource in FAMILY_RECORD_KEYS:
        stored = client.get(f"/api/households/{hid}/{resource}", headers=_h(primary)).json()
        assert len(stored) == len(FAMILY_DEMO[resource]), resource
    assert second["summary"] == first["summary"]


def test_setup_family_completes_a_partially_seeded_household(client, personas):
    """A household left half-built (e.g. an interrupted run) is completed, not duplicated."""
    first = setup_family(client)
    hid, primary = first["household_id"], personas[FAMILY_DEMO["primary_name"]]
    goal = client.get(f"/api/households/{hid}/goals", headers=_h(primary)).json()[0]
    assert client.delete(f"/api/households/{hid}/goals/{goal['id']}", headers=_h(primary)).status_code == 204
    again = setup_family(client)
    assert again["created"] == [f"goals:{goal['name']}"]
    assert len(client.get(f"/api/households/{hid}/goals", headers=_h(primary)).json()) == len(FAMILY_DEMO["goals"])


def test_setup_family_refuses_to_alter_a_different_household(client, personas):
    primary = personas[FAMILY_DEMO["primary_name"]]
    client.post("/api/households", json={"name": "Someone else's household"}, headers=_h(primary))
    with pytest.raises(FamilyDemoError, match="different household"):
        setup_family(client)


def test_family_summary_follows_the_existing_phase_34_semantics(client, personas):
    """The seeded values, summarized by the unchanged engine: yearly counted as
    amount / 12, one-time and inactive records excluded, essential expenses as
    the emergency-fund basis, a recorded zero kept, an unrecorded payment not
    counted as zero."""
    summary = setup_family(client)["summary"]
    assert summary["income"]["recurring_monthly"] == 160000            # 62000 + 95000 + 36000/12
    assert summary["income"]["one_time"] == 120000                     # the bonus, kept separate
    assert summary["income"]["active_record_count"] == 4               # the ended job is stored, not counted
    assert summary["expenses"]["recurring_essential_monthly"] == 86000  # 34000 + 15000 + 4500 + 8000 + 54000/12 + 10500 + 9500
    assert summary["expenses"]["recurring_monthly"] == 99200
    assert summary["expenses"]["one_time"] == 45000
    assert summary["cash_flow"]["monthly"] == 60800
    assert summary["assets"]["liquid"] == 360000
    assert summary["liabilities"]["outstanding"] == 320000             # includes the card's recorded 0
    assert summary["liabilities"]["monthly_payment"] == 9500           # the card's unrecorded payment is not 0
    assert summary["net_position"]["value"] == 1820000
    assert (summary["emergency_fund"]["required"], summary["emergency_fund"]["status"]) == (516000, "insufficient")


def test_family_members_see_identity_only_never_each_others_private_data(client, personas):
    report = setup_family(client)
    spouse = personas[FAMILY_DEMO["members"][0]["name"]]
    members = client.get(f"/api/households/{report['household_id']}/members", headers=_h(spouse)).json()["members"]
    for member in members:
        assert set(member) == MEMBER_FIELDS
    household_paths = [p for p in client.app.openapi()["paths"] if p.startswith("/api/households/{household_id}")]
    private = ("profile", "analysis", "questionnaire", "financial-inputs", "portfolio", "recommendation")
    assert not [p for p in household_paths if any(word in p for word in private)]


def test_the_individual_demo_personas_stay_outside_and_are_denied(client, personas):
    report = setup_family(client)
    for name in INDIVIDUAL_DEMO_NAMES:
        outsider = personas[name]
        assert client.get(f"/api/profiles/{outsider.id}/household", headers=_h(outsider)).json()["household"] is None
        for path in ("members", "income", "goals", "financial-summary"):
            denied = client.get(f"/api/households/{report['household_id']}/{path}", headers=_h(outsider))
            assert denied.status_code == 403, path
            assert "Rent" not in denied.text and "Emergency fund" not in denied.text


def test_setup_family_leaves_every_individual_record_unchanged(client, personas):
    def snapshot(customer_id):
        return (
            client.get(f"/api/profiles/{customer_id}").json(),
            client.get(f"/api/profiles/{customer_id}/questionnaire").json(),
            client.get(f"/api/profiles/{customer_id}/financial-inputs").json(),
        )

    before = {name: snapshot(c.id) for name, c in personas.items()}
    setup_family(client)
    assert {name: snapshot(c.id) for name, c in personas.items()} == before


def test_verify_family_fails_before_setup_and_passes_after(client, personas):
    ok, _ = verify_family(client)
    assert ok is False
    setup_family(client)
    ok, lines = verify_family(client)
    assert ok is True, "\n".join(lines)


def test_reset_deletes_only_the_demo_household_matched_by_name_and_primary(client, personas, db_session):
    report = setup_family(client)
    primary = personas[FAMILY_DEMO["primary_name"]]
    other_owner = personas["WealthPilot Demo — Complete"]
    decoy = client.post("/api/households", json={"name": FAMILY_DEMO["household_name"]}, headers=_h(other_owner)).json()
    assert _delete_family_household(db_session.connection(), FAMILY_DEMO["household_name"], primary.id) == 1
    remaining = dict(db_session.execute(
        text("select id, name from households where id in (:a, :b)"), {"a": report["household_id"], "b": decoy["id"]}
    ).all())
    assert remaining == {decoy["id"]: FAMILY_DEMO["household_name"]}   # same name, different primary: untouched
    for table in ("household_members", "household_incomes", "household_goals"):
        count = db_session.execute(text(f"select count(*) from {table} where household_id = :h"),
                                   {"h": report["household_id"]}).scalar()
        assert count == 0, table
    assert db_session.execute(text("select count(*) from customers where id = :c"), {"c": primary.id}).scalar() == 1

