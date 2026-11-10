"""Build the annotator package and the DRAFT manifest for the FICTIONAL rubric-clarity dry run (docs/USER_TEXT_VALIDATION_DECISION_SHEET.md O1/O4, limited approvals 2026-10-20).

    python scripts/build_dry_run_package.py                       # (re)build package/ and author_only/DRAFT_MANIFEST.json
    python scripts/build_dry_run_package.py --register FILE.csv   # also check the participant register for the independence gate
    python scripts/build_dry_run_package.py --verify              # check the existing package against the manifest; exit 1 on any problem

The package holds ONLY what an annotator may see: the fictional texts, the blank template, the instructions and an excerpt of the rubric (the parts between its `annotator-excerpt` markers:
sections 1-3 and the flag definitions). Author-only material (the challenge map, the manifest, the owner decisions, the protocol) is never copied in. The manifest is a DRAFT: it records hashes and the
approvals in force, says `frozen: false`, and lists the freeze steps still to do. It does not run or import the baseline, read any label, or compute any score. Nothing here freezes the rubric.

Documented rules (each is tested in tests/backend/scripts/test_dry_run_package_adversarial.py):
  Markers      Only exact `<!-- annotator-excerpt:start -->` / `<!-- annotator-excerpt:end -->` comments count. Any other HTML comment that mentions annotator-excerpt, missing, unbalanced, reversed,
               nested, empty or duplicate parts raise an error: the excerpt is never silently widened, shrunk or repeated.
  Refusal      `build` refuses (exit 2, nothing written) if a source is not a regular file, the package folder holds unexpected entries (it never deletes them), the texts or template are malformed or
               carry labels or extra fields, or any part to be distributed matches the leak rules below.
  Leaks        Author-only wording, owner decisions O1-O4 and O7, ambiguity ids A1-A11, HTML comments and similar are refused in every distributed file. O5 and O6 are allowed (annotators apply them).
  Verify       Checks the exact regular-file set (no extras, no symlinks, no path-like manifest entries), the same leak rules, every recorded hash, count and id hash, that package copies equal their
               sources and the excerpt equals a fresh extraction, that the manifest is a valid DRAFT, and that the rubric did not change since. A malformed manifest is reported, not crashed on.
  Line endings Files are compared and hashed with CRLF normalised to LF, so a Windows and a Unix checkout produce the same package and manifest.
  Register     Columns exactly annotator_code, role, independent_of_rubric_author, attested_on (a UTF-8 BOM from a spreadsheet is tolerated). Codes, roles and the independence answer are compared after
               stripping whitespace and ignoring case; codes must be unique across roles; independence must be `yes`; `attested_on` must be an ISO date (YYYY-MM-DD). The counts are the owner's O4 approval
               (2 annotators, 1 adjudicator). The register is the owner's own attestation: the tool checks that it is complete and consistent and CANNOT verify independence. No other eligibility rule exists.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "datasets" / "rubric_examples" / "pilot_pack_v0"
ANNOTATOR = PACK / "annotator"
PACKAGE = PACK / "package"
AUTHOR = PACK / "author_only"
MANIFEST = AUTHOR / "DRAFT_MANIFEST.json"
RUBRIC = REPO / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md"
BASELINE_SOURCE = REPO / "backend" / "wealthpilot" / "core" / "user_text_sentiment.py"

RUBRIC_VERSION = "v0-draft"
SOURCE_FILES = ("pilot_texts.jsonl", "annotation_template.csv", "INSTRUCTIONS.md")
PACKAGE_FILES = (*SOURCE_FILES, "RUBRIC_EXCERPT.md")
TEXT_KEYS = frozenset({"id", "text", "source", "split"})
TEMPLATE_COLUMNS = ("id", "annotator_id", "sentiment", "emotional_tone", "emotional_tone_proposed", "topics", "preferences", "contradictory", "ambiguous_tone", "language", "hedged", "negation",
                    "difficulty", "rubric_unclear", "note")
FORBIDDEN_IN_PACKAGE = ("author_only", "challenge", "user_text_rules", "unvalidated", "draft_manifest", "owner decision", "provenance", "consent", "freeze", "manifest", "pilot example", "pack author",
                        "author note", "not for annotators", "pre_annotation", "pre-annotation", "ambiguities", "section 5", "adr-04")
# Owner decisions an annotator has no use for (O5 and O6 describe the proposed labelling policy the annotator applies, so they are allowed), the author's ambiguity ids, and HTML comments.
FORBIDDEN_PATTERNS = (re.compile(r"\bO[1-4]\b|\bO7\b"), re.compile(r"\bA(?:1[01]|[1-9])\b"), re.compile(r"<!--|-->"))
EXCERPT_START, EXCERPT_END = "<!-- annotator-excerpt:start -->", "<!-- annotator-excerpt:end -->"
_MARKER_RE = re.compile(re.escape(EXCERPT_START) + "|" + re.escape(EXCERPT_END))
_ANY_EXCERPT_COMMENT_RE = re.compile(r"<!--[^>]*annotator-excerpt[^>]*-->", re.IGNORECASE)
REGISTER_COLUMNS = ("annotator_code", "role", "independent_of_rubric_author", "attested_on")
REQUIRED_ANNOTATORS, REQUIRED_ADJUDICATORS = 2, 1          # the owner's limited approval of O4 (2026-10-20)
MANIFEST_REQUIRED_KEYS = ("manifest_status", "frozen", "freeze_process_completed", "rubric_version", "rubric_sha256", "rubric_excerpt_sha256", "package_files", "text_count", "ids_sha256")

APPROVALS = {
    "O1": "accepted by the owner for FICTIONAL notes only; real participant text collection remains prohibited",
    "O4": "accepted by the owner for the fictional dry run: two independent annotators and one adjudicator, all independent of the rubric author; self-annotation must not be called independent",
    "O5": "PROPOSED, not accepted; Option A is the proposed annotation policy for the dry run (code-mixed/unsupported-language text annotated `uncertain`)",
    "O6": "PROPOSED, not accepted; the dry run only identifies rubric ambiguity; no production schema or API change",
    "O2": "unresolved", "O3": "unresolved", "O7": "unresolved",
}
FUTURE_BLOCKER = ("Withdrawal vs unlinkability (decision-sheet C3) is unresolved and blocks any future real-text collection: a contributor cannot withdraw a text that is stored with no link to them.")
ATTESTATION_NOTE = "The register is the owner's own attestation; the tool checks that it is complete and consistent and cannot verify independence."
FREEZE_STEPS_REMAINING = (
    "annotation completed by independent human annotators", "independent adjudication completed", "rubric ambiguities resolved and a new rubric version written",
    "owner decisions O2, O3, O7 made (and O5/O6 accepted or rejected)", "final manifest with the extended fields (rubric 5a) written and the files hashed",
)


# ------------------------------------------------------------------ hashing and reading (CRLF-normalised, regular files only)

def read_norm(path: Path) -> bytes:
    """File bytes with CRLF normalised to LF, so Windows and Unix checkouts hash and compare alike."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(read_norm(path)).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _regular(path: Path, what: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{what} is not a regular file: {path.name}")
    return path


