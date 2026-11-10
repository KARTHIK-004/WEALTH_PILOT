"""Evaluate sentiment candidates on the HELD-OUT test split of an approved labelled dataset (ADR-052). Nothing is assumed best: every candidate is scored the same way.

    python -m training.sentiment.evaluate_sentiment_model --manifest <approved manifest.json> --data <labelled.jsonl> --candidate rules_baseline \\
        --candidate models/sentiment/finbert-v1 --candidate models/sentiment/distilroberta-v1 --output <report.json>

- `rules_baseline` needs nothing installed: it runs the project's own pipeline (`analyse_user_text`) on each test text. It may ABSTAIN (mixed / uncertain / insufficient evidence are
  not classes of a Transformer head); both views are reported: metrics on the answered examples with the coverage, and a strict view in which an abstention counts as wrong.
- an artifact directory (under models/sentiment/) is scored with its own tokenizer and weights; that needs the deep-learning packages (outside the approved stack).
- the split is the training split's: same dataset, seed and fractions, so the test set is held out from any candidate trained with `train_sentiment_transformer.py`. An artifact trained on a
  different dataset id is refused.

The output states measured numbers only. Choosing a final model is a decision for the project owner, made from this report (macro-F1, per-class recall, calibration, coverage), not
from a model's popularity; an artifact is still only "validated" when its own metadata carries the full evidence (core/sentiment_model.py).

FROZEN-SET MODE (owner decision `APPROVE_SCHEMA_AND_WIRE_OFFLINE`, 2026-10-29). Given the five files of an approved frozen set, the script evaluates on the held-out split ONLY through the validated manifest
interface of `frozen_evaluation.py`:

    python -m training.sentiment.evaluate_sentiment_model --frozen-manifest <manifest.json> --records <records.jsonl> --rubric <rubric> --annotator-manifest <annotators.json> \
        --adjudication-log <log> [--candidate rules_baseline] [--predictions NAME=<predictions.json>] --output <report.json>

Every hash is verified before anything is evaluated; the evidence basis comes from the verified manifest alone (there is no command-line way to state it); the plan and policy are the owner-approved ones,
passed explicitly. Candidates are `rules_baseline` and precomputed predictions files (a JSON object of held-out id -> label or null, or id -> {label, probabilities}: owner decision E2, calibration needs
probabilities, so a labels-only candidate stays descriptive-only and the rules baseline can never be `validated`); an artifact directory is REFUSED here (a model needs R6 / R7, D10 to
D13 first). The report contains no record text and no record id, is `not_validation_evidence` unless the manifest and every check support more, ranks and selects nothing, recommends no activation, and the
exit status never depends on a target. No real manifest or dataset exists; the mode is exercised only on local synthetic fixtures.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

from training.sentiment.config import LABEL_MAP, LABELS, MODELS_DIR, SEED
from training.sentiment.dataset import DatasetManifest, LabelledRow, ManifestError, check_no_leakage, label_counts, load_manifest, load_rows, split_rows
from training.sentiment.frozen_evaluation import FrozenEvaluation, FrozenEvaluationError, evaluate_frozen, load_frozen_evaluation
from training.sentiment.local_model_dir import LocalModelError, load_classifier, predictions_payload, verify_model_directory
from training.sentiment.metrics import EvaluationPolicy, StatisticsPlan, classification_report, compare_predictions, expected_calibration_error, softmax

from wealthpilot.core.sentiment_model import ModelUnavailable
from wealthpilot.core.user_text_sentiment import METHOD_VERSION, analyse_user_text


def test_split(manifest: DatasetManifest, data_path: Path, seed: int = SEED) -> tuple[list[LabelledRow], dict]:
    rows, report = load_rows(data_path, manifest)
    splits = split_rows(rows, seed, (manifest.split_policy["train"], manifest.split_policy["validation"], manifest.split_policy["test"]))
    check_no_leakage(splits)
    if not splits.test:
        raise ManifestError("the test split is empty")
    return list(splits.test), {"rows_kept": report.kept, "test": label_counts(splits.test), "seed": seed}


def evaluate_rules_baseline(test: list[LabelledRow]) -> dict:
    """The deterministic baseline scored like a classifier: positive / negative / neutral are its answers; anything else (mixed, uncertain, insufficient evidence) is an abstention."""
    predictions, answered = [], []
    for row in test:
        label = analyse_user_text(row.text).sentiment
        if label in LABELS:
            predictions.append(LABEL_MAP[label])
            answered.append(True)
        else:
            predictions.append(-1)
            answered.append(False)
    y = np.array([LABEL_MAP[r.label] for r in test])
    p, mask = np.array(predictions), np.array(answered)
    on_answered = classification_report(y[mask], p[mask]) if mask.any() else None
    return {"candidate": "rules_baseline", "version": METHOD_VERSION, "samples": len(test), "coverage": float(mask.mean()), "abstained": int((~mask).sum()),
            "metrics_on_answered": on_answered, "strict_accuracy_abstention_counts_wrong": float((p == y).mean()),
            "calibration": "not applicable: the rules baseline reports no probability", "note": "unvalidated baseline; the labels are the dataset's, not the project's own"}


def evaluate_artifact(directory: Path, test: list[LabelledRow], manifest: DatasetManifest) -> dict:
    """Needs the deep-learning packages. Scores one trained artifact on the held-out test split with its own temperature."""
    from wealthpilot.core.sentiment_model import TransformersBackend, verify_artifact

    metadata = json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("dataset_id") != manifest.dataset_id:
        raise ManifestError("the artifact was trained on a different dataset; its test split is not held out here")
    info = verify_artifact(directory.resolve(), expected_version=metadata["model_version"], expected_name=metadata["model_name"], max_tokens=int(metadata.get("max_tokens_trained", 128)))
    backend = TransformersBackend(info.directory, max_tokens=int(metadata.get("max_tokens_trained", 128)), device="cpu", labels=info.labels, tokenizer_length=info.tokenizer_length)
    logits = np.array([backend.predict(r.text).logits for r in test])
    y = np.array([LABEL_MAP[r.label] for r in test])
    temperature = info.temperature or 1.0
    probabilities = softmax(logits, temperature)
    return {"candidate": info.model_name, "version": info.model_version, "samples": len(test), "validation_status_in_metadata": info.validation_status,
            "metrics": classification_report(y, probabilities.argmax(axis=1)), "calibration": {"temperature": temperature, **expected_calibration_error(probabilities, y)}}


def rules_baseline_predictions(frozen: FrozenEvaluation) -> dict[str, str | None]:
    """The deterministic baseline's answer for every held-out example: positive / negative / neutral are its answers; anything else (mixed, uncertain, insufficient evidence) is an abstention (None)."""
    out: dict[str, str | None] = {}
    for record in frozen.records["heldout"]:
        label = analyse_user_text(record.text).sentiment
        out[record.item_id] = label if label in LABELS else None
    return out


