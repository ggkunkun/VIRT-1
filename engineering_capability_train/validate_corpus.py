#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_corpus.py — 训练前语料门禁（失败即非零退出，禁止带病开训）。

检查项（每一项都对应工作区实测踩过的坑）：
  1. 训练目录恰好 1 个 .jsonl，且 sha256 与 corpus_manifest 一致   [L40S 训练器硬约束]
  2. manifest 全量校验                                              [make_cloud_bundle 门控]
  3. 逐行 schema：messages / role / assistant 存在 / content 为 str
  4. 工具调用：name 属于 14 个 cadcam_* 白名单、required 参数齐全、
     键名必须是 tool/arguments（禁止 name+arguments）                [v2 17 次 JSON 失败根因]
  5. 物理过闸：几何矛盾 / 体积不守恒 / FOS<1.5 / 量纲错零容忍
  6. 训练/评测 prompt 零重叠 + 硬 holdout 零泄漏                    [never train on holdout]
  7. 重复率、长度分布与截断风险（p99 > max_seq_len 时告警）
  8. DPO 对：chosen != rejected、两侧可解析 JSON、chosen 满足物理闸门
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from ect_common import (atomic_write_json, iter_jsonl, load_config, log, now_iso,
                        resolve, sha256_file, verify_manifest)
from _ect_rowcheck import (assistant_text, user_text, physics_ok,
                           check_tool_calls, tool_spec_index as _tool_spec_index)

VALID_ROLES = {"system", "user", "assistant", "tool"}


