"""Phase 36 — household goals API (`/api/households/{id}/goals`).

Uses `client` (synthetic customers on TEST_DATABASE_URL, rolled back after each
test). Authorization is Phase 32/33's, reused: any member may read, only the
primary may mutate, and the caller is the asserted `X-Customer-Id` customer.

Beyond CRUD, validation, authorization and isolation, this file guards the
phase boundary: a household goal is stored facts only (no derived goal figure
anywhere), it never touches an individual goal or the individual analysis, and
an `emergency_fund` goal never becomes a second source of truth for the
emergency-fund requirement Phase 34's summary already computes (ADR-035).
"""

from __future__ import annotations

import pytest

from tests.backend.api.conftest import approved_steps, patch_graph
from wealthpilot.api.main import app
from wealthpilot.core.goals import assess_emergency_fund

GOALS = "/api/households/{}/goals"
GOAL = "/api/households/{}/goals/{}"


def h(customer_id) -> dict[str, str]:
    return {"X-Customer-Id": str(customer_id)}


def assert_problem(response, status: int) -> dict:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == status
    assert body["title"] and body["detail"] and body["instance"]
    assert "Traceback" not in body["detail"] and "sqlalchemy" not in body["detail"].lower()
    return body


VALID = {"name": "New home", "goal_type": "house", "target_amount": 60000, "target_date": "2030-06-30"}


def create_household(client, customer, name="Goal Family"):
    response = client.post("/api/households", json={"name": name}, headers=h(customer.id))
    assert response.status_code == 201, response.text
    return response.json()


def add_member(client, household_id, primary, customer, relationship="spouse", role="member"):
    response = client.post(f"/api/households/{household_id}/members",
                           json={"customer_id": customer.id, "relationship": relationship, "role": role},
                           headers=h(primary.id))
    assert response.status_code == 201, response.text


def add_goal(client, household_id, actor, **overrides):
    response = client.post(GOALS.format(household_id), json={**VALID, **overrides}, headers=h(actor.id))
    assert response.status_code == 201, response.text
    return response.json()


def add_record(client, household_id, actor, resource, **payload):
    response = client.post(f"/api/households/{household_id}/{resource}", json=payload, headers=h(actor.id))
    assert response.status_code == 201, response.text
    return response.json()


def summary_of(client, household_id, actor):
    response = client.get(f"/api/households/{household_id}/financial-summary", headers=h(actor.id))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def family(client, make_customer):
    primary = make_customer(name="Goals Primary")
    member = make_customer(name="Goals Member")
    dependent = make_customer(name="Goals Dependent")
    created = create_household(client, primary)
    add_member(client, created["id"], primary, member)
    add_member(client, created["id"], primary, dependent, relationship="child", role="dependent")
    return {"id": created["id"], "primary": primary, "member": member, "dependent": dependent}


# ---------------------------------------------------------------- CRUD


def test_create_returns_the_goal_as_stored(client, family):
    goal = add_goal(client, family["id"], family["primary"], current_savings=12500, notes="Deposit")
    assert goal["household_id"] == family["id"]
    assert (goal["name"], goal["goal_type"], goal["target_amount"], goal["current_savings"],
            goal["target_date"], goal["notes"], goal["is_active"]) == (
        "New home", "house", 60000, 12500, "2030-06-30", "Deposit", True)


def test_list_returns_every_goal_in_id_order(client, family):
    ids = [add_goal(client, family["id"], family["primary"], name=n)["id"] for n in ("A", "B", "C")]
    listed = client.get(GOALS.format(family["id"]), headers=h(family["primary"].id)).json()
    assert [g["id"] for g in listed] == sorted(ids)


def test_get_one_returns_that_goal(client, family):
    goal = add_goal(client, family["id"], family["primary"])
    fetched = client.get(GOAL.format(family["id"], goal["id"]), headers=h(family["primary"].id))
    assert fetched.status_code == 200 and fetched.json() == goal


def test_update_changes_only_the_supplied_fields(client, family):
    goal = add_goal(client, family["id"], family["primary"], current_savings=100)
    updated = client.put(GOAL.format(family["id"], goal["id"]), json={"current_savings": 250},
                         headers=h(family["primary"].id)).json()
    assert updated["current_savings"] == 250
    assert (updated["name"], updated["target_amount"], updated["target_date"]) == ("New home", 60000, "2030-06-30")


