"""ADR-052 -- `training/sentiment/hub_fetch.py`: the read-only metadata query (form item B9) and the verified fetch step (form item E1), tested OFFLINE ONLY: a scripted in-memory transport for the logic and a
loopback server on 127.0.0.1 for the real transport. No external host is ever contacted, no model or dataset exists, and the module is never run against a real hub. The names `hub.test` and `cdn.test`
are invented."""

from __future__ import annotations

import ast
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from training.sentiment import hub_fetch as hf
from training.sentiment.hub_fetch import FetchError, FetchPolicy, FileSpec, Response, UrllibTransport, fetch_files, query_metadata, render_markdown

ID = "acme/finance-sentiment"
REV = "0123456789abcdef0123456789abcdef01234567"
OTHER_REV = "fedcba9876543210fedcba9876543210fedcba98"
HUB, CDN = "hub.test", "cdn.test"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


WEIGHTS, VOCAB, TOKCONF = b"W" * 3000, b"[PAD]\n[UNK]\nsavings\n", b'{"do_lower_case": true}'
LISTING = [{"rfilename": "model.safetensors", "size": len(WEIGHTS), "lfs": {"sha256": sha(WEIGHTS)}}, {"rfilename": "vocab.txt", "size": len(VOCAB)}, {"rfilename": "tokenizer_config.json"},
           {"rfilename": "config.json"}, {"rfilename": "pytorch_model.bin"}, {"rfilename": "training_args.bin"}, {"rfilename": "README.md"}]
CARD = "---\nlicense: cc-by-nc-sa-4.0\ncontact: someone@example.test\ntoken: hf_abcdefghijklmnopqrstuv\nphone: 9876543210123\n---\n# Model card\n## Training data\nSECRETCARDWORDS\n## Limitations\n"


def info(sha_value: str = REV, **over) -> bytes:
    body = {"id": ID, "modelId": ID, "sha": sha_value, "cardData": {"license": "cc-by-nc-sa-4.0"}, "tags": ["license:cc-by-nc-sa-4.0", "text-classification"], "gated": False,
            "library_name": "transformers", "pipeline_tag": "text-classification", "config": {"architectures": ["BertForSequenceClassification"]}, "siblings": LISTING}
    body.update(over)
    return json.dumps(body).encode()


class Scripted:
    """An in-memory transport: a table of url -> list of (status, headers, body) answered in order; unknown urls are 404. Records every request."""

    def __init__(self, table: dict[str, list[tuple[int, dict, bytes]]]) -> None:
        self.table, self.requests, self.closed = {k: list(v) for k, v in table.items()}, [], 0

    def open(self, url: str, *, timeout: float) -> Response:
        self.requests.append(url)
        queue = self.table.get(url)
        status, headers, body = queue.pop(0) if queue else (404, {}, b"")

        def close() -> None:
            self.closed += 1

        return Response(status, {k.lower(): v for k, v in headers.items()}, iter([body[i:i + 1024] for i in range(0, len(body), 1024)] or [b""]), close)


def policy(**over) -> FetchPolicy:
    values = dict(base_host=HUB, allowed_hosts=(HUB, CDN), max_requests=10, timeout_seconds=5.0, allow_loopback_http=False)
    values.update(over)
    return FetchPolicy(**values)


def urls(revision: str | None = REV) -> dict[str, str]:
    return hf.metadata_urls(ID, revision, policy())


def happy_table(sha_value: str = REV) -> dict:
    u = urls()
    return {urls(None)["model_info"]: [(200, {}, info(sha_value))], u["revision_info"]: [(200, {}, info(REV))], u["model_card"]: [(200, {}, CARD.encode())]}


def run(table: dict, *, proposed: str | None = REV, licence: str | None = "CC BY-NC-SA 4.0", pol: FetchPolicy | None = None, keep: bool = False):
    transport = Scripted(table)
    return query_metadata(ID, proposed_revision=proposed, provisional_licence=licence, policy=pol or policy(), transport=transport, keep_card_text=keep), transport


# ------------------------------------------------------------------------------------------------------------------------------- the metadata query: the happy path and what it requests
def test_a_complete_query_makes_three_requests_to_one_host_and_returns_a_sanitized_record():
    result, transport = run(happy_table())
    record = result["record"]
    assert record["stopped"] is None and record["requests_made"] == 3 and record["hosts_contacted"] == [HUB] and record["request_kinds"] == ["model_info", "revision_info", "model_card"]
    assert record["verified_revision"] == REV == record["discovered_revision"] and record["license_ids"] == ["cc-by-nc-sa-4.0"] and record["conflicts"] == []
    assert [f["name"] for f in record["files"]] == sorted(f["rfilename"] for f in LISTING) and record["pickle_capable_files"] == ["pytorch_model.bin", "training_args.bin"]
    weights = next(f for f in record["files"] if f["name"] == "model.safetensors")
    assert weights["size"] == 3000 and weights["sha256"] == sha(WEIGHTS)
    assert "config" not in record and "siblings" not in record and result["card_text"] is None
    assert record["downloads"].startswith("none")
    assert transport.requests == [urls(None)["model_info"], urls()["revision_info"], urls()["model_card"]]


