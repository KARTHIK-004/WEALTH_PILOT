"""Phase 34 — the household financial summary API
(`GET /api/households/{id}/financial-summary`).

Uses `client` (synthetic customers on TEST_DATABASE_URL, rolled back after each
test). The arithmetic itself is proved exhaustively and without a database in
`tests/backend/core/test_household_finance.py`; this file proves the endpoint
around it — that the numbers reaching the API really are the ones the stored
records imply, that authorization and cross-household isolation hold, that the
response shape is the documented one, and that Phase 34 changed nothing about
the individual analysis pipeline.
"""

from __future__ import annotations

import pytest

from tests.backend.api.conftest import approved_steps, patch_graph
from wealthpilot.api.main import app

SUMMARY = "/api/households/{}/financial-summary"


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


def create_household(client, customer, name="Summary Family"):
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


def add(client, household_id, primary, resource, **payload):
    response = client.post(f"/api/households/{household_id}/{resource}", json=payload, headers=h(primary.id))
    assert response.status_code == 201, response.text
    return response.json()


def summary_of(client, household_id, actor):
    response = client.get(SUMMARY.format(household_id), headers=h(actor.id))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def household(client, make_customer):
    """A primary, a non-primary member, and an empty household."""
    primary = make_customer(name="Summary Primary")
    member = make_customer(name="Summary Member")
    created = create_household(client, primary)
    add_member(client, created["id"], primary, member)
    return {"id": created["id"], "primary": primary, "member": member}


@pytest.fixture()
def funded(client, household):
    """A household with one record of every kind, of every frequency."""
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "income", source="Salary", amount=5200, frequency="monthly")
    add(client, hid, primary, "income", source="Bonus", amount=12000, frequency="yearly")
    add(client, hid, primary, "income", source="Gift", amount=900, frequency="one_time")
    add(client, hid, primary, "income", source="Old job", amount=400, frequency="monthly", is_active=False)
    add(client, hid, primary, "expenses", category="housing", amount=1400, frequency="monthly", is_essential=True)
    add(client, hid, primary, "expenses", category="entertainment", amount=600, frequency="monthly", is_essential=False)
    add(client, hid, primary, "expenses", category="other", amount=300, frequency="one_time", is_essential=False)
    add(client, hid, primary, "assets", name="Joint savings", asset_type="bank_account", current_value=21000, is_liquid=True)
    add(client, hid, primary, "assets", name="Flat", asset_type="real_estate", current_value=150000, is_liquid=False)
    add(client, hid, primary, "liabilities", name="Home loan", liability_type="mortgage", outstanding_amount=118000, monthly_payment=850)
    return household


# ------------------------------------------------------------------- shape


def test_summary_has_exactly_the_documented_sections(client, household):
    body = summary_of(client, household["id"], household["primary"])
    assert set(body) == {
        "household_id", "income", "expenses", "assets", "liabilities",
        "cash_flow", "net_position", "emergency_fund", "data_completeness",
    }
    assert body["household_id"] == household["id"]


def test_summary_section_fields_are_the_documented_ones(client, funded):
    body = summary_of(client, funded["id"], funded["primary"])
    assert set(body["income"]) == {"recurring_monthly", "one_time", "record_count", "active_record_count", "available", "unavailable_reason"}
    assert set(body["expenses"]) == {"recurring_monthly", "recurring_essential_monthly", "recurring_nonessential_monthly", "one_time", "record_count", "active_record_count", "available", "unavailable_reason"}
    assert set(body["assets"]) == {"total", "liquid", "record_count", "liquid_record_count", "available", "unavailable_reason"}
    assert set(body["liabilities"]) == {"outstanding", "monthly_payment", "record_count", "available", "unavailable_reason"}
    assert set(body["cash_flow"]) == {"recurring_monthly_income", "recurring_monthly_expenses", "monthly", "available", "unavailable_reason"}
    assert set(body["net_position"]) == {"total_assets", "total_outstanding_liabilities", "value", "available", "unavailable_reason"}
    assert set(body["emergency_fund"]) == {"required", "current_liquid_assets", "shortfall", "status", "target_months", "available", "unavailable_reason"}
    assert set(body["data_completeness"]) == {"income", "expenses", "assets", "liabilities", "emergency_fund"}


def test_summary_never_exposes_a_customer_id_or_member_detail(client, funded):
    """Phase 34 section 38: the summary is financial, not identity."""
    raw = client.get(SUMMARY.format(funded["id"]), headers=h(funded["primary"].id)).text
    assert "customer_id" not in raw
    assert str(funded["member"].id) not in raw or str(funded["member"].id) == str(funded["id"])


