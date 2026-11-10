"""ADR-052 -- the safe-loading seam of the offline trainer: an IMMUTABLE base-model revision that only the caller can supply, `use_safetensors=True`, `trust_remote_code=False`, offline by default,
the obsolete `safe_serialization` argument gone, and the real tokenizer length recorded in the artifact. Nothing here needs a deep-learning package, a model, a Hub id or a network: the revision
used is a SYNTHETIC hash that names nothing, and the real library calls are covered (when the packages exist) by `test_transformer_standin.py`."""

from __future__ import annotations

import dataclasses
import inspect
import json
import re
import sys
from pathlib import Path

import pytest
from sentiment_fixtures import FAKE_IDENTIFIER, FAKE_REVISION, fake_trainer, make_rows, manifest_dict, write_jsonl, write_manifest
from standin_helpers import REVISION

from training.sentiment import train_sentiment_transformer as train
from training.sentiment.config import CANDIDATES, REPO_ROOT
from training.sentiment.dataset import load_manifest
from wealthpilot.core import sentiment_model as sm

TARGETS = dict(target_precision=0.85, min_coverage=0.5, high_precision=0.95, high_min_coverage=0.2)
CLI = ["--manifest", "m.json", "--data", "d.jsonl", "--base-model", "finbert", "--version", "v1", "--target-precision", "0.9", "--min-coverage", "0.5", "--high-precision", "0.95",
       "--high-min-coverage", "0.2"]


# ------------------------------------------------------------------------------------------------ the revision must be an immutable commit hash, supplied by the caller


@pytest.mark.parametrize("good", [REVISION, "a" * 40, "0" * 40, "9f8e7d6c5b4a39281706f5e4d3c2b1a098765432"])
def test_a_full_lowercase_commit_hash_is_accepted(good):
    assert train.validate_revision(good) == good


@pytest.mark.parametrize("bad", ["main", "master", "v1.0", "refs/heads/main", "refs/pr/1", "", " ", None, 123, b"0" * 40, ["0" * 40], REVISION[:7], REVISION[:39], REVISION + "0", REVISION.upper(),
                                 "g" * 40, REVISION + "\n", " " + REVISION, REVISION + " ", "0x" + REVISION[:38]])
def test_a_branch_tag_short_hash_or_missing_value_is_refused(bad):
    with pytest.raises(train.RevisionError):
        train.validate_revision(bad)


def test_the_revision_has_no_default_anywhere_and_no_hash_is_written_in_the_sources():
    sig = inspect.signature(train.fine_tune_with_torch).parameters
    assert sig["revision"].kind is inspect.Parameter.KEYWORD_ONLY and sig["revision"].default is inspect.Parameter.empty            # required, never defaulted
    assert sig["allow_hub_download"].kind is inspect.Parameter.KEYWORD_ONLY and sig["allow_hub_download"].default is False        # offline unless asked
    for entry in CANDIDATES.values():
        assert "revision" not in entry                                                                                     # the candidate register carries identifiers only
    hash_like = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")
    for path in list((REPO_ROOT / "training" / "sentiment").glob("*.py")) + [REPO_ROOT / "backend" / "wealthpilot" / "core" / "sentiment_model.py"]:
        assert not hash_like.search(path.read_text(encoding="utf-8")), f"{path.name} contains a 40-character hash: no revision may be written into the code"


def test_calling_the_trainer_without_a_revision_is_a_type_error():
    with pytest.raises(TypeError):
        train.fine_tune_with_torch([], [], [], Path("."), base_model="finbert", epochs=0, learning_rate=1e-5, batch_size=2, max_tokens=8, seed=42)


@pytest.mark.parametrize("bad", ["main", "", None, REVISION[:7]])
def test_an_invalid_revision_is_refused_before_any_package_is_imported(monkeypatch, tmp_path, bad):
    monkeypatch.setitem(sys.modules, "torch", None)                  # an import of either package would now raise ImportError instead of the error asserted below
    monkeypatch.setitem(sys.modules, "transformers", None)
    with pytest.raises(train.RevisionError):
        train.fine_tune_with_torch([], [], [], tmp_path, base_model="finbert", epochs=0, learning_rate=1e-5, batch_size=2, max_tokens=8, seed=42, revision=bad)
    assert not list(tmp_path.iterdir())                              # nothing was written either


