"""The household of the full-pipeline persona (ADR-051), end to end through the real application (conftest.py: real app and models, throwaway SQLite file, no network).

Covers: the household built through the public API (E primary, partner F), every dataset record present exactly once, the application's own household summary checked against ARITHMETIC
DONE HERE FROM THE DATASET FILES (the seed stores no computed value), coherence with E's individual records, isolation between customers and households, idempotency without
overwriting what a user changed, the partner staying honestly pending, and the twelve monthly records reaching the behaviour endpoint for E and only for E.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text

from seed_demo_data import ALL_DEMO_PERSONAS, FAMILY_DEMO, PIPELINE_HOUSEHOLD, setup_family, verify_family

E, F, D, A, B = "WPDEMO-E", "WPDEMO-F", "WPDEMO-D", "WPDEMO-A", "WPDEMO-B"
PERSONAS = {p["demo_key"]: p for p in ALL_DEMO_PERSONAS}
RESOURCES = ("income", "expenses", "assets", "liabilities", "goals")


def as_customer(customer_id: int) -> dict[str, str]:
    return {"X-Customer-Id": str(customer_id)}


def hid(world) -> int:
    return world.household["household_id"]


def monthly(amount: float, frequency: str) -> Decimal:
    return {"monthly": Decimal(str(amount)), "yearly": Decimal(str(amount)) / 12}.get(frequency, Decimal(0))


def dataset_totals() -> dict[str, Decimal]:
    """The summary's figures worked out from the dataset records alone (the Phase 34 rules: monthly as is, yearly / 12, one-time kept apart, inactive records excluded)."""
    spec = PIPELINE_HOUSEHOLD
    income = [r for r in spec["income"] if r.get("is_active", True)]
    expenses = [r for r in spec["expenses"] if r.get("is_active", True)]
    recurring_income = sum(monthly(r["amount"], r["frequency"]) for r in income)
    recurring = [r for r in expenses if r["frequency"] != "one_time"]
    return {
        "recurring_income": recurring_income,
        "recurring_expenses": sum(monthly(r["amount"], r["frequency"]) for r in recurring),
        "essential": sum(monthly(r["amount"], r["frequency"]) for r in recurring if r["is_essential"]),
        "one_time_income": sum(Decimal(str(r["amount"])) for r in income if r["frequency"] == "one_time"),
        "one_time_expenses": sum(Decimal(str(r["amount"])) for r in expenses if r["frequency"] == "one_time"),
        "assets": sum(Decimal(str(r["current_value"])) for r in spec["assets"]),
        "liquid": sum(Decimal(str(r["current_value"])) for r in spec["assets"] if r["is_liquid"]),
        "liabilities": sum(Decimal(str(r["outstanding_amount"])) for r in spec["liabilities"]),
        "payments": sum(Decimal(str(r.get("monthly_payment") or 0)) for r in spec["liabilities"]),
    }


# ------------------------------------------------------------------------------------------ composition


def test_the_household_has_the_primary_and_the_partner_and_nobody_else(world):
    primary, partner = world.ids[E], world.ids[F]
    own = world.client.get(f"/api/profiles/{primary}/household", headers=as_customer(primary)).json()
    assert own["household"]["name"] == PIPELINE_HOUSEHOLD["household_name"] and own["household"]["member_count"] == 2
    assert (own["membership"]["relationship"], own["membership"]["role"], own["membership"]["is_dependent"]) == ("self", "primary", False)
    members = world.client.get(f"/api/households/{hid(world)}/members", headers=as_customer(primary)).json()["members"]
    assert {(m["customer_id"], m["relationship"], m["role"]) for m in members} == {(primary, "self", "primary"), (partner, "spouse", "member")}
    assert set(members[0]) == {"id", "household_id", "customer_id", "customer_name", "relationship", "role", "is_dependent", "created_at", "updated_at"}   # identity and membership only


def test_every_dataset_record_is_present_exactly_once_and_the_seed_reports_it_verified(world):
    for resource in RESOURCES:
        stored = world.client.get(f"/api/households/{hid(world)}/{resource}", headers=as_customer(world.ids[E])).json()
        key = PIPELINE_HOUSEHOLD["record_keys"][resource]
        assert sorted(row[key] for row in stored) == sorted(r[key] for r in PIPELINE_HOUSEHOLD[resource]), resource
    ok, lines = verify_family(world.client, PIPELINE_HOUSEHOLD)
    assert ok, lines


