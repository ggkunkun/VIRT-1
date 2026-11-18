# -*- coding: utf-8 -*-
"""SWARM 入口（super_agent._solve_swarm）行为测试。

沙箱缺 sympy / shapely / torch，无法直接 import VirtuSuperAgent；
因此从源码 AST 抽出 `_solve_swarm` 单独编译执行，注入最小运行时
（真实 SwarmCommander + 真实成品 STL），验证四件事：

A. 正常路径：mode=SWARM、success=True、Meta-SOP 五文档齐备、黑板书 ≥8 键、
   红蓝辩论门通过、metrics 带几何/毛坯/在线真值。
B. 编排器抛异常：success=False、circuit_breaker=True、rcfa_report 有根因，
   且 mode 仍如实标注 SWARM（不伪装成功，也不悄悄改回 AUTONOMOUS）。
C. 编排器不可导入：降级 AUTONOMOUS、requested_mode=SWARM、
   require_real_swarm=True 时 success=False + swarm_require_real 标记。
D. 默认 design_stl：未显式传 design_stl 时自动取工作区真实成品 STL。

运行： python tests/test_swarm_entry.py
"""

from __future__ import annotations

import ast
import logging
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from swarm_test_support import run_pytest_file, swarm_workspace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUPER_AGENT = ROOT / "virtu_omni" / "agent" / "super_agent.py"
DESIGN_STL = ROOT / "artifacts" / "aero_closed_impeller" / "AE_CLOSED_IMPELLER_NASA1975.stl"


# ---------------------------------------------------------------------------
# 最小运行时：等价替身（不是 mock 业务逻辑，只补 sandbox 缺的依赖）
# ---------------------------------------------------------------------------
class _Mode:
    SWARM = types.SimpleNamespace(value="SWARM")
    AUTONOMOUS = types.SimpleNamespace(value="AUTONOMOUS")


@dataclass
class _Result:
    task_prompt: str
    mode: str
    success: bool
    runtime_seconds: float
    facets_engaged: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    trace_log: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    circuit_breaker_tripped: bool = False
    rcfa_report: Optional[Dict[str, Any]] = None
    output_dir: Optional[str] = None
    modality_report: Optional[Dict[str, Any]] = None
    requested_mode: Optional[str] = None


def _load_solve_swarm():
    src = SUPER_AGENT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "VirtuSuperAgent")
    fn = next(n for n in cls.body
              if isinstance(n, ast.FunctionDef) and n.name == "_solve_swarm")
    segment = ast.get_source_segment(src, fn)
    ns: Dict[str, Any] = {
        "time": __import__("time"),
        "logger": logging.getLogger("swarm-entry-test"),
        "Path": Path,
        "WORKSPACE_DIR": str(ROOT),
        "Dict": Dict, "List": List, "Any": Any, "Optional": Optional,
        "SuperAgentMode": _Mode,
        "SuperAgentExecutionResult": _Result,
    }
    exec(segment, ns)
    return ns["_solve_swarm"]


class _Agent:
    """最小 self 替身：只提供 _solve_swarm 真正用到的成员。"""

    def __init__(self) -> None:
        self.run_ctx = types.SimpleNamespace(
            run_id="test_swarm_entry",
            log=lambda *a, **k: None,
        )
        self.autonomous_called = False

    def _solve_autonomous(self, prompt, output_dir=None, memory_safe=True):
        self.autonomous_called = True
        return _Result(task_prompt=prompt, mode="AUTONOMOUS", success=True,
                       runtime_seconds=0.0, metrics={})

    def __call__(self, *a, **k):
        return _load_solve_swarm()(self, *a, **k)


def _task():
    return {
        "design_stl": str(DESIGN_STL),
        "spindle_axis": "Z",
        "part_type": "铝合金闭式叶轮",
        "material": "AL6061-T6",
        "surface_finish": "Ra1.6",
        "tolerance": "IT8",
        "tool_radius_mm": 3.0,
        "allowance_mm": 0.01,
    }


