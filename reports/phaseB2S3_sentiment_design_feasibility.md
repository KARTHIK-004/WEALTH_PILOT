# Research Enhancement Track — Phase B2-S3: Sentiment Pipeline Design and Feasibility

**Status: DESIGN AND FEASIBILITY ONLY. Nothing was implemented, downloaded, installed, run or approved.**

**Date:** 2026-10-20 (UTC). **Written for:** the project owner, as the evidence base for deciding what a later implementation
phase (not started) may and may not do.

**Claim labels.** **[VERIFIED]** checked in the repository, a report, or a read-only probe in this phase. **[MEASURED]** a
number observed in a local artifact (a subset of VERIFIED). **[PROPOSED]** a recommendation or an existing proposal, not
approved. **[UNVERIFIED]** not checked here (includes every extrapolation and every recollection of an external fact).
**[BLOCKED]** cannot proceed without an approval or evidence not available. **[FUTURE]** work for a later phase.
Extrapolations are written **[UNVERIFIED, extrapolated]** with their assumptions beside them.

---

## 1. Executive summary

1. **S3 is design-only.** The only file created in the project is this report. Three throw-away probe scripts were written
   to the session scratchpad (outside the project); they read local artifacts read-only and printed aggregate counts.
2. **The most important result is a defect in the S2.2 reconciliation contract, found by tracing the real pipeline.**
   S2.2 requires `SlotSummary.series_rows` to equal the number of article records supplied for a batch (any theme). In the real
   pipeline `series_rows` is the number of rows that are members of **one series** (`engine.py:97-100`), which is not the
   number of captured records. Against the 192 real batches of the local B2-M development sample the S2.2 contract holds in
   **0 of 192** batches; the corrected per-theme contract holds in **192 of 192** [MEASURED]. On real data, S2.2 as written
   would mark essentially every day `slot_article_mismatch`.
3. **A second S2.2 defect: late batches.** Slot coverage is assigned by nominal batch time while articles are assigned by
   verified availability time. A synthetic late batch (nominal 20:45Z, available 21:45Z) gives day D `ok, 96/96 slots covered,
   n_eligible=0, no_news=True` and puts the article in day D+1 with no slot accounting [VERIFIED by probe]. The sample has no
   late batch (0 of 192), so this has never been exercised on real data.
4. **Several S2 inputs have no producer yet** [VERIFIED]: cross-batch dedup statuses and `story_id` (the engine only computes
   same-batch marks), a manifest-to-`SlotSummary` adapter, article-level "unverified availability" (the real pipeline rejects an
   unverified batch whole), and a per-theme slot summary.
5. **Model feasibility is not decidable from repository evidence.** The S1 audit is absent from the repository, no model card
   or licence is stored locally, and neither `torch` nor `transformers` is installed. The filter deliberately excludes company
   items (`filters.py:206-214`), the domain most financial-sentiment models are validated on. No sentiment-polarity ground
   truth exists in the project.
6. **Full-window scoring is plausible on this laptop but unmeasured:** roughly 2.5-5 million records to score (central about
   3.3 million) and on the order of 5-45 hours of CPU inference [UNVERIFIED, extrapolated], on top of a 0.86 TB download that
   has no enabling switch in this build (`__init__.py:17`).
7. **Recommendation: do not start implementation.** First approve (or revise) the open decisions in section 7, and fix the two
   contract defects in a narrowly scoped corrective phase (**S2.3**, proposed, not started). The design in section 3.6 can
   then be implemented offline with synthetic data, with no model, as before.

---

## 2. Verified current state

### 2.1 Repository and sources checked

| Item | Result |
| --- | --- |
| Branch / HEAD | `master` / `71b363f`; nothing staged; no commits [VERIFIED] |
| Tracked modifications | 49 files, all pre-existing demo-data work, plus `docs/MEMORY.md` (S2 and S2.2 entries) [VERIFIED] |
| Sentiment package | `backend/wealthpilot/data/gdelt/sentiment/` (`__init__.py`, `schema.py`, `fake_scorer.py`, `features.py`), untracked [VERIFIED] |
| Sentiment tests | `tests/backend/data/gdelt/test_sentiment_scaffold.py`, 90 tests; re-run in this phase (section 8) |
| `CLAUDE.md`, `docs/PROJECT_PLAN.md`, `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`, `docs/MEMORY.md` | Read for the relevant sections [VERIFIED] |
| **S1 audit report** | **Absent.** No file on disk (searched `reports/` and `docs/`; the only "FinBERT" mentions are `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` lines 560, 802, 847). Its contents were not reconstructed |
| **S2.1 review report** | **Absent** as a file; it existed only as a chat deliverable. Its findings are reflected in `docs/MEMORY.md` and in the S2.2 tests |
| **S2.2 completion report** | **Absent** as a file; only the `docs/MEMORY.md` entry and the code/tests exist |
| Build state | `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD = False`, adapter registry empty [VERIFIED]; `NETWORK_ENABLED_IN_THIS_BUILD` and `DEV_SAMPLE_ENABLED_IN_THIS_BUILD` are `True` from B2-M (`__init__.py:25-26`), unchanged by this phase |

### 2.2 What the pipeline actually does, per batch (traced) [VERIFIED]

| Stage | Code | What it means |
| --- | --- | --- |
| Slot grid | `session_calendar.py`, `timeutil.slot_grid` | Nominal 15-minute batch stamps |
| Availability | `availability.py:121-128`; used at `engine.py:74-78` | `available_at = max(nominal, verified Last-Modified) + 15 min`. If unverified, the **whole batch** is rejected (`BodyOutcome("availability_unverified")`; slot becomes `downloaded_invalid`); no shard is written |
| Parse | `parser.py:117-151` | A physical line is kept only if it is valid UTF-8, has 27 fields, matches the batch date, is not translated, is a web collection. Each rejection class is counted. `english_valid` is the surviving count. Only `PAGE_TITLE` is extracted (`parser.py:29`): **there is no article body** |
| Classify | `filters.py:194-238` | Per row: membership in `EQUITY_US`, `RATES_US`, `GOLD` (company items are excluded from membership, `filters.py:206-214`), `captured`, flags |
| Series counts | `engine.py:89-100`, `manifest.py:258-260` | Per batch and per series: number of rows with `members[s]` true (before any dedup), plus a US-relevant subcount. `new_stories` is written as NULL |
| Same-batch marks | `engine.py:115-118`, `dedup.mark_same_batch` (`dedup.py:52-67`) | `ORIGINAL`, `DUP_SAME_BATCH` (same URL), `SYNDICATED_SAME_BATCH` (same normalised-title hash) over **all** valid rows of the batch |
| Kept rows | `engine.py:102-113`, `output.py:21-28` | `captured` rows (and a ~1-in-1,000 hash-selected audit sample) are written with `available_at_utc`, title, tone fields, `member_*` flags, `mech_dup`. Everything else is discarded |
| Day files | `engine.py:171-214`, `output.py:135-147` | Grouped by **UTC day of the nominal stamp**, committed only when every slot of that UTC day is terminal |
| Near-empty flag | `engine.py:35,163-168,188`, `manifest.py:331-340` | Set at day commit: `rows_english_valid` (all English rows, not a theme) below 10% of the median of the same slot over up to 14 previous days; **None** with fewer than 7 baseline observations |
| Cross-batch dedup | `dedup.py:70-113` (`StoryTracker`, `deduplicate`) | **Not called by the engine.** Used only in `tests/backend/data/gdelt/test_filters_dedup.py` [VERIFIED by grep]. So `REOBSERVATION`, `UPDATE`, `SYNDICATED` and `story_id` are never produced for real data today |
| Full-window run | `__init__.py:17`, `engine.py:364` | `run_sample` is the only function that talks to a transport. "Full historical acquisition has no enabling switch at all: it always refuses." Sample limits are `config.py:45-47` (1.3 GB planned, 1.5 GB cap, 1,200 requests) |

