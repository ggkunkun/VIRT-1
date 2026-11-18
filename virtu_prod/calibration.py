# -*- coding: utf-8 -*-
"""V1 五轴标定：方位序列、枢轴偏置反算、判据评估。

口径：
  * 标准球心装在机床坐标 (100, 0, 50)（台面上方 150 mm，偏离 B 轴枢轴）；
  * 每个姿态 (B,C) 记录球心偏差 Δ（机床坐标，mm）；
  * 若枢轴存在偏置 e，则 Δ_i = (R_B(B_i)R_C(C_i) − I) · e，最小二乘反算 e，
    残差即 RTCP 误差；判据：残差 ≤0.05 mm（对应 OP2 最小设计面间隙 0.307 mm 的 1/2 预算）。
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

SPHERE_CENTER_MACHINE = (100.0, 0.0, 50.0)
B_ANGLES = (0.0, -15.0, 15.0, -30.0, 30.0)
C_ANGLES = (0.0, 90.0, 180.0, 270.0)
RTCP_LIMIT_MM = 0.05
ORIENT_LIMIT_MM = 0.05
REPEAT_LIMIT_MM = 0.005
THERMAL_LIMIT_MM = 0.020
BACKLASH_LIMIT_DEG = 0.010


def orientations() -> List[Tuple[float, float]]:
    return [(b, c) for b in B_ANGLES for c in C_ANGLES]


def rot_b(deg: float) -> np.ndarray:
    r = math.radians(deg)
    return np.array([[math.cos(r), 0.0, math.sin(r)],
                     [0.0, 1.0, 0.0],
                     [-math.sin(r), 0.0, math.cos(r)]])


def rot_c(deg: float) -> np.ndarray:
    r = math.radians(deg)
    return np.array([[math.cos(r), -math.sin(r), 0.0],
                     [math.sin(r), math.cos(r), 0.0],
                     [0.0, 0.0, 1.0]])


def sphere_positions() -> List[Dict]:
    out = []
    p = np.array(SPHERE_CENTER_MACHINE)
    for i, (b, c) in enumerate(orientations(), 1):
        mp = rot_b(b) @ (rot_c(c) @ p)
        out.append({"idx": i, "b": b, "c": c,
                    "machine": [round(float(v), 3) for v in mp]})
    return out


def estimate_pivot(samples: List[Dict]) -> Dict:
    """Δ_i = (R_i − I)e 的最小二乘反算。samples: b,c,dx,dy,dz。"""
    rows, rhs = [], []
    for s in samples:
        m = rot_b(s["b"]) @ rot_c(s["c"]) - np.eye(3)
        rows.append(m)
        rhs.append([s["dx"], s["dy"], s["dz"]])
    a = np.vstack(rows)
    bvec = np.concatenate([np.asarray(v, dtype=float) for v in rhs])
    e, *_ = np.linalg.lstsq(a, bvec, rcond=None)
    resid = bvec - a @ e
    per = resid.reshape(-1, 3)
    r_norm = np.linalg.norm(per, axis=1)
    return {"offset_mm": [round(float(v), 5) for v in e],
            "max_residual_mm": round(float(r_norm.max()), 5),
            "rms_residual_mm": round(float(np.sqrt((r_norm ** 2).mean())), 5),
            "n": len(samples), "basis": "measured (least squares)"}


def evaluate_rtcp(samples: List[Dict], limit: float = RTCP_LIMIT_MM) -> Dict:
    complete = [s for s in samples
                if all(s.get(k) is not None for k in ("b", "c", "dx", "dy", "dz"))]
    if len(complete) < 16:
        return {"status": "PENDING", "reason": f"complete_rows={len(complete)}/20",
                "n": len(complete)}
    est = estimate_pivot(complete)
    raw = max(math.sqrt(s["dx"] ** 2 + s["dy"] ** 2 + s["dz"] ** 2) for s in complete)
    ok = est["max_residual_mm"] <= limit
    return {"status": "PASS" if ok else "FAIL", "limit_mm": limit,
            "raw_max_mm": round(raw, 4), **est}


def evaluate_series(values: List[Optional[float]], limit: float, kind: str) -> Dict:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return {"status": "PENDING", "reason": f"{kind}: insufficient values"}
    spread = max(vals) - min(vals)
    return {"status": "PASS" if spread <= limit else "FAIL", "kind": kind,
            "n": len(vals), "spread": round(spread, 5), "limit": limit,
            "values": [round(v, 5) for v in vals]}


def evaluate_orientation(deviations: List[Optional[float]], diameter_mm: float = 50.0,
                         limit_deg: float = 0.05) -> Dict:
    """Ø50 端面打表：极差 δ(mm) -> 刀轴角偏差 atan(δ/50)；判据 ≤0.05°。"""
    vals = [v for v in deviations if v is not None]
    if len(vals) < 20:
        return {"status": "PENDING", "reason": f"orientation rows={len(vals)}/20"}
    angles = [math.degrees(math.atan(v / diameter_mm)) for v in vals]
    mx = max(angles)
    return {"status": "PASS" if mx <= limit_deg else "FAIL",
            "max_angle_deg": round(mx, 5), "limit_deg": limit_deg,
            "diameter_mm": diameter_mm, "n": len(vals)}


def evaluate_backlash(pairs: List[Tuple[Optional[float], Optional[float]]],
                      limit: float = BACKLASH_LIMIT_DEG) -> Dict:
    diffs = [abs(f - r) for f, r in pairs if f is not None and r is not None]
    if len(diffs) < 3:
        return {"status": "PENDING", "reason": "insufficient forward/reverse pairs"}
    return {"status": "PASS" if max(diffs) <= limit else "FAIL",
            "max_backlash_deg": round(max(diffs), 5), "limit": limit, "n": len(diffs)}


def _num(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def evaluate_evidence(evidence_dir: Path) -> Dict:
    d = Path(evidence_dir)
    out: Dict[str, Dict] = {}

    rt = read_csv(d / "U-06_rtcp_record.csv")
    samples = [{"idx": int(r.get("序号", 0) or 0), "b": _num(r.get("B(deg)")),
                "c": _num(r.get("C(deg)")), "dx": _num(r.get("ΔX(mm)")),
                "dy": _num(r.get("ΔY(mm)")), "dz": _num(r.get("ΔZ(mm)"))} for r in rt]
    out["U-06"] = evaluate_rtcp(samples) if rt else {"status": "PENDING", "reason": "no record"}

    se = read_csv(d / "U-07_siemens_orientation.csv")
    devs = [_num(r.get("指示表极差(mm)")) for r in se]
    out["U-07"] = (evaluate_orientation(devs) if se
                   else {"status": "PENDING", "reason": "no record"})

    rp = read_csv(d / "U-08_repeatability.csv")
    out["U-08-repeat"] = (evaluate_series([_num(r.get("刀长(mm)")) for r in rp],
                                          REPEAT_LIMIT_MM, "repeatability")
                          if rp else {"status": "PENDING", "reason": "no record"})

    th = read_csv(d / "U-08_thermal.csv")
    out["U-08-thermal"] = (evaluate_series([_num(r.get("Z(mm)")) for r in th],
                                           THERMAL_LIMIT_MM, "thermal")
                           if th else {"status": "PENDING", "reason": "no record"})

    bl = read_csv(d / "U-08_backlash.csv")
    pairs = [(_num(r.get("正向角(deg)")), _num(r.get("反向角(deg)"))) for r in bl]
    out["U-08-backlash"] = (evaluate_backlash(pairs) if bl
                            else {"status": "PENDING", "reason": "no record"})

    statuses = [v["status"] for v in out.values()]
    gate = "FAIL" if "FAIL" in statuses else ("PASS" if all(s == "PASS" for s in statuses)
                                              else "PENDING")
    return {"items": out, "gate": gate}
