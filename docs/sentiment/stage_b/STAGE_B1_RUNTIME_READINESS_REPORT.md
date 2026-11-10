# Stage B1 — Horizon Runtime Selection and Integration Readiness

Written for: the project owner, who must review this before any B2 work. Date: 2026-11-04.
Model: `Horizon-Labs/multilingual-sentiment-small` @ `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`. Scope: **investigation and non-mutating technical planning only.**
Evidence labels: **VERIFIED** (read from source, or measured here by a recorded command), **OBSERVED** (seen, or reported by someone else, not independently established), **PROPOSED** (a design recommendation, not implemented), **UNRESOLVED** (not enough evidence), **NOT AUTHORIZED** (outside B1).
Precedence applied: `CLAUDE.md` and `docs/PROJECT_PLAN.md` over lower-priority documents. `docs/PROJECT_PLAN.md` and `docs/MASTER_PROMPT.md` do not mention transformers, torch, ONNX or FinBERT at all (VERIFIED by search), so the sentiment-model path rests on `CLAUDE.md` and the ADRs (ADR-043, 048, 050, 052, 053, 054).

## 1. Executive Summary

**Recommended runtime: A — `transformers` 5.17.0 with CPU PyTorch and safetensors** (the stack Stage A proved), **conditional on a coexistence test (B2) before it enters the application environment.** ONNX Runtime FP32 is a possible later alternative that needs a separate artifact-policy decision; it is not recommended now. Rules-only is today's production method and remains the fallback, not an alternative way to get a Transformer reading.

Why A: it is the only option with measured evidence on this machine (real inference on the approved safetensors artifact, bitwise stable, 16-23 ms per sentence, 0.82 s load, 1.14 GB peak), it needs no change to the artifact policy, and the existing adapter already implements it.

**Findings that matter most (all VERIFIED unless marked):**

1. **The comparison design cannot use a single approved model.** The ADR-053 comparison is a fixed two-slot design (FinBERT, Twitter-RoBERTa). With the financial slot permanently empty, Horizon's result would never be compared with the rules reading and would never contribute: the result is always `one_model_unavailable` plus the rules reading as fallback. B2 needs a design decision (section 8): a single-model-versus-rules comparison and role-keyed slots.
2. **Failure-isolation gaps in the existing adapter** that matter once a real model can load (section 10), **each reproduced by fault injection with stand-in backends** (no model, no network, no database): model construction runs inside the global lock, so a status read waited 1.31 s behind another candidate's 1.5 s load; `GET /api/sentiment-model/status` itself constructs the model (1 construction measured); and an `OSError` (for example a Windows DLL failure when `torch` is imported next to TensorFlow), a `MemoryError` at load time, or a `PermissionError` on a model file all **propagate out of the research function unhandled**, so the production insight endpoint would fail with an HTTP 500 (the propagation is measured; the HTTP response itself was not exercised).
3. **Installing the stack in the application environment is not clean.** A resolver dry-run against the real project `.venv` (nothing installed) shows 16 new packages and exactly **one change to an existing package: `setuptools` 65.5.0 -> 84.2.1**; and for 7 shared packages the application's versions differ from the ones Stage A tested, so Stage A's evidence does not strictly transfer. Coexistence of TensorFlow 2.17 and PyTorch in one process is **UNRESOLVED** (untestable without installing).
4. **`CLAUDE.md` section 5 forbids adding a library outside the approved list without asking**, and torch, transformers, tokenizers, safetensors and huggingface-hub are not on it. That approval is a prerequisite for any B2 installation.
5. **Horizon's multilingual ability is unreachable** through the current pipeline: the rules front end abstains on non-English text before any model is called.

No installation, download, registry change, flag change, schema change or ONNX work was done. The project `.venv` is byte-identical before and after (section 5). **B1 verdict: complete; B2 requires the decisions in section 14.**

## 2. Existing Architecture

Inspected in the current source (not taken from old reports). `core/user_text_sentiment.py` limits: `MAX_TEXT_CHARS = 1000`, `MIN_WORDS = 3`, non-Latin share above 0.2 or too few English function words means an unsupported language.

