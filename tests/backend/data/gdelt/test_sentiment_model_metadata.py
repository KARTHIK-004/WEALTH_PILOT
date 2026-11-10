"""Offline model-metadata review. All inputs are SYNTHETIC dictionaries shaped like a model's public metadata: they are not the real models' files and prove nothing about any real model."""

from __future__ import annotations

from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import model_metadata as mm

SHA = "0123456789abcdef0123456789abcdef01234567"
API = {"sha": SHA, "siblings": [{"rfilename": "config.json"}, {"rfilename": "README.md"}, {"rfilename": "model.safetensors"}, {"rfilename": "pytorch_model.bin"}]}
CFG = {"id2label": {"0": "positive", "1": "negative", "2": "neutral"}}
CARD = "---\nlanguage: en\nlicense: apache-2.0\n---\n# card text"
PKG = Path(__file__).resolve().parents[4] / "backend/wealthpilot/data/gdelt/sentiment"


def test_a_clear_config_maps_one_to_one_and_keeps_the_declared_index_order():
    r = mm.review_metadata("synthetic/model", API, CFG, CARD)
    assert r.label_map == {"positive": "positive", "negative": "negative", "neutral": "neutral"}
    assert r.id2label == {"0": "positive", "1": "negative", "2": "neutral"} and r.revision == SHA
    assert r.card_license == "apache-2.0" and r.trust == mm.TRUST == "MODEL_CARD_CLAIM_NOT_VERIFIED"
    assert r.weight_files == ("model.safetensors", "pytorch_model.bin")                         # listed, never read


def test_case_differences_map_but_a_different_declared_order_is_preserved_not_assumed():
    r = mm.review_metadata("synthetic/model", API, {"id2label": {"0": "Neutral", "1": "Positive", "2": "Negative"}}, CARD)
    assert r.label_map == {"Neutral": "neutral", "Positive": "positive", "Negative": "negative"}
    assert list(r.id2label.values()) == ["Neutral", "Positive", "Negative"]                      # a scorer must follow THIS order, not an assumed one


@pytest.mark.parametrize("cfg", [{}, {"id2label": {"0": "LABEL_0", "1": "LABEL_1", "2": "LABEL_2"}}, {"id2label": {"0": "positive", "1": "negative"}},
                                 {"id2label": {"0": "positive", "1": "positive", "2": "neutral"}}, {"id2label": {"0": "bullish", "1": "bearish", "2": "neutral"}},
                                 {"id2label": {"0": "positive", "1": "negative", "2": "neutral", "3": "mixed"}}, {"id2label": {"0": 1, "1": 2, "2": 3}}])
def test_ambiguous_or_incomplete_labels_are_refused(cfg):
    with pytest.raises(mm.ModelMetadataError):
        mm.label_map_from_config(cfg)


@pytest.mark.parametrize("api", [{}, {"sha": "main"}, {"sha": SHA.upper()}, {"sha": SHA[:-1]}])
def test_a_revision_must_be_a_40_hex_commit(api):
    with pytest.raises(mm.ModelMetadataError, match="40-hex"):
        mm.review_metadata("synthetic/model", api, CFG, CARD)


def test_a_missing_licence_is_reported_as_none_not_guessed():
    assert mm.review_metadata("synthetic/model", API, CFG, "# no front matter").card_license is None
    assert mm.review_metadata("synthetic/model", API, CFG, "---\nlanguage: en\n---\n").card_license is None


def test_the_module_makes_no_request_and_imports_no_runtime():
    code = "\n".join(l for l in (PKG / "model_metadata.py").read_text(encoding="utf-8").splitlines() if l.startswith(("import ", "from ")))
    assert not any(m in code for m in ("requests", "urllib", "http", "socket", "torch", "transformers", "tensorflow", "huggingface"))
