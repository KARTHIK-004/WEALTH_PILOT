# Research Enhancement Track — Phase B2-H: GDELT Pre-Acquisition Readiness Gate

**Type:** verification and research-design preparation only. **Full acquisition
is NOT approved.** B3 and blockchain work have not started.

**What this phase did:**

- 180 header-only availability checks: no archive body, no other download.
- Read-only database queries.
- Official calendar documentation.

**What it did not change:** no dependency, `.gitignore`, application code,
schema, model, training script or market data, and no data directory created.

**Date:** 2026-10-12 (UTC). All web sources were accessed on this date.

**Builds on:**

- `reports/phaseB2G_gdelt_pilot_audit.md` (B2-G);
- `reports/phaseB2F_gdelt_acquisition_feasibility.md` (B2-F);
- `reports/phaseB2_historical_news_source_evaluation.md` (B2);
- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`.

**Labels:**

- **[VERIFIED]**: confirmed from official documentation, the audited master
  list, the repository, a read-only database query, or a header-only check.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed from verified inputs plus stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not yet available.

> **Superseded in part by Phase B2-I (2026-10-12):**
> `reports/phaseB2I_filter_review_and_acquisition_preparation.md`. This report is
> kept as written. Three points changed.
>
> 1. **Labelled evaluation (section 4.5).** The acquisition never stores
>    uncaptured rows, so its missed-item sample cannot be drawn afterwards. B2-I
>    replaces it with a pre-registered review of a raw training-period sample,
>    run before the capture rule is frozen.
> 2. **Decisions taken since:**
>    - the minimal window, so no holdout (section 8);
>    - the June 2025 outage accepted without further checks (section 9);
>    - filters approved for labelled review only.
> 3. **Manifest and layout (section 7).** The B2-I schema is estimated at
>    ≈0.2 GB, not ≈50 MB. The layout adds `logs/`, `audit_sample/` and `review/`,
>    and downloads default to one batch at a time.

---

## 1. Executive summary

- **The 180 unchecked absent slots are resolved** [VERIFIED]:
  - **178** are confirmed absent, each by two separately dated 404 responses.
  - **1** exists on the server although the master list omits it:
    `20220207190000` (7,338,445 B, written at 18:51:02, nine minutes before its
    batch time).
  - **1** is inconclusive but likely absent: all three answers were the same
    cached 404.
  - **The master list is therefore not a complete index.** The acquisition must
    check unlisted grid slots itself.
- **Coverage of the minimal window** [VERIFIED from the audited list and stored
  calendar]:
  - **98.86%** of the 162,512 slots present; 1,853 absent in 50 contiguous runs;
    86 near-empty files.
  - First training window: 99.64% slot coverage; 3 of 504 forecast days under
    50%.
  - Test period: 98.10%; 12 of 630 days under 90%, 10 with no news at all.
  - Embargo, lookback and the unused 37-day tail: 100%.
- **Early closes are now documented** [VERIFIED].
  - NYSE Group's official press releases list nine 1:00 p.m. ET early closes in
    the window, all with full news coverage.
  - The stored trading calendar matches the official holiday tables for
    2022–2026. It also contains one unscheduled weekday closure (2025-01-09).
- **The evaluation basis is fingerprinted, not changed** [VERIFIED].
  - `market_data` snapshot SHA-256 `563afd21…` (5 instruments × 1,177 rows).
  - Hashes of 22 market model artefacts, `metrics.json` and 8 training files.
  - **No holdout is defined anywhere.**
- **Filters:** a frozen specification `gdelt_filter_v1` is proposed (section 4).
  - The broad stock-market theme is no longer enough on its own.
  - Noisy themes become stored flags only.
  - Company-level notices are flagged.
  - Duplicates are resolved causally, at story level.
  - No precision or recall is claimed. A labelled evaluation is proposed.
- **Theme volume:** it cannot be reliably estimated without processing the
  archive.
  - Equity and rates look ample: thousands of candidate rows a day.
  - Gold is the risk: perhaps 70–360 candidate rows a day, a very low-confidence
    figure.
  - A pre-registered eligibility rule is proposed.
- **Recommendation:**
  - **Acquire the minimal window (0.860 TB).** The current evaluation design
    supports only that.
  - **Take the holdout window (0.882 TB) only if you now designate** the 37-return
    tail as a pre-registered final holdout. It costs +21.6 GB (+2.5%) and has no
    gaps.
  - **Six decisions remain open** (section 9). No full download happens until
    you approve.

---

## 2. Repository state verified

| Check | Result | Label |
| --- | --- | --- |
| Git status vs end of B2-G | Unchanged | [VERIFIED] |
| Reports and docs read | B2-G, B2-F, B2, the architecture doc and `MEMORY.md` exactly as B2-G left them. `DECISIONS.md` ends at ADR-042 and has no GDELT ADR | [VERIFIED] |
| `datasets/` | Only `raw/` (FAR-Trans, kaggle, `.gitkeep`) and `generated/`; no `gdelt` or `processed` folder | [VERIFIED] |
| `.gitignore` | `datasets/raw/*` (line 33) still ignores any future `datasets/raw/gdelt/…` | [VERIFIED] |
| Holdout definition | Searched `training/market/`, `models/metrics.json`, `docs/PROJECT_PLAN.md`, `docs/ARCHITECTURE.md`: **no holdout is defined** | [VERIFIED] |

---

## 3. Missing-slot verification: the 180 authorised header checks

### 3.1 Which slots

- **Derivation** [VERIFIED]: the 1,854 slots absent from the audited master list
  (snapshot SHA-256 `7e5d2c2e…`, B2-G), minus the 1,674 June 2025 outage slots
  that B2-F established by header checks. That leaves exactly 180.
- **Never checked before:** none of the 180 appears in any B2/B2-F/B2-G check.
  The script asserts this.
- **URLs:** the master list's own pattern,
  `http://data.gdeltproject.org/gdeltv2/<stamp>.gkg.csv.zip`.

### 3.2 Bounded policy, as run [VERIFIED]

**Method:**

- HTTP HEAD only.
- At most one redirect, followed only to the identical resource over HTTPS.
- **Pass 1:** every slot.
- **Pass 2:** every slot again, at least 60 s later.
- **Pass 3:** at least 60 s after pass 2, only for slots without two independent
  answers.

At most three attempts per slot.

**Classification:**

| Class | Rule |
| --- | --- |
| Confirmed absent | 404 at least twice and never 200 |
| Present (unlisted) | 200 at least twice and never 404 |
| Transient failure | Only network errors, 5xx or 429 |
| Inaccessible | Only other 4xx, or unexpected redirects |
| Inconclusive | Anything else |

**First run (disclosed): no availability information.**

- The server answers every `http://` request with a **301 to
  `https://data.gdeltproject.org:443/…`**, the same URL with an explicit default
  port.
- My redirect guard compared strings exactly and rejected that form. All 540
  requests therefore stopped at the redirect: 3 passes × 180, all 301, no body.
- I corrected the guard to compare scheme, host, port (443 or default) and path,
  and re-ran the same bounded policy once.

### 3.3 Results [VERIFIED]

| Classification | Slots | Evidence |
| --- | ---: | --- |
| **Confirmed absent** | **178** | 404 on both passes, each response freshly dated (server `Date` within 0–1 s of the check, different on each pass). The 404 object is empty: Content-Length 0, ETag `d41d8cd9…` = MD5 of empty input |
| **Present but not listed** | **1** | `20220207190000`: 200, Content-Length **7,338,445**, Last-Modified **2022-02-07 18:51:02 GMT** (8:58 before its nominal time, the normal pattern), ETag `8ef2936c0c8c12f111eea3976717da2b`. The first answer was fresh; the repeats were served from cache |
| **Inconclusive, likely absent** | **1** | `20260509233000`: three 404s, all the same cached response (`Date` 18:29:34, `Age` up to 1,657 s). Only one origin observation exists. The list also omits it |
| Transient failure / inaccessible | 0 | — |

**The CDN cache affected the confirmations** [VERIFIED].

- **What the headers show:** responses carry `Cache-Control: public,
  max-age=3600`.
- **Client no-cache is ignored:** pass 3 was attempted for the 2 slots without
  independent answers, with `Cache-Control: no-cache`. The CDN ignored it and
  served the cache again, with `Age` 158 s and 1,657 s.
- **Consequence:** an independent re-check of the same URL needs more than an
  hour between attempts.

**HTTP requests in B2-H:**

| Run | Requests |
| --- | ---: |
| First run (redirect only) | 540 |
| Corrected run (2 passes × 180 slots × 2 hops) | 720 |
| Pass 3 (2 slots × 2 hops) | 4 |
| **Total** | **1,264** |

All were header-only and all were for the 180 authorised slots.

### 3.4 What changes [VERIFIED]

- **Coverage:** absent slots in the window fall from 1,854 to **1,853**, and
  present files rise to **160,659**. The recovered slot is a training-period
  forecast day (2022-02-07), which now has full coverage.
- **The master list is not a complete index.** It omits at least one published
  file, so absence from the list does not prove absence from the server. The
  acquisition must therefore:
  - check each unlisted grid slot with a bounded header check;
  - fetch any that exist, verifying them by ETag and the zip's internal CRC,
    because the list gives no MD5 for them (section 7).
- **The June 2025 outage is not checked slot by slot.** Of its 1,674 slots, B2-F
  checked **441** individually: hourly, at the edges, and in samples. The other
  **1,233** sit inside runs bounded by checked 404s and are absent from the list.
  - Every checked slot agreed.
  - Given one unlisted file elsewhere, a published file inside the outage is
    unlikely but not ruled out.
  - Checking them needs about 1,233 more header-only checks. That was not
    authorised and was not done.

---

## 4. Proposed frozen filter specification: `gdelt_filter_v1` [PROPOSED; not approved]

**Design principles:**

- **Capture broadly; define series narrowly.**
  - Acquisition stores every candidate row with flags, because re-downloading
    costs 0.86 TB.
  - Only the **series definitions** feed B3.
- **Freezing:** frozen means fixed once approved. Any change becomes a new
  version, applied to the whole window.
- **What informed it:**
  - B2-G's qualitative reading of one batch's titles;
  - the codebook;
  - the GDELT theme lookup.
- **What did not:** market returns or forecast results.
- **Claims:** no precision or recall is claimed (section 4.5).

### 4.1 Row validity and derived fields

```yaml
version: gdelt_filter_v1            # PROPOSED
stream: GDELT 2.0 English GKG, <YYYYMMDDHHMMSS>.gkg.csv.zip  # never *.translation.gkg.csv.zip
row_validity:                       # failing rows are counted in the manifest, never kept
  - exactly 27 tab-separated fields (LF-terminated)
  - V2.1DATE == the file's stamp
  - GKGRECORDID matches ^<stamp>-[0-9]+$          # no translated-record marker
  - V2.1TRANSLATIONINFO == ""                     # codebook: blank for English originals
  - V2SOURCECOLLECTIONIDENTIFIER == "1"           # web
derived:
  title: html.unescape(text of <PAGE_TITLE> in V2EXTRASXML), "" if absent
  title_norm: NFKC -> casefold -> every character outside [a-z0-9&$] -> space -> single spaces -> strip
  title_hash: sha256(title_norm); null if len(title_norm) < 20 (generic or short titles never merge stories)
  url_canonical: lower-case host; drop scheme, leading "www.", query, fragment, trailing "/"
  themes: set(V1THEMES split ";") minus ""        # V1 and V2 agree on all candidate themes (B2-G)
  mentions: count of V2ENHANCEDTHEMES entries per theme ("THEME,offset")
  orgs: set(V1ORGANIZATIONS split ";")             # delivered lower-case (B2-G)
  us_location: any V1LOCATIONS entry with type in {2 US state, 3 US city} or country code "US"
  tone, positive, negative, polarity, activity_density, self_group_density, word_count: V1.5TONE fields 1-7
  page_pub_ts: <PAGE_PRECISEPUBTIMESTAMP>          # diagnostic only, never availability
phrase_match: a phrase matches title_norm only as whole words (start/end or a space on both sides)
```

### 4.2 Flags

**`company_item`** (company-level and fund-level notices). It is set when **any**
of the following matches:

- the **raw** title contains an exchange-ticker tag: `(nasdaq:`, `(nyse:`,
  `(nysearca:`, `(nyseamerican:`, `(lon:`, `(tsx:`, `(otcmkts:`;
- the raw title contains a cashtag matching `$[A-Z]{1,5}`;
- `title_norm` contains: "shares bought by", "shares sold by", "stake in",
  "position in", "price target", "coverage initiated", "reiterated",
  "upgraded", "downgraded", "insider buys", "insider sells", "insider acquires",
  "insider purchases", "director buys", "director sells".

These patterns were taken from the notice styles B2-G observed: holdings notices,
analyst ratings, insider trades.

**Flag-only themes.** These are stored but are never series members in v1:

| Theme | Why flag-only |
| --- | --- |
| `WB_2936_GOLD` | 0 of 8 titles read were gold-market news |
| `ECON_INFLATION`, `ECON_DEBT`, `WB_1045_TREASURY`, `ACT_YIELD` | The broad rates themes; 0 of 8 market items when they appeared alone |
| `EPU_CATS_MONETARY_POLICY` | An umbrella: present on every rates-core row in B2-G |
| `ECON_IPO`, `ECON_EARNINGSREPORT`, `ECON_BUBBLE` | Company-level |

### 4.3 Capture rule (what is stored)

A valid row is stored if **any** of these holds:

- `themes` contains any series theme or flag-only theme;
- `title_norm` contains any series phrase;
- `orgs` contains a `US_MARKET_ORGS` entry.

All flags and series memberships are stored with the row. Nothing is deleted
except invalid rows, which are counted.

### 4.4 Series definitions (what B3 may use)

```yaml
us_relevant: us_location
             or orgs ∩ US_MARKET_ORGS
             or title_norm has any of [wall street, nasdaq, federal reserve, fomc, s&p 500, dow jones, u s,
                                       us economy, us stocks, us treasury, us treasuries, us inflation]
US_MARKET_ORGS (exact org entries): [nasdaq, new york stock exchange, federal reserve,
                                     federal open market committee, securities and exchange commission]

EQUITY_US:     # ^IXIC, ^NDX, QQQ
  member: not company_item and (
            title_norm has [nasdaq, nasdaq 100, wall street, s&p 500, dow jones, us stocks, u s stocks]
            or ((mentions[ECON_STOCKMARKET] >= 2 or title_norm has [stock market, stock markets, equities])
                and us_relevant))
RATES_US:      # AGG
  member: not company_item and (
            title_norm has [federal reserve, fomc, treasury yield, treasury yields, us treasuries, u s treasuries]
            or ((themes ∩ RATES_SPECIFIC or title_norm has [bond yield, bond yields, bond market, bond markets,
                                                            rate hike, rate hikes, rate cut, rate cuts,
                                                            interest rate, interest rates])
                and us_relevant))
  RATES_SPECIFIC: [ECON_INTEREST_RATES, ECON_CENTRALBANK, EPU_POLICY_INTEREST_RATES, EPU_POLICY_INTEREST_RATE,
                   EPU_POLICY_MONETARY_POLICY, WB_444_MONETARY_POLICY, WB_1125_INTEREST_RATE_POLICY,
                   ECON_SOVEREIGN_DEBT, WB_335_GOVERNMENT_BOND_MARKETS, WB_333_NON_GOVERNMENT_BOND_MARKETS]
GOLD:          # GLD (a global market: no US requirement; us_relevant is still stored)
  member: not company_item and (ECON_GOLDPRICE in themes
            or title_norm has [gold price, gold prices, price of gold, spot gold, gold futures, bullion,
                               gold market, gold markets])
```

**How the B2-G findings are reflected:**

- **`ECON_STOCKMARKET` alone no longer qualifies.** It needs at least two
  mentions plus US relevance, or an explicitly US equity-market title. This
  follows the finding that about half of its titles were unrelated.
- **The bare "bond(s)" keyword is dropped.** B2-G found catastrophe bonds and
  bond-ETF notices under it.
- **Non-US central-bank news needs US relevance.**
- **`ECON_GOLDPRICE` stays the gold anchor**, despite its low volume.
- **Excluded words:** the pronoun "us" is never matched (only "u s" from "U.S."
  and multi-word phrases), nor is "fed".

**Pre-registered sensitivity variants.** Fixed now; none is chosen by results.

| Variant | Definition |
| --- | --- |
| S1, broad | B2-F's original rule: any core theme, single mention, no company exclusion |
| S2, title-only | The title phrases alone |
| S3, article-level | Counts without story deduplication |

### 4.5 No precision or recall claimed: labelled evaluation [PROPOSED]

**When:** before B3 uses any series.

**Steps:**

1. **Sample:** draw about 100 stored titles per series at random, only from
   training-period batches (forecast origins up to 2024-01-04).
2. **Precision:** a person labels each as relevant or not. Report precision with
   Wilson 95% intervals.
3. **Missed items:** draw a further random sample of *uncaptured* rows that
   contain weak cues ("stock", "gold", "bond", "yield"), to estimate what the
   rules miss.

**Rule for changes:** none may be made after any test-period data has been
examined. A change after labelling is a new version, applied to the whole window.

### 4.6 Duplicates and cross-batch updates [PROPOSED]

All state is causal. Rows are processed in availability order:
`available_at_utc`, then the `GKGRECORDID` sequence. A row can only be marked by
earlier rows, never by later ones.

| Case | Rule | Stored as |
| --- | --- | --- |
| Same `url_canonical` twice in one batch | Keep the lowest sequence number | `dup_same_batch` |
| `url_canonical` seen in an earlier batch, same content signature (`title_hash`, `word_count`) | A re-observation, not a new item | `reobservation_of` = first record ID |
| `url_canonical` seen earlier, **different** signature | An **update**: a new version at its own availability time. The earlier version is never edited | `update_of` = first record ID |
| New URL, `title_hash` already seen within the previous 72 h (by availability) | A syndicated copy of an earlier story | `story_id` = first occurrence's record ID |
| Title too short or empty (`title_hash` null) | Never merged into a story | its own `story_id` |

**Primary counting unit:** a story, counted once at its first availability.
Updates are counted separately and enter only the sensitivity variants. This
matters because B2-G found 17.8% of rows repeating a title within one batch.
Cross-batch duplicate rates are still [UNVERIFIED] and will be measured by the
acquisition.

---

## 5. Frozen evaluation protocol

### 5.1 Frozen inputs [VERIFIED; fingerprinted read-only; nothing changed]

**`market_data` table:** 5 instruments × 1,177 rows = 5,885 rows, 2022-01-03 →
2026-09-11, loaded 2026-09-13/14.

**There are no market-data files.** The market data exists only in this table.
Its fingerprint is SHA-256 over canonical rows, ordered by ticker then date:
`ticker|date|open|high|low|close|volume|source\n`, with the stored
NUMERIC(14,4) values as exact decimal strings and volume as an integer or
`NULL`.

| Ticker | SHA-256 |
| --- | --- |
| `AGG` | `f0495cbc382e583a587b8bea9a3b85e5028f23a299727ec9d0eaa08eaf99e84d` |
| `GLD` | `c7e621b1f2e406afd8d54102a03283f5b45cb5267bfd02c63748abf5b33deda7` |
| `QQQ` | `b578db723497fc3e15c28eb3e25c28801d47f90fa618e3767341d53b4f3cdd1b` |
| `^IXIC` | `6801c641e5af812af8c46a42518ebdd42736f0739d51fcb194d98ba7347b8a1a` |
| `^NDX` | `c5daa0257139c1ac79e983abcbb1feb6affcccc29690643fb3d6eeb0cdb45572` |
| **All five** (in the order above) | `563afd212589d22002696a56580998f7b61f8135547dc41933773aa92273ce40` |

**Caution [VERIFIED from code]: training did not read this table.**

- `train.py` computed returns from yfinance values held in memory.
- It then upserted them, rounded to four decimals, into this table.
- So the table is the closest frozen copy of the training input. Rounding
  differs by at most 0.00005 per price.
- **The news experiment must read this snapshot and never re-fetch**, because
  re-running `train.py` would re-download and re-write the table (B2-F §2.3).

**Model and training files** (SHA-256 recorded in the B2-H working notes; first
8 characters shown):

| Group | Hashes |
| --- | --- |
| GRU models | `gru_*_v1.keras`: AGG `58bcb48d`, GLD `f7bea80f`, IXIC `51fd28ee`, NDX `c27b3c00`, QQQ `72d8beb7` |
| LSTM models | `lstm_*_v1.keras`: AGG `c0ba06ca`, GLD `54d0bf16`, IXIC `c1c5dc85`, NDX `d7ce1cb0`, QQQ `410d7a3f` |
| Scalers | `*_scaler_v1.pkl`, identical for LSTM and GRU per ticker: AGG `f0208916`, GLD `dd3dad69`, IXIC `b7e75896`, NDX `a06089a5`, QQQ `92dc7360` |
| Configs | `naive_arima_garch_config_v1.json` `9f1419fa`; `regime_v1.json` `e72859ce` |
| Metrics | `models/metrics.json` `be0ce123` (89,467 B) |
| Training code | `training/market/`: `train.py` `7fc5ba8a`, `common.py` `eca24ce4`, `preprocessing.py` `e09dbd6b`, `models.py` `3cd6027d`, `dl_models.py` `46eabbf0`, `evaluate.py` `1ff6bb4e`, `regime.py` `0ab033c0` |

### 5.2 Dates and windows [VERIFIED; computed exactly as `train.py` indexes returns]

| Item | Value |
| --- | --- |
| Return | Simple close-to-close; dated by the day it is realised; 1,176 returns (2022-01-04 → 2026-09-11) |
| Horizon | 1 day (`FORECAST_HORIZON_DAYS = 1`) |
| Walk-forward | Expanding; 504 initial training returns, **5-return embargo**, 63-return test windows, **10 windows** |
| First training window | Returns 2022-01-04 → 2024-01-05 (forecast origins 2022-01-03 → 2024-01-04) |
| Embargo | Returns 2024-01-08 → 2024-01-12 (origins 2024-01-05 → 2024-01-11) |
| Test | Returns **2024-01-16 → 2026-07-21** (630 per instrument; origins 2024-01-12 → 2026-07-20). Windows as listed in B2-F §2.1 |
| Unused tail | 37 returns, 2026-07-22 → 2026-09-11 (origins 2026-07-21 → 2026-09-10) |
| **Final holdout** | **None is defined.** The tail is unused, not a holdout. Designating it would be a protocol change, for you to decide (section 8) |

### 5.3 News window and availability cutoff for each prediction

| Rule | Detail |
| --- | --- |
| Acquisition window | Batches 2021-12-01 00:00 → **2026-07-20 19:45 UTC** (minimal), or → 2026-09-10 19:45 UTC with the holdout. The lookback before the first forecast is 2,964 slots, none absent [VERIFIED] |
| Availability [PROPOSED; supported by B2-F/B2-G evidence] | `available_at = max(nominal batch time, HTTP Last-Modified) + 15 min`, recorded per file |
| Cutoff [VERIFIED calendar; PROPOSED rule] | cutoff(d) = **16:00 America/New_York** on trading day d, or **13:00** on an official early-close day. Converted to UTC with `zoneinfo`, so daylight saving is handled |
| Interval of forecast origin d | Batches with cutoff(previous trading day) < available_at ≤ cutoff(d) |
| Prediction | **The return dated r** may use only news in the intervals of origins up to and including the trading day before r. Same-day news is never used |
| Weekends and holidays [VERIFIED rule] | Trading days are the stored `market_data` dates, plus 2021-12-31 for the first interval (open per NYSE's 2021 notice: "2022 New Year's Day was not observed"). Non-trading days' news rolls into the next trading day |
| Embargo and windows | Unchanged. News features are strictly backward-looking. Any scaling or normalisation is fitted on each window's training rows only |

### 5.4 Market calendar [VERIFIED]

**Official early closes in the window: 1:00 p.m. ET.** Sources: NYSE Group press
releases of 27 Dec 2021 (2022–2024) and 8 Nov 2024 (2025–2027), and NYSE's
current calendar page (2026–2028).

| Year | Early closes |
| --- | --- |
| 2022 | 11-25 |
| 2023 | 07-03, 11-24 |
| 2024 | 07-03, 11-29, 12-24 |
| 2025 | 07-03, 11-28, 12-24 |
| 2026 | **None up to 2026-09-10** (next: 11-27, 12-24) |

**Who they apply to:** "New York Stock Exchange, NYSE American Equities, NYSE Arca
Equities, NYSE Chicago and NYSE National". AGG and GLD trade on NYSE Arca.

**Nasdaq (QQQ, `^IXIC`, `^NDX`):**

- **2026:** the official Nasdaq Trader schedule matches NYSE exactly.
- **2022–2025:** Nasdaq's own schedule was not fetched [UNVERIFIED].
- **Corroboration:** stored QQQ volume on all nine NYSE half-days was 31–63% of
  the surrounding median.
- **Effect:** the 13:00 cutoff is applied to every instrument on these days. If
  Nasdaq had in fact traded a full session, the rule would only delay news; it
  could not leak.

**Holidays:**

- **Matches official tables:** the stored calendar's weekday non-trading days
  equal NYSE's official holiday tables for 2022, 2023, 2024, 2025 and 2026 (to
  09-11).
- **Unscheduled closure:** one more, **2025-01-09**, is absent from the
  pre-announced calendars but present in the stored data.
- **Why stored dates are the calendar:** this captures unscheduled closures
  automatically.

**Stored volume as evidence:**

- **Not a half-day:** 2022-07-01, the Friday before a Monday 4 July, has normal
  volume, matching the official list.
- **No other half-days:** no other day shows all three ETFs below 60% of their
  local median volume.

### 5.5 Missing, near-empty and delayed batches [PROPOSED]

| Case | Policy |
| --- | --- |
| Absent slot (confirmed 404) | Missing; never zero-filled |
| Near-empty batch | Missing for coverage. Defined causally: rows < 10% of the median row count of the same UTC slot over the **previous** 14 days. B2-G's centred, size-based rule was for the pre-acquisition audit only |
| Late file (Last-Modified > nominal + 15 min) | Availability moves to Last-Modified + 15 min; flagged |
| Possible backlog (rows > 3× the same causal baseline) | Kept at its own batch time, never back-dated; flagged. Sensitivity variant without flagged batches |
| Coverage of origin d | Covered slots ÷ expected slots in d's interval |
| Coverage threshold | **Primary 0.75**; sensitivity 0.50 and 0.90. Below it, every news feature for d is **null** with `news_unavailable_reason = "gdelt_coverage_below_threshold"` |
| Model comparisons | Run on identical row sets, with and without the null rows |
| **Missing never becomes neutral** | A zero count is a real zero only when coverage is at or above the threshold; otherwise the value is null (CLAUDE.md §12). No imputation, no neutral tone, no carrying the last value forward |

---

## 6. Coverage before acquisition [VERIFIED from the audited list, B2-H checks and stored calendar]

**What "present" means here:** a slot is present when it is listed, or when the
server confirmed it.

- **Present is not meaningful coverage.** Near-empty files are counted
  separately.
- **Row-level coverage needs the files themselves.**

### 6.1 Slots and gaps

| Window | Slots | Present | Absent | Near-empty | Present and not near-empty |
| --- | ---: | ---: | ---: | ---: | ---: |
| Minimal (→ 2026-07-20 19:45) | 162,512 | 160,659 (98.860%) | 1,853 | 86 | 98.807% |
| With holdout (→ 2026-09-10 19:45) | 167,504 | 165,651 (98.894%) | 1,853 | 86 | 98.842% |

**Contiguous absent runs: 50.**

| Length | Runs |
| --- | ---: |
| 15 minutes | 45 |
| 30–60 minutes | 2 |
| 1–6 hours | 1 (2025-06-12) |
| Over 24 hours | 2: 2023-03-22/23 (32.25 h) and **2025-06-14 → 07-02 (416.25 h)** |

**Near-empty runs: 4:** one of 20.75 h (2022-11-10/11) and three single files.

### 6.2 Forecast-day coverage by period

| Period | Forecast origins | Slot coverage | Full | ≥ 99% | < 90% | < 75% | < 50% | Zero |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| First training window | 504 (2022-01-03 → 2024-01-04) | 99.638% | 472 | 482 | 3 | 3 | 3 | 0 |
| Embargo | 5 | 100% | 5 | 5 | 0 | 0 | 0 | 0 |
| Test | 630 (2024-01-12 → 2026-07-20) | 98.095% | 606 | 611 | 12 | 12 | 11 | 10 |
| Unused tail / holdout | 37 (2026-07-21 → 2026-09-10) | 100% | 37 | 37 | 0 | 0 | 0 | 0 |

**Days below 90% coverage.** These are the same 15 days as B2-G, now with
early-close-aware intervals. Under the 0.75 primary threshold, all 15 would be
null.

| Period | Forecast origins (coverage) |
| --- | --- |
| Training | 2022-11-11 (13.5%), 2023-03-22 (25.0%), 2023-03-23 (29.2%) |
| Test | 2025-06-16 (30.6%); ten days at 0% from 2025-06-17 to 07-01; 2025-07-02 (74.0%) |

That is 12 of 630 test rows (1.9%).

**All nine early-close days have full coverage.** Their intervals are shortened
correctly; for example, 2024-07-03 has 84 slots.

### 6.3 Is each market theme observable enough? [ESTIMATED; low confidence; limitation stated]

**A reliable answer needs the files.** Theme-specific coverage depends on the rows
inside each file, and only three batches have been inspected (B2 ×2, B2-G ×1, all
during US hours). The figures below are orders of magnitude, not estimates to
plan on.

**Total rows:** listed bytes per day ÷ 3.86–4.17 KB per row ≈ **122,000–132,000
English rows a day**.

| Theme | Rows per sampled batch | Share of rows | Candidate rows a day, before series rules |
| --- | --- | --- | --- |
| `ECON_STOCKMARKET` | 65 / 53 / 57 | 2.5–5.3% | ≈3,000–7,000 |
| `ECON_CENTRALBANK` | 8 / 12 / 16 | 0.6–1.1% | ≈700–1,400 |
| `ECON_INTEREST_RATES` | 9 / 18 / 13 | 0.7–0.9% | ≈900–1,150 |
| `ECON_GOLDPRICE` | 4 (one batch) | 0.27% in that batch; the lookup ratio to `ECON_STOCKMARKET` implies 0.06–0.12% | **≈70–360** |

**How the series rules thin these out** (B2-G):

- about half of `ECON_STOCKMARKET` rows have two or more mentions;
- 53–56% of equity and rates rows are US-relevant;
- 17.8% of all rows are within-batch duplicates.

**Judgement:**

- **Equity and rates** very likely have hundreds or more stories per forecast
  interval.
- **Gold** is uncertain: tens to low hundreds a day, possibly thin.

**Pre-registered eligibility rule [PROPOSED].** It uses coverage counts only,
never returns.

- **Data:** training-period intervals with adequate coverage.
- **Rule:** a series is eligible for B3 only if at least 95% of those intervals
  contain 10 or more unique stories.
- **If gold fails:** it is reported as not experimentally usable; it is neither
  padded nor merged.

---

## 7. Acquisition and storage plan [PROPOSED; nothing created]

### 7.1 Layout

Planned under `datasets/raw/gdelt/english_gkg_v1/`. `datasets/raw/*` is already
git-ignored [VERIFIED].

```text
datasets/raw/gdelt/english_gkg_v1/
  provenance/  masterfilelist_<sha256>.txt   # list snapshot used (≈128.5 MB) — keep: your decision
               filter_gdelt_filter_v1.yaml    # exact spec applied (+ its sha256)
               run_<UTC>.json                 # code/spec/list hashes, parameters, start/end, outcome
  manifest/    slots.sqlite                   # one row per expected slot (WAL, transactional)
  filtered/    YYYY/YYYY-MM-DD.tsv.gz         # kept rows per UTC day, written atomically
  tmp/         (staging; emptied at start and end)
```

### 7.2 Workflow

1. **Preflight.**
   - Check free disk space (at least 10 GB on the target drive).
   - Download a fresh master list. Record its SHA-256, plus a digest of its
     window entries.
   - Compare the window entries with this audit: 160,658 listed, 860,483,377,717
     bytes, the exact absent runs. Any difference is reported before starting.
   - Record the code, filter-spec and list hashes in `run_<UTC>.json`.
2. **Grid.**
   - Build every expected slot for the approved window.
   - **Listed slots** carry their URL, size and MD5.
   - **Unlisted slots** get a bounded header check (section 3's policy). Each
     becomes `absent_confirmed` or `present_unlisted`, with the ETag as the
     expected MD5.
3. **Per slot, one batch at a time** (2–4 connections in parallel, each handling
   one file):
   1. GET the file into memory.
   2. Verify the byte count, then the MD5 against the list or the ETag.
   3. Check the zip: exactly one member named `<stamp>.gkg.csv`, size guard,
      CRC-32.
   4. Stream-parse it (B2-G: about 5 MB of allocations).
   5. Apply row validity, the capture rule and all flags.
   6. Record in the manifest: `rows_total`, `rows_malformed`, `rows_translated`,
      `rows_kept`, per-series counts, Last-Modified, `available_at_utc`, and the
      late, near-empty and backlog flags.
   7. Nothing raw touches disk. If staging is ever needed, the file goes to
      `tmp/` and is **deleted immediately after validation**.
4. **Atomic commit per UTC day.**
   1. Once all 96 slots of a day are terminal, write the day's rows to
      `tmp/…tsv.gz`.
   2. `fsync`, then `os.replace` into `filtered/YYYY/`.
   3. In **one SQLite transaction**, mark those slots `committed` and store the
      file's SHA-256.
5. **Interruption and resumption.**
   - A crash at any point leaves the last committed day intact.
   - On restart, any day not committed is reprocessed from scratch, so processing
     is idempotent.
   - Retries are bounded: up to 5 attempts with exponential backoff over at most
     10 minutes.
   - An MD5 mismatch gets one re-download, then `failed_permanent`. A mismatch is
     never accepted silently.
6. **Throughput check.** The first few hundred files are the benchmark. Throughput
   is logged, and you decide whether to continue; there is no separate benchmark.
7. **Close-out.**
   - **Coverage report** per slot, day and forecast origin.
   - **Data-quality statistics:** duplicates, source mix, per-series counts.
   - **Eligibility check** (section 6.3).
   - **Tracked summary:** aggregates and each day file's SHA-256, written to an
     acquisition report. Titles are never included.
8. **Git and retention.**
   - No raw or processed data is ever committed.
   - Retained for the life of the research track; deletion is your call.
   - Rebuildable from GDELT's public archive using the recorded list, spec and
     code hashes.

**Tools:** no new dependency. Python's standard library covers it: `sqlite3`,
`zipfile`, `gzip`, `hashlib`, `zoneinfo`, `html`, `unicodedata`, `re`. Downloads
use `httpx` (already declared) or `urllib`. The code would live in
`backend/wealthpilot/data/` and is not written in this phase.

**Timing** [ESTIMATED, from B2-G measurements]:

| Resource | Estimate |
| --- | --- |
| Download | ≈43–47 h with a few connections, or up to about 4.6 days sequentially |
| CPU | ≈4–8 core-hours |
| Kept on disk | ≈1.7–4.3 GB |
| Manifest | ≈50 MB |
| List snapshot (optional) | ≈128.5 MB |

---

## 8. Final acquisition recommendation

| | Minimal window | Window with holdout |
| --- | --- | --- |
| Batch range | 2021-12-01 00:00 → 2026-07-20 19:45 UTC | → 2026-09-10 19:45 UTC |
| Present files | 160,659 (160,658 listed + 1 unlisted) | 165,651 |
| Download | **0.860 TB** (+7.3 MB unlisted file) | **0.882 TB** (+21.6 GB, +2.5%) |
| Extra download time | — | ≈1.1 h at the measured rate |
| Gaps in the extra period | — | None: 4,992 slots, 0 absent, 0 near-empty |
| Supported by the current evaluation design? | **Yes** | **Only if you designate the holdout first** |

**Recommendation [PROPOSED]: the minimal window**, because the current protocol
defines no holdout and only that window is needed.

**However, I recommend you consider designating the 37-return tail
(2026-07-22 → 2026-09-11) as a pre-registered final holdout now**, and then
taking the holdout window.

- **Why:** the 10 walk-forward test windows will be looked at repeatedly while B3
  is developed. An untouched holdout is the only guard against tuning to them.
- **Its limits:** it is small (37 returns per instrument, about seven weeks), so
  it is a sanity check, not a primary test.
- **Cost of including it:** small (+2.5% download, no gaps).
- **Cost of excluding it:** no untouched final check exists.
- **The decision can wait, with one condition.** Excluding it now is reversible,
  because those 37 days could be appended later while GDELT keeps the files
  online. But the designation only means something if it is made before any
  test-period result is seen.

**Readiness:**

- **Technically ready.** No blocker was found: complete gap knowledge, a verified
  calendar, verified integrity checks, a feasible streaming design, and a
  fingerprinted evaluation basis.
- **Procedurally not ready.** Six decisions are still open (section 9).

---

## 9. Remaining uncertainties and decisions

| Item | Status |
| --- | --- |
| Your internet bandwidth and monthly data cap (≈0.87–0.90 TB on the wire for the minimal window) | **UNRESOLVED.** Only you know them; not assumed |
| Final acquisition window (minimal, or with holdout) | **UNRESOLVED.** Depends on the holdout designation (section 8) |
| Filter specification `gdelt_filter_v1` | **PROPOSED.** Awaiting approval; labelled evaluation planned (section 4.5) |
| Early-close handling | **Calendar VERIFIED**, from official NYSE releases. The 13:00 ET rule awaits approval. Nasdaq's 2022–2025 schedule is [UNVERIFIED], but the rule is leak-free either way |
| Missing-data policy (thresholds, near-empty and backlog rules) | **PROPOSED.** Awaiting approval (section 5.5) |
| Storage and retention (directory, keeping the list snapshot, retention period) | **PROPOSED.** Awaiting approval (section 7) |

**Other open points:**

- **June 2025 outage:** 1,233 slots inside it were never individually checked.
  Optional: about 1,233 header checks, which need approval.
- **`20260509233000`:** inconclusive, cached only. It is one Saturday slot, and a
  re-check more than an hour apart would settle it.
- **Theme-specific volumes:** need data; the eligibility rule is pre-registered.
- **Cross-batch duplicate and update rates:** measured during acquisition.
- **Title redistribution:** still unverified, so titles stay local.

---

## 10. Sources (accessed 2026-10-12)

**Official calendar sources:**

- NYSE Group, "Announces 2022, 2023 and 2024 Holiday and Early Closings Calendar"
  (27 Dec 2021):
  <https://ir.theice.com/press/news-details/2021/NYSE-Group-Announces-2022-2023-and-2024-Holiday-and-Early-Closings-Calendar/default.aspx>
- NYSE Group, "Announces 2025, 2026 and 2027 Holiday and Early Closings Calendar"
  (8 Nov 2024):
  <https://ir.theice.com/press/news-details/2024/NYSE-Group-Announces-2025-2026-and-2027-Holiday-and-Early-Closings-Calendar/default.aspx>
- NYSE holidays and trading hours (2026–2028):
  <https://www.nyse.com/markets/hours-calendars>
- Nasdaq Trader 2026 holiday schedule:
  <https://www.nasdaqtrader.com/trader.aspx?id=calendar>

**GDELT:**

- Header-only checks: `http://data.gdeltproject.org/gdeltv2/<stamp>.gkg.csv.zip`
  for the 180 slots.
- GKG 2.1 codebook and the B2-F/B2-G GDELT sources, as cited in those reports.

**Repository** (read-only):

- the `market_data` table;
- `training/market/*.py`;
- `models/market/*`;
- `models/metrics.json`;
- the reports and docs listed in section 2.

**Not fetched:**

- the Nasdaq.com holiday page timed out;
- Wayback Machine copies are not reachable from this environment.

---

## Verification of this phase

**Files created:** this report.

**Files modified:**

- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`: a B2-H findings note;
- `docs/MEMORY.md`: the track status.

**Not modified:** any historical report.

**Network activity:**

- 1,264 header-only requests, for the 180 authorised slots only (section 3.3);
- official documentation pages.

**No archive body, master list, other sample or translated-stream file was
downloaded.**

**Database:** read-only `SELECT`s on `market_data`.

**Not done:**

- no account, billing or BigQuery query;
- no dependency or lockfile change;
- no application, schema, model, training-script or market-data change;
- no data directory created;
- no sentiment, feature, B3 or blockchain work;
- no ADR.

**Tests:** none run, because no code changed. The analysis ran as separate
read-only scripts outside the repository.