```
USER TEXT (optional)                                             [IMPLEMENTED]
  |
  v
POST /api/profiles/{id}/personalized-insights                    routers/personalized_insights.py
  |
  v
personalized_insight_service.build_insight / build_insight_from_features
  |-- monthly records (DB session) -> behaviour features -> derive_findings
  |-- stored risk assessment (DB session)                        <- authoritative for risk
  |
  v
analyse_user_text(text)                                          core/user_text_sentiment.py
  1 validate_text: control characters and > 1000 chars refused (text never echoed); whitespace normalised
  2 privacy masking of contact details and links in evidence
  3 language + financial-relevance + length checks -> may ABSTAIN (unsupported_language, unrelated_text, too_short ...)
  4 RULES BASELINE `user_text_rules_v1` (rules, safeguards: negation, hypothetical, past, third person, quote)
  |
  v
compose_insight(findings, analysis, risk)                        stored assessment stays authoritative
  |
  v
PersonalizedInsightResponse  (user_sentiment = RULES reading; risk_profile.remains_authoritative = true)
  |
  |  ===== composed AFTER compose_insight and read by nothing else =====
  v
build_transformer_research(text, analysis)                       personalized_insight_service.py  [IMPLEMENTED for FinBERT/RoBERTa slots; GATED OFF]
  |-- eligibility: text present AND interpretation_state not in {abstained, unavailable}     inference_service.run_research
  |-- registry gates: licence_status == license_verified AND safetensors     adapter.check_gates   (both active candidates BLOCKED)
  |-- verify_pretrained: manifest, exact revision, SHA-256 of every file, label order        adapter.verify_pretrained
  |-- load_adapter (global lock) -> TransformersBackend (transformers + torch, CPU)          [needs packages: NOT INSTALLED]
  |-- PretrainedAdapter.classify: ONE worker thread, wall-clock timeout, fixed reason codes
  |-- native label -> normalised label by NAME from config.json id2label                     normalization.py
  |-- compare_models (TWO fixed slots) -> decide_overall (+ rules label and rules state)     comparison.py
  v
transformer_research object on the response (optional; display only; no confidence; no intensity)
  v
frontend: TransformerResearchPanel (A rules, B two model cards, C comparison)               behaviour-sentiment-view.tsx

NOT IMPLEMENTED for Horizon: a registry entry; a generalised slot (the slots, the schema Literals `finbert` / `roberta`, the
inference service and the two panel cards are all hard-wired to the old pair); a single-model-versus-rules comparison;
a non-blocking load; a service-boundary catch-all; any installed runtime.
```

Other facts VERIFIED from the source:
- The sentiment code is reached **only** from `routers/personalized_insights.py` and `api/services/demo_behaviour_service.py` (via `personalized_insight_service`). Nothing in `agents/`, `analysis_service.py` or `qa_service.py` references sentiment, user text or the research object, so no sentiment text reaches the Gemini explanation, debate or Q&A paths, nor risk, goals, portfolio, recommendations or compliance.
- Feature flags (`config/settings.py`): `sentiment_model_enabled` (ADR-052, trained-model seam) and `sentiment_transformers_enabled` plus `..._max_tokens`, `..._timeout_seconds`, `..._device` (ADR-053); all default off. The ADR-052 path serves a single fine-tuned, validated, calibrated artifact and refuses anything unvalidated, so it cannot carry a pretrained research model.
- The application start-up (`api/lifespan.py`) warms the production model caches **fail-fast**: "the application never starts serving requests with a broken/absent model". A research feature must not inherit that.
- The backend is launched as one `uvicorn ... --reload` process (`README.md`); there is no `--workers` setting in the repository.
- The frontend panel, status endpoint and review records (`core/sentiment/reviews.py`, verdict `approved_for_research_inference` for Horizon) exist; Horizon is **not** in the active registry (`active_in_registry False`, `any runnable False`).

## 3. Stage A Evidence Reference

From `docs/sentiment/stage_a/STAGE_A_COMPLETION_REPORT.md` (VERIFIED there, reused, not repeated): isolated Python 3.11.9 environment, hash-pinned lock of 35 packages (`docs/sentiment/stage_a/requirements-stage-a.lock.txt`), `pip check` clean; transformers 5.17.0, tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 1.33.0, torch 2.15.0+cpu, numpy 1.26.4; eight files at the exact revision, every SHA-256 matching the repository's `SHA256SUMS`; `model.safetensors` `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1`; labels `0 negative, 1 neutral, 2 positive`; raw output is logits and exactly one softmax equals the library pipeline (1.9e-9); five repeats bitwise identical; 16.4-22.9 ms per sentence (median 20.4), 321.9 ms for a 512-token input; load 0.82 s; peak 1,139.7 MB (305 MB after imports); 0 network attempts, 0 `torch.load` calls, no remote code; torch used 4 default threads on this 8-CPU machine. Its limits stand: eight invented sentences, no accuracy, calibration or validation claim; TensorFlow was deliberately absent from that environment.

## 4. Runtime Comparison

