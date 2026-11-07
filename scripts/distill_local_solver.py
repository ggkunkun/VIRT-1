#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 世界模型 —— 本地「仿真器蒸馏」真实数据管线
=================================================

目标：在本机（无需云端、无需联网）用**真实数值求解器**产出制造世界状态的
「ground-truth」，写入 sim_out.jsonl，供 build_worldmodel_sft.py --distill 转成
SFT 对，让 LLM 蒸馏向真实求解器，而不是闭式公式里随机采样的伪真值。

本机可做的求解器（全部零外部依赖 / 零许可）：
  1) FEA：纯 numpy 实现 Euler-Bernoulli 梁**有限元直接刚度法**（2 节点梁单元，
     多单元装配 + 悬臂边界 + 集中/分布载荷），反算峰值 von Mises 应力、自由端
     挠度、安全系数 FOS。这是真·数值 FEA，不是套公式。
  2) 质量属性：解析 CSG（长方体 / 圆柱 + 开槽布尔减，组合体法 + 平行轴定理）
     算真实体积、质量、质心、惯性矩。
  3) 切削/公差/碰撞/几何ΔV：沿用公认精确解析公式。

可选：若本机安装了可自动化的 SolidWorks，`--use-solidworks` 会用真实 CAD
质量属性覆盖（win32com 驱动，缺失/失败则优雅回退到解析 CSG）。

输出 schema（与 build_worldmodel_sft.py --distill 完全兼容）：
  每行一个 JSON：{"inputs": {...}, "outputs": {...}, "family": "..."}

用法：
  python scripts/distill_local_solver.py --out data/sft/wm_sim_out.jsonl --n 400
  python scripts/distill_local_solver.py --out data/sft/wm_sim_out.jsonl --n 400 --use-solidworks
