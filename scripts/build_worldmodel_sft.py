#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 世界模型（World Model）SFT 数据集生成器
=============================================
目标：把 Qwen3-8B 训练成一个"制造世界模型"——给定结构化制造场景输入，
输出可被 CAD/CAE/CAM 工具链回灌验证的【世界状态预测】JSON。

两条数据来源：
  1) first-principles（默认）：用公认的 CNC 物理公式（MRR、Ra、FOS、公差、
     几何 ΔV、碰撞/过切、Auto-Diff 颜色）在参数空间采样，生成可复算真值。
     这本身就是" machining physics 世界模型"的监督信号。
  2) distill（--distill sim_out.jsonl）：读取 CAD/CAE 工具链真实输出
     （SolidWorks 质量属性 / FEA 应力报告 / VERICUT Auto-Diff / SSCNC 面板）
     转成 SFT 对，做"仿真器蒸馏"，让 LLM 逼近真实求解器。

输出格式与 train_qwen3_8b_qlora.py 完全兼容：
  {"messages":[{"role":"system",...},{"role":"user",...},{"role":"assistant",...}],
   "meta":{"stage":"WM","family":...}}

用法：
  python scripts/build_worldmodel_sft.py                 # 生成 first-principles 集
  python scripts/build_worldmodel_sft.py --out data/sft/virtu_worldmodel.jsonl --n 700
  python scripts/build_worldmodel_sft.py --distill sim_out.jsonl
