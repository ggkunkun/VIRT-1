#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/build_wm_cloud_fix_corpus.py — 构建世界工程模型（World Engineering Model）云端修复训练语料与溯源账本

本脚本把所有世界工程模型修复项（物理定律真值、几何可行域拒绝负体积与螺栓孔干涉、
闸门枚举 pass/fail 契约归一、多轮错误草稿轮 loss:false 掩码、量纲 mm^4 修复、
评测集 0 硬泄漏去污）固化为统一的 ChatML messages 云端训练语料：
  - 输出语料: cloud_train_pack/dataset/virtu_worldmodel_fix_sft.jsonl
  - 输出账本: cloud_train_pack/dataset/virtu_worldmodel_fix_sft_ledger.json

执行门禁（Fail-Closed）：
  1. 全部样本转换为标准 messages 列表，且末轮必为有效 assistant（loss != False）；
  2. 遗留门禁字面量（FOS>=1.5_pass / FOS<1.5_FAIL / pass_cut_negative / true / false）计数必为 0；
  3. 物理量纲审计 corpus_unit_audit.assert_units_clean 必为 0 bad_rows；
  4. 评测防泄漏门禁 virtu_eval.contamination_check.assert_no_leak 针对三大评测集
     （virtu_eval_v1 / virtu_eval_phys_v1 / virtu_eval_cl_v1）硬泄漏必为 0。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.corpus_unit_audit import assert_units_clean, scan as scan_units  # noqa: E402
from scripts.train_world_model_final import (  # noqa: E402
    normalize_item_messages,
)
from virtu_eval.contamination_check import (  # noqa: E402
    assert_no_leak,
    check_sample,
    load_eval_cases,
)

LEGACY_GATE_TOKENS = ("FOS>=1.5_pass", "FOS<1.5_FAIL", "pass_cut_negative")

