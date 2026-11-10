"""Offline fine-tuning of a PRETRAINED Transformer for 3-class sentiment (positive / negative / neutral), then calibration, evaluation and artifact writing (ADR-052).

    python -m training.sentiment.train_sentiment_transformer --check-environment
    python -m training.sentiment.train_sentiment_transformer --manifest <approved manifest.json> --data <labelled.jsonl> --base-model finbert --version sentiment-v1 \\
        --revision <the approved 40-character commit hash of the base model> \\
        --target-precision <owner's number> --min-coverage <owner's number> --high-precision <owner's number> --high-min-coverage <owner's number>

This is a CLASSIFICATION task on a pretrained model. It does not build a language model and it generates no text. It runs only when a human invokes it: never inside an API request, a
LangGraph node, an agent, application start-up or the frontend (`tests/training/sentiment` checks that nothing in `backend/` imports this package).

It REFUSES to run unless: (1) the dataset manifest is complete and APPROVED with a documented licence (`dataset.py`), (2) the deep-learning packages are installed (they are outside the approved
stack: see docs/DECISIONS.md ADR-052 and training/sentiment/README.md), (3) the owner's precision / coverage targets are given as arguments (nothing is defaulted or invented), and
(4) the caller supplies the IMMUTABLE revision of the base model: a full 40-character commit hash (no branch, tag or short hash; no revision and no Hub model is ever defaulted here).
The base model is loaded with `use_safetensors=True`, `trust_remote_code=False` and the supplied revision, and OFFLINE (`local_files_only=True`) unless `--allow-hub-download` is given.
That flag is the ONLY way this package touches the network: the first download of the base model's weights is a network request that needs the project owner's recorded approval.

Reproducibility: seed 42, deterministic hash-based split (`dataset.split_rows`), library versions recorded in the artifact metadata. GPU kernels (and some CPU thread schedules) can still
make two runs differ slightly. Regression (intensity) is NOT trained: it stays disabled until a dataset with documented intensity labels is approved (`--with-regression` is refused).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from wealthpilot.core.sentiment_model import is_commit_hash

from training.sentiment.artifacts import decide_validation, write_artifact
from training.sentiment.config import CANDIDATES, DEFAULT_MAX_TOKENS, LABEL_MAP, LABELS, MODELS_DIR, SEED
from training.sentiment.local_model_dir import LocalModelError, VerifiedModelDirectory, verify_model_directory
from training.sentiment.dataset import DatasetManifest, LabelledRow, ManifestError, check_no_leakage, label_counts, load_manifest, load_rows, split_rows
from training.sentiment.metrics import classification_report, expected_calibration_error, fit_temperature, select_min_confidence, softmax

REQUIRED_PACKAGES = ("torch", "transformers", "tokenizers", "safetensors")


@dataclass
class TrainerOutput:
    """What a trainer hands back after writing `model.safetensors`, `config.json` and the tokenizer files into the output directory."""

    validation_logits: np.ndarray
    test_logits: np.ndarray
    vocab_size: int                  # the model's config.vocab_size (embedding matrix); may be larger than the tokenizer
    tokenizer_length: int            # len(tokenizer): the real length of the tokenizer written with the model, recorded in the artifact and compared with the loaded tokenizer
    tokenizer_files: list[str]
    library_versions: dict[str, str]    # torch, transformers, tokenizers, safetensors (required by the artifact) and numpy, as imported by the trainer
    base_model_revision: str         # the immutable revision the base model was loaded at
    tokenizer_identifier: str        # what the tokenizer was loaded from (the same identifier as the model in this seam)
    tokenizer_revision: str          # and at which immutable revision (the same revision, by construction)


Trainer = Callable[[list[LabelledRow], list[LabelledRow], list[LabelledRow], Path], TrainerOutput]


def check_environment() -> dict:
    missing = [name for name in REQUIRED_PACKAGES if importlib.util.find_spec(name) is None]
    return {"packages_required": list(REQUIRED_PACKAGES), "missing": missing, "ready": not missing,
            "note": "These packages are outside the approved stack (CLAUDE.md section 5); installing them needs the project owner's approval (ADR-052)."}


def _indices(rows: list[LabelledRow]) -> np.ndarray:
    return np.array([LABEL_MAP[r.label] for r in rows])


def run_training(*, manifest: DatasetManifest, data_path: Path, base_model: str, version: str, output_root: Path, trainer: Trainer, target_precision: float, min_coverage: float,
                 high_precision: float, high_min_coverage: float, max_tokens: int = DEFAULT_MAX_TOKENS, seed: int = SEED, allow_development_fixture: bool = False) -> dict:
    """Everything except the heavy fine-tuning itself, which is the injected `trainer` (tests use a fake one, so this whole pipeline is exercised without any deep-learning package)."""
    if base_model not in CANDIDATES or base_model == "rules_baseline":
        raise ManifestError("the base model must be one of the documented candidates")
    if manifest.development_fixture and not allow_development_fixture:
        raise ManifestError("a development fixture is never training data")
    rows, report = load_rows(data_path, manifest)
    fractions = (manifest.split_policy["train"], manifest.split_policy["validation"], manifest.split_policy["test"])
    splits = split_rows(rows, seed, fractions)
    check_no_leakage(splits)
    if not splits.validation or not splits.test or not splits.train:
        raise ManifestError("every split needs examples")

    directory = output_root / version
    directory.mkdir(parents=True, exist_ok=True)
    output = trainer(list(splits.train), list(splits.validation), list(splits.test), directory)

    y_val, y_test = _indices(list(splits.validation)), _indices(list(splits.test))
    temperature = fit_temperature(output.validation_logits, y_val)
    p_raw, p_cal = softmax(output.test_logits), softmax(output.test_logits, temperature)
    p_val = softmax(output.validation_logits, temperature)
    threshold = select_min_confidence(p_val, y_val, target_precision=target_precision, min_coverage=min_coverage)
    high = select_min_confidence(p_val, y_val, target_precision=high_precision, min_coverage=high_min_coverage)
    cutoffs_found = bool(threshold["found"] and high["found"] and threshold["min_confidence"] <= high["min_confidence"])

    test_report = classification_report(y_test, p_cal.argmax(axis=1))
    metrics = {
        "dataset": {"dataset_id": manifest.dataset_id, "version": manifest.version, "license": manifest.license, "url": manifest.url, "language": manifest.language,
                    "domain_note": manifest.domain_note, "limitations": list(manifest.limitations), "development_fixture": manifest.development_fixture,
                    "rows_read": report.read, "rows_kept": report.kept, "skipped": dict(report.skipped), "exact_duplicates_removed": report.exact_duplicates_removed,
                    "conflicting_label_rows_removed": report.conflicting_labels_removed,
                    "splits": {"train": label_counts(splits.train), "validation": label_counts(splits.validation), "test": label_counts(splits.test)}, "seed": seed},
        "test": test_report,
        "calibration": {"temperature": temperature, "fitted_on": "validation split", "ece_before": expected_calibration_error(p_raw, y_test)["ece"],
                        "ece_after": expected_calibration_error(p_cal, y_test)["ece"], "reliability_after": expected_calibration_error(p_cal, y_test)["reliability"]},
        "abstention": {"medium": threshold, "high": high},
        "regression": {"available": False, "reason": "no dataset with documented intensity labels is approved"},
    }
    status, reasons = decide_validation(test_samples=len(splits.test), held_out_test=True, duplicate_leakage_checked=True, dataset_license=manifest.license,
                                        development_fixture=manifest.development_fixture, calibrated=True, threshold_found=cutoffs_found)
    info = write_artifact(
        directory, model_name=base_model, model_version=version, base_model=CANDIDATES[base_model]["hub_id"], base_model_license="to be verified by the project owner from the model card",
        dataset_id=manifest.dataset_id, dataset_license=manifest.license, base_model_revision=output.base_model_revision, tokenizer_identifier=output.tokenizer_identifier, tokenizer_revision=output.tokenizer_revision,
        labels=LABELS, vocab_size=output.vocab_size, tokenizer_length=output.tokenizer_length, temperature=temperature,
        min_confidence=threshold["min_confidence"] if cutoffs_found else None, band_cutoffs=(threshold["min_confidence"], high["min_confidence"]) if cutoffs_found else None,
        validation_status=status, validation_reasons=reasons, metrics=metrics, extra_files=output.tokenizer_files, test_samples=len(splits.test), held_out_test=True,
        duplicate_leakage_checked=True, training_library_versions=output.library_versions, seed=seed, max_tokens=max_tokens)
    return {"directory": str(directory), "validation_status": info.validation_status, "reasons_not_validated": reasons, "macro_f1": test_report["macro_f1"],
            "accuracy": test_report["accuracy"], "temperature": temperature}


class RevisionError(ValueError):
    """The base-model revision is missing or is not an immutable commit hash."""


def validate_revision(revision: object) -> str:
    """The base model must be pinned to an immutable revision: a full 40-character lowercase hexadecimal commit hash, supplied by the caller. A branch name (it moves), a tag (it can be
    moved), a short hash (ambiguous), an empty value and a non-string are all refused. No revision is invented or defaulted anywhere in this package."""
    if not is_commit_hash(revision):
        raise RevisionError("the base-model revision must be a full 40-character lowercase hexadecimal commit hash supplied by the caller (not a branch, a tag, a short hash or empty)")
    return revision


def base_model_loading_kwargs(revision: object, *, allow_hub_download: bool = False) -> dict:
    """Keyword arguments shared by the tokenizer and the model loads of the base model: the immutable revision, `trust_remote_code=False` (no repository code is ever executed) and
    OFFLINE loading (`local_files_only=True`) unless the caller says, explicitly, that the owner-approved first download may use the network. The model load adds `use_safetensors=True`
    (a pickle checkpoint is never read). Whether the library may ask the Hub to convert a checkpoint is NOT controlled here by any documented switch: see the README, "Hub conversion"."""
    return {"revision": validate_revision(revision), "trust_remote_code": False, "local_files_only": not allow_hub_download}


def fine_tune_with_torch(train: list[LabelledRow], validation: list[LabelledRow], test: list[LabelledRow], directory: Path, *, base_model: str, epochs: int, learning_rate: float,
                         batch_size: int, max_tokens: int, seed: int, revision: str | None, allow_hub_download: bool = False, local_model: "VerifiedModelDirectory | None" = None) -> TrainerOutput:
    """The real trainer. CPU only. `revision` (an immutable commit hash, see `validate_revision`) is required and is checked before any package is imported. The base model is read with
    `use_safetensors=True`, `trust_remote_code=False` and offline unless `allow_hub_download` is True (the owner-approved first download). The tests run this function with `epochs=0`
    against a local, randomly initialised stand-in; it has never been run against a real checkpoint (no weights are present)."""
    if local_model is not None:
        # Path B (owner decision C1): the base model is a VERIFIED LOCAL DIRECTORY, never a Hub identifier. The directory is verified again here, nothing can be downloaded, and the recorded
        # provenance is the manifest's identifier and immutable revision (a `revision` argument, if given, must equal it).
        if allow_hub_download or CANDIDATES[base_model]["hub_id"] != local_model.identifier or (revision is not None and revision != local_model.revision):
            raise RevisionError("a local base-model directory cannot be combined with a Hub download, another identifier or another revision")
        local_model = local_model.recheck()
        loading = {"trust_remote_code": False, "local_files_only": True}
        source, hub_id, base_revision = str(local_model.path), local_model.identifier, local_model.revision
    else:
        loading = base_model_loading_kwargs(revision, allow_hub_download=allow_hub_download)
        hub_id = CANDIDATES[base_model]["hub_id"]
        source, base_revision = hub_id, loading["revision"]
    import safetensors
    import tokenizers
    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    transformers.set_seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(source, **loading)
    model = AutoModelForSequenceClassification.from_pretrained(source, **loading, use_safetensors=True, num_labels=len(LABELS), id2label={i: l for i, l in enumerate(LABELS)},
                                                                label2id=dict(LABEL_MAP), ignore_mismatched_sizes=True)
    device = torch.device("cpu")
    model.to(device)

    def encode(rows: list[LabelledRow]):  # noqa: ANN202
        return tokenizer([r.text for r in rows], truncation=True, max_length=max_tokens, padding=True, return_tensors="pt")

    def logits_for(rows: list[LabelledRow]) -> np.ndarray:
        model.eval()
        out = []
        with torch.inference_mode():
            for start in range(0, len(rows), batch_size):
                batch = encode(rows[start:start + batch_size])
                out.append(model(**batch).logits.cpu().numpy())
        return np.concatenate(out)

    optimiser = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    steps = epochs * ((len(train) + batch_size - 1) // batch_size)
    schedule = get_linear_schedule_with_warmup(optimiser, int(0.1 * steps), steps)
    generator = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        model.train()
        order = torch.randperm(len(train), generator=generator).tolist()
        for start in range(0, len(order), batch_size):
            rows = [train[i] for i in order[start:start + batch_size]]
            batch = encode(rows)
            labels = torch.tensor([LABEL_MAP[r.label] for r in rows])
            loss = model(**batch, labels=labels).loss
            loss.backward()
            optimiser.step()
            schedule.step()
            optimiser.zero_grad()
    model.save_pretrained(directory)                      # transformers 5.x writes safetensors only; the 4.x `safe_serialization` argument no longer exists (tests/training/sentiment)
    tokenizer.save_pretrained(directory)
    tokenizer_files = sorted(p.name for p in directory.iterdir() if p.is_file() and p.name not in ("model.safetensors", "config.json", "generation_config.json"))
    versions = {"torch": torch.__version__, "transformers": transformers.__version__, "tokenizers": tokenizers.__version__, "safetensors": safetensors.__version__, "numpy": np.__version__}
    # provenance: what was actually loaded (the identifier and the immutable revision of the model and of its tokenizer), never a second value that could differ from it
    return TrainerOutput(logits_for(validation), logits_for(test), int(model.config.vocab_size), len(tokenizer), tokenizer_files, versions,
                         base_model_revision=base_revision, tokenizer_identifier=hub_id, tokenizer_revision=base_revision)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check-environment", action="store_true", help="report whether the required packages are installed; train nothing")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--data", type=Path, help="labelled JSON Lines file (under datasets/raw/sentiment/)")
    parser.add_argument("--base-model", choices=[c for c in CANDIDATES if c != "rules_baseline"])
    parser.add_argument("--version", help="artifact version, e.g. sentiment-v1")
    parser.add_argument("--output-root", type=Path, default=MODELS_DIR)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--target-precision", type=float, help="OWNER'S target precision of accepted predictions (required)")
    parser.add_argument("--min-coverage", type=float, help="OWNER'S minimum share of examples that must be answered at that precision (required)")
    parser.add_argument("--high-precision", type=float, help="OWNER'S target precision for the 'high' confidence band (required)")
    parser.add_argument("--high-min-coverage", type=float, help="OWNER'S minimum coverage for the 'high' band (required)")
    parser.add_argument("--revision", help="the approved IMMUTABLE revision of the base model: a full 40-character lowercase commit hash (required; never defaulted; a branch or tag is refused)")
    parser.add_argument("--allow-hub-download", action="store_true",
                        help="permit the owner-approved first download of the base model from its hub; without it the base model is read offline (local_files_only) and nothing touches the network")
    parser.add_argument("--local-model-dir", type=Path, help="Path B: a VERIFIED LOCAL directory holding exactly the five approved base-model files (replaces the Hub; needs --local-model-manifest)")
    parser.add_argument("--local-model-manifest", type=Path, help="Path B: the frozen manifest of that directory (identifier, immutable revision, SHA-256 and size of every file)")
    parser.add_argument("--with-regression", action="store_true", help="refused: no intensity-labelled dataset is approved")
    args = parser.parse_args(argv)

    if args.check_environment:
        status = check_environment()
        print(json.dumps(status, indent=2))
        return 0 if status["ready"] else 2
    if args.with_regression:
        print("REFUSED: the regression head is disabled until a dataset with documented intensity labels is approved.", file=sys.stderr)
        return 2
    local = args.local_model_dir is not None or args.local_model_manifest is not None
    needed = ("manifest", "data", "base_model", "version", "target_precision", "min_coverage", "high_precision", "high_min_coverage") + (() if local else ("revision",))
    absent = [name for name in needed if getattr(args, name) is None]
    if local and (args.local_model_dir is None or args.local_model_manifest is None):
        absent += [name for name in ("local_model_dir", "local_model_manifest") if getattr(args, name) is None]
    if absent:
        print("REFUSED: required arguments missing: " + ", ".join(f"--{n.replace('_', '-')}" for n in absent), file=sys.stderr)
        return 2
    verified_local = None
    try:
        if local:
            if args.allow_hub_download:
                raise RevisionError("a local base-model directory cannot be combined with --allow-hub-download")
            if args.revision is not None:
                validate_revision(args.revision)
            verified_local = verify_model_directory(args.local_model_dir, json.loads(args.local_model_manifest.read_text(encoding="utf-8")), identifier=CANDIDATES[args.base_model]["hub_id"],
                                                    revision=args.revision)
        else:
            validate_revision(args.revision)
    except (RevisionError, LocalModelError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc if isinstance(exc, (RevisionError, LocalModelError)) else 'the local model manifest could not be read as JSON'}", file=sys.stderr)
        return 2
    environment = check_environment()
    if not environment["ready"]:
        print("REFUSED: required packages are not installed: " + ", ".join(environment["missing"]) + ". " + environment["note"], file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(args.manifest)
        result = run_training(
            manifest=manifest, data_path=args.data, base_model=args.base_model, version=args.version, output_root=args.output_root, target_precision=args.target_precision,
            min_coverage=args.min_coverage, high_precision=args.high_precision, high_min_coverage=args.high_min_coverage, max_tokens=args.max_tokens,
            trainer=lambda tr, va, te, directory: fine_tune_with_torch(tr, va, te, directory, base_model=args.base_model, epochs=args.epochs, learning_rate=args.learning_rate,
                                                                          batch_size=args.batch_size, max_tokens=args.max_tokens, seed=SEED, revision=args.revision,
                                                                          allow_hub_download=args.allow_hub_download, local_model=verified_local))
    except ManifestError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
