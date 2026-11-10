"""Verification, lazy loading and CPU inference for ONE pretrained candidate (ADR-053; lifecycle hardened by ADR-055).

Locations: `models/sentiment_pretrained/<candidate key>/` only (no arbitrary path, no symlink). The directory must carry `pretrained_manifest.json` written by an operator after an explicit,
revision-pinned download that the owner approved; the manifest repeats the repository, the 40-character revision, the licence string and the SHA-256 of every file. Nothing is downloaded here,
at start-up or on a request. Weights must be `model.safetensors`; any pickle-capable file in the manifest refuses the artifact. Errors are fixed reason codes: no text, path or stack trace.

Lifecycle (ADR-055):
- A STATUS READ NEVER LOADS OR HASHES ANYTHING (`candidate_status` looks only at the cache, a lock, the failure memory and whether the weight file exists).
- Construction of a model never runs under the module lock: there is one lock PER candidate, taken without waiting; a concurrent request for a model that is being built is answered `loading`
  at once instead of queueing behind the build. The first request pays the build (about 3.6 s measured in B2.1); an operator may call `warm` beforehand. Nothing here runs at start-up.
- ANY unexpected exception (an `OSError` from a DLL, a `MemoryError`, a permission error on a file) becomes a fixed reason code. Nothing propagates to the production endpoint.
- After a timeout the adapter answers `timeout` immediately for the back-off window instead of queueing behind a call that may still be running.
- An optional thread cap (`ResearchConfig.threads`, unset by default; nothing is silently changed) is applied to torch once, when the backend is built.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.sentiment.normalization import ModelResult, label_order_from_id2label, result_from_logits, unavailable
from wealthpilot.core.sentiment.registry import FORMAT_SAFETENSORS, LICENCE_VERIFIED, PENDING, Candidate

PRETRAINED_ROOT = sm.ARTIFACT_ROOT.parent / "sentiment_pretrained"
MANIFEST_FILE = "pretrained_manifest.json"
MANIFEST_SCHEMA_VERSION = 1
REQUIRED_FILES = (sm.WEIGHTS_FILE, sm.CONFIG_FILE, sm.TOKENIZER_CONFIG_FILE)
FORBIDDEN_SUFFIXES = (".bin", ".pt", ".pth", ".pkl", ".pickle", ".ckpt", ".h5", ".msgpack", ".npy", ".npz", ".joblib")      # pickle-capable or framework checkpoints: never loaded
FAILURE_TTL_SECONDS = 30.0
MAX_THREADS = 64
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sentiment-research")          # one controlled inference worker


class ResearchUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ResearchConfig:
    enabled: bool = False
    max_tokens: int | None = None
    timeout_seconds: float = 5.0
    device: str = "cpu"
    threads: int | None = None          # None leaves torch's own default untouched


@dataclass(frozen=True)
class PretrainedInfo:
    directory: Path
    labels: tuple[str, ...]          # native labels in logit order, read from the model's own config.json
    tokenizer_length: int


class Backend:
    def predict(self, text: str) -> sm.BackendOutput: ...


BackendFactory = Callable[[PretrainedInfo, ResearchConfig], "Backend"]
_FIXED_REASONS = {"artifact_missing": "weights_missing", "path_not_allowed": "manifest_invalid", "artifact_corrupt": "artifact_corrupt", "dependencies_missing": "dependencies_missing",
                  "load_failed": "load_failed", "artifact_incompatible": "manifest_invalid", "invalid_configuration": "invalid_configuration"}


def _map_reason(exc: sm.ModelUnavailable) -> ResearchUnavailable:
    return ResearchUnavailable(_FIXED_REASONS.get(exc.reason, "load_failed"))


def _unexpected(exc: BaseException) -> str:
    """A fixed reason for an exception nothing anticipated. The exception itself, which can carry a path or the text, is never kept."""
    return "load_failed" if isinstance(exc, (OSError, MemoryError)) else "internal_error"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ResearchUnavailable("manifest_invalid") from None


def check_gates(candidate: Candidate) -> None:
    """The licence, weight-format and registration gates. They run before configuration is validated and before any file is touched."""
    if candidate.licence_status != LICENCE_VERIFIED:
        raise ResearchUnavailable("licence_not_verified")
    if candidate.format_status != FORMAT_SAFETENSORS:
        raise ResearchUnavailable("format_not_allowed")
    if not candidate.registered:
        raise ResearchUnavailable("registration_pending" if candidate.registration == PENDING else "no_candidate_approved")


def verify_pretrained(candidate: Candidate, root: Path = PRETRAINED_ROOT) -> PretrainedInfo:
    """Raises `ResearchUnavailable(reason)`; otherwise the verified directory, the native label order and the tokenizer length. The gates run FIRST, before any file is touched.
    This hashes every listed file (a few hundred MB): it runs once per process when a model is built and is NEVER called from a status read."""
    check_gates(candidate)
    try:
        directory = sm.resolve_artifact_directory(candidate.key, root)
    except sm.ModelUnavailable as exc:
        raise _map_reason(exc) from None
    manifest = _json(directory / MANIFEST_FILE)
    if not isinstance(manifest, dict) or manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ResearchUnavailable("manifest_invalid")
    if manifest.get("repository") != candidate.repository or manifest.get("weight_licence") != candidate.weight_licence:
        raise ResearchUnavailable("manifest_invalid")
    revision = manifest.get("revision")
    if not sm.is_commit_hash(revision) or revision != candidate.revision:
        raise ResearchUnavailable("revision_mismatch")                         # a floating or different revision is never loaded
    files, recorded = manifest.get("files"), manifest.get("manifest_sha256")
    if not isinstance(files, dict) or not all(name in files for name in REQUIRED_FILES) or not isinstance(recorded, str):
        raise ResearchUnavailable("manifest_invalid")
    if any(str(name).lower().endswith(FORBIDDEN_SUFFIXES) for name in files):
        raise ResearchUnavailable("format_not_allowed")
    for relative, expected in files.items():
        target = (directory / relative).resolve()
        if directory not in target.parents or not isinstance(expected, str):
            raise ResearchUnavailable("manifest_invalid")
        if not target.is_file() or _sha256(target) != expected:
            raise ResearchUnavailable("artifact_corrupt")
    if sm.manifest_sha256(files) != recorded:
        raise ResearchUnavailable("artifact_corrupt")
    config = _json(directory / sm.CONFIG_FILE)
    labels = label_order_from_id2label(config.get("id2label")) if isinstance(config, dict) else None
    if labels is None:
        raise ResearchUnavailable("label_unsupported")
    length = manifest.get("tokenizer_length")
    if isinstance(length, bool) or not isinstance(length, int) or length < 1:
        raise ResearchUnavailable("manifest_invalid")
    try:
        sm.check_tokenizer_fits_embeddings(length, config.get("vocab_size"))
    except sm.ModelUnavailable:
        raise ResearchUnavailable("manifest_invalid") from None
    return PretrainedInfo(directory, labels, length)


class PretrainedAdapter:
    """A verified candidate plus a backend. `classify` never raises and never returns text: any failure is an unavailable `ModelResult` with a fixed reason."""

    def __init__(self, candidate: Candidate, info: PretrainedInfo, backend: Backend, timeout_seconds: float) -> None:
        self.candidate, self.info, self._backend, self._timeout = candidate, info, backend, timeout_seconds
        self._breaker_until = 0.0

    def classify(self, text: str) -> ModelResult:
        c = self.candidate
        try:
            if time.monotonic() < self._breaker_until:
                return unavailable(c.key, c.repository, c.revision, "timeout", role=c.role)        # a previous call timed out and may still be running: do not queue behind it
            started = time.perf_counter()
            future = _EXECUTOR.submit(self._backend.predict, text)
            try:
                output = future.result(timeout=self._timeout)
            except FutureTimeout:
                future.cancel()
                self._breaker_until = time.monotonic() + FAILURE_TTL_SECONDS
                return unavailable(c.key, c.repository, c.revision, "timeout", role=c.role)
            except Exception:  # noqa: BLE001 -- a backend exception could carry the text; only a fixed code leaves
                return unavailable(c.key, c.repository, c.revision, "inference_failed", role=c.role)
            logits = list(output.logits) if isinstance(output, sm.BackendOutput) else None
            return result_from_logits(c.key, c.repository, c.revision, self.info.labels, logits, (time.perf_counter() - started) * 1000.0, role=c.role)
        except Exception:  # noqa: BLE001 -- nothing unexpected may reach the production endpoint
            return unavailable(c.key, c.repository, c.revision, "internal_error", role=c.role)


_LOCK = threading.Lock()                       # guards the dictionaries below ONLY; never held while a file is read or a model is built
_KEY_LOCKS: dict[tuple, threading.Lock] = {}   # one per candidate configuration; held while that model is being built
_CACHE: dict[tuple, PretrainedAdapter] = {}
_FAILURES: dict[tuple, tuple[float, str]] = {}


def _default_backend(info: PretrainedInfo, config: ResearchConfig) -> Backend:
    try:
        return sm.TransformersBackend(info.directory, max_tokens=int(config.max_tokens or 0), device=config.device, labels=info.labels, tokenizer_length=info.tokenizer_length,
                                      threads=config.threads)  # type: ignore[return-value]
    except sm.ModelUnavailable as exc:
        raise _map_reason(exc) from None


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
        _FAILURES.clear()
        _KEY_LOCKS.clear()


def _key(candidate: Candidate, config: ResearchConfig, root: Path, backend_factory: BackendFactory | None) -> tuple:
    return (candidate.key, config.max_tokens, config.device, config.threads, str(root), id(backend_factory))


def _config_problem(config: ResearchConfig) -> bool:
    bad_threads = config.threads is not None and (isinstance(config.threads, bool) or not isinstance(config.threads, int) or not 1 <= config.threads <= MAX_THREADS)
    return bool(not config.max_tokens or config.max_tokens < 1 or config.timeout_seconds <= 0 or config.device != "cpu" or bad_threads)


def load_adapter(candidate: Candidate, config: ResearchConfig, *, root: Path = PRETRAINED_ROOT, backend_factory: BackendFactory | None = None) -> PretrainedAdapter:
    """The cached, verified adapter, or `ResearchUnavailable(reason)`. Builds the model in the CALLER's thread, under a per-candidate lock taken without waiting: a second caller is told `loading`."""
    if not config.enabled:
        raise ResearchUnavailable("disabled")
    check_gates(candidate)
    key = _key(candidate, config, root, backend_factory)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        failed = _FAILURES.get(key)
        if failed is not None and time.monotonic() - failed[0] < FAILURE_TTL_SECONDS:
            raise ResearchUnavailable(failed[1])
        key_lock = _KEY_LOCKS.setdefault(key, threading.Lock())
    if not key_lock.acquire(blocking=False):
        raise ResearchUnavailable("loading")
    try:
        with _LOCK:
            if key in _CACHE:                                  # another thread finished between the check above and the lock
                return _CACHE[key]
        try:
            if _config_problem(config):
                raise ResearchUnavailable("invalid_configuration")
            info = verify_pretrained(candidate, root)
            if backend_factory is None and not sm.dependencies_available():
                raise ResearchUnavailable("dependencies_missing")
            adapter = PretrainedAdapter(candidate, info, (backend_factory or _default_backend)(info, config), config.timeout_seconds)
        except ResearchUnavailable as exc:
            with _LOCK:
                _FAILURES[key] = (time.monotonic(), exc.reason)
            raise
        except Exception as exc:  # noqa: BLE001 -- an OSError from a DLL, a MemoryError, a permission error: only a fixed code is kept
            reason = _unexpected(exc)
            with _LOCK:
                _FAILURES[key] = (time.monotonic(), reason)
            raise ResearchUnavailable(reason) from None
        with _LOCK:
            _CACHE[key] = adapter
        return adapter
    finally:
        key_lock.release()