def test_delete_removes_only_that_goal(client, family):
    keep = add_goal(client, family["id"], family["primary"], name="Keep")
    drop = add_goal(client, family["id"], family["primary"], name="Drop")
    assert client.delete(GOAL.format(family["id"], drop["id"]), headers=h(family["primary"].id)).status_code == 204
    listed = client.get(GOALS.format(family["id"]), headers=h(family["primary"].id)).json()
    assert [g["id"] for g in listed] == [keep["id"]]
    assert_problem(client.get(GOAL.format(family["id"], drop["id"]), headers=h(family["primary"].id)), 404)


def test_an_empty_household_lists_no_goals(client, family):
    assert client.get(GOALS.format(family["id"]), headers=h(family["primary"].id)).json() == []


@pytest.mark.parametrize("goal_type", ["emergency_fund", "house", "education", "retirement", "travel", "major_purchase", "other"])
def test_every_goal_type_can_be_created(client, family, goal_type):
    assert add_goal(client, family["id"], family["primary"], goal_type=goal_type)["goal_type"] == goal_type


# ------------------------------------------------------ null versus zero


def test_current_savings_omitted_stays_null_never_zero(client, family):
    assert add_goal(client, family["id"], family["primary"])["current_savings"] is None


def test_current_savings_recorded_zero_stays_zero(client, family):
    assert add_goal(client, family["id"], family["primary"], current_savings=0)["current_savings"] == 0


def test_current_savings_can_be_cleared_back_to_not_provided(client, family):
    goal = add_goal(client, family["id"], family["primary"], current_savings=500)
    cleared = client.put(GOAL.format(family["id"], goal["id"]), json={"current_savings": None},
                         headers=h(family["primary"].id)).json()
    assert cleared["current_savings"] is None


# ------------------------------------------------------------ is_active


def test_inactive_goals_are_stored_listed_and_reactivatable(client, family):
    """The Phase 33 convention: `is_active` is a stored fact. Nothing aggregates
    goals, so an inactive goal is simply kept and shown, never deleted."""
    goal = add_goal(client, family["id"], family["primary"], is_active=False)
    assert goal["is_active"] is False
    listed = client.get(GOALS.format(family["id"]), headers=h(family["primary"].id)).json()
    assert [g["is_active"] for g in listed] == [False]
    reactivated = client.put(GOAL.format(family["id"], goal["id"]), json={"is_active": True},
                             headers=h(family["primary"].id)).json()
    assert reactivated["is_active"] is True


def test_is_active_defaults_to_true(client, family):
    assert add_goal(client, family["id"], family["primary"])["is_active"] is True


# ----------------------------------------------------------- validation


@pytest.mark.parametrize("field", ["name", "goal_type", "target_amount", "target_date"])
def test_a_missing_required_field_is_422(client, family, field):
    payload = {k: v for k, v in VALID.items() if k != field}
    assert_problem(client.post(GOALS.format(family["id"]), json=payload, headers=h(family["primary"].id)), 422)


@pytest.mark.parametrize("overrides", [
    {"name": ""}, {"name": "   "}, {"name": "x" * 101},
    {"goal_type": "vacation"}, {"goal_type": "House"}, {"goal_type": ""},
    {"target_amount": 0}, {"target_amount": -1}, {"target_amount": "abc"}, {"target_amount": "1e400"}, {"target_amount": None},
    {"target_amount": "inf"}, {"target_amount": 1e13}, {"current_savings": "inf"}, {"current_savings": 1e13},
    {"current_savings": -0.01}, {"current_savings": "lots"},
    {"target_date": "2026-02-30"}, {"target_date": "not-a-date"}, {"target_date": "30/06/2030"}, {"target_date": 20300630},
    {"is_active": "maybe"}, {"is_active": [1]},
    {"notes": "x" * 501},
    {"household_id": 999}, {"customer_id": 1}, {"priority": 1}, {"feasibility": "Feasible"},
])
def test_invalid_input_is_422(client, family, overrides):
    assert_problem(client.post(GOALS.format(family["id"]), json={**VALID, **overrides},
                               headers=h(family["primary"].id)), 422)


def test_the_largest_storable_amount_is_accepted(client, family):
    """The upper bound is the Numeric(14, 2) storage limit -- a value it can hold
    is stored exactly; one it cannot is a 422 (above), never a database 500."""
    goal = add_goal(client, family["id"], family["primary"], target_amount=999999999999.99)
    assert goal["target_amount"] == 999999999999.99


