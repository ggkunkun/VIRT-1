# -*- coding: utf-8 -*-
"""Unit and integration tests for Virtu memory-safe stage-gated Agent Team execution."""

import os
import sys
import json
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer
from virtu_omni.agent.agent_team import IndustrialAgentTeam


def test_process_memory_reclaimer_telemetry():
    """验证物理内存感知与工作集净化功能正常。"""
    reclaimer = ProcessMemoryReclaimer()
    mem = reclaimer.get_system_memory()
    assert mem["total_mb"] > 1000.0
    assert mem["available_mb"] > 100.0
    assert 0.0 <= mem["percent"] <= 100.0

    # 净化当前工作集
    reclaimer.trim_system_working_set()
    mem_after = reclaimer.get_system_memory()
    assert mem_after["available_mb"] > 0.0


def test_execute_step_with_memory_guard(tmp_path):
    """验证单步任务「落盘 -> 校验 -> 关闭软件 -> 回收内存」闭环。"""
    reclaimer = ProcessMemoryReclaimer(log_path=str(tmp_path / "reclamation.json"))
    sample_file = str(tmp_path / "01_test_artifact.txt")

    def dummy_step():
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write("DUMMY CAD ARTIFACT CONTENT")
        return {"status": "OK", "step": "01_test"}

    result, telemetry = reclaimer.execute_step_with_memory_guard(
        step_name="test_step_01",
        step_fn=dummy_step,
        expected_files=[sample_file],
        software_key="solidworks",
        out_dir=str(tmp_path)
    )

    assert result["status"] == "OK"
    assert telemetry["persistence_success"] is True
    assert len(telemetry["files_persisted"]) == 1
    assert telemetry["files_persisted"][0]["size_bytes"] > 0
    assert os.path.exists(sample_file)


def test_industrial_agent_team_memory_safe_solve(tmp_path):
    """验证多智能体团队端到端任务执行，每步落盘，关停软件，零孤儿进程。"""
    team = IndustrialAgentTeam()
    out_dir = str(tmp_path / "agent_team_run")
    prompt = "我想制造一款精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm"

    res = team.solve(prompt, output_dir=out_dir, memory_safe=True)

    assert res["status"] == "SUCCESS"
    assert os.path.isdir(out_dir)

    # 验证关键阶段工件均已非空落盘
    expected_artifacts = [
        "01_hindsight_retrieval.json",
        "02_architecture_spec.json",
        "03_parametric_feature_tree.json",
        "03_parametric_equations.json",
        "03_solidworks_native.swb",
        "04_drawing_standards_gdt.json",
        "05_machining_macro_b.nc",
        "05_cutting_params.json",
        "06_sandbox_simulation_audit.json",
        "07_hindsight_memory_commit.json",
        "AGENT_TEAM_EXECUTION_REPORT.md",
        "manifest.json"
    ]
    for fname in expected_artifacts:
        fpath = os.path.join(out_dir, fname)
        assert os.path.exists(fpath), f"工件缺失: {fname}"
        assert os.path.getsize(fpath) > 0, f"工件为空: {fname}"

    # 验证执行报告包含内存回收记录
    with open(res["report_path"], "r", encoding="utf-8") as f:
        report_text = f.read()
    assert "阶段递进与内存回收流水线" in report_text
    assert "内存净回收" in report_text

    # 确证无 CAD/CAM 软件滞留
    reclaimer = ProcessMemoryReclaimer()
    for sw in ["solidworks", "nx", "autocad", "cimco", "vericut", "sscnc"]:
        procs = reclaimer.find_target_processes(sw)
        assert len(procs) == 0, f"软件 {sw} 仍有未关闭的滞留进程: {procs}"


if __name__ == "__main__":
    import tempfile
    import pathlib
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = pathlib.Path(tempfile.mkdtemp())
    print(">>> 运行单元测试 1: 内存状态感知与工作集净化...")
    test_process_memory_reclaimer_telemetry()
    print("    [PASS] 内存感知与工作集净化正常")

    print(">>> 运行单元测试 2: 单步任务落盘与内存守护闭环...")
    test_execute_step_with_memory_guard(p / "t2")
    print("    [PASS] 单步落盘与内存守卫正常")

    print(">>> 运行单元测试 3: 工业智能体团队全链路内存安全协同...")
    test_industrial_agent_team_memory_safe_solve(p / "t3")
    print("    [PASS] 团队端到端任务全阶段落盘与软件释放验证通过")

    print("\n==========================================")
    print("✅ 全部 3 项阶段内存安全测试 100% 通过！")
    print("==========================================")

