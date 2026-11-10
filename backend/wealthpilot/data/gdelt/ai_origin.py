"""Verified AI-origin evidence for evaluation (B2-U8). Offline; reads no key, calls no provider, writes nothing.

When any human label was made after seeing an AI suggestion (``ai_exposed``), the evaluation needs proof of that, from
the separately versioned ``b2t_annotation_v1`` export, not from the working copy's say-so alone. ``attach`` checks that
export against the verified provenance bridge (``provenance.verify``) and **blocks** on anything missing, conflicting,
fabricated or unverifiable. It never repairs, infers or defaults a record: a missing label is never a negative, an
unexplained agreement is never a verification.

What is checked, per export row: the item exists once; its source fields equal the original; its overlap membership equals
the verified membership; its label content and duplicate reference equal the working copy's; its origin, exposure,
reviewer, time and review-record hash are well formed and consistent with each other; an exposed label cites a
suggestion and an unexposed one does not; an overlap item is never AI-exposed. Per export: the CSV matches its manifest
hash, the manifest says what the CSV says, and every non-overlap item is covered (an AI-assisted label with no
covering record cannot be verified, so the dataset is incomplete).

Nothing here decides which methodology applies. It only refuses to call a label independent without evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt.annotate import LABEL_COLUMNS, SOURCE_COLUMNS, Paths
from wealthpilot.data.gdelt.provenance import ProvenanceReport

CSV_NAME, MANIFEST_NAME = "annotation_b2t_v1.csv", "EXPORT_MANIFEST.json"
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_COMPARED = tuple(c for c in LABEL_COLUMNS if c not in ("annotator_id", "annotator_type", "label_basis", "labelled_at_utc", "note"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_fingerprints(export_dir: Path | None) -> dict[str, str | None]:
    """The export files' hashes, for the evaluation fingerprint (``None`` = absent). Reading a hash is not verifying."""
    if export_dir is None:
        return {CSV_NAME: None, MANIFEST_NAME: None, "suggestions_raw_chain": None}
    c, m = export_dir / CSV_NAME, export_dir / MANIFEST_NAME
    chain = export_dir.parent / "suggestions" / "ai_suggestions_raw_v1.jsonl" if export_dir.name == "export" else None
    return {CSV_NAME: _sha(c) if c.is_file() else None, MANIFEST_NAME: _sha(m) if m.is_file() else None,
            "suggestions_raw_chain": _sha(chain) if chain is not None and chain.is_file() else None}


def _vocab() -> tuple[frozenset[str], frozenset[str]]:
    from wealthpilot.data.gdelt.ai.evaluation import ORIGINS, UNEXPOSED_ORIGINS   # local: the package is otherwise not needed
    return ORIGINS, UNEXPOSED_ORIGINS


def _load(export_dir: Path, rep: ProvenanceReport) -> list[dict[str, str]] | None:
    from wealthpilot.data.gdelt.ai import DATASET_SCHEMA
    from wealthpilot.data.gdelt.ai.export import B2T_COLUMNS
    csv_path, man_path = export_dir / CSV_NAME, export_dir / MANIFEST_NAME
    for path in (csv_path, man_path):
        if path.is_symlink() or not path.is_file():
            rep.add("ai_origin_unverifiable", None, f"the AI-origin export file {path.name} is missing or not a regular file")
    if not (csv_path.is_file() and man_path.is_file()) or csv_path.is_symlink() or man_path.is_symlink():
        return None
    try:
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError
    except (OSError, ValueError):
        rep.add("ai_origin_unverifiable", None, "EXPORT_MANIFEST.json is unreadable or not an object")
        return None
    if manifest.get("schema") != DATASET_SCHEMA:
        rep.add("ai_origin_unverifiable", None, f"the export manifest schema is not {DATASET_SCHEMA}")
        return None
    if manifest.get("csv_sha256") != _sha(csv_path):
        rep.add("ai_origin_unverifiable", None, "the export CSV does not match the hash in its manifest")
        return None
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != B2T_COLUMNS:
                rep.add("ai_origin_unverifiable", None, "the export CSV does not have the b2t_annotation_v1 columns")
                return None
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        rep.add("ai_origin_unverifiable", None, f"the export CSV cannot be read ({type(exc).__name__})")
        return None
    if manifest.get("rows") != len(rows):
        rep.add("ai_origin_unverifiable", None, "the export manifest row count differs from the CSV")
    rep.counts["ai_origin_manifest"] = manifest
    return rows


