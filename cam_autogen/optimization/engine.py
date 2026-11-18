"""M2 多目标约束优化求解引擎。

四个优化维度：加工效率(切削时间)、刀具损耗(寿命消耗比例)、加工精度(Ra/挠度相对要求)、生产成本。
标量化：J = Σ w_k · f_k(x) / f_k(x_ref)，x_ref 为手册推荐区间中点；硬约束以罚函数处理，
最终解再做严格可行性复核（max_violation ≤ 1e-6），不满足即判不可行而不是"凑一个"。
算法：差分进化（scipy.optimize.differential_evolution，迭代式全局搜索）+ 截止时间回调。
各工序目标可加可分（精度项按工序求和），故逐工序最优之和 = 全局最优。
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import differential_evolution

from cam_autogen.contracts import (
    CuttingParams, MachineLimits, ObjectiveWeights, Operation, OperationMetrics, OptimizationRequest, ProcessPlan,
)
from cam_autogen.optimization import catalog as cat
from cam_autogen.optimization.constraints import ConstraintRegistry
from cam_autogen.optimization.planner import OpDraft, plan_operations

ENGINE_VERSION = "m2-de-1.0.0"
TURN_CATS = {"face_turn", "od_rough", "od_finish", "groove", "thread", "drill_axial", "bore"}
DRILL_CATS = {"spot_drill", "drill", "drill_axial", "live_drill_cross", "live_drill_axial", "ream", "tap"}
MILL_CATS = {"face_mill", "outline_profile", "contour_rough", "contour_finish", "pocket_rough", "pocket_finish",
             "slot_mill", "live_keyway", "live_flat"}
E_CARBIDE = 600000.0


# ------------------------------------------------------------------ 决策变量与边界
def variable_space(op: OpDraft, mat: Dict[str, Any]) -> Tuple[List[str], List[Tuple[float, float]], Dict[str, float]]:
    """返回 (变量名, 边界, 固定量)。"""
    c, t, g = op.category, op.tool, op.geometry
    vt, vm = float(mat["vc_turn"]), float(mat["vc_mill"])
    D = t.diameter
    fixed: Dict[str, float] = {}

    def apb(lo: float, hi: float) -> Tuple[float, float]:
        return (lo, hi) if hi > lo + 1e-6 else (hi, hi + 1e-6)

    if c == "face_turn":
        return ["Vc", "f", "ap"], [(0.5 * vt, 1.4 * vt), (0.1, 0.4), apb(min(0.3, g["z_start"]), min(3.0, g["z_start"]))], fixed
    if c == "od_rough":
        return ["Vc", "f", "ap"], [(0.45 * vt, 1.4 * vt), (0.15, 0.5), apb(0.5, min(t.max_ap, g["radial_depth"]))], fixed
    if c in ("od_finish", "bore"):
        fixed["ap"] = g.get("allowance", 0.3) if c == "od_finish" else min(1.0, (g["d_final"] - g["d_start"]) / 2)
        return ["Vc", "f"], [(0.6 * vt, 1.6 * vt), (0.05, 0.25)], fixed
    if c == "groove":
        fixed["ap"] = t.diameter
        return ["Vc", "f"], [(0.4 * vt, 0.8 * vt), (0.03, 0.15)], fixed
    if c == "thread":
        fixed["f"] = g["pitch"]
        fixed["ap"] = g["depth"]
        return ["Vc"], [(0.35 * vt, 0.75 * vt)], fixed
    if c in ("spot_drill", "drill", "drill_axial", "live_drill_cross", "live_drill_axial"):
        fixed["ap"] = D / 2
        return ["Vc", "f"], [(0.3 * vm, 0.75 * vm), (0.008 * D + 0.02, min(0.35, 0.025 * D + 0.06))], fixed
    if c == "ream":
        fixed["ap"] = 0.1
        return ["Vc", "f"], [(0.12 * vm, 0.35 * vm), (0.1, 0.45)], fixed
    if c == "tap":
        fixed["f"] = g["pitch"]
        fixed["ap"] = g["pitch"]
        return ["Vc"], [(0.06 * vm, 0.2 * vm)], fixed
    fz_hi = min(0.25, 0.012 * D + 0.04)
    if c == "face_mill":
        fixed["ae"] = 0.7 * D
        depth = g["z_start"] - g["z_end"]
        return ["Vc", "fz", "ap"], [(0.5 * vm, 1.4 * vm), (0.08, 0.3), apb(min(0.3, depth), min(t.max_ap, 3.0, depth))], fixed
    if c in ("pocket_rough", "contour_rough"):
        depth = g["depth"]
        return ["Vc", "fz", "ap", "ae"], [(0.45 * vm, 1.4 * vm), (0.02, fz_hi), apb(min(0.2, depth), min(1.0 * D, depth)),
                                          (0.1 * D, 0.6 * D)], fixed
    if c == "outline_profile":
        depth = g["depth"]
        fixed["ae"] = max(0.05, min(g["allowance"], 0.5 * D))
        return ["Vc", "fz", "ap"], [(0.45 * vm, 1.4 * vm), (0.02, fz_hi), apb(min(0.2, depth), min(1.5 * D, depth))], fixed
    if c in ("slot_mill", "live_keyway"):
        depth = g["depth"]
        fixed["ae"] = D
        return ["Vc", "fz", "ap"], [(0.4 * vm, 1.2 * vm), (0.02, fz_hi), apb(min(0.1, depth), min(0.5 * D, depth))], fixed
    if c == "live_flat":
        depth = g["depth"]
        return ["Vc", "fz", "ap", "ae"], [(0.45 * vm, 1.3 * vm), (0.02, fz_hi), apb(min(0.2, depth), min(1.0 * D, depth)),
                                          (0.1 * D, 0.6 * D)], fixed
    if c in ("pocket_finish", "contour_finish"):
        fixed["ap"] = g["depth"]
        fixed["ae"] = max(0.05, g.get("allowance", 0.2))
        return ["Vc", "fz"], [(0.6 * vm, 1.5 * vm), (0.02, fz_hi)], fixed
    raise ValueError(f"未知工序类别 {c}")


# ------------------------------------------------------------------ 过程模型
def _vc_ref(c: str, mat: Dict[str, Any]) -> float:
    vt, vm = float(mat["vc_turn"]), float(mat["vc_mill"])
    if c in ("thread", "groove"):
        return 0.6 * vt
    if c == "tap":
        return 0.12 * vm
    if c == "ream":
        return 0.25 * vm
    if c in DRILL_CATS:
        return 0.5 * vm
    return vt if c in TURN_CATS else vm


def evaluate_op(op: OpDraft, x: Dict[str, float], mat: Dict[str, Any], lim: MachineLimits, rate_h: float,
                ctx_extra: Dict[str, Any]) -> Dict[str, float]:
    """给定参数计算全部中间量与四个目标。返回 ctx（亦供约束求值）。"""
    c, t, g = op.category, op.tool, op.geometry
    D = t.diameter
    z = t.flutes
    kc1, mc, n_tay = float(mat["kc1"]), float(mat["mc"]), float(mat["n"])
    Vc = x["Vc"]
    ap = x.get("ap", 0.0)
    live = op.setup == "live"
    n_max = lim.live_tool_max_rpm if live else lim.max_rpm
    P_max = lim.live_tool_power_kw if live else lim.max_power_kw
    ctx: Dict[str, float] = {"Vc": Vc, "ap": ap, "D": D, "z": z, "n_max": n_max, "P_max": P_max,
                             "vf_max": lim.max_feed_mm_min, "torque_max": lim.max_torque_nm or 0.0}
    overhead = 0.0
    if c in TURN_CATS:
        f = x["f"]
        ctx["f"] = f
        if c == "face_turn":
            d_ref = g["stock_d"] / 2
        elif c in ("od_rough",):
            d_ref = (g["stock_d"] + min(d for _, d in g["profile"])) / 2
        elif c == "od_finish":
            d_ref = sum(d for _, d in g["profile"]) / len(g["profile"])
        elif c == "groove":
            d_ref = (g["start_d"] + g["diameter"]) / 2
        elif c == "thread":
            d_ref = g["diameter"]
        elif c == "bore":
            d_ref = g["d_final"]
        else:
            d_ref = D
        n = 1000 * Vc / (math.pi * max(d_ref, 1.0))
        n_eff = min(n, n_max)  # CSS 被转速钳位
        vf = f * n_eff
        h = f
        kc = kc1 * max(h, 0.01) ** (-mc)
        if c == "drill_axial":
            Pc = f * Vc * D * kc / 240000.0
            Fc = Pc * 60000.0 / Vc
            t_cut = (g["depth"] + 3) / vf * (1 + 0.1 * math.ceil(g["depth"] / max(D, 1)))
        else:
            Fc = kc * ap * f
            Pc = Fc * Vc / 60000.0
            if c == "face_turn":
                passes = math.ceil((g["z_start"] - g["z_end"]) / ap - 1e-9)
                ap_eff = (g["z_start"] - g["z_end"]) / passes
                ctx["ap"] = ap_eff
                t_cut = passes * (g["stock_d"] / 2 + 2) / vf
            elif c == "od_rough":
                passes = math.ceil(g["radial_depth"] / ap - 1e-9)
                ctx["ap"] = g["radial_depth"] / passes
                mrr = 1000 * min(Vc, math.pi * d_ref * n_max / 1000) * ctx["ap"] * f
                t_cut = g["volume"] / max(mrr, 1e-6) * 1.15 + passes * 0.03
            elif c == "od_finish":
                t_cut = g["length"] / vf + 0.05
            elif c == "groove":
                plunges = max(1, math.ceil(g["width"] / D - 1e-9))
                t_cut = plunges * ((g["start_d"] - g["diameter"]) / 2 + 1) / vf
            elif c == "thread":
                passes = max(4, math.ceil(g["depth"] / 0.12))
                ctx["passes"] = passes
                t_cut = passes * (abs(g["z_start"] - g["z_end"]) + 4) / vf + passes * 0.02
            else:  # bore
                passes = max(1, math.ceil((g["d_final"] - g["d_start"]) / 2 / ap - 1e-9))
                t_cut = passes * (g["depth"] + 2) / vf
        n = n_eff
        mrr_v = Vc * ap * f * 1000
        # 工件挠度（悬臂；L/D>3 视为尾座支撑简支梁）
        Lp = ctx_extra.get("stickout", 50.0)
        dp = max(ctx_extra.get("min_d", 20.0), 1.0)
        I = math.pi * dp ** 4 / 64
        E = float(mat["e_mod"])
        Fr = 0.5 * Fc
        defl = Fr * Lp ** 3 / ((48 if Lp / dp > 3 else 3) * E * I) if c not in ("drill_axial",) else 0.0
        rε = max(t.corner_radius, 0.05)
        if c == "thread":
            Ra = 1.6
        elif c == "drill_axial":
            Ra = 2.2 + 5.0 * f
        else:
            Ra = 1000 * f ** 2 / (32 * rε) + 0.1
        ctx["h"], ctx["h_min"] = h, (0.03 if c in ("od_finish", "bore", "thread") else 0.05)
    elif c in DRILL_CATS:
        f = x["f"]
        ctx["f"] = f
        n = min(1000 * Vc / (math.pi * D), n_max)
        vf = f * n
        holes = g.get("holes") or [None]
        nh = len(holes)
        depth = g["depth"]
        if c == "tap":
            Pc = 0.0005 * Vc * D * kc1 / 1000
            Fc = Pc * 60000 / Vc
            t_cut = nh * 2 * (depth + 3) / vf
            Ra = 1.6
            h = f
        else:
            h = f / 2
            kc = kc1 * max(h, 0.01) ** (-mc)
            Pc = f * Vc * D * kc / 240000.0 * (0.15 if c == "ream" else 1.0)
            Fc = Pc * 60000 / Vc
            pecks = max(1, math.ceil(depth / max(D, 1.0))) if c != "ream" else 1
            t_cut = nh * ((depth + 3) / vf + 0.01 * pecks)
            overhead = nh * 0.01
            Ra = (0.6 + 2 * f) if c == "ream" else (2.2 + 5.0 * f)
        defl = 0.0
        mrr_v = math.pi * D ** 2 / 4 * vf
        ctx["h"], ctx["h_min"] = h, 0.01
    else:  # milling
        fz = x["fz"]
        ae = x.get("ae", ctx_extra.get("ae_fixed", 0.5 * D))
        ae = min(ae, D)
        ctx["fz"], ctx["ae"], ctx["f"] = fz, ae, fz * z
        n = min(1000 * Vc / (math.pi * D), n_max)
        vf = fz * z * n
        ratio = min(ae / D, 1.0)
        h_m = fz * (math.sqrt(ratio) if ratio < 0.5 else 0.64 + 0.36 * (1 - ratio))
        kc = kc1 * max(h_m, 0.005) ** (-mc)
        Pc = ap * ae * vf * kc / 60e6
        Fc = Pc * 60000 / max(Vc, 1e-6)
        if c == "face_mill":
            depth = g["z_start"] - g["z_end"]
            passes = math.ceil(depth / ap - 1e-9)
            ctx["ap"] = depth / passes
            lx, ly = g["xmax"] - g["xmin"], g["ymax"] - g["ymin"]
            rows = math.ceil(ly / ae) + 1
            t_cut = passes * rows * (lx + D + 4) / vf
        elif c in ("pocket_rough", "contour_rough", "live_flat"):
            depth = g["depth"]
            passes = math.ceil(depth / ap - 1e-9)
            ctx["ap"] = depth / passes
            if c == "pocket_rough":
                area = g["length"] * g["width"]
            elif c == "contour_rough":
                area = (g["xmax"] - g["xmin"] + D) * (g["ymax"] - g["ymin"] + D) - g["length"] * g["width"]
            else:
                area = g["width"] * abs(g["z1"] - g["z2"])
            t_cut = passes * (area / ae) / vf * 1.1 + passes * 0.02
        elif c == "outline_profile":
            depth = g["depth"]
            passes = math.ceil(depth / ap - 1e-9)
            ctx["ap"] = depth / passes
            radial = max(1, math.ceil(g["allowance"] / ae - 1e-9))
            perim = 2 * (g["xmax"] - g["xmin"] + g["ymax"] - g["ymin"]) + 2 * math.pi * D
            t_cut = passes * radial * perim / vf
        elif c in ("slot_mill", "live_keyway"):
            depth = g["depth"]
            passes = math.ceil(depth / ap - 1e-9)
            ctx["ap"] = depth / passes
            L = math.hypot(g["x2"] - g["x1"], g["y2"] - g["y1"]) if c == "slot_mill" else abs(g["z1"] - g["z2"])
            side = max(1, math.ceil((g["width"] - D) / (0.5 * D) - 1e-9) + 1) if g["width"] > D + 1e-6 else 1
            t_cut = passes * side * (L + 2) / vf
        else:  # pocket_finish / contour_finish
            perim = 2 * (g["length"] + g["width"])
            t_cut = perim / vf + 0.05
        mrr_v = ctx["ap"] * ae * vf
        L_t = t.length
        I = math.pi * (0.8 * D) ** 4 / 64
        defl = 0.6 * Fc * L_t ** 3 / (3 * E_CARBIDE * I)
        rough = c not in ("pocket_finish", "contour_finish")
        if c == "face_mill":
            Ra = 0.3 + 1000 * fz ** 2 / (32 * max(t.corner_radius, 0.4))
        else:
            Ra = 0.5 + 1000 * fz ** 2 / (4 * D)
        if rough and c != "face_mill":
            Ra *= 1.8
        ctx["h"], ctx["h_min"] = h_m, 0.008
    # 刀具寿命（扩展 Taylor），T_ref=15min @ Vc_ref, f_ref, ap_ref
    vref = _vc_ref(c, mat)
    f_now = ctx.get("fz", ctx.get("f", 0.1))
    f_ref = ctx_extra.get("f_ref", f_now)
    ap_ref = ctx_extra.get("ap_ref", max(ctx["ap"], 1e-3))
    T_life = 15.0 * (vref / Vc) ** (1.0 / n_tay) * (f_ref / max(f_now, 1e-6)) ** 0.75 * (ap_ref / max(ctx["ap"], 1e-6)) ** 0.25
    t_cut = t_cut + overhead
    wear = t_cut / max(T_life, 1e-6)
    edges = 1.0 if t.kind in ("turn_rough", "turn_finish", "groove", "thread", "face_mill", "boring_bar") else 0.25
    tool_cost = wear * t.edge_cost * edges
    cost = t_cut * rate_h / 60.0 + tool_cost
    Ra_req = op.ra_req
    defl_allow = (0.3 * op.tol_req if op.tol_req else None)
    if defl_allow is None:
        defl_allow = 0.05 if c in TURN_CATS or c in MILL_CATS else None
    precision = 0.0
    if Ra_req:
        precision += Ra / Ra_req
    if defl_allow:
        precision += defl / defl_allow
    torque = Pc * 9550 / max(n, 1.0)
    ctx.update({"n": n, "vf": vf, "Pc": Pc, "Fc": Fc, "Ra": Ra, "defl": defl, "T_life": T_life, "t_cut": t_cut,
                "mrr": mrr_v, "wear": wear, "cost": cost, "precision": precision, "torque": torque,
                "Ra_req": Ra_req or 0.0, "defl_allow": defl_allow or 0.0,
                "T_req": max(5.0, min(t_cut, 45.0))})
    return ctx


OBJ_KEYS = (("efficiency", "t_cut"), ("tool_wear", "wear"), ("precision", "precision"), ("cost", "cost"))


def _solve_op(op: OpDraft, mat: Dict[str, Any], req: OptimizationRequest, reg: ConstraintRegistry,
              ctx_extra: Dict[str, Any], deadline: float, seed: int) -> Tuple[Dict[str, float], Dict[str, Any]]:
    names, bounds, fixed = variable_space(op, mat)
    mid = {n: (lo + hi) / 2 for n, (lo, hi) in zip(names, bounds)}
    mid.update(fixed)
    extra = dict(ctx_extra)
    extra["f_ref"] = mid.get("fz", mid.get("f", 0.1))
    extra["ap_ref"] = max(mid.get("ap", 1.0), 1e-3)
    if "ae" in fixed:
        extra["ae_fixed"] = fixed["ae"]
    lim, rate = req.machine_limits, req.machine_rate_per_h
    ref = evaluate_op(op, mid, mat, lim, rate, extra)
    w = req.weights
    wsum = max(w.efficiency + w.tool_wear + w.precision + w.cost, 1e-9)
    weights = {"efficiency": w.efficiency / wsum, "tool_wear": w.tool_wear / wsum,
               "precision": w.precision / wsum, "cost": w.cost / wsum}
    norms = {k: max(abs(ref[key]), 1e-9) for k, key in OBJ_KEYS}
    hard = reg.hard_names()
    history: List[float] = []

    def unpack(v: np.ndarray) -> Dict[str, float]:
        d = dict(zip(names, (float(a) for a in v)))
        d.update(fixed)
        return d

    def scalar(ctx: Dict[str, float]) -> float:
        return sum(weights[k] * ctx[key] / norms[k] for k, key in OBJ_KEYS)

    def violation(ctx: Dict[str, float]) -> Tuple[float, float]:
        gs = reg.evaluate(op.category, ctx)
        hv = sum(max(0.0, v) for k, v in gs.items() if k in hard)
        sv = sum(max(0.0, v) for k, v in gs.items() if k not in hard)
        return hv, sv

    def J(v: np.ndarray) -> float:
        ctx = evaluate_op(op, unpack(v), mat, lim, rate, extra)
        hv, sv = violation(ctx)
        return scalar(ctx) + 1e3 * hv + 1e3 * hv * hv + 2.0 * sv

    def cb(xk: np.ndarray, convergence: float = 0.0) -> bool:
        history.append(J(xk))
        return time.perf_counter() > deadline

    t0 = time.perf_counter()
    if len(names) == 1 and bounds[0][1] - bounds[0][0] < 1e-5:
        best = np.array([bounds[0][0]])
        nit = nfev = 0
    else:
        res = differential_evolution(J, bounds, seed=seed, popsize=12, maxiter=120, tol=1e-8, mutation=(0.5, 1.0),
                                     recombination=0.8, polish=False, callback=cb, updating="immediate")
        best, nit, nfev = res.x, int(res.nit), int(res.nfev)
    x = unpack(best)
    ctx = evaluate_op(op, x, mat, lim, rate, extra)
    gs = reg.evaluate(op.category, ctx)
    hv = sum(max(0.0, v) for k, v in gs.items() if k in hard)
    info = {"variables": names, "bounds": bounds, "fixed": fixed, "iterations": nit, "nfev": nfev,
            "elapsed_s": round(time.perf_counter() - t0, 4), "J": scalar(ctx), "J_ref": scalar(ref),
            "constraint_values": {k: round(v, 6) for k, v in gs.items()},
            "binding": [k for k, v in gs.items() if -0.02 <= v <= 1e-6],
            "violated": [k for k, v in gs.items() if v > 1e-6 and k in hard],
            "soft_violated": [k for k, v in gs.items() if v > 1e-6 and k not in hard],
            "max_violation": hv, "history_tail": [round(h, 6) for h in history[-10:]],
            "improvement_vs_handbook_mid": round(1 - scalar(ctx) / max(scalar(ref), 1e-12), 4)}
    return ctx, info


def optimize(req: OptimizationRequest) -> ProcessPlan:
    t_start = time.perf_counter()
    budget = min(req.time_budget_s, 30.0)
    wp = req.workpiece
    mat_name, mat, mat_warn = cat.resolve_material(wp.material)
    drafts, notes = plan_operations(wp, req.process_type)
    if mat_warn:
        notes.append(mat_warn)
    reg = ConstraintRegistry()
    reg.disable(req.disabled_constraints)
    for cc in req.custom_constraints:
        reg.add_custom(cc)
    if wp.envelope.type == "cylindrical":
        prof_ds = [f.params.get("diameter", 0) for f in wp.features if f.type == "od_cylinder"]
        ctx_extra = {"stickout": (wp.envelope.length or 50) + 3.0,
                     "min_d": min([d for d in prof_ds if d > 0] or [wp.envelope.diameter or 20])}
    else:
        ctx_extra = {}
    ops: List[Operation] = []
    infeasible: List[str] = []
    per_op: List[Dict[str, Any]] = []
    tool_no: Dict[str, int] = {}
    for i, d in enumerate(drafts):
        remaining = budget - (time.perf_counter() - t_start)
        deadline = time.perf_counter() + max(0.05, remaining / max(1, len(drafts) - i)) * 0.95
        ctx, info = _solve_op(d, mat, req, reg, ctx_extra, deadline, req.seed + i)
        per_op.append({"op": d.category, **{k: info[k] for k in ("iterations", "nfev", "elapsed_s", "J", "J_ref",
                                                                 "improvement_vs_handbook_mid")}})
        if info["violated"]:
            infeasible.append(f"{d.category}{d.feature_ids}: 违反硬约束 {info['violated']} "
                              f"{ {k: info['constraint_values'][k] for k in info['violated']} }")
        tool_no.setdefault(d.tool.tool_id, len(tool_no) + 1)
        is_turn = d.category in TURN_CATS
        params = CuttingParams(
            vc_m_min=round(ctx["Vc"], 2), rpm=round(ctx["n"], 0), feed_mm_min=round(ctx["vf"], 1),
            feed_per_rev=round(ctx["f"], 4) if "fz" not in ctx else None,
            feed_per_tooth=round(ctx["fz"], 4) if "fz" in ctx else None,
            ap_mm=round(ctx["ap"], 4), ae_mm=round(ctx["ae"], 4) if "ae" in ctx else None,
            constant_surface_speed=is_turn and d.category not in ("thread", "drill_axial"),
        )
        metrics = OperationMetrics(
            cut_time_min=round(ctx["t_cut"], 4), tool_life_min=round(ctx["T_life"], 2),
            tool_wear_fraction=round(ctx["wear"], 5), ra_pred_um=round(ctx["Ra"], 3),
            deflection_mm=round(ctx["defl"], 5), power_kw=round(ctx["Pc"], 3), cost=round(ctx["cost"], 3),
            binding_constraints=info["binding"], max_violation=round(info["max_violation"], 8),
        )
        geom = dict(d.geometry)
        if d.category == "thread":
            geom["passes"] = int(ctx.get("passes", 6))
        ops.append(Operation(op_id=f"OP{(i + 1) * 10:03d}", seq=i + 1, category=d.category,
                             feature_ids=d.feature_ids, tool=d.tool, params=params, metrics=metrics, geometry=geom,
                             setup="live" if d.setup == "live" else "main",
                             notes=d.notes + ([f"软约束未满足: {info['soft_violated']}"] if info["soft_violated"] else [])))
    totals = {
        "cut_time_min": round(sum(o.metrics.cut_time_min for o in ops), 3),
        "tool_changes": len({o.tool.tool_id for o in ops}),
        "tool_wear_sum": round(sum(o.metrics.tool_wear_fraction for o in ops), 4),
        "cost": round(sum(o.metrics.cost for o in ops), 3),
        "max_power_kw": round(max(o.metrics.power_kw for o in ops), 3),
        "max_rpm": max(o.params.rpm for o in ops),
    }
    elapsed = time.perf_counter() - t_start
    return ProcessPlan(
        part_id=wp.part_id, process_type=req.process_type, material=mat_name, operations=ops, totals=totals,
        weights=req.weights,
        solver={"engine": ENGINE_VERSION, "algorithm": "differential_evolution+penalty", "elapsed_s": round(elapsed, 3),
                "time_budget_s": budget, "within_budget": elapsed <= budget + 1.0, "per_op": per_op,
                "constraints": reg.describe(), "notes": notes, "tool_numbers": tool_no},
        feasible=not infeasible, infeasible_reasons=infeasible,
    )
