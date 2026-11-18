#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 世界模型 v2 —— 「自纠错 + 设计 + 工艺规划 + 陌生环境适配」训练数据生成器
================================================================================
在 v1（first-principles 世界状态 + 仿真器蒸馏）之上，按用户目标新增四类监督信号：

  1. design_from_requirement  ：需求 -> 可直接驱动 CAD 建模的设计规格 + 质量属性
  2. machining_process_plan   ：零件/材料/精度 -> 工序序列 + 刀具 + 转速/进给 + MRR/Ra/工时
  3. unfamiliar_adaptation    ：给定「未在常识库里的材料/机床物性表」-> 用该表重算并判定
                               （训练"陌生环境快速适配"：用现场规格，不靠记忆）
  4. self_correction          ：【场景】+【LLM 草案】+【校验器反馈】-> 更正后的 world_state
                               + correction 说明（训练"世界模型更正 LLM 幻觉"）

所有数值真值由本地解析求解器 / 精确公式产生，可复算、可被 eval_worldmodel.py 验收。

输出：data/sft/virtu_worldmodel_v2.jsonl（与 train_qwen3_8b_qlora.py 兼容）
用法：
  python scripts/build_worldmodel_v2.py
  python scripts/build_worldmodel_v2.py --n-base 120 --n-design 150 --n-process 150 --n-adapt 120
