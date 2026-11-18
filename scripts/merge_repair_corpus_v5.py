#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 v5 训练语料 = 原 279 行修复集 + 补丁集过采样 4x（不改动原文件）。

过采样理由：补丁 19 行若按 1x 混入 279 行，占 6.4%，20 步链路/64 步训练中
被抽到的概率不足以纠正已固化的错误映射（Di=60/Do=120/Pi=20 -> 30.00）。
过采样 4x 后补丁占 355 行中的 76 行（21.4%），仍保留原集全部知识，
且每条补丁在 1 epoch 中至少被见过 4 次。

验证：合并后逐条检查 system/user/assistant 结构完整、无截断、sha256 记录。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v3_repair_sft.jsonl"
PATCH = ROOT / "reports" / "handover_20261115" / "train_data" / "full_repair_sft_v5.jsonl"
OUT = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v5_repair_sft.jsonl"
OVERSAMPLE = 4


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    base = load(BASE)
    patch = load(PATCH)
    merged = list(base) + patch * OVERSAMPLE
    for i, r in enumerate(merged):
        msgs = r.get("messages", [])
        roles = [m.get("role") for m in msgs]
        # 原集含 2 条（无 system）与 3 条（带 system）两类，均为单轮问答；
        # 强制要求最后一条是 assistant、倒数第二条是 user，且内容非空。
        assert len(msgs) >= 2 and roles[-2:] == ["user", "assistant"], (i, roles)
        assert all(m.get("content", "").strip() for m in msgs), i
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        for r in merged:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"[OK] base={len(base)} patch={len(patch)}x{OVERSAMPLE}={len(patch)*OVERSAMPLE} total={len(merged)}")
    print(f"[OK] patch_share={len(patch)*OVERSAMPLE/len(merged):.1%}")
    print(f"[OK] out={OUT}")
    print(f"[OK] sha256={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
