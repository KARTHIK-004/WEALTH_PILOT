"""Validates the synthetic demo dataset in `demo_data/` -- static, no database,
no server, no network.

USAGE (venv active; from the repo root or `backend/`):

    python backend/scripts/validate_demo_data.py                  # exit 1 on any failure
    python backend/scripts/validate_demo_data.py --write-manifest # regenerate demo_data/manifest.json

`--write-manifest` refuses to write a manifest for data that fails any other
check, then re-validates everything.

WHAT IS CHECKED
---------------

- Layout: every required directory and file exists; every data file is JSON in
  the one canonical format and is labelled `"source": "synthetic_demo"`.
- Personas: unique demo keys, customer names and FAR-Trans links; exactly one
  profile, questionnaire, financial-inputs and goals file per persona; every
  payload validates against the REAL API request schema and carries no field
  that schema does not define (several of those schemas would otherwise
  silently ignore an invented field); a missing value is `null` plus an
  `*_unavailable_reason`, never zero; questionnaire answers match the live
  questionnaire definition and each persona's own selection rule; a
  `risk_data_link` points at a customer present in FAR-Trans.
- Household: the household and every member resolve to known personas;
  exactly one primary, who is `self`/`primary` and the household's own
  primary; `self` for nobody else; no persona in two households; every record
  validates against its API schema; idempotency keys are unique.
- Scenarios, expected results and the seed plan: every reference resolves, the
  scenario payloads validate against `ScenarioCompareRequest`, and expected
  results use only the documented contract-level states.
- Separation: nothing under `training/` or `backend/wealthpilot/` reads
  `demo_data/`; `demo_data/` is not inside `datasets/`; the raw training files
  still have the SHA-256 hashes recorded in the manifest.
- Manifest: counts, per-file hashes, content hash and expected outcomes equal
  what the files themselves produce; the compatible Alembic head is the
  current head.

No financial value is computed here -- the application computes every result
when the data is seeded and analysed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/, for `wealthpilot`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import BaseModel, ValidationError

from demo_data_package import (
    ANALYSIS_STATE_KEYS,
    DEMO_DATA_DIR,
    FAMILY_STATE_KEYS,
    HOUSEHOLD_RECORD_RESOURCES,
    MONTHLY_RECORDS_DIR,
    PERSONA_DIRS,
    REPO_ROOT,
    SOURCE_LABEL,
    canonical_json,
    data_files,
    read_json,
)
from wealthpilot.api.schemas import (
    FinancialInputsUpdate,
    GoalCreate,
    HouseholdAssetCreate,
    HouseholdCreateRequest,
    HouseholdExpenseCreate,
    HouseholdGoalCreate,
    HouseholdIncomeCreate,
    HouseholdLiabilityCreate,
    HouseholdMemberCreateRequest,
    MonthlyRecordUpdate,
    ProfileCreateRequest,
    QuestionnaireAnswersSubmitRequest,
    ScenarioCompareRequest,
)

RECORD_SCHEMAS: dict[str, type[BaseModel]] = {
    "income": HouseholdIncomeCreate,
    "expenses": HouseholdExpenseCreate,
    "assets": HouseholdAssetCreate,
    "liabilities": HouseholdLiabilityCreate,
    "goals": HouseholdGoalCreate,
}
PROFILE_FIELDS = set(ProfileCreateRequest.model_fields) - {"goals"}
GOAL_FIELDS = set(GoalCreate.model_fields)
FINANCIAL_INPUT_FIELDS = set(FinancialInputsUpdate.model_fields)
MONTHLY_RECORD_FIELDS = set(MonthlyRecordUpdate.model_fields)
MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
MIN_REPORTED_MONTHS = 3   # the behaviour findings need at least three months for the activity facts
EXTERNAL_ID_RE = re.compile(r"^[0-9A-F]{20}$")
DEMO_KEY_RE = re.compile(r"^WPDEMO-[A-Z0-9]+$")
# The dataset directory or its loader as a whole word -- not "seed_demo_data".
DEMO_DATA_REFERENCE = re.compile(r"(?<![\w])demo_data(?:_package)?(?![\w])")
MANIFEST_COMPUTED = ("deterministic_identifier", "counts", "expected_outcomes", "files", "training_data_guard")
MANIFEST_HEADER_REQUIRED = ("dataset", "dataset_version", "source", "description", "not_for_training",
                            "compatible_with", "transactions")
DEFAULT_MANIFEST_HEADER: dict[str, Any] = {
    "dataset": "WealthPilot AI demo dataset",
    "dataset_version": "1.0.0",
    "source": SOURCE_LABEL,
    "description": (
        "Synthetic, deterministic demo data for demonstration, testing, presentation and viva: six individual "
        "personas and two households (the family and the full-pipeline household), seeded through the real public API by "
        "backend/scripts/seed_demo_data.py. Every financial result is computed by the application, never stored here."
    ),
    "not_for_training": (
        "This dataset is NOT a replacement for FAR-Trans or the Kaggle training dataset and MUST NOT be used as "
        "additional ML training data."
    ),
    "compatible_with": {"alembic_head": "f7a2d4b6c810", "api": "WealthPilot AI public API, Phases 21-36"},
    "transactions": {
        "included": False,
        "reason": (
            "The application cannot consume synthetic transactions: risk and behaviour features are read only from "
            "the immutable FAR-Trans CSVs, never from the database transactions table, so synthetic rows would be "
            "inert. A persona's real risk input is its risk_data_link to an existing FAR-Trans customer."
        ),
    },
}


class _Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.notes: list[str] = []

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _schema_errors(schema: type[BaseModel], payload: Any) -> str | None:
    try:
        schema.model_validate(payload)
    except ValidationError as exc:
        return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}" for e in exc.errors())
    return None


def _date_ok(value: Any) -> bool:
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        return False
    return 2000 <= parsed.year <= 2100


def _load_all(data_dir: Path, report: _Report) -> dict[str, Any]:
    """Every data file, parsed; format and source label checked on the way."""
    loaded: dict[str, Any] = {}
    for path in data_files(data_dir):
        rel = _rel(path, data_dir)
        text = path.read_text(encoding="utf-8")
        try:
            obj = read_json(path)
        except ValueError as exc:
            report.fail(f"{rel}: not valid JSON ({exc})")
            continue
        if text != canonical_json(obj):
            report.fail(f"{rel}: not in the canonical format (2-space indent, UTF-8, trailing newline)")
        if not isinstance(obj, dict) or obj.get("source") != SOURCE_LABEL:
            report.fail(f"{rel}: must be labelled \"source\": \"{SOURCE_LABEL}\"")
        loaded[rel] = obj
    return loaded


def _files_in(loaded: dict[str, Any], directory: str) -> dict[str, dict]:
    prefix = directory.rstrip("/") + "/"
    return {rel: obj for rel, obj in loaded.items()
            if rel.startswith(prefix) and "/" not in rel[len(prefix):] and isinstance(obj, dict)}


def _questionnaire_definition(report: _Report) -> list[dict] | None:
    try:
        from wealthpilot.api.services.questionnaire_service import get_questionnaire_sections

        return [q for section in get_questionnaire_sections() for q in section["questions"]]
    except Exception as exc:  # noqa: BLE001 - reported, never guessed around
        report.fail(f"questionnaire definition unavailable, answers cannot be checked: {type(exc).__name__}: {exc}")
        return None


def _far_trans_customer_ids(repo_root: Path, report: _Report) -> set[str] | None:
    path = repo_root / "datasets" / "raw" / "FAR-Trans" / "customer_information.csv"
    if not path.exists():
        report.note("FAR-Trans customer_information.csv not present -- risk_data_link targets not checked")
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["customerID"] for row in csv.DictReader(handle)}


def _check_personas(loaded: dict[str, Any], repo_root: Path, report: _Report) -> dict[str, dict]:
    """Returns demo_key -> profile file for every well-formed persona."""
    per_dir: dict[str, dict[str, str]] = {}          # dir -> stem -> demo_key
    by_key: dict[str, dict[str, dict]] = {}          # demo_key -> dir -> file
    for directory in PERSONA_DIRS:
        per_dir[directory] = {}
        for rel, obj in sorted(_files_in(loaded, directory).items()):
            key = obj.get("demo_key")
            if not isinstance(key, str) or not DEMO_KEY_RE.match(key):
                report.fail(f"{rel}: demo_key must look like WPDEMO-<ID>, found {key!r}")
                continue
            if directory in by_key.get(key, {}):
                report.fail(f"{directory}: duplicate demo_key {key!r} ({rel})")
                continue
            by_key.setdefault(key, {})[directory] = obj
            per_dir[directory][Path(rel).stem] = key
    for key, parts in sorted(by_key.items()):
        missing = [d for d in PERSONA_DIRS if d not in parts]
        if missing:
            report.fail(f"persona {key}: no file in {missing} (orphan or incomplete persona)")
    stems = per_dir["profiles"]
    for directory in PERSONA_DIRS[1:]:
        if per_dir[directory] != stems:
            report.fail(f"{directory}: file names and demo keys do not match profiles/ one-to-one")

    profiles = {k: p["profiles"] for k, p in by_key.items() if all(d in p for d in PERSONA_DIRS)}
    names: dict[str, str] = {}
    links: dict[str, str] = {}
    far_trans_ids = _far_trans_customer_ids(repo_root, report)
    definition = _questionnaire_definition(report)

    for key, parts in sorted(by_key.items()):
        if key not in profiles:
            continue
        profile_file, questionnaire, financial, goals_file = (parts[d] for d in PERSONA_DIRS)
        name = profile_file.get("customer_name")
        if not isinstance(name, str) or not name:
            report.fail(f"persona {key}: customer_name missing")
        elif name in names:
            report.fail(f"persona {key}: customer_name {name!r} duplicates persona {names[name]}")
        else:
            names[name] = key
        if not isinstance(profile_file.get("owned_by_seed"), bool):
            report.fail(f"persona {key}: owned_by_seed must be true or false")

        profile = profile_file.get("profile")
        if not isinstance(profile, dict):
            report.fail(f"persona {key}: profile payload missing")
        else:
            for field in sorted(set(profile) - PROFILE_FIELDS):
                report.fail(f"persona {key}: {field!r} is not a ProfileCreateRequest field")
            if profile.get("name") != name:
                report.fail(f"persona {key}: profile.name must equal customer_name")
            if error := _schema_errors(ProfileCreateRequest, profile):
                report.fail(f"persona {key}: ProfileCreateRequest rejects the profile: {error}")

        link = profile_file.get("risk_data_link", "absent")
        if link is None:
            if not str(profile_file.get("risk_data_link_unavailable_reason") or "").strip():
                report.fail(f"persona {key}: risk_data_link is null without a risk_data_link_unavailable_reason")
        elif not isinstance(link, dict) or not EXTERNAL_ID_RE.match(str(link.get("external_customer_id", ""))):
            report.fail(f"persona {key}: risk_data_link must be null or carry a 20-character FAR-Trans customerID")
        else:
            external = link["external_customer_id"]
            if external in links:
                report.fail(f"persona {key}: external_customer_id duplicates persona {links[external]}")
            links[external] = key
            if far_trans_ids is not None and external not in far_trans_ids:
                report.fail(f"persona {key}: external_customer_id {external} is not a FAR-Trans customer")

        _check_answers(key, questionnaire, definition, report, profile_file.get("demonstrates"))
        _check_financial_inputs(key, financial, report)
        _check_goals(key, goals_file, report)
    return profiles


def _check_answers(key: str, questionnaire: dict, definition: list[dict] | None, report: _Report,
                   demonstrates: Any = None) -> None:
    """Answers are curated per persona, not generated by a rule: each must be a
    real option of its question. Every persona answers every question except the
    pending-information persona, whose unanswered questions are intentional,
    declared, and part of why the application asks for more information."""
    answers = questionnaire.get("answers")
    if error := _schema_errors(QuestionnaireAnswersSubmitRequest, {"answers": answers}):
        report.fail(f"persona {key}: QuestionnaireAnswersSubmitRequest rejects the answers: {error}")
        return
    numbers = [a["question_number"] for a in answers]
    if len(numbers) != len(set(numbers)):
        report.fail(f"persona {key}: a question is answered more than once")
    if not str(questionnaire.get("answers_basis") or "").strip():
        report.fail(f"persona {key}: answers_basis is missing -- say why these answers fit the persona")
    complete = questionnaire.get("complete")
    if not isinstance(complete, bool):
        report.fail(f"persona {key}: questionnaire 'complete' must be true or false")
        return
    if definition is None:
        return
    by_number = {q["number"]: q for q in definition}
    unknown = set(numbers) - set(by_number)
    for number in sorted(unknown):
        report.fail(f"persona {key}: question {number} is not in the questionnaire")
    missing = sorted(set(by_number) - set(numbers))
    if complete:
        if missing:
            report.fail(f"persona {key}: marked complete but questions {missing} are unanswered")
    else:
        if demonstrates != "pending_information":
            report.fail(f"persona {key}: only the pending-information persona may leave questions unanswered")
        if not missing:
            report.fail(f"persona {key}: marked incomplete but every question is answered")
        elif questionnaire.get("unanswered_questions") != missing:
            report.fail(f"persona {key}: unanswered_questions must list exactly the unanswered questions {missing}")
    for answer in answers:
        question = by_number.get(answer["question_number"])
        if question is not None and answer["option_key"] not in {o["key"] for o in question["options"]}:
            report.fail(f"persona {key}: {answer['option_key']!r} is not an option of question {question['number']}")


def _check_financial_inputs(key: str, financial: dict, report: _Report) -> None:
    if "financial_inputs" not in financial:
        report.fail(f"persona {key}: financial_inputs key missing (use null plus a reason when not provided)")
        return
    inputs = financial["financial_inputs"]
    if inputs is None:
        if not str(financial.get("financial_inputs_unavailable_reason") or "").strip():
            report.fail(f"persona {key}: financial_inputs is null without a financial_inputs_unavailable_reason")
        return
    if not isinstance(inputs, dict) or not inputs:
        report.fail(f"persona {key}: financial_inputs must be an object or null")
        return
    for field in sorted(set(inputs) - FINANCIAL_INPUT_FIELDS):
        report.fail(f"persona {key}: {field!r} is not a FinancialInputsUpdate field")
    for field, value in inputs.items():
        if value is None:
            report.fail(f"persona {key}: financial_inputs.{field} is null -- omit an unknown field, never store it")
    if error := _schema_errors(FinancialInputsUpdate, inputs):
        report.fail(f"persona {key}: FinancialInputsUpdate rejects the inputs: {error}")
    omitted = sorted(FINANCIAL_INPUT_FIELDS - set(inputs))
    if omitted and not str(financial.get("financial_inputs_unavailable_reason") or "").strip():
        report.fail(f"persona {key}: {omitted} omitted without a financial_inputs_unavailable_reason")


def _check_goals(key: str, goals_file: dict, report: _Report) -> None:
    goals = goals_file.get("goals")
    if not isinstance(goals, list) or not goals:
        report.fail(f"persona {key}: goals must be a non-empty list")
        return
    priorities = []
    for goal in goals:
        for field in sorted(set(goal) - GOAL_FIELDS):
            report.fail(f"persona {key}: {field!r} is not a GoalCreate field")
        if error := _schema_errors(GoalCreate, goal):
            report.fail(f"persona {key}: GoalCreate rejects goal {goal.get('goal_type')!r}: {error}")
            continue
        if not _date_ok(goal["target_date"]):
            report.fail(f"persona {key}: goal {goal['goal_type']!r} has an out-of-range target_date")
        if goal.get("current_savings", 0) > goal["target_amount"]:
            report.fail(f"persona {key}: goal {goal['goal_type']!r} current_savings exceeds its target_amount")
        priorities.append(goal.get("priority", 1))
    if len(priorities) != len(set(priorities)):
        report.fail(f"persona {key}: two goals share a priority")


def _check_monthly_records(loaded: dict[str, Any], personas: dict[str, dict], report: _Report) -> None:
    """Reported months, only for personas that have a file: the payloads must be what `PUT .../monthly-financial-records/{YYYY-MM}` accepts, the months
    must be consecutive and unique, spending plus saving plus investing must not exceed income in any month, and the income must tell the same story as
    the persona's own annual income. Nothing is calculated that the application later reports: this compares the dataset's own numbers."""
    seen: set[str] = set()
    for rel, obj in sorted(_files_in(loaded, MONTHLY_RECORDS_DIR).items()):
        key = obj.get("demo_key")
        if key not in personas:
            report.fail(f"{rel}: demo_key {key!r} is not a persona")
            continue
        if key in seen:
            report.fail(f"{MONTHLY_RECORDS_DIR}: a second file for {key}")
        seen.add(key)
        if Path(rel).stem != _stem(loaded, "profiles", key).removesuffix(".json"):
            report.fail(f"{rel}: the file name must match the persona's other files")
        records = obj.get("records")
        if not isinstance(records, list) or len(records) < MIN_REPORTED_MONTHS:
            report.fail(f"{rel}: at least {MIN_REPORTED_MONTHS} reported months are needed for the behaviour findings")
            continue
        index: list[int] = []
        incomes: list[float] = []
        for record in records:
            period = record.get("period")
            match = MONTH_RE.match(str(period))
            if not match:
                report.fail(f"{rel}: period {period!r} must look like YYYY-MM")
                continue
            index.append(int(match.group(1)) * 12 + int(match.group(2)))
            payload = {k: v for k, v in record.items() if k != "period"}
            for field in sorted(set(payload) - MONTHLY_RECORD_FIELDS):
                report.fail(f"{rel}: {period}: {field!r} is not a MonthlyRecordUpdate field")
            if error := _schema_errors(MonthlyRecordUpdate, payload):
                report.fail(f"{rel}: {period}: MonthlyRecordUpdate rejects the record: {error}")
                continue
            if any(payload.get(f) is None for f in ("income", "expenses", "savings", "investment_contribution")):
                report.fail(f"{rel}: {period}: every amount is reported in this dataset (a missing month would be omitted, never zero-filled)")
                continue
            if payload["expenses"] + payload["savings"] + payload["investment_contribution"] > payload["income"]:
                report.fail(f"{rel}: {period}: spending, saving and investing exceed income")
            incomes.append(float(payload["income"]))
        if index != list(range(index[0], index[0] + len(index))) if index else True:
            report.fail(f"{rel}: the months must be consecutive, oldest first, with none repeated or skipped")
        profile_income = (personas[key].get("profile") or {}).get("income")
        if incomes and isinstance(profile_income, (int, float)):
            middle = sorted(incomes)[len(incomes) // 2]
            if not 0.6 * profile_income / 12 <= middle <= 1.4 * profile_income / 12:
                report.fail(f"{rel}: reported monthly income {middle:.0f} does not fit the persona's annual income {profile_income}")


def _check_household(loaded: dict[str, Any], personas: dict[str, dict], report: _Report) -> dict[str, dict]:
    households: dict[str, dict] = {}
    for rel, obj in sorted(_files_in(loaded, "household/households").items()):
        key = obj.get("demo_key")
        if not isinstance(key, str) or not DEMO_KEY_RE.match(key):
            report.fail(f"{rel}: demo_key must look like WPDEMO-<ID>")
            continue
        if key in households or key in personas:
            report.fail(f"{rel}: duplicate demo_key {key!r}")
            continue
        households[key] = obj
        if error := _schema_errors(HouseholdCreateRequest, {"name": obj.get("household_name")}):
            report.fail(f"household {key}: HouseholdCreateRequest rejects the name: {error}")
        if obj.get("primary_demo_key") not in personas:
            report.fail(f"household {key}: primary_demo_key {obj.get('primary_demo_key')!r} is an unknown persona")

    membership: dict[str, str] = {}
    members_seen: set[str] = set()
    for rel, obj in sorted(_files_in(loaded, "household/members").items()):
        hkey = obj.get("household_demo_key")
        if hkey not in households:
            report.fail(f"{rel}: household_demo_key {hkey!r} is an unknown household")
            continue
        if hkey in members_seen:
            report.fail(f"{rel}: a second members file for household {hkey}")
            continue
        members_seen.add(hkey)
        members = obj.get("members") or []
        primaries = [m for m in members if m.get("role") == "primary"]
        if len(primaries) != 1:
            report.fail(f"household {hkey}: must have exactly one primary member, found {len(primaries)}")
        for member in members:
            mkey = member.get("demo_key")
            if mkey not in personas:
                report.fail(f"household {hkey}: member {mkey!r} is an unknown persona")
                continue
            if mkey in membership:
                where = "twice in this household" if membership[mkey] == hkey else f"also in household {membership[mkey]}"
                report.fail(f"household {hkey}: persona {mkey} is {where} (a customer belongs to at most one household)")
                continue
            membership[mkey] = hkey
            relationship, role = member.get("relationship"), member.get("role")
            if role == "primary":
                if relationship != "self":
                    report.fail(f"household {hkey}: the primary member must have relationship 'self'")
                if mkey != households[hkey].get("primary_demo_key"):
                    report.fail(f"household {hkey}: the primary member is not the household's primary_demo_key")
            elif relationship == "self":
                report.fail(f"household {hkey}: relationship 'self' is reserved for the primary member")
            else:
                payload = {"customer_id": 1, "relationship": relationship, "role": role}
                if error := _schema_errors(HouseholdMemberCreateRequest, payload):
                    report.fail(f"household {hkey}: HouseholdMemberCreateRequest rejects member {mkey}: {error}")
    for hkey in households:
        if hkey not in members_seen:
            report.fail(f"household {hkey}: no members file")

    for resource, schema in RECORD_SCHEMAS.items():
        seen: set[str] = set()
        for rel, obj in sorted(_files_in(loaded, f"household/{resource}").items()):
            hkey = obj.get("household_demo_key")
            if hkey not in households:
                report.fail(f"{rel}: household_demo_key {hkey!r} is an unknown household")
                continue
            if hkey in seen:
                report.fail(f"{rel}: a second {resource} file for household {hkey}")
                continue
            seen.add(hkey)
            idem = obj.get("idempotency_key")
            records = obj.get("records")
            if not isinstance(records, list) or not records:
                report.fail(f"{rel}: records must be a non-empty list")
                continue
            keys = [r.get(idem) for r in records]
            if idem not in schema.model_fields or any(k is None for k in keys):
                report.fail(f"{rel}: idempotency_key {idem!r} must be a field every record carries")
            elif len(keys) != len(set(keys)):
                report.fail(f"{rel}: duplicate {idem} values -- the seed could not tell those records apart")
            for record in records:
                if error := _schema_errors(schema, record):
                    report.fail(f"{rel}: {schema.__name__} rejects {record.get(idem)!r}: {error}")
                    continue
                if resource == "goals":
                    if not _date_ok(record.get("target_date") or "2000-01-01"):
                        report.fail(f"{rel}: goal {record.get(idem)!r} has an out-of-range target_date")
                    if (record.get("current_savings") or 0) > record["target_amount"]:
                        report.fail(f"{rel}: goal {record.get(idem)!r} current_savings exceeds its target_amount")
        for hkey in households:
            if hkey not in seen:
                report.fail(f"household {hkey}: no {resource} file")
    return households


ANNUAL_INCOME_RANGE = (100_000, 10_000_000)       # rupees; outside this is an accidental value, not a persona
ADULT_AGE_RANGE = (18, 70)
EMERGENCY_TARGET_MONTHS = 6                        # core/goals.py's approved target; read here only to check consistency
MAX_SPOUSE_AGE_GAP = 15


def _annual(amount: float, frequency: str) -> float:
    return amount * {"monthly": 12, "yearly": 1}.get(frequency, 0)


def _check_plausibility(loaded: dict[str, Any], personas: dict[str, dict], households: dict[str, dict],
                        report: _Report) -> None:
    """Human-plausibility of the INPUTS (never of a computed result): incomes,
    spending, savings, goals and household records must tell a coherent
    financial story, and each persona's inputs must be able to cause the
    outcome it demonstrates through the application's own rules. Nothing here
    calculates a financial result -- it compares the dataset's own numbers."""
    expected = {obj.get("demo_key"): obj.get("expected") or {}
                for rel, obj in _files_in(loaded, "expected_results").items()}
    rule_ids: set[str] = set()
    try:
        import yaml

        rules = yaml.safe_load((REPO_ROOT / "config" / "compliance_rules.yaml").read_text(encoding="utf-8"))
        rule_ids = {r["id"] for r in rules["rules"]}
    except Exception as exc:  # noqa: BLE001 - reported, never guessed around
        report.fail(f"compliance rules unreadable, the Compliance persona cannot be checked: {type(exc).__name__}: {exc}")

    incomes: dict[str, float] = {}
    ages: dict[str, int] = {}
    for key, parts in sorted(personas.items()):
        profile = parts.get("profile") or {}
        financial = (loaded.get(f"financial_inputs/{_stem(loaded, 'financial_inputs', key)}") or {})
        goals_file = (loaded.get(f"individual_goals/{_stem(loaded, 'individual_goals', key)}") or {})
        status = expected.get(key, {}).get("analysis_status")
        income, age = profile.get("income"), profile.get("age")
        if not isinstance(income, (int, float)) or not ANNUAL_INCOME_RANGE[0] <= income <= ANNUAL_INCOME_RANGE[1]:
            report.fail(f"persona {key}: annual income {income!r} is outside the plausible range {ANNUAL_INCOME_RANGE}")
            continue
        incomes[key] = float(income)
        if not isinstance(age, int) or not ADULT_AGE_RANGE[0] <= age <= ADULT_AGE_RANGE[1]:
            report.fail(f"persona {key}: age {age!r} is outside {ADULT_AGE_RANGE}")
        else:
            ages[key] = age
        monthly_income = income / 12

        inputs = financial.get("financial_inputs") or {}
        essential, liquid = inputs.get("monthly_essential_expenses"), inputs.get("current_liquid_assets")
        contribution = inputs.get("contribution_amount")
        if essential is not None:
            if not 0.15 * monthly_income <= essential <= 0.75 * monthly_income:
                report.fail(f"persona {key}: essential spending {essential} is not a plausible share (15%-75%) of "
                            f"monthly income {monthly_income:.0f}")
        if contribution is not None:
            if contribution > monthly_income - (essential or 0):
                report.fail(f"persona {key}: the monthly contribution {contribution} exceeds what income leaves "
                            "after essential spending")
        if liquid is not None and liquid > income * 3:
            report.fail(f"persona {key}: easy-access savings {liquid} exceed three years of income")
        if inputs.get("annual_return_rate") is not None and not 0 <= inputs["annual_return_rate"] <= 0.25:
            report.fail(f"persona {key}: annual_return_rate is outside 0-25%")
        if inputs.get("annual_inflation_rate") is not None and not 0 <= inputs["annual_inflation_rate"] <= 0.15:
            report.fail(f"persona {key}: annual_inflation_rate is outside 0-15%")

        exp = expected.get(key, {})
        known = essential is not None and liquid is not None
        if status == "pending_information":
            if parts.get("risk_data_link") is not None:
                report.fail(f"persona {key}: expected pending information but a risk_data_link is provided")
        else:
            if parts.get("risk_data_link") is None:
                report.fail(f"persona {key}: expected {status!r} but no risk_data_link -- the risk model has no input")
            sufficient = exp.get("emergency_fund_sufficient")
            if sufficient is None and known:
                report.fail(f"persona {key}: expects an unknown emergency-fund position but both inputs are provided")
            if sufficient is not None:
                if not known:
                    report.fail(f"persona {key}: expects a known emergency-fund position but an input is missing")
                elif sufficient != (liquid >= EMERGENCY_TARGET_MONTHS * essential):
                    report.fail(f"persona {key}: emergency_fund_sufficient={sufficient} contradicts its inputs "
                                f"({liquid} liquid against {EMERGENCY_TARGET_MONTHS} x {essential} essential)")
        if exp.get("compliance_decision") == "REJECT":
            for rule in exp.get("triggered_compliance_rules") or []:
                if rule not in rule_ids:
                    report.fail(f"persona {key}: {rule!r} is not an existing compliance rule")

        for goal in goals_file.get("goals") or []:
            if isinstance(goal.get("target_amount"), (int, float)) and goal["target_amount"] < 50_000:
                report.fail(f"persona {key}: goal {goal.get('goal_type')!r} target is implausibly small")
            if not str(goal.get("goal_type") or "").strip() or str(goal["goal_type"]).strip().lower() in {
                    "goal", "test", "placeholder", "other"}:
                report.fail(f"persona {key}: goal name {goal.get('goal_type')!r} is a placeholder")

    for hkey, household in sorted(households.items()):
        def records(resource: str) -> list[dict]:
            return (loaded.get(f"household/{resource}/{_household_stem(loaded, resource, hkey)}") or {}).get("records") or []

        income = sum(_annual(r["amount"], r["frequency"]) for r in records("income") if r.get("is_active", True)) / 12
        expenses = [r for r in records("expenses") if r["frequency"] != "one_time"]
        spending = sum(_annual(r["amount"], r["frequency"]) for r in expenses) / 12
        essential = sum(_annual(r["amount"], r["frequency"]) for r in expenses if r["is_essential"]) / 12
        if spending > income:
            report.fail(f"household {hkey}: recurring spending {spending:.0f} exceeds recurring income {income:.0f} "
                        "without a stated reason")
        if essential > 0.75 * income:
            report.fail(f"household {hkey}: essential spending {essential:.0f} is over 75% of income {income:.0f}")
        liquid = sum(r["current_value"] for r in records("assets") if r.get("is_liquid"))
        if liquid <= 0:
            report.fail(f"household {hkey}: no liquid assets -- the emergency-fund balance would be empty")
        for liability in records("liabilities"):
            if (liability.get("monthly_payment") or 0) > 0 and liability["outstanding_amount"] <= 0:
                report.fail(f"household {hkey}: liability {liability['name']!r} has a payment but nothing outstanding")
        # Each EMI is recorded twice, by the demo's convention: as a liability's monthly payment and as a recurring debt_payment expense of the same size, so cash flow already
        # reflects it. The two totals must agree or the household's spending and its obligations tell different stories.
        payments = sum(liability.get("monthly_payment") or 0 for liability in records("liabilities"))
        debt_expenses = sum(_annual(r["amount"], r["frequency"]) for r in expenses if r["category"] == "debt_payment") / 12
        if abs(payments - debt_expenses) > 0.5:
            report.fail(f"household {hkey}: the monthly payments of its liabilities ({payments:.0f}) differ from its recurring "
                        f"debt_payment expenses ({debt_expenses:.0f})")
        members = [m for m in (loaded.get(f"household/members/{_household_stem(loaded, 'members', hkey)}") or {})
                   .get("members", []) if m.get("demo_key") in incomes]
        member_monthly = sum(incomes[m["demo_key"]] for m in members) / 12
        if members and not 0.4 * member_monthly <= income <= 1.5 * member_monthly:
            report.fail(f"household {hkey}: recurring income {income:.0f} is not consistent with its members' "
                        f"own annual incomes ({member_monthly:.0f} a month combined)")
        member_ages = [ages[m["demo_key"]] for m in members if m["demo_key"] in ages]
        if len(member_ages) == 2 and abs(member_ages[0] - member_ages[1]) > MAX_SPOUSE_AGE_GAP:
            report.fail(f"household {hkey}: the two members' ages differ by more than {MAX_SPOUSE_AGE_GAP} years")


