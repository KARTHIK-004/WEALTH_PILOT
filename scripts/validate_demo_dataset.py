"""Validates `demo_data/wealthpilot_complete_demo_dataset.csv` -- the whole
synthetic demo population as ONE flat table, one row per demo customer.

USAGE (repo root, venv active):

    python scripts/validate_demo_dataset.py               # validate; exit 0 valid, 1 invalid
    python scripts/validate_demo_dataset.py --regenerate  # re-export from the live app, then validate

Validation needs no database. It reads the CSV, the JSON demo dataset
package beside it (`demo_data/`, ADR-038) and the package manifest's hashes of
the raw training files.

`--regenerate` reads the REAL application in-process (FastAPI TestClient on
DATABASE_URL, no server) through its public API -- profiles, questionnaire
answers, financial inputs, household membership and summary, and each
persona's current analysis (`POST /api/analysis` returns the stored run while
the profile is unchanged) -- and writes what the API returns. No value is typed
by hand and none is calculated here: every figure is copied from an API
response; a value the API returns as null stays an empty cell.

The CSV is demo data. `training_eligible` is `false` on every row, and it must
never be used as ML training data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DATA_DIR = REPO_ROOT / "demo_data"
CSV_PATH = DEMO_DATA_DIR / "wealthpilot_complete_demo_dataset.csv"

GOAL_FIELDS = ("type", "target_amount", "target_date", "current_savings", "priority", "feasibility",
               "monte_carlo_success_probability", "unavailable_reason")
HOUSEHOLD_SUMMARY_COLUMNS = (
    "household_recurring_monthly_income",
    "household_recurring_monthly_expenses",
    "household_monthly_cash_flow",
    "household_total_assets",
    "household_liquid_assets",
    "household_outstanding_liabilities",
    "household_net_position",
    "household_emergency_fund_required",
    "household_emergency_fund_shortfall",
    "household_emergency_fund_status",
)
HOUSEHOLD_COLUMNS = ("household_id", "household_name", *HOUSEHOLD_SUMMARY_COLUMNS)
FINANCIAL_INPUT_COLUMNS = ("monthly_essential_expenses", "current_liquid_assets", "contribution_amount",
                           "annual_return_rate", "annual_inflation_rate", "contribution_periods_per_year")
COLUMNS = (
    # identity
    "demo_customer_id", "demo_persona", "demo_user_name", "demo_type",
    "household_id", "household_name", "household_role", "household_relationship", "is_dependent",
    # profile
    "customer_type", "age", "employment_status", "annual_income", "investment_capacity",
    # questionnaire
    "questionnaire_completed", "questionnaire_answers_recorded", "questionnaire_questions_total",
    # financial inputs
    "currency", *FINANCIAL_INPUT_COLUMNS, "financial_inputs_unavailable_reason",
    # emergency fund (individual analysis)
    "emergency_fund_sufficient", "emergency_fund_required_amount", "emergency_fund_current_amount",
    "emergency_fund_shortfall", "emergency_fund_unavailable_reason",
    # goals
    *(f"goal_{n}_{field}" for n in (1, 2, 3) for field in GOAL_FIELDS),
    # risk
    "risk_category", "risk_confidence", "risk_unavailable_reason",
    # portfolio
    "portfolio_weights_available", "portfolio_strategy", "qqq_weight", "agg_weight", "gld_weight",
    "portfolio_expected_return", "portfolio_expected_volatility", "portfolio_sharpe_ratio",
    # recommendation and compliance
    "recommendation_status", "recommendation_selected_strategy", "compliance_decision", "compliance_triggered_rules",
    # analysis
    "analysis_id", "analysis_status", "explanation_available",
    # household financial summary (repeated on every member row, never summed)
    *HOUSEHOLD_SUMMARY_COLUMNS,
    # demo purpose
    "demo_description", "expected_demo_flow", "notes",
    # dataset separation
    "data_source", "training_eligible", "dataset_purpose",
)
NUMERIC_COLUMNS = {
    "demo_customer_id", "household_id", "age", "annual_income", "questionnaire_answers_recorded",
    "questionnaire_questions_total", *FINANCIAL_INPUT_COLUMNS, "emergency_fund_required_amount",
    "emergency_fund_current_amount", "emergency_fund_shortfall",
    *(f"goal_{n}_{f}" for n in (1, 2, 3) for f in ("target_amount", "current_savings", "priority",
                                                     "monte_carlo_success_probability")),
    "risk_confidence", "qqq_weight", "agg_weight", "gld_weight", "portfolio_expected_return",
    "portfolio_expected_volatility", "portfolio_sharpe_ratio", "analysis_id",
    *(c for c in HOUSEHOLD_SUMMARY_COLUMNS if c != "household_emergency_fund_status"),
}
BOOLEAN_COLUMNS = {"is_dependent", "questionnaire_completed", "emergency_fund_sufficient",
                   "portfolio_weights_available", "explanation_available", "training_eligible"}
# A value group and the reason column that explains why it is missing.
REASON_GROUPS = {
    "financial_inputs_unavailable_reason": FINANCIAL_INPUT_COLUMNS,
    "emergency_fund_unavailable_reason": ("emergency_fund_sufficient", "emergency_fund_required_amount",
                                          "emergency_fund_current_amount", "emergency_fund_shortfall"),
    "risk_unavailable_reason": ("risk_category", "risk_confidence"),
    **{f"goal_{n}_unavailable_reason": (f"goal_{n}_feasibility", f"goal_{n}_monte_carlo_success_probability")
       for n in (1, 2, 3)},
}
PERSONAS = {  # dataset key -> (persona label, canonical customer id in this environment)
    "WPDEMO-A": ("APPROVED", "29107"),
    "WPDEMO-B": ("SAVINGS_FIRST", "29108"),
    "WPDEMO-C": ("COMPLIANCE_REJECTED", "29109"),
    "WPDEMO-D": ("PENDING_INFORMATION", "29096"),
}
FAMILY = {"household_id": "8", "household_name": "WealthPilot Demo Family",
          "members": {"29108": ("primary", "self"), "29109": ("member", "spouse")}}
CONSTANTS = {"data_source": "synthetic_demo", "training_eligible": "false",
             "dataset_purpose": "demo_testing_presentation", "currency": "EUR", "demo_type": "INDIVIDUAL"}
EXPECTED_DEMO_FLOW = {
    "WPDEMO-A": ("Use Individual Demo login > Dashboard > Risk Assessment > Financial Health > Goals > Portfolio "
                 "> Recommendation > Why This Recommendation (Simple and Detailed) > Scenario Simulator > "
                 "Agent Activity"),
    "WPDEMO-B": ("Use Family Demo login (resolves to this customer) > Customer Profile with the Household section "
                 "open > members / records / financial summary / household goals > own pages show savings first "
                 "with no portfolio weights"),
    "WPDEMO-C": ("No in-app login (one customer per session, no switcher): shown through the API docs (/docs) - "
                 "GET /api/profiles/lookup by name, then GET /api/analysis/{analysis_id} - compliance REJECT; "
                 "appears in the family view as the spouse (identity only)"),
    "WPDEMO-D": ("No in-app login while the Complete persona is seeded: shown through the API docs (/docs) - "
                 "analysis status pending_information with nothing downstream"),
}
NOTES = {
    "WPDEMO-A": ("Individual demo persona; in no household. The AGG weight is copied exactly as stored (a "
                 "floating-point value of about 1.7e-16), which the application displays as 0%."),
    "WPDEMO-B": ("Also the primary (self) of household 8. The household columns describe the household and are "
                 "repeated on each member row - they are not this customer's own figures and never enter the "
                 "individual analysis."),
    "WPDEMO-C": ("Also the spouse (member) of household 8. Financial inputs are deliberately not provided, so the "
                 "emergency fund is unknown and the compliance gate rejects fail-closed."),
    "WPDEMO-D": ("Phase 24 canonical demo customer (lowest id with this name). Emergency fund, goals, "
                 "compliance, portfolio, recommendation and explanation are not evaluated because the analysis "
                 "stops at pending_information."),
}
NULL_TOKENS = {"null", "none", "nan", "n/a", "na", "undefined", "nil", "-"}
SECRET_PATTERNS = re.compile(r"(AIza[0-9A-Za-z_\-]{20,}|postgres(ql)?(\+\w+)?://|password|passwd|api[_-]?key|"
                             r"secret|bearer\s+[a-z0-9]|-----BEGIN)", re.IGNORECASE)
NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")


def cell(value: Any) -> str:
    """One value as a CSV cell: null -> empty; booleans lowercase; a
    whole-number float without a trailing .0; any other float as its exact
    shortest representation (the stored value, unrounded)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() and abs(value) < 1e15 else repr(value)
    return str(value)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _package() -> dict[str, dict]:
    """The JSON demo dataset package, per dataset key."""
    parts: dict[str, dict] = {}
    for directory in ("profiles", "financial_inputs", "individual_goals", "expected_results"):
        for path in sorted((DEMO_DATA_DIR / directory).glob("*.json")):
            obj = _read_json(path)
            key = obj.get("demo_key") or obj.get("household_demo_key")
            parts.setdefault(key, {})[directory] = obj
    return parts


