#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the physics-acceptance case set (dimension ``physics``).

Why this exists: every other dimension states its gold as text the author typed. Here the gold
IS the solver's output -- ``wm_verifier.recompute(scenario)`` -- so a case cannot ship a number
nobody computed, and ``validate_cases.py`` rejects any edit that makes the gold disagree with
the physics. Each prompt enumerates the exact keys that will be graded, because the grader
demands every comparable derived field (silence is not agreement).

Templates are chosen to span the decision boundaries the domain cares about (autodiff
red/yellow/green, FOS above and below the 1.5 gate, spindle demand above and below the machine
limit), not three near-identical instances of one arithmetic problem.

Usage:
    python scripts/build_physics_acceptance_cases.py
    python scripts/build_physics_acceptance_cases.py --print-supported
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import wm_verifier as wm  # noqa: E402
from wm_contract import SYSTEM, SYSTEM_PLAIN  # noqa: E402
from virtu_eval.derivation import resolve  # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "benchmark", "virtu_eval_phys_v1")
MAX_TOKENS = {"easy": 256, "medium": 448, "hard": 704}
TOL_BY_TIER = {"easy": 0.08, "medium": 0.03, "hard": 0.01}
TARGET_MIX = {"easy": 9, "medium": 15, "hard": 6}

UNITS = {
    "doc": "mm", "woc": "mm", "L": "mm", "vf": "mm/min", "rho": "g/mm3",
    "stock_vol": "mm3", "f": "mm/rev", "r_eps": "mm", "Sy": "MPa", "sigma": "MPa",
    "tols": "mm", "upper_dev": "mm", "lower_dev": "mm", "r_out": "mm", "r_bore": "mm",
    "t": "mm", "n_holes": "个", "r_hole": "mm", "D": "mm", "n_max": "r/min",
    "z_safe": "mm", "z_min_rapid": "mm", "stock_top": "mm", "feature_vol": "mm3",
    "before": "mm3", "ap": "mm", "vc": "m/min", "l": "mm", "w": "mm", "h": "mm", "r": "mm",
}

