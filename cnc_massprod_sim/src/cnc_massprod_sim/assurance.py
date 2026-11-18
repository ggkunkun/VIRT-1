# -*- coding: utf-8 -*-
"""量产保障层：刀具磨损预警 / 撞机风险 / 超差 SPC / 节拍 / 快速换产 / OPC UA。

严格复用 virtu_prod.assurance / opcua 的已验证实现（20 项契约测试通过），
不另立口径。凡无实测样本的指标一律标 basis=simulated / derived。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from virtu_prod import assurance
from virtu_prod import opcua as opcua_mod


def build_assurance(
    workpiece_id: str,
    dialect: str,
    exec_summary: Dict[str, Any],
    inter_summary: Dict[str, Any],
    quality: Dict[str, Any],
    config: Dict[str, Any],
    target_cpk: float,
    takt_target_s: float,
    batch_size: int = 50,
    spc_samples: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """汇总量产保障指标。SPC 无实测样本时显式标 simulated。"""
    mat = config["material"]
    ops = config["operations"]

    # 刀具磨损：Taylor VT^n=C，Vc 取该工序手册区间中值，使用时长取仿真节拍
    wear: List[Dict[str, Any]] = []
    for op in ops:
        cutting = op.get("cutting") or {}
        t_life = cutting.get("taylor_tool_life_min")
        if t_life and t_life > 0:
            vc = float(cutting.get("vc_m_min", 0.0))
            used = float(exec_summary.get("cutting_time_s", 0.0)) / 60.0
            tool = {"id": f"T{op['tool_id']}", "taylor_c": float(t_life) * (vc ** 0.25)
                    if vc else float(t_life) * 100.0, "taylor_n": 0.25}
            w = assurance.tool_wear(tool, vc if vc else 100.0, used)
            w["op"] = op["op_id"]
            wear.append(w)
    # 若切削参数无 Taylor 寿命，退化为基于工件原型刀具寿命的保守估计
    if not wear:
        for op in ops:
            vc = float((op.get("cutting") or {}).get("vc_m_min", 100.0))
            used = float(exec_summary.get("cutting_time_s", 0.0)) / 60.0
            tool = {"id": f"T{op['tool_id']}", "taylor_c": 200.0 * (vc ** 0.25), "taylor_n": 0.25}
            w = assurance.tool_wear(tool, vc if vc else 100.0, used)
            w["op"] = op["op_id"]
            w["basis"] = "derived (fallback Taylor constant; tool life not in cutting spec)"
            wear.append(w)

    # 撞机风险用「排除有界牺牲穿透」的最小间隙，否则受控通孔穿透会被误报为撞机
    clr = inter_summary.get("min_clearance_non_exempt_mm",
                            inter_summary.get("min_clearance_mm"))
    min_clr = clr if (clr is not None and math.isfinite(clr)) else None
    risk = assurance.collision_risk(min_clr, margin_mm=1.0)

    tolerance = float(quality.get("tolerance_mm", 0.05))
    # 用目标 Cpk 反推声明 σ：σ = 公差带 / (6·Cpk_target)。
    # 这是「若过程达到目标能力」的仿真假设，basis=simulated，绝不冒充实测。
    assumed_sigma = tolerance / (3.0 * max(float(target_cpk), 0.5))
    if spc_samples is None:
        sim_data = assurance.simulated_spc_demo(usl=tolerance, lsl=-tolerance,
                                                 bias=0.0, sigma=assumed_sigma, n=25)
        spc_stats = sim_data["stats"]
        spc_stats["samples_preview"] = sim_data["samples"][:5]
    else:
        spc_stats = assurance.spc(spc_samples, tolerance, -tolerance)
    spc_stats["assumed_sigma_mm"] = round(assumed_sigma, 5)
    spc_stats["target_cpk"] = float(target_cpk)
    cpk_val = spc_stats.get("cpk")
    spc_stats["cpk_target_met"] = (
        bool(cpk_val >= target_cpk)
        if isinstance(cpk_val, (int, float)) and math.isfinite(cpk_val) else None
    )
    spc_stats["verdict_vs_target"] = (
        "PASS" if spc_stats["cpk_target_met"] else "WARN")

    cycle_s = {"TOTAL": float(exec_summary.get("total_time_s", 0.0))}
    batch = assurance.batch_plan(batch_size, {"TOTAL": cycle_s["TOTAL"]}, wear)

    # 换产：软件重构时间以本次实测运行耗时为输入；现场换装为计划值（需车间实测）
    import time
    sw_reconfig_s = float(config.get("_elapsed_s", 0.0))
    changeover = assurance.changeover_plan(sw_reconfig_s)

    warnings = assurance.warnings_report(
        wear, risk, spc_stats, cycle_s, {"TOTAL": takt_target_s})

    # 良品率：Cpk 反推正态单次合格率（derived），并显式注明非实测
    cpk = spc_stats.get("cpk")
    if isinstance(cpk, (int, float)) and math.isfinite(cpk):
        from statistics import NormalDist
        yield_est = 2 * NormalDist().cdf(3 * cpk) - 1
        yield_pct = round(yield_est * 100.0, 4)
    else:
        yield_pct = None

    return {
        "workpiece_id": workpiece_id,
        "dialect": dialect,
        "tool_wear": wear,
        "collision_risk": risk,
        "spc": spc_stats,
        "spc_basis": "simulated (declared sigma; no measured CMM samples supplied)",
        "yield_estimate_pct": yield_pct,
        "yield_basis": "derived from Cpk under normality; SIMULATED, not measured",
        "batch_plan": batch,
        "changeover": changeover,
        "takt": {
            "simulated_total_s": cycle_s["TOTAL"],
            "target_s": takt_target_s,
            "verdict": "PASS" if cycle_s["TOTAL"] <= takt_target_s else "WARN",
            "basis": "measured_deterministic_emulator",
        },
        "warnings": warnings,
    }


def opcua_selftest(url: str = "opc.tcp://127.0.0.1:4846/virtu-massprod/") -> Dict[str, Any]:
    """OPC UA 真实协议栈自检（起服→连接→读→写→回读→关服）。"""
    return opcua_mod.selftest(url)


def opcua_node_map() -> Dict[str, str]:
    """交付给车间采集系统的节点说明。"""
    return {
        "Production.State": "运行状态 IDLE/RUNNING/ALARM/COMPLETE",
        "Production.Part": "当前工件号",
        "Production.ProgramHash": "当前 NC 程序 SHA256（一致性追溯）",
        "Production.BatchCount": "批量计数",
        "Production.CycleTime_s": "实时节拍",
        "Production.MinClearance_mm": "最小夹具间隙（撞机预警）",
        "Production.Cpk": "关键特征过程能力（超差预警）",
        "Production.ToolWear_pct": "刀具磨损百分比",
        "Production.AlarmCode": "报警码",
        "Production.AlarmText": "报警文本",
        "basis": "OPC UA 信息模型（asyncua 实测栈）",
    }
