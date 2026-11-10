"""Helpers for the stand-in tests of the Transformer seam (ADR-052). Everything here is invented and local: a hand-written 25-token vocabulary, a SYNTHETIC revision hash (it names no real
revision and nothing is ever resolved or downloaded), fixed token ids, and placeholder bytes that are not a serialized pickle. No real model, Hub id, dataset or user text is used."""

from __future__ import annotations

import json
import struct
from pathlib import Path

VOCAB = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"] + "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon".split()
WORDS_IDS = [2, 5, 6, 1, 7, 3]                       # "alpha beta unknownword gamma" -> [CLS] alpha beta [UNK] gamma [SEP]
FIXED_IDS = [[2, 5, 6, 7, 3]]                        # [CLS] alpha beta gamma [SEP]
REVISION = "0123456789abcdef0123456789abcdef01234567"      # synthetic: a well-formed commit hash that exists nowhere
PLACEHOLDER = b"NOT-A-CHECKPOINT-PLACEHOLDER (not a serialized pickle)"
WEIGHT_SUFFIXES = (".bin", ".pt", ".pth", ".pt2", ".pkl", ".pickle", ".ckpt", ".joblib")
LABELS = ("positive", "negative", "neutral")


def write_legacy_tokenizer(directory: Path) -> Path:
    """A directory shaped like a downloaded BERT checkpoint (vocab.txt + tokenizer_config.json + special_tokens_map.json), written by hand."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "vocab.txt").write_text("\n".join(VOCAB) + "\n", encoding="utf-8")
    (directory / "tokenizer_config.json").write_text(json.dumps({"tokenizer_class": "BertTokenizer", "do_lower_case": True}), encoding="utf-8")
    (directory / "special_tokens_map.json").write_text(json.dumps({"unk_token": "[UNK]", "sep_token": "[SEP]", "pad_token": "[PAD]", "cls_token": "[CLS]", "mask_token": "[MASK]"}), encoding="utf-8")
    return directory


def listing(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)).replace("\\", "/") for p in directory.rglob("*") if p.is_file())


def weight_like_files(directory: Path) -> list[str]:
    """Files named like pickle checkpoints, TorchScript or exported programs (.bin, .pt, .pth, .pt2, ...)."""
    return [name for name in listing(directory) if name.lower().endswith(WEIGHT_SUFFIXES)]


def safetensors_header(path: Path) -> dict:
    raw = path.read_bytes()
    (length,) = struct.unpack("<Q", raw[:8])
    return json.loads(raw[8:8 + length])
