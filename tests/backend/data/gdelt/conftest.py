"""Shared fixtures for the isolated GDELT tool tests.

Every test here is offline and database-free:

- ``_no_network`` (autouse) makes any socket connection or DNS lookup fail and fails the test if one
  was attempted;
- ``_no_database`` (autouse) makes the application's engine factory raise.

All GKG rows are SYNTHETIC: titles start with "SYNTHETIC", URLs use the reserved example.com/.org
domains, and nothing here is presented as real historical news.
"""

from __future__ import annotations

import hashlib
import io
import socket
import zipfile
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import pytest

from wealthpilot.data.gdelt.config import Limits
from wealthpilot.data.gdelt.transport import HttpResponse, TransportError, archive_url

NETWORK_ATTEMPTS: list[str] = []


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    NETWORK_ATTEMPTS.clear()

    def refuse(*args, **kwargs):
        NETWORK_ATTEMPTS.append(repr(args)[:80])
        raise RuntimeError("network access is forbidden in GDELT tool tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield
    assert NETWORK_ATTEMPTS == [], f"a network connection was attempted: {NETWORK_ATTEMPTS}"


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    import wealthpilot.db.session as session_module

    def refuse(*args, **kwargs):
        raise RuntimeError("database access is forbidden in GDELT tool tests")

    monkeypatch.setattr(session_module, "get_engine", refuse)
    yield


# --------------------------------------------------------------------------- synthetic GKG builders

def http_date(dt: datetime) -> str:
    return format_datetime(dt.astimezone(timezone.utc), usegmt=True)


def make_row(stamp: str, seq: int, *, title: str | None = None,
             url: str | None = None, themes: list[str] | None = None, mentions: dict[str, int] | None = None,
             locations: list[str] | None = None, orgs: list[str] | None = None, tone: str = "0.5,1,0.5,1.5,20,0,250",
             translation: str = "", collection: str = "1", date: str | None = None, record_id: str | None = None,
             pubts: str | None = None, n_fields: int = 27) -> str:
    title = title if title is not None else f"SYNTHETIC TEST ROW {seq}: neutral placeholder text"
    themes = themes or []
    mentions = mentions or {t: 1 for t in themes}
    v2 = ";".join(f"{t},{100 + i * 10 + k}" for i, (t, n) in enumerate(sorted(mentions.items())) for k in range(n))
    extras = f"<PAGE_TITLE>{title}</PAGE_TITLE>"
    if pubts:
        extras = f"<PAGE_PRECISEPUBTIMESTAMP>{pubts}</PAGE_PRECISEPUBTIMESTAMP>" + extras
    cols = [""] * 27
    cols[0] = record_id or f"{stamp}-{seq}"
    cols[1] = date or stamp
    cols[2] = collection
    cols[3] = "example.com"
    cols[4] = url or f"https://www.example.com/synthetic/{stamp}/{seq}"
    cols[7] = ";".join(themes)
    cols[8] = v2
    cols[9] = ";".join(locations or [])
    cols[13] = ";".join(orgs or [])
    cols[15] = tone
    cols[25] = translation
    cols[26] = extras
    return "\t".join(cols[:n_fields] if n_fields <= 27 else cols + ["x"] * (n_fields - 27))


US_CITY = "3#Springfield, Illinois, United States#US#USIL#39.8#-89.6#1"
UK_CITY = "4#London, London, City of, United Kingdom#UK#UKH9#51.5#-0.1#-2601889"


def make_zip(stamp: str, lines: list[str] | bytes, *, member: str | None = None, extra_members: int = 0,
             date_time: tuple[int, ...] | None = None, compression: int = zipfile.ZIP_DEFLATED,
             final_newline: bool = True) -> bytes:
    data = lines if isinstance(lines, bytes) else ("\n".join(lines) + ("\n" if final_newline else "")).encode("utf-8")
    nominal = datetime.strptime(stamp, "%Y%m%d%H%M%S")
    dt = date_time or (nominal - timedelta(minutes=9)).timetuple()[:6]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as z:
        info = zipfile.ZipInfo(member or f"{stamp}.gkg.csv", date_time=dt)
        info.compress_type = compression
        z.writestr(info, data)
        for i in range(extra_members):
            z.writestr(f"extra{i}.txt", b"x")
    return buf.getvalue()


def headers_for(stamp: str, body: bytes, *, lm_offset_min: float = -9, age: int | None = 0,
                etag: str | None = "md5", drop: tuple[str, ...] = ()) -> dict[str, str]:
    nominal = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    h = {"content-length": str(len(body)), "last-modified": http_date(nominal + timedelta(minutes=lm_offset_min)),
         "date": http_date(datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)), "content-type": "application/zip"}
    if age is not None:
        h["age"] = str(age)
    if etag == "md5":
        h["etag"] = '"' + hashlib.md5(body).hexdigest() + '"'
    elif etag is not None:
        h["etag"] = etag
    for k in drop:
        h.pop(k, None)
    return h


