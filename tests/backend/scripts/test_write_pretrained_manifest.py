"""`scripts/write_pretrained_manifest.py`: writes a manifest only for a candidate whose gates pass, and what it writes is accepted by the adapter's verifier. Placeholder bytes only."""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wealthpilot.core.sentiment import adapter, registry

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("write_pretrained_manifest", ROOT / "scripts" / "write_pretrained_manifest.py")
tool = importlib.util.module_from_spec(SPEC)
sys.modules["write_pretrained_manifest"] = tool
SPEC.loader.exec_module(tool)                                                                      # type: ignore[union-attr]


def place(root: Path, key: str, extra: dict[str, bytes] | None = None) -> Path:
    directory = root / key
    directory.mkdir(parents=True)
    (directory / "model.safetensors").write_bytes(b"placeholder")
    (directory / "tokenizer_config.json").write_bytes(b"{}")
    (directory / "config.json").write_text(json.dumps({"id2label": {"0": "positive", "1": "negative", "2": "neutral"}, "vocab_size": 100}), encoding="utf-8")
    for name, data in (extra or {}).items():
        (directory / name).write_bytes(data)
    return directory


def test_every_real_candidate_is_refused_with_its_recorded_blocker(tmp_path):
    for key in ("finbert", "roberta"):
        place(tmp_path, key)
        with pytest.raises(tool.ManifestError, match="not permitted to run"):
            tool.build_manifest(key, 90, tmp_path)
    assert "share-alike" in str(registry.FINBERT.blocker) and "safetensors" in registry.ROBERTA.format_note.lower() and registry.ROBERTA.blocker == registry.ROBERTA.licence_note
    assert registry.HORIZON.blocker is None and registry.HORIZON.runnable_in_principle                                          # Horizon: registered for research by the owner (R1); the tool may write its manifest


def test_the_command_line_refuses_and_writes_nothing_for_a_blocked_candidate():
    for key, name in (("finbert", "FinBERT"), ("roberta", "Twitter-RoBERTa (CardiffNLP)")):
        done = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "write_pretrained_manifest.py"), "--candidate", key, "--tokenizer-length", "90"], capture_output=True, text=True, cwd=ROOT, timeout=120)
        assert done.returncode == 1 and done.stdout.startswith(f"REFUSED: {name} is not permitted to run"), done.stdout
        assert not (adapter.PRETRAINED_ROOT / key / adapter.MANIFEST_FILE).exists()


def test_with_the_gates_satisfied_the_manifest_is_accepted_by_the_adapters_verifier(tmp_path, monkeypatch):
    cand = dataclasses.replace(registry.HORIZON, registration=registry.REGISTERED)                                         # TEST-ONLY registration
    monkeypatch.setattr(tool, "by_key", lambda key: cand)
    place(tmp_path, "horizon")
    manifest = tool.build_manifest("horizon", 90, tmp_path)
    (tmp_path / "horizon" / adapter.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    info = adapter.verify_pretrained(cand, tmp_path)
    assert info.labels == ("positive", "negative", "neutral") and info.tokenizer_length == 90 and manifest["revision"] == cand.revision


def test_pickle_capable_files_missing_files_bad_labels_and_a_bad_length_are_refused(tmp_path, monkeypatch):
    cand = dataclasses.replace(registry.HORIZON, registration=registry.REGISTERED)                                         # TEST-ONLY registration
    monkeypatch.setattr(tool, "by_key", lambda key: cand)
    place(tmp_path, "horizon", {"pytorch_model.bin": b"x"})
    with pytest.raises(tool.ManifestError, match="pickle-capable"):
        tool.build_manifest("horizon", 90, tmp_path)
    (tmp_path / "horizon" / "pytorch_model.bin").unlink()
    with pytest.raises(tool.ManifestError, match="--tokenizer-length"):
        tool.build_manifest("horizon", 101, tmp_path)
    (tmp_path / "horizon" / "config.json").write_text(json.dumps({"id2label": {"0": "LABEL_0"}, "vocab_size": 100}), encoding="utf-8")
    with pytest.raises(tool.ManifestError, match="labels"):
        tool.build_manifest("horizon", 90, tmp_path)
    (tmp_path / "horizon" / "model.safetensors").unlink()
    with pytest.raises(tool.ManifestError, match="required files"):
        tool.build_manifest("horizon", 90, tmp_path)


def test_the_script_uses_no_network_and_downloads_nothing():
    source = (ROOT / "scripts" / "write_pretrained_manifest.py").read_text(encoding="utf-8")
    for forbidden in ("socket", "urllib", "requests", "httpx", "from_pretrained", "hf_hub", "snapshot_download", "import torch", "import transformers", "import subprocess", "import pickle"):
        assert forbidden not in source, forbidden
