"""The dry run and the gated suggestion run. **Neither is executed in this build.**

``dry_run`` builds every request in memory and reports counts, estimates, the four approval bindings and *every*
unmet prerequisite. It never touches a provider.

``run_suggestions`` needs a gate-issued ``RunAuthorization`` (which cannot exist while the build lock is ``False`` and
no adapter is registered). It is sequential, resumable and idempotent: an item with a terminal record is never run
again, records are appended only after a call returns, and an interrupted call leaves the item pending.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from wealthpilot.data.gdelt.ai import SUGGESTION_SCHEMA
from wealthpilot.data.gdelt.ai.config import (
    ExperimentConfig,
    RunAuthorization,
    bindings,
    _overlap_lock_blockers,
    blockers,
    excluded_item_ids,
    is_gate_issued,
    protocol_partition,
)
from wealthpilot.data.gdelt.ai.fingerprints import itemset_fingerprint, sha256_text
from wealthpilot.data.gdelt.ai.prompt import build_request, estimate_tokens, prompt_sha256
from wealthpilot.data.gdelt.ai.provider import ExecutionBlocked, ProviderError, SuggestionProvider
from wealthpilot.data.gdelt.ai.retention import EXPIRABLE, NOT_COVERED
from wealthpilot.data.gdelt.ai.rubric import load_rubric
from wealthpilot.data.gdelt.ai.schema import SourceItem, load_items, validate_output
from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.output import atomic_write
from wealthpilot.data.gdelt.ai.store import (
    AuditLog,
    Layout,
    SuggestionStore,
    verified_overlap,
    load_snapshot_items,
    sha_file,
    source_overlap_ids,
    utc,
    verify_snapshot,
    write_valid_csv,
)
REDACTED = "[REDACTED]"


class _ExclusionGuard:
    """Wraps the provider. An excluded item can never be passed to it, whatever path built the request."""

    def __init__(self, inner: SuggestionProvider, excluded: frozenset[str]) -> None:
        self._inner, self._excluded, self.name = inner, excluded, inner.name

    def suggest(self, request):  # type: ignore[no-untyped-def]
        if request.item_id in self._excluded:
            raise ExecutionBlocked(f"{request.item_id} is excluded from provider submission; the request was refused")
        return self._inner.suggest(request)


def redact(text: str, secrets: list[str]) -> str:
    """Remove known secret values from text before it is stored or shown."""
    for s in secrets:
        if s and len(s) >= 4:
            text = text.replace(s, REDACTED)
    return text


# ---------------------------------------------------------------- dry run

def dry_run(cfg: ExperimentConfig, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Plan only. Reads the ORIGINAL annotation file (no labels) and builds prompts in memory. No provider, no network,
    nothing written."""
    src = cfg.source_review_files
    log = json.loads((src / "selection_log.json").read_text(encoding="utf-8"))["files_sha256"]
    items = load_items(src / "annotation_A.csv")
    overlap_sha = log.get("annotation_B.csv", "")
    itemset = itemset_fingerprint((i.item_id, i.fingerprint) for i in items)
    rubric = load_rubric(cfg.rubric_version)
    try:
        overlap: frozenset[str] | None = source_overlap_ids(src)
        overlap_problem = None
    except (GdeltToolError, OSError, ValueError, KeyError) as exc:
        overlap, overlap_problem = None, f"overlap membership could not be verified: {exc}"
    excluded = excluded_item_ids(cfg.provider_exclusion, cfg.blind_item_ids, overlap)
    sendable = [i for i in items if i.sendable and not (excluded and i.item_id in excluded)]
    in_tokens = 0
    for i in sendable:
        req = build_request(i, rubric, max_output_tokens=cfg.limits.max_output_tokens_per_request)
        in_tokens += estimate_tokens(req.system) + estimate_tokens(req.user)
    out_upper = len(sendable) * cfg.limits.max_output_tokens_per_request
    lim = cfg.limits
    cost = None
    if lim.unit_price_input_per_1k is not None and lim.unit_price_output_per_1k is not None:
        cost = (in_tokens / 1000) * lim.unit_price_input_per_1k + (out_upper / 1000) * lim.unit_price_output_per_1k
    problems = blockers(cfg, itemset_sha256=itemset, original_overlap_sha256=overlap_sha, confirm_ai_run=False, env=env,
                        overlap_item_ids=overlap)
    if overlap_problem:
        problems.append(overlap_problem)
    part = protocol_partition(cfg.provider_exclusion, cfg.blind_item_ids, overlap, frozenset(i.item_id for i in items))
    problems += [f"protocol groups: {m}" for m in part["problems"] if m not in " ".join(problems)]
    return {
        "mode": "dry_run", "provider_called": False, "data_sent": False, "files_written": False,
        "experiment_id": cfg.experiment_id, "protocol_id": cfg.protocol_id, "destination": str(cfg.destination),
        "items": len(items), "sendable_items": len(sendable), "provider_exclusion": cfg.provider_exclusion,
        "excluded_from_provider": None if excluded is None else len(excluded), "protocol_partition": part, "overlap_lock": {"configured": cfg.overlap_labels_sha256 is not None,
                                                               "problems": _overlap_lock_blockers(cfg)},
        "items_never_sent": [{"item_id": i.item_id, "problems": list(i.input_problems)} for i in items if not i.sendable],
        "historical_overlap_items": sum(i.historical_overlap for i in items), "blind_items": len(cfg.blind_item_ids),
        "prompt_version": cfg.prompt_version, "prompt_sha256": prompt_sha256(), "rubric_version": rubric.version,
        "rubric_sha256": rubric.sha256, "itemset_sha256": itemset, "temperature": cfg.temperature,
        "polarity_option": cfg.polarity_option,
        "retention": {"retention_days": cfg.retention_days, "enforced_for": list(EXPIRABLE),
                      "not_enforced_for": list(NOT_COVERED)},
        "approval_bindings_to_approve": bindings(cfg, itemset_sha256=itemset, original_overlap_sha256=overlap_sha,
                                                 overlap_item_ids=overlap),
        "estimates": {"input_tokens_estimated_chars_div_4": in_tokens, "output_tokens_upper_bound": out_upper,
                      "cost_upper_bound": cost, "currency": lim.currency,
                      "note": "ESTIMATED. No price is assumed: cost is shown only if you supplied unit prices."},
        "limits": {k: (list(v) if isinstance(v, tuple) else v) for k, v in lim.__dict__.items()},
        "unmet_prerequisites": problems,
    }