@pytest.fixture()
def gkg():
    return SimpleNamespace(row=make_row, zip=make_zip, headers=headers_for, http_date=http_date, US_CITY=US_CITY,
                           UK_CITY=UK_CITY)


# --------------------------------------------------------------------------- fake transport

class FakeTransport:
    """Scripted in-memory transport. ``script[(method, stamp)]`` is a list of responses or exceptions,
    consumed in order (the last one repeats)."""

    def __init__(self, script: dict[tuple[str, str], list]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[tuple[str, str]] = []

    def _next(self, method: str, url: str):
        stamp = url.rsplit("/", 1)[1].split(".", 1)[0]
        self.calls.append((method, stamp))
        seq = self.script.get((method, stamp))
        if not seq:
            return HttpResponse(404, {"date": http_date(datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)), "age": "0"})
        item = seq.pop(0) if len(seq) > 1 else seq[0]
        if isinstance(item, Exception):
            raise item
        return item

    def head(self, url: str) -> HttpResponse:
        r = self._next("HEAD", url)
        return HttpResponse(r.status, dict(r.headers), None, 0, 1)

    def get(self, url: str, max_bytes: int) -> HttpResponse:
        r = self._next("GET", url)
        if r.body is not None and len(r.body) > max_bytes:
            raise TransportError("aborted_by_budget", "body over budget", max_bytes)
        return HttpResponse(r.status, dict(r.headers), r.body, len(r.body or b""), 1)


def ok_script(stamp: str, body: bytes, **hkw) -> dict[tuple[str, str], list]:
    h = headers_for(stamp, body, **hkw)
    return {("HEAD", stamp): [HttpResponse(200, h)], ("GET", stamp): [HttpResponse(200, h, body)]}


DiskUsage = namedtuple("DiskUsage", "total used free")


def disk(free: int):
    return lambda path: DiskUsage(10**12, 10**12 - free, free)


@pytest.fixture()
def fake():
    return SimpleNamespace(Transport=FakeTransport, ok_script=ok_script, disk=disk, Response=HttpResponse,
                           TransportError=TransportError, url=archive_url)


@pytest.fixture()
def small_limits():
    return Limits()


# --------------------------------------------------------------------------- run context

class FakeClock:
    def __init__(self, start: datetime = datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)):
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds)


@pytest.fixture()
def make_ctx(tmp_path):
    from wealthpilot.data.gdelt import PARSER_VERSION
    from wealthpilot.data.gdelt.engine import RunContext
    from wealthpilot.data.gdelt.events import EventLog
    from wealthpilot.data.gdelt.filters import default_classifier
    from wealthpilot.data.gdelt.guards import TransferBudget
    from wealthpilot.data.gdelt.manifest import Manifest
    from wealthpilot.data.gdelt.output import Layout

    def _make(*, limits: Limits | None = None, disk_free: int = 200 * 10**9, keep_raw: bool = False,
              sample_cutoff: datetime | None = None, root=None, run_id: str = "test-run"):
        lim = limits or Limits()
        classifier = default_classifier()
        layout = Layout(root or (tmp_path / "out"), classifier.spec.version)
        manifest = Manifest(layout.manifest_path)
        if manifest.db.execute("SELECT 1 FROM run WHERE run_id=?", (run_id,)).fetchone() is None:
            manifest.start_run(run_id, "dev_sample", code_sha256="test", parser_version=PARSER_VERSION,
                               filter_version=classifier.spec.version, filter_spec_sha256=classifier.spec.sha256,
                               audited_list_sha256="test", selection_sha256=None, params={}, python_version="test",
                               tzdata_version=None, free_bytes_at_start=None)
        clock = FakeClock()
        ctx = RunContext(run_id, layout, manifest, classifier, lim, TransferBudget(lim.max_total_bytes, lim.max_requests),
                         EventLog(None), clock=clock, sleep=clock.sleep, disk_usage=disk(disk_free), keep_raw=keep_raw,
                         sample_cutoff=sample_cutoff)
        return ctx

    return _make


