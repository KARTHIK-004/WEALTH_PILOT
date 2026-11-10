# Sentiment model: offline training and evaluation (ADR-052)

**Status: nothing has been trained, downloaded or validated.** No Transformer package is installed in the project environment, no model weights are present, and no labelled dataset has been approved. The
application therefore answers with the deterministic rules baseline (`user_text_rules_v1`, `UNVALIDATED_BASELINE`), and `SENTIMENT_MODEL_ENABLED` is `false`. Everything below is the
tested machinery that turns an approved dataset and an approved model into a validated artifact — and refuses to claim validation otherwise.

This is the integration and evaluation of a **pretrained Transformer sentiment classifier**, optionally fine-tuned for the project's domain. It is not a new language model and it generates no text.

## What must be approved first (the dependency gate)

None of these is in the approved stack (`CLAUDE.md` section 5). They are listed so the owner can decide; **nothing was installed**.

| Package | Why | Licence (to verify from the package page) | Notes |
| --- | --- | --- | --- |
| `torch` (CPU build) | run and fine-tune the model | BSD-style | the largest item: hundreds of MB to ~2 GB depending on the build; CPU is enough, no GPU is required |
| `transformers` (5.x; the isolated verification used the owner-approved set S1, `5.12.1`) | model and tokenizer classes | Apache-2.0 | 5.x drops TensorFlow/Flax, which is irrelevant here (the backend is PyTorch). **The 4.x line is not a long-term-support option for this project**: no 4.x release is free of published security advisories (dependency request, section J), and 4.x is not approved. See "Validated behaviour of transformers 5.12.1" below |
| `tokenizers` | fast tokenizers | Apache-2.0 | pulled in by `transformers` |
| `safetensors` | weights format loaded by the service (pickle checkpoints are refused) | Apache-2.0 | |

Licences above are the declared package licences (verified from package metadata for the S1 set in the dependency request, sections K and L; not legal advice). `python -m training.sentiment.train_sentiment_transformer --check-environment` reports what is missing.

## What must be approved second (model and data licences)

- **Models** (`config.CANDIDATES`): `ProsusAI/finbert` (financial-language), `FacebookAI/roberta-base`, `distilbert/distilroberta-base`, plus the rules baseline. Each model card's licence must be
  read and recorded; the licence of a fine-tuned model follows its base model **and** its training data.
- **Dataset**: a labelled set approved by the owner, documented in a manifest (`dataset_manifest.template.json`): source, version, licence, URL, label definitions, sample count, language,
  preprocessing, split policy, duplicate handling, limitations. Candidate public sets exist (for example Financial PhraseBank, which its dataset card lists as CC BY-NC-SA 3.0: non-commercial
  and share-alike, and a derived model inherits that); none is approved or downloaded.
- **Domain difference (important)**: public financial-sentiment data is mostly news about companies; WealthPilot reads a person's own statements about savings, debt, goals, liquidity and
  investment worries. A model validated on news is not thereby validated for this input. Only a labelled set of personal-finance statements can validate it (`config.DOMAIN_NOTE`).

## Pipeline (all offline; never in an API request, graph node, agent, start-up or the frontend)

```
python -m training.sentiment.train_sentiment_transformer --check-environment
python -m training.sentiment.train_sentiment_transformer --manifest datasets/raw/sentiment/<id>/manifest.json --data datasets/raw/sentiment/<id>/data.jsonl \
    --base-model finbert --version sentiment-v1 --revision <the approved 40-character commit hash of the base model> \
    --target-precision <owner> --min-coverage <owner> --high-precision <owner> --high-min-coverage <owner>
python -m training.sentiment.evaluate_sentiment_model --manifest ... --data ... --candidate rules_baseline --candidate models/sentiment/sentiment-v1 --output <report.json>
```

1. `dataset.py` validates the manifest (refuses an unapproved or unlicensed dataset), normalises text exactly as the application does, maps labels, removes exact duplicates, removes texts that carry
   conflicting labels, and splits **by group** with a seeded hash (seed 42), so no text or group is in two splits (`check_no_leakage`).
2. The trainer fine-tunes on the train split (CPU, plain PyTorch loop). The base model is loaded with `use_safetensors=True`, `trust_remote_code=False` and the **immutable revision the caller supplies** (see "Loading the base model safely"), OFFLINE unless `--allow-hub-download` is given; that flag is the only way this package touches the network and the first download needs the owner's recorded approval.
3. `metrics.py` fits ONE temperature on the **validation** split (temperature scaling), reports ECE and the reliability table on the **test** split before and after, and derives the abstention threshold
   and the confidence-band cut-offs from validation for precision / coverage targets that the owner supplies as required arguments. Nothing is defaulted or invented.
