# -*- coding: utf-8 -*-
"""可证伪测试：所有模型链路的运行时联网增强。

覆盖点：
  * 检索到真实网络来源 -> 注入 prompt / system 注记，并返回可追溯 citations；
  * 只有本地 fallback 知识时 -> 必须视为"未联网"，不注入（反证：假联网必须红）；
  * VIRTU_INTERNET=off -> 完全不触网；
  * 检索异常 -> 原样返回，推理行为不变；
  * router 的结构化输出（format=json）不注入。
"""

from __future__ import annotations

import json
import types

import pytest

from virtu_omni.internet.search_engine import SearchResponse, SearchResultItem


class _FakeSearchEngine:
    def __init__(self, results=None, is_safe=True, error=None):
        self.results = list(results or [])
        self.is_safe = is_safe
        self.error = error
        self.calls = []

    def search(self, query, num_results=5):
        self.calls.append((query, num_results))
        if self.error is not None:
            raise self.error
        return SearchResponse(
            query=query,
            is_safe=self.is_safe,
            results=self.results[:num_results],
            total_found=len(self.results),
            source_engines_used=["duckduckgo_lite"],
            filter_verdict="clean",
            execution_time_ms=1.0,
        )


def _item(title, url, snippet, engine="duckduckgo_lite"):
    return SearchResultItem(title=title, url=url, snippet=snippet, source_engine=engine)


@pytest.fixture
def fake_engine(monkeypatch):
    """Install a fake search backend for every augmentation call."""
    monkeypatch.setenv("VIRTU_INTERNET", "on")
    engine = _FakeSearchEngine()
    import virtu_omni.internet.search_engine as search_engine_module
    monkeypatch.setattr(search_engine_module, "get_search_engine", lambda: engine)
    return engine


REAL_HIT = _item(
    "GB/T 1800.1 极限与配合",
    "https://openstd.samr.gov.cn/gb/1800.1",
    "标准公差等级 IT7 对应 0.025 mm（Φ30 附近），H7/g6 为常用精密间隙配合。",
)


def test_prompt_gets_real_web_evidence(fake_engine):
    from virtu_omni.internet import augment_prompt, MARKER

    fake_engine.results = [REAL_HIT]
    prompt, citations = augment_prompt("H7/g6 配合在 Φ30 上的极限间隙是多少？")

    assert MARKER in prompt
    assert REAL_HIT.url in prompt
    assert len(citations) == 1
    assert citations[0]["url"] == REAL_HIT.url


def test_local_fallback_kb_is_never_presented_as_internet(fake_engine):
    """反证：只有本地兜底知识时，必须判定为"未联网"，不得注入。"""
    from virtu_omni.internet import augment_prompt, MARKER

    fake_engine.results = [
        _item("本地工程知识库", "local://virtu/engineering_kb",
              "系统遵循 GB/ISO 国标及力学校核守则。", engine="engineering_fallback_kb")
    ]
    original = "H7/g6 配合的极限间隙是多少？"
    prompt, citations = augment_prompt(original)

    assert prompt == original
    assert citations == []
    assert MARKER not in prompt


def test_virtu_internet_off_disables_every_path(fake_engine, monkeypatch):
    from virtu_omni.internet import augment_messages, augment_prompt

    monkeypatch.setenv("VIRTU_INTERNET", "off")
    fake_engine.results = [REAL_HIT]

    prompt, citations = augment_prompt("标准公差 IT7 是多少？")
    messages = [{"role": "user", "content": "标准公差 IT7 是多少？"}]
    augmented, msg_citations = augment_messages(messages)

    assert prompt == "标准公差 IT7 是多少？"
    assert citations == []
    assert augmented == messages
    assert msg_citations == []
    assert fake_engine.calls == []  # 完全没触网


