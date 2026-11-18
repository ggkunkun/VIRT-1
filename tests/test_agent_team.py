"""Unit and Integration Tests for Virtu Industrial Multi-Agent Team (Agent Team).

Tests:
1. Headless Sandbox Verifier: VBA COM model, Macro B kinematics collision detection.
2. Dense Vector Long-Term Memory: Semantic search and episodic memory commitment.
3. Self-Reflection Optimizer: In-the-loop virtual simulation and self-repair.
4. IndustrialAgentTeam Pipeline: End-to-end multi-agent collaborative execution.
5. WorkBuddy Bridge Integration: OpenAI-compatible response formatting with Agent Team.
"""

import sys
import os
import json
import pytest

WORKSPACE_DIR = r"D:\Virtu模型"
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.agent import (
    HeadlessSandboxVerifier,
    SelfReflectionOptimizer,
    SkillWriterAndMemory,
    IndustrialAgentTeam,
    ChiefArchitectAgent,
    ParametricModelingAgent,
    StandardsAndGDAgent,
    MachiningAndToolpathAgent,
    AuditorAndSandboxAgent,
    EvolutionAndMemoryAgent,
)


@pytest.fixture(autouse=True)
def _isolate_test_memory(tmp_path, monkeypatch):
    """Prevent unit tests from polluting production data/memory/industrial_knowledge_memory.json."""
    monkeypatch.setenv("VIRTU_MEMORY_PATH", str(tmp_path / "test_industrial_memory.json"))



def test_headless_sandbox_vba():
    verifier = HeadlessSandboxVerifier()
    
    # Invalid VBA code
    invalid_code = "Sub main()\n    Dim swApp As Object\n"
    res1 = verifier.verify_solidworks_vba(invalid_code)
    assert not res1["passed"]
    assert any("End Sub" in e for e in res1["errors"])
    assert any("ForceRebuild3" in e for e in res1["errors"])

    # Valid VBA code
    valid_code = """
Sub main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim swFeatMgr As SldWorks.FeatureManager
    Set swFeatMgr = swModel.FeatureManager
    Set swEqnMgr = swModel.GetEquationMgr
    swEqnMgr.Add -1, "\"D\" = 50.0"
    swEqnMgr.EvaluateAll
    swModel.ForceRebuild3 True
    swModel.ViewZoomtofit2
End Sub
"""
    res2 = verifier.verify_solidworks_vba(valid_code)
    assert res2["passed"]
    assert len(res2["errors"]) == 0


def test_headless_sandbox_macro_b_collision():
    verifier = HeadlessSandboxVerifier()

    # Code with rapid crash into negative Z
    crash_code = """
O0001
G21 G40
M03 S1200
G00 Z-15.0 (CRITICAL PLUNGE CRASH)
G01 X50.0 F0.2
M30
"""
    res1 = verifier.verify_cimco_macro_b(crash_code)
    assert not res1["passed"]
    assert res1["collision_detected"]
    assert any("KINEMATIC COLLISION" in e for e in res1["errors"])

    # Safe code with controlled feed
    safe_code = """
O0001
G21 G40 G28 U0.0 W0.0
M03 S1200
G00 Z2.0
G01 Z-15.0 F0.15
G01 X50.0 F0.2
M30
"""
    res2 = verifier.verify_cimco_macro_b(safe_code)
    assert res2["passed"]
    assert not res2["collision_detected"]