def ingest(ctx, stamp: str, body: bytes, headers: dict[str, str]):
    """Offline path for one batch: register, mark available, begin fetch, process."""
    from wealthpilot.data.gdelt.engine import process_body
    from wealthpilot.data.gdelt.integrity import md5_from_etag

    ctx.manifest.add_slot(stamp, archive_url(stamp), list_status="not_consulted")
    ctx.manifest.mark_available(stamp, evidence="test", content_length=int(headers["content-length"]),
                                etag_md5=md5_from_etag(headers.get("etag")))
    ctx.manifest.begin_fetch(stamp, ctx.run_id)
    return process_body(ctx, stamp, body, headers)


@pytest.fixture()
def ingest_fn():
    return ingest


# --------------------------------------------------------------------------- AI-assisted annotation (all SYNTHETIC)

@pytest.fixture()
def make_ai_env(tmp_path):
    """Factory for a synthetic ORIGINAL review folder plus an experiment config. Nothing real, nothing networked."""
    import csv
    import json
    from datetime import date

    import yaml

    from wealthpilot.data.gdelt.ai import config as aic
    from wealthpilot.data.gdelt.ai import provider as aprov
    from wealthpilot.data.gdelt.ai.fingerprints import itemset_fingerprint
    from wealthpilot.data.gdelt.ai.schema import APPROVED_INPUT_FIELDS, load_items
    from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

    counter = {"n": 0}
    env_name, secret = "FAKE_AI_API_KEY", "sk-test-CANARY-SECRET-123456"

    def title_of(i: int) -> str:
        return f"SYNTHETIC {i}: Federal Reserve raises interest rates by a quarter point"

    def _build(*, n: int = 6, overlap: tuple[str, ...] = ("D0002", "D0004"), unsendable: tuple[str, ...] = (),
               blind: tuple[str, ...] = (), dup: tuple[str, ...] = ()):
        counter["n"] += 1
        root = tmp_path / f"env{counter['n']}"
        rf = root / "review_files"
        (rf / "backup").mkdir(parents=True)
        (rf / "working").mkdir()

        def write(path, rows):
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(ANNOTATION_COLUMNS), lineterminator="\n")
                w.writeheader()
                w.writerows(rows)

        rows = []
        for i in range(1, n + 1):
            iid = f"D{i:04d}"
            title = title_of(i) + ("\x07" if iid in unsendable else "")
            rows.append({c: "" for c in ANNOTATION_COLUMNS} | {
                "item_id": iid, "gkg_record_id": f"20220301120000-{i}", "batch_ts": "20220301120000",
                "batch_date_utc": "2022-03-01", "available_at_utc": "2022-03-01T12:15:00Z", "source_domain": "example.com",
                "url": f"https://example.com/synthetic/{i}", "title": title,
                "mech_dup": "EXACT_DUP" if iid in dup else "ORIGINAL", "overlap_subset": "Y" if iid in overlap else "N"})
        write(rf / "annotation_A.csv", rows)
        write(rf / "annotation_B.csv", [r for r in rows if r["overlap_subset"] == "Y"])
        write(rf / "backup" / "annotation_A.build.csv", rows)
        write(rf / "working" / "annotation_A.working.csv", rows)
        (rf / "working" / "merge_log.jsonl").write_text("", encoding="utf-8")
        # D13: a lock record the AI package can compare with the config (a stand-in: the real one is made by
        # `annotate lock-overlap` from verified labels; these folders have no labels)
        from wealthpilot.data.gdelt.overlap_lock import SCHEMA as LOCK_SCHEMA, _sha_obj as lock_sha
        lock_body = {"schema": LOCK_SCHEMA, "overlap_labels_sha256": "ab" * 32, "overlap_items": len(overlap)}
        (rf / "working" / "overlap_labels_lock.json").write_text(
            json.dumps({**lock_body, "record_sha256": lock_sha(lock_body)}), encoding="utf-8")
        (rf / "ANNOTATION_INSTRUCTIONS.md").write_text("synthetic\n", encoding="utf-8")

        def sha(name: str) -> str:
            return hashlib.sha256((rf / name).read_bytes()).hexdigest()

        (rf / "selection_log.json").write_text(json.dumps({"files_sha256": {
            "annotation_A.csv": sha("annotation_A.csv"), "annotation_B.csv": sha("annotation_B.csv")}}), encoding="utf-8")
        env = SimpleNamespace(root=root, rf=rf, dest=root / "dest" / "b2t_test_v1", n=n, overlap=set(overlap),
                              blind=blind, secret=secret, env_name=env_name, process_env={env_name: secret},
                              ids=[f"D{i:04d}" for i in range(1, n + 1)], yaml_path=root / "experiment.yaml",
                              model="fake-model-1", provider_name="fake_provider", sha=sha)
        env.source_items = lambda: load_items(rf / "annotation_A.csv")
        env.itemset = lambda: itemset_fingerprint((i.item_id, i.fingerprint) for i in env.source_items())
        env.overlap_sha = lambda: sha("annotation_B.csv")

        def cfg_dict(*, filled: bool = True) -> dict:
            d: dict = {"experiment_id": "b2t_test_v1", "source": {"review_files": str(rf)},
                       "destination": str(env.dest),
                       "protocol": {"id": "option_B_all_items_ai_assisted", "blind_item_ids": list(blind),
                                    "review_required_for_every_item": True, "polarity_option": None,
                                    "provider_exclusion": None, "overlap_labels_sha256": None},
                       "provider": {"name": None, "model_id": None, "model_version": None,
                                    "credentials_env_var": env_name, "timeout_seconds": 30,
                                    "temperature": None},
                       "prompt": {"version": "b2t_prompt_v1", "rubric_version": "b2t_rubric_v1"},
                       "limits": {"max_requests": None, "max_input_tokens": None, "max_output_tokens_per_request": 400,
                                  "max_attempts_per_item": 3, "max_reasks_per_item": 1, "backoff_seconds": [1, 2, 4]},
                       "data_handling": {"provider_data_terms_reviewed": False, "retention_days": None,
                                         "external_transmission_fields": list(APPROVED_INPUT_FIELDS)},
                       "run_id": None, "approvals": {"A": None, "B": None, "C": None, "D": None}}
            if filled:
                d["provider"].update(name="fake_provider", model_id="fake-model-1", model_version="2026-01-01",
                                     temperature=0.0)
                d["protocol"]["polarity_option"] = "P1_required_as_in_existing_rubric"
                d["protocol"]["provider_exclusion"] = "none"      # explicit: nothing excluded (older tests send every item)
                d["protocol"]["overlap_labels_sha256"] = "ab" * 32  # matches the stand-in lock record above
                d["limits"].update(max_requests=100, max_input_tokens=1_000_000)
                d["data_handling"].update(provider_data_terms_reviewed=True, retention_days=30)
                d["run_id"] = "run-test-1"
            return d

        def write_cfg(d: dict):
            env.yaml_path.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
            return env.yaml_path

        def approved(d: dict, gates=("A", "B", "C", "D")) -> dict:
            """Return ``d`` with approval records bound to exactly what ``d`` currently says."""
            write_cfg(d)
            cfg = aic.load_experiment(env.yaml_path)
            b = aic.bindings(cfg, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                             overlap_item_ids=frozenset(env.overlap))
            d = json.loads(json.dumps(d))
            for g in gates:
                d["approvals"][g] = {"approved": True, "approved_by": "AB", "approved_on": date(2026, 10, 19),
                                     "reference": "synthetic test approval", "binds_sha256": b[g]}
            return d

        def enable(monkeypatch, factory=None):
            import wealthpilot.data.gdelt as pkg
            monkeypatch.setattr(pkg, "AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD", True)
            monkeypatch.setitem(aprov.ADAPTERS, "fake_provider", factory or (lambda *a: None))

        def authorize(cfg):
            return aic.authorize_run(cfg, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                                     confirm_ai_run=True, env=env.process_env,
                                     overlap_item_ids=frozenset(env.overlap))

        def good(item_id: str, **over) -> str:
            body = {"item_id": item_id, "rel_equity": "I", "rel_rates": "R", "rel_gold": "I", "amb_code": "",
                    "company_notice": "N", "pol_equity": "", "pol_rates": "NEG", "pol_gold": "", "note": "",
                    "evidence_excerpts": [{"field": "rel_rates", "excerpt": "raises interest rates"}],
                    "insufficient_evidence": False,
                    "uncertainty": {"rel_equity": "low", "rel_rates": "low", "rel_gold": "low"},
                    "evidence_basis": "headline_url_only"}
            body.update(over)
            return json.dumps(body)

        env.cfg_dict, env.write_cfg, env.approved, env.enable, env.authorize, env.good = (
            cfg_dict, write_cfg, approved, enable, authorize, good)
        env.load = lambda: aic.load_experiment(env.yaml_path)
        return env

    return _build


