# Research Enhancement Track — Phase B2-G: GDELT Pilot and Archive Completeness Audit

**Type:** a pilot and audit for Route A (direct streaming, local filtering), which
is conditionally approved. The two authorised downloads were made; nothing else
was downloaded.

- **Not approved:** full acquisition, B3 sentiment work.
- **Deferred:** blockchain work.
- **Unchanged:** no dependency, `.gitignore`, application code, schema, model,
  training script, market data or instrument universe changed.

**Date:** 2026-10-12 (UTC). All web sources were accessed on this date.
**Builds on:**

- `reports/phaseB2F_gdelt_acquisition_feasibility.md` (B2-F; its corrected
  research dates are used throughout);
- `reports/phaseB2_historical_news_source_evaluation.md` (B2);
- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`.

`docs/DECISIONS.md` has no GDELT ADR, and none was created.

**Labels:**

- **[VERIFIED]**: confirmed from official documentation, the master file list,
  the repository, a read-only database query, or a header-only check.
- **[MEASURED]**: observed directly in this pilot. Most values are a single
  observation.
- **[ESTIMATED]**: computed from verified or measured inputs plus the stated
  assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or a source not yet available.

---

## 1. Executive summary

- **Both authorised downloads succeeded and were verified** [VERIFIED].
  - The sample file's MD5 matches the master list's own entry and the server's
    ETag.
  - Its CRC-32 passed before extraction.
- **The sample file matches the codebook exactly** [VERIFIED for this file].
  - 1,480 rows, all with 27 tab-separated columns.
  - No parsing errors and no translated rows.
  - A title on every row.
  - One batch timestamp, shared by the file name, `V2.1DATE` and every record ID.
- **Incremental parsing is feasible** [MEASURED].
  - The file streams from an in-memory zip in 0.108 s: decompress, parse,
    validate and decide capture.
  - Python allocations peak at 5 MB, against 56 MB when the whole member is
    decompressed first.
- **The master list changes the known gaps** [VERIFIED from the list].
  - The window (2021-12-01 00:00 → 2026-07-20 19:45 UTC) has **1,854 absent
    slots of 162,512 (1.14%)**, not the 1,674 known from B2-F.
  - The June 2025 outages are confirmed exactly.
  - The list adds a **March 2023 disruption** (147 slots, including a 32-hour
    gap) and **33 isolated single slots**.
  - It shows an **83-slot run of near-empty files on 2022-11-10/11**: present,
    but under 160 KB each.
  - Every absence affects the events, mentions and GKG streams together.
- **Exact download size: 860,483,377,717 bytes (0.860 TB)** for the 160,658
  listed files [VERIFIED]. B2-F had estimated ≈0.90 TB.
- **Effect on forecast days** [VERIFIED from the list and stored trading days]:
  - **Test period:** 12 of 630 forecast days have under 90% news coverage, all
    from the June–July 2025 outage, which matches B2-F exactly.
  - **Training period:** 3 days have under 50% coverage (2022-11-11, 2023-03-22,
    2023-03-23).
- **Route A remains practical** [ESTIMATED]. Measured on this connection:
  41–44 Mbit/s sustained on one connection, with ≈1.1–1.4 s latency per
  request.
  - **Time:** about 2 days with a few parallel connections. Parallel scaling is
    untested, so up to about 4–4.6 days fetching one file at a time.
  - **CPU:** ≈4–8 core-hours.
  - **Kept on disk:** ≈1.7–4.3 GB.
  - **New dependencies:** none.
- **Filter feasibility** [VERIFIED fields; precision only qualitative]:
  - Every field the filters need exists.
  - `ECON_GOLDPRICE` looks precise but rare.
  - `WB_2936_GOLD` and the four broad rates themes looked unrelated to markets
    in every title read.
  - About half of the `ECON_STOCKMARKET` titles read were not about markets.
  - 17.8% of rows repeat a title already in the same batch.
  - The filter stays **[PROPOSED]**.
- **Cleanup:** no raw data remains on disk [VERIFIED].

---

## 2. Exact downloaded URLs and sizes

**Recorded before downloading.** At 2026-10-12 18:27:42 UTC, header-only requests
fixed each target's expected size and timestamp. Three new, empty folders were
created in the session scratch directory (outside the repository):
`b2g_tmp_gkg`, `b2g_tmp_extract` and `b2g_tmp_master`.

**How the sample was chosen.** The rule was fixed in advance:

- a file the B2-F stratified sample had already seen present;
- dated within the test returns' forecast-origin span (2024-01-12 → 2026-07-20);
- on a Tuesday to Thursday that is a stored trading day with trading days either
  side;
- between 14:30 and 19:45 UTC, which is inside the US session in both EST and EDT;
- closest in size to the B2-F mean of 5,551,767 bytes.

27 files qualified.

**Before any download the rule was tightened.** Its first version allowed any
weekday. It picked `20251128154500`, the day after Thanksgiving, an exchange
half-day. Its next candidates were the 3 July 2026 holiday, Columbus Day and New
Year's Eve. The neighbouring-trading-day condition was added at that point.

| Item | Archive sample | Master file list |
| --- | --- | --- |
| URL | <https://data.gdeltproject.org/gdeltv2/20251223144500.gkg.csv.zip> | <https://data.gdeltproject.org/gdeltv2/masterfilelist.txt> |
| Batch | Tue 2025-12-23 14:45 UTC (09:45 EST) | — |
| Expected size (header) | 6,173,549 B | 128,483,714 B (B2-F saw 128,482,752; the list grows every 15 minutes) |
| Server Last-Modified | Tue, 23 Dec 2025 14:36:05 GMT | Mon, 12 Oct 2026 18:20:56 GMT |
| ETag | `3aeaea3ff1a8d92ee9dd27fab54190e6` | `9a41a818e1d6a108b1d928d96c6d0355` |
| Download started | 18:29:08 UTC | 18:28:43 UTC (first, so its entry could verify the sample) |
| Bytes received | 6,173,549, complete | 128,483,714, complete |
| MD5 | `3aeaea3ff1a8d92ee9dd27fab54190e6`: equals the ETag **and** the master list's entry `6173549 3aeaea3ff1a8d92ee9dd27fab54190e6 …/20251223144500.gkg.csv.zip` | `9a41a818e1d6a108b1d928d96c6d0355`, equal to the ETag |
| SHA-256 | `cbb7bc5e41783c6d268fe2f9a1fa62332d012fc5bb536681312f7e70e76d438c` | `7e5d2c2efb7298af6eafb0898739ba880b875b586255e994a81ff1a975cfebf0`. This pins the list snapshot audited here |

**Guards in the download script:**

- no redirects followed;
- the sample was refused if over 10 MB, the list if over 140 MB;
- existing files were never overwritten;
- it stops on any mismatch and never substitutes another file.

The translated stream and its master list were not downloaded.

---

## 3. Pilot validation and schema findings

### 3.1 Integrity and extraction [VERIFIED]

| Check | Result |
| --- | --- |
| Valid zip | Yes; one member, not encrypted, created on Unix (`create_system` 3) |
| Member name | `20251223144500.gkg.csv`. Exactly the expected name, with no path components; extracted by streaming to a fixed path, not `extractall` |
| CRC-32 (`testzip`, before extraction) | Passed (`64fcc8d8`), 0.074 s |
| Sizes | 6,173,355 B compressed → **19,089,331 B** uncompressed (deflate, **3.09×**). Extracted size equals the declared size |
| Member timestamp | 2025-12-23 14:36:02, matching the server's Last-Modified (14:36:05 GMT) |

### 3.2 Schema against the GKG 2.1 codebook [VERIFIED for this file]

| Aspect | Finding |
| --- | --- |
| Rows and columns | 1,480 rows = 1,480 physical lines; every row has 27 tab-separated columns in the codebook order. LF line endings, trailing newline, no CR, no embedded newlines |
| Parsing errors | 0 malformed rows, 0 UTF-8 decode errors |
| `GKGRECORDID` | All match `20251223144500-<n>`; no duplicates; none carries the translated-record marker |
| `V2.1DATE` | `20251223144500` on every row |
| `V2SOURCECOLLECTIONIDENTIFIER` | 1 (web) on every row |
| `V2SOURCECOMMONNAME` / `V2DOCUMENTIDENTIFIER` | Present on every row; 284 distinct domains; 0 exact duplicate URLs, 4 after canonicalisation |
| Language indicator | `V2.1TRANSLATIONINFO` blank on all 1,480 rows. The codebook says it "will be blank for documents originally in English". There is no separate language code for English documents |
| Title | `<PAGE_TITLE>` in `V2EXTRASXML` on 1,480 rows (one empty). Median 66 characters, 90th percentile 94. 117 contain HTML entities, decoded with `html.unescape`. None contains replacement characters |
| Other `V2EXTRASXML` tags | `PAGE_LINKS` 861, `PAGE_PRECISEPUBTIMESTAMP` 733, `PAGE_AUTHORS` 617, `PAGE_ALTURL_AMP` 244, `PAGE_ALTURL_MOBILE` 2 |
| Themes | `V1THEMES` non-empty on 1,321 rows (89%); median 20 per row. Every `V2ENHANCEDTHEMES` entry (65,800) is `THEME,offset` |
| V1 vs V2 themes | The sets differ on 1,219 rows: V1 also lists parent category codes (`TAX_FNCACT`, `EPU_POLICY`, `TAX_ETHNICITY`, …) that V2 omits. **For all 21 candidate themes the two columns agree on every row.** V2 adds per-article mention counts |
| Locations | All 4,340 `V1LOCATIONS` entries have the 7 `#`-separated fields; all 12,028 `V2ENHANCEDLOCATIONS` entries have 9. Types 1–5 present: country 1,619, US state 634, US city 656, world city 1,330, world state 101 |
| Organizations | 3,758 `V1ORGANIZATIONS` entries, all lower-case |
| Tone | `V1.5TONE` has 7 numeric values on every row; tone ranges −17.2 to +15.4, median −0.22 |
| Row size | 12,898 B per row on average. `V2GCAM` alone is 69.5% of the bytes; the proposed minimal schema drops it |

