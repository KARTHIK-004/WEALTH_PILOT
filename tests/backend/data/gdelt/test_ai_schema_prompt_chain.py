"""AI-assisted annotation pipeline (built, DISABLED): input schema, structured-output validation, prompt contents,
hash chain, provider interface. All items are SYNTHETIC; nothing here calls a model or the network."""

from __future__ import annotations

import csv
import json

import pytest

from wealthpilot.data.gdelt.ai import chain, fingerprints, prompt, provider, rubric, schema
from wealthpilot.data.gdelt.ai.schema import SchemaError, SourceItem, load_items, validate_input, validate_output
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS


def item(i: int = 1, **fields) -> SourceItem:
    f = {"item_id": f"D{i:04d}", "batch_date_utc": "2022-03-01", "source_domain": "example.com",
         "url": f"https://example.com/synthetic/{i}",
         "title": f"SYNTHETIC {i}: Federal Reserve raises interest rates by a quarter point"} | fields
    return SourceItem(f["item_id"], f, fingerprints.item_fingerprint(f), False, "ORIGINAL", tuple(validate_input(f)))


def good(it: SourceItem, **over) -> str:
    body = {"item_id": it.item_id, "rel_equity": "I", "rel_rates": "R", "rel_gold": "I", "amb_code": "",
            "company_notice": "N", "pol_equity": "", "pol_rates": "NEG", "pol_gold": "", "note": "",
            "evidence_excerpts": [{"field": "rel_rates", "excerpt": "raises interest rates"}],
            "insufficient_evidence": False,
            "uncertainty": {"rel_equity": "low", "rel_rates": "low", "rel_gold": "low"},
            "evidence_basis": "headline_url_only"}
    body.update(over)
    return json.dumps(body)


# ---------------------------------------------------------------- input schema

def test_input_validation_accepts_the_approved_fields_only():
    assert validate_input(item().fields) == []
    extra = dict(item().fields, overlap_subset="Y")
    assert "exactly" in validate_input(extra)[0]
    assert validate_input({k: v for k, v in item().fields.items() if k != "url"})


@pytest.mark.parametrize("field,value,fragment", [
    ("title", "bell\x07", "control or format"), ("url", "   ", "url is empty"), ("item_id", "X1", "unexpected format"),
    ("title", "zero​width", "control or format")])
def test_unsafe_inputs_are_marked_unsendable(field, value, fragment):
    problems = validate_input(item().fields | {field: value})
    assert any(fragment in p for p in problems)


def test_load_items_reads_the_original_and_keeps_overlap_as_provenance(make_ai_env):
    env = make_ai_env()
    items = load_items(env.rf / "annotation_A.csv")
    assert [i.item_id for i in items] == env.ids
    assert {i.item_id for i in items if i.historical_overlap} == env.overlap
    assert all(set(i.fields) == set(schema.APPROVED_INPUT_FIELDS) for i in items)
    assert all(i.sendable for i in items)


def test_load_items_refuses_labels_duplicates_and_wrong_columns(make_ai_env, tmp_path):
    env = make_ai_env()
    src = env.rf / "annotation_A.csv"
    rows = list(csv.DictReader(open(src, newline="", encoding="utf-8")))

    def write(path, rs, cols=ANNOTATION_COLUMNS):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(cols), lineterminator="\n")
            w.writeheader()
            w.writerows(rs)
        return path

    labelled = [dict(r) for r in rows]
    labelled[0]["rel_equity"] = "R"
    with pytest.raises(SchemaError, match="contains labels"):
        load_items(write(tmp_path / "labelled.csv", labelled))
    with pytest.raises(SchemaError, match="unique"):
        load_items(write(tmp_path / "dup.csv", [*rows, dict(rows[0])]))
    with pytest.raises(SchemaError, match="columns"):
        load_items(write(tmp_path / "cols.csv", [{"item_id": "D0001"}], cols=("item_id",)))
    bad_overlap = [dict(r) for r in rows]
    bad_overlap[0]["overlap_subset"] = "maybe"
    with pytest.raises(SchemaError, match="overlap_subset"):
        load_items(write(tmp_path / "ov.csv", bad_overlap))
    with pytest.raises(SchemaError, match="cannot read"):
        load_items(tmp_path / "missing.csv")


def test_load_items_flags_unsendable_rows_without_editing_them(make_ai_env):
    env = make_ai_env(unsendable=("D0003",))
    by_id = {i.item_id: i for i in env.source_items()}
    assert not by_id["D0003"].sendable and "\x07" in by_id["D0003"].fields["title"]    # not silently cleaned
    assert by_id["D0001"].sendable


def test_item_fingerprint_is_stable_and_field_sensitive():
    a, b = item(1), item(1)
    assert a.fingerprint == b.fingerprint
    assert item(1, title="different").fingerprint != a.fingerprint
    assert (fingerprints.itemset_fingerprint([("D1", "x"), ("D2", "y")])
            != fingerprints.itemset_fingerprint([("D1", "x"), ("D2", "z")]))


# ---------------------------------------------------------------- structured-output validation

