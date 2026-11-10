"""Run configuration, hard limits and approval gates.

Modes:

- ``dry_run``: offline checks only. Always allowed; never touches the network.
- ``dev_sample``: the 192 pre-registered development batches. Allowed only with a complete, explicit
  approval record written by the user in the local run config, an explicit command-line
  confirmation, limits within the B2-J ceilings, and an allowance at least as large as the cap.
- ``confirmation_sample``: additionally needs a valid trigger record (``sample.py``) and its own
  approval record.
- ``full_acquisition``: always refused. No configuration value can enable it in this build.

Nothing is inferred: a missing config, a missing section, a default value, a ``true`` without the
required fields, or an example file never counts as approval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from wealthpilot.data.gdelt import (
    CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD,
    DEV_SAMPLE_ENABLED_IN_THIS_BUILD,
)
from wealthpilot.data.gdelt.errors import ApprovalRefused, ConfigError

MODES = ("dry_run", "dev_sample", "confirmation_sample", "full_acquisition")
APPROVAL_REFERENCE = "reports/phaseB2J_development_sample_approval_checklist.md"

# gdelt/ -> data/ -> wealthpilot/ -> backend/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "datasets" / "raw" / "gdelt" / "english_gkg_v1"


@dataclass(frozen=True)
class Limits:
    """Hard limits. B2-J proposals; a config may tighten them, never relax them."""

    max_planned_bytes: int = 1_300_000_000        # header-reported total before any download
    max_total_bytes: int = 1_500_000_000          # every byte received, retries included
    max_requests: int = 1_200                     # every request, retries included
    max_concurrency: int = 1
    parallel_enabled: bool = False
    min_free_bytes_preflight: int = 20_000_000_000
    min_free_bytes_runtime: int = 10_000_000_000
    max_tmp_bytes: int = 500_000_000
    max_body_bytes: int = 100_000_000
    max_uncompressed_bytes: int = 400_000_000
    max_expansion_ratio: float = 10.0
    max_line_bytes: int = 8 * 1024 * 1024
    max_attempts: int = 5
    backoff_seconds: tuple[float, ...] = (4.0, 8.0, 16.0, 32.0, 64.0)
    retry_after_cap_seconds: float = 300.0
    max_redownloads: int = 1
    absence_check_spacing_seconds: int = 3_900
    fresh_max_age_seconds: int = 60
    max_head_per_slot: int = 3
    connect_timeout_seconds: float = 15.0
    read_timeout_seconds: float = 60.0
    max_clock_skew_seconds: int = 300

    # direction in which each numeric limit may move: "max" limits may only decrease,
    # "min" limits may only increase.
    _CEILINGS = ("max_planned_bytes", "max_total_bytes", "max_requests", "max_concurrency", "max_tmp_bytes",
                 "max_body_bytes", "max_uncompressed_bytes", "max_expansion_ratio", "max_line_bytes",
                 "max_attempts", "retry_after_cap_seconds", "max_redownloads", "fresh_max_age_seconds",
                 "max_head_per_slot", "max_clock_skew_seconds")
    _FLOORS = ("min_free_bytes_preflight", "min_free_bytes_runtime", "absence_check_spacing_seconds")


def _tighten(base: Limits, overrides: dict[str, Any]) -> Limits:
    names = {f.name for f in fields(Limits)}
    unknown = set(overrides) - names
    if unknown:
        raise ConfigError(f"unknown limit keys: {sorted(unknown)}")
    changes: dict[str, Any] = {}
    for key, value in overrides.items():
        current = getattr(base, key)
        if key == "parallel_enabled":
            if value is not False:
                raise ConfigError("parallel mode is disabled in this build and cannot be enabled by config")
            continue
        if key == "backoff_seconds":
            seq = tuple(float(v) for v in value)
            if len(seq) < 1 or any(v < 0 for v in seq):
                raise ConfigError("backoff_seconds must be non-negative numbers")
            changes[key] = seq
            continue
        if isinstance(current, bool) or not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ConfigError(f"limit {key} must be a number")
        if key in Limits._CEILINGS and value > current:
            raise ConfigError(f"limit {key}={value} would relax the ceiling {current}; limits can only be tightened")
        if key in Limits._FLOORS and value < current:
            raise ConfigError(f"limit {key}={value} would relax the floor {current}; limits can only be tightened")
        if value <= 0:
            raise ConfigError(f"limit {key} must be positive")
        changes[key] = type(current)(value)
    limits = replace(base, **changes)
    if limits.max_concurrency != 1:
        raise ConfigError("downloads are sequential only: max_concurrency must be 1")
    if limits.max_planned_bytes > limits.max_total_bytes:
        raise ConfigError("max_planned_bytes cannot exceed max_total_bytes")
    return limits


@dataclass(frozen=True)
class ApprovalRecord:
    approved_by: str
    approved_on: date
    reference: str
    data_allowance_remaining_bytes: int
    stage_sha256: str
    note: str = ""


@dataclass(frozen=True)
class RunConfig:
    mode: str = "dry_run"
    output_root: Path = DEFAULT_OUTPUT_ROOT
    limits: Limits = field(default_factory=Limits)
    approvals: dict[str, ApprovalRecord] = field(default_factory=dict)
    source_path: Path | None = None


_APPROVAL_KEYS = {"approved", "approved_by", "approved_on", "reference", "data_allowance_remaining_bytes",
                  "stage_sha256", "note"}
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def _parse_approval(name: str, raw: Any) -> ApprovalRecord | None:
    """Return a record only if every field is explicit and well-formed; otherwise None."""
    if not isinstance(raw, dict):
        return None
    if set(raw) - _APPROVAL_KEYS:
        raise ConfigError(f"approval {name}: unknown keys {sorted(set(raw) - _APPROVAL_KEYS)}")
    if raw.get("approved") is not True:   # the literal YAML boolean true; strings never count
        return None
    by, on, ref = raw.get("approved_by"), raw.get("approved_on"), raw.get("reference")
    allowance, sha = raw.get("data_allowance_remaining_bytes"), raw.get("stage_sha256")
    if not isinstance(by, str) or not by.strip() or "@" in by:
        raise ConfigError(f"approval {name}: approved_by must be your initials or name (no email)")
    if not isinstance(on, date):
        raise ConfigError(f"approval {name}: approved_on must be a YYYY-MM-DD date")
    if not isinstance(ref, str) or not ref.strip():
        raise ConfigError(f"approval {name}: reference is required")
    if not isinstance(allowance, int) or isinstance(allowance, bool) or allowance <= 0:
        raise ConfigError(f"approval {name}: data_allowance_remaining_bytes must be a positive integer")
    if not isinstance(sha, str) or not _SHA_RE.match(sha):
        raise ConfigError(f"approval {name}: stage_sha256 must be the 64-hex list hash being approved, "
                          "written in quotes so YAML keeps it as text")
    return ApprovalRecord(by.strip(), on, ref.strip(), allowance, sha, str(raw.get("note", "")))


def load_config(path: Path | None) -> RunConfig:
    """Load a run config. ``None`` gives the dry-run defaults, which contain no approval."""
    if path is None:
        return RunConfig()
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")
    allowed = {"mode", "output_root", "limits", "approvals"}
    if set(raw) - allowed:
        raise ConfigError(f"unknown config keys: {sorted(set(raw) - allowed)}")
    mode = raw.get("mode", "dry_run")
    if mode not in MODES:
        raise ConfigError(f"mode must be one of {MODES}")
    output_root = Path(raw["output_root"]) if raw.get("output_root") else DEFAULT_OUTPUT_ROOT
    limits = _tighten(Limits(), raw.get("limits") or {})
    approvals_raw = raw.get("approvals") or {}
    if not isinstance(approvals_raw, dict):
        raise ConfigError("approvals must be a mapping")
    unknown = set(approvals_raw) - {"dev_sample", "confirmation_sample", "full_acquisition"}
    if unknown:
        raise ConfigError(f"unknown approval names: {sorted(unknown)}")
    approvals = {}
    for name, rec in approvals_raw.items():
        parsed = _parse_approval(name, rec)
        if parsed is not None:
            approvals[name] = parsed
    return RunConfig(mode, output_root, limits, approvals, path)


@dataclass(frozen=True)
class Authorization:
    """Proof that a gate passed. Only ``authorize`` creates a network-capable one."""

    mode: str
    network: bool
    approval: ApprovalRecord | None
    limits: Limits
    _issued_by_gate: object = field(repr=False, compare=False, default=None)


_GATE_TOKEN = object()


def is_gate_issued(auth: Authorization) -> bool:
    return auth._issued_by_gate is _GATE_TOKEN


def authorize(
    config: RunConfig,
    mode: str,
    *,
    cli_confirmed_network: bool = False,
    expected_stage_sha256: str | None = None,
    trigger_valid: bool = False,
) -> Authorization:
    """Evaluate the gate for ``mode``. Raises ``ApprovalRefused`` with the exact reason."""
    if mode not in MODES:
        raise ApprovalRefused(f"unknown mode {mode!r}")
    if mode == "dry_run":
        return Authorization("dry_run", False, None, config.limits, _GATE_TOKEN)
    if mode == "full_acquisition":
        raise ApprovalRefused("full historical acquisition is not approved and cannot be enabled in this build")
    if config.mode != mode:
        raise ApprovalRefused(f"config mode is {config.mode!r}, not {mode!r}")
    if mode == "dev_sample" and not DEV_SAMPLE_ENABLED_IN_THIS_BUILD:
        raise ApprovalRefused("development-sample acquisition is disabled in this build (B2-K)")
    if mode == "confirmation_sample":
        if not CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD:
            raise ApprovalRefused("confirmation-sample acquisition is disabled in this build")
        if not trigger_valid:
            raise ApprovalRefused("confirmation sample: the pre-registered trigger has not fired")
    approval = config.approvals.get(mode)
    if approval is None:
        raise ApprovalRefused(f"no complete approval record for {mode} in the local run config")
    if approval.reference != APPROVAL_REFERENCE and mode == "dev_sample":
        raise ApprovalRefused(f"approval reference must be {APPROVAL_REFERENCE}")
    if expected_stage_sha256 is None or approval.stage_sha256 != expected_stage_sha256:
        raise ApprovalRefused("approval stage_sha256 does not match the pre-registered list being fetched")
    if approval.data_allowance_remaining_bytes < config.limits.max_total_bytes:
        raise ApprovalRefused("confirmed data allowance is smaller than the transfer cap")
    if not cli_confirmed_network:
        raise ApprovalRefused("network use needs the explicit --confirm-network flag")
    return Authorization(mode, True, approval, config.limits, _GATE_TOKEN)