def _stem(loaded: dict[str, Any], directory: str, key: str) -> str:
    for rel, obj in loaded.items():
        if rel.startswith(directory + "/") and isinstance(obj, dict) and obj.get("demo_key") == key:
            return rel.split("/", 1)[1]
    return ""


def _household_stem(loaded: dict[str, Any], resource: str, hkey: str) -> str:
    for rel, obj in loaded.items():
        if (rel.startswith(f"household/{resource}/") and isinstance(obj, dict)
                and obj.get("household_demo_key") == hkey):
            return rel.split("/", 2)[2]
    return ""


def _check_scenarios(loaded: dict[str, Any], personas: dict[str, dict], report: _Report) -> None:
    keys: set[str] = set()
    for rel, obj in sorted(_files_in(loaded, "scenarios").items()):
        for scenario in obj.get("scenarios") or []:
            skey = scenario.get("scenario_key")
            if skey in keys:
                report.fail(f"{rel}: duplicate scenario_key {skey!r}")
            keys.add(skey)
            if scenario.get("persona_demo_key") not in personas:
                report.fail(f"{rel}: scenario {skey} refers to an unknown persona")
            sides = {}
            for side in ("scenario_a", "scenario_b"):
                params = scenario.get(side)
                if not isinstance(params, dict) or set(params) - {"portfolio_strategy"}:
                    report.fail(f"{rel}: scenario {skey} {side} may vary portfolio_strategy only")
                    params = {}
                sides[side] = {"profile_id": 1, **params}
            if error := _schema_errors(ScenarioCompareRequest, sides):
                report.fail(f"{rel}: scenario {skey}: ScenarioCompareRequest rejects it: {error}")


