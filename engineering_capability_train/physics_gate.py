#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""physics_gate.py — 工程物理合规闸门 + 决策代价模型。

三层落地（数据层 / 训练层 / 评测层共用同一份实现，杜绝"训练时一套、评分时一套"）：
  L1 确定性约束：体积守恒、几何无矛盾、公差带非负、量纲上限、单位齐次
  L2 解析复算：复用 scripts/wm_verifier.py 的 recompute()/l1_check()/verify()
  L3 工程约束：FOS>=1.5、ISO 286 配合间隙/过盈符号、尺寸链极值法 >= RSS、
              G00 禁扎刀、Auto-Diff 红色过切即致命、主轴转速与粗糙度公式

代价模型（对应"选择最优且最快的解决方案"）：
    cost = estimated_time_s * (1 + risk_weight * risk)
    物理违规候选 cost = +inf，永不入选
    chosen 必须等于可行集合里 cost 的 argmin，否则 decision_optimality 判 0

反假绿条款（沿用 SKILLS_GAP_VERDICTS_2026-11-04 的教训）：
  * 材料未解析 -> 直接 violation，禁止静默回退到 Cr12MoV（曾使 FOS 虚高 2.4 倍）
  * 载荷键名不一致 -> 直接 violation，不猜测
  * FOS 未达标却返回 optimized=True -> violation
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence

from ect_common import load_config, load_workspace_module, resolve, log

# ---------------------------------------------------------------------------
# 权威真值来源：复用工作区既有 wm_verifier，缺失时降级为内置最小实现并显式告警
# ---------------------------------------------------------------------------
try:
    _WM = load_workspace_module("scripts/wm_verifier.py")
except Exception as _exc:  # pragma: no cover
    _WM = None
    print(f"[physics_gate][WARN] wm_verifier unavailable: {_exc}", flush=True)

# ISO 286 常用尺寸段查表值（单位 μm）：(上界 mm, IT6, IT7, g6 es, p6 es)
_ISO286 = (
    (3.0, 6, 10, -2, 6),
    (6.0, 8, 12, -4, 12),
    (10.0, 9, 15, -5, 15),
    (18.0, 11, 18, -6, 18),
    (30.0, 13, 21, -7, 22),
    (50.0, 16, 25, -9, 26),
    (80.0, 19, 30, -10, 32),
    (120.0, 22, 35, -12, 37),
    (180.0, 25, 40, -14, 43),
)
# 材料屈服强度 MPa 与密度 g/cm^3（只列工作区 MATERIAL_DATABASE 中确有定义的）
_MATERIALS = {
    "Cr12MoV": {"Sy": 850.0, "rho_g_cm3": 7.85},
    "Ti-6Al-4V": {"Sy": 880.0, "rho_g_cm3": 4.43},
    "AL7075-T6": {"Sy": 503.0, "rho_g_cm3": 2.81},
    "Steel45": {"Sy": 355.0, "rho_g_cm3": 7.85},
    "45": {"Sy": 355.0, "rho_g_cm3": 7.85},
    "SS304": {"Sy": 205.0, "rho_g_cm3": 7.93},
}
RHO_MAX = 60.0  # g/cm^3，锇 22.6，任何工程材料不可能超过，用于拦死 1000 倍量纲错


@dataclass
class Verdict:
    ok: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks: Dict[str, Any] = field(default_factory=dict)
    reference: Dict[str, Any] = field(default_factory=dict)
    level: str = "L1"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _iso_row(d: float):
    for row in _ISO286:
        if d <= row[0]:
            return row
    return _ISO286[-1]


def check_material(material: Any) -> Verdict:
    """材料必须显式解析；禁止静默回退默认值。"""
    v = Verdict(ok=True)
    if not material or str(material).strip() not in _MATERIALS:
        v.ok = False
        v.violations.append(
            f"材料未解析或不在材料库: {material!r}；禁止静默套用默认材料（会使 FOS 虚高）"
        )
        return v
    v.checks["material"] = str(material)
    v.reference.update(_MATERIALS[str(material)])
    return v