def load_predictions(path: Path) -> tuple[dict[str, str | None], dict[str, dict[str, float]] | None]:
    """A candidate's precomputed held-out predictions: a JSON object of item id -> either a label or null (LABELS-ONLY) or {"label": label or null, "probabilities": {label: p}} (PROBABILITY-BEARING).
    Owner decision E2 (2026-10-29): calibration requires probability-bearing predictions, so a labels-only file is evaluated but stays descriptive-only. A file is all one kind or the other, never mixed;
    the probabilities must cover exactly the primary labels, be finite numbers in [0, 1] and sum to 1, and a non-null label must be the most probable class. A problem is reported without echoing the file."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ManifestError("a predictions file could not be read as JSON") from None
    return parse_predictions(raw)


def parse_predictions(raw: object) -> tuple[dict[str, str | None], dict[str, dict[str, float]] | None]:
    """The checks of `load_predictions` on an already parsed object, shared with the local-model path so that a model's own predictions pass the SAME gate as a precomputed file."""
    shape = "a predictions file must be a JSON object of held-out id -> label or null, or id -> {label, probabilities}"
    if not isinstance(raw, dict) or not all(isinstance(k, str) for k in raw):
        raise ManifestError(shape)
    with_probabilities = [isinstance(v, dict) for v in raw.values()]
    if any(with_probabilities) and not all(with_probabilities):
        raise ManifestError("a predictions file must carry probabilities for every record or for none")
    labels: dict[str, str | None] = {}
    probabilities: dict[str, dict[str, float]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            label, scores = value.get("label"), value.get("probabilities")
            if set(value) != {"label", "probabilities"} or not (label is None or isinstance(label, str)) or not isinstance(scores, dict):
                raise ManifestError(shape)
            if set(scores) != set(LABELS) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0 for v in scores.values())                     or abs(sum(scores.values()) - 1.0) > 1e-3:
                raise ManifestError("the probabilities must cover exactly the primary labels, be finite numbers in [0, 1] and sum to 1")
            if label is not None and (label not in scores or scores[label] < max(scores.values())):
                raise ManifestError("a non-null label must be the most probable class of its probabilities")
            labels[key], probabilities[key] = label, {k: float(v) for k, v in scores.items()}
        elif value is None or isinstance(value, str):
            labels[key] = value
        else:
            raise ManifestError(shape)
    return labels, (probabilities or None)


