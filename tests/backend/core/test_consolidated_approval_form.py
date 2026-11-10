"""Guards for `reports/sentiment_consolidated_approval_form.md` (answered in part on 2026-10-29): the single form that holds every hard decision for the real-checkpoint plan.

They protect the recorded state: every entry is exactly one of APPROVE / REJECT / KEEP UNRESOLVED / BLOCKED, only decisions the owner actually gave are recorded, nothing is inferred from a recommendation,
and the dependency rules hold. The Phase 2 rule is the owner's Option 2 (2026-10-29): A3.1 to A3.8 are PROVISIONAL until Phase 2 verifies them; Phase 2 unlocks only with exactly one candidate selected,
its identifier recorded (B2), A3.9 to A3.13 approved and B1 to B10 approved; no provisional item authorises a download, tokenizer or config access, dataset access, training or inference, so Phase 4 needs
A3.1 to A3.13 confirmed. The dependency logic below is exercised on the real form and on invented answer sets. When the owner answers more, the answering change must update the "current state" tests."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FORM = (ROOT / "reports" / "sentiment_consolidated_approval_form.md").read_text(encoding="utf-8")
A3_ALL = [f"A3.{n}" for n in range(1, 14)]
A3_PROVISIONAL = A3_ALL[:8]
A3_REQUIRED_FOR_PHASE_2 = A3_ALL[8:]
OWNER_STATED_A3 = ["A3.1", "A3.4", "A3.6", "A3.7", "A3.8"]                      # approved by the owner statement of 2026-10-29
STILL_PROVISIONAL_A3 = ["A3.3"]                                                    # A3.2 was accepted by the owner decision of the fourth brief
OWNER_APPROVED_D_SECOND_BRIEF = ["D6", "D7", "D9", "D15"]                          # approved by the owner reply of 2026-10-29 (second brief)
OWNER_APPROVED_D_THIRD_BRIEF = ["D4", "D8"]                                        # approved by the owner reply of 2026-10-29 (third brief)
OWNER_REJECTED_D = ["D20"]                                                          # rejected by the owner at the phase closure of 2026-10-30
OWNER_APPROVED_D_FOURTH_BRIEF = ["D3", "D10", "D11", "D12", "D13", "D17", "D18"]       # approved by the owner decisions of 2026-10-29 (fourth brief)
OWNER_APPROVED_D = OWNER_APPROVED_D_SECOND_BRIEF + OWNER_APPROVED_D_THIRD_BRIEF + OWNER_APPROVED_D_FOURTH_BRIEF
UNRESOLVED_D = [f"D{n}" for n in range(1, 21) if f"D{n}" not in OWNER_APPROVED_D and f"D{n}" not in OWNER_REJECTED_D]
B_ALL = [f"B{n}" for n in range(1, 11)]
EXPECTED = ["A1", "A2"] + A3_ALL + B_ALL + [f"C{n}" for n in range(1, 6)] + [f"D{n}" for n in range(1, 21)] + [f"E{n}" for n in range(1, 6)] + ["F1"]
STATUSES = ("APPROVE", "REJECT", "KEEP UNRESOLVED", "BLOCKED")


def rows() -> list[tuple[str, list[str]]]:
    out = []
    for line in FORM.splitlines():
        match = re.match(r"\| ([A-F]\d+(?:\.\d+)?) \|", line)
        if match:
            out.append((match.group(1), [cell.strip() for cell in line.strip().strip("|").split("|")]))
    return out


def status_of(entry: str) -> str | None:
    return next((s for s in STATUSES if entry == s or entry.startswith(s + " ") or entry.startswith(s + " (")), None)


def answers() -> dict[str, str]:
    return {identifier: status_of(cells[-1]) for identifier, cells in rows()}


def answers_before_remediation() -> dict[str, str]:
    """The recorded answers as they stood before TASK-CERT-1 was completed (C4 BLOCKED): the historical tests below describe that state."""
    return {**answers(), "C4": "BLOCKED", "A3.2": "KEEP UNRESOLVED"}


def answers_before_closure() -> dict[str, str]:
    """The recorded answers as they stood before the phase closure of 2026-10-30 (D20 was still KEEP UNRESOLVED): the earlier state-recording tests describe that state."""
    return {**answers(), "D20": "KEEP UNRESOLVED"}


def entries() -> dict[str, str]:
    return {identifier: cells[-1] for identifier, cells in rows()}


# ---------------------------------------------------------------------------------------------- the dependency rules (pure logic over a status mapping)
def ok(a: dict[str, str], *ids: str) -> bool:
    return all(a.get(i) == "APPROVE" for i in ids)


def one_candidate(a: dict[str, str]) -> bool:
    return (a.get("A1") == "APPROVE") != (a.get("A2") == "APPROVE")             # exactly one, never both, never none


def phases(a: dict[str, str]) -> dict[int, bool]:
    p2 = one_candidate(a) and ok(a, *A3_REQUIRED_FOR_PHASE_2, *B_ALL)            # B2 (the identifier) is one of B_ALL; A3.1 to A3.8 are provisional and NOT required here
    confirmed = one_candidate(a) and ok(a, *A3_ALL)                              # a provisional item must be confirmed (approved) before anything is downloaded
    p3 = ok(a, "C3", "C4")
    p4 = p2 and confirmed and p3 and ok(a, "C1", "C2", "C5", "E1")
    p5 = ok(a, *[f"D{n}" for n in range(1, 21)], "E3")
    p6 = p3 and p4 and p5
    p7 = p6 and ok(a, "F1")
    return {2: p2, 3: p3, 4: p4, 5: p5, 6: p6, 7: p7}


def validated_reachable(a: dict[str, str]) -> bool:
    return phases(a)[6] and ok(a, "E2")


def everything_but(*skip: str, **override: str) -> dict[str, str]:
    a = {identifier: "APPROVE" for identifier in EXPECTED}
    a["A2"] = "REJECT"                                                           # one candidate selected (A1), the other rejected
    a["F1"] = "KEEP UNRESOLVED"
    for identifier in skip:
        a[identifier] = "KEEP UNRESOLVED"
    a.update(override)
    return a


# ---------------------------------------------------------------------------------------------- the form as recorded
def test_every_decision_of_the_brief_has_its_id_exactly_once_and_in_order():
    assert [i for i, _ in rows()] == EXPECTED and len(EXPECTED) == 56


def test_every_entry_is_exactly_one_of_the_four_statuses():
    for identifier, cells in rows():
        assert status_of(cells[-1]) in STATUSES, f"{identifier}: {cells[-1]!r}"


def test_only_the_decisions_the_owner_gave_are_recorded_and_everything_else_is_unresolved_or_blocked():
    a = answers()
    assert {i for i, s in a.items() if s == "APPROVE"} == {"A1", "E1", "E2", "E5", *B_ALL, *A3_REQUIRED_FOR_PHASE_2, *OWNER_STATED_A3, "A3.2", "C1", "C2", "C3", "C4", "C5", "E4", *OWNER_APPROVED_D}
    assert {i for i, s in a.items() if s == "BLOCKED"} == set()                                 # D13 (TASK-CERT-1) was BLOCKED until the task was completed and verified on 2026-10-29
    assert {i for i, s in a.items() if s == "REJECT"} == {"A3.5", *OWNER_REJECTED_D}                               # share-alike rejected until the legal scope is verified
    assert sum(1 for s in a.values() if s == "KEEP UNRESOLVED") == 10
    assert a["F1"] == "KEEP UNRESOLVED" and "R14 is not decided and not requested" in entries()["F1"]
    for identifier in ["A2", *STILL_PROVISIONAL_A3, "D1", "E3"]:
        assert a[identifier] == "KEEP UNRESOLVED", identifier
    assert "ProsusAI/finbert" in entries()["A1"] and "ProsusAI/finbert" in entries()["B2"] and a["A2"] == "KEEP UNRESOLVED"          # the owner's single selection


def test_the_approved_entries_carry_the_exact_values_the_owner_gave():
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    for phrase in ("verified download / fetch step", "a file allow-list", "per-file SHA-256 verification", "host and redirect checks", "an explicit destination", "rollback", "Covers the fetch step only",
                   "the metadata-query tool (B9)", "never executed against a real host"):
        assert phrase in e["E1"], phrase
    assert "labels-only predictions remain descriptive-only and can never produce `validated`" in e["E2"]
    assert "metadata-only query" in e["B1"] and "one explicitly selected model identifier only" in e["B1"] and "Nothing can run until a candidate is selected" in e["B1"]
    for phrase in ("API metadata", "model-card text", "licence metadata", "repository file listing", "immutable revision metadata", "redirect metadata if exposed",
                   "Do not request or download weights, tokenizer files, `config.json`, datasets, training artifacts or generated model files"):
        assert phrase in e["B3"], phrase
    assert "maximum of **10 requests**" in e["B4"] and "stop before an eleventh" in e["B4"]
    assert "`huggingface.co` only" in e["B5"] and "official Hugging Face metadata endpoint" in e["B5"] and "unnamed redirect target is treated as an unapproved host" in e["B5"]
    assert "do not follow a redirect to a weight or file-download host" in e["B6"]
    assert "anonymous, read-only API access" in e["B7"] and "stop if the API requires authentication" in e["B7"]
    assert "only sanitized metadata in the approval report" in e["B8"] and "no tokens, cookies, raw personal data or model files" in e["B8"]
    assert "anonymous read-only API access" in e["B9"] and "built offline" in e["B9"] and "E1 covers the fetch step only" in e["B9"]
    for phrase in ("the model identifier differs", "the revision differs from the proposed value", "the licence or data terms conflict with the provisional record", "an unapproved host appears",
                   "the request would access a file", "the API requires authentication", "the request count would exceed 10"):
        assert phrase in e["B10"], phrase
    assert e["B2"].startswith("APPROVE (2026-10-29)") and "`ProsusAI/finbert`" in e["B2"] and "Only this identifier may be queried" in e["B2"]
    assert "README / model-card text is covered by B3 as sanitized metadata text only" in e["B3"] and "no endpoint is named beyond it" in e["B5"]
    assert e["E5"].startswith("APPROVE (2026-10-29)") and "maximum of **10 anonymous requests**" in e["E5"] and "Authorises the Phase 2 query of `ProsusAI/finbert` only" in e["E5"]


def test_a3_1_to_a3_8_are_recorded_as_provisional_and_a3_9_to_a3_13_are_plainly_unresolved():
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    for identifier in STILL_PROVISIONAL_A3:
        assert e[identifier].startswith("KEEP UNRESOLVED (PROVISIONAL") and "authorises no download, tokenizer access, config access, dataset access, training or inference" in e[identifier], identifier
        assert "must be confirmed before Phase 4" in e[identifier], identifier
    for identifier in OWNER_STATED_A3:
        assert e[identifier].startswith("APPROVE (2026-10-29, owner statement)"), identifier
    assert "not legal clearance" in e["A3.1"] and "non-commercial offline evaluation only" in e["A3.4"] and "0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031" in e["A3.7"] and "it authorises no download" in e["A3.8"]
    for identifier in A3_REQUIRED_FOR_PHASE_2:
        assert e[identifier].startswith("APPROVE (2026-10-29)"), identifier
    assert "`huggingface.co` only" in e["A3.9"] and "ProsusAI-finbert" in e["A3.10"] and "OFFLINE_EVALUATION_ONLY" in e["A3.13"] and "no training and no production activation" in e["A3.13"]
    assert "offline research candidate only, NOT validation" in e["A3.6"] and "not validated for personal-finance narratives" in e["A3.6"]
    assert e["A3.5"].startswith("REJECT (2026-10-29, owner statement)") and "A3.5b, share-alike, is REJECTED until the legal scope is verified" in e["A3.5"]                                      # the owner's reply, recorded by meaning


def test_only_phases_2_and_3_are_unlocked_by_the_recorded_answers():
    assert phases(answers()) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False}                    # C4 completed: Phase 3 has no open gate; the download (Phase 4) is still locked
    assert validated_reachable(answers()) is False
    assert "Totals over the 56 IDs: **44 APPROVE** (A1, A3.1, A3.2, A3.4, A3.6 to A3.13, B1 to B10, C1 to C5, D3, D4, D6 to D13, D15, D17, D18, E1, E2, E4, E5), **2 REJECT** (A3.5, D20), **0 BLOCKED**, **10 KEEP UNRESOLVED** (A2, A3.3 [provisional], D1, D2, D5, D14, D16, D19, E3, F1)" in " ".join(FORM.split())
    assert "**Approved capabilities that are not phases:**" in FORM


# ---------------------------------------------------------------------------------------------- the Phase 2 gate (Option 2), on invented answer sets
def phase_2_ready() -> dict[str, str]:
    """Exactly what unlocks Phase 2 and nothing else: one candidate, its identifier, A3.9 to A3.13, B1 to B10. A3.1 to A3.8, C, D, E and F are unresolved."""
    a = {identifier: "KEEP UNRESOLVED" for identifier in EXPECTED}
    a.update({i: "APPROVE" for i in ["A1", *A3_REQUIRED_FOR_PHASE_2, *B_ALL]})
    a["A2"] = "REJECT"
    return a


def test_phase_2_unlocks_with_exactly_the_four_required_things_and_nothing_downstream():
    assert phases(phase_2_ready()) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}


@pytest.mark.parametrize("status", ["KEEP UNRESOLVED", "REJECT", "BLOCKED"])
def test_a3_1_to_a3_8_are_not_required_to_unlock_phase_2_but_every_one_of_them_is_required_before_a_download(status):
    base = phase_2_ready()
    for identifier in A3_PROVISIONAL:
        assert phases({**base, identifier: status})[2] is True, identifier                                   # provisional: not required for Phase 2
        full = everything_but(**{identifier: status})
        assert phases(full)[2] is True and phases(full)[4] is False and phases(full)[6] is False, (identifier, status)    # but never confirmed, so no download


@pytest.mark.parametrize("status", ["KEEP UNRESOLVED", "REJECT", "BLOCKED"])
def test_a_candidate_with_any_unresolved_a3_9_to_a3_13_item_does_not_unlock_phase_2(status):
    for identifier in A3_REQUIRED_FOR_PHASE_2:
        assert phases({**phase_2_ready(), identifier: status})[2] is False, (identifier, status)
        assert phases({**everything_but(), identifier: status})[4] is False


def test_exactly_one_candidate_must_be_selected():
    base = phase_2_ready()
    assert phases({**base, "A1": "KEEP UNRESOLVED", "A2": "KEEP UNRESOLVED"})[2] is False                    # none
    assert phases({**base, "A1": "APPROVE", "A2": "APPROVE"})[2] is False                                    # both
    assert phases({**base, "A1": "REJECT", "A2": "REJECT"})[2] is False                                      # none approved
    assert phases({**base, "A1": "REJECT", "A2": "APPROVE"})[2] is True and phases({**base, "A1": "APPROVE", "A2": "KEEP UNRESOLVED"})[2] is True


@pytest.mark.parametrize("status", ["KEEP UNRESOLVED", "REJECT", "BLOCKED"])
def test_b1_to_b10_must_all_be_approved_and_b2_the_identifier_is_one_of_them(status):
    for identifier in B_ALL:
        assert phases({**phase_2_ready(), identifier: status})[2] is False, (identifier, status)
    assert phases({**phase_2_ready(), "B1": "REJECT"})[2] is False                                           # B1 rejected: B2 to B10 cannot rescue it


def test_the_other_gates_neither_unlock_nor_block_phase_2_and_stay_as_recorded():
    base = phase_2_ready()
    for identifier in [f"C{n}" for n in range(1, 6)] + [f"D{n}" for n in range(1, 21)] + ["E1", "E2", "E3", "E4", "E5", "F1"]:
        for status in ("KEEP UNRESOLVED", "APPROVE", "REJECT", "BLOCKED"):
            assert phases({**base, identifier: status})[2] is True, (identifier, status)                     # Phase 2 does not depend on them
    a = answers()
    for identifier in UNRESOLVED_D + ["E3", "F1"]:
        assert a[identifier] == "KEEP UNRESOLVED", identifier                                                # and they remain locked in the recorded form
    assert all(a[i] == "APPROVE" for i in OWNER_APPROVED_D)
    assert a["C4"] == "APPROVE" and {a[i] for i in ("C1", "C2", "C3", "C5")} == {"APPROVE"}


def test_e1_is_fetch_only_and_does_not_authorise_the_metadata_query_or_any_file_access():
    base = phase_2_ready()
    assert phases({**base, "E1": "APPROVE"}) == phases({**base, "E1": "KEEP UNRESOLVED"})                    # E1 changes nothing about Phase 2
    e1 = " ".join(entries()["E1"].split())
    assert "Covers the fetch step only" in e1 and "the metadata-query tool (B9)" in e1


def test_metadata_authorisation_authorises_no_file_access_or_download():
    a = phase_2_ready()
    assert phases(a)[2] is True
    assert phases({**a, "E1": "APPROVE"})[4] is False
    assert phases({**a, "C1": "APPROVE", "C2": "APPROVE", "C3": "APPROVE", "C4": "APPROVE", "C5": "APPROVE", "E1": "APPROVE"})[4] is False       # no confirmed A3.1 to A3.8
    assert phases(everything_but())[4] is True and phases(everything_but("E1"))[4] is False                  # a download needs every confirmation AND E1
    flat = " ".join(FORM.split())
    assert "A metadata query authorises **no** file, tokenizer, weight or dataset access" in flat and "E1 stays fetch-only" in flat


def test_a_rejected_or_blocked_item_never_unlocks_a_later_phase():
    for identifier in EXPECTED:
        for status in ("REJECT", "BLOCKED"):
            assert phases(everything_but(**{identifier: status}))[7] is False
    for identifier in A3_ALL + B_ALL:
        for status in ("REJECT", "BLOCKED"):
            a = everything_but(**{identifier: status})
            assert phases(a)[4] is False and phases(a)[6] is False, (identifier, status)


PREREQUISITES_OF_EVALUATION = A3_ALL + B_ALL + [f"C{n}" for n in range(1, 6)] + [f"D{n}" for n in range(1, 21)] + ["E1", "E3"]


def test_no_download_without_a_candidate_its_confirmed_items_the_metadata_d10_to_d13_the_cache_and_e1():
    for identifier in PREREQUISITES_OF_EVALUATION:
        for status in ("KEEP UNRESOLVED", "REJECT", "BLOCKED"):
            a = everything_but(**{identifier: status})
            if identifier not in [f"D{n}" for n in range(1, 21)] + ["E3"]:
                assert phases(a)[4] is False, (identifier, status)
            assert phases(a)[6] is False, (identifier, status)
    assert phases(everything_but(A1="REJECT"))[4] is False                                                    # both A1 and A2 rejected: no candidate
    assert phases(everything_but(A1="KEEP UNRESOLVED", A2="APPROVE"))[4] is True


@pytest.mark.parametrize("missing", [f"D{n}" for n in range(1, 21)] + ["E3"])
def test_no_evaluation_without_r8_to_r13_and_a_real_frozen_manifest(missing):
    a = everything_but(missing)
    assert phases(a)[5] is False and phases(a)[6] is False and phases(a)[7] is False


def test_validated_is_unreachable_without_probability_bearing_predictions_and_without_every_phase():
    assert validated_reachable(everything_but()) is True
    assert validated_reachable(everything_but("E2")) is False
    assert validated_reachable(everything_but("D4")) is False


def test_activation_needs_its_own_approval_even_when_everything_else_is_approved():
    a = everything_but()
    assert a["F1"] != "APPROVE" and phases(a)[7] is False
    assert phases({**a, "F1": "REJECT"})[7] is False and phases({**a, "F1": "BLOCKED"})[7] is False and phases({**a, "F1": "APPROVE"})[7] is True


# ---------------------------------------------------------------------------------------------- the text of the form
def test_the_form_states_the_option_2_rule_and_what_the_approval_left_open():
    flat = " ".join(FORM.split())
    for phrase in ("A3.1 to A3.8 are **PROVISIONAL** for the selected candidate until Phase 2 metadata verification",
                   "No provisional item authorises a download, tokenizer access, config access, dataset access, training or inference",
                   "A3.9 to A3.13 (permitted hosts, destination directory, SHA-256 policy, cleanup and rollback, evaluation-only versus training) must be explicitly approved **before** Phase 2 can unlock",
                   "exactly one candidate is selected (one of A1 / A2 approved, not both); its identifier is recorded in B2; A3.9 to A3.13 are approved; B1 to B10 are approved",
                   "C1 to C5, D1 to D20, E3, E4 and F1 remain locked", "**E1 stays fetch-only and does not authorise the query's file access.**",
                   "keep the candidate unresolved if any metadata is missing or conflicting", "A rejected or unconfirmed item keeps Phase 4 locked",
                   "an unnamed endpoint stops the query unless you name it", "nothing to compare", "the query tool (B9) must be built before Phase 2 can run"):
        assert phrase in flat, phrase
    assert "Dependency question" not in FORM and "I have not made that change" not in FORM


def test_the_owner_constraint_on_the_query_is_recorded_and_the_b3_candidate_excludes_config_files_and_everything_downloadable():
    flat = " ".join(FORM.split())
    assert "the query is **read-only** and downloads **none** of: weights, tokenizer files, model configuration files, datasets, training artifacts" in flat
    assert "If B1 is rejected or unresolved, B2 to B10 stay unresolved and Phase 2 stays locked" in flat
    b3 = dict(rows())["B3"][2]
    assert "NOT config files, weights, tokenizer files, datasets or training artifacts" in b3 and "API metadata" in b3 and "file listing" in b3
    assert "config," not in b3.split("NOT config files")[0]


def test_the_form_states_that_it_was_answered_in_part_that_a_recommendation_is_not_an_answer_and_that_nothing_was_done():
    flat = " ".join(FORM.split())
    for phrase in ("Status: ANSWERED IN PART (2026-10-29)", "A recommendation was never taken as an answer", "A recommendation is not an answer", "Silence approves nothing",
                   "Any ID you do not answer stays **UNRESOLVED**", "Nothing else the form describes has been done", "no download, no model, tokenizer, `config.json`, dataset or user text accessed",
                   "Phase 2 unlocked and ran twice", "no package installed", "nothing activated", "the phases do not start until their rows are answered"):
        assert phrase in flat, phrase


def test_the_standing_rules_the_brief_requires_are_stated():
    flat = " ".join(FORM.split())
    for phrase in ("no floating branch, tag or `main` is ever used", "full 40-character lowercase commit hash", "`trust_remote_code=False`", "`local_files_only=True` unless a run is explicitly approved",
                   "`use_safetensors=True`", "`SENTIMENT_MODEL_ENABLED=false`", "never touches risk, goals, portfolio, recommendations, compliance",
                   "never logged, persisted, cached, sent externally or written to the ledger or blockchain"):
        assert phrase in flat, phrase


def test_the_hard_gates_the_brief_names_are_all_present_as_decisions():
    flat = " ".join(FORM.split())
    for phrase in ("Model licence accepted", "Tokenizer licence", "Training-data licence and provenance accepted", "Commercial / non-commercial position", "Attribution and share-alike",
                   "Exact 40-character lowercase revision", "Exact permitted files", "Permitted download hosts and redirects", "Destination directory", "SHA-256 verification", "Cleanup and rollback",
                   "OFFLINE EVALUATION ONLY / EVALUATION AND TRAINING", "**D10** Hub conversion", "**D11** network boundary", "**D12** install the S1 set", "**D13** TASK-CERT-1",
                   "Dataset source and licence", "Fictional versus consented text", "Annotators", "Annotation blinding", "Data retention", "Deletion", "R14 activation"):
        assert phrase in flat, phrase


def test_the_findings_that_change_what_the_owner_must_decide_are_stated_with_their_item():
    flat = " ".join(FORM.split())
    assert "Today the download happens implicitly inside training" in flat and "not met by the current code" in flat                       # E1
    assert "`--allow-hub-download` is not a file allow-list" in flat                                                                  # C2
    assert "does independently authored fictional text count as valid evidence" in flat                                              # D3
    assert "leaves calibration not evaluable" in flat                                                                                 # E2


def test_recorded_revisions_are_proposals_in_a_facts_column_never_in_an_entry():
    owner_supplied = {"A3.7", "A3.10"}                                                  # the owner wrote the FinBERT proposal into these two entries (2026-10-29); provisional until Phase 2 verifies it
    for identifier, cells in rows():
        found = re.findall(r"\b[0-9a-f]{40}\b", cells[-1])
        assert (not found) or (identifier in owner_supplied and set(found) == {"0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031"}), identifier
    a37 = next(cells for identifier, cells in rows() if identifier == "A3.7")
    assert "RECORDED proposals only, never approved" in a37[2] and "Phase 2 verified it" in a37[-1]


def test_the_phase_2_result_is_recorded_as_a_stopped_partial_run_and_confirms_nothing():
    flat = " ".join(FORM.split())
    for phrase in ("### Phase 2 result, first run (2026-10-29: STOPPED by the tool; superseded by the re-run below)", "| Requests | **2 of 10**", "`huggingface.co` only; no redirect", "**none requested**; the file listing was **not obtained**",
                   "**no provisional field is confirmed or rejected**", "needs the owner's confirmation because B1 approved one query", "Phase 2 is not complete, Phases 3 to 8 stay locked"):
        assert phrase in flat, phrase
    a = answers_before_remediation()
    assert all(a[i] == "KEEP UNRESOLVED" for i in STILL_PROVISIONAL_A3)                    # a verification result is not an approval (A3.1, A3.4, A3.7, A3.8 were approved later, by the owner)
    assert phases(a)[4] is False and phases(a)[3] is False


def test_the_rerun_completed_phase_2_with_five_requests_and_resolved_every_field_without_approving_any():
    flat = " ".join(FORM.split())
    for phrase in ("### Phase 2 result, completed by the re-run (2026-10-29: COMPLETE, no stop condition)", "| Requests | **3** (`model_info`, `revision_info`, `model_card`); with the first run **5 of 10** |",
                   "`huggingface.co` only; no redirect", "**none requested**; the repository listing was read from the metadata", "Nothing is REJECTED", "not owner approvals", "`model.safetensors`",
                   "**Only `model.safetensors` has an API-published SHA-256**", "**pickle-capable format: never fetch**", "No file, tokenizer file, `config.json`, weight or dataset was requested"):
        assert phrase in flat, phrase
    verdicts = re.findall(r"\| (?:Model licence|Tokenizer licence|Training-data licence and provenance|Commercial / non-commercial|Attribution|Share-alike|Exact permitted file list|Personal-finance suitability|Exact immutable revision)[^|]*\| \*\*([A-Z ]+)\*\*", FORM)
    assert len(verdicts) == 9 and set(verdicts) <= {"CONFIRMED", "REJECTED", "UNRESOLVED", "INSUFFICIENT EVIDENCE"} and "REJECTED" not in verdicts
    assert verdicts == ["CONFIRMED", "INSUFFICIENT EVIDENCE", "INSUFFICIENT EVIDENCE", "CONFIRMED", "CONFIRMED", "UNRESOLVED", "UNRESOLVED", "INSUFFICIENT EVIDENCE", "CONFIRMED"]
    a = answers_before_remediation()
    assert all(a[i] == "KEEP UNRESOLVED" for i in STILL_PROVISIONAL_A3) and a["A2"] == "KEEP UNRESOLVED"       # a Phase 2 result is evidence, never an owner approval
    assert phases(a) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}


def test_the_options_brief_chose_nothing_so_every_provisional_row_stays_unresolved_and_only_stated_facts_are_recorded():
    flat = " ".join(FORM.split())
    for phrase in ("### Pending owner decisions on A3.1 to A3.8 (first request, 2026-10-29; four rows were answered afterwards, see the next section)", "listed the options for each field but chose none", "a verification result is not an approval",
                   "**every row below stays `KEEP UNRESOLVED`**", "No legal clearance is claimed", "the NIST / Reuters TRC2 terms were not read",
                   "Neither unlocks because Phase 2 verification succeeded"):
        assert phrase in flat, phrase
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert e["A3.8"].startswith("APPROVE (2026-10-29, owner statement)")
    for name in ("model.safetensors", "config.json", "vocab.txt", "tokenizer_config.json", "special_tokens_map.json"):
        assert f"`{name}`" in e["A3.8"].split("Never download")[0], name                               # the proposed allow-list
    for name in ("pytorch_model.bin", "tf_model.h5", "flax_model.msgpack"):
        assert f"`{name}`" in e["A3.8"].split("Never download")[1], name                               # the never-download list
    assert "hashed independently during the first approved download" in e["A3.11"] and "verification, not approval of unknown contents" in e["A3.11"] and e["A3.11"].startswith("APPROVE")
    a = answers_before_remediation()
    assert all(a[i] == "KEEP UNRESOLVED" for i in STILL_PROVISIONAL_A3) and phases(a) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}


def test_the_resolution_brief_records_only_what_it_stated_and_keeps_every_first_download_control_closed():
    flat = " ".join(FORM.split())
    for phrase in ("### Owner statement of 2026-10-29 (resolution brief): what was recorded and what was not", "They were **not** recorded as approvals before", "again lists options without choosing",
                   "A default is not a choice among those options", "**C1 to C4 stay `BLOCKED`, C5, E3 and E4 stay `KEEP UNRESOLVED`**", "recorded as **restrictions only**",
                   "never `trust_remote_code=True`", "`local_files_only=True` after download", "no download starts while any of them is open"):
        assert phrase in flat, phrase
    a = answers_before_remediation()
    assert all(a[i] == "APPROVE" for i in OWNER_STATED_A3) and all(a[i] == "KEEP UNRESOLVED" for i in STILL_PROVISIONAL_A3)
    assert a["C4"] == "BLOCKED" and all(a[i] == "KEEP UNRESOLVED" for i in ("E3", "F1", "A2"))              # at the time of the resolution brief C1 to C4 and C5 were closed; later statements opened C1 to C3 and C5, see the Phase 3 test
    assert phases(a) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}
    for pending in [*STILL_PROVISIONAL_A3, "A3.5"]:                       # fail closed: any one of them open (or rejected) keeps the download locked
        assert phases({**everything_but(), pending: "KEEP UNRESOLVED"})[4] is False


def test_phase_3_was_not_started_because_c4_is_blocked_and_nothing_was_created():
    flat = " ".join(FORM.split())
    for phrase in ("### Phase 3 attempt (2026-10-29): NOT STARTED - nothing created, nothing installed", "**BLOCKED, no work done**", "`certifi` 2026.7.22 and `pip` 26.2.1", "**No** - so the environment must not be created",
                   "**none exist**", "Retrieval needs PyPI, and no recorded approval names it", "**Two discrepancies for the owner (not resolved by me).**", "setuptools` 84.2.1",
                   "**Path B code change required (documented, NOT applied).**", "so none was run and no result is claimed", "nothing was created, so there is nothing to delete", "**Phase 3 remains LOCKED.**"):
        assert phrase in flat, phrase
    a = answers_before_remediation()
    assert phases(a) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}
    assert phases({**a, "C4": "APPROVE"})[3] is True and phases({**a, "C4": "APPROVE"})[4] is False        # C4 is the one thing between the recorded answers and Phase 3
    assert a["A3.5"] == "REJECT" and a["A3.6"] == "APPROVE" and {a[i] for i in ("C1", "C2", "C3", "C5")} == {"APPROVE"}
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert "Not implemented" in e["C1"] and "Creation is conditional" in e["C3"] and "wealthpilot-finbert-eval-venv" in e["C3"] and "wealthpilot-hf-cache" in e["C5"] and "no PyPI contact" in e["C4"]


def test_the_phase_3_preparation_is_recorded_as_offline_facts_and_one_decision_request_with_nothing_done():
    flat = " ".join(FORM.split())
    for phrase in ("### Phase 3 unblock: offline preparation (2026-10-29) and the one consolidated decision request", "**TASK-CERT-1 cannot be completed offline.**",
                   "**The `setuptools` discrepancy is resolved by the record, not by a guess.**", "The executed list is authoritative", "No version was substituted",
                   "**The six direct packages are not a sufficient `--require-hashes` set:**", "`tensorboard` 2.17.1 imports `pkg_resources`", "must stay below 82",
                   "22 of 22 deliberate defects are detected", "Nothing below was done", "`APPROVE TASK-CERT-1 PROJECT-ENVIRONMENT REMEDIATION`", "`APPROVE PYPI RETRIEVAL`",
                   "`APPROVE THE 35-WHEEL LIST OF SECTION L.3 WITH setuptools==81.0.0`", "`APPROVE OFFLINE CODE CHANGE`", "**must not be approved in this phase**", "Hugging Face is never contacted in Phase 3"):
        assert phrase in flat, phrase
    a = answers_before_remediation()
    assert a["C4"] == "BLOCKED" and phases(a) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}       # the preparation changed no decision
    assert "Prepared offline (2026-10-29), unwired" in entries()["C1"] and "the wiring is approved and applied offline" in entries()["C1"]


def test_the_second_listing_of_the_consolidated_request_chose_nothing_but_the_c5_retention_and_changed_no_status():
    flat = " ".join(FORM.split())
    for phrase in ("### Owner message of 2026-10-29 (consolidated request, second listing): what was recorded", "**none of them is recorded as decided**", "R14 is not approved in this phase",
                   "Nothing was executed: no remediation, retrieval, environment or wiring"):
        assert phrase in flat, phrase
    c5 = " ".join(entries()["C5"].split())
    for phrase in ("use only during the approved disposable operation", "delete after the successful verified artifact creation", "delete immediately on failure, mismatch or cancellation", "never reuse a partial cache"):
        assert phrase in c5, phrase
    a = answers_before_remediation()
    assert a["C4"] == "BLOCKED" and a["A3.5"] == "REJECT" and a["A3.2"] == a["A3.3"] == "KEEP UNRESOLVED" and phases(a) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}


def test_the_phase_3_execution_is_recorded_with_the_project_environment_untouched_and_c4_still_blocked():
    flat = " ".join(FORM.split())
    for phrase in ("### Phase 3 execution (2026-10-29): disposable S1 environment validated and deleted; TASK-CERT-1 stopped before any change; Path B wired offline",
                   "**TASK-CERT-1: STOPPED, nothing changed.**", "The approved lock has no `pip` wheel", "(before = after: `certifi` 2026.7.22, `pip` 26.2.1, `setuptools` 65.5.0",
                   "**Missing approval:** a named `pip` version with its wheel hash", "35 of 35 wheels, hosts `pypi.org` and `files.pythonhosted.org` only", "1124 tests passed and 2 skipped",
                   "the temporary cache path was never created", "`--local-model-dir`", "`--local-model NAME=DIRECTORY`", "No Hugging Face contact, model, tokenizer, config, dataset or user text"):
        assert phrase in flat, phrase
    a = answers_before_remediation()
    assert a["C4"] == "BLOCKED" and phases(a) == {2: True, 3: False, 4: False, 5: False, 6: False, 7: False}
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert "STOPPED before any change" in e["C4"] and "validated and deleted the same day" in e["C3"]


def test_the_pip_metadata_phase_records_a_candidate_without_selecting_it_because_the_vendored_certifi_is_unverified():
    flat = " ".join(FORM.split())
    for phrase in ("### TASK-CERT-1 metadata phase (2026-10-29): candidate `pip` 26.2.2 found; its vendored `certifi` is NOT verified, so the version stays unresolved",
                   "**exactly one: 26.2.2**", "`pip-26.2.2-py3-none-any.whl`, 1,819,850 bytes, SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`", "not yanked", "**NOT VERIFIED.**", "(NOT selected, NOT approved, NOT installed)",
                   "the exact version stays **unresolved**", "vendors `certifi==2026.6.17`", "`certifi==2026.10.23` is upgraded only together with the approved `pip` remediation and never alone",
                   "TASK-CERT-1 stays BLOCKED until the exact `pip` version and wheel hash are explicitly approved", "a separate security decision"):
        assert phrase in flat, phrase
    a = answers_before_remediation()
    assert a["C4"] == "BLOCKED" and phases(a)[3] is False and phases(a)[4] is False
    assert "Owner policy decision (2026-10-29), recorded before the metadata query" in " ".join(entries()["C4"].split())


def test_task_cert_1_is_completed_verified_and_recorded_and_the_download_is_still_locked():
    flat = " ".join(FORM.split())
    for phrase in ("### TASK-CERT-1 execution (2026-10-29): COMPLETED AND VERIFIED; C4 is now APPROVE", "`pip` 26.2.1 to **26.2.2** (SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`)", "`certifi` 2026.7.22 to **2026.10.23** (SHA-256 `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1`",
                   "differ in exactly four lines: those two packages", "`setuptools` 65.5.0, `tensorflow` 2.17.0, `keras` 3.15.1, `numpy` 1.26.4", "\"No broken requirements found.\"", "0 mismatches",
                   "vendors `certifi==2026.10.19`", "1301 passed, 5 skipped", "NOT performed, because it needs a network connection", "tree SHA-256 `8da3684ee570782c3811494df0fa3ff2a9686fe2974e476264404a997d759801`", "No rollback was needed.",
                   "no Hugging Face contact", "Phase 4 still needs A3.2, A3.3, A3.5 (rejected)"):
        assert phrase in flat, phrase
    a = answers()
    assert a["C4"] == "APPROVE" and phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False}
    assert phases({**a, "C4": "BLOCKED"})[3] is False                                                  # C4 is what Phase 3 depends on
    for pending in (*STILL_PROVISIONAL_A3, "A3.5"):
        assert phases({**everything_but(), pending: "KEEP UNRESOLVED"})[4] is False                    # the download stays locked while a legal field is open
    c4 = " ".join(entries()["C4"].split())
    assert c4.startswith("APPROVE (2026-10-29") and "COMPLETED AND VERIFIED" in c4 and "Superseded earlier text" in c4


def test_the_end_to_end_brief_produced_one_decision_request_and_approved_nothing():
    flat = " ".join(FORM.split())
    for phrase in ("### Consolidated decision request for the legal gate (Phase 1) and the dataset gate (Phase 2), asked 2026-10-29", "supplies **no value**, so nothing is approved by it",
                   "Phases 3 to 6 stay locked", "`ACCEPT ABSENCE OF A SEPARATE TOKENIZER LICENSE STATEMENT FOR OFFLINE EVALUATION ONLY`",
                   "`ACCEPT FOR OFFLINE EVALUATION ONLY WITH EXPLICIT UNVERIFIED-TERMS RISK ACCEPTANCE`",
                   "`ACCEPT ONLY FOR THE DOWNLOADED MODEL ARTIFACT AND DIRECT ADAPTATIONS; NO CLAIM ABOUT FEATURES OR OUTPUTS`", "`REJECT USE UNTIL LEGAL SCOPE IS VERIFIED`",
                   "does independently authored fictional text count as valid evidence", "the existing fictional pilot examples are NOT validation evidence unless you approve that status here",
                   "**no text may be generated, collected, downloaded or labelled until D1 to D19 are approved**", "this form's E4 is the rubric / baseline alignment", "R14: stays unresolved"):
        assert phrase in flat, phrase
    reply = FORM[FORM.index("**Reply format (one line per item"):FORM.index("## C. Network and environment")]
    for identifier in ["A3.2", "A3.3", "A3.5b", *[f"D{n}" for n in range(1, 21)], "E3", "E4", "R14"]:
        assert re.search(rf"\b{re.escape(identifier)}:", reply), identifier
    a = answers()
    assert all(a[i] == "KEEP UNRESOLVED" for i in UNRESOLVED_D) and a["E3"] == a["F1"] == "KEEP UNRESOLVED" and a["A3.5"] == "REJECT"       # the later owner reply approved only OWNER_APPROVED_D
    assert phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False}


def test_the_owner_reply_recorded_only_the_direct_approvals_and_left_every_option_list_and_value_request_unresolved():
    flat = " ".join(FORM.split())
    for phrase in ("### Owner reply of 2026-10-29 (legal, dataset, alignment and manifest brief): what was recorded and what was not", "**without choosing one**", "an option list, a request for a value and silence are not answers",
                   "REJECT stands (no option chosen; rejected until the legal scope is verified)", "fictional text stays `synthetic`, so `validated` stays unreachable",
                   "the earlier quota and coverage proposals are not adopted", "**sizes were not given**, so D10 stays KEEP UNRESOLVED", "**method and threshold not given**, so D11 stays KEEP UNRESOLVED",
                   "so D8 stays KEEP UNRESOLVED", "so D13 stays KEEP UNRESOLVED", "E4 stays KEEP UNRESOLVED", "E3 is KEEP UNRESOLVED (no APPROVE given)", "no real manifest was created",
                   "Phase 4 stays locked (A3.2, A3.3 unresolved, A3.5b rejected)", "production activation is not authorised"):
        assert phrase in flat, phrase
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert e["D6"].startswith("APPROVE (2026-10-29, owner reply)") and "still required before any annotation" in e["D6"]
    assert e["D7"].startswith("APPROVE (2026-10-29, owner reply)") and "must not see model output, rules output, risk profile or recommendations" in e["D7"]
    assert e["D9"].startswith("APPROVE (2026-10-29, owner reply)") and "NOT adopted" in e["D9"]
    assert e["D15"].startswith("APPROVE (2026-10-29, owner reply)") and "0.70" in e["D15"] and "0.30" in e["D15"]
    a = answers()
    assert set(OWNER_APPROVED_D_SECOND_BRIEF) <= {i for i in a if i.startswith("D") and a[i] == "APPROVE"}
    assert a["A3.3"] == "KEEP UNRESOLVED" and a["A3.5"] == "REJECT" and a["E3"] == a["F1"] == "KEEP UNRESOLVED"
    assert phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False} and validated_reachable(a) is False


def test_the_third_owner_reply_recorded_only_d4_and_d8_and_left_every_option_list_example_and_value_request_unresolved():
    flat = " ".join(FORM.split())
    for phrase in ("### Owner reply of 2026-10-29 (third brief: consolidated legal, dataset, manifest and alignment decisions): what was recorded and what was not", "**without choosing one**",
                   "An option list, an example and a request for a value are not answers", "This section supersedes the previous section for D4 and D8 only",
                   "A3.5b REJECT stands", "**no sizes were given**, so D10 stays KEEP UNRESOLVED", "**method and threshold not given**, so D11 stays KEEP UNRESOLVED",
                   "so D13 stays KEEP UNRESOLVED", "**nothing is generated, collected, labelled, stored or frozen**", "no real manifest", "all six stay documented comparability limitations",
                   "Phase 4 stays locked (A3.2, A3.3 unresolved, A3.5b rejected)", "KEEP UNRESOLVED, unrequested"):
        assert phrase in flat, phrase
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert e["D4"].startswith("APPROVE (2026-10-29, owner reply, third brief)") and "no raw text in any report, log or error" in e["D4"] and "no user-submitted production text is ever used for annotation" in e["D4"]
    assert "participant register" in e["D4"] and "consent wording" in e["D4"]
    assert e["D8"].startswith("APPROVE (2026-10-29, owner reply, third brief)") and "Krippendorff alpha are secondary" in e["D8"] and "multi-label agreement stays deferred" in e["D8"]
    a = answers_before_closure()
    assert {"D4", "D6", "D7", "D8", "D9", "D15"} <= {i for i in a if i.startswith("D") and a[i] == "APPROVE"}
    assert sum(1 for s in a.values() if s == "REJECT") == 1                                                    # (the totals moved on with the fourth brief; see its own test)
    assert all(a[i] == "KEEP UNRESOLVED" for i in ["A2", "A3.3", "D1", "D2", "D5", "D14", "D16", "D19", "D20", "E3", "F1"])          # still open after the fourth brief too
    assert a["A3.5"] == "REJECT" and phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False} and validated_reachable(a) is False


def test_the_fourth_owner_decisions_are_recorded_and_the_legal_and_dataset_creation_gates_stay_closed():
    flat = " ".join(FORM.split())
    for phrase in ("### Owner decisions of 2026-10-29 (fourth brief): what was recorded, and what is still needed before anything is created", "`ACCEPT ABSENCE OF A SEPARATE TOKENIZER LICENSE STATEMENT FOR NON-COMMERCIAL OFFLINE EVALUATION ONLY`",
                   "not legal clearance", "A3.5b share-alike | REJECT USE UNTIL LEGAL SCOPE IS VERIFIED", "FinBERT stays undownloaded: A3.3 is unresolved and A3.5b is rejected",
                   "fictional text REMAINS SYNTHETIC and CANNOT produce `validated`", "600 training, 100 calibration, 300 held-out", "character 5-gram Jaccard at or above 0.90, equality counts",
                   "`topic`, `difficulty`, `negation`, `contradiction`, `code_mixed`", "**no storage location is named**", "**nothing may be generated, collected, labelled, stored or frozen**",
                   "E4 is **APPROVE: KEEP DOCUMENTED DIFFERENCE** for all six differences; no production code changed", "are **not yet checked by any tool**",
                   "four deliberate faults", "Phase 4 stays locked (A3.3 unresolved, A3.5b rejected)"):
        assert phrase in flat, phrase
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert e["A3.2"].startswith("APPROVE (2026-10-29, owner decision, fourth brief)") and "NON-COMMERCIAL OFFLINE EVALUATION ONLY" in e["A3.2"] and "Superseded earlier text" in e["A3.2"]
    assert e["D3"].startswith("APPROVE (") and "REMAINS SYNTHETIC" in e["D3"] and "CANNOT produce `validated`" in e["D3"]
    assert "600, 100 and 300 statements" in e["D10"] and "0.90" in e["D11"] and "equality counts" in e["D11"] and "nfkc_casefold_char5gram_jaccard" in e["D11"]
    assert "`code_mixed`" in e["D12"] and "calibration split" in e["D13"] and "Wired offline on 2026-10-30" in e["D13"]
    assert e["D5"].startswith("KEEP UNRESOLVED") and "`v0-draft`; DO NOT FREEZE IT" in e["D5"]
    assert e["D16"].startswith("KEEP UNRESOLVED") and "no location is named" in e["D16"]
    assert e["E4"].startswith("APPROVE (") and "KEEP DOCUMENTED DIFFERENCE for all six" in e["E4"]
    a = answers_before_closure()
    assert set(OWNER_APPROVED_D_FOURTH_BRIEF) | set(OWNER_APPROVED_D_THIRD_BRIEF) | set(OWNER_APPROVED_D_SECOND_BRIEF) == {i for i in a if i.startswith("D") and a[i] == "APPROVE"}
    assert a["A3.2"] == "APPROVE" and a["A3.3"] == "KEEP UNRESOLVED" and a["A3.5"] == "REJECT" and a["E4"] == "APPROVE" and a["E3"] == a["F1"] == "KEEP UNRESOLVED"
    assert [i for i in UNRESOLVED_D] == ["D1", "D2", "D5", "D14", "D16", "D19"]
    assert (sum(s == "APPROVE" for s in a.values()), sum(s == "REJECT" for s in a.values()), sum(s == "BLOCKED" for s in a.values()), sum(s == "KEEP UNRESOLVED" for s in a.values())) == (44, 1, 0, 11)
    assert phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False} and validated_reachable(a) is False


def test_the_register_and_d13_implementation_changed_no_decision_and_created_no_data():
    flat = " ".join(FORM.split())
    for phrase in ("### Offline implementation of the participant register and D13 calibration (2026-10-30)", "**No decision changed.**", "**44 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 11 KEEP UNRESOLVED**",
                   "A3.3 stays KEEP UNRESOLVED and A3.5b stays rejected", "the rubric stays `v0-draft` and unfrozen", "D16 (no private storage location is approved)",
                   "**No real data was created, no consented data was collected, no real register or manifest exists, no rubric freeze occurred", "**cannot** verify independence",
                   "**Every error is a fixed description with counts and participant positions; it never echoes a value or a field name.**", "**no logit is invented**",
                   "a labels-only candidate (the rules baseline) is `labels_only`, is never calibrated and keeps its labels", "synthetic evidence still yields `not_validation_evidence`",
                   "28 of 30 mutants", "No real register, dataset or manifest can be created while D1, D2, D16, D19, D20 and E3 are unresolved"):
        assert phrase in flat, phrase
    a = answers_before_closure()
    assert (sum(s == "APPROVE" for s in a.values()), sum(s == "REJECT" for s in a.values()), sum(s == "BLOCKED" for s in a.values()), sum(s == "KEEP UNRESOLVED" for s in a.values())) == (44, 1, 0, 11)
    assert all(a[i] == "KEEP UNRESOLVED" for i in ("A2", "A3.3", "D1", "D2", "D5", "D14", "D16", "D19", "D20", "E3", "F1")) and a["A3.5"] == "REJECT"
    assert phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False} and validated_reachable(a) is False


def test_the_fifth_brief_and_the_end_to_end_brief_changed_no_status_and_produced_one_table():
    flat = " ".join(FORM.split())
    for phrase in ("### Owner decisions of 2026-10-30 (fifth brief) and the end-to-end brief: recorded values, blocked operations, and the one consolidated approval table",
                   "\"D14 = APPROVE\" (adjudication and agreement) is this form's D8", "\"D19 = APPROVE\" (retention and deletion) is this form's D17",
                   "**Totals do not change: 44 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 11 KEEP UNRESOLVED.**", "E3 = APPROVE SCHEMA-2 OFFLINE IMPLEMENTATION ONLY", "because the row asks for a real manifest",
                   "**no agreement result alone can produce `validated`**", "deletion is authorized by the project owner", "never deleted raw text", "No path was supplied on 2026-10-30, so nothing is invented",
                   "**The one consolidated approval table", "An omitted row keeps the value on record", "R14 activation | asked only after a real evaluation is complete",
                   "Phase 4 stays locked (A3.3 unresolved, A3.5b rejected)", "this form's own D14 (training data", "and D19 (validation design"):
        assert phrase in flat, phrase
    table = FORM[FORM.index("**The one consolidated approval table"):FORM.index("This form's own D14 (training data, only if")]
    for row in ("A3.2 tokenizer licence", "A3.3 training-data terms", "A3.5b share-alike", "D1 dataset source and licence", "D2 provenance type", "D3 can fictional data", "D5 rubric", "D10 split sizes",
                "D11 duplicates", "D12 group dimensions", "D14 adjudication and agreement", "D16 private storage path", "D19 retention and deletion", "D20 permission", "E3 real frozen manifest", "E4 six",
                "R14 activation"):
        assert row in table, row
    a = answers_before_closure()
    assert (sum(s == "APPROVE" for s in a.values()), sum(s == "REJECT" for s in a.values()), sum(s == "BLOCKED" for s in a.values()), sum(s == "KEEP UNRESOLVED" for s in a.values())) == (44, 1, 0, 11)
    assert all(a[i] == "KEEP UNRESOLVED" for i in ("A2", "A3.3", "D1", "D2", "D5", "D14", "D16", "D19", "D20", "E3", "F1")) and a["A3.5"] == "REJECT" and a["D8"] == a["D17"] == "APPROVE"
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert "no agreement result alone can produce `validated`" in e["D8"] and "never deleted raw text" in e["D17"] and "deletion is authorized by the project owner" in e["D17"]
    assert e["E3"].startswith("KEEP UNRESOLVED") and "SCHEMA-2 OFFLINE IMPLEMENTATION ONLY" in e["E3"] and e["D16"].startswith("KEEP UNRESOLVED") and "nothing is invented" in e["D16"]
    assert phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False} and validated_reachable(a) is False


CLOSURE = "The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved."


def test_the_phase_closure_rejects_d20_records_the_exact_values_and_states_the_closure():
    flat = " ".join(FORM.split())
    for phrase in ("### Phase closure (2026-10-30): the offline rules-based sentiment phase", "> " + CLOSURE, "REJECT REAL DATA CREATION, COLLECTION, LABELING, STORAGE AND MANIFEST CREATION FOR THIS PHASE",
                   "**Totals: 44 APPROVE, 2 REJECT (A3.5, D20), 0 BLOCKED, 10 KEEP UNRESOLVED.**", "A rejected item never unlocks a later phase: Phases 4 to 7 stay locked",
                   "**The approval requests for A3.3, A3.5b, D1, D2, D5, D16, D20, E3, E4 and R14 are closed for this phase and are not repeated;**", "that is a new phase with a new explicit approval request",
                   "KEEP v0-DRAFT; DO NOT FREEZE", "KEEP DOCUMENTED DIFFERENCE FOR ALL SIX RECORDED DIFFERENCES", "APPROVE SCHEMA-2 OFFLINE IMPLEMENTATION ONLY",
                   "Synthetic fixtures produce only `not_validation_evidence` or `descriptive_only`, never `validated`", "real model downloaded: no; real dataset created: no; real evaluation run: no; production activation: no",
                   "intensity regression: disabled", "blockchain / ledger sentiment payload: none"):
        assert phrase in flat, phrase
    a = answers()
    assert (sum(s == "APPROVE" for s in a.values()), sum(s == "REJECT" for s in a.values()), sum(s == "BLOCKED" for s in a.values()), sum(s == "KEEP UNRESOLVED" for s in a.values())) == (44, 2, 0, 10)
    assert {i for i, s in a.items() if s == "REJECT"} == {"A3.5", "D20"} and a["D20"] == "REJECT"
    assert all(a[i] == "KEEP UNRESOLVED" for i in ("A2", "A3.3", "D1", "D2", "D5", "D14", "D16", "D19", "E3", "F1")) and a["E4"] == "APPROVE" and a["A3.2"] == "APPROVE"
    e = {i: " ".join(v.split()) for i, v in entries().items()}
    assert e["D20"].startswith("REJECT (2026-10-30") and "new phase with a new explicit approval request" in e["D20"] and "KEEP v0-DRAFT; DO NOT FREEZE" in e["D5"] and e["D5"].startswith("KEEP UNRESOLVED")
    assert phases(a) == {2: True, 3: True, 4: False, 5: False, 6: False, 7: False} and validated_reachable(a) is False
    later = everything_but(D20="REJECT")
    assert phases(later)[5] is False and phases(later)[6] is False and phases(later)[7] is False                  # a rejected D20 alone keeps evaluation and activation locked
    for name in ("reports/sentiment_model_approval_record.md", "docs/MEMORY.md", "docs/DECISIONS.md", "training/sentiment/README.md", "docs/TEST_PLAN.md", "docs/THREAT_MODEL.md"):
        assert " ".join((ROOT / name).read_text(encoding="utf-8").split()).count("The offline rules-based sentiment phase is complete.") >= 1, name