def check_parametric_model(spec: Dict[str, Any]) -> Verdict:
    """参数化建模策略的物理合规：几何矛盾 / 体积守恒 / FOS / 公差带。"""
    v = Verdict(ok=True, level="L1")
    d = spec.get("dimensions") or spec
    tol = 1e-6

    d_out = d.get("d_outer")
    d_in = d.get("d_inner") or d.get("d_bore")
    if d_out is not None and d_in is not None:
        if not (0 < float(d_in) < float(d_out)):
            v.ok = False
            v.violations.append(f"几何矛盾：内径 {d_in} 必须满足 0 < d_inner < d_outer({d_out})")
        else:
            v.checks["annulus_valid"] = True
    for k in ("d_outer", "d_inner", "d_bore", "overall_len", "width", "length"):
        if k in d and float(d[k]) <= 0:
            v.ok = False
            v.violations.append(f"尺寸 {k}={d[k]} 必须 > 0")

    # 体积守恒：after = before + ΔV，且切除 ΔV<0 / 凸台 ΔV>0
    if all(k in spec for k in ("before_volume_mm3", "delta_volume_mm3", "after_volume_mm3")):
        before = float(spec["before_volume_mm3"])
        delta = float(spec["delta_volume_mm3"])
        after = float(spec["after_volume_mm3"])
        slack = 1e-3 + 1e-3 * max(abs(before), abs(after), abs(delta))
        if abs(after - (before + delta)) > slack:
            v.ok = False
            v.violations.append(
                f"体积守恒失败：after({after}) != before({before}) + ΔV({delta})"
            )
        if spec.get("operation") == "cut" and delta >= 0:
            v.ok = False
            v.violations.append("切除特征 ΔV 必须 < 0")
        if spec.get("operation") == "boss" and delta <= 0:
            v.ok = False
            v.violations.append("凸台特征 ΔV 必须 > 0")
        v.checks["volume_conservation"] = v.ok
        v.reference["after_volume_mm3"] = before + delta

    # 密度/质量量纲守卫（1000 倍量纲错在此拦死）
    rho = (spec.get("inputs") or {}).get("rho_g_cm3") or spec.get("rho_g_cm3")
    if rho is not None:
        if float(rho) <= 0 or float(rho) > RHO_MAX:
            v.ok = False
            v.violations.append(f"密度 {rho} g/cm^3 超出物理上限 {RHO_MAX}（疑单位错）")
        elif "mass_g" in spec and "volume_mm3" in spec:
            implied = float(spec["mass_g"]) / (float(spec["volume_mm3"]) / 1000.0)
            if implied > RHO_MAX or abs(implied - float(rho)) / max(float(rho), 1e-9) > 0.08:
                v.ok = False
                v.violations.append(
                    f"质量-体积反推密度 {implied:.3f} g/cm^3 与声明 {rho} 不符"
                )
            else:
                v.checks["dimension_homogeneous"] = True

    # FOS >= 1.5（必须显式给载荷；缺载荷是 violation 不是猜测）
    if "safety_factor" in spec or "sigma_von_mises_mpa" in spec or "load_n" in spec:
        fos = spec.get("safety_factor")
        if fos is None:
            sigma = spec.get("sigma_von_mises_mpa")
            if sigma is None:
                v.ok = False
                v.violations.append("声明了强度校核但未提供 sigma_von_mises_mpa，拒绝猜测载荷")
            else:
                m = check_material(d.get("material") or spec.get("material"))
                if not m.ok:
                    v.violations.extend(m.violations)
                    v.ok = False
                else:
                    fos = m.reference["Sy"] / float(sigma) if float(sigma) > 0 else math.inf
        if fos is not None and float(fos) < 1.5 - tol:
            v.ok = False
            v.violations.append(f"安全系数 FOS={float(fos):.3f} < 1.5，不满足强度要求")
        if spec.get("optimized") is True and fos is not None and float(fos) < 1.5:
            v.ok = False
            v.violations.append("FOS 未达标却标记 optimized=True（假绿）")
        if fos is not None:
            v.reference["safety_factor"] = fos
            v.checks["fos_ok"] = float(fos) >= 1.5

    # 公差带非负
    if "upper_dev" in spec and "lower_dev" in spec:
        if float(spec["upper_dev"]) - float(spec["lower_dev"]) < -tol:
            v.ok = False
            v.violations.append("公差带为负：ES 必须 >= EI")
        else:
            v.checks["tolerance_band_nonnegative"] = True
    return v


