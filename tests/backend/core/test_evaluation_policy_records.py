"""Guards for the evaluation-policy RECORDS: the annotation-policy decisions of 2026-10-29 are recorded in the validation decision sheet with their exact values, the approval record holds the 26
statistical-policy decisions with their basis, the approved targets exist in code only as evaluation GATES (in one place), nothing in the statistics code can enable, rank or select a model, and the
evaluation script is still not connected to the statistics or to the frozen-evaluation plumbing. When the owner decides differently, the deciding change must update these on purpose."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from training.sentiment import metrics

ROOT = Path(__file__).resolve().parents[3]
SHEET = (ROOT / "docs" / "USER_TEXT_VALIDATION_DECISION_SHEET.md").read_text(encoding="utf-8")
RECORD = (ROOT / "reports" / "sentiment_model_approval_record.md").read_text(encoding="utf-8")
SCRIPT = ROOT / "training" / "sentiment" / "evaluate_sentiment_model.py"
METRICS = ROOT / "training" / "sentiment" / "metrics.py"
DECISIONS = {"AP1": "NO_CURRENT_VIEW", "AP2": "NO_CURRENT_VIEW", "AP3": "NO_CURRENT_VIEW", "AP4": "KEEP_DOCUMENTED_DIFFERENCE", "AP5": "UNCERTAIN_WEAK", "AP6": "LABEL_CURRENT_ONLY",
             "AP7": "NO_CURRENT_VIEW", "AP8": "HEDGED_CURRENT_CONDITIONAL_NOT_CURRENT", "AP9": "TAG_TOPIC_ONLY"}


def item_block(name: str) -> str:
    start = SHEET.index(f"### {name} —")
    ends = [i for i in (SHEET.find("\n### ", start + 5), SHEET.find("\n## ", start + 5)) if i != -1]
    return SHEET[start: min(ends)] if ends else SHEET[start:]


def test_each_annotation_policy_item_records_its_exact_decision_and_none_is_blank():
    assert "| Owner entry | |" not in SHEET
    for name, token in DECISIONS.items():
        block = item_block(name)
        entry = next(line for line in block.splitlines() if line.startswith("| Owner entry |"))
        assert f"**DECIDED 2026-10-29: `{token}`.**" in entry, name
        assert "| Owner decision |" not in block, name                                  # that row label belongs to the seven original decisions O1 to O7 only
    assert "`RETAIN_DOCUMENTED_BASELINE_BEHAVIOR`" in item_block("AP6")                 # the comma-less "and" decision
    assert "`CONTEXT_DEPENDENT`" in item_block("AP8") and "polite" in item_block("AP8").lower()          # the polite-form boundary, decided in the eighteenth brief
    titles = {"AP1": "Plain quotations", "AP2": "Statements about other people", "AP3": "Past feelings", "AP4": "\"even if\"", "AP5": "Hypothetical-only", "AP6": "Mixed current and hypothetical",
              "AP7": "Negated hypothetical", "AP8": "Hedged versus conditional", "AP9": "Topic tagging"}
    for name, title in titles.items():
        assert title in item_block(name).splitlines()[0], name


def test_the_even_if_decision_keeps_both_the_rubric_and_the_baseline_and_says_comparison_is_not_claimed():
    block = item_block("AP4")
    for outcome in ("ALIGN_BASELINE_TO_RUBRIC", "ALIGN_RUBRIC_TO_BASELINE", "KEEP_DOCUMENTED_DIFFERENCE"):
        assert outcome in block, outcome
    assert "**DECIDED** (`KEEP_DOCUMENTED_DIFFERENCE`)" in block and "direct comparison with this rubric is not claimed for this case" in block and "No production change" in block


def test_the_sheet_addendum_creates_no_statement_and_sets_no_number():
    addendum = SHEET[SHEET.index("## Addendum 2026-10-29"):]
    assert "No statement was created or labelled" in addendum and "no number is set here" in addendum
    assert not re.search(r"\d+(\.\d+)?\s*%|\b0\.\d+|[<>≤≥]=?\s*\d|\b(at least|minimum of|no fewer than) (\d+|two|three|five|ten)\b", addendum, re.IGNORECASE)


def test_the_record_holds_all_26_statistical_decisions_each_with_a_value_and_how_it_was_obtained():
    start = RECORD.index("## Owner decisions recorded 2026-10-29 (seventeenth brief)")
    section = RECORD[start: RECORD.index("\n## ", start + 5)]
    rows = [line for line in section.splitlines() if re.match(r"\| \d+ \|", line)]
    assert [int(re.match(r"\| (\d+) \|", r).group(1)) for r in rows] == list(range(1, 27))
    for row in rows:
        basis = [cell.strip() for cell in row.strip().strip("|").split("|")][-1]
        assert basis in {"stated", "adopted proposal"}, row
    for token in ("`COHEN_KAPPA`", "`NO_FLOOR`", "`REPORT_ONLY`", "0.70", "0.30", "0.80", "0.85", "75 per primary class", "300", "`positive_negative_neutral`", "`NOT_REQUIRED`"):
        assert token in section, token
    assert "Approve all stated values" in section and "Adopt your proposal" in section
    assert "that rule is NOT approved" in section                                          # the seventeenth-brief state; the eighteenth brief decided it (see the next test)
    assert "**not** activation rules" in section


def test_the_approved_values_live_only_in_the_two_owner_approved_mappings_and_nothing_can_enable_rank_or_select_a_model():
    source = METRICS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    start_line = len(source[: source.index("REPORT_VERSION =")].splitlines()) + 1
    allowed = {"OWNER_APPROVED_POLICY", "OWNER_APPROVED_STATISTICS"}
    identifiers, stray = set(), []
    parents: dict[ast.AST, str] = {}
    for top in tree.body:
        name = top.targets[0].id if isinstance(top, ast.Assign) and isinstance(top.targets[0], ast.Name) else getattr(top, "name", "")
        for node in ast.walk(top):
            parents[node] = name
    for node in ast.walk(tree):
        if getattr(node, "lineno", 0) < start_line:
            continue
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            identifiers.add(node.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, float) and round(node.value, 2) in {0.7, 0.8, 0.85, 0.3} and parents.get(node) not in allowed:
            stray.append((node.value, parents.get(node)))
    assert not stray, f"an approved value appears outside the owner-approved mappings: {stray}"
    assert not [i for i in identifiers if any(word in i.lower() for word in ("activate", "enable_model", "winner", "passed", "select_model", "rank_model", "best_model"))], identifiers
    assert metrics.StatisticsPlan.owner_approved().approved is True and metrics.EvaluationPolicy.owner_approved().approved is True


def test_the_eighteenth_brief_decisions_are_recorded_with_their_exact_values():
    start = RECORD.index("## Owner decisions recorded 2026-10-29 (eighteenth brief)")
    section = RECORD[start: RECORD.index("\n## ", start + 5)]
    for token in ("`NO_LOWER_BOUND_ACTIVATION_RULE`", "`DEFER_MULTI_LABEL_AGREEMENT`", "`NON_STRATIFIED_ITEM_BOOTSTRAP`", "`APPROVE_SCHEMA_AND_WIRE_OFFLINE`", "`CONTEXT_DEPENDENT`", "Approve all five",
                  "with the strict view deciding the gate", "activation cannot be recommended from a metric report alone", "limited to polite-form handling", "tested only on local synthetic fixtures"):
        assert token in section, token
    assert "confirmed" in section and "not changed" not in section.split("### 2 to 6")[0].lower().replace("none was changed", "")


def test_the_evaluation_script_is_connected_only_through_the_frozen_interface_and_never_to_activation():
    text = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = {f"{n.module}.{alias.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module for alias in n.names}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert {"training.sentiment.frozen_evaluation.load_frozen_evaluation", "training.sentiment.frozen_evaluation.evaluate_frozen"} <= imported
    assert not any(i.startswith(("wealthpilot.api", "wealthpilot.config", "wealthpilot.agents", "wealthpilot.security")) for i in imported), imported
    assert not {"EvidenceBasis", "evaluate_predictions", "evaluation_report", "assess_against_policy", "agreement_report"} & names              # the script never builds an evidence basis or a report itself
    assert "SENTIMENT_MODEL_ENABLED" not in text