# ------------------------------------------------------------------ excerpt extraction

def extract_annotator_rubric(rubric_text: str) -> str:
    """Only the parts of the rubric enclosed by its exact `annotator-excerpt` markers (sections 1-3 and the flag definitions). Everything else -- record format, provenance, data separation, the
    protocol, owner decisions, author notes -- is left out. Raises ValueError for any marker layout that could silently widen, shrink or repeat the excerpt."""
    text = rubric_text.replace("\r\n", "\n")
    if len(_ANY_EXCERPT_COMMENT_RE.findall(text)) != len(_MARKER_RE.findall(text)):
        raise ValueError("a comment mentions annotator-excerpt but is not an exact marker (misspelled, re-spaced or re-cased); fix the marker")
    marks = list(_MARKER_RE.finditer(text))
    if not marks:
        raise ValueError("the rubric's annotator-excerpt markers are missing")
    if sum(m.group(0) == EXCERPT_START for m in marks) != sum(m.group(0) == EXCERPT_END for m in marks):
        raise ValueError("the rubric's annotator-excerpt markers are unbalanced")
    parts: list[str] = []
    open_at: int | None = None
    for m in marks:
        if m.group(0) == EXCERPT_START:
            if open_at is not None:
                raise ValueError("nested annotator-excerpt markers")
            open_at = m.end()
        else:
            if open_at is None:
                raise ValueError("annotator-excerpt end marker before its start marker (reversed)")
            part = text[open_at:m.start()].strip()
            if not part:
                raise ValueError("an annotator-excerpt part is empty")
            if part in parts:
                raise ValueError("duplicate annotator-excerpt part")
            parts.append(part)
            open_at = None
    if open_at is not None:
        raise ValueError("the rubric's annotator-excerpt markers are unbalanced")
    header = f"# Annotation rules (rubric {RUBRIC_VERSION}: labelling rules and flag definitions)\n\nDraft, not frozen. You need only this document for the labelling rules.\n\n"
    return header + "\n\n".join(parts) + "\n"


