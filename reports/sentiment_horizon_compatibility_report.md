# Horizon multilingual sentiment — decision record and compatibility investigation (ADR-054 addendum)

Written for: the project owner. Date: 2026-11-04. Nothing was installed, downloaded or run. "Read" means read from a public source through an intermediary summarising fetch (PyPI metadata, Hugging Face raw files, GitHub source); nothing was executed, and sources should be re-read directly before relying on them. Full detail: `docs/sentiment/horizon_runtime_plan.md`.

## 1. Owner decision recorded (exact scope)

`Horizon-Labs/multilingual-sentiment-small` @ `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` may be considered for **research inference only**, accepting its disclosed web-crawl and LLM-generated training data and the absence of human-validated labels. Verdict `approved_for_research_inference`.
Not authorised: production activation, dataset creation or collection, fine-tuning or training, automatic downloads, redistribution, commercial use, any human-validation / accuracy / calibration claim, any financial-decision impact; installation, download, inference and the registry change each need their own approval.
Unchanged: A3.3, A3.5 (rejected), D20 (rejected), F1/R14, all dataset gates. `tooshlegacy/distilbert-financial-tweet-sentiment` stays `blocked_by_provenance`; the financial slot is empty. Recorded in code (`HORIZON_OWNER_DECISION`), ADR-054 (addendum), `reports/sentiment_model_approval_record.md`, `docs/sentiment/*`. The consolidated approval form was not touched.

## 2-3. Environment and technical findings

Python 3.11.9 (64-bit Windows); TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9, flatbuffers 25.12.19; `pip check` clean; 153 GB free. Not installed: `transformers`, `tokenizers`, `safetensors`, `torch`, `onnx`, `onnxruntime`, `huggingface-hub`. No compatible inference runtime exists in the repository today.
Model: ModernBertForSequenceClassification, vocab 256,000, 8,192 positions (trained to 512), mean pooling, native labels negative / neutral / positive, no remote code; `PreTrainedTokenizerFast` with `tokenizer.json`; `config.json` written by transformers 5.17.0 in the v5 format (`rope_parameters`, `layer_types`).

## 4. Is transformers 4.57.1 compatible? **No.**

Its `ModernBertConfig` has no `rope_parameters` and defaults `local_rope_theta` to 10000, while this model uses 160000 for the sliding-attention layers (two of three). Expected result: **a silent wrong setting**, not an error. Patching the approved config is not authorised. The ADR-052 pins (`tokenizers 0.22.1`, `safetensors 0.6.2`) also conflict with transformers 5.17.0 (`tokenizers>=0.23.1`, `safetensors>=0.8.0`) and are superseded for this model. The earlier note that version 5 "reportedly drops TensorFlow" is withdrawn: 5.17.0 declares no TensorFlow dependency.

## 5. Is ONNX Runtime viable? **Plausible; unverified; needs an owner policy extension.**

`onnxruntime` 1.31.1 (Python >= 3.11; numpy >= 1.21.6, protobuf >= 4.25.8, flatbuffers: all satisfied) has a 14.9 MB `cp311 win_amd64` wheel and would avoid torch, transformers and safetensors. Unknown without the artifact: input/output names, opset, whether the output is logits or already probabilities (double-softmax risk), and tokenizer parity. The quantized file agrees with fp32 on only 99.3% of the author's 430 texts, so only fp32 is usable. ONNX is a different format from the safetensors the owner approved and the project rule is safetensors-only.

## 6. Recommended inference approach

Stage A (next approval): an isolated throw-away environment outside `.venv` with the reference stack, pinned download with SHA-256 verification, a standalone smoke script on fictional sentences. TensorFlow 2.17 and the application stay untouched. Stage B (separate approval): the in-app runtime (reference stack after a resolver dry-run shows no change to the TensorFlow stack, or ONNX after a policy extension and a parity check against Stage A), then the registry change with an ADR and the in-app smoke test. Reuse `TransformersBackend`, `write_pretrained_manifest.py`, the comparison and the panel unchanged.

## 7. Files changed

Created: `docs/sentiment/horizon_runtime_plan.md`, this report. Modified: `backend/wealthpilot/core/sentiment/reviews.py` (Horizon verdict, `owner_decision`, remaining gates), `api/schemas.py` and `api/services/personalized_insight_service.py` (additive `owner_decision`), `frontend/src/types/api.ts` (regenerated: 2 lines added, none removed), `frontend/tests/fixtures/demo/*.json` (regenerated), `tests/backend/core/test_sentiment_candidate_reviews.py` (+5 tests, 3 updated), `tests/backend/api/test_sentiment_research_api.py` (secret check made precise), `docs/DECISIONS.md`, `docs/MEMORY.md`, `docs/TEST_PLAN.md`, `docs/sentiment/{model_licence_review,transformer_architecture,inference_and_fallback,limitations}.md`, `reports/sentiment_model_approval_record.md`. The registry, adapter, comparison, settings and `.env` were not changed.

## 8. Tests

Backend sentiment, demo, preflight, review, policy and training suites under the socket guard: **1471 passed, 6 skipped, 1 failed** on the full run; the one failure was an over-broad "token" substring check on the public status text ("tokenizer"), which I replaced with a token-shaped-secret check; the two affected files then ran **25 passed**. I did not repeat the full run after that fix. External connection attempts: 0. Frontend: `tsc -b` clean, `npm test` 276 of 276, build succeeded, no lint errors; the mutation check was not rerun (no frontend source changed). All inference output is mocked: **TESTED_WITH_MOCKS; INFERENCE_VERIFIED: none; actual inference ran: no.** The GDELT scaffold failure is pre-existing and untouched. Preflight exit 1.

## 9. Remaining blockers (all open)

Package installation approval; weight download approval; runtime choice (reference stack vs ONNX with an artifact-policy extension); the registry change with an ADR; a real-weights smoke test; and, separately, anything about production activation (not authorised). The financial slot has no approved candidate.

## 10. Packages proposed for Stage A (not installed)

`transformers==5.17.0`, `tokenizers==0.23.3`, `safetensors==0.8.0`, `huggingface-hub>=1.5.0,<2.0` and CPU `torch>=2.5` (the last two resolved by pip, then frozen into a hash-pinned lock; the exact versions could not be named from this read), plus their transitive dependencies (`regex>=2025.10.22`, `pyyaml`, `typer`, `tqdm`, `packaging`, `filelock`, `typing-extensions>=4.13`, `setuptools>=77.0.3`, `sympy>=1.13.3`, `networkx`, `jinja2`, `fsspec`). Stage B alternative: `onnxruntime==1.31.1` with `tokenizers==0.23.3`.

## 11. Download command proposed for the next approval (not run)

```powershell
$env:HF_HUB_DISABLE_TELEMETRY = "1"
hf download Horizon-Labs/multilingual-sentiment-small model.safetensors config.json tokenizer.json tokenizer_config.json special_tokens_map.json SHA256SUMS LICENSE NOTICE `
  --revision e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac --local-dir "$env:USERPROFILE\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small"
```

Then verify every SHA-256 against `SHA256SUMS` and the recorded values (`model.safetensors` `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1`); any mismatch stops the process.

## Approval needed next (one request)

Approve Stage A: create the isolated environment, install the pins in section 10 there, run the section 11 download, verify the checksums, and run a smoke script on fictional sentences. This does not touch `.venv`, the registry, the application or any production setting.
