# Research Enhancement Track — Phase B2-J: Development Sample Approval Checklist

**Type:** preparation only. **Nothing is approved by this report.** Full
acquisition and B3 remain prohibited, and blockchain work has not started.

**What this phase did:**

- read the B2-G, B2-H and B2-I reports, the architecture document,
  `DECISIONS.md` and `MEMORY.md`;
- wrote the approval checklist, splitting decisions already made from those
  still open;
- designed the isolated parser, filter and manifest utility, with its test plan
  and resource guards;
- verified the B2-I sample design by re-deriving both lists from the B2-I report
  text alone.

**What it did not do:**

- no network request, download, database query or dependency change;
- no implementation: no application code, schema, model, training script,
  market data or data directory was touched;
- no change to the B2-I sample lists, seed, hashes, rubric or thresholds.

**Date:** 2026-10-13 (UTC).

**Builds on:**

- `reports/phaseB2I_filter_review_and_acquisition_preparation.md` (B2-I),
  SHA-256 `53637db6…`;
- `reports/phaseB2H_pre_acquisition_readiness.md` (B2-H);
- `reports/phaseB2G_gdelt_pilot_audit.md` (B2-G);
- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`.

`docs/DECISIONS.md` still ends at ADR-042 with no GDELT ADR [VERIFIED]. None was
created.

**Labels:**

- **[VERIFIED]**: confirmed from the repository or a local read-only check.
- **[ESTIMATED]**: computed from verified or measured inputs plus stated
  assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## Summary

- **Sample integrity is verified** [VERIFIED].
  - **Reproducible:** an independent re-implementation, working only from the
    B2-I report text, reproduces both lists and all three committed hashes
    (`a459a3fb…`, `b580e8cf…`, `96bd5c0c…`).
  - **Training period only:** all 192 development batches were available by
    2023-12-24 03:30 UTC, 281.5 h before the first training window's last
    cutoff. All 192 confirmation batches were available by 2024-01-03 07:00 UTC.
  - **Never inspected:** no content of any listed batch has ever been
    downloaded.
  - **Separate:** the two lists share no batch.
- **Approval checklist:** 12 items across four gates.
  - **Already decided by you (B2-I):** the minimal window; English only; the
    June 2025 outage accepted; filters approved for labelled review only;
    downloading one batch at a time.
  - **Still open:** everything needed to start, listed per gate in section 2.3.
- **Isolated utility** [PROPOSED]:
  - a new subpackage, `backend/wealthpilot/data/gdelt/`, that nothing in the
    application imports;
  - standard library plus the declared PyYAML only;
  - downloads use `http.client`, not `requests`, which is undeclared, nor `httpx`,
    which is a dev-only extra;
  - B2-I's manifest schema, unchanged;
  - every mode beyond a dry run gated by an explicit approval record.
- **Test plan:** about 90 offline tests in ten groups, built on synthetic
  fixtures and a fake transport. Real network access is blocked in every test.
- **Resource guards:**
  - hard, configurable limits on bytes, requests, concurrency, retries,
    absence-check spacing, free disk and temporary disk;
  - sequential by default; parallel disabled until you approve it;
  - the development sample is capped at 1.50 GB on the wire and should take about
    10–15 minutes at the speed measured in B2-G.

---

## 1. Evidence inspected and items preserved [VERIFIED]

**State checks:**

| Check | Result |
| --- | --- |
| Git status vs the end of B2-I | Identical |
| `pip freeze` fingerprint | `3393be50…`, unchanged |
| `DECISIONS.md` | Ends at ADR-042; no GDELT ADR |
| `MEMORY.md` | B2-I status recorded; "Full acquisition is not approved" |
| GDELT data on disk (repository and scratch folder) | None; no `datasets/raw/gdelt` folder |
| B2-I report as read | SHA-256 `53637db688cb83a0a4119e0c284af6a98de20b0d24225eadb76d73be387e7e51` |

**Carried forward unchanged from B2-I.** Any change to these would be a new,
disclosed protocol version, never a silent edit.

| Item | Where defined |
| --- | --- |
| Seed `wealthpilot-b2i-filter-review-v1`, the frame, 24 blocks, rounds and substitution rule | B2-I §4.2 |
| Development list (stage D, 192 batches), SHA-256 `a459a3fb44afd7e1e8121cd04f247564ea4e8fe434fdca33c9570e50605b2730` | B2-I §4.2, Appendix A |
| Confirmation list (stage C, 192 batches), SHA-256 `b580e8cfc3138cb2a4abc122ed27b25490ef24a4b15d7d9fddc12cf8b9ea8dd1` | B2-I §4.2, Appendix A |
| Annotation rubric, ambiguity codes and polarity field | B2-I §3 |
| Cells, sizes and item selection | B2-I §4.3 |
| Estimators, reporting floors (100 / 30 items) and agreement bar (κ ≥ 0.60) | B2-I §4.5–4.6 |
| Decision thresholds: precision ≥ 0.70 with lower bound ≥ 0.60; pooled capture recall ≥ 0.90; one revision; the stage C trigger | B2-I §4.7 |
| Manifest schema `gdelt_manifest_v1` | B2-I §6.3 |

---

## 2. Approval checklist

### 2.1 Already decided by you (B2-I instructions)

- **Route:** direct GDELT streaming, conditionally preferred.
- **Window:** the minimal window (≈0.860 TB), subject to final acquisition
  approval. There is therefore no news holdout.
- **June 2025 outage:** accepted as missing; no further checks.
- **Language and scope:** English only; market level, with no instrument-specific
  claims.
- **Missing data:** never converted to neutral.
- **Filters:** approved for labelled review only, not frozen.
- **Download strategy:** one batch at a time ("Download one batch at a time", B2-I
  workflow item 3).
- **Not approved:** full archive download; B3.

### 2.2 The twelve items

**Gates:**

- **G1:** start the implementation phase. Code and offline tests only, no
  network.
- **G2:** download the development sample.
- **L:** before the first label.
- **G3:** open the confirmation sample.
- **G4:** full acquisition. This is not being requested now.

| # | Item | Status | What you confirm | Proposed default | Needed by |
| --- | --- | --- | --- | --- | --- |
| 1 | Development sample and byte budget | **Open** | Download the 192 stage D batches in B2-I Appendix A (`a459a3fb…`): 192 header requests, then 192 downloads. Raw zips are kept in `review/` until the review closes | Stop before any download if the header-reported total exceeds **1.30 GB**. Hard cap **1.50 GB** on the wire, retries included | G2 |
| 2 | Confirmation-sample trigger | **Proposed** (B2-I §4.7) | Stage C opens only if stage D shows a revision, or a theme with fewer than 100 member rows. The second condition is decided from counts only. When it fires, the tool stops and asks you again, because it costs bandwidth | As written. Series-only revisions may instead be confirmed after acquisition, on training rows outside stage D | Rule fixed by **L**; opening needs **G3** |
| 3 | Annotation rubric and thresholds | **Proposed** (B2-I §3, §4.5–4.7) | The rubric's judgement calls: macro data is `RL` without a rates framing; local gold rates are `RL`; single companies are `RL`. Also κ ≥ 0.60; precision ≥ 0.70 with lower bound ≥ 0.60; pooled capture recall ≥ 0.90 | As written | L |
| 4 | Annotator arrangement | **Open** | Who labels | (a) you alone, with 10% re-labelled after 7 days; (b) you plus a second person on a 20% overlap; (c) Claude as a disclosed second annotator. **(b) is recommended** | L |
| 5 | Capture rule and batch availability time | Capture rule: **approved for review only**, not frozen. Availability rule: **proposed since B2-F**, never formally approved | Availability = max(nominal batch time, HTTP Last-Modified) + 15 min, recorded per file. Freezing the capture rule comes after the review | Approve the availability rule now; freeze the capture rule at G4 | Availability: G1. Capture freeze: G4 |
| 6 | Stored columns and theme-string retention | **Open** | Minimal columns (B2-I §7), or those plus the full `V1THEMES` string at ≈2–3× the storage | **Keep the full string.** It is cheap insurance against an irreversible loss: ≈4–13 GB of 182.8 GB free | G4. Not needed for the sample, whose raw zips are kept |
| 7 | Duplicate and update handling | **Proposed** (B2-H §4.6) | Causal, story-level rules: same-batch URL, re-observation, update, and a 72-hour syndication window. Only the same-batch rules are used for the sample's `mech_dup` field. The rest can be recomputed from stored rows | Approve the same-batch rules for G2; the full rules before the deduplication pass | G2 for same-batch rules; G4 for the rest |
| 8 | Early-close cutoff rule | **Proposed** (B2-H §5.3–5.4) | A 13:00 ET cutoff on the 9 official early closes. It does not affect the sample: the frame ends at a normal 16:00 close (2024-01-04), and early closes do not enter selection | As proposed | G4 (and any B3 feature) |
| 9 | Missing and near-empty data thresholds | **Proposed** (B2-H §5.5) | Coverage threshold 0.75 (0.50 and 0.90 as sensitivity). Near-empty = rows below 10% of the median for the same slot over the previous 14 days. Backlog = rows above 3× that median. All recomputable from stored row counts | As proposed | Before the G4 coverage report and B3 |
| 10 | Download strategy | One at a time: **decided**. Parallel: **open** | Whether parallel mode (2–4 connections) may ever be enabled | **Disabled for the sample.** Decide for the full run only after its first few hundred files | G2 (stays disabled); G4 (decision) |
| 11 | Internet bandwidth and data cap | **Open** | For G2: at least 1.5 GB of remaining allowance, and no metering penalty you would mind. For G4: the full B2-I §9.1 checklist | — | G2 (minimum); G4 (full) |
| 12 | Storage and retention | **Open** | Location `datasets/raw/gdelt/english_gkg_v1/` (git-ignored); review zips deleted when the review report is accepted; label files local or tracked without titles; whether to keep the master-list snapshot | Review zips deleted on acceptance; label files local | G2 (review folder); G4 (the rest) |

### 2.3 What each gate needs

| Gate | Confirm before it |
| --- | --- |
| **G1: implementation phase** | (a) adding the new subpackage and tests (section 3.1); (b) item 5's availability rule; (c) item 10: sequential default, parallel disabled; (d) the stdlib-only download layer (section 3.12) |
| **G2: download the development sample** | Items 1, 2 (the rule), 7 (same-batch rules), 11 (minimum) and 12 (review folder); also the utility passing its tests and the full regression suite; and who runs it: you, or me in one bounded session of about 10–15 minutes |
| **L: before the first label** | Items 3 and 4 |
| **G3: confirmation sample** | The trigger record plus your explicit yes |
| **G4: full acquisition (not requested)** | Items 5 (freeze), 6, 7 (full rules), 8, 9, 10 (parallel), 11 (full) and 12 (rest); then the ADR |

---

## 3. Isolated implementation design [PROPOSED; not implemented]

### 3.1 Placement and isolation

**Where the code goes:**

- **Package:** `backend/wealthpilot/data/gdelt/`. CLAUDE.md places acquisition
  code in `backend/wealthpilot/data/`.
- **Command line:** `python -m wealthpilot.data.gdelt <command>`.
- **Tests:** `tests/backend/data/gdelt/`.

**Only new files are added.** No existing module changes, not even
`wealthpilot/data/__init__.py`. Nothing exports the package.

**Isolation, each point enforced by a test (section 6, group J):**

- **Nothing in the application imports it.** No module under
  `wealthpilot.api`, `agents`, `core` or `db` imports `wealthpilot.data.gdelt`.
- **It imports almost nothing.** Only the standard library, `yaml` (PyYAML,
  declared) and itself. No SQLAlchemy, no settings, no secrets, no database.
- **It writes only under** its output root (default
  `datasets/raw/gdelt/english_gkg_v1/`) and the test's temporary folder.

**Alternatives rejected:**

- **A top-level `research/` folder:** outside the documented repository layout.
- **Scratch scripts:** not testable, and not reusable by the acquisition.

### 3.2 Modules

| Module | Responsibility |
| --- | --- |
| `config.py` | Frozen dataclasses for limits and approvals. Loads one run-config YAML and validates it. **Refuses to start without an explicit byte cap** |
| `grid.py` | UTC stamps, the slot grid, UTC days, the window. Cutoffs via `zoneinfo`, asserting `tzdata` offsets at start. `available_at` and the forecast-interval mapping |
| `sample.py` | Ships the B2-I stage lists verbatim and refuses to run unless their SHA-256 values equal the committed ones. Applies the substitution rule. Gates stage C behind a trigger record |
| `transport.py` | A `Transport` interface. `HttpsTransport` uses `http.client.HTTPSConnection`: keep-alive, the default TLS context, no automatic redirects, timeouts, and a body-size guard while streaming. Tests use a fake |
| `existence.py` | The header-check policy: turns responses into the existence states of B2-I §6.1, applying the spacing and freshness rules and the accepted-outage set |
| `integrity.py` | Size, MD5 (list or ETag), zip structure, guards and CRC-32 |
| `parser.py` | An incremental row iterator over the zip member, with per-row reason counts |
| `filters.py` + `filters/gdelt_filter_v1.yaml` | The versioned filter rules: normalisation, capture, flags, series, the S1 and S2 variants. Pure functions |
| `dedup.py` | Within-batch duplicate rules, and the causal cross-batch state (72 h), ordered by (`available_at`, record sequence) |
| `manifest.py` + `manifest_v1.sql` | B2-I's DDL, unchanged. An explicit table of allowed state transitions, checked in code before SQLite's own constraints. WAL mode, foreign keys on, one writer |
| `output.py` | Per-slot shards, atomic daily commit, the audit sample |
| `guards.py` | Byte budgets (per run and per billing period), request cap, free disk, temporary disk, the stop file, clock skew |
| `cleanup.py` | Path-guarded deletion (B2-I §8.5) |
| `review.py` | Cell assignment, item selection, the blind annotation file, the sealed key, locking and unsealing |
| `cli.py` / `__main__.py` | The commands in section 3.3 |

### 3.3 Commands and approval gates

| Command | Network | Allowed when |
| --- | --- | --- |
| `verify-plan` | None | Always. Checks list hashes, the spec hash, the config, `tzdata`, free disk and ignore rules, and prints the plan |
| `fetch-sample --stage D` | 192 header requests + 192 downloads | The config holds `approvals.dev_sample` (date, report reference) and the byte caps (G2) |
| `build-review`, `lock-labels`, `unseal` | None | After `fetch-sample` |
| `fetch-sample --stage C` | Up to 192 + 192 | A trigger record exists **and** the config holds `approvals.confirmation_sample` (G3) |
| `acquire` | Full window | Refuses unless the config holds `approvals.full_acquisition`. **Not approved;** in the next phase it is tested only against the fake transport |

Approval records are entries you write in the local run config. They are a
procedural guard against accidental runs, not a security control.

### 3.4 One slot, start to finish

1. **Budget:** check the byte, request, disk and temporary-disk guards.
2. **Header request** for the size and the ETag. A redirect is followed at most
   once, and only to the identical HTTPS resource, `:443` included: B2-H's
   corrected guard.
3. **Download** the body into memory in 1 MiB chunks. If Content-Length exceeds
   `max_body_bytes`, nothing is fetched. A stream that runs over is aborted.
4. **Check integrity** (section 3.6). On failure, re-download once; if it fails
   again, mark it `present_invalid`.
5. **Parse** incrementally and filter (sections 3.5 and 3.7).
6. **Write** the slot's shard and fsync it. Record its SHA-256, counts,
   `available_at_utc`, flags and HTTP metadata in **one** manifest transaction.
   The body is then dropped.
7. **Commit the day** once all its slots are final (section 3.9).

**Allowed transitions,** enforced in `manifest.py` before SQLite's constraints:

| From | To |
| --- | --- |
| `pending` | `in_progress` |
| `in_progress` | `fetched`, `retry_wait`, `failed_permanent` |
| `retry_wait` | `in_progress` |
| `fetched` + `validation_status = passed` | `committed` |

**Every other transition raises.** For example:

- `committed` back to `pending`;
- `absent_accepted` to `fetched`;
- `present_verified` to `request_failed`.

### 3.5 Incremental processing and bounded memory

**How a file is read:**

- **Member stream:** `zipfile.ZipFile(io.BytesIO(body)).open(member)`, read as
  bytes.
- **Rows:** split on LF only. A row is never accumulated beyond
  `max_line_bytes` (default 8 MiB); a longer row is counted `oversize_line` and
  skipped to the next LF.
- **Text:** each row is decoded as strict UTF-8 on its own, so one bad row
  cannot spoil the rest.
- **Fields:** only the fields the filter needs are converted; the rest stay as
  slices.

**Peak memory** [ESTIMATED]: one body (at most 100 MB by guard; the largest
listed file is 51.1 MB), plus about 5 MB for parsing (B2-G measured), plus the
interpreter. That is under 200 MB per process. Sequential mode holds one body at
a time.

**Optional disk staging** (`stage_body_to_disk`, off by default): the body is
streamed to `tmp/` instead of memory, still subject to the temporary-disk cap,
and deleted straight after parsing.

### 3.6 Checksum and zip validation, in order

1. **Byte count:** received bytes equal Content-Length, which equals the
   expected size (from the master list for the full run, from the header for the
   sample). Otherwise `size_mismatch`, or `body_incomplete` if truncated.
2. **MD5:** checked against the master list or the ETag. A non-MD5 ETag gives
   `md5_source = NULL`, and the slot is flagged as checked by CRC and size only.
3. **Zip structure:**
   - exactly one member, named `<stamp>.gkg.csv`;
   - no path separators, absolute paths or `..`;
   - not encrypted;
   - compression method stored or deflate.
4. **Expansion:** uncompressed size at most 400 MB and at most 10× the
   compressed size. Checked from the zip header before reading, and again while
   reading.
5. **CRC-32:** confirmed by reading the member to the end. A mismatch discards
   every row from that slot; nothing reaches a shard.

### 3.7 Deterministic filter versions

**The specification:**

- **One file per version:** `filters/gdelt_filter_v1.yaml`, read with
  `yaml.safe_load`.
- **Registered hash:** a registry maps each version to the SHA-256 of its file.
  A test fails if the file changes without a new version.
- **Fixed inside the version:** the rules of B2-H §4.1–4.4, including the S1 and
  S2 variants. No command-line or config switch changes rule meaning.

**On every output:**

- **Version stamps:** each stored row, manifest row and day file carries
  `filter_version` and `parser_version`.
- **Reproducibility:** output is byte-identical across runs. Rows keep their
  input order, gzip uses a fixed modification time of 0, and nothing depends on
  locale or hash ordering.

**A revision is a new file,** `gdelt_filter_v2.yaml`, with a change log citing
the stage D evidence. It is applied to the whole window, never in place.

### 3.8 Explicit UTC availability

- **Time zones:** every datetime is timezone-aware UTC. Naive datetimes are
  rejected at the boundaries.
- **The availability rule:**
  `available_at = max(nominal, Last-Modified) + 15 min`.
  - **Late flag:** `late_flag = 1` when Last-Modified is more than 15 minutes
    after the nominal time.
  - **No Last-Modified:** nominal + 15 min is used and the slot is listed as an
    anomaly. B2-F and B2-G found the header on every file checked.
- **Page timestamps never set availability.** `PAGE_PRECISEPUBTIMESTAMP` is
  stored as a diagnostic only.
- **Forecast origin d** takes batches with cutoff(previous trading day) <
  `available_at` ≤ cutoff(d).
  - **Calendar:** the cutoff calendar is an input, the stored trading days plus
    the approved early-close list (item 8). It is never hard-coded.
- **Sample rule:** a sample batch whose observed `available_at` falls after
  cutoff(2024-01-04) is dropped. This is pre-registered; the current margin is at
  least 38 h.

### 3.9 Atomic daily output and resumption

As B2-I §7, steps 8–9:

- **Shards:** each slot's rows go to a shard file, which is fsynced and hashed.
- **The day commit:**
  1. concatenate the day's shards in time order into a temporary file;
  2. fsync it;
  3. move it into place with `os.replace`;
  4. re-read it and hash it;
  5. write `day_commit` and mark the slots committed, in one SQLite
     transaction;
  6. delete the shards.
- **Restart:**
  - any `in_progress` slot returns to `pending`;
  - a shard with a matching hash is reused, so nothing is downloaded again;
  - a mismatched shard is deleted and its slot reset;
  - committed days are never rewritten.
- **A crash between `os.replace` and the database commit** is detected on
  restart: the file exists with no `day_commit` row. It is rebuilt from its
  shards and its hash re-checked.

### 3.10 States kept apart

The B2-I §6.1 states are used unchanged:

- **absent:** `absent_confirmed`, `absent_inconclusive`, `absent_accepted`;
- **failed:** `request_failed`, `inaccessible`, `present_invalid`;
- **not yet known:** `unverified`;
- **processed:** `present_verified` plus `committed`.

A coverage figure never counts a non-processed slot as present, and never turns
missing into zero.

### 3.11 Safe cleanup and nothing raw in Git

**Cleanup** follows the path-guarded procedure of B2-I §8.5:

- deletion only inside `tmp/` (and the review `raw/` folder on your
  instruction);
- symbolic links refused, and names checked against patterns;
- no recursive deletes;
- `delete_failed` is retried at the next start.

**Before any network request,** the preflight runs
`git check-ignore -q <output root>` and refuses an output root Git does not
ignore.

**What reaches the repository:** only aggregate reports and hashes, never titles
or rows.

### 3.12 Dependencies: none new [VERIFIED]

| Library | Status | Use |
| --- | --- | --- |
| Standard library: `http.client`, `ssl`, `zipfile`, `io`, `gzip`, `csv`, `hashlib`, `sqlite3` (SQLite 3.45.1), `zoneinfo`, `html`, `unicodedata`, `re`, `shutil`, `os`, `json` | Built in | Everything except the spec file |
| PyYAML 6.0.2 | Declared runtime dependency | Reading the filter specification and run config |
| `tzdata` 2026.4 | Installed through pandas, not declared | Time-zone data for `zoneinfo` on Windows. Checked at preflight; declaring it would be a dependency change for you to approve |
| `requests` 2.34.2 | **Not declared**; installed only because yfinance requires it | Used by the B2–B2-H scratch scripts. **Not used here,** to avoid an undeclared dependency |
| `httpx` 0.27.2 | Declared only in the `dev` extra | **Not used at runtime** |

---

## 4. Sample-design verification [VERIFIED]

**Method:** an independent script read only the B2-I report: its §4.2 algorithm
text, its Appendix B gap list and its printed lists and hashes. It did not use
B2-I's own script or saved output. It re-derived both stages, compared them, and
wrote nothing back. Nothing was regenerated or modified.

| Check | Stage D (development) | Stage C (confirmation) |
| --- | --- | --- |
| Recomputed list SHA-256 equals the committed value | Yes, `a459a3fb…` | Yes, `b580e8cf…` |
| Recomputed list equals the printed Appendix A list | Yes | Yes |
| Combined D-then-C SHA-256 | `96bd5c0c…`, matches | (same) |
| Batches; distinct; on the 15-minute grid | 192; 192; yes | 192; 192; yes |
| Range (UTC stamps) | `20211202210000` → `20231224031500` | `20211203011500` → `20240103064500` |
| All available by the first training window's last cutoff (2024-01-04 21:00 UTC) | Yes; latest at 2023-12-24 03:30, **281.5 h** before | Yes; latest at 2024-01-03 07:00, **38.0 h** before |
| In the December 2021 lookback / in training-origin intervals | 7 / 185 | 8 / 184 |
| Any batch in the embargo, test or later | None | None |
| Any known-absent slot, or the excluded B2 batch `20220103143000` | None | None |
| Any batch ever downloaded (B2: `20220103143000`, `20240112210000`; B2-G: `20251223144500`) | None | None |
| Overlap between the stages | 0 | 0 |

**Fixed before any content was inspected:**

- **Selection inputs:** the procedure uses only grid timestamps, a seeded hash
  and the known-absent metadata from the audited master list. No article content
  is involved.
- **Content never retrieved:** none of the 384 batches has ever been downloaded.
  The only three GDELT batches ever fetched are listed in the table above, and no
  GDELT file exists on disk.
- **Commitment:** the lists and their SHA-256 values were committed in B2-I and
  reproduce exactly from its text today.

**Stage C remains inaccessible.**

- **Now:** none of its content exists anywhere, and no tool to fetch it exists
  yet.
- **After implementation:**
  - `sample.py` will not load the stage C list without a trigger record:
    - stage D counts per theme, read from the stage D manifest;
    - the revision flag, which requires a v2 spec file with a change log;
    - the time;
    - your approval entry.
  - Tests cover the refusal (section 6, group I).
- **Limit:** the stamps themselves are public by design, since they are
  pre-registered. Only access to their content is gated, and the gate is
  procedural, not cryptographic.

**Still not claimed** [BLOCKED until the review runs]:

- any precision, recall or representative-coverage figure;
- any choice of filter or keyword. No test-period result has been or will be
  used.

---

## 5. Resource and network guards [PROPOSED defaults; all configurable]

| Limit (config key) | Development sample | Full acquisition (G4) | When it trips |
| --- | --- | --- | --- |
| Total bytes on the wire (`max_total_bytes`) | **1.50 GB** | **Required; no default.** The run refuses to start without it | A download that would cross the cap never starts; clean stop, `stopped_byte_budget` |
| Header-reported total before any download (`max_planned_bytes`) | **1.30 GB** (expected ≈1.03 GB) | Not used (the master list gives sizes) | Stop before the first download and report |
| Bytes per billing period (`period_bytes_cap`, `period_start_day`) | Optional | From your checklist answers | Clean stop. The next period resumes |
| Requests per run (`max_requests`) | **1,200** (192 header + 192 download + retries and substitutions) | Set at G4 | Clean stop |
| Concurrent requests (`max_concurrency`) | **1** | 1 unless you approve 2–4 | — |
| Parallel mode (`parallel_enabled`) | **false**; refused for the sample | false. Needs both the config flag and `--enable-parallel`; never more than 4 | Refused at start |
| Attempts per slot per run (`max_attempts`) | 5 | 5 | `retry_wait`, then a final pass |
| Backoff (`backoff_s`) | 4, 8, 16, 32, 64 s; `Retry-After` honoured up to 300 s; at most 10 min per slot | Same | — |
| Final retry pass (`final_pass_delay_s`) | ≥ 3,900 s (65 min) | Same | Then `request_failed` |
| Re-downloads after an integrity failure (`max_redownloads`) | 1 | 1 | `present_invalid` |
| Spacing between counted absence checks (`absence_check_spacing_s`) | ≥ 3,900 s (CDN caches 3,600 s) | Same | An earlier check is not counted |
| Freshness of an absence check | Server `Date` within 120 s of the local clock; `Age` ≤ 60 s | Same | Treated as cached and not independent |
| Header requests per slot per run (`max_head_per_slot`) | 3 | 3 | `absent_inconclusive` |
| Timeouts | Connect 15 s; read 60 s; 600 s per download | Same | Counted as transient |
| Body size (`max_body_bytes`) | 100 MB | 100 MB | `size_guard_exceeded` |
| Uncompressed size and ratio | 400 MB; 10× | Same | `size_guard_exceeded` |
| Longest row (`max_line_bytes`) | 8 MiB | 8 MiB | Row counted `oversize_line` |
| Free disk at preflight (`min_free_bytes_preflight`) | 20 GB | 20 GB (35 GB with the full theme string) | Refuses to start |
| Free disk at runtime (`min_free_bytes_runtime`) | 10 GB, checked before every download and every commit | Same | Clean stop, `stopped_disk_space` |
| Temporary disk (`max_tmp_bytes`) | 0.5 GB (`tmp/` plus any staged body) | Same | Clean stop |
| Bandwidth ceiling (`max_mbit`) | Off. You may set one | Off unless you set it | Throttled |
| Clock skew (`max_clock_skew_s`) | 300 s against the server `Date` | Same | Refuses to start, because the freshness rules depend on the clock |
| Stop file | `STOP` in the output root | Same | Stops after the current slot |

**Development sample timing** [ESTIMATED, at B2-G's measured rate]:

- 192 header requests: ≈3–5 min;
- 192 downloads, each 1.1–1.4 s of latency plus ≈1 s of transfer: ≈7–8 min;
- **about 10–15 minutes in total,** one at a time.

These figures exclude retries, throttling and any CDN slowdown.

---

## 6. Test plan [PROPOSED]

**Rules for every test:**

- **No network:** an automatic fixture makes any socket connection fail, and the
  suite asserts that no connection was attempted. All HTTP goes through a fake
  transport and a fake clock.
- **No database,** and nothing written outside the test's own temporary folder.
- **Synthetic fixtures only:** rows and zips are built inside the tests. No real
  GDELT data is used or stored.
- **Where they run:** inside the normal suite, `pytest tests/ -v`. CLAUDE.md
  still requires a clean, isolated full run before completion is claimed.

### A. Malformed input and integrity

| ID | Case | Expected |
| --- | --- | --- |
| A1 | Valid 27-field row | Parsed; title HTML-decoded; `title_norm`, `title_hash`, `url_canonical` correct |
| A2 | 26 or 28 fields | Counted `field_count`; the rest of the file still parses |
| A3 | Invalid UTF-8 in one row | That row counted `decode`; other rows unaffected |
| A4 | `V2.1DATE` or record-ID prefix ≠ stamp | `date_mismatch` |
| A5 | Non-blank `TRANSLATIONINFO`, or a translated-record marker | `translated`; never captured |
| A6 | Source collection ≠ 1 | `non_web` |
| A7 | CRLF endings, no final newline, empty rows | Handled deterministically and counted |
| A8 | Row longer than `max_line_bytes` | `oversize_line`; memory stays bounded |
| A9 | Empty or missing `PAGE_TITLE` | Title "", `title_hash` NULL |
| A10 | Two members, a wrong name, or a `../` path | `member_unexpected`; nothing written to disk |
| A11 | Encrypted member or unknown compression | `zip_invalid` |
| A12 | One byte flipped (CRC) | `crc_failed`; no row from that slot reaches a shard |
| A13 | Truncated body | `body_incomplete`; retried |
| A14 | Expansion above 10× or 400 MB (zip bomb) | `size_guard_exceeded`, without decompressing it all |
| A15 | MD5 mismatch (list or ETag); size mismatch | One re-download, then `present_invalid` |
| A16 | 50 MB synthetic member | `tracemalloc` peak below a fixed bound |

### B. Missing and unavailable batches

| ID | Case | Expected |
| --- | --- | --- |
| B1 | Listed, 200 and valid | `present_verified` |
| B2 | Unlisted, two fresh 404s ≥ 65 min apart | `absent_confirmed` |
| B3 | Two 404s under 65 min apart | Second not counted; `absent_inconclusive` if never confirmed |
| B4 | 404 with `Age` > 60 s | Not independent: `absent_inconclusive` |
| B5 | Only timeouts, 5xx or 429 | `request_failed` after the budget; never absent |
| B6 | Other 4xx; redirect to another host, path or port | `inaccessible`. A redirect to the same resource with `:443` is accepted (B2-H's run-1 case) |
| B7 | June 2025 accepted slots | `absent_accepted`; the fake transport records **zero** requests for them |
| B8 | Listed slot answering 404 twice | `absent_confirmed`, plus an anomaly |
| B9 | Unlisted slot answering 200; ETag not an MD5 | Fetched; `md5_source` NULL; flagged CRC and size only |
| B10 | Coverage with absent, failed and near-empty slots | Counted missing, never zero; the day still commits with the failures counted |

### C. Duplicate stories

| ID | Case | Expected |
| --- | --- | --- |
| C1 | Same canonical URL twice in a batch | Lowest sequence kept; `DUP_SAME_BATCH` |
| C2 | Same normalised title, different URL, same batch | `SYNDICATED_SAME_BATCH` |
| C3 | URL seen in an earlier batch, same `title_hash` and `word_count` | `reobservation_of` the first record |
| C4 | URL seen earlier, different signature | `update_of`; the earlier row is unchanged |
| C5 | Title seen 71 h 45 min earlier vs 72 h 15 min earlier | Same story vs new story |
| C6 | Short or empty titles | Never merged |
| C7 | Causality: one run vs a run resumed half-way | Identical story fields. A later row never changes an earlier one |
| C8 | URL canonicalisation: scheme, `www.`, query, fragment, trailing slash, host case | As B2-H §4.1 |

### D. Timestamp leakage

| ID | Case | Expected |
| --- | --- | --- |
| D1 | Last-Modified before the nominal time | `available_at` = nominal + 15 min |
| D2 | Last-Modified after the nominal time | `available_at` = Last-Modified + 15 min; `late_flag` only beyond 15 min |
| D3 | Page timestamp far in the past or future | No effect on `available_at` or interval |
| D4 | Available exactly at the cutoff vs one second after | This origin vs the next trading day. Includes both daylight-saving changes |
| D5 | An approved early-close day (2023-11-24) | 13:00 ET cutoff, from the calendar input |
| D6 | Weekend, holiday, and the 2025-01-09 closure | Rolled to the next trading day |
| D7 | Sample batch observed available after cutoff(2024-01-04) | Dropped and logged |
| D8 | Backlog batch | Kept at its own time; never back-dated |
| D9 | Naive datetime passed in | Rejected. `tzdata` offsets asserted at start |

### E. Manifest states

| ID | Case | Expected |
| --- | --- | --- |
| E1–E9 | The nine invalid states of B2-I §6.5 | Rejected by SQLite constraints |
| E10 | Illegal transitions in code (`committed` → `pending`, `absent_accepted` → `fetched`, …) | Raise before reaching SQLite |
| E11 | Crash between `os.replace` and the database commit | Restart rebuilds from the shards; one `day_commit` row; hash verified |
| E12 | Opening the manifest | Foreign keys on, WAL mode, schema version recorded |

### F. Filters and versions

| ID | Case | Expected |
| --- | --- | --- |
| F1 | v1 spec file edited without a version change | Test fails: SHA-256 differs from the registry |
| F2 | Theme-code look-alikes (`TAX_TERROR_GROUP_GOLDEN_DAWN`) | Not matched; exact codes only |
| F3 | Phrases: "U.S." gives "u s"; the pronoun "us"; "fed" | Whole-word rules as B2-H §4 |
| F4 | `company_item` patterns: ticker tags, cashtags, phrases | Flagged |
| F5 | Series rules: `EQUITY_US` mentions and US relevance; `RATES_US`; `GOLD` with no US requirement; S1, S2 | As B2-H §4.4 |
| F6 | Same input run twice | Byte-identical outputs and hashes |
| F7 | Audit sample over many synthetic record IDs | Deterministic; rate ≈ 1/1,000 |

### G. Resource guards (fake clock, fake disk and fake transport)

| ID | Case | Expected |
| --- | --- | --- |
| G1 | No byte cap in the config | Refuses to start |
| G2 | Header-reported total above `max_planned_bytes` | Stops before any download |
| G3 | Next download would cross `max_total_bytes` | Never started; `stopped_byte_budget`; no partial slot |
| G4 | Billing-period cap across two runs | Summed from the `attempt` rows |
| G5 | Parallel without both switches; more than 4 | Refused |
| G6 | Retry schedule and `Retry-After` cap | 4–64 s; at most 300 s |
| G7 | Absence-check spacing | Enforced |
| G8 | Free disk below the preflight or runtime floor | Refuses or stops cleanly |
| G9 | Temporary disk above `max_tmp_bytes` | Stops cleanly |
| G10 | `STOP` file | Stops after the current slot |
| G11 | Request cap | Stops cleanly |
| G12 | Clock skew over 300 s | Refuses to start |

### H. Output, resumption and cleanup

| ID | Case | Expected |
| --- | --- | --- |
| H1 | Shard and day commit | fsync, `os.replace`, hash recorded |
| H2 | Crash after each step | No duplicate rows; no download repeated when a valid shard exists |
| H3 | Second run over committed days | Days not rewritten |
| H4 | Cleanup outside `tmp/`, via a symbolic link, or a bad name | Refused |
| H5 | Leftovers in `tmp/` | Emptied at start and end, or reported |
| H6 | Output root not ignored by Git (injected checker) | Refuses to start |
| H7 | Fixture rows carrying marker titles | Logs contain no titles and no secrets |

### I. Sample and review

| ID | Case | Expected |
| --- | --- | --- |
| I1 | Shipped stage lists | SHA-256 equals `a459a3fb…` and `b580e8cf…`. Re-deriving them from the algorithm and the known-absent slots matches |
| I2 | Stage C with no trigger record, or a trigger not supported by the stage D counts | Refused |
| I3 | Sample slot absent, or invalid twice | Replaced by the next stamp in its block's order; logged |
| I4 | Cell assignment and item selection | Priority order and hash selection as B2-I §4.3; deterministic |
| I5 | Annotation file | No cell, filter, theme or tone column. Deterministic shuffle. The key is a separate file |
| I6 | Unsealing before the label hashes are recorded | Refused. Overlap subset ≈ 20% |

### J. Isolation and safety

| ID | Case | Expected |
| --- | --- | --- |
| J1 | Import graph (AST scan) | No `wealthpilot.api`, `agents`, `core` or `db` module imports the package. The package imports only the standard library, `yaml` and itself |
| J2 | `wealthpilot/data/__init__.py` | Does not import or export the package |
| J3 | Network guard | Zero connection attempts across the suite |
| J4 | File writes | Only inside each test's temporary folder |

**Acceptance for the implementation phase:**

- every test above passes;
- the full backend regression suite passes in an isolated run (CLAUDE.md §19);
- `verify-plan` succeeds on your machine without touching the network.

---

## 7. Remaining decisions

1. **G1, the implementation phase:**
   - approve the new subpackage and tests (section 3.1);
   - approve the availability rule (item 5);
   - confirm sequential by default with parallel disabled (item 10);
   - confirm the stdlib-only download layer.
2. **G2, the development sample:**
   - the byte limits: 1.30 GB planned, 1.50 GB hard cap (item 1);
   - the stage C trigger (item 2);
   - the same-batch duplicate rules (item 7);
   - at least 1.5 GB of data allowance (item 11);
   - review-folder retention (item 12);
   - who runs it: you, or me in one bounded session.
3. **Before the first label:**
   - the rubric and thresholds (item 3);
   - the annotator arrangement (item 4; (b) recommended).
4. **G3:** opening stage C, only if its trigger fires.
5. **G4, full acquisition. Not requested now:**
   - freezing the capture rule (item 5);
   - the stored columns, where keeping the full theme string is recommended
     (item 6);
   - the full duplicate rules (item 7);
   - the early-close rule (item 8);
   - the missing-data thresholds (item 9);
   - parallel mode (item 10);
   - the full data-cap answers (item 11);
   - storage and retention (item 12);
   - then the ADR.

**Unchanged:** title redistribution is still [UNVERIFIED], so titles stay local.
Full acquisition and B3 remain prohibited.

---

## 8. Next steps (each needs your instruction)

1. You answer G1. A separate implementation phase then adds
   `backend/wealthpilot/data/gdelt/` and its tests, and runs the full regression
   suite. It makes no network request.
2. You answer G2. The development sample is fetched: 192 header requests and 192
   downloads, within 1.50 GB.
3. You answer L. Then come labelling, the agreement check, locking, unsealing and
   the review report.
4. Under B2-I §4.7: freeze or revise, and open stage C only if its trigger
   fires.

---

## Verification of this phase

**Files created:** this report.

**Files modified:** `docs/MEMORY.md` (track status). No historical report was
changed.

**Network activity:** none.

**Database:** not accessed.

**Local read-only checks:**

- git status (identical to the end of B2-I before this phase's edits);
- the `pip freeze` fingerprint `3393be50…`, unchanged;
- the installed versions of `httpx`, PyYAML, `pytest`, `requests` and `numpy`;
- `backend/pyproject.toml`;
- the existing `wealthpilot/data/` package and `tests/` layout;
- the sample re-derivation (section 4).

**Analysis files** (in the session scratch folder, outside the repository):
`b2j_verify_sample.py` and its output.

**Not done:**

- no download, implementation, dependency change, ADR, or B3 or blockchain
  work;
- no change to application code, database schema, models, training scripts or
  market data.

**Tests:** none run, because no code changed.
