#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""训练集同源污染审计（只读）。

背景：2026-11-08 审计发现评测抽样 240 条里有 21 条（8.75%）与 data/sft 训练集
prompt 逐字重合，模型只是在背题，指标被系统性高估。eval_worldmodel 已改为默认
排除逐字重合用例（FIX H9），但那只挡住"完全一样"，挡不住"换个数字的同一模板"
——这类近重复同样会让模型学到"模板 → 答案"的捷径。

本脚本做三件事，全程只读，不修改任何训练数据：
  1. 逐字重合：训练集 prompt 与评测集 prompt 的精确交集
  2. 模板重合并：把 prompt 里的数字脱敏为 # 后比对，统计每个模板的样本数
  3. 建议：输出需要加固的模板簇清单，供数据侧改写/去重

用法：
  .venv/Scripts/python.exe scripts/wm_leak_audit.py
  .venv/Scripts/python.exe scripts/wm_leak_audit.py --json out.jsonl   # 明细落盘
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)

NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def template_of(text: str) -> str:
    """数字脱敏 + 空白归一，用于识别"同一模板换数字"。"""
    t = NUM_RE.sub("#", str(text or ""))
    t = re.sub(r"[，,。；;：:、\s]+", "", t)
    return t


def load_jsonl(path: str):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return out


def user_prompt(rec) -> str:
    msgs = rec.get("messages") or []
    for m in msgs:
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sft-dir", default=os.path.join(ROOT, "data", "sft"))
    ap.add_argument("--eval-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--top", type=int, default=15, help="输出前 N 个高频模板簇")
    ap.add_argument("--json", default="", help="明细落盘路径（可选）")
    args = ap.parse_args()

    # ---- 训练集
    sft_files = sorted(glob.glob(os.path.join(args.sft_dir, "*.jsonl")))
    train_prompts = set()
    train_tmpl = Counter()
    train_tmpl_files = defaultdict(set)
    train_total = 0
    for fp in sft_files:
        for rec in load_jsonl(fp):
            u = user_prompt(rec)
            if not u:
                continue
            train_total += 1
            train_prompts.add(u)
            tp = template_of(u)
            train_tmpl[tp] += 1
            train_tmpl_files[tp].add(os.path.basename(fp))

    # ---- 评测集（data 下、非 sft 的 jsonl，视为评测/参考数据）
    eval_files = [f for f in glob.glob(os.path.join(args.eval_dir, "**", "*.jsonl"), recursive=True)
                  if os.sep + "sft" + os.sep not in f]
    eval_total = exact_leak = tmpl_leak = 0
    leak_examples = []
    for fp in eval_files:
        for rec in load_jsonl(fp):
            u = user_prompt(rec)
            if not u:
                continue
            eval_total += 1
            if u in train_prompts:
                exact_leak += 1
                if len(leak_examples) < 5:
                    leak_examples.append((os.path.basename(fp), u[:70]))
            elif template_of(u) in train_tmpl:
                tmpl_leak += 1

    # ---- 训练集内部近重复
    dup_pairs = sum(c - 1 for c in train_tmpl.values() if c > 1)
    top = train_tmpl.most_common(args.top)

    print("=" * 72)
    print("训练集同源污染审计（只读）")
    print("=" * 72)
    print(f"训练集：{len(sft_files)} 个文件 / {train_total} 条带 prompt 样本 / "
          f"去重后 {len(train_prompts)} 条唯一 prompt")
    print(f"        模板簇 {len(train_tmpl)} 个，近重复溢出 {dup_pairs} 条"
          f"（{dup_pairs / train_total * 100 if train_total else 0:.2f}%）")
    print(f"评测集：{eval_total} 条")
    if eval_total:
        print(f"        逐字重合 {exact_leak} 条（{exact_leak / eval_total * 100:.2f}%）"
              "  ← FIX H9 默认已过滤")
        print(f"        模板级重合 {tmpl_leak} 条（{tmpl_leak / eval_total * 100:.2f}%）"
              "  ← 默认过滤挡不住，需数据侧加固")
    print()
    print(f"训练集内近重复 Top{args.top}（同一模板仅数字不同的样本数）：")
    for tp, c in top:
        files = ",".join(sorted(train_tmpl_files[tp]))[:44]
        print(f"  {c:>4} 条  {tp[:56]:<56}  [{files}]")
    if leak_examples:
        print("\n逐字重合样例：")
        for fn, u in leak_examples:
            print(f"  [{fn}] {u}")

    if args.json:
        rows = [{"template": tp, "count": c, "files": sorted(train_tmpl_files[tp])}
                for tp, c in top]
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\n[OK] 模板簇明细 -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
