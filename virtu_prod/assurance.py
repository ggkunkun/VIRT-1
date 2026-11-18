# -*- coding: utf-8 -*-
"""量产保障：刀具磨损 / 撞机风险 / 超差预警 / SPC 一致性 / 快速换产。

诚实边界：
  * 磨损按 Taylor 模型由实测节拍推导（derived），不是刀具寿命试验数据。
  * SPC 的 Cp/Cpk 计算器接受实测样本；演示数据显式标 basis=simulated。
  * 换产时间分为“软件重构时间”（实测，秒级）与“现场换装时间”（计划值，需车间实测）。
"""
from __future__ import annotations

import hashlib
import math
from typing import Dict, List, Optional

import numpy as np


def program_hash(nc: str) -> str:
    return hashlib.sha256(nc.encode("utf-8")).hexdigest()


def tool_wear(tool: dict, vc_m_min: float, used_min: float) -> Dict:
    n, c = float(tool["taylor_n"]), float(tool["taylor_c"])
    life = c / (max(vc_m_min, 1e-6) ** n)
    ratio = used_min / life if life > 0 else 99.0
    level = "OK" if ratio < 0.8 else ("WARN" if ratio < 1.0 else "ALARM")
    return {"tool": tool["id"], "vc_m_min": round(vc_m_min, 1),
            "expected_life_min": round(life, 1), "used_min": round(used_min, 1),
            "wear_pct": round(ratio * 100.0, 1), "level": level,
            "parts_per_tool": int(max(1, math.floor(life / max(used_min, 1e-6)))),
            "basis": "derived (Taylor VT^n=C + measured cycle time)"}


def collision_risk(min_clearance_mm: Optional[float], margin_mm: float = 1.0) -> Dict:
    if min_clearance_mm is None:
        return {"level": "UNMEASURED", "clearance_mm": None}
    v = float(min_clearance_mm)
    if v < 0:
        level = "CRITICAL"
    elif v < margin_mm:
        level = "HIGH"
    elif v < max(3.0 * margin_mm, 3.0):
        level = "MEDIUM"
    else:
        level = "LOW"
    return {"level": level, "clearance_mm": round(v, 3), "margin_mm": margin_mm,
            "action": {"CRITICAL": "停机，修正刀路/夹具后再试切",
                       "HIGH": "降速并复核夹具与刀柄间隙",
                       "MEDIUM": "增加首件目视/探针确认",
                       "LOW": "按常规巡检"}[level]}


def spc(samples: List[float], usl: float, lsl: float, subgroup: int = 5,
        basis: str = "measured") -> Dict:
    x = np.asarray(samples, dtype=float)
    if len(x) < 2:
        return {"verdict": "INSUFFICIENT_SAMPLES", "n": int(len(x)), "basis": basis}
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    cp = (usl - lsl) / (6 * sd) if sd > 0 else float("inf")
    cpk = min(usl - mu, mu - lsl) / (3 * sd) if sd > 0 else float("inf")
    out = int(((x > usl) | (x < lsl)).sum())
    return {"n": int(len(x)), "mean": round(mu, 4), "sigma": round(sd, 4),
            "cp": round(cp, 2), "cpk": round(cpk, 2), "out_of_tolerance": out,
            "usl": usl, "lsl": lsl, "subgroup": subgroup,
            "verdict": "PASS" if cpk >= 1.33 and out == 0 else "WARN",
            "basis": basis}


def simulated_spc_demo(usl: float, lsl: float, bias: float = 0.0,
                       sigma: float = 0.008, n: int = 25, seed: int = 20261118) -> Dict:
    """演示用：按声明偏差/σ 生成样本。调用方必须传 basis=simulated 展示。"""
    rng = np.random.default_rng(seed)
    data = rng.normal(bias, sigma, n)
    return {"samples": [round(float(v), 4) for v in data],
            "stats": spc(data.tolist(), usl, lsl, basis="simulated")}


def batch_plan(batch_size: int, cycle_s: Dict[str, float], wear: List[Dict]) -> Dict:
    total_cycle = sum(cycle_s.values())
    parts_per_tool = min([w["parts_per_tool"] for w in wear]) if wear else 0
    tool_changes = math.ceil(batch_size / parts_per_tool) if parts_per_tool else 0
    machining_h = batch_size * total_cycle / 3600.0
    changeover_h = tool_changes * 0.15
    return {"batch_size": batch_size,
            "cycle_per_part_min": round(total_cycle / 60.0, 1),
            "parts_per_tool_change": parts_per_tool,
            "tool_changes": tool_changes,
            "machining_h": round(machining_h, 2),
            "tool_change_h": round(changeover_h, 2),
            "total_h": round(machining_h + changeover_h, 2),
            "consistency": "同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33）",
            "basis": "derived (cycle + Taylor wear)"}


CHANGEOVER_STEPS = [
    ("夹具/软爪更换与找正", 4.0),
    ("刀具装载与对刀（T1/T2）", 3.0),
    ("程序调用与刀补/零点写入", 2.0),
    ("空运行与首件试切（含 M01 检查）", 4.0),
    ("首件三坐标/目视确认", 1.5),
]


def changeover_plan(software_reconfig_s: float) -> Dict:
    on_site = sum(t for _, t in CHANGEOVER_STEPS)
    total = on_site + software_reconfig_s / 60.0
    return {"steps": [{"step": s, "planned_min": t} for s, t in CHANGEOVER_STEPS],
            "software_reconfig_s": round(software_reconfig_s, 2),
            "on_site_planned_min": round(on_site, 1),
            "total_min": round(total, 1),
            "target_min": 15.0,
            "verdict": "PASS" if total <= 15.0 else "WARN",
            "basis": "on-site=planned (需车间实测), software=measured"}


def warnings_report(wear: List[Dict], risk: Dict, spc_stats: Dict,
                    cycle_s: Dict[str, float], targets: Dict[str, float]) -> Dict:
    alerts = []
    for w in wear:
        if w["level"] != "OK":
            alerts.append({"type": "TOOL_WEAR", "tool": w["tool"], "level": w["level"],
                           "wear_pct": w["wear_pct"]})
    if risk["level"] in ("CRITICAL", "HIGH"):
        alerts.append({"type": "COLLISION_RISK", "level": risk["level"],
                       "clearance_mm": risk["clearance_mm"]})
    if spc_stats.get("verdict") == "WARN":
        alerts.append({"type": "OUT_OF_TOLERANCE", "cpk": spc_stats.get("cpk"),
                       "out": spc_stats.get("out_of_tolerance")})
    for op, t in cycle_s.items():
        tgt = targets.get(op)
        if tgt and t > tgt:
            alerts.append({"type": "CYCLE_TARGET", "op": op,
                           "actual_s": round(t, 1), "target_s": tgt})
    return {"alerts": alerts, "count": len(alerts), "basis": "derived + measured"}