def test_a_valid_response_passes_and_keeps_the_parsed_object():
    it = item()
    v = validate_output(good(it), it)
    assert v.ok and v.errors == () and v.parsed["rel_rates"] == "R" and v.flags == ()


@pytest.mark.parametrize("raw,fragment", [
    ("not json", "not a single JSON object"), ("[1, 2]", "not a single JSON object"), ("", "not a single JSON object"),
    ("```json\n{}\n```", "not a single JSON object")])
def test_non_json_is_invalid_and_never_repaired(raw, fragment):
    v = validate_output(raw, item())
    assert not v.ok and fragment in v.errors[0] and v.parsed is None


def test_missing_and_unknown_keys_are_rejected():
    it = item()
    body = json.loads(good(it))
    body.pop("uncertainty")
    assert "missing fields: uncertainty" in validate_output(json.dumps(body), it).errors[0]
    body = json.loads(good(it)) | {"confidence": 0.99}
    assert "unexpected fields: confidence" in validate_output(json.dumps(body), it).errors


def test_a_response_for_another_item_is_rejected():
    it, other = item(1), item(2)
    v = validate_output(good(other), it)
    assert not v.ok and "does not match the requested item" in v.errors[0]


@pytest.mark.parametrize("over,fragment", [
    ({"rel_rates": "R", "pol_rates": ""}, "pol_rates is required"),                          # cross-field: R needs polarity
    ({"rel_equity": "I", "pol_equity": "POS"}, "pol_equity must be blank"),
    ({"company_notice": "Y"}, "never R"),                                                      # company notice with R
    ({"rel_equity": "A", "amb_code": ""}, "amb_code is required"),
    ({"amb_code": "A1"}, "amb_code must be blank"),
    ({"rel_rates": "maybe"}, "must be R, RL, I or A"),
    ({"evidence_basis": "full_article"}, "evidence_basis must be"),
    ({"note": "x" * 301}, "longer than"),
    ({"insufficient_evidence": True}, "no theme is labelled A"),
    ({"insufficient_evidence": "yes"}, "true or false"),
    ({"uncertainty": {"rel_equity": "low"}}, "uncertainty must give"),
    ({"uncertainty": {"rel_equity": "sure", "rel_rates": "low", "rel_gold": "low"}}, "uncertainty must give"),
    ({"rel_equity": 5}, "must be text")])
def test_cross_field_and_type_rules_are_enforced(over, fragment):
    it = item()
    v = validate_output(good(it, **over), it)
    assert not v.ok and any(fragment in e for e in v.errors), v.errors


@pytest.mark.parametrize("excerpts,fragment", [
    ([], "no supported evidence excerpt"),
    ([{"field": "rel_rates", "excerpt": "a sentence that is not in the headline"}], "does not appear"),
    ([{"field": "rel_rates", "excerpt": ""}], "empty or too long"),
    ([{"field": "rel_oil", "excerpt": "raises interest rates"}], "unknown field"),
    ([{"field": "rel_rates"}], "malformed"), ("raises interest rates", "must be a list")])
def test_evidence_excerpts_must_be_verbatim_context(excerpts, fragment):
    it = item()
    v = validate_output(good(it, evidence_excerpts=excerpts), it)
    assert not v.ok and any(fragment in e for e in v.errors), v.errors


def test_an_excerpt_may_come_from_the_url_and_is_matched_case_and_space_insensitively():
    it = item(url="https://example.com/fed-RAISES-rates")
    ok = good(it, evidence_excerpts=[{"field": "rel_rates", "excerpt": "FED-raises-RATES"}])
    assert validate_output(ok, it).ok
    spaced = good(item(), evidence_excerpts=[{"field": "rel_rates", "excerpt": "Raises   INTEREST rates"}])
    assert validate_output(spaced, item()).ok


def test_uncertain_and_insufficient_results_are_valid_but_flagged():
    it = item()
    amb = good(it, rel_gold="A", amb_code="A1", insufficient_evidence=True,
               uncertainty={"rel_equity": "low", "rel_rates": "high", "rel_gold": "high"})
    v = validate_output(amb, it)
    assert v.ok and {"ambiguous", "insufficient_evidence", "high_uncertainty_self_reported"} <= set(v.flags)


def test_flags_for_company_unclear_multi_theme_and_short_title():
    it = item(title="Rates up")
    v = validate_output(good(it, rel_equity="R", pol_equity="POS", company_notice="U",
                             evidence_excerpts=[{"field": "rel_rates", "excerpt": "rates"},
                                                {"field": "rel_equity", "excerpt": "up"}]), it)
    assert v.ok and {"company_unclear_with_r", "multi_theme_relevant", "short_or_empty_title"} <= set(v.flags)


def test_output_json_schema_matches_the_validators_keys():
    sch = schema.output_json_schema()
    assert tuple(sch["required"]) == schema.OUTPUT_KEYS and sch["additionalProperties"] is False


# ---------------------------------------------------------------- prompt and rubric

