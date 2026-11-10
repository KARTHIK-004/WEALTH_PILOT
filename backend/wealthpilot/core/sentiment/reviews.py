"""Candidate REVIEW records (ADR-054): what was found in each repository, and the verdict, as code constants.

`registry.py` holds the candidates the comparison can run (today FinBERT and Twitter-RoBERTa, both blocked). This module holds the review of every candidate considered, including the replacements
proposed on 2026-11-03, so a verdict is auditable and cannot be changed by configuration. A verdict other than `approved_for_research_inference` means the candidate must not be downloaded, installed for,
or run. **No candidate has that verdict.** Facts were read from the public Hugging Face API and raw files on CHECKED_ON through an intermediary summarising fetch, so every value below must be
re-read directly from the repository, at the pinned revision, before anything is approved or downloaded. Nothing here is legal advice.
"""

from __future__ import annotations

from dataclasses import dataclass

APPROVED = "approved_for_research_inference"
BLOCKED_LICENCE = "blocked_by_license"
BLOCKED_PROVENANCE = "blocked_by_provenance"
BLOCKED_APPROVAL = "blocked_by_approval"
INCOMPLETE = "incomplete_review"
VERDICTS = (APPROVED, BLOCKED_LICENCE, BLOCKED_PROVENANCE, BLOCKED_APPROVAL, INCOMPLETE)
CHECKED_ON = "2026-11-03"
OWNER_DECISION_DATE = "2026-11-04"
HORIZON_OWNER_DECISION = (
    "Recorded 2026-11-04 from the project owner's instruction. Horizon-Labs/multilingual-sentiment-small at revision e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac may be considered for RESEARCH INFERENCE ONLY, "
    "accepting its disclosed web-crawl and LLM-generated training data and the absence of human-validated labels. NOT authorised: production activation, dataset creation or collection, fine-tuning, "
    "training, automatic model downloads, redistribution, commercial use, any human-validation, accuracy or calibration claim, or any financial-decision impact. Package installation, weight download, "
    "actual inference and the registry change each still need their own approval.")
HORIZON_OWNER_DECISION_UPDATE = (
    " UPDATE 2026-11-07 (owner requests R1, R2, R3, ADR-056): the owner approved registering this model as the `general` RESEARCH candidate, placing the exact approved artifacts in the "
    "project's local, untracked model-artifact directory (never committed) and running the application-adapter smoke test. This does NOT authorise production activation, a financial-domain claim, dataset collection, "
    "training, human evaluation, or any accuracy or calibration claim.")
HORIZON_OWNER_DECISION_CURRENT = HORIZON_OWNER_DECISION + HORIZON_OWNER_DECISION_UPDATE


@dataclass(frozen=True)
class CandidateReview:
    key: str                                        # identifier of the review record (not necessarily an active registry key)
    role: str                                       # financial | general
    repository: str
    revision: str                                   # repository `sha` at CHECKED_ON
    architecture: str
    declared_licence: str
    licence_file: str                               # what licence document the repository actually contains
    base_model: str
    base_model_licence: str
    training_data: tuple[str, ...]
    native_labels: tuple[str, ...]                  # in logit (index) order, from config.json id2label
    label_mapping: tuple[tuple[str, str], ...]      # native label -> WealthPilot label
    languages: str
    safetensors_file: str | None
    safetensors_sha256: str | None                  # the Hub's recorded LFS sha256 for that file at the revision
    safetensors_size_bytes: int | None
    verdict: str
    blockers: tuple[str, ...]
    active_in_registry: bool                        # True only for a candidate that is REGISTERED in registry.py (ADR-055). Today only Horizon (general, research only) is registered; no candidate is production
    source_urls: tuple[str, ...]
    checked_on: str = CHECKED_ON
    owner_decision: str | None = None               # the owner's recorded, scoped decision for this candidate, if any


FINBERT_REVIEW = CandidateReview(
    key="finbert", role="financial", repository="ProsusAI/finbert", revision="0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031", architecture="BertForSequenceClassification",
    declared_licence="cc-by-nc-sa-4.0", licence_file="metadata field only (not re-inspected in this review)", base_model="not re-inspected", base_model_licence="not re-inspected",
    training_data=("not listed in repository metadata; training corpora not reviewed (A3.3)",), native_labels=("positive", "negative", "neutral"),
    label_mapping=(("positive", "positive"), ("negative", "negative"), ("neutral", "neutral")), languages="en", safetensors_file="model.safetensors", safetensors_sha256=None, safetensors_size_bytes=None,
    verdict=BLOCKED_LICENCE, blockers=("CC BY-NC-SA 4.0: non-commercial and share-alike; the owner rejected share-alike (A3.5)", "training-data terms unresolved (A3.3)"), active_in_registry=False,
    source_urls=("https://huggingface.co/api/models/ProsusAI/finbert",))

ROBERTA_REVIEW = CandidateReview(
    key="roberta", role="general", repository="cardiffnlp/twitter-roberta-base-sentiment-latest", revision="3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7", architecture="RobertaForSequenceClassification",
    declared_licence="cc-by-4.0", licence_file="metadata field only (not re-inspected in this review)", base_model="not re-inspected", base_model_licence="not re-inspected",
    training_data=("tweet_eval (social-media posts); platform and poster terms not reviewed",), native_labels=("negative", "neutral", "positive"),
    label_mapping=(("negative", "negative"), ("neutral", "neutral"), ("positive", "positive")), languages="en", safetensors_file=None, safetensors_sha256=None, safetensors_size_bytes=None,
    verdict=BLOCKED_PROVENANCE, blockers=("training data is tweet-derived and its platform terms are not reviewed or approved", "no model.safetensors is published at this revision (only pickle-capable checkpoints)"),
    active_in_registry=False, source_urls=("https://huggingface.co/api/models/cardiffnlp/twitter-roberta-base-sentiment-latest",))

