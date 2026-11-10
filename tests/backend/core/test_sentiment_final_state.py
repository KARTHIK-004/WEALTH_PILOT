"""The final state of the offline sentiment phase, verified at runtime (2026-10-30): production method `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`, no real model, no real dataset, no real
evaluation, no activation, intensity disabled, no sentiment in the ledger / anchor code. Everything runs offline: a fresh interpreter imports the sentiment modules with the network blocked and must
end up with no model or network library loaded and no connection attempt."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from wealthpilot.api.services import personalized_insight_service as service
from wealthpilot.config.settings import Settings
from wealthpilot.core import sentiment_model as trained
from wealthpilot.core.user_text_sentiment import METHOD_RULES, METHOD_VERSION, analyse_user_text

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ("I feel anxious about my debt and want to save more each month", "Please call 07700 900123 or write jane.doe@example.com about my savings worries 123456789012",
           "I am worried about money, see https://example.org/page for my loan", "If I lost my job I would panic about my savings", 'My friend said "I hate my debt" yesterday',
           "My brother is terrified about his mortgage", "Last year I was very stressed about my loan", "The weather is lovely and the football was great")
WEIGHT_FILES = ("*.safetensors", "pytorch_model.bin", "tf_model.h5", "flax_model.msgpack")
SKIP = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}


def test_the_production_method_is_the_rules_baseline_and_the_model_flag_is_false_by_default(monkeypatch):
    for key in [k for k in __import__("os").environ if k.startswith("SENTIMENT_")]:
        monkeypatch.delenv(key)
    settings = Settings(_env_file=None)
    assert METHOD_VERSION == "user_text_rules_v1" and settings.sentiment_model_enabled is False
    assert (settings.sentiment_model_name, settings.sentiment_model_path, settings.sentiment_model_version) == ("", "", "") and settings.sentiment_model_allow_fallback is True
    example = [line.strip() for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines() if line.startswith("SENTIMENT_MODEL_ENABLED")]
    assert example == ["SENTIMENT_MODEL_ENABLED=false"]
    env = ROOT / ".env"
    if env.exists():
        assert not [l for l in env.read_text(encoding="utf-8").splitlines() if l.replace(" ", "").lower().startswith("sentiment_model_enabled=true")]


def test_the_service_reports_the_model_disabled_returns_no_model_and_never_offers_an_intensity():
    status = service.sentiment_model_status()
    assert status.enabled is False and status.state == "disabled" and status.method_when_used == "rules_baseline" and status.intensity_available is False
    assert status.model_name is None and status.model_version is None and service.get_sentiment_model() is None


def test_every_sample_is_answered_by_the_rules_baseline_with_a_null_intensity_and_no_confidence():
    for text in SAMPLES:
        analysis = analyse_user_text(text)
        out = service._sentiment_out(analysis)
        assert analysis.method == METHOD_RULES == out.method and analysis.model_version == METHOD_VERSION and out.confidence is None
        assert out.sentiment_intensity is None and out.intensity_available is False and analysis.fallback_used is False


def test_evidence_is_bounded_and_masks_contact_details_and_links():
    for text in SAMPLES:
        analysis = analyse_user_text(text)
        shown = json.dumps([getattr(e, "__dict__", str(e)) for e in analysis.evidence], default=str)
        assert all(secret not in shown for secret in ("jane.doe", "example.org", "07700", "123456789012"))
        assert all(len(getattr(e, "phrase", str(e))) <= 120 for e in analysis.evidence)


def test_unsupported_unrelated_and_third_person_text_abstains_and_hypothetical_or_past_only_text_is_not_a_current_sentiment():
    assert analyse_user_text(SAMPLES[4]).abstained and analyse_user_text(SAMPLES[5]).abstained and analyse_user_text(SAMPLES[7]).abstain_reason == "unrelated_text"
    for text in (SAMPLES[3], SAMPLES[6]):
        weak = analyse_user_text(text)
        assert weak.interpretation_state == "weak" and weak.sentiment in ("uncertain", "neutral") and weak.evidence == () and weak.confidence is None


def test_switching_the_model_on_without_an_artifact_fails_closed_to_the_rules_baseline():
    config = trained.SentimentModelConfig(enabled=True, name="ProsusAI/finbert", path="does-not-exist", version="none")
    assert trained.model_status(config).state == "unavailable"
    try:
        trained.load_model(config)
        raise AssertionError("a model loaded without an artifact")
    except trained.ModelUnavailable:
        pass
    analysis = analyse_user_text(SAMPLES[0], model=None, model_unavailable_reason="model_unavailable", allow_fallback=True)
    assert analysis.method == METHOD_RULES and analysis.fallback_used is True and analysis.sentiment == "negative"


def test_no_raw_text_reaches_the_logs(caplog):
    with caplog.at_level(logging.DEBUG):
        for text in SAMPLES:
            service._sentiment_out(analyse_user_text(text))
    logged = caplog.text
    assert "jane.doe" not in logged and all(text not in logged for text in SAMPLES)


APPROVED_LOCAL_WEIGHTS = {"models/sentiment_pretrained/horizon/model.safetensors"}          # the ONE file the owner's R2 decision (2026-11-07, ADR-056) allows on disk; it is git-ignored, never tracked


def test_no_model_weights_exist_in_the_repository_except_the_one_owner_approved_untracked_file():
    found = []
    for pattern in WEIGHT_FILES:
        for path in ROOT.rglob(pattern):
            if not (set(path.relative_to(ROOT).parts) & SKIP):
                found.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    assert [f for f in found if f not in APPROVED_LOCAL_WEIGHTS] == [] and not (ROOT / "models" / "sentiment").exists()
    assert "models/sentiment_pretrained/" in (ROOT / ".gitignore").read_text(encoding="utf-8")        # so the approved file can never be committed by accident


def test_the_ledger_and_security_code_never_mention_sentiment():
    offenders = [str(p.relative_to(ROOT)) for p in (ROOT / "backend" / "wealthpilot" / "security").rglob("*.py") if "sentiment" in p.read_text(encoding="utf-8").lower()]
    assert offenders == []


def test_importing_the_sentiment_code_in_a_fresh_interpreter_loads_no_model_or_network_library_and_makes_no_connection():
    script = f"""