def _check_expected(loaded: dict[str, Any], personas: dict[str, dict], households: dict[str, dict],
                    report: _Report) -> None:
    covered: set[str] = set()
    for rel, obj in sorted(_files_in(loaded, "expected_results").items()):
        key = obj.get("demo_key") or obj.get("household_demo_key")
        expected = obj.get("expected")
        if key in covered:
            report.fail(f"{rel}: a second expected-results file for {key}")
            continue
        covered.add(key)
        if not isinstance(expected, dict):
            report.fail(f"{rel}: expected must be an object")
            continue
        if key in personas:
            vocabulary = ANALYSIS_STATE_KEYS
        elif key in households:
            vocabulary = FAMILY_STATE_KEYS
        else:
            report.fail(f"{rel}: {key!r} is neither a persona nor a household")
            continue
        for field in sorted(set(expected) - set(vocabulary)):
            report.fail(f"{rel}: unknown expected-state key {field!r}")
        for field in sorted(set(vocabulary) - set(expected)):
            report.fail(f"{rel}: expected-state key {field!r} missing")
        if key in personas:
            _check_persona_expected(rel, expected, report)
        else:
            members = next((o.get("members") or [] for o in _files_in(loaded, "household/members").values()
                            if o.get("household_demo_key") == key), [])
            if expected.get("member_count") != len(members):
                report.fail(f"{rel}: member_count must equal the dataset's {len(members)} member(s)")
            if expected.get("primary_demo_key") != households[key].get("primary_demo_key"):
                report.fail(f"{rel}: primary_demo_key does not match the household file")
    for key in [*personas, *households]:
        if key not in covered:
            report.fail(f"expected_results: no file for {key}")


