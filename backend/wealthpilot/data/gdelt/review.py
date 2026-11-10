"""Build the blind annotation files for the labelled review (B2-I sections 4.3-4.9). Offline only.

Reads the raw development batches kept by the sample run (re-checking each zip's CRC), classifies
every valid row, places it in exactly one cell, selects items by a seeded hash, and writes:

- ``annotation_A.csv``: every selected item, shuffled, with no filter, cell, theme or tone column;
- ``annotation_B.csv``: the ~20% agreement subset for a second annotator;
- ``key_sealed.csv``: cell, weights and filter outcomes, not to be opened until labels are locked;
- ``selection_log.json``: seed, list hashes, cell counts and file hashes.

All files stay local (the output root is git-ignored). Titles never go into a tracked report.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from wealthpilot.data.gdelt.dedup import mark_same_batch
from wealthpilot.data.gdelt.filters import Classifier
from wealthpilot.data.gdelt.integrity import open_member
from wealthpilot.data.gdelt.manifest import Manifest
from wealthpilot.data.gdelt.output import atomic_write
from wealthpilot.data.gdelt.parser import RowCounts, iter_rows
from wealthpilot.data.gdelt.sample import SEED, STAGE_D_SHA256

CELL_SIZES = {"C1": 200, "C2": 200, "C3": 200, "C4": 100, "C5": 200, "C6": 300, "C7": 300}
IAA_THRESHOLD = 0x33333333   # first 8 hex digits below this: ~20%
ANNOTATION_SCHEMA = "b2o_annotation_v1"   # B2-I section 4.9 template + the B2-O provenance and annotator fields
ANNOTATION_COLUMNS = ("item_id", "gkg_record_id", "batch_ts", "batch_date_utc", "available_at_utc", "page_pub_ts_utc",
                      "source_domain", "url", "title", "mech_dup", "overlap_subset",
                      "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice", "pol_equity", "pol_rates",
                      "pol_gold", "near_dup_of", "annotator_id", "annotator_type", "label_basis", "labelled_at_utc",
                      "note")
FORMULA_PREFIXES = ("=", "+", "-", "@")
KEY_COLUMNS = ("item_id", "gkg_record_id", "batch_ts", "stage", "round", "block", "cell", "cell_rows", "cell_items",
               "weight", "captured", "company_item", "member_equity_us", "member_rates_us", "member_gold",
               "s1_equity", "s1_rates", "s1_gold", "s2_equity", "s2_rates", "s2_gold", "near_miss_cue", "iaa_subset")


INSTRUCTIONS = """# Annotation instructions: GDELT development sample (B2-I rubric, plan (c))

These files are local research data (git-ignored). Titles are third-party headlines: never commit, publish or
paste them into a tracked report.

**Spreadsheet safety:** titles are untrusted text. A title starting with `=`, `+`, `-` or `@` can run as a formula in
Excel or LibreOffice. Open the CSV in a text editor, or import it with every column set to Text. Never let a
spreadsheet re-save the file in another format.

## The files

| File | What it is | Do |
| --- | --- | --- |
| `annotation_A.csv` | Every review item, shuffled | Label every row |
| `annotation_B.csv` | The overlap subset (`overlap_subset = Y`), for an independent second labeller | Do not edit it yourself |
| `key_sealed.csv` | Cell, weights and filter results per item | **Do not open** until the labels are locked (B2-I section 4.4) |
| `selection_log.json` | Seed, list hash, counts and file hashes | Reference only |

## Labelling rules (B2-I section 3)

**Judge only the title, URL, source and dates.** Do not open the link, and never use knowledge of later market moves.

**Label every theme on every row:** `rel_equity`, `rel_rates`, `rel_gold`, each one of:

| Code | Meaning |
| --- | --- |
| `R` | Relevant: the theme's market is a main subject |
| `RL` | Related: mentioned or adjacent (one company, non-US, local retail, macro without a market framing) |
| `I` | Irrelevant |
| `A` | Ambiguous: also fill `amb_code` (A1-A6, A9). Keep ambiguity rather than forcing a label |

