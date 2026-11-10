"""ADR-052 -- `training/sentiment/frozen_evaluation.py`: the offline plumbing for an approved FROZEN set (owner decision `APPROVE_SCHEMA_AND_WIRE_OFFLINE`, 2026-10-29). Every file here is generated inside the
test from invented tokens (`zq...` words with no meaning); no real dataset, model or user text exists or is read. The hashes are computed here independently of the module under test. The manifest's own
flags (approved, synthetic, rubric frozen and approved, independence) are the test's to state: the code carries them, it cannot establish them, which several tests below pin."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from training.sentiment import frozen_evaluation as fe
from training.sentiment.frozen_evaluation import NEAR_DUPLICATE_THRESHOLD, FrozenEvaluationError, char_ngrams, near_duplicate_similarity, normalize_text, text_hash, evaluate_frozen, heldout_annotator_ratings, heldout_eval_records, load_frozen_evaluation
from frozen_fixtures import Built, build, canonical_hash, perfect, sha, word  # noqa: F401  (the directory's conftest puts this folder on sys.path)
from training.sentiment.metrics import EvaluationPolicy, StatisticsPlan

LABELS = ("positive", "negative", "neutral")
POLICY = EvaluationPolicy.owner_approved()
FAST_PLAN = StatisticsPlan(0.95, 200, 42, 20, 75, False)


# ------------------------------------------------------------------------------------------------------------------------------- loading and the evidence basis
def test_a_complete_set_loads_with_every_check_true_and_an_eligible_evidence_basis(tmp_path):
    frozen = build(tmp_path).load()
    assert all(frozen.checks.values()) and list(frozen.checks) == [
        "manifest_sha256_verified", "records_sha256_verified", "rubric_sha256_verified", "annotator_manifest_verified", "adjudication_log_sha256_verified", "content_label_id_split_hashes_verified",
        "no_personal_data_markers", "record_shape_valid", "counts_consistent", "three_splits_present", "exact_duplicates_excluded", "near_duplicates_excluded", "evidence_status_consistent",
        "rubric_frozen_and_approved", "participant_register_verified", "register_consistent_with_manifest", "calibration_split_sha256_verified", "group_dimensions_approved",
        "duplicate_policy_declared"]
    assert frozen.evidence.describe()["status"] == "eligible_for_owner_review" and {s: len(r) for s, r in frozen.records.items()} == {"train": 90, "calibration": 30, "heldout": 99}
    assert [r.item_id for r in frozen.records["heldout"]] == sorted(r.item_id for r in frozen.records["heldout"])


@pytest.mark.parametrize("kwargs,reason", [(dict(approved=False), "the dataset is not approved"), (dict(fixture=True), "the data is a development fixture"),
                                           (dict(synthetic=True), "the data is synthetic"), (dict(rubric_frozen=False), "the rubric is not frozen"),
                                           (dict(rubric_approved=False), "the rubric is not frozen"), (dict(rubric_version="v0-draft"), "the rubric is not frozen"),
                                           (dict(independence=False), "annotator independence is not attested")])
def test_an_unapproved_synthetic_fixture_or_unfrozen_set_loads_but_is_never_validation_evidence(tmp_path, kwargs, reason):
    frozen = build(tmp_path, **kwargs).load()
    described = frozen.evidence.describe()
    assert described["status"] == "not_validation_evidence" and any(reason in r for r in described["reasons"])
    report = evaluate_frozen(frozen, perfect(frozen), plan=FAST_PLAN, policy=POLICY)
    assert report["assessment"]["validation"]["status"] == "not_validation_evidence"


def test_a_draft_labelled_rubric_is_not_frozen_even_if_the_manifest_says_frozen_and_approved(tmp_path):
    frozen = build(tmp_path, rubric_frozen=True, rubric_approved=True, rubric_version="v0-draft").load()
    assert frozen.checks["rubric_frozen_and_approved"] is False and frozen.evidence.rubric_frozen is False


def test_a_manifest_cannot_claim_more_evidence_than_the_checks_support(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="declares evidence_basis_status 'eligible_for_owner_review' but the verified checks give 'not_validation_evidence'"):
        build(tmp_path / "a", synthetic=True, declared_status="eligible_for_owner_review").load()
    with pytest.raises(FrozenEvaluationError, match="declares evidence_basis_status 'not_validation_evidence' but the verified checks give 'eligible_for_owner_review'"):
        build(tmp_path / "b", declared_status="not_validation_evidence").load()


# ------------------------------------------------------------------------------------------------------------------------------- schema version, immutability and hashes
def test_a_missing_or_unknown_schema_version_is_refused_before_anything_else(tmp_path):
    def drop(m):
        del m["schema_version"]

    with pytest.raises(FrozenEvaluationError, match="without a schema version is refused"):
        build(tmp_path / "a", manifest_edit=drop).load()
    for name, value in (("b", 3), ("c", 0), ("d", "1"), ("e", None)):
        with pytest.raises(FrozenEvaluationError, match="unknown schema_version"):
            build(tmp_path / name, manifest_edit=lambda m, v=value: m.update(schema_version=v)).load()


def test_a_manifest_changed_after_it_was_frozen_is_refused(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="does not match its own manifest_sha256"):
        build(tmp_path, post_edit=lambda m: m.update(dataset_purpose="changed after freezing")).load()


@pytest.mark.parametrize("target,message", [("records.jsonl", "records file does not match"), ("rubric.md", "rubric does not match"), ("annotators.json", "annotator manifest does not match"),
                                            ("adjudication_log.txt", "adjudication log does not match")])
def test_a_changed_file_does_not_match_its_manifest_hash(tmp_path, target, message):
    built = build(tmp_path)
    path = tmp_path / target
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(FrozenEvaluationError, match=message):
        built.load()


def test_the_record_level_hashes_are_recomputed_not_trusted(tmp_path):
    for name in fe.HASH_FIELDS:
        with pytest.raises(FrozenEvaluationError, match=f"recomputed {name} does not match"):
            build(tmp_path / name, manifest_edit=lambda m, n=name: m["hashes"].update({n: "0" * 64})).load()


def test_a_label_changed_in_the_records_with_a_consistent_file_hash_still_breaks_the_label_hash(tmp_path):
    built = build(tmp_path)
    lines = built.records_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["label"] = "negative" if first["label"] != "negative" else "positive"
    lines[0] = json.dumps(first)
    built.records_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = json.loads(built.manifest_path.read_text(encoding="utf-8"))
    manifest["records_file"]["sha256"] = sha(built.records_path.read_bytes())               # the file hash is made consistent on purpose
    manifest["manifest_sha256"] = canonical_hash(manifest)
    built.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(FrozenEvaluationError, match="recomputed labels_sha256 does not match"):
        built.load()


def test_a_missing_file_is_reported_not_skipped(tmp_path):
    built = build(tmp_path)
    built.log_path.unlink()
    with pytest.raises(FrozenEvaluationError, match="adjudication log could not be read"):
        built.load()


def test_hashes_are_line_ending_independent(tmp_path):
    built = build(tmp_path)
    data = built.records_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")          # force CRLF whatever the platform wrote
    built.records_path.write_bytes(data)
    assert built.load().checks["records_sha256_verified"] is True


# ------------------------------------------------------------------------------------------------------------------------------- the manifest fields
def test_every_required_field_is_enforced_including_the_ones_the_owner_added(tmp_path):
    for field in ("dataset_purpose", "license", "provenance", "created_at", "hashes", "evidence_basis_status", "manifest_sha256"):
        def drop(m, f=field):
            del m[f]

        with pytest.raises(FrozenEvaluationError, match=f"missing field '{field}'"):
            if field == "manifest_sha256":
                build(tmp_path / field, post_edit=drop).load()                                 # the immutable hash is added last, so it is dropped after the fact
            else:
                build(tmp_path / field, manifest_edit=drop).load()


def test_malformed_manifest_values_are_refused_with_the_field_named(tmp_path):
    cases = (("a", lambda m: m.update(manifest_status="DRAFT"), "FROZEN"), ("b", lambda m: m["records_file"].update(sha256="ABC"), "records_file"),
             ("c", lambda m: m["duplicates"].update(near_duplicate_threshold=0.0), "near_duplicate_threshold"), ("d", lambda m: m["duplicates"].update(near_duplicate_threshold=1), "near_duplicate_threshold"),
             ("e", lambda m: m.update(label_set="five"), "label_set"), ("f", lambda m: m["annotation"].update(adjudicator="ann-a"), "different person"), ("g", lambda m: m.update(approved="yes"), "'approved'"),
             ("h", lambda m: m["duplicates"].update(cross_split_duplicates_found=2), "cross-split duplicates"), ("i", lambda m: m.update(created_at="2026-01-01"), "'created_at'"),
             ("j", lambda m: m.update(dataset_purpose="  "), "'dataset_purpose'"), ("k", lambda m: m["provenance"].update(source=""), "provenance"),
             ("l", lambda m: m["hashes"].update(extra="0" * 64), "hashes must hold exactly"), ("m", lambda m: m.update(evidence_basis_status="validated"), "evidence_basis_status"),
             ("n", lambda m: m["rubric"].update(approved="yes"), "rubric must hold"), ("o", lambda m: m["annotation"].update(annotators=["ann a"]), "codes only"),
             ("p", lambda m: m["annotation"].update(annotator_manifest_sha256="short"), "annotator_manifest_sha256"))
    for name, edit, message in cases:
        with pytest.raises(FrozenEvaluationError, match=message):
            build(tmp_path / name, manifest_edit=edit).load()


def test_personal_data_markers_in_the_manifest_are_refused_without_echoing_them(tmp_path):
    for name, edit in (("a", lambda m: m.update(dataset_purpose="contact someone@example.com")), ("b", lambda m: m["provenance"].update(source="see https://example.org/page")),
                       ("c", lambda m: m.update(license="account 1234 5678 9012")), ("d", lambda m: m["provenance"].update(collection_method="www.example.org survey"))):
        with pytest.raises(FrozenEvaluationError, match="personal data") as raised:
            build(tmp_path / name, manifest_edit=edit).load()
        assert "example" not in str(raised.value) and "1234" not in str(raised.value)
    assert build(tmp_path / "ok").load().checks["no_personal_data_markers"] is True                  # timestamps and hashes are not mistaken for digit runs


def test_a_manifest_that_is_not_json_is_refused_without_echoing_it(tmp_path):
    built = build(tmp_path)
    built.manifest_path.write_text("{ not json SECRETMARKER", encoding="utf-8")
    with pytest.raises(FrozenEvaluationError) as raised:
        built.load()
    assert "SECRETMARKER" not in str(raised.value)


def test_the_annotator_manifest_must_agree_with_the_manifest(tmp_path):
    for name, edit in (("a", lambda a: a.update(annotators=["ann-a", "ann-c"])), ("b", lambda a: a.update(adjudicator="someone")), ("c", lambda a: a.update(independence_attested=not a["independence_attested"]))):
        built = build(tmp_path / name, annotator_file_edit=edit)
        with pytest.raises(FrozenEvaluationError, match="does not agree with the annotators"):
            built.load()


# ------------------------------------------------------------------------------------------------------------------------------- records, counts and splits
def test_invalid_records_are_counted_by_kind_and_their_text_is_never_in_the_message(tmp_path):
    bad_label = json.dumps({"id": "x1", "text": "SECRETMARKER alpha beta", "label": "ecstatic", "split": "train"})
    bad_split = json.dumps({"id": "x2", "text": "SECRETMARKER gamma delta", "label": "positive", "split": "validation"})
    bad_group = json.dumps({"id": "x3", "text": "SECRETMARKER epsilon zeta", "label": "positive", "split": "train", "groups": {"undeclared": ["a"]}})
    bad_annotator = json.dumps({"id": "x4", "text": "SECRETMARKER eta theta", "label": "positive", "split": "train", "annotator_labels": {"stranger": "positive"}})
    bad_text = json.dumps({"id": "x5", "text": "control\x07character SECRETMARKER", "label": "positive", "split": "train"})
    with pytest.raises(FrozenEvaluationError) as raised:
        build(tmp_path, extra_lines=(bad_label, bad_split, bad_group, bad_annotator, bad_text, "not json SECRETMARKER", json.dumps({"id": "train-0000", "text": "dup id", "label": "positive", "split": "train"}))).load()
    message = str(raised.value)
    for fragment in ("invalid label", "invalid split", "invalid groups", "invalid annotator_labels", "invalid text", "invalid line", "duplicate item id"):
        assert fragment in message, fragment
    assert "SECRETMARKER" not in message


def test_declared_counts_must_match_the_records(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="record_count says"):
        build(tmp_path / "a", manifest_edit=lambda m: m.update(record_count=m["record_count"] + 1)).load()
    with pytest.raises(FrozenEvaluationError, match=r"split_counts\['heldout'\]"):
        build(tmp_path / "b", manifest_edit=lambda m: m["split_counts"].update(heldout=1)).load()
    with pytest.raises(FrozenEvaluationError, match="class_counts for 'train'"):
        build(tmp_path / "c", manifest_edit=lambda m: m["class_counts"]["train"].update(positive=0)).load()


@pytest.mark.parametrize("split", ["train", "calibration", "heldout"])
def test_all_three_splits_are_required(tmp_path, split):
    sizes = {"train": 90, "calibration": 30, "heldout": 99}
    sizes[split] = 0
    with pytest.raises(FrozenEvaluationError, match=f"the '{split}' split is empty"):
        build(tmp_path, **sizes).load()


def test_an_exact_duplicate_across_splits_or_inside_a_split_is_refused_even_if_the_manifest_claims_none(tmp_path):
    def across(records):
        records[-1]["text"] = records[0]["text"].upper()                           # held-out text equals a training text, case-folded

    with pytest.raises(FrozenEvaluationError, match="exact duplicate.*across splits"):
        build(tmp_path / "a", record_edit=across).load()

    def inside(records):
        records[1]["text"] = records[0]["text"]

    with pytest.raises(FrozenEvaluationError, match="exact duplicate.*inside a split"):
        build(tmp_path / "b", record_edit=inside).load()


# 44 letters whose character 5-grams are all distinct: 40 grams. Its 40-character prefix has 36 of them, a subset, so the Jaccard similarity is exactly 36 / 40 = 0.9.
BASE = "abcdefghijklmnopqrstuvwxyz" + "acegikmoqsuwybdfhj"


def pair_with(first_text: str, second_text: str):
    def edit_records(records):
        records[0]["text"], records[-1]["text"] = first_text, second_text

    return edit_records


def test_the_boundary_pair_has_exactly_the_approved_similarity():
    assert len(char_ngrams(BASE)) == 40 and len(char_ngrams(BASE[:40])) == 36
    assert near_duplicate_similarity(BASE, BASE[:40]) == NEAR_DUPLICATE_THRESHOLD == 0.9           # equality: 36 / 40 is the float 0.9


def test_a_cross_split_pair_exactly_at_the_approved_threshold_is_a_near_duplicate(tmp_path):
    with pytest.raises(FrozenEvaluationError, match="near-duplicate similarity threshold") as caught:
        build(tmp_path / "at", record_edit=pair_with(BASE, BASE[:40])).load()
    assert BASE not in str(caught.value) and BASE[:40] not in str(caught.value)                      # a decision never exposes the text


def test_a_cross_split_pair_just_below_the_approved_threshold_is_accepted(tmp_path):
    assert near_duplicate_similarity(BASE, BASE[:39]) < 0.9                                          # 35 / 40
    assert build(tmp_path / "below", record_edit=pair_with(BASE, BASE[:39])).load().checks["near_duplicates_excluded"] is True


def test_a_pair_just_above_the_approved_threshold_is_refused(tmp_path):
    assert near_duplicate_similarity(BASE, BASE[:41]) > 0.9                                          # 37 / 40
    with pytest.raises(FrozenEvaluationError, match="near-duplicate similarity threshold"):
        build(tmp_path / "above", record_edit=pair_with(BASE, BASE[:41])).load()


def test_normalization_makes_unicode_case_and_whitespace_variants_exact_duplicates(tmp_path):
    assert normalize_text("  \uff21bc\tDEF  ghi ") == "abc def ghi" and text_hash("ABC  def") == text_hash("abc def")
    with pytest.raises(FrozenEvaluationError, match="exact duplicate"):
        build(tmp_path / "x", record_edit=pair_with("zqaaaaa zqbbbbb zqccccc", "\uff3aQAAAAA   zqbbbbb\nzqccccc")).load()


def test_character_ngrams_of_short_and_empty_texts_are_defined():
    assert char_ngrams("abc") == frozenset({"abc"}) and char_ngrams("   ") == frozenset() and near_duplicate_similarity("", "") == 1.0


def test_a_manifest_must_declare_exactly_the_approved_method_and_threshold(tmp_path):
    for index, change in enumerate(({"near_duplicate_method": "token-set Jaccard"}, {"near_duplicate_threshold": 0.8}, {"near_duplicate_threshold": 0.95})):
        with pytest.raises(FrozenEvaluationError, match="approved near_duplicate_method"):
            build(tmp_path / str(index), manifest_edit=lambda m, change=change: m["duplicates"].update(change)).load()


# ------------------------------------------------------------------------------------------------------------------------------- predictions, agreement, the report
def test_predictions_must_cover_exactly_the_held_out_ids(tmp_path):
    frozen = build(tmp_path).load()
    predictions = perfect(frozen)
    with pytest.raises(ValueError, match="1 missing, 0 unexpected"):
        heldout_eval_records(frozen, dict(list(predictions.items())[1:]))
    with pytest.raises(ValueError, match="0 missing, 1 unexpected"):
        heldout_eval_records(frozen, {**predictions, "train-0000": "positive"})
    with pytest.raises(ValueError, match="not in the held-out split"):
        heldout_eval_records(frozen, predictions, {"train-0000": {"positive": 1.0, "negative": 0.0, "neutral": 0.0}})
    records = heldout_eval_records(frozen, predictions)
    assert len(records) == 99 and all(r.truth == predictions[r.item_id] for r in records) and records[0].groups["topic"]


def test_the_pre_adjudication_ratings_are_returned_in_item_order_and_must_be_complete(tmp_path):
    frozen = build(tmp_path).load()
    ratings = heldout_annotator_ratings(frozen)
    assert list(ratings) == ["ann-a", "ann-b"] and len(ratings["ann-a"]) == 99 and ratings["ann-a"] != ratings["ann-b"]

    def strip(records):
        del records[-1]["annotator_labels"]["ann-b"]

    with pytest.raises(ValueError, match="from every annotator"):
        heldout_annotator_ratings(build(tmp_path / "x", record_edit=strip).load())


def test_a_complete_set_with_too_few_held_out_examples_is_insufficient_support_never_validated(tmp_path):
    frozen = build(tmp_path).load()                                                             # 99 held-out examples, 33 per class: below 300 and below 75 per class
    report = evaluate_frozen(frozen, perfect(frozen), plan=StatisticsPlan.owner_approved(), policy=POLICY)
    assessment = report["assessment"]
    assert assessment["validation"]["status"] == "insufficient_support"
    gates = {g["gate"]: g for g in assessment["gates"]}
    assert gates["support:heldout_size"]["status"] == "not_met" and gates["support:class:positive"]["observed"] == 33
    assert report["manifest"]["dataset_id"] == "invented-fixture" and all(report["manifest"]["checks"].values()) and report["manifest"]["manifest_sha256"] == frozen.manifest["manifest_sha256"]
    assert "R14" in assessment["activation"] and assessment["selection"].startswith("none") and assessment["activation_recommendation"].startswith("none")


def test_the_full_chain_reaches_validated_only_when_every_condition_is_stated_true_and_met_which_is_a_logic_test_not_evidence(tmp_path):
    frozen = build(tmp_path, train=270, calibration=90, heldout=300).load()                  # 100 held-out examples per class, the approved minimum is 300 and 75
    predictions = {r.item_id: (r.label if i % 12 else None) for i, r in enumerate(frozen.records["heldout"])}             # about 8% abstentions, the rest right
    probabilities = {r.item_id: {label: (0.9 if label == r.label else 0.05) for label in LABELS} for r in frozen.records["heldout"]}
    calibration_probabilities = {r.item_id: {label: (0.9 if label == r.label else 0.05) for label in LABELS} for r in frozen.records["calibration"]}
    report = evaluate_frozen(frozen, predictions, plan=StatisticsPlan.owner_approved(), policy=POLICY, probabilities=probabilities, calibration_probabilities=calibration_probabilities)
    assert report["assessment"]["validation"]["status"] == "validated" and report["assessment"]["validation"]["unmet_or_missing"] == []
    assert report["temperature_calibration"]["status"] == "fitted_and_applied" and report["temperature_calibration"]["validated"] is False
    without = evaluate_frozen(frozen, predictions, plan=StatisticsPlan.owner_approved(), policy=POLICY, probabilities=probabilities)          # no calibration-split probabilities: no temperature, no `validated`
    assert without["assessment"]["validation"]["status"] == "descriptive_only" and "temperature_calibration: not_evaluable" in without["assessment"]["validation"]["unmet_or_missing"]
    assert report["agreement"]["primary_statistic"] == "COHEN_KAPPA" and report["calibration"]["strict"]["samples"] == 300
    assert report["assessment"]["activation_recommendation"].startswith("none")                  # even then: nothing recommends activation
    # flipping ONE declared condition removes the word: the code can only carry the manifest's statements, so independence and representativeness stay the owner's to establish
    unattested = build(tmp_path / "u", train=270, calibration=90, heldout=300, independence=False).load()
    assert evaluate_frozen(unattested, {r.item_id: r.label for r in unattested.records["heldout"]}, plan=StatisticsPlan.owner_approved(), policy=POLICY)["assessment"]["validation"]["status"] == "not_validation_evidence"


def test_no_report_contains_record_text_or_record_ids(tmp_path):
    frozen = build(tmp_path).load()
    report = json.dumps(evaluate_frozen(frozen, perfect(frozen), plan=FAST_PLAN, policy=POLICY))
    for record in frozen.records["heldout"][:20]:
        assert record.item_id not in report
        assert all(token not in report for token in record.text.split())


def test_the_report_is_reproducible(tmp_path):
    frozen = build(tmp_path).load()
    one = json.dumps(evaluate_frozen(frozen, perfect(frozen), plan=FAST_PLAN, policy=POLICY), sort_keys=True)
    two = json.dumps(evaluate_frozen(build(tmp_path / "again").load(), perfect(frozen), plan=FAST_PLAN, policy=POLICY), sort_keys=True)
    assert one == two


# ------------------------------------------------------------------------------------------------------------------------------- isolation
def test_the_module_stays_offline_unlogged_and_unconnected_to_activation():
    source = Path(fe.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {alias.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__", "hashlib", "json", "re", "unicodedata", "datetime", "dataclasses", "pathlib", "typing", "training", "wealthpilot"}, imported
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {"print", "logging", "logger", "socket", "requests", "urllib", "environ", "getenv"} & names
    assert not any(m.startswith(("wealthpilot.api", "wealthpilot.config", "wealthpilot.agents", "wealthpilot.security", "wealthpilot.core.sentiment_model")) for m in {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module})
    assert "SENTIMENT_MODEL_ENABLED" not in source
