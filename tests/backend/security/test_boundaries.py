"""Static boundary checks for the sensitive-data-protection prototype (ADR-047).

These read source text; they prove the wiring claims in docs/THREAT_MODEL.md rather than leaving them as prose: no agent or LLM
module can reach the encryption service or key material, key material is read in exactly one place, the security package pulls in
no blockchain / wallet / cryptocurrency SDK, and security-relevant log calls carry only fixed text.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "backend" / "wealthpilot"


def python_files(*relative: str) -> list[Path]:
    files: list[Path] = []
    for item in relative:
        base = ROOT / item
        files += [base] if base.is_file() else sorted(base.rglob("*.py"))
    return files


def test_no_agent_llm_core_data_or_training_code_can_reach_the_security_package():
    """Gemini, AutoGen, the LangGraph nodes, the deterministic core, the data code and the training scripts never receive a key and
    never call the encryption or ledger code."""
    offenders = []
    for path in python_files("backend/wealthpilot/agents", "backend/wealthpilot/core", "backend/wealthpilot/data", "training"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"wealthpilot\.security|from wealthpilot import security|protected_data_keys|get_secret_value", text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_key_configuration_is_read_in_exactly_two_places():
    allowed = {
        "backend/wealthpilot/config/settings.py",  # declares the (SecretStr, default-empty) setting
        "backend/wealthpilot/api/dependencies.py",  # the one place that turns it into a key provider
    }
    users = {
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in python_files("backend/wealthpilot")
        if re.search(r"protected_data_keys|protected_data_active_key_id", path.read_text(encoding="utf-8"))
    }
    assert users == allowed


def test_only_the_environment_key_provider_touches_key_bytes_and_it_never_reads_the_process_environment_itself():
    for path in python_files("backend/wealthpilot/security"):
        text = path.read_text(encoding="utf-8")
        assert "os.environ" not in text and "getenv" not in text, path.name
    users = [p.name for p in python_files("backend/wealthpilot/security") if "get_key(" in p.read_text(encoding="utf-8")]
    assert sorted(users) == ["crypto.py", "keys.py"]  # the interface and its single consumer


def test_the_security_package_imports_no_blockchain_wallet_or_cryptocurrency_sdk():
    forbidden = re.compile(r"^\s*(?:from|import)\s+(web3|eth_\w*|solcx|brownie|solana|bitcoin\w*|bit|hdwallet|mnemonic|hyperledger\w*|fabric\w*|ipfshttpclient|multiformats)\b", re.M)
    for path in python_files("backend/wealthpilot/security", "backend/wealthpilot/api/services/protected_record_service.py", "backend/wealthpilot/api/routers/protected_records.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path.name


def test_the_only_new_dependency_is_the_already_installed_cryptography_library():
    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert '"cryptography==' in pyproject
    for name in ("web3", "pynacl", "pycryptodome", "bcrypt", "passlib", "pyjwt", "python-jose"):
        assert name not in pyproject.lower(), name


def test_security_log_calls_carry_only_fixed_text():
    """A log call may not interpolate: no f-string, %-format argument, .format() or extra data that could carry plaintext, a key or
    an identifier."""
    for path in python_files("backend/wealthpilot/security", "backend/wealthpilot/api/services/protected_record_service.py", "backend/wealthpilot/api/routers/protected_records.py"):
        for match in re.finditer(r"logger\.\w+\(([^)]*)\)", path.read_text(encoding="utf-8")):
            argument = match.group(1).strip()
            assert re.fullmatch(r'"[^"{}%]*"', argument), f"{path.name}: logger call is not fixed text: {argument}"


def test_the_ledger_module_cannot_name_a_sensitive_field():
    text = (PACKAGE / "security" / "ledger.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", text, flags=re.S)
    for word in ("amount", "email", "password", "token", "plaintext", "customer_id", "profile_id", "owner_id"):
        assert word not in code.lower(), word
