"""Phase 32 — household identity/membership orchestration.

Structural rules only: who belongs to which household, in what
relationship and role. There is no financial logic here and none may be
added -- household financial aggregation is a later phase
(`docs/DECISIONS.md` ADR-031), and household membership is contextual data
that never feeds `POST /api/analysis`.

Authorization model. The prototype has no server session, so every household
route takes the caller's associated customer (`X-Customer-Id`, see
`api/dependencies.py::get_acting_customer_id`) and authorizes against
membership: a customer can read a household only if they belong to it, and
only the household's PRIMARY member can add or remove members. That identity
is asserted by the client, so this stops accidental and URL-edited
cross-household access, not a malicious client (`docs/SECURITY.md`).

Rules (also enforced by the database, so no code path can bypass them):
one household per customer; one primary per household; the primary is the
`self` relationship; `self` is never a dependent. "At least one primary" is
guaranteed here, transactionally: the primary membership is created in the
same transaction as its household and nothing removes it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wealthpilot.api.errors import (
    AccessDeniedError,
    ConflictError,
    CustomerNotFoundError,
    HouseholdMemberNotFoundError,
    HouseholdNotFoundError,
)
from wealthpilot.api.schemas import (
    HouseholdMemberCreateRequest,
    HouseholdMemberOut,
    HouseholdMembersResponse,
    HouseholdOut,
    ProfileHouseholdResponse,
)
from wealthpilot.db.models import Customer, Household, HouseholdMember


@contextmanager
def _conflict_on_integrity(session: Session, detail: str) -> Iterator[None]:
    """Runs the block inside a SAVEPOINT and turns a database integrity
    violation (the backstop for a race the pre-checks below cannot see, such
    as two requests adding the same customer at once) into a 409. The
    SAVEPOINT means only this write is undone, never the caller's other
    work in the same transaction."""
    try:
        with session.begin_nested():
            yield
    except IntegrityError as exc:
        raise ConflictError(detail) from exc


def _member_count(session: Session, household_id: int) -> int:
    return session.scalar(select(func.count()).select_from(HouseholdMember).where(HouseholdMember.household_id == household_id)) or 0


def _household_out(session: Session, household: Household) -> HouseholdOut:
    return HouseholdOut(
        id=household.id,
        name=household.name,
        member_count=_member_count(session, household.id),
        created_at=household.created_at,
        updated_at=household.updated_at,
    )


def _member_out(member: HouseholdMember) -> HouseholdMemberOut:
    return HouseholdMemberOut(
        id=member.id,
        household_id=member.household_id,
        customer_id=member.customer_id,
        customer_name=member.customer.name,
        relationship=member.relationship_type,  # type: ignore[arg-type]
        role=member.role,  # type: ignore[arg-type]
        is_dependent=member.is_dependent,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def _require_customer(session: Session, customer_id: int) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise CustomerNotFoundError(f"No customer with id={customer_id}")
    return customer


def _membership_of(session: Session, customer_id: int) -> HouseholdMember | None:
    return session.scalar(select(HouseholdMember).where(HouseholdMember.customer_id == customer_id))


def _require_acting_member(session: Session, household_id: int, acting_customer_id: int) -> HouseholdMember:
    """404 for a household that does not exist, 403 for one the acting
    customer does not belong to."""
    if session.get(Household, household_id) is None:
        raise HouseholdNotFoundError(f"No household with id={household_id}")
    membership = session.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id, HouseholdMember.customer_id == acting_customer_id
        )
    )
    if membership is None:
        raise AccessDeniedError("The associated customer is not a member of this household.")
    return membership


def _require_primary(membership: HouseholdMember, action: str = "add or remove members") -> None:
    if membership.role != "primary":
        raise AccessDeniedError(f"Only the household's primary member can {action}.")


# ---------------------------------------------------------------------------
# Public authorization helpers. Phase 33's household financial data reuses
# EXACTLY this membership check rather than inventing a second rule: any member
# may read, only the primary may mutate (`docs/RULES.md` Rule 31/32).
# ---------------------------------------------------------------------------


def require_member(session: Session, household_id: int, acting_customer_id: int) -> HouseholdMember:
    """The acting customer's membership in this household. 404 if the
    household does not exist, 403 if they do not belong to it."""
    return _require_acting_member(session, household_id, acting_customer_id)


def require_primary_member(
    session: Session, household_id: int, acting_customer_id: int, *, action: str = "add or remove members"
) -> HouseholdMember:
    """As `require_member`, and additionally 403 unless the acting customer is
    the household's primary member. `action` only words the message."""
    membership = _require_acting_member(session, household_id, acting_customer_id)
    _require_primary(membership, action)
    return membership