### 3.3 Incremental parsing [MEASURED]

The zip bytes were held in memory, as Route A would hold a downloaded file. The
member was then streamed line by line through a 1 MiB buffer. Each row was
decoded, split, checked for 27 columns, checked that the date equals the file
name, checked for blank `TRANSLATIONINFO`, and run through the proposed capture
decision.

| Mode | Time (2 timing runs each) | Python allocations (tracemalloc) | Process peak working set |
| --- | --- | --- | --- |
| Streaming from the zip member | 0.108 s (≈177 MB/s of decompressed text) | **5.1 MB** | 34.3–35.3 MB (baseline 28.4–28.9 MB) |
| Whole member decompressed first | 0.107–0.108 s | 56.1 MB | 72.7–72.8 MB |

**Result:** both modes take the same time, but streaming needs about a tenth of
the memory. Extracting to disk is unnecessary. Route A can parse each file
straight from the downloaded bytes and write nothing raw to disk.

### 3.4 Timestamps [VERIFIED for this file]

**Batch timestamp:** the file name, `V2.1DATE` and the record-ID prefix are the
same `YYYYMMDDHHMMSS` value. B2-F showed this value is UTC.

**Page timestamp:** `<PAGE_PRECISEPUBTIMESTAMP>` is also `YYYYMMDDHHMMSS`. GDELT
says it is converted to UTC.