| Criterion | **A. transformers 5.17.0 + CPU torch + safetensors** | **B. ONNX Runtime FP32** (separate artifact-policy approval needed) | **C. Rules only** |
| --- | --- | --- | --- |
| Evidence on this machine | **VERIFIED** (Stage A real inference) | **UNRESOLVED**: nothing run | **VERIFIED** (measured below) |
| Python | 3.11.9 (torch 2.15.0 and onnxruntime 1.31.1 both need >= 3.11) | same | n/a |
| Artifact | `model.safetensors` 562,584,932 bytes, owner-approved, no pickle | `onnx/model.onnx` 563,103,014 bytes (sha256 `fed14ea4...b066e`, from the repository); **a different format than the one approved; the project rule is safetensors-only**; NOT AUTHORIZED | none |
| Latency | VERIFIED 16.4-22.9 ms median 20.4; 512 tokens 321.9 ms | author-reported 17.96 ms for fp32 on unknown hardware (OBSERVED, not measured here) | VERIFIED median **0.073 ms**, p95 0.108 ms, max 0.292 ms (1,600 calls, 8 fictional sentences, project `.venv`, no model) |
| Load time | VERIFIED 0.82 s warm file cache; cold UNRESOLVED | UNRESOLVED | none |
| Peak memory | VERIFIED 1,139.7 MB (305 MB imports + about 835 MB model) | UNRESOLVED (weights file is the same size class) | the application imports at about **215 MB**; no extra |
| Dependencies | torch (CPU) + transformers + tokenizers + safetensors + huggingface-hub and about 30 transitive packages | `onnxruntime` (14.9 MB cp311 win_amd64 wheel; needs numpy >= 1.21.6, protobuf >= 4.25.8, flatbuffers, packaging; all already satisfied) **plus** `tokenizers`, which itself pulls huggingface-hub; avoids torch, transformers, safetensors, sympy, networkx, jinja2 | none new |
| Unknowns | in-process coexistence with TensorFlow (UNRESOLVED) | input and output names, opset, whether the output is logits or probabilities (a double softmax would corrupt scores), tokenizer id parity with the transformers tokenizer, TensorFlow coexistence; only fp32 usable because `model_quantized.onnx` agrees on 99.3% of the author's 430 texts | none |
| TensorFlow / Keras 2.17 | no declared conflict (transformers 5.17.0 and torch declare no TensorFlow requirement); **DLL / OpenMP coexistence on Windows UNRESOLVED**; the baseline here: the first TensorFlow import in this run took 14.3 s and reached 344 MB | onnxruntime has its own native libraries: same class of risk, UNRESOLVED | none |
| NumPy / protobuf | numpy 1.26.4 used successfully in Stage A; protobuf not required, so the app's 4.25.9 is unaffected (VERIFIED by the dry-run) | numpy and protobuf requirements satisfied (VERIFIED from metadata) | n/a |
| Deployment complexity | high: about 1.5 GB disk (937 MB environment + 570 MB model, measured sizes), one model copy per worker | medium: smaller install, new artifact and parity work | none |
| Security | safetensors only; `trust_remote_code=False`; `local_files_only`; hash-verified manifest; no pickle path (VERIFIED in code and run) | ONNX is a protobuf graph, not pickle; custom ops and external-data files are a different surface; UNRESOLVED | smallest |
| Failure isolation | **gaps in the current adapter (section 10)** | would need the same hardening | n/a |
| Maintenance risk | pinned and hashed; torch 2.x and transformers 5.x move fast; v4.57.1 is **not** usable for this config (silent rope error, OBSERVED from its source; not run) | extra conversion/parity burden; the artifact is published by a third party | none |

