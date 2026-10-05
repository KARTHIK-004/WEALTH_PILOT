"""Phase 35 — household financial facts through the API, with the optional
metadata Phase 35 added, and their integration with the Phase 34 summary.

Uses `client` (synthetic customers on TEST_DATABASE_URL, rolled back after each
test). The Phase 33 CRUD/authorization matrix lives in
`test_household_finances.py` and the Phase 34 summary in
`test_household_summary.py`; this file covers what Phase 35 changed:

- the new optional fields (`notes`, asset/liability `description`, liability
  `interest_rate`) round-trip, validate, and stay `null` when absent;
- the Phase 34 summary reads these persisted records with its semantics
  intact, using the reference dataset from the Phase 35 specification;
- none of the new metadata can move a summary figure;
- cross-household isolation still holds with the new fields, and hostile
  strings are stored and returned verbatim as data.
"""

from __future__ import annotations

import pytest

from tests.backend.api.conftest import approved_steps, patch_graph
from wealthpilot.core.goals import assess_emergency_fund


def h(customer_id) -> dict[str, str]:
    return {"X-Customer-Id": str(customer_id)}


def assert_problem(response, status: int) -> dict:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert "Traceback" not in body["detail"] and "sqlalchemy" not in body["detail"].lower()
    return body


def create_household(client, customer, name="Metadata Family"):
    response = client.post("/api/households", json={"name": name}, headers=h(customer.id))
    assert response.status_code == 201, response.text
    return response.json()


def add_member(client, household_id, primary, customer, relationship="spouse", role="member"):
    response = client.post(f"/api/households/{household_id}/members",
                           json={"customer_id": customer.id, "relationship": relationship, "role": role},
                           headers=h(primary.id))
    assert response.status_code == 201, response.text


def add(client, household_id, actor, resource, **payload):
    response = client.post(f"/api/households/{household_id}/{resource}", json=payload, headers=h(actor.id))
    assert response.status_code == 201, response.text
    return response.json()


def summary_of(client, household_id, actor):
    response = client.get(f"/api/households/{household_id}/financial-summary", headers=h(actor.id))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def family(client, make_customer):
    primary = make_customer(name="Meta Primary")
    member = make_customer(name="Meta Member")
    dependent = make_customer(name="Meta Dependent")
    created = create_household(client, primary)
    add_member(client, created["id"], primary, member)
    add_member(client, created["id"], primary, dependent, relationship="child", role="dependent")
    return {"id": created["id"], "primary": primary, "member": member, "dependent": dependent}


# ------------------------------------------------------------ round-trip


def test_income_notes_round_trip(client, family):
    created = add(client, family["id"], family["primary"], "income",
                  source="Salary", amount=5000, frequency="monthly", notes="Paid on the 25th")
    assert created["notes"] == "Paid on the 25th"
    listed = client.get(f"/api/households/{family['id']}/income", headers=h(family["primary"].id)).json()
    assert listed[0]["notes"] == "Paid on the 25th"


def test_expense_notes_round_trip(client, family):
    created = add(client, family["id"], family["primary"], "expenses", category="housing", amount=1200,
                  frequency="monthly", is_essential=True, notes="Includes service charge")
    assert created["notes"] == "Includes service charge"


def test_asset_description_and_notes_round_trip(client, family):
    created = add(client, family["id"], family["primary"], "assets", name="Savings", asset_type="bank_account",
                  current_value=15000, is_liquid=True, description="Joint instant-access", notes="Opened 2019")
    assert (created["description"], created["notes"]) == ("Joint instant-access", "Opened 2019")


def test_liability_interest_rate_description_and_notes_round_trip(client, family):
    created = add(client, family["id"], family["primary"], "liabilities", name="Home loan",
                  liability_type="mortgage", outstanding_amount=150000, monthly_payment=900,
                  interest_rate=0.0425, description="Fixed until 2028", notes="Remortgage due")
    assert created["interest_rate"] == 0.0425
    assert (created["description"], created["notes"]) == ("Fixed until 2028", "Remortgage due")


def test_absent_metadata_is_returned_as_null(client, family):
    created = add(client, family["id"], family["primary"], "liabilities", name="Car loan",
                  liability_type="vehicle_loan", outstanding_amount=8000)
    assert created["interest_rate"] is None
    assert created["description"] is None and created["notes"] is None
    assert created["monthly_payment"] is None  # ADR-032: still optional


def test_a_zero_interest_rate_is_returned_as_zero_not_null(client, family):
    created = add(client, family["id"], family["primary"], "liabilities", name="Family loan",
                  liability_type="personal_loan", outstanding_amount=2000, interest_rate=0)
    assert created["interest_rate"] == 0


