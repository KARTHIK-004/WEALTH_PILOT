# Sentiment API Reference (as of 2026-11-05)

Written for: frontend and backend developers integrating with the sentiment surface. The authoritative schema is the live OpenAPI document (`app.openapi()`); `frontend/src/types/api.ts` is generated from it. Both endpoints are **display-only**: no field here feeds risk, goals, portfolio, recommendations or compliance.

## 1. `POST /api/profiles/{profile_id}/personalized-insights`

Request body: `{ "text": string | null }` (`PersonalizedInsightRequest`). The text is analysed in memory and is **never stored, logged, echoed or sent to any external service** (including Gemini). The profile is scoped by `profile_id`; the caller is the customer resolved for the session.

Response (`PersonalizedInsightResponse`) always carries `model_version` and `data_source`. Sentiment-relevant parts:

| Field | Meaning |
|---|---|
| `user_sentiment` (rules reading, `user_text_rules_v1`) | `status` (`analysed` | `unavailable`), `unavailable_reason`, `sentiment` (positive / negative / neutral / mixed / uncertain / insufficient_evidence), `emotional_tone`, `financial_relevance`, `topics`, `evidence` (short phrases of the user's own words), `confidence` (**always null** for the rules baseline) and `confidence_band` (`unavailable`), `requires_confirmation`. Missing text → `status: unavailable`, never neutral. |
| `transformer_research` | Research object below. Always present in the insight response; `enabled` is `false` and no model runs unless `SENTIMENT_TRANSFORMERS_ENABLED=true`. |

### `transformer_research` (`TransformerResearchOut`)

`enabled`, `mode: "research_experimental"`, `validation_status: "not_human_validated"`, `production_effect: "none"`, `rules_baseline`, `models[]`, `comparison`, `overall_sentiment`, `overall_source` (`transformer_comparison` | `rules_baseline_fallback`), `rules_relation` (`agrees` | `disagrees` | `rules_abstained` | `not_compared`), `uncertainty_reason`, `model_versions` (slot → revision), `model_availability`, `processing_metadata`, `notices`.

`models[]` (`ResearchModelResultOut`, one per role slot `financial` / `general`): `slot`, `display_name`, `model_id|null`, `revision|null`, `availability` (`available` | `unavailable` | `loading`), `unavailable_reason`, `native_label`, `normalized_label`, `raw_scores`, `probabilities`, `probability_kind` (`raw_softmax_uncalibrated`), `processing_ms`.

`comparison`: `status` ∈ agreement, disagreement, single_model, model_unavailable, one_model_unavailable, both_models_unavailable, no_model_configured, uncertain; `explanation`; `model_vs_rules[]` (`slot`, `rules_label`, `model_label`, `relation`, `explanation`).

`unavailable_reason` ∈ disabled, licence_not_verified, format_not_allowed, dependencies_missing, weights_missing, manifest_invalid, revision_mismatch, artifact_corrupt, label_unsupported, load_failed, timeout, inference_failed, invalid_output, invalid_configuration, input_not_eligible, loading, internal_error, no_candidate_approved, registration_pending.

**Not present, by design:** `confidence`, `intensity`, any calibrated probability, any human-validation claim.

**Current behaviour (after R1/R2, ADR-056):** flag off (default) → `enabled: false`, the `general` slot is `unavailable / disabled` (model id and revision shown), the `financial` slot `unavailable / no_candidate_approved`, `comparison.status = model_unavailable`, `overall_sentiment` is the rules-based reading (`overall_source = rules_baseline_fallback`, `uncertainty_reason = transformers_unavailable`). Flag on with the verified files present → the `general` slot answers (Horizon) and `comparison.status = single_model`; files missing → `weights_missing`; first call during a load → `loading`.

### Errors (RFC 7807, `application/problem+json`)

| Status | Condition | Notes |
|---|---|---|
| 400 | `text` longer than 1000 characters, or contains control characters | title "Invalid request"; detail names the rule, **never echoes the text** |
| 404 | unknown customer/profile (`CustomerNotFoundError`) | problem+json |
| 422 | `text` is not a string (type validation) | problem+json |
| 200 | everything else, including a model that is unavailable, loading, timed out or failed | the failure is reported inside `transformer_research` as a fixed reason code; no exception text, path or stack trace is returned |

A research failure never turns into a 500: `build_transformer_research` catches unexpected errors and returns `internal_error` slots plus the rules-based reading.

## 2. `GET /api/sentiment-model/status`

Cheap and side-effect free: **loads no weights, computes no hashes, makes no network call.** Reads code constants, settings and file existence only. Response `SentimentModelStatusOut`:

- Trained-model seam (ADR-052): `enabled`, `state` (`disabled` | `ready` | `unavailable`), `reason`, `method_when_used`, `model_name`, `model_version`, `validation_status`, `calibration_status`, `intensity_available`, `fallback_enabled`, `dependencies_available`, `data_source`.
- Research (ADR-053/055): `transformers_enabled`, `research_slots[]` (`role`, `state` ∈ registered | registration_pending | no_candidate_approved, `candidate_key`, …), `research_models[]` (`TransformerCandidateStatusOut`: role, registration, licence/format status, `availability` ∈ disabled | blocked | weights_missing | not_loaded | loading | ready | unavailable, …), `reviewed_candidates[]` (verdicts as code constants, including Horizon `approved_for_research_inference` with the owner-decision text), `production_method: "user_text_rules_v1"`, `production_activation: "not_activated"`.

A candidate is `ready` only if an earlier request in this process already loaded it (cache hit); `not_loaded` means its files are present but nothing has loaded them yet; the status call itself never causes a load.

## 3. Compatibility note

ADR-055 changed the shape of `transformer_research` (a `models[]` list keyed by role instead of fixed `finbert`/`roberta` members). The object had never been enabled in any deployment; the generated TypeScript types and test fixtures were regenerated in the same change.