def check_tolerance_fit(fit: Dict[str, Any]) -> Verdict:
    """ISO 286 配合语义：H7/g6 间隙、H7/h6 零间隙、H7/p6 过盈；尺寸链极值法 >= RSS。"""
    v = Verdict(ok=True, level="L3")
    d = float(fit.get("nominal_d_mm", 0) or 0)
    if d <= 0:
        v.ok = False
        v.violations.append("配合公称直径必须 > 0")
        return v
    _, it6, it7, g_es, p_es = _iso_row(d)
    hole = str(fit.get("hole", "H7")).upper()
    shaft = str(fit.get("shaft", "h6")).lower()

    EI = 0.0 if hole.startswith("H") else None
    if EI is None:
        v.warnings.append(f"非 H 孔制 {hole} 未做查表，仅做符号一致性校验")
        EI = 0.0
    ES = EI + (it7 if "7" in hole else it6)

    if shaft.startswith("h"):
        es, ei = 0.0, -it6
        expected = "clearance_or_line"
    elif shaft.startswith("g"):
        es, ei = float(g_es), float(g_es) - it6
        expected = "clearance"
    elif shaft.startswith("p"):
        es, ei = float(p_es), float(p_es) - it6
        expected = "interference"
    else:
        v.warnings.append(f"轴基本偏差 {shaft} 未查表，跳过符号判定")
        return v

    min_clear = EI - es          # 孔最小 - 轴最大
    max_clear = ES - ei          # 孔最大 - 轴最小
    if expected == "clearance" and not (min_clear > 0):
        v.ok = False
        v.violations.append(f"{hole}/{shaft} 应为间隙配合，但最小间隙 {min_clear} μm <= 0")
    if expected == "interference" and not (min_clear < 0):
        v.ok = False
        v.violations.append(f"{hole}/{shaft} 应为过盈配合，但最小间隙 {min_clear} μm >= 0")
    if expected == "clearance_or_line" and min_clear < 0:
        v.ok = False
        v.violations.append(f"{hole}/{shaft} 不应出现过盈，最小间隙 {min_clear} μm < 0")
    v.reference.update({
        "hole_ES_um": ES, "hole_EI_um": EI,
        "shaft_es_um": es, "shaft_ei_um": ei,
        "min_clearance_um": min_clear, "max_clearance_um": max_clear,
        "fit_class": expected, "IT6_um": it6, "IT7_um": it7,
    })

    tols = fit.get("chain_tolerances_mm")
    if tols:
        vals = [abs(float(x)) for x in tols]
        wc = sum(vals)
        rss = math.sqrt(sum(x * x for x in vals))
        v.reference.update({"worstcase_mm": wc, "rss_mm": rss})
        if wc + 1e-9 < rss:
            v.ok = False
            v.violations.append("尺寸链极值法累积公差必须 >= RSS 法（数学必然）")
        if fit.get("method") == "worstcase" and fit.get("chain_halfwidth_mm") is not None:
            if abs(float(fit["chain_halfwidth_mm"]) - wc) > 1e-6:
                v.ok = False
                v.violations.append("极值法封闭环半宽与 Σt 不符")
        if fit.get("method") == "rss" and fit.get("chain_halfwidth_mm") is not None:
            if abs(float(fit["chain_halfwidth_mm"]) - rss) > 1e-6:
                v.ok = False
                v.violations.append("RSS 法封闭环半宽与 sqrt(Σt²) 不符")
    return v


