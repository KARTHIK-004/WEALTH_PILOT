"""Phase 33 -- household financial data API (income, expenses, assets, liabilities).

Uses `client` (synthetic customers on TEST_DATABASE_URL, rolled back after each
test). Authorization is Phase 32's, reused: any member may read, only the
primary may mutate, and the caller is the asserted `X-Customer-Id` customer.

The four resources are exercised uniformly through `RESOURCES` so no category
can quietly diverge, plus per-category tests for the parts that genuinely
differ (optional `description`, nullable `monthly_payment`, zero-value rules).
The file also guards the phase boundary: no endpoint returns a total, and
household financial data changes nothing about the individual analysis.
"""

from __future__ import annotations

import pytest

from tests.backend.api.conftest import approved_steps, patch_graph
from wealthpilot.api.main import app


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


# path segment -> (valid create payload, a valid update payload, the field the update changes)
RESOURCES = {
    "income": (
        {"source": "Salary", "amount": 5000, "frequency": "monthly"},
        {"amount": 5500},
        "amount",
    ),
    "expenses": (
        {"category": "housing", "amount": 1200, "frequency": "monthly", "is_essential": True},
        {"amount": 1300},
        "amount",
    ),
    "assets": (
        {"name": "Savings", "asset_type": "bank_account", "current_value": 15000, "is_liquid": True},
        {"current_value": 16000},
        "current_value",
    ),
    "liabilities": (
        {"name": "Home loan", "liability_type": "mortgage", "outstanding_amount": 150000, "monthly_payment": 900},
        {"outstanding_amount": 140000},
        "outstanding_amount",
    ),
}
RESOURCE_NAMES = list(RESOURCES)


def create_household(client, customer, name="Finance Family"):
    response = client.post("/api/households", json={"name": name}, headers=h(customer.id))
    assert response.status_code == 201, response.text
    return response.json()


def add_member(client, household_id, primary, customer, relationship="spouse", role="member"):
    response = client.post(
        f"/api/households/{household_id}/members",
        json={"customer_id": customer.id, "relationship": relationship, "role": role},
        headers=h(primary.id),
    )
    assert response.status_code == 201, response.text
    return response.json()


def post(client, household_id, actor, resource, payload=None):
    body = RESOURCES[resource][0] if payload is None else payload
    return client.post(f"/api/households/{household_id}/{resource}", json=body, headers=h(actor.id))


def seed(client, household_id, actor, resource):
    response = post(client, household_id, actor, resource)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def household_a(client, make_customer):
    """Household A: `primary` plus a non-primary `member`, with one record of
    every resource already stored."""
    primary, member = make_customer(name="A primary"), make_customer(name="A member")
    household = create_household(client, primary, "Household A")
    add_member(client, household["id"], primary, member)
    records = {name: seed(client, household["id"], primary, name) for name in RESOURCE_NAMES}
    return {"primary": primary, "member": member, "household": household, "records": records}


