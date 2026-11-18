#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wm_step_test.py — 世界模型「真实 STEP 零件」端到端回归
=====================================================
定位（三层回归的第 2 层）：
  L1 单元层  —— wm_verifier / wm_derivation / wm_gate 的 selftest
  L2 端到端  —— 本文件：真实几何真值 + 真实 ollama 推理 + 真实护栏链路
  L3 契约层  —— 形态核验（单层平铺、invalid 契约、无静默改写）

纪律（沿用 verify_guard_feasibility 的教训）：
  1. 期望值一律由 wm_verifier.recompute 现场派生，不写作者手填值；
  2. 题面里的几何量取自真实 STEP 文件（build123d 读体积/包围盒/面数），
     不用编排好的假数；
  3. 同一条响应跑两种护栏口：scenario=None（生产链路，靠 infer 反推）
     与 scenario=scn（携结构化标注链路），分别报通过率，用来证明
     "不依赖调用侧传 scenario 也能还原族别与参数"。

用法：
  python scripts/wm_step_test.py --model virtu-wm-v3:latest --out _wm_step_test.json
  python scripts/wm_step_test.py --limit 3 --offset 0     # 分批，规避 600s 超时
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import wm_verifier  # noqa: E402
from guard_hooks import apply_guard  # noqa: E402
from eval_worldmodel import (  # noqa: E402
    call_ollama, extract_json, judge, _wrap, REL_TOL,
)

DEFAULT_STEP = os.path.join(ROOT, "projects", "impeller_autonomous_v100", "impeller_3d_cad.step")
RHO_AL6061 = 2.70e-3   # g/mm^3
RHO_45 = 7.85e-3       # g/mm^3


# ---------------------------------------------------------------------------
# 1) 真实几何真值
# ---------------------------------------------------------------------------
def read_step_truth(step_path: str) -> dict:
    """从真实 STEP 读体积 / 包围盒 / 面数。读不到就退到已实测常量并显式标注。"""
    truth = {"source": step_path, "degraded": False}
    try:
        from build123d import import_step
        shape = import_step(step_path)
        bb = shape.bounding_box()
        truth.update({
            "volume_mm3": float(shape.volume),
            "bbox_mm": [float(bb.size.X), float(bb.size.Y), float(bb.size.Z)],
            "n_solids": len(shape.solids()),
            "n_faces": len(shape.faces()),
        })
    except Exception as e:  # noqa: BLE001
        truth["degraded"] = True
        truth["error"] = f"{type(e).__name__}: {e}"
        # 2026-11-08 实测值（impeller_3d_cad.step）
        truth.update({"volume_mm3": 158187.75, "bbox_mm": [120.0, 120.0, 35.0],
                      "n_solids": 1, "n_faces": 44})
    return truth


