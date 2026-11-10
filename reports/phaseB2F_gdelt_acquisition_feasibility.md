# Research Enhancement Track — Phase B2-F: GDELT Acquisition Feasibility

**Type:** research and planning only. Nothing was acquired, no account was
created, no cost was incurred, and no application code, dependency, schema,
migration, model, training script or dataset changed. B3 has not started.
**Date of research:** 2026-10-12. All web sources were accessed on this date.
**Builds on:** `reports/phaseB2_historical_news_source_evaluation.md` (B2),
`docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` (B0).
**Status going in:** B2's source decision is conditionally approved for GDELT,
subject to acquisition feasibility and later approval of the actual acquisition
route. **This report approves nothing.**

**Scope, as instructed:** English-only GKG 2.0 (no translated stream), original
15-minute granularity, minimal window 2021-12-01 → at least 2026-07-20.

**Labels:**

- **[VERIFIED]**: confirmed from official documentation, the repository, a
  read-only database query, or a header-only observation made in this phase.
- **[ESTIMATED]**: computed from verified inputs plus the stated assumptions.
- **[PROPOSED]**: a recommendation awaiting your approval.
- **[UNVERIFIED]**: not confirmed from a primary source.
- **[BLOCKED]**: cannot be resolved without an action this phase forbids or an
  approval you have not given.

> **Superseded in part by Phase B2-G (2026-10-12):**
> `reports/phaseB2G_gdelt_pilot_audit.md`. This report is kept as written. A
> one-file pilot and a master-list audit changed four points.
>
> 1. **Download size.** The listed English files in the window total exactly
>    860,483,377,717 bytes (0.860 TB), slightly below the ≈0.895 TB estimated here.
> 2. **Gaps.** The master list shows 1,854 absent slots (1.14%), not 1,674.
>    - Besides the June 2025 outages confirmed here, it adds a March 2023
>      disruption (147 slots) and 33 isolated single slots.
>    - It also shows an 83-slot run of near-empty files on 2022-11-10/11.
>    - Section 8.1's test-window table is unchanged.
> 3. **Compression.** The sampled file decompressed at 3.09×, not the 4–5×
>    assumed in section 3.3.
> 4. **Estimates.** Filtered output is re-estimated at ≈1.7–4.3 GB, and the
>    Route B scan at ≈0.5–1.1 TiB.

---

## 1. Executive summary

**Route A is feasible and conditionally recommended:** stream the raw English
15-minute files, filter them locally, and keep no raw archive. **Route B
(Google BigQuery) is feasible only with a Google account and a Cloud project.**
Its query size cannot be pinned down without one.

| Measure | Value |
| --- | --- |
| 15-minute batch slots in the window (2021-12-01 00:00 → 2026-07-20 19:45 UTC) | 162,512 [VERIFIED arithmetic] |
| Mean English file size (time-stratified sample of 484 slots, 480 present) | 5.55 MB; 95% bootstrap interval 5.35–5.76 MB [VERIFIED sizes, ESTIMATED mean] |
| Route A download | ≈0.90 TB (95%: 0.86–0.93 TB; 0.81 TiB) [ESTIMATED] |
| Route A elapsed time | ≈20 h at a sustained 100 Mbit/s, ≈40 h at 50, ≈4 days at 20 [ESTIMATED] |
| Filtered data kept on disk | ≈2–6 GB compressed [ESTIMATED] |
| Route B query scan | ≈0.7–3.6 TiB, against a free allowance of 1 TiB per month [ESTIMATED, low confidence] |
| Free disk | C: 171 GB, D: 470 GB. The raw archive fits on neither, so streaming is required [VERIFIED] |
| New dependencies for Route A | None [VERIFIED] |

**Three new findings change the plan:**

1. **GDELT has a 17-day outage inside the test period** [VERIFIED by header-only
   requests].
   - Gap: no GDELT 2.0 files exist from **2025-06-14 18:00 to 2025-07-02 02:00
     UTC** (1,665 batches). A further 9 batches are missing on 2025-06-12.
   - Scope: the events, mentions, English GKG and translated GKG streams are all
     absent, so no other GDELT file stream can fill the gap.
   - Effect: in test window 6, **10 test returns have no news at all** for their
     forecast interval and 2 more have partial news. They must be treated as
     missing, never as neutral.
2. **B2's window dates were mapped onto price dates** [VERIFIED].
   - `training/market/train.py` builds its windows over the *return* series, so
     the test returns run **2024-01-16 → 2026-07-21**, not 2024-01-12 →
     2026-07-20.
   - B2's two dates are in fact the forecast origins. The last forecast is made
     at the 2026-07-20 close, so the news window still ends at **2026-07-20 16:00
     ET**.
3. **GDELT file timestamps are conservative** [VERIFIED for the sample].
   - The server's Last-Modified time is 8–12 minutes *before* each file's nominal
     batch time, in all 14 files sampled across 2021–2026.
   - So nominal batch time + 15 minutes is a safe availability rule.
   - Historical files show no sign of having been rewritten later.

Route A's conditions are your decisions (section 11):

- your bandwidth and data cap must cover ≈0.9 TB;
- a one-file pilot;
- a frozen filter specification;
- a storage location;
- freezing the market-data snapshot for the research track.

---

## 2. Verified research window

### 2.1 Market side

Read on 2026-10-12, read-only, from `market_data`, `training/market/common.py`,
`training/market/train.py` and `models/metrics.json`.