FAMILIES = {
    "roughness": {
        "zh": "车削后表面粗糙度估算，公式 Ra=1000*f^2/(8*r_eps)",
        "inputs": [{"f": 0.12, "r_eps": 0.8}, {"f": 0.25, "r_eps": 1.2},
                   {"f": 0.08, "r_eps": 0.4}],
    },
    "fea_fos": {
        "zh": "静强度校核，公式 FOS=Sy/sigma（Sy 为屈服强度，sigma 为峰值 von Mises 应力）",
        # spans the 1.5 gate: pass, boundary, fail
        "inputs": [{"Sy": 355.0, "sigma": 101.4}, {"Sy": 235.0, "sigma": 156.7},
                   {"Sy": 235.0, "sigma": 198.0}],
    },
    "adapt_material": {
        "zh": "材料替换后的安全系数复核，公式 FOS=Sy/sigma",
        "inputs": [{"Sy": 245.0, "sigma": 163.0}, {"Sy": 355.0, "sigma": 240.0},
                   {"Sy": 545.0, "sigma": 218.0}],
    },
    "removal": {
        "zh": "铣削去除材料，去除体积=doc*woc*L，材料去除率 MRR=doc*woc*vf，"
             "去除质量=去除体积*rho，剩余质量=stock_vol*rho-去除质量，ΔV 记为负值",
        "inputs": [{"doc": 2.0, "woc": 5.0, "vf": 400.0, "L": 100.0,
                    "rho": 7.85e-3, "stock_vol": 200000.0},
                   {"doc": 3.5, "woc": 8.0, "vf": 640.0, "L": 250.0,
                    "rho": 2.7e-3, "stock_vol": 450000.0},
                   {"doc": 1.2, "woc": 10.0, "vf": 900.0, "L": 60.0,
                    "rho": 4.5e-3, "stock_vol": 120000.0},
                   {"doc": 0.8, "woc": 12.0, "vf": 1200.0, "L": 45.0,
                    "rho": 8.9e-3, "stock_vol": 90000.0}],
    },
    "tolerance": {
        "zh": "尺寸链闭环，最坏情况半宽=各环公差半宽之和，RSS 半宽=各环公差半宽平方和开根号",
        "inputs": [{"tols": [0.05, 0.03, 0.08, 0.02], "upper_dev": 0.04, "lower_dev": -0.12},
                   {"tols": [0.1, 0.05, 0.05], "upper_dev": 0.2, "lower_dev": 0.05},
                   {"tols": [0.02, 0.02, 0.04, 0.01, 0.03], "upper_dev": 0.01,
                    "lower_dev": -0.05},
                   {"tols": [0.07, 0.07, 0.035, 0.035, 0.02], "upper_dev": 0.25,
                    "lower_dev": 0.0}],
    },
    "design": {
        "zh": "法兰盘质量，体积=pi*(r_out^2-r_bore^2)*t - n_holes*pi*r_hole^2*t",
        "inputs": [{"r_out": 50.0, "r_bore": 20.0, "t": 10.0, "n_holes": 6, "r_hole": 5.0,
                    "rho": 7.85e-3},
                   {"r_out": 80.0, "r_bore": 32.0, "t": 14.0, "n_holes": 8, "r_hole": 6.5,
                    "rho": 2.7e-3},
                   {"r_out": 120.0, "r_bore": 45.0, "t": 20.0, "n_holes": 12, "r_hole": 9.0,
                    "rho": 4.5e-3},
                   {"r_out": 65.0, "r_bore": 25.0, "t": 12.0, "n_holes": 4, "r_hole": 7.0,
                    "rho": 4.43e-3}],
    },
    "adapt_machine": {
        "zh": "机床能力适配，需求转速 n=1000*vc/(pi*D)，并判断是否不超过主轴上限 n_max",
        "inputs": [{"D": 16.0, "vc": 120.0, "n_max": 3000.0},
                   {"D": 12.0, "vc": 250.0, "n_max": 3000.0},
                   {"D": 10.0, "vc": 200.0, "n_max": 8000.0}],
    },
    "mass_props": {
        "zh": "毛坯质量属性（长方体 l/w/h 或圆柱 r/h，密度按题面）",
        "inputs": [{"shape": "box", "params": {"l": 120.0, "w": 60.0, "h": 20.0},
                    "rho": 7.85e-3},
                   {"shape": "box", "params": {"l": 200.0, "w": 40.0, "h": 40.0},
                    "rho": 2.7e-3},
                   {"shape": "cylinder", "params": {"r": 45.0, "h": 90.0}, "rho": 4.5e-3}],
    },
    "collision": {
        "zh": "G00 快速移动碰撞判定：最低点 Z 低于安全平面且低于毛坯顶面+1mm 记高风险，"
             "最低点 Z 低于毛坯顶面即过切；autodiff 取 red（过切）/yellow（风险无过切）/green（安全）",
        # deliberately one of each verdict
        "inputs": [{"z_safe": 50.0, "z_min_rapid": 38.0, "stock_top": 40.0},
                   {"z_safe": 50.0, "z_min_rapid": 40.5, "stock_top": 40.0},
                   {"z_safe": 50.0, "z_min_rapid": 55.0, "stock_top": 40.0}],
    },
    "geom_delta": {
        "zh": "切除特征后的体积变化，delta_volume_mm3 为负值且 after=before+delta",
        "inputs": [{"feature_vol": 1570.8, "before": 25000.0},
                   {"feature_vol": 490.9, "before": 8000.0},
                   {"feature_vol": 12566.4, "before": 60000.0}],
    },
    "process": {
        "zh": "车削工艺换算：n=1000*vc/(pi*D)，进给速度=f*n，MRR=ap*f*vc*1000，"
             "Ra=1000*f^2/(8*r_eps)，切削时间=加工长度/进给速度",
        "inputs": [{"D": 40.0, "L": 120.0, "ap": 2.0, "f": 0.25, "vc": 180.0, "r_eps": 0.8},
                   {"D": 65.0, "L": 300.0, "ap": 3.0, "f": 0.18, "vc": 220.0, "r_eps": 1.2},
                   {"D": 25.0, "L": 80.0, "ap": 1.0, "f": 0.1, "vc": 150.0, "r_eps": 0.4}],
    },
}

