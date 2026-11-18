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
try:  # pragma: no cover
    from distill_local_solver import mass_props_csg
    _MP_IMPORT_ERROR = ""
except Exception as _e:  # pragma: no cover
    mass_props_csg = None
    _MP_IMPORT_ERROR = repr(_e)

REL_TOL = 0.08


# ----------------------------------------------------------------------------
# 精确复算（L2 的"世界模型/参考求解器"）
# ----------------------------------------------------------------------------
def _rho_gmm3(s, default=7.85e-3):
    """密度口径归一（P-20）。

    题面写的是 g/cm3（钢 7.85），而本模块内部一律用 g/mm3（7.85e-3）：
    `removed_mass_g = V_mm3 * rho` 与 wm_schema 卡片文字
    `mass_g = V_mm3 * rho(g/cm3) / 1000` 在数值上等价，前提是 rho 已换算。
    历史 bug：场景抽取把题面的 7.85 原样塞进 scenario["rho"]，真值直接放大 1000 倍，
    模型算对反而被判错并被"纠正"成错值（也是 dimension_check 抓到 1000 倍的主因之一）。
    工程材料密度上限 0.06 g/mm3（锇 0.0226），故 rho > 0.1 只可能是 g/cm3 口径。
    """
    rho = s.get("rho")
    rho = float(default if rho is None else rho)
    if rho > 0.1:
        sys.stderr.write(f"[wm_verifier][WARN] rho={rho:g} 判定为 g/cm3 口径，已按 /1000 "
                         "换算为 g/mm3；请检查场景抽取是否漏做单位换算\n")
        rho /= 1000.0
    return rho