def read_export_rows(export_dir: Path) -> list[dict[str, str]]:
    """The export's rows. Call only after ``attach`` verified the export: it does no checking of its own."""
    with open(export_dir / CSV_NAME, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _row_checks(rep: ProvenanceReport, rows: list[dict[str, str]], origins: frozenset[str], unexposed: frozenset[str],
                bridge: Any, *, premerge: bool) -> None:
    from wealthpilot.data.gdelt.ai_bridge import BASIS_FOR_ORIGIN, CONTENT_KEYS, UNMAPPED_ORIGINS
    for r in rows:
        iid = (r.get("item_id") or "").strip()
        rec = rep.items.get(iid)
        if rec is None:
            continue                                            # unknown / blank IDs are reported by merge_ai_origin
        origin, exposure = r.get("label_origin"), r.get("ai_exposure")
        if origin not in origins:
            rep.add("origin_invalid", iid, f"label_origin {origin!r} is not a recognised review origin")
        elif exposure in ("seen", "none") and (exposure == "none") != (origin in unexposed):
            rep.add("origin_conflict", iid, f"label_origin {origin!r} and ai_exposure {exposure!r} contradict each other")
        if r.get("annotator_type") != "human" or not (r.get("annotator_id") or "").strip():
            rep.add("review_invalid", iid, "a reviewed label needs annotator_type 'human' and a named reviewer")
        if not _TS_RE.match(r.get("reviewed_at_utc") or ""):
            rep.add("review_invalid", iid, "reviewed_at_utc is missing or not a UTC timestamp")
        if not _SHA_RE.match(r.get("review_record_sha256") or ""):
            rep.add("review_invalid", iid, "review_record_sha256 is missing or malformed")
        ref = (r.get("suggestion_ref") or "").strip()
        if exposure == "seen" and not _SHA_RE.match(ref):
            rep.add("origin_conflict", iid, "an AI-exposed label must cite the suggestion it was made after")
        if exposure == "none" and ref:
            rep.add("origin_conflict", iid, "a label recorded as unexposed cites a suggestion")
        if rec["overlap"] and ref:
            rep.add("overlap_ai_exposed", iid, "an overlap item cites an AI suggestion; overlap items are never sent or shown")
        src_diff = [c for c in SOURCE_COLUMNS if (r.get(c) or "") != rec["source"][c]]
        if src_diff:
            rep.add("source_changed", iid, f"the export's source fields differ from the original: {src_diff}")
        if (r.get("overlap_subset") == "Y") != rec["overlap"]:
            rep.add("membership_conflict", iid, "the export's overlap membership differs from the verified membership")
        diff = [c for c in _COMPARED if (r.get(c) or "").strip() != rec["labels"][c]]
        if diff and not premerge:
            rep.add("label_mismatch", iid, f"the export's label content differs from the working copy: {diff}")
        if origin in BASIS_FOR_ORIGIN and not premerge and rec["origin"] != "unlabelled"                 and rec["label_basis"] != BASIS_FOR_ORIGIN[origin]:
            rep.add("origin_conflict", iid, f"review origin {origin!r} requires label_basis {BASIS_FOR_ORIGIN[origin]!r}; "
                                            f"the working copy records {rec['label_basis']!r}")
        if origin in UNMAPPED_ORIGINS and not premerge and rec["origin"] == "human_only":
            rep.add("origin_conflict", iid, f"review origin {origin!r} means an AI suggestion was seen; the working copy "
                                            "records a human-only label")
        if bridge is not None:
            sug = bridge.records.get(iid)
            if exposure == "seen" and _SHA_RE.match(ref):
                if sug is None or sug["record_sha256"] != ref:
                    rep.add("origin_conflict", iid, "the cited suggestion is not the verified valid suggestion for this item")
                elif origin == "accepted_ai" and any((r.get(k) or "").strip() != sug["parsed"][k] for k in CONTENT_KEYS):
                    rep.add("origin_conflict", iid, "an accepted label differs from the suggestion it says it accepted")
                elif origin in ("edited_ai", "rejected_ai_after_seeing")                         and all((r.get(k) or "").strip() == sug["parsed"][k] for k in CONTENT_KEYS):
                    rep.add("origin_conflict", iid, f"a {origin} label is identical to the suggestion")
            elif exposure == "none" and sug is not None and origin == "human_no_suggestion":
                rep.add("origin_conflict", iid, "the review says no suggestion existed but the verified store holds one")
        near = (r.get("near_dup_of") or "").strip()
        if near and (near == iid or near not in rep.items):
            rep.add("near_dup_invalid", iid, f"the export's near_dup_of must name another dataset item (got {near!r})")


def _chain_checks(report: ProvenanceReport, manifest: dict[str, Any], rows: list[dict[str, str]], bridge: Any) -> None:
    """F1 and F2: the export must still agree with the chains it was made from. Read-only.

    - the suggestion chain's current head equals the head the manifest recorded (any later append is refused);
    - the review chain verifies, and every exported row's ``review_record_sha256`` is the CURRENT review record's hash for
      that item (a forged hash, or a review superseded after export, is refused);
    - the manifest's review and audit heads appear in their verified chains. The audit head is only an ancestor: the
      ``export_created`` event is appended after the manifest is built, so equality would never hold.
    """
    from wealthpilot.data.gdelt.ai.chain import GENESIS, ChainedJsonl, ChainError
    from wealthpilot.data.gdelt.ai.store import ReviewStore
    layout = bridge.layout
    heads = manifest.get("chain_heads")
    if not isinstance(heads, dict) or not all(isinstance(heads.get(k), str) for k in ("suggestions", "reviews", "audit")):
        report.add("chain_heads_missing", None, "the export manifest does not record the suggestion, review and audit chain heads")
        return
    if heads["suggestions"] != bridge.head:
        report.add("chain_changed_after_export", None, "the suggestion chain's head differs from the head recorded at export: "
                                                       "records were added after the export was made")
    try:
        reviews = ChainedJsonl(layout.reviews).records()
    except ChainError as exc:
        report.add("review_chain_unverifiable", None, f"the review chain cannot be verified: {exc.reason}")
        reviews = None
    try:
        audit = ChainedJsonl(layout.audit).records()
    except ChainError as exc:
        report.add("audit_chain_unverifiable", None, f"the audit chain cannot be verified: {exc.reason}")
        audit = None
    if audit is not None and heads["audit"] not in {GENESIS, *(r["record_sha256"] for r in audit)}:
        report.add("chain_changed_after_export", None, "the audit head recorded at export is not in the audit chain")
    if reviews is None:
        return
    if heads["reviews"] not in {GENESIS, *(r["record_sha256"] for r in reviews)}:
        report.add("chain_changed_after_export", None, "the review head recorded at export is not in the review chain")
    current = ReviewStore(layout).current()
    for r in rows:
        iid = (r.get("item_id") or "").strip()
        rec = current.get(iid)
        if rec is None:
            report.add("review_record_missing", iid, "no review record exists in the review chain for this exported row")
        elif rec["record_sha256"] != r.get("review_record_sha256"):
            report.add("review_record_mismatch", iid, "the exported review hash is not the current review record's hash")


def attach(report: ProvenanceReport, export_dir: Path | None, *, premerge: bool = False,
           bridge: Any = None) -> ProvenanceReport:
    """Verify AI-origin evidence and fold any problem into ``report`` (status BLOCKED). Idempotent on a blocked report.

    ``premerge`` verifies an export before its labels exist in the working copy (it skips the comparisons with the working
    copy's labels); ``ai_bridge.labels_for_merge`` uses it. ``bridge`` is the verified B2-T suggestion set from
    ``ai_bridge.load``; ``None`` means the legacy source applies and no suggestion-level checks are made."""
    from wealthpilot.data.gdelt.provenance import merge_ai_origin
    if not report.ok:
        return report
    exposed = sorted(i for i, v in report.items.items() if v["origin"] == "ai_exposed")
    report.counts["ai_origin"] = {"required": bool(exposed), "export_supplied": export_dir is not None,
                                  "ai_exposed_items": len(exposed)}
    if export_dir is None:
        if exposed:
            report.add("ai_origin_missing", None, f"{len(exposed)} labels are AI-exposed but no AI-origin export was "
                                                  f"supplied to verify them (first: {exposed[:5]})")
        return report
    rows = _load(export_dir, report)
    if rows is None or not report.ok:
        return report
    if bridge is not None and bridge.suggestions.problems:
        report.add("suggestions_unverifiable", None, "; ".join(bridge.suggestions.problems[:3]))
        report.counts.pop("ai_origin_manifest", None)
        return report
    manifest = report.counts.pop("ai_origin_manifest")
    origins, unexposed = _vocab()
    merge_ai_origin(report, rows)                              # unknown / duplicate / exposure-vs-working conflicts
    _row_checks(report, rows, origins, unexposed, bridge, premerge=premerge)
    if bridge is not None:
        _chain_checks(report, manifest, rows, bridge)
    covered = {(r.get("item_id") or "").strip() for r in rows}
    missing = sorted(i for i, v in report.items.items() if not v["overlap"] and i not in covered)
    if missing:
        report.add("ai_origin_incomplete", None, f"{len(missing)} non-overlap items have no review record in the export, "
                                                 f"so their origin is unverified (first: {missing[:5]})")
    if manifest.get("historical_overlap_items") != report.counts["overlap"]:
        report.add("membership_conflict", None, "the export manifest's overlap count differs from the verified membership")
    report.counts["ai_origin"].update({
        "rows": len(rows), "csv_sha256": manifest.get("csv_sha256"), "by_label_origin": dict(Counter(r["label_origin"] for r in rows)),
        "by_ai_exposure": dict(Counter(r["ai_exposure"] for r in rows)), "verified": report.ok})
    return report


def verified(p: Paths, export_dir: Path | None) -> ProvenanceReport:
    """``provenance.verify`` followed by ``attach``: the one provenance result freeze and evaluation use."""
    from wealthpilot.data.gdelt import ai_bridge, provenance
    return attach(provenance.verify(p), export_dir, bridge=ai_bridge.load(p, export_dir))

