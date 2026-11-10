"""Byte, request, disk and temporary-disk guards; the sequential sample run; approval gates; CLI refusals."""

from __future__ import annotations

from datetime import date

import pytest

from wealthpilot.data import gdelt as pkg
from wealthpilot.data.gdelt.cli import main
from wealthpilot.data.gdelt.config import (
    APPROVAL_REFERENCE,
    Authorization,
    Limits,
    RunConfig,
    authorize,
    load_config,
)
from wealthpilot.data.gdelt.engine import run_sample
from wealthpilot.data.gdelt.errors import ApprovalRefused, BudgetExceeded, ConfigError, NetworkDisabledError
from wealthpilot.data.gdelt.guards import TransferBudget, check_clock_skew, check_free_disk, check_tmp_usage
from wealthpilot.data.gdelt.sample import STAGE_D_SHA256, SampleSlot
from wealthpilot.data.gdelt.transport import HttpsTransport, same_resource

S1, S2, S3 = "20220301120000", "20220301121500", "20220302120000"


def slots(*stamps):
    return [SampleSlot(s, 1, i + 1) for i, s in enumerate(stamps)]


def no_sub(block, unusable):
    return None


def batch(gkg, stamp, n=5):
    return gkg.zip(stamp, [gkg.row(stamp, i) for i in range(1, n + 1)])


# ---------------------------------------------------------------- budget primitives

def test_request_and_byte_budgets_count_every_attempt():
    b = TransferBudget(max_total_bytes=1000, max_requests=3)
    b.reserve_request(400)
    b.record_bytes(400)
    b.reserve_request(400)
    b.record_bytes(150)                       # a failed, partial transfer still counts
    with pytest.raises(BudgetExceeded) as e:
        b.reserve_request(500)                # 550 + 500 > 1000
    assert e.value.limit == "max_total_bytes"
    b.reserve_request(0)
    with pytest.raises(BudgetExceeded) as e:
        b.reserve_request(0)
    assert e.value.limit == "max_requests" and (b.requests_used, b.bytes_used) == (3, 550)
    with pytest.raises(BudgetExceeded):
        b.record_bytes(10_000)


def test_disk_tmp_and_clock_guards(tmp_path, fake):
    assert check_free_disk(tmp_path, 10, disk_usage=fake.disk(11)) == 11
    with pytest.raises(BudgetExceeded):
        check_free_disk(tmp_path / "not" / "created", 10**10, disk_usage=fake.disk(10**9))
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "a.tsv.gz").write_bytes(b"x" * 600)
    with pytest.raises(BudgetExceeded):
        check_tmp_usage(tmp_path / "t", 500)
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    assert check_clock_skew(now, now + timedelta(seconds=30), 300) == 30
    with pytest.raises(BudgetExceeded):
        check_clock_skew(now, now + timedelta(minutes=10), 300)


# ---------------------------------------------------------------- the sequential sample run (fake transport)

def test_happy_run_fetches_sequentially_and_commits(make_ctx, gkg, fake):
    script = {}
    for s in (S1, S2):
        script |= fake.ok_script(s, batch(gkg, s))
    t = fake.Transport(script)
    ctx = make_ctx(keep_raw=True)
    res = run_sample(ctx, t, slots(S1, S2), selection="stage_D", substitute=no_sub)
    assert res.outcome == "completed"
    assert t.calls == [("HEAD", S1), ("HEAD", S2), ("GET", S1), ("GET", S2)]      # headers first, then one by one
    assert ctx.budget.requests_used == 4 and ctx.budget.bytes_used == res.planned_bytes
    assert ctx.manifest.state_counts() == {"processed": 2}
    assert (ctx.layout.raw_keep / f"{S1}.gkg.csv.zip").exists()                   # review keeps the raw sample


