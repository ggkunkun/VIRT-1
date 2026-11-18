#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""训练集模板重平衡（只写入新文件，绝不改动原数据）。

依据 2026-11-08 同源污染审计：data/sft 共 31994 条带 prompt 样本，
模板簇只有 1193 个，近重复溢出 30801 条（96.27%）。最大的单一模板占
1457 条，同一题面只换数字。模型在这种分布上学到的是"模板 → 答案"的
填空捷径，不是物理推理，且训练算力大量重复消耗。

本脚本按模板簇做分层上限采样：
  - 每个模板簇最多保留 --cap 条（默认 12）
  - 簇内优先保留信息更完整的样本（assistant 回复更长、带 scenario 标注）
  - 每簇至少保留 1 条，保证模板覆盖不丢

输出到新文件（默认 output/wm_rebalanced.jsonl），原 data/sft 一个字节都不动。
是否替换训练集由使用者决定。

用法：
  .venv/Scripts/python.exe scripts/wm_rebalance_train.py --cap 12 --out <新文件>
  .venv/Scripts/python.exe scripts/wm_rebalance_train.py --dry-run    # 只看统计不落盘
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from virtu_eval.contamination_check import (
    DEFAULT_EVAL,
    assert_no_leak,
    check_sample,
    load_eval_cases,
)
from scripts.corpus_unit_audit import assert_units_clean

NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# 已被 .units_fixed.clean.jsonl / .clean.jsonl 取代的原始污染文件，以及非 SFT 的负样本库
SUPERSEDED_FILES = {
    "virtu_evolution_v5.jsonl",
    "virtu_evolution_v5.clean.jsonl",
    "virtu_evolution_v5.units_fixed.jsonl",
    "virtu_final_train.jsonl",
    "virtu_final_train.units_fixed.jsonl",
    "dpo_phys_rejects.jsonl",
    "dpo_phys_rejects.units_fixed.jsonl",
}


def template_of(text: str) -> str:
    t = NUM_RE.sub("#", str(text or ""))
    return re.sub(r"[，,。；;：:、\s]+", "", t)


def _msg_text(msgs) -> tuple[str, str]:
    u = a = ""
    for m in msgs or []:
        if not isinstance(m, dict):
            continue
        role, c = m.get("role"), m.get("content")
        if not isinstance(c, str):
            continue
        if role == "user" and not u:
            u = c
        elif role == "assistant" and not a:
            a = c
    return u, a


def user_prompt(rec) -> str:
    """兼容 data/sft 里实际存在的 5 种 schema。

    2026-11-08 实测：33135 条样本里只有 31994 条是 messages 格式，另有
    prompt / instruction+input / prompt_messages / family+inputs / DPO 等
    格式共 1141 条。旧版只认 messages，这些样本会全部落到空模板簇里被
    合并成 cap 条，等于静默丢数据（首版实测丢 1129 条）。这里逐格式兜底。
    """
    if not isinstance(rec, dict):
        return ""
    for key in ("messages", "prompt_messages"):
        u, _ = _msg_text(rec.get(key))
        if u:
            return u
    p = rec.get("prompt")
    if isinstance(p, str) and p.strip():
        return p
    ins = rec.get("instruction")
    if isinstance(ins, str) and ins.strip():
        extra = rec.get("input")
        return ins + ("\n" + extra if isinstance(extra, str) else "")
    # 纯结构化样本（family/inputs/outputs）：用输入的键值骨架作为模板，
    # 数字在 template_of 里脱敏，同 task 同类形状的样本自然归簇。
    if isinstance(rec.get("inputs"), dict):
        return rec.get("family", "") + "|" + json.dumps(rec["inputs"], ensure_ascii=False, sort_keys=True)
    return ""


def assistant_text(rec) -> str:
    if not isinstance(rec, dict):
        return ""
    for key in ("messages", "prompt_messages"):
        _, a = _msg_text(rec.get(key))
        if a:
            return a
    for key in ("chosen", "output", "outputs"):
        v = rec.get(key)
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return json.dumps(v, ensure_ascii=False)
    return ""


def quality_key(rec):
    """簇内排序：信息越完整越优先。"""
    score = 0.0
    score += min(len(assistant_text(rec)), 4000) / 1000.0   # 回复完备度
    if isinstance(rec.get("scenario"), dict):
        score += 2.0                                        # 带结构化标注
    if isinstance(rec.get("meta"), dict) and rec["meta"]:
        score += 1.0
    return score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sft-dir", default=os.path.join(ROOT, "data", "sft"))
    ap.add_argument("--cap", type=int, default=12, help="每个模板簇保留上限")
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "wm_rebalanced.jsonl"))
    ap.add_argument("--eval-dir", default=DEFAULT_EVAL)
    ap.add_argument("--include-superseded", action="store_true",
                    help="默认跳过已被 .clean.jsonl / .units_fixed.clean.jsonl 取代的原始污染文件")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    all_files = sorted(glob.glob(os.path.join(args.sft_dir, "*.jsonl")))
    files = [
        fp for fp in all_files
        if args.include_superseded or os.path.basename(fp) not in SUPERSEDED_FILES
    ]
    eval_cases = load_eval_cases(args.eval_dir)
    buckets = defaultdict(list)
    total = 0
    leaked_skipped = 0
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                total += 1
                reasons = check_sample(rec, eval_cases, jaccard_th=0.6, ignore_gold_numeric=True)
                if any(not r.startswith("gold_num=") for r in reasons):
                    leaked_skipped += 1
                    continue
                u = user_prompt(rec)
                tmpl = template_of(u) if u.strip() else f"__noprompt__{total}"
                buckets[tmpl].append((fp, rec))

    kept, dropped = [], 0
    for tmpl, items in buckets.items():
        items.sort(key=lambda x: quality_key(x[1]), reverse=True)
        keep = items[:max(1, args.cap)]
        kept.extend(keep)
        dropped += len(items) - len(keep)

    print("=" * 68)
    print("训练集模板重平衡（只写新文件）")
    print("=" * 68)
    print(f"输入：{len(files)} 文件（跳过已替代污染文件 {len(all_files) - len(files)} 个）/ {total} 条")
    print(f"评测集防泄漏过滤：剔除硬泄漏 {leaked_skipped} 条")
    print(f"模板簇：{len(buckets)} 个，簇内上限 {args.cap}")
    print(f"保留：{len(kept)} 条，剔除近重复 {dropped} 条"
          f"（{dropped / total * 100 if total else 0:.2f}%）")
    per = defaultdict(int)
    for fp, _ in kept:
        per[os.path.basename(fp)] += 1
    print("保留量按文件：")
    for fn, c in sorted(per.items(), key=lambda x: -x[1]):
        print(f"  {c:>5}  {fn}")

    if args.dry_run:
        print("\n[dry-run] 未落盘")
        return 0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for _, rec in kept:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    assert_no_leak(args.out, args.eval_dir)
    assert_units_clean(args.out)
    print(f"\n[OK] 新语料 -> {args.out}  ({os.path.getsize(args.out) / 1e6:.1f} MB)")
    print("     原 data/sft 未做任何修改；替换需人工确认后另行操作。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
