"""Offline schema and validator for the participant / annotation register that must exist before any dataset is created (owner decisions D4, D6, D7, D17, D18; 2026-10-29).

Nothing here reads a file, the network, a clock or a model: `validate_register` takes an already parsed object and an explicit `as_of` date, and either returns a small summary of CODES or raises
`RegisterError`. No real register exists and none is created by this module; it is exercised only by synthetic fixtures. The register is the owner's own attestation: the validator checks that it is
complete, consistent and free of personal-data markers, and it CANNOT verify that a person is independent of the rubric author or that a code is not a real name.

Register (JSON object; every field required; unknown fields are refused):
    schema_version 1; register_id; data_status "synthetic" | "consented"; dataset_scope; consent_wording {version, sha256} (consented data only, null for synthetic data);
    de_identification_verifier_code; deletion_authorization {authorized_by "project_owner", authorized_on, covers [raw_text, temporary_annotation_files, ...],
    retain_raw_text_until [evaluation, audit_verification, r14_decision], retain_after_deletion [subset of hashes, aggregate_metrics, decision_records],
    rollback "metadata_and_aggregate_records_only", completion_verification "required_and_recorded"};
    participants [{code, role, principal_type, independence_attested, attested_on,
                   access_authorization {granted, dataset_scope, starts_on, expires_on, may_view [...]}}].
Roles: annotator (exactly 2), adjudicator (exactly 1), evaluator (exactly 1), de_identification_verifier (at least 1) - the owner's D6 / D18 approvals. A principal is a `person`, or for the evaluator
only a non-production `service`; a `production_service` is refused. `may_view` is checked against the role: an annotator sees only statement ids, statement text and its own labels, never model output,
rules output, a risk profile or a recommendation; nobody is ever given a risk profile or a recommendation.

Errors never echo a value or a field name: a message lists fixed problem descriptions with counts and 1-based participant positions only, because a register that holds a personal detail must not
copy it into a log or a report."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Mapping

SCHEMA_VERSION = 1
ROLES = ("annotator", "adjudicator", "evaluator", "de_identification_verifier")
REQUIRED_COUNTS = {"annotator": 2, "adjudicator": 1, "evaluator": 1}          # D6 and D18: two annotators, one adjudicator, one evaluator
MIN_VERIFIERS = 1
DATA_STATUSES = ("synthetic", "consented")
PRINCIPAL_TYPES = ("person", "service", "production_service")
VIEWABLE = ("statement_id", "statement_text", "own_labels", "other_annotator_labels", "adjudication_inputs", "adjudicated_labels", "metrics", "model_output", "rules_output", "risk_profile",
            "recommendations")
ALLOWED_VIEW = {
    "annotator": frozenset({"statement_id", "statement_text", "own_labels"}),
    "adjudicator": frozenset({"statement_id", "statement_text", "own_labels", "other_annotator_labels", "adjudication_inputs"}),
    "evaluator": frozenset({"statement_id", "statement_text", "adjudicated_labels", "metrics", "model_output", "rules_output"}),
    "de_identification_verifier": frozenset({"statement_id", "statement_text"}),
}
REQUIRED_DELETION_COVERAGE = frozenset({"raw_text", "temporary_annotation_files"})          # D17
REGISTER_FIELDS = frozenset({"schema_version", "register_id", "data_status", "dataset_scope", "consent_wording", "de_identification_verifier_code", "deletion_authorization", "participants"})
PARTICIPANT_FIELDS = frozenset({"code", "role", "principal_type", "independence_attested", "attested_on", "access_authorization"})
ACCESS_FIELDS = frozenset({"granted", "dataset_scope", "starts_on", "expires_on", "may_view"})
DELETION_FIELDS = frozenset({"authorized_by", "authorized_on", "covers", "retain_raw_text_until", "retain_after_deletion", "rollback", "completion_verification"})
DELETION_AUTHORIZER = "project_owner"                                                                    # owner decision (2026-10-30): deletion is authorized by the project owner, not by a participant
RETENTION_EVENTS = frozenset({"evaluation", "audit_verification", "r14_decision"})                       # raw text and temporary annotation files may exist only until all three are complete
RETAINABLE_AFTER_DELETION = frozenset({"hashes", "aggregate_metrics", "decision_records"})
ROLLBACK_POLICY = "metadata_and_aggregate_records_only"                                                  # a rollback may restore these, never deleted raw text
COMPLETION_POLICY = "required_and_recorded"
CONSENT_FIELDS = frozenset({"version", "sha256"})

_CODE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_LABEL = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PERSONAL = re.compile(r"@|https?://|www\.|\d[\d\s().+-]{6,}\d", re.IGNORECASE)                  # an e-mail address, a link, a phone-number-like or long digit run
_CREDENTIAL = re.compile(r"\b(password|passwd|passphrase|secret|token|api[_-]?key|bearer|credential)s?\b", re.IGNORECASE)
_PRODUCTION_IDENTIFIER = re.compile(r"^\d+$|(?:^|[-_])(?:user|users|customer|cust|profile|account|acct|uid)[-_]?\d*(?:$|[-_])", re.IGNORECASE)


class RegisterError(ValueError):
    """The register is incomplete, inconsistent or carries a personal-data marker. The message holds fixed problem descriptions, counts and participant positions, never a value or a field name."""


def _strings(node: object):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _strings(value)


def _looks_personal(value: str) -> bool:
    """A date and a SHA-256 are the register's own digit runs and are not markers; everything else is scanned."""
    if _SHA256.match(value) or _DATE.match(value):
        return False
    return bool(_PERSONAL.search(value))


