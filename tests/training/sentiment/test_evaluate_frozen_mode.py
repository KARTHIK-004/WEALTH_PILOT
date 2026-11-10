"""ADR-052 -- the frozen-set mode of `training/sentiment/evaluate_sentiment_model.py` (owner decision `APPROVE_SCHEMA_AND_WIRE_OFFLINE`, 2026-10-29): the script reaches the statistics ONLY through the validated
manifest interface of `frozen_evaluation.py`. Every set here is generated inside the test from invented tokens; no real manifest, dataset, model or route is involved, and the evidence basis cannot be set
from the command line."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from frozen_fixtures import build, perfect

from training.sentiment import evaluate_sentiment_model as ev


def argv(built, output: Path, *extra: str) -> list[str]:
    return ["--frozen-manifest", str(built.manifest_path), "--records", str(built.records_path), "--rubric", str(built.rubric_path), "--annotator-manifest", str(built.annotators_path),
            "--adjudication-log", str(built.log_path), "--participant-register", str(built.register_path), "--output", str(output), *extra]


def write_predictions(path: Path, mapping: dict) -> str:
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return str(path)


# ------------------------------------------------------------------------------------------------------------------------------- the mode runs, verifies first, and reports without recommending
def test_the_mode_evaluates_the_rules_baseline_on_the_held_out_split_and_writes_one_report(tmp_path, capsys):
    built = build(tmp_path / "set", synthetic=True)
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out)) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["mode"] == "frozen_evaluation" and list(report["candidates"]) == ["rules_baseline"] and report["comparisons"] == []
    assert report["manifest"]["manifest_sha256"] == built.manifest["manifest_sha256"] and all(report["manifest"]["checks"].values())
    assert report["evidence"]["status"] == "not_validation_evidence" and report["candidates"]["rules_baseline"]["assessment"]["validation"]["status"] == "not_validation_evidence"
    assert report["plan"]["status"] == "approved by the owner (2026-10-29)" and report["policy"]["lower_bound_rule"] == "NO_LOWER_BOUND_ACTIVATION_RULE"
    assert report["selection"].startswith("none") and "R14" in report["activation"] and "never recommends" in report["activation"]
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"mode": "frozen_evaluation", "evidence": "not_validation_evidence", "candidates": {"rules_baseline": "not_validation_evidence"}, "output": str(out)}


def test_the_report_and_the_printout_contain_no_record_text_and_no_record_id(tmp_path, capsys):
    built = build(tmp_path / "set", synthetic=True)
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out)) == 0
    everything = out.read_text(encoding="utf-8") + capsys.readouterr().out
    for record in built.records[:60]:
        assert record["id"] not in everything and all(token not in everything for token in record["text"].split())


def test_the_exit_status_never_depends_on_a_target(tmp_path):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300)
    frozen = ev.load_frozen_evaluation(built.manifest_path, built.records_path, built.rubric_path, built.annotators_path, built.log_path, built.register_path)
    good = write_predictions(tmp_path / "good.json", perfect(frozen))
    bad = write_predictions(tmp_path / "bad.json", {r.item_id: "negative" if r.label != "negative" else "positive" for r in frozen.records["heldout"]})
    nothing = write_predictions(tmp_path / "none.json", {r.item_id: None for r in frozen.records["heldout"]})
    statuses = {}
    for name, path in (("good", good), ("bad", bad), ("nothing", nothing)):
        out = tmp_path / f"{name}.json"
        assert ev.main(argv(built, out, "--predictions", f"{name}={path}")) == 0
        statuses[name] = json.loads(out.read_text(encoding="utf-8"))["candidates"][name]["assessment"]
    assert all(a["activation_recommendation"].startswith("none") and a["selection"].startswith("none") for a in statuses.values())
    gates = {n: {g["gate"]: g["status"] for g in a["gates"]} for n, a in statuses.items()}
    assert gates["good"]["target:macro_f1:strict"] == "met" and gates["bad"]["target:macro_f1:strict"] == "not_met" and gates["nothing"]["coverage:minimum"] == "not_met"


def test_precomputed_predictions_are_evaluated_and_compared_with_the_rules_baseline_without_naming_a_winner(tmp_path):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300)
    frozen = ev.load_frozen_evaluation(built.manifest_path, built.records_path, built.rubric_path, built.annotators_path, built.log_path, built.register_path)
    path = write_predictions(tmp_path / "model.json", perfect(frozen))
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out, "--candidate", "rules_baseline", "--predictions", f"standin={path}")) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert list(report["candidates"]) == ["rules_baseline", "standin"] and len(report["comparisons"]) == 1
    comparison = report["comparisons"][0]
    assert (comparison["first"], comparison["second"]) == ("standin", "rules_baseline") and comparison["significance_testing"].startswith("NOT_REQUIRED") and comparison["selection"].startswith("none")
    assert {"both_correct", "only_standin_correct", "only_rules_baseline_correct", "both_wrong_or_abstained"} <= set(comparison["discordance"])
    assessment = report["candidates"]["standin"]["assessment"]
    assert report["evidence"]["status"] == "eligible_for_owner_review"                                          # the fixture's own flags say approved, non-synthetic, frozen and attested
    assert assessment["validation"]["status"] == "descriptive_only" and "calibration: not_evaluable" in assessment["validation"]["unmet_or_missing"]       # a labels-only predictions file has no confidences
    assert assessment["activation_recommendation"].startswith("none")


# ------------------------------------------------------------------------------------------------------------------------------- refusals
def test_a_tampered_set_is_refused_before_anything_is_evaluated_and_nothing_is_written(tmp_path, capsys):
    built = build(tmp_path / "set")
    built.records_path.write_text(built.records_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out)) == 2
    assert "REFUSED" in capsys.readouterr().err and not out.exists()


def test_a_model_artifact_candidate_is_refused_in_this_mode(tmp_path, capsys):
    built = build(tmp_path / "set")
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out, "--candidate", "models/sentiment/finbert-v1")) == 2
    assert "needs R6 / R7 and D10 to D13" in capsys.readouterr().err and not out.exists()


def test_predictions_that_do_not_cover_the_held_out_ids_are_refused_without_echoing_the_file(tmp_path, capsys):
    built = build(tmp_path / "set")
    frozen = ev.load_frozen_evaluation(built.manifest_path, built.records_path, built.rubric_path, built.annotators_path, built.log_path, built.register_path)
    short = dict(list(perfect(frozen).items())[1:])
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out, "--predictions", f"short={write_predictions(tmp_path / 'short.json', short)}")) == 2
    assert "1 missing, 0 unexpected" in capsys.readouterr().err and not out.exists()
    (tmp_path / "broken.json").write_text("{ not json SECRETMARKER", encoding="utf-8")
    assert ev.main(argv(built, out, "--predictions", f"broken={tmp_path / 'broken.json'}")) == 2
    assert "SECRETMARKER" not in capsys.readouterr().err
    assert ev.main(argv(built, out, "--predictions", f"rules_baseline={write_predictions(tmp_path / 'x.json', perfect(frozen))}")) == 2        # the baseline name is reserved


def test_the_five_frozen_arguments_are_all_required_and_cannot_be_mixed_with_the_ordinary_mode(tmp_path):
    built = build(tmp_path / "set")
    out = str(tmp_path / "report.json")
    with pytest.raises(SystemExit):
        ev.main(["--frozen-manifest", str(built.manifest_path), "--output", out])
    with pytest.raises(SystemExit):
        ev.main([*argv(built, Path(out)), "--manifest", str(built.manifest_path)])
    with pytest.raises(SystemExit):
        ev.main(["--output", out, "--predictions", "x=y"])
    with pytest.raises(SystemExit):
        ev.main(["--output", out])


# ------------------------------------------------------------------------------------------------------------------------------- the wiring is narrow
def test_there_is_no_command_line_way_to_state_the_evidence_or_to_approve_a_set():
    parser_source = Path(ev.__file__).read_text(encoding="utf-8")
    flags = [node.value for node in ast.walk(ast.parse(parser_source)) if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("--")]
    assert flags and not [f for f in flags if any(word in f for word in ("approve", "evidence", "valid", "synthetic", "frozen-flag", "activate", "enable"))], flags


def test_the_script_reaches_the_statistics_only_through_the_frozen_interface_and_not_the_api_settings_agents_or_activation():
    source = Path(ev.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module for a in n.names}
    assert "training.sentiment.frozen_evaluation.load_frozen_evaluation" in imported and "training.sentiment.frozen_evaluation.evaluate_frozen" in imported
    assert not any(i.startswith(("wealthpilot.api", "wealthpilot.config", "wealthpilot.agents", "wealthpilot.security")) for i in imported), imported
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {"EvidenceBasis", "evaluate_predictions", "evaluation_report", "assess_against_policy", "agreement_report"} & names             # never builds an evidence basis or a report itself
    assert "SENTIMENT_MODEL_ENABLED" not in source and "environ" not in names and "getenv" not in names


# ------------------------------------------------------------------------------------------------------------------------------- owner decision E2: probability-bearing predictions
def with_probabilities(predictions: dict, confidence: float = 0.9) -> dict:
    rest = round((1.0 - confidence) / 2, 6)
    return {i: {"label": label, "probabilities": {k: (confidence if k == label else rest) for k in ("positive", "negative", "neutral")} if label else {"positive": 1 / 3, "negative": 1 / 3, "neutral": 1 / 3}}
            for i, label in predictions.items()}


def run_candidate(tmp_path, built, mapping, name="standin"):
    out = tmp_path / f"{name}.report.json"
    code = ev.main(argv(built, out, "--predictions", f"{name}={write_predictions(tmp_path / f'{name}.json', mapping)}"))
    return code, out


def test_a_probability_bearing_file_makes_calibration_evaluable_and_the_label_only_file_does_not(tmp_path):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300)
    frozen = ev.load_frozen_evaluation(built.manifest_path, built.records_path, built.rubric_path, built.annotators_path, built.log_path, built.register_path)
    labels_only = json.loads(run_candidate(tmp_path, built, perfect(frozen), "plain")[1].read_text(encoding="utf-8"))["candidates"]["plain"]["assessment"]["validation"]
    assert "calibration: not_evaluable" in labels_only["unmet_or_missing"] and labels_only["status"] == "descriptive_only"
    code, out = run_candidate(tmp_path, built, with_probabilities(perfect(frozen)), "scored")
    assert code == 0
    assessment = json.loads(out.read_text(encoding="utf-8"))["candidates"]["scored"]["assessment"]
    assert "calibration: not_evaluable" not in assessment["validation"]["unmet_or_missing"]
    assert assessment["activation_recommendation"].startswith("none") and assessment["selection"].startswith("none")
    assert assessment["validation"]["status"] in ("validated", "insufficient_support", "descriptive_only")          # plumbing logic test only: the fixture is synthetic and nothing is activated
    for record in built.records[:40]:
        assert record["id"] not in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", ["mixed", "extra_key", "missing_class", "not_summing", "negative_value", "boolean_value", "nan", "label_not_argmax", "label_outside", "string_value", "list_entry"])
def test_malformed_probability_files_are_refused_without_echoing_the_file(tmp_path, capsys, bad):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300)
    frozen = ev.load_frozen_evaluation(built.manifest_path, built.records_path, built.rubric_path, built.annotators_path, built.log_path, built.register_path)
    mapping = with_probabilities(perfect(frozen))
    first = next(iter(mapping))
    good = mapping[first]
    if bad == "mixed":
        mapping[first] = perfect(frozen)[first]
    elif bad == "extra_key":
        mapping[first] = {**good, "SECRETMARKER": 1}
    elif bad == "missing_class":
        mapping[first] = {"label": good["label"], "probabilities": {k: v for k, v in good["probabilities"].items() if k != "neutral"}}
    elif bad == "not_summing":
        mapping[first] = {"label": good["label"], "probabilities": {k: 0.9 for k in good["probabilities"]}}
    elif bad == "negative_value":
        mapping[first] = {"label": good["label"], "probabilities": {"positive": 1.5, "negative": -0.5, "neutral": 0.0}}
    elif bad == "boolean_value":
        mapping[first] = {"label": "positive", "probabilities": {"positive": True, "negative": 0, "neutral": 0}}
    elif bad == "nan":
        mapping[first] = {"label": good["label"], "probabilities": {"positive": float("nan"), "negative": 0.5, "neutral": 0.5}}
    elif bad == "label_not_argmax":
        other = next(k for k in ("positive", "negative", "neutral") if k != good["label"])
        mapping[first] = {"label": other, "probabilities": good["probabilities"]}
    elif bad == "label_outside":
        mapping[first] = {"label": "SECRETMARKER", "probabilities": good["probabilities"]}
    elif bad == "string_value":
        mapping[first] = {"label": good["label"], "probabilities": {k: "0.3" for k in good["probabilities"]}}
    else:
        mapping[first] = ["SECRETMARKER"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")                                                          # json.dumps writes NaN as a token Python reads back
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out, "--predictions", f"bad={path}")) == 2
    assert "SECRETMARKER" not in capsys.readouterr().err and not out.exists()


def test_the_rules_baseline_never_carries_probabilities_so_it_can_never_be_validated(tmp_path):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300)
    out = tmp_path / "report.json"
    assert ev.main(argv(built, out)) == 0
    validation = json.loads(out.read_text(encoding="utf-8"))["candidates"]["rules_baseline"]["assessment"]["validation"]
    assert validation["status"] != "validated"
    assert "calibration: not_evaluable" in validation["unmet_or_missing"]                                         # no confidences, so calibration cannot be evaluated


def test_load_predictions_returns_labels_and_probabilities_separately(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"a": {"label": "positive", "probabilities": {"positive": 0.8, "negative": 0.1, "neutral": 0.1}}, "b": {"label": None, "probabilities": {"positive": 0.4, "negative": 0.3, "neutral": 0.3}}}), encoding="utf-8")
    labels, scores = ev.load_predictions(path)
    assert labels == {"a": "positive", "b": None} and scores["a"]["positive"] == 0.8 and set(scores) == {"a", "b"}
    path.write_text(json.dumps({"a": "positive", "b": None}), encoding="utf-8")
    assert ev.load_predictions(path) == ({"a": "positive", "b": None}, None)


@pytest.mark.parametrize("scores", [{"positive": 0.5, "negative": 0.5}, {"positive": 0.5, "negative": 0.3, "neutral": 0.1}, {"positive": 1.2, "negative": -0.2, "neutral": 0.0},
                                    {"positive": float("nan"), "negative": 0.5, "neutral": 0.5}, {"positive": 0.5, "negative": 0.3, "neutral": 0.2, "other": 0.0}])
def test_the_loader_itself_refuses_unusable_probabilities_not_only_the_evaluator_behind_it(tmp_path, scores):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"a": {"label": None, "probabilities": scores}}), encoding="utf-8")
    with pytest.raises(ev.ManifestError) as refused:
        ev.load_predictions(path)
    assert "0.3" not in str(refused.value) and "nan" not in str(refused.value).lower()                              # no value is echoed


# ------------------------------------------------------------------------------------------------------------------------------- Path B: a verified LOCAL model directory (owner decision C1, offline evaluation only)
from local_model_fixtures import make_local_dir, write_manifest_file  # noqa: E402


class FakeLocalClassifier:
    """Stands in for a loaded model: the class probabilities come from a lookup the test builds, never from a model."""

    def __init__(self, verified, table):
        self.verified, self.table = verified, table

    def predict(self, texts):
        return [{name: 0.9 if self.table[t] == name else 0.05 for name in ("positive", "negative", "neutral")} for t in texts]


def local_argv(built, out: Path, directory: Path, manifest: Path, name: str = "localfin") -> list[str]:
    return argv(built, out, "--local-model", f"{name}={directory}", "--local-model-manifest", f"{name}={manifest}")


def test_a_verified_local_directory_is_evaluated_with_probabilities_and_only_provenance_is_reported(tmp_path, monkeypatch):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300)
    frozen = ev.load_frozen_evaluation(built.manifest_path, built.records_path, built.rubric_path, built.annotators_path, built.log_path, built.register_path)
    table = {r.text: r.label for split in ("heldout", "calibration") for r in frozen.records[split]}          # the model also answers the calibration split (it only fits the D13 temperature)
    directory = make_local_dir(tmp_path)
    manifest = write_manifest_file(directory, tmp_path / "local_manifest.json")
    loaded: list = []
    monkeypatch.setattr(ev, "LOCAL_CLASSIFIER_LOADER", lambda verified: loaded.append(verified) or FakeLocalClassifier(verified, table))
    out = tmp_path / "report.json"
    assert ev.main(local_argv(built, out, directory, manifest)) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert len(loaded) == 1 and loaded[0].path == directory and loaded[0].revision == "0123456789abcdef0123456789abcdef01234567"
    assert report["local_models"]["localfin"] == {"identifier": "ProsusAI/finbert", "revision": "0123456789abcdef0123456789abcdef01234567",
                                                   "manifest_sha256": json.loads(manifest.read_text(encoding="utf-8"))["manifest_sha256"]}
    assessment = report["candidates"]["localfin"]["assessment"]
    assert "calibration: not_evaluable" not in assessment["validation"]["unmet_or_missing"] and assessment["activation_recommendation"].startswith("none") and assessment["selection"].startswith("none")
    everything = out.read_text(encoding="utf-8")
    assert all(r.item_id not in everything and r.text not in everything for r in frozen.records["heldout"][:60])


def test_a_tampered_or_extra_file_in_the_local_directory_is_refused_before_any_model_is_loaded(tmp_path, monkeypatch, capsys):
    built = build(tmp_path / "set")
    directory = make_local_dir(tmp_path)
    manifest = write_manifest_file(directory, tmp_path / "local_manifest.json")
    loaded: list = []
    monkeypatch.setattr(ev, "LOCAL_CLASSIFIER_LOADER", lambda verified: loaded.append(verified))
    out = tmp_path / "report.json"
    (directory / "model.safetensors").write_bytes(b"TAMPERED")
    assert ev.main(local_argv(built, out, directory, manifest)) == 2 and "local model 'localfin' refused: size_mismatch" in capsys.readouterr().err
    (directory / "model.safetensors").write_bytes(b"DUMMY-WEIGHTS" * 50)
    (directory / "pytorch_model.bin").write_bytes(b"x")
    assert ev.main(local_argv(built, out, directory, manifest)) == 2 and "forbidden_file_format" in capsys.readouterr().err
    assert loaded == [] and not out.exists()


def test_a_local_model_needs_its_manifest_a_clean_name_and_never_a_hub_identifier(tmp_path, monkeypatch):
    built = build(tmp_path / "set")
    directory = make_local_dir(tmp_path)
    manifest = write_manifest_file(directory, tmp_path / "local_manifest.json")
    monkeypatch.setattr(ev, "LOCAL_CLASSIFIER_LOADER", lambda verified: pytest.fail("a refused request must not load a model"))
    out = tmp_path / "report.json"
    for bad in (argv(built, out, "--local-model", f"localfin={directory}"),
                argv(built, out, "--local-model", f"rules_baseline={directory}", "--local-model-manifest", f"rules_baseline={manifest}"),
                argv(built, out, "--local-model", f"localfin={directory}", "--local-model", f"localfin={directory}", "--local-model-manifest", f"localfin={manifest}"),
                argv(built, out, "--local-model-manifest", f"ghost={manifest}"),
                argv(built, out, "--local-model", "ProsusAI/finbert", "--local-model-manifest", f"x={manifest}")):
        assert ev.main(bad) == 2, bad
    assert not out.exists()
    assert ev.main(argv(built, out, "--candidate", "ProsusAI/finbert")) == 2                                      # a Hub identifier as a candidate is still refused
    with pytest.raises(SystemExit):
        ev.main(["--output", str(out), "--local-model", f"x={directory}"])                                       # not available outside frozen-set mode


def test_the_evaluation_script_imports_the_local_loader_but_no_hub_network_deep_learning_or_pickle_module():
    tree = ast.parse(Path(ev.__file__).read_text(encoding="utf-8"))
    imported = {f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module for a in n.names} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert "training.sentiment.local_model_dir.load_classifier" in imported
    assert not {name for name in imported if name.split(".")[0] in ("socket", "urllib", "requests", "httpx", "huggingface_hub", "torch", "transformers", "pickle", "os")}, imported