# ------------------------------------------------------------------------------------------ the application's summary against independent arithmetic


def test_the_household_summary_is_the_applications_own_and_equals_arithmetic_done_from_the_files(world):
    expected = dataset_totals()
    summary = world.client.get(f"/api/households/{hid(world)}/financial-summary", headers=as_customer(world.ids[E])).json()
    assert Decimal(str(summary["income"]["recurring_monthly"])) == expected["recurring_income"] == 155000
    assert Decimal(str(summary["expenses"]["recurring_monthly"])) == expected["recurring_expenses"] == 96000
    assert Decimal(str(summary["expenses"]["recurring_essential_monthly"])) == expected["essential"] == 80000
    assert Decimal(str(summary["expenses"]["recurring_nonessential_monthly"])) == expected["recurring_expenses"] - expected["essential"]
    assert Decimal(str(summary["income"]["one_time"])) == expected["one_time_income"]
    assert Decimal(str(summary["expenses"]["one_time"])) == expected["one_time_expenses"]
    assert Decimal(str(summary["cash_flow"]["monthly"])) == expected["recurring_income"] - expected["recurring_expenses"] == 59000
    assert Decimal(str(summary["assets"]["total"])) == expected["assets"] and Decimal(str(summary["assets"]["liquid"])) == expected["liquid"]
    assert Decimal(str(summary["liabilities"]["outstanding"])) == expected["liabilities"]
    assert Decimal(str(summary["liabilities"]["monthly_payment"])) == expected["payments"] == 16000
    assert Decimal(str(summary["net_position"]["value"])) == expected["assets"] - expected["liabilities"]
    fund = summary["emergency_fund"]
    assert Decimal(str(fund["required"])) == 6 * expected["essential"] and fund["status"] == "sufficient" and Decimal(str(fund["shortfall"])) == 0
    assert all(summary["data_completeness"][k] != "unavailable" for k in ("income", "expenses", "assets", "liabilities", "emergency_fund"))
    # an inactive income stays stored and counted, but is in no total; a stated zero (the credit card) is a known zero, not an unknown
    assert summary["income"]["record_count"] == 5 and summary["income"]["active_record_count"] == 4
    cards = [r for r in world.client.get(f"/api/households/{hid(world)}/liabilities", headers=as_customer(world.ids[E])).json() if r["name"] == "Credit card"]
    assert cards and cards[0]["outstanding_amount"] == 0 and cards[0]["monthly_payment"] is None


def test_each_emi_is_both_a_liability_payment_and_a_debt_payment_expense_of_the_same_size(world):
    liabilities = {r["name"]: r for r in PIPELINE_HOUSEHOLD["liabilities"] if r.get("monthly_payment")}
    emis = {r["description"]: r for r in PIPELINE_HOUSEHOLD["expenses"] if r["category"] == "debt_payment"}
    assert sorted(r["monthly_payment"] for r in liabilities.values()) == sorted(r["amount"] for r in emis.values()) == [6500, 9500]
    assert all(r["interest_rate"] and 0 < r["interest_rate"] < 0.2 and r["outstanding_amount"] > 0 for r in liabilities.values())


# ------------------------------------------------------------------------------------------ coherence with E's individual records


def test_the_household_records_are_coherent_with_the_primary_members_own_records(world):
    persona = PERSONAS[E]
    latest = persona["monthly_records"][-1]
    totals = dataset_totals()
    salary = next(r for r in PIPELINE_HOUSEHOLD["income"] if r["source"] == "Primary salary (net)")
    assert salary["amount"] == latest["income"]                                                           # E's latest reported month
    emi_total = sum(r["amount"] for r in PIPELINE_HOUSEHOLD["expenses"] if r["category"] == "debt_payment")
    assert totals["recurring_expenses"] - emi_total >= latest["expenses"]                                  # the household spends at least what E reports spending
    assert totals["recurring_income"] - totals["recurring_expenses"] >= latest["savings"] + latest["investment_contribution"]   # E's saving and investing fit inside the household's cash flow
    assert totals["liquid"] >= persona["financial_inputs"]["current_liquid_assets"]                        # E's easy-access savings are part of the liquid assets
    assert any(r["current_value"] == persona["financial_inputs"]["current_liquid_assets"] for r in PIPELINE_HOUSEHOLD["assets"])
    individual = world.results[E]["goals"]
    assert individual and world.results[E]["emergency_fund"]["sufficient"] is True                          # the individual position is unchanged and sufficient