def _is_date(value: object) -> date | None:
    if not (isinstance(value, str) and _DATE.match(value)):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _label(value: object) -> bool:
    return isinstance(value, str) and bool(_LABEL.match(value))


def register_problems(register: object, as_of: date) -> list[str]:
    """Every problem found, as fixed descriptions (empty = valid). Never raises on bad input."""
    if not isinstance(register, dict):
        return ["the register must be a JSON object"]
    if register.get("schema_version") != SCHEMA_VERSION or isinstance(register.get("schema_version"), bool):
        return [f"the register must have schema_version {SCHEMA_VERSION}"]
    problems: list[str] = []
    missing = len(REGISTER_FIELDS - set(register))
    unknown = len(set(register) - REGISTER_FIELDS)
    if missing:
        problems.append(f"{missing} required register field(s) missing")
    if unknown:
        problems.append(f"{unknown} unknown register field(s)")
    if missing:
        return problems
    markers = sum(1 for s in _strings(register) if _looks_personal(s))
    credentials = sum(1 for s in _strings(register) if _CREDENTIAL.search(s))
    if markers:
        problems.append(f"{markers} register string(s) look like personal data (an e-mail address, a link or a long digit run)")
    if credentials:
        problems.append(f"{credentials} register string(s) look like a credential")

    if not _label(register["register_id"]):
        problems.append("register_id must be a short identifier")
    if not _label(register["dataset_scope"]):
        problems.append("dataset_scope must be a short identifier")
    status = register["data_status"]
    consent = register["consent_wording"]
    if status not in DATA_STATUSES:
        problems.append("data_status must be 'synthetic' or 'consented'")
    elif status == "consented":
        if not (isinstance(consent, dict) and set(consent) == CONSENT_FIELDS and _label(consent.get("version")) and isinstance(consent.get("sha256"), str) and _SHA256.match(consent["sha256"])):
            problems.append("consented data needs consent_wording metadata: a version and a 64-character lowercase hexadecimal sha256")
    elif consent is not None:
        problems.append("synthetic data must not carry consent_wording (it is marked synthetic and needs no consent)")

    participants = register["participants"]
    if not (isinstance(participants, list) and participants):
        return problems + ["participants must be a non-empty list"]
    codes: list[str] = []
    valid_window: dict[str, bool] = {}
    role_counts = {role: 0 for role in ROLES}
    for position, person in enumerate(participants, start=1):
        where = f"participant {position}"
        if not isinstance(person, dict):
            problems.append(f"{where} must be an object")
            continue
        if set(person) != PARTICIPANT_FIELDS:
            problems.append(f"{where} must hold exactly the required fields")
            continue
        code, role = person["code"], person["role"]
        if not (isinstance(code, str) and _CODE.match(code)):
            problems.append(f"{where} has a malformed code (letters, digits, hyphen, underscore; at most 32)")
        elif _PRODUCTION_IDENTIFIER.search(code):
            problems.append(f"{where} has a code that looks like a production-user identifier")
        else:
            codes.append(code.casefold())
        if role not in ROLES:
            problems.append(f"{where} has an invalid role")
        else:
            role_counts[role] += 1
        kind = person["principal_type"]
        if kind not in PRINCIPAL_TYPES:
            problems.append(f"{where} has an invalid principal_type")
        elif kind == "production_service":
            problems.append(f"{where} is a production service: production services cannot receive dataset access")
        elif kind == "service" and role != "evaluator":
            problems.append(f"{where} is a service with a role other than evaluator: only the evaluator may be a non-production service")
        if person["independence_attested"] is not True:
            problems.append(f"{where} has no independence attestation")
        attested = _is_date(person["attested_on"])
        if attested is None:
            problems.append(f"{where} has no valid attestation date (YYYY-MM-DD)")
        elif attested > as_of:
            problems.append(f"{where} has an attestation date in the future")
        access = person["access_authorization"]
        if not (isinstance(access, dict) and set(access) == ACCESS_FIELDS):
            problems.append(f"{where} has no complete access authorization")
            continue
        if access["granted"] is not True:
            problems.append(f"{where} has no granted access authorization")
        if access["dataset_scope"] != register["dataset_scope"]:
            problems.append(f"{where} has a dataset scope that differs from the register's permitted scope")
        starts, expires = _is_date(access["starts_on"]), _is_date(access["expires_on"])
        if starts is None or expires is None:
            problems.append(f"{where} has no valid authorization start and expiry dates (YYYY-MM-DD)")
        elif expires <= starts:
            problems.append(f"{where} has an authorization that expires on or before its start")
        elif expires < as_of:
            problems.append(f"{where} has an expired authorization")
        elif starts > as_of:
            problems.append(f"{where} has an authorization that has not started")
        else:
            valid_window[code if isinstance(code, str) else ""] = access["granted"] is True
        view = access["may_view"]
        if not (isinstance(view, list) and all(isinstance(v, str) for v in view) and len(set(view)) == len(view)):
            problems.append(f"{where} has a malformed may_view list")
        elif set(view) - set(VIEWABLE):
            problems.append(f"{where} may view an unknown kind of material")
        elif role in ALLOWED_VIEW and set(view) - ALLOWED_VIEW[role]:
            problems.append(f"{where} may view material its role must not see (an annotator never sees model output, rules output, a risk profile or a recommendation)")
    if len(set(codes)) != len(codes):
        problems.append("participant codes must be unique (ignoring case)")
    for role, required in REQUIRED_COUNTS.items():
        if role_counts[role] != required:
            problems.append(f"the register needs exactly {required} {role}(s)")
    if role_counts["de_identification_verifier"] < MIN_VERIFIERS:
        problems.append("the register needs at least one de_identification_verifier")

    by_code = {p["code"]: p for p in participants if isinstance(p, dict) and isinstance(p.get("code"), str)}
    verifier_code = register["de_identification_verifier_code"]
    verifier = by_code.get(verifier_code) if isinstance(verifier_code, str) else None
    if verifier is None or verifier.get("role") != "de_identification_verifier":
        problems.append("de_identification_verifier_code must name a participant whose role is de_identification_verifier")
    elif not valid_window.get(verifier_code):
        problems.append("the de-identification verifier has no valid authorization")
    deletion = register["deletion_authorization"]
    if not (isinstance(deletion, dict) and set(deletion) == DELETION_FIELDS):
        problems.append("a deletion authorization is required (authorizer, date, coverage, retention, rollback and completion policy)")
    else:
        if deletion["authorized_by"] != DELETION_AUTHORIZER:
            problems.append("the deletion must be authorized by the project owner")
        authorized = _is_date(deletion["authorized_on"])
        if authorized is None:
            problems.append("the deletion authorization has no valid date (YYYY-MM-DD)")
        elif authorized > as_of:
            problems.append("the deletion authorization is dated in the future")
        covers = deletion["covers"]
        if not (isinstance(covers, list) and all(isinstance(c, str) for c in covers)) or not REQUIRED_DELETION_COVERAGE <= set(covers):
            problems.append("the deletion authorization must cover raw text and temporary annotation files")
        until, kept = deletion["retain_raw_text_until"], deletion["retain_after_deletion"]
        if not (isinstance(until, list) and all(isinstance(e, str) for e in until) and len(set(until)) == len(until) and set(until) == RETENTION_EVENTS):
            problems.append("raw text and temporary annotation files may be retained only until the evaluation, the audit verification and the R14 decision are complete")
        if not (isinstance(kept, list) and all(isinstance(e, str) for e in kept) and len(set(kept)) == len(kept) and set(kept) <= RETAINABLE_AFTER_DELETION):
            problems.append("after deletion only approved hashes, aggregate metrics and decision records may be retained")
        if deletion["rollback"] != ROLLBACK_POLICY:
            problems.append("a rollback may restore metadata and aggregate records only, never deleted raw text")
        if deletion["completion_verification"] != COMPLETION_POLICY:
            problems.append("deletion completion must be verified and recorded")
    return problems