# ---------------------------------------------------------------------------
# 2) 12 族题面 + 结构化 scenario（参数与 recompute 的输入键严格对齐）
# ---------------------------------------------------------------------------
def build_cases(t: dict) -> list:
    V = round(t["volume_mm3"], 2)
    X, Y, Z = [round(v, 2) for v in t["bbox_mm"]]
    stock = round(X * Y * (Z + 5.0), 2)          # 毛坯 = 包围盒 Z 向各留 5mm 余量
    hole_d = 20.0
    hole_v = round(3.141592653589793 * (hole_d / 2.0) ** 2 * Z, 2)

    cases = []

    # 1 removal —— 真实 CAD 体积差
    cases.append((
        "removal",
        f"铝合金 6061 毛坯尺寸 {X}×{Y}×{Z + 5.0} mm，铣削后实测成品体积 {V} mm^3，"
        f"切削参数 DOC=1.5 mm，WOC=10 mm，进给速度 vf=400 mm/min，"
        f"求材料去除体积、去除质量、MRR 与成品质量。",
        {"task": "removal", "inputs": {
            "stock_vol": stock, "volume_mm3": V, "doc": 1.5, "woc": 10.0,
            "vf": 400.0, "rho": RHO_AL6061}},
    ))

    # 2 roughness
    cases.append((
        "roughness",
        "车削每转进给量 f=0.08 mm/r，刀尖圆弧半径 r_eps=0.8 mm，"
        "求表面粗糙度 Ra(μm)。",
        {"task": "roughness", "inputs": {"f": 0.08, "r_eps": 0.8}},
    ))

    # 3 fea_fos —— 6061-T6 屈服 276MPa，叶根峰值等效应力按自重+2kN 轴向载荷估
    cases.append((
        "fea_fos",
        f"6061-T6 叶轮承受轴向载荷 2000 N 与自重，有限元峰值等效应力 165 MPa，"
        f"材料屈服强度 Sy=276 MPa，求安全系数 FOS 并判断 FOS≥1.5 是否通过。",
        {"task": "fea_fos", "inputs": {"Sy": 276.0, "sigma": 165.0}},
    ))

    # 4 collision —— 快速定位下探到毛坯顶面以下（真过切）
    cases.append((
        "collision",
        f"数控程序安全平面 Z={Z + 0.5} mm，快速移动最低点 Z={Z - 3.0} mm，"
        f"毛坯顶面 Z={Z} mm，判断是否存在碰撞与过切风险。",
        {"task": "collision", "inputs": {
            "z_safe": Z + 0.5, "z_min_rapid": Z - 3.0, "stock_top": Z}},
    ))

    # 5 tolerance —— 真实配合：φ50 H7 孔 + 3 环节公差链
    # 口径说明：wm_verifier.recompute 的 fit_clearance = upper_dev - lower_dev 即
    # 「公差带宽度」，故 scenario 传孔的上/下偏差（+0.025 / 0），题面问题同步写成
    # 「公差带宽度」，避免与「配合间隙」混淆造成判分口径冲突。
    cases.append((
        "tolerance",
        "孔 φ50H7 上偏差 +0.025 mm、下偏差 0 mm，与之配合的轴 φ50g6 忽略不计；"
        "公差链各分量公差 0.025 mm、0.016 mm、0.021 mm，"
        "求极值法半宽、RSS 半宽与公差带宽度。",
        {"task": "tolerance", "inputs": {
            "tols": [0.025, 0.016, 0.021], "upper_dev": 0.025, "lower_dev": 0.0}},
    ))

    # 6 geom_delta —— 在真实成品上开 φ20 通孔
    cases.append((
        "geom_delta",
        f"在实测工件（切除前体积 {round(V + hole_v, 2)} mm^3）上钻 φ{hole_d} 通孔，"
        f"孔体积 {hole_v} mm^3，求切除后体积与 ΔV 是否守恒（ΔV 应为负）。",
        {"task": "geom_delta", "inputs": {
            "feature_vol": hole_v, "before": round(V + hole_v, 2)}},
    ))

    # 7 mass_props —— 毛坯质量属性（解析几何，与 STEP 同口径包围盒）
    cases.append((
        "mass_props",
        f"长方体毛坯长 {X} mm 宽 {Y} mm 高 {Z + 5.0} mm，材料 6061 铝合金，"
        f"求体积、质量与绕 Z 轴转动惯量。",
        {"task": "mass_props", "inputs": {
            "shape": "box", "params": {"l": X, "w": Y, "h": Z + 5.0},
            "rho": RHO_AL6061}},
    ))

    # 8 invalid —— 题面缺关键参数，必须报错不得硬算
    cases.append((
        "invalid",
        "这个零件切削时材料去除体积是多少？注意：题面未提供毛坯尺寸与成品体积，"
        "也未给出切削深度和进给速度。",
        {"task": "invalid", "inputs": {"stock_vol": None, "doc": None, "vf": None}},
    ))

    # 9 design —— 需求 -> 法兰轴套设计
    cases.append((
        "design",
        "设计一只轴套，外径 φ197.6 mm，内孔 φ160 mm，厚 42 mm，"
        "4 个 φ9 孔均布，材料 45 钢，求体积、质量(kg)。",
        {"task": "design", "inputs": {
            "r_out": 98.8, "r_bore": 80.0, "t": 42.0, "n_holes": 4,
            "r_hole": 4.5, "rho": RHO_45}},
    ))

    # 10 process —— 工艺方案（转速/进给/MRR/粗糙度/切削时间）
    cases.append((
        "process",
        "45 钢轴类零件车削工艺：工件直径 D=60 mm，加工长度 L=180 mm，"
        "背吃刀量 ap=1.2 mm，每转进给量 f=0.12 mm/r，切削速度 vc=150 m/min，"
        "刀尖圆弧半径 0.8 mm，求主轴转速、进给速度、材料去除率、Ra 与切削时间。",
        {"task": "process", "inputs": {
            "D": 60.0, "L": 180.0, "ap": 1.2, "f": 0.12, "vc": 150.0,
            "r_eps": 0.8}},
    ))

    # 11 adapt_machine —— 陌生机床能力核对
    cases.append((
        "adapt_machine",
        f"要到一台最高转速 n_max=6000 r/min 的机床上加工工件直径 D={X} mm 的零件，"
        f"工艺要求切削速度 vc=180 m/min，求所需主轴转速并判断该机床能否胜任。",
        {"task": "adapt_machine", "inputs": {
            "D": X, "vc": 180.0, "n_max": 6000.0}},
    ))

    # 12 adapt_material —— 材料替代后重算安全系数
    cases.append((
        "adapt_material",
        "原设计用 40Cr 调质（屈服强度 Sy=1034 MPa），因供货改 45 钢调质，"
        "屈服强度 355 MPa，工作应力 240 MPa，求替代后安全系数并判断是否可接受。",
        {"task": "adapt_material", "inputs": {"Sy": 355.0, "sigma": 240.0}},
    ))

    return cases


