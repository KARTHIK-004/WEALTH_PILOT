"""Build the sentiment validation sample, the annotation exports and the freeze-ready manifest. Local and offline: no network, no model, no scoring.

Reads (read-only): the development sample's manifest and day files (``datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1``) and ONLY the ``gkg_record_id`` column of the D13 overlap manifest
``review_files/annotation_B.csv`` (membership; no label column is accessed). Never opens the sealed key or the working label copies.
Writes (new files only, into ``datasets/derived/sentiment_validation_v1``): the sample manifest, one annotation sheet per target (item id, theme, title and a blank answer column), the secondary sheets for the
double-labelled subset, the instruction sheets and the assignment. Refuses to overwrite an existing output directory.

Usage (from the repository root):  PYTHONPATH=backend python scripts/build_sentiment_validation_sample.py
This is the ONE file under ``scripts/`` that the scaffold isolation test (``test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold``) explicitly allows to import the sentiment
package: a local, offline, human-run research preparation tool, not a production entry point. The sentiment package itself stays free of file, database and network access.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import sys
from pathlib import Path

from wealthpilot.data.gdelt.filters import load_spec
from wealthpilot.data.gdelt.sentiment import annotation_tools as at
from wealthpilot.data.gdelt.sentiment import dayfile_adapter as da
from wealthpilot.data.gdelt.sentiment import manifest_adapter as ma
from wealthpilot.data.gdelt.sentiment import polarity_validation as pv
from wealthpilot.data.gdelt.sentiment.schema import THEMES

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1"
OUT = ROOT / "datasets/derived/sentiment_validation_v1"
SEED, PER_THEME, DOUBLE_FRACTION = 42, 200, 0.20


COMMON = """# Annotation instructions: {title} (version v1)

You will see rows of `item_id`, `theme` and `title`. Fill the `code` column for every row. Use only the title text.

Rules that make your labels usable as independent ground truth:

- Work on your own judgement. Do not use any suggestion, score, tone number or model output, and do not discuss items with another annotator before you have finished.
- If you have seen any such output for an item, leave `code` blank and write `SEEN` in `note`; the item is then dropped, not guessed.
- Record your initials (never an email) as `annotator_id` when you return the sheet.
- Codes: `POS`, `NEG`, `NEU`, `MIX` (the headline clearly points both ways) and `UNC` (you cannot tell). `MIX`, `UNC` and `NEU` are three different answers: do not use `NEU` to mean "not sure".
- `MIX` and `UNC` are valid answers. They are reported as counts and are not compared with a scorer's positive/negative/neutral.
- Leave nothing blank except under the `SEEN` rule above. Do not edit `item_id`, `theme` or `title`.

"""
SHEETS = {
    "wording_tone": COMMON.format(title="wording tone") + """## Question

Judging only the WORDS of the headline, is its tone positive (`POS`), negative (`NEG`) or neutral (`NEU`)? Ignore what you think the news means for any market or asset: a headline about falling prices can be written in
neutral words, and a cheerful headline can describe a bad event. The `theme` column does not change the question.
""",
    "market_direction": COMMON.format(title="market direction") + """## Question