def test_metadata_can_be_updated_and_cleared(client, family):
    hid, primary = family["id"], family["primary"]
    record = add(client, hid, primary, "income", source="Salary", amount=5000, frequency="monthly", notes="old")
    updated = client.put(f"/api/households/{hid}/income/{record['id']}", json={"notes": "new"},
                         headers=h(primary.id)).json()
    assert updated["notes"] == "new" and updated["amount"] == 5000  # merge, not replace
    cleared = client.put(f"/api/households/{hid}/income/{record['id']}", json={"notes": None},
                         headers=h(primary.id)).json()
    assert cleared["notes"] is None


# ------------------------------------------------------------ validation


@pytest.mark.parametrize("resource, payload", [
    ("income", {"source": "S", "amount": 1, "frequency": "monthly", "notes": "x" * 501}),
    ("assets", {"name": "A", "asset_type": "cash", "current_value": 1, "is_liquid": True, "description": "x" * 201}),
    ("liabilities", {"name": "L", "liability_type": "other", "outstanding_amount": 1, "description": "x" * 201}),
])
def test_oversized_metadata_is_rejected(client, family, resource, payload):
    assert_problem(client.post(f"/api/households/{family['id']}/{resource}", json=payload,
                               headers=h(family["primary"].id)), 422)


def test_a_negative_interest_rate_is_rejected(client, family):
    assert_problem(client.post(f"/api/households/{family['id']}/liabilities",
                               json={"name": "L", "liability_type": "other", "outstanding_amount": 1,
                                     "interest_rate": -0.01},
                               headers=h(family["primary"].id)), 422)


@pytest.mark.parametrize("bad", ["abc", "1e400", "NaN", [], {}])
def test_a_malformed_interest_rate_is_rejected(client, family, bad):
    response = client.post(f"/api/households/{family['id']}/liabilities",
                           json={"name": "L", "liability_type": "other", "outstanding_amount": 1, "interest_rate": bad},
                           headers=h(family["primary"].id))
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("rate, status", [(100, 422), ("inf", 422), (99.9999, 201)])
def test_interest_rate_is_bounded_by_its_storage_limit(client, family, rate, status):
    """Numeric(6, 4) holds at most 99.9999. Anything beyond that, or non-finite,
    is a 422 -- never a database 500."""
    response = client.post(f"/api/households/{family['id']}/liabilities",
                           json={"name": "L", "liability_type": "other", "outstanding_amount": 1, "interest_rate": rate},
                           headers=h(family["primary"].id))
    assert response.status_code == status, response.text


def test_the_phase_33_amount_rule_still_applies(client, family):
    """ADR-032 kept `amount > 0`; Phase 35 did not relax it."""
    assert_problem(client.post(f"/api/households/{family['id']}/income",
                               json={"source": "Zero", "amount": 0, "frequency": "monthly"},
                               headers=h(family["primary"].id)), 422)


# ----------------------------------------------------- hostile strings


@pytest.mark.parametrize("hostile", [
    "'; DROP TABLE household_incomes; --",
    "<script>alert('x')</script>",
    "<img src=x onerror=alert(1)>",
    "Robert'); DELETE FROM households WHERE ('1'='1",
    "‮\u0000-free unicode: café ☃",
])
def test_hostile_strings_are_stored_and_returned_verbatim_as_data(client, family, hostile):
    """Parameterized SQL means these are just text: they are stored and echoed
    back unchanged, the tables still exist afterwards, and nothing executes.
    (The frontend renders text through React, which escapes it.)"""
    hostile = hostile.replace("\u0000", "")  # PostgreSQL text cannot hold NUL
    created = add(client, family["id"], family["primary"], "income",
                  source="Salary", amount=1000, frequency="monthly", notes=hostile)
    assert created["notes"] == hostile
    listed = client.get(f"/api/households/{family['id']}/income", headers=h(family["primary"].id))
    assert listed.status_code == 200 and listed.json()[0]["notes"] == hostile


# --------------------------------------------------------- permissions


def test_a_non_primary_member_cannot_write_metadata(client, family):
    assert_problem(client.post(f"/api/households/{family['id']}/income",
                               json={"source": "S", "amount": 1, "frequency": "monthly", "notes": "x"},
                               headers=h(family["member"].id)), 403)