def create_household(session: Session, acting_customer_id: int, name: str) -> tuple[HouseholdOut, HouseholdMemberOut]:
    """Creates the household and its `self`/`primary` membership for the
    acting customer, atomically. Nothing else is created."""
    _require_customer(session, acting_customer_id)
    if _membership_of(session, acting_customer_id) is not None:
        raise ConflictError("This customer already belongs to a household; a customer can belong to at most one.")

    household = Household(name=name)
    with _conflict_on_integrity(session, "This customer already belongs to a household; a customer can belong to at most one."):
        session.add(household)
        session.flush()
        primary = HouseholdMember(
            household_id=household.id,
            customer_id=acting_customer_id,
            relationship_type="self",
            role="primary",
            is_dependent=False,
        )
        session.add(primary)
    return _household_out(session, household), _member_out(primary)


def get_household(session: Session, household_id: int, acting_customer_id: int) -> HouseholdOut:
    _require_acting_member(session, household_id, acting_customer_id)
    household = session.get(Household, household_id)
    assert household is not None  # _require_acting_member just proved it exists
    return _household_out(session, household)


def get_profile_household(session: Session, profile_id: int, acting_customer_id: int) -> ProfileHouseholdResponse:
    """The acting customer's own household, if any. A customer can only ask
    about themselves; no household is ever created implicitly."""
    if profile_id != acting_customer_id:
        raise AccessDeniedError("A customer can only view their own household.")
    _require_customer(session, profile_id)
    membership = _membership_of(session, profile_id)
    if membership is None:
        return ProfileHouseholdResponse(customer_id=profile_id, household=None, membership=None)
    return ProfileHouseholdResponse(
        customer_id=profile_id,
        household=_household_out(session, membership.household),
        membership=_member_out(membership),
    )


def list_members(session: Session, household_id: int, acting_customer_id: int) -> HouseholdMembersResponse:
    _require_acting_member(session, household_id, acting_customer_id)
    members = session.scalars(
        select(HouseholdMember)
        .where(HouseholdMember.household_id == household_id)
        .order_by((HouseholdMember.role != "primary"), HouseholdMember.id)
    ).all()
    return HouseholdMembersResponse(household_id=household_id, members=[_member_out(m) for m in members])


def add_member(
    session: Session, household_id: int, acting_customer_id: int, payload: HouseholdMemberCreateRequest
) -> HouseholdMemberOut:
    """Associates an existing customer with the household. Only the primary
    member may do this. The added customer stays an independent customer:
    membership never lets anyone view, switch into or change that
    customer's own data."""
    _require_primary(_require_acting_member(session, household_id, acting_customer_id))

    _require_customer(session, payload.customer_id)
    if payload.role == "primary":
        # Only `(self, primary)` reaches here (the schema rejects every other
        # primary combination): a second primary attempt.
        raise ConflictError("This household already has a primary member; a second primary cannot be created.")

    existing = _membership_of(session, payload.customer_id)
    if existing is not None:
        if existing.household_id == household_id:
            raise ConflictError("This customer is already a member of this household.")
        raise ConflictError("This customer already belongs to a household; a customer can belong to at most one.")

    member = HouseholdMember(
        household_id=household_id,
        customer_id=payload.customer_id,
        relationship_type=payload.relationship,
        role=payload.role,
        is_dependent=payload.role == "dependent",
    )
    with _conflict_on_integrity(session, "This customer already belongs to a household; a customer can belong to at most one."):
        session.add(member)
    return _member_out(member)


def remove_member(session: Session, household_id: int, acting_customer_id: int, member_id: int) -> None:
    """Removes one membership. The primary member can never be removed
    (Phase 32 has no ownership transfer), so a household can never be left
    without its primary."""
    _require_primary(_require_acting_member(session, household_id, acting_customer_id))

    member = session.get(HouseholdMember, member_id)
    if member is None or member.household_id != household_id:
        raise HouseholdMemberNotFoundError(f"No member with id={member_id} in household id={household_id}")
    if member.role == "primary":
        raise ConflictError("The primary member cannot be removed from a household.")

    session.delete(member)
    session.flush()
