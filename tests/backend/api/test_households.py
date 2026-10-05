"""Phase 32 -- household identity and membership API.

Uses `client` (synthetic customers on TEST_DATABASE_URL, rolled back after
each test). Every household route needs the caller's associated customer in
`X-Customer-Id`; the isolation tests below use two independent customers who
each own a household, plus a third who owns none.

Household membership is contextual data only: the regression tests at the
end prove it changes nothing in `POST /api/analysis` or the financial-input
endpoints.
"""

from __future__ import annotations

import pytest

from tests.backend.api.conftest import approved_steps, patch_graph
from wealthpilot.api.main import app
from wealthpilot.api.services.analysis_service import compute_profile_hash
from wealthpilot.db.models import Household, HouseholdMember


def h(customer_id) -> dict[str, str]:
    """The caller-identity header every household route requires."""
    return {"X-Customer-Id": str(customer_id)}


def create_household(client, customer, name="My Family"):
    response = client.post("/api/households", json={"name": name}, headers=h(customer.id))
    assert response.status_code == 201, response.text
    return response.json()


def add_member(client, household_id, acting, customer, relationship="spouse", role="member"):
    return client.post(
        f"/api/households/{household_id}/members",
        json={"customer_id": customer.id, "relationship": relationship, "role": role},
        headers=h(acting.id),
    )


def assert_problem(response, status: int) -> dict:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == status
    assert body["title"] and body["detail"] and body["instance"]
    assert "Traceback" not in body["detail"] and "sqlalchemy" not in body["detail"].lower()
    return body


@pytest.fixture()
def two_households(client, make_customer):
    """Customer A owns Household A, customer B owns Household B."""
    a, b = make_customer(name="Customer A"), make_customer(name="Customer B")
    household_a, household_b = create_household(client, a, "Household A"), create_household(client, b, "Household B")
    return a, b, household_a, household_b


# ---------------------------------------------------------------------------
# Creation, automatic primary membership, retrieval, listing
# ---------------------------------------------------------------------------


def test_creating_a_household_makes_the_creator_the_self_primary_member(client, make_customer):
    customer = make_customer(name="Creator")
    household = create_household(client, customer, "  My Family  ")
    assert household["name"] == "My Family"  # trimmed
    assert household["member_count"] == 1
    assert household["created_at"] and household["updated_at"]

    members = client.get(f"/api/households/{household['id']}/members", headers=h(customer.id)).json()["members"]
    assert len(members) == 1
    only = members[0]
    assert (only["customer_id"], only["relationship"], only["role"], only["is_dependent"]) == (customer.id, "self", "primary", False)
    assert only["customer_name"] == "Creator"


def test_no_other_members_are_created_automatically(client, make_customer):
    customer = make_customer()
    household = create_household(client, customer)
    assert client.get(f"/api/households/{household['id']}", headers=h(customer.id)).json()["member_count"] == 1


def test_a_household_can_be_retrieved_by_a_member(client, make_customer):
    customer = make_customer()
    household = create_household(client, customer, "Retrieval")
    response = client.get(f"/api/households/{household['id']}", headers=h(customer.id))
    assert response.status_code == 200
    assert response.json()["name"] == "Retrieval" and response.json()["id"] == household["id"]


def test_members_are_listed_with_the_primary_first(client, make_customer):
    primary, spouse, parent = make_customer(name="P"), make_customer(name="S"), make_customer(name="Par")
    household = create_household(client, primary)
    assert add_member(client, household["id"], primary, spouse, "spouse", "member").status_code == 201
    assert add_member(client, household["id"], primary, parent, "parent", "member").status_code == 201

    members = client.get(f"/api/households/{household['id']}/members", headers=h(spouse.id)).json()["members"]  # a non-primary member may view
    assert [(m["customer_name"], m["relationship"], m["role"]) for m in members] == [
        ("P", "self", "primary"), ("S", "spouse", "member"), ("Par", "parent", "member"),
    ]
    assert client.get(f"/api/households/{household['id']}", headers=h(primary.id)).json()["member_count"] == 3