**Other fields:**

- `company_notice`: `Y`, `N` or `U`. Company and fund notices are never `R`.
- `pol_equity`, `pol_rates`, `pol_gold`: only where that theme is `R`. One of `POS`, `NEG`, `NEU`, `MIX`, `UNC`
  (uncertain), from the asset holder's view; rising yields are `NEG` for bonds. Relevance never implies polarity.
- `mech_dup`: filled by the pipeline. If you notice the same story as an earlier item, put that item's ID in
  `near_dup_of`. Later updates stay their own rows.

## Who labelled what: plan (c), project owner plus disclosed AI assistance

- `annotator_id`: your initials (never an email).
- `annotator_type`: `human` for your final labels.
- `label_basis`: how you reached the label:
  - `own`: your judgement, no suggestion seen;
  - `accepted_ai`: you checked and accepted an AI suggestion;
  - `corrected_ai`: you changed an AI suggestion;
  - `rejected_ai`: you discarded an AI suggestion and labelled yourself.

**AI suggestions** (if you ask for them) go in a separate file, `ai_suggestions_A.csv`, with `annotator_type = ai`.
They are provisional. They are never independent human ground truth, and never final until you review them.

**Overlap rows** (`overlap_subset = Y`) measure agreement:

- Label them yourself with `label_basis = own`, **without** viewing AI suggestions.
- Any independent labels for `annotation_B.csv` come from a second labeller. Under plan (c) that labeller is the AI,
  working blind, so results are reported as human-versus-AI agreement, not agreement between two people.

## Corrections and disagreements

- **Corrections:** never delete a row. Change the label and say why in `note`.
- **Disagreements:** settle overlap disagreements by discussion; keep both original labels in `adjudication.csv`
  (`item_id`, `label_a`, `label_b`, `final`, `reason`). An unresolved one becomes `A` with `amb_code = A9`.

## Locking

