"""Offline preflight (the dry run). No network request, no database, and nothing written to disk.

It reports every check with ``ok`` / ``blocked`` / ``info`` and lists all blockers, instead of stopping
at the first one, so the user can see exactly what is missing before any download.
"""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wealthpilot.data import gdelt as pkg
from wealthpilot.data.gdelt.config import APPROVAL_REFERENCE, REPO_ROOT, RunConfig
from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.filters import load_spec
from wealthpilot.data.gdelt.guards import free_bytes
from wealthpilot.data.gdelt.sample import (
    BLOCKS,
    COMBINED_SHA256,
    STAGE_C_SHA256,
    STAGE_D_SHA256,
    derive_stages,
    estimated_bytes,
    known_absent_in_frame,
    list_digest,
    load_development_stage,
)
from wealthpilot.data.gdelt.session_calendar import assert_tz_offsets


def git_is_ignored(path: Path, repo_root: Path = REPO_ROOT) -> bool | None:
    """True/False from ``git check-ignore --no-index``; None if git cannot answer. Local only."""
    try:
        rel = Path(path).resolve().relative_to(repo_root)
    except ValueError:
        return True  # outside the repository: Git cannot track it
    try:
        proc = subprocess.run(["git", "check-ignore", "-q", "--no-index", str(rel / "probe")], cwd=repo_root,
                              capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return {0: True, 1: False}.get(proc.returncode)


def run_preflight(config: RunConfig, *, stage: str = "D",
                  disk_usage: Callable[[str], object] = shutil.disk_usage,
                  git_check: Callable[[Path], bool | None] = git_is_ignored) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, status: str, detail: str, **extra: Any) -> None:
        checks.append({"check": name, "status": status, "detail": detail, **extra})
        if status == "blocked":
            blockers.append(f"{name}: {detail}")

    # 1. sample list integrity
    try:
        dev = load_development_stage()
        d_list, c_list = derive_stages(known_absent_in_frame())
        derived_ok = (list_digest(d_list) == STAGE_D_SHA256 and list_digest(c_list) == STAGE_C_SHA256
                      and list_digest(d_list + c_list) == COMBINED_SHA256 and [s.stamp for s in dev] == d_list)
        add("sample_lists", "ok" if derived_ok else "blocked",
            "stage D matches SHA-256 a459a3fb..., and re-derivation reproduces D, C and the combined hash"
            if derived_ok else "re-derivation does not reproduce the committed lists",
            batches=len(dev), blocks=BLOCKS)
    except GdeltToolError as exc:
        dev = []
        add("sample_lists", "blocked", exc.reason)

    # 2. filter specification
    try:
        spec = load_spec()
        add("filter_spec", "ok", f"{spec.version} sha256 {spec.sha256[:12]}..., status candidate_for_labelled_review")
    except GdeltToolError as exc:
        add("filter_spec", "blocked", exc.reason)

    # 3. time zone data
    try:
        assert_tz_offsets()
        tz = importlib.metadata.version("tzdata") if _has("tzdata") else "system"
        add("timezone", "ok", f"America/New_York offsets correct (tzdata {tz})")
    except GdeltToolError as exc:
        add("timezone", "blocked", exc.reason)

    # 4. budget estimate (no network: B2-G mean listed sizes per year)
    lim = config.limits
    est = estimated_bytes([s.stamp for s in dev]) if dev else 0
    add("transfer_estimate", "ok" if est <= lim.max_planned_bytes else "blocked",
        f"estimated {est:,} B for {len(dev)} batches; refusal threshold {lim.max_planned_bytes:,} B; "
        f"hard cap {lim.max_total_bytes:,} B including retries. The real figure comes from header requests "
        "before any download", estimated_bytes=est, max_planned_bytes=lim.max_planned_bytes,
        max_total_bytes=lim.max_total_bytes)
    min_requests = 2 * len(dev)
    add("request_budget", "ok" if min_requests <= lim.max_requests else "blocked",
        f"at least {min_requests} requests (one header check and one download per batch); cap {lim.max_requests}, "
        "retries and substitutions included", min_requests=min_requests, max_requests=lim.max_requests)
    add("concurrency", "ok" if lim.max_concurrency == 1 and not lim.parallel_enabled else "blocked",
        "sequential downloads; parallel mode disabled")

    # 5. disk
    try:
        free = free_bytes(config.output_root, disk_usage)
        need = lim.min_free_bytes_preflight
        add("free_disk", "ok" if free >= need else "blocked",
            f"{free:,} B free on the output drive; preflight floor {need:,} B, runtime floor "
            f"{lim.min_free_bytes_runtime:,} B; temporary cap {lim.max_tmp_bytes:,} B; raw sample kept on disk "
            f"about {est:,} B", free_bytes=free)
    except OSError as exc:
        add("free_disk", "blocked", f"cannot read free space: {exc}")

    # 6. git ignore
    ignored = git_check(config.output_root)
    add("git_ignore", {True: "ok", False: "blocked", None: "blocked"}[ignored],
        {True: f"{config.output_root} is excluded from Git", False: f"{config.output_root} is NOT ignored by Git",
         None: "git could not confirm the ignore rule"}[ignored])

    # 7. approvals and build locks
    rec = config.approvals.get("dev_sample")
    if rec is None:
        add("approval_record", "blocked", "no complete approvals.dev_sample record in a local run config "
            f"(approved: true, approved_by, approved_on, reference {APPROVAL_REFERENCE}, "
            "data_allowance_remaining_bytes, stage_sha256)")
    else:
        problems = []
        if rec.reference != APPROVAL_REFERENCE:
            problems.append("reference")
        if rec.stage_sha256 != STAGE_D_SHA256:
            problems.append("stage_sha256")
        if rec.data_allowance_remaining_bytes < lim.max_total_bytes:
            problems.append("data allowance below the transfer cap")
        add("approval_record", "blocked" if problems else "ok",
            f"problems: {problems}" if problems else f"approved by {rec.approved_by} on {rec.approved_on}")
    add("build_lock", "ok" if pkg.DEV_SAMPLE_ENABLED_IN_THIS_BUILD and pkg.NETWORK_ENABLED_IN_THIS_BUILD else "blocked",
        f"DEV_SAMPLE_ENABLED_IN_THIS_BUILD={pkg.DEV_SAMPLE_ENABLED_IN_THIS_BUILD}, "
        f"NETWORK_ENABLED_IN_THIS_BUILD={pkg.NETWORK_ENABLED_IN_THIS_BUILD}")
    add("scope", "ok", "development stage only; stage C needs a trigger and its own approval; full acquisition "
        "always refuses", stage=stage)
    review_root = Path(config.output_root) / "review" / "b2i_review_v1"
    add("destination", "info", f"manifest {review_root / 'manifest' / 'manifest.sqlite'}; kept raw sample "
        f"{review_root / 'raw'}; daily output {review_root / 'filtered'}; logs {review_root / 'logs'}; "
        f"temporary {review_root / 'tmp'}")
    add("code_fingerprint", "info", f"tool source SHA-256 {code_fingerprint()}")
    add("network", "info", "this dry run made no network request")
    return {"mode": "dry_run", "stage": stage, "ready_for_development_sample": not blockers,
            "blockers": blockers, "checks": checks, "python": sys.version.split()[0]}


PACKAGE_DIR = Path(__file__).resolve().parent


def code_fingerprint(package_dir: Path = PACKAGE_DIR) -> str:
    """SHA-256 over the tool's own source and data files (LF-normalised, sorted by relative path)."""
    import hashlib
    h = hashlib.sha256()
    for p in sorted(package_dir.rglob("*")):
        if p.is_file() and p.suffix in {".py", ".sql", ".yaml", ".txt"} and "__pycache__" not in p.parts:
            h.update(p.relative_to(package_dir).as_posix().encode("utf-8") + b"\0")
            h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def git_head(repo_root: Path = REPO_ROOT) -> tuple[str | None, bool | None]:
    """(commit, dirty) from local git; (None, None) if git cannot answer. No network."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True,
                                timeout=30, check=False).stdout.strip() or None
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True,
                                timeout=60, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    return commit, bool(status.strip())


def tzdata_version() -> str | None:
    return importlib.metadata.version("tzdata") if _has("tzdata") else None


def _has(dist: str) -> bool:
    try:
        importlib.metadata.version(dist)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False
