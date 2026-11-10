"""The pre-registered B2-I review sample: lists, verification, substitution and the stage C gate.

The stage lists ship verbatim in ``sample_data/`` (copied from B2-I Appendix A). They are never
regenerated at run time: they are loaded, and the tool refuses to run unless each list's SHA-256
equals the commitment published in B2-I section 4.2. ``derive_stages`` re-implements the selection
algorithm only so tests can show the shipped lists follow from it.

Stage C (confirmation) is loaded only through ``load_confirmation_stage``, which requires a valid
trigger record *and* an explicit approval record.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from wealthpilot.data.gdelt.config import ApprovalRecord
from wealthpilot.data.gdelt.errors import ApprovalRefused, SampleIntegrityError
from wealthpilot.data.gdelt.timeutil import slot_grid

DATA_DIR = Path(__file__).resolve().parent / "sample_data"
SEED = "wealthpilot-b2i-filter-review-v1"
FRAME_FIRST, FRAME_LAST, FRAME_EXCLUDED = "20211201000000", "20240104204500", "20220103143000"
BLOCKS, ROUNDS_PER_STAGE = 24, 8
STAGE_D_SHA256 = "a459a3fb44afd7e1e8121cd04f247564ea4e8fe434fdca33c9570e50605b2730"
STAGE_C_SHA256 = "b580e8cfc3138cb2a4abc122ed27b25490ef24a4b15d7d9fddc12cf8b9ea8dd1"
COMBINED_SHA256 = "96bd5c0c6c50d484d92d1363564b9dc42ff2407d19867eb409999458b957d08f"
AUDITED_LIST_SHA256 = "7e5d2c2efb7298af6eafb0898739ba880b875b586255e994a81ff1a975cfebf0"   # B2-G master list
# B2-G mean listed size per year (MB, 10^6 B), used only for the pre-download estimate
MEAN_LISTED_MB = {2021: 4.78, 2022: 4.72, 2023: 6.15, 2024: 5.81}
TRIGGER_MIN_MEMBER_ROWS = 100   # B2-I section 4.7 rule 4


def list_digest(stamps: list[str]) -> str:
    return hashlib.sha256(("\n".join(stamps) + "\n").encode("ascii")).hexdigest()


def _read_list(name: str, data_dir: Path) -> list[str]:
    path = data_dir / name
    if not path.exists():
        raise SampleIntegrityError(f"sample list missing: {path}")
    return [s for s in path.read_text(encoding="ascii").replace("\r\n", "\n").split("\n") if s]


@dataclass(frozen=True)
class SampleSlot:
    stamp: str
    round: int      # 1-16
    block: int      # 1-24


def _with_positions(stamps: list[str], first_round: int) -> list[SampleSlot]:
    if len(stamps) != BLOCKS * ROUNDS_PER_STAGE:
        raise SampleIntegrityError(f"stage list has {len(stamps)} stamps, expected {BLOCKS * ROUNDS_PER_STAGE}")
    return [SampleSlot(s, first_round + i // BLOCKS, i % BLOCKS + 1) for i, s in enumerate(stamps)]


def load_development_stage(data_dir: Path = DATA_DIR) -> list[SampleSlot]:
    stamps = _read_list("stage_d.txt", data_dir)
    if list_digest(stamps) != STAGE_D_SHA256:
        raise SampleIntegrityError("stage D list does not match its committed SHA-256 (B2-I section 4.2)")
    return _with_positions(stamps, 1)


def known_absent_in_frame(data_dir: Path = DATA_DIR) -> frozenset[str]:
    return frozenset(_read_list("frame_known_absent.txt", data_dir))


def frame() -> list[str]:
    return [s for s in slot_grid(FRAME_FIRST, FRAME_LAST) if s != FRAME_EXCLUDED]


def block_orders() -> list[list[str]]:
    f = frame()
    n = len(f)
    blocks = [f[(b * n) // BLOCKS:((b + 1) * n) // BLOCKS] for b in range(BLOCKS)]
    return [sorted(x, key=lambda s: hashlib.sha256(f"{SEED}|{s}".encode("ascii")).hexdigest()) for x in blocks]


def derive_stages(known_absent: frozenset[str]) -> tuple[list[str], list[str]]:
    orders = block_orders()
    pos = [0] * BLOCKS
    seq: list[str] = []
    for _round in range(2 * ROUNDS_PER_STAGE):
        for b in range(BLOCKS):
            while orders[b][pos[b]] in known_absent:
                pos[b] += 1
            seq.append(orders[b][pos[b]])
            pos[b] += 1
    return seq[:BLOCKS * ROUNDS_PER_STAGE], seq[BLOCKS * ROUNDS_PER_STAGE:]


def substitute(block: int, unusable: set[str], data_dir: Path = DATA_DIR) -> str | None:
    """Pre-registered substitution: the next stamp in the block's hash order that is not already in
    either stage list, not known absent and not already found unusable. None if the block is exhausted."""
    taken = set(_read_list("stage_d.txt", data_dir)) | set(_read_list("stage_c.txt", data_dir))
    absent = known_absent_in_frame(data_dir)
    for s in block_orders()[block - 1]:
        if s not in taken and s not in absent and s not in unusable:
            return s
    return None


def estimated_bytes(stamps: list[str]) -> int:
    return int(sum(MEAN_LISTED_MB[int(s[:4])] * 1_000_000 for s in stamps))


@dataclass(frozen=True)
class TriggerRecord:
    """Evidence that stage D fired the pre-registered trigger (B2-I section 4.7 rule 4)."""

    member_rows_by_series: dict[str, int]     # from the stage D manifest, counts only
    revision_spec_version: str | None = None  # a v2 filter spec with a change log, if revised
    revision_change_log: str | None = None


def trigger_fired(record: TriggerRecord, available_specs: set[str]) -> tuple[bool, str]:
    low = sorted(s for s, n in record.member_rows_by_series.items() if n < TRIGGER_MIN_MEMBER_ROWS)
    missing = {"EQUITY_US", "RATES_US", "GOLD"} - set(record.member_rows_by_series)
    if missing:
        return False, f"trigger record lacks counts for {sorted(missing)}"
    if record.revision_spec_version is not None:
        if record.revision_spec_version == "gdelt_filter_v1" or record.revision_spec_version not in available_specs:
            return False, "revision trigger needs a new, registered filter version"
        if not record.revision_change_log or not record.revision_change_log.strip():
            return False, "revision trigger needs a change log citing stage D evidence"
        return True, f"revision to {record.revision_spec_version}"
    if low:
        return True, f"fewer than {TRIGGER_MIN_MEMBER_ROWS} member rows in stage D for {low}"
    return False, "no trigger condition met"


def load_confirmation_stage(record: TriggerRecord | None, approval: ApprovalRecord | None, *,
                            available_specs: set[str], data_dir: Path = DATA_DIR) -> list[SampleSlot]:
    if record is None:
        raise ApprovalRefused("stage C is inaccessible: no trigger record")
    fired, why = trigger_fired(record, available_specs)
    if not fired:
        raise ApprovalRefused(f"stage C is inaccessible: {why}")
    if approval is None:
        raise ApprovalRefused("stage C is inaccessible: no separate approval record")
    if approval.stage_sha256 != STAGE_C_SHA256:
        raise ApprovalRefused("stage C approval does not name the stage C list hash")
    stamps = _read_list("stage_c.txt", data_dir)
    if list_digest(stamps) != STAGE_C_SHA256:
        raise SampleIntegrityError("stage C list does not match its committed SHA-256")
    return _with_positions(stamps, ROUNDS_PER_STAGE + 1)