def _recompute_unsafe(scenario):
    """根据结构化场景重算参考世界状态（返回与 world_state 同名的字典型）。

    本函数假定输入完整；参数不全/非法时由 :func:`recompute` 统一 fail-closed。
    """
    task = scenario.get("task")
    s = scenario.get("inputs", scenario)

    if task == "removal":
        # 参数别名：铣削口径 ap/ae 与 doc/woc 等价，两种写法都必须认。
        doc = s.get("doc", s.get("ap"))
        woc = s.get("woc", s.get("ae"))
        vf = s.get("vf")
        rho = _rho_gmm3(s)
        stock_vol = s.get("stock_vol")
        fin_vol = s.get("V", s.get("volume_mm3"))
        # 去除体积口径优先级：成品体积差（CAD 真值）> doc*woc*L（解析式）
        removed = None
        if stock_vol is not None and fin_vol is not None:
            removed = float(stock_vol) - float(fin_vol)
        elif doc is not None and woc is not None and s.get("L") is not None:
            removed = float(doc) * float(woc) * float(s["L"])
        if removed is None:
            # 关键：参数不全时返回空参考值而不是 KeyError，
            # 否则上游 except 吞掉后 ref=None，mrr 等派生量永远补不出来（缺口 A 根因）。
            return {}
        out = {
            "material_removed_mm3": removed,
            "removed_mass_g": removed * rho,
            "delta_volume_mm3": -removed,
        }
        if doc is not None and woc is not None and vf is not None:
            out["mrr_mm3_per_min"] = float(doc) * float(woc) * float(vf)
        if fin_vol is not None:
            out["resulting_mass_g"] = float(fin_vol) * rho
        elif stock_vol is not None:
            out["resulting_mass_g"] = max(0.0, float(stock_vol) * rho - removed * rho)
        return out

    if task == "roughness":
        f, r_eps = s["f"], s["r_eps"]
        return {"surface_roughness_ra_um": 1000.0 * f * f / (8.0 * r_eps)}

    if task == "fea_fos":
        Sy, sigma = s["Sy"], s["sigma"]
        fos = Sy / sigma if sigma > 0 else float("inf")
        return {
            "yield_strength_mpa": Sy,
            "peak_von_mises_mpa": sigma,
            "safety_factor": fos,
            # 契约字面（wm_contract.KEY_SCHEMA）只认 pass/fail；旧实现返回大写
            # PASS/FAIL，导致参考值与训练数据/判分器三套字面并存，归一全靠
            # GATE_ALIASES 兜底，一旦护栏未启用就判错。
            "fos_gate": "pass" if fos >= 1.5 else "fail",
        }

    if task == "lame_cylinder_closed_end":
        pressure = float(s["pressure_mpa"])
        r_outer = float(s["r_outer_mm"])
        r_inner = float(s["r_inner_mm"])
        yield_strength = float(s["yield_strength_mpa"])
        denom = r_outer ** 2 - r_inner ** 2
        # Closed-end Lamé cylinder: combine radial, hoop, and axial principal stresses
        # into von Mises stress at the bore; hoop stress alone is not von Mises stress.
        peak_vm = math.sqrt(3.0) * pressure * r_outer ** 2 / denom
        fos = yield_strength / peak_vm
        return {
            "yield_strength_mpa": yield_strength,
            "peak_von_mises_mpa": peak_vm,
            "safety_factor": fos,
            "fos_gate": "pass" if fos >= 1.5 else "fail",
        }

    if task == "collision":
        z_safe, z_min, stock_top = s["z_safe"], s["z_min_rapid"], s["stock_top"]
        gouge = z_min < stock_top
        # 2026-11-08 物理语义修复：旧判据只有「两条件同时成立」才算 high，
        # 生成器 mode 2 (z_safe < stock_top) 会产出 gouge=True（已切进毛坯、
        # autodiff=red）却 collision_risk="none" 的矛盾标签（实测 600 条里 81 条）。
        # 已过切必然是碰撞高风险：gouge 单独构成充分条件。
        risk = ((z_min < z_safe) and (z_min < stock_top + 1.0)) or gouge
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
            # P-11：契约 tolerance 族的闸门是 tolerance_pass，此前参考值里根本没有
            # 这个键 → 模型判 pass 还是 fail 都无从校验（漏判）。
            "tolerance_pass": bool(clearance >= 0.0),
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
        # 装配体口径：直接给各零件体积列表 + 密度，避免必须提供 CSG shape/params
        if s.get("parts"):
            _V = float(sum(float(x) for x in s["parts"]))
            _m = _V * _rho_gmm3(s)
            return {"volume_mm3": _V, "mass_g": _m, "mass_kg": _m / 1000.0}
        if mass_props_csg is None:
            # P-16：静默降级是历史假绿的来源之一——CSG 依赖（build123d/OCP）缺失时
            # 这里直接返回 {}，上游 `if ref:` 判定为空即整体跳过复算，且无任何告警。
            # 现在把原因显式带回，由 verify() 升级为 escalate_solver，不再伪装通过。
            sys.stderr.write("[wm_verifier][WARN] mass_props 无参考值：mass_props_csg "
                             f"不可用（{_MP_IMPORT_ERROR}）\n")
            return {}
        _rho = _rho_gmm3(s)
        V, (cx, cy, cz), (Ix, Iy, Iz) = mass_props_csg(s["shape"], s["params"], _rho)
        return {
            "volume_mm3": V,
            "mass_g": V * _rho,
            "mass_kg": V * _rho / 1000.0,
            "centroid_mm": [cx, cy, cz],
            "inertia_ixx_mm4": Ix,
            "inertia_izz_mm4": Iz,
        }

    if task == "design":
        r_out, r_bore = s["r_out"], s["r_bore"]
        t, n, r_hole = s["t"], s["n_holes"], s["r_hole"]
        rho = _rho_gmm3(s)
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
        fos = Sy / sigma if sigma > 0 else float("inf")
        # P-12：与 fea_fos 同源 —— 此前本族参考值只有 safety_factor，
        # yield_strength_mpa / peak_von_mises_mpa / fos_gate 三个契约键全无参考值，
        # 模型把现场屈服强度抄错、FOS 闸门写反都拦不住。
        return {
            "yield_strength_mpa": Sy,
            "peak_von_mises_mpa": sigma,
            "safety_factor": fos,
            "fos_gate": "pass" if fos >= 1.5 else "fail",
        }

    if task == "adapt_machine":
        D, vc, n_max = s["D"], s["vc"], s["n_max"]
        n = 1000.0 * vc / (math.pi * D)
        return {
            "required_spindle_rpm": n,
            "machine_max_rpm": n_max,
            "within_limit": bool(n <= n_max),
            # P-13：契约登记 recommended_vc_m_per_min，此前不产出 → 恒为漏判。
            "recommended_vc_m_per_min": vc,
        }

    return {}


