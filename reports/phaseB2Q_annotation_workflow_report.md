# Research Enhancement Track — Phase B2-Q: Annotation Workflow

**Result:** a safe, offline labelling workflow is ready.

- **Built:** a backup and a working copy of the 1,493-item annotation file, small-batch export, a
  validated all-or-nothing merge, and progress and validation commands.
- **Tested:** 27 new offline tests; 175 pass in total.
- **Not done:**
  - no label was prefilled;
  - no AI suggestion was created;
  - the sealed key was not opened;
  - no network request was made, and no agreement or quality metric was calculated.

**Date:** 2026-10-13 (UTC).

**Labels:**

- **[VERIFIED]**: confirmed by a local check or a test.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## 1. What was inspected [VERIFIED]

- **Instructions and rubric:** `review_files/ANNOTATION_INSTRUCTIONS.md`, the B2-I rubric (§3), and
  the B2-O and B2-P reports.
- **The annotation files:** 1,493 rows and 312 overlap rows, 0 labelled. All are byte-identical to
  the B2-O build.
- **The sealed key:** only its fingerprint (`cc45a3df…`) was compared; it was never opened.

## 2. The quick reference

**File:** `reports/phaseB2Q_annotation_quick_reference.md`.

- **Built only from the existing rubric:** what `R`, `RL`, `I` and `A` mean; when an ambiguity code is
  required; `company_notice`; when polarity is required; the valid values and `UNC`; the annotator,
  basis, note and timestamp fields; relevance versus sentiment; and preserving uncertainty.
- **Its section 8** lists six points the rubric leaves unclear. They are not resolved (section 6
  below).

## 3. Working copy

All paths below are under `datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/review_files/`, which
Git ignores.

| Path | Role |
| --- | --- |
| `annotation_A.csv` | The generated file. **Never edited.** Its hash is checked against `selection_log.json` before every action |
| `backup/annotation_A.build.csv` | Byte-identical backup (`11db13e6…`) |
| `working/annotation_A.working.csv` | The working copy. Written **only** by the tool. Currently identical to the original: no labels |
| `working/batches/batch_NNN_overlap.csv` + `.manifest.json` | Batches you label (created by `export-batch`) |
| `working/merge_log.jsonl` | Append-only record of every init, export and merge, with file hashes |

**How the workflow protects the data:**

- **IDs and source fields:**
  - **Source fields:** batch files carry only `item_id`, read-only context (date, domain, URL, title,
    duplicate mark, overlap flag) and the 14 label columns. The working copy's provenance (record ID,
    batch stamp, timestamps) is never exported.
  - **IDs:** a merge refuses a batch whose item IDs were added, removed, duplicated or edited.
  - **Every validation** compares all source fields of the working copy with the generated file.
- **Spreadsheet conversion:**
  - **Robust merge:** a merge reads only `item_id` and the label columns. Reformatting the context (for
    example a date) cannot change anything.
  - **Encoding:** files are written as UTF-8. A batch saved in another encoding is refused with
    "save it as CSV UTF-8". A byte-order mark is tolerated.
- **Overlap rows:**
  - **Order:** `export-batch` gives only overlap rows by default.
  - **Basis:** on an overlap row, any `label_basis` other than `own` is rejected.
  - **No AI suggestions** exist; they must not be requested before all 312 overlap rows are labelled.
- **No prefill:** exported batches have empty label columns.
- **No silent deletion:**
  - merging a blank row over existing labels is refused;
  - changing a label requires a reason in `note`;
  - every merge is all or nothing.
- **Sealed key:** the helper never refers to it. A test asserts that its source contains no reference
  to the key, to a transport or to `urlopen`.

## 4. Commands

