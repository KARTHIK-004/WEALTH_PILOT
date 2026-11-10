# Research Enhancement Track — Phase B2-K: GDELT Tool Implementation Report

**Type:** code and offline tests only. **No network request was made.** The development sample, full
acquisition and B3 are not authorised by this phase. Blockchain work has not started.

**Date:** 2026-10-13 (UTC).

**Instructions followed:**

- **The B2-K prompt:** build the tool; offline tests; development sample disabled; full acquisition
  always refuses.
- **The later B2 master prompt:** it allows a bounded development-sample download only if an approval
  record exists, your data allowance is confirmed, and the preflight passes. Neither of the first two
  exists, so the tool stays offline. See `reports/phaseB2L_gdelt_development_sample_and_filter_review.md`.

**Builds on:**

- `reports/phaseB2J_development_sample_approval_checklist.md` (design);
- `reports/phaseB2I_filter_review_and_acquisition_preparation.md` (protocol, schema, sample);
- `reports/phaseB2H_pre_acquisition_readiness.md` (filter v1, deduplication, calendar).

**Labels:**

- **[VERIFIED]**: confirmed by a test, a local check or the repository.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## Summary

- **The isolated tool is implemented** [VERIFIED].
  - **Location:** `backend/wealthpilot/data/gdelt/`.
  - **Size:** 24 Python files (22 modules plus `__init__` and `__main__`), the manifest schema, the candidate filter specification, the
    pre-registered sample lists, an example config and a README.
  - **Dependencies:** the standard library and the already-declared PyYAML only.
- **Offline tests: 146 passed, 0 failed** [VERIFIED].
  - **Where:** six files in `tests/backend/data/gdelt/`.
  - **Network guard:** every test runs with sockets and DNS blocked, and fails if a connection is
    attempted.
  - **Database guard:** the application's engine factory raises.
- **Static checks:** byte-compilation with warnings as errors passes; an AST scan finds no unused
  imports. No linter is installed, and none was added.
- **Isolation** [VERIFIED by tests]:
  - no application module imports the package;
  - it imports nothing from `api`, `agents`, `core` or `db`;
  - no existing file was edited.
- **Safety gates** [VERIFIED by tests and by running the CLI]:
  - the offline dry run works;
  - `fetch-sample` refuses, because the development sample is disabled in this build;
  - `acquire` always refuses;
  - the confirmation sample cannot be loaded without a valid trigger and a separate approval;
  - the HTTPS transport cannot open a connection: network is disabled in this build.
- **Genuine defects found while testing, and fixed:**
  1. A corrupted deflate stream raised `zlib.error`, which was not caught. It is now reported as an
     integrity failure.
  2. YAML read an unquoted all-digit hash in an approval record as a number. Such a record is now
     refused with a "write it in quotes" hint, and the example config quotes the hash.
- **Not run:** the full backend regression suite, because it connects to the hosted database and
  this phase allows no network access. Collecting the whole suite succeeds: 1,570 tests, the new 146
  included.

---

## 1. Files

**Created** (all new; no existing file changed):

