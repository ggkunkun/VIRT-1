# -*- coding: utf-8 -*-
"""Regression checks for pinned 8B Q4_0 Agent / Bridge / Sleep / Ollama defaults."""
from __future__ import annotations

import importlib
import inspect
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fake_http_resp(payload: dict) -> mock.MagicMock:
    raw = json.dumps(payload).encode("utf-8")
    cm = mock.MagicMock()
    cm.__enter__.return_value = io.BytesIO(raw)
    cm.__exit__.return_value = False
    return cm


def test_windows_mcp_bridge_pins_8b_q4_0_and_8192_ctx(monkeypatch):
    monkeypatch.delenv("VIRTU_AGENT_MODEL", raising=False)
    import bridges.windows_mcp_bridge as wmb

    importlib.reload(wmb)
    assert wmb.DEFAULT_MODEL == "virtu-ties-v1:latest"
    assert inspect.signature(wmb.ollama_chat).parameters["num_ctx"].default == 8192

    captured = {}

    def fake_open(req, timeout=300):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _fake_http_resp({"message": {"content": "ok"}})

    monkeypatch.setattr(wmb._http, "open", fake_open)
    resp, _elapsed = wmb.ollama_chat(wmb.DEFAULT_MODEL, [{"role": "user", "content": "hi"}], [])
    assert resp["message"]["content"] == "ok"
    assert captured["payload"]["options"]["num_ctx"] == 8192
    assert captured["payload"]["options"]["num_gpu"] == 99
    assert captured["payload"]["keep_alive"] == "2m"
    assert captured["payload"]["think"] is False

    monkeypatch.setenv("VIRTU_AGENT_MODEL", "virtu-opt-8b:latest")
    importlib.reload(wmb)
    assert wmb.DEFAULT_MODEL == "virtu-opt-8b:latest"


def test_deep_agent_defaults_to_8192_ctx(monkeypatch):
    monkeypatch.delenv("VIRTU_DEEP_NUM_CTX", raising=False)
    from bridges.deep_agent import load_config

    cfg = load_config()
    assert cfg["num_ctx"] == 8192

    monkeypatch.setenv("VIRTU_DEEP_NUM_CTX", "4096")
    assert load_config()["num_ctx"] == 4096


def test_real_backend_defaults_avoid_missing_toolcall_and_14b(monkeypatch):
    monkeypatch.delenv("VIRTU_VLLM_MODEL", raising=False)
    monkeypatch.delenv("VIRTU_TOOL_MODEL", raising=False)
    import virtu_real_backend as vrb

    assert vrb._vllm_text_model() == "virtu-ties-v1:latest"
    assert vrb._vllm_tool_model() == "virtu-ties-v1:latest"


def test_router_fast_path_8192_preserves_hard_autogpu():
    from scripts.router import virtu_router as vr

    assert vr.GEN_OPTS_FAST["num_ctx"] == 8192
    assert vr.GEN_OPTS_FAST["num_gpu"] == 99
    assert "num_gpu" not in vr.GEN_OPTS_HARD


def test_sleep_framework_refuses_unsafe_models0_fallback(monkeypatch):
    monkeypatch.delenv("VIRTU_SLEEP_MODEL", raising=False)
    from virtu_omni.memory import sleep_framework as sf

    opener = mock.MagicMock()
    opener.open.return_value = _fake_http_resp(
        {"models": [{"name": "bge-m3:latest"}, {"name": "virtu-moe-14b:latest"}]}
    )
    with mock.patch("urllib.request.build_opener", return_value=opener):
        caller, label = sf.build_ollama_model_caller()
    assert caller is None
    assert label == "model_not_found:None"


def test_sleep_framework_prefers_resident_8b_and_8192_ctx(monkeypatch):
    monkeypatch.delenv("VIRTU_SLEEP_MODEL", raising=False)
    from virtu_omni.memory import sleep_framework as sf

    captured = {}

    def fake_open(req_or_url, timeout=90):
        if isinstance(req_or_url, str) and req_or_url.endswith("/api/tags"):
            return _fake_http_resp(
                {"models": [{"name": "bge-m3:latest"}, {"name": "virtu-ties-v1:latest"}]}
            )
        captured["payload"] = json.loads(req_or_url.data.decode("utf-8"))
        return _fake_http_resp({"message": {"content": "clean answer"}})

    opener = mock.MagicMock()
    opener.open.side_effect = fake_open
    with mock.patch("urllib.request.build_opener", return_value=opener):
        caller, label = sf.build_ollama_model_caller()
        assert label == "ollama:virtu-ties-v1:latest"
        assert caller is not None
        out = caller("hello")
    assert out == "clean answer"
    assert captured["payload"]["options"]["num_ctx"] == 8192


def test_process_memory_reclaimer_unloads_active_or_8b_fallback(monkeypatch):
    from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer

    reclaimer = ProcessMemoryReclaimer()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return mock.MagicMock(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)

    opener = mock.MagicMock()
    opener.open.return_value = _fake_http_resp(
        {"models": [{"name": "virtu-ties-v1:latest"}]}
    )
    with mock.patch("urllib.request.build_opener", return_value=opener):
        assert reclaimer.unload_ollama_model() is True
    assert calls == [["ollama", "stop", "virtu-ties-v1:latest"]]

    calls.clear()
    opener.open.side_effect = RuntimeError("ollama down")
    with mock.patch("urllib.request.build_opener", return_value=opener):
        assert reclaimer.unload_ollama_model() is True
    assert calls == [["ollama", "stop", "virtu-ties-v1:latest"]]


def test_ollama_launchers_and_service_scripts_pinned():
    for bat_name in ("start_ollama_11434.bat", "start_virtu_ollama.bat"):
        raw = (ROOT / bat_name).read_bytes()
        assert b"\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b"")
        text = raw.decode("utf-8", errors="replace")
        assert r"OLLAMA_MODELS=E:\migrated\D-MigratedFromC\ollama\models" in text
        assert "OLLAMA_KV_CACHE_TYPE=q4_0" in text
        assert "OLLAMA_FLASH_ATTENTION=1" in text
        assert "OLLAMA_MAX_LOADED_MODELS=1" in text
        assert "OLLAMA_CONTEXT_LENGTH=8192" in text
        assert "OLLAMA_KEEP_ALIVE=2m" in text

    svc_text = (ROOT / "scripts" / "run_virtu_service.py").read_text(encoding="utf-8")
    assert "virtu-moe-14b" not in svc_text
    assert "virtu-ties-v1:latest" in svc_text

    pinned_text = (ROOT / "scripts" / "virtu_service_pinned.py").read_text(encoding="utf-8")
    assert "virtu-toolcall" not in pinned_text
    assert "virtu-ties-v1:latest" in pinned_text

    super_text = (ROOT / "virtu_omni" / "agent" / "super_agent.py").read_text(encoding="utf-8")
    assert 'getattr(_deep, "DEFAULT_MODEL", "qwen2.5:7b")' not in super_text
    assert 'getattr(_deep, "DEFAULT_MODEL", "virtu-ties-v1:latest")' in super_text