class ScriptedProvider:
    """A fake provider for offline tests. ``script`` maps item_id -> list of response text / exception, consumed in
    order (the last entry repeats); ``default(request)`` supplies a response for unlisted items. No network."""

    name = "fake_provider"

    def __init__(self, script: dict | None = None, *, model_id: str = "fake-model-1", default=None):
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls: list = []
        self.model_id, self.default = model_id, default

    def suggest(self, request):
        from wealthpilot.data.gdelt.ai.provider import ProviderResponse
        self.calls.append(request)
        seq = self.script.get(request.item_id)
        item = (seq.pop(0) if len(seq) > 1 else seq[0]) if seq else (self.default(request) if self.default else None)
        if isinstance(item, Exception):
            raise item
        return ProviderResponse(item, self.model_id, "2026-01-01", f"req-{len(self.calls)}", 100, 50, 12)


@pytest.fixture()
def scripted():
    return ScriptedProvider


# ---------------------------------------------------------------- B2-U8: a synthetic b2t_annotation_v1 export
# Matches a synthetic working copy, with hooks to damage one thing at a time. No provider, no key.

import csv as _csv_mod
import hashlib as _hashlib
import io as _io
import json as _json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt.annotate import Paths

SUGGESTION_REF = "a" * 64
SEEN = {"accepted_ai", "edited_ai", "rejected_ai_after_seeing", "human_uncertain", "human_insufficient_evidence"}


