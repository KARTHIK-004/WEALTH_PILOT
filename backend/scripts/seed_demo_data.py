"""Demo Data phase — deterministic, idempotent seed/setup for WealthPilot
AI's synthetic demo population.

USAGE (from `backend/`, with the venv active and a backend server already
running — see `--base-url` — or with `--in-process`, which runs every mode
through the real app in-process instead, with no server):

    python scripts/seed_demo_data.py setup
    python scripts/seed_demo_data.py verify
    python scripts/seed_demo_data.py reset

FAMILY DEMO (after `setup`):

    python scripts/seed_demo_data.py setup-family
    python scripts/seed_demo_data.py verify-family
    python scripts/seed_demo_data.py reset-family

THE DATA lives in `demo_data/` (see its README) -- the single source of every
persona, household record, scenario input and expected outcome this script
uses; `demo_data_package.py` loads it and `validate_demo_data.py` checks it.
`setup` seeds all four individual personas: the three this script owns and
Phase 24's canonical "WealthPilot Demo Customer" (the pending-information
persona), which it only creates if it is missing and which `reset` never
deletes. `verify` also checks each persona's analysis against its expected
contract-level states in `demo_data/expected_results/`.

The family demo is ONE canonical household, "WealthPilot Demo Family", built
from two EXISTING personas -- "WealthPilot Demo — Savings" as its primary
member and "WealthPilot Demo — Compliance" as the spouse -- plus a small,
synthetic, household-level set of income, expenses, assets, liabilities and
goals. It goes entirely through the real public household API (Phases 32-36):
no direct database write, no new customer record, no change to either
persona's individual profile, questionnaire, goals, financial inputs or
analysis (household membership is contextual identity only -- ADR-031). The
individual-demo personas "WealthPilot Demo — Complete" and "WealthPilot Demo
Customer" are deliberately NOT members, so the individual demo is unchanged.
See `reports/family_demo_report.md`.

DESIGN
------

This script is the ONLY place, besides Phase 24's existing frontend
`lib/demo-customer.ts`, that creates a "WealthPilot Demo" identity. It
creates THREE new, clearly-synthetic customer identities (distinct from
Phase 24's own canonical "WealthPilot Demo Customer", which this script
never touches) via the REAL, unmodified public API:

    POST /api/profiles                          (Phase 21)
    POST /api/profiles/{id}/questionnaire        (Phase 23)
    POST /api/profiles/{id}/goals                (Phase 23)
    POST /api/analysis                           (Phase 15)

The ONE thing the public API has no endpoint for — and was never meant to,
since it is an internal data-provenance field, not a user-editable one —
is `Customer.risk_inputs.external_customer_id`, the mapping
`agents/nodes.py::engineer_features_for_customer` uses to find a real
customer's row in the immutable raw FAR-Trans CSVs. `data/ingestion.py`
sets it once for FAR-Trans's own ~21,629 real customers at initial load
time; nothing else in this codebase ever sets it, and no Pydantic schema
exposes it. Populating it for a NEW demo identity is therefore the one
genuinely necessary direct database write this script performs — a single
`UPDATE customers SET risk_inputs = ... WHERE id = <the id POST
/api/profiles just returned>`, immediately after creating that row through
the real API, touching no other column and no other row.

**Why this is the correct, and only, way to get a REAL (non-fabricated)
risk/behaviour result for a new demo identity**: `engineer_features()` /
the behaviour-panel builder read EXCLUSIVELY from the raw FAR-Trans CSVs
(`load_far_trans_tables()`) — never from this application's own
`transactions` database table (confirmed by inspection: `Transaction`, the
SQLAlchemy model, is imported nowhere in `wealthpilot/` except
`data/ingestion.py`, the one-time loader). Populating the DB `transactions`
table with synthetic rows for a new customer would therefore have ZERO
effect on any model result — it would be inert, decorative data. The only
way the EXISTING, approved architecture lets a NEW customer identity
obtain a genuine, model-computed risk category is to alias
`external_customer_id` to an ALREADY-PRESENT FAR-Trans `customerID` — the
exact mechanism the system already uses for its entire real population.
This is not fabricating a transaction history and not copying personal
information (FAR-Trans transactional data carries no PII — Phase 2's own
audit already established this); it reuses one real, anonymized,
already-present customer's aggregate trading pattern as the risk-relevant
data source for a distinctly-named, clearly-synthetic demo persona. See
`scripts/find_demo_risk_candidates.py` for exactly how each
`external_customer_id` below was chosen, and
`reports/demo_dataset_catalog.md` for the full disclosure.

**Historical note, corrected by Phase 28.** Until Phase 28, through the
then-unmodified `POST /api/analysis` orchestration, NO customer could ever
reach an "approved" overall analysis result: `GraphDependencies.
monthly_essential_expenses`/`.current_liquid_assets` were never supplied,
so `emergency_fund.sufficient` was always `None`, and `core/compliance.py`'s
`emergency_fund_savings_first` rule (REJECT severity) fails closed
whenever that value is `None`. Phase 28 closed that gap with a real,
explicit data contract (`GET`/`PUT /api/profiles/{id}/financial-inputs`,
persisted in the new `financial_inputs` table, wired into
`analysis_service.py::_build_graph_dependencies`) — this script now calls
that same real endpoint for the personas where doing so is part of their
own intended demonstration (see each persona's `purpose` below), exactly
as it already does for profile/questionnaire/goal data. It still performs
exactly one direct database write, for exactly the same reason as before:
`risk_inputs.external_customer_id` remains the one field no API endpoint
exposes (see below) — financial inputs are NOT part of that direct write,
since Phase 28 gave them a real endpoint.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import text

from demo_data_package import (
    FAMILY_DEMO_KEY,
    analysis_state,
    load_expected_results,
    load_family,
    load_family_record_keys,
    load_personas,
    select_option,
)
from wealthpilot.config import get_settings
from wealthpilot.db.session import get_engine

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# The controlled demo population -- loaded from `demo_data/`, never written
# inline. Each persona's `risk_data_link` (seed-owned personas) was chosen by
# `find_demo_risk_candidates.py` (confidence >= 0.50, >= 4 months of trading
# history so behaviour-drift detection also produces a real result, not
# "insufficient trading history") -- a REAL, already-present, genuinely
# risk-labeled FAR-Trans customerID, never invented. Each persona's purpose
# is stated in its own `demo_data/profiles/*.json`.
#
#   DEMO_PERSONAS          the three personas this script owns (A, B, C):
#                          created if missing, and the only ones `reset`
#                          deletes (exact names).
#   FALLBACK_DEMO_PERSONA  Phase 24's canonical "WealthPilot Demo Customer"
#                          (D, pending information): created with the same
#                          values the frontend fallback uses if it is missing,
#                          never linked to FAR-Trans, never reset.
#
# The FAMILY demo (ADR-036) is ONE canonical household built from personas B
# and C. Its values are synthetic, household-level demo values only (EUR, the
# project's single currency) -- never training data, never read by any model,
# and never an input to any individual analysis. Each resource's records carry
# an idempotency key (FAMILY_RECORD_KEYS): setup-family creates a record only
# if no record with that key exists yet. What the records demonstrate (Phase 34
# semantics) is stated in each `demo_data/household/<resource>/*.json`.
# ---------------------------------------------------------------------------

ALL_DEMO_PERSONAS = load_personas()
DEMO_PERSONAS = [p for p in ALL_DEMO_PERSONAS if p["owned_by_seed"]]
FALLBACK_DEMO_PERSONA = next(p for p in ALL_DEMO_PERSONAS if not p["owned_by_seed"])
FAMILY_DEMO = load_family()
FAMILY_RECORD_KEYS = load_family_record_keys()
EXPECTED_RESULTS = load_expected_results()


# The seed's own position rule; defined once, beside the dataset it produced.
_select_option = select_option


def _find_existing_customer_id(client: httpx.Client, name: str) -> int | None:
    """The public API has no "find by name" endpoint (by design -- see
    Phase 24's own `lib/demo-customer.ts` docstring for the identical
    constraint) so this reads it directly, read-only, the same way this
    script's own `verify`/`reset` modes must. Never used to make setup
    depend on a client-side cache -- this script is meant to be re-run
    standalone, safely, any time."""
    settings = get_settings()
    engine = get_engine(settings.database_url)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM customers WHERE name = :name ORDER BY id LIMIT 1"), {"name": name}).first()
    return row[0] if row else None


def _set_external_customer_id(customer_id: int, external_customer_id: str) -> None:
    """The one direct database write this script performs -- see the
    module docstring for why no API endpoint exists for this field.
    Touches exactly one column on exactly one, already-created row."""
    settings = get_settings()
    engine = get_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE customers SET risk_inputs = :risk_inputs WHERE id = :id"),
            {"id": customer_id, "risk_inputs": f'{{"external_customer_id": "{external_customer_id}"}}'},
        )


FINANCIAL_INPUT_FIELDS = ("monthly_essential_expenses", "current_liquid_assets", "contribution_amount",
                          "annual_return_rate", "annual_inflation_rate", "contribution_periods_per_year")
GOAL_FIELDS = ("goal_type", "target_amount", "target_date", "current_savings", "priority")


def seed_persona(client: httpx.Client, persona: dict, link_risk_data=_set_external_customer_id) -> dict:
    """Creates -- or finds and completes -- one persona through the real API,
    from its `demo_data/` files. Idempotent: every step reads what exists and
    writes only what is missing, so a stored value is never overwritten and a
    second run creates nothing. The customer is found by exact name through
    the public lookup (lowest id when a name repeats), so this works against
    whichever database the client's app is bound to. `link_risk_data` is the
    one direct write (see the module docstring), made only for a customer
    just created and only when the persona has a `risk_data_link`. Returns a
    report of what was created vs already present."""
    report: dict = {"name": persona["name"], "created": [], "existing": []}
    customer_id = _lookup(client, persona["name"])
    if customer_id is not None:
        report["existing"].append("customer")
    else:
        customer_id = client.post("/api/profiles", json=persona["profile"]).raise_for_status().json()["customer_id"]
        report["created"].append("customer")
        if persona["external_customer_id"] is not None:
            link_risk_data(customer_id, persona["external_customer_id"])
            report["created"].append("risk_data_link")
    report["customer_id"] = customer_id

    answers = client.get(f"/api/profiles/{customer_id}/questionnaire").raise_for_status().json()["answers"]
    if answers:
        report["existing"].append(f"questionnaire ({len(answers)} answers)")
    else:
        client.post(
            f"/api/profiles/{customer_id}/questionnaire", json={"answers": persona["answers"]}
        ).raise_for_status()
        report["created"].append(f"questionnaire ({len(persona['answers'])} answers)")

    goals = client.get(f"/api/profiles/{customer_id}").raise_for_status().json()["goals"]
    if goals:
        report["existing"].append(f"goals ({len(goals)})")
    else:
        for goal in persona["goals"]:
            client.post(f"/api/profiles/{customer_id}/goals", json=goal).raise_for_status()
        report["created"].append(f"goals ({len(persona['goals'])})")

    if "financial_inputs" in persona:
        stored = client.get(f"/api/profiles/{customer_id}/financial-inputs").raise_for_status().json()
        if stored["monthly_essential_expenses"] is not None:
            report["existing"].append("financial inputs")
        else:
            client.put(
                f"/api/profiles/{customer_id}/financial-inputs", json=persona["financial_inputs"]
            ).raise_for_status()
            report["created"].append("financial inputs")
    return report


def setup(client: httpx.Client) -> None:
    for persona in ALL_DEMO_PERSONAS:
        print(f"\n=== {persona['name']} ({persona['demo_key']}) ===")
        report = seed_persona(client, persona)
        customer_id = report["customer_id"]
        print(f"  customer_id={customer_id}")
        print(f"  created ({len(report['created'])}): {report['created']}")
        print(f"  already present, left unchanged ({len(report['existing'])}): {report['existing']}")
        if "financial_inputs" not in persona:
            print("  no financial inputs for this persona (intentional -- see its own purpose)")

        t0 = time.monotonic()
        analysis = client.post("/api/analysis", json={"profile_id": customer_id}).raise_for_status().json()
        print(f"  POST /api/analysis ({time.monotonic() - t0:.1f}s): status={analysis['status']!r}, "
              f"analysis_id={analysis['analysis_id']}")
        if analysis["risk"]:
            print(f"    risk: category={analysis['risk']['risk_category']!r} "
                  f"confidence={analysis['risk']['confidence']}")
        if analysis["compliance"]:
            print(f"    compliance: decision={analysis['compliance']['decision']!r}")
        if analysis["recommendation"]:
            print(f"    recommendation: status={analysis['recommendation']['status']!r} "
                  f"strategy={analysis['recommendation'].get('selected_strategy')!r}")


def verify(client: httpx.Client) -> bool:
    """Read-only check of every persona against its `demo_data/` files and its
    expected contract-level states (`demo_data/expected_results/`). The
    analysis is read through `POST /api/analysis`, which returns the
    persona's cached run while its profile is unchanged (setup ran it)."""
    ok = True
    settings = get_settings()
    engine = get_engine(settings.database_url)

    def check(condition: bool, message: str) -> None:
        nonlocal ok
        ok = ok and condition
        print(f"  {'OK  ' if condition else 'FAIL'}  {message}")

    for persona in ALL_DEMO_PERSONAS:
        name = persona["name"]
        customer_id = _find_existing_customer_id(client, name)
        print(f"\n=== {name} ({persona['demo_key']}, customer_id={customer_id}) ===")
        if customer_id is None:
            check(False, "customer exists -- run `setup` first")
            continue

        profile = client.get(f"/api/profiles/{customer_id}").raise_for_status().json()
        answers = client.get(f"/api/profiles/{customer_id}/questionnaire").raise_for_status().json()["answers"]
        inputs = client.get(f"/api/profiles/{customer_id}/financial-inputs").raise_for_status().json()
        with engine.connect() as conn:
            dup = conn.execute(text("SELECT count(*) FROM customers WHERE name = :n"), {"n": name}).scalar()
            risk_inputs = conn.execute(
                text("SELECT risk_inputs FROM customers WHERE id = :id"), {"id": customer_id}
            ).scalar()

        if persona["owned_by_seed"] or dup == 1:
            check(dup == 1, f"exactly one customer named {name!r} (found {dup})")
        else:
            print(f"  NOTE  {dup} customers share this name; the lowest id ({customer_id}) is the persona. The "
                  "extra ones were created by the frontend fallback, per browser (a disclosed Phase 24 "
                  "limitation, ADR-030) -- never by this script -- and are left in place.")
        check(all(profile[k] == v for k, v in persona["profile"].items()), "profile matches the dataset")
        link = (risk_inputs or {}).get("external_customer_id")
        check(link == persona["external_customer_id"], f"risk data link is {persona['external_customer_id']!r}")
        check(sorted((a["question_number"], a["option_key"]) for a in answers)
              == sorted((a["question_number"], a["option_key"]) for a in persona["answers"]),
              f"questionnaire answers match the dataset ({len(persona['answers'])})")
        check(sorted(tuple(g[f] for f in GOAL_FIELDS) for g in profile["goals"])
              == sorted(tuple(g[f] for f in GOAL_FIELDS) for g in persona["goals"]),
              f"goals match the dataset ({len(persona['goals'])})")
        if "financial_inputs" in persona:
            check(all(inputs[k] == v for k, v in persona["financial_inputs"].items()),
                  "financial inputs match the dataset")
        else:
            check(all(inputs[k] is None for k in FINANCIAL_INPUT_FIELDS),
                  "no financial inputs stored (unknown stays null, never zero)")

        analysis = client.post("/api/analysis", json={"profile_id": customer_id}).raise_for_status().json()
        state = analysis_state(analysis)
        expected = EXPECTED_RESULTS[persona["demo_key"]]
        differs = {k: {"expected": v, "actual": state.get(k)} for k, v in expected.items() if state.get(k) != v}
        check(not differs, f"analysis {analysis['analysis_id']} ({state['analysis_status']}): expected states hold"
              + (f" -- differs: {differs}" if differs else ""))

    print(f"\nVERIFY {'PASSED' if ok else 'FAILED'}")
    return ok


