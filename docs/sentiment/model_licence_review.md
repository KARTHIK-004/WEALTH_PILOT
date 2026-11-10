# Model licence review — FinBERT and Twitter-RoBERTa (ADR-053)

Written for: the project owner, who decides whether either pretrained model may ever be downloaded and run. Date checked: **2026-11-03**. Nothing was downloaded; only the public Hugging Face model-API
metadata of each repository was read. This is a technical record of what the repositories state, **not legal advice and not an approval.**

## Result

| | FinBERT | Twitter-RoBERTa (CardiffNLP) |
| --- | --- | --- |
| Repository | `ProsusAI/finbert` | `cardiffnlp/twitter-roberta-base-sentiment-latest` |
| Revision read (repository `sha`) | `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` | `3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7` |
| Licence declared by the repository | `cc-by-nc-sa-4.0` | `cc-by-4.0` |
| Weight licence vs model-card licence | one `license` field was read; no separate weight / tokenizer licence is stated | one `license` field was read; no separate weight / tokenizer licence is stated |
| Non-commercial restriction | **yes** (NC) | no |
| Share-alike restriction | **yes** (SA) — the owner **rejected** share-alike (A3.5) | no |
| Attribution | required by CC BY-NC-SA 4.0 | required by CC BY 4.0 |
| Redistribution | derivatives must carry the same licence (SA); non-commercial only | allowed with attribution; the training-data terms below are separate |
| Training data named by the repository | none listed in the metadata read; the FinBERT paper's corpora (financial news, Financial PhraseBank) are **not reviewed** here — A3.3 stays unresolved | `tweet_eval` (built from social-media posts); the platform's and the posters' terms are **not reviewed** here |
| Weight file formats published at that revision | `model.safetensors`, `pytorch_model.bin`, `tf_model.h5`, `flax_model.msgpack` | `pytorch_model.bin`, `tf_model.h5` — **no `model.safetensors`** |
| **Recorded status (code: `core/sentiment/registry.py`)** | **`blocked_by_licence`** | **`license_unverified`** and **`no_safetensors_published`** |
| May run? | **No.** The owner-rejected share-alike term (A3.5) and the unresolved training-data terms (A3.3) apply. | **No.** (1) Its weights exist only as pickle-capable checkpoints, and this project never loads one. (2) No owner approval of the licence and the tweet-derived training data is recorded. |

Sources: `https://huggingface.co/api/models/ProsusAI/finbert`, `https://huggingface.co/api/models/cardiffnlp/twitter-roberta-base-sentiment-latest` (and the corresponding model pages), read 2026-11-03.
The FinBERT revision equals the one recorded in the 2026-10-27 dependency request. The revisions are what the API reported on the date above: whoever later downloads weights must re-read and
pin the revision again, because a repository can change.

## What this means

- A model card's licence tag is a statement by the repository's publisher. It does not by itself settle the terms of the data a model was trained on, and this review does not treat it as doing so.
- **FinBERT** is blocked by a decision the owner has already recorded (share-alike rejected). Only the owner can change that, and doing so requires a new ADR and a code change to the registry.
- **Twitter-RoBERTa** has a permissive declared licence, but is blocked by two independent facts: no safetensors file exists at the reviewed revision, and no approval is recorded.
  Converting its `pytorch_model.bin` would mean loading a pickle-capable file once, which this project's security rules forbid unless the owner separately accepts that risk in an isolated environment.
  A safetensors-published alternative (a different repository or a different revision) would need its own licence review.
- Both candidates are therefore reported by the application as unavailable, with these reasons, and the rules baseline `user_text_rules_v1` stays the only method in use.

## Decisions only the owner can take (recorded once; not repeated elsewhere)

1. FinBERT: accept or keep rejecting the CC BY-NC-SA 4.0 terms for this academic use, and rule on the training-data terms (A3.3).
2. Twitter-RoBERTa: approve its CC BY 4.0 licence and the `tweet_eval` provenance; choose between a safetensors-published alternative or an isolated, owner-approved one-off conversion.
3. Approve the four Python packages (`docs/sentiment/transformer_architecture.md`, "Dependencies") and a revision-pinned download.
4. Any of the above is followed by editing `registry.py` (licence_status / format_status), an ADR, and the status record — never by an environment variable.

Until then: `SENTIMENT_TRANSFORMERS_ENABLED=false`, no package installed, no weight file present.

---

# Addendum 2026-11-03 — replacement candidates reviewed (ADR-054)

The owner proposed two replacements. Facts were read on 2026-11-03 from the Hugging Face model API, `README.md`, `config.json`, `LICENSE`, `SHA256SUMS` and the Hub file tree at the pinned revisions, through an intermediary summarising fetch: **re-read them directly before approving anything.** No weight was downloaded; no package installed.