| Item | Value | Label |
| --- | --- | --- |
| Instruments | `^IXIC`, `^NDX`, `QQQ`, `AGG`, `GLD` | [VERIFIED] |
| Stored prices | 2022-01-03 → 2026-09-11, 1,177 per instrument. This is the data the 2026-09-14 training run used (`models/metrics.json`: same date range, 10 windows, 630 test observations per model) | [VERIFIED] |
| Return rows used by `train.py` | 1,176. `close.pct_change().dropna()` makes 2022-01-04 the first return (`train.py:58-59`) | [VERIFIED] |
| Walk-forward | expanding window over the returns; 504 initial training rows, 5-row embargo, 63-row test windows, 10 windows, 1-day horizon (`common.py:66-71`, `train.py:65`) | [VERIFIED] |
| First training window | returns 2022-01-04 → 2024-01-05 | [VERIFIED] |
| Test returns | **2024-01-16 → 2026-07-21** | [VERIFIED] |
| Unused tail | 37 returns, 2026-07-22 → 2026-09-11 | [VERIFIED] |

The ten test windows, by return date [VERIFIED; identical for all five
instruments]:

| Window | First test return | Last test return |
| ---: | --- | --- |
| 1 | 2024-01-16 | 2024-04-15 |
| 2 | 2024-04-16 | 2024-07-16 |
| 3 | 2024-07-17 | 2024-10-14 |
| 4 | 2024-10-15 | 2025-01-15 |
| 5 | 2025-01-16 | 2025-04-16 |
| 6 | 2025-04-17 | 2025-07-18 |
| 7 | 2025-07-21 | 2025-10-16 |
| 8 | 2025-10-17 | 2026-01-16 |
| 9 | 2026-01-20 | 2026-04-20 |
| 10 | 2026-04-21 | 2026-07-21 |

**Correction to B2.** B2 (section 3) mapped the window indices onto the 1,177
price dates. The return series starts one price date later, so every date B2
reported is one trading day early:

| B2 reported | Correct |
| --- | --- |
| First test day 2024-01-12 | First test return 2024-01-16 |
| Last test day 2026-07-20 | Last test return 2026-07-21 |
| 38 unused days | 37 unused returns |

B2's dates are exactly the forecast origins, which is why its news requirement
still holds. B2 is left as written, with a pointer to this section
(CLAUDE.md §20).

### 2.2 News window

| Item | Value | Label |
| --- | --- | --- |
| Start | **2021-12-01 00:00 UTC** (your minimum). That is about one month of trailing news before the first forecast origin, the 2022-01-03 close. December 2021 holds about 22 trading days | Start [VERIFIED as specified]; day count [ESTIMATED], because stored market data begins 2022-01-03 |
| Forecast alignment | The return dated *d* runs from the close of the previous trading day to the close of *d*. It may use only news available by 16:00 ET on that previous day | [PROPOSED] (section 8) |
| End | The last test return (2026-07-21) is forecast at the **2026-07-20 close: 16:00 EDT, which is 20:00 UTC**. With the +15-minute availability margin, the last usable batch is **2026-07-20 19:45 UTC** | Dates [VERIFIED]; margin [PROPOSED] |
| Batch slots | 1,692 full days × 96 + 80 = **162,512** | [VERIFIED arithmetic] |

### 2.3 Are market dates after 2026-07-20 needed?

- **One is, and it is already stored.** The 2026-07-21 return is the label of
  the last test row. No other market date after 2026-07-20 enters any window.
- **No news after the 2026-07-20 cutoff is needed** for the existing evaluation.
  News after that cutoff belongs to the 2026-07-21 forecast origin, whose target
  (2026-07-22) is in the unused tail.
- **The 37 unused returns (2026-07-22 → 2026-09-11) fall outside every window.**
  `walk_forward_windows` only forms complete 63-row test windows
  (`common.py:146`). They could serve as an optional final holdout. That holdout
  would need news through the 2026-09-10 close: 4,992 more batches, ≈22–28 GB
  more download (+≈3%) [ESTIMATED from the 2026 and whole-window mean sizes].
  This is your decision.
- **Caution: the window set is not frozen in code.** `fetch_ohlcv` downloads
  from yfinance with no end date (`common.py:74-78`), and `train.py` upserts the
  result into `market_data`.
  - An 11th window appears once 26 more returns exist, which means data through
    about **2026-10-19** if markets have no unscheduled closures [ESTIMATED].
  - Re-running market training after that would extend the test period beyond
    this news window.
  - **[PROPOSED]** Freeze the stored 2022-01-03 → 2026-09-11 snapshot for the
    whole research track.

---

## 3. Route A — direct streaming of the English GKG files

### 3.1 How it would work [PROPOSED]

1. **Read the master file list.** Read `masterfilelist.txt` once. It is
   128,482,752 bytes [VERIFIED by a header-only request; not downloaded]. It gives
   every file's URL, size and checksum, and the exact list of missing files.
   - `lastupdate.txt` lists size, MD5 and URL per file [VERIFIED in B2].
   - The master list is expected to use the same format [UNVERIFIED].
2. **Process each slot.** For every 15-minute slot in the window:
   1. Fetch the English `{YYYYMMDDHHMMSS}.gkg.csv.zip` into memory, never the
      `.translation.` file.
   2. Check its MD5.
   3. Decompress it in memory.
   4. Filter the rows (section 7).
   5. Append the kept rows to that month's output file and write one row to the
      batch manifest (section 6).
   6. Discard the zip. **The raw archive is never written to disk.**
3. **Resume and throttle.** A per-file checkpoint makes the job resumable.
   Concurrency stays at four connections or fewer, with retry and backoff.
4. **Tools: no new dependency.**
   - Downloads: `httpx` (already declared, `backend/pyproject.toml:50`) or the
     standard library's `urllib`.
   - Processing: `zipfile`, `csv`, `gzip`, `hashlib`, `html`, `zoneinfo`.
   - The code would live in `backend/wealthpilot/data/`, which holds acquisition
     code only.
   - You run it; CLAUDE.md rules out Claude running long jobs.

### 3.2 Evidence (header-only; no file body downloaded)