def main() -> int:
    # Load source only after the fixture has configured the temporary ROOT.
    _solve_swarm = _load_solve_swarm()
    checks = []

    # ---- A. 正常路径 ----
    agent = _Agent()
    res = _solve_swarm(agent, "设计并加工铝合金闭式叶轮",
                       params=_task(), output_dir=str(ROOT / "runs" / "swarm" / "entry_test"))
    print("A mode=", res.mode, "success=", res.success, "facets=", len(res.facets_engaged))
    print("A metrics:", {k: res.metrics.get(k) for k in
                         ("geometry_evidence_status", "recommended_tool_radius_mm",
                          "residual_over_pct", "stock_basis", "online",
                          "audit_passed", "red_team_gate")})
    print("A bb_keys=", res.metrics.get("swarm_blackboard_keys"),
          "write_audit=", res.metrics.get("swarm_write_audit_entries"),
          "red_findings=", res.metrics.get("red_team_findings"))
    docs = {str(d).split(".")[-1] for d in (res.artifacts.get("meta_sop_docs") or [])}
    print("A meta_sop:", sorted(docs))
    checks.append(("A mode=SWARM", res.mode == "SWARM"))
    checks.append(("A success", res.success is True))
    checks.append(("A 未降级 AUTONOMOUS", agent.autonomous_called is False))
    checks.append(("A Meta-SOP 五文档", docs >= {"PRD", "ARCHITECTURE", "TASKS",
                                                 "CODE_MODEL", "VERIFICATION_REPORT"}))
    checks.append(("A 黑板键 ≥8", (res.metrics.get("swarm_blackboard_keys") or 0) >= 8))
    checks.append(("A 写锁审计有记录", (res.metrics.get("swarm_write_audit_entries") or 0) > 0))
    checks.append(("A 几何实测", res.metrics.get("geometry_evidence_status") == "measured"))
    checks.append(("A 毛坯成品派生",
                   res.metrics.get("stock_basis") == "measured_from_product_mesh"))
    checks.append(("A 红队门通过",
                   res.metrics.get("red_team_gate") in (True, "pass")))
    checks.append(("A 委派了 5 个 worker", len(res.facets_engaged) >= 5))
    checks.append(("A trace 十阶段", len(res.trace_log) >= 10))

    # A2. Meta-SOP 文档必须真落盘（不能只活在内存黑板里）
    files = [Path(f) for f in (res.artifacts.get("meta_sop_files") or [])]
    print("A2 meta_sop_files=", [f.name for f in files])
    checks.append(("A2 五份文档落盘", len(files) == 5 and all(f.is_file() for f in files)))
    checks.append(("A2 文档非空", all(f.stat().st_size > 200 for f in files if f.is_file())))
    checks.append(("A2 报告为 json", any(f.suffix == ".json" and f.name.startswith("VERIFICATION")
                                        for f in files)))

    # ---- B. 编排器抛异常 -> 如实暴露失败 ----
    import virtu_omni.agent.swarm_orchestrator as so

    original = so.SwarmCommander.solve

    def _boom(self, task, output_dir=None):
        raise RuntimeError("worker 崩溃模拟")

    so.SwarmCommander.solve = _boom
    try:
        agent_b = _Agent()
        res_b = _solve_swarm(agent_b, "设计并加工复杂曲面", params=_task(),
                             output_dir=str(ROOT / "runs" / "swarm" / "entry_boom"))
    finally:
        so.SwarmCommander.solve = original
    print("B success=", res_b.success, "breaker=", res_b.circuit_breaker_tripped,
          "mode=", res_b.mode, "rcfa=", (res_b.rcfa_report or {}).get("root_cause"))
    checks.append(("B 失败不外溢", res_b.success is False))
    checks.append(("B 熔断标记", res_b.circuit_breaker_tripped is True))
    checks.append(("B RCFA 有根因", "worker 崩溃模拟" in str((res_b.rcfa_report or {}).get("root_cause"))))
    checks.append(("B mode 如实 SWARM", res_b.mode == "SWARM"))

    # ---- C. 编排器不可导入 -> 降级且诚实标注 ----
    saved = sys.modules.get("virtu_omni.agent.swarm_orchestrator")
    sys.modules["virtu_omni.agent.swarm_orchestrator"] = None  # import 会抛 ImportError
    try:
        agent_c = _Agent()
        res_c = _solve_swarm(agent_c, "任意任务", params=_task(),
                            require_real_swarm=True,
                            output_dir=str(ROOT / "runs" / "swarm" / "entry_unavail"))
    finally:
        if saved is None:
            sys.modules.pop("virtu_omni.agent.swarm_orchestrator", None)
        else:
            sys.modules["virtu_omni.agent.swarm_orchestrator"] = saved
    print("C success=", res_c.success, "mode=", res_c.mode,
          "requested=", res_c.requested_mode, "swarm_status=", res_c.metrics.get("swarm_status"),
          "require_real=", res_c.metrics.get("swarm_require_real"))
    checks.append(("C 降级 AUTONOMOUS", res_c.mode == "AUTONOMOUS"))
    checks.append(("C requested_mode=SWARM", res_c.requested_mode == "SWARM"))
    checks.append(("C require_real 时判失败", res_c.success is False))
    checks.append(("C 标注 unavailable", str(res_c.metrics.get("swarm_status", "")).startswith("unavailable")))

    # ---- D. 默认 design_stl（不传也能拿工作区成品）----
    agent_d = _Agent()
    res_d = _solve_swarm(agent_d, "闭式叶轮曲面加工",
                         params={"spindle_axis": "Z", "part_type": "铝合金闭式叶轮"},
                         output_dir=str(ROOT / "runs" / "swarm" / "entry_default_stl"))
    bb = (res_d.artifacts.get("swarm") or {}).get("blackboard_keys") or []
    print("D success=", res_d.success, "bb_keys=", len(bb))
    checks.append(("D 默认成品 STL 可用", res_d.success is True and "geometry" in bb))

    print("\n=== SWARM 入口测试 ===")
    all_pass = True
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        all_pass = all_pass and ok
    print("\n" + ("ALL PASS (%d/%d)" % (sum(1 for _, o in checks if o), len(checks))
                  if all_pass else "HAS FAILURES"))
    return 0 if all_pass else 1


def test_swarm_entry_contracts(swarm_workspace):
    assert SUPER_AGENT.is_file()
    assert not SUPER_AGENT.is_relative_to(swarm_workspace.root)
    assert _load_solve_swarm().__globals__["WORKSPACE_DIR"] == str(swarm_workspace.root)
    assert main() == 0
    swarm_workspace.assert_runs(expected_count=2)


if __name__ == "__main__":
    raise SystemExit(run_pytest_file(__file__))
