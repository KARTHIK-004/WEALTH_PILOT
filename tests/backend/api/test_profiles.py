"""GET /api/questionnaire, POST /api/profiles, GET /api/profiles/{id},
and Phase 23's persistence routes: POST/GET /api/profiles/{id}/questionnaire,
POST /api/profiles/{id}/goals."""

from __future__ import annotations

from wealthpilot.db.models import QuestionnaireAnswer


def test_questionnaire_returns_parsed_sections(client):
    response = client.get("/api/questionnaire")
    assert response.status_code == 200
    body = response.json()
    assert len(body["sections"]) == 5
    total_questions = sum(len(s["questions"]) for s in body["sections"])
    assert total_questions == 25
    first_question = body["sections"][0]["questions"][0]
    assert first_question["number"] == 1
    assert len(first_question["options"]) >= 2


def test_create_profile_then_fetch_it(client):
    create_response = client.post(
        "/api/profiles",
        json={
            "name": "Ada Lovelace",
            "age": 30,
            "income": 85000,
            "employment_status": "Employed",
            "customer_type": "Mass",
            "investment_capacity": "CAP_30K_80K",
            "goals": [
                {"goal_type": "retirement", "target_amount": 500000, "target_date": "2050-01-01", "current_savings": 10000, "priority": 1}
            ],
        },
    )
    assert create_response.status_code == 201
    customer_id = create_response.json()["customer_id"]

    get_response = client.get(f"/api/profiles/{customer_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["customer_id"] == customer_id
    assert body["name"] == "Ada Lovelace"
    assert body["data_source"] == "user-entered"
    assert len(body["goals"]) == 1
    assert body["goals"][0]["goal_type"] == "retirement"


def test_create_profile_with_no_goals(client):
    response = client.post("/api/profiles", json={"name": "Grace Hopper"})
    assert response.status_code == 201


def test_get_nonexistent_profile_returns_404_problem_json(client):
    response = client.get("/api/profiles/999999999")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Customer not found"
    assert "detail" in body
    assert "instance" in body


def test_create_profile_rejects_invalid_goal_amount(client):
    response = client.post(
        "/api/profiles",
        json={"name": "Bad Goal", "goals": [{"goal_type": "x", "target_amount": -5, "target_date": "2030-01-01"}]},
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_create_profile_rejects_missing_name(client):
    response = client.post("/api/profiles", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Phase 23 — questionnaire answer persistence
# ---------------------------------------------------------------------------


def test_submit_and_retrieve_questionnaire_answers(client, make_customer):
    customer = make_customer()

    submit = client.post(
        f"/api/profiles/{customer.id}/questionnaire",
        json={"answers": [{"question_number": 1, "option_key": "a"}, {"question_number": 2, "option_key": "b"}]},
    )
    assert submit.status_code == 200
    body = submit.json()
    assert body["customer_id"] == customer.id
    answers_by_question = {a["question_number"]: a["option_key"] for a in body["answers"]}
    assert answers_by_question == {1: "a", 2: "b"}
    assert all("updated_at" in a for a in body["answers"])

    get_response = client.get(f"/api/profiles/{customer.id}/questionnaire")
    assert get_response.status_code == 200
    got = {a["question_number"]: a["option_key"] for a in get_response.json()["answers"]}
    assert got == {1: "a", 2: "b"}


def test_resubmitting_a_question_updates_rather_than_duplicates(client, make_customer, db_session):
    customer = make_customer()

    client.post(f"/api/profiles/{customer.id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "a"}]})
    second = client.post(f"/api/profiles/{customer.id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "c"}]})
    assert second.status_code == 200
    assert second.json()["answers"] == [
        {
            "question_number": 1,
            "option_key": "c",
            "updated_at": second.json()["answers"][0]["updated_at"],
        }
    ]

    rows = db_session.query(QuestionnaireAnswer).filter_by(customer_id=customer.id, question_number=1).all()
    assert len(rows) == 1
    assert rows[0].selected_option_key == "c"

    get_response = client.get(f"/api/profiles/{customer.id}/questionnaire")
    assert len(get_response.json()["answers"]) == 1
    assert get_response.json()["answers"][0]["option_key"] == "c"


def test_submit_questionnaire_rejects_invalid_question_number(client, make_customer):
    customer = make_customer()
    response = client.post(f"/api/profiles/{customer.id}/questionnaire", json={"answers": [{"question_number": 999, "option_key": "a"}]})
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_submit_questionnaire_rejects_option_not_belonging_to_question(client, make_customer):
    customer = make_customer()
    response = client.post(f"/api/profiles/{customer.id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "z"}]})
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_submit_questionnaire_for_nonexistent_customer_returns_404(client):
    response = client.post("/api/profiles/999999999/questionnaire", json={"answers": [{"question_number": 1, "option_key": "a"}]})
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_get_questionnaire_answers_for_nonexistent_customer_returns_404(client):
    response = client.get("/api/profiles/999999999/questionnaire")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_submit_questionnaire_rejects_empty_answers_list(client, make_customer):
    customer = make_customer()
    response = client.post(f"/api/profiles/{customer.id}/questionnaire", json={"answers": []})
    assert response.status_code == 422


def test_get_questionnaire_answers_when_none_submitted_returns_empty_list(client, make_customer):
    customer = make_customer()
    response = client.get(f"/api/profiles/{customer.id}/questionnaire")
    assert response.status_code == 200
    assert response.json()["answers"] == []


def test_questionnaire_answers_are_isolated_per_customer(client, make_customer):
    customer_a = make_customer(name="Customer A")
    customer_b = make_customer(name="Customer B")

    client.post(f"/api/profiles/{customer_a.id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "a"}]})
    client.post(f"/api/profiles/{customer_b.id}/questionnaire", json={"answers": [{"question_number": 1, "option_key": "b"}]})

    a_answers = client.get(f"/api/profiles/{customer_a.id}/questionnaire").json()["answers"]
    b_answers = client.get(f"/api/profiles/{customer_b.id}/questionnaire").json()["answers"]

    assert a_answers == [{"question_number": 1, "option_key": "a", "updated_at": a_answers[0]["updated_at"]}]
    assert b_answers == [{"question_number": 1, "option_key": "b", "updated_at": b_answers[0]["updated_at"]}]


# ---------------------------------------------------------------------------
# Phase 23 — goal creation for an existing profile
# ---------------------------------------------------------------------------


def test_create_goal_for_existing_profile_then_it_appears_on_get_profile(client, make_customer):
    customer = make_customer()

    response = client.post(
        f"/api/profiles/{customer.id}/goals",
        json={"goal_type": "House Purchase", "target_amount": 300000, "target_date": "2035-06-01", "current_savings": 20000, "priority": 2},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["goal_type"] == "House Purchase"
    assert body["target_amount"] == 300000
    assert body["current_savings"] == 20000
    assert body["priority"] == 2
    assert "id" in body

    profile = client.get(f"/api/profiles/{customer.id}").json()
    assert len(profile["goals"]) == 1
    assert profile["goals"][0]["goal_type"] == "House Purchase"


def test_create_goal_uses_schema_defaults(client, make_customer):
    customer = make_customer()
    response = client.post(
        f"/api/profiles/{customer.id}/goals", json={"goal_type": "Retirement", "target_amount": 100000, "target_date": "2050-01-01"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["current_savings"] == 0
    assert body["priority"] == 1


def test_create_goal_for_nonexistent_customer_returns_404(client):
    response = client.post(
        "/api/profiles/999999999/goals",
        json={"goal_type": "x", "target_amount": 1000, "target_date": "2030-01-01"},
    )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_create_goal_rejects_invalid_amount(client, make_customer):
    customer = make_customer()
    response = client.post(
        f"/api/profiles/{customer.id}/goals",
        json={"goal_type": "x", "target_amount": -5, "target_date": "2030-01-01"},
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_create_goal_rejects_missing_required_field(client, make_customer):
    customer = make_customer()
    response = client.post(f"/api/profiles/{customer.id}/goals", json={"target_amount": 1000, "target_date": "2030-01-01"})
    assert response.status_code == 422


def test_goals_created_via_new_endpoint_are_isolated_per_customer(client, make_customer):
    customer_a = make_customer(name="Customer A")
    customer_b = make_customer(name="Customer B")

    client.post(
        f"/api/profiles/{customer_a.id}/goals",
        json={"goal_type": "A's goal", "target_amount": 1000, "target_date": "2030-01-01"},
    )

    profile_a = client.get(f"/api/profiles/{customer_a.id}").json()
    profile_b = client.get(f"/api/profiles/{customer_b.id}").json()
    assert len(profile_a["goals"]) == 1
    assert len(profile_b["goals"]) == 0


# ---------------------------------------------------------------------------
# Phase 28 — GET/PUT /api/profiles/{id}/financial-inputs
# ---------------------------------------------------------------------------


def test_get_financial_inputs_before_any_put_returns_all_null(client, make_customer):
    customer = make_customer()
    response = client.get(f"/api/profiles/{customer.id}/financial-inputs")
    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == customer.id
    assert body["monthly_essential_expenses"] is None
    assert body["current_liquid_assets"] is None
    assert body["contribution_amount"] is None
    assert body["annual_return_rate"] is None
    assert body["annual_inflation_rate"] is None
    assert body["contribution_periods_per_year"] is None
    assert body["updated_at"] is None


def test_put_financial_inputs_creates_then_returns_them(client, make_customer):
    customer = make_customer()
    response = client.put(
        f"/api/profiles/{customer.id}/financial-inputs",
        json={
            "monthly_essential_expenses": 2500.0,
            "current_liquid_assets": 15000.0,
            "contribution_amount": 500.0,
            "annual_return_rate": 0.07,
            "annual_inflation_rate": 0.03,
            "contribution_periods_per_year": 12,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["monthly_essential_expenses"] == 2500.0
    assert body["current_liquid_assets"] == 15000.0
    assert body["contribution_amount"] == 500.0
    assert body["annual_return_rate"] == 0.07
    assert body["annual_inflation_rate"] == 0.03
    assert body["contribution_periods_per_year"] == 12
    assert body["updated_at"] is not None

    get_response = client.get(f"/api/profiles/{customer.id}/financial-inputs")
    assert get_response.json()["monthly_essential_expenses"] == 2500.0


def test_put_financial_inputs_partial_update_merges_not_replaces(client, make_customer):
    customer = make_customer()
    client.put(
        f"/api/profiles/{customer.id}/financial-inputs",
        json={"monthly_essential_expenses": 2000.0, "current_liquid_assets": 10000.0},
    )
    second = client.put(
        f"/api/profiles/{customer.id}/financial-inputs", json={"current_liquid_assets": 20000.0}
    )
    assert second.status_code == 200
    body = second.json()
    assert body["monthly_essential_expenses"] == 2000.0  # untouched by the second PUT
    assert body["current_liquid_assets"] == 20000.0  # updated


def test_put_financial_inputs_explicit_null_clears_a_field(client, make_customer):
    customer = make_customer()
    client.put(f"/api/profiles/{customer.id}/financial-inputs", json={"monthly_essential_expenses": 2000.0})
    cleared = client.put(
        f"/api/profiles/{customer.id}/financial-inputs", json={"monthly_essential_expenses": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["monthly_essential_expenses"] is None


def test_put_financial_inputs_rejects_negative_amount(client, make_customer):
    customer = make_customer()
    response = client.put(
        f"/api/profiles/{customer.id}/financial-inputs", json={"monthly_essential_expenses": -100.0}
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_put_financial_inputs_rejects_impossible_rate(client, make_customer):
    customer = make_customer()
    response = client.put(f"/api/profiles/{customer.id}/financial-inputs", json={"annual_return_rate": -1.5})
    assert response.status_code == 422


def test_put_financial_inputs_rejects_non_positive_contribution_periods(client, make_customer):
    customer = make_customer()
    response = client.put(
        f"/api/profiles/{customer.id}/financial-inputs", json={"contribution_periods_per_year": 0}
    )
    assert response.status_code == 422


def test_financial_inputs_for_nonexistent_customer_returns_404(client):
    get_response = client.get("/api/profiles/999999999/financial-inputs")
    assert get_response.status_code == 404
    assert get_response.headers["content-type"] == "application/problem+json"

    put_response = client.put("/api/profiles/999999999/financial-inputs", json={"monthly_essential_expenses": 100.0})
    assert put_response.status_code == 404


def test_financial_inputs_are_isolated_per_customer(client, make_customer):
    customer_a = make_customer(name="Customer A")
    customer_b = make_customer(name="Customer B")

    client.put(f"/api/profiles/{customer_a.id}/financial-inputs", json={"monthly_essential_expenses": 1111.0})
    client.put(f"/api/profiles/{customer_b.id}/financial-inputs", json={"monthly_essential_expenses": 2222.0})

    a = client.get(f"/api/profiles/{customer_a.id}/financial-inputs").json()
    b = client.get(f"/api/profiles/{customer_b.id}/financial-inputs").json()
    assert a["monthly_essential_expenses"] == 1111.0
    assert b["monthly_essential_expenses"] == 2222.0

    # Customer A cannot read or overwrite Customer B's stored values through
    # any request scoped to Customer A's own id.
    assert a["customer_id"] == customer_a.id
    assert b["customer_id"] == customer_b.id


# ---------------------------------------------------------------------------
# Live Analysis Flow phase — GET /api/profiles/lookup (exact name lookup)
# ---------------------------------------------------------------------------


def test_lookup_profile_by_name_finds_exact_match(client, make_customer):
    customer = make_customer(name="WealthPilot Demo — Complete")
    response = client.get("/api/profiles/lookup", params={"name": "WealthPilot Demo — Complete"})
    assert response.status_code == 200
    assert response.json() == {"customer_id": customer.id}


def test_lookup_profile_by_name_returns_null_not_404_when_absent(client):
    response = client.get("/api/profiles/lookup", params={"name": "Nobody With This Name"})
    assert response.status_code == 200
    assert response.json() == {"customer_id": None}


def test_lookup_profile_by_name_is_case_sensitive_exact_match_only(client, make_customer):
    make_customer(name="WealthPilot Demo — Complete")
    response = client.get("/api/profiles/lookup", params={"name": "wealthpilot demo — complete"})
    assert response.json() == {"customer_id": None}

    partial = client.get("/api/profiles/lookup", params={"name": "WealthPilot Demo"})
    assert partial.json() == {"customer_id": None}


def test_lookup_profile_by_name_is_deterministic_when_names_are_duplicated(client, make_customer):
    """`customers.name` is not unique (Phase 24's per-browser demo flow can
    create a second customer with the same name -- a real one exists in the
    dev database). The lowest id must win, every time, rather than
    whichever row the database happens to return first."""
    first = make_customer(name="Duplicated Demo Name")
    second = make_customer(name="Duplicated Demo Name")
    assert first.id < second.id
    for _ in range(5):
        response = client.get("/api/profiles/lookup", params={"name": "Duplicated Demo Name"})
        assert response.json() == {"customer_id": first.id}


def test_lookup_profile_by_name_requires_name_param(client):
    response = client.get("/api/profiles/lookup")
    assert response.status_code == 422


def test_embedded_goals_profile_creation_still_works(client):
    """Regression: POST /api/profiles's own embedded `goals` field (Phase
    21) must be unaffected by the new dedicated goal-creation endpoint."""
    response = client.post(
        "/api/profiles",
        json={
            "name": "Embedded Goals Regression",
            "goals": [{"goal_type": "retirement", "target_amount": 500000, "target_date": "2050-01-01", "current_savings": 10000, "priority": 1}],
        },
    )
    assert response.status_code == 201
    customer_id = response.json()["customer_id"]
    profile = client.get(f"/api/profiles/{customer_id}").json()
    assert len(profile["goals"]) == 1
    assert profile["goals"][0]["goal_type"] == "retirement"
