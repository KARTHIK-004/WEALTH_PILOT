"""Offline plumbing for evaluating on an approved, FROZEN labelled set (ADR-052; owner decision `APPROVE_SCHEMA_AND_WIRE_OFFLINE`, 2026-10-29). Nothing here reads a model, the network or user text; it
verifies a manifest and the files it names, builds the explicit `EvidenceBasis` from what it verified, and calls the evaluation statistics. No real manifest or dataset exists, none is created here, and
this module is exercised only on local synthetic fixtures. It is reached by `evaluate_sentiment_model.py` ONLY through `load_frozen_evaluation` / `evaluate_frozen`, and it is connected to no model, route
or activation path. `training/sentiment/dataset.py::DatasetManifest` (used by the training pipeline) is deliberately separate and untouched.

Manifest (JSON object; every field required; `schema_version` 2 - version 1 lacked the register, calibration and duplicate-policy fields below; the schema is NOT owner-approved for real data (E3 is
unresolved) and is exercised only by local synthetic fixtures):
    schema_version; manifest_status "FROZEN"; dataset_id; dataset_version; dataset_purpose; license; provenance {source, collection_method, de_identification};
    approved (bool); approved_by; approved_on; development_fixture (bool); synthetic (bool); created_at (UTC, YYYY-MM-DDTHH:MM:SSZ);
    rubric {version, sha256, frozen (bool), approved (bool)}; records_file {name, sha256};
    hashes {record_ids_sha256, content_sha256, labels_sha256, split_assignments_sha256};
    record_count; label_set "positive_negative_neutral"; split_counts {train, calibration, heldout}; class_counts {split: {label: n}}; group_dimensions [str];
    annotation {annotators [code], adjudicator code, independence_attested (bool), annotator_manifest_sha256, adjudication_log_sha256};
    duplicates {exact_removed, near_duplicate_method, near_duplicate_threshold (0 < t <= 1), near_duplicates_removed, cross_split_duplicates_found};
    data_status ("synthetic" | "consented", agreeing with `synthetic`); participant_register {sha256 (the register file), verifier_sha256 (the de-identification verifier's entry), consent_wording_sha256
    (consented data only, otherwise null)}; calibration {split_sha256 (the calibration split's ids, content hashes and labels), temperature_policy_version, fit_split "calibration", method, bins 10,
    min_scored 20}; duplicates also {exact_method, ngram_size}; group_dimensions are drawn from the approved set (D12);
    baseline_method_version; evidence_basis_status ("eligible_for_owner_review" | "not_validation_evidence"); manifest_sha256 (the immutable hash of every other field, canonical JSON).
Records file (JSON Lines): {"id", "text", "label", "split" (train | calibration | heldout), "groups" {dimension: [value]}, optional "annotator_labels" {code: label}} -- the label is the ADJUDICATED reference;
`annotator_labels` are the independent PRE-adjudication labels. The annotator manifest (JSON) lists {"annotators", "adjudicator", "independence_attested"} and must agree with the manifest.
The participant register (JSON, `participant_register.py`) is validated at the authorization date (the manifest's `created_at` day, or an explicit `as_of`) and must agree with the manifest.

What is verified, in this order, BEFORE any evaluation (a failure raises `FrozenEvaluationError` listing problems; a message never contains a record's text): the manifest is a JSON object with a known schema
version and every field of the right type; no personal-data marker (e-mail address, link, long digit run) in any manifest string; the manifest's own `manifest_sha256`; the SHA-256 of the records file, the
rubric, the annotator manifest and the adjudication log; record shape, labels, splits and group dimensions; unique ids; the content, label, id and split-assignment hashes recomputed from the records; the
declared counts; all three splits present and disjoint; no exact duplicate (hash of the NFKC, case-folded, whitespace-collapsed text) inside or across splits; no cross-split pair whose character 5-gram Jaccard similarity reaches the approved threshold 0.90 (equality counts), the method and threshold being exactly the approved ones; and that the
manifest's declared `evidence_basis_status` equals the one computed (a manifest cannot claim more than the checks support). Approval, fixture, synthetic, rubric-frozen-and-approved and independence flags are
CARRIED into the `EvidenceBasis`, never raised: an unapproved, synthetic, fixture or draft-rubric set loads but is `not_validation_evidence`, and missing support is `insufficient_support`. The code cannot
establish independence or representativeness; its checks are about integrity.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

from training.sentiment.metrics import (
    OWNER_APPROVED_POLICY,
    TEMPERATURE_FIT_SPLIT,
    TEMPERATURE_METHOD,
    TEMPERATURE_POLICY_VERSION,
    EvalRecord,
    EvaluationPolicy,
    EvidenceBasis,
    StatisticsPlan,
    agreement_report,
    evaluation_report,
    temperature_calibration_report,
)
from training.sentiment.participant_register import DATA_STATUSES, RegisterError, consent_wording_hash, validate_register, verifier_hash
from wealthpilot.core.user_text_sentiment import UserTextError, validate_text

SCHEMA_VERSION = 2
LABEL_SET = "positive_negative_neutral"
SPLITS = ("train", "calibration", "heldout")
EVIDENCE_STATUSES = ("eligible_for_owner_review", "not_validation_evidence")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# Owner decision D11 (2026-10-29): exact duplicates by the hash of the normalized text; near duplicates by character 5-gram Jaccard similarity of the normalized text, at or above 0.90 (equality counts).
NEAR_DUPLICATE_METHOD = "nfkc_casefold_char5gram_jaccard"
NEAR_DUPLICATE_THRESHOLD = 0.9
NGRAM_SIZE = 5
EXACT_DUPLICATE_METHOD = "sha256_of_normalized_text"
APPROVED_GROUP_DIMENSIONS = ("topic", "difficulty", "negation", "contradiction", "code_mixed")          # owner decision D12 (2026-10-29)
REGISTER_FIELDS = ("sha256", "verifier_sha256", "consent_wording_sha256")
CALIBRATION_FIELDS = ("split_sha256", "temperature_policy_version", "fit_split", "method", "bins", "min_scored")          # D13: the policy values are the approved ones, not free choices
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_CODE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_NOT_CHECKED_FOR_DIGITS = ("created_at", "approved_on")
REQUIRED_FIELDS = ("schema_version", "manifest_status", "dataset_id", "dataset_version", "dataset_purpose", "license", "provenance", "approved", "approved_by", "approved_on", "development_fixture",
                   "synthetic", "created_at", "rubric", "records_file", "hashes", "record_count", "label_set", "split_counts", "class_counts", "group_dimensions", "annotation", "duplicates",
                   "baseline_method_version", "evidence_basis_status", "manifest_sha256", "data_status", "participant_register", "calibration")
HASH_FIELDS = ("record_ids_sha256", "content_sha256", "labels_sha256", "split_assignments_sha256")


class FrozenEvaluationError(ValueError):
    """The manifest or the records are incomplete, inconsistent or do not match their hashes. The message lists problems and counts, never record text."""


@dataclass(frozen=True)
class FrozenRecord:
    item_id: str
    text: str
    label: str
    split: str
    groups: Mapping[str, tuple[str, ...]]
    annotator_labels: Mapping[str, str]


@dataclass(frozen=True)
class FrozenEvaluation:
    manifest: Mapping[str, object]
    records: Mapping[str, tuple[FrozenRecord, ...]]       # split -> records in item-id order
    evidence: EvidenceBasis
    checks: Mapping[str, bool]                            # every verification, by name, in a fixed order


def sha256_file(path: Path) -> str:
    """SHA-256 of the file with CRLF normalised to LF, so Windows and Unix checkouts hash alike (as the pilot-pack builder does)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def manifest_hash(manifest: Mapping[str, object]) -> str:
    """The immutable hash: SHA-256 of the canonical JSON (sorted keys, compact separators) of every field except `manifest_sha256` itself."""
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def record_hashes(records: list[FrozenRecord]) -> dict[str, str]:
    """The four record-level hashes the manifest declares, from the records in item-id order: ids, per-record content (the text itself never leaves this function), labels and split assignments."""
    ordered = sorted(records, key=lambda r: r.item_id)

    def digest(lines: list[str]) -> str:
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    return {"record_ids_sha256": digest([r.item_id for r in ordered]),
            "content_sha256": digest([f"{r.item_id}\t{hashlib.sha256(r.text.encode('utf-8')).hexdigest()}" for r in ordered]),
            "labels_sha256": digest([f"{r.item_id}\t{r.label}" for r in ordered]),
            "split_assignments_sha256": digest([f"{r.item_id}\t{r.split}" for r in ordered])}


