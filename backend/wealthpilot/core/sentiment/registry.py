"""The research candidates, as CODE constants, and the role-based slots they can fill (ADR-053, ADR-054, ADR-055).

Two roles exist, `financial` and `general`. At most ONE registered candidate fills a role. The comparison, the API and the panel are written against roles, never against a model name, so a model
can be added or replaced without touching them.

A candidate may run only when ALL of these hold: its licence is `license_verified`, its weights are published as safetensors, and its `registration` is `registered`. Every one of them is a code
constant, changed only by a reviewed commit with an ADR, never by an environment variable or a metadata file. Today exactly ONE candidate is registered:
- `FINBERT` and `ROBERTA` are `historical` (blocked by licence / provenance and by format; see `reviews.py` and ADR-053/054; kept so the history stays auditable);
- `HORIZON` was approved by the owner for RESEARCH INFERENCE ONLY (ADR-054 addendum, 2026-11-04) and REGISTERED as the `general` research candidate by the owner's R1 decision (2026-11-07, ADR-056).
  Registered means "may run when the research flag is on and its verified files exist"; it does NOT mean production: the production method stays `user_text_rules_v1` and the `financial` slot stays empty.

Evidence for the first two (Hugging Face model API and card metadata, read on 2026-11-03; no weight file was downloaded then) is in `reviews.py`. Horizon's artifact was downloaded and verified in Stage A
(2026-11-04); its revision below is the one the owner approved.
"""

from __future__ import annotations

from dataclasses import dataclass

LICENCE_VERIFIED = "license_verified"
LICENCE_UNVERIFIED = "license_unverified"
LICENCE_BLOCKED = "blocked_by_licence"
FORMAT_SAFETENSORS = "safetensors_available"
FORMAT_NOT_ALLOWED = "no_safetensors_published"
REGISTERED = "registered"
PENDING = "pending_owner_approval"
HISTORICAL = "historical"
CHECKED_ON = "2026-11-03"
ROLES = ("financial", "general")
NORMALIZED_LABELS = ("positive", "negative", "neutral")


@dataclass(frozen=True)
class Candidate:
    key: str                         # also the directory name under models/sentiment_pretrained/
    role: str                        # financial | general
    display_name: str
    repository: str
    revision: str                    # the 40-character commit hash the owner approved / the review read
    weight_licence: str              # as stated by the repository (not a legal conclusion)
    licence_status: str
    licence_note: str
    format_status: str
    format_note: str
    registration: str                # registered | pending_owner_approval | historical
    registration_note: str
    source_urls: tuple[str, ...]

    @property
    def registered(self) -> bool:
        return self.registration == REGISTERED

    @property
    def runnable_in_principle(self) -> bool:
        return self.licence_status == LICENCE_VERIFIED and self.format_status == FORMAT_SAFETENSORS and self.registered

    @property
    def blocker(self) -> str | None:
        if self.licence_status != LICENCE_VERIFIED:
            return self.licence_note
        if self.format_status != FORMAT_SAFETENSORS:
            return self.format_note
        if not self.registered:
            return self.registration_note
        return None


FINBERT = Candidate(
    key="finbert", role="financial", display_name="FinBERT", repository="ProsusAI/finbert", revision="0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031",
    weight_licence="cc-by-nc-sa-4.0", licence_status=LICENCE_BLOCKED,
    licence_note="The repository declares CC BY-NC-SA 4.0 (non-commercial, share-alike). The project owner rejected the share-alike term (A3.5) and the training-data terms (A3.3) are unresolved.",
    format_status=FORMAT_SAFETENSORS, format_note="model.safetensors is published at this revision.",
    registration=HISTORICAL, registration_note="Historical candidate: blocked by licence; not registered and not eligible for registration.",
    source_urls=("https://huggingface.co/ProsusAI/finbert", "https://huggingface.co/api/models/ProsusAI/finbert"))

ROBERTA = Candidate(
    key="roberta", role="general", display_name="Twitter-RoBERTa (CardiffNLP)", repository="cardiffnlp/twitter-roberta-base-sentiment-latest", revision="3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7",
    weight_licence="cc-by-4.0", licence_status=LICENCE_UNVERIFIED,
    licence_note="The repository declares CC BY 4.0, but it was fine-tuned on tweet_eval over a social-media corpus whose own terms were not reviewed; no owner approval is recorded for this candidate.",
    format_status=FORMAT_NOT_ALLOWED,
    format_note="At this revision the repository publishes pytorch_model.bin and tf_model.h5 only. No model.safetensors exists, and the project never loads a pickle-capable checkpoint.",
    registration=HISTORICAL, registration_note="Historical candidate: blocked by provenance and by weight format; not registered and not eligible for registration.",
    source_urls=("https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest", "https://huggingface.co/api/models/cardiffnlp/twitter-roberta-base-sentiment-latest"))

HORIZON = Candidate(
    key="horizon", role="general", display_name="Horizon multilingual sentiment (small)", repository="Horizon-Labs/multilingual-sentiment-small", revision="e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac",
    weight_licence="apache-2.0", licence_status=LICENCE_VERIFIED,
    licence_note="Apache-2.0 with a standard LICENSE and a NOTICE; the owner accepted its disclosed web-crawl and LLM-generated training data and the absence of human-validated labels for RESEARCH INFERENCE ONLY (ADR-054 addendum, 2026-11-04).",
    format_status=FORMAT_SAFETENSORS, format_note="model.safetensors (562,584,932 bytes) is published at this revision; its SHA-256 was verified against the repository's SHA256SUMS in Stage A.",
    registration=REGISTERED,
    registration_note="Registered as the `general` RESEARCH candidate by the owner's R1 decision (2026-11-07, ADR-056). Research inference only: not production, not a financial-domain model, no human validation, no calibration; the research flag is off by default.",
    source_urls=("https://huggingface.co/Horizon-Labs/multilingual-sentiment-small", "https://huggingface.co/api/models/Horizon-Labs/multilingual-sentiment-small"))

CANDIDATES: tuple[Candidate, ...] = (HORIZON, FINBERT, ROBERTA)          # every candidate the project has recorded, registered or not


def by_key(key: str) -> Candidate:
    for candidate in CANDIDATES:
        if candidate.key == key:
            return candidate
    raise KeyError(key)


def registered_candidate(role: str) -> Candidate | None:
    """The one REGISTERED candidate that fills a role, or None. More than one is a configuration error and is refused."""
    found = [c for c in CANDIDATES if c.role == role and c.registered]
    if len(found) > 1:
        raise ValueError(f"more than one registered candidate for role {role}")
    return found[0] if found else None


def slot_state(role: str) -> tuple[Candidate | None, str | None]:
    """(candidate, None) when a registered candidate fills the role; otherwise (None, reason): `registration_pending` when an owner-approved candidate exists but is not registered, else
    `no_candidate_approved`."""
    candidate = registered_candidate(role)
    if candidate is not None:
        return candidate, None
    if any(c.role == role and c.registration == PENDING for c in CANDIDATES):
        return None, "registration_pending"
    return None, "no_candidate_approved"