**Not chosen: quantized ONNX** (as instructed; it also differs from fp32 on 0.7% of the author's inputs). **Not assumed: transformers 4.57.1.**

## 5. Dependency Compatibility

**Method (non-mutating).** `pip install --dry-run --report` was driven from the *isolated* Stage A environment with `--python <project .venv>`, so it resolved against the project environment's real installed set while running no code from, and installing nothing into, `.venv`. Requested: `transformers==5.17.0`, `tokenizers==0.23.3`, `safetensors==0.8.0`, `huggingface-hub>=1.5.0,<2.0`, `torch==2.15.0+cpu` (CPU index plus PyPI, wheels only).

**Result (VERIFIED):** exit 0; no conflict reported; pip "would install" 16 packages, all new except one: `annotated-doc`, `filelock`, `fsspec`, `hf-xet`, `huggingface-hub` 1.33.0, `jinja2`, `mpmath`, `networkx`, `safetensors` 0.8.0, `shellingham`, `sympy`, `tokenizers` 0.23.3, `torch` 2.15.0+cpu, `transformers` 5.17.0, `typer`, and **`setuptools` 65.5.0 -> 84.2.1 (an upgrade of an existing package)**. After the dry-run the project `.venv` `site-packages` timestamp (2026-10-29 21:31:18) and the frozen package list are identical to before.

| Item | Finding |
| --- | --- |
| TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9, ml-dtypes, flatbuffers | not in the "would install" set, so none would change (VERIFIED by the dry-run) |
| `setuptools` 65.5.0 -> 84.2.1 | torch declares `setuptools>=77.0.3`. A major upgrade of the build tool inside the application environment; whether anything there still relies on legacy `pkg_resources` behaviour is **UNRESOLVED** |
| 7 shared packages differ from the versions Stage A tested | the application keeps its own versions: `anyio` 4.15.1 (tested 4.16.0), `httpx` 0.27.2 (0.28.1), `idna` 3.19 (3.20), `markupsafe` 3.0.3 (3.0.4), `packaging` 25.0 (26.3), `pyyaml` 6.0.2 (6.0.3), `regex` 2026.9.10 (2026.9.29). pip accepted them, but this exact combination was **never run**. 12 others are identical (certifi, click, colorama, h11, httpcore, markdown-it-py, mdurl, numpy, pygments, rich, tqdm, typing-extensions) |
| TensorFlow + torch in one process | **UNRESOLVED** and not testable without installing. Needs a new external environment (section 14, D-B2) |
| Python / ABI | 3.11.9 meets torch 2.15.0 (>= 3.11), transformers 5.17.0 (>= 3.10), onnxruntime 1.31.1 (>= 3.11) (VERIFIED from metadata) |
| ADR-052 pins | `tokenizers 0.22.1` and `safetensors 0.6.2` conflict with transformers 5.17.0 (`>=0.23.1`, `>=0.8.0`) and are superseded for this model |
| `CLAUDE.md` section 5 | the library list does not contain any of the five new top-level packages; "Do not add a library outside this list without asking first" (VERIFIED at line 79) |

**Proposed isolated runtime lock (PROPOSED):** the existing hash-pinned `docs/sentiment/stage_a/requirements-stage-a.lock.txt` is the proposal unchanged. For an in-application install, B2 must first produce a *second* lock from the application's exact frozen set plus these packages (D-B2); that lock does not exist yet.

## 6. Recommended Runtime

**A, the reference stack, with the deployment mode decided after the coexistence test (PROPOSED):**

- **A1, in-process** (reuses the existing adapter; no new architecture): acceptable only if the coexistence test passes *and* the hardening in section 10 is in place. Costs: about 1.1 GB resident per server process on top of the application and TensorFlow; the `setuptools` upgrade; 7 untested shared versions.
- **A2, out-of-process worker** in its own environment (the Stage A environment already exists): isolates dependency, memory and DLL risk completely, at the price of a new component (process management and a local channel for the text) that needs its own ADR and privacy review. Not proposed unless A1's coexistence test fails.

My lean: A1 behind the section 10 guards, because it reuses what exists and the feature is research-only and off by default; **A2 if the coexistence test shows any TensorFlow/torch conflict.** This is a recommendation for the owner, not a decision.

## 7. Proposed Integration Architecture

Principle (PROPOSED, extending ADR-053/054): Horizon is a **display-only research reading beside the rules reading**; nothing reads it.

| # | Required guarantee | Existing mechanism (VERIFIED) | Needed in B2 (PROPOSED) |
| --- | --- | --- | --- |
| 1 | Research-only | `mode: research_experimental`, `production_effect: none`, flag default off, registry gate | add Horizon under the same gates |
| 2 | Rules stay authoritative | production `user_sentiment` is the rules reading; research composed after, read by nothing | keep; test that the response minus the research object is identical |
| 3-7 | No effect on risk, recommendations, goals, portfolio, compliance | nothing in `agents/`, `analysis_service`, `qa_service` references sentiment (VERIFIED by search); package-import guard test | keep; extend the guard to the new adapter modules |
| 8 | No text to Gemini or any external inference API | no import path from the research code to `agents/` or `google-genai`; local inference only; sockets refused in the Stage A run | add a test that the research modules import no network library (exists) and a startup assertion that offline variables are set |
| 9 | No raw text persisted or logged | the text is only an argument; no logging in the package; tested | keep |
| 10 | Inference failure never breaks the production endpoint | per-model fixed reason codes | **close gaps G3-G5 (section 10)** |
| 11 | Missing text is unavailable, not neutral | `overall_sentiment None`, `input_not_eligible` | keep |
| 12 | Model output distinguishable from rules | separate `rules_baseline`, `finbert_result` etc.; `overall_source` | add the role-keyed fields |
| 13 | Version and source traceable | revision, repository, licence, SHA-256 manifest | add `runtime` and the lock hash |
| 14 | Not presented as calibrated confidence | no confidence field; `probability_kind: raw_softmax_uncalibrated` | keep |
| 15 | Uncertainty preserved | `uncertain` from disagreement and safeguards | add single-model-versus-rules rule |

## 8. Adapter and Response Schema (PROPOSED; nothing implemented or registered)

**Interface** (a refinement of the existing `Backend` / `PretrainedAdapter`; it separates verification from loading and adds an explicit warm-up):

```python
class ResearchRuntime(Protocol):
    runtime_id: str                                 # "transformers_torch_cpu"  (an ONNX id only if separately approved)
    def verify(self) -> RuntimeInfo: ...            # manifest, revision, SHA-256, label order; loads nothing; never raises; used by GET /status
    def warm(self) -> None: ...                     # explicit, off the request path, may take seconds; failures become reason codes
    def predict(self, text: str) -> RawOutput: ... # logits only; the text never leaves; only fixed reason codes escape
```

**Role-keyed slots** replace the two fixed names (`finbert` / `roberta`): `slot: financial | general`. Horizon fills `general`; `financial` stays unavailable (`no_candidate_approved`) until a separately approved model exists.

**Normalised result** (generalises `TransformerModelResultOut`; no confidence, no intensity, no text, no path):

```python
class ResearchModelResultOut(BaseModel):
    slot: Literal["financial", "general"]
    model_id: str                                   # "Horizon-Labs/multilingual-sentiment-small"
    revision: str                                   # 40-hex, from the verified manifest
    runtime: Literal["transformers_torch_cpu"]
    availability: Literal["available", "unavailable", "loading"]
    unavailable_reason: Literal[...existing codes..., "loading", "internal_error", "no_candidate_approved"] | None
    native_label: str | None                        # exactly the model's own: negative | neutral | positive
    normalized_label: Literal["positive", "negative", "neutral"] | None
    raw_scores: dict[str, float] | None             # logits by native label
    probabilities: dict[str, float] | None          # ONE softmax over the logits, uncalibrated
    probability_kind: Literal["raw_softmax_uncalibrated"] | None
    processing_ms: float | None

class ModelVsRulesOut(BaseModel):                   # NEW: needed because only one model is approved
    model_slot: Literal["financial", "general"]
    rules_label: str | None
    model_label: Literal["positive", "negative", "neutral"] | None
    relation: Literal["agrees", "disagrees", "rules_abstained", "not_compared"]
    explanation: str
```

**Decision rule for the combined research reading with one model (PROPOSED):**

| Situation | Combined reading | Reason |
| --- | --- | --- |
| model answered, rules label equal | the label | none |
| model answered, rules label differs (including `mixed`) | `uncertain` | `rules_disagree` |
| model answered, rules abstained | the model label, flagged `rules_abstained` | none |
| rules safeguards say the wording is `weak` (negation, hypothetical, past, third person, quote) | `uncertain` | `context_safeguard` |
| model unavailable or loading, or text not eligible | the rules reading (`rules_baseline_fallback`) | `transformers_unavailable` / `loading` / `input_not_eligible` |

When the `financial` slot later gains a model, the existing two-model comparison applies unchanged. Nothing here uses Gemini or any other model to break ties.

## 9. Privacy and Security Boundaries

- **VERIFIED:** the text exists only as an in-memory argument; the research modules import no logging, network, storage or serialisation library (guard test); errors are fixed reason codes; the Stage A run refused and counted every network entry point (0) and replaced `torch.load` with a function that raises (0 calls); artifacts load only from a confined directory with `local_files_only`, `use_safetensors=True`, `trust_remote_code=False`; no code was imported from the model directory.
- **PROPOSED additions:** keep `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1` set for the serving process and assert them at load time; never log the exception object from the backend (it can carry the text); cap torch threads by a setting (Stage A used torch's default of 4 on 8 CPUs, an unmanaged value); one model copy per server process (about 1.1 GB each).
- **NOT AUTHORIZED / out of scope:** any external inference API, any storage or transmission of the text, any use of the output in a financial decision.

## 10. Failure and Fallback Strategy

Gaps found by reading `core/sentiment/adapter.py`, `core/sentiment_model.py` and the service, then **reproduced by fault injection** with the existing adapter and stand-in backends (script and output in the appendix; VERIFIED by execution; no real model, torch, network or database was involved; the HTTP 500 itself was inferred from the unhandled propagation and not exercised over HTTP):

| ID | Gap | Consequence | Proposed fix |
| --- | --- | --- | --- |
| G3 | `load_adapter` builds the model **inside the global `_LOCK`, in the request thread** | the first text-bearing request pays the whole load time (0.82 s warm; cold unmeasured) and blocks every other caller of `load_adapter`, `candidate_status` and `clear_cache` (**measured with a 1.5 s stand-in load:** a status read issued 0.2 s in waited 1.31 s) | load off the request path (explicit warm-up or a background loader); return `loading` meanwhile; never hold the lock while loading |
| G3b | `candidate_status` (used by `GET /api/sentiment-model/status`) **calls `load_adapter`** | a status read would load a 560 MB model (**measured:** `candidate_status` on an enabled, runnable candidate made 1 model construction and returned `ready`) | status uses verification only (`verify`), reports `loaded` from the cache, never loads |
| G4 | the import of `torch` is guarded by `except ImportError` only, `_sha256` file reads are unguarded, `classify_with` catches only `ResearchUnavailable`, and the service call at `personalized_insight_service.py:255` has no `try` | **measured:** an `OSError` (DLL-style), a `MemoryError` at load time and a `PermissionError` at the hash step each escaped `build_transformer_research` as an unhandled exception, while an `ImportError` and any inference-time `MemoryError` / `RuntimeError` were handled; the unguarded call site means the **production insight endpoint would return an HTTP 500** (inferred, not exercised over HTTP) | a catch-all at the service boundary that turns any exception into an unavailable research object (`internal_error`), plus narrower catches in the adapter; test with injected `OSError` and `MemoryError` |
| G5 | start-up warming in `api/lifespan.py` is fail-fast | a research model joining it could stop the application from starting | Horizon must never join the fail-fast path; optional, non-fatal warm-up only |
| G7 | one worker thread; `future.cancel()` cannot stop a running torch call | a hung inference makes every later request wait its full timeout before reporting `timeout` (**measured:** with a 0.30 s limit the next call returned `timeout` after 0.31 s while the worker was still busy) | circuit-breaker: after a timeout, report `timeout` immediately for the back-off window without queuing |
| G8 | each server process holds its own copy | N workers means N x 1.1 GB | single worker (as in the repository) and a documented limit |

Fallback order (PROPOSED, unchanged in spirit): Horizon unavailable for any reason -> the research object says so with a fixed reason -> the rules reading stands -> the production response is complete either way.

## 11. Test Matrix (PROPOSED; fictional inputs only; none is an accuracy evaluation or human validation, and no label is predicted)

Layers: **U** unit with a mocked backend; **I** integration with the mocked adapter through the API (no database or isolated runner); **R** opt-in real-weights smoke test in the isolated environment; **F** frontend component test; **D** database-backed test through the isolated runner only. Expectations are about behaviour and structure, never about which label a model "should" give.

| # | Scenario (fictional example) | Layer | Expected behaviour |
| --- | --- | --- | --- |
| 1 | positive: "I feel happy because my savings have increased this month." | U, R | available; native label from the model; normalised label present; no confidence field |
| 2 | negative: "I am worried because my monthly loan payments are becoming difficult to manage." | U, R | same structural checks |
| 3 | neutral: "I deposited five thousand rupees into my savings account this month." | U, R | same |
| 4 | mixed: "My investments are growing, but I am worried about future expenses." | U, R | a three-class label (never `mixed` from the model); the rules reading may differ and the relation is reported |
| 5 | negation: "I am not worried about my savings at all." | U, I | rules safeguards decide `weak` or not; combined reading `uncertain` with `context_safeguard` when weak |
| 6 | hypothetical / conditional: "If I lost my job I would panic about my savings." | U, I | combined `uncertain`, `context_safeguard`; the model's native label recorded but not promoted |
| 7 | sarcasm: "Great, another fee, just what my budget needed." | U, R | documented limitation; only structure and disclaimers asserted; no label asserted |
| 8 | multilingual: "Estoy muy contento porque por fin pude ahorrar." | I, F | **never reaches the model**: abstains `unsupported_language` before inference; the model slot shows `input_not_eligible` (a design fact, G12; enabling it is a policy decision, NOT AUTHORIZED) |
| 9 | code-mixed: "Mera EMI bahut high hai, I am worried." | I, F | depends on the rules language check (non-Latin share, English function words); assert the actual path, either abstain or eligible |
| 10 | empty string / whitespace only | U, I | no model call; unavailable, never neutral |
| 11 | missing text (`null`) | U, I, F | research object present, `overall_sentiment` null, `input_not_eligible` |
| 12 | fewer than 3 words: "Money worries." | I | abstain `too_short` before the model |
| 13 | over-long text (> 1,000 characters) | I | refused by `validate_text` with a problem response that never echoes the text |
| 14 | control characters in the text | I | refused, text not echoed |
| 15 | text near the token limit (about 1,000 characters) | U, R | tokenizer truncates to 512; result available; truncation flagged in processing metadata (PROPOSED field) |
| 16 | model files missing | U, I | `weights_missing`; rules reading stands; HTTP 200 |
| 17 | corrupted / wrong checksum / wrong revision / pickle file listed | U | `artifact_corrupt` / `revision_mismatch` / `format_not_allowed` |
| 18 | model loading failure (injected `OSError` on `import torch`, DLL-style) | U, I | **must not raise out of the service** (closes G4): `internal_error`, HTTP 200 |
| 19 | injected `MemoryError` during inference ("CPU memory pressure") | U, I | `inference_failed` or `internal_error`; endpoint stays 200 |
| 20 | inference timeout (backend sleeps past the limit) | U | `timeout`; second request during back-off returns immediately (closes G7) |
| 21 | invalid output (NaN, wrong length, probabilities instead of logits) | U | `invalid_output`; never a guessed label |
| 22 | rules / model disagreement (mocked logits) | U, I, F | `uncertain` with `rules_disagree`; all readings preserved and displayed |
| 23 | rules abstains, model answers | U, I | model label flagged `rules_abstained` |
| 24 | status endpoint when enabled but not loaded | I | reports verification state without loading (closes G3b); loaded flag false |
| 25 | first request while loading | U, I | `loading`, rules reading stands, no blocking |
| 26 | frontend: profile switching and cache isolation | F | the research object is not retained across profiles (card keyed by profile, `gcTime: 0`); no text in storage, URL or console |
| 27 | frontend: all states (answered, loading, unavailable, disagreement, not eligible, disabled) | F | notices shown; no confidence or intensity ever rendered |
| 28 | financial isolation | I | response minus the research object identical whatever the model returns; risk, goals, portfolio, recommendation and compliance fields unchanged |
| 29 | privacy | U, I | text absent from logs, URLs, errors, the serialised research object, caches |
| 30 | no network during ordinary tests | all but R | socket guard reports 0 attempts; real-weights test is opt-in and separate |

Real-weights tests (R) record outputs as observations and never as expected labels.

## 12. Database and Environment Safety

- **Process failure to avoid repeating (documented in the Stage A completion report, section 10.3):** plain `pytest` on `tests/backend/agents` opened sessions on the development database `neondb` and made live Gemini calls.
- **VERIFIED (B1):** `python scripts/run_isolated_db_tests.py --preflight` resolves to host `ep-wild-mode-ae88s68g-pooler.c-2.us-east-2.aws.neon.tech`, database **`neondb_test`**, confirms the effective application settings resolve to the same target, lists suites `api`, `db`, `ingestion`, states "development-database tests are deselected", and printed "preflight only: nothing executed" (exit 0). It opened no database connection and ran no tests; no URL or password was printed.
- **Rules for all future database-backed work (PROPOSED as the standing procedure):** run database-backed suites only as `python scripts/run_isolated_db_tests.py --suite api --suite db` (the runner sets both database URLs to `neondb_test` and deselects every `real_*` test); one process at a time; never plain `pytest` on `tests/backend/api`, `tests/backend/db` or `tests/backend/agents`; treat `tests/backend/agents` and any `real_*` test as an explicit owner-approved development-database read plus live-Gemini run, never a default; never query, inspect or clean up `neondb`; the sentiment unit tests (`tests/backend/core`, `tests/training`, the personalised-insight API tests that use a stubbed session) are database-free and may run under the socket guard.
- **B1 made no database call**, ran no test suite, wrote no migration and changed no schema.
- Environment: B1 installed nothing; the project `.venv` is unchanged (timestamp and frozen package list identical before and after the dry-run); the Stage A environment and model directory were not modified.

## 13. Outstanding Governance Approvals

None of these is granted by B1 (all **NOT AUTHORIZED**): adding torch, transformers, tokenizers, safetensors and huggingface-hub (and the `setuptools` change) to the approved stack in `CLAUDE.md` section 5, with an ADR; any installation into the project `.venv` or any new environment; registry change adding Horizon as `license_verified`; schema and API changes (role-keyed slots, `ModelVsRulesOut`); ONNX artifact policy, conversion or deployment; production activation or any flag change (F1/R14); production-path code changes (section 10 guards); Horizon licence scope beyond research inference (redistribution, commercial use); and the unresolved governance items A3.3 (training-data terms in general), A3.5 (share-alike, rejected), D20 (rejected), and all dataset and human-validation gates. No fine-tuning, dataset collection, annotation, accuracy or calibration claim is permitted.

## 14. Required Decisions Before B2

| ID | Decision | Why it is needed | My recommendation |
| --- | --- | --- | --- |
| D-B1 | Approve adding the five packages (and the `setuptools` jump) to the approved stack, or choose the out-of-process worker | `CLAUDE.md` section 5 forbids unapproved libraries; the dry-run shows the `setuptools` change | approve for the isolated or coexistence environment first; ADR before any application install |
| D-B2 | Approve creating a **second external environment** that replicates the application's exact frozen packages plus the Stage A stack, to import TensorFlow and PyTorch in one process, load a TensorFlow market model and Horizon together, and measure combined memory | the only way to resolve coexistence and the 7 untested shared versions without touching `.venv`; it needs installation, so it is outside B1 | yes, as the first B2 step |
| D-B3 | Choose A1 (in-process) or A2 (out-of-process worker) after D-B2 | failure isolation versus new architecture | A1 if the coexistence test is clean, else A2 |
| D-B4 | Approve the schema direction: role-keyed slots, `ModelVsRulesOut`, the single-model decision table | required for Horizon to be compared with rules at all (finding 1) | approve |
| D-B5 | Approve the production-path hardening (G3-G8) as in-scope for B2 | it touches the code path of a production endpoint | approve, with tests 16-25 first |
| D-B6 | Decide whether ONNX Runtime is to be evaluated at all | needs an artifact-policy extension and a parity check | not now |
| D-B7 | Decide whether Horizon's multilingual ability is ever to be used | requires changing the rules front end's language gate (a policy change) | no, keep English-only |
| D-B8 | Set resource policy: torch thread cap, one server worker, memory budget (about 1.1 GB for Horizon on top of about 215 MB for the application and TensorFlow's 344 MB at import) | the combined footprint is unmeasured | decide after D-B2 measurements |

## 15. B1 Verdict

**Complete.** The runtime recommendation is **A (transformers 5.17.0 + CPU torch + safetensors)**, supported by Stage A measurements and by a clean non-mutating resolver dry-run (exit 0, 16 new packages, one existing package would change: `setuptools`), and qualified by what is genuinely unknown: TensorFlow and PyTorch in one process, seven untested shared-package versions, and the `setuptools` upgrade. The investigation also found that the existing ADR-053 architecture cannot use a single approved model and has failure-isolation gaps that must be closed before any real model can be enabled; none of these requires a decision that B1 may take.

**State after B1 (VERIFIED):** production sentiment is still `user_text_rules_v1`; both transformer flags are false; the registry is unchanged and Horizon is not in it; the project `.venv` is unchanged (timestamp 2026-10-29 21:31:18; frozen list identical before and after the dry-run); no migration or schema change; no database call, test suite, installation, download or ONNX work was performed; nothing was committed or pushed. The only repository change is this report (and a one-line note in `docs/MEMORY.md`). **B2 was not started and should not start without the owner's review and the decisions in section 14.**

## Appendix. Evidence recorded in B1 (all outside the repository, in the session scratchpad `...\scratchpad\b1\`)

| Evidence | What it shows |
| --- | --- |
| `dry_run_vs_project_venv_output.txt`, `dry_run_vs_project_venv.json` | the resolver dry-run against the project `.venv`'s installed set: exit 0; "would install" 16 packages including `setuptools-84.2.1` |
| `venv_freeze_before.txt` / `venv_freeze_after.txt` | identical hashes: the project environment's frozen package list is unchanged by the dry-run |
| rules baseline timing | `analyse_user_text`: n = 1,600, median 0.073 ms, p95 0.108 ms, max 0.292 ms; no torch, transformers or onnxruntime imported |
| `mem_probe.py` | the application import reaches 215.1 MB (4.4 s); the first TensorFlow 2.17 / Keras 3.15.1 import reaches 343.9 MB (14.3 s) |
| ONNX file listing (Hugging Face API, metadata only) | `onnx/model.onnx` 563,103,014 bytes sha256 `fed14ea48666941eac7883b133d1471c93b443ec13694f6df18e9922210b066e`; `onnx/model_quantized.onnx` 268,410,774 bytes (not considered) |
| `python scripts/run_isolated_db_tests.py --preflight` | target `neondb_test` on the expected host; effective application settings agree; development-database tests deselected; "preflight only: nothing executed"; exit 0; no connection opened |
| `fault_injection.py` | the output quoted below |

```
--- faults at LOAD time
import torch fails with OSError (DLL load failed)         -> RAISED    OSError
MemoryError while building the model                      -> RAISED    MemoryError
PermissionError reading a model file (hash step)          -> RAISED    PermissionError
ImportError for the packages (the case that IS handled)   -> RETURNED  dependencies_missing
--- faults at INFERENCE time
MemoryError inside predict                                -> RETURNED  inference_failed
RuntimeError inside predict                               -> RETURNED  inference_failed
--- does a STATUS read load the model?
candidate_status(enabled, runnable) -> availability=ready loaded=True; model constructions = 1
--- does a slow load block a concurrent status read? (1.5 s stand-in load)
a status read issued 0.2 s into another candidate's load waited 1.31 s
--- timeout then the next request
first call: timeout; next call while the worker is busy: timeout after 0.31 s (limit 0.30 s)
```

## Correction (2026-11-04, found in B2.1): the `setuptools` question was already answered in the project record

Sections 1, 5 and 14 of this report describe the `setuptools` 65.5.0 -> 84.2.1 change as an **UNRESOLVED** risk ("whether anything there still relies on legacy `pkg_resources` behaviour"). It was not unresolved: `reports/sentiment_consolidated_approval_form.md` (line 247) already records that the project's `tensorboard` 2.17.1 imports `pkg_resources` (`default.py`, `data/server_ingester.py`), that `setuptools` 82 or later no longer ships it, and that **the project environment must stay below 82**; the owner had approved `setuptools==81.0.0`. The dry-run's 84.2.1 was simply the latest release; B1 should have bounded it. B2.1 installed 84.2.1 as the brief specified and then confirmed the breakage (`tensorboard.default`, `tensorboard.data.server_ingester`, `tensorboard.program` fail to import) and stopped. The corrected decision D-B1 is: use `setuptools==81.0.0` (satisfies torch's `>=77.0.3`). See `docs/sentiment/stage_b/STAGE_B2_1_RUNTIME_COEXISTENCE_REPORT.md`.
