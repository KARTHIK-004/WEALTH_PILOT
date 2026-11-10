"""Experiment configuration and the four approval gates. Fails closed.

**Gates** (each is a separate record, bound by SHA-256 to exactly what it approves):

- **A, methodology:** the protocol and the treatment of the original overlap set.
- **B, provider and model:** provider, model, prompt and rubric text, output schema.
- **C, data handling:** which fields may leave the machine, the destination and retention, and that the provider's
  data terms were reviewed.
- **D, execution:** this experiment, this exact item set, these limits.

A record is accepted only if its ``binds_sha256`` equals the hash computed from the *current* configuration. Changing
the model, a limit or the item set invalidates the matching gate, and approving one gate never satisfies another.

There is no "enabled" flag and no automatic acceptance policy: a config containing either is refused. The build lock
``AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD`` (``False``) and the absence of any provider adapter block execution
independently of this file.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from wealthpilot.data import gdelt as pkg
from wealthpilot.data.gdelt import ai as ai_pkg
from wealthpilot.data.gdelt.ai import provider as provider_mod
from wealthpilot.data.gdelt.ai.fingerprints import sha256_obj
from wealthpilot.data.gdelt.ai.prompt import PROMPT_VERSION, prompt_sha256
from wealthpilot.data.gdelt.ai.provider import ExecutionBlocked
from wealthpilot.data.gdelt.ai.rubric import load_rubric
from wealthpilot.data.gdelt.ai.schema import APPROVED_INPUT_FIELDS
from wealthpilot.data.gdelt.config import REPO_ROOT
from wealthpilot.data.gdelt.errors import ConfigError, GdeltToolError

GATES = ("A", "B", "C", "D")
GATE_NAMES = {"A": "methodology", "B": "provider and model", "C": "data handling", "D": "execution"}
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_PROVIDER_KEYS = {"name", "model_id", "model_version", "credentials_env_var", "timeout_seconds", "temperature"}
_PROTOCOL_KEYS = {"id", "blind_item_ids", "review_required_for_every_item", "polarity_option", "provider_exclusion",
                  "overlap_labels_sha256"}
# Which items may never be sent to a provider. UNSET blocks execution: the choice is the project owner's.
#   overlap_and_blind  every original overlap item (and so every blind item) is excluded
#   blind_only         only the designated blind items are excluded
#   none               nothing is excluded (an explicit choice, still bound by Gate A and Gate D)
EXCLUSION_MODES = ("overlap_and_blind", "blind_only", "none")
TEMPERATURE_MIN, TEMPERATURE_MAX = 0.0, 2.0   # provider-neutral outer bounds; an adapter must narrow them per model
POLARITY_OPTIONS = ("P1_required_as_in_existing_rubric",)   # the only one implemented; see the B2-U4 package section 6.2
_TOP = {"experiment_id", "description", "source", "destination", "protocol", "provider", "prompt", "limits",
        "data_handling", "approvals", "run_id"}


@dataclass(frozen=True)
class Approval:
    gate: str
    approved_by: str
    approved_on: date
    reference: str
    binds_sha256: str
    note: str = ""


@dataclass(frozen=True)
class Limits:
    max_requests: int | None = None
    max_attempts_per_item: int = 3
    max_reasks_per_item: int = 1
    backoff_seconds: tuple[float, ...] = (2.0, 4.0, 8.0)
    max_input_tokens: int | None = None
    max_output_tokens_per_request: int = 400
    max_cost: float | None = None
    currency: str | None = None
    unit_price_input_per_1k: float | None = None
    unit_price_output_per_1k: float | None = None


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    source_review_files: Path
    destination: Path
    protocol_id: str
    blind_item_ids: tuple[str, ...]
    provider_name: str | None
    model_id: str | None
    model_version: str | None
    credentials_env_var: str | None
    timeout_seconds: float
    prompt_version: str
    rubric_version: str
    limits: Limits
    provider_data_terms_reviewed: bool
    retention_days: int | None
    transmission_fields: tuple[str, ...]
    approvals: dict[str, Approval] = field(default_factory=dict)
    run_id: str | None = None
    source_path: Path | None = None
    temperature: float | None = None
    polarity_option: str | None = None
    provider_exclusion: str | None = None
    overlap_labels_sha256: str | None = None     # D13: verified hash of the completed human-only overlap labels


def protocol_partition(mode: str | None, blind_item_ids: Any, overlap_item_ids: frozenset[str] | None,
                       all_item_ids: frozenset[str]) -> dict[str, Any]:
    """The three item groups the protocol distinguishes, from VERIFIED membership only, plus every inconsistency.

    ``human_only_reference`` = original overlap items; ``blind`` = the designated blind subset (must be overlap items);
    ``ai_eligible`` = items that may be sent. ``matches_proposed_m2`` is true only for ``overlap_and_blind``, the proposed
    M2 design; it is a description, never an approval, and no mode is ever chosen here. Anything undeterminable or
    inconsistent is a problem and callers refuse to run.
    """
    blind = frozenset(blind_item_ids or ())
    problems: list[str] = []
    excluded = excluded_item_ids(mode, blind, overlap_item_ids)
    if mode is None:
        problems.append("protocol.provider_exclusion is not set")
    if overlap_item_ids is None:
        problems.append("the original overlap membership is not verified")
    if blind - all_item_ids:
        problems.append(f"protocol.blind_item_ids names items that are not in the dataset: {sorted(blind - all_item_ids)[:5]}")
    if overlap_item_ids is not None:
        if overlap_item_ids - all_item_ids:
            problems.append("the verified overlap names items that are not in the dataset")
        if blind - overlap_item_ids:
            problems.append("protocol.blind_item_ids must all be original overlap items")
    eligible = None if excluded is None else frozenset(all_item_ids - excluded)
    if mode == "overlap_and_blind" and eligible is not None and overlap_item_ids is not None             and (eligible & overlap_item_ids or eligible & blind):
        problems.append("an overlap or blind item is AI-eligible under overlap_and_blind (internal inconsistency)")
    return {"provider_exclusion": mode, "matches_proposed_m2": mode == "overlap_and_blind",
            "human_only_reference_items": None if overlap_item_ids is None else len(overlap_item_ids),
            "blind_items": len(blind), "ai_eligible_items": None if eligible is None else len(eligible),
            "ai_eligible_item_ids_sha256": None if eligible is None else sha256_obj(sorted(eligible)),
            "approved": False, "problems": problems}


def _find_forbidden(obj: Any, path: str = "") -> str | None:
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if isinstance(k, str) and re.search(r"auto[_-]?(accept|approve)|^enabled$|^execute$", k, re.I):
                return f"{path}/{k}"
            hit = _find_forbidden(v, f"{path}/{k}")
            if hit:
                return hit
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hit = _find_forbidden(v, f"{path}[{i}]")
            if hit:
                return hit
    return None


def _temperature(raw: Any) -> float | None:
    """``None`` stays ``None`` (the config is incomplete and execution is blocked). Anything else must be a real number
    inside the provider-neutral bounds: nothing is clamped, rounded or defaulted."""
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ConfigError("provider.temperature must be a number")
    value = float(raw)
    if not math.isfinite(value) or not TEMPERATURE_MIN <= value <= TEMPERATURE_MAX:
        raise ConfigError(f"provider.temperature {raw!r} is outside {TEMPERATURE_MIN} to {TEMPERATURE_MAX}; "
                          "it is rejected, never adjusted")
    return value


def _lock_hash(raw: Any) -> str | None:
    """``None`` stays ``None`` (incomplete: execution is blocked). Anything else must be a 64-hex hash, never coerced."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not _SHA_RE.match(raw):
        raise ConfigError("protocol.overlap_labels_sha256 must be the 64-hex hash in the overlap-labels lock record, in quotes")
    return raw