- **Sample design** (seed 42):
  - two random slots from every 7-day block across the window, 484 slots in
    total;
  - plus every slot of two random full days.
- **Results:**
  - 480 of the 484 slots were present. The 4 missing ones all fall in June
    2025 (section 8.1).
  - Both full days (2025-10-08 and 2025-12-14) had 96 of 96 files [VERIFIED].
- **Size distribution** of the 480 present stratified files [VERIFIED]:
  - mean 5.55 MB, median 5.26 MB;
  - 10th–90th percentile 2.96–8.69 MB;
  - across all 671 present files sampled, the smallest was 1.34 MB and the
    largest 13.17 MB.

| Year | Files | Mean size |
| --- | ---: | ---: |
| 2021 (December) | 9 | 5.49 MB |
| 2022 | 104 | 5.00 MB |
| 2023 | 105 | 6.40 MB |
| 2024 | 104 | 6.03 MB |
| 2025 | 100 | 5.45 MB |
| 2026 (to 07-20) | 58 | 4.34 MB |

### 3.3 Estimates [ESTIMATED]

| Quantity | Estimate | Basis |
| --- | --- | --- |
| Files present | ≈160,800–161,200 | 162,512 slots, less the 1,674 verified missing (1.03%) or the sample's 0.83% |
| Download | **0.895 TB** (95%: 0.863–0.929 TB) = 0.81 TiB | Mean size × files present. The verified gap moves this by under 0.3% |
| Protocol and retry overhead | +2–5% | Assumption |
| Elapsed time at a sustained 20 / 50 / 100 / 250 / 500 Mbit/s | 99 / 40 / 20 / 8 / 4 hours | Download ÷ throughput |
| Throughput needed to finish in 1 / 3 / 7 / 14 days | 83 / 28 / 12 / 6 Mbit/s | Same |
| CPU | ≈4–10 core-hours | Assumes 4–5× zip compression [UNVERIFIED], i.e. ≈3.6–4.5 TB of text decompressed and pre-filtered at 150–300 MB/s per core. CPU is not the bottleneck below ≈500 Mbit/s |
| Memory | under 200 MB | One file in memory at a time |

### 3.4 Assumptions and unknowns

- **GDELT server throughput per connection:** [UNVERIFIED]. Only request latency
  was observed: 675 header requests took 55.5 s with four workers.
- **Your sustained bandwidth and any monthly data cap:** [UNVERIFIED]. These are
  yours to confirm.
- **Rate limits on `data.gdeltproject.org`:** none found in the documentation
  read [UNVERIFIED].
- **Decompressed size and per-column sizes:** [UNVERIFIED]. Measuring them needs
  one file body, which is the proposed pilot (section 11).
- **Other gaps:** a gap shorter than about three days elsewhere could escape a
  two-per-week sample. The master file list settles this exactly.
- **Re-download risk:** if the filter changes after acquisition, a full
  re-download is needed. Section 7 therefore captures broadly and narrows later.

---

## 4. Route B — Google BigQuery

### 4.1 What was verified from official documentation

| Item | Finding | Label |
| --- | --- | --- |
| Tables | `gdelt-bq:gdeltv2.gkg` and the daily-partitioned `gdelt-bq:gdeltv2.gkg_partitioned` (filter on `_PARTITIONTIME`) | [VERIFIED] (2016 blog) |
| Size and partition effect | "The GDELT 2.0 GKG table contains 353 million records totaling 3.6TB" (2016). One example query processed 15 GB partitioned against 423 GB unpartitioned | [VERIFIED] (2016 figures) |
| Columns used in GDELT's examples | `DATE` (YYYYMMDDHHMMSS integer), `GKGRECORDID`, `SourceCommonName`, `V2Themes`, `V2Locations`, `V2Organizations`, `V2Persons`, `AllNames`, `TranslationInfo` | [VERIFIED] |
| Column holding page titles (the Extras XML) | Name not confirmed | [UNVERIFIED] |
| Translated rows | Share the table: the examples filter `TranslationInfo like '%srclc:heb%'`. English-only needs a filter, but the query still scans the translated rows | [VERIFIED] |
| Freshness | "all GDELT datasets are available in Google BigQuery, with live datasets updated every 15 minutes" | Statement [VERIFIED]; 2021–2026 completeness and the June 2025 gap [UNVERIFIED] |
| Account | The sandbox needs a Google Account and a Cloud project, "without providing a credit card or creating a billing account" | [VERIFIED] |
| Free allowance | 1 TiB of query processing per month; sandbox storage capped at a lifetime 10 GiB | [VERIFIED] |
| Sandbox limits | "all tables, views, and partitions automatically expire after 60 days"; no DML, streaming or Data Transfer Service | [VERIFIED] |
| Dry run | Free; returns the bytes a query would process; needs authentication | [VERIFIED] |
| Billing rules | At least 10 MiB billed per referenced table; `LIMIT` does not reduce bytes read on non-clustered tables; a per-query "maximum bytes billed" cap exists | [VERIFIED] |
| On-demand price | $6.25 per TiB after the free TiB. The pricing page did not render; the figure is the search engine's summary of `cloud.google.com/bigquery/pricing` | [UNVERIFIED] |
| Getting results out | Console download up to 10 MB; Google Drive up to 1 GB per result; table export only to Cloud Storage, up to 1 GB per file (wildcards for more) | [VERIFIED] |
| Cloud Storage | Its free tier is part of the Google Cloud Free Tier: "A Google Cloud billing account is required to access the Google Cloud Free Tier." | [VERIFIED]. So export to Cloud Storage is **[BLOCKED]** without billing |

### 4.2 Estimate [ESTIMATED, low confidence]