def test_the_query_never_requests_weights_tokenizer_files_configuration_or_datasets():
    result, transport = run(happy_table())
    for url in transport.requests:
        assert not any(marker in url for marker in ("/resolve/", "config.json", ".safetensors", ".bin", "vocab", "tokenizer", "/datasets/", "train", ".pt")), url
    assert set(hf.metadata_urls(ID, REV, policy())) == {"model_info", "revision_info", "model_card"}
    assert all(url.endswith(("?blobs=true", "/README.md")) for url in hf.metadata_urls(ID, REV, policy()).values())


def test_without_a_proposed_revision_the_main_revision_is_discovered_and_reported_for_confirmation():
    u = urls(None)
    card = hf.metadata_urls(ID, REV, policy())["model_card"]
    result, transport = run({u["model_info"]: [(200, {}, info())], card: [(200, {}, CARD.encode())]}, proposed=None)
    record = result["record"]
    assert record["stopped"] is None and record["requests_made"] == 2 and record["request_kinds"] == ["model_info", "model_card"]
    assert record["proposed_revision"] is None and record["discovered_revision"] == REV == record["verified_revision"]


def test_the_model_card_is_hashed_and_summarised_never_stored_whole_and_secrets_are_masked():
    result, _ = run(happy_table(), keep=True)
    record, text = result["record"], render_markdown(result["record"])
    assert result["card_text"] == CARD and record["card"]["sha256"] == sha(CARD.encode()) and record["card"]["characters"] == len(CARD)
    assert "SECRETCARDWORDS" not in json.dumps(record) and "SECRETCARDWORDS" not in text
    stored = json.dumps(record) + text
    for secret in ("someone@example.test", "hf_abcdefghijklmnopqrstuv", "9876543210123"):
        assert secret not in stored
    assert "[email]" in stored and "[token]" in stored and "[number]" in stored and "license: cc-by-nc-sa-4.0" in text and "# Model card" in text
    assert "downloads" in text and "pickle_capable_files" in text


def test_licence_matching_ignores_case_spacing_and_punctuation_and_a_matching_provisional_record_is_not_a_conflict():
    for provisional in ("CC BY-NC-SA 4.0", "cc-by-nc-sa-4.0", "CC_BY_NC_SA_4.0", None):
        result, _ = run(happy_table(), licence=provisional)
        assert result["record"]["stopped"] is None and result["record"]["conflicts"] == [], provisional


# ------------------------------------------------------------------------------------------------------------------------------- the seven stop conditions (B10)
def test_stop_1_the_identifier_differs():
    u = urls(None)
    result, transport = run({u["model_info"]: [(200, {}, info(id="evil/other", modelId="evil/other"))]})
    assert result["record"]["stopped"] == "identifier_differs" and len(transport.requests) == 1 and result["record"]["requests_made"] == 1


def test_stop_2_the_revision_differs_from_the_proposed_value():
    u = urls()
    for table in ({urls(None)["model_info"]: [(200, {}, info())], u["revision_info"]: [(404, {}, b"")]},
                  {urls(None)["model_info"]: [(200, {}, info())], u["revision_info"]: [(200, {}, info(OTHER_REV))]}):
        result, transport = run(table)
        assert result["record"]["stopped"] == "revision_differs" and len(transport.requests) == 2 and "model_card" not in result["record"]["request_kinds"]


def test_stop_3_the_licence_conflicts_with_the_provisional_record_and_nothing_further_is_requested():
    result, transport = run(happy_table(), licence="Apache-2.0")
    assert result["record"]["stopped"] == "licence_conflict" and result["record"]["conflicts"] == ["licence"] and len(transport.requests) == 2        # the card is not fetched


def test_stop_4_an_unapproved_host_appears_in_a_redirect():
    u = urls(None)
    result, transport = run({u["model_info"]: [(302, {"Location": "https://evil.test/api/models/acme/finance-sentiment"}, b"")]})
    assert result["record"]["stopped"] == "unapproved_host" and len(transport.requests) == 1 and transport.closed == 1


