# -*- coding: utf-8 -*-
"""agent_team 记忆投毒修复的反证测试（§5 证据先于断言 / §8.4 坏样本必红）。

缺陷：`EvolutionAndMemoryAgent.run()` 旧实现无条件把 "成功完成" 写进 Hindsight
成功经验银行；`solve_full()` 又在真实工程门出结论**之前**就经 legacy 信封归档记忆。
于是沙箱/真实门判红时，记忆库里仍躺着一条"成功经验"——下次召回会把失败当成功复用。

修复契约（本文件逐条卡死，植入坏样本必须红）：
  1. run() 的成功断言 gated 于 verdict：auditor 未过 → 不得声称成功；
  2. engineering_verdict（权威门）优先于 legacy 沙箱：verdict=False 压过 auditor=True；
  3. verdict=True → evidence_basis=measured；legacy 沙箱成功 → asserted（不冒充实测）；
  4. solve(commit_memory=False) 延后归档（DEFERRED），不在真实门前写成功经验；
  5. solve_full 真实门判红 → memory_evolution.verified_success=False，归档为复盘记录。

运行： .venv/Scripts/python.exe -m pytest tests/test_agent_team_memory_fix.py -q
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.agent.agent_team import (  # noqa: E402
    EvolutionAndMemoryAgent, IndustrialAgentTeam,
)
from virtu_omni.agent.swarm_orchestrator import SwarmCommander  # noqa: E402
from virtu_omni.memory import VirtuHindsightMemory  # noqa: E402


# --------------------------------------------------------------------------- isolation
@pytest.fixture(autouse=True)
def _isolate_side_effects(tmp_path, monkeypatch):
    """与 convergence 同款隔离：记忆/ hindsight 落 tmp，回收器不碰真机进程/显存。"""
    import virtu_omni.agent.agent_team as team_module
    import virtu_omni.agent.process_memory_reclaimer as reclaimer_module

    monkeypatch.setattr(reclaimer_module, "user32", None)
    monkeypatch.setattr(reclaimer_module, "k32", None)
    monkeypatch.setattr(reclaimer_module, "psapi", None)
    monkeypatch.setattr(reclaimer_module.ProcessMemoryReclaimer,
                        "find_target_processes", lambda self, key: [])
    monkeypatch.setattr(reclaimer_module.ProcessMemoryReclaimer,
                        "orphan_processes", lambda self, key: [])
    monkeypatch.setattr(reclaimer_module.ProcessMemoryReclaimer,
                        "unload_ollama_model", lambda *a, **k: False)
    monkeypatch.setattr(reclaimer_module.ProcessMemoryReclaimer,
                        "reclaim_all_cad_cam", lambda *a, **k: None)
    monkeypatch.setenv("VIRTU_MEMORY_PATH", str(tmp_path / "memory.json"))
    monkeypatch.delenv("HINDSIGHT_API_URL", raising=False)
    monkeypatch.delenv("HINDSIGHT_BASE_URL", raising=False)
    memory = VirtuHindsightMemory(storage_path=str(tmp_path / "hindsight.json"))
    monkeypatch.setattr(team_module, "VirtuHindsightMemory", lambda: memory)


def _agent(tmp_path):
    hs = VirtuHindsightMemory(storage_path=str(tmp_path / "hs_unit.json"))
    return EvolutionAndMemoryAgent(hindsight_memory=hs)


def _spy_retain(agent, monkeypatch):
    """捕获写进记忆银行的正文与元数据——投毒就发生在这里。"""
    calls = []
    orig = agent.hindsight.retain

    def spy(*a, **k):
        calls.append({"content": k.get("content"),
                      "metadata": k.get("metadata") or {},
                      "memory_type": k.get("memory_type")})
        return orig(*a, **k)

    monkeypatch.setattr(agent.hindsight, "retain", spy)
    return calls


def _context(auditor_passed, verdict=None):
    ctx = {
        "user_prompt": "制造一款精密法兰",
        "architecture": {"parsed_spec": {"wish_name": "Flange", "material": "AL6061"}},
        "auditor": {"passed": auditor_passed, "verified_sw_vba": "' stub vba"},
    }
    if verdict is not None:
        ctx["engineering_verdict"] = verdict
    return ctx


SUCCESS_MARKERS = ("成功完成", "验证通过")
RETRO_MARKER = "不得当作成功经验"


# --------------------------------------------------------------------------- run() verdict gate
def test_run_auditor_failed_must_not_claim_success(tmp_path, monkeypatch):
    """坏样本：沙箱未过。旧实现仍写 '成功完成' → 必须红。"""
    agent = _agent(tmp_path)
    calls = _spy_retain(agent, monkeypatch)
    res = agent.run(_context(auditor_passed=False))

    assert res["verified_success"] is False
    assert res["evidence_basis"] == "asserted"
    exp = calls[0]
    assert exp["metadata"]["engineering_verified"] is False
    assert RETRO_MARKER in exp["content"]
    assert not any(m in exp["content"] for m in SUCCESS_MARKERS), \
        f"沙箱失败却归档成功经验: {exp['content']}"


def test_run_engineering_verdict_false_overrides_auditor_pass(tmp_path, monkeypatch):
    """坏样本：legacy 沙箱自报通过，但真实工程门判红。权威门必须压过桩。"""
    agent = _agent(tmp_path)
    calls = _spy_retain(agent, monkeypatch)
    res = agent.run(_context(auditor_passed=True, verdict=False))

    assert res["verified_success"] is False
    assert res["engineering_verdict"] is False
    exp = calls[0]
    assert "真实工程门未通过" in exp["content"]
    assert RETRO_MARKER in exp["content"]
    assert not any(m in exp["content"] for m in SUCCESS_MARKERS)


def test_run_engineering_verdict_true_is_measured(tmp_path, monkeypatch):
    """正对照：真实门通过 → measured，且即便 legacy 沙箱未过也以权威门为准。"""
    agent = _agent(tmp_path)
    calls = _spy_retain(agent, monkeypatch)
    res = agent.run(_context(auditor_passed=False, verdict=True))

    assert res["verified_success"] is True
    assert res["evidence_basis"] == "measured"
    exp = calls[0]
    assert exp["metadata"]["engineering_verified"] is True
    assert exp["metadata"]["evidence_basis"] == "measured"
    assert "验证通过" in exp["content"]


def test_run_auditor_passed_no_verdict_legacy_positive(tmp_path, monkeypatch):
    """正对照：独立 legacy（无权威门）沙箱通过 → COMPLETED + EXP_，但 basis=asserted。"""
    agent = _agent(tmp_path)
    res = agent.run(_context(auditor_passed=True))

    assert res["status"] == "COMPLETED"
    assert res["memory_id"].startswith("EXP_")
    assert res["verified_success"] is True
    # legacy 沙箱是 asserted 级证据，不得冒充 measured 几何实测
    assert res["evidence_basis"] == "asserted"


# --------------------------------------------------------------------------- solve() deferral
def test_solve_commit_memory_false_defers(tmp_path):
    """commit_memory=False：第 7 步 DEFERRED，不在真实门前写成功经验。"""
    team = IndustrialAgentTeam()
    out = str(tmp_path / "deferred")
    res = team.solve("制造法兰 材质AL6061", output_dir=out,
                     memory_safe=False, commit_memory=False)

    mem = res["memory_evolution"]
    assert mem["status"] == "DEFERRED"
    assert mem["deferred"] is True
    assert mem["verified_success"] is False
    assert res["per_agent_status"]["EvolutionAndMemoryAgent.commit"] == "DEFERRED"
    # 延后归档 → 团队级 PARTIAL（不是 SUCCESS，也不是 FAILED）
    assert res["status"] == "PARTIAL"
    # 占位工件仍落盘非空（产物契约不回归）
    p = os.path.join(out, "07_hindsight_memory_commit.json")
    assert os.path.exists(p) and os.path.getsize(p) > 0
    assert json.loads(Path(p).read_text(encoding="utf-8"))["status"] == "DEFERRED"


def test_solve_default_commits_standalone(tmp_path):
    """正对照：独立 solve 默认 commit_memory=True，沙箱通过 → COMPLETED（旧契约不回归）。"""
    team = IndustrialAgentTeam()
    out = str(tmp_path / "standalone")
    res = team.solve("制造法兰 材质AL6061", output_dir=out, memory_safe=False)

    mem = res["memory_evolution"]
    assert mem["status"] == "COMPLETED"
    assert mem["memory_id"].startswith("EXP_")
    assert res["per_agent_status"]["EvolutionAndMemoryAgent.commit"] == "COMPLETED"


# --------------------------------------------------------------------------- solve_full end-to-end
def _fail_swarm(self, task, output_dir=None):
    return {
        "success": False, "mode": "SWARM", "results": {}, "trace": [],
        "blackboard_keys": ["geometry"],
        "verification_report": {
            "geometry_evidence_status": "missing_file", "stock_basis": "asserted",
            "red_team_gate": False,
            "red_team_findings": [{"id": "RED-NO-GEOMETRY-EVIDENCE", "severity": "fatal",
                                   "finding": "无几何实测证据却宣称成功"}],
            "evidence_basis": "asserted",
        },
        "meta_sop_files": [], "audit_log_len": 0, "elapsed_s": 0.01,
    }


def test_solve_full_failing_gate_does_not_poison_memory(tmp_path, monkeypatch):
    """端到端坏样本：真实门判红，即使 legacy 桩全自报完成，记忆不得标成功。"""
    team = IndustrialAgentTeam()
    calls = _spy_retain(team.memory_agent, monkeypatch)
    monkeypatch.setattr(SwarmCommander, "solve", _fail_swarm)

    out = str(tmp_path / "full_bad")
    res = team.solve_full("制造法兰 材质AL6061", params={}, output_dir=out,
                          memory_safe=False)

    assert res["status"] == "FAILED"
    assert res["engineering_verified"] is False
    mem = res["memory_evolution"]
    assert mem["verified_success"] is False
    assert mem["engineering_verdict"] is False
    assert res["per_agent_status"]["EvolutionAndMemoryAgent.commit"] == "COMPLETED"
    # 写进记忆银行的正文必须是复盘记录，而非成功经验
    exp = calls[0]
    assert exp["metadata"]["engineering_verified"] is False
    assert RETRO_MARKER in exp["content"]
    assert not any(m in exp["content"] for m in SUCCESS_MARKERS), \
        f"真实门判红却归档成功经验: {exp['content']}"
    # 权威 verdict 落盘可追溯
    p = os.path.join(out, "legacy_envelope", "07_hindsight_memory_commit.json")
    assert json.loads(Path(p).read_text(encoding="utf-8"))["verified_success"] is False


def test_solve_full_passing_gate_commits_measured_success(tmp_path, monkeypatch):
    """端到端正对照：真实门通过 → 记忆标 measured 成功经验。"""
    team = IndustrialAgentTeam()
    calls = _spy_retain(team.memory_agent, monkeypatch)
    params = {
        "design_stl": str(ROOT / "artifacts" / "aero_closed_impeller"
                          / "AE_CLOSED_IMPELLER_NASA1975.stl"),
        "spindle_axis": "Z", "part_type": "铝合金闭式叶轮", "material": "AL6061-T6",
        "surface_finish": "Ra1.6", "tolerance": "IT8",
        "tool_radius_mm": 3.0, "allowance_mm": 0.01,
    }
    out = str(tmp_path / "full_ok")
    res = team.solve_full("设计并加工铝合金闭式叶轮", params=params,
                          output_dir=out, memory_safe=False)

    assert res["status"] == "SUCCESS"
    assert res["engineering_verified"] is True
    mem = res["memory_evolution"]
    assert mem["verified_success"] is True
    assert mem["evidence_basis"] == "measured"
    exp = calls[0]
    assert exp["metadata"]["evidence_basis"] == "measured"
    assert "验证通过" in exp["content"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))