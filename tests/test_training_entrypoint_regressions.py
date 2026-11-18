"""Hermetic synthetic regression tests, not model capability measurements.

Execute only selected AST definitions/blocks: importing the entrypoint modules
would import CUDA dependencies and, for cloud master, create output directories.
No real tokenizer, model, adapter, dataset, download, or training is used.
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from pickle import UnpicklingError
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import Mock, call

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVOLUTION_PATHS = (
    ROOT / "scripts" / "train_virtu_evolution.py",
    ROOT / "cloud_train_pack" / "train_virtu_evolution.py",
)
MASTER_PATH = ROOT / "cloud_train_pack" / "train_cloud_master.py"


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _assigns(node, name):
    return isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == name for target in node.targets
    )


def _evolution_nodes(path):
    names = {"FallbackBPETokenizer", "load_safe_tokenizer", "main", "run_dpo_training"}
    nodes = [
        node for node in _parse(path).body
        if getattr(node, "name", None) in names or _assigns(node, "_FALLBACK_SPLIT_RE")
    ]
    assert len(nodes) == 5, "Test isolation must include every required definition"
    return nodes


def _forbidden(*args, **kwargs):
    raise AssertionError("Synthetic regression test must not access models, data pipelines, or training")


@pytest.fixture(autouse=True)
def _block_real_ml_imports(monkeypatch):
    for name in ("torch", "transformers", "peft", "datasets", "trl", "safetensors", "bitsandbytes"):
        monkeypatch.setitem(sys.modules, name, None)


@pytest.fixture(params=EVOLUTION_PATHS, ids=("scripts", "cloud-pack"))
def evolution(request, tmp_path):
    namespace = {
        "__name__": "synthetic_training_entrypoint_test",
        "__file__": str(request.param),
        "argparse": argparse,
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "re": re,
        "os": SimpleNamespace(path=os.path, environ={}, makedirs=_forbidden),
        "sys": sys,
        "random": SimpleNamespace(seed=Mock()),
        "ROOT": str(tmp_path),
        "EVO_DATA_PATH": str(tmp_path / "synthetic_test_sft.jsonl"),
        "EVO_DPO_PATH": str(tmp_path / "synthetic_test_pairs.jsonl"),
        "DEFAULT_SIX_DATA_DIR": str(tmp_path / "synthetic_test_six"),
        "HAVE_HF": False,
        "HAVE_TORCH": False,
        "torch": None,
        "_log": Mock(),
        "_pre_argv": Mock(),
        "auto_install_deps": _forbidden,
        "auto_download_base_model": _forbidden,
        "_load_heavy_imports": _forbidden,
        "preflight_gpu_check": _forbidden,
        "_discover_base_model": _forbidden,
        "_discover_work_dir": _forbidden,
        "build_evolution_corpus": _forbidden,
        "build_dpo_dataset": _forbidden,
        "run_post_train_pipeline": _forbidden,
        "make_training_bundle": _forbidden,
        "find_six_software_dir": Mock(return_value=None),
        "probe_template": Mock(),
        "run_selftest": Mock(return_value=0),
        "resolve_data_paths": lambda data, dpo: (data, dpo),
        "load_evolution_dataset": Mock(return_value=[
            {"input_ids": [256, 151645], "labels": [-100, 151645]}
        ]),
    }
    tree = ast.Module(body=_evolution_nodes(request.param), type_ignores=[])
    exec(compile(tree, str(request.param), "exec"), namespace)
    return namespace, request.param


def _stub_transformers(monkeypatch, loader):
    stub = ModuleType("transformers")
    stub.AutoTokenizer = SimpleNamespace(from_pretrained=loader)
    monkeypatch.setitem(sys.modules, "transformers", stub)


def _synthetic_tokenizer(vocab_size=151936, pad_token=None):
    return SimpleNamespace(vocab_size=vocab_size, pad_token=pad_token, eos_token="<test_eos>")


def _alternate_path(namespace):
    path = Path(namespace["ROOT"]) / "checkpoints" / "_base_qwen3_8b"
    path.mkdir(parents=True)
    (path / "tokenizer_config.json").write_text(
        '{"fixture": "synthetic regression test, no model assets"}', encoding="utf-8"
    )
    return str(path)


@pytest.mark.parametrize("have_hf", [False, True])
@pytest.mark.parametrize("pad_token", [None, "<test_existing_pad>"])
def test_real_tokenizer_selection_uses_lazy_import(evolution, monkeypatch, have_hf, pad_token, capsys):
    namespace, _ = evolution
    namespace["HAVE_HF"] = have_hf
    tokenizer = _synthetic_tokenizer(pad_token=pad_token)
    loader = Mock(return_value=tokenizer)
    _stub_transformers(monkeypatch, loader)
    assert "AutoTokenizer" not in namespace

    assert namespace["load_safe_tokenizer"]("synthetic-test-base") is tokenizer
    assert tokenizer.pad_token == (pad_token or tokenizer.eos_token)
    loader.assert_called_once_with("synthetic-test-base", trust_remote_code=True)
    assert "FallbackBPETokenizer" not in capsys.readouterr().out


def test_missing_dependency_refuses_training_but_allows_explicit_diagnostic(evolution, capsys):
    namespace, _ = evolution
    load = namespace["load_safe_tokenizer"]
    with pytest.raises(RuntimeError, match="refusing SFT/DPO training") as exc:
        load("synthetic-test-missing-base")
    assert "transformers import failed" in str(exc.value)
    assert "synthetic-test-missing-base" in str(exc.value)
    assert "allow_fallback=True" in str(exc.value)
    assert capsys.readouterr().out == ""

    tokenizer = load("synthetic-test-missing-base", allow_fallback=True)
    assert isinstance(tokenizer, namespace["FallbackBPETokenizer"])
    log = capsys.readouterr().out
    assert "Diagnostic-only" in log and "not Qwen BPE" in log and "synthetic" in log


def _bad_tokenizer_result(kind):
    if kind == "load-error":
        return OSError("synthetic test tokenizer load failure")
    if kind == "missing-vocab":
        return SimpleNamespace(pad_token=None, eos_token="<test_eos>")
    return _synthetic_tokenizer(vocab_size={"sparse": 1, "boundary": 1000, "null-vocab": None}[kind])


@pytest.mark.parametrize("primary", ["load-error", "sparse", "boundary", "missing-vocab", "null-vocab"])
@pytest.mark.parametrize("alternate", ["absent", "sparse", "load-error"])
def test_invalid_primary_and_alternate_fail_closed(evolution, monkeypatch, primary, alternate):
    namespace, _ = evolution
    results = [_bad_tokenizer_result(primary)]
    expected_calls = [call("synthetic-test-base", trust_remote_code=True)]
    if alternate != "absent":
        alt = _alternate_path(namespace)
        results.append(_bad_tokenizer_result(alternate))
        expected_calls.append(call(alt, trust_remote_code=True))
    loader = Mock(side_effect=results)
    _stub_transformers(monkeypatch, loader)

    with pytest.raises(RuntimeError, match="refusing SFT/DPO training") as exc:
        namespace["load_safe_tokenizer"]("synthetic-test-base")
    assert "synthetic-test-base" in str(exc.value)
    assert loader.call_args_list == expected_calls
    if alternate != "absent":
        assert alt in str(exc.value)

    loader.reset_mock(side_effect=True)
    loader.side_effect = results
    tokenizer = namespace["load_safe_tokenizer"]("synthetic-test-base", allow_fallback=True)
    assert isinstance(tokenizer, namespace["FallbackBPETokenizer"])
    assert loader.call_args_list == expected_calls


@pytest.mark.parametrize("primary", ["load-error", "sparse"])
def test_valid_alternate_is_selected_even_with_diagnostic_opt_in(evolution, monkeypatch, primary):
    namespace, _ = evolution
    alt = _alternate_path(namespace)
    tokenizer = _synthetic_tokenizer()
    loader = Mock(side_effect=[_bad_tokenizer_result(primary), tokenizer])
    _stub_transformers(monkeypatch, loader)

    assert namespace["load_safe_tokenizer"]("synthetic-test-base", allow_fallback=True) is tokenizer
    assert loader.call_args_list == [
        call("synthetic-test-base", trust_remote_code=True), call(alt, trust_remote_code=True)
    ]
    assert tokenizer.pad_token == tokenizer.eos_token


def test_fallback_tokens_are_stable_across_pythonhashseed(evolution, tmp_path):
    _, path = evolution
    nodes = [node for node in _evolution_nodes(path) if not isinstance(node, ast.FunctionDef)]
    source = ast.unparse(ast.Module(body=nodes, type_ignores=[]))
    text = "<|im_start|>SYNTHETIC_TEST 中文制造 12.50 42 x+y=z!<|im_end|>"
    program = (
        "import json, re\nfrom typing import Dict, List\n" + source
        + f"\nprint(json.dumps(FallbackBPETokenizer().encode({text!r})))\n"
    )
    outputs = []
    for seed in ("1", "777", "123456"):
        result = subprocess.run(
            [sys.executable, "-S", "-B", "-c", program],
            cwd=str(tmp_path),
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"},
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=20,
        )
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1] == outputs[2]
    assert len(outputs[0]) > 8
    assert outputs[0][0] == 151644 and outputs[0][-1] == 151645
    assert all(256 <= token < 140256 for token in outputs[0][1:-1])


def _main_argv(namespace, path, monkeypatch, mode, flags):
    monkeypatch.setattr(sys, "argv", [
        str(path), "--base", str(Path(namespace["ROOT"]) / "synthetic_test_base"),
        "--out", str(Path(namespace["ROOT"]) / "synthetic_test_output"),
        "--mode", mode, *flags,
    ])


@pytest.mark.parametrize("mode,flags", [
    ("qlora", ()), ("lora", ()), ("dpo", ()),
    ("qlora", ("--smoke", "1")), ("lora", ("--smoke", "1")), ("dpo", ("--smoke", "1")),
    ("dpo", ("--probe-only",)), ("dpo", ("--validate-only",)),
    ("dpo", ("--probe-only", "--validate-only")),
])
def test_main_refuses_missing_tokenizer_on_every_training_route(evolution, monkeypatch, mode, flags):
    namespace, path = evolution
    namespace["run_dpo_training"] = Mock(side_effect=_forbidden)
    _main_argv(namespace, path, monkeypatch, mode, flags)
    with pytest.raises(RuntimeError, match="refusing SFT/DPO training"):
        namespace["main"]()
    namespace["run_dpo_training"].assert_not_called()
    namespace["load_evolution_dataset"].assert_not_called()
    namespace["run_selftest"].assert_not_called()
    namespace["probe_template"].assert_not_called()


@pytest.mark.parametrize("mode,flags,route", [
    ("qlora", ("--selftest",), "selftest"),
    ("lora", ("--selftest",), "selftest"),
    ("dpo", ("--selftest",), "selftest"),
    ("qlora", ("--probe-only",), "probe"),
    ("lora", ("--probe-only",), "probe"),
    ("qlora", ("--validate-only",), "validate"),
    ("lora", ("--validate-only",), "validate"),
    ("qlora", ("--probe-only", "--validate-only"), "probe"),
    ("dpo", ("--selftest", "--probe-only", "--validate-only"), "selftest"),
])
def test_main_allows_fallback_only_on_exiting_diagnostic_routes(evolution, monkeypatch, mode, flags, route):
    namespace, path = evolution
    Path(namespace["EVO_DATA_PATH"]).write_text(
        '{"fixture": "synthetic test SFT data; loader is stubbed"}\n', encoding="utf-8"
    )
    namespace["run_dpo_training"] = Mock(side_effect=_forbidden)
    _main_argv(namespace, path, monkeypatch, mode, flags)
    if route == "selftest":
        with pytest.raises(SystemExit) as exc:
            namespace["main"]()
        assert exc.value.code == 0
        tokenizer = namespace["run_selftest"].call_args.args[1]
    else:
        assert namespace["main"]() is None
        if route == "probe":
            tokenizer = namespace["probe_template"].call_args.args[0]
        else:
            tokenizer = namespace["load_evolution_dataset"].call_args.kwargs["tokenizer"]
    assert isinstance(tokenizer, namespace["FallbackBPETokenizer"])
    namespace["run_dpo_training"].assert_not_called()
    assert not (Path(namespace["ROOT"]) / "synthetic_test_output").exists()


def test_direct_dpo_entry_rejects_injected_fallback_before_data_access(evolution):
    namespace, _ = evolution
    with pytest.raises(RuntimeError, match="cannot be used for DPO training"):
        namespace["run_dpo_training"](SimpleNamespace(), namespace["FallbackBPETokenizer"]())


@pytest.mark.parametrize("mode", ["qlora", "lora"])
def test_sft_entry_rejects_injected_fallback(evolution, monkeypatch, mode):
    namespace, path = evolution
    Path(namespace["EVO_DATA_PATH"]).write_text(
        '{"fixture": "synthetic test SFT data; loader is stubbed"}\n', encoding="utf-8"
    )
    namespace["load_safe_tokenizer"] = Mock(return_value=namespace["FallbackBPETokenizer"]())
    _main_argv(namespace, path, monkeypatch, mode, ())
    with pytest.raises(RuntimeError, match="cannot be used for SFT training"):
        namespace["main"]()
    assert not (Path(namespace["ROOT"]) / "synthetic_test_output").exists()


@pytest.fixture
def adapter_block(tmp_path):
    function = next(node for node in _parse(MASTER_PATH).body
                    if isinstance(node, ast.FunctionDef) and node.name == "train_dpo_stage")
    start = next(i for i, node in enumerate(function.body) if _assigns(node, "safetensor_path"))
    stop = next(i for i, node in enumerate(function.body) if _assigns(node, "pairs"))
    assert start < stop
    block = compile(ast.Module(body=function.body[start:stop], type_ignores=[]), str(MASTER_PATH), "exec")
    state = {"synthetic_test_weight": object()}
    existing_files = set()
    namespace = {
        "os": SimpleNamespace(path=SimpleNamespace(
            join=os.path.join, exists=lambda path: Path(path).name in existing_files,
        )),
        "sft_adapter_path": str(tmp_path / "synthetic_test_adapter"),
        "model": object(),
        "torch": SimpleNamespace(load=Mock(return_value=state)),
        "load_file": Mock(return_value=state),
        "set_peft_model_state_dict": Mock(),
    }
    return block, namespace, existing_files, state


@pytest.mark.parametrize("files", [
    ("adapter_model.bin",),
    ("adapter_model.safetensors",),
    ("adapter_model.safetensors", "adapter_model.bin"),
])
def test_adapter_weights_load_safely_and_prefer_safetensors(adapter_block, files):
    block, namespace, existing_files, state = adapter_block
    existing_files.update(files)
    exec(block, namespace)
    if "adapter_model.safetensors" in files:
        namespace["load_file"].assert_called_once_with(namespace["safetensor_path"])
        namespace["torch"].load.assert_not_called()
    else:
        namespace["torch"].load.assert_called_once_with(
            namespace["bin_path"], map_location="cpu", weights_only=True
        )
        namespace["load_file"].assert_not_called()
    namespace["set_peft_model_state_dict"].assert_called_once_with(namespace["model"], state)


def test_missing_adapter_weights_refuses_dpo(adapter_block):
    block, namespace, _, _ = adapter_block
    with pytest.raises(FileNotFoundError, match="refusing DPO training") as exc:
        exec(block, namespace)
    assert "adapter_model.safetensors" in str(exc.value) and "adapter_model.bin" in str(exc.value)
    assert namespace["sft_adapter_path"] in str(exc.value)
    namespace["torch"].load.assert_not_called()
    namespace["load_file"].assert_not_called()
    namespace["set_peft_model_state_dict"].assert_not_called()


@pytest.mark.parametrize("error", [
    TypeError("synthetic test: weights_only unsupported"),
    UnpicklingError("synthetic test: unsafe payload refused"),
])
def test_bin_load_failure_never_retries_unsafe_pickle(adapter_block, error):
    block, namespace, existing_files, _ = adapter_block
    existing_files.add("adapter_model.bin")
    namespace["torch"].load.side_effect = error
    with pytest.raises(type(error), match="synthetic test"):
        exec(block, namespace)
    namespace["torch"].load.assert_called_once_with(namespace["bin_path"], map_location="cpu", weights_only=True)
    namespace["set_peft_model_state_dict"].assert_not_called()


def test_failed_safetensors_does_not_silently_use_bin(adapter_block):
    block, namespace, existing_files, _ = adapter_block
    existing_files.update(("adapter_model.safetensors", "adapter_model.bin"))
    namespace["load_file"].side_effect = ValueError("synthetic test: corrupt safetensors")
    with pytest.raises(ValueError, match="synthetic test"):
        exec(block, namespace)
    namespace["torch"].load.assert_not_called()
    namespace["set_peft_model_state_dict"].assert_not_called()


def test_evolution_copies_remain_synchronized():
    assert EVOLUTION_PATHS[0].read_bytes() == EVOLUTION_PATHS[1].read_bytes()
