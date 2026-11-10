"""ADR-052 -- the real `fine_tune_with_torch`, `write_artifact`, `verify_artifact` and `TransformersBackend` against LOCAL, randomly initialised stand-in models and HAND-WRITTEN tokenizer fixtures.

These tests need `torch`, `transformers`, `tokenizers` and `safetensors`, which the project environment does not have (they are outside the approved stack): they are SKIPPED there, and were run
in a disposable environment with the hash-pinned S1 set (docs: reports/sentiment_model_approval_record.md). They use no pretrained weights, no real Hub id, no dataset and no user text: the only
inputs are fixed token ids and synthetic words from a 25-token local vocabulary, and the revision is a SYNTHETIC hash that names nothing. The trainer is called with `epochs=0`: no optimiser step.

Every test runs under an autouse guard that REFUSES and records: any socket operation, any hub-level call (`hf_hub_download`, `snapshot_download`, `try_to_load_from_cache`), `torch.load` and
(records) `pickle.load(s)`; it also checks that the Hugging Face cache directories are unchanged. A test that fails the guard fails even if its own assertions pass."""

from __future__ import annotations

import json
import pickle
import shutil
import socket
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
pytest.importorskip("tokenizers")
pytest.importorskip("safetensors")

import huggingface_hub  # noqa: E402
import safetensors  # noqa: E402
import tokenizers  # noqa: E402
import transformers.modeling_utils  # noqa: E402,F401
import transformers.utils.hub  # noqa: E402,F401
from standin_helpers import FIXED_IDS, LABELS, PLACEHOLDER, REVISION, VOCAB, WORDS_IDS, listing, safetensors_header, weight_like_files, write_legacy_tokenizer  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer, BertConfig, BertForMaskedLM, BertForSequenceClassification  # noqa: E402

from training.sentiment import train_sentiment_transformer as train  # noqa: E402
from training.sentiment.artifacts import write_artifact  # noqa: E402
from training.sentiment.dataset import LabelledRow  # noqa: E402
from wealthpilot.core import sentiment_model as sm  # noqa: E402

HUB_FUNCTIONS = ("hf_hub_download", "snapshot_download", "try_to_load_from_cache")


class Safety:
    def __init__(self) -> None:
        self.network: list = []
        self.hub: list = []
        self.torch_load: list = []
        self.pickle: list = []

    def clear(self) -> None:
        for items in (self.network, self.hub, self.torch_load, self.pickle):
            items.clear()


def _snapshot(path: Path):
    return None if not path.exists() else sorted(str(p.relative_to(path)) for p in path.rglob("*"))


@pytest.fixture(autouse=True)
def safety(monkeypatch):
    s = Safety()

    def refuse(name):
        def blocked(*a, **k):
            s.network.append(name)
            raise ConnectionError("network blocked by the test guard")
        return blocked

    for method in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, method, refuse(f"socket.{method}"))
    for function in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        monkeypatch.setattr(socket, function, refuse(f"socket.{function}"))

    def torch_load(*a, **k):
        s.torch_load.append(repr(a)[:60])
        raise AssertionError("torch.load was called: a pickle path was reached")

    monkeypatch.setattr(torch, "load", torch_load)
    real_load, real_loads = pickle.load, pickle.loads
    monkeypatch.setattr(pickle, "load", lambda *a, **k: (s.pickle.append("pickle.load"), real_load(*a, **k))[1])
    monkeypatch.setattr(pickle, "loads", lambda *a, **k: (s.pickle.append("pickle.loads"), real_loads(*a, **k))[1])

    def recorder(name):
        def record(*a, **k):
            s.hub.append(name)
            raise RuntimeError(f"hub-level call intercepted: {name}")
        return record

    for function in HUB_FUNCTIONS:
        getattr(huggingface_hub, function)                                     # resolve lazy attributes first
    for module in list(sys.modules.values()):
        if (getattr(module, "__name__", "") or "").startswith(("huggingface_hub", "transformers")):
            for function in HUB_FUNCTIONS:
                if function in getattr(module, "__dict__", {}):
                    monkeypatch.setattr(module, function, recorder(function))
    roots = [Path(huggingface_hub.constants.HF_HOME), Path.home() / ".cache" / "huggingface"]
    before = [_snapshot(p) for p in roots]
    yield s
    assert s.network == [], f"network attempts: {s.network}"
    assert s.hub == [], f"hub-level calls: {s.hub}"
    assert s.torch_load == [], "torch.load was called"
    assert s.pickle == [], f"pickle calls: {s.pickle}"
    assert [_snapshot(p) for p in roots] == before, "the Hugging Face cache directories changed"