| Path | Content |
| --- | --- |
| `backend/wealthpilot/data/gdelt/__init__.py` | Build locks (all `False`), versions |
| `.../errors.py`, `timeutil.py`, `availability.py`, `session_calendar.py`, `coverage.py` | Errors; UTC parsing; availability rule; cutoffs; missing-vs-zero counts |
| `.../config.py`, `guards.py` | Config, tighten-only limits, approval gate; resource guards |
| `.../existence.py`, `transport.py`, `integrity.py`, `parser.py` | Header-check states; locked HTTPS transport; integrity; incremental parser |
| `.../filters.py`, `specs/gdelt_filter_v1.yaml` | Versioned candidate filters (SHA-256 `73788c1f…`) |
| `.../dedup.py`, `manifest.py`, `manifest_schema.sql`, `output.py`, `cleanup.py`, `events.py` | Duplicates and updates; manifest; atomic output; guarded cleanup; title-free log |
| `.../engine.py`, `sample.py`, `review.py`, `preflight.py`, `cli.py`, `__main__.py` | Processing and the sample run; sample lists and stage C gate; review files; dry run; command line |
| `.../sample_data/stage_d.txt`, `stage_c.txt`, `frame_known_absent.txt` | B2-I Appendix A lists, verbatim, with SHA-256 `a459a3fb…` and `b580e8cf…` (equal to the commitments); the 169 known-absent frame slots from B2-I Appendix B |
| `.../config.example.yaml`, `README.md` | Example config (no approval); package documentation |
| `tests/backend/data/gdelt/conftest.py` + 6 test files | Offline fixtures, guards and tests |
| `reports/phaseB2K_gdelt_tool_implementation_report.md` | This report |

**Unchanged:**

- dependency manifests: `backend/pyproject.toml`, lockfiles, the `pip freeze` fingerprint
  `3393be50…`;
- `.gitignore`, application code, schema and migrations;
- models, training scripts and market data;
- `wealthpilot/data/__init__.py`.

The working-tree changes that existed before this phase are untouched. Git status differs from the
start of the phase only by the two new folders.

---

## 2. Architecture and isolation [VERIFIED]

**Pipeline:** header check → existence state → sequential download → size and checksum → zip
structure → availability rule → incremental parse (CRC confirmed at the end of the member) →
candidate filters → within-batch duplicates → per-slot shard → atomic daily commit.

**Isolation, enforced by tests in `test_sample_isolation.py`:**

| Rule | Test |
| --- | --- |
| Package imports only the standard library, `yaml`, `wealthpilot.data` and itself; nothing from `sqlalchemy`, `wealthpilot.db` or `wealthpilot.api` | AST scan of every module |
| No other module under `backend/wealthpilot` imports it; `wealthpilot/data/__init__.py` does not mention it | AST scan of the application |
| No socket connection or DNS lookup during any test | Autouse fixture; asserts zero attempts |
| No application database access during any test | Autouse fixture makes `get_engine` raise |

---

## 3. Availability timestamp [VERIFIED by tests]

**The rule:**

`availability_time = max(batch timestamp, verified server Last-Modified) + 15 minutes`

It is the pure function `availability.compute_availability`. All values are UTC; naive datetimes are
rejected.

**What makes a server timestamp unverified.** The batch fails closed: no rows are kept, and the
reason is recorded.

| Condition | Reason recorded |
| --- | --- |
| `Last-Modified` missing or blank | `last_modified_missing` |
| `Last-Modified` not a strict GMT IMF-fixdate (other zones and obsolete forms included) | `last_modified_unparseable` |
| `Date` header missing or unreadable | `server_date_missing` / `server_date_unparseable` |
| `Last-Modified` later than `Date` (+120 s) | `last_modified_after_server_date` |
| `Last-Modified` more than 60 min before the nominal time | `last_modified_implausibly_early` |
| Zip member time differs from `Last-Modified` by more than 10 min | `zip_member_time_disagrees_with_last_modified` |
| Cached response (`Age` > 0) with no zip time to corroborate it | `cached_timestamp_uncorroborated` |
| Negative `Age` | `age_header_invalid` |

**Flags that only push availability later:**

- `written_after_nominal`;
- `late` (more than 15 min after nominal);
- `rewrite_suspect` (more than 24 h after nominal);
- `served_from_cache`;
- `zip_time_corroborated`.

**The page publication time is never an input.** A test stores a 2099 page time as a diagnostic and
shows availability unchanged.

**Assumptions and limitations:**

- **Zip time read as UTC** [VERIFIED for one file in B2-G only]: the zip member time has no time
  zone and is read as UTC. If GDELT ever wrote local times, the rule would fail closed, not open.
