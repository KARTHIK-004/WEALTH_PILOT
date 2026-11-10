"""Writing a sentiment-model artifact in the exact shape `core/sentiment_model.verify_artifact` demands, so the writer and the loader cannot drift: `write_artifact` ends by running the
loader's own verification on what it wrote. Weights and tokenizer files are produced by the training run and passed in by path; this module hashes and describes them.

An artifact is "validated" only when every piece of evidence the loader requires is present: a held-out test split, the duplicate-leakage check, a documented dataset licence, a metrics
file, and a calibrated temperature with a documented minimum confidence. `decide_validation` is the single place that decides, and it refuses by default.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from wealthpilot.core.sentiment_model import (CONFIG_FILE, LABEL_MAP_FILE, METADATA_FILE, METADATA_SCHEMA_VERSION, TOKENIZER_CONFIG_FILE, WEIGHTS_FILE, ArtifactInfo, manifest_sha256,
                                              verify_artifact)

from training.sentiment.config import MIN_TEST_SAMPLES_FOR_VALIDATED, PREPROCESSING_VERSION

METRICS_FILE = "metrics.json"
CONFUSION_FILE = "confusion_matrix.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def decide_validation(*, test_samples: int, held_out_test: bool, duplicate_leakage_checked: bool, dataset_license: str, development_fixture: bool, calibrated: bool,
                      threshold_found: bool) -> tuple[str, list[str]]:
    """("validated" | "unvalidated", the reasons it is not). Validated needs ALL of the evidence; a development fixture can never validate anything."""
    reasons = []
    if development_fixture:
        reasons.append("the data is a development fixture, not a labelled evaluation set")
    if test_samples < MIN_TEST_SAMPLES_FOR_VALIDATED:
        reasons.append(f"the held-out test split has {test_samples} examples (< {MIN_TEST_SAMPLES_FOR_VALIDATED})")
    if not held_out_test:
        reasons.append("no held-out test split")
    if not duplicate_leakage_checked:
        reasons.append("duplicate leakage was not checked")
    if not dataset_license.strip():
        reasons.append("the dataset licence is not documented")
    if not calibrated:
        reasons.append("the model is not calibrated")
    if not threshold_found:
        reasons.append("no abstention threshold met the owner's precision and coverage targets")
    return ("validated" if not reasons else "unvalidated"), reasons


def write_artifact(directory: Path, *, model_name: str, model_version: str, base_model: str, base_model_revision: str, base_model_license: str, dataset_id: str, dataset_license: str,
                   labels: tuple[str, ...], vocab_size: int, tokenizer_length: int, tokenizer_identifier: str, tokenizer_revision: str, training_library_versions: dict,
                   temperature: float | None, min_confidence: float | None, band_cutoffs: tuple[float, float] | None, validation_status: str,
                   validation_reasons: list[str], metrics: dict, extra_files: list[str], test_samples: int, held_out_test: bool, duplicate_leakage_checked: bool,
                   regression: dict | None = None, seed: int = 42, max_tokens: int = 128) -> ArtifactInfo:
    """`directory` must already hold `model.safetensors`, `config.json`, `tokenizer_config.json` and the other tokenizer files named in `extra_files`.

    Every value that describes where the artifact came from is REQUIRED and is supplied by the caller (the trainer reports what it actually loaded); none is defaulted or invented here:
    `base_model` (the exact model identifier) with its `base_model_revision`, the tokenizer's `tokenizer_identifier` and `tokenizer_revision` (immutable 40-character lowercase commit hashes),
    and `training_library_versions` (it must name torch, transformers, tokenizers and safetensors). The metadata is written as `metadata_schema_version` 1 with a `manifest_sha256` over the
    `files` map. The function ends with the loader's own verification, so a missing or malformed value fails here, as `artifact_incompatible`, instead of at first use.

    `vocab_size` is the model's `config.vocab_size` (the embedding matrix); `tokenizer_length` is `len(tokenizer)` of the tokenizer written with the model. They are recorded separately
    and are NOT required to be equal (a padded embedding matrix is valid) but the tokenizer may not be LONGER than the matrix; the loader compares `tokenizer_length` with the length of the
    tokenizer it loads."""
    (directory / LABEL_MAP_FILE).write_text(json.dumps({label: i for i, label in enumerate(labels)}, indent=2) + "\n", encoding="utf-8")
    (directory / METRICS_FILE).write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / CONFUSION_FILE).write_text(json.dumps(metrics.get("test", {}).get("confusion_matrix", {}), indent=2) + "\n", encoding="utf-8")
    names = sorted({WEIGHTS_FILE, CONFIG_FILE, TOKENIZER_CONFIG_FILE, LABEL_MAP_FILE, METRICS_FILE, CONFUSION_FILE, *extra_files})
    calibrated = temperature is not None and min_confidence is not None and band_cutoffs is not None
    files = {name: sha256_file(directory / name) for name in names}
    metadata = {
        "metadata_schema_version": METADATA_SCHEMA_VERSION,
        "model_name": model_name, "model_version": model_version, "base_model": base_model, "base_model_revision": base_model_revision, "base_model_license": base_model_license,
        "dataset_id": dataset_id, "dataset_license": dataset_license,
        "training_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "preprocessing_version": PREPROCESSING_VERSION, "labels": list(labels), "seed": seed,
        "max_tokens_trained": max_tokens, "library_versions": dict(training_library_versions),
        "determinism_note": "Seeds are fixed; GPU kernels and some CPU thread schedules can still make runs differ slightly.",
        "tokenizer": {"identifier": tokenizer_identifier, "revision": tokenizer_revision, "vocab_size": vocab_size, "length": tokenizer_length,
                      "files": [n for n in names if n not in (WEIGHTS_FILE, CONFIG_FILE, LABEL_MAP_FILE, METRICS_FILE, CONFUSION_FILE)]},
        "validation_status": validation_status, "validation_reasons_not_validated": validation_reasons,
        "validation": {"dataset_id": dataset_id, "dataset_license": dataset_license, "test_samples": test_samples, "held_out_test": held_out_test,
                       "duplicate_leakage_checked": duplicate_leakage_checked, "macro_f1": metrics.get("test", {}).get("macro_f1"), "metrics_file": METRICS_FILE},
        "calibration": ({"status": "calibrated", "method": "temperature_scaling_on_validation_split", "temperature": temperature, "min_confidence": min_confidence,
                         "band_cutoffs": list(band_cutoffs or ()), "ece_test": metrics.get("calibration", {}).get("ece_after")} if calibrated else {"status": "uncalibrated"}),
        "regression": regression or {"available": False, "validated": False, "reason": "no validated regression head; intensity is null"},
        "files": files,
        "manifest_sha256": manifest_sha256(files),
    }
    (directory / METADATA_FILE).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    # the loader's own verification of what was just written; the artifact root check is by-passed here (the caller names the directory), everything else is enforced
    return verify_artifact(directory.resolve(), expected_version=model_version, expected_name=model_name, max_tokens=max_tokens)