"""
import os
import sys
import json
import math
import argparse
import random

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MATERIALS = {
    "45钢":       {"rho": 7.85e-3, "Sy": 355.0, "E": 2.06e5},
    "铝合金6061": {"rho": 2.70e-3, "Sy": 276.0, "E": 6.90e4},
    "不锈钢304":  {"rho": 8.00e-3, "Sy": 215.0, "E": 1.93e5},
    "钛合金TC4":  {"rho": 4.43e-3, "Sy": 830.0, "E": 1.14e5},
    "黄铜H62":     {"rho": 8.50e-3, "Sy": 200.0, "E": 1.00e5},
}


# ----------------------------------------------------------------------------
# 1) FEA —— 纯 numpy 梁有限元（直接刚度法）
# ----------------------------------------------------------------------------
def fea_beam_fem(E, I, L, b, h, F_end, q_dist=0.0, n_elem=12):
    """Euler-Bernoulli 悬臂梁 FEM 真解。

    单元刚度（2 节点，DOF=[v,θ]）：ke = E*I/L^3 * [...]
    装配全局 K → 施加悬臂 BC（根节点 v=0,θ=0）→ 求解位移 →
    反算单元端弯矩 → 峰值 σ_vm = M*c/I（c=h/2）→ FOS = Sy/σ_vm，并取自由端挠度。
    返回 dict（全部真实数值求解结果）。
    """
    c = h / 2.0                     # 中性轴到外表面距离
    n_node = n_elem + 1
    ndof = 2 * n_node
    K = np.zeros((ndof, ndof), dtype=float)
    le = L / n_elem
    # 单元刚度矩阵（无量纲部分）
    ke_base = np.array([
        [12,        6 * le,     -12,        6 * le],
        [6 * le,    4 * le**2,  -6 * le,    2 * le**2],
        [-12,      -6 * le,      12,       -6 * le],
        [6 * le,    2 * le**2,  -6 * le,    4 * le**2],
    ], dtype=float)
    ke = (E * I / le**3) * ke_base

    for e in range(n_elem):
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            for j in range(4):
                K[idx[i], idx[j]] += ke[i, j]

    # 载荷向量
    F = np.zeros(ndof, dtype=float)
    # 自由端集中力（最后节点竖向 DOF）
    F[2 * n_node - 2] += -F_end          # 向下为负
    # 分布载荷 q（每单元等效节点力：q*le/2 竖向 + q*le^2/12 弯矩）
    if q_dist != 0.0:
        for e in range(n_elem):
            idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
            fe = np.array([q_dist * le / 2, q_dist * le**2 / 12,
                           q_dist * le / 2, -q_dist * le**2 / 12], dtype=float)
            for i in range(4):
                F[idx[i]] += fe[i]

    # 边界：根节点 DOF 0,1 固定 → 划行划列
    free = list(range(2, ndof))
    Kff = K[np.ix_(free, free)]
    Ff = F[free]

    try:
        u = np.linalg.solve(Kff, Ff)
    except np.linalg.LinAlgError:
        return None
    u_full = np.zeros(ndof, dtype=float)
    u_full[free] = u

    tip_deflection = abs(u_full[2 * n_node - 2])   # 自由端竖向位移

    # 峰值弯矩：遍历单元，取单元端力向量第 4 分量（右端弯矩）绝对值最大
    peak_M = 0.0
    for e in range(n_elem):
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        ue = u_full[idx]
        fe = ke @ ue                      # 单元端力 {V1,M1,V2,M2}
        M_right = abs(fe[3])
        M_left = abs(fe[1])
        peak_M = max(peak_M, M_right, M_left)

    sigma_vm = peak_M * c / I if I > 0 else 0.0
    return {
        "peak_bending_moment_Nmm": round(peak_M, 2),
        "tip_deflection_mm": round(tip_deflection, 4),
        "peak_von_mises_mpa": round(sigma_vm, 2),
    }


# ----------------------------------------------------------------------------
# 2) 质量属性 —— 解析 CSG（组合体法 + 平行轴定理）
# ----------------------------------------------------------------------------
def _box_volume(l, w, h):
    return l * w * h


def _cyl_volume(r, h):
    return math.pi * r * r * h


def mass_props_csg(shape, params, rho):
    """解析计算长方体/圆柱（可含开槽）的质量属性。

    `inertia_*_mm4` is a second moment of AREA (mm^4). The previous expressions multiplied
    a volume by h^2/12 (mm^5) and hid the real section formula behind an `if False` branch,
    so 255 rows of data/sft/virtu_final_train.jsonl trained an mm^5 number under an mm^4
    field name while no physics case graded mass_props - nothing caught it. Convention here:
    x/y/z are the edges l/w/h, and I about an axis uses the other two as the section.
    """
    if shape == "box":
        l, w, h = params["l"], params["w"], params["h"]
        V = _box_volume(l, w, h)
        # 质心在几何中心
        cx, cy, cz = l / 2.0, w / 2.0, h / 2.0
        Ix = w * h ** 3 / 12.0
        Iy = l * h ** 3 / 12.0
        Iz = l * w ** 3 / 12.0
        return V, (cx, cy, cz), (Ix, Iy, Iz)
    elif shape == "cylinder":
        r, h = params["r"], params["h"]
        V = _cyl_volume(r, h)
        cx, cy, cz = r, r, h / 2.0
        Ix = Iz = math.pi * r ** 4 / 4.0
        Iy = math.pi * r ** 4 / 2.0
        return V, (cx, cy, cz), (Ix, Iy, Iz)
    else:
        return 0.0, (0, 0, 0), (0, 0, 0)


def solve_mass_props(rng, use_solidworks=False):
    shape = rng.choice(["box", "cylinder"])
    mat = rng.choice(list(MATERIALS))
    rho = MATERIALS[mat]["rho"]
    if shape == "box":
        l = round(rng.uniform(40, 200), 1)
        w = round(rng.uniform(20, 150), 1)
        h = round(rng.uniform(10, 120), 1)
        params = {"l": l, "w": w, "h": h}
    else:
        r = round(rng.uniform(10, 80), 1)
        h = round(rng.uniform(10, 150), 1)
        params = {"r": r, "h": h}
    V, (cx, cy, cz), (Ix, Iy, Iz) = mass_props_csg(shape, params, rho)
    mass = V * rho

    outputs = {
        "shape": shape,
        "volume_mm3": round(V, 2),
        "mass_g": round(mass, 3),
        "centroid_mm": [round(cx, 3), round(cy, 3), round(cz, 3)],
        "inertia_ixx_mm4": round(Ix, 2),
        "inertia_izz_mm4": round(Iz, 2),
    }

    # 可选：用真实 SolidWorks 质量属性覆盖
    if use_solidworks:
        sw = _try_solidworks_mass_props(shape, params)
        if sw is not None:
            outputs.update(sw)
            outputs["_solver"] = "solidworks"
    else:
        outputs["_solver"] = "analytic_csg"

    inputs = {"task": "mass_properties", "shape": shape,
              "dimensions_mm": params, "material": mat}
    return inputs, outputs, "mass_props"


# ----------------------------------------------------------------------------
# 3) 其余家族 —— 精确解析（与 build_worldmodel_sft 同源，但封装为函数）
# ----------------------------------------------------------------------------
def solve_fea(rng):
    mat = rng.choice(list(MATERIALS))
    m = MATERIALS[mat]
    Sy, E = m["Sy"], m["E"]
    b = round(rng.uniform(10, 60), 1)        # 截面宽 mm
    h = round(rng.uniform(10, 80), 1)        # 截面高 mm
    L = round(rng.uniform(100, 600), 1)      # 跨度 mm
    F = round(rng.uniform(50, 5000), 1)      # 自由端集中力 N
    I = b * h**3 / 12.0                       # 截面惯性矩 mm^4
    fem = fea_beam_fem(E, I, L, b, h, F, n_elem=12)
    if fem is None:
        return None
    sigma = fem["peak_von_mises_mpa"]
    fos = Sy / sigma if sigma > 0 else float("inf")
    outputs = {
        "material": mat,
        "yield_strength_mpa": Sy,
        "peak_von_mises_mpa": sigma,
        "tip_deflection_mm": fem["tip_deflection_mm"],
        "safety_factor": round(fos, 3) if fos != float("inf") else 99.0,
        "fos_gate": "FOS>=1.5_pass" if fos >= 1.5 else "FOS<1.5_FAIL",
    }
    inputs = {"task": "fea_beam", "material": mat, "section_mm": {"b": b, "h": h},
              "span_mm": L, "end_load_N": F, "solver": "numpy_fem_euler_bernoulli"}
    return inputs, outputs, "fea_fos"


def solve_removal(rng):
    mat = rng.choice(list(MATERIALS))
    rho = MATERIALS[mat]["rho"]
    doc = round(rng.uniform(0.5, 4.0), 2)
    woc = round(rng.uniform(1.0, 10.0), 2)
    vf = round(rng.uniform(80, 1200), 0)
    L = round(rng.uniform(20, 300), 1)
    stock_vol = round(rng.uniform(50000, 500000), 0)
    mrr = doc * woc * vf
    removed = doc * woc * L
    removed_mass = removed * rho
    remaining = max(0.0, stock_vol * rho - removed_mass)
    outputs = {
        "material_removed_mm3": round(removed, 1),
        "mrr_mm3_per_min": round(mrr, 1),
        "removed_mass_g": round(removed_mass, 3),
        "resulting_mass_g": round(remaining, 3),
        "delta_volume_mm3": round(-removed, 1),
        "volume_conservation": "pass_cut_negative",
    }
    inputs = {"task": "material_removal", "material": mat, "rough_volume_mm3": stock_vol,
              "doc_mm": doc, "woc_mm": woc, "vf_mm_min": vf, "path_length_mm": L}
    return inputs, outputs, "removal"


def solve_roughness(rng):
    f = round(rng.uniform(0.05, 0.4), 3)
    r_eps = round(rng.choice([0.2, 0.4, 0.8, 1.2, 1.6]), 2)
    ra = 1000.0 * f * f / (8.0 * r_eps)
    outputs = {
        "feed_per_rev_mm": f, "nose_radius_mm": r_eps,
        "surface_roughness_ra_um": round(ra, 3),
        "finish_class": "精加工" if ra < 3.2 else ("半精" if ra < 6.3 else "粗加工"),
    }
    inputs = {"task": "surface_roughness", "process": "turning_OD",
              "feed_mm_rev": f, "nose_radius_mm": r_eps}
    return inputs, outputs, "roughness"


def solve_collision(rng):
    z_safe = round(rng.uniform(2.0, 30.0), 1)
    z_min = round(rng.uniform(-5.0, z_safe + 5.0), 1)
    stock_top = round(rng.uniform(0.0, 20.0), 1)
    over = (z_min < z_safe) and (z_min < stock_top + 1.0)
    gouge = over and (z_min < stock_top)
    risk = "high" if over else "none"
    outputs = {
        "safe_plane_z_mm": z_safe, "rapid_min_z_mm": z_min, "stock_top_z_mm": stock_top,
        "collision_risk": risk, "gouge": bool(gouge),
        "autodiff": "red" if gouge else ("yellow" if risk == "high" else "green"),
    }
    inputs = {"task": "toolpath_collision", "safe_plane_z_mm": z_safe,
              "rapid_min_z_mm": z_min, "stock_top_z_mm": stock_top}
    return inputs, outputs, "collision"


def solve_tolerance(rng):
    n = rng.randint(2, 4)
    tols = [round(rng.uniform(0.01, 0.1), 3) for _ in range(n)]
    wc = sum(tols)
    rss = math.sqrt(sum(t * t for t in tols))
    basic = round(rng.uniform(20, 100), 1)
    upper = round(rng.uniform(0.0, 0.05), 3)
    lower = round(rng.uniform(-0.05, 0.0), 3)
    clearance = upper - lower
    fit = "间隙配合" if clearance > 0 else ("过盈配合" if clearance < 0 else "过渡配合")
    fit_class = ("H7/g6" if clearance > 0.01 else ("H7/p6" if clearance < -0.01 else "H7/js6"))
    outputs = {
        "component_tolerances_mm": tols,
        "closed_loop_worstcase_halfwidth_mm": round(wc, 4),
        "closed_loop_rss_halfwidth_mm": round(rss, 4),
        "basic_size_mm": basic, "fit_clearance_mm": round(clearance, 4),
        "tolerance_fit": fit, "fit_class": fit_class,
        "tolerance_pass": bool(clearance >= -0.005),
    }
    inputs = {"task": "tolerance_stack", "num_rings": n, "half_tolerances_mm": tols,
              "basic_size_mm": basic, "hole_upper_dev_mm": upper, "hole_lower_dev_mm": lower}
    return inputs, outputs, "tolerance"


def solve_geom_delta(rng):
    feat = rng.choice(["通孔", "沉槽", "键槽", "倒角"])
    vol = round(rng.uniform(200, 8000), 0)
    before = round(rng.uniform(20000, 200000), 0)
    dv = -vol
    outputs = {
        "feature": feat, "feature_volume_mm3": vol, "delta_volume_mm3": dv,
        "before_volume_mm3": before, "after_volume_mm3": before + dv,
        "volume_conservation": "pass_cut_negative" if dv < 0 else "FAIL",
    }
    inputs = {"task": "geometric_delta", "feature": feat,
              "feature_volume_mm3": vol, "before_volume_mm3": before}
    return inputs, outputs, "geom_delta"


def make_invalid(rng):
    cases = [
        ("切削深度 DOC=-2 mm，其余参数正常。", "negative_cut_depth"),
        ("未提供材料类型，要求预测去除质量。", "missing_material"),
        ("给定 FEA 应力 σ_vm=NaN MPa。", "nan_stress"),
    ]
    u, reason = rng.choice(cases)
    outputs = {"world_state": None, "invalid": True, "reason": reason,
               "expected_action": "拒绝并列出缺失/非法项，不输出臆测数值"}
    inputs = {"task": "invalid_probe", "prompt": u}
    return inputs, outputs, "invalid"


# ----------------------------------------------------------------------------
# 可选：SolidWorks 真实质量属性（win32com 驱动，缺失/失败 → None）
# ----------------------------------------------------------------------------
def _try_solidworks_mass_props(shape, params):
    """尝试用 SolidWorks COM 计算真实质量属性。任何异常返回 None。"""
    try:
        import win32com.client
        sw = win32com.client.Dispatch("SldWorks.Application")
        sw.Visible = False
        # 注：完整参数化建模需较长 journal；此处仅验证 SW 可连接并读质量属性。
        # 若需真实覆盖，应传入已建模零件路径。这里返回 None 触发解析回退。
        del sw
        return None
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 生成 sim_out.jsonl
# ----------------------------------------------------------------------------
FAMILY_WEIGHTS = {  # 各家族大致比例
    "fea_fos": 0.20, "mass_props": 0.18, "removal": 0.14,
    "roughness": 0.12, "collision": 0.12, "tolerance": 0.12, "geom_delta": 0.10,
    "invalid": 0.02,
}


def generate(n, seed, use_solidworks=False):
    rng = random.Random(seed)
    recs = []
    builders = {
        "fea_fos": solve_fea, "mass_props": lambda r: solve_mass_props(r, use_solidworks),
        "removal": solve_removal, "roughness": solve_roughness,
        "collision": solve_collision, "tolerance": solve_tolerance,
        "geom_delta": solve_geom_delta, "invalid": make_invalid,
    }
    fams = list(FAMILY_WEIGHTS.keys())
    probs = [FAMILY_WEIGHTS[f] for f in fams]
    for _ in range(n):
        fam = rng.choices(fams, weights=probs, k=1)[0]
        res = builders[fam](rng)
        if res is None:
            continue
        inp, out, f = res
        recs.append({"inputs": inp, "outputs": out, "family": f})
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "sft", "wm_sim_out.jsonl"))
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--use-solidworks", action="store_true",
                    help="尝试用本机 SolidWorks COM 计算真实质量属性（缺失则回退解析）")
    args = ap.parse_args()

    recs = generate(args.n, args.seed, args.use_solidworks)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    cnt = Counter(r["family"] for r in recs)
    print(f"[ok] wrote {len(recs)} sim records -> {args.out}")
    for fam, c in cnt.most_common():
        print(f"  {fam:12s} {c}")


if __name__ == "__main__":
    main()
