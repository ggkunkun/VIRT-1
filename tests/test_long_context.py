# -*- coding: utf-8 -*-
"""Contract tests for the GitHub-grounded long-context module.

No live model is required. Uses plain temp dirs because the host sitecustomize
safe-delete guard breaks pytest's tmp_path finalizer.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from virtu_omni.context import long_context as LC


class FakeBackend:
    def __init__(self):
        self.calls = []

    def chat(self, messages, *, model, num_ctx=32768, num_gpu=16,
             max_tokens=256, temperature=0.0):
        self.calls.append({"messages": list(messages), "model": model, "num_ctx": num_ctx})
        return {"text": '{"world_state": {"outer_dia_mm": 167.3}}',
                "usage": {"prompt_tokens": 4200}, "latency_s": 0.01, "timings": {}, "raw": {}}


class FakeGateway:
    def __init__(self):
        self.calls = []

    def chat(self, messages, *, model=None, **opts):
        self.calls.append({"messages": list(messages), "model": model})
        return {"success": True, "data": {"choices": [{"message": {"content": "ok"}}]}}


@pytest.fixture
def workdir():
    return Path(tempfile.mkdtemp(prefix="virtu_longctx_test_"))


def _corpus(n=20) -> str:
    parts = [
        f"第 {i} 轮评审纪要：草案外径 = {150 + i} mm，主轴转速 = {1100 + i} rpm。"
        f"会议讨论了工艺路线、刀具选择与装夹方式，记录人已完成签字确认。"
        for i in range(n)
    ]
    parts.insert(n // 2, "最终确认：法兰外径 = 167.3 mm，安全系数 FOS = 2.37，材料 45 钢，rc=0。")
    return "\n\n".join(parts)


def _session(workdir, *, physical_ctx=32768, backend=None):
    return LC.LongContextSession(
        store_path=str(workdir / "lc.sqlite"),
        backend=backend or FakeBackend(),
        physical_ctx=physical_ctx,
        top_k=4,
    )


def test_estimator_calibration_matches_measured_system_prompt():
    est = LC.TokenEstimator.from_measurement(8053, 3912)
    assert 1.9 < est.chars_per_token < 2.2
    # Character-count estimation is approximate; allow one token of rounding.
    assert abs(est.estimate("x" * 8053) - 3912) <= 1


def test_budget_scales_with_physical_window():
    small = LC.ContextBudget(physical_ctx=5120).input_budget()
    large = LC.ContextBudget(physical_ctx=32768).input_budget()
    assert small < 1200
    assert large > 20000
    assert large > small * 10


def test_store_ingest_retrieval_and_restart(workdir):
    path = str(workdir / "lc.sqlite")
    s = LC.LongContextStore(path)
    n = s.ingest("minutes", _corpus(), chunk_chars=300)
    assert n > 10
    hits = s.search("最终确认的法兰外径是多少 mm", top_k=4)
    assert hits
    assert any("167.3" in h.text for h in hits)
    assert hits[0].score >= hits[-1].score

    restarted = LC.LongContextStore(path)
    assert restarted.stats()["chunks"] == n
    assert restarted.stats()["total_chars"] > 1000


def test_compression_keeps_numbers_and_drops_prose():
    text = (
        "这是一段非常冗长的描述性文字，没有具体的技术信息，只是叙述会议氛围与流程安排。\n"
        "最终确认：法兰外径 = 167.3 mm，FOS = 2.37\n"
        "另一段纯描述文字，用于测试是否被丢弃。\n"
        "rc=0 sha256=abc123"
    )
    compressed, meta = LC.compress_chunk(text, max_chars=200)
    assert "167.3" in compressed and "FOS" in compressed and "rc=0" in compressed
    assert "会议氛围" not in compressed
    assert meta["compressed_chars"] <= 220
    assert meta["kept_lines"] < meta["total_lines"]


def test_compose_respects_tight_budget(workdir):
    session = _session(workdir, physical_ctx=5120)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    messages, meta = session.compose("最终确认的法兰外径是多少 mm")
    assert meta["estimated_packet_tokens"] <= meta["input_budget_tokens"]
    assert meta["budget_exceeded"] is False
    assert meta["retrieved_chunks"] >= 1
    assert "167.3" in messages[0]["content"]
    assert "<TASK>" in messages[1]["content"]


def test_broad_query_never_produces_empty_packet(workdir):
    session = _session(workdir)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    messages, meta = session.compose("随便聊聊")
    assert meta["retrieved_chunks"] >= 1
    assert "[/LONG_CONTEXT_RETRIEVAL]" in messages[0]["content"]


def test_english_query_expansion_hits_chinese_needle(workdir):
    """Regression: English-only recall queries used to retrieve draft chunks."""
    session = _session(workdir)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    english = (
        "Return a world_state JSON containing the FINAL CONFIRMED flange outer "
        "diameter in mm (field outer_dia_mm). Output JSON only."
    )
    messages, meta = session.compose(english)
    assert meta["retrieval_query"] != english
    assert "最终确认" in meta["retrieval_query"] and "外径" in meta["retrieval_query"]
    assert "167.3" in messages[0]["content"]


def test_explicit_retrieval_query_is_used(workdir):
    session = _session(workdir)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    messages, meta = session.compose("answer the question",
                                     retrieval_query="最终确认 法兰外径 FOS")
    assert meta["retrieval_query"] == "最终确认 法兰外径 FOS"
    assert "167.3" in messages[0]["content"]
    out = session.chat("answer the question", retrieval_query="最终确认 法兰外径 FOS")
    assert out["context_meta"]["retrieval_query"] == "最终确认 法兰外径 FOS"


class FakeRemory:
    """Simulates a compaction that frees system/history overhead."""

    def __init__(self, session):
        self.session = session
        self.compact_calls = 0
        self.checkpoint = None

    def compact(self, *, force=False):
        self.compact_calls += 1
        self.session.budget.system_overhead = 0
        return None


def test_guard_is_falsifiable_and_blocks_overflow(workdir):
    session = _session(workdir, physical_ctx=2048)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    with pytest.raises(LC.ContextBudgetExceeded, match="exceeds guard limit"):
        session.compose("最终确认的法兰外径是多少 mm")

    # Mutation probe: a healthy window must NOT be blocked.
    healthy = _session(workdir, physical_ctx=32768)
    healthy.ingest("minutes", _corpus(), chunk_chars=300)
    _, meta = healthy.compose("最终确认的法兰外径是多少 mm")
    assert meta["guard_passed"] is True
    assert meta["projected_tokens"] <= meta["guard_limit"]

    # Same healthy session, gate tightened to an impossible threshold.
    healthy.budget.guard_threshold = 0.0001
    with pytest.raises(LC.ContextBudgetExceeded):
        healthy.compose("最终确认的法兰外径是多少 mm")


def test_auto_recompact_runs_once_before_failing(workdir):
    session = _session(workdir, physical_ctx=2048)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    fake = FakeRemory(session)
    session.remory_session = fake
    messages, meta = session.compose("最终确认的法兰外径是多少 mm")
    assert fake.compact_calls == 1
    assert meta["guard_passed"] is True
    assert meta["auto_recompact_count"] == 1
    assert messages[0]["content"].startswith("<LONG_CONTEXT_RETRIEVAL")


def test_auto_recompact_can_be_disabled(workdir):
    session = _session(workdir, physical_ctx=2048)
    session.auto_recompact = False
    session.ingest("minutes", _corpus(), chunk_chars=300)
    session.remory_session = FakeRemory(session)
    with pytest.raises(LC.ContextBudgetExceeded):
        session.compose("最终确认的法兰外径是多少 mm")
    assert session.remory_session.compact_calls == 0


def test_chat_passes_native_options(workdir):
    backend = FakeBackend()
    session = _session(workdir, physical_ctx=16384, backend=backend)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    out = session.chat("最终确认的法兰外径是多少 mm")
    assert "167.3" in out["text"]
    assert backend.calls[0]["num_ctx"] == 16384
    assert out["context_meta"]["physical_ctx"] == 16384


def test_inject_and_gateway_hook_are_falsifiable(workdir):
    session = _session(workdir)
    session.ingest("minutes", _corpus(), chunk_chars=300)
    original = [
        {"role": "user", "content": "先前的任务说明"},
        {"role": "assistant", "content": "收到"},
        {"role": "user", "content": "最终确认的法兰外径是多少 mm"},
    ]
    injected = session.inject(original)
    assert len(injected) == len(original) + 1
    assert injected[-1] == original[-1]
    assert "LONG_CONTEXT_RETRIEVAL" in injected[-2]["content"]
    assert session.injection_count == 1

    gateway = FakeGateway()
    LC.attach_to_gateway(gateway, session)
    LC.attach_to_gateway(gateway, session)
    gateway.chat(original)
    assert gateway.calls[0]["model"] == LC.DEFAULT_MODEL
    assert session.injection_count == 2
    assert "LONG_CONTEXT_RETRIEVAL" in str(gateway.calls[0]["messages"])

    plain = FakeGateway()
    plain.chat(original)
    assert "LONG_CONTEXT_RETRIEVAL" not in str(plain.calls[0]["messages"])
