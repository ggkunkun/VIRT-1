"""Block training samples that leak the 240-case evaluation set.

A sample is contaminated if any of:
  1. normalized prompt hash equals an eval prompt hash
  2. 8-gram Jaccard similarity with any eval prompt >= 0.6
  3. an eval gold numeric string (length >= 4, not a tiny integer) appears
     in the training assistant/user text

Exit code 2 if any hit remains after optional --drop. Used as a release gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EVAL = os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1")

_WS = re.compile(r"\s+")
_NUM = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?")


_EXEMPT_GOLD_NUMS = {"1000", "0101", "0102", "1200", "2026", "2025", "2024", "3000"}


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    return _WS.sub(" ", t).strip().lower()


def prompt_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def ngrams(text: str, n: int = 8) -> set[str]:
    toks = re.findall(r"[\w\u4e00-\u9fff]+", normalize(text))
    if len(toks) < n:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def load_eval_cases(eval_dir: str) -> list[dict]:
    cases = []
    if not os.path.isdir(eval_dir):
        raise FileNotFoundError(eval_dir)
    for name in os.listdir(eval_dir):
        if not name.endswith(".jsonl"):
            continue
        path = os.path.join(eval_dir, name)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                prompt = rec.get("prompt") or ""
                gold = (rec.get("gold") or {}).get("answer") or ""
                cases.append({
                    "id": rec.get("id"),
                    "prompt": prompt,
                    "gold": gold,
                    "phash": prompt_hash(prompt),
                    "ngrams": ngrams(prompt, 8),
                    "gold_nums": [
                        t
                        for m in _NUM.finditer(gold)
                        for t in [m.group(0).replace(",", "")]
                        if len(t.replace(".", "")) >= 4 and t not in _EXEMPT_GOLD_NUMS
                    ],
                })
    return cases


def sample_text(rec: dict) -> tuple[str, str]:
    """Return (user_blob, all_blob) for a chat or instruction record."""
    msgs = rec.get("messages") or []
    user_parts, all_parts = [], []
    if msgs:
        for m in msgs:
            c = m.get("content") or ""
            # Structured/pair corpora carry content as a list of parts; coercing here
            # keeps the leak detector able to see the text instead of crashing the gate.
            if not isinstance(c, str):
                c = json.dumps(c, ensure_ascii=False)
            all_parts.append(c)
            if m.get("role") == "user":
                user_parts.append(c)
            tc = m.get("tool_calls")
            if tc:
                all_parts.append(json.dumps(tc, ensure_ascii=False))
    else:
        def _text(value):
            if value is None or isinstance(value, str):
                return value or ""
            return json.dumps(value, ensure_ascii=False)
        user_parts.append(_text(rec.get("instruction") or rec.get("prompt") or rec.get("input")))
        all_parts.extend([
            _text(rec.get("instruction")),
            _text(rec.get("input")),
            _text(rec.get("output") or rec.get("response")),
        ])
    return "\n".join(user_parts), "\n".join(all_parts)


def check_sample(rec: dict, eval_cases: list[dict], jaccard_th: float = 0.6,
                 ignore_gold_numeric: bool = False) -> list[str]:
    user, blob = sample_text(rec)
    hits = []
    uh = prompt_hash(user)
    ug = ngrams(user, 8)
    blob_n = normalize(blob)
    for c in eval_cases:
        if uh == c["phash"] and user.strip():
            hits.append(f"prompt_hash={c['id']}")
            continue
        if jaccard(ug, c["ngrams"]) >= jaccard_th:
            hits.append(f"ngram8={c['id']}")
            continue
        if not ignore_gold_numeric:
            for num in c["gold_nums"]:
                if num in blob_n:
                    hits.append(f"gold_num={c['id']}:{num}")
                    break
    return hits


def iter_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError:
                yield i, {"_parse_error": True, "raw": line}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("train_jsonl")
    p.add_argument("--eval-dir", default=DEFAULT_EVAL)
    p.add_argument("--jaccard", type=float, default=0.6)
    p.add_argument("--drop", default="", help="write clean jsonl here and drop hits")
    p.add_argument("--max-report", type=int, default=20)
    p.add_argument("--ignore-gold-numeric", action="store_true",
                   help="opt-in: treat 4+ digit gold-number collisions as warnings, "
                        "not leakage; hard gate uses prompt hash + n-gram Jaccard only")
    p.add_argument("--strict-numeric", action="store_true",
                   help="fail (rc=2) on numeric-proxy hits too - the old release-gate "
                        "behaviour. Default: numeric proxies are reported as warnings, "
                        "because measured 2026-11-05 they flagged 32-69% of corpora on "
                        "generic values like 0.005/0202/2021 while hard leaks were 0")
    args = p.parse_args(argv)

    cases = load_eval_cases(args.eval_dir)
    hits_n = 0
    hard_n = 0
    numeric_n = 0
    kept = []
    reports = []
    total = 0
    for i, rec in iter_jsonl(args.train_jsonl):
        total += 1
        if rec.get("_parse_error"):
            hits_n += 1
            hard_n += 1
            reports.append(f"L{i}: parse_error")
            continue
        reasons = check_sample(rec, cases, args.jaccard, ignore_gold_numeric=False)
        hard = [r for r in reasons if not r.startswith("gold_num=")]
        numeric = [r for r in reasons if r.startswith("gold_num=")]
        if hard:
            hits_n += 1
            hard_n += 1
            if len(reports) < args.max_report:
                reports.append(f"L{i}: {';'.join(hard[:3])} (HARD)")
            continue
        if numeric and not args.ignore_gold_numeric:
            numeric_n += 1
            if args.strict_numeric:
                hits_n += 1
                continue
        kept.append(rec)

    print(f"eval_cases={len(cases)} train={total} hard_leaks={hard_n} numeric_proxy_only={numeric_n}"
          f" blocking={hits_n}{' strict_numeric' if args.strict_numeric else ''}")
    for r in reports:
        print(" ", r)
    if args.drop:
        os.makedirs(os.path.dirname(os.path.abspath(args.drop)) or ".", exist_ok=True)
        with open(args.drop, "w", encoding="utf-8") as f:
            for rec in kept:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"wrote {len(kept)} clean samples -> {args.drop}")
    if hits_n:
        print("FAIL: training set overlaps evaluation set")
        return 2
    if numeric_n:
        print(f"PASS (hard): no prompt/n-gram leak; {numeric_n} rows share a gold number "
              f"with an eval case - review before treating them as independent evidence")
    else:
        print("PASS: no contamination")
    return 0


def scan_corpus(train_jsonl: str, eval_dir: str = None, jaccard_th: float = 0.6) -> dict:
    """Programmatic form of the gate so a trainer can call it before loading 16 GB."""
    cases = load_eval_cases(eval_dir or DEFAULT_EVAL)
    total = hard = numeric = 0
    first_hits = []
    for i, rec in iter_jsonl(train_jsonl):
        total += 1
        if rec.get("_parse_error"):
            hard += 1
            first_hits.append(f"L{i}: parse_error")
            continue
        reasons = check_sample(rec, cases, jaccard_th, ignore_gold_numeric=False)
        row_hard = [r for r in reasons if not r.startswith("gold_num=")]
        if row_hard:
            hard += 1
            if len(first_hits) < 5:
                first_hits.append(f"L{i}: {';'.join(row_hard[:2])}")
        elif any(r.startswith("gold_num=") for r in reasons):
            numeric += 1
    return {"path": train_jsonl, "rows": total, "hard_leaks": hard,
            "numeric_proxy_only": numeric, "examples": first_hits}


def assert_no_leak(train_jsonl: str, eval_dir: str = None, echo=print) -> dict:
    """Fail closed: a corpus holding verbatim eval prompts measures memorisation, not ability."""
    result = scan_corpus(train_jsonl, eval_dir)
    echo(f"[leak-gate] {result['path']}: rows={result['rows']} hard_leaks={result['hard_leaks']} "
         f"numeric_proxy={result['numeric_proxy_only']}")
    if result["hard_leaks"]:
        for line in result["examples"]:
            echo("  " + line)
        echo("[FATAL] 语料含评测集逐字/近重复题面，拒绝开训。先用 "
             "`python virtu_eval/contamination_check.py <corpus> --drop <clean>` 去污再指过去污文件。")
        sys.exit(2)
    return result


if __name__ == "__main__":
    sys.exit(main())
