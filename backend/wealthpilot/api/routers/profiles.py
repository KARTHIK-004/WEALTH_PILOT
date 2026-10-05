"""GET /api/questionnaire, POST /api/profiles, GET /api/profiles/{id}
(BUILD_PLAN.md section 12), plus Phase 23's persistence routes --
POST/GET /api/profiles/{id}/questionnaire and
POST /api/profiles/{id}/goals -- the Live Analysis Flow phase's
GET /api/profiles/lookup (exact-name lookup; see `ProfileLookupResponse`'s
own docstring) -- and Phase 28's GET/PUT /api/profiles/{id}/financial-inputs
(see `FinancialInputsUpdate`'s own docstring). Thin routes only --
validation and DB reads/writes through the existing `db.models` ORM, no
financial logic (every actual calculation stays in `core/goals.py`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.errors import CustomerNotFoundError, InvalidRequestError
from wealthpilot.api.schemas import (
    FinancialInputsResponse,
    FinancialInputsUpdate,
    GoalCreate,
    GoalOut,
    ProfileCreateRequest,
    ProfileCreateResponse,
    ProfileLookupResponse,
    ProfileResponse,
    QuestionnaireAnswerOut,
    QuestionnaireAnswersResponse,
    QuestionnaireAnswersSubmitRequest,
    QuestionnaireResponse,
)
from wealthpilot.api.services.questionnaire_service import get_questionnaire_sections, is_valid_answer
from wealthpilot.db.models import Customer, FinancialGoal, FinancialInputs, QuestionnaireAnswer

router = APIRouter(tags=["profiles"])


@router.get("/api/questionnaire", response_model=QuestionnaireResponse)
def get_questionnaire() -> QuestionnaireResponse:
    return QuestionnaireResponse(sections=get_questionnaire_sections())


@router.post("/api/profiles", response_model=ProfileCreateResponse, status_code=201)
def create_profile(payload: ProfileCreateRequest, session: Session = Depends(get_session)) -> ProfileCreateResponse:
    customer = Customer(
        name=payload.name,
        age=payload.age,
        income=payload.income,
        employment_status=payload.employment_status,
        customer_type=payload.customer_type,
        investment_capacity=payload.investment_capacity,
        data_source="user-entered",
    )
    session.add(customer)
    session.flush()

    for goal in payload.goals:
        session.add(
            FinancialGoal(
                customer_id=customer.id,
                goal_type=goal.goal_type,
                target_amount=goal.target_amount,
                target_date=goal.target_date,
                current_savings=goal.current_savings,
                priority=goal.priority,
            )
        )
    session.flush()

    return ProfileCreateResponse(customer_id=customer.id)


@router.get("/api/profiles/lookup", response_model=ProfileLookupResponse)
def lookup_profile_by_name(name: str, session: Session = Depends(get_session)) -> ProfileLookupResponse:
    """Live Analysis Flow phase -- see `ProfileLookupResponse`'s own
    docstring. Registered before `/api/profiles/{profile_id}` so a literal
    `lookup` path segment is never captured by that route's `int` converter
    (Starlette skips a non-numeric segment for an `int` path parameter
    regardless of registration order, but the explicit ordering keeps the
    intent unambiguous). Exact, case-sensitive `Customer.name` match only --
    no partial/fuzzy search, no listing. `customers.name` is not unique
    (Phase 24's per-browser demo flow can legitimately create a second
    customer with the same name), so when several match the LOWEST id wins,
    deterministically -- Phase 29 fix; without an ORDER BY the database was
    free to return either row on different calls."""
    customer = session.scalar(select(Customer).where(Customer.name == name).order_by(Customer.id).limit(1))
    return ProfileLookupResponse(customer_id=customer.id if customer else None)


@router.get("/api/profiles/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: int, session: Session = Depends(get_session)) -> ProfileResponse:
    customer = session.get(Customer, profile_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={profile_id}")

    return ProfileResponse(
        customer_id=customer.id,
        name=customer.name,
        age=customer.age,
        income=float(customer.income) if customer.income is not None else None,
        employment_status=customer.employment_status,
        customer_type=customer.customer_type,
        investment_capacity=customer.investment_capacity,
        goals=[
            GoalOut(
                id=g.id, goal_type=g.goal_type, target_amount=float(g.target_amount), target_date=g.target_date,
                current_savings=float(g.current_savings), priority=g.priority,
            )
            for g in customer.financial_goals
        ],
        data_source=customer.data_source,
        created_at=customer.created_at,
    )


def _questionnaire_answers_response(session: Session, profile_id: int) -> QuestionnaireAnswersResponse:
    rows = (
        session.execute(
            select(QuestionnaireAnswer)
            .where(QuestionnaireAnswer.customer_id == profile_id)
            .order_by(QuestionnaireAnswer.question_number)
        )
        .scalars()
        .all()
    )
    return QuestionnaireAnswersResponse(
        customer_id=profile_id,
        answers=[
            QuestionnaireAnswerOut(question_number=r.question_number, option_key=r.selected_option_key, updated_at=r.updated_at)
            for r in rows
        ],
    )


@router.post("/api/profiles/{profile_id}/questionnaire", response_model=QuestionnaireAnswersResponse)
def submit_questionnaire_answers(
    profile_id: int, payload: QuestionnaireAnswersSubmitRequest, session: Session = Depends(get_session)
) -> QuestionnaireAnswersResponse:
    """Upserts one row per submitted (question_number, option_key) --
    Phase 23. `question_number`/`option_key` are validated against the
    REAL parsed questionnaire (`is_valid_answer`, backed by the same
    `GET /api/questionnaire` data) before anything is written, so an
    invalid reference fails with a 400 rather than being silently stored.
    Re-submitting an already-answered question UPDATES that row (the
    `uq_questionnaire_answers_customer_question` constraint on
    `db.models.QuestionnaireAnswer` guarantees at most one row per
    question) -- never a duplicate. No score, category, or ML inference is
    computed anywhere in this function; it only stores the submitted
    identifiers."""
    customer = session.get(Customer, profile_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={profile_id}")

    for answer in payload.answers:
        if not is_valid_answer(answer.question_number, answer.option_key):
            raise InvalidRequestError(
                f"question_number={answer.question_number} has no option '{answer.option_key}'"
            )

    for answer in payload.answers:
        existing = session.execute(
            select(QuestionnaireAnswer).where(
                QuestionnaireAnswer.customer_id == profile_id,
                QuestionnaireAnswer.question_number == answer.question_number,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.selected_option_key = answer.option_key
        else:
            session.add(
                QuestionnaireAnswer(
                    customer_id=profile_id, question_number=answer.question_number, selected_option_key=answer.option_key
                )
            )
    session.flush()

    return _questionnaire_answers_response(session, profile_id)


@router.get("/api/profiles/{profile_id}/questionnaire", response_model=QuestionnaireAnswersResponse)
def get_questionnaire_answers(profile_id: int, session: Session = Depends(get_session)) -> QuestionnaireAnswersResponse:
    customer = session.get(Customer, profile_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={profile_id}")
    return _questionnaire_answers_response(session, profile_id)


@router.post("/api/profiles/{profile_id}/goals", response_model=GoalOut, status_code=201)
def create_goal_for_profile(profile_id: int, payload: GoalCreate, session: Session = Depends(get_session)) -> GoalOut:
    """Creates ONE `FinancialGoal` row for an already-existing customer --
    Phase 23's answer to the gap Phase 22 documented (the embedded `goals`
    field on `POST /api/profiles` only ever applied at customer-creation
    time). Reuses the exact same `FinancialGoal` model and `GoalCreate`/
    `GoalOut` schemas that path already used -- no second goal table, no
    invented field. `POST /api/profiles`'s own embedded-goals behavior is
    untouched by this function's existence."""
    customer = session.get(Customer, profile_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={profile_id}")

    goal = FinancialGoal(
        customer_id=profile_id,
        goal_type=payload.goal_type,
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        current_savings=payload.current_savings,
        priority=payload.priority,
    )
    session.add(goal)
    session.flush()

    return GoalOut(
        id=goal.id, goal_type=goal.goal_type, target_amount=float(goal.target_amount), target_date=goal.target_date,
        current_savings=float(goal.current_savings), priority=goal.priority,
    )


def _financial_inputs_response(profile_id: int, row: FinancialInputs | None) -> FinancialInputsResponse:
    if row is None:
        return FinancialInputsResponse(
            customer_id=profile_id, monthly_essential_expenses=None, current_liquid_assets=None,
            contribution_amount=None, annual_return_rate=None, annual_inflation_rate=None,
            contribution_periods_per_year=None, updated_at=None,
        )
    return FinancialInputsResponse(
        customer_id=profile_id,
        monthly_essential_expenses=float(row.monthly_essential_expenses) if row.monthly_essential_expenses is not None else None,
        current_liquid_assets=float(row.current_liquid_assets) if row.current_liquid_assets is not None else None,
        contribution_amount=float(row.contribution_amount) if row.contribution_amount is not None else None,
        annual_return_rate=float(row.annual_return_rate) if row.annual_return_rate is not None else None,
        annual_inflation_rate=float(row.annual_inflation_rate) if row.annual_inflation_rate is not None else None,
        contribution_periods_per_year=row.contribution_periods_per_year,
        updated_at=row.updated_at,
    )


@router.get("/api/profiles/{profile_id}/financial-inputs", response_model=FinancialInputsResponse)
def get_financial_inputs(profile_id: int, session: Session = Depends(get_session)) -> FinancialInputsResponse:
    """Phase 28 — the missing financial-input data contract §2's dependency
    map identified. A customer with no row yet returns every field `None`
    (200, not 404 -- "not yet provided" is a normal state, exactly like
    `GET .../questionnaire` returning an empty `answers` list rather than
    404ing before any answer exists)."""
    customer = session.get(Customer, profile_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={profile_id}")
    row = session.scalar(select(FinancialInputs).where(FinancialInputs.customer_id == profile_id))
    return _financial_inputs_response(profile_id, row)


@router.put("/api/profiles/{profile_id}/financial-inputs", response_model=FinancialInputsResponse)
def update_financial_inputs(
    profile_id: int, payload: FinancialInputsUpdate, session: Session = Depends(get_session)
) -> FinancialInputsResponse:
    """Upserts the one `financial_inputs` row for this customer -- merges
    only the fields the caller actually supplied (any field omitted, i.e.
    left `None` in the payload, leaves that column's current stored value
    untouched; there is no way to submit only some fields on `POST
    /api/profiles`, so this mirrors `submit_questionnaire_answers`'s own
    upsert-not-replace behaviour instead). Every value stored is exactly
    what the caller submitted -- no derived/calculated field is written
    here; `assess_emergency_fund`/`GoalAssumptions` still do all
    calculation, downstream, in `core/goals.py`, unchanged."""
    customer = session.get(Customer, profile_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={profile_id}")

    row = session.scalar(select(FinancialInputs).where(FinancialInputs.customer_id == profile_id))
    if row is None:
        row = FinancialInputs(customer_id=profile_id)
        session.add(row)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    session.flush()

    return _financial_inputs_response(profile_id, row)