def _check_persona_expected(rel: str, expected: dict, report: _Report) -> None:
    for field in ("risk_available", "goal_results_returned", "goal_feasibility_available", "recommendation_available",
                  "portfolio_weights_available", "explanation_available"):
        if field in expected and not isinstance(expected[field], bool):
            report.fail(f"{rel}: {field} must be true or false")
    if not isinstance(expected.get("analysis_status"), str):
        report.fail(f"{rel}: analysis_status must be a status string")
    if expected.get("emergency_fund_sufficient") not in (True, False, None):
        report.fail(f"{rel}: emergency_fund_sufficient must be true, false or null (unknown)")
    if expected.get("compliance_decision") not in ("PASS", "WARN", "REJECT", None):
        report.fail(f"{rel}: compliance_decision must be PASS, WARN, REJECT or null")
    triggered = expected.get("triggered_compliance_rules")
    if (expected.get("compliance_decision") is None) != (triggered is None):
        report.fail(f"{rel}: triggered_compliance_rules is null exactly when compliance was not evaluated")
    if triggered is not None and not (isinstance(triggered, list) and all(isinstance(r, str) for r in triggered)):
        report.fail(f"{rel}: triggered_compliance_rules must be a list of rule ids or null")
    if expected.get("recommendation_available") is False and expected.get("recommendation_status") is not None:
        report.fail(f"{rel}: a recommendation_status without a recommendation")


