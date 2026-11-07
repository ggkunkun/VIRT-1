#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_train_cost.py — 训练耗时可压缩空间的实测分析（本机，无需 GPU）

回答三个问题：
  Q1 一次 epoch 到底要算多少 token？各段（tools/schema/user/tool_response/assistant）占多少？
  Q2 23178 条语料的真实信息密度有多高？（去重后能压到多少条）
  Q3 padding 浪费多少？不同 batch size 下真实吞吐损失多少？

输出 JSON 报告 + 文本摘要，供决策"缩短训练时间"的杠杆。
"""
from __future__ import annotations

import json
import os
import sys
import hashlib
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from virtu_tokenize import build_example, render_full, find_assistant_spans  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "checkpoints", "_base_qwen3_8b")
DATA = os.path.join(HERE, "damodel_cad_cam_tuning", "dataset",
                    "virtu_toolcall_train_unified.jsonl")
OUT = os.path.join(HERE, "data", "validation", "train_cost_analysis.json")


def norm_msgs(msgs):
    """把 messages 归一化成可比对的指纹（忽略空白差异）。"""
    norm = []
    for m in msgs:
        d = {"role": m.get("role")}
        if m.get("content"):
            d["c"] = " ".join(str(m["content"]).split())
        if m.get("tool_calls"):
            d["tc"] = json.dumps(m["tool_calls"], sort_keys=True, ensure_ascii=False)
        if m.get("name"):
            d["n"] = m["name"]
        norm.append(json.dumps(d, sort_keys=True, ensure_ascii=False))
    return "\n".join(norm)


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    n = 0
    tok_total = 0
    loss_total = 0
    lens = []
    # 段级 token 统计
    sec_tok = Counter()
    # 指纹去重
    fp_user = Counter()      # 只看 user 段
    fp_full = Counter()      # 全对话
    fp_asst = Counter()      # 只看 assistant 的 tool_calls（真正要学的东西）
    tools_fp = Counter()
    # assistant 段数量分布
    n_asst_dist = Counter()

    with open(DATA, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            msgs = r["messages"]
            tools = r.get("tools") or []

            ids, labels, meta = build_example(msgs, tools, tok, 4096)
            n += 1
            tok_total += meta["n_tok"]
            loss_total += meta["n_loss"]
            lens.append(meta["n_tok"])
            n_asst_dist[meta["n_assistant_spans"]] += 1

            # 段级 token：按渲染文本里的角色段落切
            text = render_full(tok, msgs, tools)
            spans = find_assistant_spans(text)
            asst_chars = sum(e - s for s, e in spans)
            # tools schema 段：出现在 <tools> ... </tools> 之间
            ti = text.find("<tools>")
            tj = text.find("</tools>")
            tools_chars = (tj - ti) if (ti >= 0 and tj > ti) else 0
            total_chars = len(text) or 1
            sec_tok["tools"] += tools_chars / total_chars * meta["n_tok"]
            sec_tok["assistant"] += asst_chars / total_chars * meta["n_tok"]
            sec_tok["other"] += max(
                0, meta["n_tok"] - sec_tok["tools"] / n - sec_tok["assistant"] / n)

            fp_full[hashlib.md5(norm_msgs(msgs).encode()).hexdigest()] += 1
            fp_user[hashlib.md5(norm_msgs(
                [m for m in msgs if m.get("role") == "user"]).encode()).hexdigest()] += 1
            fp_asst[hashlib.md5("\n".join(
                json.dumps(m.get("tool_calls"), sort_keys=True, ensure_ascii=False)
                for m in msgs if m.get("role") == "assistant").encode()).hexdigest()] += 1
            tools_fp[hashlib.md5(json.dumps(tools, sort_keys=True).encode()).hexdigest()] += 1

            if n % 3000 == 0:
                print(f"  scanned {n} ...", flush=True)

    lens.sort()
    def pct(p):
        return lens[min(len(lens) - 1, int(len(lens) * p))]

    # padding 浪费：模拟 batch 内随机取样时的 padding 开销
    import random
    random.seed(42)
    pad_stats = {}
    for bs in (2, 4, 8, 16, 32):
        waste = []
        for _ in range(200):
            grp = [random.choice(lens) for _ in range(bs)]
            waste.append((max(grp) * bs - sum(grp)) / (max(grp) * bs))
        pad_stats[f"batch{bs}"] = round(sum(waste) / len(waste), 4)

    # 排序分组（group_by_length=True）后的 padding
    pad_sorted = {}
    for bs in (2, 4, 8, 16, 32):
        waste = []
        ls = sorted(lens)
        for i in range(0, min(len(ls), 200 * bs), bs):
            grp = ls[i:i + bs]
            if len(grp) < 2:
                continue
            waste.append((max(grp) * len(grp) - sum(grp)) / (max(grp) * len(grp)))
        pad_sorted[f"batch{bs}"] = round(sum(waste) / len(waste), 4)

    rep = {
        "samples": n,
        "tokens_total": tok_total,
        "loss_tokens_total": loss_total,
        "loss_ratio": round(loss_total / tok_total, 4),
        "len_min": lens[0], "len_p50": pct(0.5), "len_p90": pct(0.9),
        "len_p95": pct(0.95), "len_max": lens[-1],
        "len_mean": round(sum(lens) / len(lens), 1),
        "token_segment_estimate": {k: round(v) for k, v in sec_tok.items()},
        "unique_full_dialog": len(fp_full),
        "unique_user_query": len(fp_user),
        "unique_assistant_toolcalls": len(fp_asst),
        "unique_tools_schema": len(tools_fp),
        "dup_ratio_full": round(1 - len(fp_full) / n, 4),
        "dup_ratio_user": round(1 - len(fp_user) / n, 4),
        "dup_ratio_assistant": round(1 - len(fp_asst) / n, 4),
        "assistant_span_dist": dict(sorted(n_asst_dist.items())),
        "padding_waste_random": pad_stats,
        "padding_waste_sorted": pad_sorted,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 68)
    print("训练成本实测分析")
    print("=" * 68)
    print(f"样本数            : {rep['samples']:,}")
    print(f"总 token (1 ep)   : {tok_total:,}")
    print(f"计 loss token     : {loss_total:,} ({rep['loss_ratio']*100:.1f}%)")
    print(f"序列长度 p50/p90/max: {rep['len_p50']}/{rep['len_p90']}/{rep['len_max']}")
    print()
    print("--- 段级 token 占比（估算）---")
    seg = sec_tok
    tt = sum(seg.values())
    for k, v in seg.most_common():
        print(f"  {k:12s} {v/tt*100:5.1f}%  ({v:,.0f} tok)")
    print()
    print("--- 冗余度（去重潜力）---")
    print(f"  全对话唯一        : {rep['unique_full_dialog']:,} "
          f"(重复率 {rep['dup_ratio_full']*100:.1f}%)")
    print(f"  user query 唯一   : {rep['unique_user_query']:,} "
          f"(重复率 {rep['dup_ratio_user']*100:.1f}%)")
    print(f"  assistant toolcalls 唯一: {rep['unique_assistant_toolcalls']:,} "
          f"(重复率 {rep['dup_ratio_assistant']*100:.1f}%)")
    print(f"  tools schema 唯一 : {rep['unique_tools_schema']:,}")
    print()
    print("--- assistant 段数分布 ---")
    for k, v in sorted(n_asst_dist.items()):
        print(f"  {k} 个 assistant 段: {v:,} 条")
    print()
    print("--- padding 浪费率 ---")
    print("  随机分组:", rep["padding_waste_random"])
    print("  长度排序:", rep["padding_waste_sorted"])
    print()
    print(f"报告 -> {OUT}")


if __name__ == "__main__":
    main()
