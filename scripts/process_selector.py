# -*- coding: utf-8 -*-
"""工艺判定：自动区分车削 / 三轴铣 / 五轴铣（含车铣复合），并输出任务拆解 DAG。

判定依据全部来自网格实测（不靠零件名）：
  - 回转度 rotationality：按 Z 分层统计半径 r 的角向离散度（越小越像回转体）
  - 叶片/流道周期性：某一 Z 带的 r(theta) 做 FFT，主频即叶片数
  - 型腔深宽比：包围盒高 / 最大半径
  - 端面占比：|nz|>0.7 的面积占比（车削件通常端面占比高且回转度高）

用法:
  python scripts/process_selector.py --design design.stl --report process_decision.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def metrics(mesh: trimesh.Trimesh) -> dict:
    lo, hi = mesh.bounds
    size = hi - lo
    pts, _ = trimesh.sample.sample_surface(mesh, 20000)
    r = np.hypot(pts[:, 0], pts[:, 1])
    z = pts[:, 2]

    # 回转度：Z 分层，每层 r 的 (p95-p5)/p95
    zs = np.linspace(z.min(), z.max(), 21)
    spreads = []
    for i in range(20):
        m = (z >= zs[i]) & (z < zs[i + 1])
        if m.sum() > 100:
            rr = r[m]
            p95 = np.percentile(rr, 95)
            if p95 > 1e-6:
                spreads.append(float((p95 - np.percentile(rr, 5)) / p95))
    spread = float(np.mean(spreads)) if spreads else 0.0
    rotationality = 1.0 - min(1.0, spread / 0.5)

    # 叶片数：在 r 最大附近的 Z 带，按 theta 分箱取 max r，再做 FFT
    band = (z >= z.min() + 0.3 * size[2]) & (z <= z.min() + 0.7 * size[2])
    blade_count = 0
    if band.sum() > 500:
        th = np.arctan2(pts[band, 1], pts[band, 0])
        rr = r[band]
        nb = 180
        idx = ((th + np.pi) / (2 * np.pi) * nb).astype(int) % nb
        prof = np.full(nb, np.nan)
        for k in range(nb):
            sel = idx == k
            if sel.any():
                prof[k] = rr[sel].max()
        if np.isfinite(prof).all():
            sig = prof - prof.mean()
            spec = np.abs(np.fft.rfft(sig))
            spec[:3] = 0  # 去掉 1/2/3 阶低频（椭圆度/偏心）
            blade_count = int(np.argmax(spec))

    nz = np.abs(mesh.face_normals[:, 2])
    areas = mesh.area_faces
    flat_ratio = float(areas[nz > 0.7].sum() / max(areas.sum(), 1e-9))
    depth_ratio = float(size[2] / max(size[0], size[1]))

    return {
        "bbox_mm": [round(float(v), 2) for v in size],
        "max_radius_mm": round(float(r.max()), 2),
        "rotationality": round(rotationality, 3),
        "radius_spread": round(spread, 3),
        "blade_count_fft": blade_count,
        "flat_face_ratio": round(flat_ratio, 3),
        "height_over_diameter": round(float(size[2] / max(size[0], size[1])), 3),
        "watertight": bool(mesh.is_watertight),
    }


def decide(m: dict) -> dict:
    rot = m["rotationality"]
    blades = m["blade_count_fft"]
    flat = m["flat_face_ratio"]

    turning = 100 * rot - 40 * (1 if blades >= 6 else 0) - 20 * max(0.0, flat - 0.5)
    five = 70 * (1 - rot) + 30 * (1 if blades >= 6 else 0) + 10 * (1 if m["watertight"] else 0)
    three = 55 - 25 * (1 if blades >= 6 else 0) + 20 * max(0.0, rot - 0.6)

    scores = {"turning": round(turning, 1), "3axis_milling": round(three, 1), "5axis_milling": round(five, 1)}
    best = max(scores, key=scores.get)

    reasons = []
    if rot >= 0.8:
        reasons.append(f"回转度 {rot:.2f}：各 Z 层半径离散小，可车")
    else:
        reasons.append(f"回转度仅 {rot:.2f}：半径随角度变化大，车刀无法成形")
    if blades >= 6:
        reasons.append(f"FFT 主频 {blades} 阶：存在周期叶片/流道，需要多轴联动")
    if flat >= 0.5:
        reasons.append(f"端面占比 {flat:.2f}：有较大平面，可用铣削")
    if m["watertight"]:
        reasons.append("网格封闭：可作为实体毛坯/设计基准")

    return {"scores": scores, "recommended": best, "reasons": reasons}


DAG = [
    ("T1", "零件识别与工艺判定", "process_selector.py 输出 recommended + 指标；回转度/叶片数/深宽比全部实测"),
    ("T2", "机床与控制系统选择", "按工艺选机型：五轴铣选 B/C 摆头转台（NMV1500 + FANUC 30iM），确认行程覆盖包络"),
    ("T3", "毛坯自动识别", "auto_stock_recognition.py 生成包容块（余量 3/5/3），20000 点包容性必须 outside=0"),
    ("T4", "夹具与工件坐标系", "夹具底面贴台面，毛坯底面贴夹具顶面；WCS 放毛坯上表面中心，Z0=顶面"),
    ("T5", "刀具库", "按最小圆角/流道宽度选刀：粗 D16、半精 D10 棒棒糖、伸出 ≥ 流道深度"),
    ("T6", "刀路与 NC", "粗→半精→精；封闭流道只从 OD 槽口进入；G43.4 RTCP 开，结束 G49"),
    ("T7", "NC 静态校验", "禁止车削代码；G00 不下扎；主轴先开；M30 收尾；FANUC 语法校验 0 错"),
    ("T8", "VERICUT 工位装配", "机床/控制/夹具/毛坯/设计/NC/刀具/偏置逐项落位，XML 可解析"),
    ("T9", "仿真与偏差", "仿真日志 0 error/0 collision；Auto-Diff 红=过切必须停"),
    ("T10", "交付", "模型 + 仿真报告 + 参数校验清单，全部带实测证据"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    mesh = trimesh.load(args.design, force="mesh")
    m = metrics(mesh)
    d = decide(m)
    out = {
        "design_file": args.design,
        "metrics": m,
        "decision": d,
        "task_dag": [{"id": i, "task": t, "acceptance": a} for i, t, a in DAG],
        "basis": "measured (mesh sampling + FFT)",
    }
    Path(args.report).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
