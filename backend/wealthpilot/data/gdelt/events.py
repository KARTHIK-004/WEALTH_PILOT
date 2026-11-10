"""JSON-lines event log. Only allow-listed keys are written, so titles, URLs' text and secrets
cannot reach a log by accident."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_KEYS = frozenset({
    "event", "run_id", "mode", "batch_ts", "status", "reason", "code", "http_status", "attempt", "bytes",
    "bytes_used", "requests_used", "planned_bytes", "limit", "state", "day", "rows", "counts", "flags",
    "sha256", "seconds", "free_bytes", "detail",
})


class EventLog:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.events: list[dict[str, Any]] = []

    def emit(self, event: str, **fields: Any) -> None:
        unknown = set(fields) - ALLOWED_KEYS
        if unknown:
            raise ValueError(f"log keys not allowed: {sorted(unknown)}")
        record = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "event": event, **fields}
        self.events.append(record)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, sort_keys=True, default=str) + "\n")