# ------------------------------------------------------------------------------------------------ builders (all local; nothing downloaded)


def synthetic(texts):
    return [LabelledRow(text=t, label=LABELS[i % 3], intensity=None, group=f"g{i}") for i, t in enumerate(texts)]


def base_model_dir(tmp_path: Path, *, embedding_vocab: int | None = None) -> Path:
    """A local 'base model': a tiny randomly initialised masked LM plus a hand-written legacy-layout tokenizer. `embedding_vocab` pads the embedding matrix beyond the tokenizer."""
    torch.manual_seed(42)
    base = tmp_path / "base"
    BertForMaskedLM(BertConfig(vocab_size=embedding_vocab or len(VOCAB), hidden_size=16, num_hidden_layers=1, num_attention_heads=2, intermediate_size=32, max_position_embeddings=64,
                               type_vocab_size=2)).save_pretrained(base)
    write_legacy_tokenizer(base)
    return base


def run_seam(tmp_path, monkeypatch, base: Path, *, revision=REVISION, allow_hub_download=False, name="trained"):
    """The REAL trainer, `epochs=0` (no optimiser step), pointed at a local directory instead of a Hub id (in memory only)."""
    monkeypatch.setitem(train.CANDIDATES, "finbert", dict(train.CANDIDATES["finbert"], hub_id=str(base)))
    directory = tmp_path / name
    output = train.fine_tune_with_torch(synthetic(["alpha beta", "gamma delta"]), synthetic(["alpha gamma", "beta delta"]), synthetic(["epsilon zeta", "eta theta"]), directory, base_model="finbert",
                                        epochs=0, learning_rate=2e-5, batch_size=2, max_tokens=16, seed=42, revision=revision, allow_hub_download=allow_hub_download)
    return directory, output


def write_standin_artifact(directory: Path, output, *, tokenizer_length: int | None = None):
    return write_artifact(directory, model_name="standin-random-tiny", model_version="standin-0", base_model="local-random-init", base_model_revision=output.base_model_revision,
                          base_model_license="none: randomly initialised local stand-in", dataset_id="none", dataset_license="", labels=LABELS, vocab_size=output.vocab_size,
                          tokenizer_length=output.tokenizer_length if tokenizer_length is None else tokenizer_length, tokenizer_identifier=output.tokenizer_identifier,
                          tokenizer_revision=output.tokenizer_revision, temperature=None, min_confidence=None, band_cutoffs=None, validation_status="unvalidated", validation_reasons=["stand-in test"], metrics={"note": "stand-in"},
                          extra_files=output.tokenizer_files, test_samples=0, held_out_test=False, duplicate_leakage_checked=False, training_library_versions=output.library_versions, max_tokens=16)


def reason(call):
    with pytest.raises(sm.ModelUnavailable) as info:
        call()
    return info.value.reason


def backend(directory: Path, length: int):
    return sm.TransformersBackend(directory.resolve(), max_tokens=16, device="cpu", labels=LABELS, tokenizer_length=length)


# ------------------------------------------------------------------------------------------------ safetensors-only output; the length is recorded