- **Rows in the window:**
  - English: ≈216–231 million. The two B2 samples held 3.9–4.1 KB of compressed
    data per row, which is ≈1,340–1,440 rows per 5.55 MB file, over ≈160,800
    files.
  - Translated: about as many again. In B2's three paired header checks, its
    files were about the size of the English ones.
  - Total: ≈430–460 million rows scanned.
- **Bytes per row:** ≈1.8–8.8 KB for the minimal columns. Those are date, record
  ID, source, URL, `TranslationInfo`, tone, V1 themes, V1 locations, V1
  organizations and the Extras XML.
  - Component assumptions: themes 0.6–1.6 KB, locations 0.4–1.6 KB, Extras
    0.5–5 KB (its page-link list varies widely), everything else 0.3–0.6 KB.
  - Nothing here was measured. The 2016 all-column average was ≈10.2 KB.
- **Total scan:** ≈0.7–3.6 TiB.
  - Sandbox: 1–4 months of free allowance, querying one date slice at a time.
  - With billing: ≈$0–17 at the unverified price.
  - A free dry run, which needs the account, replaces this estimate with an
    exact figure.
- **Getting ≈5–19 GB of results out without billing:** at least 5–19 Drive
  saves of up to 1 GB each. In practice that means one query per month, 56 or
  more, each downloaded by hand. Scripting it would need `google-cloud-bigquery`,
  which is neither installed nor approved.

### 4.3 Assessment

Route B downloads only about 1–2% of what Route A does, but it costs more in
other ways:

- your Google identity on a Cloud project;
- the monthly quota, or billing;
- manual exports;
- the sandbox's 10 GiB and 60-day limits;
- no per-file checksum, so completeness and integrity cannot be checked against
  GDELT's published MD5s;
- the table's 2021–2026 completeness is unverified.

---

## 5. Storage and disk-space analysis

| Item | Size | Label |
| --- | --- | --- |
| Drive C: free | 171 GB of 464 GB | [VERIFIED] |
| Drive D: free | 470 GB of 489 GB | [VERIFIED] |
| English raw archive for the window | ≈0.90 TB. It fits on neither drive, so it cannot be retained and streaming is required | [ESTIMATED] |
| Working space while streaming | one file at a time, under 100 MB | [ESTIMATED] |
| Rows kept | ≈13–32 million (6–14% of English rows) | [ESTIMATED] |
| Filtered output, minimal schema | ≈5–19 GB uncompressed; **≈2–6 GB as gzip CSV** | [ESTIMATED] |
| Filtered output with the optional full theme list | roughly 2–3× the above | [ESTIMATED] |
| Batch manifest | 162,512 rows, ≈40 MB uncompressed | [ESTIMATED] |
| Existing data, for scale | FAR-Trans 59 MB, Kaggle 4.5 MB, generated 626 MB, models 72 MB | [VERIFIED] |
| Output format | Gzip CSV (standard library or pandas). Parquet would need `pyarrow` or `fastparquet`, neither installed nor approved | [VERIFIED] |

**Where the retention estimate comes from:**

- **Sample rate:** in B2's two samples, 6.5% and 7.9% of rows matched six ECON
  themes.
- **Broader list:** the capture list in section 7 is wider. Scaling by GDELT's
  published theme counts relative to `ECON_STOCKMARKET` gives 6–14%.
- **Precision:** to be measured in the pilot.

---

## 6. Minimal filtered schema [PROPOSED]

### 6.1 `gkg_filtered`: one row per kept English GKG record

| Column | From | Note |
| --- | --- | --- |
| `gkg_record_id` | `GKGRECORDID` | Unique key |
| `batch_ts_utc` | `V2.1DATE`, which must equal the file name | Asserted per row. The codebook: "This date will be the same for all rows in a file" [VERIFIED] |
| `available_at_utc` | Later of batch time and file Last-Modified, plus 15 min | The only time features may use (section 8) |
| `source_domain` | `V2SOURCECOMMONNAME` | |
| `document_url` | `V2DOCUMENTIDENTIFIER` | |
| `url_canonical` | Derived | Lower-cased host with scheme, `www.`, query, fragment and trailing slash removed. Used for deduplication |
| `page_title` | `<PAGE_TITLE>` in `V2EXTRASXML`, HTML entities decoded | Present for "all articles processed after noon EST" on 2019-09-22 [VERIFIED]. Stored locally only, never published |
| `title_hash` | SHA-1 of the normalised title | Deduplication |
| `page_pub_ts_utc` | `<PAGE_PRECISEPUBTIMESTAMP>` | Nullable; diagnostic only; **never used for availability** |
| `tone`, `positive`, `negative`, `polarity`, `activity_density`, `self_group_density`, `word_count` | `V1.5TONE` | The codebook's six emotional dimensions plus WordCount [VERIFIED]. GDELT's own ingestion-time tone |
| `matched_themes` | `V1THEMES` ∩ the candidate list (section 7) | Exact codes only |
| `grp_equity`, `grp_rates`, `grp_gold` | Derived | 0/1 per group |
| `country_codes` | Distinct country codes from `V1LOCATIONS` | 2-character FIPS 10-4 [VERIFIED codebook] |
| `us_location` | Derived | 1 if any location is country `US` or type 2 (US state) or 3 (US city) [VERIFIED codebook] |
| `org_hits`, `title_hits` | Derived | Which keywords matched |
| `filter_version` | Constant | e.g. `gdelt_filter_v1` |

**Dropped:** GCAM, counts, persons, images, video embeds, quotations, amounts,
all-names, enhanced dates, and the full theme, location and organization strings.
**Optional (your decision):** keep the full `V1THEMES` string. It lets later
phases re-cut kept rows without re-downloading, at roughly 2–3× the storage.

### 6.2 `batch_manifest`: one row per expected 15-minute slot, including missing ones