- Present on 733 rows (49.5%).
- The batch trailed it by a median of 135 minutes (10th–90th percentile:
  33–525).
- 2.3% of these pages were over 24 hours old.
- **10 rows claim a publication time after the batch that captured them** (all
  10 more than 15 minutes after). Page timestamps therefore cannot define
  availability.

**When the file was written:** 14:36:05 by the server's Last-Modified, and
14:36:02 by the zip member time. Both are **8 minutes 55 seconds before the
nominal 14:45:00**. The master list shows the same pattern: modified at 18:20:56,
it already listed the `20261012183000` batch, about 9 minutes before that batch's
nominal time.

---

## 4. Measured throughput, processing and storage results

| Measure | Value | Label |
| --- | --- | --- |
| Master list download | 128,483,714 B in 24.574 s = **41.8 Mbit/s overall**. After its first 1 MiB chunk (1.628 s), the rest arrived at 44.4 Mbit/s | [MEASURED], once |
| Sample download | 6,173,549 B in 2.271 s = 21.8 Mbit/s overall. The first 1 MiB chunk arrived at 1.271 s; the rest at 41.0 Mbit/s | [MEASURED], once |
| Per-request latency | ≈1.1–1.4 s: time to the first 1 MiB chunk, less that chunk's transfer time | [ESTIMATED] from the above |
| Sample sizes | 6,173,549 B compressed; 19,089,331 B decompressed (3.09×) | [MEASURED] |
| CRC check / extraction | 0.074 s / 0.082 s | [MEASURED] |
| Parse and capture decision | 0.108 s per file (≈177 MB/s of decompressed text); 154 of 1,480 rows kept (10.4%) | [MEASURED] |
| Peak memory | Streaming: 5.1 MB Python allocations, ≈35 MB process. Full load: 56 MB / 73 MB | [MEASURED] |
| Minimal schema | 154 kept rows serialised in the B2-F §6.1 shape = 62,358 B (405 B per row); gzip 21,502 B (2.9×). Built in memory only | [MEASURED] |
| Temporary disk use, peak | 153,746,594 B: zip 6,173,549 + CSV 19,089,331 + list 128,483,714 | [MEASURED] |

Throughput comes from two transfers, made at about 18:30 UTC from this machine.
It reflects both GDELT's server and this connection at that moment; neither side
can be singled out. **Parallel transfers were not tested:** no prolonged
benchmark or extra downloads were authorised.

