# Research Enhancement Track — Phase B2-O: Annotation Dataset Build

**Result: the annotation files were built and validated from the verified development sample,
entirely offline.**

- **No network request:** none was made, and no batch was re-downloaded.
- **Sealed key:** not opened.
- **Not done:** no annotation was started, and no label, title or score was generated.
- **Not touched:** the confirmation sample and the full archive. B3 has not started.

**Date:** 2026-10-13 (UTC); build at 16:56 UTC.

**Labels:**

- **[VERIFIED]**: confirmed by a local check or a test.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## 1. Input verification, before the build [VERIFIED]

A read-only audit of the local files, independent of the earlier reports:

| Check | Result |
| --- | --- |
| Manifest slots | 192, all `present_verified / fetched / passed / parsed_validated / committed` |
| Sample identity | Manifest stamps in selection order hash to `a459a3fb44afd7e1e8121cd04f247564ea4e8fe434fdca33c9570e50605b2730` |
| Raw files | 192 present. MD5 192/192 match (ETag and recorded); SHA-256 192/192; sizes 192/192; zip member and CRC-32 192/192 |
| Availability | Verified for all 192 |
| Day files | 170/170 day files and 170/170 audit files re-hash to their recorded SHA-256 |
| Recorded acquisition | 384 requests (192 header + 192 download), 1,000,147,201 B. Unchanged since B2-M |

**No discrepancy was found.**

---

## 2. Changes to the builder before the run [VERIFIED; documented, not silent]

**Requested by B2-O; added to the annotation schema only.** The schema becomes `b2o_annotation_v1`,
B2-I's template plus these fields:

| Field | Purpose |
| --- | --- |
| `item_id` as stable `D0001…D1493` (was a bare integer) | Stable annotation IDs; the same inputs always give the same order and IDs |
| `batch_ts`, `available_at_utc`, `page_pub_ts_utc` | Source timestamps. The page time is a diagnostic from the source and never used for availability |
| `overlap_subset` (`Y`/`N`) | Marks the second-annotator subset, so those rows are labelled without AI suggestions |
| `annotator_type`, `label_basis` | Plan (c) provenance: `human` or `ai`; `own`, `accepted_ai`, `corrected_ai` or `rejected_ai` |
| `ANNOTATION_INSTRUCTIONS.md` (new file) | Rubric, plan (c) workflow, corrections, disagreements, locking, spreadsheet safety |

**Unchanged:** filters, sampling (seed, cells, sizes, hash selection), row definitions, thresholds,
the sealed-key columns, blinding (theme membership is only in the sealed key) and the sample.

**Files edited:**

- `backend/wealthpilot/data/gdelt/review.py`;
- `tests/backend/data/gdelt/test_sample_isolation.py`, whose review test now also checks stable IDs,
  provenance fields, overlap consistency and the instructions file.

The tool's code fingerprint is now `022157dfa34a5f39326ee9ca15ede66993ab6fd5ce461e1d12fb6b5c0e491ea2`.
It was `cdad195b…` at acquisition; only `review.py` changed.

---

## 3. Build [VERIFIED]