def test_stop_5_a_request_would_access_a_file():
    u = urls(None)
    for target in (f"https://{HUB}/acme/finance-sentiment/resolve/{REV}/model.safetensors", f"https://{HUB}/acme/finance-sentiment/resolve/{REV}/config.json", f"https://{HUB}/datasets/x/y",
                   f"https://{HUB}/acme/finance-sentiment/raw/{REV}/vocab.txt"):
        result, transport = run({u["model_info"]: [(302, {"Location": target}, b"")]}, proposed=None)
        assert result["record"]["stopped"] == "would_access_file" and len(transport.requests) == 1, target
    for forbidden in ("model.safetensors", "config.json", "vocab.txt", "tokenizer.json", "../x"):
        with pytest.raises(FetchError) as raised:
            hf._assert_metadata_url(f"https://{HUB}/{ID}/resolve/{REV}/{forbidden}", ID, REV, policy())
        assert raised.value.code == "would_access_file"
    other = run({u["model_info"]: [(302, {"Location": f"https://{HUB}/api/models/other/model?blobs=true"}, b"")]}, proposed=None)[0]
    assert other["record"]["stopped"] == "identifier_differs"


@pytest.mark.parametrize("status", [401, 403])
def test_stop_6_the_api_requires_authentication(status):
    u = urls(None)
    result, transport = run({u["model_info"]: [(status, {}, b"")]})
    assert result["record"]["stopped"] == "authentication_required" and len(transport.requests) == 1 and transport.closed == 1


def test_stop_7_the_request_count_would_exceed_the_limit():
    for limit in (1, 2):
        result, transport = run(happy_table(), pol=policy(max_requests=limit))
        assert result["record"]["stopped"] == "request_limit" and len(transport.requests) == limit and result["record"]["requests_made"] == limit
    result, transport = run(happy_table(), pol=policy(max_requests=3))
    assert result["record"]["stopped"] is None and len(transport.requests) == 3


def test_a_stopped_record_has_no_later_fields_and_says_nothing_was_downloaded():
    u = urls(None)
    result, _ = run({u["model_info"]: [(401, {}, b"")]})
    record = result["record"]
    assert "files" not in record and "card" not in record and record["downloads"].startswith("none") and record["stopped"] == "authentication_required"
    assert "stopped: \"authentication_required\"" in render_markdown(record)


# ------------------------------------------------------------------------------------------------------------------------------- redirects, malformed answers, invalid input
def test_a_redirect_to_a_named_host_and_an_allowed_url_is_followed_and_recorded_and_a_loop_stops():
    u = urls(None)
    hop = {u["model_info"]: [(301, {"Location": u["model_info"]}, b""), (200, {}, info())], hf.metadata_urls(ID, REV, policy())["model_card"]: [(200, {}, CARD.encode())]}
    result, transport = run(hop, proposed=None)
    assert result["record"]["stopped"] is None and result["record"]["redirects"] == [{"kind": "model_info", "status": 301, "to_host": HUB}] and result["record"]["requests_made"] == 3
    assert run({u["model_info"]: [(302, {"Location": u["model_info"]}, b"")] * 6}, proposed=None)[0]["record"]["stopped"] == "redirect_limit"
    missing = run({u["model_info"]: [(302, {}, b"")]}, proposed=None)[0]
    assert missing["record"]["stopped"] == "redirect_without_location"


@pytest.mark.parametrize("body,code", [(b"not json", "malformed_response"), (b"[1, 2]", "malformed_response"), (info(sha="main"), "malformed_response"), (info(sha=None), "malformed_response"),
                                       (info(siblings="no"), "malformed_response"), (info(siblings=[{"rfilename": "../etc/passwd"}]), "malformed_response"),
                                       (info(siblings=[{"rfilename": "a b.txt"}]), "malformed_response"), pytest.param(b"x" * (hf.MAX_METADATA_BYTES + 1), "response_too_large", id="oversized")])
def test_malformed_or_oversized_answers_stop_the_query_with_a_fixed_code(body, code):
    u = urls(None)
    result, _ = run({u["model_info"]: [(200, {}, body)]}, proposed=None)
    assert result["record"]["stopped"] == code


def test_a_non_200_status_is_an_unexpected_status():
    u = urls(None)
    for status in (404, 500, 204):
        assert run({u["model_info"]: [(status, {}, b"")]}, proposed=None)[0]["record"]["stopped"] == "unexpected_status"


@pytest.mark.parametrize("identifier", ["", "model", "a/b/c", "../x/y", "a/..", "a b/c", "https://hub.test/a/b", "a/b?x=1", "a/b#f", "-a/b", "a\\b", "a/b/", "é/é"])
def test_an_invalid_identifier_is_refused_before_any_request(identifier):
    transport = Scripted({})
    with pytest.raises(FetchError) as raised:
        query_metadata(identifier, proposed_revision=None, provisional_licence=None, policy=policy(), transport=transport)
    assert raised.value.code == "invalid_identifier" and transport.requests == []