- **Corroboration is required:** the CDN serves cached copies. A header request primes the cache
  before the download, so a downloaded file's timestamp is usually cached. It is accepted only when
  the zip member time corroborates it.
- **Today's copy only:** `Last-Modified` describes the file served now. A historical first-publication
  time cannot be proven; the 15-minute margin and the flags are the mitigation.

---

## 4. Manifest: `gdelt_manifest_v1.1` [VERIFIED]

B2-I's schema, with these documented additions:

| Addition | Why |
| --- | --- |
| Existence `available` | Separates "server confirmed" from "downloaded and verified" |
| `availability_status`, `availability_reason`, `availability_flags`; validation `availability_unverified` | The fail-closed rule needs its own recorded state and reason |
| Validation `body_incomplete`; `checksum_basis` | Truncated transfers; which checksum, if any, verified the file |
| `parse_status = parsed_validated` | Separates "parsed and validated" from "committed" |
| `selection`, `sample_round`, `sample_block`; list status `not_consulted` | Provenance for the pre-registered sample. Sample runs verify by header checks, not the master list |
| `run.mode`, `run.selection_sha256`; outcome `stopped_request_budget` | Gate and budget provenance |
| `schema_meta` | Schema version check on open |

**Cleanup status** follows B2-I: it tracks temporary *archive* files only. Raw bodies stay in memory.
Shards are swept separately.

**States** (`manifest.slot_state`): `unverified`, `verified_available`, `in_progress`,
`confirmed_absent`, `absent_inconclusive`, `request_failed`, `inaccessible`, `downloaded_invalid`,
`parsed_validated`, `processed`.

**Two layers of protection:**

- **In code:** every change goes through a method that refuses illegal transitions.
- **In SQLite:** CHECK and foreign-key constraints. A test shows 12 invalid states rejected directly by
  SQLite.

---

## 5. Processing requirements [VERIFIED by tests unless stated]

| Requirement | Implementation |
| --- | --- |
| Incremental ZIP and CSV parsing | 1 MiB reads from the zip member; rows split on LF and decoded one by one |
| Bounded memory | A 20 MB member parsed with a Python allocation peak under 8 MB (tracemalloc test); long rows skipped beyond 8 MiB |
| ZIP integrity and checksums | Size vs Content-Length and expected size; MD5 vs master list or ETag (weak or multipart ETags are not checksums); one member with the exact name; no paths; not encrypted; stored or deflate; expansion at most 400 MB and 10×; CRC-32 at end of read; corrupt deflate caught |
| Deterministic filter versions | Spec refused unless its SHA-256 (line-ending-normalised) matches the registry and it is still marked a candidate; byte-identical day files across runs (test) |
| Batch IDs and UTC availability | `batch_ts`, `available_at_utc` per slot and per row |
| Row, English and per-theme counts | Per reason (field count, decode, date, translated, non-web, oversize, empty, CRLF), English-valid, captured, company items, same-batch duplicates, audit rows; `slot_series_count` per theme and filter version |
| Duplicates without collapsing updates | Same-batch URL/title marks; a causal cross-batch tracker (re-observation, **update kept as its own row**, 72 h syndication), refusing out-of-order input |
| Near-empty warnings | Causal baseline (median of the same UTC slot over the previous 14 days, at least 7 observations); `NULL` when no baseline, never "fine" |
| Atomic daily output | Shards and day files via `.partial` + fsync + `os.replace` + re-read hash; one SQLite transaction per day |
| Interruption and resumption | Crash before rename: shards survive, one commit after resume. Interrupted downloads reset. Corrupt shards reset for re-download. Orphans swept. Committed days never rewritten |
| Temporary-file cleanup | Path-guarded, non-recursive, pattern-checked deletion within `tmp/` |
| Missing never neutral | `coverage.interval_count` returns `None` with a reason below the threshold; a zero only when covered |

---

## 6. Filters [VERIFIED as implemented; quality UNVERIFIED]