def test_dense_vector_memory():
    memory_path = r"D:\Virtu模型\data\memory\test_vector_memory.json"
    if os.path.exists(memory_path):
        os.remove(memory_path)

    mem = SkillWriterAndMemory(memory_path=memory_path, embedding_dim=128)
    assert mem.vector_store is not None

    # Commit test pattern
    rec = mem.commit_experience(
        task_signature="Aero_Flange_Turning",
        problem_summary="航空钛合金耐高温法兰端面与止口精密切削",
        solution_strategy="采用圆弧刀头车削，主轴线速控制在60m/min，配合G71精车余量",
        key_rules_learned=["钛合金必须强冷冷却", "防止刀尖磨损加剧必须降低转速"]
    )
    assert rec["id"].startswith("EXP_")
    assert len(mem.vector_store.documents) == 1

    # Dense Vector Query (semantic keywords without exact wording match)
    hits = mem.query_memory("航空耐高温法兰切削加工", top_k=2)
    assert len(hits) >= 1
    assert hits[0]["id"] == rec["id"]

    # Cleanup
    if os.path.exists(memory_path):
        os.remove(memory_path)


def test_self_reflection_in_the_loop_repair():
    optimizer = SelfReflectionOptimizer()
    
    # Code with missing ForceRebuild3 and missing EqnMgr
    raw_code = """
Sub main()
    Set swFeatMgr = swModel.FeatureManager
    MsgBox "Done"
End Sub
"""
    audit = optimizer.audit_code(raw_code, "solidworks")
    assert not audit["passed"]
    assert len(audit["issues"]) > 0

    # Reflect and optimize
    opt_code, refl = optimizer.reflect_and_optimize(raw_code, audit)
    assert "ForceRebuild3" in opt_code
    assert "GetEquationMgr" in opt_code
    assert "二次沙箱回归验证" in refl

    # Re-verify through sandbox
    re_audit = optimizer.audit_code(opt_code, "solidworks")
    assert re_audit["passed"]


def test_industrial_agent_team_solve():
    team = IndustrialAgentTeam()
    res = team.solve("我想制造一款外径60mm，内孔22mm，长度80mm，材质为AL7075-T6的高强连杆衬套")

    # 团队级 status 必须由 7 步子智能体真实 status 聚合得出（不得是写死的字面量）
    assert res["status"] in ("SUCCESS", "PARTIAL")
    assert res["status"] == team.aggregate_team_status(res["per_agent_status"])
    assert len(res["per_agent_status"]) == 7
    assert set(res["per_agent_status"]) == set(IndustrialAgentTeam.ROLE_ORDER)
    assert res["runtime_seconds"] > 0
    assert len(res["team_collaboration_log"]) == 7

    # 报告不得再把"零孤儿进程滞留"写成未实测的模板断言
    with open(res["report_path"], "r", encoding="utf-8") as f:
        report_text = f.read()
    assert "零孤儿进程滞留" not in report_text
    assert "残留进程实测" in report_text
    assert res["residual_processes"]["basis"] in ("measured", "partially_unmeasured", "unmeasured")

    # Check ChiefArchitectAgent output
    arch = res["architecture"]
    assert arch["status"] == "COMPLETED"
    assert arch["parsed_spec"]["material"] == "AL7075-T6"

    # Check ParametricModelingAgent output
    pm = res["parametric_model"]
    assert pm["status"] == "COMPLETED"
    assert len(pm["feature_tree"]) > 0
    assert "equations" in pm

    # Check StandardsAndGDAgent output
    std = res["standards_gdt"]
    assert std["status"] == "COMPLETED"
    assert len(std["drawing_spec"]["fit_tolerances"]) >= 1

    # Check MachiningAndToolpathAgent output
    mach = res["machining_cnc"]
    assert mach["status"] == "COMPLETED"
    assert "G71" in mach["macro_b_code"]

    # Check AuditorAndSandboxAgent output
    audit = res["sandbox_audit"]
    assert audit["passed"] is True
    assert "verified_sw_vba" in audit
    assert audit.get("sandbox_verification", {}).get("passed") is True

    # Check EvolutionAndMemoryAgent output
    mem = res["memory_evolution"]
    assert mem["status"] == "COMPLETED"
    assert mem["memory_id"].startswith("EXP_")
    assert mem.get("skills_provenance", {}).get("passed") is True
    assert mem["skills_provenance"]["verified_skills"] >= 15


