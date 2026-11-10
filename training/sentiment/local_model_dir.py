"""Path B (form item C1, owner decision 2026-10-29): local, conversion-free use of ONE verified model directory for OFFLINE EVALUATION.

STATUS: PREPARED AND TESTED OFFLINE WITH SYNTHETIC FIXTURES ONLY. It is NOT wired into the trainer (`train_sentiment_transformer.py`), the evaluation script, the backend or any setting, and it has never
seen a real model. The owner's approval of this code change (and of every download gate) is still pending; nothing imports this module.

What it does, and nothing more:
- `build_manifest`: after an APPROVED download has produced a directory, hash its five approved files independently and write the manifest that is then frozen BEFORE anything is loaded.
- `verify_model_directory`: a directory is usable only if it holds EXACTLY the five approved files (`model.safetensors`, `config.json`, `vocab.txt`, `tokenizer_config.json`,
  `special_tokens_map.json`), no other entry (no sub-directory, no hidden file, no link, never a pickle-capable format), and every SHA-256 and size equals the manifest, whose own hash and 40-character
  revision are checked. Failures are `LocalModelError` with a fixed code: never a path, a hash or any content.
- `load_classifier`: re-verifies, then loads ONLY from that directory with `local_files_only=True`, `trust_remote_code=False` and `use_safetensors=True`, on the CPU. No Hub identifier is ever passed, so the
  library's Hub code path (download, conversion thread) is never reached.
- `predictions_payload`: class probabilities for held-out texts in the owner-approved E2 format (item id -> {"label", "probabilities"}), computed here by a stable softmax of the model's logits. The label is
  the most probable class; no abstention threshold exists because none has been approved, and none is invented.

Standard library only at import time (`transformers` and `torch` are imported lazily inside `load_classifier`, or injected for tests). No network module, no environment variable, no logger, no `print`.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from wealthpilot.core.sentiment_model import is_commit_hash, manifest_sha256

SCHEMA = "local_model_manifest_v1"
APPROVED_FILES = ("config.json", "model.safetensors", "special_tokens_map.json", "tokenizer_config.json", "vocab.txt")
PICKLE_CAPABLE_SUFFIXES = (".bin", ".pt", ".pth", ".pt2", ".pkl", ".pickle", ".h5", ".msgpack", ".ckpt", ".onnx", ".npy", ".npz", ".joblib", ".zip", ".tar", ".gz", ".py")
LABELS = ("positive", "negative", "neutral")
CODES = ("invalid_manifest", "invalid_revision", "invalid_identifier", "not_a_directory", "link_refused", "missing_file", "unexpected_file", "forbidden_file_format", "size_mismatch", "hash_mismatch",
         "invalid_label_map", "load_failed", "inference_failed", "invalid_input")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHUNK = 1 << 20


class LocalModelError(RuntimeError):
    """A refusal with a fixed code and nothing else (no path, hash, text or library message)."""

    def __init__(self, code: str) -> None:
        assert code in CODES, code
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VerifiedModelDirectory:
    path: Path
    identifier: str
    revision: str
    manifest: Mapping[str, Any] = field(repr=False)

    def recheck(self) -> "VerifiedModelDirectory":
        """Verify again immediately before use (the directory could change between the check and the load)."""
        return verify_model_directory(self.path, self.manifest, identifier=self.identifier, revision=self.revision)


def _scan(directory: Path) -> dict[str, tuple[str, int]]:
    """Name -> (SHA-256, size) of the EXACT approved file set. Refuses links, sub-directories, hidden or unknown entries and every pickle-capable format; reads each file once, in chunks."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise LocalModelError("not_a_directory")
    found: dict[str, tuple[str, int]] = {}
    with os.scandir(directory) as entries:
        listing = sorted(entries, key=lambda e: e.name)
    for entry in listing:
        if entry.is_symlink():
            raise LocalModelError("link_refused")
        if entry.name.lower().endswith(PICKLE_CAPABLE_SUFFIXES):
            raise LocalModelError("forbidden_file_format")
        if entry.name not in APPROVED_FILES or not entry.is_file(follow_symlinks=False):
            raise LocalModelError("unexpected_file")
    names = {entry.name for entry in listing}
    if names != set(APPROVED_FILES):
        raise LocalModelError("missing_file")
    for name in APPROVED_FILES:
        digest, size = hashlib.sha256(), 0
        with open(directory / name, "rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(chunk)
                size += len(chunk)
        found[name] = (digest.hexdigest(), size)
    return found


def build_manifest(identifier: str, revision: str, directory: Path) -> dict[str, Any]:
    """The manifest for a directory produced by an APPROVED download: every file hashed independently here, the revision the immutable 40-character hash. Frozen before the directory is loaded."""
    if not isinstance(identifier, str) or not _IDENTIFIER.match(identifier):
        raise LocalModelError("invalid_identifier")
    if not is_commit_hash(revision):
        raise LocalModelError("invalid_revision")
    scanned = _scan(directory)
    files = {name: digest for name, (digest, _) in scanned.items()}
    return {"schema": SCHEMA, "identifier": identifier, "revision": revision, "files": files, "sizes": {name: size for name, (_, size) in scanned.items()}, "manifest_sha256": manifest_sha256(files)}


def _check_manifest(manifest: object) -> tuple[str, str, dict[str, str], dict[str, int]]:
    if not isinstance(manifest, Mapping) or set(manifest) != {"schema", "identifier", "revision", "files", "sizes", "manifest_sha256"} or manifest["schema"] != SCHEMA:
        raise LocalModelError("invalid_manifest")
    identifier, revision, files, sizes = manifest["identifier"], manifest["revision"], manifest["files"], manifest["sizes"]
    if not isinstance(identifier, str) or not _IDENTIFIER.match(identifier):
        raise LocalModelError("invalid_identifier")
    if not is_commit_hash(revision):
        raise LocalModelError("invalid_revision")
    if not (isinstance(files, Mapping) and set(files) == set(APPROVED_FILES) and all(isinstance(v, str) and _SHA256.match(v) for v in files.values())):
        raise LocalModelError("invalid_manifest")
    if not (isinstance(sizes, Mapping) and set(sizes) == set(APPROVED_FILES) and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in sizes.values())):
        raise LocalModelError("invalid_manifest")
    if not (isinstance(manifest["manifest_sha256"], str) and manifest["manifest_sha256"] == manifest_sha256(dict(files))):
        raise LocalModelError("invalid_manifest")
    return identifier, revision, dict(files), dict(sizes)