def _check_seed_plan(loaded: dict[str, Any], report: _Report) -> None:
    plan = loaded.get("seed/seed_plan.json")
    if not isinstance(plan, dict):
        report.fail("seed/seed_plan.json missing")
        return
    reads: set[str] = set()
    for step in plan.get("steps") or []:
        value = step.get("reads")
        reads.update(value if isinstance(value, list) else [value] if value else [])
    needed = {*PERSONA_DIRS, MONTHLY_RECORDS_DIR, "household/households", "household/members",
              *(f"household/{r}" for r in HOUSEHOLD_RECORD_RESOURCES), "expected_results"}
    for directory in sorted(needed - reads):
        report.fail(f"seed/seed_plan.json: no step reads {directory}/")


def _check_separation(data_dir: Path, repo_root: Path, report: _Report) -> None:
    datasets = (repo_root / "datasets").resolve()
    if data_dir.resolve() == datasets or datasets in data_dir.resolve().parents:
        report.fail("demo_data/ must not live inside datasets/ -- demo data is kept apart from training data")
    for area in ("training", "backend/wealthpilot"):
        for path in sorted((repo_root / area).rglob("*.py")):
            if DEMO_DATA_REFERENCE.search(path.read_text(encoding="utf-8", errors="replace")):
                report.fail(f"{_rel(path, repo_root)} refers to demo_data -- only the seed and validator may read it")


