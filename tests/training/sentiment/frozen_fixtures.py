"""Shared fixture builder for the frozen-set tests (ADR-052): generates a complete frozen set (manifest, records, rubric, annotator manifest, adjudication log) inside a test directory from invented
`zq...` tokens. No real dataset, model or user text exists or is read; the hashes are computed here independently of the module under test. Imported through the directory's conftest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from training.sentiment import frozen_evaluation as fe
from training.sentiment.frozen_evaluation import load_frozen_evaluation
from register_fixtures import valid_register

LABELS = ("positive", "negative", "neutral")
ALPHABET = "abcdefghijklmnopqrstuvwxyz"


def word(n: int) -> str:
    """A letters-only token that is unique per n (digits would be shared tokens)."""
    out = ""
    for _ in range(5):
        out += ALPHABET[n % 26]
        n //= 26
    return "zq" + out


def sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def canonical_hash(manifest: dict) -> str:
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class Built:
    def __init__(self, directory: Path, manifest: dict, records: list[dict]):
        self.directory, self.manifest, self.records = directory, manifest, records
        self.manifest_path, self.records_path = directory / "manifest.json", directory / "records.jsonl"
        self.rubric_path, self.annotators_path, self.log_path = directory / "rubric.md", directory / "annotators.json", directory / "adjudication_log.txt"
        self.register_path = directory / "register.json"

    def load(self):
        return load_frozen_evaluation(self.manifest_path, self.records_path, self.rubric_path, self.annotators_path, self.log_path, self.register_path)


def build(directory: Path, *, train: int = 90, calibration: int = 30, heldout: int = 99, approved: bool = True, fixture: bool = False, synthetic: bool = False, rubric_frozen: bool = True,
          rubric_approved: bool = True, rubric_version: str = "v1", independence: bool = True, threshold: float = 0.9, extra_lines: tuple[str, ...] = (), manifest_edit=None, record_edit=None,
          declared_status: str | None = None, post_edit=None, annotator_file_edit=None, register_edit=None, data_status: str | None = None) -> Built:
    directory.mkdir(parents=True, exist_ok=True)
    counter = 0
    records: list[dict] = []
    for split, total in (("train", train), ("calibration", calibration), ("heldout", heldout)):
        for i in range(total):
            label = LABELS[i % 3]
            text = " ".join(word(counter * 5 + k) for k in range(5))
            counter += 1
            second = LABELS[(LABELS.index(label) + 1) % 3] if i % 10 == 0 else label
            records.append({"id": f"{split}-{i:04d}", "text": text, "label": label, "split": split, "groups": {"topic": ["saving" if i % 2 else "debt"], "difficulty": ["hard" if i % 5 == 0 else "easy"]},
                            "annotator_labels": {"ann-a": label, "ann-b": second}})
    if record_edit:
        record_edit(records)
    (directory / "records.jsonl").write_text("\n".join([json.dumps(r) for r in records] + list(extra_lines)) + "\n", encoding="utf-8")
    (directory / "rubric.md").write_text("an invented rubric text\n", encoding="utf-8")
    (directory / "adjudication_log.txt").write_text("an invented adjudication log\n", encoding="utf-8")
    annotators = {"annotators": ["ann-a", "ann-b"], "adjudicator": "adj", "independence_attested": independence}
    if annotator_file_edit:
        annotator_file_edit(annotators)
    (directory / "annotators.json").write_text(json.dumps(annotators), encoding="utf-8")
    status = data_status or ("synthetic" if synthetic else "consented")                       # the fixture's "eligible" path stands for approved real data, which does not exist
    register = valid_register("synthetic" if status == "synthetic" else "consented")
    if register_edit:
        register_edit(register)
    (directory / "register.json").write_text(json.dumps(register), encoding="utf-8")
    verifier_entries = sorted((p for p in register["participants"] if p["role"] == "de_identification_verifier"), key=lambda p: p["code"])
    consent = register["consent_wording"]["sha256"] if register["consent_wording"] else None
    calibration_lines = [f"{r['id']}\t{hashlib.sha256(r['text'].encode('utf-8')).hexdigest()}\t{r['label']}" for r in sorted(records, key=lambda r: r["id"]) if r["split"] == "calibration"]
    ordered = sorted(records, key=lambda r: r["id"])
    counts = {split: sum(1 for r in records if r["split"] == split) for split in fe.SPLITS}
    eligible = approved and not fixture and not synthetic and rubric_frozen and rubric_approved and not rubric_version.endswith("draft") and independence
    manifest = {
        "schema_version": 2, "manifest_status": "FROZEN", "dataset_id": "invented-fixture", "dataset_version": "1", "dataset_purpose": "exercise the frozen-set plumbing on invented tokens",
        "license": "none: invented test tokens", "provenance": {"source": "generated inside the test", "collection_method": "none", "de_identification": "not applicable: no personal data"},
        "approved": approved, "approved_by": "test", "approved_on": "2026-01-01", "development_fixture": fixture, "synthetic": synthetic, "created_at": "2026-01-01T00:00:00Z",
        "rubric": {"version": rubric_version, "sha256": sha((directory / "rubric.md").read_bytes()), "frozen": rubric_frozen, "approved": rubric_approved},
        "records_file": {"name": "records.jsonl", "sha256": sha((directory / "records.jsonl").read_bytes())},
        "hashes": {"record_ids_sha256": digest([r["id"] for r in ordered]),
                   "content_sha256": digest([f"{r['id']}\t{hashlib.sha256(r['text'].encode('utf-8')).hexdigest()}" for r in ordered]),
                   "labels_sha256": digest([f"{r['id']}\t{r['label']}" for r in ordered]), "split_assignments_sha256": digest([f"{r['id']}\t{r['split']}" for r in ordered])},
        "record_count": len(records), "label_set": "positive_negative_neutral", "split_counts": counts,
        "class_counts": {split: {label: sum(1 for r in records if r["split"] == split and r["label"] == label) for label in LABELS} for split in fe.SPLITS},
        "group_dimensions": ["difficulty", "topic"],
        "annotation": {"annotators": ["ann-a", "ann-b"], "adjudicator": "adj", "independence_attested": independence, "annotator_manifest_sha256": sha((directory / "annotators.json").read_bytes()),
                       "adjudication_log_sha256": sha((directory / "adjudication_log.txt").read_bytes())},
        "duplicates": {"exact_removed": 0, "near_duplicate_method": "nfkc_casefold_char5gram_jaccard", "near_duplicate_threshold": threshold, "near_duplicates_removed": 0, "cross_split_duplicates_found": 0,
                       "exact_method": "sha256_of_normalized_text", "ngram_size": 5},
        "data_status": status,
        "participant_register": {"sha256": sha((directory / "register.json").read_bytes()),
                                 "verifier_sha256": hashlib.sha256(json.dumps(verifier_entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest(),
                                 "consent_wording_sha256": consent},
        "calibration": {"split_sha256": digest(calibration_lines), "temperature_policy_version": "d13-temperature-v1", "fit_split": "calibration",
                        "method": "temperature_scaling_nll_on_log_probabilities", "bins": 10, "min_scored": 20},
        "baseline_method_version": "user_text_rules_v1", "evidence_basis_status": declared_status or ("eligible_for_owner_review" if eligible else "not_validation_evidence"),
    }
    if manifest_edit:
        manifest_edit(manifest)
    manifest["manifest_sha256"] = canonical_hash(manifest)
    if post_edit:
        post_edit(manifest)                                                                      # changes AFTER the hash was computed: a tampered manifest
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return Built(directory, manifest, records)


def perfect(frozen) -> dict:
    return {r.item_id: r.label for r in frozen.records["heldout"]}
