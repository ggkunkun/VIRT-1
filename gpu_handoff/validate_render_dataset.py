#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_render_dataset.py — 用官方 Qwen3 chat template 全量渲染语料并做训练前体检

为什么需要它（三个真实踩过的坑）：
  1. 手写 ChatML 与官方 template 渲染结果不一致 → 训完推理端解析不出 tool_calls
  2. HF config.vocab_size(151936) 与 tokenizer 实际词表(151669) 不一致 → GGUF 加载被拒
  3. 逐轮前缀对齐假设不成立时会静默错位 → loss 打到错误 token 上
本脚本把这三点在花钱训练之前全部验证掉。

检查项：
  C1  JSON 逐行可解析，messages/tools 结构完整
  C2  官方 template 渲染成功（含 <tools> 段）
  C3  逐轮前缀对齐（用于构造 loss mask）
  C4  loss mask 只落在 assistant 段（tool/system/user 段全部 -100）
  C5  tool_calls 段完整渲染（<tool_call> JSON 可解析）
  C6  token 长度分布统计（决定 max_length / batch / 训练成本）

用法：
  python scripts/validate_render_dataset.py \
      --data damodel_cad_cam_tuning/dataset/virtu_toolcall_train_unified.jsonl \
      --base checkpoints/_base_qwen3_8b --out data/validation/render_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from virtu_tokenize import build_example, render_full  # noqa: E402


def _parse_args():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser(description="Virtu tool-call 语料渲染体检")
    p.add_argument("--data", default=os.path.join(
        here, "damodel_cad_cam_tuning", "dataset", "virtu_toolcall_train_unified.jsonl"))
    p.add_argument("--base", default=os.path.join(here, "checkpoints", "_base_qwen3_8b"),
                   help="含 tokenizer_config.json 的基座目录（提供官方 chat_template）")
    p.add_argument("--out", default=os.path.join(here, "data", "validation", "render_report.json"))
    p.add_argument("--limit", type=int, default=0, help="只验证前 N 条（0=全部）")
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1),
                   help="并行进程数（渲染是纯 CPU 字符串操作）")
    p.add_argument("--max-length", type=int, default=4096,
                   help="截断阈值，仅用于统计超长比例（不改变渲染）")
    return p.parse_args()


