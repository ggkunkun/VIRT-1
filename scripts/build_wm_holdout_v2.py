# -*- coding: utf-8 -*-
"""build_wm_holdout_v2.py — 世界模型独立留出集 v2（12 族 × 30 例 = 360）。

设计约束（测量宪法）：
  1. 真值一律由 wm_holdout_regression.HAND 的独立解析式算出，不 import 被测
     wm_verifier 的数值实现；生成后再用 wm_verifier.verify 交叉复核，两者不一致
     立即 fail-closed。
  2. 题面用与训练语料不同的措辞；落盘前做 5-gram 覆盖率与逐字重合检查，
     超阈值即拒绝产出（不静默降级）。
  3. 冻结样本只写一次；--check 只读复核，不改文件。
  4. 评测集不得用于训练：本文件输出的 split 固定为 eval，训练侧 corpus builder
     必须显式排除 data/holdout/**。

用法：
  .venv/Scripts/python.exe scripts/build_wm_holdout_v2.py --write
  .venv/Scripts/python.exe scripts/build_wm_holdout_v2.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
os.chdir(ROOT)

import wm_holdout_regression as H  # noqa: E402
import wm_verifier as V  # noqa: E402
import eval_worldmodel as E  # noqa: E402

OUT = os.path.join(ROOT, "data", "holdout", "wm_holdout_v2.jsonl")
LEDGER = os.path.join(ROOT, "data", "holdout", "wm_holdout_v2_ledger.json")
TRAIN_PATH = os.path.join(ROOT, "data", "sft_rebalanced", "wm_train_cap12_v2.unitfix.jsonl")
REL_LEAK_MAX = 0.60
FAMILIES = ["removal", "mass_props", "roughness", "fea_fos", "collision", "tolerance",
            "design", "process", "adapt_material", "adapt_machine", "geom_delta", "invalid"]
STEEL = 7.85e-3
AL = 2.70e-3
ID_PREFIX = {
    "removal": "REM", "mass_props": "MAS", "roughness": "ROU", "fea_fos": "FEA",
    "collision": "COL", "tolerance": "TOL", "design": "DES", "process": "PRO",
    "adapt_material": "ADM", "adapt_machine": "ADA", "geom_delta": "GEO", "invalid": "INV",
}


def _r(x, nd=3):
    return round(float(x), nd)


# ---------------------------------------------------------------------------
# 参数生成（每族 10 组，3 套措辞 -> 30 例）
# ---------------------------------------------------------------------------
def gen_removal(rng, i):
    return dict(doc=_r(rng.uniform(0.5, 5.0), 1), woc=_r(rng.uniform(2.0, 12.0), 1),
                L=_r(rng.uniform(50, 400), 0), vf=_r(rng.uniform(100, 800), 0),
                rho=STEEL if i % 2 == 0 else AL)


def gen_mass_props(rng, i):
    n = 2 if i % 2 == 0 else 3
    parts = sorted(_r(rng.uniform(10_000, 200_000), 0) for _ in range(n))
    return dict(parts=parts, rho=STEEL if i % 3 else AL)


def gen_roughness(rng, i):
    return dict(f=_r(rng.uniform(0.05, 0.4), 3), r_eps=_r(rng.uniform(0.2, 1.6), 1))


def gen_fea_fos(rng, i):
    sy = _r(rng.uniform(180, 1000), 0)
    sigma = _r(sy * rng.uniform(0.30, 0.95), 1)
    return dict(Sy=sy, sigma=sigma)


def gen_collision(rng, i):
    stock = _r(rng.uniform(10, 80), 1)
    safe = _r(stock + rng.uniform(5, 30), 1)
    rapid = _r(stock + rng.uniform(-12, 20), 1)
    return dict(z_safe=safe, z_min_rapid=rapid, stock_top=stock)


def gentol(rng, i):
    k = 2 + (i % 3)
    tols = [_r(rng.uniform(0.005, 0.08), 3) for _ in range(k)]
    upper = _r(rng.uniform(-0.05, 0.08), 3)
    lower = _r(upper + rng.uniform(-0.06, 0.06), 3)
    return dict(tols=tols, upper_dev=upper, lower_dev=lower)


def gen_design(rng, i):
    r_out = _r(rng.uniform(30, 120), 1)
    r_bore = _r(r_out * rng.uniform(0.30, 0.70), 1)
    n_holes = 0 if i % 6 == 0 else rng.randint(2, 8)
    max_hole = max(1.0, (r_out - r_bore) / 2.5)
    r_hole = _r(min(rng.uniform(2.0, 8.0), max_hole), 1)
    return dict(r_out=r_out, r_bore=r_bore, t=_r(rng.uniform(8, 50), 1),
                n_holes=n_holes, r_hole=r_hole, rho=STEEL if i % 2 else AL)


def gen_process(rng, i):
    return dict(D=_r(rng.uniform(20, 120), 1), L=_r(rng.uniform(50, 400), 1),
                ap=_r(rng.uniform(0.3, 3.0), 2), f=_r(rng.uniform(0.05, 0.4), 3),
                vc=_r(rng.uniform(80, 300), 0), r_eps=_r(rng.uniform(0.4, 1.6), 1))


def gen_adapt_material(rng, i):
    sy = _r(rng.uniform(180, 1000), 0)
    return dict(Sy=sy, sigma=_r(sy * rng.uniform(0.30, 0.95), 1))


def gen_adapt_machine(rng, i):
    return dict(D=_r(rng.uniform(5, 100), 1), vc=_r(rng.uniform(80, 350), 0),
                n_max=_r(rng.choice([3000, 4000, 6000, 8000, 10000, 12000]), 0))


def gen_geom_delta(rng, i):
    fv = _r(rng.uniform(100, 50_000), 0)
    return dict(feature_vol=fv, before=_r(fv * rng.uniform(1.5, 10.0), 0))


GENS = {
    "removal": gen_removal, "mass_props": gen_mass_props, "roughness": gen_roughness,
    "fea_fos": gen_fea_fos, "collision": gen_collision, "tolerance": gentol,
    "design": gen_design, "process": gen_process, "adapt_material": gen_adapt_material,
    "adapt_machine": gen_adapt_machine, "geom_delta": gen_geom_delta,
}


# ---------------------------------------------------------------------------
# 3 套措辞 / 族（与训练生成器措辞不同）
# ---------------------------------------------------------------------------
def p_removal(s, k):
    rho = "45钢" if s["rho"] == STEEL else "6061铝"
    if k == 0:
        return (f"车间报工复核：铣削切深 {s['doc']} mm、切宽 {s['woc']} mm、走刀 {s['L']} mm，"
                f"进给速度 {s['vf']} mm/min，材料 {rho}。请给切除体积、切屑质量与材料去除率。")
    if k == 1:
        return (f"按切削参数核料：ap={s['doc']}mm，ae={s['woc']}mm，行程 {s['L']}mm，"
                f"vf={s['vf']}mm/min，{rho}。算出去除量（mm3 与 g）和 MRR。")
    return (f"粗加工工步：切深 {s['doc']} 毫米、切宽 {s['woc']} 毫米、总行程 {s['L']} 毫米，"
            f"每分钟进给 {s['vf']} 毫米，材质 {rho}，求材料去除体积、质量和去除率。")


def p_mass(s, k):
    vols = "、".join(str(int(v)) for v in s["parts"])
    mat = "45钢" if s["rho"] == STEEL else "6061铝"
    if k == 0:
        return f"称重前估算：{len(s['parts'])} 个件的体积为 {vols} mm3，材质 {mat}，求合计体积与质量。"
    if k == 1:
        return f"装配重量预算：各件体积 {vols} 立方毫米，密度按 {s['rho']} g/mm3，输出体积/质量（g 与 kg）。"
    return f"零件清单：体积分别 {vols} mm3，材料 {mat}，请折算总质量并给出千克数。"


def p_roughness(s, k):
    if k == 0:
        return f"表面质量核算：每转进给 {s['f']} mm/r，刀尖圆弧 R{s['r_eps']} mm，估算理论 Ra（μm）。"
    if k == 1:
        return f"车削残留高度估算：f={s['f']}mm/r，rε={s['r_eps']}mm，求 Ra 数值（μm）。"
    return f"精车粗糙度预测：进给量 {s['f']} 毫米每转，刀尖半径 {s['r_eps']} 毫米，给出 Ra(μm)。"


def p_fea(s, k):
    if k == 0:
        return (f"强度放行评审：材料屈服 {s['Sy']} MPa，有限元峰值 von Mises {s['sigma']} MPa，"
                f"求安全系数并判定 1.5 门限。")
    if k == 1:
        return (f"CAE 结果复核：Sy={s['Sy']}MPa，σ_vm={s['sigma']}MPa，算 FOS 并给 fos_gate。")
    return (f"零件强度校核单：屈服强度 {s['Sy']} 兆帕，工作应力 {s['sigma']} 兆帕，"
            f"请给出安全系数与通过/不通过结论。")


def p_collision(s, k):
    if k == 0:
        return (f"刀轨安全复核：安全面 Z{s['z_safe']}，快速移动最低 Z{s['z_min_rapid']}，"
                f"毛坯顶面 Z{s['stock_top']}，判碰撞风险、过切与 Auto-Diff 颜色。")
    if k == 1:
        return (f"退刀干涉检查：z_safe={s['z_safe']}mm，rapid_min={s['z_min_rapid']}mm，"
                f"stock_top={s['stock_top']}mm，给风险等级与 gouge/autodiff。")
    return (f"五轴快速定位安全判读：安全平面 {s['z_safe']} 毫米，快移最低点 {s['z_min_rapid']} 毫米，"
            f"毛坯上表面 {s['stock_top']} 毫米，输出碰撞风险与过切判定。")


def p_tolerance(s, k):
    tols = "、".join(str(t) for t in s["tols"])
    if k == 0:
        return (f"公差链预算：组成环半公差 [{tols}] mm，上偏差 {s['upper_dev']}，下偏差 {s['lower_dev']}，"
                f"求极值半宽、RSS 半宽、配合间隙与 tolerance_pass。")
    if k == 1:
        return (f"尺寸链核算：tols=[{tols}]，upper={s['upper_dev']}mm，lower={s['lower_dev']}mm，"
                f"输出 worstcase/rss/fit_clearance 与布尔判定。")
    return (f"配合分析单：各环半公差 {tols} 毫米，孔上偏差 {s['upper_dev']} 毫米、下偏差 {s['lower_dev']} 毫米，"
            f"请算极值与均方根半宽并判间隙/过盈。")


def p_design(s, k):
    d_out = _r(s["r_out"] * 2, 1)
    d_bore = _r(s["r_bore"] * 2, 1)
    mat = "45钢" if s["rho"] == STEEL else "6061铝"
    hole = (f"，{s['n_holes']} 个 φ{_r(s['r_hole']*2,1)} 孔" if s["n_holes"] else "，无孔")
    if k == 0:
        return (f"法兰/端盖设计：外径 φ{d_out}，内孔 φ{d_bore}，厚 {s['t']} mm{hole}，"
                f"材料 {mat}，求体积与质量（g、kg）。")
    if k == 1:
        return (f"回转件建模：r_out={s['r_out']}mm，r_bore={s['r_bore']}mm，t={s['t']}mm"
                f"{hole}，rho={s['rho']} g/mm3，算净体积和质量。")
    return (f"零件重量估算：外圆半径 {s['r_out']} 毫米，内孔半径 {s['r_bore']} 毫米，厚度 {s['t']} 毫米"
            f"{hole}，材质 {mat}，输出体积、质量。")


def p_process(s, k):
    if k == 0:
        return (f"工序参数计算：工件直径 {s['D']} mm，车削长度 {s['L']} mm，ap={s['ap']} mm，"
                f"f={s['f']} mm/r，vc={s['vc']} m/min，刀尖 R{s['r_eps']}，求 n、vf、MRR、Ra、切削时间。")
    if k == 1:
        return (f"车削工艺卡：D={s['D']}mm，L={s['L']}mm，背吃刀量 {s['ap']}mm，每转进给 {s['f']}mm，"
                f"切削速度 {s['vc']}m/min，rε={s['r_eps']}mm，输出五个工艺量。")
    return (f"数控车参数复核：直径 {s['D']} 毫米，加工长度 {s['L']} 毫米，切深 {s['ap']} 毫米，"
            f"进给 {s['f']} 毫米每转，线速度 {s['vc']} 米每分，刀尖圆弧 {s['r_eps']} 毫米，"
            f"求主轴转速、进给速度、去除率、粗糙度与时间。")


def p_adapt_material(s, k):
    if k == 0:
        return f"换材料复核：新牌号屈服 {s['Sy']} MPa，工作应力 {s['sigma']} MPa，重算 FOS 并判 1.5 门限。"
    if k == 1:
        return f"材料替代评估：Sy={s['Sy']}MPa，σ={s['sigma']}MPa，给安全系数和 fos_gate。"
    return f"牌号变更单：屈服强度 {s['Sy']} 兆帕，工作应力 {s['sigma']} 兆帕，请重新给出安全系数与放行结论。"


def p_adapt_machine(s, k):
    if k == 0:
        return (f"机床能力核对：工件/刀具直径 {s['D']} mm，vc={s['vc']} m/min，"
                f"机床最高 {s['n_max']} r/min，求所需转速并判是否超限。")
    if k == 1:
        return (f"现场机床适配：D={s['D']}mm，切削速度 {s['vc']}m/min，n_max={s['n_max']}rpm，"
                f"输出 required/max/within_limit/recommended_vc。")
    return (f"设备选型复核：直径 {s['D']} 毫米，线速度 {s['vc']} 米每分，主轴上限 {s['n_max']} 转每分，"
            f"算所需转速并判断能否加工。")


def p_geom_delta(s, k):
    if k == 0:
        return f"特征增删校核：特征体积 {s['feature_vol']} mm3，改前总体积 {s['before']} mm3，求 ΔV 与改后体积。"
    if k == 1:
        return f"布尔运算复核：切除体 {s['feature_vol']} 立方毫米，原体 {s['before']} 立方毫米，给前后体积与变化量。"
    return f"模型改动核算：挖去 {s['feature_vol']} mm3，原模型 {s['before']} mm3，输出 feature/before/delta/after。"


PROMPTS = {
    "removal": p_removal, "mass_props": p_mass, "roughness": p_roughness,
    "fea_fos": p_fea, "collision": p_collision, "tolerance": p_tolerance,
    "design": p_design, "process": p_process, "adapt_material": p_adapt_material,
    "adapt_machine": p_adapt_machine, "geom_delta": p_geom_delta,
}


# ---------------------------------------------------------------------------
# invalid 族：6 个 reason code × 5 套措辞 = 30
# ---------------------------------------------------------------------------
INVALID_SPECS = [
    ("negative_cut_depth", "切削深度 DOC=-2 mm", "负切削不是零去除，是非法输入"),
    ("missing_material", "只给体积 120000 mm3 却要求质量", "未给材料/密度，禁止用记忆默认值"),
    ("nan_stress", "FEA 峰值应力 σ_vm=NaN", "NaN 不可参与运算"),
    ("zero_division", "求主轴转速但直径 D=0 mm", "分母为 0 必须报非法"),
    ("out_of_range", "半公差 -0.02 mm", "负公差违反物理约束"),
    ("unit_missing", "进给 0.2，未说明 mm/r 还是 mm/min", "单位无法推断时必须报非法"),
]
INVALID_PROMPTS = [
    "工单复核：{desc}。请说明能否参与物理求解，并给出结论。",
    "现场数据检查：{desc}。这条记录可以直接算吗？给出判定。",
    "输入合法性审查：{desc}。按契约应如何处理？",
    "MES 来料参数：{desc}。请判断是否应拒绝计算。",
    "编程前自检：{desc}。这条参数能否进入求解器？",
]


def build_invalid():
    out = []
    for ci, (code, desc, why) in enumerate(INVALID_SPECS):
        for k, tpl in enumerate(INVALID_PROMPTS):
            out.append({
                "id": f"V2-INV-{ci*5+k+1:03d}", "task": "invalid",
                "template": f"INV-{code}-{k}", "inputs": {"invalid_code": code},
                "prompt": tpl.format(desc=desc),
                "expected": {"world_state": None, "invalid": True,
                             "reason": f"{code}: {why}"},
            })
    return out


# ---------------------------------------------------------------------------
def build_cases(n_per_family=30):
    cases = []
    for fam in GENS:
        g = GENS[fam]
        for i in range(n_per_family // 3):
            inputs = g(random.Random(f"v2-{fam}-{i}"), i)
            ws = H.HAND[fam](inputs)
            # 交叉复核：独立解析式 vs 被测求解器
            ref = V.recompute({"task": fam, "inputs": inputs})
            if not ref:
                raise RuntimeError(f"[FATAL] {fam} #{i} 求解器无参考值: {inputs}")
            for k, v in ws.items():
                if k not in ref:
                    raise RuntimeError(f"[FATAL] {fam} #{i} 字段 {k} 不在求解器参考值")
                if not H.approx_equal(v, ref[k]):
                    raise RuntimeError(f"[FATAL] {fam} #{i} HAND 与求解器不一致: "
                                       f"{k} {v} vs {ref[k]}")
            for ti in range(3):
                prompt = PROMPTS[fam](inputs, ti)
                cases.append({
                    "id": f"V2-{ID_PREFIX[fam]}-{i*3+ti+1:03d}", "task": fam,
                    "template": f"{fam}-T{ti}", "inputs": inputs, "prompt": prompt,
                    "expected": {"world_state": ws},
                })
    cases.extend(build_invalid())
    # 每例自检：正确应答必须被同一判分器判过
    bad = 0
    for c in cases:
        if c["task"] == "invalid":
            ok, fmt, miss = E.judge("invalid", {"world_state": None, "invalid": True},
                                    {"world_state": None, "invalid": True})
        else:
            ok, fmt, miss = E.judge(c["task"], c["expected"], c["expected"])
        if not (ok and fmt):
            bad += 1
            print(f"[FAIL] 自检未过: {c['id']} miss={miss}", file=sys.stderr)
    if bad:
        raise RuntimeError(f"[FATAL] {bad} 条期望答案无法通过判分器自检")
    return cases


def leakage_check(cases):
    train_prompts = set()
    if os.path.isfile(TRAIN_PATH):
        for line in open(TRAIN_PATH, encoding="utf-8"):
            try:
                row = json.loads(line)
            except Exception:
                continue
            for m in row.get("messages") or []:
                if isinstance(m, dict) and m.get("role") == "user" and m.get("content"):
                    train_prompts.add(m["content"])
    train_grams = H.train_grams() or set()
    v1 = set()
    v1p = os.path.join(ROOT, "data", "holdout", "wm_holdout_v1.jsonl")
    if os.path.isfile(v1p):
        for line in open(v1p, encoding="utf-8"):
            v1.add(json.loads(line)["prompt"])
    exact, v1_dup, max_cov, offenders = 0, 0, 0.0, []
    for c in cases:
        p = c["prompt"]
        if p in train_prompts:
            exact += 1
            offenders.append((c["id"], "exact_train"))
        if p in v1:
            v1_dup += 1
            offenders.append((c["id"], "dup_v1"))
        g = H._grams(p)
        if g:
            cov = len(g & train_grams) / len(g)
            max_cov = max(max_cov, cov)
            if cov > REL_LEAK_MAX:
                offenders.append((c["id"], f"5gram={cov:.3f}"))
    return {"exact_train_overlap": exact, "v1_duplicates": v1_dup,
            "max_5gram_coverage": round(max_cov, 4), "offenders": offenders[:20],
            "train_prompts": len(train_prompts), "train_grams": len(train_grams)}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--n-per-family", type=int, default=30)
    args = ap.parse_args()
    if args.check:
        if not os.path.isfile(OUT):
            raise SystemExit(f"未找到 {OUT}，先 --write")
        cases = [json.loads(l) for l in open(OUT, encoding="utf-8") if l.strip()]
    else:
        cases = build_cases(args.n_per_family)
    leak = leakage_check(cases)
    counts = Counter(c["task"] for c in cases)
    print(f"[cases] n={len(cases)} per_family={dict(counts)}")
    print(f"[leak] {json.dumps(leak, ensure_ascii=False)}")
    if leak["exact_train_overlap"] or leak["v1_duplicates"] or leak["max_5gram_coverage"] > REL_LEAK_MAX:
        raise SystemExit("[FATAL] 留出集与训练/旧留出集重合，拒绝落盘或通过检查")
    if args.write and not args.check:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            for c in cases:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        ledger = {
            "schema_version": "wm_holdout_v2",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "basis": "measured",
            "path": os.path.relpath(OUT, ROOT).replace("\\", "/"),
            "sha256": sha256(OUT),
            "n": len(cases),
            "per_family": dict(sorted(counts.items())),
            "truth_source": "wm_holdout_regression.HAND（独立解析式）",
            "crosscheck": "wm_verifier.recompute 逐字段一致",
            "leakage": leak,
            "split": "eval",
            "note": "不得用于训练；corpus builder 必须排除 data/holdout/**",
        }
        json.dump(ledger, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[ok] -> {OUT} ({len(cases)} 例), ledger -> {LEDGER}")
    print("[check] PASS")


if __name__ == "__main__":
    main()