LOCAL_CLASSIFIER_LOADER = load_classifier              # replaced only by tests (fake classifiers); the real one imports torch and transformers lazily and reads only a verified local directory


def separate_calibration(frozen, labels: dict[str, str | None], probabilities: dict[str, dict[str, float]] | None) -> tuple[dict, dict | None, dict | None]:
    """A probability-bearing candidate may also answer the CALIBRATION split (it is the only data the D13 temperature is fitted on). Returns the held-out labels, the held-out probabilities and the
    calibration probabilities (None when the candidate gave none). A labels-only candidate is left untouched, so an id outside the held-out split is still refused downstream, never skipped."""
    if probabilities is None:
        return labels, None, None
    calibration_ids = {r.item_id for r in frozen.records["calibration"]}
    return ({k: v for k, v in labels.items() if k not in calibration_ids}, {k: v for k, v in probabilities.items() if k not in calibration_ids},
            {k: v for k, v in probabilities.items() if k in calibration_ids} or None)


def local_model_predictions(frozen, name: str, directory: str, manifest_path: str) -> tuple[dict[str, str | None], dict[str, dict[str, float]] | None, dict[str, str]]:
    """Path B (owner decision C1, OFFLINE EVALUATION ONLY): predictions of one verified LOCAL model directory on the held-out texts. The directory must hold exactly the five approved files and
    match its frozen manifest (hashes, sizes, immutable revision); no Hub identifier exists on this path; the texts are read here and are never written anywhere. The predictions then pass the same
    gate as a precomputed file. Returns the labels, the probabilities and the provenance (identifier, revision, manifest hash: no text)."""
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ManifestError("a local model manifest could not be read as JSON") from None
    try:
        verified = verify_model_directory(Path(directory), manifest)
        classifier = LOCAL_CLASSIFIER_LOADER(verified)
        payload = predictions_payload({r.item_id: r.text for split in ("heldout", "calibration") for r in frozen.records[split]}, classifier)         # the calibration texts only fit the D13 temperature
    except LocalModelError as exc:
        raise ManifestError(f"local model '{name}' refused: {exc.code}") from None
    labels, probabilities = parse_predictions(payload)
    return labels, probabilities, {"identifier": verified.identifier, "revision": verified.revision, "manifest_sha256": str(verified.manifest["manifest_sha256"])}


