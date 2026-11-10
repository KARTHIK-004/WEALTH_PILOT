"""ADR-052 -- `training/sentiment/dataset.py`: the manifest gate, label mapping, duplicate handling and the deterministic, leakage-free split. Invented sentences only (a development fixture)."""

from __future__ import annotations

import json
import random

import pytest
from sentiment_fixtures import approved_manifest, make_rows, manifest_dict, write_jsonl, write_manifest

from training.sentiment.config import LABELS
from training.sentiment.dataset import (
    ManifestError,
    check_no_leakage,
    label_counts,
    load_manifest,
    load_rows,
    split_rows,
    validate_manifest,
)

FRACTIONS = (0.8, 0.1, 0.1)


# ------------------------------------------------------------------------------------------------ the manifest gate


def test_the_shipped_template_is_not_an_approved_dataset():
    from training.sentiment.config import REPO_ROOT

    template = json.loads((REPO_ROOT / "training/sentiment/dataset_manifest.template.json").read_text(encoding="utf-8"))
    with pytest.raises(ManifestError):
        validate_manifest(template)
    assert template["approved"] is False and template["development_fixture"] is False


def test_an_unapproved_dataset_is_refused_for_training():
    with pytest.raises(ManifestError, match="not approved"):
        validate_manifest(manifest_dict(development_fixture=False, approved=False))


def test_an_approved_dataset_must_name_who_approved_it_and_a_fixture_is_only_for_tests():
    with pytest.raises(ManifestError, match="approved_by"):
        validate_manifest(manifest_dict(development_fixture=False, approved=True, approved_by=""))
    with pytest.raises(ManifestError, match="development fixture"):
        validate_manifest(manifest_dict())                                              # a fixture is refused unless the caller (a test) says so
    assert validate_manifest(manifest_dict(), allow_development_fixture=True).development_fixture is True
    assert validate_manifest(approved_manifest()).approved_by == "test double"


@pytest.mark.parametrize("field", ["license", "source", "url", "language", "preprocessing", "duplicate_policy", "domain_note", "label_definitions", "label_map", "split_policy", "limitations"])
def test_every_documentation_field_is_required(field):
    raw = approved_manifest()
    del raw[field]
    with pytest.raises(ManifestError, match=field):
        validate_manifest(raw)


@pytest.mark.parametrize("change", [dict(license=" "), dict(sample_count=0), dict(label_map={"a": "furious"}), dict(split_policy={"train": 0.8}), dict(limitations=[]), dict(approved="yes")])
def test_invalid_documentation_is_refused(change):
    with pytest.raises(ManifestError):
        validate_manifest(approved_manifest(**change))


def test_intensity_labels_must_say_how_they_were_obtained():
    with pytest.raises(ManifestError, match="intensity_definition"):
        validate_manifest(approved_manifest(has_intensity=True, intensity_definition=""))
    assert validate_manifest(approved_manifest(has_intensity=True, intensity_definition="annotators rated -1..1")).has_intensity is True