**What is implemented:** `specs/gdelt_filter_v1.yaml` encodes B2-H §4 unchanged.

- **Status:** marked `candidate_for_labelled_review`. Loading refuses any other status.
- **Flag only:** the broad gold and rates themes.
- **Company notices:** flagged and excluded from every series.
- **No claims:** no precision or recall is claimed.

**Two readings disclosed here, because the source text was silent:**

1. **S2 (title-only variant):** uses each series' title phrases, the conditional ones included, with no
   US requirement, and excludes company items. B2-H did not state the company rule; the stricter
   reading was chosen.
2. **Sample substitution:** "the next stamp in its block's order" (B2-I) would reach the confirmation
   stamps. The tool skips every stamp in either stage list, so stage C is never used as a substitute.

**Also part of the spec:** the near-miss cue (review cells C6/C7) and the 1-in-1,000 audit-sample
rule (B2-I). They are not filters.

---

## 7. Approval gates and network locks [VERIFIED]

| Mode | Gate in this build | Test evidence |
| --- | --- | --- |
| Offline dry run | Always allowed; no network, writes nothing | `dry-run` CLI test; real run (B2-L) |
| Development sample | **Refused:** `DEV_SAMPLE_ENABLED_IN_THIS_BUILD = False`. With that lock lifted in a test, it still needs a complete record, the matching stage hash, an allowance at least as large as the cap, and `--confirm-network` | Five gate tests |
| Confirmation sample | **Refused:** build lock, plus a trigger record that meets the B2-I rule, plus a separate approval naming the stage C hash | Eight tests |
| Full historical acquisition | **Always refused;** no setting enables it | Gate test and `acquire` CLI test |
| Network transport | `HttpsTransport` refuses unless `NETWORK_ENABLED_IN_THIS_BUILD` is true **and** the authorisation came from the gate | Lock test and forged-authorisation test |

**Defaults are never approval.** A missing config, the example file, an empty section, the string
`'true'` or a partial record never count. Each case is tested.

---

## 8. Resource limits [VERIFIED]

**Defaults** are the B2-J values:

| Limit | Value |
| --- | --- |
| Planned total before any download (refusal threshold) | 1.30 GB |
| Total transfer, retries included (hard cap) | 1.50 GB |
| Requests | 1,200 |
| Free disk | 20 GB at preflight, 10 GB at runtime |
| Temporary disk | 0.5 GB |
| Concurrency | 1; parallel disabled |
| Retries per slot | 5, backoff 4–64 s, `Retry-After` capped at 300 s |
| Re-downloads after an integrity failure | 1 |
| Absence-check spacing | 65 min |
| Fresh `Age` | 60 s |

**Config can only tighten:**

- raising a maximum, lowering a floor, enabling parallel mode or setting concurrency above 1 is a
  configuration error;
- so is setting the planned threshold above the hard cap.

**Budgets count everything:** header checks and retries count as requests, and partial transfers
count as bytes. Tests cover each guard, with no partial slot committed when one trips.

---

## 9. Tests [VERIFIED]

**Command:**

```text
.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider
```

**Result:** 146 passed, 0 failed, 0 skipped, in about 6 s. One pytest-asyncio configuration warning
was already present in the project.

