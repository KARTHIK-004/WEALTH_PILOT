"""Duplicate and update handling (B2-H section 4.6; PROPOSED, not approved).

All state is causal: rows are processed in availability order (``available_at``, then batch stamp,
then the record sequence number). A row can be marked only by earlier rows, never by later ones.
Nothing is deleted: duplicates and updates stay as rows with explicit links, so a legitimate later
update is kept as a new version at its own availability time instead of being collapsed.

- same canonical URL earlier in the same batch           -> DUP_SAME_BATCH (lowest sequence wins)
- same normalised title, other URL, same batch           -> SYNDICATED_SAME_BATCH
- URL seen in an earlier batch, same (title_hash, words)  -> REOBSERVATION (reobservation_of = first ID)
- URL seen earlier, different signature                   -> UPDATE (update_of = first ID); a new version
- new URL, title_hash seen in the previous 72 h            -> SYNDICATED (story_id = first occurrence)
- empty or short title (title_hash None)                   -> never merged by title
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from wealthpilot.data.gdelt.timeutil import require_utc

SYNDICATION_WINDOW = timedelta(hours=72)


@dataclass(frozen=True)
class DedupInput:
    record_id: str
    batch_stamp: str
    seq: int
    available_at: datetime
    url_canonical: str
    title_hash: str | None
    word_count: str


@dataclass(frozen=True)
class DedupResult:
    record_id: str
    status: str                 # ORIGINAL, DUP_SAME_BATCH, SYNDICATED_SAME_BATCH, REOBSERVATION, UPDATE, SYNDICATED
    story_id: str
    reobservation_of: str | None = None
    update_of: str | None = None
    dup_of: str | None = None

    @property
    def new_story(self) -> bool:
        return self.status == "ORIGINAL"


def mark_same_batch(rows: Sequence[tuple[str, int, str, str | None]]) -> dict[str, str]:
    """Within one batch: ``(record_id, seq, url_canonical, title_hash)`` -> mechanical duplicate value."""
    out: dict[str, str] = {}
    seen_url: set[str] = set()
    seen_title: set[str] = set()
    for record_id, _seq, url, th in sorted(rows, key=lambda r: r[1]):
        if url in seen_url:
            out[record_id] = "DUP_SAME_BATCH"
        elif th is not None and th in seen_title:
            out[record_id] = "SYNDICATED_SAME_BATCH"
        else:
            out[record_id] = "ORIGINAL"
        seen_url.add(url)
        if th is not None:
            seen_title.add(th)
    return out


class StoryTracker:
    """Causal cross-batch story state. Feed rows in availability order with ``process``."""

    def __init__(self, window: timedelta = SYNDICATION_WINDOW) -> None:
        self.window = window
        self._url_first: dict[str, tuple[str, str, tuple[str | None, str]]] = {}  # url -> (first id, story, sig)
        self._title_first: dict[str, tuple[str, datetime]] = {}                   # hash -> (story id, first time)
        self._last_key: tuple[datetime, str, int] | None = None

    def process(self, row: DedupInput) -> DedupResult:
        at = require_utc(row.available_at, "available_at")
        key = (at, row.batch_stamp, row.seq)
        if self._last_key is not None and key < self._last_key:
            raise ValueError("rows must be processed in availability order (causal); got an earlier row")
        self._last_key = key
        sig = (row.title_hash, row.word_count)

        seen = self._url_first.get(row.url_canonical)
        if seen is not None:
            first_id, story, first_sig = seen
            first_batch = first_id.split("-", 1)[0]
            if first_batch == row.batch_stamp:
                return DedupResult(row.record_id, "DUP_SAME_BATCH", story, dup_of=first_id)
            if sig == first_sig:
                return DedupResult(row.record_id, "REOBSERVATION", story, reobservation_of=first_id)
            return DedupResult(row.record_id, "UPDATE", story, update_of=first_id)

        if row.title_hash is not None:
            prior = self._title_first.get(row.title_hash)
            if prior is not None and at - prior[1] <= self.window:
                story = prior[0]
                self._url_first[row.url_canonical] = (row.record_id, story, sig)
                status = "SYNDICATED_SAME_BATCH" if prior[0].split("-", 1)[0] == row.batch_stamp else "SYNDICATED"
                return DedupResult(row.record_id, status, story, dup_of=prior[0])
            self._title_first[row.title_hash] = (row.record_id, at)

        self._url_first[row.url_canonical] = (row.record_id, row.record_id, sig)
        return DedupResult(row.record_id, "ORIGINAL", row.record_id)


def deduplicate(rows: Iterable[DedupInput], window: timedelta = SYNDICATION_WINDOW) -> list[DedupResult]:
    ordered = sorted(rows, key=lambda r: (require_utc(r.available_at), r.batch_stamp, r.seq))
    tracker = StoryTracker(window)
    return [tracker.process(r) for r in ordered]
