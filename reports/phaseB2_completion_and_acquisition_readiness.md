# Research Enhancement Track — Phase B2: Completion and Acquisition Readiness

**Type:** the closing report for Phase B2 (historical financial-news source evaluation). **Full
historical acquisition and B3 are NOT approved.** Blockchain work is deferred until the AI track is
complete.

**Date:** 2026-10-13 (UTC).

**Builds on:**

- B2 (`phaseB2_historical_news_source_evaluation.md`);
- B2-F, B2-G, B2-H, B2-I and B2-J;
- B2-K (`phaseB2K_gdelt_tool_implementation_report.md`);
- B2-L (`phaseB2L_gdelt_development_sample_and_filter_review.md`).

All earlier reports are preserved.

**Labels:**

- **[VERIFIED]**: confirmed by the repository, a test or a local check.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## 1. Answers to the completion questions

| Question | Answer |
| --- | --- |
| Was the isolated tool implemented? | **Yes** [VERIFIED]: `backend/wealthpilot/data/gdelt/`, standard library + PyYAML only, not imported by the application |
| Exact tests run and results | `pytest tests/backend/data/gdelt -q`: **146 passed, 0 failed** (40 + 23 + 17 + 21 + 30 + 15 across six files). Compile check with warnings as errors: pass. AST unused-import scan: 0. `pytest tests --collect-only`: 1,570 collected, no errors. The DB-backed full regression suite was **not run**: it needs network access to the hosted database, which this phase forbade |
| Were development batches acquired? | **No** [BLOCKED]: no approval record, data allowance unconfirmed, build locks off |
| Actual transfer size and request count | **0 B, 0 requests.** No network request of any kind was made in B2-K or B2-L |
| Was a real labelled review completed? | **No.** No titles exist to label; no human or AI labels were produced |
| Filters empirically supported / unsupported / unverified | **Supported:** none. **Unsupported:** none. **Unverified:** all of `gdelt_filter_v1` (`EQUITY_US`, `RATES_US`, `GOLD`, the company flag, the flag-only themes, S1/S2) |
| Did the confirmation-sample trigger fire? | **No.** It cannot: it depends on stage D, which was not acquired. Stage C was not accessed |
| Is full acquisition technically justified? | **Not yet.** The technical route is feasible (B2-G, B2-H), but the capture rule is irreversible and has no labelled evidence. In addition, the tool's full-window path (fresh master list, diff, re-checking unlisted slots) is not built. Justification needs the development review first |
| What approvals remain? | Section 4 |
| Is B2 complete? | **Complete in research design; blocked on one concrete deliverable:** the development sample and its labelled review. Section 5 |

---

## 2. Proposed research configuration: `gdelt_research_config_v1` [PROPOSED; not approved]

This consolidates decisions already made with the proposals from B2-H to B2-K. **Nothing here is
promoted to an approved production setting.** Items marked *pending review* must be revisited after
the labelled development review.

```yaml
config_version: gdelt_research_config_v1          # PROPOSED
source: GDELT 2.0 GKG, English stream only        # DECIDED (B2-I)
scope: market level; no instrument-specific claims  # DECIDED
window: 2021-12-01 00:00 -> 2026-07-20 19:45 UTC (minimal, ~0.86 TB)  # DECIDED, subject to acquisition approval
parser_version: gkg_parser_v1                     # B2-K
filter_version: gdelt_filter_v1                   # candidate, pending review; spec SHA-256 73788c1f...
filters:
  series: [EQUITY_US, RATES_US, GOLD]             # B2-H 4.4, pending review
  flag_only: [WB_2936_GOLD, ECON_INFLATION, ECON_DEBT, WB_1045_TREASURY, ACT_YIELD,
              EPU_CATS_MONETARY_POLICY, ECON_IPO, ECON_EARNINGSREPORT, ECON_BUBBLE]
  company_notices: flagged, excluded from every series
  sensitivity: [S1 broad, S2 title-only, S3 article-level counts]
  capture_rule: B2-H 4.3, pending review -- IRREVERSIBLE once the full archive is filtered
source_fields_retained: B2-K output columns (ids, batch_ts, available_at, source, URL + canonical URL,
  title (local only), title_hash, page time (diagnostic), 7 tone values, candidate themes with mention
  counts, ECON_* themes, countries, US flags, organisations matched, phrase hits, flags, memberships,
  S1/S2, duplicate mark, versions)
  full_v1themes_string: OPEN decision (recommended: keep; ~2-3x storage)
audit_sample: 1 in 1,000 uncaptured rows, hash-selected by record ID   # B2-I, PROPOSED
duplicates: B2-H 4.6 causal rules; updates kept as their own rows; 72 h syndication window  # PROPOSED
availability: max(nominal, verified Last-Modified) + 15 min; fail closed (B2-K rules)  # PROPOSED, implemented
market_session: origin d gets batches with cutoff(prev trading day) < available_at <= cutoff(d);
  cutoff 16:00 America/New_York; trading days = stored market_data dates (+2021-12-31)  # PROPOSED
early_close: 13:00 ET on the 9 official NYSE early closes in the window (B2-H 5.4)  # PROPOSED
missing_data: absent, failed, invalid or unverifiable batches are missing; values null with a reason;
  never neutral, never zero, never imputed or carried forward  # DECIDED principle
near_empty: rows < 10% of the median of the same UTC slot over the previous 14 days (>= 7 observations);
  NULL when no baseline; backlog > 3x; kept, flagged, never back-dated  # PROPOSED
coverage_threshold: 0.75 primary, PROVISIONAL; sensitivity 0.50 and 0.90  # PROPOSED, not approved
theme_sufficiency: a series is usable only if >= 95% of adequately covered training intervals hold
  >= 10 unique stories; otherwise reported unusable, never padded or merged  # PROPOSED (B2-H 6.3)
provenance: master-list SHA-256 (audited 7e5d2c2e...), code/spec/list hashes per run, every HTTP
  attempt, per-file MD5/SHA-256/CRC, per-day file SHA-256, manifest schema gdelt_manifest_v1.1
```