### 2.3 The S2.2 scaffold as implemented [VERIFIED]

- `aggregate_daily` (`features.py:273`) validates inputs, builds the expected nominal slot grid per interval
  (`features.py:309`), assesses each day (`_assess_day`, `features.py:227`: grid, coverage via the existing
  `interval_count`, then reconciliation `_reconciles`, `features.py:221`), and assigns each article by verified availability to
  `(cutoff(prev), cutoff(d)]` (`features.py:331`).
- The proposed rules stay explicit inputs: `PROPOSED_DEDUP_POLICY` (`features.py:94`), `PROPOSED_COVERAGE_THRESHOLD = 0.75`
  (`features.py:76`), early-close and holiday calendars in `SentimentConfig` (`features.py:106`). Every row carries
  `rules_status = PROPOSED_NOT_APPROVED`.
- Article schema: `s2_article_v2` (`schema.py:37,56`), three labels (`schema.py:39`), tolerance 1e-6 (`schema.py:42`), three
  themes (`schema.py:46`).

### 2.4 Read-only probes run in this phase (aggregate counts only)

| Probe | Reads | Result |
| --- | --- | --- |
| Contract probe | Local B2-M manifest (opened `mode=ro&immutable=1`) and the 170 filtered day files | Section 3.1.2 |
| Theme probe | Same day files: per-theme duplicate share and title-length statistics | Section 3.2 and 3.5 |
| Late-batch probe | Synthetic in-memory records through the S2.2 aggregator | Section 3.1.3 |

No key, annotation file, AI-only store, label, `.env` or network was touched. Titles were read only to count characters and
words.

---

## 3. Findings by workstream

### 3.1 Workstream 1 — Source-to-feature contract

#### 3.1.1 The lifecycle of a count (what each number means) [VERIFIED]

| Name | Where produced | Meaning | Includes |
| --- | --- | --- | --- |
| `rows_physical` | `parser.py` (`physical_lines`) | Lines read from the archive member | Every line, valid or not |
| `rows_english_valid` | `parser.py:145` | Rows that passed validity | Duplicates, company items, uncaptured rows |
| rejected | `parser.py` counters | `malformed` (oversize, decode, field count), `date_mismatch`, `translated`, `non_web` | Counted by reason, never silently dropped |
| `rows_captured` | `engine.py:127` | Rows with `captured = True`, written to the shard | Duplicates and company items among them |
| `slot_series_count.rows` (`series_rows` in S2) | `engine.py:97-100` | Rows with `members[s]` true for **one** series `s` | Duplicates; one row can count in several series (a measured 798 of 2,751 equity rows are also members of another theme) |
| supplied article records (S2) | the future producer | Records handed to `aggregate_daily` | Whatever the producer chooses |

The names in S2 (`n_eligible`, `n_scored`) are downstream of all of these and are defined only after the dedup and text
checks.

#### 3.1.2 Does S2.2's `series_rows == supplied record count` match the pipeline? **No.** [MEASURED]

S2.2 (`features.py:221-224`) requires, for each processed slot, `series_rows == number of supplied article records for that
batch (any theme, any status)`. Checked against the 192 real batches and their kept rows:

| Check (192 batches) | Batches that hold |
| --- | ---: |
| manifest `rows_captured` equals kept rows in the day files | **192 / 192** |
| per-theme manifest series count equals kept rows with that theme's `member_*` flag (candidate contract) | **192 / 192** |
| **S2.2 as written:** every theme's `series_rows` equals total kept records | **0 / 192** |

Sample totals: kept 26,854; equity members 2,751; rates 2,909; gold 193; English rows 244,936. The S2.2 contract is wrong
because (a) `series_rows` is per series, (b) a single `SlotSummary.series_rows` cannot represent three themes, and (c) the
manifest already stores the right totals (`rows_captured`, per-series counts). On real data every day would fail
reconciliation and be `slot_article_mismatch` [VERIFIED, extrapolated from the 192-batch sample].

**Candidate contract C1 [PROPOSED].** Reconcile at two levels, both exact on the sample:

1. per batch: `rows_captured == number of supplied records for that batch_ts` (all themes, all statuses);
2. per batch and theme: `slot_series_count.rows[theme] == number of supplied records with theme_flags[theme]`.

Supplied records must therefore include duplicates and invalid-text rows (counts are taken before dedup). Test cases required:
equal counts; one record missing; one extra record; a theme flag mismatched; multi-theme record counted once per theme and
once in the batch total; unprocessed slot with records; processed slot with zero records and `rows_captured = 0`.

#### 3.1.3 Time chain and the late-batch defect [VERIFIED by probe; real-data frequency UNVERIFIED]

Chain: nominal stamp (grid) → HTTP `Last-Modified` (verified, else the batch is rejected) → `available_at = max(nominal,
Last-Modified) + 15 min` → **expected slot** in the interval's nominal grid (`features.py:309`) → **article** placed by
`available_at` (`features.py:331`) → origin-day row.

Two clocks are used for one slot. If a batch is written late, its slot stays in the earlier interval's grid but its articles
move to the later interval:

| Synthetic case (nominal 20:45Z on D2, available 21:45Z) | D2 row | D3 row |
| --- | --- | --- |
| S2.2 output | `ok`, 96/96 slots covered, `n_eligible=0`, **`no_news=True`** | `ok`, `n_eligible=1`; the slot is not in D3's grid, so nothing reconciles it |