"""
import os
import sys
import json
import math
import argparse
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DEFAULT = os.path.join(ROOT, "data", "sft", "virtu_worldmodel.jsonl")

try:
    from distill_local_solver import mass_props_csg  # 解析 CSG 质量属性
except Exception:
    mass_props_csg = None

SYSTEM = (
    "你是 Virtu 制造世界模型（World Model）。给定制造场景的结构化输入"
    "（毛坯/工件几何、刀具、切削参数、工艺指令），你必须输出可被 CAD/CAE/CAM "
    "工具链回灌验证的【世界状态预测】JSON，包含：材料去除量与几何变化 ΔV、"
    "表面粗糙度 Ra、关键 von Mises 应力与安全系数 FOS、刀轨碰撞/过切风险、"
    "公差配合与 Auto-Diff 颜色判定。所有数值必须带单位、可复算。"
    "只输出一个 JSON 对象，不要附加解释。"
)

# 常用材料密度 g/mm^3 与屈服强度 MPa
MATERIALS = {
    "45钢":   {"rho": 7.85e-3, "Sy": 355.0},
    "铝合金6061": {"rho": 2.70e-3, "Sy": 276.0},
    "不锈钢304": {"rho": 8.00e-3, "Sy": 215.0},
    "钛合金TC4": {"rho": 4.43e-3, "Sy": 830.0},
    "黄铜H62": {"rho": 8.50e-3, "Sy": 200.0},
}


def round_sig(x, n=4):
    if x == 0:
        return 0.0
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))


def make_messages(user_text, ws_json):
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": json.dumps(ws_json, ensure_ascii=False)},
        ],
        "meta": {"stage": "WM"},
    }


def gen_removal_mrr(rng):
    """材料去除率 / 去除体积 / 余下质量"""
    mat = rng.choice(list(MATERIALS))
    rho, Sy = MATERIALS[mat]["rho"], MATERIALS[mat]["Sy"]
    doc = round(rng.uniform(0.5, 4.0), 2)      # 切削深度 mm
    woc = round(rng.uniform(1.0, 10.0), 2)     # 切削宽度 mm
    vf = round(rng.uniform(80, 1200), 0)       # 进给速度 mm/min
    L = round(rng.uniform(20, 300), 1)         # 刀路长度 mm
    stock_vol = round(rng.uniform(50000, 500000), 0)  # 毛坯体积 mm^3
    mrr = doc * woc * vf                       # mm^3/min
    removed = doc * woc * L                    # mm^3
    removed_mass = removed * rho               # g
    stock_mass = stock_vol * rho
    remaining_mass = max(0.0, stock_mass - removed_mass)
    ws = {
        "world_state": {
            "material_removed_mm3": round_sig(removed),
            "mrr_mm3_per_min": round_sig(mrr),
            "removed_mass_g": round_sig(removed_mass, 3),
            "resulting_mass_g": round_sig(remaining_mass, 3),
            "delta_volume_mm3": round_sig(-removed),
            "volume_conservation": "pass_cut_negative",
        },
        "verification": {
            "formula": "MRR=DOC*WOC*vf; V_removed=DOC*WOC*L; m=rho*V",
            "checks": ["dV<0", "mrr>0"],
        },
    }
    u = (f"毛坯体积 {stock_vol:.0f} mm^3，材料 {mat}，密度 {rho*1000:.1f} g/cm^3。"
         f"用端铣刀单刀路：切削深度 DOC={doc} mm，切削宽度 WOC={woc} mm，"
         f"进给速度 vf={vf:.0f} mm/min，刀路长度 L={L} mm。预测去除量与余下质量。")
    return make_messages(u, ws)


def gen_roughness(rng):
    """表面粗糙度 Ra（车削近似 Ra=1000*f^2/(8*r_eps)）"""
    f = round(rng.uniform(0.05, 0.4), 3)        # 每转进给 mm/rev
    r_eps = round(rng.choice([0.2, 0.4, 0.8, 1.2, 1.6]), 2)  # 刀尖圆弧半径 mm
    ra = 1000.0 * f * f / (8.0 * r_eps)         # μm
    ws = {
        "world_state": {
            "feed_per_rev_mm": f,
            "nose_radius_mm": r_eps,
            "surface_roughness_ra_um": round_sig(ra, 3),
            "finish_class": "精加工" if ra < 3.2 else ("半精" if ra < 6.3 else "粗加工"),
        },
        "verification": {
            "formula": "Ra[um]=1000*f^2/(8*r_eps)",
            "checks": ["ra>0"],
        },
    }
    u = (f"车削外圆，每转进给 f={f} mm/rev，刀尖圆弧半径 r_ε={r_eps} mm。"
         f"预测加工表面粗糙度 Ra（μm）与对应粗糙度等级。")
    return make_messages(u, ws)


def gen_fea_fos(rng):
    """FEA 安全系数 FOS = Sy / von Mises"""
    mat = rng.choice(list(MATERIALS))
    Sy = MATERIALS[mat]["Sy"]
    sigma = round(rng.uniform(40, Sy * 1.4), 1)  # 施加的 von Mises 应力 MPa
    fos = Sy / sigma
    ws = {
        "world_state": {
            "material": mat,
            "yield_strength_mpa": Sy,
            "peak_von_mises_mpa": sigma,
            "safety_factor": round_sig(fos, 3),
            "fos_gate": "FOS>=1.5_pass" if fos >= 1.5 else "FOS<1.5_FAIL",
        },
        "verification": {
            "formula": "FOS=Sy/sigma_vm",
            "checks": ["FOS>=1.5"],
        },
    }
    u = (f"{mat}构件，屈服强度 Sy={Sy:.0f} MPa，FEA 算得峰值 von Mises 应力 "
         f"σ_vm={sigma} MPa。预测安全系数并判定 FOS≥1.5 是否通过。")
    return make_messages(u, ws)


def gen_collision_gcode(rng):
    """刀轨碰撞/过切风险（基于 G00 快速移动与安全平面）"""
    z_safe = round(rng.uniform(2.0, 30.0), 1)
    z_min_rapid = round(rng.uniform(-5.0, z_safe + 5.0), 1)  # 某段 G00 的最低 Z
    stock_top = round(rng.uniform(0.0, 20.0), 1)
    has_rapid_over_stock = (z_min_rapid < z_safe) and (z_min_rapid < stock_top + 1.0)
    risk = "high" if has_rapid_over_stock else "none"
    gouge = has_rapid_over_stock and (z_min_rapid < stock_top)
    ws = {
        "world_state": {
            "safe_plane_z_mm": z_safe,
            "rapid_min_z_mm": z_min_rapid,
            "stock_top_z_mm": stock_top,
            "collision_risk": risk,
            "gouge": bool(gouge),
            "autodiff": "red" if gouge else ("yellow" if risk == "high" else "green"),
        },
        "verification": {
            "formula": "risk = (Z_rapid_min < Z_safe) AND (Z_rapid_min < Z_stock_top+1)",
            "checks": ["no_gouge"],
        },
    }
    u = (f"分析一段 FANUC 加工程序：安全平面 Z={z_safe} mm，某 G00 快速移动段最低 "
         f"Z={z_min_rapid} mm，毛坯顶面 Z={stock_top} mm。预测碰撞/过切风险与 "
         f"VERICUT Auto-Diff 颜色（红=过切，黄=风险，绿=合格）。")
    return make_messages(u, ws)


def gen_tolerance(rng):
    """公差链 / 配合（极值法 + RSS + 配合等级）"""
    n = rng.randint(2, 4)
    tols = [round(rng.uniform(0.01, 0.1), 3) for _ in range(n)]  # 半公差 mm
    wc = sum(tols)                                  # 极值法半宽
    rss = math.sqrt(sum(t * t for t in tols))       # 统计法半宽
    # 间隙/干涉：基本尺寸偏差
    basic = round(rng.uniform(20, 100), 1)
    upper_dev = round(rng.uniform(0.0, 0.05), 3)
    lower_dev = round(rng.uniform(-0.05, 0.0), 3)
    clearance = upper_dev - lower_dev
    fit = "间隙配合" if clearance > 0 else ("过盈配合" if clearance < 0 else "过渡配合")
    fit_class = ("H7/g6" if clearance > 0.01 else ("H7/p6" if clearance < -0.01 else "H7/js6"))
    ws = {
        "world_state": {
            "component_tolerances_mm": tols,
            "closed_loop_worstcase_halfwidth_mm": round_sig(wc, 4),
            "closed_loop_rss_halfwidth_mm": round_sig(rss, 4),
            "basic_size_mm": basic,
            "fit_clearance_mm": round_sig(clearance, 4),
            "tolerance_fit": fit,
            "fit_class": fit_class,
            "tolerance_pass": bool(clearance >= -0.005),
        },
        "verification": {
            "formula": "WC=sum(ti); RSS=sqrt(sum(ti^2))",
            "checks": ["WC>=RSS"],
        },
    }
    u = (f"尺寸链含 {n} 个组成环，半公差分别为 {tols} mm（基本尺寸 {basic} mm）。"
         f"孔轴偏差：上偏差 +{upper_dev} mm，下偏差 {lower_dev} mm。"
         f"用极值法与统计法（RSS）给出封闭环公差带半宽，并判定配合性质与等级。")
    return make_messages(u, ws)


def gen_geometric_delta(rng):
    """特征切除的几何变化 ΔV 守恒断言"""
    feat = rng.choice(["通孔", "沉槽", "键槽", "倒角"])
    vol = round(rng.uniform(200, 8000), 0)
    before = round(rng.uniform(20000, 200000), 0)
    dv = -vol
    ws = {
        "world_state": {
            "feature": feat,
            "feature_volume_mm3": vol,
            "delta_volume_mm3": dv,
            "before_volume_mm3": before,
            "after_volume_mm3": before + dv,
            "volume_conservation": "pass_cut_negative" if dv < 0 else "FAIL",
        },
        "verification": {
            "formula": "dV = -V_feature (切除为负)",
            "checks": ["dV<0", "after=before+dV"],
        },
    }
    u = (f"在工件上切除一个{feat}，特征体积 {vol} mm^3，切除前工件体积 {before} mm^3。"
         f"预测切除后几何体积变化 ΔV 与切除后体积，并校验体积守恒。")
    return make_messages(u, ws)


def gen_mass_props(rng):
    """质量属性（体积/质量/质心/惯性矩）——解析 CSG 真实几何"""
    if mass_props_csg is None:
        return None
    shape = rng.choice(["box", "cylinder"])
    mat = rng.choice(list(MATERIALS))
    rho = MATERIALS[mat]["rho"]
    if shape == "box":
        l, w, h = (round(rng.uniform(40, 200), 1), round(rng.uniform(20, 150), 1),
                   round(rng.uniform(10, 120), 1))
        params = {"l": l, "w": w, "h": h}
    else:
        r = round(rng.uniform(10, 80), 1)
        h = round(rng.uniform(10, 150), 1)
        params = {"r": r, "h": h}
    V, (cx, cy, cz), (Ix, Iy, Iz) = mass_props_csg(shape, params, rho)
    ws = {
        "world_state": {
            "shape": shape,
            "volume_mm3": round(V, 2),
            "mass_g": round(V * rho, 3),
            "centroid_mm": [round(cx, 3), round(cy, 3), round(cz, 3)],
            "inertia_ixx_mm4": round(Ix, 2),
            "inertia_izz_mm4": round(Iz, 2),
            "solver": "analytic_csg",
        },
        "verification": {
            "formula": "V=l*w*h (box) | V=π r^2 h (cyl); m=ρV; centroid=几何中心; "
                       "I_box=截面两边之积×高^3/12 (mm^4), I_cyl=πr^4/4 与 πr^4/2 (mm^4)",
            "checks": ["V>0", "m>0"],
        },
    }
    if shape == "box":
        u = (f"预测{shape}（长 l={params['l']} mm，宽 w={params['w']} mm，"
             f"高 h={params['h']} mm）的质量属性：体积、质量、质心坐标、"
             f"绕质心惯性矩 Ixx 与 Izz。材料 {mat}。")
    else:
        u = (f"预测{shape}（半径 r={params['r']} mm，高 h={params['h']} mm）的"
             f"质量属性：体积、质量、质心坐标、绕质心惯性矩 Ixx 与 Izz。材料 {mat}。")
    return make_messages(u, ws)


def gen_invalid(rng):
    """鲁棒性：非法/矛盾输入 → 结构化 invalid 世界状态"""
    cases = [
        ("切削深度 DOC=-2 mm，其余参数正常。", "negative_cut_depth"),
        ("未提供材料类型，要求预测去除质量。", "missing_material"),
        ("给定 FEA 应力 σ_vm=NaN MPa。", "nan_stress"),
    ]
    u, reason = rng.choice(cases)
    ws = {
        "world_state": None,
        "invalid": True,
        "reason": reason,
        "expected_action": "拒绝并列出缺失/非法项，不输出臆测数值",
    }
    return make_messages(u, ws)


GENERATORS = [
    gen_removal_mrr, gen_roughness, gen_fea_fos,
    gen_collision_gcode, gen_tolerance, gen_geometric_delta,
    gen_mass_props,
]


def distill(sim_path):
    """仿真器蒸馏：读取 sim_out.jsonl（每行 {inputs, outputs, family}）转 SFT。"""
    out = []
    with open(sim_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            inp = d.get("inputs", {})
            res = d.get("outputs", {})
            fam = d.get("family", "sim")
            u = "仿真器输入：" + json.dumps(inp, ensure_ascii=False)
            ws = {
                "world_state": res,
                "verification": {"source": "simulator_distill", "family": fam},
            }
            out.append(make_messages(u, ws))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--n", type=int, default=700)
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--distill", default=None, help="仿真器输出 jsonl 路径")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    recs = []

    if args.distill:
        recs = distill(args.distill)
        print(f"[distill] loaded {len(recs)} sim records")
    else:
        n_per = max(1, args.n // (len(GENERATORS) + 1))
        for g in GENERATORS:
            for _ in range(n_per):
                r = g(rng)
                if r is not None:
                    recs.append(r)
        # 10% 鲁棒性负样本
        for _ in range(max(1, args.n // 10)):
            recs.append(gen_invalid(rng))
        rng.shuffle(recs)
        recs = recs[:args.n]
        print(f"[first-principles] generated {len(recs)} records")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[ok] wrote {len(recs)} -> {args.out}")


if __name__ == "__main__":
    main()