**Why the 0.75 threshold stays provisional:** no measured row-level coverage exists. The B2-H slot
coverage (98.86% of the window) says nothing about rows per theme.

---

## 3. Full-acquisition plan, refined [PROPOSED; not started]

The development results that would refine it do not exist, so the plan below is unchanged from
B2-H/B2-I, except where marked "new (B2-K)".

| Topic | Plan |
| --- | --- |
| Transfer | Payload 860,490,716,162 B = 0.8605 TB [VERIFIED]. On the wire 0.869–0.904 TB with 1–5% overhead [ESTIMATED]. Plus a fresh master list ≈128.5 MB. The 37-return tail is **not** included |
| Processing time | Network-bound. One file at a time: ≈93–111 h at the B2-G rate of 41–44 Mbit/s; latency alone adds 49–62 h. CPU ≈4–8 core-hours [ESTIMATED] |
| Storage | Captured rows ≈2–5 GB gzip (≈4–13 GB with the full theme string); manifest ≈0.2 GB; logs ≤0.1 GB. Free disk now ≈184 GB on the output drive [MEASURED] |
| Checksums and manifest | MD5 from the master list, or ETag for unlisted files; zip structure and CRC-32; SHA-256 recorded; `gdelt_manifest_v1.1` (B2-K) |
| Retry and resumption | Up to 5 attempts with 4–64 s backoff, then a final pass at least 65 min later. Atomic per-day commits; verified shards reused after a crash (implemented, B2-K) |
| Unlisted timestamps | The master list is incomplete (B2-H). 179 unlisted non-outage slots are re-checked: two fresh header checks at least 65 min apart, at most 3 per slot. The existence rules are implemented; **the window-wide driver is not built yet** (new, B2-K) |
| Known gaps | 1,853 absent slots in 50 runs. The June 2025 outage (1,674 slots) is `absent_accepted` and never requested |
| Availability failures | **New (B2-K):** batches whose server time cannot be verified fail closed and count as missing. Their real rate is unknown until real headers are seen [UNVERIFIED] |
| Near-empty files | Causal 14-day baseline, flagged, missing for coverage (implemented) |
| Retention and cleanup | Raw zips never kept for the full window; captured rows, audit sample, manifest and logs kept for the research track; path-guarded cleanup of `tmp/` |
| Guards | Byte cap per run and per billing period (required; no default), request cap, disk floors, temporary cap, stop file, sequential by default |
| Your bandwidth and data cap | **Unknown; not inferred.** Still needed: plan type and metering; monthly allowance and remaining amount with its reset date; what happens above the cap; fair-use limits; sustained (not advertised) speed at the planned run time; whether the machine can stay on for days. Full list in B2-I §9.1 |

**Before any full acquisition** (in addition to approval):

- a labelled review and a frozen capture rule;
- an implementation step for the window-wide driver (master-list fetch and diff, unlisted re-checks,
  per-period byte budget);
- the ADR (B2's proposed ADR-043), written after approval only.

---

## 4. Approvals outstanding

1. **Development sample:**
   - confirm the data allowance (at least 1.5 GB) and approve the sample;
   - write the local approval record;
   - authorise the reviewed change that lifts the two build locks.
2. **Annotator arrangement**, and the B2-I rubric and thresholds, before the first label.
3. **Confirmation sample:** only if stage D fires its trigger, with a separate approval.
4. **Stored-columns decision:** whether to keep the full `V1THEMES` string (recommended).
5. **Proposed policies:**
   - the early-close rule;
   - the missing-data and near-empty policy;
   - the coverage threshold (provisional).
6. **Full acquisition:** after the review, plus the bandwidth checklist, plus the window-wide
   implementation step. Then the ADR.

**Not requested:** B3 and blockchain.

---

## 5. Phase B2 status

**Complete:**

- source evaluation (B2);
- feasibility and costing (B2-F);
- pilot and archive audit (B2-G);
- pre-acquisition readiness (B2-H);
- review protocol, rubric and pre-registered sample (B2-I);
- approval checklist (B2-J);
- an implemented, tested, isolated acquisition tool (B2-K).

**Blocked on one concrete deliverable:** the development sample and its labelled filter review (B2-L).

- **What unblocks it:** your data-allowance confirmation and approval record. No technical blocker
  was found.
- **What remains impossible until then:**
  - freezing the irreversible capture rule;
  - claiming any filter quality;
  - justifying the full acquisition.

**Therefore B2 is not complete as an acquisition-readiness phase.** Only its research design is
complete.
