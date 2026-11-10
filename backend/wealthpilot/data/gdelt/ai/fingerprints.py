"""Canonical JSON and SHA-256 fingerprints used to bind approvals and to detect changed inputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def item_fingerprint(fields: dict[str, str]) -> str:
    """Fingerprint of exactly the approved input fields of one item."""
    return sha256_obj(fields)


def itemset_fingerprint(pairs: Iterable[tuple[str, str]]) -> str:
    """Fingerprint of the whole item set: sorted ``item_id:item_fingerprint`` lines."""
    lines = sorted(f"{item_id}:{fp}" for item_id, fp in pairs)
    return sha256_text("\n".join(lines) + "\n")
