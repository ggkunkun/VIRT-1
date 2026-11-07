#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Virtu v3 hardened text-SFT corpus (plan §3 / §7.1).

v3 = A（已封板文本主桶，5,991 行，逐行保留）
   + B（virtu_capability_sft_v6 中 meta.stage=S3 的 797 行边界桶）
   + C（prepare_v100_targeted_corpus.py 生成器输出，按 prompt 去重后 224 条唯一）
   + D（正常请求负例，补到负例占比 ≥ --min-negative-ratio）

去重口径（双向）：
  * 桶内：C 生成器存在 81% 的 ×30/×40 复制，必须按 prompt 归一化哈希去重；
  * 跨桶：B/C/D 不得与已收语料（含 A）出现相同 prompt；
  * A 与 B 是冻结资产，逐行保留其原有重复（manifest 中如实记账，不静默改写）。

输出：<out>/virtu_v3_text_sft.jsonl + <out>/../manifest.json（含 sha256、分桶、
token 估算、去重/负例统计、来源清单）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tokenizers import Tokenizer  # noqa: E402
from virtu_eval.contamination_check import check_sample, load_eval_cases  # noqa: E402

OUT_NAME = "virtu_v3_text_sft.jsonl"
TOKENIZER_PATH = ROOT / "checkpoints" / "_base_qwen3_8b" / "tokenizer.json"
EVAL_DIR = ROOT / "data" / "benchmark" / "virtu_eval_v1"
MAX_LEN = 2048
SEED = 20261101

CATEGORIES = ("formula_calc", "six_software", "knowledge", "boundary", "chat")

# A 桶 _source → §3.3 类别
A_SOURCE_CATEGORY = {
    "formula_n": "formula_calc",
    "formula_vf": "formula_calc",
    "formula_mrr": "formula_calc",
    "formula_t": "formula_calc",
    "formula_refusal": "boundary",
    "master_six": "six_software",
    "wish_parametric": "six_software",
    "comprehensive": "six_software",
    "drawing_chain": "six_software",
    "knowledge": "knowledge",
    "reasoning_multi_step": "knowledge",
    "reasoning_tolerance": "knowledge",
    "reasoning_taylor": "knowledge",
    "reasoning_cycle_time": "knowledge",
    "reasoning_roughness": "knowledge",
    "turing_chat": "chat",
}

# B 桶“正常请求负例”判据：assistant 不含任何拒绝/缺参话术
REFUSAL_MARKERS = (
    "无法", "不能", "拒绝", "不会", "不存在", "不属于", "并非",
    "请补充", "未提供", "严禁", "禁止", "不得", "不提供", "我没法",
    "不可",
)

C_GENERATORS = (
    ("boundary_missing_params", "gen_boundary_missing_params", "boundary"),
    ("boundary_safety_violations", "gen_boundary_safety_violations", "boundary"),
    ("boundary_geometric_conflicts", "gen_boundary_geometric_conflicts", "boundary"),
    ("boundary_jailbreak_defense", "gen_boundary_jailbreak_defense", "boundary"),
    ("hard_knowledge_formulas", "gen_hard_knowledge_formulas", "formula_calc"),
    ("hard_knowledge_standards", "gen_hard_knowledge_standards", "knowledge"),
)


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

def norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", t).strip().lower()


def prompt_key(text: str) -> str:
    return hashlib.sha256(norm_text(text).encode("utf-8")).hexdigest()


def row_key(rec: dict) -> str:
    parts = [f"{m.get('role', '')}|{m.get('content') or ''}" for m in rec.get("messages", [])]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def chat_text(system: str, user: str, assistant: str) -> tuple[str, str]:
    prompt = (f"<|im_start|>system\n{system}<|im_end|>\n"
              f"<|im_start|>user\n{user}<|im_end|>\n"
              f"<|im_start|>assistant\n")
    return prompt, prompt + assistant + "<|im_end|>"