# ---------------------------------------------------------------------------
# Export (--regenerate): API responses in, rows out -- copying, never computing
# ---------------------------------------------------------------------------


def fetch_snapshot(client) -> dict:
    """Read-only reads of the live application for every persona and household."""
    package = _package()
    snapshot: dict = {"personas": {}, "households": {},
                      "questionnaire_questions_total": sum(
                          len(s["questions"]) for s in client.get("/api/questionnaire").raise_for_status().json()["sections"])}
    for key in PERSONAS:
        name = package[key]["profiles"]["customer_name"]
        cid = client.get("/api/profiles/lookup", params={"name": name}).raise_for_status().json()["customer_id"]
        if cid is None:
            raise SystemExit(f"persona {name!r} not found -- run `seed_demo_data.py setup` first")
        who = {"X-Customer-Id": str(cid)}
        household = client.get(f"/api/profiles/{cid}/household", headers=who).raise_for_status().json()
        snapshot["personas"][key] = {
            "profile": client.get(f"/api/profiles/{cid}").raise_for_status().json(),
            "questionnaire": client.get(f"/api/profiles/{cid}/questionnaire").raise_for_status().json(),
            "financial_inputs": client.get(f"/api/profiles/{cid}/financial-inputs").raise_for_status().json(),
            "household": household,
            "analysis": client.post("/api/analysis", json={"profile_id": cid}).raise_for_status().json(),
        }
        if household["household"] is not None:
            hid = household["household"]["id"]
            if hid not in snapshot["households"]:
                snapshot["households"][hid] = client.get(
                    f"/api/households/{hid}/financial-summary", headers=who).raise_for_status().json()
    return snapshot