---

## 5. Master-list coverage and completeness audit

### 5.1 The file itself [VERIFIED]

| Check | Result |
| --- | --- |
| Lines | 1,203,294 |
| Valid entries (`size md5 url`) | 1,203,233: export 401,076, mentions 401,076, GKG 401,081 |
| Malformed lines | 61, each the bare string `http://data.gdeltproject.org/gdeltv2/` with no size, checksum or file name. **6 fall inside the window** (lines 834,163–834,168, between the 2023-03-21 23:00 and 23:15 entries, at the start of the March 2023 disruption). They cannot be mapped to any slot |
| Duplicates | 0 duplicate URLs; 0 GKG timestamps listed twice |
| Grid | 0 GKG timestamps off the 15-minute grid |
| GKG span | 2015-02-18 23:00 → 2026-10-12 18:30 UTC, so the whole research window is inside it |
| URL scheme | Entries use `http://`; the server redirects to `https://` (B2-F) |

### 5.2 Coverage of the research window [VERIFIED from the list]

| Window | Expected slots | Listed | Absent | Listed bytes |
| --- | ---: | ---: | ---: | ---: |
| Minimal: 2021-12-01 00:00 → 2026-07-20 19:45 UTC | 162,512 | **160,658** | **1,854 (1.14%)** | **860,483,377,717** |
| With the optional holdout: → 2026-09-10 19:45 UTC | 167,504 | 165,650 | 1,854 (no new absences) | 882,074,943,640 (+21.6 GB) |

**Listed files by year (minimal window).** Each year's count is exactly 96 slots
per day less that year's absences.

| Year | Files | Mean size |
| --- | ---: | ---: |
| 2021 (Dec) | 2,976 | 4.78 MB |
| 2022 | 35,035 | 4.72 MB |
| 2023 | 34,875 | 6.15 MB |
| 2024 | 35,134 | 5.81 MB |
| 2025 | 33,359 | 5.19 MB |
| 2026 (to 07-20) | 19,279 | 4.64 MB |

**Size distribution of listed files:**

- mean 5,355,995 B, median 4,943,393 B;
- 10th–90th percentile 2.79–8.46 MB;
- smallest 5,686 B, largest 51,090,571 B.

### 5.3 Evidence categories (minimal window)

| Category | Slots | Label |
| --- | ---: | --- |
| Listed in the master list | 160,658 | [VERIFIED] |
| … of which independently checked available: header-only 200 in B2-F, with listed size equal to Content-Length. Includes this pilot's sample, also MD5-verified | 671 | [VERIFIED] |
| … listed but not independently checked | 159,987 | [UNVERIFIED availability] |
| … listed but an availability check failed | 0 | [VERIFIED] |
| Absent from the master list | 1,854 | [VERIFIED] |
| … inside the outage runs B2-F established by header-only checks | 1,674 | [VERIFIED] |
| … absent and never checked against the server | 180 | [UNVERIFIED on the server] |

**Agreement so far** [VERIFIED]: wherever the list and a header-only check can be
compared, they agree.

- All 671 files B2-F saw present are listed, with identical sizes.
- All 4 sample files B2-F saw missing are absent.
- Every slot in the B2-F outage runs is absent.

The list does not mark files as missing; absence is inferred from the expected
15-minute grid. **Additional evidence needed** [PROPOSED]: header-only checks of
the 180 unchecked absent slots would show whether any exists on the server
unlisted. That is 180 requests and no downloads, and needs your approval.

---

## 6. Verified outage and missing-file findings

**All absences, by episode** [VERIFIED from the list]. In every slot, the export,
mentions and GKG streams are all missing together, so these are whole-pipeline
outages, not GKG-only losses.

| Episode | Absent slots | Period |
| --- | ---: | --- |
| 2025-06-14 18:00 → 2025-07-02 02:00 UTC | 1,665 | Test (window 6). Matches B2-F exactly |
| 2025-06-12 18:15 → 20:15 UTC | 9 | Test. Matches B2-F exactly |
| March 2023 disruption: a run 2023-03-22 04:45 → 2023-03-23 12:45 (129), 9 slots on 2023-03-21 22:00 → 03-22 04:00, and 9 singles on 03-08 … 03-19 | 147 | Training. **New** |
| Isolated single slots | 33 | 2022: 5; 2023: 18; 2024: 2; 2025: 7; 2026: 1 (2026-05-09 23:30). **New** |
| **Total** | **1,854** | |

The 10 single slots in the test-period forecast span:

| Year | Slots (UTC) |
| --- | --- |
| 2024 | 07-03 18:15; 09-01 23:15 |
| 2025 | 01-05 09:15; 03-11 06:45; 03-27 10:00; 04-24 21:30; 04-29 11:00; 05-03 00:30; 05-06 13:45 |
| 2026 | 05-09 23:30 |

