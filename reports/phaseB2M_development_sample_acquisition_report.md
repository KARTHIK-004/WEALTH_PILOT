# Research Enhancement Track — Phase B2-M: Development Sample Authorization and Acquisition

**Status: ACQUISITION COMPLETE AND VERIFIED.**

- **What ran:** the fixed 192-batch development sample, after your separate, explicit authorisation
  of the run.
- **Results:** all 192 batches were downloaded, validated and processed: 384 requests and
  1,000,147,201 B, with no retries and no failures.
- **Verification:** an independent offline audit of the local files reproduces every recorded count.
- **Not yet done:** annotation preparation. It was stopped before, as instructed.

**Date:** 2026-10-13 (UTC).

**History of this phase:**

- **First pass (15:46 UTC):** stopped at the authorization check, because none of the three
  confirmations had been given.
- **Second pass (15:50 UTC):** the user gave all three explicitly, plus a retention decision.
- **B2-N (16:08 UTC):** confirmed from local files that the run had not yet happened.
- **Execution (16:25–16:34 UTC):** after the user's explicit authorisation, the run and a post-run
  audit (sections 5–8).

**Labels:**

- **[VERIFIED]**: confirmed by a local check or a test.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

**Note:** the B2-M prompt as received ends mid-sentence ("…open the"). Everything before that point
was followed.

---

## 1. Authorization [VERIFIED as user-given; the allowance is not independently verified]

| Confirmation | The user's statement | Recorded as |
| --- | --- | --- |
| Data allowance | "Confirmed — at least 1.5 GB remains, with no unwanted charge." | `data_allowance_remaining_bytes: 1500000000`, marked **user-confirmed, not verified** |
| Sample | "Approved — only the fixed 192-batch sample, within all documented limits." | Scope: stage D only, `stage_sha256` `a459a3fb…` |
| Annotation | "(c) Me + AI-assisted annotation, with AI labels disclosed." | Option (c); AI labels disclosed and never presented as independent human ground truth |
| Retention | "Keep sample files until annotation and review are complete, then delete them when no longer needed." | Recorded in the approval note |

**Authorization complete: yes.**

**Not authorized:**

- the confirmation sample (stage C);
- the full historical archive;
- B3.

The record says so explicitly.

---

## 2. Approval record [VERIFIED]

**Where:** `datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml`.

- **Format:** the documented format (`config.example.yaml`).
- **Git:** ignored by `.gitignore:33` (`datasets/raw/*`), confirmed with `git check-ignore`.
- **Written:** 2026-10-13T15:50:03Z.

**It records:**

- the approval time (UTC);
- the scope (the fixed 192-batch development sample);
- the user-confirmed allowance;
- annotation plan (c);
- the retention decision;
- the limits, restated explicitly (planned 1.30 GB; hard cap 1.50 GB including retries; 1,200
  requests; at least 10 GB free; sequential; parallel off);
- the list fingerprint;
- a statement that the full historical archive, the confirmation sample and B3 are not authorized.

**Who approved:** `approved_by` reads "project owner (explicit chat confirmation)". No name or email
was invented.

**Validated through the real gate** (`config.authorize`; no network):

| Request | Result |
| --- | --- |
| Development sample with `--confirm-network` | Accepted |
| Development sample without the flag | Refused |
| Confirmation sample | Refused |
| Full acquisition | Refused: "not approved and cannot be enabled in this build" |

---

## 3. Code changes in this phase [VERIFIED]