def test_summary_carries_no_score_ranking_or_recommendation_field(client, funded):
    body = summary_of(client, funded["id"], funded["primary"])
    forbidden = ("score", "rank", "rating", "recommend", "strategy", "risk", "savings_rate", "debt_ratio", "probability")
    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                assert not any(word in key.lower() for word in forbidden), f"{path}{key}"
                walk(value, f"{path}{key}.")
    walk(body)


# ------------------------------------------------------- values from source


def test_values_match_the_stored_source_records(client, funded):
    body = summary_of(client, funded["id"], funded["primary"])
    # 5200 monthly + 12000 yearly / 12 = 6200; the inactive 400 is excluded
    assert body["income"]["recurring_monthly"] == 6200
    assert body["income"]["one_time"] == 900
    assert body["income"]["record_count"] == 4
    assert body["income"]["active_record_count"] == 3
    assert body["expenses"]["recurring_monthly"] == 2000
    assert body["expenses"]["recurring_essential_monthly"] == 1400
    assert body["expenses"]["recurring_nonessential_monthly"] == 600
    assert body["expenses"]["one_time"] == 300
    assert body["assets"]["total"] == 171000
    assert body["assets"]["liquid"] == 21000
    assert body["assets"]["liquid_record_count"] == 1
    assert body["liabilities"]["outstanding"] == 118000
    assert body["liabilities"]["monthly_payment"] == 850
    assert body["cash_flow"]["monthly"] == 4200
    assert body["net_position"]["value"] == 53000
    assert body["emergency_fund"]["required"] == 8400
    assert body["emergency_fund"]["current_liquid_assets"] == 21000
    assert body["emergency_fund"]["shortfall"] == 0
    assert body["emergency_fund"]["status"] == "sufficient"
    assert body["emergency_fund"]["target_months"] == 6


def test_one_time_records_never_enter_the_recurring_cash_flow(client, household):
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "income", source="Salary", amount=5000, frequency="monthly")
    add(client, hid, primary, "expenses", category="housing", amount=2000, frequency="monthly", is_essential=True)
    before = summary_of(client, hid, primary)["cash_flow"]["monthly"]
    add(client, hid, primary, "income", source="Inheritance", amount=100000, frequency="one_time")
    add(client, hid, primary, "expenses", category="other", amount=50000, frequency="one_time", is_essential=False)
    after = summary_of(client, hid, primary)
    assert after["cash_flow"]["monthly"] == before == 3000
    assert after["income"]["one_time"] == 100000
    assert after["expenses"]["one_time"] == 50000


def test_deactivating_a_record_removes_it_from_the_aggregate_but_not_the_count(client, household):
    hid, primary = household["id"], household["primary"]
    record = add(client, hid, primary, "income", source="Salary", amount=5000, frequency="monthly")
    assert summary_of(client, hid, primary)["income"]["recurring_monthly"] == 5000
    client.put(f"/api/households/{hid}/income/{record['id']}", json={"is_active": False}, headers=h(primary.id))
    body = summary_of(client, hid, primary)
    assert body["income"]["recurring_monthly"] is None
    assert body["income"]["record_count"] == 1 and body["income"]["active_record_count"] == 0
    assert body["income"]["available"] is True


def test_the_summary_follows_the_records_through_create_update_and_delete(client, household):
    hid, primary = household["id"], household["primary"]
    record = add(client, hid, primary, "assets", name="Savings", asset_type="bank_account", current_value=1000, is_liquid=True)
    assert summary_of(client, hid, primary)["assets"]["liquid"] == 1000
    client.put(f"/api/households/{hid}/assets/{record['id']}", json={"current_value": 2500}, headers=h(primary.id))
    assert summary_of(client, hid, primary)["assets"]["liquid"] == 2500
    client.delete(f"/api/households/{hid}/assets/{record['id']}", headers=h(primary.id))
    body = summary_of(client, hid, primary)
    assert body["assets"]["liquid"] is None and body["assets"]["available"] is False


def test_the_summary_is_deterministic_across_repeated_calls(client, funded):
    first = summary_of(client, funded["id"], funded["primary"])
    second = summary_of(client, funded["id"], funded["primary"])
    third = summary_of(client, funded["id"], funded["member"])
    assert first == second == third


# --------------------------------------------------------- null versus zero