| Item | `tooshlegacy/distilbert-financial-tweet-sentiment` | `Horizon-Labs/multilingual-sentiment-small` |
| --- | --- | --- |
| Role | financial | general |
| Revision (repository sha) | `ba66b6a858cc775dc9e78d773c437b7e984fd5fc` | `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` |
| Architecture | DistilBertForSequenceClassification, 66M params, vocab 30522, 512 positions | ModernBertForSequenceClassification, vocab 256000, 8192 positions, `classifier_pooling: mean` |
| Declared licence | apache-2.0 (YAML tag and card header) | apache-2.0 |
| Licence file in the repository | **none** (no LICENSE, no NOTICE); no author or organisation named | `LICENSE` (standard Apache 2.0 text, no copyright line inside) and `NOTICE` |
| Base model | `distilbert/distilbert-base-uncased` (Apache-2.0 declared; bookcorpus + wikipedia) | `jhu-clsp/mmBERT-small` (MIT declared; multilingual pretraining corpora listed, not reviewed) |
| Training data | `zeroshot/twitter-financial-news-sentiment`: ~11,932 finance tweets, MIT declared, "collected using the Twitter API"; annotators "other", process ABSENT; no Twitter/X terms statement; no PhraseBank, no share-alike wording | FineWeb / FineWeb-2 snippets (ODC-BY, 67 languages, ~433k examples) plus synthetic text written by Qwen/Qwen3.8-27B (Apache-2.0 declared); split not stated |
| How labels were made | "pre-labeled" (method not described) | soft labels from the LLM teacher, zero-shot; **no human annotation** |
| Safetensors at that revision | `model.safetensors`, 267,835,644 bytes, sha256 `97fcaa54879f7cfd07af3cdcdb73aaa011dc89ced9b4ca479038148b957c6ac0` | `model.safetensors`, 562,584,932 bytes, sha256 `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1` (matches the repo's `SHA256SUMS`) |
| Tokenizer | `tokenizer.json` (711,494 bytes, no recorded sha256) | `tokenizer.json` sha256 `f34b44a6dc8a0eef651bfa10e8325057530152606a69d9c3b6ae02efb1558f0a` |
| Native labels (config `id2label`) | 0 Bearish, 1 Bullish, 2 Neutral -> negative, positive, neutral | 0 negative, 1 neutral, 2 positive |
| Remote code | none indicated | no `auto_map` in the config |
| Languages | English only | 67 (WealthPilot sends only English text to a model) |
| Card-stated intended use | research / education, coarse bull-bear-neutral tone of short financial tweets; NOT for trading decisions, non-English, long-form news or any high-stakes use | reviews, social posts, comments, messages, support tickets; "don't use it to make decisions about individuals"; labels inherit the teacher's judgement |
| Self-reported metrics | accuracy 0.8807, macro-F1 0.8464 on its own tweet validation split (unverified; not WealthPilot evidence; not shown in the product) | macro-F1 0.635 (tweets) / 0.695 (Amazon) / 0.822 (MTEB) as stated on the card (unverified; not shown) |
| Compatible with WealthPilot governance? | Not decidable: A3.3 (training-data terms) is unresolved and the tweet provenance is undocumented | Not decidable: A3.3 unresolved; owner decision needed on web-crawl + LLM-synthetic training data |
| **Verdict** | **`blocked_by_provenance`** | **`blocked_by_approval`** |

Why the two differ: the first has concrete documentation gaps (no licence file or author, undocumented annotation and tweet-collection terms) of the kind that already blocked the CardiffNLP candidate. The second has consistent licence documents and a verifiable file hash; what remains are owner judgements
(web-crawl and LLM-written training text, LLM-made labels, and a dependency-version choice) that this review cannot make for them. Neither is `approved_for_research_inference`, so neither was downloaded.

## Consolidated owner decisions (recorded once)

1. A3.3: rule on training-data terms for the web-crawl + LLM-synthetic data (Horizon) and the tweet-derived data (tooshlegacy, CardiffNLP); A3.5 (share-alike) stays rejected, which keeps FinBERT blocked.
2. Choose or reject each candidate; if tooshlegacy, ask its publisher for a licence file and the dataset's annotation and platform terms.
3. Dependencies: approve the packages and decide the `transformers` line (4.57.1 is unverified against Horizon's v5-format config; 5.x reportedly drops TensorFlow, which the installed TensorFlow 2.17 workflow uses).
4. Approve a revision-pinned download, then a code change to `registry.py` with an ADR, then a real-weights smoke test. Production activation (F1/R14) is separate and needs validation evidence that does not exist.

---

# Addendum 2026-11-04 — scoped owner decision (Horizon)

The owner approved `Horizon-Labs/multilingual-sentiment-small` @ `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` for **research inference only**, accepting its disclosed web-crawl and LLM-generated training data and the absence of human-validated labels. Verdict: `approved_for_research_inference`. This is not a blanket licence approval:
no redistribution, commercial use, training, fine-tuning, production activation, validation claim or financial-decision impact is authorised, and the full SHA-256 of the artifact must still be verified at any later download. `tooshlegacy/distilbert-financial-tweet-sentiment` remains `blocked_by_provenance` (the financial slot is empty).
A3.3, A3.5, D20 and F1/R14 are unchanged. Compatibility and the runtime plan: `horizon_runtime_plan.md`. The ADR-054 addendum of 2026-11-03 above (tables and "Consolidated owner decisions") is historical; where it says version 5 "reportedly drops TensorFlow", that statement is withdrawn (see the plan, section 5).
