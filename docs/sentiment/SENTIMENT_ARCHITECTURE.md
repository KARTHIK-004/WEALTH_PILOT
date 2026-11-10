# Sentiment Architecture (as of 2026-11-05)

Written for: engineers and the project owner who need to know how the sentiment subsystem is wired and what it may and may not do. Authority: ADR-043 (rules baseline), ADR-052 (trained-model seam), ADR-053/054/055 (research comparison). If code and this document disagree, `docs/RULES.md` Rule 29 applies.

## 1. Two layers, one authority

| Layer | Method | Status | Effect |
|---|---|---|---|
| Production | `user_text_rules_v1` (`core/user_text_sentiment.py`) | **In use, unchanged** | Display-only context beside the stored risk assessment |
| Research | Role-based pretrained comparison (`core/sentiment/`) | **Implemented, OFF by default (`SENTIMENT_TRANSFORMERS_ENABLED=false`); Horizon registered as the `general` research candidate (ADR-056), `financial` slot empty** | Display-only, composed after `compose_insight`; never stored |

Sentiment of either layer never changes risk, goals, portfolio, recommendations, compliance or savings-first routing. Backend arithmetic remains the sole numerical authority; the frontend only displays what the API sent.

## 2. Components

```
POST /api/profiles/{id}/personalized-insights        GET /api/sentiment-model/status
        |                                                    |
 api/services/personalized_insight_service.py  ----------> sentiment_model_status()   (reads code constants + candidate_status; loads NOTHING)
        |  compose_insight()  -> rules reading (user_text_rules_v1)
        |  build_transformer_research()   (never raises)
        v
 core/sentiment/inference_service.run_research(text, rules_label, interpretation_state, config, slots)
        |        eligibility gate (English-only, length, rules "unsupported_language" => no model sees the text)
        v
 core/sentiment/adapter.classify_with(candidate|None, config, text, role=..., slot_reason=...)
        |  gates: licence -> format (safetensors) -> registration -> weights/manifest/hash -> load -> infer
        v
 core/sentiment_model.TransformersBackend   (the ONLY module that imports torch/transformers; local files only; offline)
        v
 core/sentiment/normalization.result_from_logits  (one softmax; label order read from the model's own config)
        v
 core/sentiment/comparison.{compare_slots, model_vs_rules, decide_overall}
```

## 3. Registry and role slots (`core/sentiment/registry.py`)

- Roles: `financial`, `general`. A slot is filled only by a **registered** `Candidate`.
- `Candidate.registration` ∈ `registered` | `pending_owner_approval` | `historical`; `runnable_in_principle = licence_verified ∧ safetensors ∧ registered`.
- Present candidates: Horizon (`general`, revision `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`, **registered** by the owner's R1 decision of 2026-11-07, research only), FinBERT and Twitter-RoBERTa (historical, blocked by licence/format).
- Consequence today: financial slot → `no_candidate_approved` (shown as "No model registered", never as a failure or a neutral reading); general slot → Horizon: `disabled` while the flag is off, `weights_missing` if the verified files are absent, otherwise it answers. Placed files live in the git-ignored `models/sentiment_pretrained/horizon/` and are verified against a SHA-256 manifest at first use (R2, ADR-056). A real-weights smoke test through the adapter passed (`R2_APPLICATION_ADAPTER_SMOKE_TEST_REPORT.md`); it is not an accuracy evaluation.
- Registering a candidate is a reviewed code change (and an owner decision). Configuration can never register or un-block one.

## 4. Result schema

`ModelResult` (internal) → `ResearchModelResultOut` (API): `slot`, `display_name`, `model_id|null`, `revision|null`, `availability` (`available` | `unavailable` | `loading`), `normalized_label` (positive/negative/neutral or null), `native_label`, `raw_scores` and `probabilities` (one softmax, `probability_kind: raw_softmax_uncalibrated`), `unavailable_reason` (19-value closed set), `processing_ms`. **There is no confidence field and no intensity field.** `TransformerResearchOut` adds `comparison` (status + explanation + `model_vs_rules`), `overall_sentiment`, `overall_source`, `uncertainty_reason`, `rules_relation`, `model_versions` (slot → revision), `model_availability`, `notices`, `validation_status`, `production_effect`, `processing_metadata`. Every analysis response keeps `model_version` and `data_source`.

## 5. Abstention and combined reading

- Missing text → `unavailable` (never neutral). Non-English / non-Latin / too few English function words → rules `unsupported_language` abstention; no model sees it. Text shorter than 3 words: the rules reading abstains. More than 1000 characters or control characters: rejected at the API with RFC 7807 (400); a non-string `text`: 422.
- One answering model vs rules: agree → label; differ → `uncertain` (`rules_disagree`); rules abstained → model label; rules reading "weak" (negation, hypothetical, past, third-person) → `uncertain` (`context_safeguard`). No answering model → rules label (`rules_baseline_fallback`).
- Two answering models: equal → `agreement`; different → `disagreement` and `uncertain` (`models_disagree`).
- Comparison statuses: agreement, disagreement, single_model, model_unavailable, one_model_unavailable, both_models_unavailable, no_model_configured, uncertain.

## 6. Error handling and lifecycle (ADR-055)

- Unavailability reasons are a fixed vocabulary (`disabled`, `licence_not_verified`, `format_not_allowed`, `dependencies_missing`, `weights_missing`, `manifest_invalid`, `revision_mismatch`, `artifact_corrupt`, `label_unsupported`, `load_failed`, `timeout`, `inference_failed`, `invalid_output`, `invalid_configuration`, `input_not_eligible`, `loading`, `internal_error`, `no_candidate_approved`, `registration_pending`). No exception text, path or stack trace reaches a response.
- Status path never loads weights, never hashes, never verifies (`candidate_status`).
- Load is synchronous on first use, guarded by a per-candidate non-blocking lock: a concurrent caller gets `loading` immediately. The module lock guards dictionaries only.
- A timeout opens a 30 s circuit breaker (`timeout` immediately); results are cached after a successful load; `clear_cache()` exists for tests.
- Optional `SENTIMENT_TRANSFORMERS_THREADS` (1–64; blank = untouched) is applied inside `TransformersBackend`. No startup warming, no `api/lifespan.py` change, no background threads.
- `build_transformer_research` is a catch-all boundary: any unexpected error yields `internal_error` slots plus the rules reading, never a 500.

## 7. Frontend

`frontend/src/lib/transformer-research.ts` (wording/state only) and `components/financial-health/transformer-research-panel.tsx` (markup). One card per role slot; empty slot = plain "No model registered" card; per-model "Rules-based reading" line; no confidence displayed; unknown labels render as "Unavailable", never "Neutral". TypeScript types are generated from OpenAPI (`npm run generate-types` equivalent via `app.openapi()`), never hand-written.

## 8. Boundaries that are enforced by tests

No import of torch/transformers outside `core/sentiment_model.py`; no network call on any path (socket guard); no text in logs/responses/DB; no Gemini call with user text; flags default off; production method string unchanged; no `confidence`/`intensity` key in the research object; Horizon constant remains `pending_owner_approval`. See `SENTIMENT_TEST_REPORT.md`.