def test_an_empty_household_reports_unknown_everywhere_never_zero(client, household):
    body = summary_of(client, household["id"], household["primary"])
    for section in ("income", "expenses", "assets", "liabilities"):
        assert body[section]["available"] is False
        assert body[section]["unavailable_reason"]
    assert body["income"]["recurring_monthly"] is None
    assert body["expenses"]["recurring_monthly"] is None
    assert body["assets"]["total"] is None and body["assets"]["liquid"] is None
    assert body["liabilities"]["outstanding"] is None
    assert body["cash_flow"]["monthly"] is None and body["cash_flow"]["available"] is False
    assert body["net_position"]["value"] is None and body["net_position"]["available"] is False
    assert body["emergency_fund"]["status"] == "unknown" and body["emergency_fund"]["available"] is False
    assert body["data_completeness"] == {
        "income": "unavailable", "expenses": "unavailable", "assets": "unavailable",
        "liabilities": "unavailable", "emergency_fund": "unavailable",
    }


def test_a_zero_value_asset_is_a_known_zero(client, household):
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "assets", name="Emptied account", asset_type="bank_account", current_value=0, is_liquid=True)
    body = summary_of(client, hid, primary)
    assert body["assets"]["total"] == 0 and body["assets"]["liquid"] == 0
    assert body["assets"]["available"] is True
    assert body["data_completeness"]["assets"] == "available"


def test_a_zero_outstanding_liability_is_a_known_zero(client, household):
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "liabilities", name="Repaid loan", liability_type="personal_loan", outstanding_amount=0)
    body = summary_of(client, hid, primary)
    assert body["liabilities"]["outstanding"] == 0
    assert body["liabilities"]["available"] is True
    # `monthly_payment` was not provided -- that stays unknown, not 0
    assert body["liabilities"]["monthly_payment"] is None


def test_zero_liquid_assets_gives_a_known_insufficient_emergency_fund(client, household):
    """Phase 34 section 35: a recorded zero is a fact, so the position IS known."""
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "expenses", category="food", amount=1000, frequency="monthly", is_essential=True)
    add(client, hid, primary, "assets", name="Emptied account", asset_type="cash", current_value=0, is_liquid=True)
    fund = summary_of(client, hid, primary)["emergency_fund"]
    assert fund["required"] == 6000 and fund["current_liquid_assets"] == 0
    assert fund["shortfall"] == 6000 and fund["status"] == "insufficient"
    assert fund["available"] is True


def test_missing_liquid_assets_leaves_the_emergency_fund_unknown(client, household):
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "expenses", category="food", amount=1000, frequency="monthly", is_essential=True)
    add(client, hid, primary, "assets", name="Flat", asset_type="real_estate", current_value=150000, is_liquid=False)
    fund = summary_of(client, hid, primary)["emergency_fund"]
    assert fund["status"] == "unknown" and fund["available"] is False
    assert fund["current_liquid_assets"] is None and fund["shortfall"] is None
    assert "liquid assets" in fund["unavailable_reason"]


def test_missing_essential_expenses_leaves_the_emergency_fund_unknown(client, household):
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "expenses", category="entertainment", amount=600, frequency="monthly", is_essential=False)
    add(client, hid, primary, "assets", name="Savings", asset_type="cash", current_value=50000, is_liquid=True)
    fund = summary_of(client, hid, primary)["emergency_fund"]
    assert fund["status"] == "unknown" and fund["required"] is None
    assert "essential" in fund["unavailable_reason"]


def test_cash_flow_unavailable_reason_names_the_missing_side(client, household):
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "expenses", category="housing", amount=1200, frequency="monthly", is_essential=True)
    flow = summary_of(client, hid, primary)["cash_flow"]
    assert flow["monthly"] is None and flow["available"] is False
    assert "recurring monthly income" in flow["unavailable_reason"]
    assert flow["recurring_monthly_expenses"] == 1200


def test_net_position_unavailable_reason_names_the_missing_side(client, household):
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "assets", name="Savings", asset_type="cash", current_value=1000, is_liquid=True)
    net = summary_of(client, hid, primary)["net_position"]
    assert net["value"] is None and net["available"] is False
    assert "outstanding liabilities" in net["unavailable_reason"]
    assert net["total_assets"] == 1000


def test_an_available_section_has_no_unavailable_reason(client, funded):
    body = summary_of(client, funded["id"], funded["primary"])
    for section in ("income", "expenses", "assets", "liabilities", "cash_flow", "net_position", "emergency_fund"):
        assert body[section]["unavailable_reason"] is None


# ----------------------------------------------------- emergency-fund boundary


