"""Resource guards: bytes, requests, free disk, temporary disk, stop file, clock skew.

Every request (header or body, first try or retry) is reserved here before it is made, and every
byte received is recorded, so retries always count toward the budgets. A guard never relaxes itself.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wealthpilot.data.gdelt.errors import BudgetExceeded
from wealthpilot.data.gdelt.timeutil import require_utc


@dataclass
class TransferBudget:
    max_total_bytes: int
    max_requests: int
    bytes_used: int = 0
    requests_used: int = 0

    def reserve_request(self, expected_bytes: int = 0) -> None:
        """Call before every request. ``expected_bytes`` is the size the response should bring."""
        if self.requests_used + 1 > self.max_requests:
            raise BudgetExceeded(
                f"request cap reached: {self.requests_used} of {self.max_requests} used", limit="max_requests")
        if self.bytes_used + max(expected_bytes, 0) > self.max_total_bytes:
            raise BudgetExceeded(
                f"transfer cap: {self.bytes_used} B used + {expected_bytes} B expected > {self.max_total_bytes} B",
                limit="max_total_bytes")
        self.requests_used += 1

    def remaining_bytes(self) -> int:
        return max(self.max_total_bytes - self.bytes_used, 0)

    def record_bytes(self, received: int) -> None:
        """Call with every byte count received, including failed or partial transfers."""
        if received < 0:
            raise ValueError("received bytes cannot be negative")
        self.bytes_used += received
        if self.bytes_used > self.max_total_bytes:
            raise BudgetExceeded(
                f"transfer cap exceeded: {self.bytes_used} B > {self.max_total_bytes} B", limit="max_total_bytes")


def nearest_existing(path: Path) -> Path:
    p = Path(path).resolve()
    while not p.exists():
        if p.parent == p:
            break
        p = p.parent
    return p


def free_bytes(path: Path, disk_usage: Callable[[str], object] = shutil.disk_usage) -> int:
    return int(disk_usage(str(nearest_existing(path))).free)  # type: ignore[attr-defined]


def check_free_disk(path: Path, minimum: int, *, disk_usage: Callable[[str], object] = shutil.disk_usage,
                    stage: str = "runtime") -> int:
    free = free_bytes(path, disk_usage)
    if free < minimum:
        raise BudgetExceeded(f"{stage}: free disk {free} B below the {minimum} B floor", limit="min_free_bytes")
    return free


def tmp_usage_bytes(tmp_dir: Path) -> int:
    if not tmp_dir.exists():
        return 0
    total = 0
    for root, _dirs, files in os.walk(tmp_dir):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def check_tmp_usage(tmp_dir: Path, maximum: int, extra: int = 0) -> int:
    used = tmp_usage_bytes(tmp_dir) + extra
    if used > maximum:
        raise BudgetExceeded(f"temporary disk {used} B above the {maximum} B cap", limit="max_tmp_bytes")
    return used


def stop_requested(output_root: Path) -> bool:
    return (Path(output_root) / "STOP").exists()


def check_clock_skew(local_now: datetime, server_date: datetime, max_skew_seconds: int) -> float:
    skew = abs((require_utc(local_now) - require_utc(server_date)).total_seconds())
    if skew > max_skew_seconds:
        raise BudgetExceeded(f"clock skew {skew:.0f} s exceeds {max_skew_seconds} s", limit="max_clock_skew_seconds")
    return skew