def reset(base_url: str) -> None:
    """Deletes ONLY the exact customer names this script itself creates
    (§ DEMO_PERSONAS) -- an exact-string match against a fixed, known list,
    never a prefix/wildcard match, so this can never reach a differently
    -named row by accident. Phase 24's "WealthPilot Demo Customer" is a
    different exact string and is never touched. Deletes child rows first
    (questionnaire_answers, financial_goals, agent_logs, analysis_runs),
    then the customer row itself, only for a name found in this exact set."""
    settings = get_settings()
    engine = get_engine(settings.database_url)
    names = [p["name"] for p in DEMO_PERSONAS]
    with engine.begin() as conn:
        # The family demo is built on two of these personas; remove it first so
        # deleting them never leaves an orphaned household behind.
        primary = conn.execute(
            text("SELECT id FROM customers WHERE name = :n ORDER BY id LIMIT 1"), {"n": FAMILY_DEMO["primary_name"]}
        ).scalar()
        if primary is not None:
            print(f"  deleted {_delete_family_household(conn, FAMILY_DEMO['household_name'], primary)} family demo household row(s)")
        ids = [
            r[0]
            for r in conn.execute(
                text("SELECT id FROM customers WHERE name = ANY(:names)"), {"names": names}
            ).all()
        ]
        if not ids:
            print("No demo persona customers found -- nothing to reset.")
            return
        for table in ("questionnaire_answers", "financial_goals", "financial_inputs", "agent_logs", "analysis_runs", "risk_assessments", "recommendations"):
            result = conn.execute(text(f"DELETE FROM {table} WHERE customer_id = ANY(:ids)"), {"ids": ids})
            print(f"  deleted {result.rowcount} row(s) from {table}")
        result = conn.execute(text("DELETE FROM customers WHERE id = ANY(:ids)"), {"ids": ids})
        print(f"  deleted {result.rowcount} row(s) from customers")
    print("Reset complete.")