| File | Tests | Covers |
| --- | ---: | --- |
| `test_time_availability.py` | 40 | Stamps (malformed, off-grid, invalid dates); UTC normalisation; strict HTTP dates; the availability rule including every fail-closed reason, cache corroboration and late or rewritten flags; cutoffs, early close, daylight saving, weekends, the 2025-01-09 closure |
| `test_parser_integrity.py` | 23 | Valid parsing and HTML titles; each rejection reason; CRLF; empty and oversize rows; missing final newline; wrong, extra and path-traversal members; encrypted; unsupported compression; not-a-zip; truncated; CRC corruption; corrupt deflate; zip bomb; MD5 and size mismatch; ETag rules; bounded memory; missing vs zero coverage |
| `test_filters_dedup.py` | 17 | Spec hash; edited, unregistered or "approved" spec refused; CRLF-stable hash; normalisation; each series rule; company exclusion; flag-only themes; look-alike themes; pronoun "us" and "fed"; S1/S2; determinism; audit-sample rate; same-batch duplicates; re-observation vs update; 72 h window; short titles; causal order; order independence |
| `test_manifest_engine.py` | 21 | WAL, foreign keys, schema version; 12 SQLite-level invalid states; illegal transitions; failed ≠ absent; processing counts and per-theme counts; future page time ignored; missing server time fails closed; atomic, deterministic day commit with shard cleanup; unfinished day not committed; crash before rename then single commit; resume (interrupted, corrupt shard, orphans); causal near-empty flag |
| `test_guards_gates.py` | 30 | Byte and request budgets with retries; disk, temporary-disk and clock guards; the sequential sample run (headers, then downloads one by one); planned-size refusal before any download; hard byte cap; request cap; retries with capped `Retry-After`; final retry pass → `request_failed`; integrity retry → invalid; unverifiable time → invalid; substitution; disk floor, stop file, temporary cap; tighten-only config; no implicit approval; quoted-hash rule; every gate refusal; transport lock; redirect guard |
| `test_sample_isolation.py` | 15 | Shipped lists equal the committed hashes and the algorithm; tampered list refused; substitution avoids both stages; stage C refusal paths and its single success path; blind, deterministic review files; title-free log; import isolation both ways; network guard installed |

**Fixture policy:**

- **Synthetic only:** every GKG row is synthetic. Titles start with "SYNTHETIC" and URLs use
  `example.com`. Nothing is presented as historical news.
- **Ratio guard relaxed in three tests:** synthetic rows compress far more than GDELT's measured
  3.1×. Two parser tests and one engine test pass an explicit looser expansion ratio, with a comment,
  because they test something else. The guard itself is tested separately.

**Whole suite:**

- **Collected:** `pytest tests --collect-only` collects 1,570 tests with no error.
- **Not run:** the database-backed regression suite needs network access to the hosted database,
  which this phase forbids. The new package is imported by nothing in the application, so existing
  behaviour cannot have changed. You can run `pytest tests/ -v` when convenient.

---

## 10. Final validation [VERIFIED]

| Check | Result |
| --- | --- |
| New dependencies | None. `pip freeze` fingerprint `3393be50…` unchanged; `backend/pyproject.toml` unchanged |
| Production integration | None. Import-graph tests pass; no existing file edited |
| Database changes | None. No database accessed by the tool or its tests |
| Model or market-data changes | None. `training/`, `models/` and `config/` unchanged against HEAD |
| Archive files downloaded | None. No network request in this phase. `datasets/raw/gdelt/` does not exist |
| Full-acquisition path | Always refuses; no switch exists |
| Unrelated working-tree changes | Untouched. Git status differs only by the two new folders |

---

## 11. Remaining limitations

- **Header behaviour against the real archive** [UNVERIFIED]: the live behaviour of `HttpsTransport`
  (keep-alive, `Age` on a download after a header request, timing) is untested by design. The first
  authorised run is its test, bounded by the guards.
- **Full-acquisition machinery not built:** the fresh master-list download, its diff, and the
  window-wide re-check of unlisted slots. Only the development-sample path is wired.
- **Near-empty detection on the sample:** the sample's batches are sparse, so the causal baseline will
  usually be missing. Near-empty flags there will mostly be `NULL`, which means unknown.
- **No stage C trigger input:** no command-line way exists to supply a stage C trigger record. It
  would be added only if stage D fires the trigger.
- **Full regression suite not run in this phase** (network).

**Stop.** Nothing was downloaded. The development sample needs your approval, as set out in
`reports/phaseB2L_gdelt_development_sample_and_filter_review.md`.