def _alembic_head(repo_root: Path) -> str | None:
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in (repo_root / "backend" / "alembic" / "versions").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if match := re.search(r"^revision(?:\s*:\s*str)?\s*=\s*['\"]([^'\"]+)['\"]", text, re.M):
            revisions.add(match.group(1))
        if match := re.search(r"^down_revision[^=]*=\s*(.+)$", text, re.M):
            parents.update(re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)))
    heads = revisions - parents
    return next(iter(heads)) if len(heads) == 1 else None


# The guard protects the immutable raw TRAINING datasets (FAR-Trans, Kaggle: demo_data/README.md section 12, ADR-038). Every top-level folder under datasets/raw/ is guarded by default, so a
# new raw source cannot be added unguarded by accident; a folder is excluded only by being named here, with its reason. `gdelt` is the news-sentiment research acquisition area, not a training dataset:
# the sentiment pipeline writes to it during normal use (a live SQLite manifest with -wal/-shm sidecars, run logs, a temp folder, filtered output) and keeps its own provenance and manifest, so hashing
# it into a "never modified" guard would report false changes and couple this demo manifest to unrelated research data.
GUARD_EXCLUDED_RAW_SOURCES: frozenset[str] = frozenset({"gdelt"})


def guarded_raw_files(repo_root: Path) -> list[Path]:
    """Every file under datasets/raw/ that the training-data guard covers, in a stable order (the excluded sources and `.gitkeep` are left out)."""
    raw = repo_root / "datasets" / "raw"
    if not raw.exists():
        return []
    return [p for p in sorted(raw.rglob("*")) if p.is_file() and p.name != ".gitkeep" and p.relative_to(raw).parts[0] not in GUARD_EXCLUDED_RAW_SOURCES]