"""
import os
import sys
import json
import math
import copy
import re
import random
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import build_worldmodel_sft as base  # noqa: E402
import wm_derivation  # noqa: E402  (契约要求 derivation，v2 历史语料缺这一段)
from distill_local_solver import mass_props_csg  # noqa: E402  (间接校验可用)

REL_TOL = 0.08  # 与 eval_worldmodel.py 一致

SYSTEM_V2 = base.SYSTEM + (
    " 额外规则："
    "(1) 若用户给出【草案】与【校验器反馈】，必须以反馈中的参考值为准更正，输出更正后的 "
    "world_state，并在 correction 字段说明错误类型、修正字段与修正量；若草案与参考一致则"
    "保持不变并确认，严禁无依据改动。"
    "(2) 若用户给出未在常识中的材料/机床物性表，必须严格使用该表数值计算，禁止臆造。"
    "(3) 设计任务需输出 design 规格（可直接驱动 CAD 建模）与 mass_props 世界状态。"
)


def mk(user, assistant_obj, scenario=None):
    # 契约规则 F：每个数值字段必须在顶层 derivation 给出代入算式；
    # 同时把闸门字面归一为 KEY_SCHEMA 字面（pass/fail、"true"/"false"）。
    if scenario is not None:
        wm_derivation.enrich(assistant_obj, scenario)
    rec = {
        "messages": [
            {"role": "system", "content": SYSTEM_V2},
            {"role": "user", "content": user},
            {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)},
        ],
        "meta": {"stage": "WMv2"},
    }
    # scenario 必须落盘：v1 的 make_messages 一直带，v2 此前只在传入时用于 enrich
    # 却不写入样本，导致 v2 语料（design/process/adapt/self_correction）没有任何
    # 可复算标注——评测只能靠 infer 反推族别与参数，族级判分无法逐条核对，
    # self_correction 的派生样本更是完全丢失来源场景。
    if scenario is not None:
        rec["scenario"] = scenario
    return rec


# ----------------------------------------------------------------------------
# 1) 需求 -> 设计规格 + 质量属性（"根据需求设计绘图"）
# ----------------------------------------------------------------------------
def _flange_mass(r_out, r_bore, t, n_holes, r_hole, rho):
    # 禁止 max(V,1) 静默夹紧（测量宪法第 5 条）：孔体积超过环形体积时负值
    # 必须暴露给上游判非法，而不是夹成 1.0 伪造一个正体积靶值。
    # 与 wm_verifier.recompute(design) 同口径（test_design_negative_volume...）。
    V = math.pi * (r_out ** 2 - r_bore ** 2) * t - n_holes * math.pi * r_hole ** 2 * t
    return V, V * rho


def gen_design_from_requirement(rng):
    mat = rng.choice(list(base.MATERIALS))
    rho = base.MATERIALS[mat]["rho"]
    d_out = round(rng.uniform(80, 400), 1)
    d_bore = round(rng.uniform(20, d_out * 0.6), 1)
    t = round(rng.uniform(8, 40), 1)
    n = rng.choice([4, 6, 8])
    d_hole = round(rng.uniform(6, 20), 1)
    pcd = round((d_out + d_bore) / 2.0 * rng.uniform(0.82, 0.95), 1)

    V, m = _flange_mass(d_out / 2.0, d_bore / 2.0, t, n, d_hole / 2.0, rho)
    if V <= 0 or (pcd - d_hole <= d_bore + 2.0) or (pcd + d_hole >= d_out - 2.0):
        pcd = round((d_out + d_bore) / 2.0, 1)
        d_hole = round(max(4.0, min(d_hole, (d_out - d_bore) * 0.35)), 1)
        V, m = _flange_mass(d_out / 2.0, d_bore / 2.0, t, n, d_hole / 2.0, rho)
    design = {
        "part_type": "flange",
        "outer_dia_mm": d_out,
        "bore_dia_mm": d_bore,
        "thickness_mm": t,
        "bolt_holes": {"count": n, "dia_mm": d_hole, "pcd_mm": pcd},
        "material": mat,
        "features": [
            {"kind": "cylinder", "dia_mm": d_out, "height_mm": t},
            {"kind": "through_hole", "dia_mm": d_bore, "axis": "Z"},
            {"kind": "bolt_hole_pattern", "count": n, "dia_mm": d_hole, "pcd_mm": pcd},
        ],
    }
    ws = {
        "design": design,
        "world_state": {
            "volume_mm3": base.round_sig(V, 5),
            "mass_g": base.round_sig(m, 5),
            "mass_kg": round(m / 1000.0, 4),
            "material": mat,
        },
        "verification": {
            "formula": "V=π(R_out²-R_bore²)t - n·π(R_hole²)t; m=ρV",
            "checks": ["V>0", "m>0"],
        },
    }
    u = (f"设计一个{mat}法兰：外径 φ{d_out} mm，中心孔 φ{d_bore} mm，厚度 {t} mm，"
         f"{n}×φ{d_hole} mm 螺栓孔均布于 φ{pcd} mm 节圆。"
         f"请给出可直接驱动 CAD 建模的设计规格（含特征树）与质量属性。")
    return mk(u, ws, {"task": "design", "inputs": {
        "r_out": d_out / 2.0, "r_bore": d_bore / 2.0, "t": t,
        "n_holes": n, "r_hole": d_hole / 2.0, "rho": rho}})


# ----------------------------------------------------------------------------
# 2) 工艺规划（"建模/仿真/加工"里的加工规划）
# ----------------------------------------------------------------------------
def gen_machining_process_plan(rng):
    mat = rng.choice(list(base.MATERIALS))
    D = round(rng.uniform(20, 120), 1)
    L = round(rng.uniform(50, 300), 1)
    ap = round(rng.uniform(0.5, 3.0), 2)
    f = round(rng.uniform(0.10, 0.35), 3)
    vc = round(rng.uniform(120, 300), 0)
    r_eps = rng.choice([0.4, 0.8, 1.2])

    n = 1000.0 * vc / (math.pi * D)          # rpm
    feed_rate = f * n                         # mm/min
    mrr = ap * f * vc * 1000.0                # mm^3/min
    ra = 1000.0 * f * f / (8.0 * r_eps)       # μm
    t_cut = (L / feed_rate) if feed_rate > 0 else 0.0

    ws = {
        "world_state": {
            "spindle_rpm": round(n, 1),
            "feed_rate_mm_per_min": round(feed_rate, 1),
            "mrr_mm3_per_min": base.round_sig(mrr, 4),
            "surface_roughness_ra_um": base.round_sig(ra, 3),
            "cut_time_min": round(t_cut, 3),
        },
        "process_plan": [
            {"op": "粗车", "tool": "CNMG120408", "ap_mm": ap,
             "f_mm_per_rev": f, "vc_m_per_min": vc},
            {"op": "精车", "tool": "VNMG160404", "ap_mm": 0.3,
             "f_mm_per_rev": round(f * 0.5, 3), "vc_m_per_min": round(vc * 1.2, 0)},
        ],
        "verification": {
            "formula": "n=1000·vc/(πD); vf=f·n; MRR=ap·f·vc·1000; Ra=1000f²/(8rε); t=L/vf",
            "checks": ["n>0", "MRR>0", "Ra>0"],
        },
    }
    u = (f"为{mat}轴类件（φ{D} mm，车削长度 {L} mm）制定车削工艺："
         f"粗车 ap={ap} mm、f={f} mm/rev、vc={vc} m/min，刀尖圆弧 rε={r_eps} mm。"
         f"给出主轴转速、进给速度、材料去除率 MRR、表面粗糙度 Ra 与单刀切削时间，并给出工序序列。")
    return mk(u, ws, {"task": "process", "inputs": {
        "D": D, "L": L, "ap": ap, "f": f, "vc": vc, "r_eps": r_eps}})


# ----------------------------------------------------------------------------
# 3) 陌生环境适配（用现场物性表/机床参数，不靠常识记忆）
# ----------------------------------------------------------------------------
UNFAMILIAR_MATS = [
    {"name": "Inconel 718", "rho": 8.19e-3, "Sy": 1030.0, "E": 2.05e5},
    {"name": "ZM6 镁合金", "rho": 1.82e-3, "Sy": 160.0, "E": 4.40e4},
    {"name": "17-4PH 沉淀硬化不锈钢", "rho": 7.80e-3, "Sy": 1000.0, "E": 1.96e5},
    {"name": "TA15 钛合金", "rho": 4.45e-3, "Sy": 855.0, "E": 1.10e5},
]
UNFAMILIAR_MACHINES = [
    {"name": "DMG MORI DMU 50", "n_max": 18000, "feed_max": 30000},
    {"name": "Haas VF-2", "n_max": 8100, "feed_max": 16000},
    {"name": "Mazak QTN 200", "n_max": 5000, "feed_max": 12000},
]


def gen_unfamiliar_adaptation(rng):
    mode = rng.choice(["material", "machine"])
    if mode == "material":
        m = rng.choice(UNFAMILIAR_MATS)
        sigma = round(rng.uniform(50.0, m["Sy"] * 1.2), 1)
        fos = m["Sy"] / sigma if sigma > 0 else float("inf")
        ws = {
            "world_state": {
                "material": m["name"],
                "yield_strength_mpa": m["Sy"],
                "peak_von_mises_mpa": sigma,
                "safety_factor": base.round_sig(fos, 3),
                "fos_gate": "pass" if fos >= 1.5 else "fail",
            },
            "adaptation": {"used_provided_spec": True, "source": "user_supplied_table"},
            "verification": {"formula": "FOS=Sy/σ_vm (Sy 来自用户物性表)", "checks": ["FOS>0"]},
        }
        u = (f"陌生材料 {m['name']}（不在标准库）。现场物性表：密度 {m['rho']*1000:.2f} g/cm³，"
             f"屈服强度 {m['Sy']} MPa，弹性模量 {m['E']:.0f} MPa。"
             f"构件 FEA 峰值 von Mises 应力 σ_vm={sigma} MPa。"
             f"请严格用该表数据预测安全系数并判定 FOS≥1.5 是否通过。")
        return mk(u, ws, {"task": "adapt_material", "inputs": {"Sy": m["Sy"], "sigma": sigma}})
    else:
        mc = rng.choice(UNFAMILIAR_MACHINES)
        D = round(rng.uniform(10, 80), 1)
        vc = round(rng.uniform(80, 300), 0)
        n = 1000.0 * vc / (math.pi * D)
        ok = n <= mc["n_max"]
        ws = {
            "world_state": {
                "machine": mc["name"],
                "required_spindle_rpm": round(n, 1),
                "machine_max_rpm": mc["n_max"],
                "within_limit": bool(ok),
                "recommended_vc_m_per_min": round(vc, 0),
            },
            "adaptation": {"used_provided_spec": True, "source": "user_supplied_table"},
            "verification": {"formula": "n=1000·vc/(πD); within = n<=n_max", "checks": ["n>0"]},
        }
        u = (f"陌生机床 {mc['name']}（现场参数表：最高转速 {mc['n_max']} rpm，"
             f"最大进给 {mc['feed_max']} mm/min）。要在 φ{D} mm 工件上以 vc={vc} m/min 车削，"
             f"需多少转速？是否超出机床能力？请严格按参数表判定。")
        return mk(u, ws, {"task": "adapt_machine", "inputs": {"D": D, "vc": vc, "n_max": mc["n_max"]}})


# ----------------------------------------------------------------------------
# 4) 自纠错（"LLM 幻觉 -> 世界模型/校验器更正"）
# ----------------------------------------------------------------------------
def _numeric_leaves(obj, path=""):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            out += _numeric_leaves(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _numeric_leaves(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append((path, obj))
    return out


def _set_path(obj, path, value):
    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur = obj
    for i, tok in enumerate(tokens):
        last = i == len(tokens) - 1
        if tok.startswith("["):
            idx = int(tok[1:-1])
            if last:
                cur[idx] = value
            else:
                cur = cur[idx]
        else:
            if last:
                cur[tok] = value
            else:
                cur = cur[tok]


def gen_self_correction(rng, rec):
    """从一个已知真值样本生成两条纠错样本：拒错更正 + 确认无误。"""
    try:
        ws = json.loads(rec["messages"][2]["content"])
    except Exception:
        return []
    if not isinstance(ws, dict) or not ws.get("world_state"):
        return []
    orig_user = rec["messages"][1]["content"]
    inner = ws["world_state"]
    # 纠错样本的正确答案同样必须带 derivation，否则模型学到「纠错后不用给算式」
    deriv = ws.get("derivation")
    scen = rec.get("scenario")

    cand = [(p, v) for p, v in _numeric_leaves(inner) if abs(v) > 1e-9]
    if not cand:
        return []

    field, true_v = rng.choice(cand)
    factor = 1.0 + rng.choice([-1, 1]) * rng.uniform(0.12, 0.45)
    draft_v = round(float(true_v) * factor, 6)
    if abs(draft_v - true_v) < 1e-9:
        draft_v = float(true_v) * 1.25
    rel_err = abs(draft_v - true_v) / max(abs(true_v), 1e-9)

    draft = copy.deepcopy(ws)
    _set_path(draft, "world_state." + field, draft_v)

    # (a) 草案错误 -> 更正
    wrong_out = {
        "world_state": inner,
        "correction": {
            "changed": True,
            "error_type": "numeric_hallucination",
            "corrections": [{
                "field": field, "draft": draft_v,
                "reference": true_v, "rel_err": round(rel_err, 4),
            }],
            "explanation": (
                f"{field} 草案值 {draft_v} 与求解器参考值 {true_v} 相对偏差 "
                f"{rel_err*100:.1f}%，超过 {int(REL_TOL*100)}% 容差，已按参考值更正。"
            ),
        },
        "verification": {"source": "verifier_L2", "rel_tol": REL_TOL, "resolved": True},
    }
    if deriv:
        wrong_out["derivation"] = copy.deepcopy(deriv)
    user_wrong = (
        f"【场景】{orig_user}\n"
        f"【草案】{json.dumps(draft, ensure_ascii=False)}\n"
        f"【校验器反馈】{json.dumps({'level': 'L2', 'rel_tol': REL_TOL, 'verdict': 'reject', 'issues': [{'field': field, 'draft': draft_v, 'reference': true_v, 'rel_err': round(rel_err, 4)}]}, ensure_ascii=False)}\n"
        f"请依据校验器反馈输出更正后的 world_state；若草案正确则确认不变。"
    )

    # (b) 草案正确 -> 确认
    ok_out = {
        "world_state": inner,
        "correction": {
            "changed": False, "error_type": "none", "corrections": [],
            "explanation": "草案与校验器参考一致，无需修改。",
        },
        "verification": {"source": "verifier_L2", "rel_tol": REL_TOL, "resolved": True},
    }
    if deriv:
        ok_out["derivation"] = copy.deepcopy(deriv)
    user_ok = (
        f"【场景】{orig_user}\n"
        f"【草案】{json.dumps(ws, ensure_ascii=False)}\n"
        f"【校验器反馈】{json.dumps({'level': 'L2', 'rel_tol': REL_TOL, 'verdict': 'accept', 'issues': []}, ensure_ascii=False)}\n"
        f"请依据校验器反馈输出更正后的 world_state；若草案正确则确认不变。"
    )
    return [mk(user_wrong, wrong_out, scen), mk(user_ok, ok_out, scen)]


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "sft", "virtu_worldmodel_v2.jsonl"))
    ap.add_argument("--n-base", type=int, default=110, help="每个 first-principles 族样本数")
    ap.add_argument("--n-design", type=int, default=150)
    ap.add_argument("--n-process", type=int, default=150)
    ap.add_argument("--n-adapt", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--no-sim", action="store_true", help="不合并已蒸馏的仿真器真值")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    recs = []

    # 1) 原有物理族（first-principles）
    base_recs = []
    for g in base.GENERATORS:
        for _ in range(args.n_base):
            r = g(rng)
            if r:
                base_recs.append(r)
    for _ in range(max(1, args.n_base // 6)):
        base_recs.append(base.gen_invalid(rng))
    recs.extend(base_recs)

    # 2) 新能力族
    for _ in range(args.n_design):
        recs.append(gen_design_from_requirement(rng))
    for _ in range(args.n_process):
        recs.append(gen_machining_process_plan(rng))
    for _ in range(args.n_adapt):
        recs.append(gen_unfamiliar_adaptation(rng))

    # 3) 自纠错（从有真值的样本派生）
    sc_src = []
    for r in base_recs:
        try:
            d = json.loads(r["messages"][2]["content"])
            if isinstance(d, dict) and d.get("world_state"):
                sc_src.append(r)
        except Exception:
            pass
    rng.shuffle(sc_src)
    sc_n = 0
    for r in sc_src[: min(len(sc_src) // 2, 220)]:
        eps = gen_self_correction(rng, r)
        recs.extend(eps)
        sc_n += len(eps)

    # 4) 合并仿真器蒸馏真值（400 + autocad）
    if not args.no_sim:
        for fn in ["virtu_worldmodel_distilled.jsonl", "virtu_worldmodel_autocad.jsonl"]:
            p = os.path.join(ROOT, "data", "sft", fn)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            recs.append(json.loads(line))

    rng.shuffle(recs)
    # 合并蒸馏源后必然出现重复行（旧语料实测 2049 行里 24 行重复）。
    # 以「同一条 assistant 答案」为唯一键去重，避免重复样本虚增训练权重。
    seen, uniq = set(), []
    for r in recs:
        key = r["messages"][2]["content"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    if len(uniq) != len(recs):
        print(f"[dedup] 丢弃重复样本 {len(recs) - len(uniq)} 条")
    recs = uniq

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 蒸馏源的历史 mm^5 靶值由官方审计工具就地修复，输出必须过量纲闸：
    # 生成器侧已接待修正的 mass_props_csg，但并入的 virtu_worldmodel_distilled.jsonl
    # 是旧求解器输出的冻结件（实测 81 条坏行），不修复会污染新语料。
    import corpus_unit_audit as AUD
    import normalize_wm_corpus as NWC
    tmp = args.out + ".units_tmp"
    rep = AUD.fix(args.out, tmp)
    os.replace(tmp, args.out)
    if rep["rewritten"]:
        print(f"[unit-audit] 修复 {rep['rewritten']} 行 mm^5 靶值（蒸馏源历史遗留）")
    AUD.assert_units_clean(args.out)
    NWC.process_file(args.out, apply=True)

    fam = {}
    for r in recs:
        a = r["messages"][2]["content"]
        if '"correction"' in a:
            k = "self_correction"
        elif '"design"' in a:
            k = "design"
        elif '"process_plan"' in a:
            k = "process_plan"
        elif '"adaptation"' in a:
            k = "adaptation"
        else:
            k = "world_state"
        fam[k] = fam.get(k, 0) + 1

    print(f"[ok] wrote {len(recs)} -> {args.out}")
    print(f"[stats] {json.dumps(fam, ensure_ascii=False)}  (self-correction episodes={sc_n})")


if __name__ == "__main__":
    main()
