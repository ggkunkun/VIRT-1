# -*- coding: utf-8 -*-
"""swarm_orchestrator 六处缺陷的反证测试（植入坏样本 ⇒ 必须红）。

每条都对应一个真实可发生的假象/竞态，且在修复前的代码上会翻红：
  1) release 不 notify_all → 短持有 + 长 TTL 时等待者睡满 deadline，假 LeaseTimeout；
  2) read 返回活引用 → 读者绕过写锁租约直接改共享态；
  3) snapshot 返回活引用 → 序列化快照被外部改写即污染黑板；
  4) handoff_gate 只查键存在 → 空壳前置文档（workers=[]/None）被放行；
  5) audit_worker 的 payload_error 仅在 require_ad 时判红 → 坏载荷被静默吞成"通过"（§8.4）；
  6) critic 不识别 payload_error → 证据链断裂却判绿。

运行： .venv/Scripts/python.exe -m pytest tests/test_swarm_blackboard_fix.py -q
"""
from __future__ import annotations

import os
import sys
import time
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import virtu_omni.agent.swarm_orchestrator as swarm  # noqa: E402
from virtu_omni.agent.swarm_orchestrator import (  # noqa: E402
    Blackboard, HandoffError, MetaSOPDoc, handoff_gate,
)


# ---------------------------------------------------------------------------
# 1. release 必须唤醒等待者（notify_all）
# ---------------------------------------------------------------------------
def test_release_wakes_waiter_promptly():
    bb = Blackboard(lease_ttl_s=30.0)   # 长 TTL：旧代码等待者会睡满自己的 5s deadline
    key = "k"
    holder = bb.acquire("holder", key, timeout_s=1.0)
    got: dict = {}

    def waiter():
        t0 = time.time()
        try:
            lease = bb.acquire("waiter", key, timeout_s=5.0)
            got["elapsed"] = time.time() - t0
            bb.release(lease)
        except swarm.LeaseTimeout:
            got["timeout"] = True

    th = threading.Thread(target=waiter)
    th.start()
    time.sleep(0.3)            # 确保 waiter 已进入 cond.wait
    bb.release(holder)         # 释放即应唤醒，而非等满 TTL/deadline
    th.join(timeout=8)
    assert not th.is_alive(), "等待者线程未在预算内返回"
    assert got.get("timeout") is not True, "释放后等待者仍超时（release 缺 notify_all）"
    assert "elapsed" in got, "等待者未拿到租约"
    assert got["elapsed"] < 3.0, f"等待者耗时 {got['elapsed']:.2f}s，应被立即唤醒"


# ---------------------------------------------------------------------------
# 2/3. read / snapshot 必须返回拷贝，杜绝绕过写锁
# ---------------------------------------------------------------------------
def _seed(bb: Blackboard, key: str, value: dict) -> None:
    lease = bb.acquire("w", key)
    try:
        bb.write(lease, key, value, basis="measured")
    finally:
        bb.release(lease)


def test_read_returns_copy_not_live_ref():
    bb = Blackboard()
    _seed(bb, "k", {"v": 1, "nested": {"x": 1}})
    got = bb.read("k")
    got["v"] = 999
    got["nested"]["x"] = 999
    fresh = bb.read("k")
    assert fresh["v"] == 1, "read 返回活引用：读者绕过写锁改了共享态"
    assert fresh["nested"]["x"] == 1, "read 浅拷贝：嵌套结构仍被外部改写"


def test_snapshot_returns_copy_not_live_ref():
    bb = Blackboard()
    _seed(bb, "k", {"v": 1})
    snap = bb.snapshot()
    snap["k"]["value"]["v"] = 999
    snap["k"]["meta"]["basis"] = "tampered"
    assert bb.read("k")["v"] == 1, "snapshot 返回活引用：快照改写污染黑板"
    assert bb.meta("k").get("basis") == "measured"


def test_meta_returns_copy_not_live_ref():
    bb = Blackboard()
    _seed(bb, "k", {"v": 1})
    m = bb.meta("k")
    m["basis"] = "tampered"
    assert bb.meta("k").get("basis") == "measured"


