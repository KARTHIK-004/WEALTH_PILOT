"""Path B (owner decision C1) against the REAL libraries, with a LOCAL RANDOMLY INITIALISED stand-in only: a tiny `BertForSequenceClassification` saved with `save_pretrained` (safetensors), a hand-written legacy
tokenizer, a synthetic revision. Skipped where torch / transformers / tokenizers / safetensors are not installed (the project environment); it runs in the disposable S1 environment. Every test runs under
the same guards as `test_transformer_standin.py`: zero socket attempts, zero Hub-level calls, zero `torch.load`, zero pickle calls, and the Hugging Face cache directories unchanged. No real model, Hub id,
dataset or user text exists here."""

from __future__ import annotations

import json
import pickle
import socket
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
pytest.importorskip("tokenizers")
pytest.importorskip("safetensors")

import huggingface_hub  # noqa: E402
import transformers.modeling_utils  # noqa: E402,F401
import transformers.utils.hub  # noqa: E402,F401
from frozen_fixtures import build  # noqa: E402
from standin_helpers import FIXED_IDS, LABELS, REVISION, VOCAB, listing, weight_like_files, write_legacy_tokenizer  # noqa: E402
from transformers import BertConfig, BertForSequenceClassification  # noqa: E402

from training.sentiment import evaluate_sentiment_model as ev  # noqa: E402
from training.sentiment import local_model_dir as lm  # noqa: E402
from training.sentiment import train_sentiment_transformer as train  # noqa: E402
from training.sentiment.config import CANDIDATES  # noqa: E402
from training.sentiment.dataset import LabelledRow  # noqa: E402

IDENTIFIER = CANDIDATES["finbert"]["hub_id"]                          # a string only: it is never resolved
HUB_FUNCTIONS = ("hf_hub_download", "snapshot_download", "try_to_load_from_cache")


class Safety:
    def __init__(self) -> None:
        self.network, self.hub, self.torch_load, self.pickle = [], [], [], []


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
        s.torch_load.append("torch.load")
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
        getattr(huggingface_hub, function)
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


def build_standin(tmp_path: Path, name: str = "standin"):
    """A local directory with EXACTLY the five approved file names, produced by the real library from a random tiny model (never a download)."""
    torch.manual_seed(42)
    directory = tmp_path / name
    config = BertConfig(vocab_size=len(VOCAB), hidden_size=16, num_hidden_layers=1, num_attention_heads=2, intermediate_size=32, max_position_embeddings=64, type_vocab_size=2,
                        num_labels=3, id2label=dict(enumerate(LABELS)), label2id={label: i for i, label in enumerate(LABELS)})
    model = BertForSequenceClassification(config)
    model.save_pretrained(directory)
    write_legacy_tokenizer(directory)
    extras = [n for n in listing(directory) if n not in lm.APPROVED_FILES]
    assert set(extras) <= {"generation_config.json"}, extras                                  # the only file the library may add besides the approved five
    for extra in extras:
        (directory / extra).unlink()
    assert listing(directory) == sorted(lm.APPROVED_FILES) and weight_like_files(directory) == []
    return directory, model


def verified_for(directory: Path):
    return lm.verify_model_directory(directory, lm.build_manifest(IDENTIFIER, REVISION, directory), identifier=IDENTIFIER, revision=REVISION)


def synthetic(texts):
    return [LabelledRow(text=t, label=LABELS[i % 3], intensity=None, group=f"g{i}") for i, t in enumerate(texts)]


def test_the_real_libraries_load_the_verified_directory_and_produce_valid_probabilities(tmp_path):
    directory, model = build_standin(tmp_path)
    classifier = lm.load_classifier(verified_for(directory))
    probabilities = classifier.predict(["alpha beta gamma", "delta epsilon zeta"])
    assert len(probabilities) == 2 and all(set(p) == set(LABELS) and abs(sum(p.values()) - 1.0) < 1e-6 and all(0.0 <= v <= 1.0 for v in p.values()) for p in probabilities)
    assert classifier.predict(["alpha beta gamma", "delta epsilon zeta"]) == probabilities                  # deterministic on the CPU
    model.eval()
    with torch.no_grad():
        reference = torch.softmax(model(input_ids=torch.tensor(FIXED_IDS)).logits, dim=-1)[0].tolist()
    assert [probabilities[0][label] for label in LABELS] == pytest.approx(reference, abs=1e-5)             # the safetensors round trip and the class order are exact
    assert str(next(classifier._model.parameters()).device) == "cpu" and classifier._model.training is False