def check_toolpath(tp: Dict[str, Any]) -> Verdict:
    """G00 快速定位禁扎刀；Auto-Diff 红色过切为致命错误。"""
    v = Verdict(ok=True, level="L3")
    z_safe = float(tp.get("safe_plane_z_mm", 0))
    z_min = float(tp.get("rapid_min_z_mm", tp.get("g00_min_z_mm", z_safe)))
    stock_top = float(tp.get("stock_top_z_mm", 0))
    if z_min < stock_top:
        v.ok = False
        v.violations.append(
            f"G00 扎刀：快速最低点 Z={z_min} 低于毛坯顶面 {stock_top}，必须 >= 安全平面 {z_safe}"
        )
    elif z_safe > 0 and z_min < z_safe:
        v.warnings.append(f"G00 最低点 {z_min} 低于安全平面 {z_safe}，建议抬刀")
    autodiff = str(tp.get("autodiff", "")).lower()
    if autodiff == "red":
        v.ok = False
        v.violations.append("VERICUT Auto-Diff 红色 = 过切，致命，必须停止并修复刀路")
    v.reference.update({"safe_plane_z_mm": z_safe, "rapid_min_z_mm": z_min,
                        "stock_top_z_mm": stock_top,
                        "autodiff": autodiff or ("green" if z_min >= stock_top else "red")})
    return v


def check_process(params: Dict[str, Any]) -> Verdict:
    """切削参数解析复算：n=1000Vc/(πD)、Vf=fz·z·n、Ra=f²/(8r)、MRR。"""
    v = Verdict(ok=True, level="L2")
    try:
        D = float(params["D"]); vc = float(params["vc"])
        fz = float(params.get("fz", params.get("f", 0)))
        z = float(params.get("z", 1)); ap = float(params.get("ap", 1))
        r_eps = float(params.get("r_eps", 0.8))
    except (KeyError, TypeError, ValueError) as exc:
        v.warnings.append(f"切削参数不全，跳过解析复算: {exc}")
        return v
    if min(D, vc, ap, r_eps) <= 0:
        v.ok = False
        v.violations.append("D / vc / ap / r_eps 必须 > 0")
        return v
    n = 1000.0 * vc / (math.pi * D)
    vf = fz * z * n
    ra = 1000.0 * fz * fz / (8.0 * r_eps)
    mrr = ap * fz * vc * 1000.0
    v.reference = {"spindle_rpm": n, "feed_rate_mm_per_min": vf,
                   "surface_roughness_ra_um": ra, "mrr_mm3_per_min": mrr}
    declared = params.get("declared") or {}
    for key, ref in v.reference.items():
        if key in declared and abs(float(declared[key]) - ref) / max(abs(ref), 1e-9) > 0.08:
            v.ok = False
            v.violations.append(f"{key} 声明值 {declared[key]} 与解析复算 {ref:.4f} 偏差 > 8%")
    if "n_max" in params and n > float(params["n_max"]):
        v.ok = False
        v.violations.append(f"所需转速 {n:.0f} r/min 超过机床上限 {params['n_max']}")
    return v


# ---------------------------------------------------------------------------
# 决策代价模型：最优 + 最快
# ---------------------------------------------------------------------------
def candidate_cost(cand: Dict[str, Any], scenario: Dict[str, Any],
                   risk_weight: float = 0.5) -> float:
    """物理违规 -> +inf；否则 time * (1 + risk_weight * risk)。"""
    if cand.get("physics_ok") is False:
        return math.inf
    verdict = gate_decision(cand, scenario)
    if not verdict.ok:
        return math.inf
    t = float(cand.get("estimated_time_s", 0) or 0)
    risk = float(cand.get("risk", 0) or 0)
    if t <= 0:
        return math.inf
    return t * (1.0 + risk_weight * risk)