def warm(candidate: Candidate, config: ResearchConfig, *, root: Path = PRETRAINED_ROOT, backend_factory: BackendFactory | None = None) -> str | None:
    """Explicit, operator-initiated load (never called at start-up or on a request). Returns None when the model is ready, otherwise the fixed reason."""
    try:
        load_adapter(candidate, config, root=root, backend_factory=backend_factory)
    except ResearchUnavailable as exc:
        return exc.reason
    return None


def classify_with(candidate: Candidate | None, config: ResearchConfig, text: str, *, role: str = "general", slot_reason: str = "no_candidate_approved", root: Path = PRETRAINED_ROOT,
                  backend_factory: BackendFactory | None = None) -> ModelResult:
    """Never raises. A slot with no registered candidate answers `slot_reason`; any failure of a candidate is a fixed reason."""
    if candidate is None:
        return unavailable("", "", "", slot_reason, role=role)
    try:
        return load_adapter(candidate, config, root=root, backend_factory=backend_factory).classify(text)
    except ResearchUnavailable as exc:
        return unavailable(candidate.key, candidate.repository, candidate.revision, exc.reason, role=candidate.role)
    except Exception:  # noqa: BLE001
        return unavailable(candidate.key, candidate.repository, candidate.revision, "internal_error", role=candidate.role)


