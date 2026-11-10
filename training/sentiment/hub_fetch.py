"""Verified, read-only access to a model hub for the sentiment project (ADR-052): the metadata-only query tool (form item B9) and the verified fetch step (form item E1).

STATUS: BUILT AND TESTED OFFLINE ONLY (fake transports and a loopback server). It has never been run against a real hub, and running it needs the owner's approvals (a selected candidate, B2, A3.9 to
A3.13 for the query; the confirmed A3.1 to A3.13, D10 to D13, the cache location and E1 for the fetch). Nothing imports it from the application, the API, the trainer or the evaluation script.

Design rules, each enforced in code and tested:
- Standard library only (no `huggingface_hub`, `transformers` or `torch`). No logger, no `print`, no environment variable, no cookie, no token: the only header sent is a fixed `User-Agent`.
- Nothing is baked in: the permitted hosts, the request cap and the timeout come from an explicit `FetchPolicy` with no defaults. Proxies from the environment are ignored.
- Redirects are never followed by the transport. This module follows one only to a host the policy names, over HTTPS (HTTP only to loopback in tests), and only a bounded number of times.
- The metadata query requests exactly three kinds of URL for one identifier (the model's information record, the information record at one revision, the model card `README.md` at one revision) and
  nothing else: no weights, tokenizer files, `config.json`, datasets or training artifacts. Any other URL is refused before it is requested (`would_access_file`).
- The fetch step downloads exactly the named files at one immutable 40-character revision, refuses pickle-capable and unknown formats, streams each file with an incremental SHA-256, compares it with
  the expected value, checks the destination holds exactly the expected set, and on ANY failure deletes the directory it created. It writes nowhere else.
- Every failure is a `FetchError` carrying a fixed code and nothing else: never a URL, a header, a body or a path.
- The stored result is a sanitized record (no tokens, cookies, e-mail addresses or long digit runs); the model-card text is hashed and summarised, and returned only when the caller asks for it.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping, Protocol, Sequence

from wealthpilot.core.sentiment_model import is_commit_hash

SCHEMA = "hub_metadata_record_v1"
FETCH_CODES = (
    "request_limit", "unapproved_host", "insecure_scheme", "would_access_file", "authentication_required", "identifier_differs", "revision_differs", "licence_conflict", "unexpected_status",
    "redirect_limit", "redirect_without_location", "response_too_large", "malformed_response", "invalid_revision", "invalid_identifier", "invalid_file", "forbidden_file_format", "invalid_sha256",
    "destination_not_allowed", "destination_exists", "hash_mismatch", "size_mismatch", "unexpected_file", "missing_file", "transport_failure", "invalid_policy",
)
MAX_REDIRECTS = 3
MAX_METADATA_BYTES = 5_000_000
MAX_CARD_BYTES = 1_000_000
MAX_FILES_LISTED = 500
ALLOWED_FILE_EXTENSIONS = (".safetensors", ".json", ".txt", ".model")
FORBIDDEN_FILE_EXTENSIONS = (".bin", ".pt", ".pth", ".pt2", ".pkl", ".pickle", ".h5", ".msgpack", ".ckpt", ".onnx", ".npy", ".npz", ".joblib", ".zip", ".tar", ".gz", ".py")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")                                  # a file the fetch step may download: no leading dot
_LISTED_NAME = re.compile(r"^(?:\.(?=[A-Za-z0-9]))?[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")          # a name only LISTED by the metadata query: one optional leading dot (".gitattributes" is in almost every repository); "." and ".." never match
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HOST = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]{1,5})?$")
_MASKS = ((re.compile(r"\bhf_[A-Za-z0-9]{10,}\b"), "[token]"), (re.compile(r"\S+@\S+\.\S+"), "[email]"), (re.compile(r"(?:\d[ -]?){7,}"), "[number]"))
_LOOPBACK = ("127.0.0.1", "localhost")


class FetchError(RuntimeError):
    """A refusal or a failure. The message is the fixed code and nothing else (never a URL, header, body or path)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FetchPolicy:
    """Every limit is explicit: there is no default host, request cap or timeout. `allow_loopback_http` exists for tests against a local server and permits plain HTTP to 127.0.0.1 only."""

    base_host: str
    allowed_hosts: tuple[str, ...]
    max_requests: int
    timeout_seconds: float
    allow_loopback_http: bool

    def __post_init__(self) -> None:
        hosts = tuple(self.allowed_hosts)
        if not hosts or not all(isinstance(h, str) and _HOST.match(h) for h in hosts) or self.base_host not in hosts:
            raise FetchError("invalid_policy")
        if not (isinstance(self.max_requests, int) and not isinstance(self.max_requests, bool) and self.max_requests >= 1):
            raise FetchError("invalid_policy")
        if not (isinstance(self.timeout_seconds, (int, float)) and not isinstance(self.timeout_seconds, bool) and self.timeout_seconds > 0) or not isinstance(self.allow_loopback_http, bool):
            raise FetchError("invalid_policy")


