#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Falsification tests for the memory-budget gate.

Every test here plants a *bad* input and asserts the gate goes red. A gate that
only ever says "ok" would pass a happy-path test and fail these.
"""
import json
import os
import struct
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from virtu_eval import mem_budget as mb


def facts(layers=36, kv_heads=8, key_len=128, val_len=128, layer_bytes=None,
          file_bytes=None, non_layer=None, ctx_len=40960):
    per = layer_bytes if layer_bytes is not None else [220_600_000] * layers
    return {
        "basis": "measured", "path": "<synthetic>", "arch": "qwen3moe",
        "file_bytes": file_bytes if file_bytes is not None else sum(per),
        "block_count": layers, "head_count_kv": kv_heads,
        "key_length": key_len, "value_length": val_len, "context_length": ctx_len,
        "expert_count": 2, "expert_used_count": 1,
        "per_layer_bytes": per, "non_layer_bytes": non_layer or {},
        "kv_elems_per_token": layers * kv_heads * (key_len + val_len),
    }


def env(commit=10.0, gpu_free=5000, ram=3.0):
    return {"basis": "measured", "ram_free_gb": ram, "commit_limit_gb": 32.0,
            "committed_gb": 32.0 - commit, "commit_avail_gb": commit,
            "llama_ws_gb": 0.0, "llama_priv_gb": 0.0,
            "gpu_total_mib": 6141, "gpu_used_mib": 6141 - gpu_free, "gpu_free_mib": gpu_free}


# --- context sizing: the 8x over-allocation this module exists to remove -------

def test_ctx_sized_from_demand_not_magic_8192():
    # Measured on the board7 leg: max prompt+completion was 960 tokens.
    # 960 * 1.25 = 1200 -> next 512-step = 1536, not a power-of-two 2048.
    assert mb.recommend_ctx(960) == 1536
    assert mb.recommend_ctx(960) < 8192
    assert mb.recommend_ctx(960) % 512 == 0


def test_ctx_rejects_nonpositive_demand():
    for bad in (0, -1, None, "960"):
        with pytest.raises(mb.BudgetError):
            mb.recommend_ctx(bad)


def test_ctx_respects_model_ceiling():
    assert mb.recommend_ctx(100000, facts=facts(ctx_len=4096)) == 4096
    assert mb.recommend_ctx(100000, ceiling=2048) == 2048


# --- KV math -----------------------------------------------------------------

def test_kv_matches_gguf_geometry():
    f = facts()
    # (key_len + val_len) already covers K and V -- a stray factor of 2 here
    # over-estimates the KV cache by 2x and would refuse legs that actually fit.
    assert f["kv_elems_per_token"] == 36 * 8 * (128 + 128) == 73728
    assert mb.kv_bytes(f, 4096, "f16") == 73728 * 4096 * 2
    assert mb.kv_bytes(f, 8192, "q8_0") == 2 * mb.kv_bytes(f, 4096, "q8_0")


def test_q8_0_kv_is_strictly_smaller_than_f16():
    f = facts()
    assert mb.kv_bytes(f, 4096, "q8_0") < mb.kv_bytes(f, 4096, "f16")


def test_kv_rejects_unknown_type_and_bad_ctx():
    with pytest.raises(mb.BudgetError):
        mb.kv_bytes(facts(), 4096, "q9_9")
    for bad in (0, -5, 4096.5):
        with pytest.raises(mb.BudgetError):
            mb.kv_bytes(facts(), bad)


# --- projection: which bytes land where --------------------------------------

def test_mmap_saving_is_not_assumed_by_the_gate():
    # Measured dense leg: mmap cut private bytes only ~7% (5.41 -> 5.10 GB) while
    # the working set ROSE 0.75 -> 4.39 GB. An unverified saving must not loosen
    # the gate, so the default keeps the weights counted on the host.
    f = facts(file_bytes=8_320_000_000)
    no_mmap = mb.project(f, 4096, 30, mmap=False)
    with_mmap = mb.project(f, 4096, 30, mmap=True)
    assert with_mmap["host_commit_bytes"] >= no_mmap["host_commit_bytes"] * 0.99
    assert with_mmap["vram_bytes"] == no_mmap["vram_bytes"]
    assert mb.MMAP_HOST_WEIGHT_FRACTION >= 0.9


def test_offload_takes_the_last_layers_not_the_first():
    # Non-uniform sizes make a start-vs-end slicing bug visible.
    per = [100] * 34 + [900, 900]
    f = facts(layers=36, layer_bytes=per, file_bytes=sum(per))
    p = mb.project(f, 512, num_gpu=2)
    assert p["gpu_layer_bytes"] == 1800      # the two 900-byte tail layers
    p0 = mb.project(f, 512, num_gpu=0)
    assert p0["gpu_layer_bytes"] == 0


def test_num_gpu_clamped_and_full_offload_adds_output():
    f = facts(layers=4, layer_bytes=[10] * 4, file_bytes=40,
              non_layer={"output.weight": 7})
    assert mb.project(f, 512, num_gpu=99)["num_gpu_effective"] == 5
    assert mb.project(f, 512, num_gpu=99)["gpu_layer_bytes"] == 40 + 7
    assert mb.project(f, 512, num_gpu=-3)["num_gpu_effective"] == 0


# --- the gate itself: planted bad environments must go red --------------------

def test_gate_refuses_when_commit_is_exhausted():
    p = mb.project(facts(file_bytes=8_320_000_000), 8192, 22)
    v = mb.check(p, env=env(commit=1.0, gpu_free=5000, ram=3.0))
    assert v["ok"] is False
    assert any("commit" in r for r in v["reasons"])


def test_gate_refuses_when_vram_is_exhausted():
    p = mb.project(facts(), 4096, 36)
    v = mb.check(p, env=env(commit=20.0, gpu_free=100, ram=3.0))
    assert v["ok"] is False
    assert any("vram" in r for r in v["reasons"])


def test_gate_refuses_below_ram_floor():
    p = mb.project(facts(layers=4, layer_bytes=[1] * 4, file_bytes=4), 512, 0)
    v = mb.check(p, env=env(commit=20.0, gpu_free=5000, ram=0.2))
    assert v["ok"] is False
    assert any("ram" in r for r in v["reasons"])


def test_gate_passes_a_genuinely_healthy_box():
    p = mb.project(facts(layers=4, layer_bytes=[1_000_000] * 4, file_bytes=4_000_000), 512, 4)
    assert mb.check(p, env=env(commit=20.0, gpu_free=5000, ram=4.0))["ok"] is True


def test_require_raises_instead_of_returning_falsy():
    with pytest.raises(mb.BudgetError):
        mb.require(facts(file_bytes=8_320_000_000), 8192, 22, env=env(commit=0.5))


# --- derived offload ceiling: the crash that hardcoded num_gpu caused ---------

def test_pinned_30_layers_does_not_fit_measured_free_vram():
    # Real over-fit observed 2026-11-07: 6174 model + 246 KV + 159 compute = 6580
    # MiB needed against 5080 MiB free; pinning n_gpu_layers disabled auto-fit and
    # the server died. The gate must refuse this exact configuration.
    f = facts(file_bytes=8_320_185_248)
    e = env(commit=10.0, gpu_free=5080, ram=3.0)
    p30 = mb.project(f, 4096, num_gpu=30)
    assert p30["vram_mib"] > e["gpu_free_mib"]
    assert mb.check(p30, env=e)["ok"] is False


def test_derived_offload_ceiling_fits_and_is_maximal():
    f = facts(file_bytes=8_320_185_248)
    e = env(commit=10.0, gpu_free=5080, ram=3.0)
    n = mb.max_offload_layers(f, 4096, env=e)
    assert 0 < n < 30
    assert mb.project(f, 4096, n)["vram_mib"] <= e["gpu_free_mib"] - mb.VRAM_RESERVE_MIB
    # one more layer must not fit, otherwise the ceiling is not maximal
    assert mb.project(f, 4096, n + 1)["vram_mib"] > e["gpu_free_mib"] - mb.VRAM_RESERVE_MIB


def test_derived_ceiling_shrinks_when_desktop_eats_vram():
    f = facts(file_bytes=8_320_185_248)
    roomy = mb.max_offload_layers(f, 4096, env=env(gpu_free=5080))
    tight = mb.max_offload_layers(f, 4096, env=env(gpu_free=2500))
    assert tight < roomy


def test_derived_ceiling_refuses_when_no_headroom():
    with pytest.raises(mb.BudgetError):
        mb.max_offload_layers(facts(), 4096, env=env(gpu_free=100))


def test_smaller_ctx_buys_more_offload_layers():
    f = facts(file_bytes=8_320_185_248)
    e = env(gpu_free=5080)
    assert mb.max_offload_layers(f, 1024, env=e) >= mb.max_offload_layers(f, 8192, env=e)


# --- fail-closed sampling: unreadable counters must not read as "room" --------

def test_sample_raises_on_empty_powershell(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(mb.subprocess, "run", fake_run)
    with pytest.raises(mb.BudgetError):
        mb.sample()


def test_sample_raises_on_zero_total_vram(monkeypatch):
    calls = {"n": 0}

    def fake_run(cmd, **kw):
        calls["n"] += 1
        out = "3.0|32.0|20.0|0.0|0.0" if calls["n"] == 1 else "0,0"
        return subprocess.CompletedProcess(cmd, 0, out, "")
    monkeypatch.setattr(mb.subprocess, "run", fake_run)
    with pytest.raises(mb.BudgetError):
        mb.sample()


def test_sample_raises_on_garbage_fields(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "not|a|number|here|either", "")
    monkeypatch.setattr(mb.subprocess, "run", fake_run)
    with pytest.raises(mb.BudgetError):
        mb.sample()


# --- demand extraction: an empty match set is red, not zero -------------------

def test_demand_reads_existing_records(tmp_path):
    p = tmp_path / "raw.jsonl"
    rows = [{"gen": {"prompt_tokens": 200, "completion_tokens": 100}},
            {"gen": {"prompt_tokens": 400, "completion_tokens": 560}},
            {"gen": {"prompt_tokens": 187, "completion_tokens": 50}}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    d = mb.demand_from_records([str(p)])
    assert d["n"] == 3 and d["max"] == 960 and d["basis"] == "measured"


def test_demand_refuses_empty_match_set(tmp_path):
    p = tmp_path / "raw.jsonl"
    p.write_text('{"case_id":"x"}\n\n', encoding="utf-8")
    with pytest.raises(mb.BudgetError):
        mb.demand_from_records([str(p)])


def test_demand_refuses_missing_file(tmp_path):
    with pytest.raises(mb.BudgetError):
        mb.demand_from_records([str(tmp_path / "nope.jsonl")])


# --- GGUF parser: desync / mismatch must raise, not return junk ---------------

def _write_gguf(path, layers=2, kv_heads=8, key_len=128, val_len=128, break_stream=False,
                header_layers=None):
    def s(b):
        return struct.pack("<Q", len(b)) + b

    kvs = [("general.architecture", 8, b"qwen3moe"),
           ("qwen3moe.block_count", 4, layers if header_layers is None else header_layers),
           ("qwen3moe.attention.head_count_kv", 4, kv_heads),
           ("qwen3moe.attention.key_length", 4, key_len),
           ("qwen3moe.attention.value_length", 4, val_len),
           ("qwen3moe.context_length", 4, 4096)]
    head = b"GGUF" + struct.pack("<I", 3)
    tensors = [("token_embd.weight", 0), ("output.weight", 64)]
    for i in range(layers):
        tensors.append(("blk.%d.attn_q.weight" % i, 128 + i * 256))
    body = b"".join(s(k.encode()) + struct.pack("<I", t) +
                    (s(v) if t == 8 else struct.pack("<I", v)) for k, t, v in kvs)
    if break_stream:
        body += b"\xff" * 8          # bogus next key length -> must raise
    tinfo = b"".join(s(n.encode()) + struct.pack("<I", 1) + struct.pack("<Q", 64) +
                     struct.pack("<I", 0) + struct.pack("<Q", off) for n, off in tensors)
    with open(path, "wb") as fh:
        fh.write(head + struct.pack("<QQ", len(tensors), len(kvs)) + body + tinfo + b"\x00" * 512)


def test_gguf_facts_reads_layer_geometry(tmp_path):
    p = tmp_path / "m.gguf"
    _write_gguf(str(p), layers=2)
    f = mb.gguf_facts(str(p))
    assert f["block_count"] == 2 and f["head_count_kv"] == 8
    assert f["kv_elems_per_token"] == 2 * 8 * (128 + 128)
    assert len(f["per_layer_bytes"]) == 2
    assert f["per_layer_bytes"][0] == 256


def test_gguf_facts_refuses_desynced_stream(tmp_path):
    p = tmp_path / "bad.gguf"
    _write_gguf(str(p), break_stream=True)
    with pytest.raises(mb.BudgetError):
        mb.gguf_facts(str(p))


def test_gguf_facts_refuses_layer_count_mismatch(tmp_path):
    p = tmp_path / "mismatch.gguf"
    # Header claims 3 blocks but only 2 blk.* tensors are present.
    _write_gguf(str(p), layers=2, header_layers=3)
    with pytest.raises(mb.BudgetError):
        mb.gguf_facts(str(p))


def test_gguf_facts_refuses_missing_and_non_gguf(tmp_path):
    with pytest.raises(mb.BudgetError):
        mb.gguf_facts(str(tmp_path / "absent.gguf"))
    p = tmp_path / "plain.bin"
    p.write_bytes(b"not a gguf at all")
    with pytest.raises(mb.BudgetError):
        mb.gguf_facts(str(p))


# --- tier-1 headroom gate (works without local blob access) -------------------

def test_headroom_refuses_exhausted_commit():
    with pytest.raises(mb.BudgetError, match="commit"):
        mb.require_headroom(env=env(commit=0.4, gpu_free=5000, ram=3.0))


def test_headroom_refuses_exhausted_vram():
    with pytest.raises(mb.BudgetError, match="VRAM"):
        mb.require_headroom(env=env(commit=10.0, gpu_free=249, ram=3.0))


def test_headroom_refuses_low_ram():
    with pytest.raises(mb.BudgetError, match="RAM"):
        mb.require_headroom(env=env(commit=10.0, gpu_free=5000, ram=0.3))


def test_headroom_passes_healthy_box():
    assert mb.require_headroom(env=env(commit=10.0, gpu_free=5000, ram=3.0))["gpu_free_mib"] == 5000


def test_headroom_fails_closed_when_sampler_unreadable(monkeypatch):
    def boom():
        raise mb.BudgetError("sampler unreadable")
    monkeypatch.setattr(mb, "sample", boom)
    with pytest.raises(mb.BudgetError):
        mb.require_headroom()


# --- tag resolution must not treat "missing" as "small" ----------------------

def test_blob_for_unknown_tag_raises(tmp_path):
    with pytest.raises(mb.BudgetError):
        mb.blob_for_tag("no-such-model:latest", root=str(tmp_path))


def test_blob_for_tag_reads_v2_layout(tmp_path):
    root = tmp_path
    man_dir = root / "manifests-v2" / "ollama.com" / "library" / "m"
    man_dir.mkdir(parents=True)
    (root / "blobs").mkdir()
    blob = root / "blobs" / "sha256-abc123"
    blob.write_bytes(b"GGUF-placeholder")
    (man_dir / "latest").write_text(json.dumps({
        "layers": [{"mediaType": "application/vnd.ollama.image.model",
                    "digest": "sha256:abc123"}]}), encoding="utf-8")
    assert mb.blob_for_tag("m", root=str(root)) == str(blob)


def test_blob_for_tag_raises_on_dangling_manifest(tmp_path):
    man_dir = tmp_path / "manifests-v2" / "ollama.com" / "library" / "m"
    man_dir.mkdir(parents=True)
    (man_dir / "latest").write_text(json.dumps({
        "layers": [{"mediaType": "application/vnd.ollama.image.model",
                    "digest": "sha256:gone"}]}), encoding="utf-8")
    with pytest.raises(mb.BudgetError):
        mb.blob_for_tag("m:latest", root=str(tmp_path))


def test_params_for_tag_reads_baked_placement(tmp_path):
    root = tmp_path
    man_dir = root / "manifests-v2" / "ollama.com" / "library" / "m"
    man_dir.mkdir(parents=True)
    (root / "blobs").mkdir()
    (root / "blobs" / "sha256-p").write_text('{"num_ctx":8192,"num_gpu":22}', encoding="utf-8")
    (man_dir / "latest").write_text(json.dumps({
        "layers": [{"mediaType": "application/vnd.ollama.image.params",
                    "digest": "sha256:p"}]}), encoding="utf-8")
    p = mb.params_for_tag("m", root=str(root))
    assert p["num_gpu"] == 22 and p["num_ctx"] == 8192


def test_unpinned_gpu_inherits_tag_not_full_offload():
    # The bug this guards: treating num_gpu=None as "all layers on GPU" projects
    # 8007 MiB for the MoE and refuses a leg that actually runs at 22 layers.
    f = facts(file_bytes=8_320_185_248)
    inherited = mb.project(f, 4096, 22)["vram_mib"]
    full = mb.project(f, 4096, None)["vram_mib"]
    assert inherited < full
    assert full - inherited > 1000


def test_params_layer_absent_returns_empty_not_error(tmp_path):
    man_dir = tmp_path / "manifests-v2" / "ollama.com" / "library" / "m"
    man_dir.mkdir(parents=True)
    (man_dir / "latest").write_text(json.dumps({"layers": []}), encoding="utf-8")
    assert mb.params_for_tag("m", root=str(tmp_path)) == {}


# --- orphan runner detector --------------------------------------------------

def test_orphan_detector_finds_dead_parent(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "111|222|False|5.9\n333|444|True|1.0\n", "")
    monkeypatch.setattr(mb.subprocess, "run", fake_run)
    got = mb.orphan_runners()
    assert len(got) == 1 and got[0]["pid"] == 111 and got[0]["ws_gb"] == 5.9


def test_orphan_detector_ignores_live_parent(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "333|444|True|1.0\n", "")
    monkeypatch.setattr(mb.subprocess, "run", fake_run)
    assert mb.orphan_runners() == []


# --- in-process HF load guard (the 16 GB bf16 landmine) -----------------------

def test_hf_weight_bytes_sums_shards(tmp_path):
    (tmp_path / "model-00001.safetensors").write_bytes(b"x" * 2048)
    (tmp_path / "model-00002.safetensors").write_bytes(b"x" * 1024)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    assert mb.hf_weight_bytes(str(tmp_path)) == 3072


def test_hf_weight_bytes_refuses_dir_without_weights(tmp_path):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(mb.BudgetError):
        mb.hf_weight_bytes(str(tmp_path))


def test_hf_fit_refuses_unquantized_8b_on_this_box(tmp_path, monkeypatch):
    # ~16 GB of bf16 weights against a healthy-but-small box must be refused.
    (tmp_path / "model.safetensors").write_bytes(b"x" * 16)
    monkeypatch.setattr(mb, "hf_weight_bytes", lambda p: 16 * mb.GiB)
    with pytest.raises(mb.BudgetError, match="does not fit"):
        mb.require_hf_fit(str(tmp_path), device="cuda",
                          env=env(commit=10.0, gpu_free=5080, ram=3.0))


def test_hf_fit_allows_a_model_that_actually_fits(tmp_path, monkeypatch):
    (tmp_path / "model.safetensors").write_bytes(b"x" * 16)
    monkeypatch.setattr(mb, "hf_weight_bytes", lambda p: 1 * mb.GiB)
    got = mb.require_hf_fit(str(tmp_path), device="cpu",
                            env=env(commit=10.0, gpu_free=5080, ram=3.0))
    assert got["weight_gb"] == 1.0


def test_hf_fit_cpu_device_does_not_demand_vram(tmp_path, monkeypatch):
    (tmp_path / "model.safetensors").write_bytes(b"x" * 16)
    monkeypatch.setattr(mb, "hf_weight_bytes", lambda p: 4 * mb.GiB)
    # 4 GB fits commit; on CPU the VRAM term must not apply even with no free VRAM.
    assert mb.require_hf_fit(str(tmp_path), device="cpu",
                             env=env(commit=10.0, gpu_free=100, ram=3.0))["weight_gb"] == 4.0