def test_a_dependent_cannot_create_update_or_delete_a_record(client, family):
    """Phase 32/33's rule, re-checked with the Phase 35 fields: only the primary
    writes. A dependent can read, and nothing else."""
    hid = family["id"]
    record = add(client, hid, family["primary"], "liabilities", name="Home loan", liability_type="mortgage",
                 outstanding_amount=1000, interest_rate=0.03)
    dep = h(family["dependent"].id)
    assert_problem(client.post(f"/api/households/{hid}/liabilities",
                               json={"name": "X", "liability_type": "other", "outstanding_amount": 1}, headers=dep), 403)
    assert_problem(client.put(f"/api/households/{hid}/liabilities/{record['id']}",
                              json={"interest_rate": 0.99}, headers=dep), 403)
    assert_problem(client.delete(f"/api/households/{hid}/liabilities/{record['id']}", headers=dep), 403)
    listed = client.get(f"/api/households/{hid}/liabilities", headers=dep)
    assert listed.status_code == 200 and listed.json()[0]["interest_rate"] == 0.03


# ------------------------------------------------------------ isolation


@pytest.fixture()
def two(client, make_customer):
    a_primary, b_primary = make_customer(name="Meta A"), make_customer(name="Meta B")
    a, b = create_household(client, a_primary, "Meta House A"), create_household(client, b_primary, "Meta House B")
    a_rec = add(client, a["id"], a_primary, "liabilities", name="A loan", liability_type="mortgage",
                outstanding_amount=111111, interest_rate=0.0111, notes="A-SECRET-NOTE", description="A-DESC")
    b_rec = add(client, b["id"], b_primary, "liabilities", name="B loan", liability_type="mortgage",
                outstanding_amount=222222, interest_rate=0.0222, notes="B-SECRET-NOTE", description="B-DESC")
    return {"a": a, "b": b, "a_primary": a_primary, "b_primary": b_primary, "a_rec": a_rec, "b_rec": b_rec}


@pytest.mark.parametrize("attacker, victim", [("a", "b"), ("b", "a")])
def test_neither_household_can_read_the_other(client, two, attacker, victim):
    response = client.get(f"/api/households/{two[victim]['id']}/liabilities",
                          headers=h(two[f"{attacker}_primary"].id))
    body = assert_problem(response, 403)
    for leaked in (f"{victim.upper()}-SECRET-NOTE", f"{victim.upper()}-DESC", "222222", "111111"):
        assert leaked not in str(body)


@pytest.mark.parametrize("attacker, victim", [("a", "b"), ("b", "a")])
def test_neither_household_can_modify_or_delete_the_other(client, two, attacker, victim):
    victim_id, victim_rec = two[victim]["id"], two[f"{victim}_rec"]["id"]
    attacker_h = h(two[f"{attacker}_primary"].id)
    assert_problem(client.put(f"/api/households/{victim_id}/liabilities/{victim_rec}",
                              json={"notes": "tampered"}, headers=attacker_h), 403)
    assert_problem(client.delete(f"/api/households/{victim_id}/liabilities/{victim_rec}", headers=attacker_h), 403)
    still = client.get(f"/api/households/{victim_id}/liabilities", headers=h(two[f"{victim}_primary"].id)).json()
    assert still[0]["notes"] == f"{victim.upper()}-SECRET-NOTE"


def test_a_record_id_from_another_household_is_404_and_leaks_nothing(client, two):
    """Record-ID substitution: A's own household path, B's record id."""
    body = assert_problem(client.put(f"/api/households/{two['a']['id']}/liabilities/{two['b_rec']['id']}",
                                     json={"notes": "x"}, headers=h(two["a_primary"].id)), 404)
    assert "B-SECRET-NOTE" not in str(body) and "222222" not in str(body)


# ------------------------------------------- Phase 34 summary integration


@pytest.fixture()
def reference(client, family):
    """The Phase 35 specification's reference dataset (section 18.4)."""
    hid, p = family["id"], family["primary"]
    add(client, hid, p, "income", source="Monthly salary", amount=60000, frequency="monthly")
    add(client, hid, p, "income", source="Yearly income", amount=120000, frequency="yearly")
    add(client, hid, p, "income", source="One-time bonus", amount=50000, frequency="one_time")
    add(client, hid, p, "expenses", category="housing", amount=20000, frequency="monthly", is_essential=True)
    add(client, hid, p, "expenses", category="other", amount=120000, frequency="yearly", is_essential=False)
    add(client, hid, p, "expenses", category="other", amount=30000, frequency="one_time", is_essential=False)
    add(client, hid, p, "assets", name="Liquid cash", asset_type="cash", current_value=100000, is_liquid=True)
    add(client, hid, p, "liabilities", name="Outstanding loan", liability_type="personal_loan", outstanding_amount=200000)
    return family