# ----------------------------------------------------------------------------
# 各族复算所需输入（显式声明，替代"下标取值 + KeyError 兜底"）
# ----------------------------------------------------------------------------
# 历史问题（2026-11-08 二轮）：recompute 靠 `s["f"]` 这类下标取值，缺参只能靠
# KeyError 被外层 except 捕获。结果虽然同样是"不给参考值 → escalate"，但：
#   ① 告警文本是 `KeyError: 'r_eps'`，运维看到无法判断是缺参还是代码 bug；
#   ② 用异常做控制流，任何一处 except 范围写错就会静默吞掉真实错误；
#   ③ 缺的是哪个参数、缺几个，全部丢失。
# 现在先查表，缺什么一目了然；removal / mass_props 输入组合多样，仍走各自
# 的软判断（removed is None / parts 或 CSG 回退），不在此表硬查。
REQUIRED_INPUTS = {
    "roughness": ["f", "r_eps"],
    "fea_fos": ["Sy", "sigma"],
    "lame_cylinder_closed_end": [
        "pressure_mpa", "r_outer_mm", "r_inner_mm", "yield_strength_mpa"
    ],
    "collision": ["z_safe", "z_min_rapid", "stock_top"],
    "tolerance": ["tols", "upper_dev", "lower_dev"],
    "geom_delta": ["feature_vol", "before"],
    "design": ["r_out", "r_bore", "t", "n_holes", "r_hole"],
    "process": ["D", "L", "ap", "f", "vc", "r_eps"],
    "adapt_material": ["Sy", "sigma"],
    "adapt_machine": ["D", "vc", "n_max"],
}

# 值域非法（分母 ≤ 0 等）：与缺参同等对待，不靠 ZeroDivisionError 兜底
NONPOSITIVE_INPUTS = {
    "roughness": ["r_eps"],
    "process": ["D", "r_eps"],
    "adapt_machine": ["D"],
    "lame_cylinder_closed_end": [
        "pressure_mpa", "r_outer_mm", "r_inner_mm", "yield_strength_mpa"
    ],
}


def _scn_inputs(scenario):
    if not isinstance(scenario, dict):
        return {}
    s = scenario.get("inputs", scenario)
    return s if isinstance(s, dict) else {}


def _input_defects(scenario):
    """返回 (缺参列表, 非法值列表)；两者都非空即 fail-closed。"""
    task = scenario.get("task") if isinstance(scenario, dict) else None
    s = _scn_inputs(scenario)
    missing = [k for k in REQUIRED_INPUTS.get(task, []) if s.get(k) is None]
    nonpos = []
    if task == "lame_cylinder_closed_end":
        for key in REQUIRED_INPUTS[task]:
            value = s.get(key)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                nonpos.append((key, value))
    for k in NONPOSITIVE_INPUTS.get(task, []):
        v = s.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v <= 0:
            nonpos.append((k, v))
    if task == "lame_cylinder_closed_end":
        r_outer, r_inner = s.get("r_outer_mm"), s.get("r_inner_mm")
        if (isinstance(r_outer, (int, float)) and not isinstance(r_outer, bool)
                and isinstance(r_inner, (int, float)) and not isinstance(r_inner, bool)
                and r_inner >= r_outer):
            nonpos.append(("r_inner_mm must be less than r_outer_mm", r_inner))
    return missing, nonpos


