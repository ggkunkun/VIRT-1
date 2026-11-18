# -*- coding: utf-8 -*-
"""多智能体分工运行时端到端测试（可复跑，沙箱可跑）。

覆盖：
  A. SwarmCommander.solve 在真实叶轮任务上跑通 10 阶段 + Meta-SOP 五文档 + 真实 worker 证据，
     且 success=True（几何实测 / 推荐刀具可行 / 毛坯来自成品 / 审计通过）。
  B. Blackboard 写锁租约：4 线程并发计数竞争被强制串行化（4×50=200），无租约写被拒，超时抛 LeaseTimeout。
  C. Meta-SOP 文档交接门：缺前置文档被拒。
  D. AdversarialCritic 红蓝辩论可证伪：坏交付物（success=True 但证据缺失/规范不可达/毛坯非成品）必须判红；
     好交付物必须判绿。
"""
import os
import sys
import math
import json
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni.agent.swarm_orchestrator import (
    SwarmCommander, Blackboard, Lease, LeaseError, LeaseTimeout, HandoffError, MetaSOPDoc,
    handoff_gate, meta_sop_key, AdversarialCritic, META_SOP_STAGES,
)
from swarm_test_support import swarm_workspace  # noqa: F401


def test_end_to_end_swarm_success(swarm_workspace):
    task = {
        "design_stl": str(swarm_workspace.design_stl),
        "spindle_axis": "Z",
        "part_type": "铝合金闭式叶轮",
        "material": "AL6061-T6",
        "surface_finish": "Ra1.6",
        "tolerance": "IT8",
        "tool_radius_mm": 3.0,
        "allowance_mm": 0.01,
    }
    out = str(swarm_workspace.root / "runs" / "swarm" / "test_e2e")
    res = SwarmCommander().solve(task, output_dir=out)
    vr = res["verification_report"]

    assert res["success"] is True, f"期望 success=True，实际 {vr}"
    # Meta-SOP 五文档齐备
    for s in META_SOP_STAGES:
        assert meta_sop_key(s) in res["blackboard_keys"], f"缺少 Meta-SOP 文档 {s}"
    # 真实 worker 证据
    assert vr["geometry_evidence_status"] == "measured", vr
    rec_tool = vr["recommended_tool_radius_mm"]
    assert isinstance(rec_tool, (int, float)) and not math.isinf(rec_tool) and rec_tool <= 12.0, rec_tool
    assert vr["stock_basis"] == "measured_from_product_mesh", vr
    assert vr["audit_passed"] is True, vr
    # 红蓝辩论门（致命缺陷为 0）
    assert vr["red_team_gate"] is True, vr["red_team_findings"]
    # 阶段完整
    stages = [t["stage"] for t in res["trace"]]
    assert "PARALLEL_FAN" in stages and "RED_BLUE_DEBATE" in stages and "CODE_MODEL" in stages
    # 落盘产物存在
    assert os.path.exists(res["artifact_verification_report"]), res["artifact_verification_report"]
    assert os.path.exists(res["artifact_blackboard"]), res["artifact_blackboard"]
    print("[PASS] 端到端 SWARM 成功路径：10 阶段 + Meta-SOP 五文档 + 真实证据 + 红蓝辩论绿")


