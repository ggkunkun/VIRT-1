#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立回归集（非自证检查项）。

为什么要这个文件
----------------
`wm_vuln_regression.py` 已经覆盖了 17 条历史漏洞，但它的场景与断言都由仓库
自己编写，并且真值直接取自被测实现 `wm_verifier.recompute()` —— 求解器算错，
回归照样全绿。这是同源自证的典型形态（与 `wm_eval_purity` 修掉的「模板去污后
干净用例为 0」同源）。

本文件的独立性体现在三处：
  1. 真值来自**本文件内置的解析式**（hand_* 函数），不 import `wm_verifier`
     的任何数值实现；被测求解器给出什么，都在这里被第三方公式复核一遍。
  2. 假绿探针：把本题真值同倍放大/缩小 30%（远超 REL_TOL=8%），再喂给被测
     的 `verify()`。口径若不真，错误答案照样 accept —— 这条断言直接判红。
  3. 去污：题面与训练集 user prompt 的 5-gram 覆盖率超过阈值即视为泄漏，
     防止"回归集其实是训练集的一页"。

样本是人工撰写并落盘到 `data/holdout/wm_holdout_v1.jsonl` 后冻结的：脚本运行
时不重新生成，只在文件缺失时由内置 CASES 写出。要加样本就手工改文件，这样
回归集不会跟着被测实现的生成器一起漂移。

用法：
  .venv/Scripts/python.exe scripts/wm_holdout_regression.py
  .venv/Scripts/python.exe scripts/wm_holdout_regression.py --write   # 重建冻结样本
  .venv/Scripts/python.exe scripts/wm_holdout_regression.py --only removal,design
退出码：0 全通过；1 存在失败项。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
os.chdir(ROOT)

HOLDOUT_PATH = os.path.join(ROOT, "data", "holdout", "wm_holdout_v1.jsonl")
TRAIN_PATH = os.path.join(ROOT, "data", "sft_rebalanced", "wm_train_cap12_v2.unitfix.jsonl")
REL_LEAK_MAX = 0.60          # 5-gram 覆盖率容忍上限
REL_HAND_TOL = 1e-6          # 独立解析式 vs 被测求解器
WRONG_SCALE = 1.30           # 假绿探针的偏移倍数（>8% 容差）

PASS, FAIL = [], []