def test_the_real_trainer_writes_a_safetensors_only_artifact_and_records_the_real_tokenizer_length(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    files = listing(directory)
    assert "model.safetensors" in files and "config.json" in files and "tokenizer_config.json" in files
    assert weight_like_files(directory) == [], files                                                   # no .bin / .pt / .pth / .pt2 / pickle of any kind
    assert safetensors_header(directory / "model.safetensors").get("__metadata__") == {"format": "pt"}
    assert output.tokenizer_length == len(VOCAB) == 25 and output.vocab_size == 25
    info = write_standin_artifact(directory, output)
    assert info.tokenizer_length == 25
    metadata = json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))
    assert metadata["tokenizer"]["length"] == 25 and "model.safetensors" in metadata["files"] and weight_like_files(directory) == []
    assert metadata["metadata_schema_version"] == 1 and metadata["base_model_revision"] == REVISION                                    # what the trainer actually loaded, not a default
    assert metadata["tokenizer"]["revision"] == REVISION and metadata["tokenizer"]["identifier"] == output.tokenizer_identifier != ""
    assert {name: metadata["library_versions"][name] for name in sm.REQUIRED_DEPENDENCIES} == {"torch": torch.__version__, "transformers": transformers.__version__,
                                                                                               "tokenizers": tokenizers.__version__, "safetensors": safetensors.__version__}
    assert metadata["manifest_sha256"] == sm.manifest_sha256(metadata["files"]) == info.manifest_sha256


def test_the_tokenizer_written_by_the_seam_reloads_with_the_same_vocabulary(tmp_path, monkeypatch):
    directory, _ = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False)
    assert len(tokenizer) == 25 and tokenizer("alpha beta unknownword gamma", truncation=True, max_length=8)["input_ids"] == WORDS_IDS


# ------------------------------------------------------------------------------------------------ tokenizer length: match, mismatch, padded embedding


def test_a_matching_tokenizer_length_loads_and_one_cpu_forward_pass_gives_finite_logits(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    info = write_standin_artifact(directory, output)
    loaded = backend(directory, info.tokenizer_length)
    result = loaded.predict("alpha beta gamma")
    assert len(result.logits) == 3 and all(abs(x) < 1e3 for x in result.logits) and result.logits == loaded.predict("alpha beta gamma").logits
    with torch.inference_mode():
        logits = loaded._model(input_ids=torch.tensor(FIXED_IDS), attention_mask=torch.ones(1, 5, dtype=torch.long)).logits
    assert tuple(logits.shape) == (1, 3) and bool(torch.isfinite(logits).all())


@pytest.mark.parametrize("recorded", [24, 26, 5, 1])
def test_a_recorded_length_that_differs_from_the_loaded_tokenizer_rejects_the_artifact(tmp_path, monkeypatch, recorded):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    assert reason(lambda: backend(directory, recorded)) == "artifact_incompatible"


def test_a_tokenizer_that_lost_its_vocabulary_is_rejected_even_though_every_other_check_passes(tmp_path, monkeypatch):
    """The 5.x trap: a 4.x-style construction silently gives a 5-token tokenizer. The metadata recorded 25 when the artifact was written; the loader must notice."""
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    poor = write_legacy_tokenizer(tmp_path / "poor")
    (poor / "vocab.txt").write_text("\n".join(VOCAB[:5]) + "\n", encoding="utf-8")                      # the five special tokens only
    AutoTokenizer.from_pretrained(str(poor), local_files_only=True, trust_remote_code=False).save_pretrained(directory)
    assert len(AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False)) == 5
    info = write_standin_artifact(directory, output)                                                      # regenerates the hashes; the recorded length stays the original 25
    assert info.tokenizer_length == 25 and sm.verify_artifact(directory.resolve(), expected_version="standin-0", expected_name="standin-random-tiny", max_tokens=16)
    assert reason(lambda: backend(directory, info.tokenizer_length)) == "artifact_incompatible"


def test_a_padded_embedding_matrix_remains_valid(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path, embedding_vocab=32))
    assert (output.vocab_size, output.tokenizer_length) == (32, 25)
    info = write_standin_artifact(directory, output)
    assert json.loads((directory / "config.json").read_text(encoding="utf-8"))["vocab_size"] == 32 and info.tokenizer_length == 25
    loaded = backend(directory, info.tokenizer_length)                                                    # accepted although the two numbers differ
    assert len(loaded.predict("alpha beta gamma").logits) == 3