@pytest.mark.parametrize("revision", ["main", "v1.0", "0123456", REV.upper(), REV[:-1], REV + "0", "", "refs/pr/1"])
def test_a_floating_or_malformed_revision_is_refused_before_any_request(revision):
    transport = Scripted({})
    with pytest.raises(FetchError) as raised:
        query_metadata(ID, proposed_revision=revision, provisional_licence=None, policy=policy(), transport=transport)
    assert raised.value.code == "invalid_revision" and transport.requests == []


def test_the_policy_has_no_defaults_and_validates_every_field():
    with pytest.raises(TypeError):
        FetchPolicy(base_host=HUB)                                      # type: ignore[call-arg]
    for bad in (dict(base_host="other.test"), dict(allowed_hosts=()), dict(allowed_hosts=("https://hub.test",)), dict(max_requests=0), dict(max_requests=True), dict(timeout_seconds=0),
                dict(allow_loopback_http="yes"), dict(allowed_hosts=("HUB.test x",))):
        with pytest.raises(FetchError) as raised:
            policy(**bad)
        assert raised.value.code == "invalid_policy"


def test_plain_http_and_credentials_in_a_url_are_refused():
    for url in (f"http://{HUB}/x", f"https://user:pw@{HUB}/x", f"ftp://{HUB}/x", f"https://evil.test/x"):
        with pytest.raises(FetchError):
            hf._check_url(url, policy())
    assert hf._check_url("http://127.0.0.1:8080/x", policy(allowed_hosts=(HUB, "127.0.0.1:8080"), allow_loopback_http=True)).netloc == "127.0.0.1:8080"
    with pytest.raises(FetchError):
        hf._check_url("http://hub.test/x", policy(allow_loopback_http=True))                       # loopback http is for 127.0.0.1 / localhost only


# ------------------------------------------------------------------------------------------------------------------------------- the fetch step
def file_table(overrides: dict | None = None) -> tuple[dict, list[FileSpec]]:
    base = f"https://{HUB}/{ID}/resolve/{REV}"
    table = {f"{base}/model.safetensors": [(302, {"Location": f"https://{CDN}/blob/abc?sig=SECRETSIGNATURE"}, b"")], f"https://{CDN}/blob/abc?sig=SECRETSIGNATURE": [(200, {}, WEIGHTS)],
             f"{base}/vocab.txt": [(200, {}, VOCAB)], f"{base}/tokenizer_config.json": [(200, {}, TOKCONF)]}
    table.update(overrides or {})
    specs = [FileSpec("model.safetensors", sha(WEIGHTS), len(WEIGHTS)), FileSpec("vocab.txt", sha(VOCAB)), FileSpec("tokenizer_config.json", sha(TOKCONF), len(TOKCONF))]
    return table, specs


def fetch(tmp_path: Path, table: dict, specs: list[FileSpec], **over):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (tmp_path / "out").mkdir(exist_ok=True)
    transport = Scripted(table)
    kwargs = dict(policy=policy(), transport=transport, forbidden_root=repo, max_bytes_per_file=10_000)
    kwargs.update(over)
    destination = over.pop("destination", tmp_path / "out" / "model")
    kwargs.pop("destination", None)
    return fetch_files(ID, REV, specs, destination, **kwargs), transport, destination


def test_a_complete_fetch_writes_exactly_the_named_files_verifies_every_hash_and_returns_the_provenance(tmp_path):
    table, specs = file_table()
    provenance, transport, destination = fetch(tmp_path, table, specs)
    assert sorted(p.name for p in destination.iterdir()) == ["model.safetensors", "tokenizer_config.json", "vocab.txt"]
    assert (destination / "model.safetensors").read_bytes() == WEIGHTS and (destination / "vocab.txt").read_bytes() == VOCAB
    assert provenance["verified"] is True and provenance["identifier"] == ID and provenance["revision"] == REV
    assert provenance["files"] == [{"name": "model.safetensors", "size": 3000, "sha256": sha(WEIGHTS)}, {"name": "vocab.txt", "size": len(VOCAB), "sha256": sha(VOCAB)},
                                   {"name": "tokenizer_config.json", "size": len(TOKCONF), "sha256": sha(TOKCONF)}]
    assert provenance["hosts_contacted"] == [CDN, HUB] and provenance["requests_made"] == 4 == len(transport.requests)
    assert provenance["redirects"] == [{"kind": "file", "status": 302, "to_host": CDN}]
    assert "SECRETSIGNATURE" not in json.dumps(provenance)                                       # only the host of a redirect is recorded, never its signed url
    assert not list(destination.glob("*.part"))


