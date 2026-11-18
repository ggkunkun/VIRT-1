# -*- coding: utf-8 -*-
"""把 CGTech VERICUT 9.6 官方培训库摄入 Virtu Agent 的持续学习管道。

    python scripts/ingest_vericut_training.py --root E:/training
    python scripts/ingest_vericut_training.py --root E:/training --dry-run --limit 100

产出：
* ``knowledge_base/web_knowledge_store.json`` 追加带实测溯源的知识条目
* ``data/sft/vericut_official_training.jsonl`` 重建（内容/证据驱动的训练对）
* ``reports/vericut_training_ingest_report.json`` 可复核的量化报告

幂等：按 record_id 去重；SFT 按当前知识库里全部 vericut 条目整文件重建。
源目录只读，脚本不改动 E:/training 下任何文件。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.internet.deep_learning_pipeline import (  # noqa: E402
    KNOWLEDGE_STORE_FILE,
    VERICUT_SFT_FILE,
    ContinualLearningPipeline,
)
from virtu_omni.knowledge.vericut_training import (  # noqa: E402
    DEFAULT_ROOT,
    scan,
)

REPORT_FILE = ROOT / "reports" / "vericut_training_ingest_report.json"

SELFCHECK_QUERIES = (
    "VERICUT Auto-Diff 过切 Gouge 与残料 Excess 的容差配置",
    "Session 101L Introduction to VMC Building 机床与控制配置",
    "刀具库 Tool Library GagePoint 与刀具规格",
    "Force optimization 与 Learn From NC Program 优化课程",
    "NC 程序 G43 G81 G83 钻孔与刀长补偿",
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ingest VERICUT official training assets")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="training library root (read-only)")
    ap.add_argument("--dry-run", action="store_true", help="validate only, do not write")
    ap.add_argument("--limit", type=int, default=0, help="only scan first N files (smoke test)")
    ap.add_argument("--pdf-chunk-pages", type=int, default=4)
    args = ap.parse_args(argv)

    root = Path(args.root)
    t0 = time.time()
    records, stats = scan(root, pages_per_chunk=args.pdf_chunk_pages,
                          max_files=args.limit or None)
    if not records:
        print(f"[FAIL] no records parsed from {root}; errors={stats.errors[:5]}")
        return 1

    pipeline = ContinualLearningPipeline()
    ingest = pipeline.ingest_structured_records(records, dry_run=args.dry_run)

    selfcheck = []
    if not args.dry_run:
        for q in SELFCHECK_QUERIES:
            hits = pipeline.retrieve_training_knowledge(q, top_k=1)
            selfcheck.append({
                "query": q,
                "top_topic": hits[0]["topic"] if hits else None,
                "similarity": hits[0]["similarity"] if hits else None,
                "source_path": hits[0]["source_path"] if hits else None,
            })

    report = {
        "timestamp": time.time(),
        "elapsed_s": round(time.time() - t0, 2),
        "root": str(root),
        "dry_run": bool(args.dry_run),
        "scan": stats.to_dict(),
        "ingest": ingest,
        "retrieval_selfcheck": selfcheck,
        "knowledge_store": str(KNOWLEDGE_STORE_FILE),
        "sft_file": str(VERICUT_SFT_FILE),
        "source_mode": "read_only",
    }
    if not args.dry_run:
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "files_seen": stats.files_seen,
        "records": len(records),
        "pdf_pages": stats.pdf_pages,
        "scan_errors": len(stats.errors),
        "accepted": ingest["accepted"],
        "duplicates": ingest["duplicates"],
        "rejected": ingest["rejected_count"],
        "sft_pairs": ingest["sft_pairs"],
        "store_entries_total": ingest["store_entries_total"],
        "elapsed_s": report["elapsed_s"],
        "dry_run": args.dry_run,
    }, ensure_ascii=False, indent=2))
    if selfcheck:
        print("\n[retrieval self-check]")
        for row in selfcheck:
            print(f"  {row['query'][:34]:<36} -> {str(row['top_topic'])[:58]} ({row['similarity']})")
    if not args.dry_run:
        print(f"\n[report] {REPORT_FILE}")
    return 0 if ingest["rejected_count"] == 0 and not stats.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
