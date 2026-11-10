"""The article-level schema for sentiment records (S2): strict, small and versioned. Offline; no model.

One record is one scored (or explicitly unscored) GDELT article. Validation fails closed: any problem is reported and nothing
is repaired or defaulted.

Rules that matter for point-in-time safety and honest missing data:

- ``available_at_utc`` is the verified batch availability time (existing ``availability.compute_availability``): at least one
  15-minute slot after the batch's nominal time. A record has no page-publication field, and one in a dict is rejected.
- ``availability_status`` is ``verified`` or ``unverified``. An unverified record has no availability time and can never enter
  a feature.
- Probabilities are finite, in [0, 1] and sum to 1 within ``PROB_SUM_TOLERANCE`` (1e-6, a float-rounding allowance only).
- ``pred_label`` is ``positive``, ``negative``, ``neutral`` or ``unavailable``. ``unavailable`` means the text could not be scored:
  its probabilities are all ``None``, never zeros and never a neutral vector. A scored label is an argmax of its vector.
- Text that is empty, too short or malformed (``text_status`` other than ``ok``) is never scored.
- A record from the deterministic fake scorer carries ``model_id = TEST_ONLY_FAKE_SCORER`` and is rejected unless the caller
  says it is in a test.
- Timestamps are whole seconds (the availability source is an HTTP date plus 15 minutes, so it has no sub-second part). A
  sub-second value is rejected, never rounded or truncated, so a round trip can never move a record across a cutoff.
- An ``unavailable`` record carries an explicit ``unavailable_reason`` (``text_*`` or ``scorer_failure``) consistent with
  ``text_status``, and no ``scored_at_utc``. A scored record has no reason and was scored at or after it became available.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import Any, Mapping

from wealthpilot.data.gdelt.errors import GdeltToolError, InvalidTimestampError
from wealthpilot.data.gdelt.timeutil import SLOT, parse_batch_stamp, require_utc

SCHEMA_VERSION = "s2_article_v2"
TEST_ONLY_MODEL_ID = "TEST_ONLY_FAKE_SCORER"
LABELS = ("positive", "negative", "neutral")
UNAVAILABLE = "unavailable"
UNAVAILABLE_REASONS = ("text_empty", "text_short", "text_malformed", "scorer_failure")
PROB_SUM_TOLERANCE = 1e-6
TEXT_STATUSES = ("ok", "empty", "short", "malformed")
AVAILABILITY_STATUSES = ("verified", "unverified")
DUP_STATUSES = ("ORIGINAL", "DUP_SAME_BATCH", "SYNDICATED_SAME_BATCH", "REOBSERVATION", "UPDATE", "SYNDICATED")   # dedup.py
THEMES = ("equity_us", "rates_us", "gold")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class SentimentSchemaError(GdeltToolError):
    code = "sentiment_schema_error"


@dataclass(frozen=True)
class ArticleRecord:
    article_id: str
    batch_ts: str
    available_at_utc: datetime | None
    availability_status: str
    source_domain: str
    title_sha256: str
    text_status: str
    theme_flags: Mapping[str, bool]
    story_id: str
    dup_status: str
    model_id: str
    model_revision: str
    p_positive: float | None
    p_negative: float | None
    p_neutral: float | None
    pred_label: str
    unavailable_reason: str | None
    scored_at_utc: datetime | None
    scorer_code_sha256: str
    schema_version: str = SCHEMA_VERSION


FIELD_NAMES = tuple(f.name for f in fields(ArticleRecord))


def title_sha256(title: str) -> str:
    """The SHA-256 of the exact title text (the input hash). The title itself is never stored in the record."""
    return hashlib.sha256(title.encode("utf-8")).hexdigest()


def classify_title(title: Any, *, min_chars: int) -> str:
    """``ok``, ``empty``, ``short`` or ``malformed``. ``min_chars`` is explicit (the candidate filter spec uses 20: it is not a
    setting chosen here). Control or format characters, or a lone surrogate, make a title malformed."""
    if not isinstance(title, str):
        return "malformed"
    if not isinstance(min_chars, int) or isinstance(min_chars, bool) or min_chars < 1:
        raise SentimentSchemaError("min_chars must be a positive integer")
    try:
        title.encode("utf-8")
    except UnicodeEncodeError:
        return "malformed"
    if any(unicodedata.category(ch)[0] == "C" and ch not in "\t" for ch in title):
        return "malformed"
    text = title.strip()
    if not text:
        return "empty"
    return "short" if len(text) < min_chars else "ok"


def _finite_prob(x: Any) -> bool:
    return isinstance(x, float) and not isinstance(x, bool) and math.isfinite(x) and 0.0 <= x <= 1.0


def problems(rec: ArticleRecord, *, allow_test_only: bool = False) -> list[str]:
    """Every problem with ``rec`` (empty means valid)."""
    out: list[str] = []
    available: datetime | None = None
    if not isinstance(rec, ArticleRecord):
        return ["not an ArticleRecord"]
    for name in ("article_id", "source_domain", "story_id", "model_id", "model_revision"):
        v = getattr(rec, name)
        if not (isinstance(v, str) and v.strip()):
            out.append(f"{name} is required")
    if rec.schema_version != SCHEMA_VERSION:
        out.append(f"schema_version must be {SCHEMA_VERSION}")
    try:
        nominal = parse_batch_stamp(rec.batch_ts)
    except InvalidTimestampError as exc:
        nominal = None
        out.append(f"batch_ts: {exc}")
    if rec.availability_status not in AVAILABILITY_STATUSES:
        out.append(f"availability_status must be one of {AVAILABILITY_STATUSES}")
    elif rec.availability_status == "verified":
        if rec.available_at_utc is None:
            out.append("a verified record needs available_at_utc")
        else:
            try:
                at = require_utc(rec.available_at_utc, "available_at_utc")
                available = at
                if at.microsecond:
                    out.append("available_at_utc must be whole seconds (a sub-second value could cross a cutoff)")
                if nominal is not None and at < nominal + SLOT:
                    out.append("available_at_utc is earlier than the batch time plus one slot (it was not derived from the "
                               "verified availability rule)")
            except InvalidTimestampError as exc:
                out.append(f"available_at_utc: {exc}")
    elif rec.available_at_utc is not None:
        out.append("an unverified record must not carry an availability time")
    for name in ("title_sha256", "scorer_code_sha256"):
        if not (isinstance(getattr(rec, name), str) and _SHA.match(getattr(rec, name))):
            out.append(f"{name} must be a SHA-256")
    if rec.text_status not in TEXT_STATUSES:
        out.append(f"text_status must be one of {TEXT_STATUSES}")
    if rec.dup_status not in DUP_STATUSES:
        out.append(f"dup_status must be one of {DUP_STATUSES}")
    flags = rec.theme_flags
    if not isinstance(flags, Mapping) or set(flags) != set(THEMES) or any(not isinstance(v, bool) for v in flags.values()):
        out.append(f"theme_flags must be exactly {THEMES}, each true or false")
    if rec.model_id == TEST_ONLY_MODEL_ID and not allow_test_only:
        out.append("a record from the test-only fake scorer is not allowed here")
    probs = (rec.p_positive, rec.p_negative, rec.p_neutral)
    if rec.pred_label == UNAVAILABLE:
        if any(p is not None for p in probs):
            out.append("an unavailable prediction must have no probabilities (never zeros or a neutral vector)")
        if rec.scored_at_utc is not None:
            out.append("an unavailable prediction was not scored: scored_at_utc must be null")
        if rec.unavailable_reason not in UNAVAILABLE_REASONS:
            out.append(f"an unavailable prediction needs unavailable_reason, one of {UNAVAILABLE_REASONS}")
        elif rec.text_status in TEXT_STATUSES:
            want = "scorer_failure" if rec.text_status == "ok" else f"text_{rec.text_status}"
            if rec.unavailable_reason != want:
                out.append(f"unavailable_reason {rec.unavailable_reason!r} contradicts text_status {rec.text_status!r}")
    elif rec.pred_label in LABELS:
        if rec.unavailable_reason is not None:
            out.append("a scored record must not carry an unavailable_reason")
        if rec.text_status != "ok":
            out.append("text that is not ok must not be scored")
        if not all(_finite_prob(p) for p in probs):
            out.append("probabilities must be finite floats in [0, 1]")
        else:
            if abs(sum(probs) - 1.0) > PROB_SUM_TOLERANCE:       # type: ignore[arg-type]
                out.append(f"probabilities must sum to 1 within {PROB_SUM_TOLERANCE} (got {sum(probs)!r})")  # type: ignore[arg-type]
            top = max(probs)                                       # type: ignore[type-var]
            if probs[LABELS.index(rec.pred_label)] < top:         # type: ignore[operator]
                out.append("pred_label is not an argmax of the probability vector")
        if rec.scored_at_utc is None:
            out.append("a scored record needs scored_at_utc")
    else:
        out.append(f"pred_label must be one of {LABELS + (UNAVAILABLE,)}")
        return out
    if rec.scored_at_utc is not None:
        try:
            scored = require_utc(rec.scored_at_utc, "scored_at_utc")
            if scored.microsecond:
                out.append("scored_at_utc must be whole seconds")
            if available is not None and scored < available:
                out.append("scored_at_utc is earlier than available_at_utc: a record cannot be scored before it was available")
        except InvalidTimestampError as exc:
            out.append(f"scored_at_utc: {exc}")
    return out


def validate(rec: ArticleRecord, *, allow_test_only: bool = False) -> ArticleRecord:
    errs = problems(rec, allow_test_only=allow_test_only)
    if errs:
        raise SentimentSchemaError("invalid article record: " + "; ".join(errs[:4]))
    return rec


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    utc = require_utc(value)
    if utc.microsecond:       # never truncate: a truncated time could sit on the other side of a cutoff
        raise SentimentSchemaError(f"timestamp {utc.isoformat()} is not whole seconds and cannot be serialised")
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_dict(rec: ArticleRecord) -> dict[str, Any]:
    d = {f: getattr(rec, f) for f in FIELD_NAMES}
    d["available_at_utc"], d["scored_at_utc"] = _iso(rec.available_at_utc), _iso(rec.scored_at_utc)
    d["theme_flags"] = dict(rec.theme_flags)
    return d


def from_dict(d: Mapping[str, Any], *, allow_test_only: bool = False) -> ArticleRecord:
    """Parse a stored record. Unknown fields (for example a page publication time) and missing fields are errors."""
    if not isinstance(d, Mapping):
        raise SentimentSchemaError("the record is not an object")
    extra, missing = sorted(set(d) - set(FIELD_NAMES)), sorted(set(FIELD_NAMES) - set(d))
    if extra or missing:
        raise SentimentSchemaError(f"fields differ from the schema (missing {missing}, unexpected {extra}); a page "
                                   "publication time is never an input")
    parsed = dict(d)
    for name in ("available_at_utc", "scored_at_utc"):
        v = parsed[name]
        if v is None:
            continue
        if not (isinstance(v, str) and _TS.match(v)):
            raise SentimentSchemaError(f"{name} must be a UTC timestamp YYYY-MM-DDTHH:MM:SSZ or null")
        parsed[name] = datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return validate(ArticleRecord(**parsed), allow_test_only=allow_test_only)