# ---------------------------------------------------------------------------
# Family demo -- every call below goes through the real public API. The client
# is any httpx.Client (a running server via `--base-url`, or the in-process
# FastAPI TestClient via `--in-process`, which drives the same ASGI app).
# ---------------------------------------------------------------------------


class FamilyDemoError(RuntimeError):
    """Raised instead of guessing: a missing persona, or a persona already in a
    different household, stops setup rather than being worked around."""


def _lookup(client: httpx.Client, name: str) -> int | None:
    """The public name lookup (`GET /api/profiles/lookup`) -- API-only, so it
    reads whichever database the client's app is bound to."""
    return client.get("/api/profiles/lookup", params={"name": name}).raise_for_status().json()["customer_id"]


def _as(customer_id: int) -> dict[str, str]:
    return {"X-Customer-Id": str(customer_id)}


def setup_family(client: httpx.Client, spec: dict | None = None) -> dict:
    """Creates -- or finds and completes -- the canonical family household.
    Idempotent: running it again creates nothing new. Returns a report of
    what was created vs already present."""
    spec = spec or FAMILY_DEMO
    report: dict = {"created": [], "existing": []}

    primary_id = _lookup(client, spec["primary_name"])
    member_ids = {m["name"]: _lookup(client, m["name"]) for m in spec["members"]}
    missing = [n for n, i in [(spec["primary_name"], primary_id), *member_ids.items()] if i is None]
    if missing:
        raise FamilyDemoError(
            f"persona(s) not found: {missing}. Run `seed_demo_data.py setup` first -- the family demo "
            "reuses the existing personas and never creates customer records."
        )
    who = _as(primary_id)

    current = client.get(f"/api/profiles/{primary_id}/household", headers=who).raise_for_status().json()
    if current["household"] is None:
        household = client.post("/api/households", json={"name": spec["household_name"]}, headers=who).raise_for_status().json()
        report["created"].append(f"household {household['id']}")
    elif current["household"]["name"] == spec["household_name"] and current["membership"]["role"] == "primary":
        household = current["household"]
        report["existing"].append(f"household {household['id']}")
    else:
        raise FamilyDemoError(
            f"{spec['primary_name']!r} already belongs to a different household "
            f"({current['household']['name']!r}); refusing to alter it."
        )
    hid = household["id"]
    report["household_id"] = hid

    listed = client.get(f"/api/households/{hid}/members", headers=who).raise_for_status().json()["members"]
    present = {m["customer_id"] for m in listed}
    for member in spec["members"]:
        cid = member_ids[member["name"]]
        if cid in present:
            report["existing"].append(f"member {member['name']}")
            continue
        response = client.post(
            f"/api/households/{hid}/members",
            json={"customer_id": cid, "relationship": member["relationship"], "role": member["role"]},
            headers=who,
        )
        if response.status_code == 409:
            raise FamilyDemoError(f"{member['name']!r} cannot join: {response.json().get('detail')}")
        response.raise_for_status()
        report["created"].append(f"member {member['name']}")

    for resource, key in FAMILY_RECORD_KEYS.items():
        stored = client.get(f"/api/households/{hid}/{resource}", headers=who).raise_for_status().json()
        have = {row[key] for row in stored}
        for record in spec[resource]:
            if record[key] in have:
                report["existing"].append(f"{resource}:{record[key]}")
                continue
            client.post(f"/api/households/{hid}/{resource}", json=record, headers=who).raise_for_status()
            report["created"].append(f"{resource}:{record[key]}")

    report["summary"] = client.get(f"/api/households/{hid}/financial-summary", headers=who).raise_for_status().json()
    return report


