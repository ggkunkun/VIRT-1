#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_virtu_toolcall.py — wish/tool-call 语料质量门禁（6 条判据）

对应 AGENT_TRAINING_PLAN.md §3.5，与旧的 validate_toolcall_data.py
（面向自动化设备 feature_tree 数据集）互不干扰，本脚本只验证新的 wish 语料。

判据：
  1. arguments 是合法 JSON 且能反序列化成 dict
  2. 工具名 ∈ 工具清单
  3. 满足该工具 JSON Schema 的 required，且每个 call 都有配对 tool 回执
  4. 值域合法：d_inner < d_outer；material ∈ enum；num_features ∈ [1,100]
  5. 与 spec 一致：重新解析 user wish 得到的 spec 与 parse 工具 arguments 逐字段相等
  6. 长度不超限：渲染后字符数 ≤ 8192（超出只记 warning，训练时按 max_length 截断）

通过率要求 ≥ 98%，低于此值禁止开训。

用法:
  python scripts/validate_virtu_toolcall.py
  python scripts/validate_virtu_toolcall.py --input path/to/file.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_toolcall_corpus import enhanced_parse  # noqa: E402
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine  # noqa: E402

DATASET_DIR = ROOT / "damodel_cad_cam_tuning" / "dataset"
SCHEMA_PATH = ROOT / "data" / "tools" / "tool_schema.json"
REPORT_PATH = ROOT / "data" / "validation" / "virtu_toolcall_quality_report.json"
MAX_CHARS = 8192
PASS_RATE_MIN = 0.98


def load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        tools = json.load(f)
    out = {}
    for t in tools:
        fn = t["function"]
        out[fn["name"]] = {
            "required": fn["parameters"].get("required", []),
            "properties": fn["parameters"].get("properties", {}),
        }
    return out


def validate_file(path: Path, schema: dict, engine: WishCADCAMEngine) -> dict:
    total = passed = 0
    failures = Counter()
    warnings = Counter()
    samples = []

    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            total += 1
            errs = []
            try:
                rec = json.loads(line)
            except Exception:
                failures["g1_bad_json_row"] += 1
                continue

            msgs = rec.get("messages", [])
            if not rec.get("tools"):
                errs.append("missing_tools_field")

            calls, reply_ids = [], set()
            for m in msgs:
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    calls.extend(m["tool_calls"])
                if m.get("role") == "tool":
                    reply_ids.add(m.get("tool_call_id"))

            if not calls:
                errs.append("no_tool_calls")

            for c in calls:
                cid, fn = c.get("id", ""), c.get("function", {})
                name = fn.get("name", "")
                # 门禁 1
                try:
                    args = json.loads(fn.get("arguments", ""))
                except Exception:
                    failures["g1_bad_arguments_json"] += 1
                    errs.append(f"bad_arguments_json:{name}")
                    continue
                if not isinstance(args, dict):
                    failures["g1_arguments_not_dict"] += 1
                    errs.append(f"arguments_not_dict:{name}")
                    continue
                # 门禁 2
                if name not in schema:
                    failures["g2_unknown_tool"] += 1
                    errs.append(f"unknown_tool:{name}")
                    continue
                # 门禁 3
                for req in schema[name]["required"]:
                    if req not in args:
                        failures["g3_missing_required"] += 1
                        errs.append(f"missing_required:{name}.{req}")
                if cid not in reply_ids:
                    failures["g3_missing_tool_reply"] += 1
                    errs.append(f"missing_tool_reply:{cid}")
                # 门禁 5
                if name == "cad.parse_wish_intent":
                    user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
                    expected = enhanced_parse(engine, user)
                    for k, v in expected.items():
                        if k not in args or args[k] != v:
                            failures["g5_spec_mismatch"] += 1
                            errs.append(f"spec_mismatch:{k}")
                            break
                # 门禁 4
                if "d_outer" in args and "d_inner" in args and not args["d_inner"] < args["d_outer"]:
                    failures["g4_inner_ge_outer"] += 1
                    errs.append("d_inner>=d_outer")
                if "material" in args:
                    enum = schema[name]["properties"].get("material", {}).get("enum", [])
                    if enum and args["material"] not in enum:
                        failures["g4_material_not_in_enum"] += 1
                        errs.append(f"bad_material:{args['material']}")
                if "num_features" in args:
                    v = args["num_features"]
                    if not (isinstance(v, int) and 1 <= v <= 100):
                        failures["g4_num_features_range"] += 1
                        errs.append(f"bad_num_features:{v}")

            # 门禁 6
            rendered = json.dumps(rec, ensure_ascii=False)
            if len(rendered) > MAX_CHARS:
                warnings["oversize_gt16k" if len(rendered) > 16384 else "oversize_gt8k"] += 1

            if errs:
                if len(samples) < 8:
                    samples.append({"line": lineno, "errors": errs[:6]})
            else:
                passed += 1

    rate = passed / total if total else 0.0
    return {
        "file": str(path), "total": total, "passed": passed, "failed": total - passed,
        "pass_rate": round(rate, 4), "verdict": "PASS" if rate >= PASS_RATE_MIN else "FAIL",
        "failure_breakdown": dict(failures), "warnings": dict(warnings),
        "failed_samples": samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Virtu wish/tool-call 语料质量门禁")
    ap.add_argument("--input", default=None)
    args = ap.parse_args()

    schema = load_schema()
    engine = WishCADCAMEngine()
    targets = ([Path(args.input)] if args.input else [
        DATASET_DIR / "toolcall_sft_v1.jsonl",
        DATASET_DIR / "toolcall_sft_v2_expanded.jsonl",
        DATASET_DIR / "virtu_toolcall_train_unified.jsonl",
    ])
    reports = []
    for p in targets:
        if not p.exists():
            print(f"[skip] 文件不存在: {p}")
            continue
        r = validate_file(p, schema, engine)
        reports.append(r)
        print(f"\n=== {p.name} ===")
        print(f"  总数={r['total']} 通过={r['passed']} 失败={r['failed']} "
              f"通过率={r['pass_rate']:.2%} -> {r['verdict']}")
        if r["failure_breakdown"]:
            print(f"  失败分布: {r['failure_breakdown']}")
        if r["warnings"]:
            print(f"  警告: {r['warnings']}")
        if r["failed_samples"]:
            print(f"  失败样例: {r['failed_samples'][:3]}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    print(f"\n[validate] 报告 -> {REPORT_PATH}")
    if any(r["verdict"] == "FAIL" for r in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
