# -*- coding: utf-8 -*-
"""capability_oracles.py — 新增能力的可证伪评测 oracle + GUI 成功诚实账本。

补齐审计发现的评测盲区（此前只有 FANUC 模板与解析 CAE，无以下取证）：
  1. 钣金套料利用率/重叠/包容 oracle（P1a，verify_nesting_layout）。
  2. 多控制器后处理坐标一致性 oracle（P1b，verify_coordinate_consistency）。
  3. 梁单元 FEA 解析交叉核验 oracle（P2，analyze_beam_fem）。
  4. GUI 桌面操作成功账本：从 input_audit.jsonl 实测输入门行为，但**任务成功**
     在没有真实批准运行 + 任务完成信号前一律 basis=unmeasured，绝不以 deny 日志冒充成功。

测量宪法 §8：每个 oracle 返回 basis=measured/unmeasured；空集判红；植入坏样本必须可证伪。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# ===========================================================================
# 1. GUI 桌面操作成功账本（诚实：输入门行为可测，任务成功未测）
# ===========================================================================
def gui_success_ledger(audit_path: Optional[str] = None) -> Dict[str, Any]:
    """从 desktop_input/input_audit.jsonl 实测输入门行为，GUI 任务成功标 unmeasured。

    输入门 allow/deny 是**可测**的（日志逐条计数）；但"GUI 任务成功"需要真实批准
    运行 + 任务完成信号，审计日志两者都不提供，故一律 unmeasured，禁止以 deny 冒充成功。
    """
    root = Path(__file__).resolve().parent.parent.parent
    path = Path(audit_path) if audit_path else root / "runs" / "desktop_input" / "input_audit.jsonl"
    events: List[Dict[str, Any]] = []
    read_error = None
    if path.is_file():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        except Exception as exc:
            read_error = str(exc)
    else:
        read_error = f"audit log not found: {path}"

    allow = sum(1 for e in events if e.get("event") == "allow")
    deny = sum(1 for e in events if e.get("event") == "deny")
    verdicts: Dict[str, int] = {}
    for e in events:
        code = e.get("verdict_code") or e.get("event") or "unknown"
        verdicts[code] = verdicts.get(code, 0) + 1

    return {
        "source": str(path),
        "read_error": read_error,
        "total_events": len(events),
        "input_gate_allow_count": allow,
        "input_gate_deny_count": deny,
        "verdict_code_counts": verdicts,
        "input_gate_basis": "measured" if not read_error else "unmeasured",
        # 任务成功：无批准运行 + 无任务完成信号 -> 永远 unmeasured（可证伪：deny 不得冒充成功）
        "gui_task_success": None,
        "gui_task_success_basis": "unmeasured",
        "note": ("输入门 allow/deny 为实测；GUI 任务成功需真实批准运行+任务完成信号，"
                 "审计日志不提供，故标 unmeasured。deny 日志绝不等于成功，也不等于失败。"),
    }


# ===========================================================================
# 2. 钣金套料 oracle（P1a）
# ===========================================================================
def nesting_oracle() -> Dict[str, Any]:
    """真形状套料：好布局判绿 + 植入重叠/超界坏样本判红（可证伪）。"""
    from virtu_omni.engine.sheetmetal_nesting_engine import (
        SheetMetalNestingEngine, SheetStock, NestingPart, verify_nesting_layout,
    )
    L = [(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40)]
    stock = SheetStock(length=50, width=70, edge_margin=5, kerf_spacing=0)
    parts = [NestingPart(part_id="L", length=40, width=40, quantity=2, contour=L)]
    layout = SheetMetalNestingEngine(stock=stock).optimize_nesting(parts)
    good = verify_nesting_layout(layout)

    # 植入坏样本：人为制造重叠 -> 必须判红
    bad = json.loads(json.dumps(layout))
    if bad.get("placed_items"):
        bad["placed_items"][0]["contour"] = bad["placed_items"][-1]["contour"]
    bad_gate = verify_nesting_layout(bad)

    passed = good["passed"] and not bad_gate["passed"]
    return {
        "oracle": "nesting_utilization_overlap_containment",
        "good_layout_passed": good["passed"],
        "planted_overlap_rejected": not bad_gate["passed"],
        "placed_count": layout.get("placed_count"),
        "utilization_pct": layout.get("overall_utilization_rate"),
        "recomputed_utilization_pct": good.get("recomputed_utilization_pct"),
        "passed": passed,
        "basis": "measured",
    }


# ===========================================================================
# 3. 多控制器后处理坐标一致性 oracle（P1b）
# ===========================================================================
def post_dialect_oracle() -> Dict[str, Any]:
    """同一 CL 在 FANUC/Siemens/Heidenhain 三方言下坐标逐点一致（可证伪）。"""
    from virtu_omni.engine.cnc_post_processor import (
        build_cl_from_spec, verify_coordinate_consistency, post_process, SUPPORTED_DIALECTS,
    )
    spec = {"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}
    prog = build_cl_from_spec(spec)
    coord = verify_coordinate_consistency(prog)
    per_dialect = {}
    for d in SUPPORTED_DIALECTS:
        res = post_process(prog, dialect=d)
        per_dialect[d] = {
            "status": res["status"],
            "dialect_gate_passed": res.get("dialect_gate", {}).get("passed"),
            "coord_gate_passed": res.get("coord_gate", {}).get("passed"),
        }
    all_passed = coord["passed"] and all(v["status"] == "passed" for v in per_dialect.values())
    return {
        "oracle": "post_dialect_coordinate_consistency",
        "coord_consistency_passed": coord["passed"],
        "per_dialect": per_dialect,
        "max_err_mm": {d: v.get("max_err_mm") for d, v in coord["per_dialect"].items()},
        "passed": all_passed,
        "basis": "measured",
    }


# ===========================================================================
# 4. 梁单元 FEA 交叉核验 oracle（P2）
# ===========================================================================
def fea_cross_check_oracle() -> Dict[str, Any]:
    """PyNite 悬臂梁 FEA 挠度/弯矩与解析解交叉核验（可证伪：坏 FEA 判红）。"""
    from virtu_omni.engine.universal_cae_engine import UniversalCAEEngine
    from virtu_omni.engine.universal_geometry_engine import PartFamily
    eng = UniversalCAEEngine()
    intent = {"family": PartFamily.ROTATIONAL_SHAFT.value,
              "spec": {"material": "Steel45", "d_outer": 53.0, "d_inner": 14.0,
                       "overall_len": 1000.0}}
    res = eng.analyze_beam_fem(intent, {"radial_load_n": 12000.0})
    available = res.get("status") != "unavailable"
    return {
        "oracle": "pynite_beam_fea_analytic_cross_check",
        "status": res.get("status"),
        "cross_check_passed": res.get("cross_check_passed"),
        "deflection_error_pct": res.get("deflection_error_pct"),
        "moment_error_pct": res.get("moment_error_pct"),
        "factor_of_safety": res.get("factor_of_safety"),
        "passed": bool(available and res.get("cross_check_passed")),
        "basis": res.get("basis", "unmeasured"),
    }


# ===========================================================================
# 5. 汇总取证
# ===========================================================================
def run_all_oracles(audit_path: Optional[str] = None) -> Dict[str, Any]:
    results = {
        "nesting": nesting_oracle(),
        "post_dialect": post_dialect_oracle(),
        "fea_cross_check": fea_cross_check_oracle(),
        "gui_success_ledger": gui_success_ledger(audit_path),
    }
    measurable = [results["nesting"], results["post_dialect"], results["fea_cross_check"]]
    return {
        "oracles": results,
        "all_measurable_oracles_passed": all(r["passed"] for r in measurable),
        "gui_task_success_basis": results["gui_success_ledger"]["gui_task_success_basis"],
    }


if __name__ == "__main__":
    import sys
    out = run_all_oracles()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out["all_measurable_oracles_passed"] else 1)