@dataclass(frozen=True)
class CandidateStatus:
    """What the status endpoint reports per candidate. No path, no secret, no text. Built WITHOUT loading, hashing or verifying anything."""

    candidate: Candidate
    weights_present: bool
    loaded: bool
    availability: str          # disabled | blocked | weights_missing | not_loaded | loading | ready | unavailable
    reason: str | None


def candidate_status(candidate: Candidate, config: ResearchConfig, *, root: Path = PRETRAINED_ROOT) -> CandidateStatus:
    """A cheap, side-effect-free look: the cache, the per-candidate lock, the failure memory, and whether the weight file exists. It never loads a model and never hashes a file."""
    present = (root / candidate.key / sm.WEIGHTS_FILE).is_file()
    now = time.monotonic()
    with _LOCK:
        loaded = any(k[0] == candidate.key for k in _CACHE)
        loading = any(k[0] == candidate.key and lock.locked() for k, lock in _KEY_LOCKS.items())
        failure = next((reason for k, (stamp, reason) in _FAILURES.items() if k[0] == candidate.key and now - stamp < FAILURE_TTL_SECONDS), None)
    if not config.enabled:
        return CandidateStatus(candidate, present, loaded, "disabled", "disabled")
    try:
        check_gates(candidate)
    except ResearchUnavailable as exc:
        return CandidateStatus(candidate, present, loaded, "blocked", exc.reason)
    if loaded:
        return CandidateStatus(candidate, present, True, "ready", None)
    if loading:
        return CandidateStatus(candidate, present, False, "loading", "loading")
    if failure is not None:
        return CandidateStatus(candidate, present, False, "unavailable", failure)
    if _config_problem(config):
        return CandidateStatus(candidate, present, False, "unavailable", "invalid_configuration")
    if not present:
        return CandidateStatus(candidate, present, False, "weights_missing", "weights_missing")
    return CandidateStatus(candidate, present, False, "not_loaded", None)
