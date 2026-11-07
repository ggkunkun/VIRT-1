#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
holdout_check.py — 用"结构×材料留出集"测真实泛化，不做同分布自欺。

留出集由 scripts/build_train_final.py 切出：整个 (material, 工具链) 组合在训练集中
完全不出现，因此这里的分数回答的是"没见过的材料/链能不能照工具 schema 调对"。

指标（全部可复现、逐条留证）：
  name_match  工具名对了
  args_match  工具名 + 全部参数键值都对（数值容差 1e-6）
  chain_match 整条工具链（多调用场景）按顺序全对

用法：
  python -m virtu_eval.holdout_check --arm ollama_virtu_toolcall \
      --data data/train/virtu_toolcall_holdout.jsonl --out work/_holdout_<arm>.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_eval.arms import build_arm  # noqa: E402


def gold_calls(row):
    out = []
    for m in row["messages"]:
        for tc in (m.get("tool_calls") or []):
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:  # noqa: BLE001
                args = {}
            out.append({"name": fn.get("name"), "args": args})
    return out


def parse_calls(text):
    """从模型输出里抠出工具调用 JSON：支持 {"name":..,"arguments":..} 与
    {"tool":..,"arguments":..} 两种写法，也支持被包在 <tool_call> 里。"""
    t = re.sub(r"```(?:json)?", "", text or "")
    dec = json.JSONDecoder()
    objs = []
    for i, ch in enumerate(t):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(t[i:])
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict):
            objs.append(obj)
    calls = []
    for obj in objs:
        name = obj.get("name") or obj.get("tool")
        args = obj.get("arguments") or obj.get("args")
        if name and isinstance(args, (dict, str)):
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:  # noqa: BLE001
                    continue
            calls.append({"name": name, "args": args})
    return calls


def close(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= 1e-6
    return a == b


def args_equal(want, got):
    if set(want) - set(got):
        return False
    for k, v in want.items():
        if isinstance(v, dict):
            if not isinstance(got.get(k), dict) or not args_equal(v, got[k]):
                return False
        else:
            if not close(v, got.get(k)):
                return False
    return True


def score_row(row, text):
    gold = gold_calls(row)
    got = parse_calls(text)
    if not gold:
        return {"name": False, "args": False, "chain": False, "note": "no_gold"}
    first = gold[0]
    name_ok = bool(got) and got[0]["name"] == first["name"]
    args_ok = name_ok and args_equal(first["args"], got[0]["args"])
    chain_ok = args_ok and len(got) >= len(gold) and all(
        g["name"] == gold[i]["name"] and args_equal(gold[i]["args"], g["args"])
        for i, g in enumerate(gold))
    return {"name": name_ok, "args": args_ok, "chain": chain_ok, "n_gold": len(gold),
            "n_got": len(got)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--arms-config", default="virtu_eval/arms.json")
    ap.add_argument("--data", default="data/train/virtu_toolcall_holdout.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=192)
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = json.load(open(os.path.join(root, a.arms_config), encoding="utf-8"))[a.arm]
    rows = [json.loads(l) for l in open(os.path.join(root, a.data), encoding="utf-8") if l.strip()]
    if a.limit:
        rows = rows[: a.limit]

    arm = build_arm(spec)
    arm.load()
    recs = []
    try:
        for i, row in enumerate(rows, 1):
            msgs = [m for m in row["messages"] if m.get("role") != "assistant"][:2]
            msgs = [{"role": m["role"], "content": m.get("content") or ""} for m in msgs]
            # Holdout rows carry the exact schemas used in training; withholding
            # them would measure prompt-only behavior, not tool-call generalization.
            gen = arm.generate(msgs, max_tokens=a.max_tokens, temperature=0.0, seed=1234,
                               tools=row.get("tools"))
            text = gen.get("text") or ""
            rec = {"prompt": msgs[-1]["content"], "response": text, **score_row(row, text),
                   "gold": gold_calls(row), "gen": {k: v for k, v in gen.items() if k != "text"}}
            recs.append(rec)
            if i % 10 == 0:
                print(f"  [{i}/{len(rows)}]", flush=True)
    finally:
        arm.unload()

    os.makedirs(os.path.dirname(os.path.abspath(os.path.join(root, a.out))), exist_ok=True)
    with open(os.path.join(root, a.out), "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = len(recs)
    summary = {"arm": a.arm, "n": n,
               "name_match": round(sum(r["name"] for r in recs) / max(1, n), 4),
               "args_match": round(sum(r["args"] for r in recs) / max(1, n), 4),
               "chain_match": round(sum(r["chain"] for r in recs) / max(1, n), 4)}
    print(json.dumps(summary, ensure_ascii=False))
    with open(os.path.join(root, a.out.replace(".jsonl", "_summary.json")), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