DEFAULT_SOURCE = os.path.join(
    ROOT, "data", "sft_rebalanced", "wm_train_cap12_v2.unitfix.clean.jsonl"
)
# 深根因修复语料：420 条多轮「逆设计修复」轨迹（坏解必判红→改参数不改嘴→修正解过闸），
# 专治「宣称与产物参数解耦」。不并入则重训只修尺子族，capstone 近失缺口仍在。
DEFAULT_REPAIRLOOP = os.path.join(
    ROOT, "cloud_train_pack", "dataset", "virtu_impeller_repairloop_sft.jsonl"
)
# 世界模型专用修复轨迹（2026-11-12 实测失败生成）：坏解 loss=False → 校验器反馈
# → 修正解。专治「算式不执行 / 字段不回填 / 闸门与数值矛盾」，与叶轮 repairloop 互补。
DEFAULT_WM_REPAIRLOOP = os.path.join(
    ROOT, "cloud_train_pack", "dataset", "virtu_wm_repairloop_sft.jsonl"
)
DEFAULT_OUT = os.path.join(
    ROOT, "cloud_train_pack", "dataset", "virtu_worldmodel_fix_sft.jsonl"
)
DEFAULT_LEDGER = os.path.join(
    ROOT, "cloud_train_pack", "dataset", "virtu_worldmodel_fix_sft_ledger.json"
)
BENCHMARK_DIRS = [
    os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1"),
    os.path.join(ROOT, "data", "benchmark", "virtu_eval_phys_v1"),
    os.path.join(ROOT, "data", "benchmark", "virtu_eval_cl_v1"),
]
LEGACY_RE = re.compile(
    r'"(?:' + "|".join(re.escape(t) for t in sorted(LEGACY_GATE_TOKENS)) + r')"'
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def build_corpus(
    source_path: str = DEFAULT_SOURCE,
    out_path: str = DEFAULT_OUT,
    ledger_path: str = DEFAULT_LEDGER,
    seed: int = 20261110,
    repairloop_path: str | None = DEFAULT_REPAIRLOOP,
    wm_repairloop_path: str | None = DEFAULT_WM_REPAIRLOOP,
) -> dict:
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"未找到源语料: {source_path}")
    if repairloop_path and not os.path.exists(repairloop_path):
        raise FileNotFoundError(
            f"未找到 repairloop 修复语料: {repairloop_path}。"
            "它是「改参数不改嘴」深根因的唯一训练靶，缺失时拒绝静默降级；"
            "确要排除请显式传 repairloop_path=None。"
        )
    if wm_repairloop_path and not os.path.exists(wm_repairloop_path):
        raise FileNotFoundError(
            f"未找到世界模型 repairloop 语料: {wm_repairloop_path}。"
            "缺失时拒绝静默降级；确要排除请显式传 wm_repairloop_path=None。"
        )

    # 预加载三大评测集用于全方位硬泄漏拦截
    all_eval_cases = []
    eval_suite_counts = {}
    for bdir in BENCHMARK_DIRS:
        if os.path.isdir(bdir):
            cases = load_eval_cases(bdir)
            eval_suite_counts[os.path.basename(bdir)] = len(cases)
            all_eval_cases.extend(cases)

    raw_rows = 0
    kept_records = []
    skipped_empty = 0
    skipped_hard_leak = 0
    masked_bad_turns = 0
    family_counter = Counter()
    seen_payloads = set()
    dup_skipped = 0
    repairloop_kept = 0
    wm_repairloop_kept = 0

    def ingest(path: str, family_override: str | None = None) -> None:
        nonlocal raw_rows, skipped_empty, skipped_hard_leak, masked_bad_turns
        nonlocal dup_skipped, repairloop_kept, wm_repairloop_kept
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw_rows += 1
                raw_item = json.loads(line)
                msgs = normalize_item_messages(raw_item)
                if not msgs:
                    skipped_empty += 1
                    continue

                # 确保末轮是可学习的 assistant 轮
                while msgs and msgs[-1].get("role") != "assistant":
                    msgs.pop()
                asst_turns = [m for m in msgs if m.get("role") == "assistant"]
                if not asst_turns or all(m.get("loss") is False for m in asst_turns):
                    skipped_empty += 1
                    continue

                fam = (
                    family_override
                    or raw_item.get("family")
                    or (raw_item.get("scenario") or {}).get("task")
                    or raw_item.get("category")
                    or raw_item.get("source")
                    or "general_sft"
                )
                norm_rec = {
                    "messages": msgs,
                    "family": str(fam),
                }
                if isinstance(raw_item.get("scenario"), dict):
                    norm_rec["scenario"] = raw_item["scenario"]
                if isinstance(raw_item.get("inputs"), dict):
                    norm_rec["inputs"] = raw_item["inputs"]
                if isinstance(raw_item.get("meta"), dict):
                    norm_rec["meta"] = raw_item["meta"]
                if isinstance(raw_item.get("tools"), list) and raw_item["tools"]:
                    norm_rec["tools"] = raw_item["tools"]
                if raw_item.get("last_assistant_only") is True:
                    norm_rec["last_assistant_only"] = True

                # 跨源确定性去重（repairloop 与主源可能重叠）；
                # last_assistant_only 改变 loss 掩码，必须进键，否则会误删不同训练语义的样本
                payload = json.dumps(
                    [msgs, bool(raw_item.get("last_assistant_only"))],
                    ensure_ascii=False, sort_keys=True,
                )
                ph = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                if ph in seen_payloads:
                    dup_skipped += 1
                    continue
                seen_payloads.add(ph)

                # 对归一化后的 messages 再做一次三大评测集硬泄漏复核
                reasons = check_sample(
                    norm_rec, all_eval_cases, jaccard_th=0.6, ignore_gold_numeric=True
                )
                if any(not r.startswith("gold_num=") for r in reasons):
                    skipped_hard_leak += 1
                    continue

                for m in asst_turns:
                    if m.get("loss") is False:
                        masked_bad_turns += 1

                family_counter[str(fam)] += 1
                kept_records.append(norm_rec)
                if family_override == "impeller_repairloop":
                    repairloop_kept += 1
                elif family_override == "wm_repairloop":
                    wm_repairloop_kept += 1

    ingest(source_path)
    if repairloop_path:
        ingest(repairloop_path, family_override="impeller_repairloop")
    if wm_repairloop_path:
        ingest(wm_repairloop_path, family_override="wm_repairloop")
    if repairloop_path and repairloop_kept == 0:
        raise RuntimeError(
            "[FATAL] repairloop 语料 0 条入集（全部被去重/泄漏/空轮吞掉）。"
            "深根因修复靶丢失，拒绝产出看似正常的语料。"
        )
    if wm_repairloop_path and wm_repairloop_kept == 0:
        raise RuntimeError(
            "[FATAL] 世界模型 repairloop 0 条入集。"
            "「算式不执行/字段不回填」修复靶丢失，拒绝产出看似正常的语料。"
        )

    rng = random.Random(seed)
    rng.shuffle(kept_records)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    legacy_hits = 0
    with open(out_path, "w", encoding="utf-8", newline="\n") as out_f:
        for rec in kept_records:
            s = json.dumps(rec, ensure_ascii=False)
            if LEGACY_RE.search(s):
                legacy_hits += 1
            out_f.write(s + "\n")

    if legacy_hits > 0:
        raise RuntimeError(
            f"[FATAL] 输出语料仍含 {legacy_hits} 条未归一化的旧版门禁字面量！"
        )

    # 门禁 1：三大评测集防泄漏校验
    leak_reports = {}
    for bdir in BENCHMARK_DIRS:
        if os.path.isdir(bdir):
            res = assert_no_leak(out_path, eval_dir=bdir)
            leak_reports[os.path.basename(bdir)] = {
                "hard_leaks": res["hard_leaks"],
                "numeric_proxy_only": res["numeric_proxy_only"],
            }

    # 门禁 2：物理量纲一致性校验
    assert_units_clean(out_path)
    unit_res = scan_units(out_path)

    source_sha = sha256_file(source_path)
    out_sha = sha256_file(out_path)
    ledger = {
        "schema_version": "virtu_wm_cloud_fix_corpus.v2",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured",
        "seed": seed,
        "source_path": os.path.relpath(source_path, ROOT).replace("\\", "/"),
        "source_sha256": source_sha,
        "repairloop_path": (
            os.path.relpath(repairloop_path, ROOT).replace("\\", "/")
            if repairloop_path else None
        ),
        "repairloop_sha256": sha256_file(repairloop_path) if repairloop_path else None,
        "repairloop_kept_rows": repairloop_kept,
        "wm_repairloop_path": (
            os.path.relpath(wm_repairloop_path, ROOT).replace("\\", "/")
            if wm_repairloop_path else None
        ),
        "wm_repairloop_sha256": sha256_file(wm_repairloop_path) if wm_repairloop_path else None,
        "wm_repairloop_kept_rows": wm_repairloop_kept,
        "dup_skipped": dup_skipped,
        "output_path": os.path.relpath(out_path, ROOT).replace("\\", "/"),
        "output_sha256": out_sha,
        "output_size_bytes": os.path.getsize(out_path),
        "raw_rows": raw_rows,
        "kept_rows": len(kept_records),
        "skipped_empty": skipped_empty,
        "skipped_hard_leak": skipped_hard_leak,
        "masked_bad_assistant_turns": masked_bad_turns,
        "legacy_gate_literals_remaining": legacy_hits,
        "unit_audit": {
            "rows": unit_res["rows"],
            "bad_rows": unit_res["bad_rows"],
        },
        "contamination_audit": leak_reports,
        "eval_suite_case_counts": eval_suite_counts,
        "family_distribution": dict(family_counter.most_common()),
    }
    with open(ledger_path, "w", encoding="utf-8", newline="\n") as lf:
        json.dump(ledger, lf, ensure_ascii=False, indent=2)

    print("=" * 72)
    print("[WM-Cloud-Corpus] 世界工程模型云端修复语料构建完成")
    print(f"  源文件     : {ledger['source_path']} (sha256={source_sha[:16]}...)")
    print(f"  输出语料   : {ledger['output_path']} ({len(kept_records)} 行, {os.path.getsize(out_path)/1e6:.2f} MB)")
    print(f"  输出指纹   : {out_sha}")
    print(f"  坏轮掩码数 : {masked_bad_turns} 轮 (loss=False)")
    print(f"  遗留旧门禁 : {legacy_hits}")
    print(f"  量纲坏行数 : {unit_res['bad_rows']}")
    print(f"  硬泄漏剔除 : {skipped_hard_leak} 行 (三大评测集复核 hard_leaks=0)")
    print(f"  repairloop : {repairloop_kept} 行入集 (跨源去重剔除 {dup_skipped} 行)")
    print(f"  wm repair  : {wm_repairloop_kept} 行入集")
    print(f"  账本路径   : {os.path.relpath(ledger_path, ROOT)}")
    print("=" * 72)
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description="构建世界工程模型云端修复训练语料")
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--repairloop", default=DEFAULT_REPAIRLOOP,
                    help="逆设计修复轨迹语料路径（深根因靶）")
    ap.add_argument("--no-repairloop", action="store_true",
                    help="显式排除 repairloop（仅限对照实验，默认禁止）")
    ap.add_argument("--wm-repairloop", default=DEFAULT_WM_REPAIRLOOP,
                    help="世界模型修复轨迹语料路径")
    ap.add_argument("--no-wm-repairloop", action="store_true",
                    help="显式排除世界模型 repairloop（仅限对照实验）")
    args = ap.parse_args()
    build_corpus(args.source, args.out, args.ledger, args.seed,
                 repairloop_path=None if args.no_repairloop else args.repairloop,
                 wm_repairloop_path=None if args.no_wm_repairloop else args.wm_repairloop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