def test_request_contains_only_the_approved_fields_of_one_item():
    it = SourceItem("D0007", {"item_id": "D0007", "batch_date_utc": "2022-03-01", "source_domain": "example.com",
                              "url": "https://example.com/7", "title": "SYNTHETIC headline"},
                    "fp", True, "EXACT_DUP", ())
    req = prompt.build_request(it, rubric.load_rubric(), max_output_tokens=400)
    payload = json.loads(req.user.split("(JSON):\n", 1)[1].splitlines()[0])
    assert set(payload) == set(schema.APPROVED_INPUT_FIELDS) and payload["title"] == "SYNTHETIC headline"
    for forbidden in ("overlap", "EXACT_DUP", "mech_dup", "label", "gkg_record_id", "key_sealed"):
        assert forbidden not in req.user
    assert req.item_id == "D0007" and req.max_output_tokens == 400


def test_an_unsendable_item_never_reaches_a_prompt():
    bad = item(title="bell\x07")
    with pytest.raises(provider.ExecutionBlocked, match="never sent"):
        prompt.build_request(bad, rubric.load_rubric(), max_output_tokens=400)


def test_reask_adds_only_the_repair_instruction():
    r = rubric.load_rubric()
    first = prompt.build_request(item(), r, max_output_tokens=400)
    again = prompt.build_request(item(), r, max_output_tokens=400, reask=True)
    assert again.user == first.user + "\n" + prompt.REPAIR_INSTRUCTION and again.system == first.system


def test_prompt_and_rubric_fingerprints_are_registered_and_stable():
    r = rubric.load_rubric()
    assert r.sha256 == rubric.REGISTRY["b2t_rubric_v1"] and prompt.prompt_sha256() == prompt.prompt_sha256()
    with pytest.raises(Exception, match="unregistered"):
        rubric.load_rubric("b2t_rubric_v9")
    with pytest.raises(Exception, match="differs from the registered"):
        rubric.load_rubric(registry={"b2t_rubric_v1": "0" * 64})
    assert prompt.estimate_tokens("x" * 400) == 100


# ---------------------------------------------------------------- hash chain

def test_chain_appends_verifies_and_detects_every_kind_of_tampering(tmp_path):
    c = chain.ChainedJsonl(tmp_path / "x" / "log.jsonl")
    for n in range(3):
        c.append({"n": n})
    assert [r["n"] for r in c.records()] == [0, 1, 2] and c.head() == c.records()[-1]["record_sha256"]
    path = tmp_path / "x" / "log.jsonl"
    original = path.read_bytes()
    lines = original.splitlines(keepends=True)
    path.write_bytes(original.replace(b'"n": 1', b'"n": 9').replace(b'"n":1', b'"n":9'))
    with pytest.raises(chain.ChainError, match="edited"):
        c.records()
    path.write_bytes(lines[0] + lines[2])
    with pytest.raises(chain.ChainError, match="breaks the chain"):
        c.records()
    path.write_bytes(lines[1] + lines[0] + lines[2])
    with pytest.raises(chain.ChainError, match="breaks the chain"):
        c.records()
    path.write_bytes(original + b"not json\n")
    with pytest.raises(chain.ChainError, match="not valid JSON"):
        c.records()
    with pytest.raises(chain.ChainError, match="chain fields"):
        c.append({"prev_sha256": "x"})


def test_a_partial_final_line_is_quarantined_not_deleted(tmp_path):
    path = tmp_path / "log.jsonl"
    c = chain.ChainedJsonl(path)
    c.append({"n": 0})
    path.write_bytes(path.read_bytes() + b'{"n": 1, "prev_sha256": "abc')          # a crash mid-write
    assert c.has_partial_tail() and len(c.records()) == 1
    c.append({"n": 2})
    assert [r["n"] for r in c.records()] == [0, 2] and not c.has_partial_tail()
    assert (tmp_path / "log.jsonl.partial-1").read_bytes().startswith(b'{"n": 1')


def test_empty_chain_has_genesis_head(tmp_path):
    c = chain.ChainedJsonl(tmp_path / "none.jsonl")
    assert c.records() == [] and c.head() == chain.GENESIS


# ---------------------------------------------------------------- provider interface

def test_no_adapter_is_registered_and_nothing_can_be_built():
    assert provider.ADAPTERS == {}
    with pytest.raises(provider.ProviderNotImplemented, match="no provider is configured"):
        provider.build_provider(None)
    with pytest.raises(provider.ProviderNotImplemented, match="no adapter exists"):
        provider.build_provider("any_vendor")


def test_the_disabled_provider_cannot_be_called():
    req = prompt.build_request(item(), rubric.load_rubric(), max_output_tokens=10)
    with pytest.raises(provider.ExecutionBlocked, match="disabled"):
        provider.DisabledProvider().suggest(req)


@pytest.mark.parametrize("kind,retryable", [("timeout", True), ("rate_limited", True), ("server_error", True),
                                            ("refused", False), ("auth", False), ("bad_request", False),
                                            ("something_new", False)])
def test_provider_error_retry_classification(kind, retryable):
    err = provider.ProviderError(kind, "detail")
    assert err.retryable is retryable and (err.kind in provider.ALL_KINDS)