# Per-tier quota, 9/15/6 as the schema demands. collision gets all three variants because its
# verdict fields (autodiff red/yellow/green, gouge) must each appear, or the set would only
# ever exercise two of the three states.
# mass_props is EXCLUDED (measured 2026-11-04): mass_props_csg returns V*(h^2+w^2)/12, whose
# unit is mm^5, under the field name inertia_ixx_mm4. The true area moment of the 120x60x20 box
# is w*h^3/12 = 4.0e4 mm^4 while the solver says 4.8e7, a 1200x disagreement. A field whose
# reference is dimensionally wrong cannot grade anything; same expression at
# scripts/distill_local_solver.py:180 and scripts/build_worldmodel_sft.py:267.
BUCKETS = {
    "easy": ["roughness", "fea_fos", "adapt_material"],
    "medium": ["removal", "tolerance", "design", "adapt_machine"],
    "hard": ["collision", "geom_delta", "process"],
}
QUOTA = {
    "easy": {"roughness": 3, "fea_fos": 3, "adapt_material": 3},
    "medium": {"removal": 4, "tolerance": 4, "design": 4, "adapt_machine": 3},
    "hard": {"collision": 3, "geom_delta": 2, "process": 1},
}


def _supported(family):
    """A family is usable only if the solver returns a reference for it on this box."""
    for inputs in FAMILIES[family]["inputs"]:
        try:
            if wm.recompute({"task": family, "inputs": inputs}):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _given(inputs):
    parts = []
    for key, value in inputs.items():
        if isinstance(value, dict):
            inner = "，".join(f"{k}={_num(v)} {UNITS.get(k, '')}".strip()
                             for k, v in value.items())
            parts.append(f"几何尺寸：{inner}")
        elif key == "shape":
            parts.append("几何形状 shape=「" + str(value) + "」")
        else:
            parts.append(f"{key}={_num(value)} {UNITS.get(key, '')}".strip())
    return "，".join(parts)


def _num(v):
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(str(x) for x in v) + "]"
    return str(v)


def _prompt(zh, inputs, keys, ask_derivation=False):
    head = (f"【场景】{_given(inputs)}。\n计算目标：{zh}。\n"
            f"只输出一个 JSON，顶层键为 world_state，其中必须逐项给出这些字段："
            f"{', '.join(keys)}。")
    if ask_derivation:
        return (head + "\n再在顶层给出 derivation：对上述每个数值字段，用字符串写出**代入算式**，"
                        "算式里只能出现上面给出的数值、该定律自身的常数（8、1000、12、π）与本题已算出的中间量；"
                        "乘积由校验器现算，符号名与数值必须取自上面的题面，禁止代入题面没有的数或记忆中的默认参数；"
                        "只写符号式不代数值不算完成。每个数值仍请同时填入 world_state 对应字段，保留 4 位有效数字。")
    return (head + "每个数值都要由上面给出的参数直接算出，保留 4 位有效数字；"
                   "禁止照抄示例数值，禁止使用记忆中的默认材料参数。")


def _round_sig(obj, sig=4):
    """Round to significant digits the way the contract asks, so the gold is a legal answer."""
    if isinstance(obj, dict):
        return {k: _round_sig(v, sig) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_sig(v, sig) for v in obj]
    if isinstance(obj, bool) or not isinstance(obj, (int, float)):
        return obj
    if obj == 0 or not math.isfinite(float(obj)):
        return obj
    return float(f"{float(obj):.{sig}g}")


