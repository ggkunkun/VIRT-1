#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""训练前语料预检（fail-closed）：花 40 分钟 GPU 之前，先把会白跑的坑挡掉。

检查项：
  1. 结构：每行 messages ≥2、末条必须是 assistant 且有内容、system 存在；
  2. 长度：用真实 tokenizer 编码，给出 p50/p95/max；p99 > max_length 或「无监督 token」比例过高直接失败；
  3. 几何/语法毒样本：任何「像 G71 程序」的样本必须通过 g71_semantic_check 语义门，否则失败
     （v7 的教训：55 条 G71 样本仅 8 条语义正确，训练后门禁 10/10 但 G 代码不可用）；
  4. 家族分布：统计 meta.family；关键家族（Lamé / Auto-Diff / SW 坐标 / G71）缺失或占比 <1% 告警，
     任一非关键家族占比 <0.5% 也告警（v8 的教训：某家族被压到 2.4% 就会翻车）；
  5. 重复：完全相同的 assistant 文本占比过高告警。

用法：
  python preflight_corpus.py --data six_software_v9_repair_sft.jsonl --base <模型目录或HF id> \
      --max-length 640 --report preflight.json
退出码：0 通过（含告警）；2 结构/长度失败；3 毒样本失败。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CRITICAL = ("lame", "autodiff", "sw_plane", "g71")
CODE_LINE = __import__("re").compile(r"^\s*(?:N\d+\s*)?(?:G\d+|M\d+|T\d+|S\d+|F\d|X-?\d|Z-?\d|%)")


def load_rows(p: Path) -> tuple[list[dict], list[str], int]:
    rows, errs, no_sys = [], [], 0
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            errs.append(f"line {i}: JSON 解析失败 {e}")
            continue
        m = r.get("messages") or []
        if len(m) < 2:
            errs.append(f"line {i}: messages<2")
            continue
        if m[0].get("role") != "system":
            no_sys += 1   # 多轮样本/开场即 user 属合法，仅统计
        if m[-1].get("role") != "assistant" or not (m[-1].get("content") or "").strip():
            errs.append(f"line {i}: 末条不是非空 assistant")
            continue
        rows.append(r)
    return rows, errs, no_sys