@pytest.mark.parametrize(
    "liquid, expected, shortfall",
    [(6000, "sufficient", 0), (5999, "insufficient", 1), (6001, "sufficient", 0)],
)
def test_emergency_fund_boundary_through_the_api(client, household, liquid, expected, shortfall):
    """Phase 34 section 33, end to end: required = 6 x 1000 = 6000."""
    hid, primary = household["id"], household["primary"]
    add(client, hid, primary, "expenses", category="food", amount=1000, frequency="monthly", is_essential=True)
    add(client, hid, primary, "assets", name="Savings", asset_type="cash", current_value=liquid, is_liquid=True)
    fund = summary_of(client, hid, primary)["emergency_fund"]
    assert fund["required"] == 6000
    assert fund["status"] == expected
    assert fund["shortfall"] == shortfall


# ------------------------------------------------------------ authorization


def test_the_primary_member_can_read_the_summary(client, funded):
    assert client.get(SUMMARY.format(funded["id"]), headers=h(funded["primary"].id)).status_code == 200


def test_a_non_primary_member_can_read_the_summary(client, funded):
    """Read-only: no primary-only restriction applies."""
    assert client.get(SUMMARY.format(funded["id"]), headers=h(funded["member"].id)).status_code == 200


def test_a_dependent_member_can_read_the_summary(client, household, make_customer):
    child = make_customer(name="Summary Dependent")
    add_member(client, household["id"], household["primary"], child, relationship="child", role="dependent")
    assert client.get(SUMMARY.format(household["id"]), headers=h(child.id)).status_code == 200


def test_a_non_member_is_denied(client, funded, make_customer):
    outsider = make_customer(name="Summary Outsider")
    assert_problem(client.get(SUMMARY.format(funded["id"]), headers=h(outsider.id)), 403)


def test_an_unknown_household_is_404(client, household):
    assert_problem(client.get(SUMMARY.format(9_999_999), headers=h(household["primary"].id)), 404)


def test_a_missing_identity_is_401(client, funded):
    assert_problem(client.get(SUMMARY.format(funded["id"])), 401)


def test_a_malformed_identity_is_401(client, funded):
    assert_problem(client.get(SUMMARY.format(funded["id"]), headers={"X-Customer-Id": "not-a-number"}), 401)


def test_the_summary_endpoint_is_read_only(client, funded):
    """No mutation endpoint exists for calculations (Phase 34 section 18)."""
    hid = funded["id"]
    for method in (client.post, client.put, client.patch):
        assert method(SUMMARY.format(hid), json={}, headers=h(funded["primary"].id)).status_code == 405
    assert client.delete(SUMMARY.format(hid), headers=h(funded["primary"].id)).status_code == 405


# --------------------------------------------------------------- isolation


@pytest.fixture()
def two_households(client, make_customer):
    a_primary, b_primary = make_customer(name="Isolation A"), make_customer(name="Isolation B")
    a, b = create_household(client, a_primary, "House A"), create_household(client, b_primary, "House B")
    add(client, a["id"], a_primary, "income", source="A salary", amount=1111, frequency="monthly")
    add(client, a["id"], a_primary, "expenses", category="housing", amount=111, frequency="monthly", is_essential=True)
    add(client, a["id"], a_primary, "assets", name="A savings", asset_type="cash", current_value=11111, is_liquid=True)
    add(client, a["id"], a_primary, "liabilities", name="A loan", liability_type="mortgage", outstanding_amount=1111111, monthly_payment=11)
    add(client, b["id"], b_primary, "income", source="B salary", amount=2222, frequency="monthly")
    add(client, b["id"], b_primary, "expenses", category="housing", amount=222, frequency="monthly", is_essential=True)
    add(client, b["id"], b_primary, "assets", name="B savings", asset_type="cash", current_value=22222, is_liquid=True)
    add(client, b["id"], b_primary, "liabilities", name="B loan", liability_type="mortgage", outstanding_amount=2222222, monthly_payment=22)
    return {"a": a, "a_primary": a_primary, "b": b, "b_primary": b_primary}


def test_each_household_summary_contains_only_its_own_records(client, two_households):
    a = summary_of(client, two_households["a"]["id"], two_households["a_primary"])
    b = summary_of(client, two_households["b"]["id"], two_households["b_primary"])
    assert a["income"]["recurring_monthly"] == 1111 and b["income"]["recurring_monthly"] == 2222
    assert a["expenses"]["recurring_essential_monthly"] == 111 and b["expenses"]["recurring_essential_monthly"] == 222
    assert a["assets"]["total"] == 11111 and b["assets"]["total"] == 22222
    assert a["liabilities"]["outstanding"] == 1111111 and b["liabilities"]["outstanding"] == 2222222
    assert a["net_position"]["value"] == 11111 - 1111111
    assert b["net_position"]["value"] == 22222 - 2222222