Each is about 1% of a day's batches.

**Listed but near-empty files** [VERIFIED sizes; content not inspected]. A file
counts as near-empty when it is under 10% of the median size of the same UTC
slot over ±14 days. 86 listed files meet this:

- **one 83-slot run, 2022-11-10 22:00 → 2022-11-11 18:30 UTC** (largest file
  159,602 B, against a normal ≈5 MB);
- 2022-12-31 17:45 (438,824 B);
- 2023-03-21 22:15 (5,686 B) and 23:00 (13,704 B).

These batches exist, so a presence check misses them. Only per-batch row counts
reveal them.

**Backlog-like bursts** [VERIFIED sizes].

- **Count:** 10 listed files exceed 20 MB.
- **Around the March 2023 disruption:** four files, 21.6–27.5 MB: 2023-03-22
  02:15, 02:30 and 03:00, and 2023-03-23 17:45.
- **After the June–July 2025 outage:** four files on 2025-07-02, 20.0–27.2 MB:
  15:45, 16:00, 20:00 and 20:15.
- **Unexplained:** the remaining two are the largest, 2025-08-01 18:45 (51.1 MB)
  and 2023-07-20 19:00 (37.5 MB).

**News coverage per forecast day** [VERIFIED from the list and the stored trading
days].

- **Method:**
  - Each stored trading day from 2022-01-04 to 2026-07-20 is a forecast origin
    (1,138 days).
  - Its news interval uses the B2-F rule: 16:00 America/New_York cutoff,
    batch + 15 minutes.
  - A batch counts as covered when it is listed and not near-empty.
- **Caveat:** "listed" is not "verified available" (section 5.3).
- **Check:** the result reproduces B2-F's June–July 2025 table exactly.

| Period | Origins | Full coverage | Below 90% | Below 50% | Zero |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training (2022-01-04 → 2024-01-11) | 508 | 475 | 3 | 3 | 0 |
| Test (2024-01-12 → 2026-07-20) | 630 | 606 | 12 | 11 | 10 |

The 15 affected forecast days:

| Forecast origin (close) | Coverage | Target return | Cause |
| --- | --- | --- | --- |
| 2022-11-11 | 13.5% (83 near-empty of 96) | 2022-11-14 | Near-empty run (training) |
| 2023-03-22 | 25.0% (70 absent, 2 near-empty) | 2023-03-23 | March 2023 disruption (training) |
| 2023-03-23 | 29.2% (68 absent) | 2023-03-24 | March 2023 disruption (training) |
| 2025-06-16 | 30.6% (200 of 288 absent) | 2025-06-17 | June–July 2025 outage (test) |
| 2025-06-17, 06-18, 06-20, 06-23, 06-24, 06-25, 06-26, 06-27, 06-30, 07-01 | **0%** | 2025-06-18 … 2025-07-02 | June–July 2025 outage (test) |
| 2025-07-02 | 74.0% (25 absent) | 2025-07-03 | June–July 2025 outage (test) |

---

## 7. Proposed theme-filter feasibility [VERIFIED fields; precision only qualitative; filters stay PROPOSED]

**Source columns, as found in the sample:**

- themes: `V1THEMES`, or `V2ENHANCEDTHEMES`, which gives identical candidate
  matches plus mention counts;
- `V1ORGANIZATIONS`: lower-case names;
- title: `<PAGE_TITLE>` in `V2EXTRASXML`, on 100% of rows;
- `V1LOCATIONS` for US relevance: country code `US`, or type 2 (US state) or 3
  (US city).

**Matching:** exact theme codes; whole-word, case-insensitive phrase keywords
(B2-F §7).

**Language filtering:**

- **How it works:** take the English stream, and assert blank `TRANSLATIONINFO`
  and no translated-record marker. All 1,480 rows passed.
- **Limit:** "English" is not "US". 284 domains include Indian, UK and other
  outlets, so the US-relevance flag is needed.

**Counts in this one batch (1,480 rows):**

| Group | Core-theme rows | Broad-theme rows | Keyword rows | Kept by keyword only | Total kept | US-relevant |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Equity / Nasdaq | 58 (`ECON_STOCKMARKET` 57; 28 with ≥2 mentions) | — | 15 | 3 | **61** (4.1%) | 34 |
| Rates / bonds | 31 | 72 | 18 | 2 (52 more are broad-theme only) | **86** (5.8%) | 46 |
| Gold | 4 (`ECON_GOLDPRICE`) | 29 (`WB_2936_GOLD`) | 0 | 0 (25 are broad-theme only) | **29** (2.0%) | 13 |
| Any group | | | | | **154 (10.4%)**. Themes alone would keep 150 | |