def looks_like_program(text: str) -> bool:
    return sum(1 for ln in (text or "").splitlines() if CODE_LINE.search(ln)) >= 5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--base", default="", help="tokenizer 来源；不给则跳过长度检查")
    ap.add_argument("--max-length", type=int, default=640)
    ap.add_argument("--report", default="")
    ap.add_argument("--min-rows", type=int, default=200)
    args = ap.parse_args()

    data = Path(args.data)
    if not data.exists():
        print(f"[FATAL] 语料不存在: {data}", file=sys.stderr)
        return 2
    sha = hashlib.sha256(data.read_bytes()).hexdigest()
    rows, errs, no_sys = load_rows(data)
    print(f"[Preflight] file={data.name} rows={len(rows)} sha={sha[:16]}")

    fatal: list[str] = []
    warn: list[str] = []
    info: dict = {"rows": len(rows), "sha256": sha, "max_length": args.max_length}

    if errs:
        fatal.extend(errs[:10])
        print(f"[FAIL] 结构错误 {len(errs)} 条，示例：{errs[:3]}")
    if no_sys:
        print(f"[Preflight] {no_sys} 条样本首条不是 system（多轮/直接提问，允许）")
    if len(rows) < args.min_rows:
        warn.append(f"样本量偏小（{len(rows)} < {args.min_rows}）")

    # ---- 2. 长度 / 监督 token ----
    if args.base:
        try:
            from transformers import AutoTokenizer
            sys.path.insert(0, str(HERE))
            from train_qlora import encode  # 复用同一编码函数，保证与训练一致

            import os
            base_arg = str(Path(args.base).resolve()) if os.path.isdir(args.base) else args.base
            if os.path.isdir(args.base) and not (Path(base_arg) / "tokenizer_config.json").exists():
                warn.append(f"{args.base} 缺 tokenizer_config.json，长度检查跳过")
                raise FileNotFoundError("no tokenizer_config.json")
            tok = AutoTokenizer.from_pretrained(base_arg, trust_remote_code=True)
            if tok.pad_token is None:
                tok.pad_token = tok.eos_token
            lens, no_sup = [], 0
            for r in rows:
                e = encode(tok, r["messages"], args.max_length)
                if e is None:
                    no_sup += 1
                else:
                    lens.append(len(e["input_ids"]))
            if lens:
                lens_sorted = sorted(lens)
                p50 = statistics.median(lens_sorted)
                p95 = lens_sorted[int(len(lens_sorted) * 0.95) - 1]
                info.update(tok_p50=p50, tok_p95=p95, tok_max=max(lens_sorted))
                print(f"[Preflight] tokens p50={p50} p95={p95} max={max(lens_sorted)} "
                      f"| 无监督token样本={no_sup}")
            ratio = no_sup / max(len(rows), 1)
            if ratio > 0.05:
                fatal.append(f"无监督 token 样本占比 {ratio:.1%} > 5%（max_length 太小或语料格式错）")
            elif no_sup:
                warn.append(f"{no_sup} 条样本在 max_length={args.max_length} 下无 assistant token（会被跳过）")
        except Exception as e:  # noqa: BLE001
            warn.append(f"长度检查跳过（tokenizer 不可用: {type(e).__name__}: {e}）")

    # ---- 3. G71 语义毒样本 ----
    try:
        from g71_semantic_check import check_g71_step_shaft
        bad = []
        n_prog = 0
        for i, r in enumerate(rows):
            a = r["messages"][-1].get("content") or ""
            if "G71" not in a or not looks_like_program(a):
                continue
            n_prog += 1
            res = check_g71_step_shaft(a)
            if not res["passed"]:
                bad.append((i, res["violations"]))
        info["g71_program_rows"] = n_prog
        info["g71_poison_rows"] = len(bad)
        print(f"[Preflight] G71 程序样本={n_prog} 语义不合格={len(bad)}")
        if bad:
            fatal.append(f"{len(bad)} 条 G71 程序语义不合格（示例 index={bad[0][0]} {bad[0][1][:3]}）")
        elif n_prog == 0:
            warn.append("语料中没有 G71 程序样本（若被测 G71 探针，几乎必然失败）")
    except ImportError:
        warn.append("未找到 g71_semantic_check.py，跳过语义门")

    # ---- 4. 家族分布 ----
    fam = Counter(str(r.get("meta", {}).get("family") or "?") for r in rows)
    info["families"] = dict(fam.most_common(15))
    total = max(len(rows), 1)
    for key in CRITICAL:
        hit = sum(c for f, c in fam.items() if key in f.lower())
        if hit == 0:
            warn.append(f"关键家族缺失: {key}")
        elif hit / total < 0.01:
            warn.append(f"关键家族占比过低: {key} = {hit}/{total} ({hit/total:.1%})")
    thin = [f"{f}={c} ({c/total:.1%})" for f, c in fam.items() if c / total < 0.005 and f != "?"]
    if thin:
        warn.append("占比 <0.5% 的家族: " + ", ".join(thin[:5]))

    # ---- 5. 重复 ----
    dup = Counter((r["messages"][-1].get("content") or "")[:200] for r in rows)
    top_dup, top_n = dup.most_common(1)[0]
    info["dup_top_ratio"] = round(top_n / total, 3)
    if top_n / total > 0.2:
        warn.append(f"最高重复样本占比 {top_n/total:.0%}（前 200 字相同）")

    # ---- 结论 ----
    info.update(fatal=fatal, warnings=warn, verdict="FAIL" if fatal else "PASS")
    print("\n[结论] " + ("FAIL" if fatal else "PASS"))
    for x in fatal:
        print("  ✗", x)
    for x in warn:
        print("  !", x)

    if args.report:
        Path(args.report).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Preflight] report → {args.report}")

    if fatal:
        return 3 if any("G71" in x for x in fatal) else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
