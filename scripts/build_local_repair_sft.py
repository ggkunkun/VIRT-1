#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 279 行 DPO 缺陷修复集转成 SFT 语料（取 chosen 为 assistant 目标）。

用途：本地 6GB QLoRA SFT 增量修复 six-software:v3 的已知缺陷
（Lamé / 坐标单位隔离 / Auto-Diff / G00 安全 等）。

设计约束：
  * 零新增依赖（不装 datasets），直接产出 train_vericut_local_qlora.py 可吃的 messages 格式。
  * 保留原 prompt 里的 system 消息与 user 轮次；chosen 作为最后一条 assistant。
  * 不修改源文件；产物落 reports/handover_20261115/train_data/，带完整血缘。
  * 拒绝式微调（ReST）语义：只学正确回答，不学错误回答。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "cloud_train_pack" / "dataset_v2" / "vericut96_v3_dpo_repair.jsonl"
OUT_DIR = ROOT / "reports" / "handover_20261115" / "train_data"
OUT = OUT_DIR / "six_software_v3_repair_sft.jsonl"
LEDGER = OUT_DIR / "six_software_v3_repair_sft_ledger.json"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src_sha = sha256_file(SRC)
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]

    out_rows = []
    stat = {"total": len(rows), "prompt_list": 0, "prompt_str": 0, "skipped": 0}
    for r in rows:
        prompt = r.get("prompt")
        chosen = r.get("chosen")
        if not chosen:
            stat["skipped"] += 1
            continue
        if isinstance(prompt, list):
            msgs = [dict(m) for m in prompt if isinstance(m, dict) and m.get("role") in ("system", "user", "assistant", "tool")]
            stat["prompt_list"] += 1
            # 若 prompt 已含 assistant 结尾，追加会导致连续 assistant；此时替换最后一条
            if msgs and msgs[-1].get("role") == "assistant":
                msgs = msgs[:-1]
        elif isinstance(prompt, str):
            msgs = [{"role": "user", "content": prompt}]
            stat["prompt_str"] += 1
        else:
            stat["skipped"] += 1
            continue
        msgs.append({"role": "assistant", "content": str(chosen)})
        rec = {
            "messages": msgs,
            "meta": {
                "basis": "dpo_chosen_promoted",
                "source": "vericut96_v3_dpo_repair.jsonl",
                "source_sha256": src_sha,
                "family": r.get("family"),
                "software": r.get("software"),
                "source_run_id": r.get("source_run_id"),
                "evidence_sha256": r.get("evidence_sha256"),
            },
        }
        out_rows.append(rec)

    with OUT.open("w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ledger = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "本地 6GB QLoRA SFT 增量修复 six-software:v3 缺陷",
        "source_file": str(SRC.relative_to(ROOT)),
        "source_sha256": src_sha,
        "output_file": str(OUT.relative_to(ROOT)),
        "output_sha256": sha256_file(OUT),
        "rows": len(out_rows),
        "stat": stat,
        "method": "rejection-sampling SFT: DPO prompt + chosen -> messages; rejected discarded",
        "note": "仅用正确回答做监督微调；不含 rejected，不引入 DPO 依赖",
    }
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ledger, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
