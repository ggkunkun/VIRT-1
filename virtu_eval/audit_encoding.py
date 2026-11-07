"""Encoding audit for the evaluation case set.

The case validator only checks JSON *structure*.  A file can be perfectly
valid JSON whose Chinese text was transcoded UTF-8 -> GBK -> UTF-8, and the
validator will happily call it VALID while every prompt reads as mojibake.

That is exactly what happened to generalization.jsonl.  This audit looks for
the fingerprints of lossy transcoding and for U+FFFD replacement characters,
in the case files and in every image ground-truth file.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Characters that only show up when CJK text is decoded with the wrong codec
# and then re-encoded.  This list is deliberately conservative: a hit must be
# evidence, not a guess.
MOJIBAKE_MARKERS = [
    "锟斤拷", "烫烫烫", "屯屯屯",          # classic GBK<->UTF-8 round trip damage
    "鎸夈", "鏍煎紡", "璇锋眰",          # 按缩进格式 / 格式 / 请求
    "宸ヤ綔", "宸ュ", "鍨嬬",            # 工作 / 模型 / 型
    "鍙浠", "缁", "鏄", "涓", "鐨",      # 可 / 给 / 是 / 中 / 的
    "锛", "銆", "鈥", "闂", "鍙",       # ， 。 “ ” 、
    "绫", "褰", "鏍", "璁", "绠",        # 缩 / 繁 / 根 / 记 / 结
]

REPLACEMENT = "\ufffd"

CJK = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")


def scan_text(text, where, problems):
    hits = [m for m in MOJIBAKE_MARKERS if m in text]
    if hits:
        problems.append(f"{where}: mojibake markers {hits[:4]}")
    if REPLACEMENT in text:
        problems.append(f"{where}: U+FFFD replacement char x{text.count(REPLACEMENT)}")
    # CJK text mixed with lone latin words is legal, but a *whole file* of it
    # with zero CJK is a signal the decode was wrong.
    return hits


def audit_case_file(path):
    problems = []
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        problems.append(f"{os.path.basename(path)}: not valid UTF-8 ({exc})")
        return problems, 0

    n_ok = 0
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{os.path.basename(path)}:{i}: bad_json {exc}")
            continue
        n_ok += 1
        blob = json.dumps(rec, ensure_ascii=False)
        scan_text(blob, f"{os.path.basename(path)}:{i}", problems)
        # a healthy Chinese case has real CJK and readable punctuation
        if rec.get("language") == "zh":
            if not CJK.search(blob):
                problems.append(f"{os.path.basename(path)}:{i}: zh case with no CJK")
    return problems, n_ok


def main():
    case_dir = sys.argv[1] if len(sys.argv) > 1 else "data/benchmark/virtu_eval_v1"
    case_dir = os.path.join(ROOT, case_dir)
    problems, total = [], 0
    for fname in sorted(os.listdir(case_dir)):
        if not fname.endswith(".jsonl"):
            continue
        p, n = audit_case_file(os.path.join(case_dir, fname))
        problems.extend(p)
        total += n
        print(f"{fname:22s} parsed={n:3d} problems={len(p)}")
    # images ground truth
    gt = os.path.join(case_dir, "images", "ground_truth.json")
    if os.path.exists(gt):
        raw = open(gt, "rb").read()
        try:
            t = raw.decode("utf-8")
            scan_text(t, "images/ground_truth.json", problems)
        except UnicodeDecodeError as exc:
            problems.append(f"images/ground_truth.json: not valid UTF-8 ({exc})")
    print(f"\ntotal parsed cases: {total}")
    if problems:
        print(f"\nENCODING PROBLEMS ({len(problems)}):")
        for p in problems[:80]:
            print("  -", p)
        return 1
    print("\nENCODING OK: all case files are clean UTF-8 with no mojibake.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