import json, socket, sys
sys.path[:0] = [{str(ROOT)!r}, {str(ROOT / 'backend')!r}]
attempts = []
def blocked(*a, **k):
    attempts.append(1)
    raise OSError('blocked')
socket.socket.connect = blocked
socket.getaddrinfo = blocked
from wealthpilot.api.services import personalized_insight_service as service
from wealthpilot.core.user_text_sentiment import analyse_user_text
service.sentiment_model_status(); service.get_sentiment_model(); analyse_user_text('I feel anxious about my debt')
bad = [m for m in ('torch', 'transformers', 'tokenizers', 'safetensors', 'huggingface_hub', 'tensorflow', 'requests', 'httpx', 'urllib3') if m in sys.modules]
print(json.dumps({{'modules': bad, 'attempts': len(attempts)}}))
"""
    done = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert done.returncode == 0, done.stderr[-300:]
    assert json.loads(done.stdout.strip().splitlines()[-1]) == {"modules": [], "attempts": 0}


def test_no_financial_calculation_or_decision_module_imports_the_sentiment_code():
    """Sentiment is informational only: the optimizer, goals, compliance, recommendation, household finance, backtest and every agent module (risk, portfolio, recommendation and the explanation / debate layers)
    neither import the sentiment, model or personalized-insight modules nor mention sentiment at all."""
    import ast

    names = ("backtest", "compliance", "goals", "household_finance", "optimizer", "recommendation")
    modules = [ROOT / "backend" / "wealthpilot" / "core" / f"{n}.py" for n in names] + sorted((ROOT / "backend" / "wealthpilot" / "agents").glob("*.py"))
    for path in modules:
        source = path.read_text(encoding="utf-8")
        assert "sentiment" not in source.lower(), path.name
        imported = {n.module or "" for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import) for a in n.names}
        assert not any(x.endswith(("user_text_sentiment", "sentiment_model", "personalized_insight")) for x in imported), path.name


def test_the_sentiment_code_has_no_language_model_or_network_client_and_only_a_local_gated_loader():
    rules = (ROOT / "backend" / "wealthpilot" / "core" / "user_text_sentiment.py").read_text(encoding="utf-8").lower()
    gated = (ROOT / "backend" / "wealthpilot" / "core" / "sentiment_model.py").read_text(encoding="utf-8")
    words = ("genai", "gemini", "autogen", "openai", "anthropic", "import requests", "import httpx", "urllib.request", "huggingface_hub")
    assert not any(w in rules or w in gated.lower() for w in words) and "from_pretrained" not in rules
    loads = [line.strip() for line in gated.splitlines() if "from_pretrained" in line]
    assert len(loads) == 2 and all("local_files_only=True" in l and "trust_remote_code=False" in l for l in loads) and "use_safetensors=True" in loads[1]          # the only loader is local, never remote code