def test_an_unknown_customer_cannot_create_a_household(client):
    assert_problem(client.post("/api/households", json={"name": "Ghost"}, headers=h(999_999_999)), 404)


def test_a_customer_can_create_only_one_household(client, make_customer):
    customer = make_customer()
    create_household(client, customer)
    body = assert_problem(client.post("/api/households", json={"name": "Second"}, headers=h(customer.id)), 409)
    assert "at most one" in body["detail"]


def test_household_creation_rejects_blank_or_unknown_fields(client, make_customer):
    customer = make_customer()
    assert_problem(client.post("/api/households", json={"name": "   "}, headers=h(customer.id)), 422)
    assert_problem(client.post("/api/households", json={"name": ""}, headers=h(customer.id)), 422)
    assert_problem(client.post("/api/households", json={}, headers=h(customer.id)), 422)
    # No financial field can be smuggled in: unknown fields are rejected.
    for field, value in (("income", 50000), ("expenses", 100), ("assets", 1), ("liabilities", 1), ("goals", []), ("risk", "Aggressive")):
        assert_problem(client.post("/api/households", json={"name": "X", field: value}, headers=h(customer.id)), 422)
    assert client.get(f"/api/profiles/{customer.id}/household", headers=h(customer.id)).json()["household"] is None


# ---------------------------------------------------------------------------
# Adding members and the membership rules
# ---------------------------------------------------------------------------


def test_the_primary_can_add_members_of_each_kind(client, make_customer):
    primary = make_customer(name="P")
    household = create_household(client, primary)
    for relationship, role in (("spouse", "member"), ("parent", "member"), ("child", "dependent"), ("sibling", "member"), ("other", "dependent")):
        other = make_customer(name=f"{relationship}-{role}")
        response = add_member(client, household["id"], primary, other, relationship, role)
        assert response.status_code == 201, response.text
        body = response.json()
        assert (body["relationship"], body["role"], body["is_dependent"], body["customer_name"]) == (relationship, role, role == "dependent", other.name)
    assert client.get(f"/api/households/{household['id']}", headers=h(primary.id)).json()["member_count"] == 6


def test_role_defaults_to_member(client, make_customer):
    primary, spouse = make_customer(), make_customer()
    household = create_household(client, primary)
    response = client.post(
        f"/api/households/{household['id']}/members", json={"customer_id": spouse.id, "relationship": "spouse"}, headers=h(primary.id)
    )
    assert response.status_code == 201 and response.json()["role"] == "member" and response.json()["is_dependent"] is False


def test_a_dependent_is_flagged_as_dependent_and_may_be_any_non_self_relationship(client, make_customer):
    primary, child = make_customer(), make_customer(name="Child")
    household = create_household(client, primary)
    body = add_member(client, household["id"], primary, child, "child", "dependent").json()
    assert body["role"] == "dependent" and body["is_dependent"] is True


def test_the_same_customer_cannot_be_added_twice_to_the_same_household(client, make_customer):
    primary, spouse = make_customer(), make_customer()
    household = create_household(client, primary)
    assert add_member(client, household["id"], primary, spouse).status_code == 201
    body = assert_problem(add_member(client, household["id"], primary, spouse, "sibling", "member"), 409)
    assert "already a member of this household" in body["detail"]


def test_a_customer_already_in_another_household_cannot_be_added(client, two_households):
    a, b, household_a, _household_b = two_households
    body = assert_problem(add_member(client, household_a["id"], a, b), 409)  # B already owns Household B
    assert "at most one" in body["detail"]
    assert "Household B" not in body["detail"]  # does not reveal which household


def test_a_second_primary_cannot_be_created(client, make_customer):
    primary, other = make_customer(), make_customer()
    household = create_household(client, primary)
    body = assert_problem(add_member(client, household["id"], primary, other, "self", "primary"), 409)
    assert "second primary" in body["detail"]
    assert client.get(f"/api/households/{household['id']}", headers=h(primary.id)).json()["member_count"] == 1


