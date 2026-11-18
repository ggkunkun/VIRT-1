# -*- coding: utf-8 -*-
"""Contract tests for the Remory protocol adapter (no live model required).

Evidence policy (AGENTS.md §5/§6): every claim below is verified by running
pytest. Mutation probes are included so the gates are falsifiable.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

import pytest

from virtu_omni.memory import remory_adapter as R


class FakeBackend:
    def __init__(self):
        self.calls = []

    def chat(self, messages, *, model, max_tokens=512, temperature=0.0):
        self.calls.append({"messages": list(messages), "model": model})
        return {"text": '{"ok": true}', "usage": {"prompt_tokens": len(str(messages))}, "raw": {}}


class FakeGateway:
    def __init__(self):
        self.calls = []

    def chat(self, messages, *, model=None, **opts):
        self.calls.append({"messages": list(messages), "model": model, "opts": opts})
        return {"success": True, "data": {"choices": [{"message": {"content": "ok"}}]}}


PREFIX = [{"role": "system", "content": "SYS-CONTRACT-v1"}]


@pytest.fixture
def workdir():
    # NOTE: the host sitecustomize safe-delete guard breaks pytest's workdir
    # finalizer (assert not self._finalizers). Use a plain temp dir instead.
    return Path(tempfile.mkdtemp(prefix="virtu_remory_test_"))


def _store(workdir):
    return str(workdir / "remory" / "memory.sqlite")


def _session(workdir, backend=None, prefix=PREFIX, sid="s1"):
    return R.RemorySession(
        session_id=sid,
        store_path=_store(workdir),
        prefix_messages=prefix,
        backend=backend or FakeBackend(),
        keep_recent=2,
    )


def _history(session, n=6):
    for i in range(n):
        session.append("user", f"第 {i} 轮：法兰外径 D{i+1} = {160 + i} mm，材质 45 钢")
        session.append("assistant", f"确认采用 D{i+1}，rc=0，sha256=hash{i}")


def test_digest_is_byte_identical_to_upstream_formula():
    value = {"b": 2, "a": [1, "中"]}
    expected = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    assert R.digest(value) == expected


def test_checkpoint_descriptor_roundtrip_and_validation():
    cp = R.Checkpoint("rm_" + "a" * 48, "summary", "b" * 64)
    assert R.Checkpoint.from_dict(cp.to_dict()) == cp
    for bad in (
        {"handle": "bad", "summary": "x", "prefix_sha256": "b" * 64},
        {"handle": "rm_" + "a" * 48, "summary": 3, "prefix_sha256": "b" * 64},
        {"handle": "rm_" + "a" * 48, "summary": "x", "prefix_sha256": "short"},
    ):
        with pytest.raises(ValueError):
            R.Checkpoint.from_dict(bad)


def test_compact_publishes_immutable_checkpoint_and_persists(workdir):
    session = _session(workdir)
    _history(session)
    cp = session.compact(force=True)
    assert re.fullmatch(r"rm_[0-9a-f]{48}", cp.handle)
    assert cp.prefix_sha256 == R.digest(PREFIX)
    assert len(cp.summary) > 20
    record = session.store.load(cp.handle, "s1")
    assert record["receipt"]["backend"] == R.BACKEND_ID
    assert record["receipt"]["compression_depth"] == 1
    assert any("160 mm" in item for item in record["residual"])
    assert len(session.history) == session.keep_recent

    # Restart: a brand-new session object sees the same checkpoint in SQLite.
    resumed = _session(workdir)
    assert resumed.resume(cp.handle) == cp
    assert "<REMORY_MEMORY" in resumed.client.render(cp.handle)


def test_prefix_identity_guard_is_falsifiable(workdir):
    session = _session(workdir)
    _history(session)
    cp = session.compact(force=True)
    changed = _session(workdir, prefix=[{"role": "system", "content": "SYS-CONTRACT-v2"}])
    changed.resume(cp.handle)
    with pytest.raises(ValueError, match="prefix changed"):
        changed.harness.generate(
            checkpoint=changed.checkpoint,
            prefix_messages=changed.prefix_messages,
            messages=[{"role": "user", "content": "question"}],
        )
    with pytest.raises(ValueError, match="prefix changed"):
        changed.harness.compact(
            prefix_messages=changed.prefix_messages,
            removed_messages=[{"role": "user", "content": "x"}],
            previous=changed.checkpoint,
        )


def test_failed_compaction_never_publishes_and_keeps_previous(workdir):
    session = _session(workdir)
    _history(session)
    first = session.compact(force=True)
    count_before = session.store.count("s1")

    # Failure source 1: empty removed history.
    with pytest.raises(RuntimeError):
        session.client.compact(
            prefix_messages=PREFIX, removed_messages=[], summary="x", previous=first
        )
    # Failure source 2: summary generator raised (Harness.compact must not publish).
    def broken_summary(removed, previous):
        raise RuntimeError("summary generation failed")

    session.harness.summary_fn = broken_summary
    session.history = [{"role": "user", "content": "new"}]
    with pytest.raises(RuntimeError, match="summary generation failed"):
        session.compact(force=True)
    assert session.checkpoint == first
    assert session.store.count("s1") == count_before


def test_chained_compaction_merges_residual_and_increments_depth(workdir):
    session = _session(workdir)
    _history(session, n=3)
    first = session.compact(force=True)
    session.append("user", "追加：安全系数 FOS = 2.1，输出文件 flange.step")
    session.append("assistant", "已验证 rc=0")
    # Push the FOS turn out of the retained window: only removed history is
    # encoded (upstream semantics), recent turns stay verbatim in context.
    for i in range(4):
        session.append("user", f"后续步骤 {i}")
        session.append("assistant", f"步骤 {i} 完成，rc=0")
    second = session.compact(force=True)
    assert second.handle != first.handle
    record = session.store.load(second.handle, "s1")
    assert record["previous"] == first.handle
    assert record["receipt"]["compression_depth"] == 2
    assert any("FOS" in item or "2.1" in item for item in record["residual"])
    assert any("160 mm" in item for item in record["residual"])


def test_delete_is_session_scoped(workdir):
    session = _session(workdir)
    _history(session)
    cp = session.compact(force=True)
    other = _session(workdir, sid="other")
    assert other.store.load(cp.handle, "other") is None
    assert other.client.delete(cp.handle) is False
    assert session.client.delete(cp.handle) is True
    assert session.store.load(cp.handle, "s1") is None


def test_session_chat_injects_memory_after_prefix(workdir):
    backend = FakeBackend()
    session = _session(workdir, backend=backend)
    session.chat("hello")  # no checkpoint yet -> plain generation
    assert not any("REMORY_MEMORY" in str(m) for m in backend.calls[0]["messages"])

    _history(session)
    cp = session.compact(force=True)
    session.chat("外径是多少？")
    messages = backend.calls[-1]["messages"]
    assert messages[0] == PREFIX[0]
    # user role is mandatory: an explicit system message would replace the
    # main model's Modelfile SYSTEM contract (measured 3906 -> 71 tokens).
    assert messages[1]["role"] == "user"
    assert cp.handle in messages[1]["content"]
    assert "[RESIDUAL_MEMORY" in messages[1]["content"]


def test_gateway_attach_is_transparent_and_idempotent(workdir):
    gateway = FakeGateway()
    session = _session(workdir)
    _history(session)
    cp = session.compact(force=True)
    R.attach_to_gateway(gateway, session)
    R.attach_to_gateway(gateway, session)  # no double-wrapping
    gateway.chat([{"role": "user", "content": "继续"}])
    call = gateway.calls[0]
    assert call["model"] == R.DEFAULT_MODEL
    assert cp.handle in str(call["messages"])
    assert session.injection_count == 1
    assert session.last_injected_handle == cp.handle

    # Negative control: an unattached gateway receives no memory carrier.
    plain = FakeGateway()
    plain.chat([{"role": "user", "content": "继续"}])
    assert "REMORY_MEMORY" not in str(plain.calls[0]["messages"])


def test_ollama_backend_delegates_to_gateway_result(workdir):
    gateway = FakeGateway()
    backend = R.OllamaChatBackend(gateway=gateway)
    out = backend.chat([{"role": "user", "content": "hi"}], model=R.DEFAULT_MODEL)
    assert out["text"] == "ok"
    assert gateway.calls[0]["model"] == R.DEFAULT_MODEL