# ---------------------------------------------------------------------------
# 4. handoff_gate 必须拒绝空壳前置字段（非空校验）
# ---------------------------------------------------------------------------
def test_handoff_rejects_empty_list_required_field():
    bb = Blackboard()
    handoff_gate(bb, "PRD", None, [], {"workers": []}, "arch", "asserted")
    with pytest.raises(HandoffError):
        handoff_gate(bb, "ARCHITECTURE", "PRD", ["workers"], {"mapping": {}},
                     "arch", "asserted")


def test_handoff_rejects_none_required_field():
    bb = Blackboard()
    handoff_gate(bb, "PRD", None, [], {"workers": None}, "arch", "asserted")
    with pytest.raises(HandoffError):
        handoff_gate(bb, "ARCHITECTURE", "PRD", ["workers"], {}, "arch", "asserted")


def test_handoff_rejects_empty_dict_required_field():
    bb = Blackboard()
    handoff_gate(bb, "PRD", None, [], {"mapping": {}}, "arch", "asserted")
    with pytest.raises(HandoffError):
        handoff_gate(bb, "TASKS", "PRD", ["mapping"], {"tasks": {}}, "arch", "asserted")


def test_handoff_accepts_scalar_zero_and_nonempty():
    """正对照：标量 0 是合法取值（不算空），非空容器放行 —— 防止过度拒绝。"""
    bb = Blackboard()
    handoff_gate(bb, "PRD", None, [], {"count": 0, "workers": ["a"]}, "arch", "asserted")
    doc = handoff_gate(bb, "ARCHITECTURE", "PRD", ["count", "workers"],
                       {"mapping": {}}, "arch", "asserted")
    assert isinstance(doc, MetaSOPDoc)


# ---------------------------------------------------------------------------
# 5/6. Auto-Diff payload_error 必须无条件判红（§8.4 解析失败不得当作通过）
# ---------------------------------------------------------------------------
def _good_geometry_bb() -> Blackboard:
    bb = Blackboard()
    bb._store["geometry"] = {"evidence_status": "measured",
                             "recommended_tool_radius_mm": 5.0, "undercut_face_count": 0}
    bb._store["process_plan"] = {"online": False, "corrections": [],
                                 "requires_multiaxis": False}
    bb._store["toolpath"] = {"stock_basis": "measured_from_product_mesh",
                             "requires_multiaxis": False, "stock_shape": "cylinder"}
    return bb


def test_audit_payload_error_is_red_even_when_not_required(tmp_path, monkeypatch):
    bb = _good_geometry_bb()
    monkeypatch.setattr(swarm, "resolve_sample_assets_for_task", lambda task: {})
    corrupt = tmp_path / "bad.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    # require_autodiff 默认 False：旧代码会静默放行坏载荷
    task = {"autodiff_payload": str(corrupt), "allowance_mm": 0.01}
    rep = swarm.audit_worker(task, bb)
    assert rep["autodiff"]["basis"] == "payload_error"
    assert rep["passed"] is False, "坏载荷在 require_ad=False 时被静默吞成通过（§8.4）"
    assert any("载荷" in d for d in rep["defects"])


def test_audit_no_payload_still_passes_when_not_required(monkeypatch):
    """正对照：未提供载荷且未强制 → 审计仍可通过（证明不是无条件全红）。"""
    bb = _good_geometry_bb()
    monkeypatch.setattr(swarm, "resolve_sample_assets_for_task", lambda task: {})
    rep = swarm.audit_worker({"allowance_mm": 0.01}, bb)
    assert rep["passed"] is True
    assert rep["autodiff"]["basis"] == "not_provided"


def test_critic_rejects_payload_error_even_if_audit_claims_pass(monkeypatch):
    bb = _good_geometry_bb()
    bb._store["audit"] = {"passed": True, "defects": [],
                          "autodiff": {"basis": "payload_error",
                                       "error": "JSONDecodeError: boom"}}
    monkeypatch.setattr(swarm, "resolve_sample_assets_for_task", lambda task: {})
    res = swarm.AdversarialCritic().debate({"success": True}, bb)
    ids = [d["id"] for d in res["red_team_findings"]]
    assert "RED-AUTODIFF-ERROR" in ids, ids
    assert res["gate_passed"] is False, "证据链断裂却判绿"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))