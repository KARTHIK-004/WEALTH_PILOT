"""A deterministic TEST-ONLY fake scorer (S2). It is NOT a sentiment model and must never be used on real articles.

It turns the SHA-256 of a title into a valid probability vector. The numbers carry no information about the text: they exist
so the schema, aggregation and point-in-time logic can be tested with reproducible, valid inputs. Nothing here "reads" a headline
for tone, and no rule here is a stand-in for sentiment.

Safeguards:

- ``model_id`` is ``TEST_ONLY_FAKE_SCORER`` and every record it makes says so; the schema and the aggregator reject such a
  record unless the caller passes ``allow_test_only=True``.
- It accepts only ``SyntheticArticle`` objects, and a synthetic article must have an ``article_id`` starting ``SYN-`` and a source
  domain ending ``.invalid`` or ``.test``: real GDELT identifiers and domains are refused.
- It is not exported from the ``sentiment`` package and is not registered anywhere.
- It fails closed outside a test run: constructing the scorer raises ``FakeScorerUseError`` unless ``pytest`` is loaded, so
  production code that imports it by accident cannot score anything with it.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.schema import (
    LABELS, SCHEMA_VERSION, TEST_ONLY_MODEL_ID, UNAVAILABLE, ArticleRecord, classify_title, title_sha256, validate,
)
from wealthpilot.data.gdelt.timeutil import require_utc

MODEL_REVISION = "fake-v1"
__test__ = False                      # not a pytest test module even though it is used by tests


class NotSyntheticError(GdeltToolError):
    code = "sentiment_not_synthetic"


class FakeScorerUseError(GdeltToolError):
    code = "sentiment_fake_scorer_outside_tests"


@dataclass(frozen=True)
class SyntheticArticle:
    """A made-up article. Real identifiers and domains are refused by the scorer."""

    article_id: str
    batch_ts: str
    available_at_utc: datetime | None
    availability_status: str
    source_domain: str
    title: str
    theme_flags: Mapping[str, bool]
    story_id: str
    dup_status: str = "ORIGINAL"


def scorer_code_sha256() -> str:
    """The SHA-256 of this module's source: the ``scorer_code_sha256`` its records carry."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _vector(title: str) -> tuple[float, float, float]:
    """Three positive weights from the title's SHA-256, normalised. Deterministic; carries no sentiment."""
    raw = hashlib.sha256(title.encode("utf-8")).digest()
    w = [raw[i] + 1 for i in range(3)]                                  # 1..256
    total = float(sum(w))
    return w[0] / total, w[1] / total, w[2] / total


class FakeScorerTestOnly:
    """Deterministic fake scorer. ``TEST_ONLY`` is true and is part of every record it produces."""

    TEST_ONLY = True
    model_id = TEST_ONLY_MODEL_ID
    model_revision = MODEL_REVISION

    def __init__(self, *, min_chars: int) -> None:
        if "pytest" not in sys.modules:
            raise FakeScorerUseError("the fake scorer is test-only and refuses to run outside a test session")
        self.min_chars = min_chars

    @staticmethod
    def _check_synthetic(a: SyntheticArticle) -> None:
        if not isinstance(a, SyntheticArticle):
            raise NotSyntheticError("the fake scorer accepts only SyntheticArticle objects")
        if not a.article_id.startswith("SYN-") or not a.source_domain.endswith((".invalid", ".test")):
            raise NotSyntheticError("the fake scorer refuses anything that is not marked synthetic "
                                    "(article_id 'SYN-...' and a '.invalid' or '.test' domain)")

    def score(self, article: SyntheticArticle, *, scored_at: datetime) -> ArticleRecord:
        self._check_synthetic(article)
        scored_at = require_utc(scored_at, "scored_at")
        status = classify_title(article.title, min_chars=self.min_chars)
        reason: str | None = None
        if status == "ok":
            p = _vector(article.title)
            label = LABELS[max(range(3), key=lambda i: (p[i], -i))]            # argmax; the first label wins a tie
            probs: tuple[float | None, float | None, float | None] = p
        else:
            label, probs, reason = UNAVAILABLE, (None, None, None), f"text_{status}"   # unscorable text: no vector at all
        return validate(ArticleRecord(
            article_id=article.article_id, batch_ts=article.batch_ts, available_at_utc=article.available_at_utc,
            availability_status=article.availability_status, source_domain=article.source_domain,
            title_sha256=title_sha256(article.title), text_status=status, theme_flags=dict(article.theme_flags),
            story_id=article.story_id, dup_status=article.dup_status, model_id=self.model_id, model_revision=self.model_revision,
            p_positive=probs[0], p_negative=probs[1], p_neutral=probs[2], pred_label=label, unavailable_reason=reason,
            scored_at_utc=scored_at if label != UNAVAILABLE else None, scorer_code_sha256=scorer_code_sha256(),
            schema_version=SCHEMA_VERSION), allow_test_only=True)

