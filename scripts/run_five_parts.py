#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_five_parts.py — 5 个真实零件的 CAD→CAM→仿真闭环，并把失败写回数据集。

口径（与 AGENT_CHAIN_RUNTIME.md 一致，且只认回读证据）：
  executed    软件真跑，产物有实测数值
  substituted 该软件无原生接口，由确定性校验替代
  blocked     原生接口在但本机条件缺失，必须附实测报错
「宏返回 True」「窗口开着」一律不算 executed。

输出：
  runs/five_parts/<ts>/<part>/chain_evidence.json   每零件证据
  runs/five_parts/five_parts_summary.json           汇总（计数 + 逐阶段状态）
  data/validation/five_parts_failures.jsonl         失败写回（可直接并入训练语料的反例池）

用法：
  python scripts/run_five_parts.py                 # 跑全部 5 个
  python scripts/run_five_parts.py --parts shaft   # 只跑指定零件
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PART_WISHES = [
    ("flange_ss304", "我想制造一款法兰盘 材质SS304 外径80mm 轴孔24mm 宽20mm"),
    ("shaft_45steel", "车削一根传动轴 材质45#钢 外径50mm 轴孔0mm 长度120mm"),
    ("wheel_mold_cr12", "我想制造一款精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm 三道圆弧槽R15 R12 R10"),
    ("impeller_ti", "我想制造一款五轴叶轮 材质Ti-6Al-4V 外径100mm 轴孔30mm 长度60mm 六道叶片 圆弧槽R8 R6"),
    ("bracket_al7075", "制造一款铝合金精密支架 材质AL7075-T6 外径70mm 轴孔20mm 宽35mm 两道圆弧槽R5 R4"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="", help="逗号分隔的零件 name，空=全部")
    ap.add_argument("--out-root", default=os.path.join(ROOT, "runs", "five_parts"))
    a = ap.parse_args()
    only = [x for x in a.parts.split(",") if x]

    from agent_chain_executor import run_chain  # 延迟导入，避免无 GUI 环境下导入期副作用

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_root = os.path.join(a.out_root, ts)
    os.makedirs(out_root, exist_ok=True)
    summary = {"started": ts, "parts": [], "counts": {"executed": 0, "substituted": 0, "blocked": 0},
               "failures": []}
    for name, wish in PART_WISHES:
        if only and name not in only:
            continue
        print(f"[part] {name} ...", flush=True)
        t0 = time.time()
        try:
            bundle = run_chain(wish, out_root=out_root, memory_safe=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[part] {name} 链级异常: {exc!r}", flush=True)
            summary["parts"].append({"name": name, "wish": wish, "stages": {},
                                     "error": f"{type(exc).__name__}:{exc}"})
            summary["counts"]["blocked"] += 1
            continue
        verdicts = bundle.get("verdicts", {})
        rec = {"name": name, "wish": wish, "out_dir": bundle.get("out_dir"),
               "spec": bundle.get("spec"), "verdicts": verdicts,
               "wall_min": round((time.time() - t0) / 60, 2)}
        summary["parts"].append(rec)
        for st, v in verdicts.items():
            summary["counts"][v] = summary["counts"].get(v, 0) + 1
            if v == "blocked":
                ev = (bundle.get("stages") or {}).get(st, {})
                summary["failures"].append({
                    "part": name, "stage": st, "status": v,
                    "error": ev.get("error") or ev.get("notes") or ev.get("note") or "",
                    "unlock": ev.get("unlock") or ev.get("unlock_action") or "",
                    "evidence_dir": bundle.get("out_dir"),
                    "wish": wish,
                })
        print(f"[part] {name} -> {verdicts}", flush=True)

    with open(os.path.join(out_root, "five_parts_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    fpath = os.path.join(ROOT, "data", "validation", "five_parts_failures.jsonl")
    with open(fpath, "w", encoding="utf-8") as f:
        for rec in summary["failures"]:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(summary["counts"], ensure_ascii=False))
    print(f"[out] {os.path.join(out_root, 'five_parts_summary.json')}")
    print(f"[out] {fpath} ({len(summary['failures'])} 条失败记录)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