def test_a_member_of_one_household_cannot_read_the_other_summary(client, two_households):
    body = assert_problem(
        client.get(SUMMARY.format(two_households["b"]["id"]), headers=h(two_households["a_primary"].id)), 403
    )
    for leaked in ("2222", "22222", "2222222", "B salary", "B loan"):
        assert leaked not in str(body)


def test_records_of_another_household_never_reach_a_summary(client, two_households):
    """The aggregation queries are scoped by the path's household_id, so B's
    rows cannot join into A's totals no matter how many records exist."""
    a = summary_of(client, two_households["a"]["id"], two_households["a_primary"])
    assert a["income"]["record_count"] == 1
    assert a["assets"]["record_count"] == 1
    assert a["liabilities"]["record_count"] == 1
    assert a["income"]["recurring_monthly"] == 1111  # not 1111 + 2222


def test_adding_records_to_one_household_never_changes_the_other_summary(client, two_households):
    before = summary_of(client, two_households["a"]["id"], two_households["a_primary"])
    add(client, two_households["b"]["id"], two_households["b_primary"], "income", source="B extra", amount=9999, frequency="monthly")
    add(client, two_households["b"]["id"], two_households["b_primary"], "assets", name="B extra", asset_type="cash", current_value=9999, is_liquid=True)
    assert summary_of(client, two_households["a"]["id"], two_households["a_primary"]) == before


def test_the_summary_household_id_is_always_the_path_household(client, two_households):
    for key, actor in (("a", "a_primary"), ("b", "b_primary")):
        body = summary_of(client, two_households[key]["id"], two_households[actor])
        assert body["household_id"] == two_households[key]["id"]


# --------------------------------------------------------------- OpenAPI


def test_exactly_one_household_calculation_route_exists():
    paths = app.openapi()["paths"]
    summary_paths = {p: sorted(ops) for p, ops in paths.items() if "financial-summary" in p}
    assert summary_paths == {"/api/households/{household_id}/financial-summary": ["get"]}

    aggregate_words = ("totals", "net-worth", "networth", "savings", "debt-ratio", "cash-flow", "aggregate")
    assert not [p for p in paths if any(word in p.lower() for word in aggregate_words)]


def test_no_goal_feasibility_or_recommendation_field_exists_on_the_summary_schema():
    """Phase 34 section 42: none of the later-phase concepts leaked in."""
    schema = app.openapi()["components"]["schemas"]["HouseholdFinancialSummaryResponse"]
    assert set(schema["properties"]) == {
        "household_id", "income", "expenses", "assets", "liabilities",
        "cash_flow", "net_position", "emergency_fund", "data_completeness",
    }
    rendered = str(app.openapi()["components"]["schemas"])
    for word in ("monte_carlo", "feasibility", "savings_first", "portfolio_weight", "compliance"):
        assert word not in rendered.lower() or "Household" not in word


# ------------------------------------------------------------- regression


def test_the_summary_endpoint_does_not_change_the_individual_analysis(client, make_customer, monkeypatch):
    """Phase 34 section 28: reading a household summary must not touch, or be
    touched by, the individual pipeline."""
    customer = make_customer(name="Summary Analysed")
    patch_graph(monkeypatch, approved_steps(customer.id))
    before = client.post("/api/analysis", json={"profile_id": customer.id})
    assert before.status_code == 200 and before.json()["status"] == "approved"

    created = create_household(client, customer)
    add(client, created["id"], customer, "income", source="Salary", amount=5000, frequency="monthly")
    add(client, created["id"], customer, "expenses", category="housing", amount=9000, frequency="monthly", is_essential=True)
    fund = summary_of(client, created["id"], customer)["emergency_fund"]
    assert fund["status"] == "unknown"  # no liquid assets recorded

    after = client.post("/api/analysis", json={"profile_id": customer.id})
    assert after.status_code == 200
    assert after.json() == before.json()


def test_household_finances_do_not_reach_the_individual_financial_inputs(client, make_customer):
    customer = make_customer(name="Summary Inputs")
    created = create_household(client, customer)
    before = client.get(f"/api/profiles/{customer.id}/financial-inputs").json()
    add(client, created["id"], customer, "expenses", category="housing", amount=1234, frequency="monthly", is_essential=True)
    add(client, created["id"], customer, "assets", name="Savings", asset_type="cash", current_value=99999, is_liquid=True)
    summary_of(client, created["id"], customer)
    assert client.get(f"/api/profiles/{customer.id}/financial-inputs").json() == before
