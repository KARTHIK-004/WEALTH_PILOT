# Sentiment — Privacy and Security Audit (2026-11-05)

Written for: the project owner and security reviewers. Scope: the optional free text a customer may type, the rules baseline, and the research Transformer path. This is a prototype audit (`docs/SECURITY.md` limits apply: no per-account authorization layer, minimal prototype authentication). It is evidence-based: each control names the test that guards it.

## 1. Data-flow diagram

```
 customer's text (optional, ≤1000 chars)
        |  HTTPS to own backend only
        v
 POST /api/profiles/{id}/personalized-insights
        |  validate: str, ≤1000 chars, no control chars  --(violation)--> RFC 7807 400/422 (text NEVER echoed)
        v
 [in-process memory only]
   rules baseline (user_text_rules_v1) ──> user_sentiment (display)
        |
        | only if SENTIMENT_TRANSFORMERS_ENABLED=true AND a candidate is registered AND the text is English-eligible
        v
   Transformer adapter ──> local tokenizer + local safetensors (offline) ──> logits ──> one softmax
        v
   transformer_research (display)  ──> response to the same caller
        x  NOT persisted      x  NOT logged     x  NOT sent to Gemini / AutoGen / any external service
        x  NOT used by risk, goals, portfolio, recommendations, compliance
```

Trust boundaries: browser → backend (the only network hop that carries the text); backend process memory (text lives for the duration of the request); local model files (read-only). No other boundary is crossed.

## 2. Privacy controls

| Control | Mechanism | Guarding test(s) |
|---|---|---|
| Text is not stored | No DB column or model field holds it; the service builds the response and discards it | `test_personalized_insights*.py` (no persistence), research slots privacy tests |
| Text is not logged | No log call receives text; reasons are fixed codes | secret/privacy tests in `test_sentiment_research_slots.py` (log capture asserts absence) |
| Text is not echoed in errors | Length/content checks are in the service and the message names the rule only | `test_sentiment_research_api.py` (400/422 bodies contain no text) |
| No external transfer | `TransformersBackend` loads local files with offline flags; all network entry points are refused in tests; no Gemini/AutoGen path receives user text | netguard socket guard on the whole DB-free set; `test_sentiment_research_slots.py` isolation tests |
| Evidence excerpts are short phrases of the user's own words, shown only to that user | rules baseline output only | rules regression tests |
| Status endpoint is customer-independent | `GET /api/sentiment-model/status` returns no path, secret or text | API tests |
| Non-English / code-mixed text never reaches a model | rules `unsupported_language` gate precedes the adapter | `test_sentiment_research_slots.py` (Tamil, code-mixed) |
| No demo/test fixture contains real personal data | all sentences are fictional and synthetic | rules regression fixture (`rules_golden.json`) |

## 3. Security controls

- **Supply chain / model integrity:** weights must be `safetensors`; pickle-capable and framework checkpoints (`.bin`, `.pt`, `.pth`, `.pkl`, `.pickle`, `.ckpt`, `.h5`, `.msgpack`, `.npy`, `.npz`, `.joblib`) make the directory invalid. Exact 40-character revision; a `pretrained_manifest.json` with per-file SHA-256 and a manifest digest is checked at load. `torch.load` is never used (a test replaces it with a raiser). `trust_remote_code` is never used. Network is refused at load time (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`).
- **Path safety:** the model directory is `models/sentiment_pretrained/<key>/` derived from the registry key; symbolic links are rejected; no path comes from a request or from configuration at inference time.
- **Fail-closed gates:** licence → format → registration → files → manifest → load → inference. Any failure yields a fixed reason code; the rules reading answers.
- **Resource safety:** input capped at 1000 characters and `max_tokens`; per-candidate non-blocking load lock (no thundering herd; concurrent callers get `loading`); inference timeout with a 30 s circuit breaker; optional thread cap; no background threads or startup warming.
- **No information leakage:** exceptions map to fixed reasons (`load_failed`, `internal_error`, …); `build_transformer_research` never raises; RFC 7807 for every error; no stack trace, prompt, path or chain-of-thought is returned.
- **Prompt-injection:** the text never reaches an LLM on this path; the existing Gemini prompt-injection tests are unaffected.
- **Dependency surface:** the Transformer stack is installed in the project `.venv` under B2.1 (owner-authorised) and imported lazily and only from `core/sentiment_model.py`; the backend does not import TensorFlow at runtime. `setuptools==81.0.0` is pinned for TensorBoard's `pkg_resources` (recorded constraint, `RECOVERY_RECORD.md`).
- **Feature flags default off** (`SENTIMENT_TRANSFORMERS_ENABLED=false`); the status endpoint reports `production_activation: "not_activated"`.

## 4. Findings and residual risks

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | The weights' training data are web crawl and LLM-generated text with LLM labels; outputs may encode bias or toxicity. | Medium (quality, not confidentiality) | Accepted by the owner for research only; display-only with an "experimental" label; not used for any decision |
| 2 | First request after enabling pays a synchronous model load (≈3–4 s measured). | Low | By design (no startup warming without approval); concurrent callers get `loading` |
| 3 | Importing PyTorch and TensorFlow loads two OpenMP runtimes in one process (libiomp5md.dll, vcomp140.dll). | Low | OBSERVED stable in B2.1 in both import orders; the backend itself does not import TensorFlow; thread cap available |
| 4 | Prototype authentication / no per-account authorization (`docs/SECURITY.md`). | Disclosed | Out of scope; unchanged |
| 5 | Real-weights path through the adapter has not run. | Process | The opt-in smoke test exists; it needs the owner to approve placing the files |
| 6 | Dev database boundary incident (an earlier plain-pytest run of the `agents` directory touched `neondb` read-only by design and made 3 live Gemini calls). | Disclosed earlier | Not repeated; DB-backed suites now run only through `scripts/run_isolated_db_tests.py` |

No finding permits user text to leave the process, and none was found that does.

## 5. Not done (needs authority)

Retention/deletion policy for any stored text (D16 unresolved — nothing is stored, so nothing needs one); consented-text collection (D20 rejected); production activation (F1/R14 unresolved); registering Horizon.