def test_unsupported_relationship_and_role_values_are_rejected(client, make_customer):
    primary, other = make_customer(), make_customer()
    household = create_household(client, primary)
    for relationship in ("cousin", "Spouse", "", "friend"):
        response = client.post(
            f"/api/households/{household['id']}/members", json={"customer_id": other.id, "relationship": relationship, "role": "member"}, headers=h(primary.id)
        )
        assert_problem(response, 422)
    for role in ("owner", "Member", "", "admin"):
        response = client.post(
            f"/api/households/{household['id']}/members", json={"customer_id": other.id, "relationship": "spouse", "role": role}, headers=h(primary.id)
        )
        assert_problem(response, 422)


@pytest.mark.parametrize(
    "relationship, role",
    [("spouse", "primary"), ("child", "primary"), ("other", "primary"), ("self", "member"), ("self", "dependent")],
)
def test_primary_and_self_combination_rules_are_validated(client, make_customer, relationship, role):
    """A primary is always `self`; `self` is reserved for the primary and is
    never a dependent."""
    primary, other = make_customer(), make_customer()
    household = create_household(client, primary)
    body = assert_problem(add_member(client, household["id"], primary, other, relationship, role), 422)
    assert "self" in body["detail"] or "primary" in body["detail"]
    assert client.get(f"/api/households/{household['id']}", headers=h(primary.id)).json()["member_count"] == 1


def test_member_creation_rejects_unknown_fields_and_bad_ids(client, make_customer):
    primary, other = make_customer(), make_customer()
    household = create_household(client, primary)
    url = f"/api/households/{household['id']}/members"
    assert_problem(client.post(url, json={"customer_id": other.id, "relationship": "spouse", "is_dependent": True}, headers=h(primary.id)), 422)
    assert_problem(client.post(url, json={"customer_id": other.id, "relationship": "spouse", "income": 1}, headers=h(primary.id)), 422)
    assert_problem(client.post(url, json={"customer_id": 0, "relationship": "spouse"}, headers=h(primary.id)), 422)
    assert_problem(client.post(url, json={"relationship": "spouse"}, headers=h(primary.id)), 422)


