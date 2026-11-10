"""Monthly financial records and behaviour features (Research Enhancement
Track B1, `docs/DECISIONS.md` ADR-042).

Orchestration only: validation of the payload lives in `api/schemas.py`, the
arithmetic in `core/behaviour_features.py`. Every query is scoped by
`customer_id` (ADR-024). Amounts are stored exactly as submitted; nothing is
derived or written back, and nothing here is read by the analysis pipeline, so
saving a month cannot change any existing result.

Privacy: no amount, payload or feature value is ever logged by this module.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wealthpilot.api.errors import (
    ConflictError,
    CustomerNotFoundError,
    InvalidRequestError,
    MonthlyRecordNotFoundError,
    UnprocessableRecordError,
)
from wealthpilot.api.schemas import (
    BehaviourFeaturesResponse,
    ChangeFeatureOut,
    ConsistencyFeatureOut,
    FeatureValueOut,
    MonthlyRecordListResponse,
    MonthlyRecordResponse,
    MonthlyRecordUpdate,
    RatioFeaturesOut,
)
from wealthpilot.core.behaviour_features import (
    BehaviourFeatures,
    ChangeFeature,
    ConsistencyFeature,
    FeatureValue,
    MonthlyObservation,
    compute_behaviour_features,
)
from wealthpilot.db.models import Customer, MonthlyFinancialRecord

DATA_SOURCE = "monthly_financial_records"
EARLIEST_PERIOD = date(2000, 1, 1)
_PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_AMOUNT_FIELDS = ("income", "expenses", "savings", "investment_contribution")


def parse_period(value: str, *, today: date | None = None) -> date:
    """`YYYY-MM` -> the first day of that month. A future month cannot have been
    observed yet, and years before 2000 are not a plausible reporting period."""
    match = _PERIOD_RE.match(value)
    if match is None:
        raise InvalidRequestError("period must be a calendar month written as YYYY-MM, for example 2026-09.")
    period = date(int(match.group(1)), int(match.group(2)), 1)
    current = today or date.today()
    if period < EARLIEST_PERIOD:
        raise InvalidRequestError("period is too far in the past to be a plausible reporting month.")
    if period > date(current.year, current.month, 1):
        raise InvalidRequestError("period cannot be in the future: a month is reported after it has started.")
    return period


def _require_customer(session: Session, customer_id: int) -> None:
    if session.get(Customer, customer_id) is None:
        raise CustomerNotFoundError(f"No customer with id={customer_id}")


def _num(value: object) -> float | None:
    return None if value is None else float(value)


def _response(row: MonthlyFinancialRecord) -> MonthlyRecordResponse:
    return MonthlyRecordResponse(
        customer_id=row.customer_id,
        period=f"{row.period_month:%Y-%m}",
        income=_num(row.income),
        expenses=_num(row.expenses),
        savings=_num(row.savings),
        investment_contribution=_num(row.investment_contribution),
        income_basis=row.income_basis,  # type: ignore[arg-type]
        updated_at=row.updated_at,
    )


def _find(session: Session, customer_id: int, period: date) -> MonthlyFinancialRecord | None:
    return session.scalar(
        select(MonthlyFinancialRecord).where(
            MonthlyFinancialRecord.customer_id == customer_id, MonthlyFinancialRecord.period_month == period
        )
    )


def upsert_record(session: Session, customer_id: int, period_text: str, payload: MonthlyRecordUpdate) -> MonthlyRecordResponse:
    """Creates or corrects the one record for this customer and month. Fields
    omitted from the payload are untouched; explicit nulls clear. The merged
    result must still hold at least one amount, and an income basis requires an
    income."""
    _require_customer(session, customer_id)
    period = parse_period(period_text)
    row = _find(session, customer_id, period)

    # Merge into a plain dict first and validate it BEFORE touching any stored
    # row, so a rejected request can never leave a half-applied change behind.
    merged: dict[str, object] = {
        f: (getattr(row, f) if row is not None else None) for f in (*_AMOUNT_FIELDS, "income_basis")
    }
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        merged[field] = Decimal(repr(value)) if value is not None and field in _AMOUNT_FIELDS else value

    if all(merged[f] is None for f in _AMOUNT_FIELDS):
        raise UnprocessableRecordError(
            "A monthly record must contain at least one amount. To remove a month, delete it instead."
        )
    if merged["income"] is None:
        if payload.income_basis is not None:
            raise UnprocessableRecordError("income_basis can only be set together with an income.")
        merged["income_basis"] = None

    if row is None:
        row = MonthlyFinancialRecord(customer_id=customer_id, period_month=period)
        session.add(row)
    for field, value in merged.items():
        setattr(row, field, value)
    try:
        session.flush()
    except IntegrityError:
        # Two saves for the same new month raced. Never let the driver's error
        # (which embeds the submitted amounts) reach a log or a response.
        session.rollback()
        raise ConflictError("This month was saved at the same time from another request. Please try again.") from None
    session.refresh(row)
    return _response(row)


def list_records(session: Session, customer_id: int) -> MonthlyRecordListResponse:
    _require_customer(session, customer_id)
    rows = session.scalars(
        select(MonthlyFinancialRecord)
        .where(MonthlyFinancialRecord.customer_id == customer_id)
        .order_by(MonthlyFinancialRecord.period_month.desc())
    ).all()
    return MonthlyRecordListResponse(customer_id=customer_id, records=[_response(r) for r in rows])


def get_record(session: Session, customer_id: int, period_text: str) -> MonthlyRecordResponse:
    _require_customer(session, customer_id)
    row = _find(session, customer_id, parse_period(period_text))
    if row is None:
        raise MonthlyRecordNotFoundError(f"No record for {period_text}.")
    return _response(row)


def delete_record(session: Session, customer_id: int, period_text: str) -> None:
    _require_customer(session, customer_id)
    row = _find(session, customer_id, parse_period(period_text))
    if row is None:
        raise MonthlyRecordNotFoundError(f"No record for {period_text}.")
    session.delete(row)
    session.flush()


def _value(feature: FeatureValue) -> FeatureValueOut:
    return FeatureValueOut(value=feature.value, unavailable_reason=feature.unavailable_reason)


def _change(feature: ChangeFeature) -> ChangeFeatureOut:
    return ChangeFeatureOut(absolute_change=_value(feature.absolute_change), relative_change=_value(feature.relative_change))


def _consistency(feature: ConsistencyFeature) -> ConsistencyFeatureOut:
    return ConsistencyFeatureOut(
        share_with_amount=_value(feature.share_with_amount),
        known_months=feature.known_months,
        window_months=feature.window_months,
    )


def _dec(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def core_features(session: Session, customer_id: int) -> BehaviourFeatures:
    """The core feature set for this customer's own reported months (scoped by
    `customer_id`; shared with the personalised-insight service, ADR-043). A
    customer with no records gets features that are all unavailable with a
    reason -- never zeros."""
    _require_customer(session, customer_id)
    rows = session.scalars(
        select(MonthlyFinancialRecord).where(MonthlyFinancialRecord.customer_id == customer_id)
    ).all()
    return compute_behaviour_features(
        MonthlyObservation(
            period=r.period_month,
            income=_dec(r.income),
            expenses=_dec(r.expenses),
            savings=_dec(r.savings),
            investment_contribution=_dec(r.investment_contribution),
            income_basis=r.income_basis,
        )
        for r in rows
    )


def behaviour_features(session: Session, customer_id: int) -> BehaviourFeaturesResponse:
    """The feature set for this customer's own reported months. A customer with
    no records gets a valid response whose every feature is unavailable with a
    reason -- never zeros."""
    result = core_features(session, customer_id)
    return BehaviourFeaturesResponse(
        customer_id=customer_id,
        model_version=result.feature_set_version,
        data_source=DATA_SOURCE,
        currency=result.currency,
        observation_count=result.observation_count,
        latest_period=None if result.latest_period is None else f"{result.latest_period:%Y-%m}",
        latest_income_basis=result.latest_income_basis,  # type: ignore[arg-type]
        latest_ratios=RatioFeaturesOut(
            expense_to_income=_value(result.latest_ratios.expense_to_income),
            savings_to_income=_value(result.latest_ratios.savings_to_income),
            investment_contribution_to_income=_value(result.latest_ratios.investment_contribution_to_income),
        ),
        income_change=_change(result.income_change),
        expenses_change=_change(result.expenses_change),
        savings_change=_change(result.savings_change),
        investment_contribution_change=_change(result.investment_contribution_change),
        savings_consistency=_consistency(result.savings_consistency),
        investment_contribution_consistency=_consistency(result.investment_contribution_consistency),
        data_quality_notes=result.data_quality_notes,
    )