@pytest.fixture()
def household_b(client, make_customer):
    """An unrelated household with its own records."""
    primary = make_customer(name="B primary")
    household = create_household(client, primary, "Household B")
    records = {name: seed(client, household["id"], primary, name) for name in RESOURCE_NAMES}
    return {"primary": primary, "household": household, "records": records}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_primary_can_create_and_the_record_is_returned_as_stored(client, make_customer, resource):
    primary = make_customer()
    household = create_household(client, primary)
    payload = RESOURCES[resource][0]

    response = post(client, household["id"], primary, resource)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] > 0
    assert body["household_id"] == household["id"]  # ownership comes from the path
    assert body["created_at"] and body["updated_at"]
    for field, value in payload.items():
        assert body[field] == value, field


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_a_member_can_read_and_the_list_holds_only_this_households_records(client, household_a, household_b, resource):
    for actor in (household_a["primary"], household_a["member"]):
        response = client.get(f"/api/households/{household_a['household']['id']}/{resource}", headers=h(actor.id))
        assert response.status_code == 200, response.text
        rows = response.json()
        assert isinstance(rows, list) and len(rows) == 1
        assert rows[0]["id"] == household_a["records"][resource]["id"]
        assert rows[0]["household_id"] == household_a["household"]["id"]
        assert rows[0]["id"] != household_b["records"][resource]["id"]


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_primary_can_update_only_the_supplied_fields(client, household_a, resource):
    household_id = household_a["household"]["id"]
    record = household_a["records"][resource]
    created_payload, update_payload, changed_field = RESOURCES[resource]

    response = client.put(
        f"/api/households/{household_id}/{resource}/{record['id']}", json=update_payload, headers=h(household_a["primary"].id)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == record["id"] and body["household_id"] == household_id
    assert body[changed_field] == update_payload[changed_field]
    for field, value in created_payload.items():
        if field not in update_payload:
            assert body[field] == value, f"{field} should have been left alone"


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_update_does_not_create_a_second_record(client, household_a, resource):
    household_id = household_a["household"]["id"]
    record = household_a["records"][resource]
    client.put(f"/api/households/{household_id}/{resource}/{record['id']}", json=RESOURCES[resource][1], headers=h(household_a["primary"].id))
    rows = client.get(f"/api/households/{household_id}/{resource}", headers=h(household_a["primary"].id)).json()
    assert len(rows) == 1 and rows[0]["id"] == record["id"]


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_primary_can_delete_only_the_targeted_record(client, household_a, resource):
    household_id = household_a["household"]["id"]
    keep = seed(client, household_id, household_a["primary"], resource)
    target = household_a["records"][resource]

    response = client.delete(f"/api/households/{household_id}/{resource}/{target['id']}", headers=h(household_a["primary"].id))
    assert response.status_code == 204 and response.content == b""

    remaining = client.get(f"/api/households/{household_id}/{resource}", headers=h(household_a["primary"].id)).json()
    assert [row["id"] for row in remaining] == [keep["id"]]
    # deleting it again is a 404 -- the row is really gone
    assert_problem(client.delete(f"/api/households/{household_id}/{resource}/{target['id']}", headers=h(household_a["primary"].id)), 404)


def test_an_empty_household_returns_empty_lists_not_an_error(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    for resource in RESOURCE_NAMES:
        response = client.get(f"/api/households/{household['id']}/{resource}", headers=h(primary.id))
        assert response.status_code == 200 and response.json() == []


def test_many_records_of_the_same_resource_are_all_kept(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    first = seed(client, household["id"], primary, "income")
    second = post(client, household["id"], primary, "income", {"source": "Freelance", "amount": 800, "frequency": "monthly"}).json()
    rows = client.get(f"/api/households/{household['id']}/income", headers=h(primary.id)).json()
    assert [r["id"] for r in rows] == [first["id"], second["id"]]
    assert {r["source"] for r in rows} == {"Salary", "Freelance"}


# ---------------------------------------------------------------------------
# Per-resource specifics
# ---------------------------------------------------------------------------


def test_income_is_active_defaults_to_true_and_can_be_set_false(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    assert post(client, household["id"], primary, "income").json()["is_active"] is True
    body = post(client, household["id"], primary, "income", {"source": "Old job", "amount": 10, "frequency": "monthly", "is_active": False}).json()
    assert body["is_active"] is False


def test_expense_description_is_optional_and_stays_null(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    body = post(client, household["id"], primary, "expenses", {"category": "food", "amount": 300, "frequency": "monthly", "is_essential": True}).json()
    assert body["description"] is None  # absent stays NULL, never ""
    assert body["is_active"] is True


def test_expense_is_essential_has_no_default_and_must_be_stated(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    assert_problem(post(client, household["id"], primary, "expenses", {"category": "food", "amount": 300, "frequency": "monthly"}), 422)


def test_asset_value_may_be_zero(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    body = post(client, household["id"], primary, "assets", {"name": "Empty account", "asset_type": "cash", "current_value": 0, "is_liquid": True}).json()
    assert body["current_value"] == 0


def test_liability_monthly_payment_null_and_zero_are_different_facts(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    omitted = post(client, household["id"], primary, "liabilities", {"name": "Family loan", "liability_type": "personal_loan", "outstanding_amount": 5000}).json()
    explicit_zero = post(client, household["id"], primary, "liabilities", {"name": "Interest free", "liability_type": "other", "outstanding_amount": 100, "monthly_payment": 0}).json()
    assert omitted["monthly_payment"] is None
    assert explicit_zero["monthly_payment"] == 0

    # and an explicit null through PUT clears it back to "not provided"
    cleared = client.put(
        f"/api/households/{household['id']}/liabilities/{explicit_zero['id']}", json={"monthly_payment": None}, headers=h(primary.id)
    ).json()
    assert cleared["monthly_payment"] is None


def test_liability_outstanding_amount_may_be_zero(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    body = post(client, household["id"], primary, "liabilities", {"name": "Paid off", "liability_type": "vehicle_loan", "outstanding_amount": 0}).json()
    assert body["outstanding_amount"] == 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "resource, payload",
    [
        ("income", {"amount": 100, "frequency": "monthly"}),                                   # no source
        ("income", {"source": "S", "frequency": "monthly"}),                                   # no amount
        ("income", {"source": "S", "amount": 100}),                                            # no frequency
        ("expenses", {"amount": 100, "frequency": "monthly", "is_essential": True}),           # no category
        ("expenses", {"category": "food", "frequency": "monthly", "is_essential": True}),      # no amount
        ("assets", {"asset_type": "cash", "current_value": 1, "is_liquid": True}),             # no name
        ("assets", {"name": "A", "current_value": 1, "is_liquid": True}),                      # no asset_type
        ("assets", {"name": "A", "asset_type": "cash", "is_liquid": True}),                    # no current_value
        ("assets", {"name": "A", "asset_type": "cash", "current_value": 1}),                   # no is_liquid
        ("liabilities", {"liability_type": "mortgage", "outstanding_amount": 1}),              # no name
        ("liabilities", {"name": "L", "outstanding_amount": 1}),                               # no liability_type
        ("liabilities", {"name": "L", "liability_type": "mortgage"}),                          # no outstanding_amount
    ],
)
def test_missing_required_fields_are_422(client, make_customer, resource, payload):
    primary = make_customer()
    household = create_household(client, primary)
    assert_problem(post(client, household["id"], primary, resource, payload), 422)


@pytest.mark.parametrize("frequency", ["weekly", "Monthly", "", "daily", 5])
def test_invalid_frequency_is_422(client, make_customer, frequency):
    primary = make_customer()
    household = create_household(client, primary)
    assert_problem(post(client, household["id"], primary, "income", {"source": "S", "amount": 10, "frequency": frequency}), 422)
    assert_problem(post(client, household["id"], primary, "expenses", {"category": "food", "amount": 10, "frequency": frequency, "is_essential": False}), 422)


@pytest.mark.parametrize(
    "resource, payload",
    [
        ("expenses", {"category": "groceries", "amount": 10, "frequency": "monthly", "is_essential": True}),
        ("expenses", {"category": "Housing", "amount": 10, "frequency": "monthly", "is_essential": True}),
        ("assets", {"name": "A", "asset_type": "crypto", "current_value": 1, "is_liquid": True}),
        ("assets", {"name": "A", "asset_type": "Cash", "current_value": 1, "is_liquid": True}),
        ("liabilities", {"name": "L", "liability_type": "payday_loan", "outstanding_amount": 1}),
        ("liabilities", {"name": "L", "liability_type": "Mortgage", "outstanding_amount": 1}),
    ],
)
def test_invalid_category_or_type_is_422(client, make_customer, resource, payload):
    primary = make_customer()
    household = create_household(client, primary)
    assert_problem(post(client, household["id"], primary, resource, payload), 422)


@pytest.mark.parametrize("amount", [0, -0.01, -100])
def test_income_and_expense_amounts_must_be_strictly_positive(client, make_customer, amount):
    primary = make_customer()
    household = create_household(client, primary)
    assert_problem(post(client, household["id"], primary, "income", {"source": "S", "amount": amount, "frequency": "monthly"}), 422)
    assert_problem(post(client, household["id"], primary, "expenses", {"category": "food", "amount": amount, "frequency": "monthly", "is_essential": True}), 422)


def test_negative_asset_and_liability_values_are_422(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    assert_problem(post(client, household["id"], primary, "assets", {"name": "A", "asset_type": "cash", "current_value": -1, "is_liquid": True}), 422)
    assert_problem(post(client, household["id"], primary, "liabilities", {"name": "L", "liability_type": "other", "outstanding_amount": -1}), 422)
    assert_problem(post(client, household["id"], primary, "liabilities", {"name": "L", "liability_type": "other", "outstanding_amount": 10, "monthly_payment": -1}), 422)


def test_blank_free_text_identifiers_are_422(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    assert_problem(post(client, household["id"], primary, "income", {"source": "   ", "amount": 10, "frequency": "monthly"}), 422)
    assert_problem(post(client, household["id"], primary, "assets", {"name": "  ", "asset_type": "cash", "current_value": 1, "is_liquid": True}), 422)
    assert_problem(post(client, household["id"], primary, "liabilities", {"name": "", "liability_type": "other", "outstanding_amount": 1}), 422)


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_unknown_fields_are_rejected(client, make_customer, resource):
    """Nothing outside the phase's own contract can be smuggled in -- including
    a computed-looking field."""
    primary = make_customer()
    household = create_household(client, primary)
    for extra in ({"total": 1}, {"net_worth": 1}, {"customer_id": 1}, {"currency": "EUR"}):
        assert_problem(post(client, household["id"], primary, resource, {**RESOURCES[resource][0], **extra}), 422)


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_invalid_values_are_rejected_on_update_too(client, household_a, resource):
    household_id = household_a["household"]["id"]
    record_id = household_a["records"][resource]["id"]
    bad = {"income": {"amount": 0}, "expenses": {"amount": -5}, "assets": {"current_value": -1}, "liabilities": {"outstanding_amount": -1}}[resource]
    assert_problem(client.put(f"/api/households/{household_id}/{resource}/{record_id}", json=bad, headers=h(household_a["primary"].id)), 422)
    assert_problem(client.put(f"/api/households/{household_id}/{resource}/{record_id}", json={"nonsense": 1}, headers=h(household_a["primary"].id)), 422)


# ---------------------------------------------------------------------------
# Authorization and isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_missing_or_malformed_identity_is_401_on_every_route(client, household_a, resource):
    household_id = household_a["household"]["id"]
    record_id = household_a["records"][resource]["id"]
    for headers in ({}, {"X-Customer-Id": ""}, {"X-Customer-Id": "abc"}, {"X-Customer-Id": "0"}, {"X-Customer-Id": "-3"}):
        assert_problem(client.get(f"/api/households/{household_id}/{resource}", headers=headers), 401)
        assert_problem(client.post(f"/api/households/{household_id}/{resource}", json=RESOURCES[resource][0], headers=headers), 401)
        assert_problem(client.put(f"/api/households/{household_id}/{resource}/{record_id}", json=RESOURCES[resource][1], headers=headers), 401)
        assert_problem(client.delete(f"/api/households/{household_id}/{resource}/{record_id}", headers=headers), 401)


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_a_non_member_is_denied_on_every_route(client, household_a, household_b, resource):
    """Customer B (a different household) and an outsider with no household."""
    household_id = household_a["household"]["id"]
    record_id = household_a["records"][resource]["id"]
    for outsider in (household_b["primary"],):
        assert_problem(client.get(f"/api/households/{household_id}/{resource}", headers=h(outsider.id)), 403)
        assert_problem(client.post(f"/api/households/{household_id}/{resource}", json=RESOURCES[resource][0], headers=h(outsider.id)), 403)
        assert_problem(client.put(f"/api/households/{household_id}/{resource}/{record_id}", json=RESOURCES[resource][1], headers=h(outsider.id)), 403)
        assert_problem(client.delete(f"/api/households/{household_id}/{resource}/{record_id}", headers=h(outsider.id)), 403)


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_a_customer_with_no_household_at_all_is_denied(client, household_a, make_customer, resource):
    outsider = make_customer(name="No household")
    assert_problem(client.get(f"/api/households/{household_a['household']['id']}/{resource}", headers=h(outsider.id)), 403)


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_a_non_primary_member_can_read_but_not_mutate(client, household_a, resource):
    household_id = household_a["household"]["id"]
    record_id = household_a["records"][resource]["id"]
    member = household_a["member"]

    assert client.get(f"/api/households/{household_id}/{resource}", headers=h(member.id)).status_code == 200
    assert_problem(client.post(f"/api/households/{household_id}/{resource}", json=RESOURCES[resource][0], headers=h(member.id)), 403)
    assert_problem(client.put(f"/api/households/{household_id}/{resource}/{record_id}", json=RESOURCES[resource][1], headers=h(member.id)), 403)
    assert_problem(client.delete(f"/api/households/{household_id}/{resource}/{record_id}", headers=h(member.id)), 403)
    # nothing changed
    assert len(client.get(f"/api/households/{household_id}/{resource}", headers=h(member.id)).json()) == 1


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_a_dependent_member_can_read_but_not_mutate(client, household_a, make_customer, resource):
    dependent = make_customer(name="Dependent")
    add_member(client, household_a["household"]["id"], household_a["primary"], dependent, relationship="child", role="dependent")
    assert client.get(f"/api/households/{household_a['household']['id']}/{resource}", headers=h(dependent.id)).status_code == 200
    assert_problem(post(client, household_a["household"]["id"], dependent, resource), 403)


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_unknown_household_is_404_on_every_route(client, make_customer, resource):
    customer = make_customer()
    assert_problem(client.get(f"/api/households/999999999/{resource}", headers=h(customer.id)), 404)
    assert_problem(client.post(f"/api/households/999999999/{resource}", json=RESOURCES[resource][0], headers=h(customer.id)), 404)
    assert_problem(client.put(f"/api/households/999999999/{resource}/1", json=RESOURCES[resource][1], headers=h(customer.id)), 404)
    assert_problem(client.delete(f"/api/households/999999999/{resource}/1", headers=h(customer.id)), 404)


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_a_record_id_cannot_cross_household_boundaries(client, household_a, household_b, resource):
    """A's primary uses A's household in the path but B's record id: a 404 that
    does not reveal the record's existence, and B's record is untouched."""
    a_id, b_record = household_a["household"]["id"], household_b["records"][resource]

    body = assert_problem(
        client.put(f"/api/households/{a_id}/{resource}/{b_record['id']}", json=RESOURCES[resource][1], headers=h(household_a["primary"].id)), 404
    )
    assert str(b_record["id"]) in body["detail"] and "household" in body["detail"].lower()
    assert_problem(client.delete(f"/api/households/{a_id}/{resource}/{b_record['id']}", headers=h(household_a["primary"].id)), 404)

    still_there = client.get(f"/api/households/{household_b['household']['id']}/{resource}", headers=h(household_b["primary"].id)).json()
    assert [row["id"] for row in still_there] == [b_record["id"]]


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_deleting_from_one_household_never_affects_another(client, household_a, household_b, resource):
    a, b = household_a["household"]["id"], household_b["household"]["id"]
    client.delete(f"/api/households/{a}/{resource}/{household_a['records'][resource]['id']}", headers=h(household_a["primary"].id))
    assert client.get(f"/api/households/{a}/{resource}", headers=h(household_a["primary"].id)).json() == []
    assert len(client.get(f"/api/households/{b}/{resource}", headers=h(household_b["primary"].id)).json()) == 1


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_household_ownership_cannot_be_changed_through_an_update(client, household_a, household_b, resource):
    a, b = household_a["household"]["id"], household_b["household"]["id"]
    record = household_a["records"][resource]

    assert_problem(client.put(f"/api/households/{a}/{resource}/{record['id']}", json={"household_id": b}, headers=h(household_a["primary"].id)), 422)
    assert_problem(
        client.put(f"/api/households/{a}/{resource}/{record['id']}", json={**RESOURCES[resource][1], "household_id": b}, headers=h(household_a["primary"].id)), 422
    )
    after = client.get(f"/api/households/{a}/{resource}", headers=h(household_a["primary"].id)).json()
    assert [row["id"] for row in after] == [record["id"]] and after[0]["household_id"] == a
    assert len(client.get(f"/api/households/{b}/{resource}", headers=h(household_b["primary"].id)).json()) == 1


@pytest.mark.parametrize("resource", RESOURCE_NAMES)
def test_a_denied_response_never_leaks_another_households_data(client, household_a, household_b, resource):
    denied = client.get(f"/api/households/{household_a['household']['id']}/{resource}", headers=h(household_b["primary"].id))
    assert denied.status_code == 403
    for value in ("Salary", "Savings", "Home loan", "housing", "Household A"):
        assert value not in denied.text


def test_removing_a_member_does_not_remove_household_financial_data(client, household_a):
    """The records belong to the household, not to a member."""
    household_id = household_a["household"]["id"]
    members = client.get(f"/api/households/{household_id}/members", headers=h(household_a["primary"].id)).json()["members"]
    member_row = next(m for m in members if m["role"] != "primary")

    assert client.delete(f"/api/households/{household_id}/members/{member_row['id']}", headers=h(household_a["primary"].id)).status_code == 204
    for resource in RESOURCE_NAMES:
        assert len(client.get(f"/api/households/{household_id}/{resource}", headers=h(household_a["primary"].id)).json()) == 1


# ---------------------------------------------------------------------------
# Phase boundary: source data only, and nothing else changed
# ---------------------------------------------------------------------------


def test_openapi_exposes_exactly_the_sixteen_financial_routes_and_no_aggregate():
    paths = app.openapi()["paths"]
    finance = {
        (method.upper(), path)
        for path, ops in paths.items()
        for method in ops
        if any(segment in path for segment in ("/income", "/expenses", "/assets", "/liabilities"))
    }
    expected = set()
    for collection, item in (("income", "income_id"), ("expenses", "expense_id"), ("assets", "asset_id"), ("liabilities", "liability_id")):
        expected.add(("GET", f"/api/households/{{household_id}}/{collection}"))
        expected.add(("POST", f"/api/households/{{household_id}}/{collection}"))
        expected.add(("PUT", f"/api/households/{{household_id}}/{collection}/{{{item}}}"))
        expected.add(("DELETE", f"/api/households/{{household_id}}/{collection}/{{{item}}}"))
    assert finance == expected

    # Phase 34 added exactly ONE household calculation route, in its own module
    # and its own test file (`test_household_summary.py`); the CRUD routes above
    # are still pure storage. Any OTHER aggregate route would be a regression.
    aggregates = [p for p in paths if any(w in p.lower() for w in ("summary", "totals", "net-worth", "networth", "savings", "debt-ratio", "cash-flow", "aggregate"))]
    assert aggregates == ["/api/households/{household_id}/financial-summary"]


def test_no_household_financial_schema_contains_a_derived_field():
    """Source records only: no total/sum/ratio/score field anywhere."""
    schemas = app.openapi()["components"]["schemas"]
    # The twelve Phase 33 SOURCE-RECORD schemas, named explicitly: Phase 34's
    # summary sections are aggregates by design and are checked separately in
    # `test_household_summary.py`, so a name-substring filter would now be
    # ambiguous.
    names = [
        f"Household{resource}{kind}"
        for resource in ("Income", "Expense", "Asset", "Liability")
        for kind in ("Create", "Update", "Response")
    ]
    assert all(name in schemas for name in names)
    assert len(names) == 12
    forbidden = ("total", "sum", "net_worth", "ratio", "score", "savings", "cash_flow", "aggregate", "emergency", "average", "monthly_total")
    for name in names:
        for field in schemas[name].get("properties", {}):
            assert not any(word in field.lower() for word in forbidden), f"{name}.{field}"


def test_household_financial_data_does_not_change_the_individual_analysis(client, make_customer, monkeypatch):
    customer = make_customer(name="Analysed")
    patch_graph(monkeypatch, approved_steps(customer.id))
    before = client.post("/api/analysis", json={"profile_id": customer.id})
    assert before.status_code == 200 and before.json()["status"] == "approved"

    household = create_household(client, customer)
    for resource in RESOURCE_NAMES:
        seed(client, household["id"], customer, resource)

    after = client.post("/api/analysis", json={"profile_id": customer.id})
    assert after.status_code == 200
    assert after.json() == before.json()  # identical body, same analysis_id: the cache key did not move


def test_household_financial_data_does_not_touch_individual_financial_inputs(client, make_customer):
    customer = make_customer()
    client.put(f"/api/profiles/{customer.id}/financial-inputs", json={"monthly_essential_expenses": 2000, "current_liquid_assets": 9000})
    before = client.get(f"/api/profiles/{customer.id}/financial-inputs").json()

    household = create_household(client, customer)
    for resource in RESOURCE_NAMES:
        seed(client, household["id"], customer, resource)

    assert client.get(f"/api/profiles/{customer.id}/financial-inputs").json() == before


def test_a_members_own_financial_inputs_are_not_shared_with_the_household(client, household_a):
    """Individual and household financial data stay separate in both directions."""
    member = household_a["member"]
    assert client.get(f"/api/profiles/{member.id}/financial-inputs").json()["monthly_essential_expenses"] is None
    client.put(f"/api/profiles/{member.id}/financial-inputs", json={"monthly_essential_expenses": 1234})

    rows = client.get(f"/api/households/{household_a['household']['id']}/expenses", headers=h(household_a["primary"].id)).json()
    assert [row["amount"] for row in rows] == [1200]  # the household's own expense, untouched by the member's input