@dataclass
class Response:
    status: int
    headers: Mapping[str, str]
    chunks: Iterator[bytes]
    close: Callable[[], None] = lambda: None          # releases the connection when the body is not read (a refusal, a redirect, a non-200)


class Transport(Protocol):
    def open(self, url: str, *, timeout: float) -> Response: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):      # type: ignore[no-untyped-def]  # never follow: a 3xx is returned to the caller, who applies the host policy
        return None


class UrllibTransport:
    """The real transport: GET only, no redirect following, no proxy from the environment, no cookie jar, no credential handler, one fixed User-Agent."""

    USER_AGENT = "wealthpilot-sentiment-fetch/1"

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def open(self, url: str, *, timeout: float) -> Response:
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "*/*"}, method="GET")
        try:
            raw = self._opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:        # 3xx / 4xx / 5xx are responses here
            raw = error
        except (urllib.error.URLError, OSError, ValueError):
            raise FetchError("transport_failure") from None
        status = getattr(raw, "status", None) or getattr(raw, "code", 0)
        headers = {key.lower(): value for key, value in raw.headers.items()}

        def chunks() -> Iterator[bytes]:
            try:
                while True:
                    block = raw.read(65536)
                    if not block:
                        break
                    yield block
            except OSError:
                raise FetchError("transport_failure") from None
            finally:
                raw.close()

        return Response(int(status), headers, chunks(), raw.close)


class _Budget:
    def __init__(self, limit: int) -> None:
        self.limit, self.used = limit, 0

    def spend(self) -> None:
        if self.used >= self.limit:
            raise FetchError("request_limit")
        self.used += 1


def _scheme(policy: FetchPolicy) -> str:
    return "http" if policy.allow_loopback_http else "https"


def _check_url(url: str, policy: FetchPolicy) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower()
    if "@" in host or not host or host not in policy.allowed_hosts:
        raise FetchError("unapproved_host")
    hostname = parts.hostname or ""
    if parts.scheme == "http":
        if not (policy.allow_loopback_http and hostname in _LOOPBACK):
            raise FetchError("insecure_scheme")
    elif parts.scheme != "https":
        raise FetchError("insecure_scheme")
    return parts


def _valid_identifier(identifier: object) -> str:
    if not (isinstance(identifier, str) and _IDENTIFIER.match(identifier)) or ".." in identifier:
        raise FetchError("invalid_identifier")
    return identifier


def _valid_revision(revision: object) -> str:
    if not is_commit_hash(revision):
        raise FetchError("invalid_revision")
    return revision


def metadata_urls(identifier: str, revision: str | None, policy: FetchPolicy) -> dict[str, str]:
    """The ONLY urls the metadata query may request, by kind. Nothing in the repository (weights, tokenizer files, configuration, datasets) is among them."""
    base = f"{_scheme(policy)}://{policy.base_host}"
    urls = {"model_info": f"{base}/api/models/{identifier}?blobs=true"}
    if revision is not None:
        urls["revision_info"] = f"{base}/api/models/{identifier}/revision/{revision}?blobs=true"
        urls["model_card"] = f"{base}/{identifier}/raw/{revision}/README.md"
    return urls


def _assert_metadata_url(url: str, identifier: str, revision: str | None, policy: FetchPolicy) -> None:
    if url not in set(metadata_urls(identifier, revision, policy).values()):
        raise FetchError("would_access_file")


def _read(response: Response, limit: int) -> bytes:
    body = bytearray()
    for block in response.chunks:
        body.extend(block)
        if len(body) > limit:
            raise FetchError("response_too_large")
    return bytes(body)


def _mask(text: str) -> str:
    for pattern, replacement in _MASKS:
        text = pattern.sub(replacement, text)
    return text