def training_data_hashes(repo_root: Path) -> dict[str, str]:
    return {_rel(p, repo_root): _sha256(p) for p in guarded_raw_files(repo_root)}


def check_training_data_guard(guard: dict[str, str], repo_root: Path) -> tuple[list[str], list[str]]:
    """(errors, notes): a recorded raw file whose bytes changed is an error; a
    recorded file absent from this checkout (datasets are not committed) is
    only noted, since there is nothing to compare."""
    errors: list[str] = []
    notes: list[str] = []
    for rel, recorded in sorted(guard.items()):
        path = repo_root / rel
        if not path.exists():
            notes.append(f"training-data guard: {rel} not present in this checkout (not compared)")
        elif _sha256(path) != recorded:
            errors.append(f"training-data guard: {rel} changed -- raw training data must never be modified")
    return errors, notes


def _counts(loaded: dict[str, Any]) -> dict[str, Any]:
    profiles = _files_in(loaded, "profiles").values()
    questionnaires = _files_in(loaded, "questionnaire").values()
    financial = _files_in(loaded, "financial_inputs").values()
    members = [m for f in _files_in(loaded, "household/members").values() for m in f.get("members") or []]
    records = {r: sum(len(f.get("records") or []) for f in _files_in(loaded, f"household/{r}").values())
               for r in HOUSEHOLD_RECORD_RESOURCES}
    scenario_files = list(_files_in(loaded, "scenarios").values())
    return {
        "data_files": len(loaded),
        "individual_personas": len(profiles),
        "personas_owned_by_seed": sum(1 for p in profiles if p.get("owned_by_seed") is True),
        "questionnaire_answer_sets": len(questionnaires),
        "questionnaire_answers": sum(len(q.get("answers") or []) for q in questionnaires),
        "financial_input_records_provided": sum(1 for f in financial if f.get("financial_inputs") is not None),
        "financial_input_records_not_provided": sum(1 for f in financial if f.get("financial_inputs") is None),
        "individual_goals": sum(len(g.get("goals") or []) for g in _files_in(loaded, "individual_goals").values()),
        "monthly_record_sets": len(_files_in(loaded, MONTHLY_RECORDS_DIR)),
        "monthly_records": sum(len(m.get("records") or []) for m in _files_in(loaded, MONTHLY_RECORDS_DIR).values()),
        "households": len(_files_in(loaded, "household/households")),
        "household_members": len(members),
        "household_financial_records": {r: records[r] for r in HOUSEHOLD_RECORD_RESOURCES if r != "goals"},
        "household_goals": records["goals"],
        "scenarios": sum(len(f.get("scenarios") or []) for f in scenario_files),
        "scenarios_not_supported_by_the_contract": sum(len(f.get("not_supported_by_the_contract") or [])
                                                       for f in scenario_files),
        "expected_result_sets": len(_files_in(loaded, "expected_results")),
        "transactions": 0,
    }


def _expected_outcomes(loaded: dict[str, Any]) -> dict[str, dict]:
    outcomes: dict[str, dict] = {}
    for obj in _files_in(loaded, "expected_results").values():
        key = obj.get("demo_key") or obj.get("household_demo_key")
        expected = obj.get("expected") or {}
        if "analysis_status" in expected:
            outcomes[key] = {"analysis_status": expected["analysis_status"],
                             "recommendation_status": expected.get("recommendation_status")}
        else:
            outcomes[key] = {"household_summary_available": expected.get("household_summary_available"),
                             "member_count": expected.get("member_count")}
    return dict(sorted(outcomes.items()))