def _exclusion(raw: Any) -> str | None:
    if raw is None:
        return None
    if raw not in EXCLUSION_MODES:
        raise ConfigError(f"protocol.provider_exclusion {raw!r} is not one of {list(EXCLUSION_MODES)}")
    return str(raw)


def excluded_item_ids(mode: str | None, blind_item_ids: Any, overlap_item_ids: frozenset[str] | None) -> frozenset[str] | None:
    """The items that must never reach a provider, from VERIFIED membership only. ``None`` means it cannot be
    determined (mode unset, or the overlap membership was not verified): callers must treat that as blocked."""
    blind = frozenset(blind_item_ids or ())
    if mode == "none":
        return frozenset()
    if mode == "blind_only":
        return blind
    if mode == "overlap_and_blind":
        return None if overlap_item_ids is None else frozenset(overlap_item_ids) | blind
    return None


def _polarity_option(raw: Any) -> str | None:
    if raw is None:
        return None
    if raw not in POLARITY_OPTIONS:
        raise ConfigError(f"protocol.polarity_option {raw!r} is not implemented. Only {list(POLARITY_OPTIONS)} exists; "
                          "any other polarity policy is a separate, approved change")
    return str(raw)


def _p(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def _approval(gate: str, raw: Any) -> Approval | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"approval {gate} must be a record or null")
    extra = set(raw) - {"approved", "approved_by", "approved_on", "reference", "binds_sha256", "note"}
    if extra:
        raise ConfigError(f"approval {gate}: unknown keys {sorted(extra)}")
    if raw.get("approved") is not True:             # only the YAML boolean true counts
        return None
    by, on, ref, binds = raw.get("approved_by"), raw.get("approved_on"), raw.get("reference"), raw.get("binds_sha256")
    if not isinstance(by, str) or not by.strip() or "@" in by:
        raise ConfigError(f"approval {gate}: approved_by must be initials or a name (no email)")
    if not isinstance(on, date):
        raise ConfigError(f"approval {gate}: approved_on must be a YYYY-MM-DD date")
    if not isinstance(ref, str) or not ref.strip():
        raise ConfigError(f"approval {gate}: reference is required")
    if not isinstance(binds, str) or not _SHA_RE.match(binds):
        raise ConfigError(f"approval {gate}: binds_sha256 must be the 64-hex hash shown by the dry run, in quotes")
    return Approval(gate, by.strip(), on, ref.strip(), binds, str(raw.get("note", "")))