def calibration_split_hash(records: list[FrozenRecord]) -> str:
    """SHA-256 over the calibration split's ids, content hashes and adjudicated labels (no text): the manifest records it so a changed calibration split is detected."""
    lines = [f"{r.item_id}\t{hashlib.sha256(r.text.encode('utf-8')).hexdigest()}\t{r.label}" for r in sorted(records, key=lambda r: r.item_id)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Unicode NFKC, case-folded, whitespace collapsed to single spaces: the form both duplicate checks compare."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def text_hash(text: str) -> str:
    """The exact-duplicate key: a duplicate decision is recorded by this hash, never by the text."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def char_ngrams(text: str, size: int = NGRAM_SIZE) -> frozenset[str]:
    """The distinct character n-grams of the normalized text (a text shorter than `size` is one gram; an empty text has none)."""
    normalized = normalize_text(text)
    return frozenset(normalized[i:i + size] for i in range(max(len(normalized) - size + 1, 1))) if normalized else frozenset()


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


def near_duplicate_similarity(first: str, second: str) -> float:
    return _jaccard(char_ngrams(first), char_ngrams(second))


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _non_empty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _strings(node: object, key: str = "") -> list[tuple[str, str]]:
    if isinstance(node, str):
        return [(key, node)]
    if isinstance(node, dict):
        return [pair for k, v in node.items() for pair in _strings(v, str(k))]
    if isinstance(node, list):
        return [pair for v in node for pair in _strings(v, key)]
    return []


def _manifest_problems(m: object) -> list[str]:
    if not isinstance(m, dict):
        return ["the manifest must be a JSON object"]
    if "schema_version" not in m:
        return ["missing field 'schema_version': a manifest without a schema version is refused"]
    if m["schema_version"] != SCHEMA_VERSION:
        return [f"unknown schema_version: only {SCHEMA_VERSION} is supported"]
    problems = [f"missing field '{name}'" for name in REQUIRED_FIELDS if name not in m]
    if problems:
        return problems
    if m["manifest_status"] != "FROZEN":
        problems.append("manifest_status must be FROZEN")
    for name in ("dataset_id", "dataset_version", "dataset_purpose", "license", "approved_by", "baseline_method_version"):
        if not _non_empty(m[name]):
            problems.append(f"'{name}' must be a non-empty string")
    for name in ("approved", "development_fixture", "synthetic"):
        if not isinstance(m[name], bool):
            problems.append(f"'{name}' must be true or false")
    if not (isinstance(m["created_at"], str) and _TIMESTAMP.match(m["created_at"])):
        problems.append("'created_at' must be a UTC timestamp YYYY-MM-DDTHH:MM:SSZ")
    if not _non_empty(m["approved_on"]):
        problems.append("'approved_on' must be a non-empty date string")
    provenance = m["provenance"]
    if not (isinstance(provenance, dict) and all(_non_empty(provenance.get(k)) for k in ("source", "collection_method", "de_identification"))):
        problems.append("provenance must hold a source, a collection_method and a de_identification statement")
    if m["label_set"] != LABEL_SET:
        problems.append(f"label_set must be '{LABEL_SET}'")
    if m["evidence_basis_status"] not in EVIDENCE_STATUSES:
        problems.append("evidence_basis_status must be one of " + ", ".join(EVIDENCE_STATUSES))
    if not (isinstance(m["manifest_sha256"], str) and _SHA256.match(m["manifest_sha256"])):
        problems.append("manifest_sha256 must be a 64-character lowercase hexadecimal hash")
    rubric, records_file, hashes, annotation, duplicates = m["rubric"], m["records_file"], m["hashes"], m["annotation"], m["duplicates"]
    if not (isinstance(rubric, dict) and _non_empty(rubric.get("version")) and isinstance(rubric.get("frozen"), bool) and isinstance(rubric.get("approved"), bool)
            and isinstance(rubric.get("sha256"), str) and _SHA256.match(rubric["sha256"])):
        problems.append("rubric must hold a version, frozen and approved flags and a 64-character lowercase hexadecimal sha256")
    if not (isinstance(records_file, dict) and _non_empty(records_file.get("name")) and isinstance(records_file.get("sha256"), str) and _SHA256.match(records_file["sha256"])):
        problems.append("records_file must hold a name and a 64-character lowercase hexadecimal sha256")
    if not (isinstance(hashes, dict) and set(hashes) == set(HASH_FIELDS) and all(isinstance(v, str) and _SHA256.match(v) for v in hashes.values())):
        problems.append("hashes must hold exactly " + ", ".join(HASH_FIELDS) + ", each a 64-character lowercase hexadecimal hash")
    if not (isinstance(annotation, dict) and isinstance(annotation.get("annotators"), list) and annotation["annotators"] and all(isinstance(a, str) and _CODE.match(a) for a in annotation["annotators"])
            and len(set(annotation["annotators"])) == len(annotation["annotators"]) and isinstance(annotation.get("adjudicator"), str) and _CODE.match(annotation["adjudicator"])
            and isinstance(annotation.get("independence_attested"), bool) and all(isinstance(annotation.get(k), str) and _SHA256.match(annotation[k])
                                                                                  for k in ("annotator_manifest_sha256", "adjudication_log_sha256"))):
        problems.append("annotation must hold distinct annotator codes, an adjudicator code (codes only: letters, digits, hyphen, underscore), an independence_attested flag, "
                        "an annotator_manifest_sha256 and an adjudication_log_sha256")
    elif annotation["adjudicator"] in annotation["annotators"]:
        problems.append("the adjudicator must be a different person from the annotators")
    if not (isinstance(duplicates, dict) and all(_is_count(duplicates.get(k)) for k in ("exact_removed", "near_duplicates_removed", "cross_split_duplicates_found"))
            and _non_empty(duplicates.get("near_duplicate_method")) and isinstance(duplicates.get("near_duplicate_threshold"), float) and 0.0 < duplicates["near_duplicate_threshold"] <= 1.0):
        problems.append("duplicates must hold exact_removed, near_duplicate_method, near_duplicate_threshold (a float in (0, 1]), near_duplicates_removed and cross_split_duplicates_found")
    elif duplicates["near_duplicate_method"] != NEAR_DUPLICATE_METHOD or duplicates["near_duplicate_threshold"] != NEAR_DUPLICATE_THRESHOLD:
        problems.append(f"duplicates must declare the approved near_duplicate_method '{NEAR_DUPLICATE_METHOD}' and near_duplicate_threshold {NEAR_DUPLICATE_THRESHOLD}")
    elif duplicates.get("exact_method") != EXACT_DUPLICATE_METHOD or duplicates.get("ngram_size") != NGRAM_SIZE or isinstance(duplicates.get("ngram_size"), bool):
        problems.append(f"duplicates must declare the approved exact_method '{EXACT_DUPLICATE_METHOD}' and ngram_size {NGRAM_SIZE}")
    elif duplicates["cross_split_duplicates_found"] != 0:
        problems.append("the manifest itself records cross-split duplicates")
    if not (_is_count(m["record_count"]) and isinstance(m["split_counts"], dict) and set(m["split_counts"]) == set(SPLITS) and all(_is_count(v) for v in m["split_counts"].values())):
        problems.append("record_count and split_counts (train, calibration, heldout) must be non-negative integers")
    if not (isinstance(m["group_dimensions"], list) and all(isinstance(d, str) and d for d in m["group_dimensions"]) and len(set(m["group_dimensions"])) == len(m["group_dimensions"])):
        problems.append("group_dimensions must be a list of distinct names")
    elif set(m["group_dimensions"]) - set(APPROVED_GROUP_DIMENSIONS):
        problems.append("group_dimensions may only be drawn from " + ", ".join(APPROVED_GROUP_DIMENSIONS))
    status, register = m["data_status"], m["participant_register"]
    if status not in DATA_STATUSES:
        problems.append("data_status must be 'synthetic' or 'consented'")
    elif isinstance(m["synthetic"], bool) and m["synthetic"] != (status == "synthetic"):
        problems.append("data_status and the synthetic flag disagree")
    if not (isinstance(register, dict) and set(register) == set(REGISTER_FIELDS) and all(isinstance(register[k], str) and _SHA256.match(register[k]) for k in ("sha256", "verifier_sha256"))
            and (register["consent_wording_sha256"] is None or (isinstance(register["consent_wording_sha256"], str) and _SHA256.match(register["consent_wording_sha256"])))):
        problems.append("participant_register must hold exactly " + ", ".join(REGISTER_FIELDS) + " (64-character lowercase hexadecimal hashes; the consent hash may be null)")
    elif status in DATA_STATUSES and (register["consent_wording_sha256"] is None) != (status == "synthetic"):
        problems.append("consent_wording_sha256 must be present exactly when the data is consented")
    calibration = m["calibration"]
    if not (isinstance(calibration, dict) and set(calibration) == set(CALIBRATION_FIELDS) and isinstance(calibration["split_sha256"], str) and _SHA256.match(calibration["split_sha256"])
            and calibration["temperature_policy_version"] == TEMPERATURE_POLICY_VERSION and calibration["fit_split"] == TEMPERATURE_FIT_SPLIT and calibration["method"] == TEMPERATURE_METHOD
            and calibration["bins"] == OWNER_APPROVED_POLICY["bins"] and not isinstance(calibration["bins"], bool) and calibration["min_scored"] == OWNER_APPROVED_POLICY["min_calibration_sample"]
            and not isinstance(calibration["min_scored"], bool)):
        problems.append(f"calibration must hold exactly {', '.join(CALIBRATION_FIELDS)} with the approved temperature policy '{TEMPERATURE_POLICY_VERSION}' fitted on the "
                        f"'{TEMPERATURE_FIT_SPLIT}' split, {OWNER_APPROVED_POLICY['bins']} bins and a minimum of {OWNER_APPROVED_POLICY['min_calibration_sample']} scored examples")
    markers = sum(1 for key, value in _strings(m) if not _SHA256.match(value) and (re.search(r"@|https?://|www\.", value, re.IGNORECASE)
                                                                                    or (key not in _NOT_CHECKED_FOR_DIGITS and re.search(r"\d[\d\s-]{6,}\d", value))))
    if markers:
        problems.append(f"{markers} manifest string(s) look like personal data (an e-mail address, a link or a long digit run): the manifest must not carry personal data")
    return problems


def load_frozen_evaluation(manifest_path: Path, records_path: Path, rubric_path: Path, annotator_manifest_path: Path, adjudication_log_path: Path, participant_register_path: Path, *,
                           as_of: date | None = None) -> FrozenEvaluation:
    """Verify and load an approved frozen set. All six files are required: every hash in the manifest is checked against the file or the recomputed value, never trusted. The participant register
    must be valid on `as_of` (default: the day the manifest was frozen) and agree with the manifest."""
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise FrozenEvaluationError("the manifest could not be read as JSON") from None
    problems = _manifest_problems(manifest)
    if problems:
        raise FrozenEvaluationError("the manifest is not valid: " + "; ".join(problems))
    if manifest_hash(manifest) != manifest["manifest_sha256"]:
        raise FrozenEvaluationError("the manifest does not match its own manifest_sha256 (it was changed after it was frozen)")
    problems = []
    for what, path, expected in (("records file", records_path, manifest["records_file"]["sha256"]), ("rubric", rubric_path, manifest["rubric"]["sha256"]),
                                 ("annotator manifest", annotator_manifest_path, manifest["annotation"]["annotator_manifest_sha256"]),
                                 ("adjudication log", adjudication_log_path, manifest["annotation"]["adjudication_log_sha256"]),
                                 ("participant register", participant_register_path, manifest["participant_register"]["sha256"])):
        try:
            if sha256_file(path) != expected:
                problems.append(f"the {what} does not match its manifest SHA-256")
        except OSError:
            problems.append(f"the {what} could not be read")
    if problems:
        raise FrozenEvaluationError("; ".join(problems))
    try:
        annotator_manifest = json.loads(Path(annotator_manifest_path).read_text(encoding="utf-8"))
    except ValueError:
        raise FrozenEvaluationError("the annotator manifest could not be read as JSON") from None
    annotation = manifest["annotation"]
    if not (isinstance(annotator_manifest, dict) and annotator_manifest.get("annotators") == annotation["annotators"] and annotator_manifest.get("adjudicator") == annotation["adjudicator"]
            and annotator_manifest.get("independence_attested") == annotation["independence_attested"]):
        raise FrozenEvaluationError("the annotator manifest does not agree with the annotators, adjudicator and independence statement in the manifest")

    try:
        register = json.loads(Path(participant_register_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise FrozenEvaluationError("the participant register could not be read as JSON") from None
    try:
        authorized_on = as_of or date.fromisoformat(manifest["created_at"][:10])
    except ValueError:
        raise FrozenEvaluationError("'created_at' is not a real date") from None
    try:
        summary = validate_register(register, as_of=authorized_on)
    except RegisterError as exc:
        raise FrozenEvaluationError(str(exc)) from None
    disagreements = []
    if summary["data_status"] != manifest["data_status"]:
        disagreements.append("the data status")
    if summary["dataset_scope"] != manifest["dataset_id"]:
        disagreements.append("the permitted dataset scope")
    if summary["annotators"] != sorted(annotation["annotators"]) or summary["adjudicator"] != annotation["adjudicator"]:
        disagreements.append("the annotator and adjudicator codes")
    if verifier_hash(register) != manifest["participant_register"]["verifier_sha256"]:
        disagreements.append("the de-identification verifier hash")
    if consent_wording_hash(register) != manifest["participant_register"]["consent_wording_sha256"]:
        disagreements.append("the consent wording hash")
    if disagreements:
        raise FrozenEvaluationError("the participant register does not agree with the manifest on " + ", ".join(disagreements))

    labels = ("positive", "negative", "neutral")
    dimensions, annotators = set(manifest["group_dimensions"]), set(annotation["annotators"])
    by_split: dict[str, list[FrozenRecord]] = {split: [] for split in SPLITS}
    bad = {"line": 0, "label": 0, "split": 0, "text": 0, "groups": 0, "annotator_labels": 0}
    seen_ids: set[str] = set()
    duplicate_ids = 0
    for line in Path(records_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            item_id, text, label, split, groups = raw["id"], raw["text"], raw["label"], raw["split"], raw.get("groups", {})
            given = raw.get("annotator_labels", {})
        except (ValueError, KeyError, TypeError):
            bad["line"] += 1
            continue
        if not isinstance(item_id, str) or not item_id:
            bad["line"] += 1
            continue
        if item_id in seen_ids:
            duplicate_ids += 1
            continue
        seen_ids.add(item_id)
        try:
            cleaned = validate_text(text)
        except UserTextError:
            cleaned = None
        if not cleaned:
            bad["text"] += 1
            continue
        if label not in labels:
            bad["label"] += 1
            continue
        if split not in SPLITS:
            bad["split"] += 1
            continue
        if not (isinstance(groups, dict) and set(groups) <= dimensions and all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in groups.values())):
            bad["groups"] += 1
            continue
        if not (isinstance(given, dict) and set(given) <= annotators and all(v in labels for v in given.values())):
            bad["annotator_labels"] += 1
            continue
        by_split[split].append(FrozenRecord(item_id, cleaned, label, split, {d: tuple(v) for d, v in sorted(groups.items())}, dict(sorted(given.items()))))
    problems = [f"{count} record(s) with an invalid {what}" for what, count in bad.items() if count] + ([f"{duplicate_ids} duplicate item id(s)"] if duplicate_ids else [])

    everything = [r for split in SPLITS for r in by_split[split]]
    recomputed = record_hashes(everything)
    for name in HASH_FIELDS:
        if recomputed[name] != manifest["hashes"][name]:
            problems.append(f"the recomputed {name} does not match the manifest")
    if calibration_split_hash(by_split["calibration"]) != manifest["calibration"]["split_sha256"]:
        problems.append("the recomputed calibration split hash does not match the manifest")
    total = len(everything)
    if total != manifest["record_count"]:
        problems.append(f"record_count says {manifest['record_count']} but {total} valid records were read")
    for split in SPLITS:
        if len(by_split[split]) != manifest["split_counts"][split]:
            problems.append(f"split_counts['{split}'] says {manifest['split_counts'][split]} but {len(by_split[split])} were read")
        if not by_split[split]:
            problems.append(f"the '{split}' split is empty: separate training, calibration and held-out splits are required")
        counts = {label: sum(1 for r in by_split[split] if r.label == label) for label in labels}
        declared = manifest["class_counts"].get(split) if isinstance(manifest["class_counts"], dict) else None
        if declared != counts:
            problems.append(f"class_counts for '{split}' do not match the records")

    exact_inside = exact_across = near = 0
    first_split: dict[str, str] = {}
    for split in SPLITS:
        for record in by_split[split]:
            key = text_hash(record.text)
            if key in first_split:
                if first_split[key] == split:
                    exact_inside += 1
                else:
                    exact_across += 1
            else:
                first_split[key] = split
    threshold = manifest["duplicates"]["near_duplicate_threshold"]
    token_sets = {split: [(r.item_id, char_ngrams(r.text)) for r in by_split[split]] for split in SPLITS}
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            for _, ta in token_sets[a]:
                near += sum(1 for _, tb in token_sets[b] if _jaccard(ta, tb) >= threshold)
    if exact_inside:
        problems.append(f"{exact_inside} exact duplicate(s) inside a split")
    if exact_across:
        problems.append(f"{exact_across} exact duplicate(s) across splits")
    if near:
        problems.append(f"{near} cross-split pair(s) at or above the declared near-duplicate similarity threshold")
    if problems:
        raise FrozenEvaluationError("; ".join(problems))

    rubric = manifest["rubric"]
    rubric_ready = bool(rubric["frozen"] and rubric["approved"] and not rubric["version"].endswith("draft"))
    evidence = EvidenceBasis(dataset_approved=manifest["approved"], development_fixture=manifest["development_fixture"], synthetic=manifest["synthetic"], rubric_frozen=rubric_ready,
                             manifest_hashes_verified=True, independence_attested=annotation["independence_attested"], duplicates_excluded=True, splits_separate=True)
    computed_status = evidence.describe()["status"]
    if manifest["evidence_basis_status"] != computed_status:
        raise FrozenEvaluationError(f"the manifest declares evidence_basis_status '{manifest['evidence_basis_status']}' but the verified checks give '{computed_status}'")
    checks = {"manifest_sha256_verified": True, "records_sha256_verified": True, "rubric_sha256_verified": True, "annotator_manifest_verified": True, "adjudication_log_sha256_verified": True,
              "content_label_id_split_hashes_verified": True, "no_personal_data_markers": True, "record_shape_valid": True, "counts_consistent": True, "three_splits_present": True,
              "exact_duplicates_excluded": True, "near_duplicates_excluded": True, "evidence_status_consistent": True, "rubric_frozen_and_approved": rubric_ready,
              "participant_register_verified": True, "register_consistent_with_manifest": True, "calibration_split_sha256_verified": True, "group_dimensions_approved": True,
              "duplicate_policy_declared": True}
    ordered = {split: tuple(sorted(by_split[split], key=lambda r: r.item_id)) for split in SPLITS}
    return FrozenEvaluation(manifest, ordered, evidence, checks)


def heldout_eval_records(frozen: FrozenEvaluation, predictions: Mapping[str, str | None], probabilities: Mapping[str, Mapping[str, float]] | None = None) -> list[EvalRecord]:
    """One `EvalRecord` per held-out example from a candidate's predictions (None = abstained). The predictions must cover the held-out ids exactly: a missing or extra id is an error, never a
    silent skip or a default. The labels used are the adjudicated reference labels."""
    heldout = frozen.records["heldout"]
    ids = {r.item_id for r in heldout}
    if set(predictions) != ids:
        raise ValueError(f"the predictions must cover exactly the held-out ids: {len(ids - set(predictions))} missing, {len(set(predictions) - ids)} unexpected")
    if probabilities is not None and not set(probabilities) <= ids:
        raise ValueError("probabilities were given for ids that are not in the held-out split")
    return [EvalRecord(r.item_id, r.label, predictions[r.item_id], None if probabilities is None else probabilities.get(r.item_id), dict(r.groups)) for r in heldout]


def calibration_eval_records(frozen: FrozenEvaluation, probabilities: Mapping[str, Mapping[str, float]] | None) -> list[EvalRecord]:
    """One `EvalRecord` per CALIBRATION-split example, carrying the candidate's probabilities (None for a labels-only candidate). They are used only to fit the temperature (D13): the adjudicated label is
    the truth and no prediction is attached. The probabilities must cover exactly the calibration ids: a missing or extra id is an error, never a silent skip."""
    calibration = frozen.records["calibration"]
    if probabilities is None:
        return [EvalRecord(r.item_id, r.label, None, None, {}) for r in calibration]
    ids = {r.item_id for r in calibration}
    if set(probabilities) != ids:
        raise ValueError(f"the calibration probabilities must cover exactly the calibration ids: {len(ids - set(probabilities))} missing, {len(set(probabilities) - ids)} unexpected")
    return [EvalRecord(r.item_id, r.label, None, probabilities[r.item_id], {}) for r in calibration]


def heldout_annotator_ratings(frozen: FrozenEvaluation) -> dict[str, list[str]]:
    """The independent PRE-adjudication labels of the held-out split, by annotator code, in item-id order (for `agreement_report`). Every held-out record must carry a label from every annotator."""
    codes = sorted(frozen.manifest["annotation"]["annotators"])
    ratings: dict[str, list[str]] = {code: [] for code in codes}
    for record in frozen.records["heldout"]:
        if set(record.annotator_labels) != set(codes):
            raise ValueError("every held-out record needs a pre-adjudication label from every annotator")
        for code in codes:
            ratings[code].append(record.annotator_labels[code])
    return ratings


def evaluate_frozen(frozen: FrozenEvaluation, predictions: Mapping[str, str | None], *, plan: StatisticsPlan, policy: EvaluationPolicy,
                    probabilities: Mapping[str, Mapping[str, float]] | None = None, calibration_probabilities: Mapping[str, Mapping[str, float]] | None = None) -> dict:
    """The complete report for one candidate on the held-out split, with the evidence basis taken from the verified manifest. It evaluates and prints; it does not enable, rank or select anything,
    and it contains no record text (only counts, ids are never echoed)."""
    records = heldout_eval_records(frozen, predictions, probabilities)
    agreement = agreement_report(heldout_annotator_ratings(frozen), labels=policy.primary_labels, plan=plan, policy=policy) if len(frozen.manifest["annotation"]["annotators"]) >= 2 else None
    temperature = temperature_calibration_report(calibration_eval_records(frozen, calibration_probabilities), records, labels=policy.primary_labels, plan=plan, evidence=frozen.evidence, policy=policy)
    report = evaluation_report(records, labels=policy.primary_labels, plan=plan, evidence=frozen.evidence, policy=policy, agreement=agreement, calibration_fit=temperature["fit"])
    return {**report, "temperature_calibration": temperature, "manifest": {"dataset_id": frozen.manifest["dataset_id"], "dataset_version": frozen.manifest["dataset_version"], "dataset_purpose": frozen.manifest["dataset_purpose"],
                                   "manifest_sha256": frozen.manifest["manifest_sha256"], "checks": dict(frozen.checks)}, "agreement": agreement}