# ------------------------------------------------------------------ content checks shared by build and verify

def leak_problems(name: str, text: str) -> list[str]:
    low = text.lower()
    found = [f"{name} contains author-only wording '{w.strip()}'" for w in FORBIDDEN_IN_PACKAGE if w in low]
    found += [f"{name} contains non-annotator content matching '{p.pattern}'" for p in FORBIDDEN_PATTERNS if p.search(text)]
    return found


def text_problems(data: bytes) -> list[str]:
    """pilot_texts.jsonl: exactly the four fields, fictional, no labels or annotator fields, unique ids."""
    problems, ids = [], []
    for n, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            problems.append(f"pilot_texts.jsonl line {n} is not valid JSON")
            continue
        if not isinstance(row, dict) or set(row) != TEXT_KEYS:
            problems.append(f"pilot_texts.jsonl line {n} must have exactly the keys {sorted(TEXT_KEYS)}, found {sorted(row) if isinstance(row, dict) else type(row).__name__}")
            continue
        if row["source"] != "synthetic_pilot" or row["split"] != "pilot_preparation" or not isinstance(row["text"], str) or not row["text"].strip() or len(row["text"]) > 1000:
            problems.append(f"pilot_texts.jsonl line {n} is not a fictional pilot text (source, split or text)")
        ids.append(row["id"])
    if not ids or len(set(ids)) != len(ids):
        problems.append("pilot_texts.jsonl ids must be present and unique")
    return problems


def template_problems(data: bytes, text_ids: list[str]) -> list[str]:
    """annotation_template.csv: exactly the agreed columns, one blank row per text in order, nothing pre-filled."""
    rows = list(csv.reader(data.decode("utf-8").splitlines()))
    if not rows or tuple(rows[0]) != TEMPLATE_COLUMNS:
        return [f"annotation_template.csv header must be exactly {', '.join(TEMPLATE_COLUMNS)}"]
    body = rows[1:]
    problems = []
    if [r[0] for r in body if r] != text_ids:
        problems.append("annotation_template.csv ids must match the texts exactly, in the same order")
    for r in body:
        if len(r) != len(TEMPLATE_COLUMNS) or any(cell.strip() for cell in r[1:]):
            problems.append(f"annotation_template.csv row {r[0] if r else '?'} must be blank except its id (nothing pre-filled)")
            break
    return problems


def _text_ids(data: bytes) -> list[str]:
    return [json.loads(line)["id"] for line in data.decode("utf-8").splitlines() if line.strip()]