D2 is wrong twice: the slot was not available at D2's cutoff (so coverage is overstated and the day should be unavailable or
partially covered), and the article's absence is reported as "verified no news". The point-in-time rule is violated for the
coverage number even though the features themselves never leak. The B2-H text itself is ambiguous: it defines interval
membership by availability (`reports/phaseB2H_pre_acquisition_readiness.md:443`) but coverage as "covered slots ÷ expected
slots in d's interval" (line 500), without saying which clock assigns a slot.

Evidence on real frequency: the sample has 0 late batches (Last-Modified 6.9-12.5 min before nominal, B2-M section 6;
`late_flag` sum 0). B2-F reports historical files with no sign of rewriting (`reports/phaseB2F_gdelt_acquisition_feasibility.md`
lines 81-84, 457-468), but that is a sample of 1,736 header checks, not the full window. The post-outage periods (June-July
2025; March 2023) are where late files would be expected [UNVERIFIED].

**Candidate contract C2 [PROPOSED, approval required].** Two options; this phase does not choose:

| Option | Rule | Consequence |
| --- | --- | --- |
| **C2-A: availability-gated coverage** | The expected set stays the nominal grid. A slot is covered for interval d only if its verified `available_at <= cutoff(d)`. A late slot is "late for d" (not covered), and its records are placed in the interval of their availability under a recorded late-arrival ledger | Strictly point-in-time. A late slot lowers d's coverage even if it arrives a minute after the cutoff. Needs `available_at` in the slot summary |
| **C2-B: nominal-time assignment, availability-gated content** | Keep coverage by nominal time; require that no covered slot is late, otherwise the interval is unavailable | Simpler, more conservative: one late slot makes the whole interval unavailable |

Either needs `SlotSummary` (or a new wrapper) to carry `available_at_utc`, the theme, and a **state reason** (see 3.3). Test
cases: late slot crossing a cutoff (both options), late slot not crossing a cutoff, late slot in a weekend interval, late
slot at exactly the cutoff, late slot whose records are duplicates, absent versus late versus unverified.

#### 3.1.4 Other contract gaps found while tracing [VERIFIED]

| # | Finding | Evidence | Proposed handling |
| --- | --- | --- | --- |
| G1 | No manifest-to-`SlotSummary` adapter exists; `SlotSummary` is used only by `coverage.py` and the S2 code | grep | Specify the adapter in the implementation design; map slot states below |
| G2 | The S2 schema's article-level `availability_status="unverified"` has no real source. An unverified batch is rejected whole and produces no records | `engine.py:77-78,356-360` | Treat it as a slot state (`downloaded_invalid` with reason `availability_unverified`), not an article state |
| G3 | `dup_status` (same-batch only) exists; cross-batch statuses and `story_id` have no producer | `engine.py` imports only `mark_same_batch`; grep | A separate offline, chronologically ordered pass is needed (3.2) |
| G4 | `title_sha256` in `schema.py:82` is the hash of the **raw** title; the filter's `title_hash` (`filters.py:76`) hashes the **normalised** title (NFKC, casefold, punctuation removed, `filters.py:71-73`). They differ | code | Name both explicitly; use the normalised hash as the dedup/cache key, keep the raw hash as input provenance |
| G5 | Day files are keyed by the UTC day of the nominal stamp; an ET interval spans two UTC days (and 3 for a weekend), and the near-empty flag is set at each day's commit | `engine.py:171-214`, `output.py:55-56` | An interval is buildable only when all the day files it touches are committed |
| G6 | `near_empty` uses all-English `rows_english_valid`, not theme rows; unknown (None) until 7 baseline days exist, and S2 counts unknown as **not covered** (`coverage.py:42-43`) | `engine.py:163-168` | See 3.3; a contiguous window with a pre-window lookback avoids the warm-up gap, but only if baselines are computed in chronological order |
| G7 | The near-empty baseline is set once at day commit and "committed slots are never reset" (`manifest.py:293`); an out-of-order or resumed run changes the baseline a later day sees | `manifest.py:288-304,331-340` | Process and commit days strictly chronologically, or record the baseline's inputs |
| G8 | The sentiment `THEMES` (`schema.py:46`) are lower-case; the filter series are upper-case (`filters.py:33`) and the day-file flags are `member_equity_us` etc. (`output.py:25-26`) | code | Fix the mapping in the adapter design |

**Slot-state mapping [PROPOSED].** Real states are `confirmed_absent`, `absent_inconclusive`, `request_failed`,
`inaccessible`, `downloaded_invalid`, `parsed_validated`, `processed`, plus non-terminal `unverified`, `verified_available`,
`in_progress` (`manifest.py:38-60`). Only `processed` is "processed". The other terminal states are distinct reasons the
slot is missing and should be kept distinct (3.3). A non-terminal slot means the interval cannot be built yet.

### 3.2 Workstream 2 — Deduplication and story updates

#### 3.2.1 What exists

| Source | Content |
| --- | --- |
| `dedup.py:8-14` | The six statuses and their rules; all state causal, processed in `(available_at, batch, seq)` order; 72-hour syndication window (`dedup.py:24`) |
| B2-H section 4.6 (`reports/phaseB2H_pre_acquisition_readiness.md:358-376`) | Primary counting unit: **a story, counted once at its first availability. Updates are counted separately and enter only the sensitivity variants** |
| S2.2 `PROPOSED_DEDUP_POLICY` (`features.py:94`) | Duplicates = `DUP_SAME_BATCH`, `SYNDICATED_SAME_BATCH`, `REOBSERVATION`, `SYNDICATED`; `UPDATE` **kept** as a new version (`keep_all_versions`) |
| Measured, B2-M sample | 18.0% of English rows are same-batch duplicates (44,209 of 244,936). Of 26,854 kept rows: `ORIGINAL` 22,038; `SYNDICATED_SAME_BATCH` 4,555; `DUP_SAME_BATCH` 261. Per theme, same-batch duplicate share: equity 23.2%, rates 20.9%, gold 4.7% |
| Cross-batch rates | Never measured: the sample is 192 isolated batches over 170 days, and cross-batch dedup is not run by the engine [VERIFIED] |

**Documented inconsistency [VERIFIED]:** B2-H's primary unit excludes updates from the primary counts; the S2.2 proposed
policy includes them (as versions). These cannot both be the primary rule. This phase does not resolve it.

#### 3.2.2 Alternatives and their consequences [PROPOSED comparison; none approved]