def test_a_hash_mismatch_aborts_deletes_everything_it_created_and_touches_nothing_else(tmp_path):
    table, specs = file_table()
    specs[1] = FileSpec("vocab.txt", sha(b"something else"))
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FetchError) as raised:
        fetch(tmp_path, table, specs)
    assert raised.value.code == "hash_mismatch" and not (tmp_path / "out" / "model").exists() and (tmp_path / "out" / "keep.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("break_it,code", [("size", "size_mismatch"), ("big", "response_too_large"), ("status", "unexpected_status"), ("auth", "authentication_required"), ("host", "unapproved_host"),
                                           ("loop", "redirect_limit")])
def test_every_failure_rolls_back_the_destination(tmp_path, break_it, code):
    table, specs = file_table()
    base = f"https://{HUB}/{ID}/resolve/{REV}"
    if break_it == "size":
        specs[0] = FileSpec("model.safetensors", sha(WEIGHTS), len(WEIGHTS) + 1)
    elif break_it == "big":
        table[f"{base}/vocab.txt"] = [(200, {}, b"V" * 20_000)]
    elif break_it == "status":
        table[f"{base}/vocab.txt"] = [(500, {}, b"")]
    elif break_it == "auth":
        table[f"{base}/vocab.txt"] = [(401, {}, b"")]
    elif break_it == "host":
        table[f"{base}/vocab.txt"] = [(302, {"Location": "https://evil.test/vocab.txt"}, b"")]
    elif break_it == "loop":
        table[f"{base}/vocab.txt"] = [(302, {"Location": f"{base}/vocab.txt"}, b"")] * 6
    with pytest.raises(FetchError) as raised:
        fetch(tmp_path, table, specs)
    assert raised.value.code == code and not (tmp_path / "out" / "model").exists()


def test_the_request_budget_covers_redirects_and_a_breach_rolls_back(tmp_path):
    table, specs = file_table()
    with pytest.raises(FetchError) as raised:
        fetch(tmp_path, table, specs, policy=policy(max_requests=3))                           # the weights alone need two requests (the redirect), so the fourth is refused
    assert raised.value.code == "request_limit" and not (tmp_path / "out" / "model").exists()
    (tmp_path / "again").mkdir()
    provenance, transport, _ = fetch(tmp_path / "again", *file_table(), policy=policy(max_requests=4))
    assert provenance["requests_made"] == 4


@pytest.mark.parametrize("name", ["pytorch_model.bin", "model.pt", "model.pth", "model.pt2", "weights.pkl", "x.pickle", "tf_model.h5", "flax_model.msgpack", "training_args.bin", "model.ckpt", "model.onnx",
                                  "code.py", "archive.zip", "weights.npz", "MODEL.BIN"])
def test_pickle_capable_and_unknown_formats_are_refused_before_any_request(tmp_path, name):
    transport = Scripted({})
    (tmp_path / "repo").mkdir()
    (tmp_path / "out").mkdir()
    with pytest.raises(FetchError) as raised:
        fetch_files(ID, REV, [FileSpec(name, "0" * 64)], tmp_path / "out" / "model", policy=policy(), transport=transport, forbidden_root=tmp_path / "repo", max_bytes_per_file=10)
    assert raised.value.code == "forbidden_file_format" and transport.requests == [] and not (tmp_path / "out" / "model").exists()


@pytest.mark.parametrize("name,code", [("../x.txt", "invalid_file"), ("a/b.txt", "invalid_file"), ("a\\b.txt", "invalid_file"), ("", "invalid_file"), (".hidden.txt", "invalid_file"), ("noextension", "forbidden_file_format"),
                                       ("weights.safetensors.exe", "forbidden_file_format"), ("name with space.txt", "invalid_file")])
def test_invalid_file_names_are_refused_before_any_request(tmp_path, name, code):
    transport = Scripted({})
    (tmp_path / "repo").mkdir()
    (tmp_path / "out").mkdir()
    with pytest.raises(FetchError) as raised:
        fetch_files(ID, REV, [FileSpec(name, "0" * 64)], tmp_path / "out" / "model", policy=policy(), transport=transport, forbidden_root=tmp_path / "repo", max_bytes_per_file=10)
    assert raised.value.code == code and transport.requests == []


def test_a_missing_or_malformed_expected_hash_and_duplicate_names_are_refused_before_any_request(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "out").mkdir()
    for specs, code in (([FileSpec("vocab.txt", "")], "invalid_sha256"), ([FileSpec("vocab.txt", "A" * 64)], "invalid_sha256"), ([FileSpec("vocab.txt", "0" * 63)], "invalid_sha256"),
                        ([FileSpec("vocab.txt", "0" * 64), FileSpec("vocab.txt", "1" * 64)], "invalid_file"), ([], "invalid_file"), ([FileSpec("vocab.txt", "0" * 64, 0)], "invalid_file")):
        transport = Scripted({})
        with pytest.raises(FetchError) as raised:
            fetch_files(ID, REV, specs, tmp_path / "out" / "model", policy=policy(), transport=transport, forbidden_root=tmp_path / "repo", max_bytes_per_file=10)
        assert raised.value.code == code and transport.requests == []
    with pytest.raises(TypeError):
        FileSpec("vocab.txt")                                                                   # type: ignore[call-arg]  # there is no unverified download: the hash is required