| Field group | Fields |
| --- | --- |
| File identity | `batch_ts_utc`, `file_url`, `http_last_modified_utc`, `bytes` |
| Status | `status`: `ok`, `missing`, `error`, `md5_mismatch` or `late_or_rewritten` |
| Integrity | `md5_expected` (from the master list), `md5_actual` |
| Row counts | `rows_total`, `rows_malformed` (not 27 columns), `rows_translated` (must be 0), `rows_kept` |
| Group counts | `rows_equity`, `rows_rates`, `rows_gold`, `rows_us` |
| Processing | `processed_at_utc`, `filter_version` |

**Why the manifest matters:**

- It supplies the denominators (all English rows per slot) that turn counts into
  shares, which absorbs changes in GDELT's overall volume. Mean file size ranges
  from 4.34 to 6.40 MB across years.
- It makes coverage explicit.

---

## 7. Proposed market-theme filters [PROPOSED; to be frozen before any data is compared with returns]

**Matching rules:**

- **Themes:** split `V1THEMES` on `;` and compare exact codes. Never use
  substring matching. A substring test would pull in, for example,
  `TAX_TERROR_GROUP_GOLDEN_DAWN`, `CRIME_STEAL_LIVESTOCK` and
  `TAX_DISEASE_GOLDENHAR_SYNDROME` [VERIFIED as lookup entries].
- **Keywords:** case-insensitive, whole-word matches in the title or in
  `V1ORGANIZATIONS`.

**Capture rule:** keep a row if it matches any group's themes or keywords. The
groups are stored as flags, so B3 can tighten precision later without
re-downloading.

The bracketed counts below come from GDELT's theme lookup
(`LOOKUP-GKGTHEMES.TXT`, last modified 2021-11-25) [VERIFIED as published]. They
count documents across all of GKG history and both language streams, so they
only show relative frequency.

| Group (instruments) | Core themes [lookup count] | Broad themes: kept but flagged lower-precision | Keywords |
| --- | --- | --- | --- |
| **Equity** (`^IXIC`, `^NDX`, `QQQ`) | `ECON_STOCKMARKET` [46,735,585], `ECON_IPO` [2,146,510], `ECON_EARNINGSREPORT` [717,185], `ECON_BUBBLE` [232,717] | none | nasdaq, nasdaq-100, wall street, s&p 500, dow jones, stock market, invesco qqq |
| **Rates and bonds** (`AGG`) | `ECON_INTEREST_RATES` [10,502,251], `ECON_CENTRALBANK` [10,666,137], `EPU_CATS_MONETARY_POLICY` [14,925,382], `EPU_POLICY_INTEREST_RATES` [5,975,013], `EPU_POLICY_INTEREST_RATE` [3,213,356], `EPU_POLICY_MONETARY_POLICY` [1,984,501], `WB_444_MONETARY_POLICY` [2,616,888], `WB_1125_INTEREST_RATE_POLICY` [130,404], `ECON_SOVEREIGN_DEBT` [1,317,827], `WB_335_GOVERNMENT_BOND_MARKETS` [12,977], `WB_333_NON_GOVERNMENT_BOND_MARKETS` [24,734] | `ECON_INFLATION` [10,415,945], `ECON_DEBT` [20,807,975], `WB_1045_TREASURY` [7,477,731], `ACT_YIELD` [1,245,595] | federal reserve, fomc, treasury yield(s), bond(s), rate hike, rate cut, interest rate(s) |
| **Gold** (`GLD`) | `ECON_GOLDPRICE` [1,078,913] | `WB_2936_GOLD` [29,824,307], probably mining-heavy | gold price(s), spot gold, gold futures, bullion, spdr gold |

**Notes on the theme lists:**

- `ECON_BONDS` and `ECON_GOLD` do not exist in the lookup [VERIFIED].
- The bare word "fed" is excluded as too ambiguous. "federal reserve" and "fomc"
  cover it.
- The lists were checked against the lookup on 2026-10-12. B3 may still prune
  them before freezing, never after looking at returns.

**US relevance:**

- **Equity and rates:** these series should be US-focused. A row counts as US if
  `us_location` is set or it matches a US-market keyword (nasdaq, wall street,
  federal reserve, fomc, s&p 500, dow jones).
- **Kept as a flag only:** US relevance never removes a row, so B3 can measure
  its effect.
- **Gold:** gold is a global market, so there is no US requirement, but the flag
  is kept.

**Excluded at capture, and counted in the manifest:**

- rows without 27 columns;
- rows whose `TRANSLATIONINFO` is not blank. The codebook says it "will be blank
  for documents originally in English" [VERIFIED], so none are expected in the
  English stream.
- duplicate `GKGRECORDID`s.

**Precision of every list:** [UNVERIFIED]. The pilot should report kept rows per
group per file, and you can read a sample of about 50 titles per group.

---

## 8. Timestamp and leakage safeguards

1. **Availability time** [PROPOSED]. Take the later of the nominal batch time
   and the file's Last-Modified time, and add 15 minutes.
   - **UTC:** batch times are UTC. The codebook states no time zone [VERIFIED
     absence]. But `lastupdate.txt` showed batch `20261012171500` when the local
     UTC clock read 17:12:34 [VERIFIED].
   - **Files are written before their label:** Last-Modified fell 7.9–11.8
     minutes *before* the nominal batch time in 14 of 14 files sampled across
     2021–2026 [VERIFIED].
   - **Including around the outage:** it was 2–13 minutes before the label in all
     53 present files checked at the outage's edges on 2025-06-12, 2025-06-14
     and 2025-07-02 [VERIFIED].
   - **So:** a file never holds anything later than its label, and historical
     files show no sign of being rewritten. The 15 minutes then model a live
     poller's delay.
   - **Late files:** a file whose Last-Modified is more than 15 minutes after its
     label is flagged `late_or_rewritten`. Its availability moves to
     Last-Modified + 15 minutes.