def build_rows(snapshot: dict) -> list[dict[str, str]]:
    package = _package()
    total_questions = snapshot["questionnaire_questions_total"]
    rows = []
    for key, (label, _) in PERSONAS.items():
        data = snapshot["personas"][key]
        profile, analysis = data["profile"], data["analysis"]
        inputs = data["financial_inputs"]
        answers = data["questionnaire"]["answers"]
        household, membership = data["household"]["household"], data["household"]["membership"]
        row: dict[str, Any] = {
            "demo_customer_id": profile["customer_id"], "demo_persona": label, "demo_user_name": profile["name"],
            "demo_type": CONSTANTS["demo_type"],
            "household_id": household and household["id"], "household_name": household and household["name"],
            "household_role": membership and membership["role"],
            "household_relationship": membership and membership["relationship"],
            "is_dependent": membership and membership["is_dependent"],
            "customer_type": profile["customer_type"], "age": profile["age"],
            "employment_status": profile["employment_status"], "annual_income": profile["income"],
            "investment_capacity": profile["investment_capacity"],
            "questionnaire_completed": len({a["question_number"] for a in answers}) == total_questions,
            "questionnaire_answers_recorded": len(answers), "questionnaire_questions_total": total_questions,
            "currency": CONSTANTS["currency"],
            **{c: inputs[c] for c in FINANCIAL_INPUT_COLUMNS},
            "financial_inputs_unavailable_reason":
                package[key]["financial_inputs"].get("financial_inputs_unavailable_reason")
                if all(inputs[c] is None for c in FINANCIAL_INPUT_COLUMNS) else None,
        }
        ef = analysis.get("emergency_fund") or {}
        row.update({
            "emergency_fund_sufficient": ef.get("sufficient"), "emergency_fund_required_amount": ef.get("required_amount"),
            "emergency_fund_current_amount": ef.get("current_amount"), "emergency_fund_shortfall": ef.get("shortfall"),
            "emergency_fund_unavailable_reason": ef.get("unavailable_reason"),
        })
        results = {g["goal_id"]: g for g in analysis.get("goals") or []}
        goals = sorted(profile["goals"], key=lambda g: (g["priority"], g["id"]))
        for n in (1, 2, 3):
            goal = goals[n - 1] if n <= len(goals) else None
            result = results.get(goal["id"], {}) if goal else {}
            row.update({
                f"goal_{n}_type": goal and goal["goal_type"], f"goal_{n}_target_amount": goal and goal["target_amount"],
                f"goal_{n}_target_date": goal and goal["target_date"],
                f"goal_{n}_current_savings": goal and goal["current_savings"], f"goal_{n}_priority": goal and goal["priority"],
                f"goal_{n}_feasibility": result.get("feasibility"),
                f"goal_{n}_monte_carlo_success_probability": result.get("monte_carlo_success_probability"),
                f"goal_{n}_unavailable_reason": result.get("unavailable_reason"),
            })
        risk = analysis.get("risk") or {}
        portfolio = analysis.get("portfolio") or {}
        weights = portfolio.get("weights") or {}
        compliance = analysis.get("compliance")
        recommendation = analysis.get("recommendation")
        row.update({
            "risk_category": risk.get("risk_category"), "risk_confidence": risk.get("confidence"),
            "risk_unavailable_reason": risk.get("unavailable_reason"),
            "portfolio_weights_available": bool(weights), "portfolio_strategy": portfolio.get("strategy"),
            "qqq_weight": weights.get("QQQ"), "agg_weight": weights.get("AGG"), "gld_weight": weights.get("GLD"),
            "portfolio_expected_return": portfolio.get("expected_return"),
            "portfolio_expected_volatility": portfolio.get("expected_volatility"),
            "portfolio_sharpe_ratio": portfolio.get("sharpe_ratio"),
            "recommendation_status": recommendation and recommendation.get("status"),
            "recommendation_selected_strategy": recommendation and recommendation.get("selected_strategy"),
            "compliance_decision": compliance and compliance.get("decision"),
            "compliance_triggered_rules": compliance and ";".join(
                sorted(r["rule_id"] for r in compliance.get("rule_results") or [] if r.get("triggered"))),
            "analysis_id": analysis["analysis_id"], "analysis_status": analysis["status"],
            "explanation_available": analysis.get("explanation") is not None,
        })
        summary = snapshot["households"].get(household["id"]) if household else None
        row.update({c: None for c in HOUSEHOLD_SUMMARY_COLUMNS})
        if summary:
            row.update({
                "household_recurring_monthly_income": summary["income"]["recurring_monthly"],
                "household_recurring_monthly_expenses": summary["expenses"]["recurring_monthly"],
                "household_monthly_cash_flow": summary["cash_flow"]["monthly"],
                "household_total_assets": summary["assets"]["total"],
                "household_liquid_assets": summary["assets"]["liquid"],
                "household_outstanding_liabilities": summary["liabilities"]["outstanding"],
                "household_net_position": summary["net_position"]["value"],
                "household_emergency_fund_required": summary["emergency_fund"]["required"],
                "household_emergency_fund_shortfall": summary["emergency_fund"]["shortfall"],
                "household_emergency_fund_status": summary["emergency_fund"]["status"],
            })
        row.update({
            "demo_description": package[key]["profiles"]["purpose"], "expected_demo_flow": EXPECTED_DEMO_FLOW[key],
            "notes": NOTES[key], "data_source": CONSTANTS["data_source"],
            "training_eligible": CONSTANTS["training_eligible"], "dataset_purpose": CONSTANTS["dataset_purpose"],
        })
        rows.append({c: cell(row[c]) for c in COLUMNS})
    return rows


