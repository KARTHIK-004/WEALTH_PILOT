# Inference, fallback and operating the research models (ADR-053)

## States you will see today

`SENTIMENT_TRANSFORMERS_ENABLED=false` (default and current): the API returns `transformer_research.enabled=false`, both results `unavailable` / `disabled`, the combined reading equal to the rules
reading with source `rules_baseline_fallback`. The page shows "Research models are switched off".

Switched on anyway: both candidates stay unavailable (`licence_not_verified`; RoBERTa additionally `format_not_allowed`). `GET /api/sentiment-model/status` shows `availability: "blocked"`,
`inference_enabled: false`, the recorded blocker, and `production_activation: "not_activated"`. The status never claims a model is active when weights are missing.

## Fallback

The rules baseline `user_text_rules_v1` is the production method in every state and is never changed to agree with a model. Whenever the pair cannot be compared the combined reading is the rules reading
and says so (`overall_source: rules_baseline_fallback`, plus `uncertainty_reason`). Nothing in the pretrained path can fail a request: every failure is a per-model fixed reason code.

## Disable

Set `SENTIMENT_TRANSFORMERS_ENABLED=false` (the default) and restart the backend. Removing `models/sentiment_pretrained/` has the same effect (`weights_missing`).

## Test without real users or models

```
PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/backend/core/test_sentiment_research_pair.py tests/backend/api/test_sentiment_research_api.py tests/backend/scripts/test_write_pretrained_manifest.py -q
cd frontend && npm test && npx tsc -b && npx oxlint
```

These use stand-in backends that return fixed logits and a few bytes of placeholder "weights". They need no internet, no package and no model. They verify policy and wording; **they are not model inference.**
The fictional demo (`/financial-behaviour?demo=true`, dev only) shows the panel in its current "switched off" state with the real backend output.

## If the owner later approves a candidate (NOT done; for the record)

Only after the owner has recorded approval of the licence, the dependency versions and the download — and `registry.py` has been changed by a reviewed commit with an ADR:

```
# 1. install the approved, hash-pinned packages into .venv (see reports/sentiment_transformer_dependency_request.md)
# 2. as a deliberate operator step, download the PINNED revision of the safetensors weights and the small config/tokenizer files only (never *.bin, *.h5, *.msgpack):
#      huggingface-cli download <repository> model.safetensors config.json tokenizer_config.json <tokenizer files> --revision <40-char sha> --local-dir models/sentiment_pretrained/<key>
# 3. record the integrity manifest (refuses a blocked candidate, a pickle-capable file, or unsupported labels):
python scripts/write_pretrained_manifest.py --candidate <finbert|roberta> --tokenizer-length <len(tokenizer)>
# 4. configure and restart
#      SENTIMENT_TRANSFORMERS_ENABLED=true  SENTIMENT_TRANSFORMERS_MAX_TOKENS=128  SENTIMENT_TRANSFORMERS_TIMEOUT_SECONDS=5  SENTIMENT_TRANSFORMERS_DEVICE=cpu
# 5. an opt-in smoke test against the real weights must be written and run then; none exists now.
```

HF offline variables (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) should be set when serving. The application itself never downloads anything, at start-up or on a request.

---

## Enabling a replacement later (ADR-054; not done)

Only after the owner's recorded approvals (licence/provenance, packages, pinned download): add the approved `Candidate` to `registry.py` as `license_verified` by a reviewed commit, generalise the `finbert` / `roberta` keys to `financial` / `general` across `inference_service.py`, `schemas.py`, the TypeScript
labels, fixtures and mutants, regenerate `frontend/src/types/api.ts`, install the approved packages, download only the pinned `model.safetensors`, config and tokenizer files into `models/sentiment_pretrained/<key>/`, run `python scripts/write_pretrained_manifest.py --candidate <key> --tokenizer-length <n>`,
set the four `SENTIMENT_TRANSFORMERS_*` variables and restart. Then write and run an opt-in real-weights smoke test; only that can earn the status INFERENCE_VERIFIED. Until then every state in this document applies unchanged.

---

## Horizon: staged path to research inference (2026-11-04; nothing below has been run)

Stage A: an isolated throw-away environment outside `.venv`, `transformers==5.17.0`, `tokenizers==0.23.3`, `safetensors==0.8.0`, `huggingface-hub` 1.x, CPU `torch`; pinned download with SHA-256 verification; a standalone smoke script on fictional sentences. Stage B: choose the in-application runtime after a resolver dry-run shows no change to TensorFlow 2.17, then the registry change with an ADR, the manifest, and the in-app smoke test.
Every state described earlier in this document (disabled, blocked, fallback to `user_text_rules_v1`) is what applies until both stages are approved and done. Commands and pins: `horizon_runtime_plan.md`, sections 8 and 9.