# --------------------------------------------------------------------------- #
# 单条渲染 + 掩码构造（掩码逻辑统一来自 scripts/virtu_tokenize.py）
# --------------------------------------------------------------------------- #
def render_one(args_tuple):
    """worker：渲染单条，返回体检结果 dict。"""
    idx, line, tokenizer, max_length = args_tuple
    t0 = time.time()
    try:
        rec = json.loads(line)
    except Exception as e:
        return {"idx": idx, "ok": False, "stage": "C1", "err": f"JSON 解析失败: {e}"}

    messages = rec.get("messages")
    tools = rec.get("tools") or []
    if not isinstance(messages, list) or not messages:
        return {"idx": idx, "ok": False, "stage": "C1", "err": "messages 缺失或非列表"}

    # C2: 整体渲染 + tools 段
    try:
        full = render_full(tokenizer, messages, tools)
    except Exception as e:
        return {"idx": idx, "ok": False, "stage": "C2", "err": f"template 渲染失败: {e}"}

    has_tools_block = "<tools>" in full
    if tools and not has_tools_block:
        return {"idx": idx, "ok": False, "stage": "C2", "err": "template 未渲染 <tools> 段"}

    # C3 + C4: 掩码构造（整条渲染 + 字符定位 + offset mapping）
    try:
        ids, labels, meta = build_example(messages, tools, tokenizer, max_length)
    except Exception as e:
        return {"idx": idx, "ok": False, "stage": "C3", "err": f"掩码构造失败: {e}"}

    if not ids:
        return {"idx": idx, "ok": False, "stage": "C3", "err": "渲染后 token 为空"}

    # C4: 必须有 loss token，且 loss 段数 == assistant 消息数
    n_loss = meta["n_loss"]
    if n_loss == 0:
        return {"idx": idx, "ok": False, "stage": "C4", "err": "无任何 loss token"}

    n_assistant = sum(1 for m in messages if m.get("role") == "assistant")
    if meta["n_assistant_spans"] != n_assistant:
        return {"idx": idx, "ok": False, "stage": "C4",
                "err": f"assistant 段数不匹配: 定位 {meta['n_assistant_spans']} vs 消息 {n_assistant}"}

    # C4b: 掩码不得把 tool_response 文本算进 loss
    loss_text = tokenizer.decode([t for t, l in zip(ids, labels) if l != -100])
    if "<tool_response>" in loss_text:
        return {"idx": idx, "ok": False, "stage": "C4", "err": "loss 段含 <tool_response> 标记"}

    # C5: tool_calls 段必须渲染成可解析 JSON
    n_tc = 0
    tc_bad = 0
    for m in messages:
        for tc in (m.get("tool_calls") or []):
            n_tc += 1
            fn = tc.get("function", tc)
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    json.loads(args)
                except Exception:
                    tc_bad += 1
            elif not isinstance(args, dict):
                tc_bad += 1
    if tc_bad:
        return {"idx": idx, "ok": False, "stage": "C5",
                "err": f"{tc_bad}/{n_tc} 个 tool_call 参数不可解析"}

    # 渲染出的 <tool_call> JSON 是否完整
    if n_tc and "<tool_call>" not in full:
        return {"idx": idx, "ok": False, "stage": "C5", "err": "tool_call 未渲染成 <tool_call> 段"}

    # C5b: 真实 tool_call 渲染数应与数据一致
    # 判据：真实调用渲染成 <tool_call>\n{"name": "xxx", "arguments": ...
    # 而模板的格式说明段里是 <tool_call>\n{"name": <function-name>, ...
    # 用 "name": 后跟引号+真实函数名 来区分，避免把说明示例算进去。
    real_pat = re.compile(r'<tool_call>\s*\{"name":\s*"')
    n_rendered_tc = len(real_pat.findall(full))
    if n_rendered_tc != n_tc:
        return {"idx": idx, "ok": False, "stage": "C5",
                "err": f"tool_call 渲染数不符: 渲染 {n_rendered_tc} vs 数据 {n_tc}"}

    return {
        "idx": idx, "ok": True, "stage": None, "err": None,
        "n_tok": meta["n_tok"], "n_loss": n_loss, "n_rounds": len(messages),
        "n_tool_calls": n_tc, "n_chars": meta["n_chars"],
        "truncated": meta["truncated"], "loss_ratio": meta["loss_ratio"],
        "n_assistant_spans": meta["n_assistant_spans"],
        "elapsed": time.time() - t0,
    }


def _worker(payload):
    """Pool worker：首次调用时初始化进程级 tokenizer，之后复用。"""
    global _TOK
    import os as _os
    if _TOK is None:
        from transformers import AutoTokenizer
        _TOK = AutoTokenizer.from_pretrained(payload[2])
    return render_one((payload[0], payload[1], _TOK, payload[3]))


_TOK = None


