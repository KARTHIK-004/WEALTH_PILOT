"""The scorer interface (a port) for the sentiment pipeline. Pure Python: it imports no ML library and makes no network call.

No model is approved (policy ``scorer_approval_and_polarity_validation`` is ``UNRESOLVED_NOT_APPLIED``), so nothing in this repository implements the port for a real
model. This module fixes the contract a future, separately approved local scorer must satisfy, and refuses to run until the policy says it is applied:

- ``score_candidates`` first calls ``require_policies_applied`` for that policy (it raises ``PolicyBlockedError`` today) and refuses the test-only fake identity;
- text that the existing classifier calls empty, short or malformed is **never sent to the scorer**; it becomes an explicit ``unavailable`` outcome;
- raw scorer output is validated strictly (exactly the declared labels, finite probabilities in [0, 1] that sum to 1 within the schema tolerance, one result per text);
  anything else, and any scorer exception, becomes ``scorer_failure``. There is **no fallback to neutral**, to zero or to a previous value;
- the label mapping from the model's labels to ``positive`` / ``negative`` / ``neutral`` is explicit and must be a bijection; the predicted label is the schema's argmax (first label wins a tie);
- outcomes are returned in input order, deterministically. They are ``ScoreOutcome`` values, **not** ``ArticleRecord`` objects: turning a candidate into a scored record also needs the
  unapproved eligibility, counting-unit and ``story_id`` rules (E3, OD-11), so that step is deliberately not implemented here.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.dayfile_adapter import CandidateRecord
from wealthpilot.data.gdelt.sentiment.policy import PolicyState, require_policies_applied
from wealthpilot.data.gdelt.sentiment.schema import LABELS, PROB_SUM_TOLERANCE, TEST_ONLY_MODEL_ID, UNAVAILABLE, classify_title

SCORER_POLICY = "scorer_approval_and_polarity_validation"
_SHA = re.compile(r"^[0-9a-f]{64}$")


class ScorerPortError(GdeltToolError):
    code = "sentiment_scorer_port_error"


class ScorerOutputError(GdeltToolError):
    code = "sentiment_scorer_output_invalid"


@dataclass(frozen=True)
class ScorerIdentity:
    """Who produced a score. Every field is required so a result can always be traced to an exact model and code version."""

    model_id: str
    model_revision: str
    weights_sha256: str
    scorer_code_sha256: str
    label_map: Mapping[str, str]            # the model's own label -> positive | negative | neutral (a bijection)

    def __post_init__(self) -> None:
        for name in ("model_id", "model_revision"):
            if not (isinstance(getattr(self, name), str) and getattr(self, name).strip()):
                raise ScorerPortError(f"{name} is required")
        for name in ("weights_sha256", "scorer_code_sha256"):
            if not (isinstance(getattr(self, name), str) and _SHA.match(getattr(self, name))):
                raise ScorerPortError(f"{name} must be a lowercase SHA-256 hex digest")
        if self.model_id == TEST_ONLY_MODEL_ID:
            raise ScorerPortError("the test-only fake scorer identity is not a production scorer")
        targets = list(self.label_map.values())
        if sorted(targets) != sorted(LABELS) or len(set(self.label_map)) != len(LABELS):
            raise ScorerPortError(f"label_map must map exactly three model labels one-to-one onto {LABELS}")


@runtime_checkable
class ScorerPort(Protocol):
    """A local scorer. ``score_batch`` returns, for each text in order, a mapping of the model's labels to probabilities, or ``None`` when the model failed for that text."""

    identity: ScorerIdentity

    def score_batch(self, texts: Sequence[str]) -> Sequence[Mapping[str, float] | None]: ...


@dataclass(frozen=True)
class ScoreOutcome:
    candidate_id: str
    label: str                                           # positive | negative | neutral | unavailable
    probabilities: tuple[float, float, float] | None     # (positive, negative, neutral); None whenever the label is unavailable
    unavailable_reason: str | None                       # text_empty | text_short | text_malformed | scorer_failure


def validate_raw_scores(raw: object, identity: ScorerIdentity) -> tuple[float, float, float]:
    """Check one raw result and return its probabilities in schema label order. Raises ``ScorerOutputError`` on anything unexpected."""
    if not isinstance(raw, Mapping):
        raise ScorerOutputError("a result must be a mapping of label to probability")
    if set(raw) != set(identity.label_map):
        raise ScorerOutputError(f"labels {sorted(map(str, raw))} differ from the declared {sorted(identity.label_map)}")
    by_schema: dict[str, float] = {}
    for model_label, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ScorerOutputError(f"probability for {model_label!r} must be a finite number in [0, 1]")
        by_schema[identity.label_map[model_label]] = float(value)
    probs = tuple(by_schema[label] for label in LABELS)
    if abs(sum(probs) - 1.0) > PROB_SUM_TOLERANCE:
        raise ScorerOutputError(f"probabilities must sum to 1 within {PROB_SUM_TOLERANCE} (got {sum(probs)!r})")
    return probs                                         # type: ignore[return-value]


def _failure(candidate_id: str, reason: str) -> ScoreOutcome:
    return ScoreOutcome(candidate_id, UNAVAILABLE, None, reason)


def score_candidates(candidates: Sequence[CandidateRecord], scorer: ScorerPort, *, policy: PolicyState, min_chars: int,
                     batch_size: int = 64) -> tuple[ScoreOutcome, ...]:
    """Score candidate titles with an approved local scorer; returns one outcome per candidate, in order. Refuses while the scorer policy is unapplied."""
    require_policies_applied(policy, (SCORER_POLICY,))
    if not isinstance(scorer, ScorerPort) or not isinstance(scorer.identity, ScorerIdentity):
        raise ScorerPortError("scorer must implement ScorerPort with a ScorerIdentity")
    if not (isinstance(batch_size, int) and not isinstance(batch_size, bool) and batch_size >= 1):
        raise ScorerPortError("batch_size must be an integer >= 1")
    if not (isinstance(min_chars, int) and not isinstance(min_chars, bool) and min_chars >= 1):
        raise ScorerPortError("min_chars must be an integer >= 1 (the caller states the text rule; there is no default)")
    ids = [c.article_id for c in candidates]
    if len(set(ids)) != len(ids):
        raise ScorerPortError("candidate ids must be unique: a duplicate would make outcomes ambiguous")
    outcomes: dict[str, ScoreOutcome] = {}
    todo: list[CandidateRecord] = []
    for c in candidates:
        status = classify_title(c.title, min_chars=min_chars)
        if status == "ok":
            todo.append(c)
        else:
            outcomes[c.article_id] = _failure(c.article_id, f"text_{status}")          # never sent to the scorer
    for start in range(0, len(todo), batch_size):
        batch = todo[start:start + batch_size]
        try:
            raw = list(scorer.score_batch([c.title for c in batch]))
        except Exception:                                                             # noqa: BLE001 - any scorer error is an explicit failure, never a value
            raw = [None] * len(batch)
        if len(raw) != len(batch):
            raw = [None] * len(batch)                                                 # a wrong-length answer cannot be aligned to its texts
        for c, r in zip(batch, raw):
            try:
                probs = validate_raw_scores(r, scorer.identity)
            except ScorerOutputError:
                outcomes[c.article_id] = _failure(c.article_id, "scorer_failure")
                continue
            label = LABELS[max(range(3), key=lambda i: (probs[i], -i))]                # the schema's argmax: the first label wins a tie
            outcomes[c.article_id] = ScoreOutcome(c.article_id, label, probs, None)
    return tuple(outcomes[i] for i in ids)
