# Pretrained Transformer comparison — architecture (ADR-053)

A research-only, display-only comparison of two **pretrained** sentiment classifiers (FinBERT, Twitter-RoBERTa) against each other and against the production rules baseline. No training, no
fine-tuning, no dataset, no human labels, no regression head. Off by default. **Neither model can run today** (`model_licence_review.md`).

## Where it sits

```
user text (optional, in memory only)
  -> analyse_user_text            privacy + length + control characters, language, financial relevance, rules baseline  (user_text_rules_v1; production)
  -> eligible?  (interpretation_state not abstained / unavailable, text present)
       no  -> every model result = unavailable(input_not_eligible); the rules reading stands
       yes -> core/sentiment/inference_service.run_research
                 -> adapter.classify_with(FINBERT)   independent
                 -> adapter.classify_with(ROBERTA)   independent
                 -> comparison.compare_models        agreement | disagreement | one_model_unavailable | both_models_unavailable | uncertain
                 -> comparison.decide_overall        + the rules label and the rules safeguards (context "weak")
  -> PersonalizedInsightResponse.transformer_research   (composed AFTER compose_insight; nothing reads it)
```

The stored risk assessment, goals, portfolio, recommendation, compliance and savings-first logic are not inputs to, or outputs of, this package. `core/sentiment/` imports only `core.sentiment_model`
(artifact helpers) and itself; a test fails if it imports a decision module, a network, logging, storage or serialisation library, or `torch` / `transformers` at module level.

## Modules (`backend/wealthpilot/core/sentiment/`)

| Module | Role |
| --- | --- |
| `registry.py` | the two candidates as **code constants**: repository, 40-character revision, declared weight licence, `licence_status`, `format_status`, source URLs, date checked |
| `normalization.py` | native label -> `positive` / `negative` / `neutral` **by name** from the model's own `config.json` (never by index); `ModelResult`; logits -> uncalibrated softmax; invalid output -> unavailable |
| `adapter.py` | gates, manifest + SHA-256 verification, lazy load, one inference worker with a timeout, 30 s failure back-off, per-candidate status |
| `comparison.py` | pure two-model comparison and the rules relation; never averages, never breaks a tie |
| `inference_service.py` | eligibility, runs both candidates, never raises |

Service wiring: `api/services/personalized_insight_service.py` (`build_transformer_research`, `research_candidate_statuses`). Schemas: `api/schemas.py` (`TransformerResearchOut` and friends).
Frontend: `lib/transformer-research.ts`, `components/financial-health/transformer-research-panel.tsx`, rendered by `behaviour-sentiment-view.tsx`.

## Gates, in order (a failure is a fixed reason code, never text or a path)

1. `SENTIMENT_TRANSFORMERS_ENABLED` is true — else `disabled`.
2. Licence status in `registry.py` is `license_verified` — else `licence_not_verified`. (**Both candidates fail here today.**)
3. Format status is `safetensors_available` — else `format_not_allowed`. (RoBERTa fails here too.)
4. Settings valid (`SENTIMENT_TRANSFORMERS_MAX_TOKENS`, `_TIMEOUT_SECONDS`, `_DEVICE=cpu`) — else `invalid_configuration`; nothing is defaulted.
5. Directory `models/sentiment_pretrained/<key>/` exists, strictly inside the root, no symbolic link — else `weights_missing` / `manifest_invalid`.
6. `pretrained_manifest.json`: schema 1; repository, weight licence and the **exact** 40-character revision match the registry (`revision_mismatch` for a floating or different revision); every file's SHA-256 matches and the manifest hash is recomputed (`artifact_corrupt`); `model.safetensors`, `config.json`, `tokenizer_config.json` listed; **any** `.bin` / `.pt` / `.pkl` / `.ckpt` / `.h5` / `.msgpack` / ... file listed refuses the artifact (`format_not_allowed`).
7. `config.json` `id2label` is a complete 0..n-1 mapping of exactly positive / negative / neutral names — else `label_unsupported`.
8. Tokenizer length recorded in the manifest is checked against the embedding matrix before any inference, and against the loaded tokenizer (`TransformersBackend`, `trust_remote_code=False`, `local_files_only=True`, `use_safetensors=True`).
9. Packages importable — else `dependencies_missing`.

