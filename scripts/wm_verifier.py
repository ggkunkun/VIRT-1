#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 运行时校验器（Verifier Ladder）—— LLM 草案的"世界模型更正"执行件
=========================================================================
三级验证阶梯（快→慢、便宜→贵），只在高风险/大分歧时才升级到真求解器：

  L1 确定性检查（零成本，必过）：
      schema/必需字段/单位键/守恒律(ΔV<0, after=before+ΔV)/数值边界(>0)
  L2 世界模型/解析求解器复算（毫秒级）：
      用精确公式重算参考值，与 LLM 声称值逐字段比对（REL_TOL=8%）
  L3 真求解器升级（分钟级）：
      L2 超差且高风险时，建议升级到 numpy FEM / SW / AutoCAD / VERICUT 取真值

输出结构：
  {ok, level, action, issues[], reference{}, corrected_world_state{}, note}

action ∈ {accept, correct_with_reference, reject_L1, escalate_solver}

用法：
  python scripts/wm_verifier.py --selftest
  python scripts/wm_verifier.py --scenario scen.json --out llm_out.json
"""
import os
import sys
import json
import math
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from distill_local_solver import mass_props_csg
except Exception:  # pragma: no cover
    mass_props_csg = None

REL_TOL = 0.08


# ----------------------------------------------------------------------------
# 精确复算（L2 的"世界模型/参考求解器"）
# ----------------------------------------------------------------------------
def recompute(scenario):
    """根据结构化场景重算参考世界状态（返回与 world_state 同名的字典型）。"""
    task = scenario.get("task")
    s = scenario.get("inputs", scenario)

    if task == "removal":
        doc, woc, vf = s["doc"], s["woc"], s["vf"]
        L, rho, stock_vol = s["L"], s["rho"], s["stock_vol"]
        removed = doc * woc * L
        mrr = doc * woc * vf
        removed_mass = removed * rho
        remaining = max(0.0, stock_vol * rho - removed_mass)
        return {
            "material_removed_mm3": removed,
            "mrr_mm3_per_min": mrr,
            "removed_mass_g": removed_mass,
            "resulting_mass_g": remaining,
            "delta_volume_mm3": -removed,
        }

    if task == "roughness":
        f, r_eps = s["f"], s["r_eps"]
        return {"surface_roughness_ra_um": 1000.0 * f * f / (8.0 * r_eps)}

    if task == "fea_fos":
        Sy, sigma = s["Sy"], s["sigma"]
        fos = Sy / sigma if sigma > 0 else float("inf")
        return {
            "peak_von_mises_mpa": sigma,
            "safety_factor": fos,
            "fos_gate": "PASS" if fos >= 1.5 else "FAIL",
        }

    if task == "collision":
        z_safe, z_min, stock_top = s["z_safe"], s["z_min_rapid"], s["stock_top"]
        risk = (z_min < z_safe) and (z_min < stock_top + 1.0)
        gouge = z_min < stock_top
        return {
            "safe_plane_z_mm": z_safe,
            "rapid_min_z_mm": z_min,
            "stock_top_z_mm": stock_top,
            "collision_risk": "high" if risk else "none",
            "gouge": bool(gouge),
            "autodiff": "red" if gouge else ("yellow" if risk else "green"),
        }

    if task == "tolerance":
        tols = s["tols"]
        wc = sum(tols)
        rss = math.sqrt(sum(t * t for t in tols))
        clearance = s["upper_dev"] - s["lower_dev"]
        return {
            "closed_loop_worstcase_halfwidth_mm": wc,
            "closed_loop_rss_halfwidth_mm": rss,
            "fit_clearance_mm": clearance,
        }

    if task == "geom_delta":
        feat, before = s["feature_vol"], s["before"]
        return {
            "feature_volume_mm3": feat,
            "delta_volume_mm3": -feat,
            "before_volume_mm3": before,
            "after_volume_mm3": before - feat,
        }

    if task == "mass_props":
        if mass_props_csg is None:
            return {}
        V, (cx, cy, cz), (Ix, Iy, Iz) = mass_props_csg(s["shape"], s["params"], s["rho"])
        return {
            "volume_mm3": V,
            "mass_g": V * s["rho"],
            "centroid_mm": [cx, cy, cz],
            "inertia_ixx_mm4": Ix,
            "inertia_izz_mm4": Iz,
        }

    if task == "design":
        r_out, r_bore = s["r_out"], s["r_bore"]
        t, n, r_hole, rho = s["t"], s["n_holes"], s["r_hole"], s["rho"]
        V = math.pi * (r_out ** 2 - r_bore ** 2) * t - n * math.pi * r_hole ** 2 * t
        return {"volume_mm3": V, "mass_g": V * rho, "mass_kg": V * rho / 1000.0}

    if task == "process":
        D, L, ap, f, vc, r_eps = s["D"], s["L"], s["ap"], s["f"], s["vc"], s["r_eps"]
        n = 1000.0 * vc / (math.pi * D)
        feed = f * n
        return {
            "spindle_rpm": n,
            "feed_rate_mm_per_min": feed,
            "mrr_mm3_per_min": ap * f * vc * 1000.0,
            "surface_roughness_ra_um": 1000.0 * f * f / (8.0 * r_eps),
            "cut_time_min": (L / feed) if feed > 0 else 0.0,
        }

    if task == "adapt_material":
        Sy, sigma = s["Sy"], s["sigma"]
        return {"safety_factor": Sy / sigma if sigma > 0 else float("inf")}

    if task == "adapt_machine":
        D, vc, n_max = s["D"], s["vc"], s["n_max"]
        n = 1000.0 * vc / (math.pi * D)
        return {"required_spindle_rpm": n, "within_limit": bool(n <= n_max)}

    return {}


# ----------------------------------------------------------------------------
# L1 确定性检查
# ----------------------------------------------------------------------------
REQUIRED = {
    "removal": ["material_removed_mm3", "mrr_mm3_per_min", "delta_volume_mm3"],
    "roughness": ["surface_roughness_ra_um"],
    "fea_fos": ["safety_factor"],
    "collision": ["collision_risk", "gouge", "autodiff"],
    "tolerance": ["closed_loop_worstcase_halfwidth_mm", "closed_loop_rss_halfwidth_mm"],
    "geom_delta": ["delta_volume_mm3", "after_volume_mm3"],
    "mass_props": ["volume_mm3", "mass_g"],
    "design": ["volume_mm3", "mass_g"],
    "process": ["spindle_rpm", "mrr_mm3_per_min", "surface_roughness_ra_um"],
    "adapt_material": ["safety_factor"],
    "adapt_machine": ["required_spindle_rpm", "within_limit"],
}

POSITIVE = {
    "mrr_mm3_per_min", "removed_mass_g", "resulting_mass_g", "surface_roughness_ra_um",
    "safety_factor", "volume_mm3", "mass_g", "mass_kg", "spindle_rpm",
    "feed_rate_mm_per_min", "cut_time_min", "required_spindle_rpm",
}


# ----------------------------------------------------------------------------
# L1-b 量纲一致性（纯物理约束，不依赖题面额外字段）
# ----------------------------------------------------------------------------
# 实测证据：virtu-wm-v3 在 removal 族把题面给的密度 7.8 g/cm^3 直接当 g/mm^3 用，
# 算出 35150 g（正确 35.15 g），偏差 1000 倍。这是 Q4 小模型最典型的量纲错。
# 自然界密度最大的金属锇为 22.6 g/cm^3，任何工程材料都不可能超过 60，
# 因此用「质量/体积 反推有效密度 > 60」作为绝对不可能判据，零误伤。
RHO_MAX_PHYSICAL = 60.0  # g/cm^3

MASS_FIELDS = ("resulting_mass_g", "removed_mass_g", "mass_g")
# 关键：质量字段必须配正确的体积，否则会把正确结果误判为量纲错。
#   resulting_mass_g（余下质量）= 工件总体积 × rho  -> 配总体积
#   removed_mass_g  （去除质量）= 去除体积 × rho    -> 配 material_removed_mm3
#   mass_g          （零件质量）= 零件体积 × rho    -> 配 volume_mm3
PAIR_MAP = {
    "resulting_mass_g": ("volume_mm3", "after_volume_mm3", "before_volume_mm3",
                         "blank_volume_mm3", "volume_after_mm3"),
    "removed_mass_g": ("material_removed_mm3",),
    "mass_g": ("volume_mm3", "after_volume_mm3", "before_volume_mm3", "blank_volume_mm3"),
}
SCEN_VOL_KEYS = ("stock_vol", "blank_volume_mm3", "volume_mm3", "blank_vol", "v0")


def _as_pos_float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def dimension_check(ws, scenario=None):
    """用 质量/体积 反推有效密度，超出物理上限即判量纲错。"""
    issues = []
    if not isinstance(ws, dict):
        return issues

    scen_vol = None
    if scenario:
        inp = scenario.get("inputs") or {}
        for k in SCEN_VOL_KEYS:
            v = _as_pos_float(inp.get(k))
            if v is not None:
                scen_vol = (f"inputs.{k}", v)
                break

    for mk in MASS_FIELDS:
        if mk not in ws:
            continue
        mv = _as_pos_float(ws[mk])
        if mv is None:
            continue
        cand = None
        for vk in PAIR_MAP[mk]:
            v = _as_pos_float(ws.get(vk))
            if v is not None:
                cand = (vk, v)
                break
        if cand is None and mk == "resulting_mass_g":
            cand = scen_vol
        if cand is None:
            continue
        vk, vv = cand
        rho_eff = mv / (vv / 1000.0)  # g/mm^3 -> g/cm^3
        if rho_eff > RHO_MAX_PHYSICAL:
            issues.append(
                f"量纲错误：{mk}={mv:g} g 与 {vk}={vv:g} mm^3 反推密度 "
                f"{rho_eff:g} g/cm^3，超过物理上限 {RHO_MAX_PHYSICAL:g} "
                f"（约 {rho_eff / 7.85:.0f} 倍于钢，疑将 g/cm^3 当 g/mm^3）"
            )
    return issues


def l1_check(ws, scenario):
    issues = []
    if not isinstance(ws, dict):
        return ["world_state 不是 JSON 对象"]
    if ws.get("invalid") is True or ws.get("world_state") is None and ws.get("invalid"):
        # 显式 invalid 是合法的（用于非法输入）
        return []
    task = scenario.get("task")
    for k in REQUIRED.get(task, []):
        if k not in ws:
            issues.append(f"缺少必需字段 {k}")
    # 守恒
    if task in ("removal", "geom_delta") and "delta_volume_mm3" in ws:
        try:
            if not (float(ws["delta_volume_mm3"]) < 0):
                issues.append("ΔV 必须 <0（切除为负）")
        except Exception:
            issues.append("ΔV 非数值")
    if task == "geom_delta" and all(k in ws for k in ("after_volume_mm3", "before_volume_mm3", "delta_volume_mm3")):
        try:
            before = float(ws["before_volume_mm3"])
            after = float(ws["after_volume_mm3"])
            delta = float(ws["delta_volume_mm3"])
            # The contract asks for 3-4 significant digits, so an absolute 1e-3 slack would
            # reject a correctly rounded state (25000 - 1571 != 23430). Slack must scale with
            # the magnitudes; real conservation breaks are orders of magnitude, not 0.1%.
            slack = 1e-3 + 1e-3 * max(abs(before), abs(after), abs(delta))
            if abs(after - (before + delta)) > slack:
                issues.append("体积守恒失败: after != before + ΔV")
        except Exception:
            pass
    # 正数边界
    for k in POSITIVE:
        if k in ws:
            try:
                if float(ws[k]) <= 0:
                    issues.append(f"{k} 必须 >0")
            except Exception:
                issues.append(f"{k} 非数值")
    # 量纲一致性（1000 倍量纲错在此拦死，不让它进 L2/L3）
    issues.extend(dimension_check(ws, scenario))
    return issues


# ----------------------------------------------------------------------------
# L2 复算比对
# ----------------------------------------------------------------------------
def _cmp_numeric(pred, ref, tol=REL_TOL):
    mism = []
    for k, rv in ref.items():
        if k not in pred:
            continue
        pv = pred[k]
        if isinstance(rv, bool) or isinstance(pv, bool):
            if bool(pv) != bool(rv):
                mism.append({"field": k, "pred": pv, "ref": rv, "type": "bool"})
            continue
        if isinstance(rv, (int, float)) and isinstance(pv, (int, float)):
            denom = max(abs(rv), 1e-9)
            rel = abs(pv - rv) / denom
            if rel > tol:
                mism.append({"field": k, "pred": pv, "ref": rv, "rel_err": round(rel, 4)})
        elif isinstance(rv, str) and isinstance(pv, str):
            if pv != rv:
                mism.append({"field": k, "pred": pv, "ref": rv, "type": "str"})
    return mism


def verify(llm_out, scenario, high_stakes=False):
    """主入口：输入 LLM 输出（含 world_state）与结构化场景，返回裁决。"""
    ws = llm_out.get("world_state", llm_out) if isinstance(llm_out, dict) else None
    if ws is None:
        return {"ok": False, "level": "L1", "action": "reject_L1",
                "issues": ["无法解析 world_state"], "reference": {}, "corrected_world_state": None}

    l1 = l1_check(ws, scenario)
    if l1:
        return {"ok": False, "level": "L1", "action": "reject_L1",
                "issues": l1, "reference": {}, "corrected_world_state": None}

    ref = recompute(scenario)
    mism = _cmp_numeric(ws, ref)
    if not mism:
        return {"ok": True, "level": "L2", "action": "accept",
                "issues": [], "reference": ref, "corrected_world_state": ws}

    if high_stakes:
        return {"ok": False, "level": "L3", "action": "escalate_solver",
                "issues": mism, "reference": ref, "corrected_world_state": None,
                "note": "L2 超差且高风险，建议升级 numpy FEM / SW / AutoCAD / VERICUT 取真值"}

    corrected = dict(ws)
    corrected.update(ref)
    return {"ok": False, "level": "L2", "action": "correct_with_reference",
            "issues": mism, "reference": ref, "corrected_world_state": corrected}


# ----------------------------------------------------------------------------
# 自检
# ----------------------------------------------------------------------------
def _approx(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def selftest():
    ok_all = True
    # 1) removal：正确草案 -> accept
    scen = {"task": "removal", "inputs": {"doc": 2.0, "woc": 5.0, "vf": 400.0,
                                           "L": 100.0, "rho": 7.85e-3, "stock_vol": 200000.0}}
    ref = recompute(scen)
    good = {"world_state": ref}
    r = verify(good, scen)
    exp = r["action"] == "accept"
    print(f"[{'PASS' if exp else 'FAIL'}] removal accept -> {r['action']}")
    ok_all &= exp

    # 2) removal：错误草案 -> correct_with_reference
    bad_ws = dict(ref)
    bad_ws["mrr_mm3_per_min"] = ref["mrr_mm3_per_min"] * 1.4
    r = verify({"world_state": bad_ws}, scen)
    exp = r["action"] == "correct_with_reference" and _approx(
        r["corrected_world_state"]["mrr_mm3_per_min"], ref["mrr_mm3_per_min"], 1e-9)
    print(f"[{'PASS' if exp else 'FAIL'}] removal correct -> {r['action']}")
    ok_all &= exp

    # 3) L1 守恒违规
    bad2 = {"world_state": dict(ref, delta_volume_mm3=+ref["material_removed_mm3"])}
    r = verify(bad2, scen)
    exp = r["action"] == "reject_L1"
    print(f"[{'PASS' if exp else 'FAIL'}] L1 conservation -> {r['action']}")
    ok_all &= exp

    # 4) fea_fos
    scen2 = {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 200.0}}
    ref2 = recompute(scen2)
    r = verify({"world_state": ref2}, scen2)
    exp = r["action"] == "accept" and _approx(ref2["safety_factor"], 1.775)
    print(f"[{'PASS' if exp else 'FAIL'}] fea_fos accept -> {r['action']}")
    ok_all &= exp

    # 5) design
    scen3 = {"task": "design", "inputs": {"r_out": 100.0, "r_bore": 30.0, "t": 20.0,
                                           "n_holes": 6, "r_hole": 9.0, "rho": 7.85e-3}}
    ref3 = recompute(scen3)
    r = verify({"world_state": ref3}, scen3)
    exp = r["action"] == "accept" and ref3["volume_mm3"] > 0
    print(f"[{'PASS' if exp else 'FAIL'}] design accept -> {r['action']}")
    ok_all &= exp

    # 6) 高风险超差 -> escalate
    r = verify({"world_state": bad_ws}, scen, high_stakes=True)
    exp = r["action"] == "escalate_solver"
    print(f"[{'PASS' if exp else 'FAIL'}] high-stakes escalate -> {r['action']}")
    ok_all &= exp

    # 7) 量纲错 1000 倍（把 g/cm^3 当 g/mm^3）-> 必须 L1 拦死
    dim_ws = dict(ref)
    dim_ws["resulting_mass_g"] = ref["resulting_mass_g"] * 1000.0
    r = verify({"world_state": dim_ws}, scen)
    exp = r["action"] == "reject_L1" and any("量纲" in i for i in r["issues"])
    print(f"[{'PASS' if exp else 'FAIL'}] L1 dimension 1000x -> {r['action']}")
    if exp:
        print(f"       证据: {[i for i in r['issues'] if '量纲' in i][0][:110]}")
    ok_all &= exp

    # 8) 量纲正常时不得误伤（回归保护）
    r = verify({"world_state": ref}, scen)
    exp = r["action"] == "accept" and not any("量纲" in i for i in r["issues"])
    print(f"[{'PASS' if exp else 'FAIL'}] L1 dimension no-false-positive -> {r['action']}")
    ok_all &= exp

    print("\n[selftest]", "ALL PASS" if ok_all else "SOME FAILED")
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scenario", help="结构化场景 JSON 文件")
    ap.add_argument("--out", help="LLM 输出 JSON 文件")
    ap.add_argument("--high-stakes", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if not args.scenario or not args.out:
        ap.print_help()
        sys.exit(2)

    scen = json.load(open(args.scenario, encoding="utf-8"))
    llm_out = json.load(open(args.out, encoding="utf-8"))
    verdict = verify(llm_out, scen, high_stakes=args.high_stakes)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
