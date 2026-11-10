"""Offline review of a model's metadata files, for use AFTER an owner-authorised metadata-only read. Pure: it parses dictionaries and text the caller already has; it makes no request and loads no weights.

Nothing here verifies a model. Every licence or training-data statement comes from the model card and is returned labelled ``MODEL_CARD_CLAIM_NOT_VERIFIED``; the owner still has to review the licence text.
What it does enforce is mechanical: the revision is a 40-hex commit id, the file list names no weights the review would need, and the label names map one-to-one onto ``positive`` / ``negative`` / ``neutral``
(a label such as ``LABEL_0`` is refused as ambiguous: a silent reordering would invert sentiment).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.schema import LABELS

TRUST = "MODEL_CARD_CLAIM_NOT_VERIFIED"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_LICENSE_LINE = re.compile(r"^license:\s*(\S.*?)\s*$", re.MULTILINE)
_WEIGHT_SUFFIXES = (".safetensors", ".bin", ".h5", ".onnx", ".pt", ".pth", ".msgpack", ".gguf", ".tflite", ".ot")


class ModelMetadataError(GdeltToolError):
    code = "sentiment_model_metadata_error"


def label_map_from_config(config: Mapping[str, object]) -> dict[str, str]:
    """Map the model's own label names (``id2label`` values) one-to-one onto the project labels, case-insensitively. Refuses anything ambiguous."""
    id2label = config.get("id2label")
    if not isinstance(id2label, Mapping) or len(id2label) != 3:
        raise ModelMetadataError("config.id2label must name exactly three labels")
    out: dict[str, str] = {}
    for idx, name in id2label.items():
        if not isinstance(name, str) or name.strip().lower() not in LABELS:
            raise ModelMetadataError(f"label {name!r} (index {idx}) is not one of {LABELS}: the mapping is ambiguous and needs an owner decision")
        out[name] = name.strip().lower()
    if sorted(out.values()) != sorted(LABELS):
        raise ModelMetadataError(f"the labels do not map one-to-one onto {LABELS}")
    return out


@dataclass(frozen=True)
class MetadataReview:
    model_id: str
    revision: str                          # the 40-hex commit id the files were read at
    label_map: Mapping[str, str]           # model label -> project label (from config.json)
    id2label: Mapping[str, str]            # index -> model label, as the checkpoint declares it (order matters for the scorer)
    card_license: str | None               # as written in the model card front matter; a claim, not a verified licence
    weight_files: tuple[str, ...]          # listed only, never read
    trust: str = TRUST


def review_metadata(model_id: str, api: Mapping[str, object], config: Mapping[str, object], readme: str) -> MetadataReview:
    """``api`` is the model's public metadata JSON (with ``sha`` and ``siblings``), ``config`` its config.json, ``readme`` its model card text."""
    sha = api.get("sha")
    if not (isinstance(sha, str) and _SHA40.match(sha)):
        raise ModelMetadataError("the metadata must carry a 40-hex commit id (the revision to pin)")
    siblings = api.get("siblings", [])
    names = tuple(sorted(str(s.get("rfilename")) for s in siblings if isinstance(s, Mapping))) if isinstance(siblings, list) else ()
    lm = _LICENSE_LINE.search(readme.split("---")[1]) if readme.startswith("---") and readme.count("---") >= 2 else None
    id2label = {str(k): str(v) for k, v in config["id2label"].items()} if isinstance(config.get("id2label"), Mapping) else {}   # type: ignore[union-attr]
    return MetadataReview(model_id, sha, label_map_from_config(config), id2label, lm.group(1) if lm else None,
                          tuple(n for n in names if n.lower().endswith(_WEIGHT_SUFFIXES)))