def test_the_summary_reads_the_persisted_reference_dataset(client, reference):
    body = summary_of(client, reference["id"], reference["primary"])
    # 60,000 monthly + 120,000 yearly / 12
    assert body["income"]["recurring_monthly"] == 70000
    assert body["income"]["one_time"] == 50000
    # 20,000 monthly + 120,000 yearly / 12
    assert body["expenses"]["recurring_monthly"] == 30000
    assert body["expenses"]["recurring_essential_monthly"] == 20000
    assert body["expenses"]["recurring_nonessential_monthly"] == 10000
    assert body["expenses"]["one_time"] == 30000
    # one-time records excluded from recurring cash flow
    assert body["cash_flow"]["monthly"] == 40000
    assert body["assets"]["liquid"] == 100000
    assert body["liabilities"]["outstanding"] == 200000
    assert body["net_position"]["value"] == -100000
    # 6 x 20,000 = 120,000 required against 100,000 liquid
    assert body["emergency_fund"]["required"] == 120000
    assert body["emergency_fund"]["shortfall"] == 20000
    assert body["emergency_fund"]["status"] == "insufficient"


def test_the_summary_emergency_fund_agrees_with_the_individual_engine(client, reference):
    """Section 18.5: same inputs, same answer as `core/goals.py`."""
    fund = summary_of(client, reference["id"], reference["primary"])["emergency_fund"]
    individual = assess_emergency_fund(monthly_essential_expenses=20000, current_liquid_assets=100000)
    assert fund["required"] == pytest.approx(individual.required_amount)
    assert fund["shortfall"] == pytest.approx(individual.shortfall)
    assert (fund["status"] == "sufficient") is individual.sufficient


def test_metadata_never_moves_a_summary_figure(client, make_customer):
    """Two households with identical facts -- one with every Phase 35 field
    filled in, one with none -- must produce identical summaries apart from
    `household_id`. (Each needs its own primary: a customer can belong to only
    one household.)"""
    bare_primary, rich_primary = make_customer(name="Bare Twin"), make_customer(name="Rich Twin")
    bare = create_household(client, bare_primary, "Bare Twin House")["id"]
    rich = create_household(client, rich_primary, "Rich Twin House")["id"]

    facts = [
        ("income", {"source": "Salary", "amount": 5000, "frequency": "monthly"}, {"notes": "n"}),
        ("expenses", {"category": "food", "amount": 1000, "frequency": "monthly", "is_essential": True}, {"notes": "n"}),
        ("assets", {"name": "Cash", "asset_type": "cash", "current_value": 9000, "is_liquid": True},
         {"notes": "n", "description": "d"}),
        ("liabilities", {"name": "Card", "liability_type": "credit_card", "outstanding_amount": 500, "monthly_payment": 50},
         {"notes": "n", "description": "d", "interest_rate": 0.19}),
    ]
    for resource, fact, metadata in facts:
        add(client, bare, bare_primary, resource, **fact)
        add(client, rich, rich_primary, resource, **fact, **metadata)

    a, b = summary_of(client, bare, bare_primary), summary_of(client, rich, rich_primary)
    a.pop("household_id"), b.pop("household_id")
    assert a == b


def test_inactive_records_stay_excluded_after_phase_35(client, family):
    hid, p = family["id"], family["primary"]
    add(client, hid, p, "income", source="Salary", amount=5000, frequency="monthly")
    add(client, hid, p, "income", source="Old job", amount=9999, frequency="monthly", is_active=False, notes="ended")
    assert summary_of(client, hid, p)["income"]["recurring_monthly"] == 5000


def test_explicit_zero_survives_and_absence_stays_unavailable(client, family):
    hid, p = family["id"], family["primary"]
    add(client, hid, p, "assets", name="Emptied", asset_type="cash", current_value=0, is_liquid=True)
    body = summary_of(client, hid, p)
    assert body["assets"]["liquid"] == 0 and body["assets"]["available"] is True
    assert body["liabilities"]["outstanding"] is None and body["liabilities"]["available"] is False


# ------------------------------------------------------------- regression


def test_the_individual_analysis_is_unaffected_by_household_metadata(client, make_customer, monkeypatch):
    customer = make_customer(name="Meta Analysed")
    patch_graph(monkeypatch, approved_steps(customer.id))
    before = client.post("/api/analysis", json={"profile_id": customer.id})
    assert before.status_code == 200
    hid = create_household(client, customer)["id"]
    add(client, hid, customer, "liabilities", name="Loan", liability_type="personal_loan",
        outstanding_amount=99999, interest_rate=0.29, notes="high interest")
    after = client.post("/api/analysis", json={"profile_id": customer.id})
    assert after.json() == before.json()


def test_the_individual_financial_inputs_are_unaffected(client, make_customer):
    customer = make_customer(name="Meta Inputs")
    before = client.get(f"/api/profiles/{customer.id}/financial-inputs").json()
    hid = create_household(client, customer)["id"]
    add(client, hid, customer, "assets", name="Cash", asset_type="cash", current_value=50000, is_liquid=True,
        notes="should not become an individual input")
    assert client.get(f"/api/profiles/{customer.id}/financial-inputs").json() == before