@pytest.mark.parametrize("field", ["name", "goal_type", "target_amount", "target_date", "is_active"])
def test_a_required_field_cannot_be_cleared_with_null(client, family, field):
    """An explicit null on a required field is a client error (422), never a 500
    from the NOT NULL column."""
    goal = add_goal(client, family["id"], family["primary"])
    body = assert_problem(client.put(GOAL.format(family["id"], goal["id"]), json={field: None},
                                     headers=h(family["primary"].id)), 422)
    assert field in body["detail"]


def test_household_id_cannot_be_changed_through_an_update(client, family, make_customer):
    other = create_household(client, make_customer(name="Goals Other"), "Other")
    goal = add_goal(client, family["id"], family["primary"])
    assert_problem(client.put(GOAL.format(family["id"], goal["id"]), json={"household_id": other["id"]},
                              headers=h(family["primary"].id)), 422)


# ---------------------------------------------------------- permissions


def test_any_member_can_read(client, family):
    goal = add_goal(client, family["id"], family["primary"])
    for actor in ("member", "dependent"):
        assert client.get(GOALS.format(family["id"]), headers=h(family[actor].id)).json()[0]["id"] == goal["id"]
        assert client.get(GOAL.format(family["id"], goal["id"]), headers=h(family[actor].id)).status_code == 200


@pytest.mark.parametrize("actor", ["member", "dependent"])
def test_only_the_primary_can_create_update_or_delete(client, family, actor):
    goal = add_goal(client, family["id"], family["primary"])
    who = h(family[actor].id)
    assert_problem(client.post(GOALS.format(family["id"]), json=VALID, headers=who), 403)
    assert_problem(client.put(GOAL.format(family["id"], goal["id"]), json={"name": "x"}, headers=who), 403)
    assert_problem(client.delete(GOAL.format(family["id"], goal["id"]), headers=who), 403)
    unchanged = client.get(GOAL.format(family["id"], goal["id"]), headers=h(family["primary"].id)).json()
    assert unchanged == goal


def test_a_non_member_is_denied_everything(client, family, make_customer):
    outsider = make_customer(name="Goals Outsider")
    goal = add_goal(client, family["id"], family["primary"], name="Secret goal", target_amount=987654)
    who = h(outsider.id)
    for response in (
        client.get(GOALS.format(family["id"]), headers=who),
        client.get(GOAL.format(family["id"], goal["id"]), headers=who),
        client.post(GOALS.format(family["id"]), json=VALID, headers=who),
        client.put(GOAL.format(family["id"], goal["id"]), json={"name": "x"}, headers=who),
        client.delete(GOAL.format(family["id"], goal["id"]), headers=who),
    ):
        body = assert_problem(response, 403)
        assert "Secret goal" not in str(body) and "987654" not in str(body)


def test_an_unknown_household_is_404(client, family):
    assert_problem(client.get(GOALS.format(9_999_999), headers=h(family["primary"].id)), 404)


def test_an_unknown_goal_is_404(client, family):
    assert_problem(client.get(GOAL.format(family["id"], 9_999_999), headers=h(family["primary"].id)), 404)


@pytest.mark.parametrize("identity", [None, "abc", "0", "-3", "1.5"])
def test_a_missing_or_malformed_identity_is_401(client, family, identity):
    headers = {} if identity is None else {"X-Customer-Id": identity}
    assert_problem(client.get(GOALS.format(family["id"]), headers=headers), 401)


# ------------------------------------------------------------ isolation


@pytest.fixture()
def two(client, make_customer):
    a_primary, b_primary = make_customer(name="Goal A"), make_customer(name="Goal B")
    a, b = create_household(client, a_primary, "Goal House A"), create_household(client, b_primary, "Goal House B")
    a_goal = add_goal(client, a["id"], a_primary, name="A-SECRET-GOAL", target_amount=111111, notes="A-NOTE")
    b_goal = add_goal(client, b["id"], b_primary, name="B-SECRET-GOAL", target_amount=222222, notes="B-NOTE")
    return {"a": a, "b": b, "a_primary": a_primary, "b_primary": b_primary, "a_goal": a_goal, "b_goal": b_goal}