def best_candidate(candidates: Sequence[Dict[str, Any]], scenario: Dict[str, Any],
                   risk_weight: float = 0.5) -> Optional[str]:
    """返回可行集合里代价最小的候选 id；全不可行返回 None。"""
    scored = [(candidate_cost(c, scenario, risk_weight), str(c.get("id")))
              for c in candidates]
    finite = [(c, cid) for c, cid in scored if math.isfinite(c)]
    if not finite:
        return None
    return min(finite, key=lambda x: (x[0], x[1]))[1]


def gate_decision(decision: Dict[str, Any], scenario: Dict[str, Any]) -> Verdict:
    """裁决一条建模/工艺决策：合并所有适用的物理检查。"""
    v = Verdict(ok=True)
    def _merge(other: Verdict, tag: str) -> None:
        if not other.ok:
            v.ok = False
        v.violations.extend(f"[{tag}] {x}" for x in other.violations)
        v.warnings.extend(f"[{tag}] {x}" for x in other.warnings)
        for k, val in other.checks.items():
            v.checks[f"{tag}.{k}"] = val
        for k, val in other.reference.items():
            v.reference[f"{tag}.{k}"] = val

    if decision.get("physics_ok") is False:
        v.ok = False
        v.violations.append("决策被显式标记为物理违规")
    if "material" in decision and decision["material"] is not None:
        _merge(check_material(decision["material"]), "material")
    if decision.get("model_spec"):
        _merge(check_parametric_model(decision["model_spec"]), "model")
    if decision.get("fit"):
        _merge(check_tolerance_fit(decision["fit"]), "fit")
    if decision.get("toolpath"):
        _merge(check_toolpath(decision["toolpath"]), "toolpath")
    if decision.get("process_params"):
        _merge(check_process(decision["process_params"]), "process")

    # L2：若场景带 (task, inputs) 且决策给了 world_state，调用工作区权威复算
    ws = decision.get("world_state")
    if ws and _WM is not None and scenario.get("task"):
        try:
            out = _WM.verify({"world_state": ws}, scenario)
            if out.get("action") in ("reject_L1", "escalate_solver", "correct_with_reference"):
                v.ok = False
                for issue in out.get("issues", []):
                    v.violations.append(f"[wm_verifier:{out['action']}] {issue}")
            else:
                v.checks["wm_verifier"] = out.get("action")
            v.reference["wm_verifier"] = out.get("reference", {})
        except Exception as exc:  # pragma: no cover
            v.warnings.append(f"wm_verifier 调用异常: {exc}")
    return v


def gate_record(record: Dict[str, Any]) -> Verdict:
    """语料 / 评测记录统一入口。"""
    scenario = record.get("scenario") or {}
    decision = record.get("decision") or record.get("output_parsed") or {}
    if not isinstance(decision, dict):
        return Verdict(ok=False, violations=["decision 不是 JSON 对象，无法做物理校验"])
    return gate_decision(decision, scenario)