def test_bridge_has_no_fake_synthesis_fallback():
    """The bridge must never resurrect the fixed 7,420-token fake report path."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" / "workbuddy_virtu_bridge.py").read_text(
        encoding="utf-8")
    assert "def _synthesize_response" not in src
    assert "100% PASS" not in src
    assert "沙箱仿真校验" not in src


def test_aggregate_team_status_rules():
    """团队级状态聚合规则：全 COMPLETED→SUCCESS；任一 FAILED→FAILED；其余→PARTIAL。"""
    agg = IndustrialAgentTeam.aggregate_team_status
    all_done = {k: "COMPLETED" for k in IndustrialAgentTeam.ROLE_ORDER}
    assert agg(all_done) == "SUCCESS"

    one_failed = dict(all_done)
    one_failed["AuditorAndSandboxAgent"] = "FAILED"
    assert agg(one_failed) == "FAILED"

    one_pending = dict(all_done)
    one_pending["MachiningAndToolpathAgent"] = "RUNNING"
    assert agg(one_pending) == "PARTIAL"

    # fail-closed：status 缺失（UNKNOWN）不得被算作完成
    one_unknown = dict(all_done)
    one_unknown["ChiefArchitectAgent"] = "UNKNOWN"
    assert agg(one_unknown) == "PARTIAL"


def test_industrial_agent_team_reports_failure_when_audit_fails():
    """反证用例：注入审计失败 → 团队级 status 必须 != SUCCESS。

    修复前 solve() 末尾为字面量 return {"status": "SUCCESS"}，本用例必红。
    """
    team = IndustrialAgentTeam()
    real_run = team.auditor_agent.run
    calls = {"n": 0}

    def fake_audit_run(payload):
        calls["n"] += 1
        real = dict(real_run(payload))
        real["status"] = "FAILED"
        real["passed"] = False
        return real

    team.auditor_agent.run = fake_audit_run
    try:
        res = team.solve("失败路径注入测试：外径60mm 内孔22mm 高强连杆衬套", memory_safe=False)
    finally:
        team.auditor_agent.run = real_run

    assert calls["n"] == 1
    assert res["per_agent_status"]["AuditorAndSandboxAgent"] == "FAILED"
    assert res["status"] != "SUCCESS"
    assert res["status"] == "FAILED"
    assert res["audit_passed"] is False
    with open(res["report_path"], "r", encoding="utf-8") as f:
        assert "FAILED" in f.read()


def test_skills_provenance_detects_tampering(tmp_path):
    """反证用例：篡改技能文件字节后，verify_skills_provenance() 必须判红并报告 sha256 mismatch。"""
    import hashlib
    fake_skills = tmp_path / "skills"
    skill_dir = fake_skills / "tampered-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    original_bytes = b"# Original Skill\n"
    skill_md.write_bytes(original_bytes)
    expected_sha = hashlib.sha256(original_bytes).hexdigest()

    prov = {
        "skills": {
            "tampered-skill": {
                "name": "tampered-skill",
                "install_path": "skills/tampered-skill",
                "files": [
                    {
                        "path": "SKILL.md",
                        "bytes": len(original_bytes),
                        "sha256": expected_sha,
                    }
                ],
            }
        }
    }
    prov_path = fake_skills / "SKILLS_PROVENANCE.json"
    prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")

    mem = SkillWriterAndMemory(
        memory_path=str(tmp_path / "mem.json"),
        skills_root=str(fake_skills),
    )
    ok_res = mem.verify_skills_provenance()
    assert ok_res["passed"] is True
    assert ok_res["verified_skills"] == 1
    assert ok_res["mismatches"] == []

    # 植入坏样本：篡改 SKILL.md 内容
    skill_md.write_bytes(b"# Tampered Skill\n")
    bad_res = mem.verify_skills_provenance()
    assert bad_res["passed"] is False
    assert bad_res["verified_skills"] == 0
    assert any("sha256 mismatch" in m for m in bad_res["mismatches"])