# ---------------------------------------------------------------- run

@dataclass
class RunResult:
    outcome: str
    counts: dict[str, int] = field(default_factory=dict)
    requests_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None


def _record(cfg: ExperimentConfig, run_id: str, item: SourceItem, attempt: int, rubric_sha: str, **extra: Any) -> dict[str, Any]:
    return {"schema": SUGGESTION_SCHEMA, "run_id": run_id, "item_id": item.item_id,
            "input_fingerprint": item.fingerprint, "attempt": attempt, "prompt_version": cfg.prompt_version,
            "prompt_sha256": prompt_sha256(), "rubric_version": cfg.rubric_version, "rubric_sha256": rubric_sha,
            "params": {"max_output_tokens": cfg.limits.max_output_tokens_per_request,
                       "timeout_seconds": cfg.timeout_seconds, "temperature": cfg.temperature},
            "terminal": False, **extra}


def _manifest_body(cfg: ExperimentConfig, auth: RunAuthorization, rubric_sha: str) -> dict[str, Any]:
    """The effective settings of a run. A resumed run must reproduce this exactly."""
    lim = cfg.limits
    return {"schema": "b2t_run_manifest_v1", "run_id": auth.run_id, "experiment_id": cfg.experiment_id,
            "provider": cfg.provider_name, "model_id": cfg.model_id, "model_version": cfg.model_version,
            "temperature": cfg.temperature, "max_output_tokens": lim.max_output_tokens_per_request,
            "timeout_seconds": cfg.timeout_seconds, "prompt_version": cfg.prompt_version,
            "prompt_sha256": prompt_sha256(), "rubric_version": cfg.rubric_version, "rubric_sha256": rubric_sha,
            "polarity_option": cfg.polarity_option, "overlap_labels_sha256": cfg.overlap_labels_sha256,
            "approval_bindings": dict(auth.bindings),
            "limits": {k: (list(v) if isinstance(v, tuple) else v) for k, v in lim.__dict__.items()}}


def _write_run_manifest(layout: Layout, body: dict[str, Any], now: datetime) -> str:
    """Create the run manifest, or verify that an existing one (a resumed run) is identical. Returns its SHA-256."""
    path = layout.run_manifest(body["run_id"])
    if path.exists():
        recorded = json.loads(path.read_text(encoding="utf-8"))
        recorded.pop("created_at_utc", None)
        if recorded != body:
            raise ExecutionBlocked("the run manifest of this run_id differs from the current settings; a resumed run "
                                   "must use identical settings (new settings need a new run_id and approval)")
        return sha_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps({**body, "created_at_utc": utc(now)}, indent=1, sort_keys=True).encode("utf-8"))
    os.chmod(path, 0o444)
    return sha_file(path)