def test_planned_total_above_threshold_stops_before_any_download(make_ctx, gkg, fake):
    script = fake.ok_script(S1, batch(gkg, S1, 50))
    t = fake.Transport(script)
    ctx = make_ctx(limits=Limits(max_planned_bytes=100, max_total_bytes=10**6))
    res = run_sample(ctx, t, slots(S1), selection="stage_D", substitute=no_sub)
    assert res.outcome == "stopped_byte_budget" and "nothing downloaded" in res.stop_reason
    assert [c[0] for c in t.calls] == ["HEAD"]


def test_hard_byte_cap_stops_with_no_partial_slot(make_ctx, gkg, fake):
    b1, b2 = batch(gkg, S1, 40), batch(gkg, S2, 40)
    t = fake.Transport(fake.ok_script(S1, b1) | fake.ok_script(S2, b2))
    cap = len(b1) + len(b2) // 2
    ctx = make_ctx(limits=Limits(max_planned_bytes=cap, max_total_bytes=cap))
    res = run_sample(ctx, t, slots(S1, S2), selection="stage_D", substitute=no_sub)
    assert res.outcome == "stopped_byte_budget"
    assert ctx.manifest.state(S2) != "parsed_validated" and ctx.budget.bytes_used <= cap
    assert ("GET", S2) not in t.calls                                # refused before the request


def test_request_cap_counts_headers_and_retries(make_ctx, gkg, fake):
    body = batch(gkg, S1)
    ok = fake.ok_script(S1, body)
    err = fake.TransportError("timeout", "slow", 1234)
    t = fake.Transport({("HEAD", S1): ok[("HEAD", S1)], ("GET", S1): [err, err, err, err]})
    ctx = make_ctx(limits=Limits(max_requests=3))
    res = run_sample(ctx, t, slots(S1), selection="stage_D", substitute=no_sub)
    assert res.outcome == "stopped_request_budget"
    assert ctx.budget.requests_used == 3 and ctx.budget.bytes_used == 2 * 1234   # partial bytes of retries count


def test_transient_errors_retry_with_backoff_and_count_toward_budgets(make_ctx, gkg, fake):
    body = batch(gkg, S1)
    ok = fake.ok_script(S1, body)
    busy = fake.Response(503, {"retry-after": "1000"})
    t = fake.Transport({("HEAD", S1): ok[("HEAD", S1)], ("GET", S1): [busy, busy, ok[("GET", S1)][0]]})
    ctx = make_ctx()
    res = run_sample(ctx, t, slots(S1), selection="stage_D", substitute=no_sub)
    assert res.outcome == "completed" and ctx.manifest.state(S1) == "processed"
    assert ctx.budget.requests_used == 4 and ctx.clock.sleeps == [300.0, 300.0]     # Retry-After capped at 300 s
    attempts = ctx.manifest.db.execute("SELECT COUNT(*) FROM attempt WHERE kind='get'").fetchone()[0]
    assert attempts == 3


def test_exhausted_retries_wait_for_a_final_pass_then_fail_not_absent(make_ctx, gkg, fake):
    body = batch(gkg, S1)
    ok = fake.ok_script(S1, body)
    err = fake.TransportError("connection_error", "reset")
    t = fake.Transport({("HEAD", S1): ok[("HEAD", S1)], ("GET", S1): [err]})
    ctx = make_ctx()
    res = run_sample(ctx, t, slots(S1), selection="stage_D", substitute=no_sub)
    assert res.outcome == "interrupted" and ctx.manifest.state(S1) == "in_progress"
    ctx.clock.now = ctx.clock.now.replace(hour=ctx.clock.now.hour + 2)
    res2 = run_sample(ctx, t, slots(S1), selection="stage_D", substitute=no_sub)
    assert ctx.manifest.state(S1) == "request_failed" and res2.outcome == "completed"