def verify_family(client: httpx.Client, spec: dict | None = None) -> tuple[bool, list[str]]:
    """Read-only check of the canonical family demo. Returns (ok, messages)."""
    spec = spec or FAMILY_DEMO
    lines: list[str] = []
    ok = True

    def check(condition: bool, message: str) -> None:
        nonlocal ok
        ok = ok and condition
        lines.append(f"{'OK  ' if condition else 'FAIL'}  {message}")

    primary_id = _lookup(client, spec["primary_name"])
    check(primary_id is not None, f"primary persona {spec['primary_name']!r} exists")
    if primary_id is None:
        return ok, lines
    who = _as(primary_id)
    current = client.get(f"/api/profiles/{primary_id}/household", headers=who).json()
    household = current.get("household")
    check(household is not None and household["name"] == spec["household_name"],
          f"primary belongs to {spec['household_name']!r}")
    if household is None:
        return ok, lines
    hid = household["id"]
    check(current["membership"]["role"] == "primary" and current["membership"]["relationship"] == "self"
          and current["membership"]["is_dependent"] is False, "primary is self / primary / not dependent")

    members = client.get(f"/api/households/{hid}/members", headers=who).json()["members"]
    by_id = {m["customer_id"]: m for m in members}
    for member in spec["members"]:
        cid = _lookup(client, member["name"])
        m = by_id.get(cid)
        check(m is not None and m["relationship"] == member["relationship"] and m["role"] == member["role"],
              f"{member['name']!r} is a {member['relationship']} / {member['role']}")
    check(len(members) == 1 + len(spec["members"]), f"exactly {1 + len(spec['members'])} members")
    check(set(members[0]) == {"id", "household_id", "customer_id", "customer_name", "relationship", "role",
                              "is_dependent", "created_at", "updated_at"},
          "member entries carry identity/membership fields only")

    for resource, key in FAMILY_RECORD_KEYS.items():
        stored = client.get(f"/api/households/{hid}/{resource}", headers=who).json()
        keys = [row[key] for row in stored]
        expected = [record[key] for record in spec[resource]]
        check(all(keys.count(k) == 1 for k in expected), f"{resource}: each of {len(expected)} demo record(s) present exactly once")

    summary = client.get(f"/api/households/{hid}/financial-summary", headers=who)
    check(summary.status_code == 200, "financial summary readable by the primary")
    if spec is FAMILY_DEMO:
        expected = EXPECTED_RESULTS[FAMILY_DEMO_KEY]
        goals = client.get(f"/api/households/{hid}/goals", headers=who)
        check(len(members) == expected["member_count"], f"member count is the expected {expected['member_count']}")
        check((summary.status_code == 200) == expected["household_summary_available"],
              "household summary availability is as expected")
        check((goals.status_code == 200 and bool(goals.json())) == expected["household_goals_available"],
              "household goals availability is as expected")

    for name in ("WealthPilot Demo — Complete", "WealthPilot Demo Customer"):
        outsider = _lookup(client, name)
        if outsider is None:
            lines.append(f"--    {name!r} not present in this environment (skipped)")
            continue
        own = client.get(f"/api/profiles/{outsider}/household", headers=_as(outsider)).json()
        check(own["household"] is None, f"individual-demo persona {name!r} is in no household")
        denied = client.get(f"/api/households/{hid}/financial-summary", headers=_as(outsider))
        check(denied.status_code == 403, f"{name!r} (non-member) is denied the family household (403)")
    return ok, lines