def chk(tag: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(tag)
    print(f"[{'PASS' if cond else 'FAIL'}] {tag}" + (f"  {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 独立解析式（真值来源）——刻意与 wm_verifier 的实现分开写，便于互相审计
# ---------------------------------------------------------------------------
def hand_removal(s):
    removed = s["doc"] * s["woc"] * s["L"]
    out = {"material_removed_mm3": removed,
           "removed_mass_g": removed * s["rho"],
           "delta_volume_mm3": -removed}
    if "vf" in s:
        out["mrr_mm3_per_min"] = s["doc"] * s["woc"] * s["vf"]
    return out


def hand_mass_props(s):
    V = float(sum(s["parts"]))
    return {"volume_mm3": V, "mass_g": V * s["rho"], "mass_kg": V * s["rho"] / 1000.0}


def hand_roughness(s):
    return {"surface_roughness_ra_um": 1000.0 * s["f"] ** 2 / (8.0 * s["r_eps"])}


def hand_fea_fos(s):
    fos = s["Sy"] / s["sigma"]
    return {"yield_strength_mpa": s["Sy"], "peak_von_mises_mpa": s["sigma"],
            "safety_factor": fos, "fos_gate": "pass" if fos >= 1.5 else "fail"}


def hand_collision(s):
    gouge = s["z_min_rapid"] < s["stock_top"]
    risk = ((s["z_min_rapid"] < s["z_safe"]) and (s["z_min_rapid"] < s["stock_top"] + 1.0)) or gouge
    return {"safe_plane_z_mm": s["z_safe"], "rapid_min_z_mm": s["z_min_rapid"],
            "stock_top_z_mm": s["stock_top"],
            "collision_risk": "high" if risk else "none",
            "gouge": bool(gouge),
            "autodiff": "red" if gouge else ("yellow" if risk else "green")}


def hand_tolerance(s):
    tols = s["tols"]
    clearance = s["upper_dev"] - s["lower_dev"]
    return {"closed_loop_worstcase_halfwidth_mm": sum(tols),
            "closed_loop_rss_halfwidth_mm": math.sqrt(sum(t * t for t in tols)),
            "fit_clearance_mm": clearance,
            "tolerance_pass": bool(clearance >= 0.0)}


def hand_geom_delta(s):
    return {"feature_volume_mm3": s["feature_vol"], "delta_volume_mm3": -s["feature_vol"],
            "before_volume_mm3": s["before"], "after_volume_mm3": s["before"] - s["feature_vol"]}


def hand_design(s):
    V = (math.pi * (s["r_out"] ** 2 - s["r_bore"] ** 2) * s["t"]
         - s["n_holes"] * math.pi * s["r_hole"] ** 2 * s["t"])
    return {"volume_mm3": V, "mass_g": V * s["rho"], "mass_kg": V * s["rho"] / 1000.0}


def hand_process(s):
    n = 1000.0 * s["vc"] / (math.pi * s["D"])
    feed = s["f"] * n
    return {"spindle_rpm": n, "feed_rate_mm_per_min": feed,
            "mrr_mm3_per_min": s["ap"] * s["f"] * s["vc"] * 1000.0,
            "surface_roughness_ra_um": 1000.0 * s["f"] ** 2 / (8.0 * s["r_eps"]),
            "cut_time_min": (s["L"] / feed) if feed > 0 else 0.0}


def hand_adapt_machine(s):
    n = 1000.0 * s["vc"] / (math.pi * s["D"])
    return {"required_spindle_rpm": n, "machine_max_rpm": s["n_max"],
            "within_limit": bool(n <= s["n_max"]), "recommended_vc_m_per_min": s["vc"]}


HAND = {
    "removal": hand_removal,
    "mass_props": hand_mass_props,
    "roughness": hand_roughness,
    "fea_fos": hand_fea_fos,
    "adapt_material": hand_fea_fos,
    "collision": hand_collision,
    "tolerance": hand_tolerance,
    "geom_delta": hand_geom_delta,
    "design": hand_design,
    "process": hand_process,
    "adapt_machine": hand_adapt_machine,
}

STEEL = 7.85e-3
AL = 2.70e-3

# 人工样本：题面为生产/现场口吻，inputs 显式给齐，真值由上面 HAND 独立算出
CASES = [
    dict(id="HO-REM-01", task="removal",
         prompt="现场核算去除量：切深 2mm，切宽 5mm，行程 100mm，进给速度 400mm/min，45钢，求去除体积、质量与材料去除率。",
         inputs=dict(doc=2.0, woc=5.0, L=100.0, vf=400.0, rho=STEEL)),
    dict(id="HO-REM-02", task="removal",
         prompt="铝合金件粗铣，切深 1.5mm，切宽 3mm，刀具行程 250mm，进给 250mm/min，按 6061 密度算切屑质量。",
         inputs=dict(doc=1.5, woc=3.0, L=250.0, vf=250.0, rho=AL)),
    dict(id="HO-MAS-01", task="mass_props",
         prompt="装配体三个零件的体积分别是 120000、80000、45000 立方毫米，材料 45 钢，折算总质量。",
         inputs=dict(parts=[120000.0, 80000.0, 45000.0], rho=STEEL)),
    dict(id="HO-MAS-02", task="mass_props",
         prompt="两个铝件体积 30000 与 15000 mm3，密度 2.70e-3 g/mm3，求体积合计与质量。",
         inputs=dict(parts=[30000.0, 15000.0], rho=AL)),
    dict(id="HO-ROU-01", task="roughness",
         prompt="精车表面粗糙度预估：进给 0.2 mm/r，刀尖圆弧半径 0.8 mm，45钢。",
         inputs=dict(f=0.2, r_eps=0.8)),
    dict(id="HO-ROU-02", task="roughness",
         prompt="精加工 Ra 预估，每转进给 0.1mm，刀尖 R0.4mm，材料 6061。",
         inputs=dict(f=0.1, r_eps=0.4)),
    dict(id="HO-FOS-01", task="fea_fos",
         prompt="支架强度校核：屈服强度 355 MPa，峰值应力 200 MPa，给安全系数并判断能否放行。",
         inputs=dict(Sy=355.0, sigma=200.0)),
    dict(id="HO-FOS-02", task="fea_fos",
         prompt="Q235 件屈服 235 MPa，计算峰值应力 200 MPa，安全系数够不够？",
         inputs=dict(Sy=235.0, sigma=200.0)),
    dict(id="HO-COL-01", task="collision",
         prompt="五轴退刀校核：安全面 Z50，快速定位最低 Z45，毛坯顶面 Z40，判碰撞风险。",
         inputs=dict(z_safe=50.0, z_min_rapid=45.0, stock_top=40.0)),
    dict(id="HO-COL-02", task="collision",
         prompt="刀柄干涉检查：安全面 Z30，快速下刀到 Z25，毛坯顶面 Z35，出风险等级与过切判断。",
         inputs=dict(z_safe=30.0, z_min_rapid=25.0, stock_top=35.0)),
    dict(id="HO-TOL-01", task="tolerance",
         prompt="孔轴配合计算：公差链 [0.02, 0.015]，上偏差 0.05，下偏差 0.02，给最坏情况半宽、RSS 半宽与配合间隙。",
         inputs=dict(tols=[0.02, 0.015], upper_dev=0.05, lower_dev=0.02)),
    dict(id="HO-TOL-02", task="tolerance",
         prompt="配合公差分析，公差链 [0.03, 0.02, 0.01]，上偏差 0.01，下偏差 0.04，判过盈还是间隙。",
         inputs=dict(tols=[0.03, 0.02, 0.01], upper_dev=0.01, lower_dev=0.04)),
    dict(id="HO-DES-01", task="design",
         prompt="法兰设计：外径 197.6 mm，内孔 80 mm，厚 25 mm，6 个 φ8.6 螺栓孔，45钢，出体积与质量。",
         inputs=dict(r_out=98.8, r_bore=40.0, t=25.0, n_holes=6, r_hole=4.3, rho=STEEL)),
    dict(id="HO-DES-02", task="design",
         prompt="端盖建模需求：外径 120 mm，中心孔 50 mm，厚度 18 mm，4 个 φ6.6 孔，6061 铝，求体积和质量。",
         inputs=dict(r_out=60.0, r_bore=25.0, t=18.0, n_holes=4, r_hole=3.3, rho=AL)),
    dict(id="HO-PRO-01", task="process",
         prompt="工序卡参数：直径 50 mm，车削长度 120 mm，背吃刀量 1.5 mm，进给 0.2 mm/r，切削速度 180 m/min，刀尖 R0.8。",
         inputs=dict(D=50.0, L=120.0, ap=1.5, f=0.2, vc=180.0, r_eps=0.8)),
    dict(id="HO-PRO-02", task="process",
         prompt="车削工艺核算，工件直径 80 mm，加工长度 200 mm，ap 2.5 mm，f 0.15 mm/r，vc 150 m/min，刀尖圆弧 1.2 mm。",
         inputs=dict(D=80.0, L=200.0, ap=2.5, f=0.15, vc=150.0, r_eps=1.2)),
    dict(id="HO-ADM-01", task="adapt_material",
         prompt="原来 45 钢的件换 6061 铝，屈服 235 MPa，工作应力 150 MPa，重新评估安全系数。",
         inputs=dict(Sy=235.0, sigma=150.0)),
    dict(id="HO-ADM-02", task="adapt_material",
         prompt="材料换牌号后复核强度：屈服 205 MPa，峰值应力 180 MPa，能不能放行。",
         inputs=dict(Sy=205.0, sigma=180.0)),
    dict(id="HO-MAC-01", task="adapt_machine",
         prompt="机床能力校验：刀具直径 40 mm，切削速度 200 m/min，机床最高 8000 r/min，看转速是否超限。",
         inputs=dict(D=40.0, vc=200.0, n_max=8000.0)),
    dict(id="HO-MAC-02", task="adapt_machine",
         prompt="小孔钻削，直径 10 mm，切削速度 300 m/min，主轴上限 8000 r/min，判能不能干。",
         inputs=dict(D=10.0, vc=300.0, n_max=8000.0)),
    dict(id="HO-GEO-01", task="geom_delta",
         prompt="特征体积 15000 mm3，改前总体积 200000 mm3，算改动后体积变化。",
         inputs=dict(feature_vol=15000.0, before=200000.0)),
    dict(id="HO-GEO-02", task="geom_delta",
         prompt="挖掉一个体积 800 立方毫米的特征，原模型 50000 立方毫米，出前后体积与增删量。",
         inputs=dict(feature_vol=800.0, before=50000.0)),
]


# ---------------------------------------------------------------------------
def load_cases(write: bool):
    if write or not os.path.isfile(HOLDOUT_PATH):
        os.makedirs(os.path.dirname(HOLDOUT_PATH), exist_ok=True)
        with open(HOLDOUT_PATH, "w", encoding="utf-8") as f:
            for c in CASES:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"[holdout] 已写出冻结样本 {len(CASES)} 条 -> {os.path.relpath(HOLDOUT_PATH, ROOT)}")
    out = []
    with open(HOLDOUT_PATH, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _grams(s: str, n: int = 5):
    t = _norm(s)
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def train_grams():
    """训练集 user prompt 的 5-gram 全集（用于泄漏检查）。"""
    pool = set()
    if not os.path.isfile(TRAIN_PATH):
        return None
    with open(TRAIN_PATH, encoding="utf-8") as f:
        for ln in f:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            texts = []
            if isinstance(row.get("messages"), list):
                texts = [m.get("content", "") for m in row["messages"] if isinstance(m, dict)]
            elif isinstance(row.get("prompt"), str):
                texts = [row["prompt"]]
            elif isinstance(row.get("input"), str):
                texts = [row["input"]]
            for t in texts:
                if t:
                    pool |= _grams(t)
    return pool


def approx_equal(a, b, tol=REL_HAND_TOL) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(abs(a), abs(b), 1e-9)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(approx_equal(x, y, tol) for x, y in zip(a, b))
    return str(a).strip().lower() == str(b).strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="用内置 CASES 重建冻结样本")
    ap.add_argument("--only", default="", help="只跑指定族，逗号分隔")
    args = ap.parse_args()

    import anti_hallucination_guard as A     # 被测：题面归族
    import wm_verifier as V                  # 被测：复算 + 裁决

    cases = load_cases(args.write)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    if only:
        cases = [c for c in cases if c["task"] in only]

    print("=" * 78)
    print(f"独立回归集 holdout v1  样本 {len(cases)} 条  真值来源=本文件解析式")
    print("=" * 78)

    # ---- 1) 独立真值 vs 被测求解器 -------------------------------------
    solver_bad, hand_bad = [], []
    for c in cases:
        task, inputs = c["task"], c["inputs"]
        hand = HAND[task](inputs)
        scen = {"task": task, "inputs": inputs}
        ref = V.recompute(scen)
        if not ref:
            solver_bad.append(f"{c['id']}:空参考值")
            continue
        for k, hv in hand.items():
            if k not in ref:
                solver_bad.append(f"{c['id']}:缺键{k}")
            elif not approx_equal(hv, ref[k]):
                solver_bad.append(f"{c['id']}:{k} 手算={hv} 求解器={ref[k]}")
    chk("A 被测求解器与独立解析式一致（求解器算错即判红，不再同源自证）",
        not solver_bad, "; ".join(solver_bad[:4]))

    # ---- 2) 假绿探针：正确值必须 accept，偏移 30% 必须 reject ----------
    for c in cases:
        task, inputs = c["task"], c["inputs"]
        scen = {"task": task, "inputs": inputs}
        ref = V.recompute(scen)
        if not ref:
            hand_bad.append(f"{c['id']}:无参考值，无法做假绿探针")
            continue
        ok_verdict = V.verify({"world_state": dict(ref)}, scen)
        if not ok_verdict.get("ok"):
            hand_bad.append(f"{c['id']}:正确值被误杀({ok_verdict.get('action')})")
        wrong = {}
        for k, v in ref.items():
            wrong[k] = v * WRONG_SCALE if isinstance(v, (int, float)) and not isinstance(v, bool) else v
        bad_verdict = V.verify({"world_state": wrong}, scen)
        if bad_verdict.get("ok"):
            hand_bad.append(f"{c['id']}:偏移30%仍被 accept（口径失真）")
    chk(f"B 假绿探针：正确值 accept、偏移 {int((WRONG_SCALE-1)*100)}% 必 reject",
        not hand_bad, "; ".join(hand_bad[:4]))

    # ---- 3) 题面归族：生产口吻必须归到标注族 ---------------------------
    mis = []
    for c in cases:
        inf = A.infer_scenario_from_prompt(c["prompt"])
        got = (inf or {}).get("task")
        if got != c["task"]:
            mis.append(f"{c['id']}: 标{c['task']} -> 得{got}")
    chk("C 题面归族：独立样本的现场口吻必须落到标注族", not mis, "; ".join(mis[:6]))

    # ---- 4) 去污：holdout 不得是训练集的一页 ---------------------------
    pool = train_grams()
    if pool is None:
        chk("D 训练集去污（训练集缺失，无法证伪）", False, f"找不到 {TRAIN_PATH}")
    else:
        leaks = []
        for c in cases:
            g = _grams(c["prompt"])
            if not g:
                continue
            cover = len(g & pool) / len(g)
            if cover > REL_LEAK_MAX:
                leaks.append(f"{c['id']}:{cover:.0%}")
        chk(f"D 去污：题面 5-gram 训练集覆盖率 ≤ {REL_LEAK_MAX:.0%}",
            not leaks, "; ".join(leaks[:5]))

    print("-" * 78)
    print(f"PASS {len(PASS)} / {len(PASS)+len(FAIL)}" + (f"   FAIL {len(FAIL)}" if FAIL else ""))
    if FAIL:
        print("[holdout] 存在失败项，口径不可信", file=sys.stderr)
        return 1
    print("[holdout] 独立回归集全通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