Overlaps: equity and rates 14 rows, equity and gold 5, rates and gold 6.

### 7.1 Likely false positives and negatives

This review is qualitative and covers only one batch. Up to 8 titles per category
were read locally and are not reproduced here (B2 §8). No returns and no forecast
results were used.

**Equity / Nasdaq.**

- **False positives:** `ECON_STOCKMARKET` also fires on incidental mentions.
  About half of the 8 titles read were not about markets: public spending, legal
  funding, holiday closures, a criminal case. The market-related ones were mostly
  company-level items: fund-holdings notices, analyst coverage, a platform
  launch.
- **False negatives:** 14 titles with "stock" or "shares" words were not
  captured. They were company-level insider-trade or holdings notices, often for
  NYSE American or London listings, or non-financial uses of "shares". None was a
  market-level item.
- **Ambiguities:**
  - whether company-level boilerplate belongs in a market-level series;
  - whether NYSE and broad US-equity news should feed a Nasdaq-focused series,
    since the keywords are Nasdaq-centric.

**Rates / bonds.**

- **False positives:**
  - **Core themes:** about half of the titles read were macro or rates-relevant
    (US GDP releases, an Indian central-bank liquidity operation). The rest were
    tangential (a licence revocation, housing affordability, a court filing).
  - **Broad themes:** the four broad themes **alone** (`ECON_INFLATION`,
    `ECON_DEBT`, `WB_1045_TREASURY`, `ACT_YIELD`) gave 0 of 8 market items: tax
    policy, student loans, a corporate restructuring, a trade conference.
  - **Keyword "bond(s)":** caught insurance catastrophe bonds and a bond-ETF
    holdings notice.
- **False negatives:** a macro futures preview was caught only through an
  organization keyword.
- **Ambiguities:**
  - non-US central banks tagged `ECON_CENTRALBANK`, which the US flag handles;
  - "treasury" outside the US;
  - `ACT_YIELD` used as a verb.

**Gold.**

- **True positives:** all 4 `ECON_GOLDPRICE` rows were gold-price related: two US
  market wraps mentioning gold, one local gold price, one gold-rally item.
- **False positives:** `WB_2936_GOLD` on its own gave 0 of 8 gold-market items:
  crafts, crime, diplomacy, sport, TV listings, a mercury seizure.
- **Correct rejections:** the phrase keywords rightly ignored 5 titles with
  "gold/golden": company names, a navy programme, a surname, sports medals.
- **False negatives:** unknown; none observed.
- **Ambiguities:** volume is very low (4 core rows in this batch).

**Every group: duplicates.** 264 of 1,480 rows (17.8%) repeat a title already in
the batch: 104 groups, the largest with 12 rows. They come mostly from:

- radio-station networks (`iheart.com` 39 rows; `wknofm.org`, `kawc.org`);
- a TV-listings site (`tvguide.co.uk` 27);
- wire syndication (`english.news.cn` 12);
- newspaper groups.

The deduplication policy therefore changes counts materially and must be fixed in
advance.

### 7.2 Implications [PROPOSED; pre-registration only, never tuned on returns]

- **Possible changes for you to decide** before filter v1 is frozen:
  - keep `WB_2936_GOLD` and the four broad rates themes as stored flags only,
    outside the group definitions, or drop `WB_2936_GOLD`;
  - store V2 mention counts so that a "≥2 mentions" rule can be evaluated;
  - flag company-level boilerplate and syndicated duplicates instead of
    deleting them.
- **Keywords:** they added only 4 kept rows here. Their main value is as a
  precision check, not for recall.
- **Measuring precision:** a formal precision estimate needs a labelled title
  sample drawn only from training-period batches, which is a later, separately
  approved step.

---

## 8. Timestamp and leakage implications

1. **The batch stamp is the only availability anchor** [VERIFIED for this file].
   The file name, `V2.1DATE` and every record-ID prefix are identical.
2. **The availability rule survived the check** [VERIFIED, provisional]. The rule
   is max(nominal batch time, Last-Modified) + 15 minutes.
   - **This file:** written 8:55 before its nominal time, so it was available by
     15:00:00 UTC on 2025-12-23. That is about 24 minutes after it was actually
     written, so the rule is conservative here.
   - **Same pattern elsewhere:** the master list's own update timing, B2-F's 14
     sampled files and the 53 files at the outage edges.
   - **Limit:** one file and these observations cannot guarantee the rule for
     all 160,658 files. **Recording each file's Last-Modified in the manifest is
     part of the rule**, not optional.