**All offline**, run from the repository root. They print JSON: progress, item IDs and error messages,
never titles.

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt annotate <action> --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml [options]
```

| Action | What it does |
| --- | --- |
| `init` | **Done in B2-Q.** Verified the original, wrote the backup and the working copy. Refuses to run again |
| `export-batch [--size N] [--all]` | Writes the next N (default 50, at most 200) unlabelled rows to a new batch file. Overlap rows only, unless `--all` (overlap rows still come first) |
| `merge --batch <file>` | Validates every labelled row of the batch against the rubric. If all pass, copies the labels into the working copy atomically; otherwise merges nothing and lists the errors by item ID |
| `validate` | Integrity of the working copy, plus rubric errors on every labelled row |
| `status` | Progress: labelled rows, overlap labelled, errors, `label_basis` counts, working-copy hash |

**Exit codes:** 0 when clean, 1 when errors are listed, 2 for a configuration error.

**Rules the merge and validation enforce,** all from the rubric:

| Field | Rule |
| --- | --- |
| `rel_*` | Each theme `R`, `RL`, `I` or `A` |
| `amb_code` | Required if and only if a theme is `A`. Values A1–A6, A9. A2 is not allowed for gold alone. A9 needs a `note` |
| `pol_*` | Required if and only if that theme is `R`. Values `POS`, `NEG`, `NEU`, `MIX`, `UNC` |
| `company_notice` | `Y`, `N` or `U`. `Y` excludes `R` on every theme |
| `near_dup_of` | Another existing item ID |
| `annotator_id` | Required; no email |
| `annotator_type` | `human` |
| `label_basis` | `own` on overlap rows. AI-based values only once `ai_suggestions_A.csv` exists |
| `labelled_at_utc` | A UTC date, or a date-time ending in `Z` |

**Real-data state after `init`, `validate` and `status`:**

- **Counts:** 1,493 rows; 312 overlap; 0 labelled; 0 errors.
- **Integrity:** OK.
- **Working-copy hash:** `11db13e6…`, equal to the original.

## 5. Recommended batching

- **Size:** labelling batches of 50 rows take about 15–25 minutes at 15–30 s per item [ESTIMATED,
  B2-I §4.10].
- **Overlap first:** the 312 overlap rows make 7 batches: 6 × 50 + 1 × 12.
- **One batch at a time:**
  1. export;
  2. label;
  3. merge;
  4. check `status`.

  Don't export the next batch until the current one has merged cleanly. An unmerged batch's rows
  count as pending, and the next export would include them again.
- **Then:**
  1. decide on AI suggestions for the remaining 1,181 rows;
  2. continue with `export-batch --all`.

## 6. Unresolved questions (yours)

These are the six points in quick-reference section 8:

1. **One `amb_code` for three themes:** the rule when two themes are ambiguous for different reasons.
2. **"Earlier" in `near_dup_of`:** what it means.
3. **`labelled_at_utc`:** precision. The validator accepts a date or a date-time.
4. **`company_notice = U` with `R`:** allowed by the literal rubric.
5. **The working copy:** it, not `annotation_A.csv`, now holds the final labels. This supersedes the
   "same file name" instruction in B2-P §3.
6. **The one empty-title item:** the rubric does not cover it. A1 was B2-O's reading.

**Item 1 is best settled before you begin.** The others need no action unless you disagree.

## 7. Tests [VERIFIED]

| Check | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt -q -p no:cacheprovider` | **175 passed, 0 failed:** the 148 existing tests plus 27 new ones in `test_annotate.py` |
| What the new tests cover | init, backup and never-overwrite; refusal of a tampered original; overlap-first export with safe columns and nothing prefilled; valid merge touching only labels and ignoring reformatted context; 17 rubric violations each rejecting the whole merge; AI basis needing a suggestions file and never on overlap rows; edited batch IDs refused; blank rows skipped; corrections needing a note; labels cannot be blanked; non-UTF-8 batch refused; a tampered working copy detected; status and completion; no reference to the sealed key |
| Compile with warnings as errors; unused-import scan | OK; 0 |

**Every test is offline.** Sockets and the database are blocked, and the fixtures are synthetic.

## 8. Changes

**Created:**

- `backend/wealthpilot/data/gdelt/annotate.py`;
- `tests/backend/data/gdelt/test_annotate.py`;
- `reports/phaseB2Q_annotation_quick_reference.md`;
- this report;
- git-ignored data files: `backup/annotation_A.build.csv`, `working/annotation_A.working.csv`,
  `working/merge_log.jsonl`.

**Modified:**

- `backend/wealthpilot/data/gdelt/cli.py` (the `annotate` command);
- `backend/wealthpilot/data/gdelt/README.md`;
- `docs/MEMORY.md`.

**Unchanged:**

- the generated review files and the sealed key;
- filters, sampling and the rubric;
- the downloaded sample;
- dependencies, application code and the database.

**Not done:** no commit or push.

## 9. How to start labelling the 312 overlap rows

1. **Read** `reports/phaseB2Q_annotation_quick_reference.md`. Decide unresolved question 1, or tell me
   your choice.
2. **Export the first overlap batch:**

   ```text
   .venv/Scripts/python.exe -m wealthpilot.data.gdelt annotate export-batch --size 50 --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml
   ```

   This creates `working/batches/batch_001_overlap.csv`, items in file order.
3. **Open it** in a text editor, or import it into a spreadsheet with **every column as Text**. Fill
   the label columns:
   - `annotator_type = human`;
   - `label_basis = own`.

   **No AI suggestions for these rows.** Save it as **CSV UTF-8**, under the same name.
