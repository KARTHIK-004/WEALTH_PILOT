"""The candidate → scored-record contract (owner decisions E3a/E3b/E3c, OD-11a, scoring input = title only). Pure and offline: no model, file or network access.

What is scored (E3a): a candidate whose ``text_status`` is ``ok`` AND that carries at least one theme flag. Same-batch duplicates are included (the counting unit is decided at aggregation).
What is converted (E3b): every theme-flagged candidate becomes an ``ArticleRecord``: a scored one when it was scored, an ``unavailable`` one with its existing ``text_*`` reason when its text
is empty, short or malformed (it is never sent to a scorer), or ``unavailable`` / ``scorer_failure`` when the scorer failed. A candidate with **no** theme flag is **not** converted: it
stays a candidate and is reported as ``not_theme_relevant``.
Fields (E3c, OD-11a): ``dup_status`` is the candidate's same-batch status, the only relation the day files carry (no ``dedup.py`` pass, so no cross-batch status). ``story_id`` is
``UNLINKED:<article_id>``: a deterministic, record-specific value that is **not a story-identity claim**; no records are linked, so exact-URL and title-hash repeats stay diagnostics
(``RepeatedContent``) only. The scoring input is the validated title (``CandidateRecord.title``); no body is fetched.
Source availability (``available_at_utc``, the verified batch availability) is carried as is; there is no page-publication field.

Everything fails closed: an inconsistent text status or title hash, a missing or unexpected outcome, or an invalid record raises rather than being repaired.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.dayfile_adapter import CandidateRecord
from wealthpilot.data.gdelt.sentiment.schema import (
    SCHEMA_VERSION, UNAVAILABLE, ArticleRecord, classify_title, title_sha256, validate,
)
from wealthpilot.data.gdelt.sentiment.scorer_port import ScoreOutcome, ScorerIdentity
from wealthpilot.data.gdelt.timeutil import require_utc

STORY_ID_PREFIX = "UNLINKED:"            # "unlinked record; not a story-identity claim"
NOT_THEME_RELEVANT = "not_theme_relevant"


class ConversionError(GdeltToolError):
    code = "sentiment_conversion_error"


@dataclass(frozen=True)
class NotConverted:
    article_id: str
    reason: str                          # NOT_THEME_RELEVANT


@dataclass(frozen=True)
class ConversionResult:
    records: tuple[ArticleRecord, ...]
    not_converted: tuple[NotConverted, ...]


def unlinked_story_id(article_id: str) -> str:
    return f"{STORY_ID_PREFIX}{article_id}"


def has_theme(c: CandidateRecord) -> bool:
    return any(c.theme_flags.values())


def scoring_inputs(candidates: Sequence[CandidateRecord], *, min_chars: int) -> tuple[CandidateRecord, ...]:
    """E3a: the candidates to send to a scorer: ``text_status == ok`` and at least one theme flag (duplicates included), in input order."""
    out = []
    for c in candidates:
        status = classify_title(c.title, min_chars=min_chars)
        if status != c.text_status:
            raise ConversionError(f"{c.article_id}: text_status {c.text_status!r} contradicts the title classification {status!r}")
        if has_theme(c) and status == "ok":
            out.append(c)
    return tuple(out)


def convert(candidates: Sequence[CandidateRecord], outcomes: Sequence[ScoreOutcome], identity: ScorerIdentity, *, scored_at: datetime,
            min_chars: int) -> ConversionResult:
    """Build ``ArticleRecord`` objects for the theme-flagged candidates, in input order. ``outcomes`` must cover exactly ``scoring_inputs(candidates)``."""
    scored_at = require_utc(scored_at, "scored_at")
    wanted = {c.article_id for c in scoring_inputs(candidates, min_chars=min_chars)}
    by_id: dict[str, ScoreOutcome] = {}
    for o in outcomes:
        if o.candidate_id in by_id:
            raise ConversionError(f"{o.candidate_id}: duplicate score outcome")
        by_id[o.candidate_id] = o
    if set(by_id) != wanted:
        missing, extra = sorted(wanted - set(by_id)), sorted(set(by_id) - wanted)
        raise ConversionError(f"outcomes must cover exactly the scoring inputs (missing {len(missing)}, unexpected {len(extra)})")
    if len({c.article_id for c in candidates}) != len(candidates):
        raise ConversionError("candidate ids must be unique")
    records: list[ArticleRecord] = []
    skipped: list[NotConverted] = []
    for c in candidates:
        if not has_theme(c):
            skipped.append(NotConverted(c.article_id, NOT_THEME_RELEVANT))
            continue
        digest = title_sha256(c.title)
        if digest != c.title_sha256_raw:
            raise ConversionError(f"{c.article_id}: the title does not match its recorded hash")
        if c.text_status == "ok":
            o = by_id[c.article_id]
            label, probs, reason = o.label, o.probabilities or (None, None, None), o.unavailable_reason
        else:
            label, probs, reason = UNAVAILABLE, (None, None, None), f"text_{c.text_status}"        # never reaches a scorer
        records.append(validate(ArticleRecord(
            article_id=c.article_id, batch_ts=c.batch_ts, available_at_utc=c.available_at_utc, availability_status=c.availability_status,
            source_domain=c.source_domain, title_sha256=digest, text_status=c.text_status, theme_flags=dict(c.theme_flags),
            story_id=unlinked_story_id(c.article_id), dup_status=c.same_batch_status, model_id=identity.model_id,
            model_revision=identity.model_revision, p_positive=probs[0], p_negative=probs[1], p_neutral=probs[2], pred_label=label,
            unavailable_reason=reason, scored_at_utc=None if label == UNAVAILABLE else scored_at,
            scorer_code_sha256=identity.scorer_code_sha256, schema_version=SCHEMA_VERSION)))
    return ConversionResult(tuple(records), tuple(skipped))
