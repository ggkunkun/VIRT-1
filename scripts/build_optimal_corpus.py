#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_optimal_corpus.py — 分层平衡的最优语料（同时解决"效率"与"质量"）

【实测前提】scripts/analyze_sufficiency.py / scripts/analyze_efficiency.py
  1) 信息维度极少
     - 工具序列×参数键结构：     仅     7 种
     - 结构×material：           仅    30 种
     - user 表述模式（数字掩码）：仅   121 种
  2) 瘦身语料里 system 段占 63.5%（tools schema 全库唯一，每条重复渲染）
  3) 【质量问题】material 严重失衡
       Cr12MoV  56.7%   ← 模型会偏向预测它
       20CrMnTi  0.3% (50条)  Steel45 1.3%  P20 1.4% ...
     这是会实打实损害效果的，比效率问题更严重

【本脚本做什么】
  按 material 分层平衡抽样，每层优先覆盖不同表述模式；再配合 schema 档位压缩。
  用 ~2,500 条覆盖全部 121 种表述 + 9 种材料，而不是 18,330 条。

【schema 档位】
  slim    当前瘦身 schema（916 tok）        基线
  ultra   极限瘦身，删类型修饰（582 tok）    省 ~20%
  name    只留工具名（308 tok）             省 ~37%
  none    不带 schema，工具内置化（0 tok）   省 ~60%（推理侧须同步不带 tools）

用法:
  python scripts/build_optimal_corpus.py --per-material 300 --schema ultra \
      --out data/toolcall_optimal.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLIM = os.path.join(HERE, "data", "toolcall_slim.jsonl")


def parse_args_of(msg):
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except Exception:
            args = {}
        if not isinstance(args, dict):
            args = {}
        return fn.get("name"), tuple(sorted(args.keys())), args
    return None, (), {}


def collect_args(msgs):
    allargs = {}
    for m in msgs:
        if m.get("tool_calls"):
            _, _, a = parse_args_of(m)
            if a:
                allargs.update(a)
    return allargs


def user_phrase(msgs):
    for m in msgs:
        if m.get("role") == "user":
            return " ".join(re.sub(r"[-+]?\d*\.?\d+", "#",
                                   str(m.get("content") or "")).split())[:120]
    return ""


def ultra_thin(tools):
    out = []
    for t in tools or []:
        fn = t.get("function") or {}
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        compact = {}
        for k, v in props.items():
            if not isinstance(v, dict):
                continue
            e = {"type": v.get("type")}
            if "enum" in v:
                e["enum"] = v["enum"]
            compact[k] = e
        out.append({"type": "function", "function": {
            "name": fn.get("name"),
            "parameters": {"type": "object", "properties": compact,
                           "required": params.get("required") or []}}})
    return out


def name_only(tools):
    return [{"type": "function", "function": {
        "name": (t.get("function") or {}).get("name"),
        "parameters": {"type": "object", "properties": {}, "required": []}
    }} for t in tools or []]


def apply_schema(tools, mode):
    if mode == "ultra":
        return ultra_thin(tools)
    if mode == "name":
        return name_only(tools)
    if mode == "none":
        return []
    return tools


def main():
    p = argparse.ArgumentParser(description="分层平衡的最优训练语料")
    p.add_argument("--data", default=SLIM)
    p.add_argument("--out", required=True)
    p.add_argument("--per-material", type=int, default=300,
                   help="每种 material 最多取多少条（默认 300，可覆盖全部表述模式）")
    p.add_argument("--schema", default="ultra",
                   choices=["slim", "ultra", "name", "none"])
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rng = random.Random(args.seed)
    by_mat = defaultdict(list)
    total = 0
    with open(args.data, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            total += 1
            a = collect_args(r["messages"])
            mat = str(a.get("material", "None"))
            by_mat[mat].append({"row": r, "phrase": user_phrase(r["messages"])})

    sel_recs = []
    for mat, lst in sorted(by_mat.items()):
        # 先按表述模式去重优先，保证覆盖尽量多的说法
        seen = set()
        phase1, phase2 = [], []
        for it in lst:
            if it["phrase"] in seen:
                phase2.append(it)
            else:
                seen.add(it["phrase"])
                phase1.append(it)
        rng.shuffle(phase1)
        rng.shuffle(phase2)
        picked = phase1[: args.per_material]
        if len(picked) < args.per_material:
            picked += phase2[: args.per_material - len(picked)]
        sel_recs.extend(picked)

    rng.shuffle(sel_recs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    mat_dist = Counter()
    with open(args.out, "w", encoding="utf-8") as f:
        for it in sel_recs:
            row = {"tools": apply_schema(it["row"].get("tools") or [], args.schema),
                   "messages": it["row"]["messages"]}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            mat_dist[str(collect_args(row["messages"]).get("material", "None"))] += 1

    print(f"[optimal] 输入 {total:,} 条 -> 输出 {len(sel_recs):,} 条 "
          f"(压缩 {100*(1-len(sel_recs)/total):.1f}%)")
    print(f"[optimal] schema 档位: {args.schema}")
    print(f"[optimal] material 分布（已平衡）:")
    for k, v in mat_dist.most_common():
        print(f"    {k:<12s} {v:>5,}  {v/len(sel_recs)*100:5.1f}%")
    print(f"[optimal] -> {args.out}")


if __name__ == "__main__":
    main()