2. **Never use a page's own timestamp for availability** [VERIFIED reason, from
   B2]. In one batch:
   - page time trailed the batch by a median of 149 minutes (10th–90th
     percentile 35–387);
   - 2.9% of rows were more than 24 hours old;
   - 28 rows were dated after the batch that captured them.
3. **Trading-day assignment** [PROPOSED].
   - **Cutoff:** 16:00 America/New_York on each stored trading date: 20:00 UTC in
     summer, 21:00 UTC in winter (`zoneinfo` and `tzdata` are installed
     [VERIFIED]).
   - **Rule:** a row belongs to trading day *t* when the previous trading day's
     cutoff < `available_at_utc` ≤ *t*'s cutoff. Weekend and holiday news rolls
     into the next trading day.
   - **Calendar:** the stored `market_data` dates are the calendar.
4. **Forecast alignment** [PROPOSED].
   - **Allowed:** the return dated *d* may use only news assigned to trading days
     before *d*.
   - **Not allowed:** same-day news is contemporaneous with the return and must
     not be used to forecast it.
5. **Early closes: [BLOCKED].** Half-day sessions need an earlier cutoff, but no
   list of them is available:
   - `market_data` has no session times;
   - no calendar library is installed (`pandas_market_calendars` and
     `exchange_calendars` are absent [VERIFIED]), and none is approved.

   There are two ways forward:
   - **(a) Official list:** you approve a small list cited from the exchange's
     official schedule.
   - **(b) Uniform 13:00 ET cutoff:** use 13:00 ET every day. It cannot leak on
     any session closing at or after 13:00, but it delays three hours of news
     every day.
6. **Missing data** [PROPOSED].
   - Missing batches stay missing in the manifest and are never zero-filled.
   - Each day's features carry a coverage fraction.
   - Below a threshold, they are null with an unavailable reason (CLAUDE.md §12).
     B3 sets the threshold; none is invented here.
7. **Duplicates** [PROPOSED].
   - **Same URL:** keep the earliest `available_at_utc` per `url_canonical`. A
     later row with the same URL but a changed title is kept as a new item at its
     own time. The earlier row is never edited.
   - **Same title:** title-hash duplicates across sources are grouped, not
     dropped. B3 fixes the policy.
   - **Cross-batch rates:** still [UNVERIFIED].
8. **No retroactive sentiment** [PROPOSED; B2 §7.1 rule 9].
   - Acquisition stores only GDELT's ingestion-time tone.
   - Any later classifier is a B3 decision and must not have been trained on
     test-period data.
   - No LLM scores historical headlines.
9. **Normalisation** [PROPOSED]. Shares use the manifest's denominators. Any
   scaling is fitted on training folds only, with trailing windows.
10. **Pre-registration** [PROPOSED].
    - Filter v1 is frozen and committed before acquisition.
    - It is never tuned against test-period returns.
    - Every row records its `filter_version`.
11. **The walk-forward is untouched** [PROPOSED]. The 504/5/63 windows and the
    embargo do not change. News features join existing rows only.
12. **Taxonomy drift.** The theme lookup was last modified 2021-11-25, before the
    window [VERIFIED]. The tagger itself could still change, so the coverage
    report should track monthly theme shares [PROPOSED].

### 8.1 The June–July 2025 GDELT outage [VERIFIED by header-only requests]

| Gap | First missing batch (UTC) | Last missing batch (UTC) | Batches |
| ---: | --- | --- | ---: |
| 1 | 2025-06-12 18:15 | 2025-06-12 20:15 | 9 |
| 2 | 2025-06-14 18:00 | 2025-07-02 02:00 | 1,665 |
| | | **Total** (1.03% of the window) | **1,674** |

**How this was established:**

- **Scan:** an hourly scan of 2025-06-01 → 2025-07-10 (960 slots), then
  15-minute checks at each edge.
- **Other streams:** at 2025-06-20 12:00 the events export, mentions, English
  GKG and translated GKG files are **all** absent. The translated file at
  2025-06-13 12:00 exists. No GDELT file stream fills the gap. Whether BigQuery
  covers it is [UNVERIFIED].
- **Possible backlog:** several files on 2025-07-02 after the gap are unusually
  large, up to 16.71 MB at 06:00 UTC against a sample 90th percentile of 8.69 MB.
  That fits backlog processing but does not prove it. Any backlog is used at its
  own batch time and never back-dated.
- **No other gap was found** by the sample. The master file list would confirm
  this exactly.

**Effect on test window 6** (2025-04-17 → 2025-07-18). The rule is from item 3
above. The stored trading days show that 2025-06-19 was not a trading day.

| Forecast origin (close) | News coverage of its interval | Target return |
| --- | --- | --- |
| 2025-06-12 | 89 of 96 batches (7 missing, US afternoon) | 2025-06-13 |
| 2025-06-13 | 94 of 96 | 2025-06-16 |
| 2025-06-16 | 88 of 288 (31%; weekend included) | 2025-06-17 |
| 2025-06-17, 06-18, 06-20, 06-23, 06-24, 06-25, 06-26, 06-27, 06-30, 07-01 | **0%** | 2025-06-18, 06-20, 06-23, 06-24, 06-25, 06-26, 06-27, 06-30, 07-01, 07-02 |
| 2025-07-02 | 71 of 96 (74%) | 2025-07-03 |

**What this means for the evaluation:**

- **Scale:** 10 of 630 test returns per instrument (1.6%) have no news for their
  forecast interval.
- **Trailing features:** any trailing-window news feature stays degraded for its
  window length after 2025-07-02.
- **Proposal [PROPOSED]:** null with an unavailable reason, never neutral. Report
  the news model and the baseline on the same rows, both with and without the
  affected dates.
- **Feasibility:** this does not block it.

---