| Policy | Counts | Sentiment weighting | Leakage risk | Reproducibility |
| --- | --- | --- | --- | --- |
| **P0 no dedup** (every record) | Highest; ~21% inflated by same-batch copies in the sample | Syndicated stories weigh more: a popularity/attention signal mixed into sentiment | None from dedup | Trivial |
| **P1 story once, first availability** (B2-H primary) | Lowest; updates excluded | Equal weight per story | Causal only if processed in availability order with a pre-window warm-up (72 h for title state; **unbounded for URL state**) | Deterministic if ordering ties are fixed; depends on `canonical_url` dropping query strings (`filters.py:82-90`) |
| **P2 story once + latest version** | As P1, but the story's score may be replaced by an update | Reflects revised wording | **High:** a "latest" value must be as of the cutoff, never the final version | Needs explicit versioning per cutoff |
| **P3 keep all versions** (S2.2 proposal) | Updates add records | A heavily updated story weighs more | Low if each version is stamped at its own availability | Simple; `n_eligible` counts versions, not stories |
| **P4 story once + separate intensity feature** (`n_copies`, `n_updates`) | As P1 plus extra features | Equal weight; attention kept as its own, clearly named feature | As P1 | Extra features must be defined in an ADR first (`CLAUDE.md` section 10) |

Other points that affect every option:

- **Scoring cost.** Identical normalised titles get identical scores, so score once per `(normalised title hash, model
  revision)` and reuse. This also makes the choice between P0-P4 an aggregation decision, not a scoring one.
- **Memory.** The `StoryTracker` URL dictionary is unbounded. Over about 23 million captured rows an in-memory dictionary is a
  multi-gigabyte structure (rough, assumed ~300 B/entry: about 7 GB) against 15.7 GB of RAM [UNVERIFIED, extrapolated]; feeding
  only theme members (~5 million) or a disk-backed store avoids it.
- **False merges.** `canonical_url` drops the query string, which can merge distinct articles on sites that use `?id=`; the
  rate is unmeasured [UNVERIFIED].
- **Warm-up.** First occurrences before the window start are invisible; syndication within 72 h of the window start would be
  misclassified without a lookback pass.
- **Unresolved rows.** The S2.2 `unresolved_story_ids` branch cannot be triggered by real `StoryTracker` output (an `ORIGINAL`'s
  `story_id` is its own record id) and is therefore a pure integrity check [VERIFIED by reading `dedup.py:107`].

**Recommendation [PROPOSED, approval required]:** decide P1 versus P3/P4 before implementation, run `deduplicate` as its own
offline pass, report the same-batch and cross-batch shares as measured facts from the full window, and keep the S2.2 fail-closed
statuses until a policy is approved. This phase does not choose.

### 3.3 Workstream 3 — Coverage and missingness

#### 3.3.1 The quantities, kept distinct [PROPOSED taxonomy]

| # | Quantity | Source | Unit | Measurable or unavailable | Evidence needed to call it measurable |
| --- | --- | --- | --- | --- | --- |
| 1 | Expected source slots | Nominal grid from the cutoffs (`features.py:309`) | slots | Always known | A validated calendar (holidays, early closes: unapproved) |
| 2 | Retrieved slots | Manifest `existence` / `fetch_status` | slots | Known per terminal state | State reasons kept (absent vs invalid vs failed) |
| 3 | Processed slots | `slot_state == "processed"` | slots | Known | Point-in-time `available_at <= cutoff` (C2) |
| 4 | Near-empty slots | `near_empty_flag` | slots | **Unknown** for the first 7 baseline days, for any slot whose baseline is incomplete, and always in the sample | Chronological baseline (G6, G7); approval of the 10% / 14-day rule |
| 5 | Eligible article records | After text validity and dup labels | records | Known only when 1-3 are adequate **and** C1 reconciles | Reconciliation (3.1.2) |
| 6 | Unique stories | `story_id` | stories | **Uncertain**: needs the cross-batch pass (G3) | Dedup policy approval; full-window measured rates |
| 7 | Scored records | Model output | records | Known after scoring | A scorer that returns `unavailable` with a reason |
| 8 | Unavailable records | Text invalid or scorer failure | records | Known | `unavailable_reason` (added in S2.2) |

S2.2 exposes items 1, 3 (as covered), 4 (count), 5, 6 (distinct story count), 7 and 8, with source `coverage` and
`scoring_coverage` kept separate. It does not yet distinguish item 2's reasons (absent, invalid, failed, late).

#### 3.3.2 Can the existing metrics be interpreted correctly? Assessment

| Situation | Today's behaviour | Interpretable? |
| --- | --- | --- |
| Missing batches | `missing_source_batches` / `insufficient_coverage`, all features `None` | Yes, but reasons (absent vs invalid vs failed) are lost |
| Near-empty processed slots | Counted as not covered | **Not safely.** A quiet but healthy window reads as missing, a non-random selection (informative missingness). Their count is exposed, which helps |
| Unknown near-empty | Counted as not covered (`coverage.py:42-43`) | Only the start of a window, or an incomplete baseline, is affected; a pre-window lookback of at least 14 days is needed [PROPOSED] |
| Partial scoring | `scoring_status` / `scoring_coverage`, reason `partially_scored_x_of_y` | Yes; no threshold is invented |
| Duplicates-only interval | `no_news=None`, `duplicates_only_unresolved` | Yes, pending the policy |
| Delayed availability | **Wrong** (3.1.3) | **No**, until C2 |
| Theme-specific coverage | Not available: `series_rows` and `near_empty` are slot-level, not theme-level | **No.** A theme (especially gold, ~1 member per batch in the sample) can have zero rows in an otherwise healthy slot; that is a real zero only if the slot was fully processed, and the contract above does not currently say so per theme |

**Thresholds.** 0.75 source coverage (B2-H `:501`, sensitivity 0.50 and 0.90) and any scoring-coverage threshold are
**unapproved proposals**; this report adopts neither. B2-H's pre-registered eligibility rule (a series is usable only if at
least 95% of training intervals hold 10 or more unique stories, `:586-593`) is also **PROPOSED**. On the sample, gold has about
1 member row per batch (about 97 per day before dedup and before cross-batch dedup), so the rule may well fail for gold
[UNVERIFIED, extrapolated: the sample is 192 isolated batches].

**Missing is never neutral or zero** [VERIFIED rule: `CLAUDE.md` section 12, B2-H `:503`]. The measurable states are
"processed slot, zero eligible records" (a real zero, `no_news=True`) and "scored neutral" (a real value). Everything else
stays `None` with a reason.

### 3.4 Workstream 4 — Real sentiment model feasibility

**Evidence limits, stated first.** The S1 audit is absent. The repository names **FinBERT** as the leading candidate and marks
its licence, availability and hardware fit [UNVERIFIED] (`docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md:560-564`). No model card,
licence text or weights exist locally (no `~/.cache/huggingface`, no `torch` cache). I did not contact any external source. Every
statement about a model below that is not a repository fact is a recollection and is labelled [UNVERIFIED].

#### 3.4.1 Local environment [VERIFIED]