@pytest.mark.parametrize("attacker, victim", [("a", "b"), ("b", "a")])
def test_neither_household_can_read_list_modify_or_delete_the_other(client, two, attacker, victim):
    vid, vgoal = two[victim]["id"], two[f"{victim}_goal"]["id"]
    who = h(two[f"{attacker}_primary"].id)
    secrets = (f"{victim.upper()}-SECRET-GOAL", f"{victim.upper()}-NOTE", "111111" if victim == "a" else "222222")
    for response in (
        client.get(GOALS.format(vid), headers=who),
        client.get(GOAL.format(vid, vgoal), headers=who),
        client.post(GOALS.format(vid), json=VALID, headers=who),
        client.put(GOAL.format(vid, vgoal), json={"name": "tampered"}, headers=who),
        client.delete(GOAL.format(vid, vgoal), headers=who),
    ):
        body = assert_problem(response, 403)
        assert not any(secret in str(body) for secret in secrets)
    still = client.get(GOAL.format(vid, vgoal), headers=h(two[f"{victim}_primary"].id)).json()
    assert still == two[f"{victim}_goal"]


def test_a_goal_id_from_another_household_is_404_on_every_verb(client, two):
    """Goal-ID substitution: A's own household path, B's goal id."""
    who, path = h(two["a_primary"].id), GOAL.format(two["a"]["id"], two["b_goal"]["id"])
    for response in (client.get(path, headers=who), client.put(path, json={"name": "x"}, headers=who),
                     client.delete(path, headers=who)):
        body = assert_problem(response, 404)
        assert "B-SECRET-GOAL" not in str(body) and "222222" not in str(body)
    assert client.get(GOAL.format(two["b"]["id"], two["b_goal"]["id"]),
                      headers=h(two["b_primary"].id)).json() == two["b_goal"]


def test_each_household_lists_only_its_own_goals(client, two):
    a = client.get(GOALS.format(two["a"]["id"]), headers=h(two["a_primary"].id)).json()
    b = client.get(GOALS.format(two["b"]["id"]), headers=h(two["b_primary"].id)).json()
    assert [g["name"] for g in a] == ["A-SECRET-GOAL"]
    assert [g["name"] for g in b] == ["B-SECRET-GOAL"]


# ------------------------------------------------------ hostile strings


@pytest.mark.parametrize("hostile", [
    "'; DROP TABLE household_goals; --",
    "Robert'); DELETE FROM households WHERE ('1'='1",
    "<script>alert('x')</script>",
    "<img src=x onerror=alert(1)>",
])
def test_hostile_names_and_notes_are_stored_verbatim_as_data(client, family, hostile):
    goal = add_goal(client, family["id"], family["primary"], name=hostile[:100], notes=hostile)
    assert (goal["name"], goal["notes"]) == (hostile[:100], hostile)
    listed = client.get(GOALS.format(family["id"]), headers=h(family["primary"].id))
    assert listed.status_code == 200 and listed.json()[0]["notes"] == hostile


# ----------------------------------------------- emergency-fund integration


def test_an_emergency_fund_goal_never_changes_the_calculated_requirement(client, family):
    """ADR-035: the goal stores the household's own stated target; the summary's
    requirement (6 x essential expenses, Phase 34) stays the single calculated
    figure, unaffected by any goal."""
    hid, p = family["id"], family["primary"]
    add_record(client, hid, p, "expenses", category="housing", amount=1000, frequency="monthly", is_essential=True)
    add_record(client, hid, p, "assets", name="Cash", asset_type="cash", current_value=4000, is_liquid=True)
    before = summary_of(client, hid, p)
    goal = add_goal(client, hid, p, name="Rainy day", goal_type="emergency_fund", target_amount=25000, current_savings=4000)
    after = summary_of(client, hid, p)
    assert after == before
    assert after["emergency_fund"]["required"] == 6000        # calculated, unchanged
    assert goal["target_amount"] == 25000                     # the household's own stated target


def test_the_summary_emergency_fund_still_agrees_with_the_individual_engine(client, family):
    hid, p = family["id"], family["primary"]
    add_record(client, hid, p, "expenses", category="food", amount=1500, frequency="monthly", is_essential=True)
    add_record(client, hid, p, "assets", name="Cash", asset_type="cash", current_value=7000, is_liquid=True)
    add_goal(client, hid, p, goal_type="emergency_fund", target_amount=9000)
    fund = summary_of(client, hid, p)["emergency_fund"]
    individual = assess_emergency_fund(monthly_essential_expenses=1500, current_liquid_assets=7000)
    assert fund["required"] == pytest.approx(individual.required_amount)
    assert fund["shortfall"] == pytest.approx(individual.shortfall)
    assert (fund["status"] == "sufficient") is individual.sufficient