def test_search_failure_keeps_prompt_unchanged(fake_engine):
    from virtu_omni.internet import augment_prompt

    fake_engine.error = ConnectionError("network unreachable")
    original = "FANUC Macro B 的 #100 与 #500 变量区别？"
    prompt, citations = augment_prompt(original)

    assert prompt == original
    assert citations == []


def test_messages_are_injected_as_system_note_without_touching_user_text(fake_engine):
    from virtu_omni.internet import augment_messages

    fake_engine.results = [REAL_HIT]
    messages = [
        {"role": "system", "content": "你是工业助手。"},
        {"role": "user", "content": "H7/g6 配合的极限间隙是多少？"},
    ]
    augmented, citations = augment_messages(messages)

    assert len(citations) == 1
    assert augmented[0]["role"] == "system"
    assert REAL_HIT.url in augmented[0]["content"]
    # 用户原文绝不能被改写（数值校核只读 user 文本）
    assert augmented[1] == messages[1]
    assert len(augmented) == len(messages)


def test_messages_augmentation_is_idempotent(fake_engine):
    from virtu_omni.internet import augment_messages

    fake_engine.results = [REAL_HIT]
    messages = [{"role": "user", "content": "H7/g6 配合的极限间隙是多少？"}]
    once, _ = augment_messages(messages)
    twice, citations = augment_messages(once)

    assert twice == once
    assert citations == []


def test_router_appends_context_and_skips_json_format(fake_engine, monkeypatch):
    import virtu_router
    from virtu_omni.internet import MARKER

    fake_engine.results = [REAL_HIT]
    captured = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"response": "ok"}).encode("utf-8")

    def _fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(virtu_router.urllib.request, "urlopen", _fake_urlopen)

    virtu_router.ollama_generate("qwen2.5:3b", "H7/g6 配合极限间隙是多少？", stream=False)
    assert MARKER in captured["payload"]["prompt"]

    captured.clear()
    virtu_router.ollama_generate(
        "qwen2.5:3b", "H7/g6 配合极限间隙是多少？", stream=False, format="json")
    assert MARKER not in captured["payload"]["prompt"]


def test_backend_skips_tool_requests_but_augments_plain_chat(fake_engine):
    from virtu_real_backend import VirtuRealModel
    from virtu_omni.internet import MARKER

    fake_engine.results = [REAL_HIT]
    backend = types.SimpleNamespace()
    plain = [{"role": "user", "content": "H7/g6 配合的极限间隙是多少？"}]

    augmented = VirtuRealModel._with_internet(backend, plain)
    assert MARKER in augmented[0]["content"]
    assert augmented[-1] == plain[-1]

    skipped = VirtuRealModel._with_internet(
        backend, plain, tools=[{"type": "function", "function": {"name": "cadcam"}}])
    assert skipped == plain


def test_serving_server_calls_augmentation_before_tokenize(monkeypatch):
    from fastapi.testclient import TestClient

    from virtu_omni.config import ModelConfig, VirtuOmniConfig
    from virtu_omni.serving.server import create_app
    import virtu_omni.internet.augmentation as augmentation

    called = {}

    def _fake_augment(prompt, num_results=3):
        called["prompt"] = prompt
        return prompt + "\n[stub web context]", [{"url": "https://example.com"}]

    monkeypatch.setattr(augmentation, "augment_prompt", _fake_augment)

    token = "serving-augment-token-" + "x" * 40
    cfg = VirtuOmniConfig(model=ModelConfig(
        num_layers=1, hidden_dim=64, intermediate_dim=192, vocab_size=200,
        patch_size=14, image_resolution=56,
    ))
    client = TestClient(create_app(cfg, bearer_token=token),
                        headers={"Authorization": f"Bearer {token}"})
    response = client.post("/v1/chat/completions", json={
        "model": "Virtu-Omni-10B",
        "messages": [{"role": "user", "content": "IT7 公差是多少？"}],
        "stream": False,
    })

    assert response.status_code == 200
    assert called["prompt"] == "IT7 公差是多少？"