def _normal(licence: str) -> str:
    return re.sub(r"[\s_.-]+", "", licence.lower())


def _json(body: bytes) -> dict:
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise FetchError("malformed_response") from None
    if not isinstance(data, dict):
        raise FetchError("malformed_response")
    return data


def _open_checked(url: str, policy: FetchPolicy, transport: Transport, budget: _Budget, contacted: set[str], redirects: list[dict], *, kind: str, identifier: str, revision: str | None,
                  metadata: bool, status_error: str = "unexpected_status") -> Response:
    """One GET, following at most MAX_REDIRECTS redirects, each only to a host the policy names (and, for metadata, only to a URL of an allowed kind). Returns a 200 response; every other
    outcome raises a fixed code, and a response whose body is not going to be read is closed first."""
    hops = 0
    while True:
        _check_url(url, policy)
        if metadata:
            _assert_metadata_url(url, identifier, revision, policy)
        budget.spend()
        response = transport.open(url, timeout=policy.timeout_seconds)
        contacted.add(urllib.parse.urlsplit(url).netloc.lower())
        if response.status == 200:
            return response
        try:
            if response.status in (401, 403):
                raise FetchError("authentication_required")
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise FetchError("redirect_without_location")
                hops += 1
                if hops > MAX_REDIRECTS:
                    raise FetchError("redirect_limit")
                target = urllib.parse.urljoin(url, location)
                parts = _check_url(target, policy)                                     # an unapproved host or scheme stops here, before anything is requested
                redirects.append({"kind": kind, "status": response.status, "to_host": parts.netloc.lower()})
                if metadata and target not in set(metadata_urls(identifier, revision, policy).values()):
                    raise FetchError("identifier_differs" if parts.path.startswith("/api/models/") else "would_access_file")
                url = target
                continue
            raise FetchError(status_error)
        finally:
            response.close()


