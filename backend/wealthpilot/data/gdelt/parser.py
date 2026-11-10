"""Incremental GKG 2.1 row parser.

Reads the zip member in 1 MiB chunks, splits on LF, decodes each row as strict UTF-8 on its own, and
checks row validity (B2-H section 4.1). Memory stays bounded by the chunk size plus the longest row
allowed (``max_line_bytes``); a longer row is skipped to the next LF and counted. Rows are yielded
as they are read, but callers must not keep anything until the iterator finishes: the zip CRC-32 is
only confirmed at the end of the member, and a failure raises ``IntegrityError``.
"""

from __future__ import annotations

import html
import re
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import IO

from wealthpilot.data.gdelt.errors import IntegrityError

CHUNK = 1024 * 1024
N_FIELDS = 27
# GKG 2.1 column positions (codebook order, verified in B2-G)
C_ID, C_DATE, C_COLLECTION, C_SOURCE, C_URL = 0, 1, 2, 3, 4
C_V1THEMES, C_V2THEMES, C_V1LOCATIONS, C_V1ORGS, C_TONE = 7, 8, 9, 13, 15
C_TRANSLATION, C_EXTRAS = 25, 26

_TITLE_RE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)
_PUBTS_RE = re.compile(r"<PAGE_PRECISEPUBTIMESTAMP>(\d{14})</PAGE_PRECISEPUBTIMESTAMP>")


@dataclass
class RowCounts:
    physical_lines: int = 0
    empty_lines: int = 0
    crlf_lines: int = 0
    oversize_lines: int = 0
    decode_errors: int = 0
    field_count_errors: int = 0
    date_mismatch: int = 0
    translated: int = 0
    non_web: int = 0
    english_valid: int = 0
    missing_final_newline: bool = False

    @property
    def malformed(self) -> int:
        return self.oversize_lines + self.decode_errors + self.field_count_errors


@dataclass(frozen=True)
class GkgRow:
    record_id: str
    seq: int
    batch_stamp: str
    source_domain: str
    document_url: str
    v1_themes: str
    v2_themes: str
    v1_locations: str
    v1_orgs: str
    tone: str
    title: str                       # HTML-decoded; "" if absent
    page_pub_ts: str | None          # diagnostic only; never used for availability


@dataclass
class _LineSplitter:
    max_line_bytes: int
    counts: RowCounts
    _buf: bytearray = field(default_factory=bytearray)
    _skipping: bool = False

    def feed(self, chunk: bytes) -> Iterator[bytes]:
        start = 0
        while True:
            nl = chunk.find(b"\n", start)
            if nl < 0:
                piece = chunk[start:]
                if not self._skipping:
                    self._buf += piece
                    if len(self._buf) > self.max_line_bytes:
                        self._buf.clear()
                        self._skipping = True
                return
            piece = chunk[start:nl]
            start = nl + 1
            if self._skipping:
                self._skipping = False
                self.counts.physical_lines += 1
                self.counts.oversize_lines += 1
                continue
            if len(self._buf) + len(piece) > self.max_line_bytes:
                self._buf.clear()
                self.counts.physical_lines += 1
                self.counts.oversize_lines += 1
                continue
            self._buf += piece
            line = bytes(self._buf)
            self._buf.clear()
            yield line

    def finish(self) -> Iterator[bytes]:
        if self._skipping:
            self._skipping = False
            self.counts.physical_lines += 1
            self.counts.oversize_lines += 1
            self.counts.missing_final_newline = True
        elif self._buf:
            self.counts.missing_final_newline = True
            line = bytes(self._buf)
            self._buf.clear()
            yield line


def _parse_line(raw: bytes, stamp: str, counts: RowCounts) -> GkgRow | None:
    counts.physical_lines += 1
    if raw.endswith(b"\r"):
        counts.crlf_lines += 1
        raw = raw[:-1]
    if not raw:
        counts.empty_lines += 1
        return None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        counts.decode_errors += 1
        return None
    cols = text.split("\t")
    if len(cols) != N_FIELDS:
        counts.field_count_errors += 1
        return None
    record_id = cols[C_ID]
    prefix, _, suffix = record_id.partition("-")
    if cols[C_DATE] != stamp or prefix != stamp:
        counts.date_mismatch += 1
        return None
    if cols[C_TRANSLATION] != "" or not suffix.isdigit():
        counts.translated += 1
        return None
    if cols[C_COLLECTION] != "1":
        counts.non_web += 1
        return None
    counts.english_valid += 1
    extras = cols[C_EXTRAS]
    m = _TITLE_RE.search(extras)
    title = html.unescape(m.group(1)).strip() if m else ""
    p = _PUBTS_RE.search(extras)
    return GkgRow(record_id, int(suffix), stamp, cols[C_SOURCE], cols[C_URL], cols[C_V1THEMES], cols[C_V2THEMES],
                  cols[C_V1LOCATIONS], cols[C_V1ORGS], cols[C_TONE], title, p.group(1) if p else None)


def iter_rows(stream: IO[bytes], stamp: str, counts: RowCounts, *, max_line_bytes: int,
              max_uncompressed: int) -> Iterator[GkgRow]:
    """Yield valid English rows from a binary member stream; count every rejected line by reason."""
    splitter = _LineSplitter(max_line_bytes, counts)
    read_total = 0
    try:
        while True:
            chunk = stream.read(CHUNK)
            if not chunk:
                break
            read_total += len(chunk)
            if read_total > max_uncompressed:
                raise IntegrityError(f"member exceeded {max_uncompressed} B while reading", status="size_guard_exceeded")
            for line in splitter.feed(chunk):
                row = _parse_line(line, stamp, counts)
                if row is not None:
                    yield row
    except (zipfile.BadZipFile, zlib.error) as exc:  # CRC-32 mismatch at end of member, or corrupt data
        raise IntegrityError(f"zip CRC or data error: {exc}", status="crc_failed") from exc
    except (EOFError, OSError, ValueError) as exc:
        raise IntegrityError(f"zip member unreadable: {exc}", status="zip_invalid") from exc
    for line in splitter.finish():
        row = _parse_line(line, stamp, counts)
        if row is not None:
            yield row
