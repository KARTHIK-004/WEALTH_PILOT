# Horizon multilingual sentiment — owner decision, compatibility findings and runtime plan (ADR-054 addendum)

Written for: the project owner, who must approve each next step separately. Date: 2026-11-04. **Nothing was installed, downloaded or run.** Every "VERIFIED" below means *read from a public source (PyPI metadata, Hugging Face raw files, GitHub source) through an intermediary summarising fetch*; nothing was executed. Re-read the cited sources directly before relying on them.

## 1. The owner decision, exactly as recorded

`Horizon-Labs/multilingual-sentiment-small` at revision `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` **may be considered for research inference only**, accepting its disclosed web-crawl and LLM-generated training data and the absence of human-validated labels (recorded 2026-11-04).

| Authorised | NOT authorised (each is a separate decision) |
| --- | --- |
| research inference on this one revision, display-only | production activation; dataset creation or collection; fine-tuning or training; automatic model downloads; redistribution; commercial use; any human-validation, accuracy or calibration claim; any financial-decision impact; package installation; weight download; running inference; changing the active registry |

Unchanged: A3.3 (general training-data terms), A3.5 (share-alike) rejected, D20 rejected, F1/R14 activation, all dataset gates. The `tooshlegacy` financial model stays `blocked_by_provenance`; **the financial slot is empty** (no financial candidate is approved; the registry's FinBERT entry stays gated off). The scoped decision is stored in code as `HORIZON_OWNER_DECISION` (`core/sentiment/reviews.py`) and shown on `GET /api/sentiment-model/status`.

## 2. Local environment (VERIFIED by `pip list` / `pip check`, read-only)

Python 3.11.9 (64-bit, Windows 11); TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9, flatbuffers 25.12.19, ml-dtypes 0.4.1, scikit-learn 1.5.2, scipy 1.14.1, pandas 2.2.3, xgboost 2.1.2, shap 0.46.0, statsmodels 0.14.4, packaging 25.0. **Not installed:** `transformers`, `tokenizers`, `safetensors`, `torch`, `onnx`, `onnxruntime`, `huggingface-hub`, `sentencepiece`. `pip check`: no broken requirements. Disk: 153 GB free on `C:`. The repository has no compatible inference runtime for this model today (the existing `TransformersBackend` needs the four absent packages).

## 3. The model and what it requires (VERIFIED from the repository)

ModernBertForSequenceClassification on the `mmBERT-small` base: vocab 256,000; 8,192 positions (trained on texts up to 512 tokens, so use `max_tokens=512`); `classifier_pooling: mean`; native labels `0 negative, 1 neutral, 2 positive` (kept as-is); float32; no `auto_map`, so no remote code. Tokenizer: `PreTrainedTokenizerFast`, `tokenizer.json` (sha256 `f34b44a6…8f0a`), `add_bos_token: true`, `cls=<bos>`, `sep=<eos>`, `pad=<pad>`, `model_input_names: [input_ids, attention_mask]`. The `config.json` was written by **transformers 5.17.0** and stores positional-encoding settings in the v5 format: `rope_parameters` per layer type (both `rope_theta: 160000`) and a `layer_types` list.

## 4. Is transformers 4.57.1 compatible? — **No (treat as incompatible)**

- The v4.57.1 `ModernBertConfig` source has **no** `rope_parameters` and **no** `layer_types`; its constructor takes `global_rope_theta=160000.0` and `local_rope_theta=10000.0`. This model's config contains neither legacy key, so a 4.57.1 load would not see its `rope_parameters` and would fall back to `local_rope_theta=10000` for the sliding-attention layers (two of every three layers), where the model was built with 160000.
- The base model's own v4-era config sets `local_rope_theta: 160000` explicitly, which confirms that 160000 is the intended value.
- The likely failure is **silent**: the model loads and returns numbers, but wrong ones. That is exactly the kind of error that would not be noticed and would go on to be shown to a user. (Whether the base class stores or rejects the unknown keys was not visible in the source read; either way the setting is not applied.)
- Patching the approved `config.json` with legacy keys would modify an approved artifact and is not authorised.
- Therefore the ADR-052 pins (`transformers==4.57.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`) are **superseded for this model**: `transformers` 5.17.0 requires `tokenizers>=0.23.1,<0.24` and `safetensors>=0.8.0`.

## 5. Is transformers 5.x required? — **Yes, and 5.17.0 specifically**

5.17.0 is the version that wrote the config; its source reads `rope_parameters` and `layer_types` and converts legacy `global_rope_theta` / `local_rope_theta`. Its declared requirements (PyPI metadata): `huggingface-hub>=1.5.0,<2.0`, `numpy>=1.17`, `packaging>=20`, `pyyaml>=5.1`, `regex>=2025.10.22`, `tokenizers>=0.23.1,<0.24`, `typer`, `safetensors>=0.8.0`, `tqdm>=4.60`; `torch>=2.5` only as an extra; Python `>=3.10`. A newer 5.22.1 exists (Python `>=3.11`) but was not checked against this model. **Correction of the earlier note:** it was said that version 5 "reportedly drops TensorFlow". 5.17.0 declares no TensorFlow or Flax dependency, and the v5.0.0 release notes read (the page was truncated) say only that a TensorFlow utility directory was removed. The existing TensorFlow 2.17 workflow uses Keras directly, not `transformers`, so it is not expected to be affected; **a resolver dry-run has not been done and is part of the next stage.**

## 6. Is ONNX Runtime viable? — **Plausible, not verifiable yet, and needs a policy decision**

- For: the repository ships `onnx/model.onnx` and `onnx/model_quantized.onnx`; `onnxruntime` 1.31.1 requires Python `>=3.11`, `numpy>=1.21.6`, `protobuf>=4.25.8`, `flatbuffers`, `packaging` (all already satisfied: numpy 1.26.4, protobuf 4.25.9 which TensorFlow 2.17 also accepts, flatbuffers 25.12.19) and has a `cp311 win_amd64` wheel of 14,885,761 bytes. It would avoid `torch`, `transformers` and `safetensors`. Tokenisation could use the `tokenizers` library on `tokenizer.json` (0.23.3 itself depends on `huggingface-hub`).
- Against / unknown: the ONNX input and output names, opset and whether the output is logits or already probabilities (a double softmax would corrupt the scores) cannot be known without reading the file; token-id parity between `tokenizers` and the transformers tokenizer (special-token wrapping) is unverified; `model_quantized.onnx` agrees with fp32 on only 99.3% of the author's 430 texts, so only the fp32 file could be used; and **the project's rule is safetensors only**: ONNX is not pickle-capable but is a different artifact format than the one the owner approved, so using it needs an explicit owner extension of the artifact policy.

## 7. Recommended approach

1. **Stage A (next approval): an isolated, throw-away virtual environment outside the project's `.venv`** with the reference stack (`transformers` 5.17.0 + `torch` CPU + `safetensors`). Download the pinned files to a folder outside the repository, verify every SHA-256 against `SHA256SUMS`, and run a standalone smoke script on fictional sentences to confirm the load, the label order, sane logits and tokenizer behaviour. This neither touches TensorFlow 2.17 nor changes the application. Only this can earn INFERENCE_VERIFIED, and only for the reference implementation.
2. **Stage B (separate approval): choose the in-application runtime**: install the verified, hash-pinned set into the main environment only after a resolver dry-run shows no change to the TensorFlow stack, or evaluate ONNX Runtime against Stage A's outputs (needs the artifact-policy extension). Then the registry change with an ADR (the key generalisation described in ADR-054), `scripts/write_pretrained_manifest.py`, and the real-weights smoke test inside the app.
3. Keep `SENTIMENT_TRANSFORMERS_ENABLED=false`, `user_text_rules_v1` as production, and F1/R14 untouched throughout.

Engineering notes for Stage B (no code written): reuse `TransformersBackend`, `write_pretrained_manifest.py`, the comparison and the panel unchanged; set `SENTIMENT_TRANSFORMERS_MAX_TOKENS=512`; the first request pays the model-load time (about 0.56 GB of weights) outside the inference timeout, so an explicit operator warm-up is advisable; WealthPilot sends only English text to a model, so the multilingual ability is unused; the financial slot stays unavailable.

## 8. Packages proposed for Stage A (not installed; not approved)

| Package | Proposed pin | Basis |
| --- | --- | --- |
| `transformers` | `==5.17.0` | VERIFIED: wrote the config; requirements read |
| `tokenizers` | `==0.23.3` | VERIFIED latest read; satisfies `>=0.23.1,<0.24` |
| `safetensors` | `==0.8.0` | VERIFIED latest read; satisfies `>=0.8.0`; no base dependencies |
| `huggingface-hub` | `>=1.5.0,<2.0` (exact version resolved, then frozen) | the latest release read (2.4.0) is outside the bound, so the exact 1.x version could not be named from this read |
| `torch` (CPU) | `>=2.5` from `https://download.pytorch.org/whl/cpu` (exact version resolved, then frozen) | the index listing read was truncated at 2.1.2, so a qualifying cp311 Windows wheel could not be confirmed; PyPI lists 2.15.0 (Python `>=3.11`) |
| transitive | `regex>=2025.10.22`, `pyyaml`, `typer`, `tqdm`, `packaging`, `numpy` (already present), and torch's `filelock`, `typing-extensions>=4.13`, `setuptools>=77.0.3`, `sympy>=1.13.3`, `networkx`, `jinja2`, `fsspec` | from the metadata read |

Stage A would produce a hash-pinned lock file from the first successful install. Footprint (ESTIMATE, unmeasured): weights 562,584,932 bytes (VERIFIED size) so about 0.6 GB RAM for the weights, roughly 1 to 1.5 GB resident with torch; the torch CPU install about 1 to 2 GB on disk. Alternative for Stage B: `onnxruntime==1.31.1` and `tokenizers==0.23.3`.

## 9. Download command proposed for the next approval (NOT RUN)

```powershell
# in the isolated Stage A environment, outside the repository; telemetry off; only the files inference needs (no onnx/, code/, eval/, training/)
$env:HF_HUB_DISABLE_TELEMETRY = "1"
hf download Horizon-Labs/multilingual-sentiment-small model.safetensors config.json tokenizer.json tokenizer_config.json special_tokens_map.json SHA256SUMS LICENSE NOTICE `
  --revision e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac --local-dir "$env:USERPROFILE\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small"
```

(`hf` is the command-line tool of `huggingface-hub` 1.x; confirm with `hf --help`.) Then verify with Python `hashlib` against the recorded values: `model.safetensors` `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1`, `tokenizer.json` `f34b44a6dc8a0eef651bfa10e8325057530152606a69d9c3b6ae02efb1558f0a`, `config.json` `516d8046cca3238145113bbe8b5e2b5b34b2f0c04b0ca093d7761c5f0a504eb9`, `tokenizer_config.json` `ea349495764b24570b4560fe2e4a557e5c0a47e6bce782c2409b1d6445cf8633`, `special_tokens_map.json` `baec30ea10906f16adb8c18af7a34023002c1746542612b8b41c9f09e1351351`; the full `model.safetensors` hash must also equal the Hub's recorded value. Any mismatch stops the process. Only after Stage B is the verified directory copied to `models/sentiment_pretrained/<key>/` and given a manifest.

## 10. Remaining gates for Horizon (all open)

Package installation approval; weight download approval; the `transformers` line (5.17.0 recommended); the in-app runtime choice (reference stack or ONNX with an artifact-policy extension); the registry change with an ADR; a real-weights smoke test; and, separately and later, any production activation, which this decision does not authorise.
