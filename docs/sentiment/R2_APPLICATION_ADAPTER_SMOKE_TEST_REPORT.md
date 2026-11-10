# R2 — Artifact Placement and Application-Adapter Smoke Test (2026-11-07)

Written for: the project owner and reviewers. **This is a smoke test on six fictional sentences. It is not an accuracy, calibration or validation evaluation, and no result below may be quoted as one.** All measurements are from one Windows 11 machine (i7-1165G7, 4 cores/8 threads, 16 GB RAM, CPU only, under memory pressure from other applications) and this test configuration.

## 1. Result

| Item | Status |
|---|---|
| Artifact placement and integrity | **VERIFIED** |
| Application adapter loading (registry -> gates -> manifest/hash verification -> safetensors load) | **VERIFIED** |
| Real-weight inference through the adapter and the service | **VERIFIED** |
| Output normalisation, label order, single softmax | **VERIFIED** |
| Research comparison output (general model vs rules, empty financial slot) | **VERIFIED** |
| Privacy (no text in logs or responses, no network, no `torch.load`) | **VERIFIED** |
| Lifecycle (status never loads, concurrency, bounded timeout, missing files) | **VERIFIED** |
| Production flags / production method | **UNCHANGED, VERIFIED** |

Command: `WEALTHPILOT_REAL_WEIGHTS_SMOKE=1 WEALTHPILOT_SMOKE_EVIDENCE=docs/sentiment/r_series/evidence/r2_smoke_evidence.json pytest tests/backend/core/test_horizon_real_weights_smoke.py` -> **9 passed** (31 s). Raw outputs: `docs/sentiment/r_series/evidence/r2_smoke_evidence.json`.

## 2. Storage policy and placement

- Convention inspected: the adapter reads `models/sentiment_pretrained/<key>/` (`adapter.PRETRAINED_ROOT`). The existing `.gitignore` ignored only `models/sentiment/**`, so the new directory was **not** ignored; `models/sentiment_pretrained/` is now ignored in full (`git check-ignore` confirms for the weights and the config). Nothing was added to Git; no model binary can be committed by `git add .`. The repository has a single commit and no external artifact store, so a local untracked directory is the safest location consistent with the project; the Stage A directory outside the repository remains as the source copy.
- Exact approved revision only: `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`. No download was made in R2; the files were copied from the already-verified Stage A directory.
- Files placed (size, SHA-256; all matched the Stage A record and the repository `SHA256SUMS`, and `sha256sum -c` passed for the five files listed there): `model.safetensors` 562,584,932 bytes `f0d0b6d2…02dd1`; `tokenizer.json` 34,363,286 `f34b44a6…8f0a`; `tokenizer_config.json` 46,440 `ea349495…8633`; `config.json` 2,075 `516d8046…b9`; `special_tokens_map.json` 636 `baec30ea…1351`; `LICENSE` 11,358 `cfc7749b…d30`; `NOTICE` 1,566 `8dd5797f…186`; `SHA256SUMS` 690 `fb38ed23…91ec`. Full list: `r_series/evidence/r2_placed_artifact_hashes.txt`. No `onnx/`, pickle or framework checkpoint is present.
- `pretrained_manifest.json` was produced by `scripts/write_pretrained_manifest.py --candidate horizon --tokenizer-length 256000` (manifest digest `9fa0c909…4da9`); the tool itself refused nothing because the registration gate is now satisfied.
- Remote code is never enabled (`trust_remote_code=False`), weights load as safetensors only, hub access is offline, and `torch.load` was replaced by a raiser during the test.

## 3. Fixed fictional sentences and observed outputs (adapter level)

Raw scores are the model's logits in its own label order (negative, neutral, positive); the probabilities are the single uncalibrated softmax. The adapter's logits equal the Stage A direct-loading logits to within rounding (max difference 6e-4, the Stage A values being rounded to four decimals).