def query_metadata(identifier: str, *, proposed_revision: str | None, provisional_licence: str | None, policy: FetchPolicy, transport: Transport, keep_card_text: bool = False) -> dict:
    """The read-only, anonymous, metadata-only query (form items B1 to B10). Returns a sanitized record; `stopped` names the stop condition if one fired (the query stops at once, so later fields
    are absent), otherwise it is None. The model-card text is never in the record: when `keep_card_text` is true it is returned under `card_text` OUTSIDE the record, for the owner to read."""
    identifier = _valid_identifier(identifier)
    if proposed_revision is not None:
        proposed_revision = _valid_revision(proposed_revision)
    budget, contacted, redirects = _Budget(policy.max_requests), set(), []
    kinds: list[str] = []
    record: dict = {"schema": SCHEMA, "identifier": identifier, "proposed_revision": proposed_revision, "provisional_licence": provisional_licence, "stopped": None, "conflicts": [],
                    "downloads": "none: no weights, tokenizer files, config.json, datasets or training artifacts were requested"}
    card_text: str | None = None

    def finish() -> dict:
        record.update({"requests_made": budget.used, "hosts_contacted": sorted(contacted), "request_kinds": list(kinds), "redirects": list(redirects)})
        return {"record": record, "card_text": card_text}

    try:
        # 1. the model's information record
        kinds.append("model_info")
        response = _open_checked(metadata_urls(identifier, None, policy)["model_info"], policy, transport, budget, contacted, redirects, kind="model_info", identifier=identifier, revision=None,
                                 metadata=True)
        info = _json(_read(response, MAX_METADATA_BYTES))
        returned_id = info.get("id", info.get("modelId"))
        if returned_id != identifier:
            raise FetchError("identifier_differs")
        main_sha = info.get("sha")
        if not is_commit_hash(main_sha):
            raise FetchError("malformed_response")
        record["discovered_revision"] = main_sha
        verified = info
        verified_revision = main_sha
        # 2. the information record at the proposed immutable revision, when one was proposed
        if proposed_revision is not None:
            kinds.append("revision_info")
            response = _open_checked(metadata_urls(identifier, proposed_revision, policy)["revision_info"], policy, transport, budget, contacted, redirects, kind="revision_info",
                                     identifier=identifier, revision=proposed_revision, metadata=True, status_error="revision_differs")
            verified = _json(_read(response, MAX_METADATA_BYTES))
            if verified.get("id", verified.get("modelId")) != identifier:
                raise FetchError("identifier_differs")
            if verified.get("sha") != proposed_revision:
                raise FetchError("revision_differs")
            verified_revision = proposed_revision
        record["verified_revision"] = verified_revision
        # 3. licence metadata, the file listing and the other fields, from the record already read (no further request)
        card_data = verified.get("cardData") if isinstance(verified.get("cardData"), dict) else {}
        licences = card_data.get("license", [])
        licences = [licences] if isinstance(licences, str) else [x for x in licences if isinstance(x, str)] if isinstance(licences, list) else []
        licences += [t.split(":", 1)[1] for t in verified.get("tags", []) if isinstance(t, str) and t.startswith("license:")]
        record["license_ids"] = sorted({_mask(x)[:80] for x in licences})
        record["gated"] = verified.get("gated") if isinstance(verified.get("gated"), (bool, str)) else None
        record["library_name"] = _mask(str(verified.get("library_name", "")))[:60] or None
        record["pipeline_tag"] = _mask(str(verified.get("pipeline_tag", "")))[:60] or None
        record["tags"] = sorted({_mask(t)[:60] for t in verified.get("tags", []) if isinstance(t, str)})[:40]
        siblings = verified.get("siblings", [])
        if not isinstance(siblings, list) or len(siblings) > MAX_FILES_LISTED:
            raise FetchError("malformed_response")
        files = []
        for entry in siblings:
            name = entry.get("rfilename") if isinstance(entry, dict) else None
            parts = name.split("/") if isinstance(name, str) else []
            if not parts or len(parts) > 4 or not all(_LISTED_NAME.match(part) for part in parts):          # a file in a sub-folder is listed by name only; traversal and odd names are refused
                raise FetchError("malformed_response")
            lfs = entry.get("lfs") if isinstance(entry.get("lfs"), dict) else {}
            sha = lfs.get("sha256") if isinstance(lfs.get("sha256"), str) and _SHA256.match(lfs.get("sha256")) else None
            size = entry.get("size") if isinstance(entry.get("size"), int) and not isinstance(entry.get("size"), bool) else None
            files.append({"name": name, "size": size, "sha256": sha})
        record["files"] = sorted(files, key=lambda f: f["name"])
        record["pickle_capable_files"] = sorted(f["name"] for f in files if f["name"].lower().endswith(FORBIDDEN_FILE_EXTENSIONS))
        # the licence stop condition
        if provisional_licence is not None:
            if _normal(provisional_licence) not in {_normal(x) for x in licences}:
                record["conflicts"].append("licence")
                raise FetchError("licence_conflict")
        # 4. the model card at the verified revision
        kinds.append("model_card")
        response = _open_checked(metadata_urls(identifier, verified_revision, policy)["model_card"], policy, transport, budget, contacted, redirects, kind="model_card", identifier=identifier,
                                 revision=verified_revision, metadata=True)
        body = _read(response, MAX_CARD_BYTES)
        text = body.decode("utf-8", errors="replace")
        lines = text.splitlines()
        front: list[str] = []
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                front.append(_mask(line)[:200])
                if len(front) >= 60:
                    break
        headings = [_mask(line.strip())[:120] for line in lines if line.startswith("#")][:40]
        record["card"] = {"sha256": hashlib.sha256(body).hexdigest(), "characters": len(text), "front_matter": front, "headings": headings}
        if keep_card_text:
            card_text = text
    except FetchError as error:
        record["stopped"] = error.code
    return finish()


def render_markdown(record: Mapping[str, object]) -> str:
    """The sanitized record as text for the approval report. It never contains the model-card text, only its hash, size, front matter and headings."""
    lines = [f"### Hub metadata record (`{record['schema']}`) for `{record['identifier']}`", ""]
    for key in ("stopped", "conflicts", "proposed_revision", "discovered_revision", "verified_revision", "provisional_licence", "license_ids", "gated", "library_name", "pipeline_tag", "requests_made",
                "hosts_contacted", "request_kinds", "redirects", "pickle_capable_files", "downloads"):
        if key in record:
            lines.append(f"- {key}: {json.dumps(record[key], sort_keys=True)}")
    for file in record.get("files", []):                                                                # type: ignore[union-attr]
        lines.append(f"- file: {json.dumps(file, sort_keys=True)}")
    card = record.get("card")
    if isinstance(card, dict):
        lines.append(f"- model card: sha256 {card['sha256']}, {card['characters']} characters")
        lines += [f"  - front matter: {line}" for line in card["front_matter"]] + [f"  - heading: {line}" for line in card["headings"]]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class FileSpec:
    """One permitted file: a flat name, its expected SHA-256 (required: there is no unverified download) and, optionally, its exact size."""

    name: str
    sha256: str
    size: int | None = None


