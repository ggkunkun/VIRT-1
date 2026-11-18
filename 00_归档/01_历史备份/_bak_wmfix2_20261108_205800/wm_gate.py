#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wm_gate.py — 世界模型确定性判定层（把"阈值判定"从模型手里拿走）

实测依据（2026-11-07 探针）：13.63B 能算对数值（FOS=1.13、Ra=1.68 均在 8% 容差内），
但把 1.13 判成 fos_gate="FOS>=1.5_pass"、把 1.68μm 判成"粗加工"——即
**数值推理可用、规则连接不可用**。因此闸门/等级/Auto-Diff 颜色一律由本层按
确定阈值重算，schema 中不再让模型生成。

覆盖：
  fos_gate        : safety_factor >= 1.5 -> pass
  finish_class    : Ra<3.2 精加工 / <6.3 半精 / else 粗加工
  volume_conservation : delta_volume_mm3<0 -> pass
  autodiff        : gouge True -> red / collision_risk high -> yellow / else green
  tolerance_pass  : fit_clearance_mm >= 0（与 wm_verifier.recompute 同口径；
                    旧阈值 -0.005 是第二套定律， clearance∈[-0.005,0) 时与判分器冲突）
  fit_class       : 由 fit_clearance 与 tolerance_fit 推 H7/g6 | H7/js6 | H7/p6

闸门字面一律用契约短字面（pass/fail），与 wm_contract.KEY_SCHEMA / guard 同源；
长字面（FOS>=1.5_pass 等）只作历史语料兼容，由 normalize_gate 归一，本层不再产出。
"""
from __future__ import annotations
from typing import Any, Dict, Optional


def _f(ws: Dict[str, Any], k: str) -> Optional[float]:
    v = ws.get(k)
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def normalize(ws: Dict[str, Any]) -> Dict[str, Any]:
    """就地补全/纠正确定性判定字段，返回新 dict。"""
    if not isinstance(ws, dict):
        return ws
    out = dict(ws)
    # 1) FOS 闸门
    fos = _f(out, "safety_factor")
    if fos is not None:
        out["fos_gate"] = "pass" if fos >= 1.5 - 1e-12 else "fail"
    # 2) 粗糙度等级
    ra = _f(out, "surface_roughness_ra_um")
    if ra is not None:
        out["finish_class"] = "精加工" if ra < 3.2 else ("半精" if ra < 6.3 else "粗加工")
    # 3) 体积守恒
    dv = _f(out, "delta_volume_mm3")
    if dv is not None:
        out["volume_conservation"] = "pass" if dv < 0 else "fail"
        b, a = _f(out, "before_volume_mm3"), _f(out, "after_volume_mm3")
        if b is not None and a is not None and abs((b + dv) - a) > 1e-6:
            out["after_volume_mm3"] = round(b + dv, 3)  # 守恒式优先
    # 4) Auto-Diff 颜色
    if "gouge" in out or "collision_risk" in out:
        gouge = bool(out.get("gouge"))
        risk = str(out.get("collision_risk", "")).lower()
        out["autodiff"] = "red" if gouge else ("yellow" if risk in ("high", "medium") else "green")
        # collision_risk 是 L2 求解器按题面 Z 值算出的判定（需两个比较同时成立），
        # 旧实现只要 gouge=True 就无条件改写成 "high"，与 wm_verifier.recompute /
        # 定律卡 / 训练标签直接冲突：同一份输入，闸门把求解器判 "none" 的答案
        # 悄悄改成 "high"，护栏后评测必然误判。判定权归求解器，本层只推 autodiff。
    # 5) 公差配合
    clr = _f(out, "fit_clearance_mm")
    if clr is not None:
        if clr > 0.01:
            out["tolerance_fit"], out["fit_class"] = "间隙配合", "H7/g6"
        elif clr < -0.01:
            out["tolerance_fit"], out["fit_class"] = "过盈配合", "H7/p6"
        else:
            out["tolerance_fit"], out["fit_class"] = "过渡配合", "H7/js6"
        out["tolerance_pass"] = bool(clr >= 0.0)
    return out


def normalize_pred(pred: Any) -> Any:
    """对整条预测做归一化（world_state 内），保留其余键。"""
    if not isinstance(pred, dict):
        return pred
    ws = pred.get("world_state")
    if isinstance(ws, dict):
        p = dict(pred)
        p["world_state"] = normalize(ws)
        return p
    return pred


def _selftest() -> int:
    ok = 0
    cases = [
        ({"safety_factor": 1.13}, "fos_gate", "fail"),
        ({"safety_factor": 1.5}, "fos_gate", "pass"),
        ({"surface_roughness_ra_um": 1.68}, "finish_class", "精加工"),
        ({"surface_roughness_ra_um": 4.0}, "finish_class", "半精"),
        ({"surface_roughness_ra_um": 8.0}, "finish_class", "粗加工"),
        ({"delta_volume_mm3": -1200.0}, "volume_conservation", "pass"),
        ({"delta_volume_mm3": 5.0}, "volume_conservation", "fail"),
        ({"gouge": True, "collision_risk": "none"}, "autodiff", "red"),
        # 反证：判定权归求解器，闸门不得把 risk=none 悄悄改写成 high
        ({"gouge": True, "collision_risk": "none"}, "collision_risk", "none"),
        ({"gouge": False, "collision_risk": "high"}, "autodiff", "yellow"),
        ({"gouge": False, "collision_risk": "none"}, "autodiff", "green"),
        ({"fit_clearance_mm": 0.03}, "fit_class", "H7/g6"),
        ({"fit_clearance_mm": -0.03}, "fit_class", "H7/p6"),
        ({"fit_clearance_mm": 0.0}, "fit_class", "H7/js6"),
        # 反证：旧阈值 -0.005 会把这两条判 True，与 wm_verifier(>=0) 冲突
        ({"fit_clearance_mm": -0.003}, "tolerance_pass", False),
        ({"fit_clearance_mm": 0.0}, "tolerance_pass", True),
    ]
    for ws, k, want in cases:
        got = normalize(ws).get(k)
        if got == want:
            ok += 1
        else:
            print(f"[FAIL] {ws} -> {k}={got!r} want {want!r}")
    # 体积守恒自纠
    n = normalize({"delta_volume_mm3": -100.0, "before_volume_mm3": 5000.0, "after_volume_mm3": 4900.0})
    ok += int(n["after_volume_mm3"] == 4900.0)
    n2 = normalize({"delta_volume_mm3": -100.0, "before_volume_mm3": 5000.0, "after_volume_mm3": 4800.0})
    ok += int(n2["after_volume_mm3"] == 4900.0)
    total = len(cases) + 2
    print(f"[wm_gate] SELFTEST {ok}/{total} PASS")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