def test_the_stand_in_is_refused_as_a_primary_model_because_it_is_unvalidated(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    config = sm.SentimentModelConfig(enabled=True, name="standin-random-tiny", path=directory.name, version="standin-0", max_tokens=16, device="cpu")
    assert reason(lambda: sm.load_model(config, root=directory.parent)) == "not_validated"
    sm.clear_cache()


# ------------------------------------------------------------------------------------------------ pickle, .bin, .pt and .pt2 are refused


@pytest.mark.parametrize("name", ["pytorch_model.bin", "model.pt", "model.pth", "model.pt2", "pytorch_model.pt2"])
def test_a_directory_with_only_a_pickle_or_exported_program_is_refused_by_the_backend_and_the_library(tmp_path, monkeypatch, name):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    only = tmp_path / "only-pickle"
    shutil.copytree(directory, only)
    (only / "model.safetensors").unlink()
    (only / name).write_bytes(PLACEHOLDER)                                                                # placeholder bytes: not a serialized pickle
    assert reason(lambda: backend(only, output.tokenizer_length)) == "load_failed"
    with pytest.raises(OSError):
        AutoModelForSequenceClassification.from_pretrained(str(only), local_files_only=True, trust_remote_code=False, use_safetensors=True)


@pytest.mark.parametrize("name", ["pytorch_model.bin", "model.pt", "model.pth", "model.pt2"])
def test_an_artifact_whose_metadata_lists_a_pickle_instead_of_safetensors_is_refused_by_the_verifier(tmp_path, monkeypatch, name):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    path = directory / "model_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["files"][name] = metadata["files"].pop("model.safetensors")
    path.write_text(json.dumps(metadata), encoding="utf-8")
    assert reason(lambda: sm.verify_artifact(directory.resolve(), expected_version="standin-0", expected_name="standin-random-tiny", max_tokens=16)) == "artifact_incompatible"


def test_safetensors_is_chosen_and_a_placeholder_pickle_beside_it_is_never_read(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    both = tmp_path / "both"
    shutil.copytree(directory, both)
    (both / "pytorch_model.bin").write_bytes(PLACEHOLDER)
    assert len(backend(both, output.tokenizer_length).predict("alpha beta").logits) == 3                  # the autouse guard fails the test if torch.load was reached


# ------------------------------------------------------------------------------------------------ the loading keywords, and trust_remote_code=False in effect


def spy_on_loaders(monkeypatch):
    calls = {"tokenizer": [], "model": []}
    original_tokenizer, original_model = AutoTokenizer.from_pretrained, AutoModelForSequenceClassification.from_pretrained
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", staticmethod(lambda *a, **k: (calls["tokenizer"].append(dict(k)), original_tokenizer(*a, **k))[1]))
    monkeypatch.setattr(AutoModelForSequenceClassification, "from_pretrained", staticmethod(lambda *a, **k: (calls["model"].append(dict(k)), original_model(*a, **k))[1]))
    return calls


def test_the_runtime_backend_loads_offline_without_remote_code_and_with_safetensors_only(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    calls = spy_on_loaders(monkeypatch)
    backend(directory, output.tokenizer_length)
    assert calls["tokenizer"] == [{"local_files_only": True, "trust_remote_code": False}]
    assert calls["model"] == [{"local_files_only": True, "trust_remote_code": False, "use_safetensors": True}]


def test_the_trainer_loads_the_base_model_pinned_offline_without_remote_code_and_with_safetensors_only(tmp_path, monkeypatch):
    base = base_model_dir(tmp_path)
    calls = spy_on_loaders(monkeypatch)
    run_seam(tmp_path, monkeypatch, base)
    assert calls["tokenizer"] == [{"revision": REVISION, "trust_remote_code": False, "local_files_only": True}]
    (model_call,) = calls["model"]
    assert model_call["revision"] == REVISION and model_call["trust_remote_code"] is False and model_call["local_files_only"] is True and model_call["use_safetensors"] is True
    assert model_call["num_labels"] == 3 and model_call["ignore_mismatched_sizes"] is True


def test_only_the_explicit_switch_lets_the_trainer_leave_offline_mode_and_remote_code_stays_refused(tmp_path, monkeypatch):
    base = base_model_dir(tmp_path)
    calls = spy_on_loaders(monkeypatch)
    run_seam(tmp_path, monkeypatch, base, allow_hub_download=True)                # a LOCAL directory is used, so nothing can reach the network: the guard would fail the test
    assert calls["tokenizer"][0]["local_files_only"] is False and calls["model"][0]["local_files_only"] is False
    assert calls["tokenizer"][0]["trust_remote_code"] is False and calls["model"][0]["trust_remote_code"] is False and calls["model"][0]["use_safetensors"] is True


@pytest.mark.parametrize("bad", ["main", "", "v1", REVISION[:8], REVISION.upper()])
def test_an_invalid_revision_is_refused_before_the_base_model_is_touched(tmp_path, monkeypatch, bad):
    base = base_model_dir(tmp_path)
    calls = spy_on_loaders(monkeypatch)
    with pytest.raises(train.RevisionError):
        run_seam(tmp_path, monkeypatch, base, revision=bad)
    assert calls == {"tokenizer": [], "model": []} and not (tmp_path / "trained").exists()


def test_trust_remote_code_false_never_executes_custom_model_or_tokenizer_code(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    custom = tmp_path / "custom"
    shutil.copytree(directory, custom)
    model_marker, tokenizer_marker = tmp_path / "MARKER_model.txt", tmp_path / "MARKER_tokenizer.txt"
    config = json.loads((custom / "config.json").read_text(encoding="utf-8"))
    config["auto_map"] = {"AutoModelForSequenceClassification": "modeling_custom.CustomModel"}
    (custom / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (custom / "modeling_custom.py").write_text(f"from pathlib import Path\nPath(r'{model_marker}').write_text('executed')\nraise RuntimeError('executed')\n", encoding="utf-8")
    tokenizer_config = json.loads((custom / "tokenizer_config.json").read_text(encoding="utf-8"))
    tokenizer_config["auto_map"] = {"AutoTokenizer": ["tokenization_custom.CustomTokenizer", None]}
    (custom / "tokenizer_config.json").write_text(json.dumps(tokenizer_config), encoding="utf-8")
    (custom / "tokenization_custom.py").write_text(f"from pathlib import Path\nPath(r'{tokenizer_marker}').write_text('executed')\n", encoding="utf-8")
    try:
        backend(custom, output.tokenizer_length)                                                          # the native classes are used; auto_map is ignored
    except sm.ModelUnavailable:
        pass                                                                                              # refusing is also acceptable; executing is not
    assert not model_marker.exists() and not tokenizer_marker.exists()


def test_a_config_naming_a_hub_repository_in_a_private_key_triggers_no_network_or_hub_call(tmp_path, monkeypatch):
    """The CVE-2026-4372 mechanism, defanged: `_attn_implementation_internal` pointing at a (synthetic) repository. The autouse guard fails the test on any network or hub-level attempt."""
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path))
    write_standin_artifact(directory, output)
    crafted = tmp_path / "crafted"
    shutil.copytree(directory, crafted)
    config = json.loads((crafted / "config.json").read_text(encoding="utf-8"))
    config["_attn_implementation_internal"] = "synthetic-org/synthetic-kernel"
    (crafted / "config.json").write_text(json.dumps(config), encoding="utf-8")
    model = AutoModelForSequenceClassification.from_pretrained(str(crafted), local_files_only=True, trust_remote_code=False, use_safetensors=True)
    assert "synthetic-org" not in str(getattr(model.config, "_attn_implementation", ""))


# ------------------------------------------------------------------------------------------------ the guard itself, and background Hub conversion


def test_the_safety_guard_really_refuses_and_records_each_kind_of_access(safety):
    with pytest.raises(ConnectionError):
        socket.create_connection(("synthetic-host.invalid", 80))
    with pytest.raises(RuntimeError):
        huggingface_hub.hf_hub_download("synthetic-org/synthetic-model", "model.safetensors")
    with pytest.raises(AssertionError):
        torch.load("synthetic.pt")
    pickle.loads(pickle.dumps({"a": 1}))
    assert safety.network and safety.hub == ["hf_hub_download"] and safety.torch_load and safety.pickle == ["pickle.loads"]
    safety.clear()                                                                                        # the controls are done: the autouse check now expects silence


def test_hub_conversion_is_not_requested_for_a_pinned_revision_with_use_safetensors(monkeypatch):
    """Installed-version behaviour (transformers 5.12.1, read from its source; NOT a documented guarantee): with `use_safetensors=True` the library asks the Hub to convert a pickle checkpoint only
    when the revision is `main`. A pinned commit hash therefore never starts a conversion. The hub is simulated: `cached_file` reports the safetensors file as missing, nothing is contacted."""
    modeling = sys.modules["transformers.modeling_utils"]
    if not all(hasattr(modeling, name) for name in ("auto_conversion", "cached_file", "is_offline_mode")):
        pytest.skip("this transformers version has no such internals; the check documents 5.12.1 only")
    monkeypatch.delenv("DISABLE_SAFETENSORS_CONVERSION", raising=False)
    monkeypatch.setattr(modeling, "is_offline_mode", lambda: False)
    monkeypatch.setattr(modeling, "cached_file", lambda *a, **k: None)
    conversions: list = []
    monkeypatch.setattr(modeling, "auto_conversion", lambda *a, **k: (conversions.append(k.get("revision")), (None, k.get("revision"), False))[1])
    config = BertConfig(vocab_size=25, hidden_size=16, num_hidden_layers=1, num_attention_heads=2, intermediate_size=32, max_position_embeddings=64, num_labels=3)
    with pytest.raises(OSError):
        BertForSequenceClassification.from_pretrained("synthetic-org/synthetic-model", config=config, revision=REVISION, use_safetensors=True, local_files_only=False)
    assert conversions == []
    with pytest.raises(OSError):                                                                          # control: the same call on the moving branch would have asked for a conversion
        BertForSequenceClassification.from_pretrained("synthetic-org/synthetic-model", config=config, revision="main", use_safetensors=True, local_files_only=False)
    assert conversions == ["main"]


# ------------------------------------------------------------------------------------------------ D9 with a real tokenizer and a real (random) embedding matrix


def test_a_tokenizer_longer_than_the_embedding_matrix_is_refused_by_the_writer_and_by_the_backend(tmp_path, monkeypatch):
    """A base model whose embedding matrix (20 rows) is smaller than the tokenizer (25 tokens). The synthetic rows only use ids below 20, so the trainer itself runs; the artifact is then refused."""
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path, embedding_vocab=20))
    assert (output.vocab_size, output.tokenizer_length) == (20, 25)
    with pytest.raises(sm.ModelUnavailable) as refused:
        write_standin_artifact(directory, output)                                                         # the writer ends with the loader's own verification
    assert refused.value.reason == "artifact_incompatible"
    assert reason(lambda: backend(directory, output.tokenizer_length)) == "artifact_incompatible"          # the backend refuses it too, in the constructor, before any text is seen


def test_a_tokenizer_equal_to_the_embedding_matrix_is_accepted_with_a_real_model(tmp_path, monkeypatch):
    directory, output = run_seam(tmp_path, monkeypatch, base_model_dir(tmp_path, embedding_vocab=25))
    assert (output.vocab_size, output.tokenizer_length) == (25, 25)
    info = write_standin_artifact(directory, output)
    assert len(backend(directory, info.tokenizer_length).predict("alpha beta").logits) == 3