def _validate_files(files: Sequence[FileSpec]) -> None:
    if not files:
        raise FetchError("invalid_file")
    seen: set[str] = set()
    for spec in files:
        if not (isinstance(spec, FileSpec) and isinstance(spec.name, str) and _FILE_NAME.match(spec.name)) or spec.name in seen or ".." in spec.name:
            raise FetchError("invalid_file")
        seen.add(spec.name)
        lowered = spec.name.lower()
        if lowered.endswith(FORBIDDEN_FILE_EXTENSIONS) or not lowered.endswith(ALLOWED_FILE_EXTENSIONS):
            raise FetchError("forbidden_file_format")
        if not (isinstance(spec.sha256, str) and _SHA256.match(spec.sha256)):
            raise FetchError("invalid_sha256")
        if spec.size is not None and not (isinstance(spec.size, int) and not isinstance(spec.size, bool) and spec.size > 0):
            raise FetchError("invalid_file")


def _validate_destination(destination: Path, forbidden_root: Path) -> Path:
    if not isinstance(destination, Path) or not destination.is_absolute():
        raise FetchError("destination_not_allowed")
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink():
        raise FetchError("destination_not_allowed")
    target, root = parent.resolve() / destination.name, Path(forbidden_root).resolve()
    if target == root or root in target.parents or target in root.parents:
        raise FetchError("destination_not_allowed")
    if destination.exists() or destination.is_symlink():
        raise FetchError("destination_exists")
    return destination


def verify_listing(destination: Path, expected: Sequence[str]) -> None:
    """The destination holds exactly the expected files: a missing one and an extra one are both failures."""
    present = {p.name for p in Path(destination).iterdir()}
    if present - set(expected):
        raise FetchError("unexpected_file")
    if set(expected) - present:
        raise FetchError("missing_file")


def fetch_files(identifier: str, revision: str, files: Sequence[FileSpec], destination: Path, *, policy: FetchPolicy, transport: Transport, forbidden_root: Path, max_bytes_per_file: int) -> dict:
    """Download exactly `files` at `revision` into a NEW directory `destination`, verify every SHA-256, and return the provenance. On any failure the directory this call created is deleted and a
    `FetchError` is raised. Everything that can be refused is refused before the first request."""
    identifier, revision = _valid_identifier(identifier), _valid_revision(revision)
    _validate_files(files)
    if not (isinstance(max_bytes_per_file, int) and not isinstance(max_bytes_per_file, bool) and max_bytes_per_file > 0):
        raise FetchError("invalid_file")
    destination = _validate_destination(Path(destination), Path(forbidden_root))
    budget, contacted, redirects = _Budget(policy.max_requests), set(), []
    destination.mkdir()                                                                       # created here and nowhere else: the rollback removes exactly this directory
    provenance: list[dict] = []
    try:
        for spec in files:
            url = f"{_scheme(policy)}://{policy.base_host}/{identifier}/resolve/{revision}/{spec.name}"
            response = _open_checked(url, policy, transport, budget, contacted, redirects, kind="file", identifier=identifier, revision=revision, metadata=False)
            cap = spec.size if spec.size is not None else max_bytes_per_file
            digest, total, partial = hashlib.sha256(), 0, destination / (spec.name + ".part")
            with partial.open("wb") as handle:
                for block in response.chunks:
                    total += len(block)
                    if total > min(cap, max_bytes_per_file):
                        raise FetchError("response_too_large")
                    digest.update(block)
                    handle.write(block)
            if spec.size is not None and total != spec.size:
                raise FetchError("size_mismatch")
            if digest.hexdigest() != spec.sha256:
                raise FetchError("hash_mismatch")
            partial.rename(destination / spec.name)
            provenance.append({"name": spec.name, "size": total, "sha256": digest.hexdigest()})
        verify_listing(destination, [spec.name for spec in files])
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return {"identifier": identifier, "revision": revision, "files": provenance, "destination": str(destination), "requests_made": budget.used, "hosts_contacted": sorted(contacted),
            "redirects": list(redirects), "verified": True}