def baseline_method_version() -> str | None:
    """Read the constant from the source text; the baseline is neither imported nor run."""
    match = re.search(r'^METHOD_VERSION\s*=\s*"([^"]+)"', BASELINE_SOURCE.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


# ------------------------------------------------------------------ the independence gate

def check_register(path: Path | None) -> list[str]:
    """Blockers that keep the package from being distributed (empty list = gate passed). See the module docstring for the rules."""
    if path is None:
        return ["no participant register supplied: annotators and an adjudicator, each attested independent of the rubric author, are not yet identified"]
    if not path.is_file():
        return [f"participant register not found: {path.name}"]
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != REGISTER_COLUMNS:
            return [f"participant register must have exactly the columns {', '.join(REGISTER_COLUMNS)}"]
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]
    blockers: list[str] = []
    codes = [(r["annotator_code"] or "").strip().casefold() for r in rows]
    if len(set(codes)) != len(codes) or "" in codes:
        blockers.append("annotator codes must be present and unique (ignoring case and spaces), across both roles")
    for r in rows:
        who = (r["annotator_code"] or "").strip() or "(blank)"
        if (r["role"] or "").strip().casefold() not in ("annotator", "adjudicator"):
            blockers.append(f"role of {who} must be annotator or adjudicator")
        if (r["independent_of_rubric_author"] or "").strip().casefold() != "yes":
            blockers.append(f"{who} is not attested independent of the rubric author")
        try:
            date.fromisoformat((r["attested_on"] or "").strip())
        except ValueError:
            blockers.append(f"{who} has no valid attestation date (attested_on must be YYYY-MM-DD)")
    annotators = sum((r["role"] or "").strip().casefold() == "annotator" for r in rows)
    adjudicators = sum((r["role"] or "").strip().casefold() == "adjudicator" for r in rows)
    if annotators < REQUIRED_ANNOTATORS:
        blockers.append(f"need {REQUIRED_ANNOTATORS} independent annotators, register has {annotators}")
    if adjudicators < REQUIRED_ADJUDICATORS:
        blockers.append(f"need {REQUIRED_ADJUDICATORS} independent adjudicator, register has {adjudicators}")
    return blockers


# ------------------------------------------------------------------ build

def build(register: Path | None = None) -> dict:
    """Write the package and the DRAFT manifest, or raise ValueError having written nothing."""
    if PACKAGE.exists():
        unexpected = sorted(p.name for p in PACKAGE.iterdir() if p.name not in PACKAGE_FILES)
        if unexpected:
            raise ValueError(f"the package folder holds unexpected entries {unexpected}; the builder never deletes anything, remove them yourself")
    sources = {name: read_norm(_regular(ANNOTATOR / name, f"source {name}")) for name in SOURCE_FILES}
    excerpt = extract_annotator_rubric(RUBRIC.read_text(encoding="utf-8")).encode("utf-8")
    problems = text_problems(sources["pilot_texts.jsonl"])
    if not problems:
        problems += template_problems(sources["annotation_template.csv"], _text_ids(sources["pilot_texts.jsonl"]))
    for name, data in {**sources, "RUBRIC_EXCERPT.md": excerpt}.items():
        problems += leak_problems(name, data.decode("utf-8"))
    if problems:
        raise ValueError("refusing to build a package that leaks or is malformed: " + "; ".join(problems))
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for name, data in sources.items():
        (PACKAGE / name).write_bytes(data)
    (PACKAGE / "RUBRIC_EXCERPT.md").write_bytes(excerpt)
    blockers = check_register(register)
    texts = _text_ids(sources["pilot_texts.jsonl"])
    manifest = {
        "manifest_status": "DRAFT",
        "frozen": False,
        "freeze_process_completed": False,
        "freeze_steps_remaining": list(FREEZE_STEPS_REMAINING),
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha256": sha256_file(RUBRIC),
        "rubric_excerpt_sha256": sha256_file(PACKAGE / "RUBRIC_EXCERPT.md"),
        "package_files": {name: sha256_file(PACKAGE / name) for name in PACKAGE_FILES},
        "text_count": len(texts),
        "ids_sha256": sha256_text("\n".join(texts)),
        "data_kind": "FICTIONAL synthetic notes; not real user text; not validation data",
        "owner_decisions_in_force": APPROVALS,
        "baseline_method_version_recorded_only": baseline_method_version(),
        "baseline_status": "UNVALIDATED_BASELINE (not run on this pack)",
        "annotation_status": "NOT STARTED",
        "annotators_required": REQUIRED_ANNOTATORS,
        "adjudicators_required": REQUIRED_ADJUDICATORS,
        "distribution_ready": not blockers,
        "distribution_blockers": blockers,
        "independence_attestation_note": ATTESTATION_NOTE,
        "future_real_text_blocker": FUTURE_BLOCKER,
    }
    AUTHOR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return manifest


# ------------------------------------------------------------------ verify