Python 3.11.9 (AMD64); `numpy 1.26.4`, `scipy 1.14.1`, `pandas 2.2.3`, `scikit-learn 1.5.2`, `xgboost 2.1.2`, `statsmodels
0.14.4`, `arch 7.1.0`, `tensorflow 2.17.0`, `keras 3.15.1`, `shap 0.46.0`, `google-genai 0.3.0`, `tzdata 2026.4`. **Not
installed:** `torch`, `transformers`, `tokenizers`, `safetensors`, `onnxruntime`, `sentencepiece`. Hardware: Intel Core
i7-1165G7 (4 cores / 8 threads), 15.7 GB RAM, NVIDIA GeForce MX450 plus Intel Iris Xe, 164 GB free on `C:`.
`CLAUDE.md` section 5 does not approve `transformers` or `torch`; `RESEARCH_ENHANCEMENT_ARCHITECTURE.md:696` says to ask first.

#### 3.4.2 Candidate families (the S1 list is not available, so these are not claimed to be S1's)

| Candidate | Repository evidence | Other facts | Status |
| --- | --- | --- | --- |
| FinBERT-class transformer classifier (three-class positive/negative/neutral) | Named in the architecture doc only; **no specific checkpoint is stated** | Size, licence, label order, training data: recollection only | [UNVERIFIED] |
| Distilled or smaller financial-news classifier | None | Recollection only | [UNVERIFIED] |
| Financial lexicon (dictionary-based) | None | No transformer dependency; dictionary licence unknown | [UNVERIFIED] |
| **GDELT's own tone fields** | `tone`, `positive`, `negative`, `polarity` columns already in every kept row (`output.py:22-24`, `parser.py:26,150`) | Document-level lexicon tone over the full article, not the headline; no new dependency | [VERIFIED present; quality UNVERIFIED]. The natural zero-dependency "sentiment-only" baseline |
| LLM zero-shot scoring through a provider | Provider gates A-D, build lock and registry all closed | Sends text off-machine; also carries hindsight (below) | [BLOCKED] |

#### 3.4.3 Evaluation dimensions

| Dimension | Finding |
| --- | --- |
| **Licence** | Weights licence for any candidate: [UNVERIFIED] and cannot be checked offline. GDELT's licence permits academic use with citation (`docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md:286-287`, from the B2 evaluation). Financial PhraseBank, a likely validation corpus, is CC BY-NC-SA 3.0 (`reports/phaseB2_historical_news_source_evaluation.md:86-87,194`): non-commercial and share-alike, which constrains how a derived artifact is shared. A model trained on it inherits a question that needs a model-card check [UNVERIFIED] |
| **Framework / dependency conflicts** | `transformers` needs a tensor backend. The project has TensorFlow 2.17 and Keras 3.15.1; whether the current `transformers` supports a TensorFlow route, and whether `torch`, `transformers`, `tokenizers` and `safetensors` resolve against `numpy 1.26.4` and TensorFlow's pins, is [UNVERIFIED]. A resolver dry-run needs network access and is not authorised. Recommendation: test in an **isolated** environment, never in `.venv` |
| **Size** | A BERT-base-class model is on the order of 110 million parameters, about 0.44 GB as 32-bit floats (arithmetic on a recalled parameter count) [UNVERIFIED]. It fits in 15.7 GB RAM |
| **Throughput** | Measured input: median title 62-64 characters, about 10-11 words, p90 93-102 characters, max 255 [MEASURED on the sample]. That is roughly 16-24 word-piece tokens (assumed). At about 4 GFLOP per headline (assumed) and an assumed 30-150 headlines per second on a 4-core laptop CPU, 3.3 million headlines is about 6-30 hours [UNVERIFIED, extrapolated; **no benchmark may be run**]. The MX450 (small dedicated memory) is not a reliable inference target, and native-Windows TensorFlow 2.17 has no GPU support (recollection) [UNVERIFIED] |
| **Reproducibility** | Needs a pinned model revision and weights hash, deterministic inference (CPU, fixed batch composition, `random_state=42`), and `scorer_code_sha256` plus `model_revision` stored per record (both already in the S2 schema). Batch-size-dependent numerical differences must be tested; a revision change invalidates the cache |
| **Label mapping** | S2 labels are `positive`, `negative`, `neutral` with an argmax check (`schema.py:39`). A candidate's `id2label` order must be verified against its own configuration before approval; a silent reordering would invert sentiment. Also not covered: ties, the probability-sum tolerance of 1e-6 when a model stores float32 or rounded output |
| **Domain mismatch** | The filter **excludes company items** from every theme (`filters.py:206-214`), so the headlines are market-level and macro, while most financial-sentiment training and validation corpora are company-specific (Financial PhraseBank is Finnish-company sentences, `reports/phaseB2_historical_news_source_evaluation.md:214`). Also, headline-only input (`parser.py:29`): no body |
| **Validation data** | **None exists for sentiment polarity.** The B2 annotation work measures whether the **filter** captures the right rows; it carries no polarity labels. Hindsight-free human polarity labels on this text are needed; the project forbids fake or AI-generated ground truth, and the human-labelling plan is not decided [BLOCKED] |
| **Temporal contamination** | A pre-trained classifier can only encode knowledge up to its own training date. A large language model scored on 2022-2026 headlines can carry knowledge of what happened next, which is hindsight inside a leakage-controlled study. This is a strong reason to exclude zero-shot LLM scoring from the primary arm [PROPOSED] |

#### 3.4.4 Equity versus rates versus gold

- **Equity** headlines ("stocks rally", "Wall Street slumps") are the closest to what a three-class tone model is built for, but
  they are market-level, not company-level (domain mismatch above).
- **Rates** polarity is ambiguous for markets: "Fed signals more hikes" is hawkish; its text tone is neutral or negative, but its
  meaning for an equity-versus-bond instrument depends on the instrument. A tone model scores wording, not market direction.
- **Gold** is thin (about 1 member row per batch in the sample) and its direction depends on rates and the dollar, not on the
  tone of a gold headline.
- A single `expected_model_id` per run (`features.py:106`, `SentimentConfig`) means **one model for every theme**. If one model
  is not validated for each theme, the design needs per-theme model identity, which is a schema change.
- Therefore the sentiment feature is a *text-tone* feature whose relationship to asset behaviour is itself the research
  question; it must be validated per theme and cannot be assumed to transfer [PROPOSED].

**Conclusion.** No model, licence or dependency can be recommended on evidence available here. **BLOCKED** pending an
explicitly authorised, metadata-only check (model card, licence, label map) and a decision on a polarity-validation set.

### 3.5 Workstream 5 — Full-window feasibility

Window: 2021-12-01 00:00 to 2026-07-20 19:45 UTC (1,693 days; the minimal window that supports the existing walk-forward,
B2-H `:440`). Optional holdout to 2026-09-10 adds 4,992 slots.