## 9. Git and data-retention plan [PROPOSED unless marked]

**Raw files:**

- The zips are never written to disk.
- If a retry cache is ever needed, it goes under `datasets/raw/gdelt/`, which
  `.gitignore:33` (`datasets/raw/*`) already ignores [VERIFIED], and is deleted
  after processing.

**Filtered data: two options.**

| | Recommended: `datasets/raw/gdelt/english_gkg_v1/` | Alternative: `datasets/processed/gdelt/v1/` |
| --- | --- | --- |
| Fit with CLAUDE.md | Matches its rule that `datasets/raw/` is "the single canonical location for original/downloaded data" | A new top-level convention |
| Fit with B2 | B2 suggested this location | — |
| Git | Already ignored, so no `.gitignore` change. A README or manifest inside is ignored too [VERIFIED with `git check-ignore`], the same as FAR-Trans's README today | **Not ignored today** [VERIFIED]. Needs, before any write: `datasets/processed/**/*.csv`, `datasets/processed/**/*.csv.gz`, `datasets/processed/**/*.parquet`. This mirrors `.gitignore:38` (`datasets/generated/**/*.csv`), so a README could stay tracked beside the data |
| Immutability | Covered by the existing rule "Raw datasets under `datasets/raw/` are immutable" | Would need stating |

**What stays tracked:**

- the filter specification (e.g. `config/gdelt_filter_v1.yaml`);
- the acquisition code (`backend/wealthpilot/data/`);
- the acquisition phase's report, carrying the summary manifest: rows per month,
  coverage, the gap list, and SHA-256 of every output file;
- the ADR, written after your approval.

**Rules:**

- **Data:** never commit it.
- **Titles:** never publish them; they stay local (B2 §8).
- **Database:** no PostgreSQL load. Whether B3 stores features in the hosted
  database is a later decision.
- **Citation:** cite the GDELT Project with a link, as its terms require [VERIFIED
  in B2].

**Retention:**

- Keep the extract for the life of the research track. Deleting it is your call.
- **Rebuilding:** it can be rebuilt from GDELT's public archive with the same
  filter version, as long as GDELT keeps the files online [UNVERIFIED long-term].
- **New filter versions:** a new version goes in a new directory and never
  overwrites the old one.

---

## 10. Comparison

| Criterion | Route A: stream raw English files | Route B: BigQuery |
| --- | --- | --- |
| Account | None [VERIFIED] | Google Account and a Cloud project [VERIFIED] |
| Billing | None | None in the sandbox. Needed beyond 1 TiB a month, and for Cloud Storage export [VERIFIED] |
| Money | $0 | $0 within quota; ≈$0–17 with billing [ESTIMATED; price UNVERIFIED] |
| Data downloaded | ≈0.90 TB [ESTIMATED] | ≈5–19 GB of results [ESTIMATED] |
| Elapsed time | ≈20 h at 100 Mbit/s; ≈4 days at 20 Mbit/s [ESTIMATED] | Queries take minutes. Quota means 1–4 months in the sandbox; manual export takes hours [ESTIMATED] |
| Local disk kept | ≈2–6 GB | Same |
| New dependency | None [VERIFIED] | None if console-only. `google-cloud-bigquery` if scripted (not approved) |
| English only | By stream choice: translated files are never fetched, and `TRANSLATIONINFO` is asserted blank | By a filter; translated rows are still scanned and billed |
| Integrity | MD5 per file from the master list; Last-Modified recorded | Query metadata only; no per-file checksum |
| Completeness check | Exact, per file | Indirect (rows per `DATE`) |
| Availability evidence | Batch time plus file Last-Modified | `DATE` only |
| Reproducibility | Re-runnable from the public archive with a frozen filter | Live table can change; allowance resets monthly |
| Automation | Scripted and resumable | Manual console steps unless a new library is approved |
| Main risks | Bandwidth or data cap; unknown server throughput; full re-download if the filter changes | Account; quota; 10 GiB and 60-day sandbox limits; title column unverified; 2021–2026 completeness unverified |
| June–July 2025 outage | Present [VERIFIED] | Presumably present [UNVERIFIED] |

---

## 11. Recommendation and remaining decisions

**Recommendation [PROPOSED]: Route A, conditionally.**

- **Why A:**
  - It needs no account, no billing and no new dependency.
  - It is scripted and resumable.
  - Per-file MD5 and Last-Modified give the strongest evidence of integrity and
    availability.
  - Its only real cost is ≈0.9 TB of download.
- **When B instead:** Route B is the fallback if your connection cannot move
  ≈0.9 TB, because of a data cap or a sustained speed below roughly 10 Mbit/s,
  *and* you are willing to create a Google Cloud project. Its exact scan should
  then be fixed with a free dry run before any real query.

**Your decisions.** None is implied by this report.

1. **Route:** A, B, or neither.
2. **Connection:** your sustained download speed and any monthly data cap. Route
   A needs ≈0.90 TB plus a few percent for retries.
3. **Pilot**, approved separately:
   - **P1:** one 15-minute file (≈5.5 MB) processed end to end. It measures
     throughput, decompressed size, per-column sizes, filter yield and title
     precision.
   - **P2:** one full day (96 files, ≈0.5 GB), only if P1 is inconclusive.
4. **Master file list:** one download of `masterfilelist.txt` (128 MB). It gives
   exact sizes, MD5s and the full missing-file list, replacing this report's
   sample.
5. **Filter v1** (section 7): approve or amend it before acquisition. It is
   frozen afterwards.
6. **Storage:** `datasets/raw/gdelt/english_gkg_v1/` (recommended) or
   `datasets/processed/gdelt/v1/` with new `.gitignore` rules. Also, whether to
   keep the full `V1THEMES` string.
7. **Window end:**
   - minimum: 2026-07-20 20:00 UTC;
   - or 2026-09-10 close, which adds the 37-return holdout for ≈+3% download.