def _delete_family_household(conn, household_name: str, primary_id: int) -> int:
    """Deletes the demo household -- matched by its EXACT name AND by the given
    primary member, never by name alone -- and, through the existing ON DELETE
    CASCADE foreign keys, its memberships, financial records and goals. There
    is no household-deletion API (by design, ADR-031), so this is the one
    direct write the family demo needs, and only on reset. Customers are never
    touched."""
    result = conn.execute(
        text(
            "DELETE FROM households WHERE name = :name AND id IN ("
            " SELECT household_id FROM household_members"
            " WHERE customer_id = :primary AND role = 'primary')"
        ),
        {"name": household_name, "primary": primary_id},
    )
    return result.rowcount


def reset_family() -> None:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    with engine.begin() as conn:
        primary = conn.execute(
            text("SELECT id FROM customers WHERE name = :n ORDER BY id LIMIT 1"), {"n": FAMILY_DEMO["primary_name"]}
        ).scalar()
        if primary is None:
            print("Family primary persona not found -- nothing to reset.")
            return
        deleted = _delete_family_household(conn, FAMILY_DEMO["household_name"], primary)
    print(f"  deleted {deleted} demo household row(s) (members, records and goals cascade)")
    print("Family reset complete. The personas themselves are unchanged.")


def _open_client(args: argparse.Namespace):
    """A running server by default; with --in-process, the real app itself
    through FastAPI's TestClient (the same routes, validation and database --
    no server is started)."""
    if not args.in_process:
        return httpx.Client(base_url=args.base_url, timeout=60.0)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `training.*`
    from fastapi.testclient import TestClient

    from wealthpilot.api.main import app

    return TestClient(app)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["setup", "verify", "reset", "setup-family", "verify-family", "reset-family"])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"running backend base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--in-process", action="store_true",
                        help="run through the real app in-process (FastAPI TestClient on DATABASE_URL; no server needed)")
    args = parser.parse_args()

    if args.mode == "setup":
        with _open_client(args) as client:
            setup(client)
    elif args.mode == "verify":
        with _open_client(args) as client:
            ok = verify(client)
        sys.exit(0 if ok else 1)
    elif args.mode == "reset":
        reset(args.base_url)
    elif args.mode == "setup-family":
        with _open_client(args) as client:
            report = setup_family(client)
        print(f"household_id={report['household_id']}")
        print(f"created ({len(report['created'])}): {report['created']}")
        print(f"already present ({len(report['existing'])}): {report['existing']}")
        summary = report["summary"]
        print(f"summary: recurring income={summary['income']['recurring_monthly']}, "
              f"recurring expenses={summary['expenses']['recurring_monthly']}, "
              f"monthly cash flow={summary['cash_flow']['monthly']}, net position={summary['net_position']['value']}, "
              f"emergency fund required={summary['emergency_fund']['required']} "
              f"({summary['emergency_fund']['status']})")
    elif args.mode == "verify-family":
        with _open_client(args) as client:
            ok, lines = verify_family(client)
        print("\n".join(lines))
        print(f"\nVERIFY-FAMILY {'PASSED' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)
    elif args.mode == "reset-family":
        reset_family()


if __name__ == "__main__":
    main()