| Quantity | Value | Basis | Class |
| --- | --- | --- | --- |
| Expected / listed / absent slots | 162,512 / 160,658 / 1,854 (1.14%) | Master list sum, `reports/phaseB2G_gdelt_pilot_audit.md:244-247` | VERIFIED (one list snapshot) |
| Listed bytes | 860,483,377,717 (0.860 TB); +21.6 GB with holdout | same | VERIFIED |
| Mean / median file | 5.36 MB / 4.94 MB; yearly means 4.64-6.15 MB | `:252-264` | VERIFIED |
| Measured throughput | 41.8 Mbit/s overall list; 41-44 Mbit/s per file; 1.1-1.4 s latency | B2-G, single measurements | MEASURED once |
| B2-M run | 192 batches, 384 requests, 1,000,147,201 B, 8 min 49 s, no retries | `reports/phaseB2M_development_sample_acquisition_report.md:142-149` | MEASURED |
| Request count, full window | about 321,000 (two per slot: header check plus download, `engine.py:259-361`) | 160,658 x 2 | extrapolated |
| Elapsed, sequential | about 91-111 h (B2-G) or about 123 h (192-batch rate of 2.76 s per slot times 160,658) | two bases agree within ~25% | ESTIMATED / extrapolated |
| Elapsed, parallel | about 43-47 h | B2-G; parallelism **UNVERIFIED**; the shipped config runs sequentially | UNVERIFIED |
| Parse CPU | about 3.7-7.8 core-hours | B2-G, from 0.108 s per file measured once | ESTIMATED |
| Memory, parse | about 35 MB per typical file, 80-90 MB for the largest (51 MB) | B2-G streaming | MEASURED once / scaled |
| English rows | about 206-223 million | B2-G | ESTIMATED |
| Captured rows | 10.96% in the sample (26,854 of 244,936); B2-G 10.4%; B2-H range 6-14% | measured / estimated | about 23 million (12-31 million) extrapolated |
| Theme member rows per batch (sample means) | equity 14.33, rates 15.15, gold 1.01 | probe, 192 batches | MEASURED |
| Theme member rows per day | about 1,376 / 1,454 / 97 (total about 2,927 incidences) | x 96 batches | extrapolated |
| Theme rows over the window | about 4.96 million incidences; about 4.2 million distinct records after the measured multi-theme overlap | x 1,693 days; overlap from the probe | extrapolated |
| Records to score after same-batch dedup | about 3.3 million (21.4% measured same-batch share removed); plausible range **2.5-5 million** | volume varies by year; cross-batch dedup unmeasured | extrapolated, low confidence |
| Inference time | **about 5-45 hours** CPU | 2.5-5 million records at an assumed 30-150 per second | UNVERIFIED, extrapolated |
| Storage: filtered input | about 1.7-4.3 GB gzip (B2-G); about 3.3 GB at the sample rate | 140 B/row gzip measured on 154 rows (B2-G) | ESTIMATED |
| Storage: scored table | about 0.2-1.2 GB uncompressed for 3-5 million records (about 60-250 B/row, assumed) | schema size | UNVERIFIED, extrapolated |
| Dedup state | in-memory URL map about 1.5 GB for members only, about 7 GB for all captured rows (assumed ~300 B/entry) | 3.2.2 | UNVERIFIED, extrapolated |

**Discrepancy to flag.** B2-H estimated `ECON_STOCKMARKET` at about 3,000-7,000 rows a day (`:569`); the measured equity
**series members** are about 1,376 a day. The two count different things (theme presence versus filter membership after
company exclusion and US conditions), but any plan must use the member counts [VERIFIED reading; reconciliation of the two
definitions UNVERIFIED].

**Representativeness.** The sample is 192 isolated batches from 2021-12-02 to 2023-12-24 across 170 UTC days and all 24 hours
[MEASURED]. It contains no 2024-2026 data, no outage period, no weekend-specific design, and no contiguous batches, so
cross-batch dedup, near-empty rules and day-level theme volumes are not measurable from it.

**Candidate incremental design [FUTURE, not implemented].**

1. Process **chronologically, one UTC day at a time**; commit each day atomically (the existing engine already does this).
2. Run cross-batch dedup as a **separate offline pass** over the committed day files, with persisted, disk-backed story state
   and a documented warm-up, keyed by the normalised title hash.
3. Score **unique normalised titles once** per `(title_hash, model_revision)`; cache to an append-only table; resume by day.
4. Build features per interval only when every touched day file is committed and every slot state is terminal (G5).
5. Freeze each stage's output with a hash (the manifest already hashes day files) so a rerun is byte-comparable.
6. Fixed budgets per stage (bytes, requests, hours) with a refusal when exceeded, mirroring `config.py:45-47`.

None of this was built or run. A **separate gated phase with its own switch** would be required for the download itself
(`__init__.py:17`): the existing 1.3 GB / 1.5 GB / 1,200-request limits (`config.py:45-47`) cannot cover it.

### 3.6 Workstream 6 — Research experiment design

#### 3.6.1 Constraints from the project (VERIFIED, not changed here)

- Forecasts never feed the optimizer as expected returns (`docs/PROJECT_PLAN.md:162`); the market signal is a category that
  may nudge within the compliance envelope (`RESEARCH_ENHANCEMENT_ARCHITECTURE.md:680-687`). Sentiment never triggers a buy or
  sell and sits last in precedence (ADR-016, `docs/DECISIONS.md:312`).
- The existing walk-forward: 504 initial training days, 63-day test windows, 5-day embargo, `random_state=42`, five
  instruments (`^IXIC`, `^NDX`, QQQ, AGG, GLD), 630 test observations, forecast horizon 1 day, volatility defined as 20-day
  realised standard deviation (`models/metrics.json`, market section) [VERIFIED].
- Sentiment inputs are unvalidated: the filter is a candidate (`filters.py:8`), the B2 evaluation cannot decide without
  independent labels, and no polarity truth exists. **Unvalidated sentiment is not an input to any model**
  (`RESEARCH_ENHANCEMENT_ARCHITECTURE.md:542`).

#### 3.6.2 Candidate targets (the target is NOT approved)

| Target | Source | Strengths | Weaknesses | Notes |
| --- | --- | --- | --- | --- |
| T1 next-day return | existing | Continuity | Existing models are at noise level; sentiment effects undetectable (`:595`) | Rejected as primary in the architecture doc, not approved |
| T2 next-day direction | existing | Simple | 630 observations give about 2-3.9 point uncertainty on accuracy (`:596`) | Same |
| T3 forward 5-day realised-volatility category (Low/Normal/High, tercile cut points from training only) | proposed `:598-604` | Persistent, measurable, GARCH is a strong baseline, fits the recommendation layer | Overlapping 5-day labels cut the effective sample; embargo at least 5 days | **PROPOSED primary**, awaiting approval |
| T4 regime class (Trending/Volatile/Range-bound) | existing, ADR-016 | Matches delivered system | Label is a function of trailing returns: overlap-leakage risk | Secondary |
| T5 20-day realised volatility (continuous) | existing definition | Continuity with `metrics.json` | Autocorrelation and overlap; metric choice open | Alternative to T3 |