def test_the_model_payload_passes_the_evaluation_scripts_own_prediction_gate(tmp_path):
    directory, _ = build_standin(tmp_path)
    classifier = lm.load_classifier(verified_for(directory))
    payload = lm.predictions_payload({"a": "alpha beta", "b": "gamma delta", "c": "unknownword"}, classifier, batch_size=2)
    labels, probabilities = ev.parse_predictions(json.loads(json.dumps(payload)))
    assert set(labels) == {"a", "b", "c"} and probabilities is not None and all(labels[i] == max(probabilities[i], key=probabilities[i].get) for i in labels)


def test_a_tampered_or_extended_directory_is_refused_before_the_library_is_asked_to_load(tmp_path, monkeypatch):
    directory, _ = build_standin(tmp_path)
    verified = verified_for(directory)
    calls: list = []
    monkeypatch.setattr(transformers.AutoModelForSequenceClassification, "from_pretrained", classmethod(lambda cls, *a, **k: calls.append(a) or pytest.fail("the library was asked to load")))
    data = (directory / "model.safetensors").read_bytes()
    (directory / "model.safetensors").write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises(lm.LocalModelError) as raised:
        lm.load_classifier(verified)
    assert raised.value.code == "hash_mismatch" and calls == []
    (directory / "model.safetensors").write_bytes(data)
    (directory / "pytorch_model.bin").write_bytes(b"NOT-A-CHECKPOINT-PLACEHOLDER")
    with pytest.raises(lm.LocalModelError) as raised:
        lm.load_classifier(verified)
    assert raised.value.code == "forbidden_file_format" and calls == []


def test_the_trainer_accepts_the_verified_directory_and_records_the_manifest_revision_as_its_provenance(tmp_path):
    directory, _ = build_standin(tmp_path)
    output = train.fine_tune_with_torch(synthetic(["alpha beta", "gamma delta"]), synthetic(["alpha gamma", "beta delta"]), synthetic(["epsilon zeta", "eta theta"]), tmp_path / "trained",
                                        base_model="finbert", epochs=0, learning_rate=2e-5, batch_size=2, max_tokens=16, seed=42, revision=None, local_model=verified_for(directory))
    assert output.base_model_revision == REVISION == output.tokenizer_revision and output.tokenizer_identifier == IDENTIFIER
    assert output.tokenizer_length == len(VOCAB) and "model.safetensors" in listing(tmp_path / "trained") and weight_like_files(tmp_path / "trained") == []


def test_the_evaluation_script_runs_the_real_local_model_end_to_end_without_validating_it(tmp_path):
    directory, _ = build_standin(tmp_path)
    manifest = tmp_path / "local_manifest.json"
    manifest.write_text(json.dumps(lm.build_manifest(IDENTIFIER, REVISION, directory)), encoding="utf-8")
    built = build(tmp_path / "set", train=270, calibration=90, heldout=300)
    out = tmp_path / "report.json"
    code = ev.main(["--frozen-manifest", str(built.manifest_path), "--records", str(built.records_path), "--rubric", str(built.rubric_path), "--annotator-manifest", str(built.annotators_path),
                    "--adjudication-log", str(built.log_path), "--participant-register", str(built.register_path), "--output", str(out), "--local-model", f"standin={directory}", "--local-model-manifest", f"standin={manifest}"])
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assessment = report["candidates"]["standin"]["assessment"]
    assert report["local_models"]["standin"]["revision"] == REVISION and assessment["validation"]["status"] != "validated"                    # a random stand-in is never validated
    assert assessment["activation_recommendation"].startswith("none") and "calibration: not_evaluable" not in assessment["validation"]["unmet_or_missing"]
    text = out.read_text(encoding="utf-8")
    assert all(record["text"] not in text and record["id"] not in text for record in built.records[:50])
