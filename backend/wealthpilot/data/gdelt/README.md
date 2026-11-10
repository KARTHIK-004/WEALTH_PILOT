# Isolated GDELT acquisition and processing tool (Research Enhancement Track)

Built in Phase B2-K.

**Current state (Phase B2-M):** the development-sample and network locks are lifted, so only the fixed
192-batch development sample can be downloaded. It still needs:

- a complete local approval record;
- the matching list hash;
- the explicit `--confirm-network` flag.

The confirmation sample stays locked, and full historical acquisition always refuses. The filters are
candidates for labelled review, not approved production filters.

Nothing in the WealthPilot application imports this package. It imports only the standard library,
PyYAML (already declared) and itself. Tests enforce both rules.

## Package structure

| Module | Role |
| --- | --- |
| `__init__.py` | Build locks: `NETWORK_ENABLED_IN_THIS_BUILD` and `DEV_SAMPLE_ENABLED_IN_THIS_BUILD` are `True` since B2-M; `CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD` is `False`; versions |
| `config.py` | Run config, hard limits (tighten-only), approval records, the `authorize` gate |
| `timeutil.py` | UTC-only parsing: batch stamps, strict HTTP dates; naive times rejected |
| `availability.py` | The availability rule as a pure function; fails closed |
| `session_calendar.py` | 16:00 / 13:00 ET cutoffs and forecast-origin mapping; the calendar is an input |
| `coverage.py` | Interval counts that stay `None` (with a reason) when coverage is too low; never a fake zero |
| `existence.py` | Header-check observations into absent / failed / unknown states |
| `transport.py` | `Transport` interface; the locked `HttpsTransport`; the redirect guard |
| `integrity.py` | Size, MD5 (master list or ETag), zip structure, expansion guards |
| `parser.py` | Incremental GKG 2.1 row parser with per-reason counts and bounded memory |
| `filters.py` + `specs/gdelt_filter_v1.yaml` | Versioned candidate filters, refused if the file's SHA-256 differs from the registry |
| `dedup.py` | Within-batch and causal cross-batch duplicate and update handling |
| `manifest.py` + `manifest_schema.sql` | Resumable SQLite manifest (`gdelt_manifest_v1.1`) and its state machine |
| `output.py` | Per-slot shards and atomic, deterministic daily gzip TSV files |
| `engine.py` | One batch: body → validated shard. The sequential sample run. Day commits and resumption |
| `guards.py` | Byte, request, free-disk, temporary-disk, stop-file and clock-skew guards |
| `cleanup.py` | Path-guarded deletion: never recursive, never outside `tmp/` |
| `sample.py` + `sample_data/` | The B2-I pre-registered lists, verified by SHA-256; stage C gating |
| `review.py` | Blind annotation files for the labelled review (offline) |
| `annotate.py` | Annotation workflow: backup, working copy, small batches, validated merge, status. Never reads the sealed key |
| `labeller.py` | `annotate label`: interactive, human-only labelling of the 312 overlap items. Answers are kept per item; a review screen shows every problem the rubric validator finds (the company-notice rule is explained); `<` goes back; nothing is saved until the item is valid; atomic save per item; skip, quit, resume, corrections with a reason. Never shows AI suggestions or key data |
| `estimators.py` | Pure estimators from B2-I §4.6 (weighted precision, pooled and capture recall, company statistics, batch-cluster bootstrap, Wilson) and agreement arithmetic (raw agreement, Cohen's kappa, Gwet's AC1). No file or key access |
| `evaluate.py` | `annotate freeze` and `annotate evaluate`. Freeze needs all 1,493 items labelled and valid. Evaluation checks the freeze first, and only then reads the sealed key (the only module besides the build that names it). Aggregates only; never overwrites. Agreement is deliberately not computed |
| `ai/` | **B2-U3: AI-assisted annotation pipeline, BUILT BUT DISABLED.** Separately versioned experiment (see "AI-assisted annotation pipeline" below). Stdlib + PyYAML only; no provider SDK, no adapter, no network. Never reads the sealed key or the human working-copy labels |
| `preflight.py` | The offline dry run |
| `cli.py`, `__main__.py` | Command line |
| `events.py` | JSON-lines log with allow-listed keys only (no titles) |

## Offline dry run