Implications that apply to every target: the effective sample after overlap is smaller than 630 (a null result must be
interpretable); three themes by five instruments by several targets is a large comparison family; the instrument mapping is
asset-class level, not ticker level (GDELT supports no ticker mapping, `RESEARCH_ENHANCEMENT_ARCHITECTURE.md:288-289`).

#### 3.6.3 Candidate arms

| Arm | Inputs | Purpose | Constraint |
| --- | --- | --- | --- |
| **A market-only** | Existing price, return, volatility, momentum, volume features | The bar to beat | Existing artifacts are not retrained unless approved |
| **B sentiment-only** | S2 daily features (`mean_net`, dispersion, `no_news`, counts, coverage) | Whether sentiment alone carries information | Includes `B0`: GDELT native tone, no model |
| **C hybrid** | A + B | The claim under test | Missing sentiment is a missing value with a mask, never neutral |
| **D existing** | Naive, ARIMA/GARCH, regime rule | Continuity | Unchanged |
| **E time-shuffled control** | C with the sentiment block permuted in time | Detects pipeline artifacts and spurious gains | See below |

**Control design [PROPOSED].** Permute the *sentiment feature rows* across dates, not within a day, in blocks long enough to
preserve their autocorrelation (for example a circular shift by at least the maximum label window plus the embargo), applied
**within each training fold and each test window identically in distribution**, repeated over many fixed seeds (42 and derived),
and with the **missingness mask moved together with the values** so that coverage patterns cannot leak. A hybrid that beats the
unshuffled baseline by no more than the shuffled distribution's spread is not evidence. Also run a coverage-only control (counts
and `no_news` without the sentiment values) to separate "news volume" from "sentiment".

#### 3.6.4 Point-in-time controls and checks

| Control | Detail |
| --- | --- |
| Alignment | The return dated r may use only origin days up to the trading day before r (`phaseB2H:444`); same-day news is never used |
| Cutoff | `(cutoff(prev), cutoff(d)]`, verified availability only; 16:00 ET, 13:00 ET on approved early closes. Holiday and early-close calendars are **unapproved inputs** |
| Chronology | Expanding-window walk-forward, 504 initial days, 63-day windows, embargo at least the label window (5 days for T3) |
| Final holdout | A period untouched until the last step; the optional 2026-07-21 to 2026-09-10 data (B2-H) is a candidate |
| Fit on train only | Scalers, category cut points, imputation rules, any feature selection; stored with the model |
| Seeds and versions | `random_state=42`; log library versions, filter version, dedup policy version, model revision and weights hash, dataset hashes |
| Leakage tests (extend the existing S2 tests) | (1) Appending any later article never changes an earlier row (exists). (2) Randomising all articles after a cutoff leaves features unchanged. (3) No feature column is a function of the label window. (4) Same inputs in shuffled order give identical features (exists). (5) A rerun reproduces day-file hashes. (6) Dedup state at time t is identical whether the run continued past t or stopped at t. (7) Scored values depend on title only, never on batch order |
| Metrics | By target: macro-F1, balanced accuracy, per-class recall (categories); MAE/RMSE against naive and GARCH (continuous); calibration if probabilities are used |
| Uncertainty | Block or stationary bootstrap confidence intervals over folds; Diebold-Mariano-style tests with a HAC variance for overlapping labels [PROPOSED]; report effective sample sizes |
| Multiplicity | Pre-register the family (instrument x target x arm); a correction (for example Holm) across the family; report negative results |
| Eligibility | B2-H's pre-registered rule (95% of training intervals with 10 or more unique stories) decides whether a theme is usable; gold may be reported as not usable rather than padded |
| Portfolio claims | Need a separate backtest; a better forecast metric alone shows nothing about outcomes (`:657-659`) |

Nothing in 3.6 is approved; target, calendar, dedup, coverage and model remain open.

---

## 4. Evidence table

| Decision / question | Current evidence | Options | Recommendation (not approval) | Approval required | Blocker |
| --- | --- | --- | --- | --- | --- |
| Does S2.2's reconciliation match the pipeline? | 0/192 batches under S2.2; 192/192 under per-theme contract (probe) | Keep; per-theme contract C1; drop reconciliation | C1 | Contract C1 | **S2.3 corrective phase** |
| How are late batches assigned? | Probe: D2 `no_news=True`, D3 unaccounted; sample has 0 late | C2-A, C2-B | C2-A or C2-B; decide with real late-rate evidence | C2 choice | Late rate unmeasured; needs `available_at` in slot summary |
| Dedup and story updates | B2-H primary excludes updates; S2.2 keeps versions; cross-batch dedup unrun | P0-P4 (3.2.2) | Decide before building; run as separate pass | Dedup policy ADR | Cross-batch rates unmeasured |
| Coverage threshold | 0.75 proposed (B2-H `:501`); sensitivity 0.5/0.9 | 0.5, 0.75, 0.9, none | Treat as a sensitivity range | Threshold approval | Theme-level coverage undefined |
| Near-empty rule | 10% of 14-day median, min 7 obs (`engine.py:35`); unknown in sample | Keep; theme-level; exclude from coverage | Measure its effect before approval | Rule approval | Needs contiguous data |
| Scoring-coverage threshold | None exists | Fixed fraction; minimum count; none | Report-only until a rule is approved | Threshold approval | None technical |
| Early-close / holiday calendars | Proposed list in code; holidays are caller input | Approve proposed; derive from stored market dates | B2-H uses stored trading dates; use that | Calendar approval | 2026 Nov/Dec half-days outside window |
| Theme-specific cutoffs | Single equity cutoff | Per-theme cutoffs | Defer | Target + calendar | Forecast target |
| Real model and licence | No card, no weights, no S1 report | Transformer; lexicon; GDELT tone; LLM | Evaluate GDELT tone arm first; others after checks | Model + licence | Metadata check not authorised |
| Dependency approval | No `torch`/`transformers`; TF 2.17 present | Isolated env; none | Isolated environment only | Per `CLAUDE.md` section 5 | Resolver check needs network |
| Polarity validation set | None | Financial PhraseBank (CC BY-NC-SA); human-labelled sample | Human, hindsight-free | Labelling plan | No labels; none may be faked |
| Full-window acquisition | 0.86 TB, about 321k requests; no switch | Phased; sample only | Separate gated phase with own limits | Explicit authorisation | Switch absent by design |
| Forecast target | T3 proposed; T1/T2 rejected as primary | T1-T5 | T3 | Target approval | Open |
| Evaluation protocol | Existing walk-forward; control design 3.6.3 | As above | As 3.6.4 | Pre-registration | Open |
| Cross-theme model identity | One `expected_model_id` | Per-theme models | Decide with model choice | Schema change ADR | Model choice |
| Hash naming | `title_sha256` raw vs `title_hash` normalised | Rename; both | Name both | Schema ADR | None |