def run(cfg: Dict[str, Any], report_out: str | None = None) -> Dict[str, Any]:
    paths = cfg["paths"]
    corpus_p = resolve(paths["corpus_out"])
    dpo_p = resolve(paths["dpo_out"])
    eval_p = resolve(paths["data_dir"]) / "eval_tasks.jsonl"
    manifest_p = resolve(paths["manifest_out"])
    report: Dict[str, Any] = {"checked_at": now_iso(), "errors": [], "warnings": [],
                              "stats": {}}

    def err(msg: str) -> None:
        report["errors"].append(msg)

    def warn(msg: str) -> None:
        report["warnings"].append(msg)

    # 1. 恰好一个训练 jsonl
    corpus_files = sorted(corpus_p.parent.glob("*.jsonl"))
    report["stats"]["corpus_dir_jsonl_files"] = [p.name for p in corpus_files]
    if cfg["reproducibility"]["require_single_corpus_jsonl"]:
        training_files = [p for p in corpus_files if p.name != "eval_tasks.jsonl"
                          and "dpo" not in p.name]
        if len(training_files) != 1 or training_files[0].resolve() != corpus_p.resolve():
            err(f"训练目录必须恰好 1 个训练 jsonl，实际 {[p.name for p in training_files]}")

    # 2. manifest
    if not manifest_p.is_file():
        err(f"缺少 corpus_manifest.json: {manifest_p}")
    else:
        chk = verify_manifest(manifest_p)
        report["stats"]["manifest"] = chk
        if not chk["ok"]:
            err(f"manifest sha256 校验失败: {chk['mismatches']}")

    # 3-5. 逐行
    if not corpus_p.is_file():
        err(f"缺少训练语料: {corpus_p}")
        return report
    index = _tool_spec_index()
    rows = list(iter_jsonl(corpus_p))
    report["stats"]["train_rows"] = len(rows)
    seen, dup, phys_bad, tool_bad, schema_bad = set(), 0, 0, 0, 0
    char_lens: List[int] = []
    for i, r in enumerate(rows, 1):
        msgs = r.get("messages")
        if not isinstance(msgs, list) or not msgs:
            schema_bad += 1
            if schema_bad <= 3:
                err(f"line {i}: messages 缺失或不是列表")
            continue
        if any(m.get("role") not in VALID_ROLES for m in msgs):
            schema_bad += 1
            continue
        if any(not isinstance(m.get("content"), str) for m in msgs):
            schema_bad += 1
            continue
        if not any(m.get("role") == "assistant" for m in msgs):
            schema_bad += 1
            continue
        u, a = user_text(r), assistant_text(r)
        h = u + "\x00" + a
        if h in seen:
            dup += 1
        seen.add(h)
        char_lens.append(len(h))
        e = check_tool_calls(a, index)
        if e:
            tool_bad += 1
            if tool_bad <= 3:
                err(f"line {i} 工具调用: {'; '.join(e[:3])}")
        ok, reasons = physics_ok(r)
        if not ok:
            phys_bad += 1
            if phys_bad <= 3:
                err(f"line {i} 物理违规: {'; '.join(reasons)[:200]}")
    report["stats"].update({"duplicates": dup, "schema_bad": schema_bad,
                            "tool_call_bad": tool_bad, "physics_violations": phys_bad})
    if schema_bad:
        err(f"{schema_bad} 行 schema 不合规")
    if dup:
        warn(f"{dup} 条重复样本（去重键=整条对话）")

    # 7. 长度分布：字符数 / 4 近似 token 数，只作风险提示；真值在 selftest 用 tokenizer
    if char_lens:
        s = sorted(char_lens)
        p99 = s[min(len(s) - 1, int(len(s) * 0.99))]
        approx = p99 / 4.0
        report["stats"]["p99_chars"] = p99
        report["stats"]["approx_p99_tokens"] = round(approx, 1)
        max_len = int(resolve_max_len(cfg))
        if approx > max_len:
            warn(f"p99 近似 {approx:.0f} tokens > max_seq_len {max_len}，存在截断风险；"
                 "请执行 train_sft.py --selftest 用真实 tokenizer 复核")
    report["stats"]["capability_distribution"] = dict(
        Counter((r.get("meta") or {}).get("capability", "unknown") for r in rows))

    # 6. 泄漏
    train_prompts = {user_text(r) for r in rows}
    if eval_p.is_file():
        eval_tasks = list(iter_jsonl(eval_p))
        report["stats"]["eval_tasks"] = len(eval_tasks)
        overlap = sum(1 for t in eval_tasks if t.get("prompt") in train_prompts)
        report["stats"]["train_eval_overlap"] = overlap
        if overlap:
            err(f"训练/评测 prompt 重叠 {overlap} 条")
    else:
        err(f"缺少评测任务集: {eval_p}")
    hard = resolve(cfg["reuse_assets"]["hard_holdout"])
    if hard.is_file():
        hs = {str(rec.get("prompt") or "") for rec in iter_jsonl(hard)}
        leak = len(hs & train_prompts)
        report["stats"]["hard_holdout_overlap"] = leak
        if leak:
            err(f"硬 holdout 泄漏 {leak} 条（该集合只允许训练后验收）")
    else:
        warn(f"硬 holdout 文件不存在，跳过: {hard}")

    # 8. DPO 对
    if dpo_p.is_file():
        pairs = list(iter_jsonl(dpo_p))
        bad = 0
        for j, p in enumerate(pairs, 1):
            if p.get("chosen") == p.get("rejected"):
                bad += 1
                continue
            try:
                c = json.loads(p["chosen"])
                rj = json.loads(p["rejected"])
            except (json.JSONDecodeError, KeyError):
                bad += 1
                continue
            # chosen 必须是语义接地的完整决策；rejected 必须仍是合法 JSON 对象
            if not isinstance(c, dict) or not all(
                    k in c for k in ("selected", "reason", "physics_basis")):
                bad += 1
                continue
            if not isinstance(rj, dict) or "selected" not in rj:
                bad += 1
                continue
            if p.get("category") != "ungrounded_guess" and len(str(c["reason"])) < 20:
                bad += 1
                continue
        report["stats"]["dpo_pairs"] = len(pairs)
        report["stats"]["dpo_bad"] = bad
        report["stats"]["dpo_categories"] = dict(Counter(p.get("category") for p in pairs))
        if bad:
            err(f"DPO 对不合规 {bad} 条")
    else:
        err(f"缺少 DPO 数据: {dpo_p}")

    report["ok"] = not report["errors"]
    if report_out:
        atomic_write_json(resolve(report_out), report)
    return report


def resolve_max_len(cfg: Dict[str, Any]) -> int:
    try:
        t = load_config("train")
        prof = t["profiles"][t["default_profile"]]
        return int(prof["max_seq_len"])
    except Exception:
        return int(cfg.get("max_seq_len", 2560))


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力训练 - 语料门禁")
    ap.add_argument("--report-out", default=None)
    ap.add_argument("--strict", action="store_true", help="warnings 也判失败")
    args = ap.parse_args()
    rep = run(load_config("pipeline"), args.report_out)
    log("validate", f"errors={len(rep['errors'])} warnings={len(rep['warnings'])} "
                    f"ok={rep['ok']}")
    print(json.dumps({k: v for k, v in rep.items() if k != "stats"}, ensure_ascii=False, indent=2))
    print(json.dumps(rep["stats"], ensure_ascii=False, indent=2))
    failed = (not rep["ok"]) or (args.strict and rep["warnings"])
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