From the repository root, in the project venv:

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt dry-run            # human-readable
.venv/Scripts/python.exe -m wealthpilot.data.gdelt dry-run --json     # machine-readable
.venv/Scripts/python.exe -m wealthpilot.data.gdelt dry-run --config <run_config.yaml>
```

**What it checks, with no network request and nothing written:**

- the stage D list against its committed hash, and its re-derivation;
- the filter-spec hash;
- time-zone data;
- the transfer estimate against 1.30 GB, and the request budget;
- sequential mode;
- free disk;
- the Git ignore rule for the output root;
- the approval record;
- the build locks.

It lists every blocker, not just the first.

**Other commands:**

| Command | Behaviour | Exit code |
| --- | --- | --- |
| `fetch-sample` | Runs only with a valid approval record and `--confirm-network` | 0, 3 or 4 |
| `acquire` | Always refuses | 3 |
| `build-review` | Needs a completed development sample | — |
| `annotate init / export-batch / merge / validate / status / label` | Offline labelling workflow (see `reports/phaseB2Q_annotation_workflow_report.md`) | 0, 1 or 2 |
| `annotate freeze` | Refuses until every item is labelled and valid; then writes a read-only freeze record | 0 or 1 |
| `annotate evaluate` | Refuses without a matching freeze. Only then opens the sealed key and writes aggregate estimates | 0 or 1 |
| `ai dry-run / init / queue / progress / qc / review / export --experiment <yaml>` | Local only (B2-U3). `dry-run` plans and writes nothing; `init` snapshots the originals into a new versioned folder | 0, 1 or 2 |
| `ai run --experiment <yaml> --confirm-ai-run` | **UNAVAILABLE in this build.** Always exits 3 and lists every unmet prerequisite | 3 |
| `ai retention --experiment <yaml> [--confirm-delete]` | B2-U5. Dry run by default. With `--confirm-delete`, deletes only expired derived files and crash fragments (see below). Never touches the originals, chains, reviews, audit, snapshot or export | 0 or 1 |
| `ai evaluate --experiment <yaml> [--blind-provenance <json>]` | B2-U5. Offline integrity checks and methodology-neutral counts for the exported dataset. Prints a report; writes nothing; never opens the sealed key | 0 or 1 |

## AI-assisted annotation pipeline (B2-U3, built but disabled)

Nothing here has been run. No model was called, no data was sent, no suggestion exists, no label was assigned.

- **Why it is separate.** AI assistance on the 312 original overlap items changes the human-only design of the original
  experiment. The original files are never edited; the pipeline snapshots them into a new versioned folder and keeps the
  original overlap list as `historical_overlap.json`. A label made after seeing a suggestion is recorded with
  `ai_exposure = seen` and is never described as an independent human label.
- **Four separate approval gates**, each bound by SHA-256 to exactly what it approves (the dry run prints the hashes):
  A methodology, B provider and model (with the prompt and rubric text), C data handling, D execution (item set, run ID,
  limits). Approving one never satisfies another; changing the content invalidates the matching gate.
- **Independent locks.** The build constant `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD` is `False`; the adapter registry is
  empty; `--confirm-ai-run` is required; the environment variable named for credentials must exist (its value is never
  read or stored). A config with an `enabled` or `auto_accept` key is refused, and every item always goes to a human.
- **Artifacts** (all under the new destination, never inside the original review folder): `snapshot/`, `inputs/`,
  `suggestions/` (raw hash-chained attempts, derived valid CSV), `review/` (hash-chained human review actions), `audit/`,
  `queue/`, `export/`, `fingerprints.json`.
- **Review actions:** accept, edit, reject, uncertain, insufficient evidence, plus no-suggestion and blind. Edit and
  reject need a reason code. A repeat review is a correction with a reason; the earlier record stays in the history.
- **Tests:** `test_ai_schema_prompt_chain.py`, `test_ai_gates_snapshot.py`, `test_ai_run_review_export.py` (all offline,
  synthetic; the build lock is lifted only inside a test, with a scripted fake provider).
- **B2-U5 repairs:** the reviewer's "same story as item" answer is kept (`near_dup_of`; empty means none; malformed,
  unknown or self references are refused). `provider.temperature` is required, validated (0 to 2, never clamped) and covered
  by Gate B; the run writes a read-only `audit/run_manifest_<run_id>.json`. `protocol.polarity_option` must be recorded
  (the polarity decision is the owner's; only `P1_required_as_in_existing_rubric` exists) and is covered by Gate A.
  A blind label cites no suggestion (`suggestion_ref` is the suggestion *shown*).
- **Retention scope:** `retention_days` expires only the derived suggestion CSV, the queue CSV and suggestion crash
  fragments, measured from the end of the last recorded run. The raw provider responses sit inside the hash chain and are
  **not** expirable in the current layout (a design decision for the data-handling gate).
- **Tests:** also `test_ai_repairs_duplicates_temperature.py` and `test_ai_retention_evaluation.py`.

**`ai_suggestions_A.csv` (validator-enforced schema, 2026-10-16 fix).** The file is read only when a label claims an
AI-based `label_basis` (`accepted_ai`, `corrected_ai`, `rejected_ai`). It needs the columns `item_id`,
`annotator_type`, `rel_equity`, `rel_rates`, `rel_gold`, `amb_code`, `company_notice`, `pol_equity`,
`pol_rates`, `pol_gold` and `note` (extra provenance columns are allowed). A row is valid only if its item
is known, appears once, is **not** an overlap item, is marked `annotator_type = ai`, and satisfies the
rubric. A label's AI basis is accepted only for an item with its **own** valid row. The human-only
workflow never reads this file. No tool in this package creates it.

## Configuration

See `config.example.yaml`. Copy it to an ignored location before editing; the default output root is
`datasets/raw/gdelt/english_gkg_v1/`.

**Limits:**

- **Tighten only:** a config may lower maxima and raise floors, never the reverse.
- **Sequential only:** `parallel_enabled: true` and `max_concurrency` above 1 are refused.

**What counts as an approval:** a record you write under `approvals.dev_sample`, with every field
explicit:

- `approved: true` (the YAML boolean);
- `approved_by` (no email);
- `approved_on`;
- `reference` (the B2-J checklist);
- `data_allowance_remaining_bytes` (at least the 1.5 GB cap);
- `stage_sha256` (quoted).

**What never counts:** defaults, the example file, test fixtures, a quoted `"true"` or a partial
record.

## Manifest states (`manifest.slot_state`)

| State | Meaning |
| --- | --- |
| `unverified` | Expected slot; nothing observed yet |
| `verified_available` | Header check returned 200; not downloaded yet |
| `in_progress` | Downloading, or waiting for a retry |
| `confirmed_absent` | Two fresh 404s more than 65 minutes apart, or the accepted June 2025 outage |
| `absent_inconclusive` | 404s that could not be confirmed independently, or inconsistent answers |
| `request_failed` | Only transient failures within the retry budget. **Failed is never absent** |
| `inaccessible` | Other 4xx, or a redirect elsewhere |
| `downloaded_invalid` | A body arrived but failed integrity, or the availability rule failed closed |
| `parsed_validated` | Integrity, availability and parsing passed; rows are in a shard |
| `processed` | Its UTC day was committed atomically |

## Availability rule

`available_at = max(nominal batch time, verified server Last-Modified) + 15 min`, computed in
`availability.py`.

**It fails closed when any of these is true:**

- `Last-Modified` or `Date` is missing or not a strict GMT date;
- `Last-Modified` is later than `Date`;
- `Last-Modified` is more than 60 minutes before the nominal time;
- the zip member time disagrees with `Last-Modified` by more than 10 minutes;
- a cached response (`Age` > 0) has no zip time to corroborate it.

The page publication time is never used.

## Error handling and guards

**Exit codes:** 0 success, 2 configuration error, 3 refused by a gate, 4 stopped by a guard, 1 other.

**What the guards track:**

- every request, retries and header checks included, against a request cap;
- every byte received, partial transfers included, against a byte cap.

**When they trip:**

- **Before any download:** a planned total above 1.30 GB stops the run.
- **Before every download:** a request that would cross the 1.50 GB cap is never started.
- **Free disk:** below 20 GB at preflight, or 10 GB at runtime, stops the run.
- **Temporary disk:** above 0.5 GB stops the run.
- **Stop file:** a `STOP` file in the output root stops the run after the current slot.

**No limit relaxes itself.**

## Running the authorised sample (B2-M)

Steps 1–3 were done in B2-M:

1. You confirmed your remaining data allowance (at least 1.5 GB) and approved the development sample.
2. The approval record was written to a local run config.
3. In a reviewed change, the build locks `DEV_SAMPLE_ENABLED_IN_THIS_BUILD` and
   `NETWORK_ENABLED_IN_THIS_BUILD` were set to `True`.
4. `dry-run --config …` must show no blockers.
5. `fetch-sample --config … --confirm-network` runs:
   - 192 header requests, then up to 192 sequential downloads;
   - raw zips kept under `review/b2i_review_v1/raw/` for the labelled review.

## What the tool intentionally cannot do yet

- **Downloads:** only the 192-batch development sample can be downloaded, and only behind its gate.
- **Confirmation sample:** no stage C trigger record can be supplied from the command line.
- **Full historical acquisition:** none. The fresh master-list download and diff it would need are
  not implemented.
- **No AI generation:** no provider adapter, prompt builder or suggestion generator exists. The B2-T
  proposal for one is not approved.
- **No agreement result:** the agreement functions are arithmetic only and are not wired to any dataset.
- **No sentiment, features or models:** no sentiment scoring, feature generation, model input or
  database writes.
- **No production filters:** no filter is approved for production.