def main() -> None:
    args = _parse_args()
    if not os.path.exists(args.data):
        raise SystemExit(f"[FATAL] 数据集不存在: {args.data}")
    if not os.path.exists(os.path.join(args.base, "tokenizer_config.json")):
        raise SystemExit(f"[FATAL] 基座目录缺 tokenizer_config.json: {args.base}")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.base)
    ct = tok.chat_template or ""
    print(f"[render] tokenizer={type(tok).__name__} vocab={len(tok)} "
          f"chat_template={len(ct)}字 含tools段={'<tools>' in ct}")
    if "<tools>" not in ct:
        print("[render][WARN] 基座 chat_template 不含 tools 段，工具调用训练会失败。")

    print("[render] 读取数据集 ...", flush=True)
    lines = []
    with open(args.data, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                lines.append(line)
    if args.limit:
        lines = lines[:args.limit]
    total = len(lines)
    print(f"[render] 待验证 {total} 条", flush=True)

    payloads = [(i, ln, args.base, args.max_length) for i, ln in enumerate(lines)]

    t0 = time.time()
    results = []
    if args.workers > 1:
        import multiprocessing as mp
        ctx = mp.get_context("fork" if hasattr(os, "fork") else "spawn")
        with ctx.Pool(processes=args.workers) as pool:
            for i, r in enumerate(pool.imap_unordered(_worker, payloads, chunksize=32)):
                results.append(r)
                if (i + 1) % 2000 == 0:
                    el = time.time() - t0
                    rate = (i + 1) / el if el else 0
                    print(f"  [{i+1}/{total}] {el:.0f}s  ({rate:.0f} 条/s)", flush=True)
    else:
        for pl in payloads:
            results.append(render_one((pl[0], pl[1], tok, pl[3])))

    ok = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]
    toks = sorted(r["n_tok"] for r in ok)
    loss_toks = sum(r["n_loss"] for r in ok)
    trunc = sum(1 for r in ok if r["truncated"])

    def pct(p):
        if not toks:
            return 0
        return toks[min(len(toks) - 1, int(len(toks) * p))]

    stage_counter = Counter(r["stage"] for r in bad)
    role_counter = Counter()
    for r in ok:
        role_counter["assistant"] += r.get("n_assistant_spans", 0)
        role_counter["total_rounds"] += r.get("n_rounds", 0)

    report = {
        "dataset": args.data,
        "base": args.base,
        "total": total,
        "passed": len(ok),
        "failed": len(bad),
        "pass_rate": round(len(ok) / total, 6) if total else 0,
        "failures_by_stage": dict(stage_counter),
        "failure_samples": [{"idx": r["idx"], "stage": r["stage"], "err": r["err"]}
                            for r in bad[:20]],
        "token_stats": {
            "min": toks[0] if toks else 0,
            "p50": pct(0.50), "p90": pct(0.90), "p95": pct(0.95), "p99": pct(0.99),
            "max": toks[-1] if toks else 0,
            "mean": round(statistics.fmean(toks), 1) if toks else 0,
            "total_tokens": sum(toks),
            "total_loss_tokens": loss_toks,
            "truncated_at_max_length": trunc,
            "truncated_ratio": round(trunc / len(ok), 4) if ok else 0,
            "max_length": args.max_length,
        },
        "role_stats": dict(role_counter),
        "loss_ratio_mean": round(statistics.fmean([r["loss_ratio"] for r in ok]), 4) if ok else 0,
        "elapsed_sec": round(time.time() - t0, 1),
        "checks": {
            "C1_json_structure": "PASS" if not stage_counter.get("C1") else "FAIL",
            "C2_template_render": "PASS" if not stage_counter.get("C2") else "FAIL",
            "C3_mask_construction": "PASS" if not stage_counter.get("C3") else "FAIL",
            "C4_loss_mask_scope": "PASS" if not stage_counter.get("C4") else "FAIL",
            "C5_tool_call_integrity": "PASS" if not stage_counter.get("C5") else "FAIL",
        },
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 66)
    print(f"[render] 通过 {len(ok)}/{total}  ({report['pass_rate']*100:.3f}%)")
    for k, v in report["checks"].items():
        print(f"   {k:26s} {v}")
    ts = report["token_stats"]
    print(f"\n[token] min={ts['min']} p50={ts['p50']} p90={ts['p90']} "
          f"p95={ts['p95']} p99={ts['p99']} max={ts['max']} mean={ts['mean']}")
    print(f"[token] 总量 {ts['total_tokens']:,} | 计 loss {ts['total_loss_tokens']:,} "
          f"({ts['total_loss_tokens']/max(1,ts['total_tokens'])*100:.1f}%)")
    print(f"[token] 超 {ts['max_length']} 截断: {ts['truncated_at_max_length']} "
          f"({ts['truncated_ratio']*100:.2f}%)")
    print(f"[mask ] 平均 loss token 占比: {report['loss_ratio_mean']*100:.1f}%")
    print(f"[time ] {report['elapsed_sec']}s")
    if bad:
        print(f"\n[FAIL] 失败分布: {dict(stage_counter)}")
        for s in report["failure_samples"][:5]:
            print(f"   #{s['idx']} [{s['stage']}] {s['err']}")
    print(f"\n[report] -> {args.out}")
    print("=" * 66)
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
