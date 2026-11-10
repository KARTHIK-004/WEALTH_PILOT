"""The registered rubric text for prompts. A changed file is refused, like a changed filter spec."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wealthpilot.data.gdelt.ai.fingerprints import sha256_text
from wealthpilot.data.gdelt.errors import FilterSpecError

RUBRIC_DIR = Path(__file__).resolve().parent
FILES = {"b2t_rubric_v1": "rubric_v1.md"}
REGISTRY: dict[str, str] = {
    "b2t_rubric_v1": "d513a76bb45c8f3bd0c21dd12221769a738219cfc91089b41199d681b653ff57",
}


@dataclass(frozen=True)
class Rubric:
    version: str
    text: str
    sha256: str


def load_rubric(version: str = "b2t_rubric_v1", *, directory: Path = RUBRIC_DIR,
                registry: dict[str, str] | None = None) -> Rubric:
    registry = REGISTRY if registry is None else registry
    if version not in registry or version not in FILES:
        raise FilterSpecError(f"unregistered rubric version {version!r}")
    path = directory / FILES[version]
    if not path.exists():
        raise FilterSpecError(f"rubric file missing: {path}")
    text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")   # LF-normalised, like the filter spec
    digest = sha256_text(text)
    if digest != registry[version]:
        raise FilterSpecError(f"{path.name} SHA-256 {digest} differs from the registered {registry[version]}; "
                              "a changed rubric text needs a new version")
    return Rubric(version, text, digest)
