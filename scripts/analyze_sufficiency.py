#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_sufficiency.py — 到底需要多少样本？（样本量学习曲线推演）

背景：
  瘦身语料 18,330 条，但「工具序列+参数键组合」只有 7 种 -> 结构多样性极低
  system 段占 63.5% -> 每条都在重复同一份 tools schema

真正的未知数是：**多少样本够学会？**
这里不做拍脑袋，而是把"信息维度"拆开量化：
  D1 结构维度：工具调用序列 + 参数键集合      -> 只有 7 种，几百条就饱和
  D2 取值维度：material/尺寸 等枚举与数值组合  -> 决定覆盖率需要多少条
  D3 语言维度：user query 的自然语言表述多样性 -> 决定意图->参数的泛化能力

方法：对每条样本抽取「(工具名, 参数键, 参数值集合)」的近似指纹，
     做饱和曲线：随着样本量增加，新增"未见过的模式"还剩多少。
     曲线趋于平坦处 = 边际信息接近 0 = 收益递减点。
"""
from __future__ import annotations

import json
import os
import sys
import random
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLIM = os.path.join(HERE, "data", "toolcall_slim.jsonl")
OUT = os.path.join(HERE, "data", "validation", "sufficiency_analysis.json")


def parse_args_of(msg):
    """返回该 assistant tool_call 的 (name, sorted_keys, 值指纹)。"""
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


def main():
    rng = random.Random(42)
    rows = []
    n = 0
    # 各项单独统计
    struct_c = Counter()        # (工具序列, 参数键)
    mat_c = Counter()           # 材料取值
    dim_c = Counter()           # 尺寸组合(近似到整数)
    user_norm_c = Counter()     # user query 归一化后的多样性
    param_val_fp = Counter()    # 完整参数值指纹

    with open(SLIM, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            msgs = r["messages"]
            n += 1
            calls = []
            for m in msgs:
                if m.get("tool_calls"):
                    nm, keys, args = parse_args_of(m)
                    if nm:
                        calls.append((nm, keys, args))
            struct_c[tuple((c[0], c[1]) for c in calls)] += 1
            # merge 所有调用的参数
            allargs = {}
            for _, _, a in calls:
                allargs.update(a)
            for k, v in allargs.items():
                if k == "material":
                    mat_c[str(v)] += 1
            dims = tuple(sorted(
                f"{k}={round(float(v),1)}" for k, v in allargs.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)))
            if dims:
                dim_c[dims] += 1
            param_val_fp[json.dumps(allargs, sort_keys=True, ensure_ascii=False)] += 1
            users = [str(m.get("content") or "") for m in msgs if m.get("role") == "user"]
            if users:
                # 归一化：去掉数字，保留词序，衡量"表述模式"多样性
                import re
                u = users[0]
                u = re.sub(r"[-+]?\d*\.?\d+", "#", u)
                u = " ".join(u.split())
                user_norm_c[u[:120]] += 1

    print("=" * 72)
    print("样本充分性分析")
    print("=" * 72)
    print(f"瘦身语料样本数: {n:,}")
    print()
    print("--- D1 结构维度（工具序列 × 参数键）---")
    print(f"  不同结构: {len(struct_c)} 种")
    print(f"  最大一类占比: {struct_c.most_common(1)[0][1]/n*100:.1f}%")
    print()
    print("--- D2 取值维度 ---")
    print(f"  material 取值: {len(mat_c)} 种")
    for k, v in mat_c.most_common(10):
        print(f"    {k:<12s} {v:,}")
    print(f"  尺寸/数值组合: {len(dim_c)} 种")
    print(f"  完整参数指纹: {len(param_val_fp)} 种 "
          f"(唯一率 {len(param_val_fp)/n*100:.1f}%)")
    print()
    print("--- D3 语言维度（user 表述模式，数字已掩码）---")
    print(f"  不同表述模式: {len(user_norm_c)} 种")
    for k, v in user_norm_c.most_common(5):
        print(f"    {v:>6,} 条  {k[:70]}")
    print()

    # 饱和曲线：随机顺序累积，看"新模式"增长何时饱和
    print("--- 饱和曲线（随机抽样累积，看新模式何时不再增长）---")
    order = list(range(n))
    rng.shuffle(order)
    # 预抽取每条的模式指纹
    patterns = []
    with open(SLIM, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            allargs = {}
            for m in r["messages"]:
                if m.get("tool_calls"):
                    nm, keys, args = parse_args_of(m)
                    if args:
                        allargs.update(args)
            patterns.append(json.dumps(allargs, sort_keys=True, ensure_ascii=False))

    seen = set()
    marks = [500, 1000, 2000, 3000, 5000, 8000, 12000, 18330]
    curve = []
    mi = 0
    for i, idx in enumerate(order, 1):
        seen.add(patterns[idx])
        if mi < len(marks) and i >= marks[mi]:
            curve.append({"samples": i, "unique_params": len(seen),
                          "coverage_pct": round(len(seen) / len(param_val_fp) * 100, 1)})
            mi += 1
    for c in curve:
        print(f"    {c['samples']:>6,} 条 -> 覆盖不同参数组合 {c['unique_params']:,} "
              f"({c['coverage_pct']}% 的总模式)")

    out = {
        "samples": n,
        "d1_structures": len(struct_c),
        "d2_material_values": len(mat_c),
        "d2_material_dist": dict(mat_c.most_common(30)),
        "d2_dim_combos": len(dim_c),
        "d2_full_param_fingerprints": len(param_val_fp),
        "d2_unique_rate_pct": round(len(param_val_fp) / n * 100, 1),
        "d3_user_phrasings": len(user_norm_c),
        "saturation_curve": curve,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n报告 -> {OUT}")


if __name__ == "__main__":
    main()