3. **Page timestamps stay diagnostic only** [VERIFIED]. 10 of 733 rows claim
   publication after their own batch.
4. **Outages and backlogs** [PROPOSED].
   - Batches after an outage can carry stale articles at their own batch time.
     They must never be back-dated.
   - Volume features need per-batch flags: absent, near-empty (from row counts),
     and possible backlog (size or row count far above the slot's usual level).
5. **Coverage-based nulls** [PROPOSED].
   - The section 6 table is the starting list: 3 training days and 12 test days.
   - The threshold is a B3 decision. Below it, features are null with a reason,
     never neutral or zero (CLAUDE.md §12).
6. **Snapshot pinning** [PROPOSED].
   - The list is live and could in principle gain backfilled entries later.
   - The acquisition manifest should record the list's SHA-256 (`7e5d2c2e…` for
     this audit) and diff any later snapshot.
7. **Unchanged from B2-F:**
   - the 16:00 ET cutoff;
   - the forecast alignment (the return dated *d* uses news assigned before *d*);
   - early-close handling, still **[BLOCKED]**;
   - the market-snapshot freeze, still to be decided.

---

## 9. Updated transfer and resource estimates

These replace B2-F's sample-based figures. Ranges reflect single measurements.

| Quantity | B2-F | B2-G | Basis |
| --- | --- | --- | --- |
| Download, minimal window | ≈0.895 TB (95%: 0.863–0.929) | **0.860 TB exact** for listed files; 0.87–0.90 TB on the wire with 1–5% protocol and retry overhead | Master-list sum [VERIFIED] + assumption |
| Download with holdout | ≈+22–28 GB | **+21.6 GB** (0.882 TB) | [VERIFIED] |
| Elapsed time, a few parallel connections | ≈40 h at 50 Mbit/s | **≈43–47 h** if the aggregate stays at the measured 41–44 Mbit/s and latency overlaps; faster if parallel connections scale | [ESTIMATED]; parallelism [UNVERIFIED] |
| Elapsed time, one file at a time | — | ≈91–111 h (3.8–4.6 days): 1.1–1.4 s latency plus 0.97–1.05 s transfer per mean file | [ESTIMATED] |
| CPU | ≈4–10 core-hours | **≈3.7–7.8 core-hours** (central ≈4.2) | 0.860 TB × 2.8–3.6 compression (3.09 measured once) ÷ 110–180 MB/s (177 measured once) [ESTIMATED] |
| Memory | under 200 MB | ≈35 MB process for a typical file; ≈80–90 MB for the largest listed file (51 MB) | Streaming, measured once, scaled [ESTIMATED] |
| English rows in the window | ≈216–231 M | ≈206–223 M | Listed bytes ÷ 3.86–4.17 KB compressed per row (3 files) [ESTIMATED] |
| Rows kept | 6–14% | 6–14% (10.4% here; B2's 6.5–7.9% used a narrower theme list) | [ESTIMATED] |
| Filtered output, minimal schema | ≈2–6 GB gzip | **≈1.7–4.3 GB gzip** (≈5–13 GB uncompressed) | 405 B per row and 2.9× gzip, measured on 154 rows [ESTIMATED] |
| Route B scan (context only) | ≈0.7–3.6 TiB | ≈0.5–1.1 TiB | Measured column sizes (V1 vs V2 variants) + 2 B per STRING [assumption] × 1.8–2.2× English rows for the translated stream [assumption] [ESTIMATED] |

Network time dominates; CPU, memory and disk are not constraints. B2-F's
"4–5× compression" assumption was too high: the measured ratio is 3.09×.

---

## 10. Cleanup confirmation [VERIFIED]

**Deleted:**

- the sample zip (6,173,549 B);
- the extracted CSV (19,089,331 B);
- the master list (128,483,714 B);
- their three temporary folders.

`rm` exited 0, and a listing shows no `b2g_tmp_*` folder remains.

**Raw-file search:** across the repository (excluding `.venv`, `node_modules` and
`.git`) and the scratch directory, for `*.zip`, `*.gkg.csv`, `*.export.CSV*`,
`*.mentions.CSV*` and `masterfilelist*`. **No GDELT raw file remains.**

**Master list not kept.** No approved repository convention exists for it, so
it was deleted. Its provenance is recorded here: URL, size, MD5, SHA-256,
Last-Modified.

**What the scratch directory keeps:** scripts and derived summaries only (counts,
timestamps, sizes). No titles and no raw rows.

**Not created:**

- `datasets/raw/gdelt/`, `datasets/processed/`, or any other permanent data
  folder;
- `.gitignore` changes;
- any change to the database (read-only queries on `market_data`) or to
  user-owned data.

---

## 11. Unresolved issues and limitations

- **Single samples:**
  - **One file:** schema, timing, compression and filter counts come from one
    15-minute batch on a pre-Christmas Tuesday. B2's 2022 and 2024 samples also
    had 27 columns, but other periods may differ in mix and size.
  - **Two transfers:** throughput and latency come from two transfers at one
    time of day. Parallel behaviour is untested.
- **Unchecked availability:**
  - 159,987 listed files have not been checked one by one. Their availability is
    presumed from the list, which agreed with every header-only check so far.
  - 180 absent slots have never been checked against the server.
- **Unknown meaning:**
  - the 61 malformed placeholder lines, 6 of them inside the window;
  - the two unexplained large files (2025-08-01 and 2023-07-20).
- **Heuristics:** near-empty detection is a size rule, not a row count. The
  manifest's row counts would replace it.
- **Filter precision:** qualitative only, from about 8 titles per category in one
  batch.
- **Still blocked or undecided:**
  - early-close calendar: [BLOCKED];
  - market-snapshot freeze: not yet decided;
  - title redistribution: still unverified, so titles stay local.
- **Out of scope:** the translated stream was not examined.

---

## 12. Recommendation for the next approval decision

**Route A remains practical. I recommend approving full acquisition only together
with the decisions below** [PROPOSED]. The pilot found no technical blocker:

- the files parse exactly as documented;
- streaming works within a few megabytes of memory;
- integrity is verifiable per file (MD5 equals the ETag, CRC-32 in the zip);
- the exact size is known (0.860 TB).

**Decisions needed before any full acquisition:**

1. **Approve the acquisition itself:**
   - Route A over the minimal window (160,658 files, 0.860 TB), or with the
     holdout (165,650 files, 0.882 TB);
   - pinned to master-list snapshot `7e5d2c2e…`, or to a fresh snapshot taken at
     the start, with the diff recorded.
2. **Run parameters:**
   - 2–4 parallel connections with retry and backoff;
   - you run it yourself, expecting about 2 days (up to about 5 sequentially);
   - the first few hundred files serve as the throughput check, with no separate
     benchmark.
3. **Filter v1:** approve it as proposed in B2-F, or with the section 7.2
   changes. It is frozen before any data is compared with returns.
4. **Storage and provenance:**
   - `datasets/raw/gdelt/english_gkg_v1/` (already ignored; recommended);
   - whether a copy of the master-list snapshot (≈128 MB) is kept there as
     provenance;
   - whether to store V2 mention counts and the full `V1THEMES` string.
5. **Coverage policy:** null features below a coverage threshold for the days in
   section 6, plus absent, near-empty and backlog flags per batch.
6. **Optional:** approve 180 header-only checks of the unchecked absent slots.
7. **Carried over from B2-F:**
   - early-close handling: an official list or a uniform 13:00 ET cutoff;
   - freezing the market snapshot (2022-01-03 → 2026-09-11);
   - the ADR (B2's proposed ADR-043), written after your approval and not
     before.

**Stop.** The full archive has not been downloaded, B3 has not started, and
nothing proceeds without your explicit approval.

---

## Sources (accessed 2026-10-12)

**Downloaded:**

- <https://data.gdeltproject.org/gdeltv2/20251223144500.gkg.csv.zip>
- <https://data.gdeltproject.org/gdeltv2/masterfilelist.txt>

**Read:**

- GKG 2.1 codebook:
  <http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf>
  (field definitions, as extracted in B2/B2-F);
- GDELT blog posts on page titles (<https://blog.gdeltproject.org/?p=7791>) and
  precise publication timestamps (<https://blog.gdeltproject.org/?p=3176>).

**Repository** (read-only):

- the `market_data` table (stored trading days);
- `reports/phaseB2F_gdelt_acquisition_feasibility.md`;
- `reports/phaseB2_historical_news_source_evaluation.md`;
- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`;
- `docs/DECISIONS.md`;
- `docs/MEMORY.md`;
- `.gitignore`.

## Verification of this phase

**Files created:** this report.

**Files modified:**

- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`: a B2-G findings note;
- `docs/MEMORY.md`: the track status;
- `reports/phaseB2F_gdelt_acquisition_feasibility.md`: a factual superseded-by
  note only.

**Network activity:**

- the two authorised downloads;
- two header-only requests, to record them beforehand.

Nothing else was fetched. In particular, no other archive file and nothing from
the translated stream.

**Not done:**

- no account, billing, BigQuery query or paid service;
- no dependency or lockfile change;
- no application, API, migration, model or training-script change;
- no database write;
- no sentiment scoring or feature generation;
- no B3 or blockchain work.

**Tests:** none run, because no code changed. All pilot analysis ran as separate
scripts outside the repository.
