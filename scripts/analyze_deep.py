#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_deep.py — 深度校验：参数依赖 / 模板副作用 / 学习信号占比

回答：
  Q1 tool_calls.arguments 的真实类型？call#2 参数是否真的不依赖 tool_response？
  Q2 为什么 S3(丢末尾总结) token 反而 +3.3%？模板副作用是什么？
  Q3 assistant token 里，tool_call 段 vs 最终总结段各占多少？（学习信号密度）
  Q4 第二个 tool_response（长 markdown 手册）占比多大？可否安全裁剪？
"""
from __future__ import annotations

import json
import os
import sys
import hashlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from virtu_tokenize import render_full, find_assistant_spans  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "checkpoints", "_base_qwen3_8b")
DATA = os.path.join(HERE, "damodel_cad_cam_tuning", "dataset",
                    "virtu_toolcall_train_unified.jsonl")
OUT = os.path.join(HERE, "data", "validation", "deep_analysis.json")
IM_START = "<|im_start|>"


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    n = 0
    arg_types = Counter()
    # call#2 参数值 -> 来自哪个 tool_response
    dep = {"tool1": 0, "tool2": 0, "nowhere": 0, "total": 0}
    # call#1 参数值 -> 来自 user
    dep1 = {"user": 0, "nowhere": 0, "total": 0}
    # assistant token 分段
    asst_tc = 0
    asst_final = 0
    # 工具返回长度
    tr_chars = Counter()
    tr_tok = Counter()
    # 模板副作用：S3 变体前后对比
    s3_probe = []
    # 每个 tool 名字的调用频次
    tool_freq = Counter()

    def scalar_values(obj):
        vals = []
        if isinstance(obj, dict):
            for v in obj.values():
                vals.extend(scalar_values(v))
        elif isinstance(obj, list):
            for v in obj:
                vals.extend(scalar_values(v))
        elif obj is not None and not isinstance(obj, (dict, list)):
            s = str(obj).strip()
            if s:
                vals.append(s)
        return vals

    with open(DATA, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            msgs = r["messages"]
            tools = r.get("tools") or []
            n += 1

            calls = [m for m in msgs if m.get("tool_calls")]
            tmsgs = [m for m in msgs if m.get("role") == "tool"]
            umsgs = [m for m in msgs if m.get("role") == "user"]
            utext = " ".join(str(m.get("content") or "") for m in umsgs)

            for ci, m in enumerate(calls):
                for tc in (m.get("tool_calls") or []):
                    tool_freq[(tc.get("function") or {}).get("name")] += 1

            # Q1: arguments 类型
            if calls:
                a0 = (calls[0]["tool_calls"][0].get("function") or {}).get("arguments")
                arg_types[type(a0).__name__] += 1

            # Q1/Q4: 参数依赖检测
            if len(calls) >= 2:
                args2 = (calls[1]["tool_calls"][0].get("function") or {}).get("arguments")
                if isinstance(args2, str):
                    try:
                        args2 = json.loads(args2)
                    except Exception:
                        args2 = {}
                vals2 = scalar_values(args2)
                t1 = str(tmsgs[0].get("content") or "") if tmsgs else ""
                t2 = str(tmsgs[1].get("content") or "") if len(tmsgs) > 1 else ""
                for v in vals2:
                    dep["total"] += 1
                    if len(v) >= 2 and v in t1:
                        dep["tool1"] += 1
                    elif len(v) >= 2 and v in t2:
                        dep["tool2"] += 1
                    else:
                        dep["nowhere"] += 1
            if calls:
                a1 = (calls[0]["tool_calls"][0].get("function") or {}).get("arguments")
                if isinstance(a1, str):
                    try:
                        a1 = json.loads(a1)
                    except Exception:
                        a1 = {}
                for v in scalar_values(a1):
                    dep1["total"] += 1
                    if len(v) >= 2 and v in utext:
                        dep1["user"] += 1
                    else:
                        dep1["nowhere"] += 1

            # Q3: assistant token 分段
            text = render_full(tok, msgs, tools)
            spans = find_assistant_spans(text)
            enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
            offs = enc["offset_mapping"]
            # assistant 段按顺序对应：前 n-1 是 tool_call 段，最后是总结段
            n_tc_spans = max(0, len(calls))
            for si, (s0, e0) in enumerate(spans):
                c = sum(1 for a, b in offs if a >= s0 and b <= e0 and b > a)
                if si < n_tc_spans:
                    asst_tc += c
                else:
                    asst_final += c

            # Q4: 工具返回长度
            for i, tm in enumerate(tmsgs):
                c = str(tm.get("content") or "")
                tr_chars[f"tr{i+1}"] += len(c)
                tr_tok[f"tr{i+1}"] += len(tok(c, add_special_tokens=False)["input_ids"])

            # Q2: S3 变体 token 对比
            if n <= 40:
                out = []
                for m in msgs:
                    if m.get("role") == "assistant" and not m.get("tool_calls"):
                        break
                    out.append(m)
                t2 = render_full(tok, out, tools)
                s3_probe.append({
                    "orig": len(tok(text, add_special_tokens=False)["input_ids"]),
                    "s3": len(tok(t2, add_special_tokens=False)["input_ids"]),
                    "orig_tail": text[-260:],
                    "s3_tail": t2[-260:],
                })

    rep = {
        "samples": n,
        "arguments_type_dist": dict(arg_types),
        "call2_param_dependency": dep,
        "call1_param_dependency": dep1,
        "assistant_tokens": {
            "tool_call_spans": asst_tc,
            "final_summary_spans": asst_final,
            "tool_call_pct": round(asst_tc / max(1, asst_tc + asst_final) * 100, 2),
        },
        "tool_response_chars": dict(tr_chars),
        "tool_response_tokens": dict(tr_tok),
        "tool_call_freq": dict(tool_freq),
        "s3_probe": s3_probe[:5],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print("深度校验")
    print("=" * 70)
    print(f"样本 {n:,}")
    print("\n--- Q1 arguments 类型 ---")
    print(f"  {rep['arguments_type_dist']}")
    print("\n--- Q1 call#2 参数值来源 ---")
    d = dep
    print(f"  标量总数 {d['total']:,} | 来自 tool_response#1 {d['tool1']:,} "
          f"({d['tool1']/max(1,d['total'])*100:.1f}%) | 来自 #2 {d['tool2']:,} "
          f"({d['tool2']/max(1,d['total'])*100:.1f}%) | 无处可寻 {d['nowhere']:,} "
          f"({d['nowhere']/max(1,d['total'])*100:.1f}%)")
    d1 = dep1
    print(f"--- call#1 参数值来源: 来自 user {d1['user']:,} "
          f"({d1['user']/max(1,d1['total'])*100:.1f}%) | 无处 {d1['nowhere']:,} "
          f"({d1['nowhere']/max(1,d1['total'])*100:.1f}%)")
    print("\n--- Q3 assistant token 分段 ---")
    a = rep["assistant_tokens"]
    print(f"  tool_call 段 {a['tool_call_spans']:,} ({a['tool_call_pct']}%) | "
          f"最终总结段 {a['final_summary_spans']:,} ({100-a['tool_call_pct']:.1f}%)")
    print("\n--- Q4 工具返回 token ---")
    for k, v in sorted(tr_tok.items()):
        print(f"  {k}: {v:,} tok | {tr_chars[k]:,} chars")
    print("\n--- 工具调用频次 ---")
    for k, v in tool_freq.most_common():
        print(f"  {k}: {v:,}")
    print("\n--- Q2 S3 模板副作用（首条对比）---")
    for s in s3_probe[:2]:
        print(f"  orig={s['orig']} s3={s['s3']}  (delta {s['s3']-s['orig']:+d})")
        print(f"    s3_tail: ...{s['s3_tail'][-150:]!r}")
    print(f"\n报告 -> {OUT}")


if __name__ == "__main__":
    main()