def test_blackboard_write_lock_serializes_contention():
    bb = Blackboard(lease_ttl_s=2.0)
    key = "counter"
    bb._store[key] = {"v": 0}
    bb._meta[key] = {"writer": "init", "written_at": 0.0, "basis": "asserted"}

    def racer():
        for _ in range(50):
            lease = bb.acquire("racer", key, timeout_s=5.0)
            try:
                cur = bb.read(key)
                bb.write(lease, key, {"v": cur["v"] + 1}, basis="measured")
            finally:
                bb.release(lease)

    threads = [threading.Thread(target=racer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert bb.read(key)["v"] == 200, f"写锁失效：计数={bb.read(key)['v']} 应为 200"
    print("[PASS] Blackboard 写锁租约：4 线程×50=200 次写入完整串行化")

    # 无有效租约写必须被拒
    try:
        bb.write(Lease("x", "ghost", key, 0, 1), key, {"v": -1})
        raise AssertionError("无租约写竟被允许")
    except LeaseError:
        print("[PASS] 写锁门禁：无有效租约写入被拒 (LeaseError)")

    # 超时：长期持有租约后他人必须等待/超时
    holder = bb.acquire("holder", "k2", timeout_s=1.0)
    try:
        bb._store["k2"] = {}
        caught = False
        try:
            bb.acquire("other", "k2", timeout_s=0.3)
        except LeaseTimeout:
            caught = True
        assert caught, "租约占用期间他人 acquire 未超时"
        print("[PASS] 写锁租约超时：占用期间竞争者超时 (LeaseTimeout)")
    finally:
        bb.release(holder)


def test_meta_sop_handoff_gate_blocks_missing_prior():
    bb = Blackboard()
    try:
        handoff_gate(bb, "ARCHITECTURE", "PRD", ["workers"], {}, "x", "asserted")
        raise AssertionError("缺 PRD 前置文档竟被放行")
    except HandoffError:
        print("[PASS] Meta-SOP 交接门：缺前置文档被拒 (HandoffError)")
    # 写齐前置后应放行
    handoff_gate(bb, "PRD", None, [], {"workers": ["a"]}, "arch", "asserted")
    doc = handoff_gate(bb, "ARCHITECTURE", "PRD", ["workers"], {"mapping": {}}, "arch", "asserted")
    assert isinstance(doc, MetaSOPDoc)
    print("[PASS] Meta-SOP 交接门：前置齐备后正常放行")


def test_red_blue_debate_falsifiable():
    critic = AdversarialCritic()

    # 好交付物：几何实测 + 推荐刀具可行 + 毛坯来自成品 + 审计通过
    good_bb = Blackboard()
    good_bb._store["geometry"] = {
        "evidence_status": "measured", "faces_over_allowance_pct": 0.0,
        "recommended_tool_radius_mm": 5.0, "undercut_face_count": 0,
    }
    good_bb._store["process_plan"] = {"online": False, "corrections": [], "requires_multiaxis": False}
    good_bb._store["toolpath"] = {"stock_basis": "measured_from_product_mesh", "requires_multiaxis": False}
    good_bb._store["audit"] = {"passed": True, "defects": []}
    good = critic.debate({"success": True}, good_bb)
    assert good["gate_passed"] is True, good["red_team_findings"]
    print("[PASS] 红蓝辩论：好交付物判绿 (gate_passed=True)")

    # 坏交付物：宣称成功但证据缺失 + 规范不可达 + 毛坯非成品
    bad_bb = Blackboard()
    bad_bb._store["geometry"] = {
        "evidence_status": "asserted", "faces_over_allowance_pct": 100.0,
        "recommended_tool_radius_mm": float("inf"), "undercut_face_count": 50,
    }
    bad_bb._store["process_plan"] = {"online": True, "corrections": [], "requires_multiaxis": False}
    bad_bb._store["toolpath"] = {"stock_basis": "asserted", "requires_multiaxis": False}
    bad_bb._store["audit"] = {"passed": True, "defects": []}  # 蓝队谎报审计通过
    bad = critic.debate({"success": True}, bad_bb)
    assert bad["gate_passed"] is False, "坏交付物竟判绿"
    ids = [d["id"] for d in bad["red_team_findings"]]
    assert "RED-NO-GEOM-EVIDENCE" in ids, ids
    assert "RED-SPEC-UNREACHABLE" in ids, ids
    assert "RED-STOCK-NOT-PRODUCT" in ids, ids
    assert "RED-FAKE-ONLINE" in ids, ids
    print("[PASS] 红蓝辩论：坏交付物判红 (gate_passed=False, 含致命缺陷)", ids)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))
