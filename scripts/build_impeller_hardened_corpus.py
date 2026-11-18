# -*- coding: utf-8 -*-
"""合并叶轮修复语料与通用能力回放缓冲，防目标微调灾难性遗忘。

配比〔拟〕：impeller_fix ×3（强修复信号）+ capability_v5 前 1500 条（通用回放）。
合并后必须重新通过 contamination + unit 两道闸（不信文件名）。
"""
import sys
import json
import random
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
DS = ROOT / "cloud_train_pack" / "dataset"
OUT = DS / "virtu_impeller_hardened_sft.jsonl"
LEDGER = DS / "virtu_impeller_hardened_sft_ledger.json"


def main():
    fix = [l.strip() for l in open(DS / "virtu_impeller_fix_sft.jsonl", encoding="utf-8") if l.strip()]
    cap = [l.strip() for l in open(DS / "virtu_capability_sft_v5.jsonl", encoding="utf-8") if l.strip()][:1500]
    rows = fix * 3 + cap
    random.Random(11).shuffle(rows)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    from virtu_eval.contamination_check import assert_no_leak
    from corpus_unit_audit import assert_units_clean
    leak = assert_no_leak(str(OUT))
    assert_units_clean(str(OUT))
    ledger = {"total": len(rows), "impeller_fix_unique": len(fix), "impeller_oversample": 3,
              "impeller_rows": len(fix) * 3, "capability_replay": len(cap),
              "contamination_hard_leaks": leak.get("hard_leaks") if isinstance(leak, dict) else "pass",
              "unit_gate": "pass", "mix_note": "〔拟〕29% targeted / 71% general replay"}
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[HARDENED CORPUS CERTIFIED]", json.dumps(ledger, ensure_ascii=False))


if __name__ == "__main__":
    main()