# ------------------------------------------------------------------------------------------------ the shared loading keywords


def test_the_loading_keywords_pin_the_revision_refuse_remote_code_and_default_to_offline():
    assert train.base_model_loading_kwargs(REVISION) == {"revision": REVISION, "trust_remote_code": False, "local_files_only": True}


def test_only_an_explicit_download_switch_turns_offline_loading_off_and_remote_code_stays_refused():
    kwargs = train.base_model_loading_kwargs(REVISION, allow_hub_download=True)
    assert kwargs == {"revision": REVISION, "trust_remote_code": False, "local_files_only": False}


def test_the_loading_keywords_validate_the_revision():
    with pytest.raises(train.RevisionError):
        train.base_model_loading_kwargs("main")


def test_the_trainer_source_loads_with_the_shared_keywords_and_no_obsolete_serialization_argument():
    source = inspect.getsource(train.fine_tune_with_torch)
    assert "safe_serialization=" not in source                                                    # transformers 5.x: the 4.x keyword is gone (accepted silently, no effect)
    assert "model.save_pretrained(directory)" in source and "tokenizer.save_pretrained(directory)" in source
    assert source.count("**loading") == 2 and "use_safetensors=True" in source                      # the tokenizer and the model are loaded with the same pinned, offline keywords
    for call in re.findall(r"from_pretrained\([^\n]*", source):
        assert "**loading" in call or "hub_id" in call, call
    assert source.index("base_model_loading_kwargs(revision") < source.index("import torch")        # the revision is checked before any heavy import


def test_no_other_call_in_the_training_package_loads_a_pretrained_model():
    for path in (REPO_ROOT / "training" / "sentiment").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name not in ("train_sentiment_transformer.py", "local_model_dir.py"):
            assert "from_pretrained" not in text, path.name


