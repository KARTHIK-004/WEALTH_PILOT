"""Phase 33 — household financial DATA (source records only).

Stores and returns what a household reports about its income, expenses,
assets and liabilities, plus the optional factual metadata Phase 35 added
(`notes` everywhere, `description` on assets and liabilities, `interest_rate`
on liabilities) -- none of which any calculation reads. It computes **nothing**: there is no total, sum,
net worth, cash flow, ratio, savings or emergency-fund calculation in this
module and none may be added here — aggregation is a later phase
(`docs/DECISIONS.md` ADR-032). None of this data reaches the individual
analysis pipeline, which is unchanged.

Authorization is Phase 32's, unchanged and reused (`household_service`'s
`require_member`/`require_primary_member`): the caller is the asserted
`X-Customer-Id` customer, any member of the household may READ, and only the
primary member may create, update or delete. A non-member gets 403, an
unknown household 404, a missing identity 401.

Ownership is server-controlled. Every record is reached as
`(household_id from the path, record id)`, so a record belonging to another
household is simply not found (404) — its existence is never revealed, and
`household_id` cannot be changed through any payload (the update schemas do
not define that field, and they forbid unknown fields).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wealthpilot.api.errors import HouseholdRecordNotFoundError
from wealthpilot.api.schemas import (
    HouseholdAssetCreate,
    HouseholdAssetResponse,
    HouseholdAssetUpdate,
    HouseholdExpenseCreate,
    HouseholdExpenseResponse,
    HouseholdExpenseUpdate,
    HouseholdIncomeCreate,
    HouseholdIncomeResponse,
    HouseholdIncomeUpdate,
    HouseholdLiabilityCreate,
    HouseholdLiabilityResponse,
    HouseholdLiabilityUpdate,
)
from wealthpilot.api.services.household_service import require_member, require_primary_member
from wealthpilot.db.models import HouseholdAsset, HouseholdExpense, HouseholdIncome, HouseholdLiability


def _money(value: Any) -> float | None:
    """A `Numeric` column comes back as `Decimal`; the public contract is a
    float. `None` stays `None` — never 0 (CLAUDE.md section 12)."""
    return None if value is None else float(value)


@dataclass(frozen=True)
class _Resource:
    """One financial resource: its ORM model and the wording used in its
    not-found message. The four resources share this plumbing, but each has
    its own explicit public functions below."""

    model: type
    label: str


_INCOME = _Resource(HouseholdIncome, "income record")
_EXPENSE = _Resource(HouseholdExpense, "expense record")
_ASSET = _Resource(HouseholdAsset, "asset record")
_LIABILITY = _Resource(HouseholdLiability, "liability record")


def _list_rows(session: Session, resource: _Resource, household_id: int, acting_customer_id: int) -> list[Any]:
    require_member(session, household_id, acting_customer_id)
    return list(
        session.scalars(
            select(resource.model)
            .where(resource.model.household_id == household_id)
            .order_by(resource.model.id)
        ).all()
    )


def _create_row(session: Session, resource: _Resource, household_id: int, acting_customer_id: int, values: dict) -> Any:
    require_primary_member(session, household_id, acting_customer_id, action="manage household financial data")
    # `household_id` comes from the path, never from the caller's payload.
    row = resource.model(household_id=household_id, **values)
    session.add(row)
    session.flush()
    return row


def _owned_row(session: Session, resource: _Resource, household_id: int, record_id: int) -> Any:
    """Scoped by BOTH ids, so a record belonging to another household is a
    404 rather than a leak."""
    row = session.get(resource.model, record_id)
    if row is None or row.household_id != household_id:
        raise HouseholdRecordNotFoundError(f"No {resource.label} with id={record_id} in household id={household_id}")
    return row


def _update_row(
    session: Session, resource: _Resource, household_id: int, acting_customer_id: int, record_id: int, changes: dict
) -> Any:
    require_primary_member(session, household_id, acting_customer_id, action="manage household financial data")
    row = _owned_row(session, resource, household_id, record_id)
    for field, value in changes.items():
        setattr(row, field, value)
    session.flush()
    return row


def _delete_row(session: Session, resource: _Resource, household_id: int, acting_customer_id: int, record_id: int) -> None:
    require_primary_member(session, household_id, acting_customer_id, action="manage household financial data")
    session.delete(_owned_row(session, resource, household_id, record_id))
    session.flush()


# --------------------------------------------------------------------- income


def _income_out(row: HouseholdIncome) -> HouseholdIncomeResponse:
    return HouseholdIncomeResponse(
        id=row.id, household_id=row.household_id, source=row.source, amount=_money(row.amount),
        frequency=row.frequency, is_active=row.is_active, notes=row.notes,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def list_income(session: Session, household_id: int, acting_customer_id: int) -> list[HouseholdIncomeResponse]:
    return [_income_out(row) for row in _list_rows(session, _INCOME, household_id, acting_customer_id)]


def create_income(session: Session, household_id: int, acting_customer_id: int, payload: HouseholdIncomeCreate) -> HouseholdIncomeResponse:
    return _income_out(_create_row(session, _INCOME, household_id, acting_customer_id, payload.model_dump()))


def update_income(session: Session, household_id: int, acting_customer_id: int, income_id: int, payload: HouseholdIncomeUpdate) -> HouseholdIncomeResponse:
    return _income_out(_update_row(session, _INCOME, household_id, acting_customer_id, income_id, payload.model_dump(exclude_unset=True)))


def delete_income(session: Session, household_id: int, acting_customer_id: int, income_id: int) -> None:
    _delete_row(session, _INCOME, household_id, acting_customer_id, income_id)


# -------------------------------------------------------------------- expense


def _expense_out(row: HouseholdExpense) -> HouseholdExpenseResponse:
    return HouseholdExpenseResponse(
        id=row.id, household_id=row.household_id, category=row.category, description=row.description,
        amount=_money(row.amount), frequency=row.frequency, is_essential=row.is_essential,
        is_active=row.is_active, notes=row.notes, created_at=row.created_at, updated_at=row.updated_at,
    )


def list_expenses(session: Session, household_id: int, acting_customer_id: int) -> list[HouseholdExpenseResponse]:
    return [_expense_out(row) for row in _list_rows(session, _EXPENSE, household_id, acting_customer_id)]


def create_expense(session: Session, household_id: int, acting_customer_id: int, payload: HouseholdExpenseCreate) -> HouseholdExpenseResponse:
    return _expense_out(_create_row(session, _EXPENSE, household_id, acting_customer_id, payload.model_dump()))


def update_expense(session: Session, household_id: int, acting_customer_id: int, expense_id: int, payload: HouseholdExpenseUpdate) -> HouseholdExpenseResponse:
    return _expense_out(_update_row(session, _EXPENSE, household_id, acting_customer_id, expense_id, payload.model_dump(exclude_unset=True)))


def delete_expense(session: Session, household_id: int, acting_customer_id: int, expense_id: int) -> None:
    _delete_row(session, _EXPENSE, household_id, acting_customer_id, expense_id)


# ---------------------------------------------------------------------- asset


def _asset_out(row: HouseholdAsset) -> HouseholdAssetResponse:
    return HouseholdAssetResponse(
        id=row.id, household_id=row.household_id, name=row.name, asset_type=row.asset_type,
        current_value=_money(row.current_value), is_liquid=row.is_liquid,
        description=row.description, notes=row.notes,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def list_assets(session: Session, household_id: int, acting_customer_id: int) -> list[HouseholdAssetResponse]:
    return [_asset_out(row) for row in _list_rows(session, _ASSET, household_id, acting_customer_id)]


def create_asset(session: Session, household_id: int, acting_customer_id: int, payload: HouseholdAssetCreate) -> HouseholdAssetResponse:
    return _asset_out(_create_row(session, _ASSET, household_id, acting_customer_id, payload.model_dump()))


def update_asset(session: Session, household_id: int, acting_customer_id: int, asset_id: int, payload: HouseholdAssetUpdate) -> HouseholdAssetResponse:
    return _asset_out(_update_row(session, _ASSET, household_id, acting_customer_id, asset_id, payload.model_dump(exclude_unset=True)))


def delete_asset(session: Session, household_id: int, acting_customer_id: int, asset_id: int) -> None:
    _delete_row(session, _ASSET, household_id, acting_customer_id, asset_id)


# ------------------------------------------------------------------ liability


def _liability_out(row: HouseholdLiability) -> HouseholdLiabilityResponse:
    return HouseholdLiabilityResponse(
        id=row.id, household_id=row.household_id, name=row.name, liability_type=row.liability_type,
        outstanding_amount=_money(row.outstanding_amount), monthly_payment=_money(row.monthly_payment),
        # A stored rate, echoed back as recorded. `_money` is only the
        # Decimal -> float conversion, and `None` stays `None`.
        interest_rate=_money(row.interest_rate), description=row.description, notes=row.notes,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def list_liabilities(session: Session, household_id: int, acting_customer_id: int) -> list[HouseholdLiabilityResponse]:
    return [_liability_out(row) for row in _list_rows(session, _LIABILITY, household_id, acting_customer_id)]


def create_liability(session: Session, household_id: int, acting_customer_id: int, payload: HouseholdLiabilityCreate) -> HouseholdLiabilityResponse:
    return _liability_out(_create_row(session, _LIABILITY, household_id, acting_customer_id, payload.model_dump()))


def update_liability(session: Session, household_id: int, acting_customer_id: int, liability_id: int, payload: HouseholdLiabilityUpdate) -> HouseholdLiabilityResponse:
    return _liability_out(_update_row(session, _LIABILITY, household_id, acting_customer_id, liability_id, payload.model_dump(exclude_unset=True)))


def delete_liability(session: Session, household_id: int, acting_customer_id: int, liability_id: int) -> None:
    _delete_row(session, _LIABILITY, household_id, acting_customer_id, liability_id)