**Command:** run from the repository root, twice.

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt build-review --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml
```

**Both runs:** exit 0, and the second run's outputs are **byte-identical** to the first.

**Inputs used:**

- 192 of 192 batches;
- **0** excluded by the pre-registered training-cutoff rule;
- the 63 undecodable rows found at acquisition are not candidates (they are excluded and counted).

**Candidate rows and review items by cell** (B2-I §4.3; each valid row is in exactly one cell):

| Cell | Definition | Candidate rows | Review items |
| --- | --- | ---: | ---: |
| C1 | `GOLD` member | 193 | **193** (all; below the 200 cap) |
| C2 | `RATES_US` member, not C1 | 2,848 | 200 |
| C3 | `EQUITY_US` member, not C1–C2 | 1,953 | 200 |
| C4 | Captured company notice | 1,560 | 100 |
| C5 | Other captured row | 20,300 | 200 |
| C6 | Not captured; near-miss cue | 24,492 | 300 |
| C7 | Not captured; no cue | 193,590 | 300 |
| **Total** | | **244,936** (all valid English rows) | **1,493** |

**Not reached:** the 1,500 maximum, because the gold cell holds only 193 rows.

**Theme memberships per item:** these overlap (one row can belong to several themes) and live only in
the sealed key. They are not reported, to keep annotation blind.

**Second-annotator subset:**

- **Size:** **312 items (20.9%)**, in `annotation_B.csv`.
- **Selection:** as documented. An item belongs when the first 8 hex digits of
  SHA-256(`seed|iaa|record_id`) fall below `0x33333333`, about 20%. The selection is
  content-independent.

---

## 4. Output files [VERIFIED]

**Location** (git-ignored): `datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/review_files/`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `annotation_A.csv` (1,493 items) | 456,319 | `11db13e668bd3da8401164721fa3357b7f2c6ffc8879aa25724f1c228ba201af` |
| `annotation_B.csv` (312 items) | 96,655 | `211729002893c1e4ce5ae3787112ca4dbe119607a928a2621d36247fe2d3874e` |
| `key_sealed.csv` | 142,900 | `cc45a3df0465f2e7d45d741094b945f5a54d2eca940e086c25ae8991cc35f6aa` |
| `ANNOTATION_INSTRUCTIONS.md` | 3,601 | `e9d73df65fd2465cad206e2b41233f31d9c51169bc8aef7696551fdf03c619ef` |
| `selection_log.json` | 967 | `15fa23029c0284008fb92d9445463a48f91f02ce8bf9f63939a09fa84d291fe7` |

`selection_log.json` records:

- the seed;
- the stage D hash;
- the schema;
- cell counts;
- the item and overlap counts;
- the file hashes;
- `labels_locked: false`.

---

## 5. Validation [VERIFIED]

A validator read **only** `annotation_A.csv`, `annotation_B.csv`, the manifest and the raw zips. It
never read the sealed key.

| Check | Result |
| --- | --- |
| Duplicate `item_id` / bad ID format / duplicate record IDs | 0 / 0 / 0 |
| Every item's batch verified and committed in the manifest | 1,493 / 1,493 (from 187 of the 192 batches; at most 21 items from one batch) |
| Every record found in its source batch (re-parsed from the kept zip) | **1,493 / 1,493** |
| Title, URL, domain and page timestamp identical to the source record | 1,493 / 1,493 each (title as published, HTML entities decoded) |
| `batch_date_utc` and `available_at_utc` equal to the manifest | 1,493 / 1,493 |
| Pre-filled label, annotator or note cells | **0**: no label exists yet |
| `annotation_B.csv` equal to the `overlap_subset = Y` rows of A | Yes; 312 rows, identical content |
| Deterministic rebuild | Byte-identical |
| Source sample unchanged after the build | The audit repeated after the build gives identical states, hashes, CRCs, day files and request records (still 384 requests, 1,000,147,201 B, one run) |
| Network | None. The build reads local files only, and the manifest records no new attempt |
| Offline tests | `pytest tests/backend/data/gdelt -q`: **148 passed, 0 failed** |
| Compile (warnings as errors); unused imports | OK; 0 |
| Dependencies, Git status | `pip freeze` fingerprint `3393be50…` unchanged; Git status unchanged (data is git-ignored); nothing committed |

**What the annotator sees:**

- **Pipeline duplicate marks:** `ORIGINAL` 1,269, `SYNDICATED_SAME_BATCH` 214, `DUP_SAME_BATCH` 10.
- **Page timestamps:** present on 659 items.

**How the sealed key was protected:**

- **Never opened:** not opened, parsed, previewed or printed.
- **Only fingerprinted:** its only handling was a SHA-256 fingerprint over its bytes.
- **Blindness:** the validator worked without it. The annotation files contain no cell, weight, filter,
  theme or tone column.
- **Instructions:** they forbid opening it before the labels are locked.

---

## 6. Open quality issues

| Issue | Handling |
| --- | --- |
| 1 item has an empty source title | Kept as published. The rubric's A1 code ("title uninformative") covers it |
| 0 titles start with `=`, `+`, `-` or `@` | Formula injection is not currently possible. The instructions still require opening CSVs as text, because titles are untrusted |
| The gold cell holds only 193 rows | Precision for gold will rest on at most 193 labelled items. This is above B2-I's 100-item reporting floor, but the intervals will be wide. Not padded; any broadening would be a separate, disclosed decision |
| Near-empty flags are unknown for all sample batches | Expected for isolated batches (B2-M §6); does not affect annotation |
| AI-versus-human agreement under plan (c) | The second labeller for `annotation_B.csv` would be an AI, so agreement will be reported as human-versus-AI, never as two-human agreement |

---

## 7. Exact next step: manual annotation (yours)

1. **Read** `review_files/ANNOTATION_INSTRUCTIONS.md`.
2. **Open** `annotation_A.csv` in a text editor, or import it with every column as Text. Do not let a
   spreadsheet reformat or re-save it.
3. **Label every row:**
   - `rel_equity`, `rel_rates`, `rel_gold` (`R` / `RL` / `I` / `A`, plus `amb_code` when `A`);
   - `company_notice`;
   - polarity only where a theme is `R`;
   - `near_dup_of` when you spot the same story;
   - `annotator_id` (your initials), `annotator_type = human`, `label_basis`, `labelled_at_utc`.
4. **Overlap rows:** label the 312 `overlap_subset = Y` rows yourself (`label_basis = own`), without
   viewing AI suggestions.
5. **AI suggestions, if you want them** for the other rows: ask, and they will be written to a
   separate `ai_suggestions_A.csv` (`annotator_type = ai`) for you to accept, correct or reject. They
   are never final, and never independent human ground truth.
6. **When done:** say so. The label-file hashes are then locked in `selection_log.json`, and only then
   is `key_sealed.csv` opened to compute the B2-I estimates.

**Out of scope until approved:** confirmation sample, full acquisition, B3.