def test_the_one_other_loader_loads_only_a_verified_local_directory_with_the_safe_parameters():
    """`local_model_dir.py` (Path B, prepared and unwired) is the only other module that may call `from_pretrained`: its calls take the local directory path variable, never an identifier, with
    `local_files_only=True` and `trust_remote_code=False` as literal constants (and `use_safetensors=True` for the model)."""
    import ast

    tree = ast.parse((REPO_ROOT / "training" / "sentiment" / "local_model_dir.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "from_pretrained"]
    assert len(calls) == 2
    for call in calls:
        assert len(call.args) == 1 and isinstance(call.args[0], ast.Name) and call.args[0].id == "path"
        keywords = {k.arg: k.value for k in call.keywords}
        assert isinstance(keywords["local_files_only"], ast.Constant) and keywords["local_files_only"].value is True
        assert isinstance(keywords["trust_remote_code"], ast.Constant) and keywords["trust_remote_code"].value is False
    assert sum(1 for c in calls if any(k.arg == "use_safetensors" and isinstance(k.value, ast.Constant) and k.value.value is True for k in c.keywords)) == 1


# ------------------------------------------------------------------------------------------------ the command line


def test_the_command_line_requires_a_revision_and_refuses_a_branch(capsys):
    assert train.main(CLI) == 2 and "required arguments missing: --revision" in capsys.readouterr().err
    assert train.main(CLI + ["--revision", "main"]) == 2 and "40-character lowercase hexadecimal commit hash" in capsys.readouterr().err
    assert train.main(CLI + ["--revision", REVISION[:12]]) == 2 and "REFUSED" in capsys.readouterr().err


def test_the_command_line_passes_the_revision_and_the_download_switch_to_the_trainer(tmp_path, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(train.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(train, "load_manifest", lambda path: object())
    monkeypatch.setattr(train, "run_training", lambda **kwargs: kwargs["trainer"]([], [], [], tmp_path) or {"ok": True})
    monkeypatch.setattr(train, "fine_tune_with_torch", lambda *a, **k: seen.update(k))
    assert train.main(CLI + ["--revision", REVISION]) == 0
    assert seen["revision"] == REVISION and seen["allow_hub_download"] is False          # offline unless the switch is given
    seen.clear()
    assert train.main(CLI + ["--revision", REVISION, "--allow-hub-download"]) == 0
    assert seen["revision"] == REVISION and seen["allow_hub_download"] is True


# ------------------------------------------------------------------------------------------------ the artifact records the real tokenizer length


def test_the_trainer_output_has_the_tokenizer_length_as_a_required_field():
    fields = {f.name: f for f in dataclasses.fields(train.TrainerOutput)}
    assert "tokenizer_length" in fields
    assert fields["tokenizer_length"].default is dataclasses.MISSING and fields["tokenizer_length"].default_factory is dataclasses.MISSING          # no default: a trainer cannot forget it


def test_the_artifact_records_the_tokenizer_length_apart_from_the_embedding_size_and_the_loader_accepts_the_padded_case(tmp_path):
    data = write_jsonl(tmp_path / "data.jsonl", make_rows(40, group_every=4))
    manifest = load_manifest(write_manifest(tmp_path / "manifest.json", manifest_dict()), allow_development_fixture=True)
    result = train.run_training(manifest=manifest, data_path=data, base_model="finbert", version="sentiment-v1", output_root=tmp_path / "out", trainer=fake_trainer(), allow_development_fixture=True,
                                **TARGETS)
    directory = Path(result["directory"])
    metadata = json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))
    assert metadata["tokenizer"]["vocab_size"] == 5000 and metadata["tokenizer"]["length"] == 4990                  # padded embedding matrix: two numbers, not required to be equal
    info = sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="finbert", max_tokens=128)
    assert info.tokenizer_length == 4990


def test_the_writer_cannot_produce_an_artifact_the_loader_would_refuse(tmp_path):
    """`write_artifact` ends with the loader's own verification, so a missing or malformed length fails at writing time, not at first use."""
    data = write_jsonl(tmp_path / "data.jsonl", make_rows(40, group_every=4))
    manifest = load_manifest(write_manifest(tmp_path / "manifest.json", manifest_dict()), allow_development_fixture=True)
    for index, bad in enumerate((0, -1, True, None, "25")):
        base = fake_trainer()

        def trainer(tr, va, te, directory, _bad=bad, _base=base):
            out = _base(tr, va, te, directory)
            out.tokenizer_length = _bad
            return out

        with pytest.raises(sm.ModelUnavailable) as info:
            train.run_training(manifest=manifest, data_path=data, base_model="finbert", version=f"bad-length-{index}", output_root=tmp_path / "out", trainer=trainer,
                               allow_development_fixture=True, **TARGETS)
        assert info.value.reason == "artifact_incompatible"


# ------------------------------------------------------------------------------------------------ D8: the provenance the trainer reports reaches the artifact; the writer cannot emit what the loader refuses


def run_fake(tmp_path, *, trainer=None, version="sentiment-v1"):
    data = write_jsonl(tmp_path / "data.jsonl", make_rows(40, group_every=4))
    manifest = load_manifest(write_manifest(tmp_path / "manifest.json", manifest_dict()), allow_development_fixture=True)
    return train.run_training(manifest=manifest, data_path=data, base_model="finbert", version=version, output_root=tmp_path / "out", trainer=trainer or fake_trainer(),
                              allow_development_fixture=True, **TARGETS)


def test_the_trainer_output_requires_the_revisions_and_the_tokenizer_identifier():
    fields = {f.name: f for f in dataclasses.fields(train.TrainerOutput)}
    for name in ("base_model_revision", "tokenizer_identifier", "tokenizer_revision", "tokenizer_length", "library_versions"):
        assert name in fields and fields[name].default is dataclasses.MISSING and fields[name].default_factory is dataclasses.MISSING, name         # a trainer cannot forget one


def test_the_artifact_carries_the_full_version_1_provenance_the_trainer_reported(tmp_path):
    directory = Path(run_fake(tmp_path)["directory"])
    metadata = json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))
    assert metadata["metadata_schema_version"] == 1 and metadata["base_model_revision"] == FAKE_REVISION
    assert metadata["base_model"] == CANDIDATES["finbert"]["hub_id"]                                               # the identifier comes from the candidate register, nothing is invented
    assert metadata["tokenizer"]["identifier"] == FAKE_IDENTIFIER and metadata["tokenizer"]["revision"] == FAKE_REVISION
    assert metadata["tokenizer"]["length"] == 4990 and metadata["tokenizer"]["vocab_size"] == 5000
    assert {"torch", "transformers", "tokenizers", "safetensors"} <= set(metadata["library_versions"])
    assert metadata["labels"] == list(("positive", "negative", "neutral")) and metadata["calibration"]["status"] in ("calibrated", "uncalibrated")
    import hashlib

    independent = hashlib.sha256(json.dumps(metadata["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert metadata["manifest_sha256"] == independent == sm.manifest_sha256(metadata["files"])
    info = sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="finbert", max_tokens=128)
    assert (info.schema_version, info.base_model_revision, info.tokenizer_revision, info.manifest_sha256) == (1, FAKE_REVISION, FAKE_REVISION, independent)


@pytest.mark.parametrize("field,bad", [("base_model_revision", "main"), ("base_model_revision", FAKE_REVISION[:7]), ("base_model_revision", FAKE_REVISION.upper()), ("base_model_revision", ""),
                                       ("tokenizer_revision", "v1.0"), ("tokenizer_revision", FAKE_REVISION + "0"), ("tokenizer_revision", None), ("tokenizer_identifier", ""),
                                       ("tokenizer_identifier", None), ("tokenizer_length", 0), ("tokenizer_length", None), ("tokenizer_length", 5001)])
def test_the_writer_refuses_missing_or_malformed_provenance_and_a_tokenizer_longer_than_the_matrix(tmp_path, field, bad):
    base = fake_trainer()

    def trainer(tr, va, te, directory):
        out = base(tr, va, te, directory)
        setattr(out, field, bad)
        return out

    with pytest.raises(sm.ModelUnavailable) as info:
        run_fake(tmp_path, trainer=trainer)
    assert info.value.reason == "artifact_incompatible" and str(info.value) == "artifact_incompatible"


@pytest.mark.parametrize("missing", ["torch", "transformers", "tokenizers", "safetensors"])
def test_the_writer_refuses_a_trainer_that_does_not_report_a_required_dependency_version(tmp_path, missing):
    base = fake_trainer()

    def trainer(tr, va, te, directory):
        out = base(tr, va, te, directory)
        out.library_versions.pop(missing)
        return out

    with pytest.raises(sm.ModelUnavailable) as info:
        run_fake(tmp_path, trainer=trainer)
    assert info.value.reason == "artifact_incompatible"


def test_the_trainer_reports_what_it_loaded_and_the_dependency_versions_of_all_four_packages():
    source = inspect.getsource(train.fine_tune_with_torch)
    assert "base_model_revision=base_revision" in source and "tokenizer_revision=base_revision" in source and "tokenizer_identifier=hub_id" in source          # what was actually loaded
    assert 'base_revision = hub_id, loading["revision"]' in source and "local_model.identifier, local_model.revision" in source                       # the Hub path's validated revision, or the local manifest's
    for expected in ('"tokenizers": tokenizers.__version__', '"safetensors": safetensors.__version__', '"torch": torch.__version__', '"transformers": transformers.__version__'):
        assert expected in source, expected
    assert source.index("base_model_loading_kwargs(revision") < source.index("import safetensors")                  # still validated before any package is imported


def test_the_trainer_has_no_second_copy_of_the_revision_rule():
    text = (REPO_ROOT / "training" / "sentiment" / "train_sentiment_transformer.py").read_text(encoding="utf-8")
    assert "[0-9a-f]{40}" not in text and "is_commit_hash(revision)" in text and sm.is_commit_hash(REVISION) and not sm.is_commit_hash("main")


def test_no_migration_or_upgrade_code_exists_for_the_artifact_metadata():
    import ast

    for path in (REPO_ROOT / "backend" / "wealthpilot" / "core" / "sentiment_model.py", REPO_ROOT / "training" / "sentiment" / "artifacts.py",
                 REPO_ROOT / "training" / "sentiment" / "train_sentiment_transformer.py", REPO_ROOT / "training" / "sentiment" / "evaluate_sentiment_model.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not any(word in node.name.lower() for word in ("migrat", "upgrade", "convert_metadata", "backfill")), (path.name, node.name)


def test_artifacts_are_written_once_and_the_writer_has_no_in_place_edit_path():
    """The only function that writes `model_metadata.json` is `write_artifact`, and the loader never writes: an artifact is immutable and is replaced by retraining."""
    text = (REPO_ROOT / "backend" / "wealthpilot" / "core" / "sentiment_model.py").read_text(encoding="utf-8")
    assert "write_text" not in text and "write_bytes" not in text and ".open(\"w" not in text


# ------------------------------------------------------------------------------------------------ Path B: a verified LOCAL base-model directory (owner decision C1)
from local_model_fixtures import IDENTIFIER, REVISION as LOCAL_REVISION, make_local_dir, write_manifest_file  # noqa: E402
from training.sentiment import local_model_dir as lm  # noqa: E402


def local_cli(tmp_path, *extra, revision=None):
    directory = make_local_dir(tmp_path)
    manifest = write_manifest_file(directory, tmp_path / "local_manifest.json")
    args = CLI + ["--local-model-dir", str(directory), "--local-model-manifest", str(manifest)] + list(extra) + (["--revision", revision] if revision else [])
    return args, directory, manifest


def patched_trainer(monkeypatch, tmp_path):
    seen: dict = {}
    monkeypatch.setattr(train.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(train, "load_manifest", lambda path: object())
    monkeypatch.setattr(train, "run_training", lambda **kwargs: kwargs["trainer"]([], [], [], tmp_path) or {"ok": True})
    monkeypatch.setattr(train, "fine_tune_with_torch", lambda *a, **k: seen.update(k))
    return seen


def test_a_verified_local_directory_replaces_the_hub_and_needs_no_revision_argument(tmp_path, monkeypatch):
    seen = patched_trainer(monkeypatch, tmp_path)
    args, directory, _ = local_cli(tmp_path)
    assert train.main(args) == 0
    local = seen["local_model"]
    assert local.path == directory and local.identifier == IDENTIFIER and local.revision == LOCAL_REVISION and seen["allow_hub_download"] is False and seen["revision"] is None


def test_the_local_directory_is_refused_when_unverified_mismatched_or_combined_with_a_download(tmp_path, monkeypatch, capsys):
    patched_trainer(monkeypatch, tmp_path)
    args, directory, manifest = local_cli(tmp_path)
    assert train.main(args + ["--allow-hub-download"]) == 2 and "cannot be combined with --allow-hub-download" in capsys.readouterr().err
    assert train.main(args + ["--revision", "f" * 40]) == 2 and "invalid_revision" in capsys.readouterr().err
    assert train.main(args + ["--revision", "main"]) == 2 and "40-character" in capsys.readouterr().err
    (directory / "model.safetensors").write_bytes(b"TAMPERED")
    assert train.main(args) == 2 and "size_mismatch" in capsys.readouterr().err
    assert train.main(CLI + ["--local-model-dir", str(directory)]) == 2 and "--local-model-manifest" in capsys.readouterr().err
    second = make_local_dir(tmp_path, "second")
    other = tmp_path / "other.json"
    other.write_text(json.dumps(lm.build_manifest("Other/model", LOCAL_REVISION, second)), encoding="utf-8")
    assert train.main(CLI + ["--local-model-dir", str(second), "--local-model-manifest", str(other)]) == 2 and "invalid_identifier" in capsys.readouterr().err
    (tmp_path / "bad.json").write_text("{ not json SECRETMARKER", encoding="utf-8")
    assert train.main(CLI + ["--local-model-dir", str(second), "--local-model-manifest", str(tmp_path / "bad.json")]) == 2 and "SECRETMARKER" not in capsys.readouterr().err


def test_the_trainer_function_refuses_a_local_directory_combined_with_a_download_or_another_revision(tmp_path):
    directory = make_local_dir(tmp_path)
    verified = lm.verify_model_directory(directory, lm.build_manifest(IDENTIFIER, LOCAL_REVISION, directory))
    for kwargs in ({"allow_hub_download": True}, {"revision": "f" * 40}):
        with pytest.raises(train.RevisionError):
            train.fine_tune_with_torch([], [], [], tmp_path / "out", base_model="finbert", epochs=0, learning_rate=1e-5, batch_size=1, max_tokens=8, seed=1, **{"revision": None, **kwargs}, local_model=verified)


def test_the_local_branch_of_the_trainer_loads_offline_without_remote_code_and_never_passes_a_hub_identifier():
    source = inspect.getsource(train.fine_tune_with_torch)
    assert 'loading = {"trust_remote_code": False, "local_files_only": True}' in source and "source, hub_id, base_revision = str(local_model.path), local_model.identifier, local_model.revision" in source
    assert "AutoTokenizer.from_pretrained(source, **loading)" in source and "use_safetensors=True" in source and "local_model = local_model.recheck()" in source          # re-verified before use
    assert source.index("local_model.recheck()") < source.index("import safetensors")                                                                                # before any package is imported