def load_experiment(path: Path) -> ExperimentConfig:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read experiment config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("experiment config must be a mapping")
    hit = _find_forbidden(raw)
    if hit:
        raise ConfigError(f"{hit}: automatic acceptance and 'enabled' flags are not part of this design and are refused")
    if set(raw) - _TOP:
        raise ConfigError(f"unknown config keys: {sorted(set(raw) - _TOP)}")
    proto = raw.get("protocol") or {}
    if not isinstance(proto, dict) or set(proto) - _PROTOCOL_KEYS:
        raise ConfigError(f"unknown protocol keys: {sorted(set(proto) - _PROTOCOL_KEYS) if isinstance(proto, dict) else proto}")
    if proto.get("review_required_for_every_item", True) is not True:
        raise ConfigError("every item must be human-reviewed: review_required_for_every_item cannot be false")
    prov, prompt = raw.get("provider") or {}, raw.get("prompt") or {}
    if not isinstance(prov, dict) or set(prov) - _PROVIDER_KEYS:
        raise ConfigError(f"unknown provider keys: {sorted(set(prov) - _PROVIDER_KEYS) if isinstance(prov, dict) else prov}")
    lim, dh = raw.get("limits") or {}, raw.get("data_handling") or {}
    src = raw.get("source") or {}
    if not raw.get("experiment_id") or not src.get("review_files") or not raw.get("destination"):
        raise ConfigError("experiment_id, source.review_files and destination are required")
    env = prov.get("credentials_env_var")
    if env is not None and not (isinstance(env, str) and _ENV_NAME_RE.match(env)):
        raise ConfigError("provider.credentials_env_var must be the NAME of an environment variable, never a secret")
    try:
        limits = Limits(**{**Limits().__dict__, **{k: (tuple(v) if k == "backoff_seconds" else v) for k, v in lim.items()}})
    except TypeError as exc:
        raise ConfigError(f"unknown limit keys: {exc}") from exc
    approvals_raw = raw.get("approvals") or {}
    if set(approvals_raw) - set(GATES):
        raise ConfigError(f"approvals may only be {list(GATES)}")
    approvals = {g: a for g in GATES if (a := _approval(g, approvals_raw.get(g))) is not None}
    return ExperimentConfig(
        experiment_id=str(raw["experiment_id"]), source_review_files=_p(src["review_files"]),
        destination=_p(raw["destination"]), protocol_id=str(proto.get("id", "")),
        blind_item_ids=tuple(sorted(proto.get("blind_item_ids") or ())),
        provider_name=prov.get("name"), model_id=prov.get("model_id"), model_version=prov.get("model_version"),
        credentials_env_var=env, timeout_seconds=float(prov.get("timeout_seconds", 60)),
        prompt_version=str(prompt.get("version", PROMPT_VERSION)),
        rubric_version=str(prompt.get("rubric_version", "b2t_rubric_v1")), limits=limits,
        provider_data_terms_reviewed=dh.get("provider_data_terms_reviewed") is True,
        retention_days=dh.get("retention_days"),
        transmission_fields=tuple(dh.get("external_transmission_fields") or ()), approvals=approvals,
        run_id=raw.get("run_id"), source_path=Path(path), temperature=_temperature(prov.get("temperature")),
        polarity_option=_polarity_option(proto.get("polarity_option")),
        provider_exclusion=_exclusion(proto.get("provider_exclusion")),
        overlap_labels_sha256=_lock_hash(proto.get("overlap_labels_sha256")))