4. `artifacts.py` writes `models/sentiment/<version>/` (weights, tokenizer, `config.json`, `label_map.json`, `metrics.json`, `confusion_matrix.json`, `model_metadata.json` with SHA-256 of every
   file, dataset id and licence, preprocessing version, timestamp, calibration, regression state, and the provenance of "Artifact metadata (schema version 1)" below) and immediately re-verifies it with the application's own loader.
5. **`validated`** is written only when ALL evidence exists: held-out test split of at least `MIN_TEST_SAMPLES_FOR_VALIDATED`, duplicate-leakage check, documented dataset licence, calibration, a
   threshold meeting the owner's targets, and the data is not a development fixture. Otherwise `unvalidated` plus the reasons, and the application refuses to use the model as primary.

Seeds are fixed, but GPU kernels (and some CPU thread schedules) can make two runs differ slightly; the library versions are recorded so a run can be repeated as closely as possible.

## Loading the base model safely (the training seam)

`fine_tune_with_torch` takes the base model only through `base_model_loading_kwargs`: `revision` (REQUIRED, supplied by the caller: a full 40-character lowercase commit hash; a branch, a tag, a
short hash or an empty value is refused before any package is imported; nothing in this package defaults or invents one, and no Hub model is defaulted), `trust_remote_code=False`, and
`local_files_only=True` unless `allow_hub_download` / `--allow-hub-download` is given. The model load adds `use_safetensors=True`. The command line has no default for `--revision`.
The revision the trainer used is written into the artifact metadata (`base_model_revision` and the tokenizer's `revision`; see the next section), so the recorded value is the one that was loaded.

## Artifact metadata (schema version 1)

`model_metadata.json` is written by `write_artifact` and read by `verify_artifact`; both fail closed. Every artifact must carry:

| Field | Rule |
| --- | --- |
| `metadata_schema_version` | the integer `1`; missing, unknown, newer or non-integer is refused (`artifact_incompatible`); there is no migration and no best-effort reading |
| `base_model` | the exact model identifier (non-empty text) |
| `base_model_revision` | an immutable 40-character lowercase commit hash (never a branch, tag, short hash or empty value) |
| `tokenizer.identifier` and `tokenizer.revision` | the tokenizer's identifier and immutable revision (in this seam the same as the model's, by construction) |
| `tokenizer.length` | `len(tokenizer)` as an integer of at least 1; compared with the loaded tokenizer and never greater than `config.vocab_size` |
| `library_versions` | at least `torch`, `transformers`, `tokenizers` and `safetensors`, as non-empty text (provenance only: the loader does not compare them with what is installed); other entries such as `numpy` are allowed |
| `manifest_sha256` | SHA-256 of the canonical JSON of the `files` map; a malformed value is `artifact_incompatible`, a well-formed value that differs from the recomputed one is `artifact_corrupt` |
| existing fields | `files` (per-file SHA-256), label map, calibration, validation evidence, versions: unchanged and still enforced |

An artifact written before these fields existed fails closed as `artifact_incompatible`. Artifacts are never edited in place: a different format means retraining. **Limit:** the manifest hash and the
per-file hashes live in the same directory as the metadata, so they detect corruption and an inconsistent edit, not someone who rewrites the whole directory.

**Tokenizer and embedding matrix (D9).** A tokenizer longer than `config.vocab_size` can emit an id with no embedding row, so it is refused (`artifact_incompatible`) both when the metadata is verified and,
before any text is processed, when `TransformersBackend` loads the tokenizer and the model. Equality is not required: a shorter tokenizer (a padded embedding matrix) is valid.

**Hub conversion.** In transformers 5.12.1 the library may ask the Hub to convert a pickle checkpoint to safetensors: synchronously when `use_safetensors=True`, the repository has no safetensors
file, the library is online and `revision` is `main`; and in a background thread after it has loaded a pickle (`.bin`) checkpoint, which `use_safetensors=True` excludes. Per the installed source (a
test checks the first case; this is not a documented guarantee), a pinned commit hash with `use_safetensors=True` therefore never starts a conversion. A switch named
`DISABLE_SAFETENSORS_CONVERSION` exists in that source but is **not documented** (no documentation was found), so this package does not set or rely on it. Do not treat the protection above as
permanent: re-check it whenever the transformers version changes.