def test_the_financial_summary_is_unchanged_by_goals(client, family):
    """Phase 34 regression: aggregation, NULL-vs-zero and is_active semantics
    are exactly as before once goals exist."""
    hid, p = family["id"], family["primary"]
    add_record(client, hid, p, "income", source="Salary", amount=5000, frequency="monthly")
    add_record(client, hid, p, "income", source="Old", amount=900, frequency="monthly", is_active=False)
    add_record(client, hid, p, "assets", name="Emptied", asset_type="cash", current_value=0, is_liquid=True)
    before = summary_of(client, hid, p)
    for goal_type in ("emergency_fund", "house", "retirement"):
        add_goal(client, hid, p, goal_type=goal_type, current_savings=0)
    after = summary_of(client, hid, p)
    assert after == before
    assert after["income"]["recurring_monthly"] == 5000        # inactive still excluded
    assert after["assets"]["liquid"] == 0                      # a known zero
    assert after["liabilities"]["outstanding"] is None         # still unknown, not zero


# -------------------------------------------------- no derived goal figure


def test_no_goal_response_or_schema_carries_a_derived_figure(client, family):
    goal = add_goal(client, family["id"], family["primary"], current_savings=100)
    forbidden = ("inflation", "adjusted", "required", "contribution", "gap", "probability", "feasib",
                 "priority", "rank", "score", "recommend")
    assert not [k for k in goal if any(word in k for word in forbidden)]
    schemas = app.openapi()["components"]["schemas"]
    for name in ("HouseholdGoalCreate", "HouseholdGoalUpdate", "HouseholdGoalResponse"):
        assert not [f for f in schemas[name]["properties"] if any(word in f for word in forbidden)], name


def test_the_goal_routes_are_exactly_the_five_documented_ones():
    paths = app.openapi()["paths"]
    goal_routes = {(m.upper(), p) for p, ops in paths.items() if p.startswith("/api/households/") and "/goals" in p for m in ops}
    assert goal_routes == {
        ("GET", "/api/households/{household_id}/goals"),
        ("POST", "/api/households/{household_id}/goals"),
        ("GET", "/api/households/{household_id}/goals/{goal_id}"),
        ("PUT", "/api/households/{household_id}/goals/{goal_id}"),
        ("DELETE", "/api/households/{household_id}/goals/{goal_id}"),
    }
    assert not [p for p in paths if "goal" in p and any(w in p for w in ("feasib", "projection", "plan", "recommend"))]


# ------------------------------------------------ individual-goal regression


def test_household_goals_never_touch_the_individual_goals(client, make_customer):
    customer = make_customer(name="Goals Individual")
    created = client.post(f"/api/profiles/{customer.id}/goals",
                          json={"goal_type": "Retirement", "target_amount": 250000, "target_date": "2045-01-01",
                                "current_savings": 10000, "priority": 2})
    assert created.status_code == 201, created.text
    before = client.get(f"/api/profiles/{customer.id}").json()["goals"]

    hid = create_household(client, customer)["id"]
    add_goal(client, hid, customer, goal_type="retirement", target_amount=999999, current_savings=1)
    add_goal(client, hid, customer, goal_type="house")

    after = client.get(f"/api/profiles/{customer.id}").json()["goals"]
    assert after == before and len(after) == 1
    assert after[0]["target_amount"] == 250000 and after[0]["priority"] == 2


def test_household_goals_do_not_change_the_individual_analysis(client, make_customer, monkeypatch):
    customer = make_customer(name="Goals Analysed")
    patch_graph(monkeypatch, approved_steps(customer.id))
    before = client.post("/api/analysis", json={"profile_id": customer.id})
    assert before.status_code == 200 and before.json()["status"] == "approved"
    hid = create_household(client, customer)["id"]
    add_goal(client, hid, customer, goal_type="emergency_fund", target_amount=50000, current_savings=0)
    after = client.post("/api/analysis", json={"profile_id": customer.id})
    assert after.json() == before.json()


def test_household_goals_do_not_change_the_individual_financial_inputs(client, make_customer):
    customer = make_customer(name="Goals Inputs")
    before = client.get(f"/api/profiles/{customer.id}/financial-inputs").json()
    hid = create_household(client, customer)["id"]
    add_goal(client, hid, customer, goal_type="emergency_fund", target_amount=30000, current_savings=5000)
    assert client.get(f"/api/profiles/{customer.id}/financial-inputs").json() == before