def test_adding_an_unknown_customer_is_a_404(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    body = assert_problem(
        client.post(f"/api/households/{household['id']}/members", json={"customer_id": 999_999_999, "relationship": "spouse"}, headers=h(primary.id)), 404
    )
    assert body["title"] == "Customer not found"


def test_a_database_integrity_race_is_reported_as_409_not_500(client, make_customer, monkeypatch, db_session):
    """The pre-checks cannot see a concurrent request, so the database's
    unique constraint is the backstop -- and it must surface as a 409, with
    the session still usable afterwards."""
    from wealthpilot.api.services import household_service

    a, b = make_customer(name="A"), make_customer(name="B")
    household = create_household(client, a, "Race")
    other_household = create_household(client, b, "Other")  # B already belongs to Other
    monkeypatch.setattr(household_service, "_membership_of", lambda session, customer_id: None)  # blind the pre-check

    body = assert_problem(add_member(client, household["id"], a, b), 409)
    assert "at most one" in body["detail"]
    monkeypatch.undo()
    assert client.get(f"/api/households/{household['id']}", headers=h(a.id)).json()["member_count"] == 1  # nothing was added
    assert client.get(f"/api/households/{other_household['id']}", headers=h(b.id)).status_code == 200  # session still healthy
    assert db_session.query(HouseholdMember).filter_by(customer_id=b.id).count() == 1


# ---------------------------------------------------------------------------
# Removing members
# ---------------------------------------------------------------------------


def test_the_primary_can_remove_a_member_who_is_then_free_to_join_elsewhere(client, two_households, make_customer):
    a, b, household_a, household_b = two_households
    spouse = make_customer(name="Spouse")
    member = add_member(client, household_a["id"], a, spouse).json()

    response = client.delete(f"/api/households/{household_a['id']}/members/{member['id']}", headers=h(a.id))
    assert response.status_code == 204 and response.content == b""
    assert client.get(f"/api/households/{household_a['id']}", headers=h(a.id)).json()["member_count"] == 1
    assert add_member(client, household_b["id"], b, spouse).status_code == 201  # free again


def test_the_primary_member_cannot_be_removed(client, make_customer):
    primary, spouse = make_customer(), make_customer()
    household = create_household(client, primary)
    add_member(client, household["id"], primary, spouse)
    members = client.get(f"/api/households/{household['id']}/members", headers=h(primary.id)).json()["members"]
    primary_row = next(m for m in members if m["role"] == "primary")

    body = assert_problem(client.delete(f"/api/households/{household['id']}/members/{primary_row['id']}", headers=h(primary.id)), 409)
    assert "primary member cannot be removed" in body["detail"]
    assert client.get(f"/api/households/{household['id']}", headers=h(primary.id)).json()["member_count"] == 2


def test_removing_the_only_member_is_also_refused(client, make_customer):
    primary = make_customer()
    household = create_household(client, primary)
    row = client.get(f"/api/households/{household['id']}/members", headers=h(primary.id)).json()["members"][0]
    assert_problem(client.delete(f"/api/households/{household['id']}/members/{row['id']}", headers=h(primary.id)), 409)


def test_removing_an_unknown_member_or_one_from_another_household_is_a_404(client, two_households):
    a, b, household_a, household_b = two_households
    b_row = client.get(f"/api/households/{household_b['id']}/members", headers=h(b.id)).json()["members"][0]
    assert_problem(client.delete(f"/api/households/{household_a['id']}/members/999999999", headers=h(a.id)), 404)
    # a real membership id, but it belongs to Household B, so it is "not in this household"
    assert_problem(client.delete(f"/api/households/{household_a['id']}/members/{b_row['id']}", headers=h(a.id)), 404)
    assert client.get(f"/api/households/{household_b['id']}", headers=h(b.id)).json()["member_count"] == 1


def test_there_is_no_household_deletion_endpoint(client, make_customer):
    customer = make_customer()
    household = create_household(client, customer)
    response = client.delete(f"/api/households/{household['id']}", headers=h(customer.id))
    assert response.status_code == 405
    assert not any(method.lower() == "delete" for method in app.openapi()["paths"]["/api/households/{household_id}"])


# ---------------------------------------------------------------------------
# Identity, authorization and isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("header_value", [None, "", "abc", "0", "-3", "1.5"])
def test_every_household_route_requires_a_valid_customer_identity(client, make_customer, header_value):
    customer = make_customer()
    household = create_household(client, customer)
    headers = {} if header_value is None else {"X-Customer-Id": header_value}
    member_id = client.get(f"/api/households/{household['id']}/members", headers=h(customer.id)).json()["members"][0]["id"]
    calls = [
        client.post("/api/households", json={"name": "X"}, headers=headers),
        client.get(f"/api/households/{household['id']}", headers=headers),
        client.get(f"/api/households/{household['id']}/members", headers=headers),
        client.post(f"/api/households/{household['id']}/members", json={"customer_id": customer.id, "relationship": "other"}, headers=headers),
        client.delete(f"/api/households/{household['id']}/members/{member_id}", headers=headers),
        client.get(f"/api/profiles/{customer.id}/household", headers=headers),
    ]
    for response in calls:
        assert_problem(response, 401)


def test_a_customer_can_access_their_own_household_and_not_another(client, two_households):
    a, b, household_a, household_b = two_households
    assert client.get(f"/api/households/{household_a['id']}", headers=h(a.id)).status_code == 200      # A -> Household A
    assert client.get(f"/api/households/{household_b['id']}", headers=h(b.id)).status_code == 200      # B -> Household B
    assert_problem(client.get(f"/api/households/{household_b['id']}", headers=h(a.id)), 403)            # A -> Household B
    assert_problem(client.get(f"/api/households/{household_b['id']}/members", headers=h(a.id)), 403)
    assert_problem(client.get(f"/api/households/{household_a['id']}", headers=h(b.id)), 403)            # B -> Household A


def test_another_households_data_is_never_in_a_denied_response(client, two_households):
    a, b, _household_a, household_b = two_households
    denied = client.get(f"/api/households/{household_b['id']}/members", headers=h(a.id))
    assert denied.status_code == 403
    assert "Customer B" not in denied.text and "Household B" not in denied.text


def test_a_customer_cannot_modify_or_delete_from_another_households(client, two_households, make_customer):
    a, b, household_a, household_b = two_households
    outsider = make_customer(name="Outsider")
    b_row = client.get(f"/api/households/{household_b['id']}/members", headers=h(b.id)).json()["members"][0]

    # A cannot add anyone to Household B, including themself or the outsider ...
    assert_problem(add_member(client, household_b["id"], a, outsider), 403)
    assert_problem(add_member(client, household_b["id"], a, a, "spouse", "member"), 403)
    # ... cannot delete from it ...
    assert_problem(client.delete(f"/api/households/{household_b['id']}/members/{b_row['id']}", headers=h(a.id)), 403)
    # ... and none of that changed Household B.
    assert client.get(f"/api/households/{household_b['id']}", headers=h(b.id)).json()["member_count"] == 1
    assert client.get(f"/api/profiles/{a.id}/household", headers=h(a.id)).json()["household"]["id"] == household_a["id"]


def test_a_customer_cannot_join_a_household_without_the_primary_adding_them(client, two_households, make_customer):
    a, _b, household_a, _household_b = two_households
    outsider = make_customer(name="Outsider")
    assert_problem(add_member(client, household_a["id"], outsider, outsider, "spouse", "member"), 403)
    assert client.get(f"/api/profiles/{outsider.id}/household", headers=h(outsider.id)).json()["household"] is None


def test_the_primary_can_add_another_customer_to_their_own_household_only_by_the_membership_rules(client, make_customer):
    a, b = make_customer(name="A"), make_customer(name="B")
    household_a = create_household(client, a)
    assert add_member(client, household_a["id"], a, b).status_code == 201  # allowed: A is primary, B has no household
    assert client.get(f"/api/profiles/{b.id}/household", headers=h(b.id)).json()["household"]["id"] == household_a["id"]


def test_only_the_primary_can_add_or_remove_members(client, make_customer):
    primary, spouse, child, newcomer = make_customer(), make_customer(name="S"), make_customer(name="C"), make_customer(name="N")
    household = create_household(client, primary)
    add_member(client, household["id"], primary, spouse)
    child_row = add_member(client, household["id"], primary, child, "child", "dependent").json()

    assert_problem(add_member(client, household["id"], spouse, newcomer), 403)      # a member cannot add
    assert_problem(add_member(client, household["id"], child, newcomer), 403)       # a dependent cannot add
    assert_problem(client.delete(f"/api/households/{household['id']}/members/{child_row['id']}", headers=h(spouse.id)), 403)
    assert client.get(f"/api/households/{household['id']}", headers=h(primary.id)).json()["member_count"] == 3


def test_membership_does_not_grant_access_to_another_members_profile_household_or_account(client, make_customer):
    a, b = make_customer(name="A"), make_customer(name="B")
    household = create_household(client, a)
    add_member(client, household["id"], a, b)
    # Household membership is not account access: A still cannot ask about B's own household record
    assert_problem(client.get(f"/api/profiles/{b.id}/household", headers=h(a.id)), 403)
    assert_problem(client.get(f"/api/profiles/{a.id}/household", headers=h(b.id)), 403)


def test_unknown_household_is_a_404_and_a_non_member_gets_a_403(client, make_customer):
    customer = make_customer()
    assert_problem(client.get("/api/households/999999999", headers=h(customer.id)), 404)
    assert_problem(client.get("/api/households/999999999/members", headers=h(customer.id)), 404)
    assert_problem(add_member(client, 999_999_999, customer, customer, "spouse"), 404)
    assert_problem(client.delete("/api/households/999999999/members/1", headers=h(customer.id)), 404)


# ---------------------------------------------------------------------------
# Profile household
# ---------------------------------------------------------------------------


def test_profile_household_is_empty_until_one_is_created_and_never_created_implicitly(client, make_customer, db_session):
    customer = make_customer()
    before = db_session.query(Household).count()

    for _ in range(2):
        response = client.get(f"/api/profiles/{customer.id}/household", headers=h(customer.id))
        assert response.status_code == 200
        assert response.json() == {"customer_id": customer.id, "household": None, "membership": None}
    assert db_session.query(Household).count() == before  # a read never creates one

    household = create_household(client, customer, "Now It Exists")
    body = client.get(f"/api/profiles/{customer.id}/household", headers=h(customer.id)).json()
    assert body["household"]["id"] == household["id"] and body["household"]["member_count"] == 1
    assert (body["membership"]["relationship"], body["membership"]["role"]) == ("self", "primary")


def test_profile_household_shows_a_non_primary_members_own_role(client, make_customer):
    primary, spouse = make_customer(), make_customer(name="Spouse")
    household = create_household(client, primary)
    add_member(client, household["id"], primary, spouse)
    body = client.get(f"/api/profiles/{spouse.id}/household", headers=h(spouse.id)).json()
    assert body["household"]["id"] == household["id"] and body["household"]["member_count"] == 2
    assert (body["membership"]["relationship"], body["membership"]["role"]) == ("spouse", "member")


def test_profile_household_is_only_for_the_calling_customer(client, two_households):
    a, b, _ha, _hb = two_households
    assert_problem(client.get(f"/api/profiles/{b.id}/household", headers=h(a.id)), 403)


def test_profile_household_for_an_unknown_customer_is_a_404(client):
    assert_problem(client.get("/api/profiles/999999999/household", headers=h(999_999_999)), 404)


# ---------------------------------------------------------------------------
# API contract and "identity only" guarantees
# ---------------------------------------------------------------------------


def test_openapi_lists_exactly_the_household_routes():
    paths = app.openapi()["paths"]
    household_routes = {(method.upper(), path) for path, ops in paths.items() if "household" in path for method in ops}

    phase_32 = {
        ("POST", "/api/households"),
        ("GET", "/api/households/{household_id}"),
        ("GET", "/api/households/{household_id}/members"),
        ("POST", "/api/households/{household_id}/members"),
        ("DELETE", "/api/households/{household_id}/members/{member_id}"),
        ("GET", "/api/profiles/{profile_id}/household"),
    }
    # Phase 33 -- source-record CRUD for the four financial resources.
    phase_33 = {
        (method, f"/api/households/{{household_id}}/{collection}{suffix}")
        for collection, item in (("income", "income_id"), ("expenses", "expense_id"), ("assets", "asset_id"), ("liabilities", "liability_id"))
        for method, suffix in (("GET", ""), ("POST", ""), ("PUT", f"/{{{item}}}"), ("DELETE", f"/{{{item}}}"))
    }
    # Phase 34 -- the one read-only aggregation route. There is deliberately
    # still no household deletion route and no mutation route for calculations.
    phase_34 = {("GET", "/api/households/{household_id}/financial-summary")}
    # Phase 36 -- household goals (stored facts only). Phase 35 added no route.
    phase_36 = {
        ("GET", "/api/households/{household_id}/goals"),
        ("POST", "/api/households/{household_id}/goals"),
        ("GET", "/api/households/{household_id}/goals/{goal_id}"),
        ("PUT", "/api/households/{household_id}/goals/{goal_id}"),
        ("DELETE", "/api/households/{household_id}/goals/{goal_id}"),
    }

    assert household_routes == phase_32 | phase_33 | phase_34 | phase_36


def test_household_schemas_contain_no_financial_field():
    """Identity and membership only: nothing financial may appear in any
    household request or response schema."""
    schemas = app.openapi()["components"]["schemas"]
    names = ["HouseholdCreateRequest", "HouseholdMemberCreateRequest", "HouseholdOut", "HouseholdMemberOut", "HouseholdMembersResponse", "ProfileHouseholdResponse"]
    forbidden = ("income", "expense", "asset", "liabilit", "saving", "debt", "goal", "risk", "portfolio", "recommend", "cash", "net_worth", "contribution", "emergency")
    for name in names:
        for field in schemas[name]["properties"]:
            assert not any(word in field.lower() for word in forbidden), f"{name}.{field}"


# ---------------------------------------------------------------------------
# Existing behaviour must not change
# ---------------------------------------------------------------------------


def test_household_membership_does_not_change_the_analysis_result(client, make_customer, monkeypatch, db_session):
    customer, spouse = make_customer(name="Analysed"), make_customer(name="Spouse")
    patch_graph(monkeypatch, approved_steps(customer.id))

    goals = list(customer.financial_goals)
    hash_before = compute_profile_hash(customer, goals, None, None)
    before = client.post("/api/analysis", json={"profile_id": customer.id})
    assert before.status_code == 200 and before.json()["status"] == "approved"

    household = create_household(client, customer)
    assert add_member(client, household["id"], customer, spouse, "spouse", "member").status_code == 201
    db_session.refresh(customer)

    after = client.post("/api/analysis", json={"profile_id": customer.id})
    assert after.status_code == 200
    assert after.json() == before.json()  # identical body, same analysis_id: a cache hit on an unchanged profile
    assert compute_profile_hash(customer, list(customer.financial_goals), None, None) == hash_before


def test_household_membership_does_not_change_a_members_own_analysis(client, make_customer, monkeypatch):
    primary, spouse = make_customer(name="P"), make_customer(name="S")
    patch_graph(monkeypatch, approved_steps(spouse.id))
    before = client.post("/api/analysis", json={"profile_id": spouse.id}).json()

    household = create_household(client, primary)
    add_member(client, household["id"], primary, spouse)

    assert client.post("/api/analysis", json={"profile_id": spouse.id}).json() == before


def test_financial_inputs_are_unaffected_by_household_membership(client, make_customer, monkeypatch):
    customer, spouse = make_customer(), make_customer()
    put = client.put(f"/api/profiles/{customer.id}/financial-inputs", json={"monthly_essential_expenses": 2000, "current_liquid_assets": 9000})
    assert put.status_code == 200
    before = client.get(f"/api/profiles/{customer.id}/financial-inputs").json()

    household = create_household(client, customer)
    add_member(client, household["id"], customer, spouse)

    assert client.get(f"/api/profiles/{customer.id}/financial-inputs").json() == before
    assert client.get(f"/api/profiles/{spouse.id}/financial-inputs").json()["monthly_essential_expenses"] is None  # nothing was shared or aggregated
    later = client.put(f"/api/profiles/{customer.id}/financial-inputs", json={"contribution_amount": 300}).json()
    assert later["monthly_essential_expenses"] == 2000 and later["contribution_amount"] == 300


def test_existing_profile_and_goal_endpoints_are_unaffected(client, make_customer):
    customer = make_customer(name="Plain")
    household = create_household(client, customer)
    profile = client.get(f"/api/profiles/{customer.id}").json()
    assert profile["name"] == "Plain" and "household" not in profile
    goal = client.post(f"/api/profiles/{customer.id}/goals", json={"goal_type": "Retirement", "target_amount": 1000, "target_date": "2045-01-01"})
    assert goal.status_code == 201
    assert client.get(f"/api/households/{household['id']}", headers=h(customer.id)).json()["member_count"] == 1