## Validated behaviour of transformers 5.12.1, and what is still unproven

Validated on a locally generated, randomly initialised stand-in (not a real model), in a disposable environment with the owner-approved hash-pinned set S1 (`torch==2.13.0`, `transformers==5.12.1`,
`tokenizers==0.22.1`, `safetensors==0.6.2`; `reports/sentiment_model_approval_record.md`):

- `model.save_pretrained(directory)` writes `model.safetensors` only (no `.bin`, `.pt`, `.pt2`); the 4.x argument `safe_serialization` no longer exists and was silently ignored (identical output with
  `True`, `False` or nothing), which is why the call no longer passes it. Non-generative models get no `generation_config.json`.
- The runtime loader's keywords all work: `local_files_only=True` (forwarded to the hub layer as cache-only resolution), `trust_remote_code=False` (a local `auto_map` is ignored and its code is never
  executed), `use_safetensors=True` (a directory with only `.bin`, `.pt`, `.pth` or `.pt2` is refused). A private `_attn_implementation_internal` key in a local config is not applied.
- A tokenizer saved with `tokenizer.save_pretrained` reloads with the same vocabulary. **Tokenizer trap:** in 5.x the 4.x argument `BertTokenizer(vocab_file=...)` is silently ignored and builds a
  5-token tokenizer; the artifact therefore records `tokenizer.length` (the real `len(tokenizer)`) and the loader refuses a tokenizer of any other length (`artifact_incompatible`). The length is
  not required to equal `config.vocab_size` (a padded embedding matrix is valid) but may not exceed it.
- `write_artifact` / `verify_artifact` accept the stand-in artifact as `unvalidated`, and `load_model` refuses it as primary (`not_validated`).

Still unproven (no real checkpoint, download or training loop has ever been run here): behaviour with a real base model; a real head-size mismatch under `ignore_mismatched_sizes=True`; whether
`accelerate` is needed by a real `from_pretrained`; a real training loop; `tokenizers` 0.22.1 warns that building a WordPiece tokenizer from a `vocab.txt` path is deprecated (it works now); the
background Hub-conversion behaviour above depends on the installed library's source. The provenance fields and the tokenizer-versus-matrix rule were added after the stand-in run above and are covered by tests that need no
packages; the library-dependent stand-in tests were updated for them, and the S1 disposable-environment regression check of 2026-10-28 passed: 381 tests passed, 1 skipped, 0 failed, using only local randomly initialised stand-in models and hand-written tokenizers, with no real model weights, Hugging Face assets, datasets or user text accessed (see "Tests").

## Regression (sentiment intensity)

Disabled. An intensity head would need a dataset whose labels are CONTINUOUS scores in [-1, 1] given by annotators (`has_intensity`, `intensity_definition` in the manifest), separate training and
separate MAE / RMSE reporting (`metrics.regression_metrics`). A classifier probability is never turned into an intensity. Until then the API returns `sentiment_intensity: null` and
`intensity_available: false`. `--with-regression` is refused.

## Evaluation statistics and the approved evaluation policy (offline, for a future approved dataset)

`metrics.py` holds reusable, deterministic evaluation statistics (standard library + `numpy`; no model, file or network): `evaluate_predictions` (strict and selective accuracy / macro-F1, accepted-prediction precision,
coverage and abstention, per-class precision / recall / F1 with intervals, confusion matrix with an `abstained` column), `grouped_report` (undersized or empty groups are listed, never interval-estimated),
`calibration_report` (equal-width bins; a `strict` view over every scored example and an `accepted_only` view), `compare_predictions` (paired bootstrap difference and discordance, no winner),
`cohen_kappa` / `krippendorff_alpha_nominal` / `agreement_report`, `assess_against_policy` and `evaluation_report`.

