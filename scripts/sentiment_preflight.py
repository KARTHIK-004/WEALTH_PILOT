"""Read-only pre-flight for enabling the Transformer sentiment model (ADR-052). It decides nothing and enables nothing: it reads the owner's recorded approvals in
`reports/sentiment_consolidated_approval_form.md`, checks what exists on this machine, and prints which gate is BLOCKED and why. Exit status 0 only when every gate passes.

    python scripts/sentiment_preflight.py            # human-readable report
    python scripts/sentiment_preflight.py --json     # the same, as JSON

It touches no network, no model, no dataset and no user text: it parses one Markdown file, asks `importlib` whether four packages are installed (without importing them), and tests whether a few
paths exist. A passing report is NOT an approval and does not switch anything on; enabling the model remains the owner's separate R14 decision.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORM = REPO / "reports" / "sentiment_consolidated_approval_form.md"
APPROVED_MODELS = Path.home() / ".copilot" / "wealthpilot-approved-models"
ARTIFACT_ROOT = REPO / "models" / "sentiment"
PACKAGES = ("torch", "transformers", "tokenizers", "safetensors")
WEIGHT_FILE = "model.safetensors"
STATUSES = ("APPROVE", "REJECT", "KEEP UNRESOLVED", "BLOCKED")

LEGAL = [f"A3.{n}" for n in range(1, 14)]                    # model, tokenizer, revision, training-data terms, share-alike, intended use ...
DEPENDENCIES = ["C1", "C2", "C3", "C4", "C5", "E1"]            # approved environment, hash-pinned set, download step
DATASET = [f"D{n}" for n in range(1, 21)]                      # source, provenance, privacy, rubric freeze, splits, duplicates, retention, deletion, access, permission
EVALUATION = ["E2", "E3"]                                      # probability-bearing predictions, a real frozen manifest
ACTIVATION = ["F1"]                                            # R14: switching the model on is the owner's separate, final decision


def recorded_answers(form_text: str) -> dict[str, str]:
    """Each decision id of the consolidated form mapped to its recorded status (the first status word of the row's last cell)."""
    out: dict[str, str] = {}
    for line in form_text.splitlines():
        match = re.match(r"\| ([A-F]\d+(?:\.\d+)?) \|", line)
        if not match:
            continue
        last = line.strip().strip("|").split(" | ")[-1].strip()
        status = next((s for s in STATUSES if last == s or last.startswith(s + " ") or last.startswith(s + " (")), None)
        if status:
            out[match.group(1)] = status
    return out


def _not_approved(answers: dict[str, str], ids: list[str]) -> list[str]:
    return [f"{i}: {answers.get(i, 'not recorded')}" for i in ids if answers.get(i) != "APPROVE"]


def evaluate(answers: dict[str, str], installed: dict[str, bool], model_files: list[str], frozen_manifest: bool, enabled_flag: bool | None) -> list[dict]:
    """The gates, each `{"gate", "passed", "blockers"}`. Pure: every input is passed in, so it is tested with invented state."""
    gates = [
        {"gate": "1 legal and licensing", "blockers": _not_approved(answers, LEGAL)},
        {"gate": "2 dependencies and environment", "blockers": _not_approved(answers, DEPENDENCIES) + [f"package not installed: {p}" for p in PACKAGES if not installed.get(p)]},
        {"gate": "3 dataset, provenance, privacy, rubric, register, deletion", "blockers": _not_approved(answers, DATASET) + ([] if frozen_manifest else ["no frozen manifest exists"])},
        {"gate": "4 evaluation and calibration", "blockers": _not_approved(answers, EVALUATION) + ([] if frozen_manifest else ["no evaluation can exist without a frozen manifest"])},
        {"gate": "5 verified local model artifact", "blockers": [] if model_files else [f"no {WEIGHT_FILE} in {ARTIFACT_ROOT} or {APPROVED_MODELS}"]},
        {"gate": "6 activation decision (R14)", "blockers": _not_approved(answers, ACTIVATION)},
        {"gate": "7 production configuration is still the rules baseline", "blockers": [] if enabled_flag is False else [f"SENTIMENT_MODEL_ENABLED is {enabled_flag}, expected false until R14"]},
    ]
    for gate in gates:
        gate["passed"] = not gate["blockers"]
    gates[-1]["note"] = "this gate describes the CURRENT safe state; it passes while the model is off"
    return gates


def _model_files() -> list[str]:
    roots = [ARTIFACT_ROOT, APPROVED_MODELS]
    return sorted(str(p) for r in roots if r.is_dir() for p in r.rglob(WEIGHT_FILE))


def _frozen_manifest_exists() -> bool:
    skip = {".git", ".venv", "node_modules", "tests", "__pycache__", "frontend", ".claude"}
    for folder in (REPO / "datasets", REPO / "demo_data", REPO / "models"):
        for path in folder.rglob("*.json") if folder.is_dir() else []:
            if skip & set(path.relative_to(REPO).parts):
                continue
            if '"manifest_status": "FROZEN"' in path.read_text(encoding="utf-8", errors="ignore"):
                return True
    return False


def _flag() -> bool | None:
    sys.path[:0] = [str(REPO), str(REPO / "backend")]
    try:
        from wealthpilot.config import get_settings

        return bool(get_settings().sentiment_model_enabled)
    except Exception:  # noqa: BLE001 - the report must never crash on a configuration problem; it says "unknown"
        return None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    gates = evaluate(recorded_answers(FORM.read_text(encoding="utf-8")), {p: importlib.util.find_spec(p) is not None for p in PACKAGES}, _model_files(), _frozen_manifest_exists(), _flag())
    ready = all(g["passed"] for g in gates[:-1])                          # the last gate is the safe-state description, not a requirement
    result = {"transformer_may_be_enabled": ready, "gates": gates, "note": "read-only report: it enables nothing and a pass is not an approval"}
    if "--json" in args:
        print(json.dumps(result, indent=2))
    else:
        for gate in gates:
            print(f"[{'PASS' if gate['passed'] else 'BLOCKED'}] gate {gate['gate']}")
            for blocker in gate["blockers"]:
                print(f"         - {blocker}")
        print("RESULT:", "every gate passed (enabling is still the owner's R14 decision)" if ready else "BLOCKED: the Transformer must stay disabled and the rules baseline stays the method")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
