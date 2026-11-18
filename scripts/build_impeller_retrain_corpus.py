# -*- coding: utf-8 -*-
"""build_impeller_retrain_corpus.py — 8.2B 根因重训语料：全链路修复轨迹(×2) + 既有叶轮修复/通用回放。

repairloop(420)×2 = 840 强信号治：
  - R1 逆设计 + 首轮直通 (direct_design)
  - R2 多轮修复 5 类故障模式，且首轮坏解显式标记 loss=False 严禁负样本污染
  - R3 Stage B (build123d CAD) / Stage C (气动强度分析) / Stage D (ezdxf 工程图) / Workbench 协议
hardened(2106: 叶轮 T1-T4×3 + 通用回放) 保 T1/T2/T3/T4 与通用能力不回退。
合并后重过 contamination + unit 双闸。
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
OUT = DS / "virtu_impeller_retrain_sft.jsonl"
LEDGER = DS / "virtu_impeller_retrain_ledger.json"


def main():
    loop = [l.strip() for l in open(DS / "virtu_impeller_repairloop_sft.jsonl", encoding="utf-8") if l.strip()]
    hard = [l.strip() for l in open(DS / "virtu_impeller_hardened_sft.jsonl", encoding="utf-8") if l.strip()]
    rows = loop * 2 + hard
    random.Random(2027).shuffle(rows)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    from virtu_eval.contamination_check import assert_no_leak
    from corpus_unit_audit import assert_units_clean
    leak = assert_no_leak(str(OUT))
    assert_units_clean(str(OUT))
    ledger = {"total": len(rows), "repairloop_unique": len(loop), "repairloop_x": 2,
              "repairloop_rows": len(loop) * 2, "hardened_rows": len(hard),
              "contamination_hard_leaks": leak.get("hard_leaks") if isinstance(leak, dict) else "pass",
              "unit_gate": "pass",
              "note": f"8.2B 根因重训：全链路修复轨迹({len(loop)*2}，坏解轮 loss=False) + 叶轮T1-T4与通用回放({len(hard)})"}
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[RETRAIN CORPUS]", json.dumps(ledger, ensure_ascii=False))


if __name__ == "__main__":
    main()