4. **Merge it:**

   ```text
   .venv/Scripts/python.exe -m wealthpilot.data.gdelt annotate merge --batch datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/review_files/working/batches/batch_001_overlap.csv --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml
   ```

   **If errors are listed,** fix those item IDs in the same batch file and merge again. Nothing is
   merged until the batch is clean.
5. **Check progress:** `... annotate status --config …`. Repeat steps 2–4 until `overlap_labelled` is
   312 (7 batches).
6. **Then tell me.** You decide whether you want AI suggestions for the remaining 1,181 rows.

**Still not authorised:** the confirmation sample, full acquisition, B3.

---

## 10. Update (B2-S, 2026-10-13 18:37 UTC): decisions recorded, and the first batch exported

**Decisions** (project owner; recorded in `reports/phaseB2R_annotation_rubric_addendum.md`):

1. **Ambiguity codes, option (b):** one primary code in `amb_code`, with further theme-specific
   ambiguity described in `note`.
2. **Duplicate ordering:** `available_at_utc` first, then the record sequence. Never page time or
   `item_id`.

The rubric and the validator are unchanged.

**Checked before the export:**

- the generated files, the sealed key (fingerprint only), the backup and the working copy are
  unchanged (`11db13e6…`), with 0 labels;
- no AI-suggestion file;
- the downloaded sample's full audit is unchanged;
- 185 offline tests pass; compile and unused-import checks are clean.

**Exported** with `annotate export-batch --size 50`:

- **File:** `review_files/working/batches/batch_001_overlap.csv`, SHA-256 `105ce3d4…`, with a
  manifest.
- **Rows:** 50, `D0001` … `D0207` in file order, **all in the 312-item overlap subset.**

**Verified after the export:**

- **Columns:** the safe batch columns only; no record ID, batch stamp or timestamps.
- **IDs:** unique and equal to the manifest.
- **Context:** identical to the working copy.
- **Labels:** every label cell is empty.
- **Working copy:** unchanged.
- **Merge path:** a merge of the unlabelled batch, tried on a throwaway copy of the review folder (sealed
  key excluded, copy deleted), returned 0 merged, 50 skipped as blank, and no errors.

**Remaining:** **262** overlap rows, then the 1,181 others.

---

## 11. Update (2026-10-13 18:51 UTC): interactive labeller for the overlap items (Part 1 only)

**New command:** `annotate label` (`backend/wealthpilot/data/gdelt/labeller.py`). It labels the **312
overlap items** at a prompt, one at a time, so no CSV needs editing.

**What it shows:** only item ID, date, source domain, URL, title (control characters stripped) and the
pipeline's duplicate mark.

**What it asks:** the three relevance labels; the primary `amb_code` only if a theme is `A`;
polarity only for `R` themes; `company_notice`; an optional near-duplicate ID; a note (required for
A9).

**What it fills:** only session facts. That is your initials (asked once), `annotator_type =
human`, `label_basis = own`, and the real UTC time of saving with seconds.

**How it saves:** each item goes through `annotate.save_item`, which uses the existing validator.
The write is atomic, with one log entry per item. A failed item is not saved and is asked again.

**Controls:**

- `s` skips an item; it stays unlabelled.
- `q`, Ctrl+C or end of input quits without saving the current item.
- Running the command again resumes.
- `--item Dxxxx` revisits one overlap item. Changing a labelled item needs a confirmation and a
  correction reason, which is added to `note`.

**Scope:**

- **Overlap rows only:** `--item` refuses non-overlap IDs.
- **No AI and no key:** it never reads or shows AI suggestions or key data. A test plants marker
  data in both files and asserts nothing leaks.

**Batch files:** batch export and merge are unchanged and still work. Batch 1 can be left unused:
`annotate label` works directly on the working copy.

**Tests:** 14 new in `tests/backend/data/gdelt/test_labeller.py`. **199 passed** in total. Compile
and unused-import checks are clean.

**On the real data:** a smoke start with no input stopped at the initials prompt. Nothing was saved,
and all fingerprints are unchanged.

---

## 12. Update (B2-U, 2026-10-15): labeller usability fix

The labeller now keeps all answers for an item, explains the company-notice rule (Y excludes R) as
soon as it applies, offers `<` to go back, and shows a review screen listing every problem the rubric
validator finds. Nothing is saved until the item is valid, and a refused save keeps every answer.
The rubric and validator are unchanged. Details and the AI-assistance design (documented, not
started): `reports/phaseB2U_labeller_usability_and_ai_assistance_design.md`. Tests: 212 pass.