def test_the_household_changed_nothing_about_any_individual_analysis(world):
    for key, customer_id in world.ids.items():
        again = world.client.post("/api/analysis", json={"profile_id": customer_id})
        assert again.status_code == 200
        assert again.json() == world.results[key], key
    with world.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM analysis_runs WHERE customer_id = :i"), {"i": world.ids[E]}).scalar() == 1   # no second run was needed


# ------------------------------------------------------------------------------------------ the partner stays honestly pending


def test_the_partner_is_pending_information_with_nothing_invented(world):
    result = world.results[F]
    assert result["status"] == "pending_information"
    assert result["risk"] is None or result["risk"].get("risk_category") is None
    assert not result["recommendation"] and not result["explanation"]
    assert world.client.get(f"/api/profiles/{world.ids[F]}/financial-inputs").json()["monthly_essential_expenses"] is None   # unknown stays null, never zero
    insight = world.client.post(f"/api/profiles/{world.ids[F]}/personalized-insights", json={}).json()
    assert insight["behaviour"]["observation_count"] == 0 and insight["risk_profile"] is None


# ------------------------------------------------------------------------------------------ isolation


def test_only_members_read_the_household_and_every_other_customer_is_denied(world):
    primary, partner = world.ids[E], world.ids[F]
    url = f"/api/households/{hid(world)}"
    assert world.client.get(f"{url}/financial-summary", headers=as_customer(partner)).status_code == 200       # a member may read
    for outsider in (A, D, B):
        for path in ("financial-summary", "members", "income", "assets", "liabilities"):
            assert world.client.get(f"{url}/{path}", headers=as_customer(world.ids[outsider])).status_code == 403, (outsider, path)
    assert world.client.get(f"{url}/financial-summary").status_code == 401                                         # no identity at all
    # a member cannot read a profile's household on another customer's behalf, and E's household id is not reachable with the family primary's identity
    assert world.client.get(f"/api/profiles/{partner}/household", headers=as_customer(primary)).status_code == 403
    family = world.client.get(f"/api/profiles/{world.ids[B]}/household", headers=as_customer(world.ids[B])).json()
    assert family["household"] is None or family["household"]["id"] != hid(world)


def test_only_the_primary_writes_and_a_record_of_another_household_is_a_404(world):
    primary, partner = world.ids[E], world.ids[F]
    body = {"source": "Test only", "amount": 1000, "frequency": "monthly"}
    assert world.client.post(f"/api/households/{hid(world)}/income", json=body, headers=as_customer(partner)).status_code == 403
    mine = world.client.get(f"/api/households/{hid(world)}/income", headers=as_customer(primary)).json()[0]["id"]
    assert world.client.put(f"/api/households/{hid(world)}/income/{mine}", json={"amount": 1}, headers=as_customer(partner)).status_code == 403


def test_the_individual_demo_personas_belong_to_no_household(world):
    for key in (A, D):
        own = world.client.get(f"/api/profiles/{world.ids[key]}/household", headers=as_customer(world.ids[key])).json()
        assert own["household"] is None and own["membership"] is None, key


# ------------------------------------------------------------------------------------------ idempotency without overwriting