def recompute(scenario):
    """L2 参考值的唯一入口：输入不完整时 fail-closed，绝不抛异常、绝不返回非有限值。

    历史缺陷（2026-11-08 实测）：除 removal 外各族都直接下标取 ``s["..."]``，
    少一个参数就抛 KeyError；``verify()`` 不吞异常直接崩，而 Guard 用
    ``except: ref=None`` 吞掉后走「无参考值 → accept」分支 —— 同一份错误输入，
    两条链路一条崩、一条假绿。现在统一在这里收敛：
      参数缺失 / 除零 / 类型错 / 非有限值 → 返回 ``{}`` + 显式 WARN
    ``verify()`` 与 Guard 看到空 ref 都会升级为 escalate_solver / L2_NO_REF。
    """
    task = scenario.get("task", "?") if isinstance(scenario, dict) else "?"
    missing, nonpos = _input_defects(scenario)
    if missing:
        sys.stderr.write(f"[wm_verifier][WARN] recompute(task={task}) 缺参 {missing}，"
                         "本次不给参考值（fail-closed）\n")
        return {}
    if nonpos:
        sys.stderr.write(f"[wm_verifier][WARN] recompute(task={task}) 值域非法 {nonpos}"
                         "（分母必须 > 0），本次不给参考值（fail-closed）\n")
        return {}
    try:
        out = _recompute_unsafe(scenario)
    except (KeyError, ZeroDivisionError, TypeError, ValueError, IndexError, OverflowError) as e:
        sys.stderr.write(f"[wm_verifier][WARN] recompute(task={task}) 输入不完整或非法，"
                         f"本次不给参考值: {type(e).__name__}: {e}\n")
        return {}
    # inf/NaN 不是合法 JSON 数值：例如 sigma=0 时 FOS=inf，会污染 gold 与判分。
    bad = [k for k, v in out.items() if isinstance(v, float) and not math.isfinite(v)]
    if bad:
        task = scenario.get("task", "?") if isinstance(scenario, dict) else "?"
        sys.stderr.write(f"[wm_verifier][WARN] recompute(task={task}) 产出非有限值 {bad}，"
                         "本次不给参考值\n")
        return {}
    return out