def run_suggestions(cfg: ExperimentConfig, auth: RunAuthorization, provider: SuggestionProvider, *,
                    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                    sleep: Callable[[float], None] = lambda s: None,
                    env: Mapping[str, str] | None = None) -> RunResult:
    if not is_gate_issued(auth):
        raise ExecutionBlocked("no gate-issued authorization")
    env = os.environ if env is None else env
    layout = Layout(cfg.destination)
    verify_snapshot(cfg)
    items = load_snapshot_items(layout)
    overlap = verified_overlap(layout)                         # verified manifest, never inferred from IDs or order
    overlap_sha = sha_file(layout.snapshot / "annotation_B.csv")
    itemset = itemset_fingerprint((i.item_id, i.fingerprint) for i in items)
    if bindings(cfg, itemset_sha256=itemset, original_overlap_sha256=overlap_sha, overlap_item_ids=overlap) != auth.bindings:
        raise ExecutionBlocked("the configuration or the items changed after authorization")
    excluded = excluded_item_ids(cfg.provider_exclusion, cfg.blind_item_ids, overlap)
    if excluded is None:
        raise ExecutionBlocked("protocol.provider_exclusion is not set or the overlap membership is unverified")
    from wealthpilot.data.gdelt.overlap_lock import read_record
    lock, _why = read_record(cfg.source_review_files)
    if lock is None or lock["overlap_labels_sha256"] != cfg.overlap_labels_sha256:
        raise ExecutionBlocked("overlap-first control: the overlap-labels lock record is missing or does not match the "
                               "configured hash; no suggestion is generated before the human-only labels are locked")
    part = protocol_partition(cfg.provider_exclusion, cfg.blind_item_ids, overlap, frozenset(i.item_id for i in items))
    if part["problems"]:
        raise ExecutionBlocked("the protocol's item groups are inconsistent: " + "; ".join(part["problems"]))
    provider = _ExclusionGuard(provider, excluded)
    if getattr(provider, "name", None) != cfg.provider_name:
        raise ExecutionBlocked("the provider adapter does not match the approved provider")
    if cfg.temperature is None:
        raise ExecutionBlocked("provider.temperature is not set; no default is substituted")
    rubric = load_rubric(cfg.rubric_version)
    store, audit = SuggestionStore(layout), AuditLog(layout)
    stray = sorted({r["item_id"] for r in store.records() if r["item_id"] in excluded})
    if stray:                                                  # also verifies the hash chain before anything is appended
        raise ExecutionBlocked(f"suggestion records exist for excluded items {stray[:5]}: the store is contaminated "
                               "and the run is refused")
    manifest_sha = _write_run_manifest(layout, _manifest_body(cfg, auth, rubric.sha256), clock())
    secrets = [env[cfg.credentials_env_var]] if cfg.credentials_env_var and cfg.credentials_env_var in env else []
    lim, run_id = cfg.limits, auth.run_id
    result = RunResult("completed")
    terminal = store.terminal()
    pending = [i for i in items if i.sendable and i.item_id not in terminal and i.item_id not in excluded]
    audit.emit("run_started", now=clock(), run_id=run_id, experiment_id=cfg.experiment_id, sha256=manifest_sha,
               counts={"pending": len(pending), "already_terminal": len(terminal)})
    cost_so_far = 0.0

    def priced() -> bool:
        return lim.max_cost is not None and lim.unit_price_input_per_1k is not None

    def stop(reason: str, outcome: str) -> None:
        result.outcome, result.stop_reason = outcome, reason
        audit.emit("run_stopped", now=clock(), run_id=run_id, outcome=outcome, reason=reason)

    try:
        for item in pending:
            if (layout.root / "STOP").exists():
                stop("STOP file present", "stopped_by_user")
                break
            attempts_total = len(store.attempts_for(item.item_id))
            calls = reasks = 0
            reask = False
            while True:
                if item.item_id in excluded:                    # defence in depth: no retry or re-ask path can reach it
                    raise ExecutionBlocked(f"{item.item_id} is excluded from provider submission")
                req = build_request(item, rubric, max_output_tokens=lim.max_output_tokens_per_request, reask=reask,
                                    temperature=cfg.temperature)
                est_in = estimate_tokens(req.system) + estimate_tokens(req.user)
                if result.requests_used + 1 > (lim.max_requests or 0):
                    stop(f"request cap of {lim.max_requests} reached", "stopped_request_cap")
                    break
                if result.input_tokens + est_in > (lim.max_input_tokens or 0):
                    stop(f"input-token cap of {lim.max_input_tokens} would be exceeded", "stopped_token_cap")
                    break
                if priced():
                    projected = ((est_in / 1000) * (lim.unit_price_input_per_1k or 0)
                                 + (req.max_output_tokens / 1000) * (lim.unit_price_output_per_1k or 0))
                    if cost_so_far + projected > (lim.max_cost or 0):
                        stop(f"cost cap of {lim.max_cost} {lim.currency} would be exceeded", "stopped_cost_cap")
                        break
                result.requests_used += 1
                calls += 1
                attempts_total += 1
                started = clock()
                try:
                    resp = provider.suggest(req)
                except ProviderError as exc:
                    detail = redact(exc.detail, secrets)
                    last = calls >= lim.max_attempts_per_item or not exc.retryable
                    store.append(_record(cfg, run_id, item, attempts_total, rubric.sha256, status="provider_error",
                                         kind="reask" if reask else "call", started_at_utc=utc(started),
                                         finished_at_utc=utc(clock()), provider={"name": provider.name,
                                         "model_id": cfg.model_id, "model_version": cfg.model_version, "request_id": None},
                                         error={"kind": exc.kind, "retryable": exc.retryable, "detail": detail},
                                         terminal=last, **({"terminal_status": "failed"} if last else {})))
                    if last:
                        break
                    sleep(lim.backoff_seconds[min(calls - 1, len(lim.backoff_seconds) - 1)])
                    continue
                if resp.model_id != cfg.model_id:
                    store.append(_record(cfg, run_id, item, attempts_total, rubric.sha256, status="model_mismatch",
                                         kind="call", started_at_utc=utc(started), finished_at_utc=utc(clock()),
                                         provider={"name": provider.name, "model_id": resp.model_id,
                                                   "model_version": resp.model_version, "request_id": resp.request_id},
                                         error={"kind": "model_mismatch", "retryable": False,
                                                "detail": "served model differs from the approved model"}))
                    stop("the provider served a model other than the approved one", "stopped_model_mismatch")
                    raise ExecutionBlocked("the provider served a model other than the approved one")
                tin = resp.input_tokens if resp.input_tokens is not None else est_in
                tout = resp.output_tokens if resp.output_tokens is not None else estimate_tokens(resp.text)
                result.input_tokens += tin
                result.output_tokens += tout
                if priced():
                    cost_so_far += (tin / 1000) * (lim.unit_price_input_per_1k or 0) + (tout / 1000) * (lim.unit_price_output_per_1k or 0)
                v = validate_output(resp.text, item)
                common = dict(kind="reask" if reask else "call", started_at_utc=utc(started), finished_at_utc=utc(clock()),
                              provider={"name": provider.name, "model_id": resp.model_id,
                                        "model_version": resp.model_version, "request_id": resp.request_id},
                              tokens={"input": tin, "output": tout, "estimated": resp.input_tokens is None},
                              latency_ms=resp.latency_ms, raw_response=resp.text,
                              raw_response_sha256=sha256_text(resp.text), parsed=v.parsed,
                              validation={"ok": v.ok, "errors": list(v.errors), "flags": list(v.flags)})
                if v.ok:
                    store.append(_record(cfg, run_id, item, attempts_total, rubric.sha256, status="valid", terminal=True,
                                         terminal_status="valid", **common))
                    break
                last = reasks >= lim.max_reasks_per_item
                store.append(_record(cfg, run_id, item, attempts_total, rubric.sha256, status="invalid_output",
                                     terminal=last, **({"terminal_status": "invalid"} if last else {}), **common))
                if last:
                    break
                reasks += 1
                reask = True
            if result.outcome != "completed":
                break
    finally:
        write_valid_csv(layout, store)
    term = store.terminal()
    result.counts = {s: sum(1 for r in term.values() if r.get("terminal_status") == s) for s in ("valid", "invalid", "failed")}
    result.counts["pending"] = sum(1 for i in items if i.sendable and i.item_id not in term and i.item_id not in excluded)
    audit.emit("run_finished", now=clock(), run_id=run_id, outcome=result.outcome, counts=result.counts,
               requests_used=result.requests_used, tokens_in=result.input_tokens, tokens_out=result.output_tokens)
    return result