def extract_messages(item: dict):
    """Return (system, user, assistant) or None (same contract as the trainer)."""
    msgs = item.get("messages")
    if isinstance(msgs, list) and msgs:
        system = next((m.get("content") for m in msgs
                       if m.get("role") == "system" and isinstance(m.get("content"), str)), "")
        user = next((m.get("content") for m in msgs
                     if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        assistant = next((m.get("content") for m in msgs
                          if m.get("role") == "assistant"
                          and isinstance(m.get("content"), str)
                          and m.get("content").strip()), "")
        if not user.strip() or not assistant.strip():
            return None
        return system.strip(), user.strip(), assistant.strip()
    if item.get("instruction"):
        user = item.get("instruction", "")
        if item.get("input"):
            user += "\n【输入参数与背景】: " + item["input"]
        assistant = item.get("output", "")
        if not user.strip() or not assistant.strip():
            return None
        return "", user.strip(), assistant.strip()
    return None


def make_record(system, user, assistant, *, bucket, category, source,
                negative=False, stage=None, extra=None):
    meta = {"bucket": bucket, "category": category, "source": source}
    if negative:
        meta["negative"] = True
    if stage:
        meta["stage"] = stage
    rec = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "meta": meta,
    }
    for k, v in (extra or {}).items():
        rec[k] = v
    return rec


def iter_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def is_refusal(assistant: str) -> bool:
    return any(marker in assistant for marker in REFUSAL_MARKERS)


# ---------------------------------------------------------------------------
# A / B loaders
# ---------------------------------------------------------------------------

def load_fix_bucket(path: Path, eval_cases, stats: dict) -> list[dict]:
    rows, dropped = [], Counter()
    seen_keys = set()
    for item in iter_jsonl(path):
        triplet = extract_messages(item)
        if triplet is None:
            dropped["malformed"] += 1
            continue
        system, user, assistant = triplet
        src = item.get("_source") or "unknown"
        category = A_SOURCE_CATEGORY.get(src)
        if category is None:
            dropped["unknown_source"] += 1
            category = "uncategorized"
        if check_sample(item, eval_cases, ignore_gold_numeric=True):
            dropped["eval_overlap"] += 1
            continue
        key = row_key(item)
        if key in seen_keys:
            dropped["duplicate_rows"] += 1
        seen_keys.add(key)
        rows.append(make_record(system, user, assistant, bucket="A",
                                category=category, source=src,
                                extra={"_source": src}))
    stats.update({"rows_used": len(rows), **{f"dropped_{k}": v for k, v in dropped.items()}})
    return rows


def load_boundary_bucket(path: Path, eval_cases, stats: dict, forbidden: set[str]) -> list[dict]:
    rows, dropped = [], Counter()
    seen_keys = set()
    for item in iter_jsonl(path):
        if item.get("meta", {}).get("stage") != "S3":
            dropped["not_s3"] += 1
            continue
        triplet = extract_messages(item)
        if triplet is None:
            dropped["malformed"] += 1
            continue
        system, user, assistant = triplet
        key = prompt_key(user)
        if key in forbidden:
            dropped["cross_bucket_duplicate"] += 1
            continue
        if check_sample(item, eval_cases, ignore_gold_numeric=True):
            dropped["eval_overlap"] += 1
            continue
        if row_key(item) in seen_keys:
            dropped["duplicate_rows"] += 1
        seen_keys.add(row_key(item))
        negative = not is_refusal(assistant)
        rows.append(make_record(system, user, assistant, bucket="B",
                                category="boundary", source="capability_sft_s3",
                                negative=negative, stage="S3"))
    stats.update({"rows_used": len(rows),
                  "negatives": sum(1 for r in rows if r["meta"].get("negative")),
                  **{f"dropped_{k}": v for k, v in dropped.items()}})
    return rows


# ---------------------------------------------------------------------------
# C loader (import the generator, then dedupe its ×30/×40 repeats)
# ---------------------------------------------------------------------------

def load_targeted_bucket(path: Path, eval_cases, stats: dict, forbidden: set[str]) -> list[dict]:
    spec = importlib.util.spec_from_file_location("_virtu_targeted_corpus", str(path))
    if spec is None or spec.loader is None:
        raise SystemExit(f"[FATAL] cannot import targeted generator: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    generated = []
    for source, fn_name, category in C_GENERATORS:
        fn = getattr(mod, fn_name, None)
        if fn is None:
            raise SystemExit(f"[FATAL] {path} has no {fn_name}()")
        generated.extend((category, source, item) for item in fn())

    rows, dropped = [], Counter()
    seen = set()
    by_source = Counter()
    for category, source, item in generated:
        triplet = extract_messages(item)
        if triplet is None:
            dropped["malformed"] += 1
            continue
        system, user, assistant = triplet
        key = prompt_key(user)
        if key in seen:
            dropped["duplicate_prompts"] += 1
            continue
        seen.add(key)
        if key in forbidden:
            dropped["cross_bucket_duplicate"] += 1
            continue
        if check_sample(item, eval_cases, ignore_gold_numeric=True):
            dropped["eval_overlap"] += 1
            continue
        by_source[source] += 1
        rows.append(make_record(system, user, assistant, bucket="C",
                                category=category, source=source))
    stats.update({"generated_rows": len(generated), "rows_used": len(rows),
                  "unique_prompts": len(seen), "by_generator": dict(by_source),
                  **{f"dropped_{k}": v for k, v in dropped.items()}})
    return rows


# ---------------------------------------------------------------------------
# D negatives (templates from scripts/build_capability_sft.py)
# ---------------------------------------------------------------------------

def load_negative_patch(need: int, seen_all: set[str], eval_cases, stats: dict) -> list[dict]:
    if need <= 0:
        stats.update({"required": 0, "rows_used": 0})
        return []
    gen_path = ROOT / "scripts" / "build_capability_sft.py"
    spec = importlib.util.spec_from_file_location("_virtu_capability_sft", str(gen_path))
    if spec is None or spec.loader is None:
        raise SystemExit(f"[FATAL] cannot import negative templates: {gen_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rng = random.Random(SEED)
    rows, used_pool, dropped = [], 0, Counter()
    attempts = 0
    while len(rows) < need and attempts < 6:
        attempts += 1
        pool = (
            mod.gen_reasoning(rng, need * 2)
            + mod.gen_knowledge(rng, min(60, need))
            + mod.gen_instruction(rng, min(60, need))
        )
        used_pool += len(pool)
        for item in pool:
            if len(rows) >= need:
                break
            triplet = extract_messages(item)
            if triplet is None:
                dropped["malformed"] += 1
                continue
            system, user, assistant = triplet
            if is_refusal(assistant):
                dropped["refusal_answer"] += 1
                continue
            key = prompt_key(user)
            if key in seen_all:
                dropped["prompt_duplicate"] += 1
                continue
            if check_sample(item, eval_cases, ignore_gold_numeric=True):
                dropped["eval_overlap"] += 1
                continue
            seen_all.add(key)
            rows.append(make_record(system, user, assistant, bucket="D",
                                    category="boundary", source="negative_patch",
                                    negative=True, stage="S3"))
    if len(rows) < need:
        raise SystemExit(f"[FATAL] negative pool exhausted: got {len(rows)} / {need}")
    stats.update({"required": need, "pool_generated": used_pool, "rows_used": len(rows),
                  **{f"dropped_{k}": v for k, v in dropped.items()}})
    return rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def token_stats(rows: list[dict], tokenizer: Tokenizer) -> dict:
    full_total = capped_total = prompt_total = answer_total = truncated = 0
    lengths = []
    for rec in rows:
        system, user, assistant = extract_messages(rec)
        prompt, full = chat_text(system, user, assistant)
        p_ids = tokenizer.encode(prompt, add_special_tokens=False).ids
        f_ids = tokenizer.encode(full, add_special_tokens=False).ids
        a_ids = tokenizer.encode(assistant, add_special_tokens=False).ids
        capped = min(len(f_ids), MAX_LEN)
        if len(f_ids) > MAX_LEN:
            truncated += 1
        prompt_total += len(p_ids)
        answer_total += len(a_ids)
        full_total += len(f_ids)
        capped_total += capped
        lengths.append(len(f_ids))
    lengths.sort()

    def pct(q: float) -> int:
        if not lengths:
            return 0
        return lengths[min(len(lengths) - 1, int(round(q * (len(lengths) - 1))))]

    return {
        "full_total": full_total,
        "capped_total": capped_total,
        "prompt_total": prompt_total,
        "answer_total": answer_total,
        "p50": pct(0.50),
        "p90": pct(0.90),
        "p99": pct(0.99),
        "max": lengths[-1] if lengths else 0,
        "truncated": truncated,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build the Virtu v3 hardened SFT corpus")
    p.add_argument("--fix", required=True, help="A bucket jsonl (virtu_fix_text_sft_v1)")
    p.add_argument("--boundary", required=True, help="B bucket jsonl (virtu_capability_sft_v6)")
    p.add_argument("--targeted", required=True, help="C bucket generator .py")
    p.add_argument("--out", required=True, help="output train dir, e.g. data/train/virtu_v3/train")
    p.add_argument("--min-negative-ratio", type=float, default=0.30)
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args(argv)

    fix_path = Path(args.fix).resolve()
    bnd_path = Path(args.boundary).resolve()
    tgt_path = Path(args.targeted).resolve()
    for path in (fix_path, bnd_path, tgt_path, TOKENIZER_PATH):
        if not path.exists():
            raise SystemExit(f"[FATAL] missing input: {path}")
    if not 0 < args.min_negative_ratio < 1:
        raise SystemExit("[FATAL] --min-negative-ratio must be in (0, 1)")

    out_dir = Path(args.out).resolve()
    manifest_dir = out_dir.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    eval_cases = load_eval_cases(str(EVAL_DIR))
    sources: dict[str, dict] = {}

    a_stats: dict = {}
    a_rows = load_fix_bucket(fix_path, eval_cases, a_stats)
    sources["A_fix"] = {"path": str(fix_path.relative_to(ROOT)), "sha256": sha256_file(fix_path),
                        "rows": len(a_rows), **a_stats}
    print(f"[A] rows={len(a_rows)} duplicate_rows={a_stats.get('dropped_duplicate_rows', 0)}",
          flush=True)

    b_stats: dict = {}
    keys_a = {prompt_key(r["messages"][1]["content"]) for r in a_rows}
    b_rows = load_boundary_bucket(bnd_path, eval_cases, b_stats, forbidden=keys_a)
    sources["B_boundary"] = {"path": str(bnd_path.relative_to(ROOT)), "sha256": sha256_file(bnd_path),
                             "rows": len(b_rows), **b_stats}
    print(f"[B] rows={len(b_rows)} negatives={b_stats.get('negatives', 0)}", flush=True)

    c_stats: dict = {}
    keys_b = {prompt_key(r["messages"][1]["content"]) for r in b_rows}
    c_rows = load_targeted_bucket(tgt_path, eval_cases, c_stats, forbidden=keys_a | keys_b)
    sources["C_targeted"] = {"path": str(tgt_path.relative_to(ROOT)), "sha256": sha256_file(tgt_path),
                             "rows": len(c_rows), **c_stats}
    print(f"[C] generated={c_stats.get('generated_rows', 0)} unique={len(c_rows)} "
          f"duplicates={c_stats.get('dropped_duplicate_prompts', 0)}", flush=True)

    # 负例补足：B 桶现有 neg 占 B 的比例不足时，按
    #   total_neg / (B_total + total_neg) >= ratio 求解所需总量
    n_b = len(b_rows)
    neg_b = b_stats.get("negatives", 0)
    required_total_neg = math.ceil(args.min_negative_ratio * n_b / (1 - args.min_negative_ratio))
    need_d = max(0, required_total_neg - neg_b)

    seen_all = {prompt_key(r["messages"][1]["content"]) for r in a_rows}
    seen_b = {prompt_key(r["messages"][1]["content"]) for r in b_rows}
    seen_all |= seen_b
    seen_c = {prompt_key(r["messages"][1]["content"]) for r in c_rows}
    seen_all |= seen_c

    d_stats: dict = {}
    d_rows = load_negative_patch(need_d, seen_all, eval_cases, d_stats)
    sources["D_negatives"] = {"path": "scripts/build_capability_sft.py",
                              "rows": len(d_rows), **d_stats}
    print(f"[D] rows={len(d_rows)} (required_total_neg={required_total_neg}, B_neg={neg_b})",
          flush=True)

    rows = a_rows + b_rows + c_rows + d_rows
    random.Random(args.seed).shuffle(rows)

    # ---- gates ----
    total = len(rows)
    cats = Counter(r["meta"]["category"] for r in rows)
    uncategorized = cats.get("uncategorized", 0)
    if uncategorized:
        raise SystemExit(f"[FATAL] {uncategorized} A rows have an unmapped _source")
    if not all(r["messages"][0]["content"] and r["messages"][1]["content"]
               and r["messages"][2]["content"] for r in rows):
        raise SystemExit("[FATAL] empty system/user/assistant content in output")

    c_boundary = sum(1 for r in c_rows if r["meta"]["category"] == "boundary")
    neg_final = neg_b + len(d_rows)
    boundary_bucket = n_b + c_boundary + len(d_rows)
    ratio = neg_final / boundary_bucket if boundary_bucket else 0.0
    if ratio < args.min_negative_ratio:
        raise SystemExit(f"[FATAL] negative ratio {ratio:.3f} < {args.min_negative_ratio}")

    dup_a = len(a_rows) - len({row_key(r) for r in a_rows})
    dup_b = len(b_rows) - len({row_key(r) for r in b_rows})
    cross_dup = (b_stats.get("dropped_cross_bucket_duplicate", 0)
                 + c_stats.get("dropped_cross_bucket_duplicate", 0))
    if cross_dup:
        print(f"[note] dropped {cross_dup} cross-bucket duplicate prompts", flush=True)
    if dup_a or dup_b:
        print(f"[note] inherited duplicate rows: A={dup_a} B={dup_b} "
              f"(frozen inputs kept verbatim; see manifest.dedupe)", flush=True)

    # ---- write ----
    out_jsonl = out_dir / OUT_NAME
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    digest = sha256_file(out_jsonl)

    tok = token_stats(rows, Tokenizer.from_file(str(TOKENIZER_PATH)))

    manifest = {
        "version": "virtu_v3_text_sft",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": args.seed,
        "format": "ShareGPT messages; train_virtu.py / train_virtu_v100.py compatible",
        "toolcall_strategy": "excluded (E bucket stays in the virtu-toolcall channel)",
        "max_len": MAX_LEN,
        "total": total,
        "rows": {"A": len(a_rows), "B": len(b_rows), "C": len(c_rows), "D": len(d_rows)},
        "categories": {c: cats.get(c, 0) for c in CATEGORIES},
        "boundary": {
            "B_rows": n_b,
            "B_negatives": neg_b,
            "C_boundary_rows": c_boundary,
            "D_negative_patch": len(d_rows),
            "A_missing_param_refusals": sum(1 for r in a_rows
                                            if r["meta"]["source"] == "formula_refusal"),
            "negative_ratio_in_B_C_D": round(ratio, 4),
            "negative_ratio_requirement": args.min_negative_ratio,
            "required_total_negatives": required_total_neg,
        },
        "dedupe": {
            "key": "sha256(NFKC + whitespace-collapsed + lowercase user prompt)",
            "policy": "frozen A/B kept verbatim; C/D deduped internally; "
                      "cross-bucket prompt collisions dropped",
            "C_generated_rows": c_stats.get("generated_rows", 0),
            "C_unique_prompts": len(c_rows),
            "C_dropped_duplicate_prompts": c_stats.get("dropped_duplicate_prompts", 0),
            "C_import_policy": "只调用 6 个纯生成函数；main() 的 ×6/×30/×40/×2/×10 复制"
                               "（1,188 行）不执行，964 条重复从未进入语料",
            "inherited_duplicate_rows": {"A": dup_a, "B": dup_b},
            "B_prompt_overlap_with_A": cross_dup,
        },
        "eval_filter": {
            "eval_dir": str(EVAL_DIR.relative_to(ROOT)),
            "eval_cases": len(eval_cases),
            "gate": "prompt hash + 8-gram jaccard>=0.6 (gold numeric collisions ignored)",
            "dropped": {k: v.get("dropped_eval_overlap", 0) for k, v in sources.items()},
        },
        "tokens": tok,
        "sources": sources,
        "sha256": digest,
        "dataset_sha256": digest,
        "next_gate": "python virtu_eval/contamination_check.py <out.jsonl> --eval-dir "
                     "data/benchmark/virtu_eval_v1 --ignore-gold-numeric",
    }
    body = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (manifest_dir / "manifest.json").write_text(body, encoding="utf-8")
    # train_virtu_v100.py 在 preflight 里按旧文件名查找 sha 闸，写一份同名兼容副本
    (manifest_dir / "virtu_fix_text_sft_v1.manifest.json").write_text(body, encoding="utf-8")

    print(json.dumps({
        "out": str(out_jsonl),
        "total": total,
        "rows": manifest["rows"],
        "categories": manifest["categories"],
        "negative_ratio_in_B_C_D": manifest["boundary"]["negative_ratio_in_B_C_D"],
        "tokens_per_epoch": tok["capped_total"],
        "sha256": digest,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
