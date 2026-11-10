"""Shards and atomic daily output (deterministic gzip TSV, standard library only).

Per slot: kept rows (``captured``) and audit rows (``audit``) go to one shard,
``tmp/<day>/<stamp>.tsv.gz``, written to a ``.partial`` file, fsynced, renamed, and hashed.
Per UTC day: shards are concatenated in batch order into ``filtered/<filter_version>/YYYY/YYYY-MM-DD.tsv.gz``
and ``audit_sample/<filter_version>/YYYY/YYYY-MM-DD.tsv.gz`` the same way, then re-read and hashed.
gzip uses mtime 0 and no file name, so identical input gives byte-identical output.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

COLUMNS = (
    "row_kind", "gkg_record_id", "batch_ts", "available_at_utc", "source_domain", "document_url", "url_canonical",
    "page_title", "title_hash", "page_pub_ts_utc", "tone", "positive", "negative", "polarity", "activity_density",
    "self_group_density", "word_count", "candidate_themes", "econ_themes", "country_codes", "us_location",
    "us_relevant", "us_market_orgs", "title_hits", "company_item", "flag_themes", "member_equity_us",
    "member_rates_us", "member_gold", "s1_equity_us", "s1_rates_us", "s1_gold", "s2_equity_us", "s2_rates_us",
    "s2_gold", "mech_dup", "near_miss_cue", "filter_version", "parser_version",
)


@dataclass(frozen=True)
class Layout:
    root: Path
    filter_version: str

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest" / "manifest.sqlite"

    @property
    def tmp(self) -> Path:
        return self.root / "tmp"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def raw_keep(self) -> Path:
        return self.root / "raw"

    def shard_path(self, day: str, stamp: str) -> Path:
        return self.tmp / day / f"{stamp}.tsv.gz"

    def day_path(self, day: str) -> Path:
        return self.root / "filtered" / self.filter_version / day[:4] / f"{day}.tsv.gz"

    def audit_path(self, day: str) -> Path:
        return self.root / "audit_sample" / self.filter_version / day[:4] / f"{day}.tsv.gz"


def _clean(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def encode_rows(rows: Iterable[Sequence[object]], header: bool = False) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, escapechar="\\")
    if header:
        writer.writerow(COLUMNS)
    for row in rows:
        if len(row) != len(COLUMNS):
            raise ValueError(f"row has {len(row)} values, expected {len(COLUMNS)}")
        writer.writerow([_clean(v) for v in row])
    return buf.getvalue().encode("utf-8")


def _gzip(data: bytes) -> bytes:
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0, compresslevel=6) as gz:
        gz.write(data)
    return out.getvalue()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, data: bytes, *, fail_before_replace: bool = False) -> str:
    """Write ``data`` via ``<name>.partial`` + fsync + ``os.replace``; return the SHA-256 re-read from disk.

    ``fail_before_replace`` exists only so tests can simulate a crash at that point.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    with open(partial, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if fail_before_replace:
        raise OSError("simulated crash before os.replace")
    os.replace(partial, path)
    digest = sha256_file(path)
    if digest != hashlib.sha256(data).hexdigest():
        raise OSError(f"re-read hash mismatch for {path}")
    return digest


def write_shard(path: Path, rows: Sequence[Sequence[object]]) -> str:
    return atomic_write(path, _gzip(encode_rows(rows)))


def read_shard_rows(path: Path) -> list[list[str]]:
    text = gzip.decompress(path.read_bytes()).decode("utf-8")
    reader = csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
    return [r for r in reader if r]


@dataclass(frozen=True)
class DayFiles:
    rows_kept: int
    audit_rows: int
    file_path: Path
    file_sha256: str
    file_bytes: int
    audit_path: Path
    audit_sha256: str


def write_day(layout: Layout, day: str, shard_paths: Sequence[Path], *, fail_before_replace: bool = False) -> DayFiles:
    """Concatenate shards (already in batch order) into the day's two files, atomically."""
    kept: list[list[str]] = []
    audit: list[list[str]] = []
    for p in shard_paths:
        for row in read_shard_rows(p):
            (kept if row[0] == "captured" else audit).append(row)
    day_bytes = _gzip(encode_rows(kept, header=True))
    audit_bytes = _gzip(encode_rows(audit, header=True))
    day_path, audit_path = layout.day_path(day), layout.audit_path(day)
    audit_sha = atomic_write(audit_path, audit_bytes)
    day_sha = atomic_write(day_path, day_bytes, fail_before_replace=fail_before_replace)
    return DayFiles(len(kept), len(audit), day_path, day_sha, day_path.stat().st_size, audit_path, audit_sha)