@pytest.mark.parametrize("revision", ["main", "v1", REV.upper(), REV[:10], ""])
def test_the_fetch_step_refuses_a_floating_revision(tmp_path, revision):
    transport = Scripted({})
    (tmp_path / "repo").mkdir()
    (tmp_path / "out").mkdir()
    with pytest.raises(FetchError) as raised:
        fetch_files(ID, revision, [FileSpec("vocab.txt", "0" * 64)], tmp_path / "out" / "model", policy=policy(), transport=transport, forbidden_root=tmp_path / "repo", max_bytes_per_file=10)
    assert raised.value.code == "invalid_revision" and transport.requests == []


def test_the_destination_must_be_new_absolute_outside_the_repository_and_under_an_existing_parent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "out").mkdir()
    table, specs = file_table()
    with pytest.raises(FetchError) as raised:
        fetch_files(ID, REV, specs, tmp_path / "out", policy=policy(), transport=Scripted(table), forbidden_root=repo, max_bytes_per_file=10_000)
    assert raised.value.code == "destination_exists"
    for bad in (Path("relative/model"), repo / "model", repo, tmp_path / "missing_parent" / "model", tmp_path):
        transport = Scripted(table)
        with pytest.raises(FetchError) as raised:
            fetch_files(ID, REV, specs, bad, policy=policy(), transport=transport, forbidden_root=repo, max_bytes_per_file=10_000)
        assert raised.value.code in ("destination_not_allowed", "destination_exists") and transport.requests == [], bad
    (tmp_path / "out" / "taken").mkdir()
    with pytest.raises(FetchError) as raised:
        fetch_files(ID, REV, specs, tmp_path / "out" / "taken", policy=policy(), transport=Scripted(table), forbidden_root=repo, max_bytes_per_file=10_000)
    assert raised.value.code == "destination_exists" and (tmp_path / "out" / "taken").is_dir()           # an existing directory is never deleted


