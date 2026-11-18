#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 自主智能体轨迹 SFT 数据生成器（Agentic Trajectories）
============================================================
为「世界模型具备自主思考、自主决策」构造多轮轨迹监督信号：

    user(任务) -> assistant{think, plan, action{tool,args}}
               -> tool{ok, result}              (真实求解器返回，唯一真值)
               -> assistant{think, verify, action{finalize}}
               -> tool{ok}
               -> assistant{world_state/design, decision, verification}

训练器（train_qwen3_8b_qlora.py 系列）只对 assistant 段算 loss，
tool 段全 mask —— 因此模型学的是"怎么想、怎么选工具、怎么校验、怎么定稿"。

六类轨迹：
  1. fea_agent      ：梁强度 -> 调 fea_solver -> FOS 判定
  2. removal_agent  ：切削去除 -> 调 mrr_calc -> 体积守恒校验
  3. design_agent   ：需求 -> 调 mass_props -> 设计规格 + 质量属性
  4. collision_agent：G 代码 -> 调 collision_check -> 过切/碰撞决策
  5. recover_agent  ：首次工具调用单位错误 -> 自检发现 -> 重规划重算
  6. ood_agent      ：陌生材料物性表 -> 严格用表重算 -> 适配决策

输出：data/sft/virtu_agentic.jsonl
用法：python scripts/build_agentic_sft.py --n 120
"""
import os
import sys
import json
import math
import random
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

from distill_local_solver import fea_beam_fem, mass_props_csg, MATERIALS as MATS  # noqa: E402

AGENT_SYSTEM = (
    "你是 Virtu 自主制造世界模型智能体。面对任何工程任务，你必须自主完成："
    "(1) think：分析任务、识别已知/未知、指出需要的物理量；"
    "(2) plan：列出步骤与要调用的工具；"
    "(3) act：以 action={tool,args} 调用工业工具"
    "（fea_solver / mrr_calc / mass_props / collision_check / use_spec）；"
    "(4) observe：读取工具返回的真实结果，严禁臆造；"
    "(5) verify：用守恒律/边界/容差自检；"
    "(6) replan：若工具失败或结果超差，说明原因并改进后重试；"
    "(7) finalize：给出最终 world_state JSON。"
    "工具返回是唯一真值来源；缺关键参数时先补全或明确拒绝。"
)


def _j(o):
    return json.dumps(o, ensure_ascii=False)


def traj(family, user, turns, final, mask_turn_indices=()):
    msgs = [{"role": "system", "content": AGENT_SYSTEM},
            {"role": "user", "content": user}]
    for idx, (a, t) in enumerate(turns):
        asst_msg = {"role": "assistant", "content": _j(a)}
        if idx in mask_turn_indices:
            asst_msg["loss"] = False
        msgs.append(asst_msg)
        if t is not None:
            msgs.append({"role": "tool", "content": _j(t)})
    msgs.append({"role": "assistant", "content": _j(final)})
    return {"messages": msgs, "meta": {"stage": "AGENT", "family": family}}


def _flange_mass(r_out, r_bore, t, n, r_hole, rho):
    V = math.pi * (r_out ** 2 - r_bore ** 2) * t - n * math.pi * r_hole ** 2 * t
    return V, V * rho


# ---------------------------------------------------------------------------
def gen_fea_agent(rng):
    mat = rng.choice(list(MATS))
    m = MATS[mat]
    b = round(rng.uniform(10, 60), 1)
    h = round(rng.uniform(10, 80), 1)
    L = round(rng.uniform(100, 600), 1)
    F = round(rng.uniform(50, 5000), 1)
    I = b * h ** 3 / 12.0
    fem = fea_beam_fem(m["E"], I, L, b, h, F, n_elem=12)
    if fem is None:
        return None
    sigma = fem["peak_von_mises_mpa"]
    fos = m["Sy"] / sigma if sigma > 0 else float("inf")
    gate = "pass" if fos >= 1.5 else "fail"

    user = (f"【任务】校核悬臂梁强度。材料 {mat}（Sy={m['Sy']} MPa, E={m['E']:.0f} MPa），"
            f"截面 {b}×{h} mm，悬臂长 {L} mm，自由端集中载荷 {F} N。要求 FOS≥1.5。")
    a1 = {"think": "需要峰值弯曲应力与安全系数；用 fea_solver 直接算，不自估。",
          "plan": ["调 fea_solver 求 peak_von_mises / 挠度", "用 Sy/σ 判 FOS", "定稿"],
          "action": {"tool": "fea_solver",
                     "args": {"E": m["E"], "I": round(I, 2), "L": L, "b": b, "h": h, "F": F}}}
    t1 = {"ok": True, "result": {"peak_von_mises_mpa": sigma,
                                 "tip_deflection_mm": fem["tip_deflection_mm"]}}
    a2 = {"think": f"σ_vm={sigma} MPa，FOS={m['Sy']}/{sigma}={fos:.3f}，与阈值 1.5 比较。",
          "verify": {"safety_factor": round(fos, 3), "gate": gate,
                     "check": "FOS = Sy / σ_vm"},
          "action": {"tool": "finalize", "args": {}}}
    t2 = {"ok": True}
    final = {"world_state": {"material": mat, "yield_strength_mpa": m["Sy"],
                             "peak_von_mises_mpa": sigma,
                             "tip_deflection_mm": fem["tip_deflection_mm"],
                             "safety_factor": round(fos, 3), "fos_gate": gate},
             "decision": "通过" if fos >= 1.5 else "不通过，需增大截面或更换材料",
             "verification": {"formula": "FOS=Sy/σ_vm", "checks": ["FOS>=1.5"]}}
    return traj("fea_agent", user, [(a1, t1), (a2, t2)], final)


def gen_removal_agent(rng):
    mat = rng.choice(list(MATS))
    rho = MATS[mat]["rho"]
    doc = round(rng.uniform(0.5, 4.0), 2)
    woc = round(rng.uniform(1.0, 10.0), 2)
    vf = round(rng.uniform(80, 1200), 0)
    L = round(rng.uniform(20, 300), 1)
    stock_vol = round(rng.uniform(50000, 500000), 0)
    removed = doc * woc * L
    mrr = doc * woc * vf
    removed_mass = removed * rho
    remaining = max(0.0, stock_vol * rho - removed_mass)

    user = (f"【任务】预测单刀路材料去除。毛坯体积 {stock_vol:.0f} mm³，材料 {mat}"
            f"（ρ={rho*1000:.1f} g/cm³）；DOC={doc} mm，WOC={woc} mm，vf={vf:.0f} mm/min，"
            f"刀路长 {L} mm。")
    a1 = {"think": "需要去除体积、MRR、去除质量与余量；用精确公式，不近似。",
          "plan": ["调 mrr_calc", "校验 ΔV<0 与质量守恒"],
          "action": {"tool": "mrr_calc",
                     "args": {"doc": doc, "woc": woc, "vf": vf, "L": L,
                              "rho": rho, "stock_vol": stock_vol}}}
    t1 = {"ok": True, "result": {"material_removed_mm3": round(removed, 3),
                                 "mrr_mm3_per_min": round(mrr, 3),
                                 "removed_mass_g": round(removed_mass, 4),
                                 "resulting_mass_g": round(remaining, 4)}}
    a2 = {"think": f"去除 {removed:.2f} mm³ -> ΔV={-removed:.2f}<0，守恒成立。",
          "verify": {"delta_volume_mm3": round(-removed, 3),
                     "volume_conservation": "pass"},
          "action": {"tool": "finalize", "args": {}}}
    t2 = {"ok": True}
    final = {"world_state": {"material_removed_mm3": round(removed, 3),
                             "mrr_mm3_per_min": round(mrr, 3),
                             "removed_mass_g": round(removed_mass, 4),
                             "resulting_mass_g": round(remaining, 4),
                             "delta_volume_mm3": round(-removed, 3),
                             "volume_conservation": "pass"},
             "decision": "参数可用，预计去除量与余量如 world_state",
             "verification": {"formula": "MRR=DOC·WOC·vf; V=DOC·WOC·L",
                              "checks": ["dV<0", "mass_conservation"]}}
    return traj("removal_agent", user, [(a1, t1), (a2, t2)], final)


def gen_design_agent(rng):
    mat = rng.choice(list(MATS))
    rho = MATS[mat]["rho"]
    d_out = round(rng.uniform(80, 400), 1)
    d_bore = round(rng.uniform(20, d_out * 0.6), 1)
    t = round(rng.uniform(8, 40), 1)
    n = rng.choice([4, 6, 8])
    d_hole = round(rng.uniform(6, 20), 1)
    pcd = round((d_out + d_bore) / 2 * rng.uniform(0.82, 0.95), 1)
    V, mass = _flange_mass(d_out / 2, d_bore / 2, t, n, d_hole / 2, rho)
    if V <= 0 or (pcd - d_hole <= d_bore + 2.0) or (pcd + d_hole >= d_out - 2.0):
        pcd = round((d_out + d_bore) / 2.0, 1)
        d_hole = round(max(4.0, min(d_hole, (d_out - d_bore) * 0.35)), 1)
        V, mass = _flange_mass(d_out / 2, d_bore / 2, t, n, d_hole / 2, rho)

    user = (f"【任务】设计 {mat} 法兰：外径 φ{d_out}，中心孔 φ{d_bore}，厚 {t} mm，"
            f"{n}×φ{d_hole} 螺栓孔 @ φ{pcd} 节圆。输出 CAD 设计规格与质量属性。")
    a1 = {"think": "先定特征树（外圆柱-中心通孔-螺栓孔阵列），再算体积/质量。",
          "plan": ["调 mass_props 验证体积/质量", "输出 design 规格"],
          "action": {"tool": "mass_props",
                     "args": {"shape": "flange", "r_out": d_out / 2, "r_bore": d_bore / 2,
                              "t": t, "n_holes": n, "r_hole": d_hole / 2, "rho": rho}}}
    t1 = {"ok": True, "result": {"volume_mm3": round(V, 2), "mass_g": round(mass, 3)}}
    a2 = {"think": f"V={V:.1f} mm³ >0，m={mass:.1f} g >0，几何自洽。",
          "verify": {"volume_mm3": round(V, 2), "mass_g": round(mass, 3), "check": "V>0,m>0"},
          "action": {"tool": "finalize", "args": {}}}
    t2 = {"ok": True}
    final = {"design": {"part_type": "flange", "outer_dia_mm": d_out, "bore_dia_mm": d_bore,
                        "thickness_mm": t,
                        "bolt_holes": {"count": n, "dia_mm": d_hole, "pcd_mm": pcd},
                        "material": mat,
                        "features": [{"kind": "cylinder", "dia_mm": d_out, "height_mm": t},
                                     {"kind": "through_hole", "dia_mm": d_bore, "axis": "Z"},
                                     {"kind": "bolt_hole_pattern", "count": n,
                                      "dia_mm": d_hole, "pcd_mm": pcd}]},
             "world_state": {"volume_mm3": round(V, 2), "mass_g": round(mass, 3),
                             "mass_kg": round(mass / 1000, 4), "material": mat},
             "decision": "设计可用，可直接驱动 CAD 建模",
             "verification": {"formula": "V=π(R_out²-R_bore²)t - nπr_h²t", "checks": ["V>0"]}}
    return traj("design_agent", user, [(a1, t1), (a2, t2)], final)


def gen_collision_agent(rng):
    z_safe = round(rng.uniform(2.0, 30.0), 1)
    z_min = round(rng.uniform(-5.0, z_safe + 5.0), 1)
    stock_top = round(rng.uniform(0.0, 20.0), 1)
    risk = (z_min < z_safe) and (z_min < stock_top + 1.0)
    gouge = z_min < stock_top
    color = "red" if gouge else ("yellow" if risk else "green")

    user = (f"【任务】检查 FANUC 程序安全性：安全平面 Z={z_safe} mm，某 G00 最低 Z={z_min} mm，"
            f"毛坯顶面 Z={stock_top} mm。给碰撞/过切判定与 Auto-Diff 颜色。")
    a1 = {"think": "把 G00 最低点与安全平面/毛坯顶面比较，判断风险与过切。",
          "plan": ["调 collision_check", "红色则拒收并改刀轨"],
          "action": {"tool": "collision_check",
                     "args": {"z_safe": z_safe, "z_min_rapid": z_min, "stock_top": stock_top}}}
    t1 = {"ok": True, "result": {"collision_risk": "high" if risk else "none",
                                 "gouge": bool(gouge), "autodiff": color}}
    a2 = {"think": f"gouge={gouge}，颜色={color}；{'必须抬刀/改安全平面' if gouge else '可执行'}。",
          "verify": {"gouge": bool(gouge), "autodiff": color, "check": "no_gouge"},
          "action": {"tool": "finalize", "args": {}}}
    t2 = {"ok": True}
    final = {"world_state": {"safe_plane_z_mm": z_safe, "rapid_min_z_mm": z_min,
                             "stock_top_z_mm": stock_top,
                             "collision_risk": "high" if risk else "none",
                             "gouge": bool(gouge), "autodiff": color},
             "decision": "拒收刀轨，抬高安全平面后重出程序" if gouge else
                         ("降速/检查快移路径" if risk else "刀轨安全，可执行"),
             "verification": {"formula": "risk=(Zmin<Zsafe)∧(Zmin<Ztop+1)", "checks": ["no_gouge"]}}
    return traj("collision_agent", user, [(a1, t1), (a2, t2)], final)


def gen_recover_agent(rng):
    """单位错误自恢复：任务给 kN，首次误用 N，工具告警 -> 自检重算。"""
    mat = rng.choice(list(MATS))
    m = MATS[mat]
    b = round(rng.uniform(10, 60), 1)
    h = round(rng.uniform(10, 80), 1)
    L = round(rng.uniform(100, 600), 1)
    F_kN = round(rng.uniform(1, 20), 2)
    F_N = F_kN * 1000.0
    I = b * h ** 3 / 12.0
    fem_wrong = fea_beam_fem(m["E"], I, L, b, h, F_kN, n_elem=12)
    fem_ok = fea_beam_fem(m["E"], I, L, b, h, F_N, n_elem=12)
    if fem_ok is None:
        return None
    sigma = fem_ok["peak_von_mises_mpa"]
    fos = m["Sy"] / sigma if sigma > 0 else float("inf")

    user = (f"【任务】校核悬臂梁。材料 {mat}，截面 {b}×{h} mm，长 {L} mm，"
            f"自由端载荷 {F_kN} kN。要求 FOS≥1.5。")
    a1 = {"think": "按公式直接调 fea_solver 求应力。",
          "plan": ["调 fea_solver", "算 FOS"],
          "action": {"tool": "fea_solver",
                     "args": {"E": m["E"], "I": round(I, 2), "L": L, "b": b, "h": h, "F": F_kN}}}
    t1 = {"ok": True,
          "result": {"peak_von_mises_mpa": fem_wrong["peak_von_mises_mpa"] if fem_wrong else 0.0,
                     "tip_deflection_mm": fem_wrong["tip_deflection_mm"] if fem_wrong else 0.0},
          "warning": "载荷单位可疑：任务为 kN，输入 F 仅 %.2f，请确认是否应为 %.0f N" % (F_kN, F_N)}
    a2 = {"think": f"工具告警：任务写 {F_kN} kN，我误传 {F_kN} N，量级差 1000 倍。按 {F_N:.0f} N 重算。",
          "plan": ["修正单位后重调 fea_solver", "再判 FOS"],
          "action": {"tool": "fea_solver",
                     "args": {"E": m["E"], "I": round(I, 2), "L": L, "b": b, "h": h, "F": F_N}}}
    t2 = {"ok": True, "result": {"peak_von_mises_mpa": sigma,
                                 "tip_deflection_mm": fem_ok["tip_deflection_mm"]}}
    a3 = {"think": f"修正后 σ={sigma} MPa，FOS={fos:.3f}。",
          "verify": {"safety_factor": round(fos, 3),
                     "gate": "pass" if fos >= 1.5 else "fail",
                     "check": "unit fix + FOS=Sy/σ"},
          "action": {"tool": "finalize", "args": {}}}
    t3 = {"ok": True}
    final = {"world_state": {"material": mat, "yield_strength_mpa": m["Sy"],
                             "peak_von_mises_mpa": sigma,
                             "tip_deflection_mm": fem_ok["tip_deflection_mm"],
                             "safety_factor": round(fos, 3),
                             "fos_gate": "pass" if fos >= 1.5 else "fail"},
             "decision": "通过" if fos >= 1.5 else "不通过，需加强",
             "correction": {"error_type": "unit_error", "from": f"{F_kN} N", "to": f"{F_N:.0f} N"},
             "verification": {"formula": "FOS=Sy/σ", "checks": ["unit_fixed", "FOS>=1.5"]}}
    return traj("recover_agent", user, [(a1, t1), (a2, t2), (a3, t3)], final, mask_turn_indices=(0,))


OOD = [
    {"name": "Inconel 718", "rho": 8.19e-3, "Sy": 1030.0},
    {"name": "ZM6 镁合金", "rho": 1.82e-3, "Sy": 160.0},
    {"name": "17-4PH 不锈钢", "rho": 7.80e-3, "Sy": 1000.0},
]


def gen_ood_agent(rng):
    m = rng.choice(OOD)
    sigma = round(rng.uniform(50.0, m["Sy"] * 1.2), 1)
    fos = m["Sy"] / sigma
    user = (f"【任务】陌生材料 {m['name']}，现场物性表：密度 {m['rho']*1000:.2f} g/cm³，"
            f"屈服 {m['Sy']} MPa。FEA 峰值 σ_vm={sigma} MPa。判 FOS≥1.5。")
    a1 = {"think": "该材料不在标准库，必须用现场物性表的 Sy，禁止用记忆值。",
          "plan": ["用给定 Sy 计算 FOS", "判定并说明来源"],
          "action": {"tool": "use_spec", "args": {"Sy": m["Sy"], "sigma": sigma}}}
    t1 = {"ok": True, "result": {"safety_factor": round(fos, 3)}}
    a2 = {"think": f"FOS={fos:.3f}（来源：现场物性表 Sy={m['Sy']} MPa）。",
          "verify": {"safety_factor": round(fos, 3), "source": "user_supplied_table"},
          "action": {"tool": "finalize", "args": {}}}
    t2 = {"ok": True}
    final = {"world_state": {"material": m["name"], "yield_strength_mpa": m["Sy"],
                             "peak_von_mises_mpa": sigma, "safety_factor": round(fos, 3),
                             "fos_gate": "pass" if fos >= 1.5 else "fail"},
             "adaptation": {"used_provided_spec": True, "source": "user_supplied_table"},
             "decision": "通过" if fos >= 1.5 else "不通过，需加强",
             "verification": {"formula": "FOS=Sy/σ (Sy 来自现场表)", "checks": ["FOS>=1.5"]}}
    return traj("ood_agent", user, [(a1, t1), (a2, t2)], final)


GENS = [gen_fea_agent, gen_removal_agent, gen_design_agent,
        gen_collision_agent, gen_recover_agent, gen_ood_agent]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "sft", "virtu_agentic.jsonl"))
    ap.add_argument("--n", type=int, default=120, help="每类轨迹样本数")
    ap.add_argument("--seed", type=int, default=20261103)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    recs = []
    for g in GENS:
        made = 0
        for _ in range(args.n * 2):
            if made >= args.n:
                break
            r = g(rng)
            if r:
                recs.append(r)
                made += 1
        print(f"  {g.__name__}: {made}")
    rng.shuffle(recs)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    fam = {}
    for r in recs:
        k = r["meta"]["family"]
        fam[k] = fam.get(k, 0) + 1
    print(f"[ok] wrote {len(recs)} agentic trajectories -> {args.out}")
    print(f"[stats] {json.dumps(fam, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