def verify_model_directory(directory: Path, manifest: Mapping[str, Any], *, identifier: str | None = None, revision: str | None = None) -> VerifiedModelDirectory:
    """The one gate in front of every load. `identifier` / `revision`, when given, must equal the manifest's (the caller pins what the owner approved)."""
    manifest_identifier, manifest_revision, files, sizes = _check_manifest(manifest)
    if identifier is not None and identifier != manifest_identifier:
        raise LocalModelError("invalid_identifier")
    if revision is not None and (not is_commit_hash(revision) or revision != manifest_revision):
        raise LocalModelError("invalid_revision")
    scanned = _scan(directory)
    for name in APPROVED_FILES:
        digest, size = scanned[name]
        if size != sizes[name]:
            raise LocalModelError("size_mismatch")
        if digest != files[name]:
            raise LocalModelError("hash_mismatch")
    return VerifiedModelDirectory(Path(directory), manifest_identifier, manifest_revision, dict(manifest))


def read_label_order(verified: VerifiedModelDirectory) -> tuple[str, ...]:
    """The class order of the model, from the verified `config.json` `id2label`: indices 0..n-1, each a primary label (case-insensitive), no repeat. Anything else is refused: no label is assumed."""
    try:
        config = json.loads((verified.path / "config.json").read_text(encoding="utf-8"))
        mapping = config["id2label"]
        order = tuple(str(mapping[str(i)]).strip().lower() for i in range(len(mapping)))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise LocalModelError("invalid_label_map") from None
    if len(order) != len(LABELS) or set(order) != set(LABELS):
        raise LocalModelError("invalid_label_map")
    return order


def softmax(logits: Sequence[float]) -> list[float]:
    """Numerically stable softmax. A non-finite logit is refused."""
    if not logits or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in logits):
        raise LocalModelError("inference_failed")
    top = max(logits)
    exps = [math.exp(x - top) for x in logits]
    total = sum(exps)
    return [e / total for e in exps]


class LocalClassifier:
    """A model loaded from a verified directory. `predict` returns one {label: probability} per text, in the input order."""

    def __init__(self, verified: VerifiedModelDirectory, tokenizer: Any, model: Any, torch_module: Any, order: tuple[str, ...]) -> None:
        self.verified, self._tokenizer, self._model, self._torch, self._order = verified, tokenizer, model, torch_module, order

    def predict(self, texts: Sequence[str]) -> list[dict[str, float]]:
        if not isinstance(texts, (list, tuple)) or not texts or not all(isinstance(t, str) and t.strip() for t in texts):
            raise LocalModelError("invalid_input")
        try:
            encoded = self._tokenizer(list(texts), return_tensors="pt", padding=True, truncation=True)
            with self._torch.no_grad():
                rows = self._model(**encoded).logits.tolist()
        except Exception:
            raise LocalModelError("inference_failed") from None
        if not isinstance(rows, list) or len(rows) != len(texts) or any(not isinstance(r, list) or len(r) != len(self._order) for r in rows):
            raise LocalModelError("inference_failed")
        return [dict(zip(self._order, softmax(row))) for row in rows]


def load_classifier(verified: VerifiedModelDirectory, *, transformers_module: Any = None, torch_module: Any = None) -> LocalClassifier:
    """Re-verify, then load from the local directory only. The libraries are imported here (or injected by a test); the directory path is the only model reference ever passed to them."""
    verified = verified.recheck()
    order = read_label_order(verified)
    try:
        transformers = transformers_module or importlib.import_module("transformers")
        torch = torch_module or importlib.import_module("torch")
        path = str(verified.path)
        tokenizer = transformers.AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        model = transformers.AutoModelForSequenceClassification.from_pretrained(path, local_files_only=True, trust_remote_code=False, use_safetensors=True)
        model.to("cpu")
        model.eval()
    except Exception:
        raise LocalModelError("load_failed") from None
    return LocalClassifier(verified, tokenizer, model, torch, order)


def predictions_payload(item_texts: Mapping[str, str], classifier: LocalClassifier, *, batch_size: int = 16) -> dict[str, dict[str, Any]]:
    """Held-out item id -> {"label", "probabilities"} (the E2 format). Every item gets the most probable class as its label: no abstention rule has been approved. The texts are only read, never kept."""
    if not isinstance(item_texts, Mapping) or not item_texts or not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise LocalModelError("invalid_input")
    ids = list(item_texts)
    payload: dict[str, dict[str, Any]] = {}
    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        for item_id, probabilities in zip(batch, classifier.predict([item_texts[i] for i in batch])):
            label = max(LABELS, key=lambda name: (probabilities[name], -LABELS.index(name)))
            payload[item_id] = {"label": label, "probabilities": probabilities}
    return payload