| File | Change |
| --- | --- |
| `backend/wealthpilot/data/gdelt/__init__.py` | `NETWORK_ENABLED_IN_THIS_BUILD` and `DEV_SAMPLE_ENABLED_IN_THIS_BUILD` set to `True`. `CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD` stays `False`. Full acquisition still has no switch |
| `backend/wealthpilot/data/gdelt/cli.py`, `preflight.py` | **Provenance fix:** a run now records a real code fingerprint (SHA-256 of the tool's source and data files), the Git commit and dirty flag, the `tzdata` version and the free bytes at start. Before, it recorded the placeholder `"see provenance"`. The preflight now also prints the destination paths and the code fingerprint |
| `backend/wealthpilot/data/gdelt/README.md` | Lock description updated |
| `tests/backend/data/gdelt/test_guards_gates.py` | **Lock tests:** they now patch the locks off to keep testing locked behaviour. **New tests:** one asserts the post-B2-M build state (confirmation lock still on; no-config, missing-flag and wrong-hash requests still refused); another shows a gate-issued transport opens no connection when created, while forged or dry-run authorisations are refused. **Added:** a code-fingerprint test |

**No safeguard was weakened.** The limits, gates, fail-closed availability rule and state separation
are unchanged.

**Tests:** `pytest tests/backend/data/gdelt -q` gave **148 passed, 0 failed**, with sockets and the
database blocked. Compile with warnings as errors: OK. Unused imports: 0.

---

## 4. Preflight report [VERIFIED, offline]

**Command:** `dry-run --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml`.

| Item | Value |
| --- | --- |
| Batches | 192 (stage D only) |
| List fingerprint | `a459a3fb44afd7e1e8121cd04f247564ea4e8fe434fdca33c9570e50605b2730`. Matches; re-derivation reproduces D, C and the combined hash |
| Expected transfer | ≈1,033,930,000 B [ESTIMATED]. The exact total comes from 192 header requests, and the run stops before any download if it exceeds 1.30 GB |
| Hard cap | 1,500,000,000 B, retries included |
| Request budget | At least 384; cap 1,200 |
| Free disk | 184,071,860,224 B [MEASURED]; floors 20 GB (preflight) and 10 GB (runtime) |
| Destination | `datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/`, containing `manifest/manifest.sqlite`, `raw/` (kept sample zips), `filtered/`, `audit_sample/`, `logs/` and `tmp/`. All git-ignored |
| Code fingerprint | `cdad195baac30ae80c900f8fc4c11fc80114df3854c7e759bce6dd9aff2db576` |
| Full-archive path | Not enabled; `acquire` always refuses |
| Confirmation sample | Locked |
| Result | `ready_for_development_sample: True` |

---

## 5. Acquisition results [VERIFIED from the local manifest and files]

**Command:** run from the repository root, exactly as authorised.

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt fetch-sample --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml --confirm-network
```

**Before the run:** a final offline preflight was ready with no blockers. The config and code
fingerprints were unchanged since B2-M.

| Item | Result |
| --- | --- |
| Run | `20261013T162537Z-b858ed`, 16:25:37 → 16:34:26 UTC (8 min 49 s); outcome `completed`; exit code 0 |
| Batches attempted / downloaded / validated / processed | **192 / 192 / 192 / 192** |
| Rejected / absent / failed / unresolved | **0 / 0 / 0 / 0**. No substitution was needed |
| Requests | **384:** 192 header checks + 192 downloads, all HTTP 200. At most one of each per batch: no retries. Cap: 1,200 |
| Bytes transferred | **1,000,147,201 B** (≈1.00 GB). The sum of recorded attempt bytes equals the size of the 192 files on disk. Planned threshold 1.30 GB and hard cap 1.50 GB both respected |
| Batch sizes | 1,387,346 to 12,055,818 B; median 4,648,508 B |
| Sample identity | The manifest's stamps, in selection order, hash to `a459a3fb…`. Rounds 1–8 × blocks 1–24 as registered. Only `stage_D` slots exist. **The confirmation sample and the full archive were not accessed** |
| Free disk | 180,936,495,104 B at the start (recorded by the run); 179,928,846,336 B after. Floors 20 GB and 10 GB never approached |

---

## 6. Validation results [VERIFIED]

**Integrity:**

| Check | Result |
| --- | --- |
| Checksums | MD5 from each file's ETag (no master list is used for the sample): **192/192 match**. SHA-256 of the kept files recomputed after the run: **192/192 match** the manifest. Sizes: 192/192 equal Content-Length and the header-reported size |
| Zip integrity | Exactly one member with the expected name; CRC-32 re-verified with `testzip`: **192/192 pass** |

**Availability timestamps:** **192/192 verified**; none failed closed.

- **Server time:** `Last-Modified` was 6.9 to 12.5 minutes **before** the nominal batch time (median
  10.4). So availability = nominal + 15 min for every batch, and none is late.
- **Cached copies:** 155 downloads came from the CDN cache (`Age` > 0). Every one was accepted only
  because the zip member time corroborated `Last-Modified`, which holds for all 192.
- **Training cutoff:** the latest availability is 2023-12-24 03:30 UTC, well before the first training
  window's cutoff (2024-01-04 21:00 UTC). No batch carries `after_sample_cutoff`.

**Parsing:**

| Count | Value |
| --- | --- |
| Physical lines | 244,999 |
| Valid English rows | 244,936; per batch 359 to 3,052, median 1,121 |
| Malformed | **63, all invalid UTF-8**, in 37 batches, at most 10 in one. Excluded and counted, never dropped silently |
| Date mismatch, translated, non-web | 0, 0, 0 |
| Same-batch duplicates (URL or title) | **44,209 (18.0%)**, consistent with B2-G's 17.8% |
| Captured rows | 26,854 (10.96%); 1,560 of them flagged as company items |
| Audit-sample rows | 203 uncaptured rows (hash-selected, ~1 in 1,000) |

**Per-theme member rows** (candidate filter `gdelt_filter_v1`; rows before story deduplication,
**not** a quality measure):

| Theme | v1 members (US-relevant) | S1 broad | S2 title-only |
| --- | ---: | ---: | ---: |
| `EQUITY_US` | 2,751 (2,751) | 13,103 | 1,217 |
| `RATES_US` | 2,909 (2,908) | 6,894 | 464 |
| `GOLD` | 193 (100) | 199 | 50 |

**Flag-only themes, rows:**

- `ECON_INFLATION` 7,825;
- `EPU_CATS_MONETARY_POLICY` 5,529;
- `ECON_DEBT` 4,167;
- `WB_2936_GOLD` 3,682;
- `WB_1045_TREASURY` 2,546;
- `ECON_IPO` 491;
- `ECON_EARNINGSREPORT` 315;
- `ACT_YIELD` 156;
- `ECON_BUBBLE` 29.

**Rows matching a near-miss cue but not captured:** 24,492.

**Every theme has at least 100 member rows,** so the count-based stage C trigger has **not** fired.
The revision trigger can only follow the labelled review.

**Output:**

- **Day commits:** 170 UTC days committed atomically, and all 170 day files and 170 audit files
  re-hash to their recorded SHA-256.
- **Rows kept:** 26,854, equal to the captured total.
- **Temporary folder:** empty.

**Reproducibility:** re-parsing all 192 kept archives offline with the tool's own parser, filter and
deduplication gives exactly the recorded counts for every batch:

- physical lines;
- malformed rows;
- valid rows;
- captured rows;
- same-batch duplicates;
- per-theme members.

**Near-empty detection:** `NULL` (unknown) for all 192. The sample's batches are isolated in time, so
no causal 14-day baseline exists. This was the expected limitation (B2-K §11). Nothing is presented as
"not near-empty".

**Stored locally** (git-ignored), `datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/`, about
1,006 MB:

| Folder | Files |
| --- | --- |
| `raw/` | 192 kept sample zips; retained until annotation and review end, then deleted, per your decision |
| `filtered/`, `audit_sample/` | 170 day files each |
| `manifest/` | The manifest (with its WAL files) |
| `logs/` | `run_20261013T162537Z-b858ed.jsonl` |

---

## 7. Gaps, deviations and checks after the run

**Gaps:** none in acquisition. No batch is missing, failed, invalid or unresolved.

**Deviations:**

- **Git commit location:** the commit (`71b363f…`, working tree dirty because of the existing
  uncommitted changes) went into the run's `params_json`. The dedicated `run.code_git_commit` column
  is empty, because `start_run` has no parameter for it. Provenance is complete but stored in a
  different field. This is a small fix for a later phase.
- **Corroboration rule in practice:** 155 of 192 downloads were cached copies. The rule (B2-K) worked
  as designed: each was accepted only on zip-time corroboration.

**Checks after the run:**

| Check | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt -q` | 148 passed, 0 failed (offline) |
| Compile with warnings as errors | OK |
| Unused imports | 0 |
| Git status | Unchanged by the run (the data folder is ignored) |
| `pip freeze` fingerprint | `3393be50…`, unchanged |
| Commits | None made |

---

## 8. Exact next action (annotation was not started, as instructed)

**Your instruction is needed to prepare the annotation files.** The next command is offline: no
network. It builds the blind review files from the verified local sample:

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt build-review --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml
```

**What it writes,** into `datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/review_files/`
(git-ignored):

| File | Content |
| --- | --- |
| `annotation_A.csv` | Up to 1,500 items selected by B2-I's seeded cell design |
| `annotation_B.csv` | The ~20% overlap subset |
| `key_sealed.csv` | Each item's cell, weight and filter results |
| `selection_log.json` | Hashes and counts |

**Then you label under option (c):**

- **AI suggestions:** any suggested labels would be disclosed, and you review, correct or reject
  them.
- **No hindsight:** labels never use knowledge of later market moves.