def render_csv(rows: list[dict[str, str]]) -> bytes:
    """UTF-8 with a byte-order mark (so Excel reads the em dashes correctly),
    comma-delimited, fields quoted only where needed, CRLF line endings."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def regenerate(path: Path = CSV_PATH) -> None:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    sys.path.insert(0, str(REPO_ROOT))  # `training.*`, imported by the app at startup
    from fastapi.testclient import TestClient

    from wealthpilot.api.main import app

    with TestClient(app) as client:
        snapshot = fetch_snapshot(client)
    path.write_bytes(render_csv(build_rows(snapshot)))
    print(f"wrote {path} from the live application")


# ---------------------------------------------------------------------------
# Validation -- no database
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(path: Path = CSV_PATH) -> tuple[list[str], dict]:
    """(errors, facts) -- errors is empty when the CSV is valid."""
    errors: list[str] = []
    facts: dict = {}
    if not path.exists():
        return [f"{path} does not exist"], facts
    raw = path.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        errors.append("no UTF-8 byte-order mark: Excel would show the em dashes in names incorrectly")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return [f"not UTF-8: {exc}"], facts
    try:
        table = list(csv.reader(io.StringIO(text, newline=""), delimiter=","))
    except csv.Error as exc:
        return [f"not a loadable CSV: {exc}"], facts
    if not table:
        return ["the CSV is empty"], facts
    header, body = table[0], table[1:]
    facts.update(rows=len(body), columns=len(header))
    if len(header) != len(set(header)):
        errors.append(f"duplicate column names: {sorted({h for h in header if header.count(h) > 1})}")
    missing = [c for c in COLUMNS if c not in header]
    if missing:
        errors.append(f"required columns missing: {missing}")
    elif tuple(header) != COLUMNS:
        errors.append("columns are not in the documented order")
    if any(r == header for r in body):
        errors.append("the header row appears more than once")
    rows = []
    for number, values in enumerate(body, start=2):
        if len(values) != len(header):
            errors.append(f"line {number}: {len(values)} fields, the header has {len(header)}")
            continue
        rows.append(dict(zip(header, values)))
    if errors and missing:
        return errors, facts

    for row in rows:
        rid = row.get("demo_customer_id", "?")
        for column, value in row.items():
            if "\n" in value or "\r" in value:
                errors.append(f"customer {rid}: {column} contains a line break")
            if value[:1] in ("=", "+", "@") or (value.startswith("-") and not NUMBER_RE.match(value)):
                errors.append(f"customer {rid}: {column} starts like a spreadsheet formula")
            if value.strip().lower() in NULL_TOKENS:
                errors.append(f"customer {rid}: {column} is {value!r} -- a missing value must be an empty cell")
            if SECRET_PATTERNS.search(value):
                errors.append(f"customer {rid}: {column} looks like a credential or connection string")
            if value and column in NUMERIC_COLUMNS and not NUMBER_RE.match(value):
                errors.append(f"customer {rid}: {column} = {value!r} is not a number")
            if value and column in BOOLEAN_COLUMNS and value not in ("true", "false"):
                errors.append(f"customer {rid}: {column} = {value!r} is not true/false")
        for column, expected in CONSTANTS.items():
            if row.get(column) != expected:
                errors.append(f"customer {rid}: {column} must be {expected!r}, found {row.get(column)!r}")
        for reason, group in REASON_GROUPS.items():
            if row.get(reason):
                for column in group:
                    if row.get(column):
                        errors.append(f"customer {rid}: {column} = {row[column]!r} although {reason} says it is "
                                      "unavailable -- a missing value must stay empty, never 0")

    ids = [r["demo_customer_id"] for r in rows]
    if len(ids) != len(set(ids)):
        errors.append(f"duplicate demo_customer_id: {sorted({i for i in ids if ids.count(i) > 1})}")
    by_id = {r["demo_customer_id"]: r for r in rows}
    package = _package()
    for key, (label, cid) in PERSONAS.items():
        matches = [r for r in rows if r["demo_persona"] == label]
        if len(matches) != 1:
            errors.append(f"persona {label}: expected exactly one row, found {len(matches)}")
        row = by_id.get(cid)
        if row is None:
            errors.append(f"required customer {cid} ({label}) is missing")
            continue
        if row["demo_persona"] != label:
            errors.append(f"customer {cid}: demo_persona must be {label}, found {row['demo_persona']!r}")
        errors.extend(_cross_check(cid, row, package.get(key, {})))

    households: dict[str, list[dict]] = {}
    for row in rows:
        if row["household_id"]:
            households.setdefault(row["household_id"], []).append(row)
        elif any(row[c] for c in (*HOUSEHOLD_COLUMNS, "household_role", "household_relationship", "is_dependent")):
            errors.append(f"customer {row['demo_customer_id']}: household columns filled without a household_id")
    facts["households"] = {hid: sorted(r["demo_customer_id"] for r in members) for hid, members in households.items()}
    family = households.get(FAMILY["household_id"])
    if not family:
        errors.append(f"household {FAMILY['household_id']} is missing")
    else:
        if {r["demo_customer_id"] for r in family} != set(FAMILY["members"]):
            errors.append(f"household {FAMILY['household_id']} members must be {sorted(FAMILY['members'])}")
        for row in family:
            expected = FAMILY["members"].get(row["demo_customer_id"])
            if expected and (row["household_role"], row["household_relationship"]) != expected:
                errors.append(f"customer {row['demo_customer_id']}: must be {expected[0]}/{expected[1]} in household "
                              f"{FAMILY['household_id']}, found {row['household_role']}/{row['household_relationship']}")
            if row["household_name"] != FAMILY["household_name"]:
                errors.append(f"customer {row['demo_customer_id']}: household_name must be {FAMILY['household_name']!r}")
    for hid, members in households.items():
        primaries = [r for r in members if r["household_role"] == "primary"]
        if len(primaries) != 1:
            errors.append(f"household {hid}: exactly one primary member required, found {len(primaries)}")
        for row in members:
            if (row["household_role"] == "primary") != (row["household_relationship"] == "self"):
                errors.append(f"customer {row['demo_customer_id']}: 'self' and 'primary' must go together")
            if row["household_relationship"] == "self" and row["is_dependent"] != "false":
                errors.append(f"customer {row['demo_customer_id']}: the primary (self) is never a dependent")
        for column in HOUSEHOLD_COLUMNS:
            values = {r[column] for r in members}
            if len(values) != 1:
                errors.append(f"household {hid}: {column} differs between member rows ({sorted(values)}) -- "
                              "household values are repeated on each row, never summed or split")
        if not members[0]["household_emergency_fund_status"]:
            errors.append(f"household {hid}: household summary values are missing")

    errors.extend(_training_data_unchanged())
    return errors, facts


def _cross_check(cid: str, row: dict, package: dict) -> list[str]:
    """The CSV must say what the JSON demo package says -- the same data in two
    shapes. A value the package leaves null must be an empty cell here."""
    errors = []
    profile_file = package.get("profiles", {})
    profile = profile_file.get("profile", {})
    for column, field in (("demo_user_name", "name"), ("customer_type", "customer_type"), ("age", "age"),
                          ("employment_status", "employment_status"), ("annual_income", "income"),
                          ("investment_capacity", "investment_capacity")):
        if row[column] != cell(profile.get(field)) and not _same_number(row[column], profile.get(field)):
            errors.append(f"customer {cid}: {column} {row[column]!r} differs from the demo package ({profile.get(field)!r})")
    inputs = package.get("financial_inputs", {}).get("financial_inputs")
    for column in FINANCIAL_INPUT_COLUMNS:
        source = None if inputs is None else inputs.get(column)
        if source is None and row[column]:
            errors.append(f"customer {cid}: {column} = {row[column]!r}, but the demo package records it as not "
                          "provided -- a missing value must stay empty, never 0")
        elif source is not None and not _same_number(row[column], source):
            errors.append(f"customer {cid}: {column} {row[column]!r} differs from the demo package ({source!r})")
    for n, goal in enumerate(package.get("individual_goals", {}).get("goals", []), start=1):
        if n > 3:
            break
        for field, key in (("type", "goal_type"), ("target_date", "target_date")):
            if row[f"goal_{n}_{field}"] != str(goal[key]):
                errors.append(f"customer {cid}: goal_{n}_{field} differs from the demo package")
        for field in ("target_amount", "current_savings", "priority"):
            if not _same_number(row[f"goal_{n}_{field}"], goal[field]):
                errors.append(f"customer {cid}: goal_{n}_{field} differs from the demo package")
    expected = package.get("expected_results", {}).get("expected", {})
    for column, state in (("analysis_status", "analysis_status"), ("recommendation_status", "recommendation_status"),
                          ("compliance_decision", "compliance_decision"),
                          ("explanation_available", "explanation_available"),
                          ("emergency_fund_sufficient", "emergency_fund_sufficient"),
                          ("portfolio_weights_available", "portfolio_weights_available")):
        if state in expected and row[column] != cell(expected[state]):
            errors.append(f"customer {cid}: {column} {row[column]!r} differs from the expected state "
                          f"{cell(expected[state])!r}")
    triggered = expected.get("triggered_compliance_rules")
    if "triggered_compliance_rules" in expected and row["compliance_triggered_rules"] != ";".join(triggered or []):
        errors.append(f"customer {cid}: compliance_triggered_rules differs from the expected state")
    return errors


def _same_number(text: str, value: Any) -> bool:
    if value is None:
        return text == ""
    try:
        return float(text) == float(value)
    except ValueError:
        return False


def _training_data_unchanged() -> list[str]:
    """The raw FAR-Trans / Kaggle files still have the SHA-256 hashes recorded
    in the demo package manifest (files absent from a checkout are skipped)."""
    manifest = DEMO_DATA_DIR / "manifest.json"
    if not manifest.exists():
        return ["demo_data/manifest.json missing -- cannot confirm the raw training data is unchanged"]
    errors = []
    for rel, recorded in sorted(_read_json(manifest).get("training_data_guard", {}).items()):
        path = REPO_ROOT / rel
        if path.exists() and _sha256(path) != recorded:
            errors.append(f"raw training file {rel} has changed -- it must never be modified")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--regenerate", action="store_true",
                        help="re-export the CSV from the live application (reads DATABASE_URL), then validate")
    args = parser.parse_args(argv)
    if args.regenerate:
        regenerate()
    errors, facts = validate()
    for error in errors:
        print(f"FAIL  {error}")
    if facts:
        print(f"{CSV_PATH.relative_to(REPO_ROOT).as_posix()}: {facts.get('rows')} rows x {facts.get('columns')} columns; "
              f"households {facts.get('households', {})}")
    print(f"\nDEMO DATASET CSV {'VALID' if not errors else f'INVALID: {len(errors)} error(s)'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