def verify() -> list[str]:
    """Problems with the package or manifest (empty list = consistent). Never raises on bad input."""
    if not PACKAGE.is_dir() or not MANIFEST.is_file():
        return ["package or manifest is missing; run the builder"]
    problems: list[str] = []
    entries = sorted(PACKAGE.iterdir(), key=lambda p: p.name)
    if [p.name for p in entries] != sorted(PACKAGE_FILES):
        problems.append(f"package files are {[p.name for p in entries]}, expected {sorted(PACKAGE_FILES)}")
    problems += [f"{p.name} is not a regular file (symlink or folder)" for p in entries if p.name in PACKAGE_FILES and (p.is_symlink() or not p.is_file())]
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError
    except ValueError:
        return problems + ["the manifest is not valid JSON"]
    missing = [k for k in MANIFEST_REQUIRED_KEYS if k not in manifest]
    if missing:
        return problems + [f"the manifest is missing {missing}"]
    if not isinstance(manifest["package_files"], dict) or sorted(manifest["package_files"]) != sorted(PACKAGE_FILES):
        problems.append(f"the manifest's package_files must list exactly {sorted(PACKAGE_FILES)}")
    readable = {p.name: p for p in entries if p.name in PACKAGE_FILES and p.is_file() and not p.is_symlink()}
    for name, path in readable.items():
        problems += leak_problems(name, path.read_text(encoding="utf-8"))
        if isinstance(manifest["package_files"], dict) and manifest["package_files"].get(name) != sha256_file(path):
            problems.append(f"{name} differs from the manifest hash")
    for name in SOURCE_FILES:
        source = ANNOTATOR / name
        if name in readable and source.is_file() and not source.is_symlink() and read_norm(readable[name]) != read_norm(source):
            problems.append(f"{name} differs from its source in annotator/; rebuild the package")
    if "pilot_texts.jsonl" in readable:
        data = read_norm(readable["pilot_texts.jsonl"])
        text_issues = text_problems(data)
        problems += text_issues
        if not text_issues:
            ids = _text_ids(data)
            if manifest["text_count"] != len(ids):
                problems.append(f"the manifest text_count {manifest['text_count']} does not match the {len(ids)} texts")
            if manifest["ids_sha256"] != sha256_text("\n".join(ids)):
                problems.append("the manifest ids_sha256 does not match the texts")
            if "annotation_template.csv" in readable:
                problems += template_problems(read_norm(readable["annotation_template.csv"]), ids)
    if "RUBRIC_EXCERPT.md" in readable:
        if manifest["rubric_excerpt_sha256"] != sha256_file(readable["RUBRIC_EXCERPT.md"]):
            problems.append("the manifest rubric_excerpt_sha256 does not match RUBRIC_EXCERPT.md")
        try:
            if readable["RUBRIC_EXCERPT.md"].read_text(encoding="utf-8").replace("\r\n", "\n") != extract_annotator_rubric(RUBRIC.read_text(encoding="utf-8")):
                problems.append("RUBRIC_EXCERPT.md does not match the rubric's annotator-excerpt parts; rebuild the package")
        except ValueError as exc:
            problems.append(str(exc))
    if manifest.get("frozen") is not False or manifest.get("manifest_status") != "DRAFT":
        problems.append("the manifest must stay a DRAFT until the freeze process is completed")
    if manifest["rubric_sha256"] != sha256_file(RUBRIC):
        problems.append("the rubric changed since the manifest was written; rebuild (this is a new draft, not a freeze)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--register", type=Path, help="participant register CSV (annotator_code, role, independent_of_rubric_author, attested_on)")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if args.verify:
        problems = verify()
        print("\n".join(problems) if problems else "package and DRAFT manifest are consistent")
        return 1 if problems else 0
    try:
        manifest = build(args.register)
    except ValueError as exc:
        print(f"BUILD REFUSED: {exc}")
        return 2
    print(f"package written ({manifest['text_count']} fictional texts); manifest status {manifest['manifest_status']}, frozen={manifest['frozen']}")
    print(f"distribution_ready={manifest['distribution_ready']}")
    for blocker in manifest["distribution_blockers"]:
        print(f"BLOCKER: {blocker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