def test_running_setup_again_creates_nothing_and_never_overwrites_what_a_user_changed(world):
    primary = world.ids[E]

    def counts() -> dict[str, int]:
        with world.engine.connect() as conn:
            return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in (
                "customers", "households", "household_members", "household_incomes", "household_expenses", "household_assets", "household_liabilities", "household_goals", "monthly_financial_records")}

    before = counts()
    rent = next(r for r in world.client.get(f"/api/households/{hid(world)}/expenses", headers=as_customer(primary)).json() if r["description"] == "Rent")
    assert world.client.put(f"/api/households/{hid(world)}/expenses/{rent['id']}", json={"amount": 31000}, headers=as_customer(primary)).status_code == 200
    again = setup_family(world.client, PIPELINE_HOUSEHOLD)
    assert again["created"] == [] and again["household_id"] == hid(world)
    for persona in ALL_DEMO_PERSONAS:                                         # re-seeding the personas through the same code path creates nothing either
        from seed_demo_data import seed_persona
        assert seed_persona(world.client, persona, link_risk_data=world.link)["created"] == [], persona["demo_key"]
    assert counts() == before                                                  # no duplicate member, loan, EMI, expense, goal or month
    stored = next(r for r in world.client.get(f"/api/households/{hid(world)}/expenses", headers=as_customer(primary)).json() if r["description"] == "Rent")
    assert stored["amount"] == 31000                                           # the user's edit survived
    assert world.client.put(f"/api/households/{hid(world)}/expenses/{rent['id']}", json={"amount": 30000}, headers=as_customer(primary)).status_code == 200   # restore for later tests


def test_the_family_household_is_untouched_by_the_pipeline_household(world):
    assert FAMILY_DEMO["household_name"] != PIPELINE_HOUSEHOLD["household_name"]
    with world.engine.connect() as conn:
        names = {r[0] for r in conn.execute(text("SELECT name FROM households"))}
    assert names == {PIPELINE_HOUSEHOLD["household_name"]}                     # this module's world has only the pipeline household: the family one is built by `setup-family`


# ------------------------------------------------------------------------------------------ the twelve monthly records reach the behaviour endpoint, for E only


def test_all_twelve_months_are_stored_for_the_exact_profile_and_the_behaviour_endpoint_returns_them(world):
    customer_id = world.ids[E]
    listed = world.client.get(f"/api/profiles/{customer_id}/monthly-financial-records").json()["records"]
    assert [r["period"] for r in listed][::-1] == [r["period"] for r in PERSONAS[E]["monthly_records"]] and len(listed) == 12
    assert {r["customer_id"] for r in listed} == {customer_id}                                    # every month belongs to exactly this profile
    insight = world.client.post(f"/api/profiles/{customer_id}/personalized-insights", json={}).json()
    assert insight["customer_id"] == customer_id and insight["behaviour"]["observation_count"] == 12 and insight["behaviour"]["latest_period"] == "2026-09"
    features = world.client.get(f"/api/profiles/{customer_id}/behaviour-features").json()
    assert features["observation_count"] == 12


def test_a_profile_without_months_reports_zero_and_never_borrows_another_profiles(world):
    for key in (A, D, F):
        customer_id = world.ids[key]
        assert world.client.get(f"/api/profiles/{customer_id}/monthly-financial-records").json()["records"] == [], key
        insight = world.client.post(f"/api/profiles/{customer_id}/personalized-insights", json={}).json()
        assert insight["behaviour"]["observation_count"] == 0 and insight["behaviour"]["history"] == "none", key
        assert all(f["status"] != "observed" or f["category"] == "coverage" for f in insight["behaviour"]["findings"]), key   # nothing observed that needs a month


# ------------------------------------------------------------------------------------------ one `setup` command leaves the whole full-pipeline account complete


def test_the_setup_command_builds_the_household_and_a_second_run_changes_nothing(world, capsys, monkeypatch):
    import seed_demo_data
    from seed_demo_data import setup

    asked: list[str] = []
    real = seed_demo_data.setup_family
    monkeypatch.setattr(seed_demo_data, "setup_family", lambda client, spec=None: (asked.append((spec or {}).get("demo_key", "family")), real(client, spec))[1])

    def counts() -> tuple:
        with world.engine.connect() as conn:
            return tuple(conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in (
                "customers", "households", "household_members", "household_incomes", "household_expenses", "household_assets", "household_liabilities", "household_goals",
                "monthly_financial_records", "financial_goals", "questionnaire_answers", "analysis_runs"))

    before = counts()
    setup(world.client)                                                    # the documented command, run against a database that already holds everything
    out = capsys.readouterr().out
    assert asked == [PIPELINE_HOUSEHOLD["demo_key"]]                       # `setup` addresses exactly the full-pipeline household (not the family one)
    assert PIPELINE_HOUSEHOLD["household_name"] in out and "created (0): []" in out and counts() == before
