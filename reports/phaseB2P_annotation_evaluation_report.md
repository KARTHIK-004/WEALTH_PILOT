# Research Enhancement Track — Phase B2-P: Annotation Verification and Evaluation

**Result: STOPPED before the sealed key. The annotations have not been done.**

- **What the files show:** no label exists in either annotation file, so the completion checks fail
  and no evaluation was possible.
- **This is a gap report**, as B2-P §1 requires.
- **Untouched:** the sealed key was not accessed, nothing was frozen or evaluated, and no network
  request was made.

**Date:** 2026-10-13 17:25 UTC.

**Labels:**

- **[VERIFIED]**: confirmed by a local check or a test.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## 1. Input files and fingerprints [VERIFIED]

**Folder:** `datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/review_files/` (git-ignored).

| File | SHA-256 now | Equal to the B2-O build? |
| --- | --- | --- |
| `annotation_A.csv` | `11db13e668bd3da8401164721fa3357b7f2c6ffc8879aa25724f1c228ba201af` | Yes, byte-identical |
| `annotation_B.csv` | `211729002893c1e4ce5ae3787112ca4dbe119607a928a2621d36247fe2d3874e` | Yes |
| `key_sealed.csv` | `cc45a3df0465f2e7d45d741094b945f5a54d2eca940e086c25ae8991cc35f6aa` | Yes. Only its fingerprint was compared; the file was not opened |
| `ANNOTATION_INSTRUCTIONS.md`, `selection_log.json` | `e9d73df6…`, `15fa2302…` | Yes |

**Files last written:** 2026-10-13 22:28 local (16:58 UTC), by the B2-O rebuild.

**Not found** anywhere in the review folder, nor on the Desktop or in Downloads, Documents or OneDrive:

- `ai_suggestions_A.csv`;
- `adjudication.csv`;
- any other labelled copy of `annotation_A`/`annotation_B`.

---

## 2. Completion checks [BLOCKED: failed]

| Check (B2-P §1) | Result |
| --- | --- |
| Every row has a completed label, or a permitted uncertainty/abstention label | **0 of 1,493 rows.** All 14 label, annotator and note columns are empty in every row |
| All 1,493 stable IDs accounted for | Yes: `D0001`–`D1493`, unchanged and unique |
| 312 overlap items labelled by a human without prior AI suggestions | **0 of 312** labelled |
| AI suggestions stored separately and marked as AI | None exist |
| Provenance of accepted, corrected or rejected suggestions | Not applicable: no labels |
| IDs and source provenance unchanged; no duplicate or untracked rows | Yes: the files are byte-identical to the B2-O build |
| Final files saved and fingerprinted | The fingerprints above are of the **unlabelled** files |

**What was therefore not done:**

- no annotation freeze;
- no access to the sealed key (`key_sealed.csv` was neither opened nor parsed);
- no evaluation and no agreement figure;
- no confusion matrix, precision or recall.

**Every evaluation result in B2-P §4 is unavailable.**

---

## 3. Gap list: the corrections needed before B2-P can proceed

1. **Label every row of `annotation_A.csv`** (1,493 rows), following
   `review_files/ANNOTATION_INSTRUCTIONS.md`.
   - **Required on every row:** `rel_equity`, `rel_rates`, `rel_gold` (each `R`, `RL`, `I` or `A`);
     `company_notice` (`Y`, `N` or `U`); `annotator_id` (your initials); `annotator_type`;
     `label_basis`; `labelled_at_utc`.
   - **When required:**
     - `amb_code` whenever any theme is `A`;
     - `pol_*` for each theme labelled `R` (`UNC` allowed);
     - `near_dup_of` when you spot the same story.
2. **Label the 312 rows with `overlap_subset = Y` yourself first,** without viewing any AI
   suggestion (`label_basis = own`).
3. **AI assistance for the remaining rows, if you want it:** ask for `ai_suggestions_A.csv`. It is
   written as a separate file marked `annotator_type = ai`. Then record your decision on each row:
   `accepted_ai`, `corrected_ai` or `rejected_ai`.
4. **Do not change** `item_id`, `gkg_record_id`, `batch_ts`, the timestamps, `source_domain`, `url`,
   `title`, `mech_dup` or `overlap_subset`. Save as UTF-8 CSV, in the same folder and under the same
   name.
5. **Tell me when it is complete.** The completion checks are then re-run, the labelled files are
   frozen by SHA-256, and only then is the sealed key opened.

---

## 4. Tests and checks [VERIFIED]

| Check | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt -q -p no:cacheprovider` | **148 passed, 0 failed** (offline; sockets and database blocked) |
| Compile with warnings as errors; unused-import scan | OK; 0 |
| Review files after the checks | Unchanged (fingerprints re-compared) |

**Unchanged:**

- tool code, the review files, the downloaded sample;
- dependencies, application code, database and models.

**Not done:** no commit or push.

---

## 5. Filter suitability

**Insufficient evidence.** No labelled item exists, so the candidate filters (`gdelt_filter_v1`)
remain **unverified**. Nothing is claimed about their precision, recall or suitability.

---

## 6. Exact next step

**The labelling itself (yours), as set out in section 3.**

- **Not needed:** no further approval is required to label.
- **Still not authorised:** the confirmation sample, full acquisition and B3.