def build_manifest(data_dir: Path = DEMO_DATA_DIR, repo_root: Path = REPO_ROOT,
                   header: dict[str, Any] | None = None) -> dict[str, Any]:
    """The manifest the files themselves produce: the (hand-maintained) header
    followed by counts, hashes and expected outcomes -- no timestamp, so the
    same files always give the same manifest."""
    loaded = {_rel(p, data_dir): read_json(p) for p in data_files(data_dir)}
    files = {_rel(p, data_dir): _sha256(p) for p in data_files(data_dir)}
    content = hashlib.sha256("".join(f"{rel}\t{sha}\n" for rel, sha in files.items()).encode("utf-8")).hexdigest()
    manifest = dict(header or DEFAULT_MANIFEST_HEADER)
    manifest.update({
        "deterministic_identifier": content,
        "counts": _counts(loaded),
        "expected_outcomes": _expected_outcomes(loaded),
        "files": files,
        "training_data_guard": training_data_hashes(repo_root),
    })
    return manifest


def _check_manifest(data_dir: Path, repo_root: Path, report: _Report, *, check_training_data: bool) -> None:
    path = data_dir / "manifest.json"
    if not path.exists():
        report.fail("manifest.json missing -- run with --write-manifest")
        return
    manifest = read_json(path)
    for field in MANIFEST_HEADER_REQUIRED:
        if field not in manifest:
            report.fail(f"manifest.json: {field!r} missing")
    if manifest.get("source") != SOURCE_LABEL:
        report.fail(f"manifest.json: source must be {SOURCE_LABEL!r}")
    if "MUST NOT" not in str(manifest.get("not_for_training", "")):
        report.fail("manifest.json: not_for_training must state the dataset MUST NOT be used for ML training")
    if not re.match(r"^\d+\.\d+\.\d+$", str(manifest.get("dataset_version", ""))):
        report.fail("manifest.json: dataset_version must be MAJOR.MINOR.PATCH")
    head = _alembic_head(repo_root)
    if (manifest.get("compatible_with") or {}).get("alembic_head") != head:
        report.fail(f"manifest.json: compatible_with.alembic_head is not the current Alembic head ({head})")

    header = {k: v for k, v in manifest.items() if k not in MANIFEST_COMPUTED}
    rebuilt = build_manifest(data_dir, repo_root, header)
    recorded_files = manifest.get("files") or {}
    for rel in sorted(set(rebuilt["files"]) - set(recorded_files)):
        report.fail(f"manifest.json: {rel} is not listed in the manifest")
    for rel in sorted(set(recorded_files) - set(rebuilt["files"])):
        report.fail(f"manifest.json: lists {rel}, which does not exist")
    for rel in sorted(set(recorded_files) & set(rebuilt["files"])):
        if recorded_files[rel] != rebuilt["files"][rel]:
            report.fail(f"manifest.json: sha256 of {rel} differs -- edited without regenerating the manifest")
    for field in ("deterministic_identifier", "counts", "expected_outcomes"):
        if manifest.get(field) != rebuilt[field]:
            report.fail(f"manifest.json: {field} is out of date with the files")
    if check_training_data:
        errors, notes = check_training_data_guard(manifest.get("training_data_guard") or {}, repo_root)
        for error in errors:
            report.fail(error)
        for note in notes:
            report.note(note)


def run_checks(data_dir: Path = DEMO_DATA_DIR, repo_root: Path = REPO_ROOT, *, check_manifest: bool = True,
               check_training_data: bool = True) -> _Report:
    report = _Report()
    for required in ("README.md", *PERSONA_DIRS, MONTHLY_RECORDS_DIR, "household/households", "household/members",
                     *(f"household/{r}" for r in HOUSEHOLD_RECORD_RESOURCES), "scenarios", "expected_results",
                     "seed"):
        if not (data_dir / required).exists():
            report.fail(f"required {required} missing from {data_dir.name}/")
    loaded = _load_all(data_dir, report)
    personas = _check_personas(loaded, repo_root, report)
    households = _check_household(loaded, personas, report)
    _check_scenarios(loaded, personas, report)
    _check_monthly_records(loaded, personas, report)
    _check_expected(loaded, personas, households, report)
    _check_plausibility(loaded, personas, households, report)
    _check_seed_plan(loaded, report)
    _check_separation(data_dir, repo_root, report)
    if check_manifest:
        _check_manifest(data_dir, repo_root, report, check_training_data=check_training_data)
    return report


def validate(data_dir: Path = DEMO_DATA_DIR, repo_root: Path = REPO_ROOT, *, check_manifest: bool = True,
             check_training_data: bool = True) -> list[str]:
    """Every validation error (empty when the dataset is valid)."""
    return run_checks(data_dir, repo_root, check_manifest=check_manifest,
                      check_training_data=check_training_data).errors


def write_manifest(data_dir: Path = DEMO_DATA_DIR, repo_root: Path = REPO_ROOT) -> Path:
    path = data_dir / "manifest.json"
    header = None
    if path.exists():
        header = {k: v for k, v in read_json(path).items() if k not in MANIFEST_COMPUTED}
    path.write_text(canonical_json(build_manifest(data_dir, repo_root, header)), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-manifest", action="store_true", help="regenerate demo_data/manifest.json first")
    parser.add_argument("--data-dir", type=Path, default=DEMO_DATA_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.write_manifest:
        pre = run_checks(args.data_dir, check_manifest=False)
        if pre.errors:
            print("\n".join(f"FAIL  {e}" for e in pre.errors))
            print(f"\nNOT WRITING THE MANIFEST: {len(pre.errors)} error(s) in the data")
            return 1
        print(f"wrote {write_manifest(args.data_dir)}")

    report = run_checks(args.data_dir)
    for note in report.notes:
        print(f"NOTE  {note}")
    for error in report.errors:
        print(f"FAIL  {error}")
    manifest_path = args.data_dir / "manifest.json"
    if not report.errors and manifest_path.exists():
        manifest = read_json(manifest_path)
        counts = manifest["counts"]
        print(f"dataset {manifest['dataset_version']} ({manifest['deterministic_identifier'][:12]}): "
              f"{counts['individual_personas']} personas, {counts['households']} household, "
              f"{counts['data_files']} data files, {len(manifest['training_data_guard'])} raw training files unchanged")
    print(f"\nDEMO DATA {'VALID' if not report.errors else f'INVALID: {len(report.errors)} error(s)'}")
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