**Owner-approved policy (2026-10-29, `reports/sentiment_model_approval_record.md`).** Level 0.95, 2,000 resamples, seed 42; Wilson intervals for proportions, stratified percentile bootstrap for F1 and paired differences,
a non-stratified item bootstrap for kappa; support 75 per primary class, 20 per subgroup, 300 held-out; primary labels positive / negative / neutral (`mixed` and `uncertain` reported separately); Cohen's kappa primary with
no floor, specific agreement and Krippendorff's alpha secondary, multi-label agreement deferred, pre-adjudication labels primary; 10 bins, ECE report-only, descriptive below 20 scored examples; coverage at least 0.70
(abstention at most 0.30), macro-F1 0.80 decided by the strict view, accepted-prediction precision 0.85, no per-class recall floor; no significance test; **no lower-bound activation rule**. The values live in
`OWNER_APPROVED_STATISTICS` and `OWNER_APPROVED_POLICY`, built by `StatisticsPlan.owner_approved()` / `EvaluationPolicy.owner_approved()`; every call still takes the plan and policy explicitly, and `approved=True` is refused
for any other value. **They are evaluation gates, not activation rules:** `assess_against_policy` prints required, observed and met / not met / not evaluable for each gate and gives the wording `validated`,
`not_validation_evidence`, `descriptive_only` or `insufficient_support`; it never ranks or selects a candidate and never recommends activation (intervals are reported, never gated; activation is the separate R14
decision). Synthetic, unapproved, fixture, unfrozen-rubric or unverified data is always `not_validation_evidence` (`EvidenceBasis`, eight required conditions). An undefined quantity is `None` with a reason (the older
`classification_report` returns 0.0 for an undefined precision and must not be used for evidence).

**Frozen-set plumbing (schema confirmed 2026-10-29).** `frozen_evaluation.py` verifies an approved frozen set before any evaluation: schema version, field types, no personal-data markers, the manifest's own hash, the hashes of
the records file, rubric, annotator manifest and adjudication log, the content / label / id / split-assignment hashes recomputed from the records, counts, three separate splits, exact and near-duplicate exclusion, and that the
declared evidence status equals the computed one. `evaluate_sentiment_model.py` has a frozen-set mode that reaches it only through `load_frozen_evaluation` and `evaluate_frozen` (see its docstring): the evidence basis comes
from the manifest alone, a model artifact is refused, the report holds no record text or id and recommends nothing, and the exit status never depends on a target. **No real manifest or dataset exists**; the mode is exercised
only on fixtures generated inside the tests. A labels-only predictions file has no confidences, so its candidate stays `descriptive_only`; owner decision E2 adds an optional probability-bearing format (`id -> {"label", "probabilities"}`, all records or none) that makes calibration evaluable, and the rules baseline never carries probabilities. `local_model_dir.py` is the Path B loader for one verified local model directory, used ONLY by the offline trainer (`--local-model-dir` / `--local-model-manifest`) and the offline evaluation script (`--local-model NAME=DIR` / `--local-model-manifest NAME=FILE`); never by a route, a setting or a script; synthetic and random stand-in models only, no real model has been seen. `hub_fetch.py` is the offline-built E1 fetch step and restricted B9 metadata query (standard library, injected transport, explicit policy; nothing imports it; its metadata query ran against `huggingface.co` on 2026-10-29 (two runs, 5 requests, completed), and its download path has never run against a real host). Tests: `test_sentiment_statistics.py`, `test_sentiment_policy_gates.py`,
`test_frozen_evaluation.py`, `test_evaluate_frozen_mode.py` (helper `frozen_fixtures.py`).

**Participant register, D13 calibration and manifest schema 2 (2026-10-30; offline, synthetic fixtures only).** `participant_register.py` validates the register that must exist before any dataset (codes, roles, attestations, access and deletion authorizations, consent metadata for consented data; fixed, sanitized errors; it cannot verify independence). `metrics.py` fits the D13 temperature on the calibration split's log-probabilities only (`fit_calibration_temperature`), applies it to held-out probabilities only (`apply_temperature`) and reports before / after calibration (`temperature_calibration_report`, 10 equal-width bins, strict and accepted-only, descriptive-only below 20, no invented logits, never `validated`). `frozen_evaluation.py` is schema 2: the register is a sixth verified input and the manifest carries the register, verifier, consent and calibration-split hashes, the temperature-policy version, the data status, the duplicate policy and the approved group dimensions; `evaluate_sentiment_model.py` frozen mode takes `--participant-register` and lets a probability-bearing predictions file or local model also answer the calibration split. Tests: `test_participant_register.py`, `test_temperature_calibration.py`, `test_frozen_register_and_calibration.py` (helpers `register_fixtures.py`, `frozen_fixtures.py`). The register also carries the deletion policy (project-owner authorization; raw text kept only until evaluation, audit verification and the R14 decision; rollback never restores raw text), and `test_no_fixture_is_real_evidence.py` guards against a fixture passing as real evidence. No real register, manifest or dataset exists.

