"""Regression tests for per-request model routing and served_model attribution."""
import threading

import pytest

import scripts.ollama_toolcall_client as ollama_client
import virtu_real_backend as backend


def _bare_model():
    obj = object.__new__(backend.VirtuRealModel)
    obj.vllm_url = "http://127.0.0.1:11434/v1"
    obj.temperature = 0.3
    obj.max_tokens = 64
    obj._resolved = "vllm_http"
    obj._last_model_used = None
    obj._generation_lock = threading.RLock()
    obj.thinking_mode = "auto"
    return obj


@pytest.fixture
def capture_chat(monkeypatch):
    calls = []

    def fake_chat(model, messages, tools=None, **kwargs):
        calls.append({"model": model, "tools": tools})
        return {"content": "ok", "tool_calls": []}

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setenv("VIRTU_VLLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("VIRTU_TOOL_MODEL", "virtu-production:v3")
    return calls


def test_text_turn_uses_general_model(capture_chat):
    obj = _bare_model()
    text = obj._gen_vllm([{"role": "user", "content": "1+1=?"}], cad=False)
    assert text == "ok"
    assert capture_chat[-1]["model"] == "qwen3:8b"
    assert obj.identity()["last_model_used"] == "qwen3:8b"


def test_tool_turn_uses_production_model(capture_chat):
    obj = _bare_model()
    tools = [{"type": "function", "function": {"name": "cadcam_preflight"}}]
    text, calls = obj._gen_vllm([{"role": "user", "content": "巡检"}], cad=True, tools=tools)
    assert text == "ok" and calls == []
    assert capture_chat[-1]["model"] == "virtu-production:v3"
    assert obj.identity()["last_model_used"] == "virtu-production:v3"