def build_cases(supported, ask="numbers"):
    for tier, quota in QUOTA.items():
        missing = [f for f in quota if f not in supported]
        if missing:
            raise SystemExit(f"tier {tier} quota needs unsupported families {missing}")
        if sum(quota.values()) != TARGET_MIX[tier]:
            raise SystemExit(f"tier {tier} quota {sum(quota.values())} != {TARGET_MIX[tier]}")

    derivation = ask == "derivation"
    dimension = "derivation" if derivation else "physics"
    cases, seq = [], {t: 0 for t in TARGET_MIX}
    for tier in ("easy", "medium", "hard"):
        for family in BUCKETS[tier]:
            templates = FAMILIES[family]["inputs"]
            for variant in range(QUOTA[tier][family]):
                inputs = templates[variant % len(templates)]
                scenario = {"task": family, "inputs": inputs}
                ref = wm.recompute(scenario)
                if not ref:
                    raise SystemExit(f"solver lost family {family} mid-build: {scenario}")
                keys = sorted(ref)
                # The prompt asks for everything, but must_compare lists only what the ladder can
                # actually compare: _cmp_numeric skips list-valued fields (centroid_mm), and naming
                # a non-comparable field here would make the gold unsatisfiable.
                graded = [k for k, v in ref.items()
                          if v is None or isinstance(v, (int, float, str))]
                gold_state = _round_sig(ref)
                gold_obj = ({"world_state": gold_state, "derivation": _gold_derivation(family, inputs)}
                            if derivation else {"world_state": gold_state})
                criteria = [
                    {"type": "json_object", "key": "json_shape", "weight": 1,
                     "required_keys": (["world_state", "derivation"] if derivation else ["world_state"])},
                    {"type": "physics_invariant", "key": "invariants", "weight": 1,
                     "scenario": scenario},
                    {"type": "world_state_verified", "key": "reproduced_by_solver",
                     "weight": 3, "scenario": scenario, "tol_rel": TOL_BY_TIER[tier],
                     "must_compare": graded},
                ]
                if derivation:
                    criteria.insert(1, {"type": "derivation_verified", "key": "law_and_binding",
                                        "weight": 3, "scenario": scenario,
                                        "tol_rel": 0.01})
                seq[tier] += 1
                letter = {"easy": "e", "medium": "m", "hard": "h"}[tier]
                cases.append({
                    "id": f"{dimension}-{letter}{seq[tier]:02d}",
                    "dimension": dimension,
                    "tier": tier,
                    "language": "zh",
                    "system": (SYSTEM if derivation else SYSTEM_PLAIN),
                    "context": [],
                    "prompt": _prompt(FAMILIES[family]["zh"], inputs, keys, derivation),
                    "images": [],
                    "max_tokens": MAX_TOKENS[tier],
                    "tags": [dimension, family, "solver-gold"],
                    "gold": {
                        "answer": json.dumps(gold_obj, ensure_ascii=False),
                        "derivation": (f"gold=wm_verifier.recompute(task={family}) 原样派生，无人工填写；"
                                       f"tol_rel={TOL_BY_TIER[tier]}（{tier}），求解器默认 {wm.REL_TOL}"),
                    },
                    "criteria": criteria,
                })
    return cases


def _gold_derivation(task, inputs):
    """The substituted expression per field, generated by the registry -- never typed by hand."""
    return resolve(task, inputs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--ask", choices=["numbers", "derivation"], default="numbers",
                    help="numbers = physics dimension (fill in the values); "
                         "derivation = derivation dimension (write the substituted law, "
                         "the verifier does the arithmetic)")
    ap.add_argument("--print-supported", action="store_true")
    args = ap.parse_args()

    supported = {f: _supported(f) for f in FAMILIES}
    if args.print_supported:
        for fam, ok in supported.items():
            print(f"{fam:16s} solver={'yes' if ok else 'NO '}")
        return 0

    usable = {f for f, ok in supported.items() if ok}
    for tier, fams in BUCKETS.items():
        if not [f for f in fams if f in usable]:
            raise SystemExit(f"tier {tier} has no solver-supported family: {fams}")

    cases = build_cases(usable, ask=args.ask)
    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f"{args.ask if args.ask != 'numbers' else 'physics'}.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    tiers = {}
    for c in cases:
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
    print(f"[ok] {len(cases)} cases -> {os.path.relpath(path, ROOT)}  tiers={tiers}")
    print(f"     solver-unsupported families excluded: {sorted(set(FAMILIES) - usable) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
