"""Phase B1 -- optional monthly financial records and behaviour features.

API tests against the rollback-safe TEST database (the shared `client` /
`make_customer` fixtures), plus direct tests of the table's own constraints.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from wealthpilot.api.services.analysis_service import compute_profile_hash
from wealthpilot.db.models import MonthlyFinancialRecord

PAST = "2025-03"


def url(customer_id: int, period: str | None = None) -> str:
    base = f"/api/profiles/{customer_id}/monthly-financial-records"
    return base if period is None else f"{base}/{period}"


# ------------------------------------------------------------------ optional / partial


def test_a_customer_with_no_records_has_an_empty_list_not_an_error(client, make_customer):
    customer = make_customer()
    body = client.get(url(customer.id)).json()
    assert body == {"customer_id": customer.id, "records": []}


def test_a_single_amount_is_a_valid_partial_record_and_the_rest_stay_null(client, make_customer):
    c = make_customer()
    r = client.put(url(c.id, PAST), json={"expenses": 40000})
    assert r.status_code == 200
    body = r.json()
    assert body["expenses"] == 40000
    assert body["income"] is None and body["savings"] is None and body["investment_contribution"] is None
    assert body["income_basis"] is None and body["period"] == PAST


def test_explicit_zero_is_stored_as_zero_and_missing_stays_null(client, make_customer):
    c = make_customer()
    body = client.put(url(c.id, PAST), json={"income": 100000, "investment_contribution": 0}).json()
    assert body["investment_contribution"] == 0
    assert body["savings"] is None  # omitted is not zero


def test_an_empty_payload_is_rejected_a_record_needs_an_amount(client, make_customer):
    c = make_customer()
    r = client.put(url(c.id, PAST), json={})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert client.get(url(c.id)).json()["records"] == []


def test_a_null_only_payload_is_rejected(client, make_customer):
    c = make_customer()
    assert client.put(url(c.id, PAST), json={"income": None}).status_code == 422


# ------------------------------------------------------------------ numeric validation


@pytest.mark.parametrize(
    "payload",
    [
        {"income": -1},
        {"expenses": -0.01},
        {"income": "1000"},          # strings are never coerced
        {"income": "1,000"},
        {"income": "12e3"},
        {"income": "abc"},
        {"income": True},
        {"income": [1]},
        {"income": 100.123},         # more than two decimal places
        {"income": 1e15},            # beyond Numeric(14, 2)
        {"income_basis": "after-tax", "income": 1},
        {"unknown_field": 1},
    ],
)
def test_malformed_values_are_rejected_with_422_and_nothing_is_stored(client, make_customer, payload):
    c = make_customer()
    assert client.put(url(c.id, PAST), json=payload).status_code == 422
    assert client.get(url(c.id)).json()["records"] == []


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_nan_and_infinity_are_rejected(client, make_customer, literal):
    c = make_customer()
    r = client.put(url(c.id, PAST), content=f'{{"income": {literal}}}', headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert client.get(url(c.id)).json()["records"] == []


def test_two_decimal_places_are_accepted(client, make_customer):
    c = make_customer()
    assert client.put(url(c.id, PAST), json={"income": 100000.55}).json()["income"] == 100000.55


# ------------------------------------------------------------------ periods


@pytest.mark.parametrize("bad", ["2025-13", "2025-00", "25-03", "2025-3", "abcd-ef", "2025-03-01"])
def test_a_malformed_period_is_rejected(client, make_customer, bad):
    c = make_customer()
    assert client.put(url(c.id, bad), json={"income": 1}).status_code == 400


def test_a_future_month_is_rejected(client, make_customer):
    c = make_customer()
    future = f"{date.today().year + 1}-01"
    assert client.put(url(c.id, future), json={"income": 1}).status_code == 400


def test_an_implausibly_old_period_is_rejected(client, make_customer):
    c = make_customer()
    assert client.put(url(c.id, "1999-12"), json={"income": 1}).status_code == 400


def test_the_current_month_is_accepted(client, make_customer):
    c = make_customer()
    now = f"{date.today():%Y-%m}"
    assert client.put(url(c.id, now), json={"income": 1}).status_code == 200


# ------------------------------------------------------------------ duplicates, updates, corrections


def test_a_month_is_stored_once_and_a_second_put_corrects_it(client, make_customer):
    c = make_customer()
    client.put(url(c.id, PAST), json={"income": 100000, "expenses": 40000})
    client.put(url(c.id, PAST), json={"expenses": 45000})
    records = client.get(url(c.id)).json()["records"]
    assert len(records) == 1
    assert records[0]["income"] == 100000      # omitted field kept
    assert records[0]["expenses"] == 45000     # supplied field corrected


def test_an_explicit_null_clears_a_field(client, make_customer):
    c = make_customer()
    client.put(url(c.id, PAST), json={"income": 100000, "expenses": 40000})
    body = client.put(url(c.id, PAST), json={"expenses": None}).json()
    assert body["expenses"] is None and body["income"] == 100000


def test_clearing_the_last_amount_is_rejected_and_the_record_survives(client, make_customer):
    c = make_customer()
    client.put(url(c.id, PAST), json={"expenses": 40000})
    assert client.put(url(c.id, PAST), json={"expenses": None}).status_code == 422
    assert client.get(url(c.id, PAST)).json()["expenses"] == 40000


def test_delete_removes_a_month_and_a_second_delete_is_404(client, make_customer):
    c = make_customer()
    client.put(url(c.id, PAST), json={"income": 1})
    assert client.delete(url(c.id, PAST)).status_code == 204
    assert client.get(url(c.id, PAST)).status_code == 404
    assert client.delete(url(c.id, PAST)).status_code == 404


def test_records_are_listed_newest_first(client, make_customer):
    c = make_customer()
    for period in ("2025-01", "2025-03", "2025-02"):
        client.put(url(c.id, period), json={"income": 1})
    assert [r["period"] for r in client.get(url(c.id)).json()["records"]] == ["2025-03", "2025-02", "2025-01"]


# ------------------------------------------------------------------ income basis


def test_income_basis_is_stored_when_income_is_present(client, make_customer):
    c = make_customer()
    assert client.put(url(c.id, PAST), json={"income": 1, "income_basis": "net"}).json()["income_basis"] == "net"


def test_income_basis_without_income_is_rejected(client, make_customer):
    c = make_customer()
    assert client.put(url(c.id, PAST), json={"expenses": 5, "income_basis": "gross"}).status_code == 422


def test_clearing_income_clears_its_basis(client, make_customer):
    c = make_customer()
    client.put(url(c.id, PAST), json={"income": 1, "expenses": 5, "income_basis": "net"})
    body = client.put(url(c.id, PAST), json={"income": None}).json()
    assert body["income"] is None and body["income_basis"] is None


# ------------------------------------------------------------------ isolation and not-found


def test_one_customers_records_are_invisible_to_another(client, make_customer):
    a, b = make_customer(name="A"), make_customer(name="B")
    client.put(url(a.id, PAST), json={"income": 1})
    assert client.get(url(b.id)).json()["records"] == []
    assert client.get(url(b.id, PAST)).status_code == 404
    assert client.delete(url(b.id, PAST)).status_code == 404
    assert client.get(url(a.id, PAST)).status_code == 200


def test_an_unknown_customer_is_404_on_every_route(client):
    for call in (
        lambda: client.get(url(999_999_999)),
        lambda: client.put(url(999_999_999, PAST), json={"income": 1}),
        lambda: client.delete(url(999_999_999, PAST)),
        lambda: client.get("/api/profiles/999999999/behaviour-features"),
    ):
        assert call().status_code == 404


# ------------------------------------------------------------------ features endpoint


def test_features_for_a_customer_with_no_records_are_all_unavailable_never_zero(client, make_customer):
    c = make_customer()
    body = client.get(f"/api/profiles/{c.id}/behaviour-features").json()
    assert body["observation_count"] == 0 and body["latest_period"] is None
    assert body["model_version"] == "behaviour_features_v1" and body["data_source"] == "monthly_financial_records"
    for feature in (body["latest_ratios"]["expense_to_income"], body["expenses_change"]["absolute_change"],
                    body["savings_consistency"]["share_with_amount"]):
        assert feature["value"] is None and feature["unavailable_reason"]


def test_features_reflect_the_stored_months(client, make_customer):
    c = make_customer()
    client.put(url(c.id, "2025-02"), json={"income": 100000, "expenses": 40000, "savings": 20000, "investment_contribution": 10000, "income_basis": "net"})
    client.put(url(c.id, "2025-03"), json={"income": 100000, "expenses": 50000, "savings": 20000, "investment_contribution": 10000, "income_basis": "net"})
    body = client.get(f"/api/profiles/{c.id}/behaviour-features").json()
    assert body["latest_period"] == "2025-03" and body["latest_income_basis"] == "net"
    assert body["latest_ratios"]["expense_to_income"]["value"] == pytest.approx(0.5)
    assert body["expenses_change"]["absolute_change"]["value"] == 10000
    assert body["expenses_change"]["relative_change"]["value"] == pytest.approx(0.25)
    assert body["currency"] == "INR"


def test_features_never_use_the_annual_profile_income(client, make_customer):
    c = make_customer(income=1_200_000)  # the existing ANNUAL figure
    client.put(url(c.id, PAST), json={"expenses": 40000})  # no monthly income reported
    body = client.get(f"/api/profiles/{c.id}/behaviour-features").json()
    ratio = body["latest_ratios"]["expense_to_income"]
    assert ratio["value"] is None and "Income was not reported" in ratio["unavailable_reason"]


# ------------------------------------------------------------------ existing behaviour untouched


def test_saving_monthly_records_does_not_change_the_analysis_cache_key(client, make_customer, db_session):
    c = make_customer(income=600000)
    before = compute_profile_hash(c, [])
    client.put(url(c.id, PAST), json={"income": 50000, "expenses": 30000})
    db_session.expire_all()
    assert compute_profile_hash(c, []) == before


def test_existing_financial_inputs_are_unaffected(client, make_customer):
    c = make_customer()
    client.put(f"/api/profiles/{c.id}/financial-inputs", json={"monthly_essential_expenses": 30000, "current_liquid_assets": 100000})
    client.put(url(c.id, PAST), json={"expenses": 12345})
    stored = client.get(f"/api/profiles/{c.id}/financial-inputs").json()
    assert stored["monthly_essential_expenses"] == 30000 and stored["current_liquid_assets"] == 100000


def test_a_customer_with_no_monthly_records_still_loads_the_profile(client, make_customer):
    c = make_customer()
    assert client.get(f"/api/profiles/{c.id}").status_code == 200


# ------------------------------------------------------------------ table constraints (defence in depth)


def _insert(db_session, customer_id, **kw):
    db_session.add(MonthlyFinancialRecord(customer_id=customer_id, period_month=kw.pop("period", date(2025, 3, 1)), **kw))
    db_session.flush()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"income": -1},
        {"period": date(2025, 3, 15), "income": 1},
        {"income_basis": "net", "expenses": 1},        # basis without income
        {"income": 1, "income_basis": "pretax"},
        {},                                             # no amount at all
    ],
)
def test_the_table_itself_rejects_invalid_rows(db_session, make_customer, kwargs):
    c = make_customer()
    with pytest.raises(IntegrityError):
        _insert(db_session, c.id, **kwargs)
    db_session.rollback()


def test_the_table_rejects_a_duplicate_period(db_session, make_customer):
    c = make_customer()
    _insert(db_session, c.id, income=1)
    with pytest.raises(IntegrityError):
        _insert(db_session, c.id, income=2)
    db_session.rollback()


def test_a_duplicate_period_race_is_a_409_and_never_echoes_the_amounts(client, make_customer, monkeypatch):
    """If two saves of the same NEW month race, the loser hits the unique
    constraint. It must become a clean 409 -- the driver's own error embeds the
    submitted amounts and must not reach the response."""
    from wealthpilot.api.services import monthly_records_service as service

    c = make_customer()
    assert client.put(url(c.id, PAST), json={"income": 1}).status_code == 200
    monkeypatch.setattr(service, "_find", lambda *args, **kwargs: None)  # the racer saw no row yet
    r = client.put(url(c.id, PAST), json={"income": 987654.32})
    assert r.status_code == 409
    assert "987654" not in r.text