def validate_register(register: object, *, as_of: date) -> dict:
    """Returns {"data_status", "annotators", "adjudicator", "evaluator", "verifier", "dataset_scope"} (codes only) for a valid register; raises `RegisterError` otherwise."""
    if not isinstance(as_of, date):
        raise TypeError("as_of must be a date")
    problems = register_problems(register, as_of)
    if problems:
        raise RegisterError("the participant register is not valid: " + "; ".join(problems))
    participants = register["participants"]
    pick = lambda role: sorted(p["code"] for p in participants if p["role"] == role)  # noqa: E731
    return {"data_status": register["data_status"], "dataset_scope": register["dataset_scope"], "annotators": pick("annotator"), "adjudicator": pick("adjudicator")[0],
            "evaluator": pick("evaluator")[0], "verifier": register["de_identification_verifier_code"]}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verifier_hash(register: Mapping[str, object]) -> str:
    """SHA-256 of the canonical JSON of the de-identification verifier's register entry (which carries its attestation and authorization): what the frozen manifest records."""
    entries = [p for p in register["participants"] if p["role"] == "de_identification_verifier"]          # type: ignore[index]
    return hashlib.sha256(_canonical(sorted(entries, key=lambda p: p["code"])).encode("utf-8")).hexdigest()


def consent_wording_hash(register: Mapping[str, object]) -> str | None:
    consent = register.get("consent_wording")
    return consent["sha256"] if isinstance(consent, dict) else None