def run_frozen(args: argparse.Namespace) -> int:
    """Frozen-set mode: verify the set, evaluate each candidate on the held-out split, compare each with the rules baseline, write one report. Nothing here enables, ranks or selects a model."""
    plan, policy = StatisticsPlan.owner_approved(), EvaluationPolicy.owner_approved()
    try:
        frozen = load_frozen_evaluation(args.frozen_manifest, args.records, args.rubric, args.annotator_manifest, args.adjudication_log, args.participant_register, as_of=date.today())
        predictions: dict[str, dict[str, str | None]] = {}
        scores: dict[str, dict[str, dict[str, float]] | None] = {}
        for candidate in args.candidate or ["rules_baseline"]:
            if candidate != "rules_baseline":
                raise ManifestError("frozen-set mode accepts only the candidate 'rules_baseline' (a model artifact needs R6 / R7 and D10 to D13 first); use --predictions NAME=FILE for precomputed predictions")
            predictions["rules_baseline"], scores["rules_baseline"] = rules_baseline_predictions(frozen), None          # the baseline reports no probability: labels-only, descriptive-only
        for spec in args.predictions:
            name, separator, path = spec.partition("=")
            if not separator or not name or not path or name == "rules_baseline" or name in predictions:
                raise ManifestError("--predictions must be NAME=FILE with a NAME that is not 'rules_baseline' and not repeated")
            predictions[name], scores[name] = load_predictions(Path(path))
        local_models: dict[str, dict[str, str]] = {}
        manifests = dict(spec.partition("=")[::2] for spec in args.local_model_manifest)
        requested = [spec.partition("=") for spec in args.local_model]
        names = [name for name, _, _ in requested]
        if (any(not separator or not name or not directory or name == "rules_baseline" or name in predictions for name, separator, directory in requested) or len(set(names)) != len(names)
                or len(manifests) != len(args.local_model_manifest) or set(manifests) != set(names)):
            raise ManifestError("--local-model must be NAME=DIRECTORY with a NAME that is not 'rules_baseline' and not repeated, and each needs exactly one matching --local-model-manifest NAME=FILE")
        for name, _, directory in requested:                                                     # every request is validated BEFORE any model is verified or loaded
            predictions[name], scores[name], local_models[name] = local_model_predictions(frozen, name, directory, manifests[name])
        results = {}
        for name, preds in list(predictions.items()):
            predictions[name], held_scores, calibration_scores = separate_calibration(frozen, preds, scores[name])
            results[name] = evaluate_frozen(frozen, predictions[name], plan=plan, policy=policy, probabilities=held_scores, calibration_probabilities=calibration_scores)
        heldout = frozen.records["heldout"]
        comparisons = []
        if "rules_baseline" in predictions:
            truth = [r.label for r in heldout]
            baseline = [predictions["rules_baseline"][r.item_id] for r in heldout]
            for name, preds in predictions.items():
                if name != "rules_baseline":
                    comparisons.append(compare_predictions(truth, [preds[r.item_id] for r in heldout], baseline, labels=policy.primary_labels, plan=plan, evidence=frozen.evidence,
                                                           first_name=name, second_name="rules_baseline"))
    except (FrozenEvaluationError, ManifestError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    report = {"mode": "frozen_evaluation", "manifest": {"dataset_id": frozen.manifest["dataset_id"], "dataset_version": frozen.manifest["dataset_version"], "manifest_sha256": frozen.manifest["manifest_sha256"],
                                                           "checks": dict(frozen.checks)}, "evidence": frozen.evidence.describe(), "plan": plan.describe(), "policy": policy.describe(),
              "candidates": results, "comparisons": comparisons, "local_models": local_models,
              "selection": "none: no candidate is ranked or selected", "activation": "not decided here: activation is the separate R14 decision, and a report alone never recommends it"}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": "frozen_evaluation", "evidence": frozen.evidence.describe()["status"], "candidates": {n: r["assessment"]["validation"]["status"] for n, r in results.items()},
                      "output": str(args.output)}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--candidate", action="append", default=[], help="'rules_baseline' or an artifact directory under models/sentiment/ (repeatable; frozen-set mode: 'rules_baseline' only)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frozen-manifest", type=Path, help="frozen-set mode: the approved frozen manifest")
    parser.add_argument("--records", type=Path, help="frozen-set mode: the records file")
    parser.add_argument("--rubric", type=Path, help="frozen-set mode: the rubric file named by the manifest")
    parser.add_argument("--annotator-manifest", type=Path, help="frozen-set mode: the annotator manifest")
    parser.add_argument("--adjudication-log", type=Path, help="frozen-set mode: the adjudication log")
    parser.add_argument("--participant-register", type=Path, help="frozen-set mode: the participant register named by the manifest")
    parser.add_argument("--predictions", action="append", default=[], help="frozen-set mode: NAME=FILE of precomputed held-out predictions (repeatable)")
    parser.add_argument("--local-model", action="append", default=[], help="frozen-set mode, Path B: NAME=DIRECTORY of a verified LOCAL model directory (exactly the five approved files; never a Hub identifier)")
    parser.add_argument("--local-model-manifest", action="append", default=[], help="frozen-set mode, Path B: NAME=FILE, the frozen manifest of that directory")
    args = parser.parse_args(argv)
    frozen_arguments = [args.frozen_manifest, args.records, args.rubric, args.annotator_manifest, args.adjudication_log, args.participant_register]
    if any(a is not None for a in frozen_arguments):
        if any(a is None for a in frozen_arguments) or args.manifest is not None or args.data is not None:
            parser.error("frozen-set mode needs all six of --frozen-manifest, --records, --rubric, --annotator-manifest, --adjudication-log and --participant-register, and cannot be combined with --manifest or --data")
        return run_frozen(args)
    if args.predictions or args.local_model or args.local_model_manifest:
        parser.error("--predictions, --local-model and --local-model-manifest belong to frozen-set mode")
    if args.manifest is None or args.data is None:
        parser.error("--manifest and --data are required (or the five frozen-set arguments)")
    try:
        manifest = load_manifest(args.manifest)
        test, split = test_split(manifest, args.data)
        results = []
        for candidate in args.candidate or ["rules_baseline"]:
            if candidate == "rules_baseline":
                results.append(evaluate_rules_baseline(test))
            else:
                directory = Path(candidate) if Path(candidate).is_absolute() else MODELS_DIR / Path(candidate).name
                results.append(evaluate_artifact(directory, test, manifest))
    except (ManifestError, ImportError, ModelUnavailable) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    report = {"dataset": {"dataset_id": manifest.dataset_id, "license": manifest.license, "domain_note": manifest.domain_note}, "split": split, "candidates": results,
              "selection": "not made here: the project owner chooses from these measured results"}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dataset": manifest.dataset_id, "test_samples": len(test), "candidates": [r["candidate"] for r in results], "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