def bindings(cfg: ExperimentConfig, *, itemset_sha256: str, original_overlap_sha256: str,
             overlap_item_ids: frozenset[str] | None = None) -> dict[str, str]:
    """The hash each gate must bind. The dry run prints these so you approve exactly what you saw."""
    rubric = load_rubric(cfg.rubric_version)
    lim = cfg.limits
    excluded = excluded_item_ids(cfg.provider_exclusion, cfg.blind_item_ids, overlap_item_ids)
    excluded_sha = "UNVERIFIED" if excluded is None else sha256_obj(sorted(excluded))   # never equals an approved hash
    return {
        "A": sha256_obj({"experiment_id": cfg.experiment_id, "protocol_id": cfg.protocol_id,
                         "blind_item_ids": list(cfg.blind_item_ids), "review_required_for_every_item": True,
                         "polarity_option": cfg.polarity_option, "provider_exclusion": cfg.provider_exclusion,
                         "original_overlap_sha256": original_overlap_sha256}),
        "B": sha256_obj({"provider": cfg.provider_name, "model_id": cfg.model_id, "model_version": cfg.model_version,
                         "temperature": cfg.temperature,
                         "credentials_env_var": cfg.credentials_env_var, "prompt_version": cfg.prompt_version,
                         "prompt_sha256": prompt_sha256(), "rubric_version": rubric.version,
                         "rubric_sha256": rubric.sha256, "output_version": ai_pkg.OUTPUT_VERSION}),
        "C": sha256_obj({"transmission_fields": list(cfg.transmission_fields), "destination": str(cfg.destination),
                         "retention_days": cfg.retention_days,
                         "provider_data_terms_reviewed": cfg.provider_data_terms_reviewed}),
        "D": sha256_obj({"experiment_id": cfg.experiment_id, "itemset_sha256": itemset_sha256, "run_id": cfg.run_id,
                         "provider_excluded_item_ids_sha256": excluded_sha,
                         "overlap_labels_sha256": cfg.overlap_labels_sha256,
                         "limits": {k: (list(v) if isinstance(v, tuple) else v) for k, v in lim.__dict__.items()}}),
    }


def _overlap_lock_blockers(cfg: ExperimentConfig) -> list[str]:
    """D13, overlap first: the verified hash of the completed 312 human-only labels must be set in the config (and so in
    Gate D) and must equal the lock record's. Only the record is read, never a label."""
    if cfg.overlap_labels_sha256 is None:
        return ["protocol.overlap_labels_sha256 is not set: the completed human-only overlap labels must be locked first "
                "(`annotate lock-overlap`), and their hash bound into Gate D"]
    from wealthpilot.data.gdelt.overlap_lock import read_record
    rec, why = read_record(cfg.source_review_files)
    if rec is None:
        return [f"overlap-first control: {why}"]
    if rec["overlap_labels_sha256"] != cfg.overlap_labels_sha256:
        return ["overlap-first control: protocol.overlap_labels_sha256 differs from the lock record's hash"]
    return []


