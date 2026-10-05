"""Data-quality checks for the raw FAR-Trans and Kaggle datasets.

Read-only: every function here only reads files under `datasets/raw/` and
never writes, moves, or modifies them. Uses the Python standard library only
(csv/collections/statistics) rather than pandas — Phase 2 is inspection of
flat CSV files, which stdlib handles directly, and this sidesteps needing
pandas/numpy installed at all for a phase that doesn't do feature
engineering. pandas remains the approved, intended tool for Phase 3's actual
preprocessing pipelines.

This module reports what is actually in the files. It does not know in
advance what the "right" answer is — genuine findings (including ones that
contradict docs/PROJECT_PLAN.md's or the FAR-Trans README's stated values)
are reported as found, not smoothed over.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wealthpilot.data.acquisition import FAR_TRANS_DIR, KAGGLE_DIR

GENUINE_RISK_LEVELS = {"Conservative", "Income", "Balanced", "Aggressive"}


@dataclass
class FileQualityReport:
    path: str
    row_count: int
    columns: list[str]
    null_counts: dict[str, int]
    duplicate_full_rows: int
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [row for row in reader]
    return header, rows


def _null_counts(header: list[str], rows: list[list[str]]) -> dict[str, int]:
    idx = {c: i for i, c in enumerate(header)}
    counts = dict.fromkeys(header, 0)
    for row in rows:
        for col in header:
            if row[idx[col]].strip() == "":
                counts[col] += 1
    return counts


def _duplicate_full_rows(rows: list[list[str]]) -> int:
    counter = Counter(tuple(row) for row in rows)
    return sum(c - 1 for c in counter.values() if c > 1)


def check_customer_information() -> FileQualityReport:
    path = FAR_TRANS_DIR / "customer_information.csv"
    header, rows = _read_csv(path)
    idx = {c: i for i, c in enumerate(header)}

    customer_ids = [r[idx["customerID"]] for r in rows]
    unique_customers = set(customer_ids)
    risk_dist = Counter(r[idx["riskLevel"]] for r in rows)
    genuine_rows = [r for r in rows if r[idx["riskLevel"]] in GENUINE_RISK_LEVELS]
    genuine_customers = {r[idx["customerID"]] for r in genuine_rows}

    notes = [
        f"{len(rows) - len(unique_customers)} rows share a customerID with another row "
        "(multiple dated records per customer) — this is expected per the FAR-Trans "
        "README and must not be deduplicated away.",
        f"{len(genuine_rows)} rows ({len(genuine_customers)} distinct customers) carry a "
        "genuine riskLevel (Conservative/Income/Balanced/Aggressive); the rest are "
        "Predicted_* or Not_Available and must be excluded from supervised training labels.",
    ]

    cap_dist = Counter(r[idx["investmentCapacity"]] for r in rows)
    if "CAP_LT30K" in cap_dist or "Predicted_CAP_LT30K" in cap_dist:
        notes.append(
            "investmentCapacity's actual 'under 30K' value is 'CAP_LT30K' (no underscore "
            "before 30K) — the FAR-Trans README and docs/PROJECT_PLAN.md both document it "
            "as 'CAP_LT_30K'. Code filtering on this band must match the real value, not "
            "the documented spelling."
        )

    type_dist = Counter(r[idx["customerType"]] for r in rows)
    if "Legal Entity" in type_dist:
        notes.append(
            "customerType's actual legal-entity value is 'Legal Entity' (capital E) — "
            "docs/PROJECT_PLAN.md documents it as 'Legal entity'."
        )

    return FileQualityReport(
        path=str(path),
        row_count=len(rows),
        columns=header,
        null_counts=_null_counts(header, rows),
        duplicate_full_rows=_duplicate_full_rows(rows),
        notes=notes,
        extra={
            "unique_customer_count": len(unique_customers),
            "risk_level_distribution": dict(risk_dist),
            "investment_capacity_distribution": dict(cap_dist),
            "customer_type_distribution": dict(type_dist),
            "genuine_label_row_count": len(genuine_rows),
            "genuine_label_customer_count": len(genuine_customers),
        },
    )


def check_asset_information() -> FileQualityReport:
    path = FAR_TRANS_DIR / "asset_information.csv"
    header, rows = _read_csv(path)
    idx = {c: i for i, c in enumerate(header)}

    isins = [r[idx["ISIN"]] for r in rows]
    unique_isins = set(isins)
    category_dist = Counter(r[idx["assetCategory"]] for r in rows)

    notes = [
        f"{len(rows) - len(unique_isins)} rows share an ISIN with another row "
        "(README: 'an asset can appear here several times') — not necessarily an error.",
    ]

    return FileQualityReport(
        path=str(path),
        row_count=len(rows),
        columns=header,
        null_counts=_null_counts(header, rows),
        duplicate_full_rows=_duplicate_full_rows(rows),
        notes=notes,
        extra={
            "unique_isin_count": len(unique_isins),
            "asset_category_distribution": dict(category_dist),
        },
    )


def check_markets() -> FileQualityReport:
    path = FAR_TRANS_DIR / "markets.csv"
    header, rows = _read_csv(path)
    return FileQualityReport(
        path=str(path),
        row_count=len(rows),
        columns=header,
        null_counts=_null_counts(header, rows),
        duplicate_full_rows=_duplicate_full_rows(rows),
    )


def check_close_prices() -> FileQualityReport:
    path = FAR_TRANS_DIR / "close_prices.csv"
    header, rows = _read_csv(path)
    idx = {c: i for i, c in enumerate(header)}

    dates = [r[idx["timestamp"]] for r in rows]
    isins = [r[idx["ISIN"]] for r in rows]
    pair_counts = Counter(zip(isins, dates, strict=True))
    duplicate_pairs = sum(c - 1 for c in pair_counts.values() if c > 1)
    nonpositive = sum(1 for r in rows if float(r[idx["closePrice"]]) <= 0)
    rows_per_isin = Counter(isins)
    coverage = sorted(rows_per_isin.values())

    notes = [
        "closePrice is close-only, in euros, with no open/high/low/volume — those columns "
        "in the market_data table can only be populated from yfinance (Phase 6).",
        f"Coverage per ISIN ranges from {coverage[0]} to {coverage[-1]} rows "
        f"(median {coverage[len(coverage) // 2]}); assets near the low end have too little "
        "history for time-series modelling.",
    ]

    return FileQualityReport(
        path=str(path),
        row_count=len(rows),
        columns=header,
        null_counts=_null_counts(header, rows),
        duplicate_full_rows=_duplicate_full_rows(rows),
        notes=notes,
        extra={
            "date_range": [min(dates), max(dates)],
            "unique_isin_count": len(set(isins)),
            "duplicate_isin_date_pairs": duplicate_pairs,
            "nonpositive_close_price_rows": nonpositive,
            "rows_per_isin_min": coverage[0],
            "rows_per_isin_max": coverage[-1],
        },
    )


def check_limit_prices() -> FileQualityReport:
    path = FAR_TRANS_DIR / "limit_prices.csv"
    header, rows = _read_csv(path)
    idx = {c: i for i, c in enumerate(header)}
    isins = [r[idx["ISIN"]] for r in rows]
    return FileQualityReport(
        path=str(path),
        row_count=len(rows),
        columns=header,
        null_counts=_null_counts(header, rows),
        duplicate_full_rows=_duplicate_full_rows(rows),
        extra={"unique_isin_count": len(set(isins))},
    )


def check_transactions() -> FileQualityReport:
    path = FAR_TRANS_DIR / "transactions.csv"
    header, rows = _read_csv(path)
    idx = {c: i for i, c in enumerate(header)}

    txn_ids = [r[idx["transactionID"]] for r in rows]
    unique_txn_ids = set(txn_ids)
    txn_type_dist = Counter(r[idx["transactionType"]] for r in rows)
    channel_dist = Counter(r[idx["channel"]] for r in rows)
    dates = [r[idx["timestamp"]] for r in rows]
    nonpositive_value = sum(1 for r in rows if float(r[idx["totalValue"]]) <= 0)
    nonpositive_units = sum(1 for r in rows if float(r[idx["units"]]) <= 0)

    notes = []
    if len(unique_txn_ids) != len(rows):
        repeated_ids = {tid for tid, c in Counter(txn_ids).items() if c > 1}
        sample = next(iter(repeated_ids))
        sample_rows = [r for r in rows if r[idx["transactionID"]] == sample]
        sample_customers = {r[idx["customerID"]] for r in sample_rows}
        pattern = (
            "each repeat pairs two different customerIDs against an otherwise identical "
            "row (same ISIN/type/timestamp/totalValue/units) — consistent with joint "
            "account co-ownership, not accidental duplication"
            if len(sample_customers) == len(sample_rows)
            else "repeats do not obviously share a single pattern — inspect before assuming"
        )
        notes.append(
            f"transactionID is not a unique row key: {len(rows)} rows but only "
            f"{len(unique_txn_ids)} distinct values ({len(repeated_ids)} IDs repeat, "
            f"{len(rows) - len(unique_txn_ids)} extra rows). Zero exact full-row "
            f"duplicates exist, so this is not double-counting — {pattern}. A unique row "
            "key for this table is (customerID, transactionID), not transactionID alone."
        )

    return FileQualityReport(
        path=str(path),
        row_count=len(rows),
        columns=header,
        null_counts=_null_counts(header, rows),
        duplicate_full_rows=_duplicate_full_rows(rows),
        notes=notes,
        extra={
            "date_range": [min(dates), max(dates)],
            "unique_customer_count": len({r[idx["customerID"]] for r in rows}),
            "unique_transaction_id_count": len(unique_txn_ids),
            "transaction_type_distribution": dict(txn_type_dist),
            "channel_distribution": dict(channel_dist),
            "nonpositive_total_value_rows": nonpositive_value,
            "nonpositive_units_rows": nonpositive_units,
        },
    )


def check_questionnaires() -> FileQualityReport:
    """questionnaires.csv is NOT CSV — a plain-text question/answer list. Confirm that."""
    path = FAR_TRANS_DIR / "questionnaires.csv"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    question_lines = [ln for ln in lines if ln.strip() and ln.strip()[0].isdigit() and "." in ln]
    looks_like_csv_header = "," in lines[0] if lines else False

    notes = [
        "Confirmed NOT a CSV file despite the .csv extension — a plain-text list of "
        f"MiFID II questions and lettered answer options ({len(question_lines)} numbered "
        "questions found). Contains no customer answers and no per-customer rows, "
        "matching docs/PROJECT_PLAN.md's claim. Questionnaire score/answers cannot be a "
        "training feature because no answers exist in this file.",
    ]
    if looks_like_csv_header:
        notes.append("First non-empty line contains a comma — re-check the CSV assumption.")

    return FileQualityReport(
        path=str(path),
        row_count=len(question_lines),
        columns=[],
        null_counts={},
        duplicate_full_rows=0,
        notes=notes,
        extra={"total_lines": len(lines), "question_count": len(question_lines)},
    )


def check_kaggle_file(filename: str) -> FileQualityReport:
    path = KAGGLE_DIR / filename
    header, rows = _read_csv(path)
    idx = {c: i for i, c in enumerate(header)}

    user_col = "user_id" if "user_id" in idx else None
    extra: dict[str, Any] = {}
    if user_col:
        user_ids = [r[idx[user_col]] for r in rows]
        extra["unique_user_id_count"] = len(set(user_ids))

    return FileQualityReport(
        path=str(path),
        row_count=len(rows),
        columns=header,
        null_counts=_null_counts(header, rows),
        duplicate_full_rows=_duplicate_full_rows(rows),
        extra=extra,
    )


def generate_far_trans_report() -> dict[str, FileQualityReport]:
    return {
        "customer_information.csv": check_customer_information(),
        "asset_information.csv": check_asset_information(),
        "markets.csv": check_markets(),
        "close_prices.csv": check_close_prices(),
        "limit_prices.csv": check_limit_prices(),
        "transactions.csv": check_transactions(),
        "questionnaires.csv": check_questionnaires(),
    }


def generate_kaggle_report() -> dict[str, FileQualityReport]:
    return {
        path.name: check_kaggle_file(path.name)
        for path in sorted(KAGGLE_DIR.glob("*.csv"))
    }
