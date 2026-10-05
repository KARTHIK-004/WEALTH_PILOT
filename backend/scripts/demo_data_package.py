"""Reads the synthetic demo dataset in `demo_data/` -- files in, dicts out.

`demo_data/` is the single source of WealthPilot AI's demo population: four
individual personas (profile, questionnaire answers, financial inputs, goals)
and one family household (members, income, expenses, assets, liabilities,
goals), plus scenario inputs and the expected high-level outcomes. See
`demo_data/README.md`.

This module only READS those files and reshapes them into the structures
`seed_demo_data.py` sends through the real public API. It has no database
access, makes no API call and calculates nothing: every financial result
(risk, emergency fund, goal feasibility, portfolio, compliance,
recommendation, household summary) is computed by the application when the
data is seeded and analysed. `analysis_state` reads only statuses, flags and
rule ids from an existing `AnalysisResult` response -- never a number.

The dataset is synthetic demo data. It is not a replacement for FAR-Trans or
the Kaggle dataset, and nothing under `training/` may read it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DATA_DIR = REPO_ROOT / "demo_data"
SOURCE_LABEL = "synthetic_demo"
FAMILY_DEMO_KEY = "WPDEMO-FAM"

PERSONA_DIRS = ("profiles", "questionnaire", "financial_inputs", "individual_goals")
HOUSEHOLD_RECORD_RESOURCES = ("income", "expenses", "assets", "liabilities", "goals")

# The contract-level states `expected_results/` may state, and how each is
# read from an `AnalysisResult` response (see `analysis_state`).
ANALYSIS_STATE_KEYS = (
    "analysis_status",
    "risk_available",
    "goal_results_returned",
    "goal_feasibility_available",
    "emergency_fund_sufficient",
    "compliance_decision",
    "triggered_compliance_rules",
    "recommendation_available",
    "recommendation_status",
    "portfolio_weights_available",
    "explanation_available",
)
FAMILY_STATE_KEYS = (
    "member_count",
    "primary_demo_key",
    "every_dataset_record_present_exactly_once",
    "household_summary_available",
    "household_goals_available",
    "non_members_denied",
)


class DemoDataError(ValueError):
    """The dataset is missing a file or a reference -- raised instead of guessing."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(obj: Any) -> str:
    """The one on-disk format: two-space indent, UTF-8 characters kept, keys in
    authored order, trailing newline -- so regenerating a file is byte-stable."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def data_files(data_dir: Path = DEMO_DATA_DIR) -> list[Path]:
    """Every data file of the package (all JSON except the manifest), in a stable order."""
    return sorted(
        (p for p in data_dir.rglob("*.json") if p.name != "manifest.json"),
        key=lambda p: p.relative_to(data_dir).as_posix(),
    )


def select_option(options: list[dict], offset: int) -> str:
    """Deterministic, position-based option choice (never a score/weighting
    of the option's own content) -- `offset=0` first option, `offset=-1`
    last option, otherwise a middle-ish index. Each persona uses a
    different offset so the demo questionnaires are intentionally
    different from one another, while remaining a pure "which real option
    did this demo submission use" choice -- never converted into or read
    as a score of any kind. The materialised answers in
    `demo_data/questionnaire/` must equal this rule's result (the validator
    checks it)."""
    if offset == 0:
        return options[0]["key"]
    if offset == -1:
        return options[-1]["key"]
    return options[(len(options) - 1) // 2]["key"]


def _index(directory: Path, key_field: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        obj = read_json(path)
        key = obj.get(key_field)
        if key is None:
            raise DemoDataError(f"{path.name}: no {key_field!r}")
        if key in indexed:
            raise DemoDataError(f"{directory.name}: {key_field} {key!r} appears in more than one file")
        indexed[key] = obj
    return indexed


def _one(indexed: dict[str, dict], key: str, where: str) -> dict:
    if key not in indexed:
        raise DemoDataError(f"{where}: no file for {key!r}")
    return indexed[key]


def load_personas(data_dir: Path = DEMO_DATA_DIR) -> list[dict]:
    """One dict per persona, ordered by demo key (A, B, C, D), in the shape the
    seed uses. `financial_inputs` is present only when the persona's file
    provides them -- a persona without inputs has no such key, never zeros."""
    parts = {d: _index(data_dir / d, "demo_key") for d in PERSONA_DIRS}
    personas = []
    for key, profile_file in sorted(parts["profiles"].items()):
        questionnaire = _one(parts["questionnaire"], key, "questionnaire")
        financial = _one(parts["financial_inputs"], key, "financial_inputs")
        goals = _one(parts["individual_goals"], key, "individual_goals")
        link = profile_file["risk_data_link"]
        persona = {
            "demo_key": key,
            "name": profile_file["customer_name"],
            "purpose": profile_file["purpose"],
            "owned_by_seed": profile_file["owned_by_seed"],
            "external_customer_id": None if link is None else link["external_customer_id"],
            "profile": profile_file["profile"],
            "goals": goals["goals"],
            "answer_offset": questionnaire["selection_rule"]["answer_offset"],
            "answers": questionnaire["answers"],
        }
        if financial["financial_inputs"] is not None:
            persona["financial_inputs"] = financial["financial_inputs"]
        personas.append(persona)
    return personas


def load_family(data_dir: Path = DEMO_DATA_DIR, household_key: str = FAMILY_DEMO_KEY) -> dict:
    """The family household in the shape `setup_family` sends through the API:
    names resolved from the persona files, the members to add (the primary is
    the household's creator, not an added member), and each resource's records."""
    names = {key: p["customer_name"] for key, p in _index(data_dir / "profiles", "demo_key").items()}
    household_dir = data_dir / "household"
    household = _one(_index(household_dir / "households", "demo_key"), household_key, "household/households")
    members = _one(_index(household_dir / "members", "household_demo_key"), household_key, "household/members")

    def name_of(demo_key: str) -> str:
        if demo_key not in names:
            raise DemoDataError(f"household {household_key}: unknown persona {demo_key!r}")
        return names[demo_key]

    family: dict[str, Any] = {
        "household_name": household["household_name"],
        "primary_name": name_of(household["primary_demo_key"]),
        "members": [
            {"name": name_of(m["demo_key"]), "relationship": m["relationship"], "role": m["role"]}
            for m in members["members"]
            if m["role"] != "primary"
        ],
    }
    for resource in HOUSEHOLD_RECORD_RESOURCES:
        family[resource] = _one(
            _index(household_dir / resource, "household_demo_key"), household_key, f"household/{resource}"
        )["records"]
    return family


def load_family_record_keys(data_dir: Path = DEMO_DATA_DIR, household_key: str = FAMILY_DEMO_KEY) -> dict[str, str]:
    """resource -> the field that identifies one of its records for idempotency."""
    return {
        resource: _one(
            _index(data_dir / "household" / resource, "household_demo_key"), household_key, f"household/{resource}"
        )["idempotency_key"]
        for resource in HOUSEHOLD_RECORD_RESOURCES
    }


def load_expected_results(data_dir: Path = DEMO_DATA_DIR) -> dict[str, dict]:
    """demo key (persona or household) -> its expected contract-level states."""
    expected: dict[str, dict] = {}
    for path in sorted((data_dir / "expected_results").glob("*.json")):
        obj = read_json(path)
        key = obj.get("demo_key") or obj.get("household_demo_key")
        if key is None or key in expected:
            raise DemoDataError(f"expected_results/{path.name}: missing or repeated demo key")
        expected[key] = obj["expected"]
    return expected


def load_scenarios(data_dir: Path = DEMO_DATA_DIR) -> list[dict]:
    scenarios: list[dict] = []
    for path in sorted((data_dir / "scenarios").glob("*.json")):
        scenarios.extend(read_json(path)["scenarios"])
    return scenarios


def analysis_state(result: dict) -> dict:
    """The contract-level state of an `AnalysisResult` response: which outcome,
    which sections are present, which compliance rule triggered. Every value is
    a status string, a boolean or a rule id read straight from the response --
    never a number, and nothing recomputed. `None` keeps "not evaluated" apart
    from "evaluated, nothing triggered" (`[]`)."""
    risk = result.get("risk") or {}
    goals = result.get("goals") or []
    emergency_fund = result.get("emergency_fund")
    compliance = result.get("compliance")
    recommendation = result.get("recommendation")
    portfolio = result.get("portfolio") or {}
    return {
        "analysis_status": result.get("status"),
        "risk_available": risk.get("risk_category") is not None,
        "goal_results_returned": bool(goals),
        "goal_feasibility_available": any(g.get("feasibility") is not None for g in goals),
        "emergency_fund_sufficient": None if emergency_fund is None else emergency_fund.get("sufficient"),
        "compliance_decision": None if compliance is None else compliance.get("decision"),
        "triggered_compliance_rules": None
        if compliance is None
        else sorted(r["rule_id"] for r in compliance.get("rule_results") or [] if r.get("triggered")),
        "recommendation_available": recommendation is not None,
        "recommendation_status": None if recommendation is None else recommendation.get("status"),
        "portfolio_weights_available": bool(portfolio.get("weights")),
        "explanation_available": result.get("explanation") is not None,
    }
