"""Labelled-data handling for the sentiment model: manifest validation, loading, label mapping, duplicate handling and a deterministic, leakage-free split.

Pure Python (no deep-learning package, no network). Training and evaluation refuse a dataset whose manifest is not APPROVED, undocumented, or unlicensed.

Duplicate-leakage policy (documented in the manifest and enforced here):
- text is normalised exactly as the application normalises user text (`validate_text`), then compared case-insensitively;
- an exact duplicate with the same label is kept once; the same text with DIFFERENT labels is removed from every split (it is not a usable example) and counted;
- the split assigns whole GROUPS (an optional `group` field such as an author or document id; otherwise the normalised text itself), so a group never straddles train / validation / test;
- `check_no_leakage` re-verifies that no normalised text and no group appears in two splits.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from wealthpilot.core.user_text_sentiment import UserTextError, validate_text

from training.sentiment.config import LABELS, MIN_TEXT_CHARS

REQUIRED_MANIFEST_FIELDS = ("dataset_id", "version", "source", "url", "license", "language", "label_definitions", "label_map", "sample_count", "preprocessing", "split_policy",
                            "duplicate_policy", "limitations", "domain_note", "approved", "development_fixture")


class ManifestError(ValueError):
    """The dataset manifest is incomplete or not approved. The message lists problems, never data."""


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    version: str
    source: str
    url: str
    license: str
    language: str
    label_definitions: dict[str, str]
    label_map: dict[str, str]                 # the dataset's own label -> one of LABELS
    sample_count: int
    preprocessing: str
    split_policy: dict
    duplicate_policy: str
    limitations: tuple[str, ...]
    domain_note: str
    approved: bool
    development_fixture: bool
    approved_by: str = ""
    has_intensity: bool = False
    intensity_definition: str = ""


def validate_manifest(raw: object, *, allow_development_fixture: bool = False) -> DatasetManifest:
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise ManifestError("the manifest must be a JSON object")
    for name in REQUIRED_MANIFEST_FIELDS:
        if name not in raw:
            problems.append(f"missing field: {name}")
    if problems:
        raise ManifestError("; ".join(problems))
    for name in ("dataset_id", "version", "source", "url", "license", "language", "preprocessing", "duplicate_policy", "domain_note"):
        if not isinstance(raw[name], str) or not raw[name].strip():
            problems.append(f"{name} must be a non-empty string")
    if not isinstance(raw["label_map"], dict) or not raw["label_map"] or not set(raw["label_map"].values()) <= set(LABELS):
        problems.append(f"label_map must map the dataset's labels onto {LABELS}")
    if not isinstance(raw["label_definitions"], dict) or not raw["label_definitions"]:
        problems.append("label_definitions must define every label")
    if not isinstance(raw["sample_count"], int) or isinstance(raw["sample_count"], bool) or raw["sample_count"] <= 0:
        problems.append("sample_count must be a positive integer")
    if not isinstance(raw["split_policy"], dict) or not {"train", "validation", "test"} <= set(raw["split_policy"]):
        problems.append("split_policy must give train, validation and test fractions")
    if not isinstance(raw["limitations"], list) or not raw["limitations"]:
        problems.append("limitations must be a non-empty list")
    if not isinstance(raw["approved"], bool) or not isinstance(raw["development_fixture"], bool):
        problems.append("approved and development_fixture must be true or false")
    if problems:
        raise ManifestError("; ".join(problems))
    if raw["development_fixture"] and not allow_development_fixture:
        raise ManifestError("a development fixture is for tests only; it is never training or validation data")
    if not raw["approved"] and not raw["development_fixture"]:
        raise ManifestError("the dataset is not approved: the project owner must approve its source and licence first (approved: true, approved_by)")
    if raw["approved"] and not str(raw.get("approved_by") or "").strip():
        raise ManifestError("an approved dataset must name who approved it (approved_by)")
    if raw.get("has_intensity") and not str(raw.get("intensity_definition") or "").strip():
        raise ManifestError("a dataset with intensity targets must define how they were obtained (intensity_definition)")
    return DatasetManifest(
        dataset_id=raw["dataset_id"], version=raw["version"], source=raw["source"], url=raw["url"], license=raw["license"], language=raw["language"], label_definitions=dict(raw["label_definitions"]),
        label_map=dict(raw["label_map"]), sample_count=raw["sample_count"], preprocessing=raw["preprocessing"], split_policy=dict(raw["split_policy"]), duplicate_policy=raw["duplicate_policy"],
        limitations=tuple(raw["limitations"]), domain_note=raw["domain_note"], approved=raw["approved"], development_fixture=raw["development_fixture"], approved_by=str(raw.get("approved_by") or ""),
        has_intensity=bool(raw.get("has_intensity")), intensity_definition=str(raw.get("intensity_definition") or ""))


def load_manifest(path: Path, *, allow_development_fixture: bool = False) -> DatasetManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ManifestError("the manifest could not be read as JSON") from None
    return validate_manifest(raw, allow_development_fixture=allow_development_fixture)


@dataclass(frozen=True)
class LabelledRow:
    text: str                  # normalised exactly like user text
    label: str                 # one of LABELS
    intensity: float | None    # -1.0 .. +1.0 from the dataset itself, or None
    group: str                 # the unit that must not straddle splits


@dataclass
class LoadReport:
    read: int = 0
    kept: int = 0
    skipped: Counter = field(default_factory=Counter)
    exact_duplicates_removed: int = 0
    conflicting_labels_removed: int = 0


def normalise_key(text: str) -> str:
    return text.casefold()


def load_rows(path: Path, manifest: DatasetManifest) -> tuple[list[LabelledRow], LoadReport]:
    """JSON Lines: {"text": ..., "label": ..., optional "intensity": float in [-1, 1], optional "group": str}. Invalid lines are counted by reason, never echoed."""
    report = LoadReport()
    candidates: list[LabelledRow] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            report.read += 1
            try:
                item = json.loads(line)
            except ValueError:
                report.skipped["bad_json"] += 1
                continue
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                report.skipped["missing_text"] += 1
                continue
            label = manifest.label_map.get(str(item.get("label")))
            if label is None:
                report.skipped["unknown_label"] += 1
                continue
            try:
                text = validate_text(item["text"])
            except UserTextError:
                report.skipped["unusable_text"] += 1
                continue
            if text is None or len(text) < MIN_TEXT_CHARS:
                report.skipped["empty_or_too_short"] += 1
                continue
            intensity = item.get("intensity")
            if intensity is not None:
                if not manifest.has_intensity or isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not -1.0 <= float(intensity) <= 1.0:
                    report.skipped["bad_intensity"] += 1
                    continue
                intensity = float(intensity)
            group = str(item.get("group") or normalise_key(text))
            candidates.append(LabelledRow(text, label, intensity, group))

    by_key: dict[str, list[LabelledRow]] = {}
    for row in candidates:
        by_key.setdefault(normalise_key(row.text), []).append(row)
    rows: list[LabelledRow] = []
    for key, same in by_key.items():
        if len({r.label for r in same}) > 1:
            report.conflicting_labels_removed += len(same)           # the same text with different labels is not a usable example
            continue
        report.exact_duplicates_removed += len(same) - 1
        rows.append(same[0])
    report.kept = len(rows)
    return rows, report


@dataclass(frozen=True)
class Splits:
    train: tuple[LabelledRow, ...]
    validation: tuple[LabelledRow, ...]
    test: tuple[LabelledRow, ...]


def _bucket(seed: int, group: str) -> int:
    return int(hashlib.sha256(f"{seed}:{group}".encode("utf-8")).hexdigest(), 16)


def split_rows(rows: list[LabelledRow], seed: int, fractions: tuple[float, float, float]) -> Splits:
    """Deterministic: the same rows, seed and fractions always give the same split, independent of input order. Whole groups are assigned, filling train, then validation, then test
    in the order of a seeded hash, separately for each group's majority label (so every split has every class where the data allows)."""
    if abs(sum(fractions) - 1.0) > 1e-9 or any(f <= 0 for f in fractions):
        raise ValueError("fractions must be positive and sum to 1")
    groups: dict[str, list[LabelledRow]] = {}
    for row in rows:
        groups.setdefault(row.group, []).append(row)
    by_label: dict[str, list[str]] = {}
    for group, members in groups.items():
        majority = Counter(r.label for r in members).most_common(1)[0][0]
        by_label.setdefault(majority, []).append(group)
    assigned: dict[str, list[LabelledRow]] = {"train": [], "validation": [], "test": []}
    for label in sorted(by_label):
        ordered = sorted(by_label[label], key=lambda g: (_bucket(seed, g), g))
        total = sum(len(groups[g]) for g in ordered)
        targets = (fractions[0] * total, (fractions[0] + fractions[1]) * total)
        seen = 0
        for group in ordered:
            name = "train" if seen < targets[0] else "validation" if seen < targets[1] else "test"
            assigned[name].extend(groups[group])
            seen += len(groups[group])
    return Splits(*(tuple(sorted(assigned[n], key=lambda r: (_bucket(seed, r.group), r.text))) for n in ("train", "validation", "test")))


def check_no_leakage(splits: Splits) -> None:
    """Raises if a normalised text or a group appears in more than one split."""
    names = ("train", "validation", "test")
    parts = [getattr(splits, n) for n in names]
    for i in range(3):
        for j in range(i + 1, 3):
            if {normalise_key(r.text) for r in parts[i]} & {normalise_key(r.text) for r in parts[j]}:
                raise ValueError(f"duplicate text across the {names[i]} and {names[j]} splits")
            if {r.group for r in parts[i]} & {r.group for r in parts[j]}:
                raise ValueError(f"a group straddles the {names[i]} and {names[j]} splits")


def label_counts(rows: tuple[LabelledRow, ...] | list[LabelledRow]) -> dict[str, int]:
    counts = Counter(r.label for r in rows)
    return {label: counts.get(label, 0) for label in LABELS}
