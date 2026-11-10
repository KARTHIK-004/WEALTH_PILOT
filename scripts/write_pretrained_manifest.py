"""Write `pretrained_manifest.json` for a pretrained research candidate whose files an operator has ALREADY placed under `models/sentiment_pretrained/<key>/` (ADR-053).

    python scripts/write_pretrained_manifest.py --candidate finbert --tokenizer-length 30522

Offline and read-only apart from the one manifest file it writes: no network, no model load, no package import beyond the standard library and the repository's registry. It is NOT a way
around the gates: it refuses a candidate whose recorded licence is not `license_verified` or whose weights are not published as safetensors (both are code constants in
`core/sentiment/registry.py` and change only through a reviewed code change and an ADR; a candidate that is not REGISTERED is refused too), refuses a directory that holds a pickle-capable or framework checkpoint, and refuses a
`config.json` whose labels are not exactly positive / negative / neutral. `--tokenizer-length` is `len(tokenizer)` as printed by the operator's own tokenizer check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from wealthpilot.core import sentiment_model as sm  # noqa: E402
from wealthpilot.core.sentiment import adapter  # noqa: E402
from wealthpilot.core.sentiment.normalization import label_order_from_id2label  # noqa: E402
from wealthpilot.core.sentiment.registry import CANDIDATES, by_key  # noqa: E402


class ManifestError(ValueError):
    pass


def build_manifest(key: str, tokenizer_length: int, root: Path = adapter.PRETRAINED_ROOT) -> dict:
    candidate = by_key(key)
    if not candidate.runnable_in_principle:
        raise ManifestError(f"{candidate.display_name} is not permitted to run: {candidate.blocker}")
    directory = root / key
    if not directory.is_dir() or directory.is_symlink():
        raise ManifestError("the candidate directory does not exist (or is a symbolic link)")
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.name != adapter.MANIFEST_FILE)
    banned = [p.name for p in files if p.name.lower().endswith(adapter.FORBIDDEN_SUFFIXES)]
    if banned:
        raise ManifestError(f"pickle-capable or framework checkpoint files are present and must be removed: {', '.join(banned)}")
    names = {str(p.relative_to(directory)).replace("\\", "/") for p in files}
    missing = [n for n in adapter.REQUIRED_FILES if n not in names]
    if missing:
        raise ManifestError(f"required files are missing: {', '.join(missing)}")
    config = json.loads((directory / sm.CONFIG_FILE).read_text(encoding="utf-8"))
    if label_order_from_id2label(config.get("id2label")) is None:
        raise ManifestError("config.json labels are not exactly positive / negative / neutral")
    if isinstance(tokenizer_length, bool) or tokenizer_length < 1 or tokenizer_length > int(config.get("vocab_size", 0)):
        raise ManifestError("--tokenizer-length must be a positive number that does not exceed config.json vocab_size")
    hashes = {str(p.relative_to(directory)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    return {"manifest_schema_version": adapter.MANIFEST_SCHEMA_VERSION, "repository": candidate.repository, "revision": candidate.revision, "weight_licence": candidate.weight_licence,
            "tokenizer_length": tokenizer_length, "files": hashes, "manifest_sha256": sm.manifest_sha256(hashes)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", required=True, choices=[c.key for c in CANDIDATES])
    parser.add_argument("--tokenizer-length", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(args.candidate, args.tokenizer_length)
    except (ManifestError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    (adapter.PRETRAINED_ROOT / args.candidate / adapter.MANIFEST_FILE).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {adapter.MANIFEST_FILE} for {args.candidate} ({len(manifest['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
