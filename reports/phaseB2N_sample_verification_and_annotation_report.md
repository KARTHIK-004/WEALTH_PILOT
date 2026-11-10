# Research Enhancement Track — Phase B2-N: Sample Verification and Annotation Preparation

**Result:** the B2-M acquisition **has not run**. There is no local sample, so there was nothing to
verify and no annotation dataset could be prepared.

- **This is a gap report**, as B2-N Step 4 requires when the sample is unavailable.
- **No network request was made** and no switch was changed.
- **Report history:** this is a new file, so the B2-M report stays as it was.

**Date:** 2026-10-13 16:08 UTC.

**Labels:**

- **[VERIFIED]**: confirmed by a local check or a test.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## 1. Did the acquisition run? No [VERIFIED from local files]

Checked directly on disk, not from earlier reports or the conversation:

| Evidence | Finding |
| --- | --- |
| Files under `datasets/raw/gdelt/` | Exactly one: `english_gkg_v1/provenance/run_config.yaml` (2,028 B, SHA-256 `5581f3e3…`). Its modification time (21:20 local, i.e. 15:50 UTC) is when B2-M wrote it, so it is unchanged since then |
| Acquisition output folder `english_gkg_v1/review/b2i_review_v1/` | **Does not exist.** No manifest (`manifest/manifest.sqlite`), no `raw/`, `filtered/`, `logs/` or `tmp/` |
| GDELT archives or manifests anywhere in the repository or the session scratch folder | None |
| Build locks | `NETWORK_ENABLED_IN_THIS_BUILD = True`, `DEV_SAMPLE_ENABLED_IN_THIS_BUILD = True` (B2-M); `CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD = False`. Not changed in B2-N |
| Development list | `sample_data/stage_d.txt` SHA-256 `a459a3fb44afd7e1e8121cd04f247564ea4e8fe434fdca33c9570e50605b2730`, matching the commitment |

The tool creates the manifest and the `review/b2i_review_v1/` folder at the start of any
`fetch-sample` run, before its first request. Their absence shows the run was never started on this
machine.

---

## 2. Acquisition audit [BLOCKED: no data]

| Item | Value |
| --- | --- |
| Expected batches | 192 |
| Downloaded / validated / rejected / missing / failed | 0 / 0 / 0 / 0 / 0 |
| Unresolved | **192** (not attempted) |
| Bytes transferred / requests | **0 B / 0**: no manifest `attempt` rows exist, because no manifest exists |
| Manifest fingerprint | The list fingerprint matches `a459a3fb…`. There is no acquisition manifest to compare |
| Checksum, zip integrity, availability timestamps | Not applicable |
| Duplicate and parsing statistics | Not applicable |
| Untrusted or irreproducible files | None, because no data files exist |

**Coverage is not complete:** all 192 batches are unresolved. Nothing here is a neutral observation;
it is simply absent.

---

## 3. Annotation preparation [BLOCKED]

**Not done, as instructed:**

- no annotation file was created;
- no title, label or score was generated.

**What comes after the run** (the annotation builder is ready and tested on synthetic data):
`build-review` creates the blind files from the verified local sample:

| File | Content |
| --- | --- |
| `annotation_A.csv` | All selected items |
| `annotation_B.csv` | The ~20% overlap subset |
| `key_sealed.csv` | Each item's cell, weight and filter results; kept sealed until the labels are locked |
| `selection_log.json` | Hashes and counts |

**Every annotation row keeps its provenance:** record ID, batch date, source domain, URL, title as
published, and the pipeline's duplicate value.

---

## 4. Tests and checks [VERIFIED]

| Check | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt -q -p no:cacheprovider` | **148 passed, 0 failed.** Sockets and DNS are blocked and the database factory raises in every test. Tests write only to temporary folders. `datasets/raw/gdelt/english_gkg_v1/` still holds only `provenance/` afterwards |
| Compile with warnings as errors | OK |
| AST unused-import scan | 0 |
| Network-enabled tests | None exist, and none was run |

---

## 5. Changes in B2-N

**Created:** this report.

**Modified:** `docs/MEMORY.md` (status line).

**Unchanged:**

- tool code, tests, switches and the approval record;
- dependencies, application code, database, models and market data.

**Not done:** no commit or push. Unrelated working-tree changes are untouched.

---

## 6. Exact next action for the project owner

**Explicitly authorise the B2-M acquisition run.** It was prepared and validated in B2-M but never
executed. Either:

- say "run the B2-M acquisition" and I will run it in this session; or
- run it yourself from the repository root:

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt fetch-sample --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml --confirm-network
```

**What the run does:**

- **Scope:** only the 192 fixed development batches.
- **Order:** header checks first, then sequential downloads.
- **Limits:** it stops before downloading if the header-reported total exceeds 1.30 GB. It never
  exceeds 1.50 GB or 1,200 requests, retries included.

**After it finishes:**

1. Verify the local results: counts, bytes, checksums and timestamps.
2. Run `build-review` for the blind annotation files.
3. You label under option (c), with any AI suggestions disclosed as suggestions you review, correct
   or reject, never as independent human ground truth.
