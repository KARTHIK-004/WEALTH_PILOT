"""Path B (form item C1): `training/sentiment/local_model_dir.py`, tested ONLY with synthetic local fixtures: dummy bytes in a temporary directory, fake `transformers` / `torch` modules, no network, no real model, no
tokenizer, no dataset. The module is not wired into anything yet; these tests are what a later owner approval of the code change would rest on."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from training.sentiment import evaluate_sentiment_model as ev
from training.sentiment import local_model_dir as lm

ID = "Example/finbert-stand-in"
REV = "0123456789abcdef0123456789abcdef01234567"
CONFIG = {"id2label": {"0": "positive", "1": "negative", "2": "neutral"}}


def make_dir(root: Path, name: str = "model", *, config: dict | None = None) -> Path:
    directory = root / name
    directory.mkdir()
    (directory / "model.safetensors").write_bytes(b"WEIGHTS" * 100)
    (directory / "config.json").write_text(json.dumps(CONFIG if config is None else config), encoding="utf-8")
    (directory / "vocab.txt").write_text("[PAD]\n[UNK]\nsavings\n", encoding="utf-8")
    (directory / "tokenizer_config.json").write_text('{"do_lower_case": true}', encoding="utf-8")
    (directory / "special_tokens_map.json").write_text("{}", encoding="utf-8")
    return directory


def manifest_for(directory: Path) -> dict:
    return lm.build_manifest(ID, REV, directory)


def code_of(call) -> str:
    with pytest.raises(lm.LocalModelError) as raised:
        call()
    return raised.value.code


# ------------------------------------------------------------------------------------------------------------------------------- manifest and directory verification
def test_a_directory_with_exactly_the_five_approved_files_verifies_against_its_own_manifest(tmp_path):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    assert set(manifest["files"]) == set(lm.APPROVED_FILES) == {"model.safetensors", "config.json", "vocab.txt", "tokenizer_config.json", "special_tokens_map.json"}
    verified = lm.verify_model_directory(directory, manifest, identifier=ID, revision=REV)
    assert (verified.identifier, verified.revision, verified.path) == (ID, REV, directory)


@pytest.mark.parametrize("extra,code", [("pytorch_model.bin", "forbidden_file_format"), ("tf_model.h5", "forbidden_file_format"), ("flax_model.msgpack", "forbidden_file_format"), ("training_args.bin", "forbidden_file_format"),
                                        ("remote_code.py", "forbidden_file_format"), ("MODEL.BIN", "forbidden_file_format"), ("README.md", "unexpected_file"), (".gitattributes", "unexpected_file"),
                                        ("notes.txt", "unexpected_file")])
def test_any_other_file_is_refused_and_pickle_capable_formats_get_their_own_code(tmp_path, extra, code):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    (directory / extra).write_bytes(b"x")
    assert code_of(lambda: lm.verify_model_directory(directory, manifest)) == code
    assert code_of(lambda: lm.build_manifest(ID, REV, directory)) == code


def test_a_sub_directory_a_missing_file_and_a_non_directory_are_refused(tmp_path):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    (directory / "nested").mkdir()
    assert code_of(lambda: lm.verify_model_directory(directory, manifest)) == "unexpected_file"
    (directory / "nested").rmdir()
    (directory / "vocab.txt").unlink()
    assert code_of(lambda: lm.verify_model_directory(directory, manifest)) == "missing_file"
    assert code_of(lambda: lm.verify_model_directory(tmp_path / "absent", manifest)) == "not_a_directory"
    (tmp_path / "file").write_bytes(b"x")
    assert code_of(lambda: lm.verify_model_directory(tmp_path / "file", manifest)) == "not_a_directory"


def test_a_changed_byte_is_a_hash_mismatch_and_a_changed_length_a_size_mismatch(tmp_path):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    original = (directory / "model.safetensors").read_bytes()
    (directory / "model.safetensors").write_bytes(b"X" + original[1:])
    assert code_of(lambda: lm.verify_model_directory(directory, manifest)) == "hash_mismatch"
    (directory / "model.safetensors").write_bytes(original + b"!")
    assert code_of(lambda: lm.verify_model_directory(directory, manifest)) == "size_mismatch"
    (directory / "model.safetensors").write_bytes(original)
    lm.verify_model_directory(directory, manifest)                                                  # restored: verifies again


def test_a_tampered_or_malformed_manifest_is_refused_before_the_directory_is_trusted(tmp_path):
    directory = make_dir(tmp_path)
    good = manifest_for(directory)
    swapped = {**good, "files": {**good["files"], "vocab.txt": "0" * 64}}                           # edited hash, stale manifest_sha256
    assert code_of(lambda: lm.verify_model_directory(directory, swapped)) == "invalid_manifest"
    for broken in ({**good, "schema": "other"}, {k: v for k, v in good.items() if k != "sizes"}, {**good, "extra": 1}, {**good, "files": {"model.safetensors": "0" * 64}},
                   {**good, "sizes": {**good["sizes"], "vocab.txt": -1}}, {**good, "sizes": {**good["sizes"], "vocab.txt": True}}, {**good, "manifest_sha256": "nothex"}, "not a mapping", None):
        assert code_of(lambda broken=broken: lm.verify_model_directory(directory, broken)) in ("invalid_manifest",), broken


@pytest.mark.parametrize("revision", ["main", "v1.0", "0123456", "0123456789ABCDEF0123456789ABCDEF01234567", "0123456789abcdef0123456789abcdef0123456", "0123456789abcdef0123456789abcdef012345678", "", None])
def test_a_floating_or_malformed_revision_is_refused_everywhere(tmp_path, revision):
    directory = make_dir(tmp_path)
    good = manifest_for(directory)
    assert code_of(lambda: lm.build_manifest(ID, revision, directory)) == "invalid_revision"
    assert code_of(lambda: lm.verify_model_directory(directory, {**good, "revision": revision})) == "invalid_revision"
    if revision is not None:                                                                         # None means "the caller pins nothing"; any other value must be the exact approved hash
        assert code_of(lambda: lm.verify_model_directory(directory, good, revision=revision)) == "invalid_revision"


def test_the_caller_can_pin_the_identifier_and_the_revision_it_approved(tmp_path):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    assert code_of(lambda: lm.verify_model_directory(directory, manifest, identifier="Other/model")) == "invalid_identifier"
    assert code_of(lambda: lm.verify_model_directory(directory, manifest, revision="f" * 40)) == "invalid_revision"
    for bad in ("", "no-slash", "a/b/c", "../x/y", "a/ b", "a/b?x=1"):
        assert code_of(lambda bad=bad: lm.build_manifest(bad, REV, directory)) == "invalid_identifier"


def test_a_link_is_refused(tmp_path):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    target = tmp_path / "elsewhere.bin"
    target.write_bytes(b"x")
    (directory / "vocab.txt").unlink()
    try:
        (directory / "vocab.txt").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links need a privilege this account does not have")
    assert code_of(lambda: lm.verify_model_directory(directory, manifest)) == "link_refused"


def test_errors_carry_a_fixed_code_and_never_a_path_a_hash_or_content(tmp_path):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    (directory / "model.safetensors").write_bytes(b"SECRETMARKER")
    with pytest.raises(lm.LocalModelError) as raised:
        lm.verify_model_directory(directory, manifest)
    message = str(raised.value)
    assert message == raised.value.code and message in lm.CODES
    assert str(directory) not in message and "SECRETMARKER" not in message and manifest["files"]["model.safetensors"] not in message


# ------------------------------------------------------------------------------------------------------------------------------- label order and probabilities
def test_the_label_order_comes_from_the_verified_config_and_nothing_is_assumed(tmp_path):
    verified = lm.verify_model_directory(*(lambda d: (d, manifest_for(d)))(make_dir(tmp_path)))
    assert lm.read_label_order(verified) == ("positive", "negative", "neutral")


@pytest.mark.parametrize("config", [{"id2label": {"0": "LABEL_0", "1": "LABEL_1", "2": "LABEL_2"}}, {"id2label": {"0": "positive", "1": "negative"}}, {"id2label": {"0": "positive", "1": "positive", "2": "neutral"}},
                                    {"id2label": {"0": "positive", "1": "negative", "2": "neutral", "3": "mixed"}}, {"id2label": {"0": "positive", "2": "negative", "3": "neutral"}}, {"no": "labels"}, [1]])
def test_an_unusable_label_map_is_refused(tmp_path, config):
    directory = make_dir(tmp_path, config=config)
    verified = lm.verify_model_directory(directory, manifest_for(directory))
    assert code_of(lambda: lm.read_label_order(verified)) == "invalid_label_map"


def test_a_reordered_or_capitalised_label_map_is_read_as_given(tmp_path):
    directory = make_dir(tmp_path, config={"id2label": {"0": "Neutral", "1": "POSITIVE", "2": "negative"}})
    verified = lm.verify_model_directory(directory, manifest_for(directory))
    assert lm.read_label_order(verified) == ("neutral", "positive", "negative")


def test_softmax_is_stable_normalised_monotone_and_refuses_non_finite_values():
    assert sum(lm.softmax([1000.0, 1001.0, 999.0])) == pytest.approx(1.0) and lm.softmax([1000.0, 1001.0, 999.0])[1] == max(lm.softmax([1000.0, 1001.0, 999.0]))
    assert lm.softmax([0.0, 0.0, 0.0]) == pytest.approx([1 / 3] * 3)
    assert lm.softmax([-1000.0, 0.0])[0] == pytest.approx(0.0)
    for bad in ([], [float("nan"), 1.0], [float("inf"), 0.0], [True, 1.0], ["1", 2.0]):
        assert code_of(lambda bad=bad: lm.softmax(bad)) == "inference_failed"


# ------------------------------------------------------------------------------------------------------------------------------- loading: only from the local directory, with the safe parameters
class FakeTensor:
    def __init__(self, rows):
        self.rows = rows

    def tolist(self):
        return self.rows


class FakeModel:
    calls: list = []

    def __init__(self, logits_for):
        self.logits_for, self.device, self.evaluating = logits_for, None, False

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        self.evaluating = True
        return self

    def __call__(self, **encoded):
        return type("Out", (), {"logits": FakeTensor([self.logits_for(t) for t in encoded["texts"]])})()


class FakeTransformers:
    def __init__(self, logits_for=lambda text: [2.0, 0.0, -1.0]):
        self.calls, self.model = [], FakeModel(logits_for)
        outer = self

        class AutoTokenizer:
            @staticmethod
            def from_pretrained(path, **kwargs):
                outer.calls.append(("tokenizer", path, kwargs))
                return lambda texts, **kw: {"texts": texts}

        class AutoModelForSequenceClassification:
            @staticmethod
            def from_pretrained(path, **kwargs):
                outer.calls.append(("model", path, kwargs))
                return outer.model

        self.AutoTokenizer, self.AutoModelForSequenceClassification = AutoTokenizer, AutoModelForSequenceClassification


class FakeTorch:
    @staticmethod
    def no_grad():
        class Context:
            def __enter__(self):
                return None

            def __exit__(self, *exc):
                return False

        return Context()


def verified_dir(tmp_path):
    directory = make_dir(tmp_path)
    return lm.verify_model_directory(directory, manifest_for(directory), identifier=ID, revision=REV)


def test_loading_passes_only_the_local_directory_with_the_safe_parameters_and_uses_the_cpu(tmp_path):
    verified, fake = verified_dir(tmp_path), FakeTransformers()
    classifier = lm.load_classifier(verified, transformers_module=fake, torch_module=FakeTorch)
    assert [c[0] for c in fake.calls] == ["tokenizer", "model"] and all(c[1] == str(verified.path) for c in fake.calls)
    assert ID not in repr(fake.calls) and REV not in repr(fake.calls)                                  # never a Hub identifier or revision
    assert fake.calls[0][2] == {"local_files_only": True, "trust_remote_code": False}
    assert fake.calls[1][2] == {"local_files_only": True, "trust_remote_code": False, "use_safetensors": True}
    assert fake.model.device == "cpu" and fake.model.evaluating is True and classifier.verified.revision == REV


def test_the_directory_is_verified_again_immediately_before_the_load_and_nothing_is_loaded_if_it_changed(tmp_path):
    verified, fake = verified_dir(tmp_path), FakeTransformers()
    (verified.path / "model.safetensors").write_bytes(b"CHANGED AFTER THE CHECK")
    assert code_of(lambda: lm.load_classifier(verified, transformers_module=fake, torch_module=FakeTorch)) in ("size_mismatch", "hash_mismatch")
    assert fake.calls == []
    (verified.path / "pytorch_model.bin").write_bytes(b"x")
    assert code_of(lambda: lm.load_classifier(verified, transformers_module=fake, torch_module=FakeTorch)) == "forbidden_file_format" and fake.calls == []


def test_a_library_failure_during_loading_is_a_fixed_code_without_the_library_message(tmp_path):
    verified = verified_dir(tmp_path)

    class Broken(FakeTransformers):
        def __init__(self):
            super().__init__()

            class AutoTokenizer:
                @staticmethod
                def from_pretrained(path, **kwargs):
                    raise OSError("SECRETMARKER " + path)

            self.AutoTokenizer = AutoTokenizer

    with pytest.raises(lm.LocalModelError) as raised:
        lm.load_classifier(verified, transformers_module=Broken(), torch_module=FakeTorch)
    assert raised.value.code == "load_failed" and "SECRETMARKER" not in str(raised.value) and str(verified.path) not in str(raised.value)


# ------------------------------------------------------------------------------------------------------------------------------- probability-bearing predictions in the owner-approved E2 format
def loaded(tmp_path, logits_for=lambda text: [2.0, 0.0, -1.0]):
    return lm.load_classifier(verified_dir(tmp_path), transformers_module=FakeTransformers(logits_for), torch_module=FakeTorch)


def test_the_payload_is_the_e2_format_and_the_evaluation_script_accepts_it(tmp_path):
    table = {"great": [3.0, 0.0, 0.0], "awful": [0.0, 3.0, 0.0], "so so": [0.0, 0.0, 3.0]}
    classifier = loaded(tmp_path, lambda text: table[text])
    payload = lm.predictions_payload({"a": "great", "b": "awful", "c": "so so"}, classifier, batch_size=2)
    assert [payload[i]["label"] for i in "abc"] == ["positive", "negative", "neutral"]
    for entry in payload.values():
        assert set(entry) == {"label", "probabilities"} and set(entry["probabilities"]) == set(lm.LABELS) and sum(entry["probabilities"].values()) == pytest.approx(1.0)
    path = tmp_path / "predictions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    labels, probabilities = ev.load_predictions(path)                                                  # the real E2 loader: classes, range, sum and argmax are all checked there
    assert labels == {"a": "positive", "b": "negative", "c": "neutral"} and probabilities is not None and set(probabilities) == {"a", "b", "c"}


def test_the_label_is_always_the_most_probable_class_and_a_tie_is_broken_by_the_fixed_label_order(tmp_path):
    classifier = loaded(tmp_path, lambda text: [1.0, 1.0, 1.0])
    entry = lm.predictions_payload({"a": "anything"}, classifier)["a"]
    assert entry["label"] == "positive" and max(entry["probabilities"].values()) == pytest.approx(1 / 3)
    other = tmp_path / "second"
    other.mkdir()
    second = loaded(other)                                                                           # logits [2, 0, -1]
    reordered = lm.LocalClassifier(second.verified, second._tokenizer, second._model, second._torch, ("neutral", "positive", "negative"))
    entry = lm.predictions_payload({"a": "x"}, reordered)["a"]
    assert entry["probabilities"]["neutral"] == pytest.approx(lm.softmax([2.0, 0.0, -1.0])[0]) and entry["label"] == "neutral"       # the class order of the model is honoured


def test_batches_cover_every_item_exactly_once_in_order(tmp_path):
    seen = []
    classifier = loaded(tmp_path, lambda text: seen.append(text) or [0.0, 0.0, 1.0])
    items = {f"id{i}": f"text {i}" for i in range(7)}
    payload = lm.predictions_payload(items, classifier, batch_size=3)
    assert seen == list(items.values()) and list(payload) == list(items)


@pytest.mark.parametrize("texts", [[], [""], ["   "], [1], "a string", None, ["ok", None]])
def test_invalid_input_texts_are_refused_without_echo(tmp_path, texts):
    classifier = loaded(tmp_path)
    assert code_of(lambda: classifier.predict(texts)) == "invalid_input"


@pytest.mark.parametrize("items,batch", [({}, 4), (None, 4), ({"a": "x"}, 0), ({"a": "x"}, True), ({"a": "x"}, "4")])
def test_invalid_payload_requests_are_refused(tmp_path, items, batch):
    classifier = loaded(tmp_path)
    assert code_of(lambda: lm.predictions_payload(items, classifier, batch_size=batch)) == "invalid_input"


def test_a_model_that_returns_the_wrong_shape_or_non_finite_logits_is_a_fixed_code_without_the_text(tmp_path):
    for index, logits in enumerate(([1.0, 2.0], [float("nan"), 0.0, 1.0], [1.0, 2.0, 3.0, 4.0])):
        folder = tmp_path / f"case{index}"
        folder.mkdir()
        classifier = loaded(folder, lambda text, logits=logits: logits)
        with pytest.raises(lm.LocalModelError) as raised:
            classifier.predict(["SECRETMARKER text"])
        assert raised.value.code == "inference_failed" and "SECRETMARKER" not in str(raised.value)


# ------------------------------------------------------------------------------------------------------------------------------- the module stays inside its boundary
def test_the_module_is_standard_library_only_at_import_time_and_cannot_reach_a_network_a_hub_pickle_or_the_environment():
    source = Path(lm.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_imports = {a.name.split(".")[0] for n in tree.body if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
    assert top_imports <= {"__future__", "hashlib", "importlib", "json", "math", "os", "re", "dataclasses", "pathlib", "typing", "wealthpilot"}, top_imports
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {"socket", "urllib", "requests", "httpx", "huggingface_hub", "snapshot_download", "hf_hub_download", "pickle", "environ", "getenv", "load_file", "print", "trust_remote_code_true"} & names
    for forbidden in ("torch.load", "pickle.load", "trust_remote_code=True", "local_files_only=False", "use_safetensors=False", "os.environ", "huggingface.co", "https://", "http://"):
        assert forbidden not in source.replace("`trust_remote_code=False`", ""), forbidden


def test_only_the_trainer_and_the_evaluation_script_import_the_module_never_the_backend_a_route_a_setting_or_a_script():
    """Path B wiring (owner approval 2026-10-29): the offline trainer and the offline evaluation script use it; nothing in the backend, the API, the settings or `scripts/` may."""
    root = Path(__file__).resolve().parents[3]
    importers = {path.name for path in [*(root / "backend" / "wealthpilot").rglob("*.py"), *(root / "training").rglob("*.py"), *(root / "scripts").rglob("*.py")]
                 if path.name != "local_model_dir.py" and "local_model_dir" in path.read_text(encoding="utf-8", errors="ignore")}
    assert importers == {"train_sentiment_transformer.py", "evaluate_sentiment_model.py"}, importers


def test_a_link_is_refused_even_where_this_account_cannot_create_one(tmp_path, monkeypatch):
    directory = make_dir(tmp_path)
    manifest = manifest_for(directory)
    real_scandir = lm.os.scandir

    class LinkEntry:
        def __init__(self, entry):
            self.name, self._entry = entry.name, entry

        def is_symlink(self):
            return self.name == "vocab.txt"

        def is_file(self, follow_symlinks=True):
            return self._entry.is_file(follow_symlinks=follow_symlinks)

    class Listing:
        def __enter__(self):
            self._inner = real_scandir(directory)
            return [LinkEntry(e) for e in self._inner.__enter__()]

        def __exit__(self, *exc):
            return self._inner.__exit__(*exc)

    monkeypatch.setattr(lm.os, "scandir", lambda path: Listing())
    assert code_of(lambda: lm.verify_model_directory(directory, manifest)) == "link_refused"
