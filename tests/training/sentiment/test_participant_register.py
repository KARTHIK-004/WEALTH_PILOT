"""Tests for `training/sentiment/participant_register.py` on SYNTHETIC registers only (see register_fixtures.py). No real person, contact detail, credential, text, model or network is involved."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from register_fixtures import AS_OF, CONSENT_SHA, SCOPE, access, edited, person, valid_register  # noqa: F401  (the directory's conftest puts this folder on sys.path)
from training.sentiment import participant_register as pr
from training.sentiment.participant_register import RegisterError, consent_wording_hash, register_problems, validate_register, verifier_hash


def refused(register, match: str, as_of: date = AS_OF) -> str:
    with pytest.raises(RegisterError, match=match) as caught:
        validate_register(register, as_of=as_of)
    return str(caught.value)


def participant(register: dict, code: str) -> dict:
    return next(p for p in register["participants"] if p["code"] == code)


# ------------------------------------------------------------------------------------------------------------------------------- valid registers
def test_a_valid_synthetic_register_is_accepted_and_summarised_by_codes_only():
    summary = validate_register(valid_register(), as_of=AS_OF)
    assert summary == {"data_status": "synthetic", "dataset_scope": SCOPE, "annotators": ["ann-a", "ann-b"], "adjudicator": "adj", "evaluator": "ev", "verifier": "ver"}


def test_a_valid_consented_register_with_consent_metadata_is_accepted():
    register = valid_register("consented")
    assert validate_register(register, as_of=AS_OF)["data_status"] == "consented"
    assert consent_wording_hash(register) == CONSENT_SHA and consent_wording_hash(valid_register()) is None


def test_a_non_production_evaluator_service_is_accepted():
    register = edited(lambda r: participant(r, "ev").update(principal_type="service"))
    assert validate_register(register, as_of=AS_OF)["evaluator"] == "ev"


def test_the_schema_constants_follow_the_owner_decisions():
    assert pr.REQUIRED_COUNTS == {"annotator": 2, "adjudicator": 1, "evaluator": 1} and pr.MIN_VERIFIERS == 1
    assert pr.ROLES == ("annotator", "adjudicator", "evaluator", "de_identification_verifier") and pr.DATA_STATUSES == ("synthetic", "consented")
    assert pr.REQUIRED_DELETION_COVERAGE == {"raw_text", "temporary_annotation_files"}


# ------------------------------------------------------------------------------------------------------------------------------- structure
@pytest.mark.parametrize("bad", [None, [], "register", 5])
def test_a_register_that_is_not_an_object_is_refused(bad):
    refused(bad, "must be a JSON object")


@pytest.mark.parametrize("version", [0, 2, "1", None, True])
def test_an_unknown_schema_version_is_refused(version):
    refused(edited(lambda r: r.update(schema_version=version)), "schema_version")


def test_a_missing_register_field_is_refused_and_counted():
    for field in ("register_id", "data_status", "dataset_scope", "consent_wording", "de_identification_verifier_code", "deletion_authorization", "participants"):
        refused(edited(lambda r, f=field: r.pop(f)), "1 required register field")


def test_an_unknown_register_field_is_refused_without_naming_it():
    message = refused(edited(lambda r: r.update(favourite_colour="blue")), "1 unknown register field")
    assert "favourite_colour" not in message and "blue" not in message


def test_participants_must_be_a_non_empty_list_of_complete_objects():
    refused(edited(lambda r: r.update(participants=[])), "participants must be a non-empty list")
    refused(edited(lambda r: r.update(participants="x")), "participants must be a non-empty list")
    refused(edited(lambda r: r["participants"].__setitem__(0, "ann-a")), "participant 1 must be an object")
    refused(edited(lambda r: participant(r, "ann-a").pop("attested_on")), "participant 1 must hold exactly the required fields")
    refused(edited(lambda r: participant(r, "ann-a").update(extra="x")), "participant 1 must hold exactly the required fields")


# ------------------------------------------------------------------------------------------------------------------------------- codes and roles
def test_duplicate_codes_are_refused_even_across_case():
    refused(edited(lambda r: participant(r, "ann-b").update(code="ann-a")), "codes must be unique")
    refused(edited(lambda r: participant(r, "ann-b").update(code="ANN-A")), "codes must be unique")


@pytest.mark.parametrize("role", ["reviewer", "Annotator", "", None, 7, "admin"])
def test_an_invalid_role_is_refused(role):
    refused(edited(lambda r: participant(r, "ann-a").update(role=role)), "participant 1 has an invalid role")


def test_the_role_counts_are_exactly_the_owner_approved_ones():
    refused(edited(lambda r: r["participants"].pop(1)), "exactly 2 annotator")
    refused(edited(lambda r: r["participants"].append(person("ann-c", "annotator", ["statement_id"]))), "exactly 2 annotator")
    refused(edited(lambda r: r["participants"].pop(2)), "exactly 1 adjudicator")
    refused(edited(lambda r: r["participants"].pop(3)), "exactly 1 evaluator")
    refused(edited(lambda r: r["participants"].append(person("ev-2", "evaluator", ["statement_id"]))), "exactly 1 evaluator")


@pytest.mark.parametrize("code", ["", "has space", "x" * 33, "ann/a", 5, None])
def test_a_malformed_code_is_refused(code):
    refused(edited(lambda r: participant(r, "ann-a").update(code=code)), "participant 1 has a malformed code")


@pytest.mark.parametrize("code", ["123456", "customer-17", "user_42", "profile9", "acct-1", "uid"])
def test_a_code_that_looks_like_a_production_user_identifier_is_refused(code):
    refused(edited(lambda r: participant(r, "ann-a").update(code=code)), "looks like a production-user identifier")


# ------------------------------------------------------------------------------------------------------------------------------- attestations
@pytest.mark.parametrize("value", [False, None, "yes", 1, "true"])
def test_missing_or_non_boolean_independence_is_refused(value):
    refused(edited(lambda r: participant(r, "ann-a").update(independence_attested=value)), "participant 1 has no independence attestation")


def test_every_role_needs_an_independence_attestation():
    for index in range(5):
        refused(edited(lambda r, i=index: r["participants"][i].update(independence_attested=False)), f"participant {index + 1} has no independence attestation")


@pytest.mark.parametrize("value", ["", "2026-13-01", "01/02/2026", None, "2026-1-1", 20260101])
def test_an_invalid_attestation_date_is_refused(value):
    refused(edited(lambda r: participant(r, "adj").update(attested_on=value)), "participant 3 has no valid attestation date")


def test_a_future_attestation_date_is_refused():
    refused(edited(lambda r: participant(r, "adj").update(attested_on="2099-01-01")), "attestation date in the future")


# ------------------------------------------------------------------------------------------------------------------------------- the de-identification verifier
def test_the_verifier_code_must_name_a_verifier():
    refused(edited(lambda r: r.update(de_identification_verifier_code="ann-a")), "must name a participant whose role is de_identification_verifier")
    refused(edited(lambda r: r.update(de_identification_verifier_code="nobody")), "must name a participant whose role is de_identification_verifier")
    refused(edited(lambda r: r.update(de_identification_verifier_code=None)), "must name a participant whose role is de_identification_verifier")


def test_at_least_one_verifier_is_required():
    refused(edited(lambda r: r["participants"].pop(4)), "at least one de_identification_verifier")


def test_a_verifier_without_a_valid_authorization_is_refused():
    refused(edited(lambda r: participant(r, "ver")["access_authorization"].update(granted=False)), "participant 5 has no granted access authorization")
    refused(edited(lambda r: participant(r, "ver")["access_authorization"].update(expires_on="2026-02-01")), "participant 5 has an expired authorization")
    refused(edited(lambda r: participant(r, "ver").update(access_authorization=None)), "participant 5 has no complete access authorization")
    message = refused(edited(lambda r: participant(r, "ver").update(access_authorization=None)), "the de-identification verifier has no valid authorization")
    assert "participant 5" in message


# ------------------------------------------------------------------------------------------------------------------------------- consent and synthetic status
def test_consented_data_without_consent_metadata_is_refused():
    refused(edited(lambda r: r.update(consent_wording=None), "consented"), "consented data needs consent_wording metadata")
    refused(edited(lambda r: r["consent_wording"].pop("version"), "consented"), "consented data needs consent_wording metadata")
    refused(edited(lambda r: r["consent_wording"].update(sha256="not-a-hash"), "consented"), "consented data needs consent_wording metadata")
    refused(edited(lambda r: r["consent_wording"].update(sha256=CONSENT_SHA.upper()), "consented"), "consented data needs consent_wording metadata")
    refused(edited(lambda r: r.update(consent_wording="consent given"), "consented"), "consented data needs consent_wording metadata")


def test_synthetic_data_needs_no_consent_but_must_not_claim_it_and_must_be_marked_synthetic():
    assert validate_register(valid_register("synthetic"), as_of=AS_OF)["data_status"] == "synthetic"
    refused(edited(lambda r: r.update(consent_wording={"version": "v1", "sha256": CONSENT_SHA})), "synthetic data must not carry consent_wording")
    for status in ("fictional", "", None, "real", "SYNTHETIC"):
        refused(edited(lambda r, s=status: r.update(data_status=s)), "data_status must be 'synthetic' or 'consented'")


# ------------------------------------------------------------------------------------------------------------------------------- access and production services
def test_a_production_service_cannot_receive_dataset_access_in_any_role():
    for index, code in enumerate(("ann-a", "ann-b", "adj", "ev", "ver")):
        refused(edited(lambda r, c=code: participant(r, c).update(principal_type="production_service")), f"participant {index + 1} is a production service")


def test_evaluator_access_cannot_be_granted_to_a_production_service():
    refused(edited(lambda r: participant(r, "ev").update(principal_type="production_service")), "production services cannot receive dataset access")


def test_only_the_evaluator_may_be_a_non_production_service():
    refused(edited(lambda r: participant(r, "adj").update(principal_type="service")), "only the evaluator may be a non-production service")
    refused(edited(lambda r: participant(r, "ann-a").update(principal_type="service")), "only the evaluator may be a non-production service")
    refused(edited(lambda r: participant(r, "ann-a").update(principal_type="robot")), "invalid principal_type")


@pytest.mark.parametrize("material", ["model_output", "rules_output", "risk_profile", "recommendations", "adjudicated_labels", "other_annotator_labels", "metrics"])
def test_an_annotator_cannot_receive_anything_beyond_the_text_its_id_and_its_own_labels(material):
    for code in ("ann-a", "ann-b"):
        refused(edited(lambda r, c=code, m=material: participant(r, c)["access_authorization"]["may_view"].append(m)), "may view material its role must not see")


@pytest.mark.parametrize("material", ["risk_profile", "recommendations"])
def test_nobody_is_ever_given_a_risk_profile_or_a_recommendation(material):
    for code in ("ann-a", "adj", "ev", "ver"):
        refused(edited(lambda r, c=code, m=material: participant(r, c)["access_authorization"]["may_view"].append(m)), "may view material its role must not see")


def test_an_unknown_kind_of_material_or_a_malformed_view_list_is_refused():
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"]["may_view"].append("raw_database")), "may view an unknown kind of material")
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(may_view="statement_text")), "malformed may_view list")
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(may_view=["statement_id", "statement_id"])), "malformed may_view list")


def test_the_evaluator_may_see_model_and_rules_output_but_the_verifier_may_not():
    assert validate_register(valid_register(), as_of=AS_OF)["evaluator"] == "ev"
    refused(edited(lambda r: participant(r, "ver")["access_authorization"]["may_view"].append("model_output")), "may view material its role must not see")


def test_access_that_is_not_granted_or_has_the_wrong_scope_is_refused():
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(granted=False)), "no granted access authorization")
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(granted="yes")), "no granted access authorization")
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(dataset_scope="another-dataset")), "scope that differs")
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].pop("may_view")), "no complete access authorization")


# ------------------------------------------------------------------------------------------------------------------------------- authorization windows
def test_an_expired_authorization_is_refused_and_the_day_of_expiry_is_still_valid():
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(expires_on="2026-10-28")), "participant 1 has an expired authorization")
    assert validate_register(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(expires_on="2026-10-29")), as_of=AS_OF)["annotators"] == ["ann-a", "ann-b"]
    refused(valid_register(), "expired authorization", as_of=date(2100, 1, 1))                                  # the same register expires with time


def test_an_authorization_that_has_not_started_or_has_an_inverted_window_is_refused():
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(starts_on="2026-10-30")), "has an authorization that has not started")
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(starts_on="2027-01-01", expires_on="2026-12-31")), "expires on or before its start")
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update(starts_on="2026-05-01", expires_on="2026-05-01")), "expires on or before its start")


@pytest.mark.parametrize("field", ["starts_on", "expires_on"])
@pytest.mark.parametrize("value", ["", "tomorrow", "2026-02-30", None, "2026/01/01"])
def test_missing_or_malformed_authorization_dates_are_refused(field, value):
    refused(edited(lambda r: participant(r, "ann-a")["access_authorization"].update({field: value})), "no valid authorization start and expiry dates")


# ------------------------------------------------------------------------------------------------------------------------------- deletion authorization
def test_the_deletion_retention_rollback_and_completion_policy_are_the_owner_decisions():
    for until in (["evaluation"], ["evaluation", "audit_verification"], ["evaluation", "audit_verification", "r14_decision", "forever"], "evaluation", [], None,
                  ["evaluation", "evaluation", "audit_verification", "r14_decision"]):
        refused(edited(lambda r, u=until: r["deletion_authorization"].update(retain_raw_text_until=u)), "may be retained only until the evaluation, the audit verification and the R14 decision")
    for kept in (["raw_text"], ["hashes", "annotations"], "hashes", None, ["hashes", "hashes"]):
        refused(edited(lambda r, k=kept: r["deletion_authorization"].update(retain_after_deletion=k)), "only approved hashes, aggregate metrics and decision records may be retained")
    for rollback in ("full_restore", "metadata_and_raw_text", "", None):
        refused(edited(lambda r, v=rollback: r["deletion_authorization"].update(rollback=v)), "never deleted raw text")
    for completion in ("optional", "recorded", "", None):
        refused(edited(lambda r, v=completion: r["deletion_authorization"].update(completion_verification=v)), "deletion completion must be verified and recorded")
    assert validate_register(edited(lambda r: r["deletion_authorization"].update(retain_after_deletion=["hashes"])), as_of=AS_OF)["evaluator"] == "ev"          # keeping fewer kinds is allowed
    assert validate_register(valid_register(), as_of=AS_OF)["evaluator"] == "ev"


def test_a_deletion_authorization_is_required_and_must_be_complete():
    refused(edited(lambda r: r.pop("deletion_authorization")), "1 required register field")
    refused(edited(lambda r: r.update(deletion_authorization=None)), "a deletion authorization is required")
    refused(edited(lambda r: r["deletion_authorization"].pop("covers")), "a deletion authorization is required")
    for who in ("nobody", "ev", "ann-a", "", None, "Project_Owner"):
        refused(edited(lambda r, w=who: r["deletion_authorization"].update(authorized_by=w)), "must be authorized by the project owner")
    for field in ("retain_raw_text_until", "retain_after_deletion", "rollback", "completion_verification"):
        refused(edited(lambda r, f=field: r["deletion_authorization"].pop(f)), "a deletion authorization is required")
    refused(edited(lambda r: r["deletion_authorization"].update(authorized_on="2099-01-01")), "dated in the future")
    refused(edited(lambda r: r["deletion_authorization"].update(authorized_on="soon")), "no valid date")
    refused(edited(lambda r: r["deletion_authorization"].update(covers=["raw_text"])), "must cover raw text and temporary annotation files")
    refused(edited(lambda r: r["deletion_authorization"].update(covers="raw_text")), "must cover raw text and temporary annotation files")
    assert validate_register(edited(lambda r: r["deletion_authorization"]["covers"].append("caches")), as_of=AS_OF)["evaluator"] == "ev"


# ------------------------------------------------------------------------------------------------------------------------------- personal data, credentials and sanitized errors
SENSITIVE = ("alice.smith@example.com", "https://example.org/alice", "+44 7700 900123", "4111 1111 1111 1111", "password=hunter2", "api_key sk-12345", "bearer abc")


@pytest.mark.parametrize("value", SENSITIVE[:4])
def test_a_personal_data_marker_in_any_string_is_refused_and_never_echoed(value):
    for place in (lambda r: r.update(register_id=value), lambda r: r.update(dataset_scope=value), lambda r: participant(r, "ann-a").update(code=value),
                  lambda r: participant(r, "ann-a").update(attested_on=value), lambda r: participant(r, "ann-a")["access_authorization"]["may_view"].append(value),
                  lambda r: r["deletion_authorization"].update(authorized_by=value), lambda r: r["deletion_authorization"]["covers"].append(value)):
        with pytest.raises(RegisterError) as caught:
            validate_register(edited(place), as_of=AS_OF)
        message = str(caught.value)
        assert "look like personal data" in message
        assert value not in message and value.split()[0] not in message


@pytest.mark.parametrize("value", SENSITIVE[4:])
def test_a_credential_in_any_string_is_refused_and_never_echoed(value):
    with pytest.raises(RegisterError) as caught:
        validate_register(edited(lambda r: participant(r, "ann-a").update(attested_on=value)), as_of=AS_OF)
    assert "look like a credential" in str(caught.value) and "hunter2" not in str(caught.value) and "sk-12345" not in str(caught.value) and "abc" not in str(caught.value)


def test_an_unexpected_field_holding_contact_details_is_refused_without_echoing_its_name_or_value():
    register = edited(lambda r: participant(r, "ann-a").update(email_address="alice.smith@example.com", full_name="Alice Smith"))
    with pytest.raises(RegisterError) as caught:
        validate_register(register, as_of=AS_OF)
    message = str(caught.value)
    assert "alice" not in message.lower() and "example.com" not in message and "email_address" not in message and "full_name" not in message and "Smith" not in message
    assert "look like personal data" in message and "participant 1 must hold exactly the required fields" in message


def test_dates_and_hashes_are_not_mistaken_for_personal_data():
    assert register_problems(valid_register("consented"), AS_OF) == []


def test_every_message_is_built_from_fixed_text_counts_and_positions():
    broken = edited(lambda r: (participant(r, "ann-a").update(independence_attested=False, code="alice@example.com"), r.update(register_id="Alice Smith 555-123-4567")))
    for problem in register_problems(broken, AS_OF):
        assert "alice" not in problem.lower() and "smith" not in problem.lower() and "555" not in problem and "example.com" not in problem


def test_register_problems_never_raises_on_hostile_input():
    for bad in (None, [], {}, {"schema_version": 1}, {**valid_register(), "participants": [None, 5, [], {}]}, {**valid_register(), "deletion_authorization": 7},
                {**valid_register(), "participants": [{"code": 1}]}):
        assert isinstance(register_problems(bad, AS_OF), list) and register_problems(bad, AS_OF)


def test_as_of_must_be_a_date():
    with pytest.raises(TypeError):
        validate_register(valid_register(), as_of="2026-10-29")                                      # type: ignore[arg-type]


# ------------------------------------------------------------------------------------------------------------------------------- hashes and isolation
def test_the_verifier_hash_is_deterministic_and_changes_with_the_verifier_entry_only():
    first = verifier_hash(valid_register())
    assert first == verifier_hash(valid_register()) and len(first) == 64
    assert verifier_hash(edited(lambda r: participant(r, "ann-a").update(attested_on="2026-02-02"))) == first                   # another participant does not change it
    assert verifier_hash(edited(lambda r: participant(r, "ver").update(attested_on="2026-02-02"))) != first
    assert verifier_hash(edited(lambda r: participant(r, "ver")["access_authorization"].update(expires_on="2098-12-31"))) != first


def test_the_module_is_offline_clockless_and_imports_nothing_that_reads_a_model_or_the_network():
    source = Path(pr.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {alias.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__", "hashlib", "json", "re", "datetime", "typing"}, imported
    assert "today(" not in source and "now(" not in source and "open(" not in source and "read_text" not in source
