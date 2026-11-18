#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for the serving-default memory fixes.

Covers: served-layer attribution across both manifest layouts (+ the .params media
type), and the router's runtime-derived MoE offload split that replaced the
crash-prone static num_gpu=22.
"""
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from virtu_eval import arms, mem_budget as mb


def _store(tmp_path, layout):
    if layout == "v2":
        man_dir = tmp_path / "manifests-v2" / "ollama.com" / "library" / "m"
    else:
        man_dir = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "m"
    man_dir.mkdir(parents=True)
    (tmp_path / "blobs").mkdir(exist_ok=True)
    layers = [
        {"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:aaa", "size": 100},
        {"mediaType": "application/vnd.ollama.image.params", "digest": "sha256:bbb", "size": 50},
        {"mediaType": "application/vnd.ollama.image.system", "digest": "sha256:ccc", "size": 10},
    ]
    (man_dir / "latest").write_text(
        json.dumps({"layers": layers, "config": {"digest": "sha256:cfg"}}), encoding="utf-8")


@pytest.mark.parametrize("layout", ["v2", "legacy"])
def test_read_layers_resolves_both_layouts_and_params(tmp_path, monkeypatch, layout):
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path))
    _store(tmp_path, layout)
    sl = arms.OllamaNativeArm("m:latest").served_layers
    assert "error" not in sl, sl
    assert sl["model"] == "sha256:aaa"
    # The params layer media type ends in .params, not .parameters; the old loop
    # never matched it, so attribution silently dropped the sampling/placement layer.
    assert sl["parameters"] == "sha256:bbb"
    assert sl["parameters_bytes"] == 50
    assert sl["manifest_digest"] == "sha256:cfg"


def test_read_layers_missing_tag_is_an_error_not_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path))
    (tmp_path / "blobs").mkdir()
    sl = arms.OllamaNativeArm("absent:latest").served_layers
    assert "error" in sl


def _load_router():
    spec = importlib.util.spec_from_file_location(
        "router_under_test", os.path.join(ROOT, "scripts", "router", "virtu_router.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _healthy():
    return {"basis": "measured", "ram_free_gb": 3.0, "commit_limit_gb": 32.0,
            "committed_gb": 21.0, "commit_avail_gb": 11.0, "llama_ws_gb": 0.0,
            "llama_priv_gb": 0.0, "gpu_total_mib": 6141, "gpu_used_mib": 1061,
            "gpu_free_mib": 5080}


def test_router_hard_opts_no_longer_pin_num_gpu():
    r = _load_router()
    assert "num_gpu" not in r.GEN_OPTS_HARD


def test_router_derives_safe_ceiling_on_healthy_box(monkeypatch):
    monkeypatch.setattr(mb, "sample", _healthy)
    r = _load_router()
    try:
        mb.facts_for_tag(r.HARD_MODEL)
    except mb.BudgetError as exc:
        # HARD_MODEL is a mutable tag (§8.2); without its real facts the exact
        # ceiling cannot be derived. The conservative fallback is locked
        # separately by test_router_falls_back_to_conservative_ceiling below.
        pytest.skip("hard-model facts unavailable: %s" % exc)
    assert r._hard_num_gpu(4096) == 21
    assert r._hard_num_gpu(8192) == 20
    assert r._hard_num_gpu(1536) == 22


def test_router_falls_back_to_conservative_ceiling(monkeypatch):
    """When model facts cannot be read, derive a safe ceiling, never the crash-prone 22."""
    monkeypatch.setattr(mb, "sample", _healthy)

    def _no_facts(tag):
        raise mb.BudgetError("tag %r absent (synthetic)" % tag)

    monkeypatch.setattr(mb, "facts_for_tag", _no_facts)
    r = _load_router()
    assert r._hard_num_gpu(4096) == 20
    assert r._hard_num_gpu(8192) == 20


def test_router_falls_back_to_cpu_when_no_vram_headroom(monkeypatch):
    tight = dict(_healthy(), gpu_free_mib=274, gpu_used_mib=5867)
    monkeypatch.setattr(mb, "sample", lambda: tight)
    r = _load_router()
    # The old static 22 would have crashed the server here; 0 = CPU-only, safe.
    assert r._hard_num_gpu(4096) == 0


def test_router_derivation_never_returns_the_crash_prone_22_at_ctx4096(monkeypatch):
    monkeypatch.setattr(mb, "sample", _healthy)
    r = _load_router()
    assert r._hard_num_gpu(4096) != 22