FINANCIAL_DISTILBERT_REVIEW = CandidateReview(
    key="tooshlegacy_distilbert_financial_tweet", role="financial", repository="tooshlegacy/distilbert-financial-tweet-sentiment", revision="ba66b6a858cc775dc9e78d773c437b7e984fd5fc",
    architecture="DistilBertForSequenceClassification (66M parameters per the card; vocab 30522; 512 positions)", declared_licence="apache-2.0 (YAML metadata and model-card header)",
    licence_file="NONE: the repository contains no LICENSE or NOTICE file, and the card names no author or organisation (it links a personal GitHub project)",
    base_model="distilbert/distilbert-base-uncased (repository sha 12040accade4e8a0f71eabdb258fecc2e7e948be)", base_model_licence="apache-2.0 (declared); trained on bookcorpus and wikipedia",
    training_data=("zeroshot/twitter-financial-news-sentiment (sha ccbe24de388e287beb92dd393a335c376b350ac3): ~11,932 finance-related tweets, MIT declared; 'collected using the Twitter API'; "
                   "annotators recorded only as 'other', annotation process ABSENT; no Twitter/X terms or redistribution statement; no Financial PhraseBank and no share-alike or non-commercial wording found",),
    native_labels=("Bearish", "Bullish", "Neutral"), label_mapping=(("Bearish", "negative"), ("Bullish", "positive"), ("Neutral", "neutral")), languages="en only",
    safetensors_file="model.safetensors", safetensors_sha256="97fcaa54879f7cfd07af3cdcdb73aaa011dc89ced9b4ca479038148b957c6ac0", safetensors_size_bytes=267835644,
    verdict=BLOCKED_PROVENANCE,
    blockers=("training data is third-party tweets collected through the Twitter API; how they were annotated and whether platform terms permit this use are undocumented (the same unresolved issue that blocked the CardiffNLP candidate)",
              "no licence file in the repository and no identifiable author or organisation: the Apache-2.0 declaration is a bare metadata tag",
              "A3.3 (training-data terms) is unresolved and the owner has not approved this candidate"),
    active_in_registry=False, source_urls=("https://huggingface.co/api/models/tooshlegacy/distilbert-financial-tweet-sentiment",
                                           "https://huggingface.co/api/datasets/zeroshot/twitter-financial-news-sentiment", "https://huggingface.co/api/models/distilbert/distilbert-base-uncased"))

GENERAL_MULTILINGUAL_REVIEW = CandidateReview(
    key="horizon_multilingual_sentiment_small", role="general", repository="Horizon-Labs/multilingual-sentiment-small", revision="e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac",
    architecture="ModernBertForSequenceClassification (vocab 256000; 8192 positions; config written by transformers 5.17.0 with v5-format keys such as rope_parameters)",
    declared_licence="apache-2.0", licence_file="LICENSE (Apache License 2.0 text; no copyright line inside it) and NOTICE (names Horizon Labs and the MIT base model)",
    base_model="jhu-clsp/mmBERT-small (repository sha abc32620dd4f6ab06f5fbe905dc25f310618e09f)", base_model_licence="mit (declared); its multilingual pretraining corpora are listed but not reviewed",
    training_data=("snippets of FineWeb-2 and FineWeb (ODC-BY dataset licence; a web crawl, so rights in the underlying pages are not covered by that tag), 67 languages, about 433k training examples",
                   "synthetic reviews, posts, comments, messages and complaints written by the teacher LLM Qwen/Qwen3.8-27B (repository exists, apache-2.0 declared, sha 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0); the real/synthetic split is not stated",
                   "labels are soft labels from that LLM, zero-shot; NO human annotation (the card: 'the model inherits the teacher's judgement')"),
    native_labels=("negative", "neutral", "positive"), label_mapping=(("negative", "negative"), ("neutral", "neutral"), ("positive", "positive")),
    languages="multilingual (67 languages); WealthPilot passes only English text to a model, other languages abstain before reaching it",
    safetensors_file="model.safetensors", safetensors_sha256="f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1", safetensors_size_bytes=562584932,
    verdict=APPROVED,
    blockers=("REMAINING limits (research use only): transformers 4.57.1 is NOT compatible with this config (it ignores rope_parameters and would silently use local_rope_theta 10000 instead of 160000), "
              "so transformers >= 5 is required; 5.17.0 is installed in the project environment (B2.1) and the older ADR-052 pins (tokenizers 0.22.1, safetensors 0.6.2) are not used for this model",
              "registered as the `general` research candidate (R1, ADR-056) but NOT production: production activation (F1/R14), any financial-domain claim, and any accuracy, calibration or human-validation claim remain unauthorised",
              "inference was verified by direct loading (Stage A, B2.1); inference through the application adapter is verified only by the opt-in real-weights smoke test (R2)",
              "the card says not to use it to make decisions about individuals: acceptable only because WealthPilot uses sentiment as display-only context; its training data and LLM-made labels are accepted for research inference only"),
    active_in_registry=True, source_urls=("https://huggingface.co/api/models/Horizon-Labs/multilingual-sentiment-small", "https://huggingface.co/Horizon-Labs/multilingual-sentiment-small/raw/e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac/SHA256SUMS",
                                           "https://huggingface.co/api/models/jhu-clsp/mmBERT-small", "https://huggingface.co/api/models/Qwen/Qwen3.8-27B"),
    owner_decision=HORIZON_OWNER_DECISION_CURRENT)

REVIEWS: tuple[CandidateReview, ...] = (FINBERT_REVIEW, ROBERTA_REVIEW, FINANCIAL_DISTILBERT_REVIEW, GENERAL_MULTILINGUAL_REVIEW)