8. **Freeze the market snapshot** (2022-01-03 → 2026-09-11) for the research
   track. That means not re-running market training during it (section 2.3).
9. **Early closes:** an official list from a source you approve, or a uniform
   13:00 ET cutoff.
10. **The June–July 2025 outage:** accept the proposed handling (null, with
    results reported with and without the affected rows).
11. **After your approval:** B2's proposed ADR-043, which records:
    - the source;
    - the route;
    - the availability rule;
    - the storage location;
    - the citation basis.

**Still unverified:**

- GDELT server throughput;
- cross-batch duplicate rates;
- filter precision;
- BigQuery's title column, completeness and exact scan size;
- whether any gap besides June–July 2025 exists (the master list settles this).

---

## 12. Official sources and access dates

All accessed 2026-10-12. "Updated" is the page's own last-updated date where it
shows one.

| Source | URL | Used for |
| --- | --- | --- |
| GDELT GKG 2.1 codebook | <http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf> | `V2.1DATE`, `GKGRECORDID`, `V1.5TONE`, `TRANSLATIONINFO`, location fields (text extracted earlier in B2/B2-F) |
| GDELT 2.0 raw files | <https://data.gdeltproject.org/gdeltv2/> | 1,736 header-only requests in this phase: sizes, availability, Last-Modified |
| GDELT master file list | <http://data.gdeltproject.org/gdeltv2/masterfilelist.txt> | Size and Last-Modified only (header request) |
| GDELT theme lookup | <http://data.gdeltproject.org/api/v2/guides/LOOKUP-GKGTHEMES.TXT> | Theme names and counts (59,315 lines; streamed, not stored) |
| GDELT category list | <http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_CategoryList.xlsx> | Existence and size (header request) |
| GDELT blog, "New GKG 2.0 Article Metadata Fields" (2016-04-22) | <https://blog.gdeltproject.org/?p=3176> | `PAGE_PRECISEPUBTIMESTAMP` (≈33% of articles, converted to UTC) |
| GDELT blog, "GKG 2.0 Now Includes Page Titles" (2019-09-22) | <https://blog.gdeltproject.org/?p=7791> | `<PAGE_TITLE>` in the Extras XML since 2019-09-22 |
| GDELT blog, "Announcing Partitioned GDELT BigQuery Tables" (2016-08-15) | <https://blog.gdeltproject.org/announcing-partitioned-gdelt-bigquery-tables/> | Table names, `_PARTITIONTIME`, 353M records / 3.6 TB |
| GDELT blog, "Google BigQuery + GKG 2.0: Sample Queries" (2015-03-04) | <https://blog.gdeltproject.org/google-bigquery-gkg-2-0-sample-queries/> | Column names; translated rows in the same table |
| GDELT data page | <https://www.gdeltproject.org/data.html> | BigQuery availability statement |
| GDELT terms of use | <https://www.gdeltproject.org/about.html> | Citation requirement (verified in B2) |
| BigQuery sandbox (updated 2026-10-09) | <https://docs.cloud.google.com/bigquery/docs/sandbox> | No billing; 1 TiB per month; 10 GiB; 60-day expiry; unsupported features |
| Estimate and control costs | <https://docs.cloud.google.com/bigquery/docs/estimate-costs> | Free dry run; 10 MiB minimum; free TiB per month |
| Cost best practices | <https://docs.cloud.google.com/bigquery/docs/best-practices-costs> | `LIMIT` behaviour; maximum bytes billed |
| Export table data | <https://docs.cloud.google.com/bigquery/docs/exporting-data> | Cloud Storage only; 1 GB per file; formats |
| Writing query results (updated 2026-10-09) | <https://docs.cloud.google.com/bigquery/docs/writing-results> | 10 MB local download; 1 GB to Drive |
| Google Cloud free features (updated 2026-10-09) | <https://docs.cloud.google.com/free/docs/free-cloud-features> | Free tier and Cloud Storage need a billing account |
| BigQuery pricing | <https://cloud.google.com/bigquery/pricing> | Did not render. The $6.25/TiB figure is from the search engine's summary [UNVERIFIED] |

**Repository sources** (read-only):

- `training/market/common.py`, `train.py` and `preprocessing.py`;
- `models/metrics.json`;
- the `market_data` table;
- `.gitignore`;
- `backend/pyproject.toml`.

---

## Verification of this phase

**Files created:** this report.

**Files modified:**

- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`: corrected B2 dates and a short
  B2-F findings note;
- `reports/phaseB2_historical_news_source_evaluation.md`: a superseded-by note
  only;
- `docs/MEMORY.md`: the track status.

**Network activity in this phase:**

- **Raw-file header requests:** 1,736, all to `data.gdeltproject.org`.

  | Purpose | Requests |
  | --- | ---: |
  | Stratified sample and two full days | 675 |
  | Last-Modified check | 16 |
  | Hourly gap scan | 960 |
  | Gap edges | 80 |
  | Other streams | 5 |

- **Other GDELT header requests:** the master file list, category list and theme
  lookup.
- **One documentation file streamed:** the theme lookup, 2,044,449 bytes,
  nothing stored.
- **Documentation pages.**
- **No GKG, events or mentions archive body was downloaded.**

**Database:** read-only `SELECT`s on `market_data`, for the window mapping and
trading days.

**Not done:**

- No account was created.
- No billing was configured.
- No BigQuery query or dry run was made.
- No provider was contacted and no licence was accepted.
- Nothing was installed.
- The market instrument universe did not change.
- No sentiment or feature work was done.
- B3 and blockchain work have not started.

**Unchanged:**

- application code, APIs, schema and migrations;
- models and training scripts;
- datasets;
- dependencies and lockfiles.

**Tests:** none run; no code changed.