For the named `theme` (equity_us = US equities / Nasdaq, rates_us = US rates / bonds, gold = gold), does the news point to a positive (`POS`), negative (`NEG`) or neutral (`NEU`) effect on that asset, from the point of view of
someone who HOLDS it? Rising yields are `NEG` for bonds. Judge only what the headline supports, not what you know happened afterwards. The same headline can have different codes for different themes.
""",
}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def overlap_ids() -> list[str]:
    """Membership only: the gkg_record_id column of the original overlap manifest. No other column is read."""
    with (SAMPLE / "review_files" / "annotation_B.csv").open(encoding="utf-8", newline="") as fh:
        return sorted({row["gkg_record_id"] for row in csv.DictReader(fh)})


def load_candidates():
    db = sqlite3.connect(f"file:{(SAMPLE / 'manifest' / 'manifest.sqlite').as_posix()}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    slot_rows = [dict(r) for r in db.execute("SELECT * FROM slot")]
    series = [dict(r) for r in db.execute("SELECT * FROM slot_series_count")]
    commits = [dict(r) for r in db.execute("SELECT * FROM day_commit ORDER BY utc_day")]
    db.close()
    min_chars = int(load_spec().raw["title_hash_min_chars"])
    slots = ma.adapt_manifest(slot_rows, series, filter_version="gdelt_filter_v1", expected_batches=sorted(r["batch_ts"] for r in slot_rows)).require_ok().by_batch()
    cands = []
    for c in commits:
        res = da.adapt_day_file((SAMPLE / c["file_relpath"]).read_bytes(), utc_day=c["utc_day"], slots=slots, min_chars=min_chars, source_name=c["file_relpath"], day_commit=c)
        if not res.ok:
            raise SystemExit(f"day file {c['utc_day']} did not validate: {res.rejections[:1]}")
        cands += list(res.records)
    return cands, min_chars, commits


def csv_text(rows: list[dict[str, str]], fields: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main() -> int:
    if OUT.exists():
        print(f"refusing to overwrite {OUT}", file=sys.stderr)
        return 1
    cands, min_chars, commits = load_candidates()
    excluded = frozenset(overlap_ids())
    sample = pv.draw_validation_sample(cands, excluded_ids=excluded, per_theme=PER_THEME, seed=SEED, min_chars=min_chars)
    assignment = at.assign_double_annotation(sample, fraction=DOUBLE_FRACTION, seed=SEED)
    rows = pv.annotation_rows(sample, cands)                                   # id, theme, title only
    OUT.mkdir(parents=True)
    files: dict[str, str] = {}
    export_hashes: dict[str, str] = {}
    instr_hashes: dict[str, str] = {}
    secondary = {(i, t) for t in THEMES for i in assignment.double[t]}
    for target in at.TARGETS:
        text = SHEETS[target]
        (OUT / f"INSTRUCTIONS_{target}.md").write_text(text, encoding="utf-8", newline="\n")
        instr_hashes[target] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        order = lambda r: hashlib.sha256(f"{SEED}:order:{target}:{r['theme']}:{r['article_id']}".encode()).hexdigest()      # noqa: E731
        sheet = [{"item_id": r["article_id"], "theme": r["theme"], "title": r["title"], "code": "", "note": ""} for r in sorted(rows, key=order)]
        second = [r for r in sheet if (r["item_id"], r["theme"]) in secondary]
        second.sort(key=lambda r: hashlib.sha256(f"{SEED}:order2:{target}:{r['theme']}:{r['item_id']}".encode()).hexdigest())      # a different order for the second annotator
        export_hashes[target] = at.target_export_sha256(target, rows)
        for name, content in ((f"annotation_{target}_primary.csv", sheet), (f"annotation_{target}_secondary.csv", second)):
            (OUT / name).write_text(csv_text(content, ["item_id", "theme", "title", "code", "note"]), encoding="utf-8", newline="\n")
            files[name] = sha256_file(OUT / name)
        files[f"INSTRUCTIONS_{target}.md"] = instr_hashes[target]
    dbl = [{"item_id": i, "theme": t} for t in THEMES for i in assignment.double[t]]
    (OUT / "double_annotation_assignment.csv").write_text(csv_text(dbl, ["item_id", "theme"]), encoding="utf-8", newline="\n")
    files["double_annotation_assignment.csv"] = sha256_file(OUT / "double_annotation_assignment.csv")
    multi = len({a for t in THEMES for a in sample.by_theme[t]}) < sum(len(sample.by_theme[t]) for t in THEMES)
    cand_fp = hashlib.sha256(json.dumps(sorted([c.article_id, c.title_sha256_raw, c.text_status, sorted(c.theme_flags.items())] for c in cands), separators=(",", ":")).encode()).hexdigest()
    manifest = {
        "schema": "sentiment_validation_sample_v1", "seed": SEED, "per_theme_requested": PER_THEME, "double_fraction": DOUBLE_FRACTION,
        "pool_sizes_after_exclusions": dict(sample.pool_sizes), "sampled": {t: len(sample.by_theme[t]) for t in THEMES}, "shortfall": dict(sample.shortfall),
        "n_candidates_excluded_by_overlap_control": sample.n_excluded_in_pool, "articles_in_more_than_one_theme": multi,
        "double_annotation": {"n_double": dict(assignment.n_double), "not_feasible_themes": list(assignment.not_feasible), "assignment_sha256": assignment.sha256},
        "sample_manifest_sha256": sample.manifest_sha256, "sample_ids": {t: list(sample.by_theme[t]) for t in THEMES},
        "export_content_sha256_per_target": export_hashes, "instruction_sha256_per_target": instr_hashes, "output_file_sha256": files,
        "exclusion_control": {"name": "D13 overlap manifest", "source": "review_files/annotation_B.csv", "columns_read": ["gkg_record_id"], "n_ids": len(excluded),
                              "ids_sha256": hashlib.sha256("\n".join(sorted(excluded)).encode()).hexdigest(),
                              "overlap_lock_record": "absent (no D13 lock record exists in this repository); labels were not read"},
        "source_fingerprints": {"manifest_sqlite_sha256": sha256_file(SAMPLE / "manifest" / "manifest.sqlite"),
                                "day_files_sha256": hashlib.sha256("\n".join(sorted(f"{c['utc_day']}:{c['file_sha256']}" for c in commits)).encode()).hexdigest(),
                                "n_day_files": len(commits), "n_candidates": len(cands), "candidates_sha256": cand_fp, "min_chars": min_chars},
        "metrics_protocol_status": at.PROTOCOL_STATUS, "mix_unc_treatment": at.NOT_COMPARABLE_TREATMENT,
        "code_sha256": {m: sha256_file(ROOT / f"backend/wealthpilot/data/gdelt/sentiment/{m}.py") for m in ("annotation_tools", "polarity_validation", "scored_records")},
    }
    (OUT / "sample_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    print(json.dumps({k: manifest[k] for k in ("pool_sizes_after_exclusions", "sampled", "shortfall", "double_annotation", "sample_manifest_sha256", "export_content_sha256_per_target")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