def test_integrity_failure_retries_once_then_marks_invalid(make_ctx, gkg, fake):
    body = batch(gkg, S1)
    h = gkg.headers(S1, body)
    corrupt = bytearray(body)
    corrupt[len(corrupt) // 2] ^= 0xFF
    bad = fake.Response(200, h, bytes(corrupt))
    t = fake.Transport({("HEAD", S1): [fake.Response(200, h)], ("GET", S1): [bad, bad]})
    ctx = make_ctx()
    run_sample(ctx, t, slots(S1), selection="stage_D", substitute=no_sub)
    row = ctx.manifest.slot(S1)
    assert ctx.manifest.state(S1) == "downloaded_invalid" and row["validation_status"] == "md5_mismatch"
    assert [c for c in t.calls if c[0] == "GET"] == [("GET", S1), ("GET", S1)]


def test_unverifiable_server_time_is_recorded_as_invalid_not_used(make_ctx, gkg, fake):
    body = batch(gkg, S1)
    h = gkg.headers(S1, body, drop=("date",))
    t = fake.Transport({("HEAD", S1): [fake.Response(200, h)], ("GET", S1): [fake.Response(200, h, body)]})
    ctx = make_ctx()
    run_sample(ctx, t, slots(S1), selection="stage_D", substitute=no_sub)
    row = ctx.manifest.slot(S1)
    assert ctx.manifest.state(S1) == "downloaded_invalid"
    assert (row["validation_status"], row["availability_reason"]) == ("availability_unverified", "server_date_missing")


def test_absent_sample_slot_is_replaced_by_the_pre_registered_rule(make_ctx, gkg, fake):
    body = batch(gkg, S3)
    t = fake.Transport(fake.ok_script(S3, body))                     # S1 answers 404 (default)
    ctx = make_ctx()
    calls = []

    def sub(block, unusable):
        calls.append((block, set(unusable)))
        return S3 if S3 not in unusable else None

    res = run_sample(ctx, t, slots(S1), selection="stage_D", substitute=sub)
    assert res.substitutions == [(S1, S3)] and calls[0] == (1, {S1})
    assert ctx.manifest.state(S1) == "absent_inconclusive" and ctx.manifest.state(S3) == "processed"


def test_disk_floor_stop_file_and_tmp_cap(make_ctx, gkg, fake, tmp_path):
    t = fake.Transport(fake.ok_script(S1, batch(gkg, S1)))
    low = make_ctx(disk_free=5 * 10**9, root=tmp_path / "low")
    assert run_sample(low, t, slots(S1), selection="stage_D", substitute=no_sub).outcome == "stopped_disk_space"
    assert t.calls == []                                             # refused before the first request
    stop = make_ctx(root=tmp_path / "stop")
    (stop.layout.root / "STOP").write_text("stop")
    assert run_sample(stop, t, slots(S1), selection="stage_D", substitute=no_sub).outcome == "stopped_by_user"
    capped = make_ctx(root=tmp_path / "cap", limits=Limits(max_tmp_bytes=10))
    (capped.layout.tmp / "2022-03-01").mkdir(parents=True)
    (capped.layout.tmp / "2022-03-01" / "keep.bin").write_bytes(b"x" * 100)
    res = run_sample(capped, t, slots(S1), selection="stage_D", substitute=no_sub)
    assert res.outcome == "stopped_byte_budget" and "temporary disk" in res.stop_reason


# ---------------------------------------------------------------- configuration and limits

def write_cfg(tmp_path, text):
    p = tmp_path / "run.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_limits_can_be_tightened_never_relaxed(tmp_path):
    cfg = load_config(write_cfg(tmp_path, "limits:\n  max_total_bytes: 1000000000\n  max_planned_bytes: 900000000\n"
                                          "  max_requests: 500\n"))
    assert cfg.limits.max_total_bytes == 1_000_000_000 and cfg.limits.max_requests == 500
    for text in ("limits:\n  max_total_bytes: 1600000000\n", "limits:\n  max_requests: 1201\n",
                 "limits:\n  max_planned_bytes: 1400000000\n", "limits:\n  min_free_bytes_runtime: 1000\n",
                 "limits:\n  parallel_enabled: true\n", "limits:\n  max_concurrency: 2\n",
                 "limits:\n  surprise: 1\n", "unknown_key: 1\n", "mode: everything\n",
                 "limits:\n  max_total_bytes: 1000000000\n"):          # cap below the planned threshold
        with pytest.raises(ConfigError):
            load_config(write_cfg(tmp_path, text))


def test_defaults_examples_and_partial_records_are_never_approval(tmp_path):
    assert load_config(None).approvals == {}
    example = pkg.__path__[0] + "/config.example.yaml"
    assert load_config(example).approvals == {}
    vague = load_config(write_cfg(tmp_path, "mode: dev_sample\napprovals:\n  dev_sample:\n    approved: 'true'\n"))
    assert vague.approvals == {}                                     # a string is not the boolean true
    with pytest.raises(ConfigError):
        load_config(write_cfg(tmp_path, "mode: dev_sample\napprovals:\n  dev_sample:\n    approved: true\n"))
    with pytest.raises(ConfigError, match="email"):
        load_config(write_cfg(tmp_path, f"""mode: dev_sample
approvals:
  dev_sample: {{approved: true, approved_by: a@b.c, approved_on: 2026-10-13, reference: {APPROVAL_REFERENCE},
               data_allowance_remaining_bytes: 2000000000, stage_sha256: "{STAGE_D_SHA256}"}}
"""))


def full_record_config(tmp_path, allowance=2_000_000_000, sha=STAGE_D_SHA256, mode="dev_sample"):
    return load_config(write_cfg(tmp_path, f"""mode: {mode}
approvals:
  dev_sample: {{approved: true, approved_by: TEST, approved_on: 2026-10-13, reference: {APPROVAL_REFERENCE},
               data_allowance_remaining_bytes: {allowance}, stage_sha256: "{sha}"}}
"""))


def test_full_acquisition_always_refuses(tmp_path):
    cfg = full_record_config(tmp_path, mode="full_acquisition")
    with pytest.raises(ApprovalRefused, match="not approved"):
        authorize(cfg, "full_acquisition", cli_confirmed_network=True, expected_stage_sha256=STAGE_D_SHA256)
    assert main(["acquire"]) == 3


def test_development_sample_lock_refuses_even_with_a_complete_record(tmp_path, monkeypatch):
    import wealthpilot.data.gdelt.config as config_module
    monkeypatch.setattr(config_module, "DEV_SAMPLE_ENABLED_IN_THIS_BUILD", False)
    cfg = full_record_config(tmp_path)
    with pytest.raises(ApprovalRefused, match="disabled in this build"):
        authorize(cfg, "dev_sample", cli_confirmed_network=True, expected_stage_sha256=STAGE_D_SHA256)


def test_build_state_after_b2m_keeps_every_other_gate(tmp_path):
    # B2-M lifted the development-sample and network locks only; the confirmation lock stays on
    assert pkg.DEV_SAMPLE_ENABLED_IN_THIS_BUILD is True and pkg.NETWORK_ENABLED_IN_THIS_BUILD is True
    assert pkg.CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD is False
    assert main(["fetch-sample", "--confirm-network"]) == 3          # no config: mode is dry_run
    cfg = full_record_config(tmp_path)
    with pytest.raises(ApprovalRefused, match="--confirm-network"):
        authorize(cfg, "dev_sample", cli_confirmed_network=False, expected_stage_sha256=STAGE_D_SHA256)
    with pytest.raises(ApprovalRefused, match="stage_sha256"):
        authorize(cfg, "dev_sample", cli_confirmed_network=True, expected_stage_sha256="b" * 64)


@pytest.mark.parametrize("kwargs,flag,match", [
    ({"sha": "0" * 64}, True, "stage_sha256"),
    ({"allowance": 1_000_000_000}, True, "allowance"),
    ({}, False, "--confirm-network"),
])
def test_gate_reasons_when_the_build_lock_is_lifted(tmp_path, monkeypatch, kwargs, flag, match):
    import wealthpilot.data.gdelt.config as config_module
    monkeypatch.setattr(config_module, "DEV_SAMPLE_ENABLED_IN_THIS_BUILD", True)
    cfg = full_record_config(tmp_path, **kwargs)
    with pytest.raises(ApprovalRefused, match=match):
        authorize(cfg, "dev_sample", cli_confirmed_network=flag, expected_stage_sha256=STAGE_D_SHA256)


def test_gate_passes_only_with_everything_and_the_transport_needs_a_gate_token(tmp_path, monkeypatch):
    import wealthpilot.data.gdelt.config as config_module
    monkeypatch.setattr(config_module, "DEV_SAMPLE_ENABLED_IN_THIS_BUILD", True)
    cfg = full_record_config(tmp_path)
    with pytest.raises(ApprovalRefused, match="no complete approval"):
        authorize(RunConfig(mode="dev_sample"), "dev_sample", cli_confirmed_network=True,
                  expected_stage_sha256=STAGE_D_SHA256)
    auth = authorize(cfg, "dev_sample", cli_confirmed_network=True, expected_stage_sha256=STAGE_D_SHA256)
    assert auth.network and auth.approval.approved_on == date(2026, 10, 13)
    monkeypatch.setattr(pkg, "NETWORK_ENABLED_IN_THIS_BUILD", False)
    with pytest.raises(NetworkDisabledError):
        HttpsTransport(auth, cfg.limits)                              # network lock off: refused
    monkeypatch.setattr(pkg, "NETWORK_ENABLED_IN_THIS_BUILD", True)
    forged = Authorization("dev_sample", True, None, cfg.limits)      # not issued by the gate
    with pytest.raises(NetworkDisabledError, match="gate-issued"):
        HttpsTransport(forged, cfg.limits)
    dry = authorize(cfg, "dry_run")                                   # gate-issued but not network-capable
    with pytest.raises(NetworkDisabledError):
        HttpsTransport(dry, cfg.limits)
    transport = HttpsTransport(auth, cfg.limits)                      # constructing opens no connection
    assert transport._conn is None


def test_confirmation_sample_is_refused_without_a_trigger(tmp_path):
    cfg = full_record_config(tmp_path, mode="confirmation_sample")
    with pytest.raises(ApprovalRefused):
        authorize(cfg, "confirmation_sample", cli_confirmed_network=True, trigger_valid=False)
    assert main(["fetch-sample", "--stage", "C", "--confirm-network"]) == 3


def test_dry_run_cli_is_offline_and_reports_blockers(capsys):
    assert main(["dry-run"]) == 0
    out = capsys.readouterr().out
    assert "ready_for_development_sample: False" in out and "approval_record" in out and "build_lock" in out


@pytest.mark.parametrize("location,ok", [
    ("https://data.gdeltproject.org:443/gdeltv2/x.zip", True),       # the B2-H run-1 case
    ("https://data.gdeltproject.org/gdeltv2/x.zip", True),
    ("http://data.gdeltproject.org/gdeltv2/x.zip", False),
    ("https://data.gdeltproject.org:8443/gdeltv2/x.zip", False),
    ("https://evil.example.org/gdeltv2/x.zip", False),
    ("https://data.gdeltproject.org/gdeltv2/x.zip?a=1", False),
    ("https://data.gdeltproject.org:bad/gdeltv2/x.zip", False),
])
def test_redirect_guard(location, ok):
    assert same_resource("https://data.gdeltproject.org/gdeltv2/x.zip", location) is ok


def test_unquoted_numeric_hash_is_refused_with_a_hint(tmp_path):
    with pytest.raises(ConfigError, match="in quotes"):
        load_config(write_cfg(tmp_path, f"""mode: dev_sample
approvals:
  dev_sample: {{approved: true, approved_by: T, approved_on: 2026-10-13, reference: {APPROVAL_REFERENCE},
               data_allowance_remaining_bytes: 2000000000, stage_sha256: {"1" * 64}}}
"""))


def test_code_fingerprint_is_deterministic_and_covers_the_tool(tmp_path):
    from wealthpilot.data.gdelt.preflight import code_fingerprint
    assert code_fingerprint() == code_fingerprint() and len(code_fingerprint()) == 64
    (tmp_path / "a.py").write_text("x = 1")
    first = code_fingerprint(tmp_path)
    (tmp_path / "a.py").write_text("x = 2")
    assert code_fingerprint(tmp_path) != first
