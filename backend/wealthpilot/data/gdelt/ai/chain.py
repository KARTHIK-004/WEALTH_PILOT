"""Append-only, tamper-evident JSON-lines files (a SHA-256 hash chain).

Each record carries ``prev_sha256`` and ``record_sha256``. Editing, deleting, reordering or inserting a record breaks
the chain and is detected on read. Records are only ever appended (one line, then fsync). If a crash leaves an
incomplete final line, the next append first moves that fragment to a ``.partial-N`` file, never deleting it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt.ai.fingerprints import sha256_obj
from wealthpilot.data.gdelt.errors import GdeltToolError

GENESIS = "0" * 64


class ChainError(GdeltToolError):
    code = "ai_chain_error"


class ChainedJsonl:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _scan(self) -> tuple[list[dict[str, Any]], bool]:
        if not self.path.exists():
            return [], False
        data = self.path.read_bytes()
        partial = bool(data) and not data.endswith(b"\n")
        lines = data.split(b"\n")
        lines = lines[:-1]                      # the piece after the last newline: empty, or an incomplete fragment
        records: list[dict[str, Any]] = []
        prev = GENESIS
        for n, line in enumerate(lines, start=1):
            try:
                rec = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise ChainError(f"{self.path.name} line {n} is not valid JSON") from exc
            if not isinstance(rec, dict) or "prev_sha256" not in rec or "record_sha256" not in rec:
                raise ChainError(f"{self.path.name} line {n} lacks chain fields")
            if rec["prev_sha256"] != prev:
                raise ChainError(f"{self.path.name} line {n} breaks the chain (a record was removed, added or moved)")
            body = {k: v for k, v in rec.items() if k != "record_sha256"}
            if sha256_obj(body) != rec["record_sha256"]:
                raise ChainError(f"{self.path.name} line {n} was edited after it was written")
            prev = rec["record_sha256"]
            records.append(rec)
        return records, partial

    def records(self) -> list[dict[str, Any]]:
        return self._scan()[0]

    def head(self) -> str:
        recs = self.records()
        return recs[-1]["record_sha256"] if recs else GENESIS

    def has_partial_tail(self) -> bool:
        return self._scan()[1]

    def _quarantine_tail(self) -> Path:
        data = self.path.read_bytes()
        cut = data.rfind(b"\n") + 1
        n = 1
        while self.path.with_name(f"{self.path.name}.partial-{n}").exists():
            n += 1
        target = self.path.with_name(f"{self.path.name}.partial-{n}")
        target.write_bytes(data[cut:])
        with open(self.path, "r+b") as f:
            f.truncate(cut)
            f.flush()
            os.fsync(f.fileno())
        return target

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        if "prev_sha256" in record or "record_sha256" in record:
            raise ChainError("records must not carry chain fields")
        records, partial = self._scan()
        if partial:
            self._quarantine_tail()
        prev = records[-1]["record_sha256"] if records else GENESIS
        body = {**record, "prev_sha256": prev}
        full = {**body, "record_sha256": sha256_obj(body)}
        line = (json.dumps(full, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "ab") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        return full
