"""Schema-2 frozen-manifest metadata, the participant-register check and the D13 calibration wiring of `frozen_evaluation.py` / `evaluate_sentiment_model.py` (owner decisions, 2026-10-29). Everything is
generated inside the test from invented tokens and an invented register: no real manifest, dataset, participant, model or text exists, and synthetic evidence can never produce `validated`."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from frozen_fixtures import build, perfect
from register_fixtures import edited as edited_register

from training.sentiment import evaluate_sentiment_model as ev
from training.sentiment import frozen_evaluation as fe
from training.sentiment.frozen_evaluation import FrozenEvaluationError, calibration_eval_records, evaluate_frozen, load_frozen_evaluation
from training.sentiment.metrics import EvaluationPolicy, StatisticsPlan

LABELS = ("positive", "negative", "neutral")
POLICY = EvaluationPolicy.owner_approved()
FAST_PLAN = StatisticsPlan(0.95, 200, 42, 20, 75, False)
HEX = "0" * 64


def participant(register: dict, code: str) -> dict:
    return next(p for p in register["participants"] if p["code"] == code)


def confident(frozen, split: str, peak: float = 0.9, error_every: int = 3) -> dict:
    """Probabilities for one split: confident at `peak`, right except every `error_every`-th example (so the candidate is overconfident)."""
    out = {}
    for i, r in enumerate(frozen.records[split]):
        chosen = r.label if i % error_every else LABELS[(LABELS.index(r.label) + 1) % 3]
        out[r.item_id] = {label: (peak if label == chosen else (1 - peak) / 2) for label in LABELS}
    return out


def labels_of(probabilities: dict) -> dict:
    return {k: max(v, key=v.get) for k, v in probabilities.items()}


# ------------------------------------------------------------------------------------------------------------------------------- the new manifest fields
def test_the_manifest_carries_the_register_calibration_group_and_duplicate_metadata_and_is_schema_2(tmp_path):
    built = build(tmp_path)
    m = built.manifest
    assert m["schema_version"] == fe.SCHEMA_VERSION == 2 and m["data_status"] == "consented" and set(m["participant_register"]) == {"sha256", "verifier_sha256", "consent_wording_sha256"}
    assert m["calibration"] == {"split_sha256": m["calibration"]["split_sha256"], "temperature_policy_version": "d13-temperature-v1", "fit_split": "calibration",
                                "method": "temperature_scaling_nll_on_log_probabilities", "bins": 10, "min_scored": 20}
    assert m["duplicates"]["exact_method"] == "sha256_of_normalized_text" and m["duplicates"]["ngram_size"] == 5 and set(m["group_dimensions"]) <= set(fe.APPROVED_GROUP_DIMENSIONS)
    checks = built.load().checks
    assert all(checks.values()) and {"participant_register_verified", "register_consistent_with_manifest", "calibration_split_sha256_verified", "group_dimensions_approved",
                                      "duplicate_policy_declared"} <= set(checks)


def test_a_schema_1_manifest_is_refused_as_unknown(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="unknown schema_version"):
        build(tmp_path, manifest_edit=lambda m: m.update(schema_version=1)).load()


@pytest.mark.parametrize("field", ["data_status", "participant_register", "calibration"])
def test_a_missing_new_field_is_refused(tmp_path, field):
    with pytest.raises(FrozenEvaluationError, match=f"missing field '{field}'"):
        build(tmp_path, manifest_edit=lambda m: m.pop(field)).load()


MALFORMED = {
    "register_extra_key": (lambda m: m["participant_register"].update(extra=HEX), "participant_register must hold exactly"),
    "register_hash_not_hex": (lambda m: m["participant_register"].update(sha256="ABC"), "participant_register must hold exactly"),
    "verifier_hash_missing": (lambda m: m["participant_register"].pop("verifier_sha256"), "participant_register must hold exactly"),
    "register_not_object": (lambda m: m.update(participant_register="x"), "participant_register must hold exactly"),
    "consent_hash_malformed": (lambda m: m["participant_register"].update(consent_wording_sha256="nope"), "participant_register must hold exactly"),
    "consented_without_consent_hash": (lambda m: m["participant_register"].update(consent_wording_sha256=None), "consent_wording_sha256 must be present exactly when the data is consented"),
    "invalid_status": (lambda m: m.update(data_status="fictional"), "data_status must be 'synthetic' or 'consented'"),
    "status_vs_flag": (lambda m: m.update(data_status="synthetic"), "data_status and the synthetic flag disagree"),
    "policy_version": (lambda m: m["calibration"].update(temperature_policy_version="v2"), "calibration must hold exactly"),
    "fit_split": (lambda m: m["calibration"].update(fit_split="heldout"), "calibration must hold exactly"),
    "train_split": (lambda m: m["calibration"].update(fit_split="train"), "calibration must hold exactly"),
    "method": (lambda m: m["calibration"].update(method="isotonic"), "calibration must hold exactly"),
    "bins": (lambda m: m["calibration"].update(bins=15), "calibration must hold exactly"),
    "bins_bool": (lambda m: m["calibration"].update(bins=True), "calibration must hold exactly"),
    "min_scored": (lambda m: m["calibration"].update(min_scored=19), "calibration must hold exactly"),
    "split_hash": (lambda m: m["calibration"].update(split_sha256="short"), "calibration must hold exactly"),
    "calibration_extra": (lambda m: m["calibration"].update(extra=1), "calibration must hold exactly"),
    "calibration_missing": (lambda m: m["calibration"].pop("method"), "calibration must hold exactly"),
    "group_unapproved": (lambda m: m.update(group_dimensions=["topic", "age"]), "group_dimensions may only be drawn from"),
    "exact_method": (lambda m: m["duplicates"].update(exact_method="casefold"), "exact_method"),
    "ngram_size": (lambda m: m["duplicates"].update(ngram_size=4), "ngram_size"),
    "ngram_bool": (lambda m: m["duplicates"].update(ngram_size=True), "ngram_size"),
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_missing_malformed_or_inconsistent_metadata_is_refused_with_the_existing_fixed_behaviour(tmp_path, name):
    change, message = MALFORMED[name]
    with pytest.raises(FrozenEvaluationError, match=message) as caught:
        build(tmp_path, manifest_edit=change).load()
    assert "zq" not in str(caught.value)                                                          # the message never contains record text


def test_the_synthetic_status_pairs_with_a_synthetic_register_and_no_consent_hash(tmp_path):
    built = build(tmp_path, synthetic=True)
    assert built.manifest["data_status"] == "synthetic" and built.manifest["participant_register"]["consent_wording_sha256"] is None
    with pytest.raises(FrozenEvaluationError, match="consent_wording_sha256 must be present exactly when"):
        build(tmp_path / "x", synthetic=True, manifest_edit=lambda m: m["participant_register"].update(consent_wording_sha256=HEX)).load()


def test_the_manifest_hash_still_covers_the_new_fields(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="does not match its own manifest_sha256"):
        build(tmp_path / "a", post_edit=lambda m: m["calibration"].update(bins=10, split_sha256=HEX)).load()
    with pytest.raises(FrozenEvaluationError, match="does not match its own manifest_sha256"):
        build(tmp_path / "b", post_edit=lambda m: m["participant_register"].update(sha256=HEX)).load()
    with pytest.raises(FrozenEvaluationError, match="does not match its own manifest_sha256"):
        build(tmp_path / "c", post_edit=lambda m: m.update(approved_by="someone else")).load()


# ------------------------------------------------------------------------------------------------------------------------------- the register is verified, validated and agreed with the manifest
def test_a_changed_register_file_does_not_match_its_manifest_hash(tmp_path):
    built = build(tmp_path)
    built.register_path.write_text(built.register_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(FrozenEvaluationError, match="the participant register does not match its manifest SHA-256"):
        built.load()
    built.register_path.unlink()
    with pytest.raises(FrozenEvaluationError, match="the participant register could not be read"):
        built.load()


def test_an_unreadable_register_is_refused_without_echoing_it(tmp_path):
    built = build(tmp_path, manifest_edit=None)
    built.register_path.write_bytes(b"not json at all SECRET-CONTENT")
    built.manifest["participant_register"]["sha256"] = fe.sha256_file(built.register_path)
    built.manifest["manifest_sha256"] = fe.manifest_hash(built.manifest)
    built.manifest_path.write_text(json.dumps(built.manifest), encoding="utf-8")
    with pytest.raises(FrozenEvaluationError, match="could not be read as JSON") as caught:
        built.load()
    assert "SECRET-CONTENT" not in str(caught.value)


def test_an_invalid_register_is_refused_at_load_with_the_register_s_own_sanitized_message(tmp_path):
    def sees_model_output(register):
        participant(register, "ann-a")["access_authorization"]["may_view"].append("model_output")
        register["register_id"] = "alice.smith@example.com"

    with pytest.raises(FrozenEvaluationError, match="the participant register is not valid") as caught:
        build(tmp_path, register_edit=sees_model_output).load()
    message = str(caught.value)
    assert "may view material its role must not see" in message and "look like personal data" in message
    assert "alice" not in message.lower() and "example.com" not in message


@pytest.mark.parametrize("name,change,message", [
    ("no_independence", lambda r: participant(r, "adj").update(independence_attested=False), "participant 3 has no independence attestation"),
    ("production_service", lambda r: participant(r, "ev").update(principal_type="production_service"), "production services cannot receive dataset access"),
    ("no_deletion", lambda r: r.update(deletion_authorization=None), "a deletion authorization is required"),
    ("duplicate_codes", lambda r: participant(r, "ann-b").update(code="ann-a"), "codes must be unique"),
    ("verifier_unauthorized", lambda r: participant(r, "ver")["access_authorization"].update(granted=False), "participant 5 has no granted access authorization"),
])
def test_register_defects_stop_the_load(tmp_path, name, change, message):
    with pytest.raises(FrozenEvaluationError, match=message):
        build(tmp_path, register_edit=change).load()


def test_the_authorization_must_be_valid_on_the_freezing_day_and_on_an_explicit_evaluation_day(tmp_path):
    soon = lambda r: [p["access_authorization"].update(expires_on="2026-06-30") for p in r["participants"]]  # noqa: E731
    built = build(tmp_path, register_edit=soon)
    assert built.load().checks["participant_register_verified"] is True                         # valid on the day the manifest was frozen (2026-01-01)
    args = (built.manifest_path, built.records_path, built.rubric_path, built.annotators_path, built.log_path, built.register_path)
    assert load_frozen_evaluation(*args, as_of=date(2026, 6, 30)).checks["participant_register_verified"] is True
    with pytest.raises(FrozenEvaluationError, match="has an expired authorization"):
        load_frozen_evaluation(*args, as_of=date(2026, 7, 1))
    with pytest.raises(FrozenEvaluationError, match="has an authorization that has not started"):
        load_frozen_evaluation(*args, as_of=date(2025, 12, 31))


@pytest.mark.parametrize("name,edit,expected", [
    ("data_status", lambda m: m.update(data_status="synthetic", synthetic=True), "the data status"),
    ("scope", lambda m: m.update(dataset_id="another-dataset"), "the permitted dataset scope"),
    ("verifier_hash", lambda m: m["participant_register"].update(verifier_sha256=HEX), "the de-identification verifier hash"),
    ("consent_hash", lambda m: m["participant_register"].update(consent_wording_sha256="d" * 64), "the consent wording hash"),
])
def test_a_register_that_disagrees_with_the_manifest_is_refused(tmp_path, name, edit, expected):
    # (for the data-status case the manifest also drops the consent hash so that only the status disagrees with the consented register)
    def change(m):
        edit(m)
        if name == "data_status":
            m["participant_register"]["consent_wording_sha256"] = None
    with pytest.raises(FrozenEvaluationError, match=f"does not agree with the manifest on .*{expected}"):
        build(tmp_path, manifest_edit=change).load()


def test_registered_annotator_codes_must_match_the_manifest_s_annotators_and_adjudicator(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="the annotator and adjudicator codes"):
        build(tmp_path / "a", register_edit=lambda r: participant(r, "ann-b").update(code="ann-z")).load()
    with pytest.raises(FrozenEvaluationError, match="the annotator and adjudicator codes"):
        build(tmp_path / "b", register_edit=lambda r: participant(r, "adj").update(code="adj-2")).load()


def test_a_register_edit_cannot_hide_behind_the_fixture_hash(tmp_path):
    scope = lambda r: (r.update(dataset_scope="other-scope"), [p["access_authorization"].update(dataset_scope="other-scope") for p in r["participants"]])  # noqa: E731
    with pytest.raises(FrozenEvaluationError, match="the permitted dataset scope"):
        build(tmp_path, register_edit=scope).load()


def test_the_calibration_split_hash_is_recomputed_from_the_records(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="the recomputed calibration split hash does not match the manifest"):
        build(tmp_path, manifest_edit=lambda m: m["calibration"].update(split_sha256=HEX)).load()
    built = build(tmp_path / "ok")
    frozen = built.load()
    assert fe.calibration_split_hash(list(frozen.records["calibration"])) == built.manifest["calibration"]["split_sha256"]
    assert fe.calibration_split_hash(list(frozen.records["calibration"])) != fe.calibration_split_hash(list(frozen.records["train"]))


# ------------------------------------------------------------------------------------------------------------------------------- calibration through evaluate_frozen
def test_the_report_fits_the_temperature_on_the_calibration_split_and_applies_it_to_the_heldout_split_only(tmp_path):
    frozen = build(tmp_path, train=90, calibration=90, heldout=99).load()
    held, calibration = confident(frozen, "heldout"), confident(frozen, "calibration")
    report = evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=calibration)
    temperature = report["temperature_calibration"]
    assert temperature["status"] == "fitted_and_applied" and temperature["fit"]["fit_split"] == "calibration" and temperature["fit"]["scored"] == 90 and temperature["fit"]["temperature"] > 1.0
    assert temperature["heldout_calibrated"]["strict"]["ece"] < temperature["heldout_uncalibrated"]["strict"]["ece"] and temperature["labels_changed"] is False
    assert temperature["heldout_calibrated"]["scored"] == temperature["heldout_uncalibrated"]["scored"] == 99
    other = confident(frozen, "heldout", peak=0.6, error_every=2)
    assert evaluate_frozen(frozen, labels_of(other), plan=FAST_PLAN, policy=POLICY, probabilities=other, calibration_probabilities=calibration)["temperature_calibration"]["fit"] == temperature["fit"]
    assert report["calibration"]["strict"]["samples"] == 99                                       # the headline calibration section is the held-out view


def test_a_calibration_split_below_the_minimum_is_descriptive_only(tmp_path):
    frozen = build(tmp_path, train=90, calibration=19, heldout=99).load()
    held = confident(frozen, "heldout")
    report = evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=confident(frozen, "calibration"))
    assert report["temperature_calibration"]["status"] == "descriptive_only" and report["temperature_calibration"]["fit"]["temperature"] is None and report["temperature_calibration"]["applied"] is False
    exactly = build(tmp_path / "20", train=90, calibration=20, heldout=99).load()
    held20 = confident(exactly, "heldout")
    assert evaluate_frozen(exactly, labels_of(held20), plan=FAST_PLAN, policy=POLICY, probabilities=held20,
                           calibration_probabilities=confident(exactly, "calibration"))["temperature_calibration"]["status"] == "fitted_and_applied"


def test_calibration_probabilities_must_cover_exactly_the_calibration_ids_and_name_no_id(tmp_path):
    frozen = build(tmp_path, train=90, calibration=30, heldout=99).load()
    held, calibration = confident(frozen, "heldout"), confident(frozen, "calibration")
    short = dict(list(calibration.items())[1:])
    with pytest.raises(ValueError, match=r"cover exactly the calibration ids: 1 missing, 0 unexpected") as caught:
        evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=short)
    assert not any(i in str(caught.value) for i in calibration)
    with pytest.raises(ValueError, match=r"0 missing, 1 unexpected"):
        evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities={**calibration, "heldout-0000": calibration[next(iter(calibration))]})
    assert [r.item_id for r in calibration_eval_records(frozen, None)] == [r.item_id for r in frozen.records["calibration"]]


def test_heldout_ids_cannot_be_used_as_calibration_data_and_the_two_sets_stay_apart(tmp_path):
    frozen = build(tmp_path, train=90, calibration=30, heldout=99).load()
    held = confident(frozen, "heldout")
    with pytest.raises(ValueError, match="calibration probabilities must cover exactly the calibration ids"):
        evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=held)


def test_a_probability_that_names_a_wrong_label_or_does_not_sum_to_one_is_refused_without_echoing_an_id(tmp_path):
    frozen = build(tmp_path, train=90, calibration=30, heldout=99).load()
    held, calibration = confident(frozen, "heldout"), confident(frozen, "calibration")
    first = next(iter(calibration))
    bad = {**calibration, first: {"positive": 0.9, "negative": 0.9, "neutral": 0.9}}
    with pytest.raises(ValueError, match="must sum to 1") as caught:
        evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=bad)
    assert first not in str(caught.value)
    wrong_label = {**labels_of(held)}
    wrong_label[next(iter(held))] = "neutral" if labels_of(held)[next(iter(held))] != "neutral" else "positive"
    with pytest.raises(ValueError, match="must be the most probable class"):
        evaluate_frozen(frozen, wrong_label, plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=calibration)


def test_the_labels_only_rules_baseline_is_not_calibrated_changed_or_validated(tmp_path):
    frozen = build(tmp_path, train=270, calibration=90, heldout=300).load()
    baseline = {r.item_id: r.label for r in frozen.records["heldout"]}
    report = evaluate_frozen(frozen, baseline, plan=FAST_PLAN, policy=POLICY)
    assert report["temperature_calibration"]["status"] == "labels_only" and report["temperature_calibration"]["applied"] is False and report["temperature_calibration"]["labels_changed"] is False
    assert report["assessment"]["validation"]["status"] == "descriptive_only" and report["assessment"]["activation_recommendation"].startswith("none")


def test_synthetic_evidence_never_produces_validated_even_with_a_fitted_temperature(tmp_path):
    frozen = build(tmp_path, train=270, calibration=90, heldout=300, synthetic=True).load()
    held, calibration = confident(frozen, "heldout", error_every=50), confident(frozen, "calibration", error_every=50)
    report = evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=calibration)
    assert report["temperature_calibration"]["status"] == "fitted_and_applied" and report["assessment"]["validation"]["status"] == "not_validation_evidence"
    assert report["temperature_calibration"]["validated"] is False and report["temperature_calibration"]["activation_recommendation"].startswith("none")


def test_the_report_holds_no_record_text_id_or_register_content(tmp_path):
    frozen = build(tmp_path, train=90, calibration=30, heldout=99).load()
    held, calibration = confident(frozen, "heldout"), confident(frozen, "calibration")
    report = json.dumps(evaluate_frozen(frozen, labels_of(held), plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=calibration))
    for split in ("heldout", "calibration"):
        for record in frozen.records[split][:20]:
            assert record.item_id not in report and all(token not in report for token in record.text.split())
    assert "invented-register-1" not in report and '"ver"' not in report and "deletion" not in report and "consent" not in report          # nothing of the register is copied into a report


# ------------------------------------------------------------------------------------------------------------------------------- the command line
def argv(built, output: Path, *extra: str) -> list[str]:
    return ["--frozen-manifest", str(built.manifest_path), "--records", str(built.records_path), "--rubric", str(built.rubric_path), "--annotator-manifest", str(built.annotators_path),
            "--adjudication-log", str(built.log_path), "--participant-register", str(built.register_path), "--output", str(output), *extra]


def predictions_file(path: Path, probabilities: dict) -> str:
    payload = {k: {"label": max(v, key=v.get), "probabilities": v} for k, v in probabilities.items()}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_the_command_line_needs_the_participant_register(tmp_path, capsys):
    built = build(tmp_path / "set", synthetic=True)
    args = argv(built, tmp_path / "r.json")
    index = args.index("--participant-register")
    with pytest.raises(SystemExit) as caught:
        ev.main(args[:index] + args[index + 2:])
    assert caught.value.code == 2 and "all six of --frozen-manifest" in capsys.readouterr().err


def test_a_predictions_file_that_also_answers_the_calibration_split_is_calibrated_by_the_command_line(tmp_path):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300, synthetic=True)
    frozen = built.load()
    file = predictions_file(tmp_path / "p.json", {**confident(frozen, "heldout"), **confident(frozen, "calibration")})
    out = tmp_path / "r.json"
    assert ev.main(argv(built, out, "--predictions", f"cand={file}")) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    temperature = report["candidates"]["cand"]["temperature_calibration"]
    assert temperature["status"] == "fitted_and_applied" and temperature["fit"]["scored"] == 90 and temperature["heldout_calibrated"]["scored"] == 300
    assert report["candidates"]["rules_baseline"]["temperature_calibration"]["status"] == "labels_only"
    assert report["candidates"]["cand"]["assessment"]["validation"]["status"] == "not_validation_evidence" and report["selection"].startswith("none")


def test_a_probability_file_that_answers_only_the_heldout_split_is_reported_without_a_temperature(tmp_path):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300, synthetic=True)
    frozen = built.load()
    file = predictions_file(tmp_path / "p.json", confident(frozen, "heldout"))
    out = tmp_path / "r.json"
    assert ev.main(argv(built, out, "--predictions", f"cand={file}")) == 0
    temperature = json.loads(out.read_text(encoding="utf-8"))["candidates"]["cand"]["temperature_calibration"]
    assert temperature["status"] == "unavailable" and temperature["fit"]["temperature"] is None and temperature["applied"] is False and "none is invented" in temperature["reason"]


def test_a_partial_calibration_answer_or_a_stray_id_is_refused_without_echoing_it(tmp_path, capsys):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300, synthetic=True)
    frozen = built.load()
    calibration = confident(frozen, "calibration")
    partial = predictions_file(tmp_path / "partial.json", {**confident(frozen, "heldout"), **dict(list(calibration.items())[:10])})
    assert ev.main(argv(built, tmp_path / "r.json", "--predictions", f"cand={partial}")) == 2
    assert "cover exactly the calibration ids: 80 missing" in capsys.readouterr().err
    stray = predictions_file(tmp_path / "stray.json", {**confident(frozen, "heldout"), "train-0000": confident(frozen, "calibration")[next(iter(calibration))]})
    assert ev.main(argv(built, tmp_path / "r2.json", "--predictions", f"cand={stray}")) == 2
    assert "train-0000" not in capsys.readouterr().err


def test_a_labels_only_file_that_also_names_calibration_ids_is_refused(tmp_path, capsys):
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300, synthetic=True)
    frozen = built.load()
    mapping = {**perfect(frozen), **{r.item_id: r.label for r in frozen.records["calibration"]}}
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    assert ev.main(argv(built, tmp_path / "r.json", "--predictions", f"cand={path}")) == 2
    assert "unexpected" in capsys.readouterr().err