def _guard_obj(g: dict) -> dict:
    """从 apply_guard 回执提取供 judge 判分的对象（兼容常规 world_state 与 invalid 契约形态）。"""
    if not isinstance(g, dict):
        return {}
    corr = g.get("corrected")
    if isinstance(corr, dict) and ("invalid" in corr or "world_state" in corr):
        return corr
    return _wrap(g.get("final_world_state"))


# ---------------------------------------------------------------------------
# 3) 端到端跑批
# ---------------------------------------------------------------------------
def run(model: str, cases: list, offset: int = 0, limit: int = 0,
        timeout: float = 180.0, force_json: bool = True) -> dict:
    sel = cases[offset:offset + limit] if limit > 0 else cases[offset:]
    rows = []
    for fam, prompt, scn in sel:
        t0 = time.time()
        if fam == "invalid" or (isinstance(scn, dict) and scn.get("task") == "invalid"):
            exp = {"invalid": True, "world_state": None,
                   "reason": "missing_required_inputs",
                   "violated_constraints": ["missing_inputs"]}
        else:
            exp = {"world_state": wm_verifier.recompute(scn)} if scn else {"world_state": None}
            if scn and not exp["world_state"]:
                rows.append({"family": fam, "skipped": "recompute_empty", "prompt": prompt})
                continue
        try:
            raw = call_ollama(model, prompt, "", force_json=force_json,
                              timeout_sec=timeout)
        except Exception as e:  # noqa: BLE001
            rows.append({"family": fam, "error": f"{type(e).__name__}: {e}",
                         "prompt": prompt})
            continue
        dt = round(time.time() - t0, 2)

        # 生产链路：不传 scenario，护栏必须自己反推
        g_prod = apply_guard(raw, prompt=prompt, scenario=None, tol_rel=REL_TOL)
        # 标注链路：传生成器口径的 scenario
        g_lab = apply_guard(raw, prompt=prompt, scenario=scn, tol_rel=REL_TOL)

        raw_obj = extract_json(raw)
        ok_raw, fmt_raw, miss_raw = judge(fam, exp, raw_obj) if scn \
            else (None, None, [])
        ok_prod, _, miss_prod = judge(fam, exp, _guard_obj(g_prod)) \
            if scn else (None, None, [])
        ok_lab, _, miss_lab = judge(fam, exp, _guard_obj(g_lab)) \
            if scn else (None, None, [])

        rows.append({
            "family": fam, "prompt": prompt, "scenario": scn, "sec": dt,
            "expected": exp, "raw": raw,
            "raw_pass": ok_raw, "raw_fmt": fmt_raw, "raw_miss": miss_raw,
            "prod": {"action": g_prod.get("action"), "layers": g_prod.get("layers_hit"),
                     "issues": g_prod.get("issues"), "pass": ok_prod, "miss": miss_prod},
            "lab": {"action": g_lab.get("action"), "layers": g_lab.get("layers_hit"),
                    "issues": g_lab.get("issues"), "pass": ok_lab, "miss": miss_lab},
        })
    return {"model": model, "n": len(rows), "rows": rows}


