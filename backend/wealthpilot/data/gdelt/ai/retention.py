"""Retention for AI-run artifacts (B2-U5). **Dry run by default; deletion needs an explicit confirmation.**

``retention_days`` is enforced only for the artifacts named in ``EXPIRABLE``. Everything else in the experiment folder is
protected and is never listed for deletion: the snapshot (original files), the item inputs, the hash-chained suggestion,
review and audit records, run manifests, the export, the fingerprints, approvals, and anything outside the folder.

**Limitation (a design decision for the data-handling gate).** The raw provider responses live *inside* the hash-chained
suggestion record. Deleting or editing one would break the chain that proves nothing was altered, so they are **not**
expirable in the current layout. Making them expirable needs a layout change: store the response text in a separate
payload file and keep only its SHA-256 in the chain. That change is not made here (it also decides what the research
record must keep, which is yours to decide).

The retention clock starts when the last AI run ended, read from the hash-chained audit log, not from file times. With no
recorded run, an unfinished run, or an unreadable time, nothing expires.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt.ai.store import AuditLog, Layout, utc
from wealthpilot.data.gdelt.ai.chain import ChainedJsonl
from wealthpilot.data.gdelt.errors import GdeltToolError

MAX_RETENTION_DAYS = 3650
# derived files that can be rebuilt from the protected chain, and crash fragments of the raw suggestion chain
EXPIRABLE = ("suggestions/ai_suggestions_valid_v1.csv", "queue/review_queue_v1.csv",
             "suggestions/ai_suggestions_raw_v1.jsonl.partial-<N>")
NOT_COVERED = ("snapshot/ (original files)", "inputs/", "suggestions/ai_suggestions_raw_v1.jsonl (raw provider responses: "
               "hash-chained, not expirable in the current layout)", "review/", "audit/ (including run manifests)",
               "export/", "fingerprints.json", "approvals in the experiment config", "everything outside the folder")
_PARTIAL_RE = re.compile(r"^ai_suggestions_raw_v1\.jsonl\.partial-\d+$")
_BOUNDARY_EVENTS = {"run_started", "run_finished", "run_stopped"}
_TS = "%Y-%m-%dT%H:%M:%SZ"


class RetentionError(GdeltToolError):
    code = "ai_retention_error"


def validate_retention_days(value: Any) -> int:
    """An integer from 1 to 3650. Nothing is defaulted, rounded or clamped."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_RETENTION_DAYS:
        raise RetentionError(f"retention_days must be a whole number from 1 to {MAX_RETENTION_DAYS} (got {value!r})")
    return value


def run_end(layout: Layout) -> tuple[datetime | None, str]:
    """When the last AI run ended, or why that is not known. Reads (and so verifies) the audit hash chain."""
    events = [e for e in ChainedJsonl(layout.audit).records() if e.get("event") in _BOUNDARY_EVENTS]
    if not events:
        return None, "no AI run is recorded, so the retention clock has not started"
    last = events[-1]
    if last["event"] == "run_started":
        return None, "the last run has not finished (interrupted or in progress), so nothing expires"
    try:
        return datetime.strptime(str(last.get("at_utc")), _TS).replace(tzinfo=timezone.utc), "ok"
    except ValueError:
        return None, "the recorded end time of the last run is missing or invalid, so nothing expires"


def _candidates(layout: Layout) -> list[tuple[str, Path]]:
    out = [(rel, layout.root / rel) for rel in EXPIRABLE[:2]]
    folder = layout.suggestions_raw.parent
    if folder.is_dir():
        out += [(f"suggestions/{p.name}", p) for p in sorted(folder.iterdir()) if _PARTIAL_RE.match(p.name)]
    return out


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def plan(layout: Layout, retention_days: Any, *,
         clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    """What would expire. Writes nothing."""
    days = validate_retention_days(retention_days)
    if not (layout.root / "snapshot" / "annotation_A.csv").is_file() or not layout.audit.is_file():
        raise RetentionError(f"{layout.root} is not an AI experiment folder (no snapshot and audit log); nothing is touched")
    ended, why = run_end(layout)
    now = clock()
    expires_at = ended + timedelta(days=days) if ended else None
    rows: list[dict[str, Any]] = []
    for rel, path in _candidates(layout):
        if not path.exists() and not path.is_symlink():
            continue
        row: dict[str, Any] = {"path": rel, "bytes": None, "action": "keep", "reason": ""}
        if path.is_symlink() or not path.is_file() or not _inside(layout.root, path):
            row["reason"] = "not a regular file inside the experiment folder; never touched"
        else:
            row["bytes"] = path.stat().st_size
            if expires_at is None:
                row["reason"] = why
            elif now < expires_at:
                row["reason"] = f"not expired: the retention period ends {utc(expires_at)}"
            else:
                row["action"], row["reason"] = "delete", f"expired {utc(expires_at)}"
        rows.append(row)
    return {"mode": "dry_run", "retention_days": days, "run_ended_at_utc": utc(ended) if ended else None,
            "clock_note": why, "expires_at_utc": utc(expires_at) if expires_at else None, "evaluated_at_utc": utc(now),
            "artifacts": rows, "would_delete": sum(r["action"] == "delete" for r in rows),
            "covered_by_retention": list(EXPIRABLE), "not_covered_by_retention": list(NOT_COVERED)}


def enforce(layout: Layout, retention_days: Any, *, confirm_delete: bool = False,
            clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    """Dry run unless ``confirm_delete`` is true. Deletes only the files the plan marked, never a directory."""
    result = plan(layout, retention_days, clock=clock)
    if not confirm_delete:
        return result
    deleted: list[str] = []
    for row in result["artifacts"]:
        if row["action"] != "delete":
            continue
        path = layout.root / row["path"]
        if path.is_symlink() or not path.is_file() or not _inside(layout.root, path):
            raise RetentionError(f"{row['path']} changed since the plan; nothing further was deleted")
        os.chmod(path, 0o666)
        path.unlink()
        deleted.append(row["path"])
        row["action"] = "deleted"
    if deleted:
        AuditLog(layout).emit("retention_deleted", now=clock(), counts={"deleted": len(deleted)}, detail=sorted(deleted))
    return {**result, "mode": "deleted" if deleted else "confirmed_nothing_expired", "deleted": deleted}