---

## 5. Measured facts versus assumptions

**Measured or verified in this phase or earlier local artifacts**

- The pipeline structure, counts and states in 2.2; the absence of any cross-batch dedup in the engine.
- The 192-batch sample: 244,936 English rows; 26,854 captured; themes 2,751 / 2,909 / 193; same-batch duplicates 18.0%; median
  title 62-64 characters; 0 late; near-empty unknown for all 192.
- The reconciliation probe (0/192 versus 192/192), the multi-theme overlap, the late-batch behaviour of S2.2 (synthetic).
- Master-list totals (162,512 / 160,658 / 1,854; 0.860 TB); one-off throughput and parse timings from B2-G; the B2-M run.
- Software and hardware facts in 3.4.1; 90 sentiment tests re-run (section 8).

**Assumptions and extrapolations (all UNVERIFIED)**

- Everything per-day and per-window: sample means x 96 x 1,693; overlap and dedup shares applied to the whole window.
- Cross-batch duplicate rates, theme volumes outside 2021-2023, late-file frequency.
- Model size, token counts, FLOPs, throughput, memory, licence, label order, dependency compatibility, GPU support.
- Dedup state memory; scored-table size.
- Network time for the full window and the parallel speed-up.

---

## 6. Risks, open questions and dependencies

**Risks**

1. S2.2's contract would reject real data; a late batch could be reported as verified no-news (3.1). Highest priority.
2. The filter is a candidate and unvalidated; every sentiment feature inherits that (B2 evaluation still lacks independent labels).
3. Domain mismatch: a company-trained model scored on market-level headlines, with no polarity ground truth.
4. Gold is thin; the eligibility rule may remove it.
5. Informative missingness from the near-empty rule and from the chronological-baseline dependency (G6, G7).
6. Memory and ordering risk in cross-batch dedup (3.2.2).
7. An effective sample of a few hundred overlapping observations: only large effects are detectable.
8. A dependency change in the project environment could break the TensorFlow models (mitigate with isolation).

**Open questions**

- Which clock assigns a slot to an interval (C2)? What is the real late-file rate in the full window?
- Which dedup unit is primary (P1 versus P3/P4)? What are the real cross-batch rates?
- Is the 10%/14-day near-empty rule acceptable, and should coverage be per theme?
- Which model, licence and dependency path, and where do polarity labels come from?
- Which target, calendar and holdout?

**Dependencies (in order)**

`S2.3` corrective phase (C1, C2, adapter spec) → approvals A1-A5 below → offline, synthetic-data implementation of the adapter
and the dedup pass → model/licence/labelling decisions → separately authorised acquisition → scoring → features → experiments.

---

## 7. Minimal approval checklist for a later implementation phase

Nothing here is approved. Each line is a decision the project owner would make.

- [ ] **A1** Contract C1 (per-batch and per-theme reconciliation) adopted, and S2.3 authorised to correct S2.2 offline.
- [ ] **A2** Late-batch rule: C2-A, C2-B or another, and the slot summary extended with `available_at_utc`, theme and a state reason.
- [ ] **A3** Dedup and story-update policy (P0-P4) and the primary counting unit; whether cross-batch dedup runs as a separate pass.
- [ ] **A4** Coverage rule: source threshold (or sensitivity range), near-empty rule, and whether coverage is per theme.
- [ ] **A5** Scoring-coverage handling (report-only, or a threshold).
- [ ] **A6** Early-close and holiday calendars (and that theme-specific calendars stay deferred until the target is approved).
- [ ] **A7** Forecast target and the evaluation protocol, including the holdout and the multiplicity family.
- [ ] **A8** Hash and field naming (`title_sha256` versus normalised hash) and the per-theme model identity question.
- [ ] **A9** Model, licence and dependency route (an isolated environment), after an explicitly authorised metadata check.
- [ ] **A10** Polarity-validation data: source, human-labelling plan, no hindsight, no fabricated labels.
- [ ] **A11** Full-window acquisition: a separate gated phase with its own switch, data allowance, request and time limits, and a retention decision.
- [ ] **A12** Inference budget (hours, hardware) and where scored tables are stored (git-ignored, outside `datasets/raw` immutability rules).
- [ ] **A13** Confirmation that no provider, no off-machine text transmission and no LLM scoring is part of the primary arm.

---

## 8. Checks performed, and what was deliberately NOT done

### 8.1 Checks performed

| Check | Result |
| --- | --- |
| Read `CLAUDE.md`, `PROJECT_PLAN.md` (§2.4 line), `RESEARCH_ENHANCEMENT_ARCHITECTURE.md` (7-13), `MEMORY.md` (S2 entries), B2-F/G/H/M reports (relevant sections), the sentiment code and tests, `parser.py`, `engine.py`, `dedup.py`, `filters.py`, `output.py`, `manifest.py` (states, counts, baseline), `coverage.py`, `availability.py`, `session_calendar.py`, `timeutil.py`, `__init__.py`, `config.py` limits | Done |
| Searched for the S1 audit, S2.1 review and S2.2 report as files | Absent (2.1) |
| Local software and hardware inspection | Done (3.4.1) |
| Three read-only probes (manifest opened `mode=ro&immutable=1`; day files read; one synthetic in-memory run) | Done; scripts are in the scratchpad only |
| `pytest tests/backend/data/gdelt/test_sentiment_scaffold.py -q -p no:cacheprovider` | See final report message for the exact result |
| `git status` | Only this report added in the project; see final message |

### 8.2 Deliberately not done

- No edit to `schema.py`, `fake_scorer.py`, `features.py`, any test, the acquisition code, the compliance rules or any gate.
- No network access, no download, no package installation or dependency resolution, no model weights, no inference.
- No full-window or additional GDELT acquisition; the `NETWORK`/`DEV_SAMPLE` switches were not touched.
- No provider call and no transmission of any text. No Gate A-D record, freeze, build lock or adapter.
- No read of `key_sealed.csv`, `annotation_*` files, AI-only suggestions, labels, `.env` or API keys.
- No change to D8 criteria, the D12/D12.1 guard, the D13 lock, or any approved decision.
- No decision taken on dedup, coverage, calendar, model, licence, dependency, target or acquisition.
- No staging, commit or push; no unrelated full-project, frontend or hosted-database tests.
- No S4, no S2.3, no implementation. This report only *proposes* S2.3.
