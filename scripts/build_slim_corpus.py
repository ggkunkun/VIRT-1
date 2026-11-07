#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_slim_corpus.py — 按实测数据构建"瘦身训练语料"

【实测依据】（scripts/analyze_variants2.py，18,330 条去重口径）
  tools schema   : 1193 tok/条，全库 1 个变体，占单条 token 的 46%
  tool_response#1: ~181 字符（parse_wish_intent 的 JSON spec）
  tool_response#2: ~1664 字符的长 markdown 手册，占全库 27% token
  重复样本       : 4,848 条 (20.9%)
  call#2 参数 67.7% 来自 tool_response#1（不是 #2）

【四种瘦身档位】
  none     原样
  dedup    仅去重                       省 20.9%
  drop2    去重 + 丢 tr2 与末尾总结       省 47.7%（相对原样）
  slim     去重 + 丢 tr2/总结 + schema瘦身 省 53.3%（相对原样）

【安全性】
  - tr2 与末尾总结同时丢弃：总结依赖 tr2，保留总结必须留 tr2，二者同进同退
  - 保留 mix-summary 比例的完整长样本（默认 15%），维持"能收尾总结"的能力
  - schema 瘦身只删参数的 description，保留 name/type/enum/required
    —— 推理侧仍用完整 schema，模型靠 name/type 定位参数，靠 enum 取值

用法：
  python scripts/build_slim_corpus.py --mode slim --out data/toolcall_slim.jsonl
  python scripts/build_slim_corpus.py --mode drop2 --mix-summary 0.15
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import hashlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "damodel_cad_cam_tuning", "dataset",
                    "virtu_toolcall_train_unified.jsonl")


def parse_args():
    p = argparse.ArgumentParser(description="构建瘦身 tool-call 训练语料")
    p.add_argument("--data", default=DATA)
    p.add_argument("--out", required=True)
    p.add_argument("--mode", default="slim",
                   choices=["none", "dedup", "drop2", "slim"])
    p.add_argument("--mix-summary", type=float, default=0.15,
                   help="保留多少比例的完整长样本（含 tr2 + 最终总结），维持收尾能力")
    p.add_argument("--slim-schema", action="store_true", default=None,
                   help="是否瘦身 tools schema（mode=slim 时默认开）")
    p.add_argument("--no-slim-schema", dest="slim_schema", action="store_false")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def norm_key(msgs):
    out = []
    for m in msgs:
        d = {"r": m.get("role")}
        if m.get("content"):
            d["c"] = " ".join(str(m.get("content") or "").split())
        if m.get("tool_calls"):
            d["t"] = json.dumps(m.get("tool_calls"), sort_keys=True, ensure_ascii=False)
        if m.get("name"):
            d["n"] = m.get("name")
        out.append(json.dumps(d, sort_keys=True, ensure_ascii=False))
    return hashlib.md5("\n".join(out).encode()).hexdigest()


def strip_param_desc(tools):
    out = []
    for t in tools or []:
        t = json.loads(json.dumps(t, ensure_ascii=False))
        fn = t.get("function") or {}
        props = (fn.get("parameters") or {}).get("properties") or {}
        for k, v in props.items():
            if isinstance(v, dict):
                v.pop("description", None)
        out.append(t)
    return out


def drop_tr2_and_summary(msgs):
    """保留 system/user/assistant#1/tool#1/assistant#2；丢弃 tool#2 与最终总结。"""
    out = []
    nc = 0
    for m in msgs:
        rr = m.get("role")
        if rr == "assistant":
            if m.get("tool_calls"):
                nc += 1
                if nc > 2:
                    break
                out.append(m)
            else:
                break
        elif rr == "tool":
            if nc >= 2:
                break
            out.append(m)
        else:
            out.append(m)
    return out


def main():
    args = parse_args()
    if args.mode == "slim" and args.slim_schema is None:
        args.slim_schema = True

    rnd = random.Random(args.seed)
    seen = set()
    out_rows = []
    stats = {"read": 0, "dup": 0, "kept_long": 0, "kept_short": 0,
             "dropped_summary": 0, "schema_slim": 0}

    with open(args.data, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            stats["read"] += 1
            msgs = r.get("messages") or []
            tools = r.get("tools") or []

            if args.mode != "none":
                k = norm_key(msgs)
                if k in seen:
                    stats["dup"] += 1
                    continue
                seen.add(k)

            row = {"tools": tools, "messages": msgs}

            if args.mode in ("drop2", "slim"):
                keep_long = rnd.random() < args.mix_summary
                if keep_long:
                    stats["kept_long"] += 1
                else:
                    new_msgs = drop_tr2_and_summary(msgs)
                    if len(new_msgs) < len(msgs):
                        stats["dropped_summary"] += 1
                    row["messages"] = new_msgs
                    stats["kept_short"] += 1

            if args.mode == "slim" and args.slim_schema:
                row["tools"] = strip_param_desc(tools)
                stats["schema_slim"] += 1

            out_rows.append(row)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[slim] 模式={args.mode} mix-summary={args.mix_summary} "
          f"schema瘦身={args.slim_schema}")
    print(f"[slim] 读取 {stats['read']:,} | 去重丢弃 {stats['dup']:,} | "
          f"输出 {len(out_rows):,}")
    print(f"[slim] 完整长样本 {stats['kept_long']:,} | 瘦身样本 {stats['kept_short']:,}")
    print(f"[slim] -> {args.out}")


if __name__ == "__main__":
    main()
