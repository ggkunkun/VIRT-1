# -*- coding: utf-8 -*-
"""agent_team 收敛验证：legacy 信封 vs 真实工程运行时（SwarmCommander）。

背景：`agent_team.IndustrialAgentTeam` 原有 7 步流水线的工程内容是模板/桩
（固定子模块、写死 GD&T、示例 VBA/Macro B），却会自报 `status=SUCCESS`；
真实工程能力在 `swarm_orchestrator.SwarmCommander`。两者并存容易被误用。

本测试锁死收敛后的契约：

A. legacy `solve()` 必须显式标注自己不是真实工程验证
   （runtime=legacy_stub_pipeline / evidence_basis=asserted / engineering_verified=False）。
B. `solve_engineering()` 跑真实链：状态 SUCCESS、几何 measured、5 份 Meta-SOP 落盘。
C. `solve_full()` 成功路径：status 跟真实门走，保留 legacy 字段以兼容下游。
D. **可证伪**：真实门失败时，即使 legacy 桩 agent 全部自报 COMPLETED，
   `solve_full()` 的 status 必须是 FAILED（不再出现"桩自报成功"掩盖真实失败）。

运行： python tests/test_agent_team_convergence.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.agent.agent_team import (  # noqa: E402
    LEGACY_RUNTIME_TAG, REAL_ENGINEERING_RUNTIME, IndustrialAgentTeam,
)
from virtu_omni.agent.swarm_orchestrator import SwarmCommander  # noqa: E402

RUN_ROOT = ROOT / "runs" / "convergence_test"


def _params():
    return {
        "design_stl": str(ROOT / "artifacts" / "aero_closed_impeller"
                          / "AE_CLOSED_IMPELLER_NASA1975.stl"),
        "spindle_axis": "Z",
        "part_type": "铝合金闭式叶轮",
        "material": "AL6061-T6",
        "surface_finish": "Ra1.6",
        "tolerance": "IT8",
        "tool_radius_mm": 3.0,
        "allowance_mm": 0.01,
    }


def main() -> int:
    checks = []

    # ---- A. legacy 信封必须自我标注（不冒充真实工程验证）----
    team = IndustrialAgentTeam()
    legacy = team.solve("设计一个铝合金闭式叶轮并加工",
                        output_dir=str(RUN_ROOT / "legacy"),
                        memory_safe=False)
    print("A runtime=", legacy.get("runtime"), "| status=", legacy.get("status"),
          "| evidence=", legacy.get("evidence_basis"),
          "| verified=", legacy.get("engineering_verified"))
    checks.append(("A legacy 打了桩标签", legacy.get("runtime") == LEGACY_RUNTIME_TAG))
    checks.append(("A legacy 证据为 asserted", legacy.get("evidence_basis") == "asserted"))
    checks.append(("A legacy 明示未验证", legacy.get("engineering_verified") is False))
    checks.append(("A legacy 指向真实运行时",
                   legacy.get("engineering_runtime") == REAL_ENGINEERING_RUNTIME))
    # legacy 原有契约不回归
    checks.append(("A legacy 7 步不回归",
                   legacy.get("status") in ("SUCCESS", "PARTIAL")
                   and len(legacy.get("per_agent_status") or {}) == 7
                   and len(legacy.get("team_collaboration_log") or []) == 7))

    # ---- B. solve_engineering 跑真实链 ----
    eng = team.solve_engineering("设计并加工铝合金闭式叶轮", params=_params(),
                                 output_dir=str(RUN_ROOT / "engineering"))
    vr = eng.get("verification_report") or {}
    files = [Path(f) for f in (eng.get("meta_sop_files") or [])]
    print("B status=", eng.get("status"), "| success=", eng.get("success"),
          "| evidence=", eng.get("evidence_basis"),
          "| geom=", vr.get("geometry_evidence_status"),
          "| stock=", vr.get("stock_basis"),
          "| red_gate=", vr.get("red_team_gate"),
          "| meta_sop=", len(files), "| bb_keys=", len(eng.get("blackboard_keys") or []))
    checks.append(("B 真实链成功", eng.get("status") == "SUCCESS"))
    checks.append(("B 标记为已实测验证", eng.get("engineering_verified") is True))
    checks.append(("B 几何实测", vr.get("geometry_evidence_status") == "measured"))
    checks.append(("B 毛坯成品派生",
                   vr.get("stock_basis") == "measured_from_product_mesh"))
    checks.append(("B 红蓝辩论门通过", vr.get("red_team_gate") in (True, "pass")))
    checks.append(("B 五份 Meta-SOP 落盘",
                   len(files) == 5 and all(f.is_file() and f.stat().st_size > 200
                                           for f in files)))
    checks.append(("B 黑板键 ≥8", len(eng.get("blackboard_keys") or []) >= 8))
    checks.append(("B worker 状态齐备", len(eng.get("per_agent_status") or {}) >= 5))

    # ---- C. solve_full 成功路径 ----
    full = team.solve_full("设计并加工铝合金闭式叶轮", params=_params(),
                           output_dir=str(RUN_ROOT / "full_ok"), memory_safe=False)
    print("C status=", full.get("status"), "| legacy_status=", full.get("legacy_status"),
          "| verified=", full.get("engineering_verified"),
          "| runtime=", full.get("runtime"))
    checks.append(("C 合并后状态=SUCCESS", full.get("status") == "SUCCESS"))
    checks.append(("C 保留 legacy 兼容字段",
                   bool(full.get("architecture")) and bool(full.get("parametric_model"))
                   and bool(full.get("persisted_manifest"))))
    checks.append(("C 带真实验证报告",
                   bool((full.get("swarm_verification") or {}).get("red_team_gate") is not None)))
    checks.append(("C legacy 自报状态单独保留", full.get("legacy_status") in ("SUCCESS", "PARTIAL")))

    # ---- D. 可证伪：真实门失败必须压过桩自报成功 ----
    team_d = IndustrialAgentTeam()
    # 用便宜的 legacy 替身隔离"合并语义"（真实 legacy 已在 A 验证）
    team_d.solve = lambda *a, **k: {
        "status": "SUCCESS",
        "per_agent_status": {r: "COMPLETED" for r in IndustrialAgentTeam.ROLE_ORDER},
        "architecture": {"agent": "stub"}, "parametric_model": {"agent": "stub"},
        "persisted_manifest": [], "team_collaboration_log": [],
        "output_dir": str(RUN_ROOT / "full_bad" / "legacy_envelope"),
        "runtime": LEGACY_RUNTIME_TAG, "evidence_basis": "asserted",
        "engineering_verified": False,
    }
    original = SwarmCommander.solve

    def _fail(self, task, output_dir=None):
        return {
            "success": False, "mode": "SWARM",
            "results": {}, "trace": [], "blackboard_keys": ["geometry"],
            "verification_report": {
                "geometry_evidence_status": "missing_file",
                "stock_basis": "asserted",
                "red_team_gate": False,
                "red_team_findings": [{"id": "RED-NO-GEOMETRY-EVIDENCE",
                                      "severity": "fatal",
                                      "finding": "无几何实测证据却宣称成功"}],
                "evidence_basis": "asserted",
            },
            "meta_sop_files": [], "audit_log_len": 0, "elapsed_s": 0.01,
        }

    SwarmCommander.solve = _fail
    try:
        bad = team_d.solve_full("设计并加工闭式叶轮", params=_params(),
                                output_dir=str(RUN_ROOT / "full_bad"),
                                memory_safe=False)
    finally:
        SwarmCommander.solve = original
    print("D status=", bad.get("status"), "| legacy_status=", bad.get("legacy_status"),
          "| verified=", bad.get("engineering_verified"),
          "| red=", (bad.get("swarm_verification") or {}).get("red_team_findings"))
    checks.append(("D 真失败压过桩成功", bad.get("status") == "FAILED"))
    checks.append(("D 桩自报仍可对照", bad.get("legacy_status") == "SUCCESS"))
    checks.append(("D 未验证标记正确", bad.get("engineering_verified") is False))
    checks.append(("D 缺陷清单可追溯",
                   bool((bad.get("swarm_verification") or {}).get("red_team_findings"))))

    print("\n=== agent_team 收敛测试 ===")
    all_pass = True
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        all_pass = all_pass and bool(ok)
    print("\n" + ("ALL PASS (%d/%d)" % (sum(1 for _, o in checks if o), len(checks))
                  if all_pass else "HAS FAILURES"))
    return 0 if all_pass else 1


import pytest

from swarm_test_support import run_pytest_file, swarm_workspace  # noqa: F401


@pytest.fixture(autouse=True)
def _isolate_team_side_effects(tmp_path, monkeypatch):
    import virtu_omni.agent.agent_team as team_module
    import virtu_omni.agent.process_memory_reclaimer as reclaimer_module
    from virtu_omni.memory import VirtuHindsightMemory

    monkeypatch.setattr(reclaimer_module, "user32", None)
    monkeypatch.setattr(reclaimer_module, "k32", None)
    monkeypatch.setattr(reclaimer_module, "psapi", None)
    monkeypatch.setattr(reclaimer_module.ProcessMemoryReclaimer,
                        "find_target_processes", lambda self, key: [])
    monkeypatch.setattr(reclaimer_module.ProcessMemoryReclaimer,
                        "unload_ollama_model", lambda *a, **k: False)
    monkeypatch.setenv("VIRTU_MEMORY_PATH", str(tmp_path / "memory.json"))
    monkeypatch.delenv("HINDSIGHT_API_URL", raising=False)
    monkeypatch.delenv("HINDSIGHT_BASE_URL", raising=False)
    memory = VirtuHindsightMemory(storage_path=str(tmp_path / "hindsight.json"))
    monkeypatch.setattr(team_module, "VirtuHindsightMemory", lambda: memory)


def test_agent_team_convergence_contracts(swarm_workspace):
    assert main() == 0
    swarm_workspace.assert_runs(expected_count=2)


if __name__ == "__main__":
    raise SystemExit(run_pytest_file(__file__))
