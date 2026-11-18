# -*- coding: utf-8 -*-
"""生成 VERICUT 官方培训案例索引（只读扫描 E:/training）。

    python scripts/index_training_cases.py
    python scripts/index_training_cases.py --root E:/training --no-pdf
    python scripts/index_training_cases.py --check          # 只校验现有索引

产出 ``knowledge_base/training_case_index.json``：每个案例的
状态（error_demo / reference）、所需加工能力（车床/三轴/四轴/五轴定位/五轴联动/车铣）、
机床轴配置、NC 实测指标与证据路径。Agent 通过 ``query_training_cases`` 工具查询。
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

from virtu_omni.knowledge.training_case_catalog import (  # noqa: E402
    DEFAULT_INDEX_PATH,
    DEFAULT_ROOT,
    DEFAULT_VERIFICATION_PATH,
    answer_query,
    build_catalog,
    enrich_with_verification,
    load_catalog,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Index VERICUT training cases (read-only)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="training library root (read-only)")
    ap.add_argument("--out", default=str(DEFAULT_INDEX_PATH), help="output JSON index")
    ap.add_argument("--no-pdf", action="store_true", help="skip PDF text evidence")
    ap.add_argument("--verification", default=str(DEFAULT_VERIFICATION_PATH),
                    help="merge error-case reproduction report into the index")
    ap.add_argument("--no-verification", action="store_true",
                    help="do not merge error_case_verification.json")
    ap.add_argument("--check", action="store_true", help="validate existing index only")
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    if args.check:
        catalog = load_catalog(out_path)
        if not catalog:
            print(f"[FAIL] index not found or unreadable: {out_path}")
            return 1
        bad = [c["case_id"] for c in catalog.get("cases", [])
               if not c.get("sha256") or not c.get("path")]
        unverified = [
            c["case_id"] for c in catalog.get("cases", [])
            if c.get("status") == "error_demo"
            and (not c.get("verification_status") or not c.get("reproduction")
                 or not c.get("error_type"))
        ]
        summary = catalog.get("summary", {})
        print(json.dumps({
            "index": str(out_path),
            "cases": len(catalog.get("cases", [])),
            "cases_without_evidence": bad,
            "error_cases_without_verification": unverified,
            "error_case_verification": summary.get("error_case_verification"),
            "summary": {k: summary.get(k) for k in (
                "by_status", "by_capability", "turning_cases", "three_axis_cases",
                "four_axis_cases", "five_axis_cases", "mill_turn_cases")},
        }, ensure_ascii=False, indent=2))
        return 0 if not bad and not unverified else 1

    t0 = time.time()
    catalog = build_catalog(Path(args.root), read_pdf=not args.no_pdf)
    if not args.no_verification:
        enrich_with_verification(catalog, Path(args.verification))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = catalog["summary"]
    print(json.dumps({
        "root": catalog["root"],
        "index": str(out_path),
        "cases": summary["cases"],
        "by_status": summary["by_status"],
        "by_capability": summary["by_capability"],
        "machines": summary["machines"],
        "sessions": summary["sessions"],
        "standalone_programs": summary["standalone_programs"],
        "error_case_verification": summary.get("error_case_verification"),
        "elapsed_s": round(time.time() - t0, 2),
        "pdf_text_available": catalog["method"]["pdf_text_available"],
    }, ensure_ascii=False, indent=2))

    for q in ("哪些是错误案例", "哪些需要车床", "哪些只需要三轴", "哪些需要五轴联动"):
        ans = answer_query(catalog, q, limit=12)
        ids = [c["case_id"] for c in ans["cases"]]
        print(f"\n[{q}] {len(ids)} 个案例：{', '.join(ids[:8])}"
              f"{' …' if len(ids) > 8 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
