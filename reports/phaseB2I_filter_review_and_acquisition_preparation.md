# Research Enhancement Track — Phase B2-I: Filter Review and Acquisition Preparation

**Type:** preparation only. **Full archive download is NOT approved. B3 is NOT
approved.** Blockchain work has not started.

**What this phase did:**

- read the B2 to B2-H reports, the architecture document, `DECISIONS.md` and
  `MEMORY.md`;
- inventoried the GDELT evidence that still exists, in the repository and in the
  session scratch folder;
- wrote the annotation rubric, the sampling and labelling protocol and the
  annotation template;
- fixed a pre-registered training-period sample, computed from saved metadata
  only;
- designed the manifest schema and compiled it in a throwaway in-memory database;
- checked the ignore rules (read-only) and free disk space.

**What it did not do:** no network request of any kind, no download, no database
query, and no change to dependencies, `.gitignore`, application code, schema,
models, training scripts or market data. No data directory was created.

**Date:** 2026-10-12 (UTC).

**Builds on:**

- `reports/phaseB2H_pre_acquisition_readiness.md` (B2-H);
- `reports/phaseB2G_gdelt_pilot_audit.md` (B2-G);
- `reports/phaseB2F_gdelt_acquisition_feasibility.md` (B2-F);
- `reports/phaseB2_historical_news_source_evaluation.md` (B2);
- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`.

`docs/DECISIONS.md` still ends at ADR-042 and has no GDELT ADR [VERIFIED]. None
was created.

**Labels:**

- **[VERIFIED]**: confirmed from the repository, the saved B2 to B2-H evidence, or
  a local read-only check.
- **[MEASURED]**: observed directly in this phase (disk space; schema size with
  placeholder rows).
- **[ESTIMATED]**: computed from verified or measured inputs plus stated
  assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## Summary

- **The empirical filter review is BLOCKED** [VERIFIED]. No usable title sample
  exists:
  - only three GDELT batches were ever downloaded (two in B2, one in B2-G), all
    were deleted, and only counts were kept. No title survives;
  - two of the three are test-period batches. The only training-period batch
    (2022-01-03 14:30 UTC) was never title-reviewed;
  - the B2-G batch is test-period and shaped `gdelt_filter_v1`, so it could not
    be evaluation data even if it still existed;
  - downloading again is not authorised in this phase. No precision, recall,
    counts or examples are reported.
- **Prepared instead** [PROPOSED]:
  - a rubric with five categories per theme, a separate polarity field and a
    company-notice field (section 3);
  - a sample fixed now, before any content is seen: 192 training-period batches
    (≈1.03 GB) for development and 192 more for confirmation. They come from a
    seeded hash procedure, and the lists are committed by SHA-256 (`a459a3fb…`,
    `b580e8cf…`; section 4, Appendix A);
  - blind labelling, an agreement check, weighted estimators and decision rules
    (section 4);
  - a ready annotation template (section 4.9).
- **A gap in B2-H's plan is fixed** [VERIFIED]:
  - **The gap:** B2-H's check for missed stories sampled *uncaptured* rows, but
    the acquisition stores only captured rows.
  - **Consequence:** recall can only be measured on a raw sample, before the
    capture rule is frozen.
  - **Proposed addition:** the acquisition also keeps a 1-in-1,000 hash-selected
    audit sample of uncaptured rows.
- **Only three acquisition choices are irreversible:** the capture rule, the
  stored columns and the audit-sample rate. Series rules, flags and deduplication
  can all be recomputed later from stored rows.
- **Manifest and workflow** [PROPOSED]:
  - **Schema:** five SQLite tables. It compiles, and its constraints rejected 9
    of 9 invalid states in an in-memory test.
  - **Workflow:**
    - downloads one batch at a time;
    - re-checks unlisted slots with header checks that allow for the CDN's
      one-hour cache;
    - never requests the accepted June 2025 outage;
    - commits each UTC day atomically;
    - stops at byte-budget and disk-space limits.
- **Storage** [VERIFIED]:
  - every planned path is git-ignored by `datasets/raw/*`. `datasets/processed/`
    is not, so it is not used;
  - drive C: has 182.8 GB free. The plan needs ≈3–8 GB, or ≈5–16 GB if the full
    theme string is kept.
- **Bandwidth and data allowance are unknown and not assumed** (section 9).
  - **Volume:** the minimal window is 0.87–0.90 TB on the wire.
  - **Time:** ≈19 h of pure transfer at 100 Mbit/s, but ≈2.8–3.4 days one file
    at a time, because per-request latency dominates.
- **Recommended order:**
  1. you approve the protocol;
  2. the development sample is downloaded (≈1.03 GB);
  3. it is labelled;
  4. the capture rule is frozen;
  5. you decide on the full acquisition.

---

## 1. Confirmed decisions and boundaries

| Decision (B2-I instructions) | Status | Effect on the plan |
| --- | --- | --- |
| Route: direct GDELT streaming | Conditionally preferred | The workflow (section 7) assumes it. No BigQuery, account or billing |
| Window | Minimal, ≈0.860 TB, subject to final acquisition approval | 162,512 slots, 2021-12-01 00:00 → 2026-07-20 19:45 UTC |
| Holdout | Follows from the minimal window | **No news-based final holdout exists**: the 37-return tail gets no news. It could be appended later (+21.6 GB), but only if designated before any test-period result is seen (B2-H §8) |
| Filters | Approved for labelled review only; not frozen | Sections 3–4 review them. The acquisition waits for a frozen capture rule |
| June 2025 outage | Known missing slots accepted; no further checks | All 1,674 slots are recorded as `absent_accepted` and never requested |
| Language | English only | Only the English stream; the translated stream is never requested |
| Scope | Market level; no instrument-specific claims | Three market series (US equity, US rates, gold). Their link to instruments is a weak, market-level proxy |
| Missing data | Never neutral | Absent, failed and near-empty batches stay explicit in the manifest and the outputs |
| Full archive download | **NOT APPROVED** | Nothing was downloaded |
| B3 sentiment | **NOT APPROVED** | Polarity is only an annotation field; nothing is scored |
| Bandwidth and data allowance | Unknown | Not assumed. A checklist and byte budgets instead (sections 7 and 9) |

**Still open from B2-H:**

- the 13:00 ET early-close cutoff rule (the calendar itself is verified);
- the missing-data thresholds (0.75 primary; 0.50 and 0.90 sensitivity);
- storage and retention (section 8.4).

---

## 2. Available evidence and sample availability [VERIFIED]

| Evidence | Training or test? | Status | Usable for the review? |
| --- | --- | --- | --- |
| B2 batch `20220103143000` | Training: forecast origin 2022-01-03 | Deleted in B2. Only counts kept; its titles were never examined | No: not retained |
| B2 batch `20240112210000` | Test: available at 21:15 UTC, after that day's 21:00 UTC cutoff. Origin 2024-01-16, since 15 January was a market holiday | Deleted in B2. Counts only, including keyword counts over titles | No: test period; not retained |
| B2-G batch `20251223144500` | Test: origin 2025-12-23 | Deleted in B2-G. About 8 titles per category were read; none were recorded | No: test period; it shaped v1; not retained |
| Scratch summaries (`gdelt_*`, `b2f_*`, `b2g_*`, `b2h_*` JSON) | — | Counts, sizes, timestamps and column statistics. The only title text is one truncated 11-character fragment in a B2 timing diagnostic | No titles |
| Repository | — | No GDELT data; `datasets/` has no `gdelt` folder | — |

**How this was checked:**

- every saved JSON file was searched for title fields;
- the cleanup records of B2 ("Verification of this phase") and B2-G (§10) were
  re-read;
- a recursive search of the scratch folder found no archive, extracted CSV or
  master list.

**Lawful retention is not the obstacle.** GDELT's terms allow unrestricted
academic use and retention, with citation (B2 §4.3) [VERIFIED]. Whether
publishers' headlines may be republished is [UNVERIFIED], so titles stay local in
any case.

**The filter's design evidence came from the test period** [VERIFIED].

- **What shaped v1:** B2-G's qualitative reading of one test-period batch
  (2025-12-23 14:45 UTC).
- **What did not:** no returns, prices or forecasts (B2-G §7.1). No target
  information entered the filter.
- **Strictly, though,** the design has seen one test-period batch of titles.
- **From now on,** filter evidence comes only from the first training window.
  Any B3 report should disclose this.

---

## 3. Annotation rubric [PROPOSED]

### 3.1 What is labelled, and from what

- **Unit:** one GKG row, which is one article URL as captured in one batch.
- **Evidence allowed:**
  - the decoded title;
  - the source domain and full URL;
  - the batch date (UTC).
- **Not used:**
  - the article page. It is never fetched: this avoids link-rot bias, avoids
    copyright exposure and adds no network traffic;
  - GDELT's themes, tone and locations. They stay hidden, so labels do not echo
    the filter;
  - prices, returns, or any knowledge of later events.
- **Limitation:** labels measure *title-evident* relevance. An article with a
  relevant body but an uninformative title is labelled on its title.

### 3.2 Relevance and polarity are separate axes

- **Relevance** says whether an item is about the theme's market. It says nothing
  about direction.
- **Polarity** is recorded separately, and only for items labelled Relevant
  (section 3.8). A Relevant item may be positive, negative, neutral or mixed.
- **Consequence:** a precise filter is not a sentiment signal.

### 3.3 Relevance categories

Each item is labelled for **all three themes**, so the annotator cannot infer
which filter selected it. One item can be Relevant to several themes, as a
market wrap reporting stocks, Treasury yields and gold would be.

| Code | Category | Rule |
| --- | --- | --- |
| `R` | Relevant market news | The theme's market is a main subject: its prices, moves or outlook, or a driver explicitly framed through that market |
| `RL` | Related but not directly relevant | Mentions or borders on the theme's market without being mainly about it. Examples: one company, a non-US market (for the US themes), local retail prices, macro news with no market framing |
| `I` | Irrelevant | No real connection; a word or theme matched in another sense |
| `A` | Ambiguous | The allowed evidence cannot decide; an ambiguity code is required (section 3.7) |
| — | Duplicate or updated story | Recorded in its own field (section 3.6). The item still gets relevance labels, so duplicates can be counted, or excluded, without losing labels |

**Topic, not impact.** `R` never requires that the news moved prices.
Annotators must not use hindsight.

### 3.4 Theme boundaries

**US equity / Nasdaq-related markets** (series `EQUITY_US`; `^IXIC`, `^NDX` and
`QQQ` by a market-level link):

| Code | Typical items |
| --- | --- |
| `R` | Any of: the US stock market as a main subject; a broad US index (Nasdaq Composite, Nasdaq-100, S&P 500, Dow, Russell 2000) and its moves, levels or outlook; market-wide drivers framed by their effect on US stocks; sector moves framed as market moves; market-structure events (trading halts, circuit breakers); market-level fund flows |
| `RL` | A single company's shares, earnings, IPO or rating, mega-caps included; company or fund notices; non-US stock markets; US macro news with no stock-market framing; crypto; general investing advice |
| `I` | "Stock" as inventory or livestock; "shares" on social media; "Wall Street" as a place or film; no market content |
| `A`, typically | Market not named and the country unclear (A2); market-level or single company unclear (A3) |

**Interest-rate / bond markets** (series `RATES_US`; `AGG`):

| Code | Typical items |
| --- | --- |
| `R` | Any of: Federal Reserve decisions, expected moves, or officials' signals on rates; US Treasury yields or US bond-market moves; the outlook for US rates; US inflation or jobs data, when the title frames it through rates, the Fed or bonds |
| `RL` | Non-US central banks or bond markets; US inflation or jobs data with no rates framing; US mortgage or consumer-loan rates; one issuer's bond sale; US fiscal or debt-ceiling politics with no market framing |
| `I` | "Bond" as a relationship, bail bond or film character; "yield" in farming; "treasury" as an organisation's funds; student-loan or tax policy with no rate angle |
| `A`, typically | Country unclear (A2); which rate is meant is unclear (A4) |

**Gold markets** (series `GOLD`; `GLD`; a global market, so no US requirement):

| Code | Typical items |
| --- | --- |
| `R` | The gold price or gold market as a main subject: spot or futures moves, outlook, market-level demand or supply (central-bank buying, gold-fund flows) |
| `RL` | A gold miner's results or deals; local retail gold-rate listings; other precious metals; a cross-asset wrap that mentions gold in passing |
| `I` | Medals, "Gold Coast", colours, names, jewellery fashion, crafts, thefts of gold objects |
| `A`, typically | Unclear whether "gold" means the commodity (A4) |

### 3.5 Company and fund notices, handled separately

- **The field:** `company_notice` (`Y` / `N` / `U`) marks company- or fund-level
  notices:
  - holdings disclosures, including an adviser's position in QQQ, GLD or AGG;
  - analyst ratings and price targets;
  - insider trades;
  - dividend declarations;
  - one company's earnings.
- **Ceiling:** such an item is at most `RL` for every theme, because the scope is
  market level.
- **What it measures:** it is labelled independently of the `company_item` flag.
  That shows how accurate the flag is, and whether notices leak into a series.

### 3.6 Duplicate or updated story

| Value | Set by | Meaning |
| --- | --- | --- |
| `ORIGINAL` | Pipeline | First occurrence seen |
| `DUP_SAME_BATCH` | Pipeline | The same canonical URL appeared earlier in the same batch |
| `SYNDICATED_SAME_BATCH` | Pipeline | The same normalised title (at least 20 characters) appeared under a different URL earlier in the same batch |
| `REOBSERVATION`, `UPDATE`, `SYNDICATED` | Pipeline, **after acquisition only** | The cross-batch cases of B2-H §4.6. Isolated sample batches cannot show them (section 4.11) |
| `NEAR_DUP` | Annotator | Clearly the same story as an earlier item in the file, but not merged by the pipeline. `near_dup_of` names that item |

Precision is reported twice: over all labelled items, and over unique stories,
which excludes every value except `ORIGINAL`.

### 3.7 Ambiguity codes

| Code | Meaning |
| --- | --- |
| A1 | Title uninformative: generic, truncated, a site name, "live updates" |
| A2 | Country unclear, US or not (US themes only) |
| A3 | Market-level or single company unclear |
| A4 | Word sense unclear: gold, bond, yield, stock, shares, rates |
| A5 | Title not English, or garbled |
| A6 | Title and URL disagree |
| A9 | Other, explained in the note. Also used for a disagreement left unresolved after adjudication |

### 3.8 Polarity: only for `R`, per theme

**What polarity records:** the direction the title reports or clearly implies for
holders of that theme's asset. It is never the annotator's own forecast.

| Theme | `POS` | `NEG` |
| --- | --- | --- |
| `EQUITY_US` | US stocks rising, or news framed as supportive | Falling, or framed as adverse |
| `RATES_US` (for holders of US bonds) | Yields falling, or cuts expected | Yields rising, or hikes expected |
| `GOLD` | Gold price up | Gold price down |

**Other values:**

- `NEU`: factual, with no direction;
- `MIX`: opposite directions, for example Nasdaq up and Dow down;
- `UNC`: the direction cannot be determined.

**Use:** polarity is not analysed in this review and never informs filter choice.
It is kept for a later, separately approved evaluation.

---

## 4. Sampling and labelling protocol [PROPOSED; pre-registered]

### 4.1 Population [VERIFIED counts]

- **Period:** the **first training window only.**
  - **Rule:** batches whose availability (nominal time + 15 min) falls at or
    before cutoff(2024-01-04). That is 16:00 ET = 21:00 UTC, the window's last
    forecast origin.
  - **Range:** 2021-12-01 00:00 → 2024-01-04 20:45 UTC, the lookback month
    included.
  - **Excluded:** embargo, test, tail and holdout data.
- **Frame:**
  - 73,428 grid slots, less `20220103143000` (the B2 sample batch), gives
    **73,427**;
  - **169** are known absent: the March 2023 disruption (147) and isolated
    single slots (22);
  - **86** are near-empty but present. **73,258** are present.
- **Late files:** a sampled batch whose observed `available_at` lands after the
  cutoff is dropped. This rule is pre-registered.
- **What conclusions cover:** this window only. They are not claims about the
  test period, where the source mix may differ.

### 4.2 Batch selection, fixed before any content is seen

```text
SEED   = "wealthpilot-b2i-filter-review-v1"
frame  = every 15-minute stamp 20211201000000 .. 20240104204500 (UTC), minus 20220103143000; N = 73,427
blocks = 24 contiguous time blocks: block b = frame[floor(b*N/24) : floor((b+1)*N/24)]   (3,059-3,060 slots, ~31.9 days)
order  = inside each block, ascending SHA-256(SEED + "|" + stamp) as lower-case hex
round r (r = 1..16): for each block in time order, take the next stamp in that block's order
         that is not a known-absent slot (Appendix B)
stage D (development) = rounds 1-8;  stage C (confirmation) = rounds 9-16
digest = SHA-256 of the stamps in selection order (round 1 blocks 1-24, then round 2, ...),
         one per line, ASCII, LF after every line including the last
```

| Property | Stage D (rounds 1–8) | Stage C (rounds 9–16) |
| --- | --- | --- |
| Batches | 192 | 192 |
| Distinct UTC days | 170 | 172 |
| By year | 2021: 7, 2022: 96, 2023: 89 | 2021: 8, 2022: 94, 2023: 89, 2024: 1 |
| By UTC hour band (00–05 / 06–11 / 12–17 / 18–23) | 41 / 54 / 46 / 51 | 45 / 45 / 46 / 56 |
| Weekend batches | 67 | 54 |
| Near-empty or known-absent selected | 0 | 0 |
| Download [ESTIMATED from B2-G's mean listed size per year] | ≈1.03 GB | ≈1.03 GB |
| List SHA-256 | `a459a3fb44afd7e1e8121cd04f247564ea4e8fe434fdca33c9570e50605b2730` | `b580e8cfc3138cb2a4abc122ed27b25490ef24a4b15d7d9fddc12cf8b9ea8dd1` |

**Combined list (D then C):**
`96bd5c0c6c50d484d92d1363564b9dc42ff2407d19867eb409999458b957d08f`.

**Substitution:** one known-absent slot was skipped during selection,
`20230321233000` in block 15.

**At download time:** a selected slot found absent, or failing integrity twice,
is replaced by the next stamp in its block's order. This rule is pre-registered.

**Size and checksum for the sample:** a header-only request per file gives
Content-Length and ETag (the MD5), and the zip's CRC is checked too. The
128.5 MB master list is not needed for the sample.

### 4.3 Item cells and sample sizes

Every valid English row in the downloaded batches is placed in exactly one cell,
by the first rule that matches. All rules are `gdelt_filter_v1` as written in
B2-H §4.

| Cell | Rule | Items per stage |
| --- | --- | ---: |
| C1 | `GOLD` member | all, up to 200 |
| C2 | `RATES_US` member | 200 |
| C3 | `EQUITY_US` member | 200 |
| C4 | Captured and flagged `company_item` | 100 |
| C5 | Any other captured row: flag-only themes, single-mention stock-market rows, non-US rates, … | 200 |
| C6 | Not captured; a near-miss cue (below) | 300 |
| C7 | Not captured; no cue | 300 |
| **Total** | | **≤ 1,500** |

**How items are chosen:**

- if a cell has fewer rows than its size, all of them are taken;
- otherwise rows are ranked by SHA-256(`SEED|row|<GKGRECORDID>`), and the first
  *n* are taken.

**Near-miss cues** (whole words in `title_norm`, or a theme prefix):

- **Equity words:** stock, stocks, shares, equity, equities, dow, nyse, s&p,
  rally, selloff, sell off, futures, investors.
- **Rates words:** bond, bonds, yield, yields, treasury, treasuries, fed, rates,
  inflation, cpi, powell, mortgage, monetary.
- **Gold words:** gold, precious, ounce, xau.
- **Themes:** any `V1THEMES` code starting with `ECON_`.

**Why the cells look like this:**

- C1–C3 measure series precision.
- C4 checks the company flag.
- C5 shows what the series rules leave out of the stored rows; those can be
  recovered later without downloading again.
- C6 and C7 show what the capture rule loses for good. That is the irreversible
  part.

The comparison variants S1 (broad) and S2 (title-only) from B2-H §4.4 are scored
on the same labels.

### 4.4 Blinding and labelling steps

1. **Download** the stage D batches (after your approval) into
   `review/b2i_review_v1/raw/`, with the integrity checks of section 7.
2. **Process** every row: validity, `gdelt_filter_v1`, S1 and S2, the
   within-batch duplicate checks, and the cell. Record every cell's row count.
3. **Build two files:**
   - **the annotation file:** titles, URLs, domains, dates and the pipeline's
     duplicate value. Items are shuffled by SHA-256(`SEED|order|<GKGRECORDID>`);
   - **a sealed key:** cell, weights, filter outcomes, rounds.
4. **Label:** annotator A labels everything. Annotator B labels the overlap
   subset: items with SHA-256(`SEED|iaa|<GKGRECORDID>`) in its lowest 20% (first
   8 hex digits < 0x33333333).
5. **Lock:** before unsealing, record each label file's SHA-256 in
   `selection_log.json`. After that, labels change only through logged
   error corrections.
6. **Agreement** (section 4.5) is computed from labels alone, before unsealing.
7. **Unseal** the key and compute the estimates (section 4.6).

### 4.5 Agreement and adjudication

- **Statistic:** Cohen's κ per theme, for `R` versus not-`R` and for the full
  four-way label, with raw agreement.
- **Proposed bar:** κ ≥ 0.60 for `R` versus not-`R`.
  - **Below it:** the rubric for that theme is clarified, as a new rubric
    version, and both annotators re-label that theme's items before unsealing.
- **Disagreements:** settled by discussion. Both original labels are kept.
  Anything left unresolved becomes `A`/A9 and is listed by record ID.
- **If only one person is available:** 10% of the items are re-labelled after at
  least 7 days, and the report shows within-annotator consistency instead.
- **Claude as a second annotator:** possible, if you choose, but disclosed as
  model labels. They are never the only basis for a precision figure.

### 4.6 Estimators and reporting rules

**Weights.** Each cell has weight w = N / n: rows in the cell across the stage's
batches, divided by items labelled.

| Quantity | Definition |
| --- | --- |
| Precision, theme T | Weighted share of sampled T members labelled `R`. Ambiguous items are excluded from the point estimate. Bounds treat them as all non-`R` or all `R`. A lenient version counts `R` + `RL` |
| Pooled recall, theme T | Weighted `R` among T members ÷ weighted `R` over cells C1–C6 |
| Capture recall, theme T | Weighted `R` in captured cells (C1–C5) ÷ weighted `R` over all cells. If C7 has no `R` item, its share is bounded by the rule of three (3/n, one-sided 95%) and the recall is reported as a lower bound |
| Company flag | Share of C4 labelled `company_notice = Y`; weighted share of series members labelled `Y` (leakage) |
| Duplicates | Pipeline duplicate rates; count of annotator `NEAR_DUP` items |
| Intervals | Batch-cluster bootstrap: 2,000 resamples of the stage's batches, `numpy` `default_rng(42)`. Unweighted Wilson intervals per cell as a cross-check |

**Reporting rules:**

| Non-ambiguous members labelled | Precision reported as |
| ---: | --- |
| 100 or more | An estimate, with its interval |
| 30–99 | "Indicative" only |
| Under 30 | Counts only |

- **Recall:** always reported as the pooled and capture decomposition with its
  limits, never as one unqualified number.
- **Titles:** never quoted. Examples are given by record ID and pattern.

### 4.7 Decision rules [PROPOSED; to be fixed before the first label]

> **Status note (B2-U12, 2026-10-19):** the numeric criteria below (precision 0.70, lower bound 0.60, recall 0.90, floor 100) were **approved as written** by the project owner (D8), with "pooled capture recall" read as pooled recall (D4) and the generator `random.Random(42)` (D5). See `phaseB2U12_m2_selection_and_plan.md`. The text below is unchanged.


1. **Freeze a series unchanged** if its precision (ambiguous excluded) is at
   least 0.70, its bootstrap lower bound is at least 0.60, and its pooled capture
   recall is at least 0.90.
2. **Otherwise, revise once** (v2). Each change must cite stage D record IDs and
   a pattern. v2 is then estimated on **stage C only**, data it has not seen.
   - **Pass:** v2 is frozen if it meets rule 1 on stage C.
   - **Fail:** the series is reported "not usable", like B2-H's eligibility rule.
     There is no further tuning.
3. **Widening the capture rule** is cheap in storage and must be settled before
   the full acquisition.
4. **When stage C is fetched.** Only when stage D shows either of:
   - a revision was made;
   - a theme has fewer than 100 member rows. This is decided from counts only,
     never labels.

   A revision that touches only series rules could instead be confirmed after
   acquisition, on stored training-period rows from batches outside stage D,
   which saves ≈1 GB.

These thresholds are suggestions, not derived from data. Choose them before any
label exists.

### 4.8 How cherry-picking is prevented

- **Batches:** fixed by a seeded hash before any content is seen, and committed
  by SHA-256 in this report.
- **Items:** chosen inside batches by a seeded hash, with fixed cell sizes.
- **Blinding:** annotators never see cell, filter outcome, themes or tone, and
  items from all cells are shuffled together.
- **Completeness:** every selected item is labelled and reported; none may be
  dropped.
- **Frozen in advance:**
  - the rubric and the decision rules, before the first label;
  - stage C triggers, from counts, never labels;
  - label files, by SHA-256, before the key is unsealed.
- **Hold-out confirmation:** any revision is judged on stage C.
- **Training period only:** no returns, model outputs, forecasts or test-period
  data at any step.

### 4.9 Annotation template

**Annotation file** (`annotation_<A|B>.csv`; UTF-8; RFC 4180 quoting):

```csv
item_id,gkg_record_id,batch_date_utc,source_domain,url,title,mech_dup,rel_equity,rel_rates,rel_gold,amb_code,company_notice,pol_equity,pol_rates,pol_gold,near_dup_of,annotator_id,labelled_at_utc,note
```

| Column | Filled by | Allowed values |
| --- | --- | --- |
| `item_id` … `title` | Pipeline (read-only) | Shuffled order; the title is decoded |
| `mech_dup` | Pipeline (read-only) | `ORIGINAL`, `DUP_SAME_BATCH`, `SYNDICATED_SAME_BATCH` |
| `rel_equity`, `rel_rates`, `rel_gold` | Annotator | `R`, `RL`, `I`, `A` (all three, always) |
| `amb_code` | Annotator | A1–A6, A9. Required if any `rel_*` is `A` |
| `company_notice` | Annotator | `Y`, `N`, `U` |
| `pol_equity`, `pol_rates`, `pol_gold` | Annotator | `POS`, `NEG`, `NEU`, `MIX`, `UNC`. Only where that theme is `R`; otherwise blank |
| `near_dup_of` | Annotator | The `item_id` of an earlier item telling the same story, or blank |
| `annotator_id` | Annotator | Initials; never an email |
| `labelled_at_utc`, `note` | Annotator | ISO time; free text, which stays local |

**Sealed key** (`key_sealed.csv`; not opened until the labels are locked):

```csv
item_id,gkg_record_id,batch_ts,stage,round,block,cell,cell_rows,cell_items,weight,captured,company_item,member_equity_us,member_rates_us,member_gold,s1_equity,s1_rates,s1_gold,s2_equity,s2_rates,s2_gold,near_miss_cue,iaa_subset
```

**Other files** (local only):

- `adjudication.csv`;
- `selection_log.json`: seed, list hashes, stages fetched, per-batch integrity
  results, cell counts, label-file hashes.

**Annotator card:**

1. Judge the topic, not its impact. Never use knowledge of later market moves.
2. Use the title, URL, source and date only. Do not open the link.
3. Label every theme:
   - `R`: the theme's market is a main subject;
   - `RL`: mentioned or adjacent (one company, non-US, local retail, macro with
     no market framing);
   - `I`: no real connection;
   - `A`: only when you cannot decide, with a code.
4. Company and fund notices: set `company_notice = Y`. They are never `R`.
5. Polarity only for `R`, from the asset holder's view. Rising yields are `NEG`
   for bonds.
6. Mark a near-duplicate you notice with `near_dup_of`.
7. Once a file is locked, only fix errors, and log each fix in `note`.

### 4.10 Effort and data [ESTIMATED]

- **Download:**
  - stage D: 192 files, ≈1.03 GB;
  - stage C, only if triggered: another ≈1.03 GB;
  - 192–384 header requests.
- **Labelling:** at most 1,500 items per stage, at 15–30 s each:
  - annotator A: ≈6–12.5 hours;
  - annotator B, on ≈300 overlap items: ≈1.25–2.5 hours.
- **Tooling:** the parser and `gdelt_filter_v1` must exist as code first. Writing
  them once, in a separately approved phase, means the review tests exactly what
  the acquisition will run.

### 4.11 After acquisition: duplicate audit [PROPOSED]

Cross-batch duplicates cannot be judged on isolated sample batches. After
acquisition, and on training-period rows only, draw seeded samples of 100 each:

- story merges (syndication);
- updates;
- re-observations;
- unmerged near-duplicate title pairs: word-set (Jaccard) overlap of at least 0.6
  within 72 h.

Label each "same story: `Y`/`N`/`U`". This gives the merge precision and the
missed-merge rate of B2-H §4.6.

---

## 5. Filter-review results: BLOCKED

| Theme | Titles reviewed | `R` / `RL` / `I` / `A` | Duplicates and updates | Precision | False positives and negatives | Unresolved disagreements |
| --- | ---: | --- | --- | --- | --- | --- |
| US equity / Nasdaq (`EQUITY_US`) | 0 | Not available | Not available | Not estimated | None | None |
| Interest rates / bonds (`RATES_US`) | 0 | Not available | Not available | Not estimated | None | None |
| Gold (`GOLD`) | 0 | Not available | Not available | Not estimated | None | None |

**Why** [VERIFIED; section 2]:

- no authorised title sample is retained;
- the only training-period batch ever downloaded was never title-reviewed, and is
  deleted;
- the one batch whose titles were read is test-period and in-sample for v1.

**What was not done:**

- no recall is claimed;
- no data was downloaded to fill the gap;
- no sample was reconstructed.

**B2-G's reading does not count as a review.** About 8 titles per category from
one test-period batch were read qualitatively. They were not randomly drawn, not
recorded, and in-sample, so they are not reported as results.

**Filter status:** `gdelt_filter_v1` stays **PROPOSED**, approved for labelled
review only.

---

## 6. Proposed manifest schema: `gdelt_manifest_v1` [PROPOSED; not created]

### 6.1 How slots are classified

Each slot carries five independent status fields: existence, fetch, validation,
commit and cleanup. Existence keeps "absent", "failed" and "not yet known" apart:

| `existence` | Meaning | Counts as |
| --- | --- | --- |
| `unverified` | Nothing observed yet. Every listed slot starts here | Not yet known |
| `present_verified` | Fetched, and every integrity check passed | Present |
| `present_invalid` | A body arrived but failed integrity twice | **Failed**, not absent |
| `absent_confirmed` | At least two fresh 404s more than an hour apart, and never a 200 | Absent |
| `absent_inconclusive` | 404s only from the CDN cache, or not independent | Absent, flagged |
| `absent_accepted` | The June 2025 outage, accepted by decision and never requested | Absent, by decision |
| `request_failed` | Only timeouts, connection errors, 5xx or 429 | **Failed**, not absent |
| `inaccessible` | Another 4xx, or a redirect outside the allowed form | **Failed**, not absent |

Every slot that is not `present_verified` is missing for coverage, but the reason
is never lost.

### 6.2 Starting state for the minimal window [VERIFIED counts]

| Slots | Starting state | At acquisition |
| ---: | --- | --- |
| 160,658 | Listed: `unverified`, with the list's size and MD5 | Fetched |
| 1 | `20220207190000`: unlisted, present per B2-H (7,338,445 B, ETag `8ef2936c…`) | Re-checked by header, then fetched; ETag used as the MD5 |
| 178 | Unlisted, absent per B2-H | Re-checked by header, at most 3 requests each |
| 1 | `20260509233000`: unlisted, B2-H inconclusive | Re-checked by header |
| 1,674 | June 2025 outage: `absent_accepted` | Never requested |
| **162,512** | | |

**Provenance:** `run.audited_list_sha256` records the audited snapshot
`7e5d2c2efb7298af6eafb0898739ba880b875b586255e994a81ff1a975cfebf0` (B2-G).
Appendix B keeps its gap list, so a fresh list can be compared slot by slot.

### 6.3 DDL

SQLite through Python's standard `sqlite3`, with `journal_mode=WAL` and
`foreign_keys=ON`.

```sql
CREATE TABLE run (
    run_id                       TEXT PRIMARY KEY,        -- UTC start, e.g. '20261101T080000Z'
    started_at_utc               TEXT NOT NULL,
    ended_at_utc                 TEXT,
    outcome                      TEXT NOT NULL DEFAULT 'running' CHECK (outcome IN (
                                     'running', 'completed', 'stopped_by_user', 'stopped_byte_budget',
                                     'stopped_disk_space', 'stopped_error', 'interrupted')),
    window_first_ts              TEXT NOT NULL,           -- '20211201000000'
    window_last_ts               TEXT NOT NULL,           -- '20260720194500'
    code_git_commit              TEXT,
    code_dirty                   INTEGER CHECK (code_dirty IN (0, 1)),
    code_sha256                  TEXT NOT NULL,           -- acquisition and filter modules
    parser_version               TEXT NOT NULL,
    filter_version               TEXT NOT NULL,           -- e.g. 'gdelt_filter_v1'
    filter_spec_sha256           TEXT NOT NULL,
    audited_list_sha256          TEXT NOT NULL,           -- B2-G snapshot '7e5d2c2e...'
    masterlist_url               TEXT NOT NULL,
    masterlist_fetched_at_utc    TEXT,
    masterlist_bytes             INTEGER,
    masterlist_md5               TEXT,
    masterlist_sha256            TEXT,
    masterlist_last_modified_utc TEXT,
    masterlist_diff_json         TEXT,                    -- window entries vs the audited snapshot
    params_json                  TEXT NOT NULL,           -- concurrency, retry policy, byte budgets, thresholds, seeds
    python_version               TEXT NOT NULL,
    tzdata_version               TEXT,
    free_bytes_at_start          INTEGER,
    bytes_downloaded             INTEGER NOT NULL DEFAULT 0,
    requests_made                INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE slot (                                       -- one row per expected 15-minute slot, present or not
    batch_ts               TEXT PRIMARY KEY CHECK (length(batch_ts) = 14 AND batch_ts NOT GLOB '*[^0-9]*'),
    utc_day                TEXT NOT NULL,                 -- 'YYYY-MM-DD', the commit unit
    nominal_utc            TEXT NOT NULL,                 -- ISO 8601 form of batch_ts
    url                    TEXT NOT NULL,                 -- https://data.gdeltproject.org/gdeltv2/<ts>.gkg.csv.zip
    list_status            TEXT NOT NULL CHECK (list_status IN ('listed', 'unlisted')),
    expected_bytes         INTEGER,                       -- master list; Content-Length when unlisted
    expected_md5           TEXT,                          -- master list; ETag when it is a 32-hex MD5
    md5_source             TEXT CHECK (md5_source IN ('master_list', 'etag')),  -- NULL: no checksum published
    existence              TEXT NOT NULL DEFAULT 'unverified' CHECK (existence IN (
                               'unverified',           -- nothing observed yet (every listed slot starts here)
                               'present_verified',     -- fetched; every integrity check passed
                               'present_invalid',      -- a body arrived but failed integrity twice
                               'absent_confirmed',     -- >= 2 fresh 404s more than 1 h apart, never a 200
                               'absent_inconclusive',  -- 404s only from the CDN cache, or not independent
                               'absent_accepted',      -- known June 2025 outage, accepted as missing, not re-checked
                               'request_failed',       -- only timeouts, connection errors, 5xx or 429
                               'inaccessible')),       -- other 4xx, or a redirect outside the allowed form
    existence_evidence     TEXT,                          -- e.g. 'B2-H HEAD 404 x2', 'run 20261101T080000Z HEAD x2'
    fetch_status           TEXT NOT NULL DEFAULT 'pending' CHECK (fetch_status IN (
                               'pending', 'in_progress', 'fetched', 'retry_wait', 'failed_permanent',
                               'not_applicable')),
    attempts               INTEGER NOT NULL DEFAULT 0,
    next_attempt_after_utc TEXT,
    http_status_last       INTEGER,
    http_etag              TEXT,
    http_last_modified_utc TEXT,
    actual_bytes           INTEGER,
    actual_md5             TEXT,
    actual_sha256          TEXT,
    zip_member_name        TEXT,
    zip_member_bytes       INTEGER,                       -- uncompressed
    zip_crc32              TEXT,
    validation_status      TEXT NOT NULL DEFAULT 'pending' CHECK (validation_status IN (
                               'pending', 'passed', 'size_mismatch', 'md5_mismatch', 'zip_invalid',
                               'crc_failed', 'member_unexpected', 'size_guard_exceeded', 'not_applicable')),
    available_at_utc       TEXT,                          -- max(nominal, Last-Modified) + 15 min
    late_flag              INTEGER CHECK (late_flag IN (0, 1)),       -- Last-Modified > nominal + 15 min
    rows_physical          INTEGER,                       -- lines in the zip member
    rows_malformed         INTEGER,                       -- not 27 fields, or not valid UTF-8
    rows_date_mismatch     INTEGER,                       -- V2.1DATE or record-ID prefix differs from batch_ts
    rows_translated        INTEGER,                       -- TRANSLATIONINFO non-blank or translated-record marker
    rows_non_web           INTEGER,                       -- source collection identifier is not 1
    rows_english_valid     INTEGER,                       -- passed every row-validity rule
    rows_captured          INTEGER,
    rows_company_item      INTEGER,
    rows_dup_same_batch    INTEGER,
    rows_audit_sample      INTEGER,                       -- uncaptured rows kept by the hash-selected audit sample
    near_empty_flag        INTEGER CHECK (near_empty_flag IN (0, 1)), -- NULL: no causal baseline yet
    near_empty_baseline    REAL,                          -- median rows_english_valid, same UTC slot, previous 14 days
    backlog_flag           INTEGER CHECK (backlog_flag IN (0, 1)),
    shard_relpath          TEXT,                          -- tmp/<day>/<ts>.tsv.gz: kept + audit rows, until the day commits
    shard_sha256           TEXT,                          -- lets a restart reuse the shard instead of re-downloading
    parser_version         TEXT,
    filter_version         TEXT,
    processed_at_utc       TEXT,
    run_id                 TEXT REFERENCES run (run_id),
    commit_status          TEXT NOT NULL DEFAULT 'pending' CHECK (commit_status IN (
                               'pending', 'committed', 'not_applicable')),
    cleanup_status         TEXT NOT NULL DEFAULT 'nothing_written' CHECK (cleanup_status IN (
                               'nothing_written', 'temp_present', 'temp_deleted', 'delete_failed')),
    CHECK (existence <> 'present_verified' OR (validation_status = 'passed' AND fetch_status = 'fetched')),
    CHECK (existence <> 'present_invalid'
           OR (fetch_status = 'failed_permanent' AND validation_status NOT IN ('pending', 'passed'))),
    CHECK (existence NOT IN ('absent_confirmed', 'absent_inconclusive', 'absent_accepted')
           OR (fetch_status = 'not_applicable' AND commit_status = 'not_applicable')),
    CHECK (commit_status <> 'committed'
           OR (existence = 'present_verified' AND rows_english_valid IS NOT NULL
               AND cleanup_status IN ('nothing_written', 'temp_deleted'))),
    CHECK (md5_source IS NULL OR expected_md5 IS NOT NULL)
);
CREATE INDEX slot_by_day ON slot (utc_day);
CREATE INDEX slot_open ON slot (fetch_status, existence) WHERE commit_status = 'pending';

CREATE TABLE attempt (                                    -- every HTTP request, kept for the retry history
    attempt_id        INTEGER PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES run (run_id),
    batch_ts          TEXT REFERENCES slot (batch_ts),    -- NULL for the master-list request
    kind              TEXT NOT NULL CHECK (kind IN ('head', 'get', 'masterlist_get')),
    attempt_no        INTEGER NOT NULL CHECK (attempt_no >= 1),
    url               TEXT NOT NULL,
    started_at_utc    TEXT NOT NULL,
    elapsed_ms        INTEGER,
    outcome           TEXT NOT NULL CHECK (outcome IN (
                          'response', 'timeout', 'connection_error', 'tls_error', 'redirect_rejected',
                          'body_incomplete', 'aborted_by_budget', 'aborted_by_user')),
    http_status       INTEGER,
    location          TEXT,
    content_length    INTEGER,
    etag              TEXT,
    last_modified_utc TEXT,
    server_date_utc   TEXT,                               -- freshness evidence behind the CDN
    age_seconds       INTEGER,                            -- CDN cache age
    cache_control     TEXT,
    bytes_received    INTEGER NOT NULL DEFAULT 0,
    error_class       TEXT,                               -- exception class name only, never a payload
    backoff_before_s  REAL,
    CHECK (outcome <> 'response' OR http_status IS NOT NULL)
);
CREATE INDEX attempt_by_slot ON attempt (batch_ts, kind, attempt_no);
CREATE INDEX attempt_by_time ON attempt (started_at_utc);

CREATE TABLE slot_series_count (                          -- per theme, per filter version; later versions add rows
    batch_ts         TEXT NOT NULL REFERENCES slot (batch_ts),
    filter_version   TEXT NOT NULL,
    series           TEXT NOT NULL CHECK (series IN ('EQUITY_US', 'RATES_US', 'GOLD')),
    rows             INTEGER NOT NULL CHECK (rows >= 0),             -- member rows, before deduplication
    rows_us_relevant INTEGER NOT NULL CHECK (rows_us_relevant >= 0),
    new_stories      INTEGER CHECK (new_stories >= 0),               -- NULL until the deduplication pass
    PRIMARY KEY (batch_ts, filter_version, series)
) WITHOUT ROWID;

CREATE TABLE day_commit (                                 -- one row per UTC day file written atomically
    utc_day          TEXT NOT NULL,
    filter_version   TEXT NOT NULL,
    parser_version   TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('committed', 'superseded')),
    slots_expected   INTEGER NOT NULL,                    -- 96; 80 on 2026-07-20
    slots_present    INTEGER NOT NULL,
    slots_absent     INTEGER NOT NULL,                    -- confirmed + inconclusive + accepted
    slots_failed     INTEGER NOT NULL,                    -- request_failed + inaccessible + present_invalid
    rows_kept        INTEGER NOT NULL,
    file_relpath     TEXT NOT NULL,                       -- 'filtered/2022/2022-01-03.tsv.gz'
    file_bytes       INTEGER NOT NULL,
    file_sha256      TEXT NOT NULL,
    audit_relpath    TEXT,                                -- 'audit_sample/2022/2022-01-03.tsv.gz'
    audit_sha256     TEXT,
    committed_at_utc TEXT NOT NULL,
    run_id           TEXT NOT NULL REFERENCES run (run_id),
    PRIMARY KEY (utc_day, filter_version, parser_version),
    CHECK (slots_present + slots_absent + slots_failed = slots_expected)
);
```

### 6.4 Where each required field lives

| Requirement | Field(s) |
| --- | --- |
| Source URL and batch timestamp | `slot.url`, `slot.batch_ts`, `slot.nominal_utc` |
| Expected and actual file size | `expected_bytes`, `actual_bytes`, `zip_member_bytes` |
| Available checksum | `expected_md5` + `md5_source` (`master_list`, `etag`, or NULL for none); `actual_md5`, `actual_sha256`, `zip_crc32` |
| Download status | `fetch_status`, `attempts`, `next_attempt_after_utc` |
| HTTP status and retry history | `http_status_last`; one `attempt` row per request, with status, `Date`, `Age`, error class and backoff |
| Parsed row count | `rows_physical`, `rows_malformed`, `rows_date_mismatch` |
| English-language row count | `rows_english_valid`; `rows_translated` must be 0 |
| Filtered row count per theme | `rows_captured`; `slot_series_count` per theme and filter version |
| Near-empty-file warning | `near_empty_flag` and `near_empty_baseline` (causal), plus `backlog_flag` |
| Missing or inaccessible status | `existence` (section 6.1) with `existence_evidence` |
| UTC availability timestamp | `available_at_utc`, `late_flag`, `http_last_modified_utc` |
| Parser and filter versions | `run.*_version`, `slot.*_version`, `day_commit` key |
| Validation status | `validation_status` |
| Cleanup status | `cleanup_status`; `day_commit` records each file's hash |

### 6.5 Schema self-test [VERIFIED; in memory only]

The DDL was compiled once with SQLite 3.45.1 (the project venv). No file was
created and no GDELT data was involved.

- **Created:** 5 tables and 4 indexes.
- **Rejected, 9 of 9 invalid states using placeholder values:**
  - `present_verified` before validation;
  - an absent slot still pending download;
  - an unknown status;
  - a commit while a temporary file exists;
  - a non-numeric stamp;
  - an MD5 source without an MD5;
  - day counts that do not add up;
  - an unknown series;
  - an attempt for a missing slot.
- **Accepted:** the valid commit transition.

**Size** [ESTIMATED]: filled in memory with placeholder rows of realistic width
for all 162,512 slots, 169,000 attempts and 483,000 series rows, the manifest
took 186 MB. With the shard columns added, the estimate is **≈0.2 GB**. This
replaces B2-H's ≈50 MB, which assumed a smaller schema.

---

## 7. Future streaming workflow [PROPOSED; not implemented, not run]

**Preconditions, all required before the first archive request:**

- the capture rule, stored columns and audit-sample rate are frozen (after the
  review);
- the full acquisition is approved;
- your data-allowance answers are recorded and byte budgets are set;
- the code exists in `backend/wealthpilot/data/`, with tests, from a separately
  approved phase;
- you run it (CLAUDE.md: Claude does not run long jobs).

**Step 0, preflight.** No archive traffic.

- **Environment:** the project venv. `zoneinfo` offsets are checked, for example
  2022-01-03 16:00 ET = 21:00 UTC and 2022-07-01 16:00 ET = 20:00 UTC.
- **Disk:** free space at or above the preflight threshold (section 8.3).
- **Git:** `git check-ignore` confirms the output root is ignored.
- **Record:** a `run` row with code, spec and list hashes and the parameters.
- **Clean start:** `tmp/` emptied.

**The twelve required steps:**

1. **Iterate the approved window.**
   - **Range:** 2021-12-01 00:00 → 2026-07-20 19:45 UTC, 162,512 slots.
   - **Order and manifest:** in time order, one manifest row per slot.
2. **Resolve each timestamp, including unlisted ones.**
   - **Fresh list:** download one (≈128.5 MB, counted in the budget) and record
     its MD5, SHA-256 and Last-Modified.
   - **Compare:** diff its window entries against the audited snapshot (160,658
     entries, 860,483,377,717 B, the Appendix B gaps).
   - **Unlisted slots** outside the accepted outage (180 today) get a bounded
     header check:
     - **Two checks, at least 65 minutes apart:** the CDN caches for 3,600 s.
     - **Independence:** each check must show a fresh `Date` and an `Age` of 60 s
       or less.
     - **At most 3 requests per slot.**
   - **Outcomes:**
     - two 404s → `absent_confirmed`;
     - 200 → fetched, with Content-Length and ETag as its size and MD5;
     - cached answers only → `absent_inconclusive`;
     - only transient errors → `request_failed`;
     - another 4xx → `inaccessible`.
   - **June 2025 outage:** recorded as `absent_accepted`, with no request.
3. **Download one batch at a time.**
   - **URL:** directly `https://data.gdeltproject.org/gdeltv2/<ts>.gkg.csv.zip`,
     avoiding the `http://` 301.
   - **Redirects:** at most one, to the identical resource (B2-H's corrected
     guard).
   - **Memory:** the body goes into memory, with a 100 MB guard (largest listed
     file 51.1 MB).
   - **Budget:** checked before each request.
   - **Parallelism:** 2–4 connections only if you decide so after the first few
     hundred files.
4. **Verify checksums and zip integrity.**
   - **Bytes:** byte count equals Content-Length and the expected size.
   - **MD5:** checked against the list or the ETag. "No checksum" is recorded
     when neither exists.
   - **Zip:** exactly one member, named `<ts>.gkg.csv`, with no path part; not
     encrypted; deflate or stored; at most 10× expansion and 400 MB.
   - **CRC-32:** confirmed by reading the member to the end.
   - **On failure:** one re-download, then `present_invalid`.
5. **Parse incrementally.**
   - **Line by line:** bytes from the zip member; each line decoded as strict
     UTF-8.
   - **Row checks:**
     - 27 tab-separated fields;
     - `V2.1DATE` and the record-ID prefix equal the stamp;
     - `TRANSLATIONINFO` blank;
     - collection identifier 1.
   - **Rejects** are counted by reason.
6. **Apply the approved language and theme filters.**
   - **Capture:** the frozen capture rule on valid English rows.
   - **Flags:** company flag, US relevance, flag-only themes.
   - **Series:** membership for the filter version in force.
   - **Duplicates:** within-batch duplicate marks.
   - **Audit sample:** an uncaptured row whose SHA-256(seed + record ID) falls in
     the lowest 1/1,000 of the range is kept, tagged `audit`.
7. **Record counts, near-empty batches and provenance.**
   - **Per slot:** the slot row (counts, `available_at_utc`, late flag,
     versions, HTTP metadata), the `attempt` rows and `slot_series_count`.
   - **Before each day commits:** near-empty and backlog flags, computed causally
     from earlier days.
8. **Write output atomically.**
   - **Shards:** each slot's kept and audit rows go to a shard,
     `tmp/<day>/<ts>.tsv.gz`, which is fsynced and hashed.
   - **Day commit, when every slot of a UTC day is final:**
     1. shards are concatenated in time order into the day files;
     2. the files are fsynced and moved into place with `os.replace`;
     3. they are re-read and hashed;
     4. one SQLite transaction writes `day_commit` and marks the slots
        committed;
     5. the shards are deleted.
9. **Resume safely.**
   - **On start:** `in_progress` returns to `pending`.
   - **Shards:** a shard with a matching SHA-256 is reused, so no re-download is
     needed. A mismatched shard is deleted and its slot reset.
   - **Never touched:** committed days.
   - **Retries:** `retry_wait` times are honoured.
10. **Delete temporary archives after validation.**
    - **Raw bytes never reach disk:** the zip is dropped as soon as its shard is
      written.
    - **If on-disk staging is enabled:** each staged zip is deleted right after
      validation and parsing. A slot cannot commit while its temporary file
      exists; the schema enforces this.
11. **Preserve missingness and coverage.**
    - **Every slot keeps its existence state.** Nothing is zero-filled.
    - **Coverage** per slot, day and forecast origin uses existence plus the
      near-empty flags.
    - **Days with failures still commit,** with the failures counted.
12. **Keep raw and processed data outside Git.**
    - **Everything stays under the ignored root.**
    - **Tracked reports** carry only aggregates and hashes, never titles.

**Step 13, close-out.**

- **Coverage report** per slot, day and forecast origin.
- **Anomaly list:**
  - listed files that answer 404;
  - unlisted files that exist;
  - late files;
  - near-empty, backlog and invalid files.
- **Data-quality statistics.**
- **The eligibility check** of B2-H §6.3.

**Guards throughout:**

- **Byte budgets:** per run, and per billing period summed from
  `attempt.bytes_received`. At the limit, the current slot finishes and the run
  stops cleanly.
- **Disk floor:** 10 GB free, or the run stops.
- **Stop file:** a `STOP` file in the dataset folder ends the run after the
  current slot.
- **Progress log:** throughput, ETA and budget every 60 s. Logs never contain
  titles or secrets.

**Failure handling:**

| Situation | Handling | Manifest |
| --- | --- | --- |
| Timeout, connection error, 5xx, 429 | Up to 5 attempts with backoff of 4–64 s (at most 10 min), honouring `Retry-After`; a final pass at least 65 min later | `retry_wait`, then `request_failed` |
| 404 on a listed slot | Second check at least 65 min later, with a fresh `Date` | `absent_confirmed`, listed as an anomaly |
| 404 only from the cache | Not independent evidence | `absent_inconclusive` |
| Another 4xx, or a redirect elsewhere | No retry | `inaccessible` |
| Size or MD5 mismatch, bad zip, CRC error | One re-download, then stop for that slot | `present_invalid`, with the reason |
| Body above the guard | Transfer aborted | `size_guard_exceeded` |
| Last-Modified after nominal + 15 min | Availability = Last-Modified + 15 min | `late_flag = 1` |
| Rows < 10% of the causal baseline | Kept; missing for coverage | `near_empty_flag = 1` |
| Rows > 3× the causal baseline | Kept at its own time, never back-dated | `backlog_flag = 1` |
| Byte budget or disk floor reached | Current slot finishes; clean stop | `run.outcome` |
| Crash | Restart reuses verified shards | `in_progress` → `pending` |

**Columns of the stored rows** (gzip TSV; standard library only; PROPOSED):

- **Identity and time:** `gkg_record_id`, `batch_ts`, `available_at_utc`.
- **Source:** `source_domain`, `document_url`, `url_canonical`.
- **Title:** `page_title` (local only), `title_hash`, `page_pub_ts_utc`
  (diagnostic only).
- **Tone:** the seven `V1.5TONE` values.
- **Themes:** candidate themes with mention counts; all `ECON_*` codes.
- **Places and organisations:** `country_codes`, `us_location`, US-market
  organisations matched.
- **Matches and flags:** title phrases matched, `company_item`, flag-only themes,
  the three series memberships, `dup_same_batch`.
- **Versions:** `filter_version`, `parser_version`.
- **Optional, your decision:** the full `V1THEMES` string, at ≈2–3× the
  storage.

**The three irreversible choices are fixed before acquisition:** the capture
rule, these columns and the audit rate. Everything else can be recomputed from
stored rows: series rules, flags, story deduplication.

---

## 8. Storage and resource plan

### 8.1 Location and ignore rules [VERIFIED; read-only `git check-ignore --no-index`, nothing created]

| Planned path | Git |
| --- | --- |
| `datasets/raw/gdelt/english_gkg_v1/manifest/…`, `filtered/…`, `logs/…`, `review/…`, `tmp/…` | Ignored by `.gitignore:33` (`datasets/raw/*`) |
| `datasets/raw/gdelt/README.md` | Ignored too, so a README there would not be tracked |
| `datasets/processed/gdelt/…` | **Not ignored**, so not used. Using it would need an approved `.gitignore` change |

### 8.2 Layout [PROPOSED]

```text
datasets/raw/gdelt/english_gkg_v1/          # ignored; nothing created yet
  provenance/    run_<UTC>.json              # code, spec and list hashes; parameters; outcome
                 filter_<version>.yaml       # exact rules applied (+ SHA-256)
                 masterlist_<sha256>.txt     # optional (your decision), ~128.5 MB
  manifest/      manifest.sqlite             # section 6 schema, WAL
  filtered/      <filter_version>/YYYY/YYYY-MM-DD.tsv.gz       # captured rows per UTC day
  audit_sample/  <filter_version>/YYYY/YYYY-MM-DD.tsv.gz       # 1-in-1,000 uncaptured rows
  logs/          run_<UTC>.jsonl[.gz]        # progress and errors; never titles
  review/        b2i_review_v1/
                   raw/<ts>.gkg.csv.zip      # sample batches, kept until the review closes
                   annotation_A.csv  annotation_B.csv  key_sealed.csv
                   adjudication.csv  selection_log.json
  tmp/           <day>/<ts>.tsv.gz           # per-slot shards; emptied at start and end
```

### 8.3 Disk space

**Free space now** [MEASURED, 2026-10-12 19:20 UTC]:

| Drive | Size | Free |
| --- | ---: | ---: |
| C: (holds the repository) | 498.1 GB (463.9 GiB) | **182.8 GB** (170.3 GiB) |
| D: | 524.3 GB (488.3 GiB) | 504.2 GB (469.6 GiB) |

B2-F's "171 GB" and "470 GB" were GiB figures.

**What the plan needs** [ESTIMATED]:

| Item | Size | Basis |
| --- | --- | --- |
| Captured rows, minimal columns + v1 flags | ≈2–5 GB gzip | B2-G: 405 B per row, 2.9× gzip, 6–14% of rows kept |
| … if the full `V1THEMES` string is kept | ≈4–13 GB gzip | B2-F: 2–3× |
| Audit sample (1 in 1,000 uncaptured rows) | ≈0.1 GB raw; ≈30 MB gzip | 177–210 M uncaptured rows × ≈450 B |
| Manifest | ≈0.2 GB | Section 6.5 |
| Logs | ≤0.1 GB per full run; ≈10 MB gzipped | ≈0.33 M JSON lines |
| Temporary | ≤0.2 GB | One day of shards; zips stay in memory |
| Review sample | ≈1.03 GB (+1.03 GB if stage C) | Until the review closes |
| Master-list snapshot (optional) | ≈0.13 GB | |
| **Total** | **≈3–8 GB** (≈5–16 GB with full themes) | |

**Proposed thresholds:**

- **Preflight:** free space at least twice the projected maximum, which is 20 GB
  (35 GB with full themes).
- **Runtime floor:** 10 GB. Below it, the run stops cleanly.

C: passes today. The check is repeated at run time, never assumed.

### 8.4 Retention [PROPOSED]

- **Kept for the life of the research track:** `filtered/`, `audit_sample/`,
  `manifest/`, `logs/` and `provenance/`.
  - **Immutable once committed:** a new filter or parser version writes new
    files and never overwrites.
  - **Deletion:** only on your instruction.
- **`review/`:**
  - **Raw sample zips:** deleted when the review report is accepted, unless you
    keep them.
  - **Annotation files and the sealed key:** kept with the dataset, local and
    never committed.
- **`tmp/`:** emptied at the start and end of every run.
- **Master-list snapshot:** kept or not, your decision. Its SHA-256 is recorded
  either way.
- **Git:** nothing under `datasets/raw/gdelt/` is ever committed.

### 8.5 Safe cleanup procedure [PROPOSED]

1. **Who deletes, and where:** only the acquisition tool, and only inside
   `tmp/` (and `review/<id>/raw/` on your instruction).
2. **Path guard. Refuse:**
   - anything whose resolved path lies outside those folders;
   - any symbolic link;
   - any name outside the expected patterns (`^\d{14}\.gkg\.csv\.zip$`,
     `^\d{14}\.tsv\.gz$`, `*.partial`).
3. **Shards:** deleted only after their day's transaction has committed and the
   day file's SHA-256 has been re-read and matched.
4. **Recording:** every deletion goes into `cleanup_status` and the log. A
   `delete_failed` is retried at the next start.
5. **Never:**
   - recursive deletion;
   - deleting committed outputs;
   - touching other datasets.
6. **End of run:** `tmp/` must be empty, or the run report lists what remains.

### 8.6 Runtime environment [VERIFIED]

- **The need:** the cutoff calculation needs IANA time-zone data. On Windows,
  `zoneinfo` gets it from the `tzdata` package.
- **Project venv:** Python 3.11.9 has `tzdata` 2026.4, as a dependency of pandas
  2.2.3.
- **System Python:** 3.13 lacks it. This phase's frame script failed there and
  ran in the venv.
- **Consequence:** acquisition code must run in the project venv. Declaring
  `tzdata` directly would be a dependency change, for you to approve.

---

## 9. Internet and data-cap checklist

### 9.1 Please confirm (nothing is assumed)

1. **Plan type:** fixed broadband, mobile or hotspot, or satellite. Is it
   metered?
2. **Monthly allowance:** in GB or TB, or "unlimited".
3. **Remaining allowance** this billing period, and the date it resets.
4. **Above the cap:** extra charges, throttling or suspension?
5. **"Unlimited" plans:** is there a fair-use threshold, and what happens beyond
   it (throttling, deprioritisation)?
6. **Off-peak windows** with unmetered or faster use.
7. **Sustained speed,** not the advertised one. Run your provider's or a neutral
   speed test yourself, 2–3 times a day, when the job would run.
8. **Shared use:** other household traffic during the run.
9. **Uptime:** can the machine stay on and awake for several days (sleep
   settings, power, restarts for updates)?
10. **Network path:** a VPN, proxy or metered-connection setting that could slow
    or meter the traffic.
11. **Provider limits** on very long downloads or many requests.
12. **Your ceiling:** the most this job may use per day or per billing period.
    This becomes the byte budget.

### 9.2 Volume on the wire [VERIFIED payload; ESTIMATED overhead]

| Item | Volume |
| --- | --- |
| Minimal-window payload: 160,658 listed files + 1 unlisted file | 860,490,716,162 B = 0.8605 TB (0.7826 TiB) |
| With 1–5% protocol and retry overhead | **0.869–0.904 TB** |
| Fresh master list at acquisition | ≈128.5 MB |
| Review sample, if approved | ≈1.03 GB (stage D), +≈1.03 GB (stage C, only if triggered) |
| Header checks | ≈0.5 MB (about 360–540 requests) |

### 9.3 Time [ESTIMATED]

| Sustained throughput | Pure transfer (0–5% overhead) | One file at a time (+1.1–1.4 s per file) |
| --- | --- | --- |
| 10 Mbit/s | 191–201 h (8.0–8.4 days) | 240–263 h (10.0–11.0 days) |
| 25 Mbit/s | 77–80 h (3.2–3.3 days) | 126–143 h (5.2–5.9 days) |
| **41–44 Mbit/s** (B2-G, measured once) | 44–49 h | 93–111 h (3.9–4.6 days) |
| 50 Mbit/s | 38–40 h | 87–103 h (3.6–4.3 days) |
| 100 Mbit/s | 19–20 h | 68–83 h (2.8–3.4 days) |
| 250 Mbit/s | 7.6–8.0 h | 57–71 h (2.4–2.9 days) |
| 500 Mbit/s | 3.8–4.0 h | 53–67 h (2.2–2.8 days) |

**How to read these:**

- **Latency dominates one-file-at-a-time downloading.** The 1.1–1.4 s per
  request measured in B2-G adds 49–62 h on its own, whatever the speed.
- **Parallel connections:** 2–4 would overlap most of that latency, if GDELT's
  server allows [UNVERIFIED]. This is your decision (section 10).
- **Not included in these times:**
  - retries beyond the assumed overhead;
  - changes in latency;
  - throttling by your provider or by GDELT;
  - machine sleep or restarts;
  - pauses forced by a byte budget.
- **Real time can be longer.** These are planning ranges, not promises.

### 9.4 Spreading the download over billing periods [ESTIMATED]

The run can stop at a byte budget and resume in the next period. Periods needed
= 0.87–0.90 TB ÷ budget, rounded up.

| Budget for this job per period | Periods needed |
| --- | --- |
| 150 GB | 6–7 |
| 300 GB | 3–4 |
| 450 GB | 2–3 |
| 900 GB | 1–2 |

The fresh master list and any review sample come out of the same budget.

---

## 10. Outstanding approval decisions

**Before any labelling:**

1. **The review protocol:**
   - the rubric, including its judgement calls: inflation and jobs data are `RL`
     for rates without a rates framing; local gold rates are `RL`; single
     companies are `RL`;
   - the cells and sizes, the estimators and the decision thresholds
     (section 4.7);
   - the pre-registered batch lists.
2. **Download of stage D:** 192 training-period files, ≈1.03 GB, listed in
   Appendix A. Stage C would need your approval when its pre-registered trigger
   fires.
3. **Annotators:**
   - **Option A:** you alone, with a 10% re-label after 7 days;
   - **Option B:** you plus a second person on a 20% overlap;
   - **Option C:** Claude as a disclosed second annotator.
4. **Implementation phase:** the parser, `gdelt_filter_v1` and the manifest
   code in `backend/wealthpilot/data/`, with tests, written once and reused by
   the review and the acquisition.

**Before any full acquisition:**

1. **Freeze the irreversible choices:**
   - the capture rule (v1, or widened after the review);
   - the stored columns: is the full `V1THEMES` string kept?
   - the audit-sample rate (1 in 1,000 proposed).
2. **Your checklist answers** (section 9.1). They set the byte budget per
   period and the per-run cap.
3. **Concurrency:** one at a time (the default), or 2–4 after the throughput
   check.
4. **Still pending from B2-H:**
   - the 13:00 ET early-close rule;
   - the missing-data thresholds (0.75 primary; 0.50 and 0.90 sensitivity).
5. **Storage and retention** (section 8.4):
   - whether to keep the master-list snapshot;
   - when to delete the review sample;
   - whether label files stay local or are tracked without titles.
6. **Full acquisition of the minimal window.**
7. **The ADR,** B2's proposed ADR-043. It is written only after that approval.

**Unchanged:** title redistribution is still [UNVERIFIED], so titles stay local.

---

## 11. Exact next steps

**Nothing below starts without your instruction.**

1. **You review sections 3–4** and approve or edit:
   - the rubric;
   - the decision thresholds;
   - the annotator arrangement.

   Edits are made now, before any title is seen.
2. **You answer the section 9.1 checklist.**
3. **Implementation phase** (approved separately). It writes:
   - the GKG parser, `gdelt_filter_v1` (with S1 and S2) and the manifest module;
   - a review tool that fetches the Appendix A list (headers, then bodies),
     checks integrity, assigns cells and builds the blinded files;
   - tests on synthetic fixtures.
4. **Stage D:**
   1. download, about 1.03 GB in minutes at the measured rate;
   2. label;
   3. measure agreement;
   4. lock the label files;
   5. unseal the key;
   6. estimate;
   7. report aggregates only.
5. **Decide under section 4.7:**
   - freeze v1, or revise once and confirm on stage C;
   - settle the capture rule, the columns and the audit rate.
6. **Full acquisition decision.** Then the ADR. Then you run the acquisition,
   within the agreed budgets.
7. **Afterwards:**
   - the duplicate audit (section 4.11);
   - the coverage and eligibility report.

   B3 is considered only after that, and only with approval.

---

## Appendix A — Pre-registered review batches (UTC stamps)

**Blocks** (slots per block; known-absent slots in the block):

| Block | First slot | Last slot | Slots | Known absent |
| --- | --- | --- | ---: | ---: |
| B01 | 20211201000000 | 20220101203000 | 3,059 | 0 |
| B02 | 20220101204500 | 20220202173000 | 3,059 | 1 |
| B03 | 20220202174500 | 20220306143000 | 3,060 | 0 |
| B04 | 20220306144500 | 20220407111500 | 3,059 | 0 |
| B05 | 20220407113000 | 20220509081500 | 3,060 | 0 |
| B06 | 20220509083000 | 20220610050000 | 3,059 | 1 |
| B07 | 20220610051500 | 20220712020000 | 3,060 | 0 |
| B08 | 20220712021500 | 20220812224500 | 3,059 | 0 |
| B09 | 20220812230000 | 20220913194500 | 3,060 | 0 |
| B10 | 20220913200000 | 20221015163000 | 3,059 | 0 |
| B11 | 20221015164500 | 20221116133000 | 3,060 | 2 |
| B12 | 20221116134500 | 20221218101500 | 3,059 | 0 |
| B13 | 20221218103000 | 20230119070000 | 3,059 | 1 |
| B14 | 20230119071500 | 20230220040000 | 3,060 | 0 |
| B15 | 20230220041500 | 20230324004500 | 3,059 | 147 |
| B16 | 20230324010000 | 20230424214500 | 3,060 | 2 |
| B17 | 20230424220000 | 20230526183000 | 3,059 | 4 |
| B18 | 20230526184500 | 20230627153000 | 3,060 | 3 |
| B19 | 20230627154500 | 20230729121500 | 3,059 | 1 |
| B20 | 20230729123000 | 20230830091500 | 3,060 | 1 |
| B21 | 20230830093000 | 20231001060000 | 3,059 | 1 |
| B22 | 20231001061500 | 20231102030000 | 3,060 | 2 |
| B23 | 20231102031500 | 20231203234500 | 3,059 | 3 |
| B24 | 20231204000000 | 20240104204500 | 3,060 | 0 |

**Reading the lists:** each line is one block's stamps for rounds 1–8 (stage D)
or 9–16 (stage C), in round order. The SHA-256 digests in section 4.2 are taken
over the stamps in selection order: round 1 for B01–B24, then round 2, and so on.

**Stage D (rounds 1–8):**

```text
B01 20211202210000 20211211044500 20211219031500 20220101083000 20211217171500 20211210031500 20211215194500 20211206151500
B02 20220116234500 20220108181500 20220130143000 20220115230000 20220104173000 20220119101500 20220125191500 20220111071500
B03 20220207140000 20220212203000 20220304223000 20220219081500 20220305044500 20220205031500 20220223171500 20220222230000
B04 20220324110000 20220328163000 20220319033000 20220406233000 20220403193000 20220327183000 20220323100000 20220315223000
B05 20220502110000 20220415151500 20220413180000 20220414063000 20220407193000 20220508220000 20220508181500 20220413071500
B06 20220609233000 20220517154500 20220515224500 20220510031500 20220529084500 20220510160000 20220604181500 20220512223000
B07 20220625171500 20220620000000 20220702183000 20220614023000 20220610194500 20220614170000 20220622233000 20220626174500
B08 20220808130000 20220731041500 20220812070000 20220811210000 20220811031500 20220716220000 20220730044500 20220718140000
B09 20220820143000 20220831100000 20220826033000 20220826190000 20220816010000 20220910223000 20220822091500 20220905233000
B10 20221005210000 20221002150000 20220920173000 20220918213000 20220925024500 20220920004500 20220915151500 20220929083000
B11 20221114084500 20221107121500 20221115001500 20221022161500 20221104031500 20221107090000 20221030164500 20221026100000
B12 20221201104500 20221201101500 20221203141500 20221127170000 20221121161500 20221210003000 20221118093000 20221128111500
B13 20221225041500 20230112230000 20221221214500 20221226110000 20221224203000 20221230083000 20221221073000 20221229093000
B14 20230123170000 20230210114500 20230120133000 20230205021500 20230126144500 20230130070000 20230120094500 20230128141500
B15 20230220141500 20230314104500 20230305053000 20230223101500 20230304021500 20230228113000 20230319054500 20230319191500
B16 20230423030000 20230326111500 20230328051500 20230411000000 20230423080000 20230324231500 20230324114500 20230410073000
B17 20230513231500 20230429221500 20230427010000 20230516060000 20230513093000 20230514223000 20230515221500 20230513193000
B18 20230605193000 20230529164500 20230618234500 20230626111500 20230611134500 20230602184500 20230620084500 20230601041500
B19 20230703164500 20230718013000 20230727134500 20230629040000 20230719033000 20230720000000 20230708140000 20230702110000
B20 20230804233000 20230823091500 20230807000000 20230827194500 20230730171500 20230823051500 20230816124500 20230804174500
B21 20230908030000 20230921170000 20230903064500 20230911084500 20230831131500 20230907043000 20230923000000 20230907014500
B22 20231101100000 20231029231500 20231023163000 20231029103000 20231031203000 20231023174500 20231101083000 20231015120000
B23 20231203111500 20231113024500 20231120204500 20231118083000 20231104064500 20231130080000 20231114130000 20231102181500
B24 20231215223000 20231224031500 20231205104500 20231222134500 20231221060000 20231209103000 20231219141500 20231207091500
```

**Stage C (rounds 9–16), fetched only if triggered (section 4.7):**

```text
B01 20211226184500 20211209163000 20211207161500 20211203011500 20211219204500 20211220100000 20211227230000 20211211211500
B02 20220201010000 20220202013000 20220125181500 20220102094500 20220120180000 20220111214500 20220125050000 20220118111500
B03 20220226013000 20220210174500 20220216003000 20220228214500 20220223023000 20220228124500 20220217213000 20220208153000
B04 20220404223000 20220312141500 20220401094500 20220318031500 20220313204500 20220404203000 20220323073000 20220313063000
B05 20220411120000 20220426181500 20220430030000 20220418174500 20220505033000 20220509044500 20220425081500 20220502070000
B06 20220518203000 20220609011500 20220601084500 20220527120000 20220602204500 20220515130000 20220511031500 20220522170000
B07 20220615184500 20220613100000 20220619091500 20220710174500 20220611051500 20220618184500 20220712010000 20220705181500
B08 20220714144500 20220804224500 20220719061500 20220725040000 20220807040000 20220714093000 20220810131500 20220809080000
B09 20220912034500 20220826184500 20220903074500 20220902081500 20220823031500 20220819211500 20220829224500 20220816130000
B10 20220915233000 20220923184500 20220921061500 20220919094500 20220914184500 20220925063000 20221010151500 20221010084500
B11 20221103091500 20221101211500 20221029170000 20221028234500 20221029211500 20221102201500 20221115223000 20221115213000
B12 20221120201500 20221120144500 20221209043000 20221212143000 20221215160000 20221217093000 20221207201500 20221119200000
B13 20230111094500 20221229201500 20221224190000 20221220024500 20221221070000 20221221003000 20230104060000 20221227181500
B14 20230120054500 20230206071500 20230204221500 20230216201500 20230201001500 20230120093000 20230202054500 20230220020000
B15 20230313071500 20230226203000 20230311220000 20230309101500 20230226120000 20230223084500 20230226044500 20230320234500
B16 20230407161500 20230330221500 20230420194500 20230411050000 20230408154500 20230424020000 20230409074500 20230404073000
B17 20230505051500 20230428141500 20230427230000 20230524000000 20230515090000 20230510164500 20230513174500 20230509113000
B18 20230617140000 20230610154500 20230610031500 20230613154500 20230617154500 20230606141500 20230609191500 20230602084500
B19 20230702034500 20230629161500 20230716233000 20230726230000 20230715184500 20230704193000 20230719143000 20230711060000
B20 20230825084500 20230806044500 20230813081500 20230810141500 20230824160000 20230824103000 20230816111500 20230806094500
B21 20230919213000 20230909080000 20231001044500 20230922163000 20230912124500 20230916054500 20230923034500 20230924160000
B22 20231017123000 20231012174500 20231006033000 20231006193000 20231017204500 20231029184500 20231010144500 20231013160000
B23 20231119041500 20231128214500 20231108054500 20231115183000 20231118084500 20231128061500 20231109050000 20231103021500
B24 20231224021500 20231221174500 20231227021500 20231226154500 20231231120000 20240103064500 20231230140000 20231205001500
```

---

## Appendix B — Absent slots in the minimal window [VERIFIED]

**Source:** the audited master list (snapshot SHA-256 `7e5d2c2e…`), corrected by
B2-H's header checks.

**Totals:** 1,853 slots in 50 runs. Single stamps unless a range is shown;
counts in brackets.

**Re-checked by header at acquisition (48 runs, 179 slots):**

```text
2022  20220117124500  20220519211500  20221105141500  20221108223000
2023  20230101201500  20230308093000  20230309000000  20230311023000  20230311173000  20230312031500
      20230314053000  20230314203000  20230316021500  20230319051500  20230321220000
      20230321223000-20230321224500 (2)  20230321233000-20230322000000 (3)  20230322004500
      20230322013000  20230322040000  20230322044500-20230323124500 (129)
      20230414103000  20230422023000  20230502101500  20230522174500  20230523061500  20230526141500
      20230530141500  20230609023000  20230611033000  20230724171500  20230829084500  20230905204500
      20231017143000  20231024064500  20231102110000  20231109004500  20231111184500
2024  20240703181500  20240901231500
2025  20250105091500  20250311064500  20250327100000  20250424213000  20250429110000  20250503003000
      20250506134500
2026  20260509233000 (B2-H inconclusive: cached 404 only)
```

**Accepted as missing, never requested (2 runs, 1,674 slots):**

```text
20250612181500-20250612201500 (9)
20250614180000-20250702020000 (1,665)
```

**Present though unlisted (B2-H):** `20220207190000`; 7,338,445 B; ETag
`8ef2936c0c8c12f111eea3976717da2b`.

**Present but near-empty** (size rule; 4 runs, 86 slots):

- `20221110220000`–`20221111183000` (83);
- `20221231174500`;
- `20230321221500`;
- `20230321230000`.

---

## Sources

**No web source was accessed in this phase.** Facts carried forward cite the
earlier reports.

- **GDELT terms of use,** as verified in B2 §4.3 and §5:
  <https://www.gdeltproject.org/about.html>.
- **GKG 2.1 codebook,** as used in B2-F and B2-G:
  <http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf>.
- **Archive file pattern** (no request made):
  `https://data.gdeltproject.org/gdeltv2/<YYYYMMDDHHMMSS>.gkg.csv.zip`.
- **Repository,** read-only:
  - the B2 to B2-H reports;
  - `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`;
  - `docs/DECISIONS.md`;
  - `docs/MEMORY.md`;
  - `.gitignore`.

---

## Verification of this phase

**Files created:** this report.

**Files modified:**

- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`: a B2-I findings note;
- `docs/MEMORY.md`: the track status;
- `reports/phaseB2H_pre_acquisition_readiness.md`: a superseded-in-part note only.
  The body is unchanged.

**Network activity:** none. No archive file, sample, master list or
translated-stream file was downloaded, and no header check was made.

**Database:** not accessed.

**Local read-only checks:**

- git status: unchanged from the end of B2-H before this phase's edits;
- `git check-ignore` on planned paths;
- free disk space;
- the `pip freeze` fingerprint, `3393be50…`, unchanged;
- `training/`, `models/`, `.gitignore` and the dependency manifests: no
  difference from HEAD.

**Analysis files** (in the session scratch folder, outside the repository):

- `b2i_sampling_frame.py` and `.json`;
- `b2i_manifest_v1.sql`, `b2i_manifest_check.py`, `b2i_manifest_size.py`.

They read only saved B2-G and B2-H summaries.

**Not done:**

- no account, billing or paid service;
- no dependency or lockfile change;
- no application, API, migration, model, training-script or market-data change;
- no data directory;
- no sentiment, feature, B3 or blockchain work;
- no ADR.

**Tests:** none run, because no code changed.
