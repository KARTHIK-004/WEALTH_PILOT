"""A SYNTHETIC participant register for the offline tests. Every code, date and scope here is invented; no person, contact detail, credential or text exists. Imported through the directory's conftest."""
from __future__ import annotations

import copy
from datetime import date

AS_OF = date(2026, 10, 29)
FAR_FUTURE = "2099-12-31"
SCOPE = "invented-fixture"
CONSENT_SHA = "c" * 64


def access(role: str, view: list[str], *, scope: str = SCOPE, starts: str = "2026-01-01", expires: str = FAR_FUTURE, granted: bool = True) -> dict:
    return {"granted": granted, "dataset_scope": scope, "starts_on": starts, "expires_on": expires, "may_view": view}


def person(code: str, role: str, view: list[str], **overrides) -> dict:
    entry = {"code": code, "role": role, "principal_type": "person", "independence_attested": True, "attested_on": "2026-01-01", "access_authorization": access(role, view)}
    entry.update(overrides)
    return entry


def valid_register(status: str = "synthetic") -> dict:
    return {
        "schema_version": 1, "register_id": "invented-register-1", "data_status": status, "dataset_scope": SCOPE,
        "consent_wording": {"version": "invented-consent-v1", "sha256": CONSENT_SHA} if status == "consented" else None,
        "de_identification_verifier_code": "ver",
        "deletion_authorization": {"authorized_by": "project_owner", "authorized_on": "2026-01-01", "covers": ["raw_text", "temporary_annotation_files"],
                                   "retain_raw_text_until": ["evaluation", "audit_verification", "r14_decision"], "retain_after_deletion": ["hashes", "aggregate_metrics", "decision_records"],
                                   "rollback": "metadata_and_aggregate_records_only", "completion_verification": "required_and_recorded"},
        "participants": [
            person("ann-a", "annotator", ["statement_id", "statement_text", "own_labels"]),
            person("ann-b", "annotator", ["statement_id", "statement_text", "own_labels"]),
            person("adj", "adjudicator", ["statement_id", "statement_text", "other_annotator_labels", "adjudication_inputs"]),
            person("ev", "evaluator", ["statement_id", "statement_text", "adjudicated_labels", "metrics", "model_output", "rules_output"]),
            person("ver", "de_identification_verifier", ["statement_id", "statement_text"]),
        ],
    }


def edited(change, status: str = "synthetic") -> dict:
    register = copy.deepcopy(valid_register(status))
    change(register)
    return register