def test_an_unreadable_manifest_is_a_manifest_error_without_its_content(tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text("{not json PRIVATE", encoding="utf-8")
    with pytest.raises(ManifestError) as info:
        load_manifest(bad)
    assert "PRIVATE" not in str(info.value)


# ------------------------------------------------------------------------------------------------ loading, label mapping, duplicates


def test_labels_are_mapped_through_the_manifest_and_invalid_lines_are_counted_never_echoed(tmp_path):
    manifest = validate_manifest(approved_manifest(label_map={"bullish": "positive", "bearish": "negative", "flat": "neutral"}))
    rows = [{"text": "I feel hopeful about my savings", "label": "bullish"}, {"text": "I am anxious about my loan", "label": "bearish"}, {"text": "My budget is reviewed monthly", "label": "flat"},
            {"text": "unknown label text here", "label": "ecstatic"}, {"text": "ab", "label": "flat"}, {"text": "bad\x07control character PRIVATE", "label": "flat"}, {"label": "flat"}]
    path = write_jsonl(tmp_path / "d.jsonl", rows, extra_lines=["{not json PRIVATE"])
    loaded, report = load_rows(path, manifest)
    assert sorted((r.label, r.text) for r in loaded) == sorted([("positive", "I feel hopeful about my savings"), ("negative", "I am anxious about my loan"), ("neutral", "My budget is reviewed monthly")])
    assert report.read == 8 and report.kept == 3
    assert dict(report.skipped) == {"unknown_label": 1, "empty_or_too_short": 1, "unusable_text": 1, "missing_text": 1, "bad_json": 1}
    assert "PRIVATE" not in repr(report)


def test_text_is_normalised_exactly_like_user_text(tmp_path):
    manifest = validate_manifest(approved_manifest())
    path = write_jsonl(tmp_path / "d.jsonl", [{"text": "  I   feel\n\thopeful   about my savings  ", "label": "positive"}])
    assert load_rows(path, manifest)[0][0].text == "I feel hopeful about my savings"


def test_exact_duplicates_are_kept_once_and_conflicting_labels_are_removed(tmp_path):
    manifest = validate_manifest(approved_manifest())
    rows = [{"text": "I feel hopeful about my savings", "label": "positive"}, {"text": "i FEEL hopeful about my  savings", "label": "positive"},         # same text, same label
            {"text": "I worry about my loan", "label": "negative"}, {"text": "I worry about my loan", "label": "neutral"},                                # same text, different labels
            {"text": "My budget is reviewed monthly", "label": "neutral"}]
    loaded, report = load_rows(write_jsonl(tmp_path / "d.jsonl", rows), manifest)
    assert sorted(r.text for r in loaded) == ["I feel hopeful about my savings", "My budget is reviewed monthly"]
    assert (report.exact_duplicates_removed, report.conflicting_labels_removed) == (1, 2)


def test_intensity_is_accepted_only_when_the_manifest_has_it_and_only_within_range(tmp_path):
    rows = [{"text": "I feel hopeful about my savings", "label": "positive", "intensity": 0.6}, {"text": "I am anxious about my loan", "label": "negative", "intensity": -3}]
    without = load_rows(write_jsonl(tmp_path / "a.jsonl", rows), validate_manifest(approved_manifest()))
    assert without[0] == [] and without[1].skipped["bad_intensity"] == 2
    with_intensity = load_rows(write_jsonl(tmp_path / "b.jsonl", rows), validate_manifest(approved_manifest(has_intensity=True, intensity_definition="annotator rating -1..1")))
    assert [(r.text, r.intensity) for r in with_intensity[0]] == [("I feel hopeful about my savings", 0.6)] and with_intensity[1].skipped["bad_intensity"] == 1


# ------------------------------------------------------------------------------------------------ the split


def rows_from(raw: list[dict], tmp_path):
    return load_rows(write_jsonl(tmp_path / "s.jsonl", raw), validate_manifest(approved_manifest()))[0]


def test_the_split_is_reproducible_and_independent_of_input_order(tmp_path):
    raw = make_rows(60, group_every=3)
    shuffled = raw[:]
    random.Random(1).shuffle(shuffled)
    a, b = split_rows(rows_from(raw, tmp_path), 42, FRACTIONS), split_rows(rows_from(shuffled, tmp_path), 42, FRACTIONS)
    assert (a.train, a.validation, a.test) == (b.train, b.validation, b.test)
    other = split_rows(rows_from(raw, tmp_path), 7, FRACTIONS)
    assert other.test != a.test                                                          # a different seed gives a different split


def test_the_split_has_every_class_in_every_part_keeps_groups_whole_and_is_leak_free(tmp_path):
    rows = rows_from(make_rows(60, group_every=3), tmp_path)
    splits = split_rows(rows, 42, FRACTIONS)
    assert len(splits.train) + len(splits.validation) + len(splits.test) == len(rows)
    for part in (splits.train, splits.validation, splits.test):
        assert all(count > 0 for count in label_counts(part).values()), label_counts(part)
    assert abs(len(splits.test) / len(rows) - 0.1) < 0.05 and len(splits.train) > 5 * len(splits.test)
    check_no_leakage(splits)
    groups = {part: {r.group for r in getattr(splits, part)} for part in ("train", "validation", "test")}
    assert not (groups["train"] & groups["test"]) and not (groups["train"] & groups["validation"]) and not (groups["validation"] & groups["test"])


def test_a_leak_between_splits_is_detected():
    from training.sentiment.dataset import LabelledRow, Splits

    leaky = Splits((LabelledRow("same text here", "positive", None, "g1"),), (LabelledRow("other text there", "negative", None, "g2"),), (LabelledRow("SAME text here", "positive", None, "g3"),))
    with pytest.raises(ValueError, match="duplicate text"):
        check_no_leakage(leaky)
    shared_group = Splits((LabelledRow("one text here", "positive", None, "g"),), (), (LabelledRow("two text here", "negative", None, "g"),))
    with pytest.raises(ValueError, match="group straddles"):
        check_no_leakage(shared_group)


def test_invalid_fractions_are_refused(tmp_path):
    with pytest.raises(ValueError):
        split_rows(rows_from(make_rows(10), tmp_path), 42, (0.5, 0.2, 0.2))
    with pytest.raises(ValueError):
        split_rows(rows_from(make_rows(10), tmp_path), 42, (1.0, 0.0, 0.0))


def test_the_label_counts_cover_exactly_the_three_classes(tmp_path):
    counts = label_counts(rows_from(make_rows(5), tmp_path))
    assert set(counts) == set(LABELS) and sum(counts.values()) == 15
    assert write_manifest(tmp_path / "m.json", approved_manifest()).exists()