def test_the_listing_check_reports_an_unexpected_and_a_missing_file(tmp_path):
    folder = tmp_path / "d"
    folder.mkdir()
    (folder / "a.txt").write_text("a", encoding="utf-8")
    hf.verify_listing(folder, ["a.txt"])
    (folder / "extra.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FetchError) as unexpected:
        hf.verify_listing(folder, ["a.txt"])
    assert unexpected.value.code == "unexpected_file"
    (folder / "extra.txt").unlink()
    with pytest.raises(FetchError) as missing:
        hf.verify_listing(folder, ["a.txt", "b.txt"])
    assert missing.value.code == "missing_file"


def test_the_fetch_writes_nowhere_else_and_never_touches_a_cache_directory(tmp_path, monkeypatch):
    cache = tmp_path / "fake_hf_home"
    cache.mkdir()
    monkeypatch.setenv("HF_HOME", str(cache))
    monkeypatch.setenv("HOME", str(tmp_path / "fake_home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "fake_home"))
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    table, specs = file_table()
    fetch(tmp_path, table, specs)
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    new = [p for p in after if p not in before]
    assert all(p.startswith(("out/model", "out", "repo")) for p in new), new
    assert list(cache.iterdir()) == [] and not (tmp_path / "fake_home").exists()


def test_an_error_carries_only_its_fixed_code_never_a_url_or_content(tmp_path):
    table, specs = file_table({f"https://{HUB}/{ID}/resolve/{REV}/vocab.txt": [(302, {"Location": "https://evil.test/SECRETPATH?token=SECRETTOKEN"}, b"")]})
    with pytest.raises(FetchError) as raised:
        fetch(tmp_path, table, specs)
    assert str(raised.value) == raised.value.code == "unapproved_host" and "SECRET" not in repr(raised.value) and raised.value.code in hf.FETCH_CODES
    assert all(code == code.lower() and " " not in code for code in hf.FETCH_CODES)


# ------------------------------------------------------------------------------------------------------------------------------- the real transport, against a LOOPBACK server only
class Server:
    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, dict, bytes]] = {}
        self.log: list[tuple[str, dict]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:                                        # noqa: N802
                outer.log.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
                status, headers, body = outer.routes.get(self.path, (404, {}, b""))
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:                           # noqa: ANN002
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.netloc = f"127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def servers():
    hub, cdn = Server(), Server()
    yield hub, cdn
    hub.stop()
    cdn.stop()


def loopback_policy(hub: Server, cdn: Server, **over) -> FetchPolicy:
    return policy(base_host=hub.netloc, allowed_hosts=(hub.netloc, cdn.netloc), allow_loopback_http=True, **over)


def test_the_real_transport_returns_redirects_and_errors_as_responses_and_sends_nothing_but_a_fixed_user_agent(servers, monkeypatch):
    hub, cdn = servers
    hub.routes["/redirect"] = (302, {"Location": f"http://{cdn.netloc}/blob"}, b"")
    hub.routes["/missing-auth"] = (401, {}, b"")
    hub.routes["/ok"] = (200, {"X-Ignored": "1"}, b"hello")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")                 # a bogus proxy in the environment must be ignored
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    transport = UrllibTransport()
    redirect = transport.open(f"http://{hub.netloc}/redirect", timeout=5)
    assert redirect.status == 302 and redirect.headers["location"] == f"http://{cdn.netloc}/blob" and cdn.log == []             # the redirect was NOT followed
    assert transport.open(f"http://{hub.netloc}/missing-auth", timeout=5).status == 401
    ok = transport.open(f"http://{hub.netloc}/ok", timeout=5)
    assert ok.status == 200 and b"".join(ok.chunks) == b"hello"
    for _, headers in hub.log:
        assert headers.get("user-agent") == UrllibTransport.USER_AGENT and "authorization" not in headers and "cookie" not in headers and "proxy-authorization" not in headers


def test_the_real_transport_reports_a_refused_connection_as_a_fixed_code():
    transport = UrllibTransport()
    with pytest.raises(FetchError) as raised:
        transport.open("http://127.0.0.1:9/never", timeout=2)
    assert raised.value.code == "transport_failure"


def test_the_whole_metadata_query_and_the_whole_fetch_run_against_a_loopback_hub_with_the_real_transport(servers, tmp_path):
    hub, cdn = servers
    pol = loopback_policy(hub, cdn)
    hub.routes[f"/api/models/{ID}?blobs=true"] = (200, {}, info())
    hub.routes[f"/api/models/{ID}/revision/{REV}?blobs=true"] = (200, {}, info())
    hub.routes[f"/{ID}/raw/{REV}/README.md"] = (200, {}, CARD.encode())
    record = query_metadata(ID, proposed_revision=REV, provisional_licence="CC BY-NC-SA 4.0", policy=pol, transport=UrllibTransport())["record"]
    assert record["stopped"] is None and record["requests_made"] == 3 and record["hosts_contacted"] == [hub.netloc]
    assert [p for p, _ in hub.log] == [f"/api/models/{ID}?blobs=true", f"/api/models/{ID}/revision/{REV}?blobs=true", f"/{ID}/raw/{REV}/README.md"] and cdn.log == []
    base = f"/{ID}/resolve/{REV}"
    hub.routes[f"{base}/model.safetensors"] = (302, {"Location": f"http://{cdn.netloc}/blob/abc?sig=1"}, b"")
    cdn.routes["/blob/abc?sig=1"] = (200, {}, WEIGHTS)
    hub.routes[f"{base}/vocab.txt"] = (200, {}, VOCAB)
    (tmp_path / "repo").mkdir()
    (tmp_path / "out").mkdir()
    provenance = fetch_files(ID, REV, [FileSpec("model.safetensors", sha(WEIGHTS), len(WEIGHTS)), FileSpec("vocab.txt", sha(VOCAB))], tmp_path / "out" / "model", policy=pol, transport=UrllibTransport(),
                             forbidden_root=tmp_path / "repo", max_bytes_per_file=10_000)
    assert provenance["verified"] is True and sorted(provenance["hosts_contacted"]) == sorted([hub.netloc, cdn.netloc]) and provenance["requests_made"] == 3
    assert (tmp_path / "out" / "model" / "model.safetensors").read_bytes() == WEIGHTS
    assert {p for p, _ in hub.log + cdn.log}.isdisjoint({f"{base}/config.json", f"{base}/pytorch_model.bin"})


def test_a_loopback_redirect_to_an_unlisted_server_is_refused_before_it_is_contacted(servers, tmp_path):
    hub, cdn = servers
    third = Server()
    try:
        pol = loopback_policy(hub, cdn)
        hub.routes[f"/{ID}/resolve/{REV}/vocab.txt"] = (302, {"Location": f"http://{third.netloc}/vocab.txt"}, b"")
        third.routes["/vocab.txt"] = (200, {}, VOCAB)
        (tmp_path / "repo").mkdir()
        (tmp_path / "out").mkdir()
        with pytest.raises(FetchError) as raised:
            fetch_files(ID, REV, [FileSpec("vocab.txt", sha(VOCAB))], tmp_path / "out" / "model", policy=pol, transport=UrllibTransport(), forbidden_root=tmp_path / "repo", max_bytes_per_file=1000)
        assert raised.value.code == "unapproved_host" and third.log == [] and not (tmp_path / "out" / "model").exists()
    finally:
        third.stop()


# ------------------------------------------------------------------------------------------------------------------------------- the module itself
def test_the_module_is_standard_library_only_unlogged_hostless_and_unconnected_to_the_application():
    source = Path(hf.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported <= {"__future__", "hashlib", "json", "re", "shutil", "urllib.error", "urllib.parse", "urllib.request", "dataclasses", "pathlib", "typing", "wealthpilot.core.sentiment_model"}, imported
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {"print", "logging", "logger", "environ", "getenv", "socket", "HTTPCookieProcessor", "HTTPBasicAuthHandler", "HTTPPasswordMgr", "Authorization"} & names
    assert "huggingface.co" not in source.lower() and "hf.co" not in source.lower() and "https://" not in source.replace('"https"', "").replace("'https'", "").split('"""', 2)[2]      # no host is baked in code
    for other in ("training/sentiment/train_sentiment_transformer.py", "training/sentiment/evaluate_sentiment_model.py", "training/sentiment/frozen_evaluation.py", "backend/wealthpilot/api/main.py"):
        path = Path(hf.__file__).parents[2] / other
        assert "hub_fetch" not in path.read_text(encoding="utf-8"), other                                   # nothing imports it yet


def test_every_failure_code_is_a_fixed_lowercase_token_and_the_module_raises_only_known_codes():
    source = Path(hf.__file__).read_text(encoding="utf-8")
    import re

    raised = set(re.findall(r'FetchError\("([a-z_]+)"\)', source)) | set(re.findall(r'status_error: str = "([a-z_]+)"', source)) | {"identifier_differs", "would_access_file"}
    assert raised <= set(hf.FETCH_CODES), raised - set(hf.FETCH_CODES)


# ------------------------------------------------------------------------------------------------------------------------------- defence in depth (exercised directly)
def test_the_request_gate_itself_refuses_a_metadata_url_of_another_kind_even_if_a_caller_passes_one():
    transport = Scripted({})
    for forbidden in (f"https://{HUB}/{ID}/resolve/{REV}/config.json", f"https://{HUB}/{ID}/resolve/{REV}/model.safetensors", f"https://{HUB}/datasets/a/b", f"https://{HUB}/{ID}/raw/{REV}/vocab.txt"):
        with pytest.raises(FetchError) as raised:
            hf._open_checked(forbidden, policy(), transport, hf._Budget(5), set(), [], kind="model_info", identifier=ID, revision=REV, metadata=True)
        assert raised.value.code == "would_access_file" and transport.requests == [], forbidden


def test_a_stray_file_that_appears_in_the_destination_during_the_download_fails_the_fetch_and_rolls_back(tmp_path):
    table, specs = file_table()
    destination = tmp_path / "out" / "model"

    class Meddling(Scripted):
        def open(self, url, *, timeout):                                      # another process drops a file into the destination while the download runs
            if url.endswith("tokenizer_config.json"):
                (destination / "intruder.txt").write_text("x", encoding="utf-8")
            return super().open(url, timeout=timeout)

    (tmp_path / "repo").mkdir()
    (tmp_path / "out").mkdir()
    with pytest.raises(FetchError) as raised:
        fetch_files(ID, REV, specs, destination, policy=policy(), transport=Meddling(table), forbidden_root=tmp_path / "repo", max_bytes_per_file=10_000)
    assert raised.value.code == "unexpected_file" and not destination.exists()


# ------------------------------------------------------------------------------------------------------------------------------- a real listing contains a dot-file (found by the first real Phase 2 query, 2026-10-29)
def test_a_listing_with_the_dot_file_every_repository_has_is_accepted_and_traversal_names_are_still_refused():
    u = urls(None)
    listing = [*LISTING, {"rfilename": ".gitattributes", "size": 1477}]
    result, _ = run({u["model_info"]: [(200, {}, info(siblings=listing))]}, proposed=None)
    assert result["record"]["stopped"] is None or result["record"]["stopped"] != "malformed_response"
    assert ".gitattributes" in [f["name"] for f in result["record"]["files"]]
    for bad in ("..", ".", ".../x", "a/../b", "a/./b", "./a", ".", "..hidden", ".-x", "/.gitattributes", ".gitattributes/", "a//b"):
        refused, _ = run({u["model_info"]: [(200, {}, info(siblings=[{"rfilename": bad}]))]}, proposed=None)
        assert refused["record"]["stopped"] == "malformed_response", bad
    assert hf._LISTED_NAME.match(".gitattributes") and not hf._LISTED_NAME.match("..") and not hf._LISTED_NAME.match(".")
    assert not hf._FILE_NAME.match(".gitattributes")                                                        # but a dot-file is still never a file the fetch step may download