At run time: a wall-clock timeout (`timeout`), any backend exception (`inference_failed`, the exception text is discarded), non-finite or wrong-length output (`invalid_output`).

## Label normalisation

FinBERT and Twitter-RoBERTa document **different class orders**. The code never assumes an order: it reads `id2label` and maps by name. The native label is returned beside the normalised one.
The models cannot say `mixed` or `uncertain`; those states arise only in the comparison (disagreement, rules safeguards). An unknown label such as `LABEL_0` makes the model unavailable. It is never mapped to neutral.

## Comparison and the combined reading

| Situation | Combined reading | Source | Reason |
| --- | --- | --- | --- |
| both answer, same label, rules agree or abstain | the shared label | `transformer_comparison` | none |
| both answer, different labels | `uncertain` | `transformer_comparison` | `models_disagree` |
| models agree, rules differ (including `mixed`) | `uncertain` | `transformer_comparison` | `rules_disagree` |
| models agree, rules safeguards say the wording is `weak` (negation, hypothetical, past, third person, quote) | `uncertain` | `transformer_comparison` | `context_safeguard` |
| one or both unavailable | the rules reading | `rules_baseline_fallback` | `one_model_unavailable` / `transformers_unavailable` |
| text not eligible | the rules reading | `rules_baseline_fallback` | `input_not_eligible` |

All three readings (rules, FinBERT, RoBERTa) are always returned separately. Scores are each model's own logits and an **uncalibrated** softmax (`probability_kind`); there is no `confidence` field,
no intensity, and no cross-model comparison of scores.

## Dependencies (not installed)

The ADR-052 proposal stands: `torch==2.6.0` (CPU build), `transformers==4.57.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`, in the optional `sentiment` group of `backend/pyproject.toml`, hash-pinned. TensorFlow 2.17
(installed) remains untouched; Transformers 5 reportedly drops TensorFlow support, so PyTorch is the only practical backend. Sizes, coexistence risks and the rollback plan are in
`reports/sentiment_transformer_dependency_request.md`. None of this has been approved or installed.

---

## Reviews and replacement candidates (ADR-054, 2026-11-03)

`core/sentiment/reviews.py` holds a review record for every candidate considered (FinBERT, Twitter-RoBERTa, `tooshlegacy/distilbert-financial-tweet-sentiment`, `Horizon-Labs/multilingual-sentiment-small`): repository, revision, architecture, declared licence, licence file,
base model and licence, training data, native labels and their mapping, safetensors file and hash, **verdict** (one of `approved_for_research_inference`, `blocked_by_license`, `blocked_by_provenance`, `blocked_by_approval`, `incomplete_review`), blockers and sources.
The verdicts are code constants; they are listed read-only under `reviewed_candidates` on `GET /api/sentiment-model/status`. The active comparison pair in `registry.py` is unchanged (both gated off). Review records do not make anything runnable.

Label vocabulary: `normalization.py` accepts positive / negative / neutral and the financial-tweet words bullish (positive) and bearish (negative), case-insensitively, returns the model's own spelling as the native label, and refuses a set that mixes vocabularies or contains any other word.

---

## Horizon runtime findings (2026-11-04)

`transformers` 4.57.1 cannot be used for the Horizon model (silent wrong rotary-embedding setting for the sliding-attention layers); `transformers` 5.17.0 is required, with `tokenizers>=0.23.1` and `safetensors>=0.8.0`, superseding the ADR-052 pins for this model. The existing `TransformersBackend`, manifest tool, comparison and panel are reused unchanged; the only registry-level work is the later, separately approved key generalisation. Details and the staged plan: `horizon_runtime_plan.md`.