def summarize(res: dict) -> None:
    rows = [r for r in res["rows"] if "skipped" not in r and "error" not in r]
    print(f"\n=== STEP 端到端回归: {res['model']} (n={len(rows)}) ===")
    print(f"{'family':15s} {'raw':>6s} {'prod':>6s} {'lab':>6s} "
          f"{'prod_action':>12s} {'sec':>7s}")
    for r in rows:
        f = lambda v: "-" if v is None else ("PASS" if v else "FAIL")  # noqa: E731
        print(f"{r['family']:15s} {f(r['raw_pass']):>6s} {f(r['prod']['pass']):>6s} "
              f"{f(r['lab']['pass']):>6s} {str(r['prod']['action']):>12s} "
              f"{r['sec']:>7.1f}")
        if r["prod"]["issues"]:
            print(f"    prod issues: {json.dumps(r['prod']['issues'], ensure_ascii=False)[:220]}")
        if r["prod"]["miss"]:
            print(f"    prod miss:   {json.dumps(r['prod']['miss'], ensure_ascii=False)[:220]}")
    n_valid = [r for r in rows if r["prod"]["pass"] is not None]
    if n_valid:
        pp = sum(1 for r in n_valid if r["prod"]["pass"])
        pl = sum(1 for r in n_valid if r["lab"]["pass"])
        pr = sum(1 for r in n_valid if r["raw_pass"])
        print(f"  {'TOTAL':15s} {pr:3d}/{len(n_valid)}  prod {pp:3d}/{len(n_valid)}"
              f"  lab {pl:3d}/{len(n_valid)}")
    blocked = sum(1 for r in rows if r["prod"]["action"] in ("rejected", "escalate"))
    print(f"  prod 拦截(rejected/escalate) = {blocked}")
    errs = [r for r in res["rows"] if "error" in r or "skipped" in r]
    if errs:
        print(f"  [warn] 跳过/异常 {len(errs)} 条："
              f"{[e['family'] for e in errs]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="virtu-wm-v3:latest")
    ap.add_argument("--step", default=DEFAULT_STEP)
    ap.add_argument("--out", default="_wm_step_test.json")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--no-json-format", action="store_true")
    ap.add_argument("--truth-only", action="store_true", help="只打印几何真值与用例表，不调模型")
    args = ap.parse_args()

    t = read_step_truth(args.step)
    print(f"[step] {t['source']}")
    print(f"[step] V={t['volume_mm3']:.2f} mm^3  bbox={t['bbox_mm']}  "
          f"solids={t['n_solids']}  faces={t['n_faces']}  degraded={t['degraded']}")
    cases = build_cases(t)
    print(f"[cases] {len(cases)} 族：{[c[0] for c in cases]}")
    if args.truth_only:
        for fam, prompt, scn in cases:
            exp = wm_verifier.recompute(scn) if scn else None
            print(f"\n-- {fam}\n   Q: {prompt}\n   A: {json.dumps(exp, ensure_ascii=False)}")
        return 0

    res = run(args.model, cases, args.offset, args.limit, args.timeout,
              not args.no_json_format)
    res["step_truth"] = t
    summarize(res)
    out = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[ok] 明细 -> {out}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