def _write_export(p: Paths, export_dir: Path, *, seen: dict[str, str] | None = None,
                 mutate_row: Callable[[dict[str, str]], None] | None = None,
                 mutate_manifest: Callable[[dict[str, Any]], None] | None = None,
                 drop: frozenset[str] = frozenset(), duplicate: frozenset[str] = frozenset(),
                 rehash: bool = True) -> Path:
    """``seen`` maps item_id -> an AI-seen label_origin; every other item is a human_no_suggestion record."""
    from wealthpilot.data.gdelt import annotate
    from wealthpilot.data.gdelt.ai import DATASET_SCHEMA
    from wealthpilot.data.gdelt.ai.export import B2T_COLUMNS
    seen = seen or {}
    working = {r["item_id"]: r for r in annotate._working_rows(p)}
    rows: list[dict[str, str]] = []
    for iid, w in working.items():
        if iid in drop:
            continue
        origin = seen.get(iid, "human_no_suggestion")
        row = {c: w[c] for c in B2T_COLUMNS if c in w}
        row.update({"protocol_id": "SYNTH-PROTO", "insufficient_evidence": "N", "annotator_id": "AB",
                    "annotator_type": "human", "reviewed_at_utc": "2026-10-16T09:00:00Z", "label_origin": origin,
                    "ai_exposure": "seen" if origin in SEEN else "none",
                    "suggestion_ref": SUGGESTION_REF if origin in SEEN else "", "edit_reason_code": "",
                    "review_seconds": "12.0", "review_record_sha256": _hashlib.sha256(iid.encode()).hexdigest()})
        if mutate_row:
            mutate_row(row)
        rows.append(row)
        if iid in duplicate:
            rows.append(dict(row))
    buf = _io.StringIO()
    wr = _csv_mod.DictWriter(buf, fieldnames=list(B2T_COLUMNS), lineterminator="\n")
    wr.writeheader()
    wr.writerows(rows)
    export_dir.mkdir(parents=True, exist_ok=True)
    data = buf.getvalue().encode("utf-8")
    csv_path = export_dir / "annotation_b2t_v1.csv"
    csv_path.write_bytes(data)
    manifest = {"schema": DATASET_SCHEMA, "rows": len(rows), "csv_sha256": _hashlib.sha256(data).hexdigest(),
                "historical_overlap_items": sum(w["overlap_subset"] == "Y" for w in working.values())}
    if mutate_manifest:
        mutate_manifest(manifest)
    if not rehash:
        manifest["csv_sha256"] = "0" * 64
    (export_dir / "EXPORT_MANIFEST.json").write_text(_json.dumps(manifest), encoding="utf-8")
    return export_dir


@pytest.fixture()
def write_export():
    return _write_export
