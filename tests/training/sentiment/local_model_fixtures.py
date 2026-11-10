"""Synthetic local model directories for the Path B tests: dummy bytes in the five approved file names, a hand-written `config.json` label map, a synthetic 40-character revision. Nothing here is a model."""
from __future__ import annotations

import json
from pathlib import Path

from training.sentiment import local_model_dir as lm
from training.sentiment.config import CANDIDATES

IDENTIFIER = CANDIDATES["finbert"]["hub_id"]                                   # the candidate's identifier only as a string: nothing is ever resolved
REVISION = "0123456789abcdef0123456789abcdef01234567"                          # synthetic
CONFIG = {"id2label": {"0": "positive", "1": "negative", "2": "neutral"}}


def make_local_dir(root: Path, name: str = "localmodel") -> Path:
    directory = root / name
    directory.mkdir()
    (directory / "model.safetensors").write_bytes(b"DUMMY-WEIGHTS" * 50)
    (directory / "config.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    (directory / "vocab.txt").write_text("[PAD]\n[UNK]\nalpha\n", encoding="utf-8")
    (directory / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (directory / "special_tokens_map.json").write_text("{}", encoding="utf-8")
    return directory


def write_manifest_file(directory: Path, path: Path, *, identifier: str = IDENTIFIER, revision: str = REVISION) -> Path:
    path.write_text(json.dumps(lm.build_manifest(identifier, revision, directory)), encoding="utf-8")
    return path