# ----------------------------------------------------------------------------
# L1 确定性检查
# ----------------------------------------------------------------------------
REQUIRED = {
    "removal": ["material_removed_mm3", "mrr_mm3_per_min", "delta_volume_mm3"],
    "roughness": ["surface_roughness_ra_um"],
    "fea_fos": ["safety_factor"],
    "lame_cylinder_closed_end": ["peak_von_mises_mpa", "safety_factor"],
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
    "safety_factor", "peak_von_mises_mpa", "volume_mm3", "mass_g", "mass_kg", "spindle_rpm",
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
    # 契约的 invalid 在**顶层** {"invalid": true, "world_state": null, "reason": ...}，
    # verify() 已在取 ws 之前裁决并 accept。这里拿到的 ws 是 world_state 内层，
    # 内层出现 invalid 键本身就是格式违规，不是合法响应。
    # 历史 bug：`ws.get("world_state") is None and ws.get("invalid")` 中 and 优先于 or，
    # 且内层恒无 world_state 键 → 只要内层塞任意 truthy 的 invalid（哪怕是 1），
    # REQUIRED / 守恒 / 正值 / 量纲四道 L1 检查全部空转（实测 2026-11-08）。
    # 现在只有「内层确实是纯 invalid 声明」才放行，其它一律照常检查。
    if ws.get("invalid") is True and set(ws) <= {"invalid", "reason"}:
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
        # P-8 修复：原实现 `if k not in pred: continue` —— 复算得出的参考量若模型压根
        # 没写，既不报错也不进 corrected，等于"漏写即免检"，是假绿的另一个入口。
        # 现在记为 missing（corrected 会用参考值补齐），但不因缺失而否定已有正确字段。
        if k not in pred:
            mism.append({"field": k, "pred": None, "ref": rv, "type": "missing"})
            continue
        pv = pred[k]
        if isinstance(rv, bool) or isinstance(pv, bool):
            if _to_bool(pv) != _to_bool(rv):
                mism.append({"field": k, "pred": pv, "ref": rv, "type": "bool"})
            continue
        if isinstance(rv, (int, float)) and isinstance(pv, (int, float)):
            denom = max(abs(rv), 1e-9)
            rel = abs(pv - rv) / denom
            if rel > tol:
                mism.append({"field": k, "pred": pv, "ref": rv, "rel_err": round(rel, 4)})
        elif isinstance(rv, str) and isinstance(pv, str):
            # P-9 修复：材质/机床等文本量区分大小写会产生 "Al6061" vs "AL6061" 的
            # 伪不一致，白白触发一轮纠正。
            if _norm_text(pv) != _norm_text(rv):
                mism.append({"field": k, "pred": pv, "ref": rv, "type": "str"})
    return mism


def _norm_text(v):
    return str(v).strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y", "是", "pass", "ok"):
        return True
    if s in ("false", "0", "no", "n", "否", "fail", "ng"):
        return False
    return None


def verify(llm_out, scenario, high_stakes=False):
    """主入口：输入 LLM 输出（含 world_state）与结构化场景，返回裁决。"""
    ws = llm_out.get("world_state", llm_out) if isinstance(llm_out, dict) else None
    # P-10 修复：契约明文允许「非法输入 → {"invalid": true, "world_state": null}」。
    # 但 verify 取 world_state 得到 None 后直接判 reject_L1，把合规的 invalid 响应
    # 当成解析失败：训练里每一条 invalid 样本都会被护栏反转成拒绝，模型永远学不会。
    if ws is None and isinstance(llm_out, dict) and llm_out.get("invalid") is True:
        # FIX H4（2026-11-08 审计）：原实现无条件 accept，等于开了一条
        # 「一律报 invalid 即可跳过全部数值校验」的通道。现在必须与 scenario 反查：
        #   - scenario 本身是 invalid 族 / 无 task  -> 合规，放行（保留 P-10 语义）
        #   - scenario 参数齐全可算出参考值          -> 模型谎报 invalid，拒绝
        #   - scenario 有 task 但参数不全（ref 为空） -> 无法证伪，保守放行并留痕
        task = (scenario or {}).get("task") if isinstance(scenario, dict) else None
        if task and str(task) != "invalid":
            ref_chk = recompute(scenario)
            if ref_chk:
                return {"ok": False, "level": "L2", "action": "reject_L1",
                        "issues": ["谎报 invalid：题面参数齐备且求解器可算出参考值，"
                                   f"不得以缺参为由拒绝计算（task={task}）"],
                        "reference": ref_chk, "corrected_world_state": None,
                        "note": "按场景求解器参考值重新作答，或指出真正缺失的必需参数"}
            return {"ok": True, "level": "L1", "action": "accept",
                    "issues": [], "reference": {}, "corrected_world_state": llm_out,
                    "note": "invalid 响应无法与场景证伪（scenario 参数不全），保守放行"}
        return {"ok": True, "level": "L1", "action": "accept",
                "issues": [], "reference": {}, "corrected_world_state": llm_out}
    if ws is None:
        return {"ok": False, "level": "L1", "action": "reject_L1",
                "issues": ["无法解析 world_state"], "reference": {}, "corrected_world_state": None}

    l1 = l1_check(ws, scenario)
    if l1:
        return {"ok": False, "level": "L1", "action": "reject_L1",
                "issues": l1, "reference": {}, "corrected_world_state": None}

    ref = recompute(scenario)
    if not ref:
        # P-17（假绿源头）：ref 为空时 mism 恒为空 -> 直接 accept。
        # 这道"空比对即通过"的缝，是 L2 通道最隐蔽的假绿：scenario 少个参数、
        # 或 CSG 依赖缺失，任何离谱数值都能过。改为 escalate_solver，不给出 ok。
        return {"ok": False, "level": "L2", "action": "escalate_solver",
                "issues": ["无参考值：scenario 参数不全或求解器能力不可用，未做数值校验"],
                "reference": {}, "corrected_world_state": None,
                "note": "补全 scenario 输入或修复求解器依赖后再校验"}
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

    # 3b) P-10 回归：契约合规的 invalid 响应必须 accept，不得被当成解析失败
    #     FIX H4：accept 的前提是「场景本身也确实不可算 / 就是 invalid 族」。
    r = verify({"invalid": True, "world_state": None}, {"task": "invalid", "inputs": {}})
    exp = r["action"] == "accept"
    print(f"[{'PASS' if exp else 'FAIL'}] invalid contract accept -> {r['action']}")
    ok_all &= exp
    # 3b2) FIX H4 反证：场景参数齐备可算时谎报 invalid，必须被拒（旧实现无条件 accept，
    #      等于开了一条「一律报 invalid 跳过全部数值校验」的后门）。
    r = verify({"invalid": True, "world_state": None}, scen)
    exp = r["action"] == "reject_L1"
    print(f"[{'PASS' if exp else 'FAIL'}] invalid 谎报拦截 -> {r['action']}")
    ok_all &= exp

    # 3c) P-8 回归：模型漏写复算量必须被补齐（missing 记账），不能漏写即免检。
    # 注意只能用非 REQUIRED 的键验证——缺失必需字段由 L1 先拒，走不到 L2 补齐。
    partial = {"world_state": {k: v for k, v in ref.items() if k != "resulting_mass_g"}}
    r = verify(partial, scen)
    exp = (r["action"] == "correct_with_reference"
           and any(i.get("type") == "missing" and i["field"] == "resulting_mass_g"
                   for i in r["issues"])
           and _approx(r["corrected_world_state"]["resulting_mass_g"],
                       ref["resulting_mass_g"], 1e-9))
    print(f"[{'PASS' if exp else 'FAIL'}] missing field 补齐 -> {r['action']}")
    ok_all &= exp

    # 3d) P-14 回归：两处 REQUIRED 语义不同但必须包含关系一致——
    #   wm_schema.REQUIRED_FIELDS = 下发给模型的 JSON Schema required（模型必须写）
    #   本文件 REQUIRED            = L1 最低门槛（缺了就 reject_L1）
    # 约束方向只有一个：L1 要查的字段必须在 schema 必填里。否则模型完全合规地
    # 按 schema 输出、却被 L1 判缺字段拒绝 —— 典型的"护栏比契约更严"假拒绝。
    try:
        import wm_schema as _S
        gap = {fam: sorted(set(REQUIRED.get(fam, [])) - set(_S.REQUIRED_FIELDS.get(fam, [])))
               for fam in REQUIRED}
        gap = {k: v for k, v in gap.items() if v}
        exp = not gap
        if not exp:
            print("       L1 门槛字段未在 schema 必填中:", gap)
    except ImportError:
        exp = True
    print(f"[{'PASS' if exp else 'FAIL'}] L1 REQUIRED ⊆ schema REQUIRED")
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

    # 9) 反证闸门：内层塞任意 truthy invalid 不得让四道 L1 检查空转
    base_issues = l1_check({"material_removed_mm3": 1.0}, scen)
    bypass_issues = l1_check({"material_removed_mm3": 1.0, "invalid": 1}, scen)
    exp = bool(base_issues) and base_issues == bypass_issues
    print(f"[{'PASS' if exp else 'FAIL'}] L1 不可被 invalid 键绕过 -> {len(bypass_issues)} issues")
    ok_all &= exp

    # 10) 反证闸门：参数不全 / 除零 / 非有限值一律 fail-closed，不得抛异常
    bad_scen = [
        {"task": "roughness", "inputs": {"f": 0.1}},
        {"task": "roughness", "inputs": {"f": 0.1, "r_eps": 0}},
        {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 0}},
        {"task": "process", "inputs": {"D": 0, "L": 1, "ap": 1, "f": 1, "vc": 1, "r_eps": 1}},
        {"task": "tolerance", "inputs": {"tols": [0.1]}},
    ]
    try:
        exp = all(recompute(s) == {} for s in bad_scen)
    except Exception as e:
        exp = False
        print(f"       异常未收敛: {type(e).__name__}: {e}")
    v = verify({"world_state": {"surface_roughness_ra_um": 1.25}}, bad_scen[0])
    exp = exp and v["action"] == "escalate_solver"
    print(f"[{'PASS' if exp else 'FAIL'}] 缺参/除零/inf -> escalate_solver -> {v['action']}")
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
    # Windows 控制台默认 GBK：selftest 的 ⊆ 与裁决 JSON 的数学符号会直接
    # UnicodeEncodeError 崩掉后半段检查（实测 2026-11-08）。入口统一转 UTF-8。
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    main()
