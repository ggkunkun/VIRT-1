#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_efficiency.py — 学习效率分析：瘦身之后还剩多少纯冗余？

核心问题：
  瘦身把 token 砍了一半，但被砍的都不是 system 段 —— tools schema 依然存在，
  所以它在剩余语料里的占比可能不降反升。这是下一层的杠杆。

同时测：
  - system / user / assistant 在瘦身语料里的真实占比
  - 若把 tools schema 进一步极限压缩（只留 name+参数名+enum），能到多少
  - 若完全去掉 schema（把 8 个工具做成"内置知识"），剩余 token 是多少
  - 多样样本的实际规模（同一工具同一模式的重复度）
"""
from __future__ import annotations

import json
import os
import sys
import hashlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from virtu_tokenize import render_full  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "checkpoints", "_base_qwen3_8b")
SLIM = os.path.join(HERE, "data", "toolcall_slim.jsonl")
OUT = os.path.join(HERE, "data", "validation", "efficiency_analysis.json")
IM_START = "<|im_start|>"
STRIDE = int(os.environ.get("EFF_STRIDE", "5"))


def role_segments(text):
    segs = []
    idx = 0
    while True:
        i = text.find(IM_START, idx)
        if i < 0:
            break
        j = text.find("\n", i)
        if j < 0:
            break
        role = text[i + len(IM_START):j].strip()
        nxt = text.find(IM_START, j)
        end = nxt if nxt > 0 else len(text)
        segs.append((role, j + 1, end))
        idx = end
    return segs


def ultra_thin_schema(tools):
    """极限瘦身：每个工具只留 name + 参数名列表 + enum 值 + required，删掉一切描述与类型修饰。"""
    out = []
    for t in tools or []:
        fn = (t.get("function") or {})
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        compact = {}
        for k, v in props.items():
            if not isinstance(v, dict):
                continue
            entry = {"type": v.get("type")}
            if "enum" in v:
                entry["enum"] = v["enum"]
            compact[k] = entry
        out.append({"type": "function", "function": {
            "name": fn.get("name"),
            "parameters": {"type": "object", "properties": compact,
                           "required": params.get("required") or []}
        }})
    return out


def no_names_schema(tools):
    """只留工具名，完全不列参数（模型靠训练"背"参数结构）。"""
    return [{"type": "function", "function": {
        "name": (t.get("function") or {}).get("name"),
        "parameters": {"type": "object", "properties": {}, "required": []}
    }} for t in tools or []]


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    n = 0
    sn = 0
    role_tok = Counter()
    V = Counter()
    total_tok = 0

    # 多样性：按"工具调用序列 + 参数键集合"作指纹
    diver = Counter()
    tool_combo = Counter()

    with open(SLIM, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            msgs = r["messages"]
            tools = r.get("tools") or []
            n += 1

            # 多样性指纹：调用的工具有序序列 + 每个调用的键集合
            seq = []
            for m in msgs:
                for tc in (m.get("tool_calls") or []):
                    fn = (tc.get("function") or {})
                    nm = fn.get("name")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = {}
                    seq.append((nm, tuple(sorted(args.keys()))))
                    break
            if seq:
                tool_combo[tuple(seq)] += 1

            if sn % STRIDE:
                sn += 1
                continue
            sn += 1

            # 当前瘦身语料的分段
            text = render_full(tok, msgs, tools)
            ids = tok(text, add_special_tokens=False, return_offsets_mapping=True)
            offs = ids["offset_mapping"]
            segs = role_segments(text)
            bounds = [(s, e) for _, s, e in segs]
            roles = [r_ for r_, _, _ in segs]
            bi = 0
            for a, b in offs:
                if b <= a:
                    continue
                while bi + 1 < len(bounds) and a >= bounds[bi][1]:
                    bi += 1
                if a >= bounds[bi][0] and b <= bounds[bi][1]:
                    role_tok[roles[bi]] += 1
            V["cur"] += len(ids["input_ids"])
            total_tok += len(ids["input_ids"])

            V["ultra"] += len(tok(render_full(tok, msgs, ultra_thin_schema(tools)),
                                  add_special_tokens=False)["input_ids"])
            V["noname"] += len(tok(render_full(tok, msgs, no_names_schema(tools)),
                                   add_special_tokens=False)["input_ids"])
            # 完全去掉 tools（模型内置化）
            V["notools"] += len(tok(render_full(tok, msgs, []),
                                    add_special_tokens=False)["input_ids"])

            if sn % (STRIDE * 800) < STRIDE:
                print(f"  {sn // STRIDE} ...", flush=True)

    scale = n / max(1, sn // STRIDE)
    # 取一条测 schema 本身三种形态的 token
    with open(SLIM, encoding="utf-8") as f:
        r0 = json.loads(f.readline())
    t0 = r0.get("tools") or []
    s_cur = len(tok(json.dumps(t0, ensure_ascii=False), add_special_tokens=False)["input_ids"])
    s_ult = len(tok(json.dumps(ultra_thin_schema(t0), ensure_ascii=False),
                    add_special_tokens=False)["input_ids"])
    s_non = len(tok(json.dumps(no_names_schema(t0), ensure_ascii=False),
                    add_special_tokens=False)["input_ids"])

    res = {}
    for k in V:
        res[k] = int(V[k] * scale)
    base = res["cur"]

    out = {
        "samples": n,
        "role_token_breakdown_slim": dict(role_tok),
        "role_pct": {k: round(v / sum(role_tok.values()) * 100, 2)
                     for k, v in role_tok.items()},
        "schema_tokens_per_variant": {
            "current_slim": s_cur, "ultra_thin": s_ult, "name_only": s_non,
        },
        "variants": res,
        "saving_vs_current": {k: round(100 * (1 - v / base), 1) for k, v in res.items()},
        "unique_tool_key_combos": len(tool_combo),
        "combo_top10": [{"combo": str(c)[:110], "count": v}
                        for c, v in tool_combo.most_common(10)],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 72)
    print("学习效率分析：瘦身后还剩多少冗余")
    print("=" * 72)
    print(f"瘦身语料 {n:,} 条 | 每 epoch token {base:,}")
    print()
    print("--- 瘦身语料角色占比（system 不降反升？）---")
    tot = sum(role_tok.values())
    for k, v in role_tok.most_common():
        print(f"  {k:12s} {v:>11,}  {v/tot*100:5.1f}%")
    print()
    print("--- tools schema 三种形态（单条）---")
    sv = out["schema_tokens_per_variant"]
    print(f"  当前瘦身 {sv['current_slim']} tok | 极限瘦身 {sv['ultra_thin']} tok "
          f"| 只留工具名 {sv['name_only']} tok")
    print()
    print("--- 进一步压缩的收益 ---")
    desc = {"cur": "当前 slim 基线", "ultra": "极限瘦身 schema",
            "noname": "schema 只留工具名", "notools": "完全不要 schema（工具内置）"}
    for k in ("cur", "ultra", "noname", "notools"):
        print(f"  {k:8s} {res[k]:>12,}  省 {out['saving_vs_current'][k]:>5.1f}%   {desc[k]}")
    print()
    print("--- 多样性 ---")
    print(f"  不同「工具序列+参数键组合」仅 {out['unique_tool_key_combos']} 种")
    for c in out["combo_top10"][:6]:
        print(f"    {c['count']:>6,} 条  {c['combo']}")
    print(f"\n报告 -> {OUT}")


if __name__ == "__main__":
    main()
