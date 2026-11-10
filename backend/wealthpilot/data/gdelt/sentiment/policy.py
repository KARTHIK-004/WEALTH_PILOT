"""Policy state for the sentiment research pipeline (S2.8B): immutable, and a fail-closed guard for downstream use. Pure and offline.

A research policy is **usable downstream only when its status says it is applied**: ``APPLIED_APPROVED`` or ``APPLIED_PROVISIONAL``
(applied in code and selected by the owner, the latter explicitly provisional and still carried as such). Every other status blocks:
``UNRESOLVED_NOT_APPLIED`` (no decision), ``SELECTED_NOT_APPLIED`` / ``SELECTED_PROVISIONAL_NOT_APPLIED`` (the owner chose, but the
code does not apply it yet), ``SELECTED_APPLIED_LOOKBACK_UNDECIDED`` (applied, but a parameter it needs is still undecided),
``CALLER_SUPPLIED_NOT_APPROVED``, ``MINIMUM_POINT_IN_TIME_ONLY``, ``NOT_IMPLEMENTED``.

``PolicyState`` is a frozen snapshot: ``from_mapping`` copies the input, so changing the original mapping afterwards cannot change
the state, and a plain mapping is never accepted by the guard (it could be changed between the check and the use).

Limits, stated plainly: the guard prevents accidental use of unresolved policies. It cannot prove that an ``APPLIED_*`` status is
genuine: whoever builds a ``PolicyState`` attests to it. Nothing in the production code builds an applied state; only tests do, and
they say so.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from wealthpilot.data.gdelt.errors import GdeltToolError

APPLIED_APPROVED = "APPLIED_APPROVED"
APPLIED_PROVISIONAL = "APPLIED_PROVISIONAL"
USABLE_STATUSES = (APPLIED_APPROVED, APPLIED_PROVISIONAL)
REQUIRED_POLICIES = (
    "deduplication_and_story_updates",
    "cross_interval_story_uniqueness",
    "source_coverage_threshold",
    "scoring_coverage_threshold",
    "scorer_approval_and_polarity_validation",        # a scoring result stays unusable until a scorer and its validation are approved
    "near_empty_slot_handling",
    "holiday_and_early_close_calendars",
    "late_batch_strictness",
)


class PolicyBlockedError(GdeltToolError):
    code = "sentiment_policy_blocked"


@dataclass(frozen=True)
class PolicyState:
    """An immutable, sorted snapshot of policy name -> status."""

    items: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or not all(
                isinstance(p, tuple) and len(p) == 2 and all(isinstance(x, str) and x for x in p) for p in self.items):
            raise PolicyBlockedError("items must be a tuple of (name, status) string pairs")
        names = [n for n, _ in self.items]
        if names != sorted(set(names)):
            raise PolicyBlockedError("policy names must be unique and sorted")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> "PolicyState":
        if not isinstance(mapping, Mapping):
            raise PolicyBlockedError("a policy state is built from a mapping of name to status")
        return cls(tuple(sorted((str(k), str(v)) for k, v in mapping.items())))

    def as_mapping(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.items))

    def status(self, name: str) -> str | None:
        return dict(self.items).get(name)

    def unresolved(self, required: tuple[str, ...] = REQUIRED_POLICIES) -> tuple[tuple[str, str | None], ...]:
        known = dict(self.items)
        return tuple((n, known.get(n)) for n in required if known.get(n) not in USABLE_STATUSES)

    def provisional(self) -> tuple[str, ...]:
        return tuple(n for n, s in self.items if s == APPLIED_PROVISIONAL)


def require_policies_applied(state: PolicyState, required: tuple[str, ...] = REQUIRED_POLICIES) -> PolicyState:
    """Raise ``PolicyBlockedError`` unless every required policy is applied. Returns the state (so provisional items stay visible)."""
    if not isinstance(state, PolicyState):
        raise PolicyBlockedError("a PolicyState is required (a plain mapping is refused: it could change after the check)")
    missing = state.unresolved(required)
    if missing:
        shown = ", ".join(f"{n}={s}" for n, s in missing)
        raise PolicyBlockedError(f"{len(missing)} required policy decision(s) are not applied: {shown}")
    return state