| Case | Sentence (fictional) | Model label | Raw scores (neg / neu / pos) | Softmax (neg / neu / pos) |
|---|---|---|---|---|
| positive | I feel happy because my savings have increased this month. | positive | -2.031 / -1.753 / 6.600 | 0.0002 / 0.0002 / 0.9996 |
| negative | I am worried because my monthly loan payments are becoming difficult to manage. | negative | 4.702 / 0.621 / -2.895 | 0.983 / 0.017 / 0.0005 |
| neutral | I deposited five thousand rupees into my savings account this month. | neutral | -2.374 / 3.407 / 0.176 | 0.003 / 0.959 / 0.038 |
| negation | I am not worried about my savings at all. | positive | -1.141 / 0.852 / 1.977 | 0.032 / 0.237 / 0.731 |
| mixed | My investments are growing, but I am worried about future expenses. | neutral | 0.211 / 2.544 / -0.828 | 0.086 / 0.884 / 0.030 |
| ambiguous | I reviewed my account statement yesterday. | neutral | -1.786 / 4.418 / -0.815 | 0.002 / 0.993 / 0.005 |
| unsupported (Spanish) | Estoy muy contento porque por fin pude ahorrar para mis vacaciones. | **not run** | - | - |

The scores are **not confidence values**: they are one uncalibrated softmax, valid only within this model.

## 4. Application behaviour on the same sentences (service path, flag-independent config)

| Case | Rules reading (state) | Model | Relation | Combined reading | Why |
|---|---|---|---|---|---|
| positive | positive (valid) | positive | agrees | positive | agreement |
| negative | negative (valid) | negative | agrees | negative | agreement |
| neutral | neutral (weak) | neutral | agrees | **uncertain** | `context_safeguard`: the rules mark the wording weak, so the application will not call it a finding |
| negation | uncertain (weak) | positive | rules did not commit | **uncertain** | `context_safeguard` (negation) |
| mixed | negative (valid) | neutral | differs | **uncertain** | `rules_disagree` |
| ambiguous | insufficient_evidence (abstained) | **not run** | - | insufficient_evidence (rules fallback) | the eligibility gate stops it before the model; `input_not_eligible` |
| unsupported (Spanish) | insufficient_evidence (abstained) | **not run** | - | insufficient_evidence (rules fallback) | non-English never reaches a model |

In every row: the `financial` slot is `unavailable / no_candidate_approved` and shown as empty (not a failure); `production_effect = none`; `validation_status = not_human_validated`; no `confidence` or `intensity` field exists in the response. The model alone calls "mixed" neutral and "negation" positive; the application does not trust either without the rules' agreement, which is exactly what the safeguards are for. **This says nothing about which reading is more accurate.**

## 5. Lifecycle and failure tests (all on the real files)

- A status read with the real files present calls no verification, hashing or model construction (those functions were replaced with raisers) and reports `not_loaded`; after a request it reports `ready`; it never causes a load.
- Four simultaneous first callers: **1 answered, 3 received `loading`, 0 errors**; afterwards every caller is answered.
- A missing directory: fixed reason `weights_missing`, the rules reading answers, nothing raises (also covered by unit fault-injection tests for corrupt, wrong-revision and forbidden-file cases).
- Timeout: with a 1 ms limit the call returned `timeout` and the next call returned `timeout` from the circuit breaker in ~10 microseconds instead of queueing behind the running inference.
- A research failure cannot become an HTTP 500 (`build_transformer_research` never raises; covered by the unit suite and the API tests).
- Resource cleanup: the cache is cleared between tests; models are held in memory for the process lifetime by design (no unload API).

## 6. Measurements (this machine only)

| Quantity | Value |
|---|---|
| First call: SHA-256 verification of all files + load + first inference | 10.2 s (13.9 s in one unlogged earlier run; includes hashing ~600 MB; page cache and memory pressure matter) |
| Warm single-sentence inference | median 24.9 ms (min 22.6, max 32.7, 6 calls) |
| Peak working set after load / after inference | 1285 MB / 1285 MB (current 1076 -> 1077 MB); this process did not import TensorFlow |
| Network attempts | 0 |

## 7. Privacy and isolation verification

A unique marker token embedded in a test sentence appeared in neither the serialised response nor any captured log record (DEBUG level). No database was opened; Gemini was not involved; no recommendation, risk, goal, portfolio or compliance code ran. The production insight reading (`user_sentiment`, method `rules_baseline`) is untouched.

## 8. Limits

Six fictional sentences cannot support any statement about accuracy, calibration, bias or domain suitability. The model's web-crawl and LLM-labelled training data, its lack of human validation and its general (non-financial) domain remain exactly as in `SENTIMENT_MODEL_CARD.md`.