**Baseline polite forms (AP8 `CONTEXT_DEPENDENT`).** "I would like ..." / "I would prefer ..." is a current want unless a condition precedes, is inside, or directly follows it in the same sentence; this is the one
production-baseline change the owner authorised (`tests/backend/core/test_user_text_polite_forms.py`). The annotation policy (AP1 to AP9) is decided in `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md`; the rubric and the rules
baseline still differ in the documented cases (section 7 of the rubric) and the baseline is otherwise unchanged.

Still open: rubric / baseline difference (f), a predictions format with probabilities, a real dataset,
annotation and a frozen approved rubric (R8 to R13), and the R6 / R7, D10 to D13, R14 chain.

## Configuration (backend, `.env.example`)

`SENTIMENT_MODEL_ENABLED` (default false), `SENTIMENT_MODEL_NAME`, `SENTIMENT_MODEL_PATH` (a directory inside `models/sentiment/`; anything else is refused), `SENTIMENT_MODEL_VERSION`,
`SENTIMENT_MODEL_MIN_CONFIDENCE` (can only raise the artifact's own calibrated minimum), `SENTIMENT_MODEL_ALLOW_FALLBACK` (default true), `SENTIMENT_MODEL_MAX_TOKENS` (required when enabled),
`SENTIMENT_MODEL_DEVICE` (`cpu`), `SENTIMENT_MODEL_TIMEOUT_SECONDS` (default 5). `GET /api/sentiment-model/status` shows whether a model is in use and why not.

## Tests

`tests/training/sentiment/` exercises everything above with a development fixture generated inside the tests (`sentiment_fixtures.py`: invented sentences, `development_fixture: true`, never validation data) and
a fake trainer, so no deep-learning package is needed. `test_transformer_training_seam.py` (revision, loading keywords, command line, recorded tokenizer length) and
`tests/backend/core/test_sentiment_tokenizer_integrity.py` (the length checks, driven through fake packages) and `tests/backend/core/test_sentiment_artifact_provenance.py` (schema version, provenance, manifest hash, the tokenizer-versus-matrix rule, refusal of pickle / `.bin` / `.pt` / `.pt2`, and a guard against network, Hub import and pickle calls) also run without the packages.

`test_transformer_standin.py` runs the real `fine_tune_with_torch` (with `epochs=0`: no optimiser step), `write_artifact`, `verify_artifact` and `TransformersBackend` against a locally generated,
randomly initialised stand-in model and hand-written tokenizer fixtures. It is **skipped in the project environment** (no `torch` / `transformers`); the 32 library-dependent tests passed on 2026-10-27 in a disposable environment with the hash-pinned S1 set, and a mutation check (six deliberate defects) was detected by the tests. **Since then** the metadata schema (provenance, manifest hash, tokenizer-versus-matrix rule) changed and this module was updated for it (and two tests added); the S1 disposable-environment regression check of 2026-10-28 then passed: 381 tests passed, 1 skipped, 0 failed (34 of them in this module), using only local randomly initialised stand-in models and hand-written tokenizers, with no real model weights, Hugging Face assets, datasets or user text accessed. It uses no pretrained weights, no real Hub
id, no dataset and no user text, and runs under a guard that refuses sockets, `torch.load` and hub-level calls and checks the Hugging Face cache is unchanged.


## Phase closure (2026-10-30)

> The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved.

What exists and is verified, offline and on synthetic fixtures only: the rules-baseline comparison, the gated artifact loader and its provenance / tokenizer / safetensors checks, the Path B local-directory loader (random stand-ins), the participant-register validator, D13 calibration, the schema-2 frozen-evaluation plumbing and the approved evaluation statistics. Synthetic fixtures produce only `not_validation_evidence` or `descriptive_only`, never `validated`. What does not exist: a downloaded model, a real dataset, a real register or manifest, a real evaluation, an activation. Open and closed for this phase: A3.3, D1, D2, D16, R14 unresolved; A3.5b rejected; D20 rejected; D5 kept `v0-draft`; E3 schema-2 offline only; E4 documented differences kept. Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model downloaded: no; real dataset created: no; real evaluation run: no; production activation: no; intensity regression: disabled; blockchain / ledger sentiment payload: none.

## Pretrained-only comparison (ADR-053) — no training happens here

The FinBERT / Twitter-RoBERTa comparison runs pretrained classifiers as they are: no fine-tuning, no dataset, no labels. Nothing in `training/` is used by it. See `docs/sentiment/` for the licence
review (both candidates are blocked today), the architecture and how a candidate could be enabled after the owner's approvals.