# ---------------------------------------------------------------------------
# 自检：正例必须通过，每类负例必须被拦下（反假绿回归）
# ---------------------------------------------------------------------------
def selftest() -> int:
    cases = []

    def check(name: str, got: bool, expected: bool, detail: str = "") -> None:
        cases.append((name, got, expected, detail))

    good_model = {"dimensions": {"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0,
                                 "material": "Cr12MoV"},
                  "before_volume_mm3": 100000.0, "delta_volume_mm3": -1571.0,
                  "after_volume_mm3": 98429.0, "operation": "cut",
                  "sigma_von_mises_mpa": 200.0}
    r = check_parametric_model(good_model)
    check("参数化模型正例", r.ok, True, str(r.violations))
    check("FOS 自动复算 >= 1.5", bool(r.reference.get("safety_factor", 0) >= 1.5), True)

    bad = dict(good_model, dimensions={"d_outer": 14.0, "d_inner": 53.0,
                                       "material": "Cr12MoV"})
    check("几何矛盾被拦", check_parametric_model(bad).ok, False)
    bad2 = dict(good_model, after_volume_mm3=123456.0)
    check("体积不守恒被拦", check_parametric_model(bad2).ok, False)
    bad3 = dict(good_model, material="Unobtainium")
    check("材料未解析不被静默放行", check_material(bad3.get("material")).ok, False)
    bad4 = dict(good_model, sigma_von_mises_mpa=800.0)
    r4 = check_parametric_model(bad4)
    check("FOS<1.5 被拦", r4.ok, False, str(r4.violations))
    bad5 = dict(good_model, rho_g_cm3=7850.0, mass_g=785000.0, volume_mm3=100000.0)
    check("1000 倍量纲错被拦", check_parametric_model(bad5).ok, False)

    r = check_tolerance_fit({"nominal_d_mm": 40.0, "hole": "H7", "shaft": "g6",
                             "chain_tolerances_mm": [0.1, 0.2, 0.15],
                             "method": "worstcase", "chain_halfwidth_mm": 0.45})
    check("H7/g6 间隙配合正例", r.ok, True, str(r.violations))
    check("尺寸链极值法 >= RSS",
          bool(r.reference.get("worstcase_mm", 0) >= r.reference.get("rss_mm", 1)), True)
    check("H7/p6 判为过盈",
          check_tolerance_fit({"nominal_d_mm": 40.0, "hole": "H7", "shaft": "p6"})
          .reference.get("min_clearance_um", 1) < 0, True)
    check("RSS 数值错误被拦",
          check_tolerance_fit({"nominal_d_mm": 30.0, "hole": "H7", "shaft": "h6",
                              "chain_tolerances_mm": [0.1, 0.2], "method": "rss",
                              "chain_halfwidth_mm": 0.9}).ok, False)

    check("G00 扎刀被拦",
          check_toolpath({"safe_plane_z_mm": 5.0, "rapid_min_z_mm": -1.0,
                          "stock_top_z_mm": 0.0}).ok, False)
    check("Auto-Diff 红色致命",
          check_toolpath({"safe_plane_z_mm": 5.0, "rapid_min_z_mm": 6.0,
                          "stock_top_z_mm": 0.0, "autodiff": "red"}).ok, False)
    check("安全刀路通过",
          check_toolpath({"safe_plane_z_mm": 5.0, "rapid_min_z_mm": 6.0,
                          "stock_top_z_mm": 0.0}).ok, True)

    rp = check_process({"D": 20.0, "vc": 100.0, "fz": 0.1, "z": 4, "ap": 2.0,
                        "r_eps": 0.8, "n_max": 2000})
    check("切削公式无超转速", rp.ok, True, str(rp.violations))
    check("n=1000Vc/piD 复算",
          abs(rp.reference["spindle_rpm"] - 1000 * 100 / (math.pi * 20)) < 1e-6, True)
    check("超机床转速被拦",
          check_process({"D": 20.0, "vc": 100.0, "fz": 0.1, "ap": 2.0,
                         "r_eps": 0.8, "n_max": 1000}).ok, False)

    cands = [
        {"id": "slow", "estimated_time_s": 120.0, "risk": 0.1},
        {"id": "fast", "estimated_time_s": 45.0, "risk": 0.1},
        {"id": "violating", "estimated_time_s": 1.0, "risk": 0.0, "physics_ok": False},
    ]
    check("最优且最快 = argmin(cost)", best_candidate(cands, {}) == "fast", True)
    check("全不可行返回 None",
          best_candidate([{"id": "x", "estimated_time_s": 1.0, "physics_ok": False}], {}) is None,
          True)

    failed = [c for c in cases if c[1] != c[2]]
    for name, got, exp, detail in cases:
        print(f"[{'PASS' if got == exp else 'FAIL'}] {name}" + (f"  {detail}" if detail and got != exp else ""))
    print(f"\n[selftest] {len(cases) - len(failed)}/{len(cases)} passed")
    return 0 if not failed else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程物理合规闸门")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--record", help="待校验的 JSON 记录文件")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.record:
        with open(args.record, encoding="utf-8") as f:
            rec = json.load(f)
        print(json.dumps(gate_record(rec).as_dict(), ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
