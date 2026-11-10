"""Constants of the offline sentiment-model pipeline (ADR-052). Nothing here is downloaded, trained or evaluated by importing it.

The candidates are IDENTIFIERS of pretrained models, not an endorsement: no candidate is assumed best, none has been downloaded, and each one's licence must be verified from its model
card by the project owner before use (`license_to_verify`). The final model is chosen from MEASURED results on an approved dataset (`evaluate_sentiment_model.py`).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models" / "sentiment"                     # model artifacts (weights are never tracked; metadata and metrics may be)
DATA_DIR = REPO_ROOT / "datasets" / "raw" / "sentiment"            # downloaded labelled data: immutable, gitignored (datasets/raw/*)

SEED = 42                                                           # every stochastic step; GPU kernels may still be non-deterministic (documented in the README)
PREPROCESSING_VERSION = "sentiment_prep_v1"                         # NFKC is NOT applied; text goes through core.user_text_sentiment.validate_text (control characters, whitespace, 1,000 chars)
LABELS = ("positive", "negative", "neutral")                        # the classes a Transformer head has; mixed / uncertain / insufficient_evidence come from the pipeline, never from a head
LABEL_MAP = {label: index for index, label in enumerate(LABELS)}
DEFAULT_MAX_TOKENS = 128
MIN_TEXT_CHARS = 3

# name -> what it is. `hub_id` is only an identifier for a later, approved download; `license_to_verify` is deliberate: no licence is asserted here.
CANDIDATES: dict[str, dict[str, str]] = {
    "finbert": {"hub_id": "ProsusAI/finbert", "role": "pretrained financial-language Transformer (3-class sentiment head already trained on financial news)", "license_to_verify": "yes"},
    "roberta-base": {"hub_id": "FacebookAI/roberta-base", "role": "general-language comparison model (needs a new classification head)", "license_to_verify": "yes"},
    "distilroberta-base": {"hub_id": "distilbert/distilroberta-base", "role": "smaller general-language comparison model (needs a new classification head)", "license_to_verify": "yes"},
    "rules_baseline": {"hub_id": "", "role": "the current deterministic rules baseline user_text_rules_v1 (always evaluated, no download)", "license_to_verify": "no"},
}

# What it takes for an artifact to be called "validated" (checked by training, and again by the loader in core/sentiment_model.py). These are structural requirements, not accuracy targets:
# the accuracy / precision targets are owner decisions and are REQUIRED command-line arguments, never defaults.
MIN_TEST_SAMPLES_FOR_VALIDATED = 200

DOMAIN_NOTE = (
    "Public financial sentiment data is mostly NEWS or MARKET commentary written about companies. WealthPilot reads a person's OWN statements about their savings, debt, goals, liquidity "
    "and investment worries. The two differ in subject, voice and vocabulary, so a model validated on news is NOT thereby validated on this input; only a labelled set of personal-finance "
    "statements can validate it. Until one exists, the model stays unvalidated and the rules baseline is the method."
)
