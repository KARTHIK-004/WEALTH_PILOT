"""Command line: ``python -m wealthpilot.data.gdelt <command>``.

    dry-run       offline preflight; never touches the network (always allowed)
    fetch-sample  the pre-registered development (or, if triggered, confirmation) sample; gated
    acquire       full historical acquisition: always refuses in this build
    build-review  offline: blind annotation files from a completed development sample

Exit codes: 0 success, 2 configuration error, 3 refused by a gate, 4 stopped by a guard, 1 other error.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from wealthpilot.data.gdelt import PARSER_VERSION
from wealthpilot.data.gdelt.config import load_config
from wealthpilot.data.gdelt.ai.provider import ExecutionBlocked
from wealthpilot.data.gdelt.errors import ApprovalRefused, BudgetExceeded, ConfigError, GdeltToolError


def _print(obj: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=1, default=str))
        return
    if isinstance(obj, dict) and "checks" in obj:
        for c in obj["checks"]:
            print(f"[{c['status']:>7}] {c['check']}: {c['detail']}")
        print(f"ready_for_development_sample: {obj['ready_for_development_sample']}")
        for b in obj["blockers"]:
            print(f"  BLOCKER {b}")
    else:
        print(obj)


def cmd_dry_run(args: argparse.Namespace) -> int:
    from wealthpilot.data.gdelt.preflight import run_preflight
    report = run_preflight(load_config(args.config), stage="D")
    _print(report, args.json)
    return 0


def cmd_fetch_sample(args: argparse.Namespace) -> int:
    from wealthpilot.data.gdelt.config import authorize
    from wealthpilot.data.gdelt.sample import STAGE_C_SHA256, STAGE_D_SHA256
    config = load_config(args.config)
    mode = "dev_sample" if args.stage == "D" else "confirmation_sample"
    expected = STAGE_D_SHA256 if args.stage == "D" else STAGE_C_SHA256
    # Stage C additionally needs a trigger record; none can be supplied on the command line in this build.
    auth = authorize(config, mode, cli_confirmed_network=args.confirm_network, expected_stage_sha256=expected,
                     trigger_valid=False)
    return _run_authorized_sample(config, auth)  # unreachable in this build: authorize() refuses above


def _run_authorized_sample(config, auth) -> int:  # type: ignore[no-untyped-def]
    """Kept explicit so the next, approved phase only flips the build locks. Not reachable in B2-K."""
    from wealthpilot.data.gdelt.engine import RunContext, run_sample
    from wealthpilot.data.gdelt.events import EventLog
    from wealthpilot.data.gdelt.filters import default_classifier
    from wealthpilot.data.gdelt.guards import TransferBudget
    from wealthpilot.data.gdelt.manifest import Manifest
    from wealthpilot.data.gdelt.output import Layout
    from wealthpilot.data.gdelt.preflight import run_preflight
    from wealthpilot.data.gdelt.sample import load_development_stage, substitute
    from wealthpilot.data.gdelt.session_calendar import cutoff_utc
    from wealthpilot.data.gdelt.transport import HttpsTransport
    from datetime import date

    report = run_preflight(config, stage="D")
    if report["blockers"]:
        _print(report, False)
        return 3
    classifier = default_classifier()
    layout = Layout(config.output_root / "review" / "b2i_review_v1", classifier.spec.version)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    manifest = Manifest(layout.manifest_path)
    budget = TransferBudget(config.limits.max_total_bytes, config.limits.max_requests)
    ctx = RunContext(run_id, layout, manifest, classifier, config.limits, budget,
                     EventLog(layout.logs / f"run_{run_id}.jsonl"), keep_raw=True,
                     sample_cutoff=cutoff_utc(date(2024, 1, 4)))
    from wealthpilot.data.gdelt.guards import free_bytes
    from wealthpilot.data.gdelt.preflight import code_fingerprint, git_head, tzdata_version
    commit, dirty = git_head()
    manifest.start_run(run_id, auth.mode, code_sha256=code_fingerprint(), parser_version=PARSER_VERSION,
                       filter_version=classifier.spec.version, filter_spec_sha256=classifier.spec.sha256,
                       audited_list_sha256="7e5d2c2efb7298af6eafb0898739ba880b875b586255e994a81ff1a975cfebf0",
                       selection_sha256=auth.approval.stage_sha256 if auth.approval else None,
                       params={"limits": config.limits.__dict__, "config": str(config.source_path),
                               "git_commit": commit, "git_dirty": dirty},
                       python_version=sys.version.split()[0], tzdata_version=tzdata_version(),
                       free_bytes_at_start=free_bytes(layout.root))
    result = run_sample(ctx, HttpsTransport(auth, config.limits), load_development_stage(), selection="stage_D",
                        substitute=substitute)
    manifest.end_run(run_id, result.outcome, bytes_downloaded=budget.bytes_used, requests_made=budget.requests_used)
    print(json.dumps({"outcome": result.outcome, "stop_reason": result.stop_reason, "bytes": budget.bytes_used,
                      "requests": budget.requests_used, "states": manifest.state_counts()}, indent=1))
    return 0 if result.outcome == "completed" else 4


def cmd_acquire(args: argparse.Namespace) -> int:
    from wealthpilot.data.gdelt.config import authorize
    authorize(load_config(args.config), "full_acquisition")  # always raises ApprovalRefused
    return 3  # pragma: no cover


def cmd_build_review(args: argparse.Namespace) -> int:
    from wealthpilot.data.gdelt.filters import default_classifier
    from wealthpilot.data.gdelt.manifest import Manifest
    from wealthpilot.data.gdelt.output import Layout
    from wealthpilot.data.gdelt.review import build_review
    config = load_config(args.config)
    classifier = default_classifier()
    layout = Layout(config.output_root / "review" / "b2i_review_v1", classifier.spec.version)
    if not layout.manifest_path.exists():
        raise ConfigError(f"no development-sample manifest at {layout.manifest_path}; nothing to review")
    summary = build_review(Manifest(layout.manifest_path), layout.raw_keep, classifier, layout.root / "review_files",
                           max_uncompressed=config.limits.max_uncompressed_bytes,
                           max_ratio=config.limits.max_expansion_ratio, max_line_bytes=config.limits.max_line_bytes)
    print(json.dumps(summary.__dict__, indent=1, default=str))
    return 0


def _ai_origin_dir(args: argparse.Namespace) -> Path | None:
    """The AI-origin export folder named by ``--ai-experiment`` (reads the experiment YAML only), or None."""
    if not getattr(args, "ai_experiment", None):
        return None
    from wealthpilot.data.gdelt.ai import config as aic
    from wealthpilot.data.gdelt.ai import store as ast
    return ast.Layout(aic.load_experiment(args.ai_experiment).destination).export


def _ai_suggestions(paths: object, args: argparse.Namespace) -> object:
    """The verified B2-T suggestion set for ``--ai-experiment``, or None (the legacy source applies)."""
    from wealthpilot.data.gdelt import ai_bridge
    bridge = ai_bridge.load(paths, _ai_origin_dir(args))
    return bridge.suggestions if bridge else None


def cmd_annotate(args: argparse.Namespace) -> int:
    """Offline annotation workflow. Never reads the sealed key; no network."""
    from wealthpilot.data.gdelt import annotate
    config = load_config(args.config)
    paths = annotate.Paths(config.output_root / "review" / "b2i_review_v1" / "review_files")
    if args.action == "init":
        out: object = annotate.init(paths)
    elif args.action == "export-batch":
        out = annotate.export_batch(paths, size=args.size, overlap_only=not args.all)
    elif args.action == "merge":
        if not args.batch:
            raise ConfigError("merge needs --batch <path to the labelled batch file>")
        out = annotate.merge(paths, Path(args.batch), ai_suggestions=_ai_suggestions(paths, args))
    elif args.action == "label":
        from wealthpilot.data.gdelt.labeller import Labeller
        try:
            sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
        labeller = Labeller(paths)
        out = labeller.revisit(args.item.strip().upper()) if args.item else labeller.run()
    elif args.action == "freeze":
        from wealthpilot.data.gdelt import evaluate as evaluation
        out = evaluation.freeze(paths, _ai_origin_dir(args))
    elif args.action == "evaluate":
        from wealthpilot.data.gdelt import evaluate as evaluation
        out = evaluation.evaluate(paths, ai_origin_dir=_ai_origin_dir(args))
    elif args.action == "metric-status":
        from wealthpilot.data.gdelt import metric_status
        out = metric_status.report(paths, ai_only_root=args.ai_only_store)
    elif args.action == "lock-overlap":
        from wealthpilot.data.gdelt import overlap_lock
        out = overlap_lock.create(paths)
    elif args.action == "validate":
        rep = annotate.validate(paths, ai_suggestions=_ai_suggestions(paths, args))
        out = {"ok": rep.ok, "complete": rep.complete, "rows": rep.rows, "labelled": rep.labelled,
               "overlap_rows": rep.overlap_rows, "overlap_labelled": rep.overlap_labelled,
               "integrity_errors": rep.integrity_errors, "row_errors": rep.errors}
    else:
        out = annotate.status(paths)
    print(json.dumps(out, indent=1, default=str))
    if isinstance(out, dict) and (out.get("errors") or out.get("row_errors") or out.get("integrity_errors")):
        return 1
    return 0


def cmd_ai(args: argparse.Namespace) -> int:
    """AI-assisted annotation pipeline (DISABLED). `dry-run`, `queue`, `progress`, `qc`, `review` and `export` are
    local; `run` fails closed and lists every unmet prerequisite. No provider is ever called from here in this build."""
    from wealthpilot.data.gdelt.ai import config as aic
    from wealthpilot.data.gdelt.ai import evaluation as aev
    from wealthpilot.data.gdelt.ai import retention as aret
    from wealthpilot.data.gdelt.ai import export as aex
    from wealthpilot.data.gdelt.ai import provider as aprov
    from wealthpilot.data.gdelt.ai import queue as aq
    from wealthpilot.data.gdelt.ai import reviewer as arv
    from wealthpilot.data.gdelt.ai import runner as arun
    from wealthpilot.data.gdelt.ai import store as ast
    from wealthpilot.data.gdelt.ai.fingerprints import itemset_fingerprint
    from wealthpilot.data.gdelt.ai.schema import load_items

    cfg = aic.load_experiment(args.experiment)
    layout = ast.Layout(cfg.destination)
    blind = frozenset(cfg.blind_item_ids)

    def excluded_ids() -> frozenset[str]:
        if cfg.provider_exclusion in (None, "none"):
            return frozenset()
        return aic.excluded_item_ids(cfg.provider_exclusion, cfg.blind_item_ids, ast.verified_overlap(layout)) or frozenset()

    out: object
    if args.action == "dry-run":
        out = arun.dry_run(cfg)
    elif args.action == "init":
        out = ast.init_experiment(cfg)
    elif args.action == "run":
        src_items = load_items(cfg.source_review_files / "annotation_A.csv")
        log = json.loads((cfg.source_review_files / "selection_log.json").read_text(encoding="utf-8"))["files_sha256"]
        try:
            overlap_ids = ast.source_overlap_ids(cfg.source_review_files)
        except GdeltToolError:
            overlap_ids = None
        auth = aic.authorize_run(cfg, itemset_sha256=itemset_fingerprint((i.item_id, i.fingerprint) for i in src_items),
                                 original_overlap_sha256=log.get("annotation_B.csv", ""),
                                 confirm_ai_run=args.confirm_ai_run, overlap_item_ids=overlap_ids)
        provider = aprov.build_provider(cfg.provider_name, cfg, auth)
        res = arun.run_suggestions(cfg, auth, provider)
        out = {"outcome": res.outcome, "counts": res.counts, "requests_used": res.requests_used,
               "stop_reason": res.stop_reason}
    elif args.action == "retention":
        out = aret.enforce(layout, cfg.retention_days, confirm_delete=args.confirm_delete)
    else:
        items = ast.load_snapshot_items(layout)
        if args.action == "evaluate":
            rows, schema_problems = aev.read_export(layout.export / "annotation_b2t_v1.csv")
            overlap, _ = ast.historical_overlap_ids(layout)
            suggestions = ast.SuggestionStore(layout)
            valid = {k: v for k, v in suggestions.terminal().items() if v.get("terminal_status") == "valid"}
            prov = json.loads(Path(args.blind_provenance).read_text(encoding="utf-8")) if args.blind_provenance else None
            out = aev.evaluate(rows, schema_problems, universe_ids={i.item_id for i in items}, overlap_ids=overlap,
                               valid_suggestions=valid, first_suggestion_at=aev.first_suggestion_time(suggestions.records()),
                               provenance=prov, experiment_id=cfg.experiment_id)
            print(json.dumps(out, indent=1, default=str))
            return 0 if out["integrity_ok"] else 1
        if args.action == "progress":
            out = aq.progress(items, layout, blind, excluded_ids())
        elif args.action == "qc":
            out = aq.qc_report(items, layout)
        elif args.action == "export":
            out = aex.export_dataset(layout, cfg, items)
        else:
            tiers = tuple(int(t) for t in args.tiers.split(",")) if args.tiers else aq.QueuePolicy().tiers
            rows = aq.build_queue(items, layout, blind, aq.QueuePolicy(tiers=tiers, limit=args.limit), excluded_ids())
            aq.write_queue_csv(layout, rows)
            if args.action == "queue":
                out = {"queue_file": str(layout.queue), "items": len(rows),
                       "by_tier": {aq.TIERS[t]: sum(1 for r in rows if r["tier"] == t) for t in aq.TIERS}}
            else:
                try:
                    sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
                except (AttributeError, ValueError):
                    pass
                out = arv.AiReviewer(layout, items, protocol_id=cfg.protocol_id, experiment_id=cfg.experiment_id,
                                     blind_ids=blind, excluded_ids=excluded_ids()).run(rows)
    print(json.dumps(out, indent=1, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m wealthpilot.data.gdelt", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("dry-run", help="offline preflight; no network")
    p.add_argument("--config", type=Path)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_dry_run)
    p = sub.add_parser("fetch-sample", help="gated sample download (refused in this build)")
    p.add_argument("--config", type=Path)
    p.add_argument("--stage", choices=("D", "C"), default="D")
    p.add_argument("--confirm-network", action="store_true")
    p.set_defaults(func=cmd_fetch_sample)
    p = sub.add_parser("acquire", help="full historical acquisition (always refused)")
    p.add_argument("--config", type=Path)
    p.set_defaults(func=cmd_acquire)
    p = sub.add_parser("build-review", help="offline: annotation files from a completed sample")
    p.add_argument("--config", type=Path)
    p.set_defaults(func=cmd_build_review)
    p = sub.add_parser("annotate", help="offline: annotation working copy, batches, validated merge, status")
    p.add_argument("action", choices=("init", "export-batch", "merge", "validate", "status", "label", "freeze",
                                          "evaluate", "lock-overlap", "metric-status"))
    p.add_argument("--config", type=Path)
    p.add_argument("--size", type=int, default=50)
    p.add_argument("--all", action="store_true", help="export-batch: include non-overlap rows (overlap first)")
    p.add_argument("--batch", help="merge: path to the labelled batch file")
    p.add_argument("--item", help="label: revisit one overlap item (a change needs a correction reason)")
    p.add_argument("--ai-only-store", type=Path,
                   help="metric-status: an AI-only suggestion store to count as exploratory (never independent evidence)")
    p.add_argument("--ai-experiment", type=Path,
                   help="validate/merge/freeze/evaluate: the experiment YAML whose B2-T suggestion store and AI-origin export verify AI-based labels")
    p.set_defaults(func=cmd_annotate)
    p = sub.add_parser("ai", help="AI-assisted annotation pipeline: BUILT BUT DISABLED (see ai/__init__.py)")
    p.add_argument("action", choices=("dry-run", "init", "run", "queue", "progress", "qc", "review", "export", "evaluate",
                                       "retention"))
    p.add_argument("--experiment", type=Path, required=True, help="path to the experiment YAML (not created by default)")
    p.add_argument("--confirm-ai-run", action="store_true", help="one of several conditions for `run`; never sufficient alone")
    p.add_argument("--tiers", help="queue/review: comma-separated tiers to include, for example 0,1")
    p.add_argument("--limit", type=int, help="queue/review: list at most this many items")
    p.add_argument("--blind-provenance", type=Path, help="evaluate: JSON provenance of the pre-registered blind subset")
    p.add_argument("--confirm-delete", action="store_true",
                   help="retention: actually delete the expired AI-run artifacts (default is a dry run)")
    p.set_defaults(func=cmd_ai)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ExecutionBlocked as exc:
        print(f"BLOCKED: {exc.reason}", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 3
    except ApprovalRefused as exc:
        print(f"REFUSED: {exc.reason}", file=sys.stderr)
        return 3
    except BudgetExceeded as exc:
        print(f"STOPPED by guard {exc.limit}: {exc.reason}", file=sys.stderr)
        return 4
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc.reason}", file=sys.stderr)
        return 2
    except GdeltToolError as exc:
        print(f"ERROR ({exc.code}): {exc.reason}", file=sys.stderr)
        return 1
