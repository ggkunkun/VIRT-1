#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_segments.py — 精确分段 token 计量 + 缩短策略收益 + 截断安全性验证

三件事：
  1) 精确分段 token 计量（单次 tokenize + offset_mapping 分桶，修正 tools 段定位 bug）
  2) 缩短策略 token 收益模拟（去重 / 截断 tool_response / 丢末尾总结 / 只留首轮）
  3) 【关键】截断安全性：下一个 tool_call 的参数值是否来自上一个 tool_response？
     若"是"，截断 tool_response 就会切断学习信号 -> 不安全
"""
from __future__ import annotations

import json
import os
import sys
import hashlib
import re
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from virtu_tokenize import render_full  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "checkpoints", "_base_qwen3_8b")
DATA = os.path.join(HERE, "damodel_cad_cam_tuning", "dataset",
                    "virtu_toolcall_train_unified.jsonl")
OUT = os.path.join(HERE, "data", "validation", "segment_analysis.json")
IM_START = "<|im_start|>"


def role_segments(text):
    """返回 [(role, char_start, char_end)]，char_end 为下一段起点。"""
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


def norm(msgs):
    out = []
    for m in msgs:
        d = {"r": m.get("role")}
        if m.get("content"):
            d["c"] = " ".join(str(m["content"]).split())
        if m.get("tool_calls"):
            d["t"] = json.dumps(m["tool_calls"], sort_keys=True, ensure_ascii=False)
        if m.get("name"):
            d["n"] = m["name"]
        out.append(json.dumps(d, sort_keys=True, ensure_ascii=False))
    return "\n".join(out)


def scalar_values(obj):
    """从 tool_calls 参数里抽出所有标量值（字符串/数字），做传播检测。"""
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


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    role_tok = Counter()
    role_n = Counter()
    n = 0
    total_tok = 0
    seen = set()
    dup = 0

    # 策略累计（抽样外推）
    STRIDE = 3
    sim_i = 0
    sim = Counter()
    sim_base = 0

    # 截断安全性：参数值是否来自上一个 tool_response
    prop_total = 0
    prop_found = 0
    prop_samples = 0
    # 第一个 tool_response 的长度分布（字符）
    tr1_len = []
    tool_seq_lens = Counter()

    with open(DATA, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            msgs = r["messages"]
            tools = r.get("tools") or []
            text = render_full(tok, msgs, tools)
            n += 1

            # ---- 1) 单次 tokenize + offset 分桶 ----
            enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
            offs = enc["offset_mapping"]
            segs = role_segments(text)
            # 每段 char 范围 -> 找所属段
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
                    role_n[roles[bi]] += 1
            total_tok += len(enc["input_ids"])

            # ---- 2) 去重 ----
            fp = hashlib.md5(norm(msgs).encode()).hexdigest()
            is_dup = fp in seen
            seen.add(fp)
            if is_dup:
                dup += 1

            # ---- 3) 截断安全性检测 ----
            calls = [m for m in msgs if m.get("tool_calls")]
            toolsmsg = [m for m in msgs if m.get("role") == "tool"]
            if len(calls) >= 2 and len(toolsmsg) >= 1:
                prev_tool_text = str(toolsmsg[0].get("content") or "")
                tr1_len.append(len(prev_tool_text))
                v2 = []
                for tc in calls[1].get("tool_calls") or []:
                    v2.extend(scalar_values((tc.get("function") or {}).get("arguments")))
                if v2:
                    prop_samples += 1
                    for v in v2:
                        prop_total += 1
                        if len(v) >= 3 and v in prev_tool_text:
                            prop_found += 1

            # ---- 4) 策略模拟（抽样） ----
            if sim_i % STRIDE == 0:
                sim_i += 1
                sim_base += len(enc["input_ids"])
                # S3: 丢末尾自然语言总结（保留到最后一条 tool_call）
                def build(trunc_tool_chars, drop_final, only_first):
                    out = []
                    nc = 0
                    for m in msgs:
                        rr = m.get("role")
                        if rr == "tool":
                            c = str(m.get("content") or "")
                            if trunc_tool_chars and len(c) > trunc_tool_chars:
                                c = c[:trunc_tool_chars] + "…[截断]"
                            out.append({**m, "content": c})
                        elif rr == "assistant":
                            if only_first and m.get("tool_calls"):
                                nc += 1
                                if nc > 1:
                                    break
                            if drop_final and not m.get("tool_calls"):
                                break
                            out.append(m)
                        else:
                            out.append(m)
                    return out

                v3 = build(0, True, False)
                v4 = build(600, True, False)
                v5 = build(0, False, True)
                sim["S3"] += len(tok(render_full(tok, v3, tools), add_special_tokens=False)["input_ids"])
                sim["S4"] += len(tok(render_full(tok, v4, tools), add_special_tokens=False)["input_ids"])
                sim["S5"] += len(tok(render_full(tok, v5, tools), add_special_tokens=False)["input_ids"])

            if n % 4000 == 0:
                print(f"  {n} ...", flush=True)

    scale = n / max(1, sim_i)
    tr1_len.sort()

    def pct(p):
        return tr1_len[min(len(tr1_len) - 1, int(len(tr1_len) * p))] if tr1_len else 0

    rep = {
        "samples": n,
        "dup_samples": dup,
        "dup_ratio": round(dup / n, 4),
        "baseline_tokens": total_tok,
        "role_token": dict(role_tok),
        "role_token_pct": {k: round(v / total_tok * 100, 2) for k, v in role_tok.items()},
        "role_count": dict(role_n),
        "strategies": {
            "S0_baseline": {"tokens": total_tok, "samples": n},
            "S1_dedup": {"tokens": total_tok - int(dup / n * total_tok),
                         "samples": n - dup},
            "S3_drop_final": {"tokens": int(sim["S3"] * scale), "samples": n},
            "S4_dedup_dropfinal_trunc600": {"tokens": int(sim["S4"] * scale), "samples": n},
            "S5_first_call_only": {"tokens": int(sim["S5"] * scale), "samples": n},
        },
        "propagation": {
            "samples_checked": prop_samples,
            "scalar_values_total": prop_total,
            "found_in_prev_tool_response": prop_found,
            "ratio": round(prop_found / max(1, prop_total), 4),
        },
        "tool_response_1_len_chars": {
            "p50": pct(0.5), "p90": pct(0.9), "p99": pct(0.99), "max": tr1_len[-1] if tr1_len else 0,
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("分段 token 计量 + 缩短策略收益 + 截断安全性")
    print("=" * 70)
    print(f"样本 {n:,} | 基线 1 epoch token {total_tok:,} | 重复 {dup:,} ({dup/n*100:.1f}%)")
    print()
    print("--- 按角色 token 占比（精确）---")
    for k, v in role_tok.most_common():
        print(f"  {k:12s} {v:>12,}  {v/total_tok*100:5.1f}%   (出现 {role_n[k]:,} 次)")
    print()
    print("--- 缩短策略 token 收益 ---")
    b = rep["strategies"]["S0_baseline"]["tokens"]
    for k, s in rep["strategies"].items():
        print(f"  {k:34s} {s['tokens']:>12,}  省 {100*(1-s['tokens']/b):5.1f}%")
    print()
    print("--- 截断安全性：call#2 参数值是否来自 tool_response#1 ---")
    p = rep["propagation"]
    print(f"  样本 {p['samples_checked']:,} | 标量参数 {p['scalar_values_total']:,} | "
          f"来自上轮 tool 返回 {p['found_in_prev_tool_response']:,} ({p['ratio']*100:.1f}%)")
    t = rep["tool_response_1_len_chars"]
    print(f"  tool_response#1 长度(字符) p50={t['p50']} p90={t['p90']} max={t['max']}")
    print(f"\n报告 -> {OUT}")


if __name__ == "__main__":
    main()