def blockers(cfg: ExperimentConfig, *, itemset_sha256: str, original_overlap_sha256: str,
             confirm_ai_run: bool = False, env: Mapping[str, str] | None = None,
             overlap_item_ids: frozenset[str] | None = None) -> list[str]:
    """Every prerequisite that is missing, all listed (not just the first)."""
    env = os.environ if env is None else env
    out: list[str] = []
    if not pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD:
        out.append("build lock: AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False (a reviewed code change lifts it)")
    if not confirm_ai_run:
        out.append("the explicit --confirm-ai-run flag was not given")
    if not cfg.protocol_id:
        out.append("protocol.id is not set")
    if not (cfg.provider_name and cfg.model_id and cfg.model_version):
        out.append("provider.name, model_id and model_version are not all set (approval Gate B)")
    elif cfg.provider_name not in provider_mod.ADAPTERS:
        out.append(f"no adapter exists for provider {cfg.provider_name!r}; none is registered in this build")
    if cfg.provider_exclusion is None:
        out.append("protocol.provider_exclusion is not set: whether overlap or blind items may be sent to a provider "
                   "is the project owner's decision")
    elif cfg.provider_exclusion == "overlap_and_blind" and overlap_item_ids is None:
        out.append("the original overlap membership could not be verified, so the excluded set is unknown")
    if overlap_item_ids is not None and set(cfg.blind_item_ids) - set(overlap_item_ids):
        out.append("protocol.blind_item_ids must all be original overlap items")
    out += _overlap_lock_blockers(cfg)
    if cfg.temperature is None:
        out.append("provider.temperature is not set (approval Gate B); no default is substituted")
    if cfg.polarity_option is None:
        out.append("protocol.polarity_option is not recorded: the polarity decision is yours "
                   "(approval package B2-U4 section 6.2)")
    if not cfg.credentials_env_var:
        out.append("provider.credentials_env_var is not set")
    elif cfg.credentials_env_var not in env:
        out.append(f"environment variable {cfg.credentials_env_var} is not set (its value is never read here)")
    lim = cfg.limits
    if not (isinstance(lim.max_requests, int) and lim.max_requests > 0):
        out.append("limits.max_requests must be set to a positive integer")
    if not (isinstance(lim.max_input_tokens, int) and lim.max_input_tokens > 0):
        out.append("limits.max_input_tokens must be set to a positive integer")
    if lim.max_cost is not None and not (lim.currency and lim.unit_price_input_per_1k is not None
                                         and lim.unit_price_output_per_1k is not None):
        out.append("limits.max_cost needs currency and both unit prices (approved pricing); no price is assumed")
    if not (1 <= lim.max_attempts_per_item <= 5 and 0 <= lim.max_reasks_per_item <= 1):
        out.append("limits.max_attempts_per_item must be 1-5 and max_reasks_per_item 0-1")
    if cfg.transmission_fields != APPROVED_INPUT_FIELDS:
        out.append(f"data_handling.external_transmission_fields must be exactly {list(APPROVED_INPUT_FIELDS)}")
    if not cfg.provider_data_terms_reviewed:
        out.append("data_handling.provider_data_terms_reviewed is not true")
    if not (isinstance(cfg.retention_days, int) and cfg.retention_days > 0):
        out.append("data_handling.retention_days is not set")
    if not cfg.run_id:
        out.append("run_id is not set")
    elif not isinstance(cfg.run_id, str) or not _RUN_ID_RE.match(cfg.run_id):
        out.append("run_id must be 1-64 letters, digits, '.', '_' or '-' (it names a file)")
    try:
        expected = bindings(cfg, itemset_sha256=itemset_sha256, original_overlap_sha256=original_overlap_sha256,
                            overlap_item_ids=overlap_item_ids)
    except GdeltToolError as exc:
        return out + [f"rubric: {exc.reason}"]
    for g in GATES:
        a = cfg.approvals.get(g)
        if a is None:
            out.append(f"gate {g} ({GATE_NAMES[g]}) has no approval record")
        elif a.binds_sha256 != expected[g]:
            out.append(f"gate {g} ({GATE_NAMES[g]}) approval is bound to different content than the current "
                       "configuration; re-run the dry run and approve what it shows")
    return out


@dataclass(frozen=True)
class RunAuthorization:
    experiment_id: str
    run_id: str
    bindings: dict[str, str]
    _issued_by_gate: object = field(repr=False, compare=False, default=None)


_GATE_TOKEN = object()


def is_gate_issued(auth: RunAuthorization) -> bool:
    return auth._issued_by_gate is _GATE_TOKEN


def authorize_run(cfg: ExperimentConfig, *, itemset_sha256: str, original_overlap_sha256: str,
                  confirm_ai_run: bool, env: Mapping[str, str] | None = None,
                  overlap_item_ids: frozenset[str] | None = None) -> RunAuthorization:
    """Raises ``ExecutionBlocked`` listing every missing prerequisite; returns an authorization only if none is missing."""
    problems = blockers(cfg, itemset_sha256=itemset_sha256, original_overlap_sha256=original_overlap_sha256,
                        confirm_ai_run=confirm_ai_run, env=env, overlap_item_ids=overlap_item_ids)
    if problems:
        raise ExecutionBlocked(f"AI execution is blocked ({len(problems)} unmet prerequisites)", tuple(problems))
    b = bindings(cfg, itemset_sha256=itemset_sha256, original_overlap_sha256=original_overlap_sha256,
                 overlap_item_ids=overlap_item_ids)
    return RunAuthorization(cfg.experiment_id, str(cfg.run_id), b, _GATE_TOKEN)