When labelling is complete, the SHA-256 of each label file is recorded in `selection_log.json` (`labels_locked: true`).
Only then may `key_sealed.csv` be opened to compute the results.
"""


def _h(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def cell_of(members: dict[str, bool], captured: bool, company_item: bool, near_miss: bool) -> str:
    if members["GOLD"]:
        return "C1"
    if members["RATES_US"]:
        return "C2"
    if members["EQUITY_US"]:
        return "C3"
    if captured and company_item:
        return "C4"
    if captured:
        return "C5"
    return "C6" if near_miss else "C7"


@dataclass(frozen=True)
class ReviewSummary:
    batches_used: int
    cell_rows: dict[str, int]
    cell_items: dict[str, int]
    items: int
    iaa_items: int
    files: dict[str, str]


def _csv_bytes(header: tuple[str, ...], rows: list[list[object]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def build_review(manifest: Manifest, raw_dir: Path, classifier: Classifier, out_dir: Path, *,
                 max_uncompressed: int, max_ratio: float, max_line_bytes: int) -> ReviewSummary:
    slots = manifest.slots("selection = 'stage_D' AND existence = 'present_verified'")
    usable = [r for r in slots if "after_sample_cutoff" not in (r["availability_flags"] or "")]
    by_cell: dict[str, list[dict]] = defaultdict(list)
    for r in usable:
        stamp = r["batch_ts"]
        body = (raw_dir / f"{stamp}.gkg.csv.zip").read_bytes()
        if hashlib.sha256(body).hexdigest() != r["actual_sha256"]:
            raise ValueError(f"kept raw file for {stamp} does not match its recorded SHA-256")
        archive, info = open_member(body, stamp, max_uncompressed=max_uncompressed, max_ratio=max_ratio)
        rows = []
        with archive.open(info) as stream:
            rows = list(iter_rows(stream, stamp, RowCounts(), max_line_bytes=max_line_bytes,
                                  max_uncompressed=max_uncompressed))
        classified = [(row, classifier.classify(row)) for row in rows]
        marks = mark_same_batch([(row.record_id, row.seq, c.url_canonical, c.title_hash) for row, c in classified])
        for row, c in classified:
            cell = cell_of(c.members, c.captured, c.company_item, c.near_miss_cue)
            by_cell[cell].append({"row": row, "c": c, "mech": marks[row.record_id], "slot": r})

    cell_rows = {k: len(by_cell.get(k, [])) for k in CELL_SIZES}
    chosen: list[dict] = []
    cell_items: dict[str, int] = {}
    for cell, size in CELL_SIZES.items():
        pool = sorted(by_cell.get(cell, []), key=lambda x: _h(SEED, "row", x["row"].record_id))
        take = pool[:size]
        cell_items[cell] = len(take)
        for x in take:
            x["cell"] = cell
        chosen.extend(take)
    chosen.sort(key=lambda x: _h(SEED, "order", x["row"].record_id))

    ann, ann_b, key = [], [], []
    for i, x in enumerate(chosen, start=1):
        row, c, slot = x["row"], x["c"], x["slot"]
        iaa = int(_h(SEED, "iaa", row.record_id)[:8], 16) < IAA_THRESHOLD
        item_id = f"D{i:04d}"   # stable: same inputs give the same order and IDs
        page_ts = (f"{row.page_pub_ts[:4]}-{row.page_pub_ts[4:6]}-{row.page_pub_ts[6:8]}T{row.page_pub_ts[8:10]}:"
                   f"{row.page_pub_ts[10:12]}:{row.page_pub_ts[12:14]}Z") if row.page_pub_ts else ""
        a = [item_id, row.record_id, slot["batch_ts"], slot["utc_day"], slot["available_at_utc"], page_ts,
             row.source_domain, row.document_url, row.title, x["mech"], "Y" if iaa else "N",
             "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
        ann.append(a)
        if iaa:
            ann_b.append(a)
        n, k = cell_rows[x["cell"]], cell_items[x["cell"]]
        key.append([item_id, row.record_id, slot["batch_ts"], "D", slot["sample_round"], slot["sample_block"], x["cell"],
                    n, k, f"{n / k:.6f}", int(c.captured), int(c.company_item),
                    *(int(c.members[s]) for s in ("EQUITY_US", "RATES_US", "GOLD")),
                    *(int(c.s1[s]) for s in ("EQUITY_US", "RATES_US", "GOLD")),
                    *(int(c.s2[s]) for s in ("EQUITY_US", "RATES_US", "GOLD")), int(c.near_miss_cue), int(iaa)])

    files = {
        "annotation_A.csv": atomic_write(out_dir / "annotation_A.csv", _csv_bytes(ANNOTATION_COLUMNS, ann)),
        "annotation_B.csv": atomic_write(out_dir / "annotation_B.csv", _csv_bytes(ANNOTATION_COLUMNS, ann_b)),
        "key_sealed.csv": atomic_write(out_dir / "key_sealed.csv", _csv_bytes(KEY_COLUMNS, key)),
    }
    files["ANNOTATION_INSTRUCTIONS.md"] = atomic_write(out_dir / "ANNOTATION_INSTRUCTIONS.md",
                                                       INSTRUCTIONS.encode("utf-8"))
    log = {"seed": SEED, "stage_d_sha256": STAGE_D_SHA256, "annotation_schema": ANNOTATION_SCHEMA,
           "batches_used": len(usable), "batches_excluded_after_cutoff": len(slots) - len(usable),
           "cell_rows": cell_rows, "cell_items": cell_items, "items": len(ann), "overlap_items": len(ann_b),
           "titles_with_spreadsheet_formula_prefix": sum(1 for a in ann if str(a[8]).startswith(FORMULA_PREFIXES)),
           "files_sha256": files, "labels_locked": False}
    files["selection_log.json"] = atomic_write(out_dir / "selection_log.json",
                                               json.dumps(log, indent=1, sort_keys=True).encode("utf-8"))
    return ReviewSummary(len(usable), cell_rows, cell_items, len(ann), len(ann_b), files)
