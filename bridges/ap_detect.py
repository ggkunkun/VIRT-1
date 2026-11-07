# -*- coding: utf-8 -*-
"""STEP AP 版本 / 文本编码 批量探测器（P2 源头治理的可执行检查工具）。

配套 AP242_EXPORT_GUIDE.md：在重新导出前先盘点语料里有多少 AP203/GBK 文件，
导出后再复跑本工具验证迁移是否生效。

用法:
  python3 bridges/ap_detect.py --dir assets
  python3 bridges/ap_detect.py --dir assets --json reports/ap_detect.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from step_bom import detect_ap, detect_encoding, StepBOM  # noqa: E402


def probe(path: str) -> Dict[str, Any]:
    raw = open(path, "rb").read()
    ap = detect_ap(raw)
    enc = detect_encoding(raw)
    # 实体类型特征（判断是否有装配结构、几何表达类型）
    has_assembly = b"NEXT_ASSEMBLY_USAGE_OCCURRENCE" in raw or \
                   b"PRODUCT_DEFINITION_USAGE" in raw
    brep_kinds = {
        "MANIFOLD_SOLID_BREP": raw.count(b"MANIFOLD_SOLID_BREP"),
        "BREP_WITH_VOIDS": raw.count(b"BREP_WITH_VOIDS"),
        "ADVANCED_BREP_SHAPE_REPRESENTATION": raw.count(
            b"ADVANCED_BREP_SHAPE_REPRESENTATION"),
    }
    adv = {
        "needs_utf8_migration": enc != "utf-8",
        "recommend_ap242": ap in ("AP203", "AP214", "UNKNOWN"),
        "notes": [],
    }
    if enc != "utf-8":
        adv["notes"].append("非 UTF-8 编码：中文零件名在 LLM 分词下会乱码，"
                            "建议用 bridges/step_normalize.py 归一化或改导出 AP242")
    if ap == "AP203":
        adv["notes"].append("AP203 产品结构稀疏、不支持 PMI；且 SolidWorks 中文版常写 GBK 字节")
    if ap == "AP214":
        adv["notes"].append("AP214 结构表达较老，建议升级 AP242 获得完整产品结构与 PMI")
    if not has_assembly:
        adv["notes"].append("单零件文件（无 NAUO/PDU 装配关系）")
    return {
        "file": os.path.basename(path),
        "path": path.replace("\\", "/"),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()[:16],
        "ap_version": ap,
        "encoding": enc,
        "has_assembly_structure": has_assembly,
        "brep_kinds": brep_kinds,
        "advice": adv,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="STEP AP 版本/编码批量探测")
    ap.add_argument("--dir", action="append", default=[], help="目录(可多次)")
    ap.add_argument("--file", action="append", default=[], help="单文件(可多次)")
    ap.add_argument("--json", default="", help="写出 JSON 报告")
    a = ap.parse_args(argv)
    dirs = a.dir or ["assets"]
    paths: List[str] = list(a.file)
    for d in dirs:
        if os.path.isfile(d):
            paths.append(d)
            continue
        for base, _sub, fns in os.walk(d):
            if any(s in base for s in (".git", "__pycache__", ".venv")):
                continue
            for fn in fns:
                if fn.lower().endswith((".step", ".stp")):
                    paths.append(os.path.join(base, fn))
    paths = sorted(set(paths))
    recs = [probe(p) for p in paths]
    apc = Counter(r["ap_version"] for r in recs)
    enc = Counter(r["encoding"] for r in recs)
    need_utf8 = sum(1 for r in recs if r["advice"]["needs_utf8_migration"])
    need_242 = sum(1 for r in recs if r["advice"]["recommend_ap242"])
    report = {
        "tool": "bridges.ap_detect", "basis": "measured",
        "sample_size_n": len(recs),
        "ap_distribution": dict(apc), "encoding_distribution": dict(enc),
        "needs_utf8_migration": need_utf8, "recommend_ap242": need_242,
        "records": recs,
    }
    print("[ap_detect] n=%d | AP=%s | 编码=%s | 需UTF8迁移=%d | 建议升级AP242=%d" %
          (len(recs), dict(apc), dict(enc), need_utf8, need_242))
    for r in recs:
        print("  %-36s %-8s %-7s %s" % (
            r["file"][:36], r["ap_version"], r["encoding"],
            "装配体" if r["has_assembly_structure"] else "单零件"))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("[+] 写出报告: %s" % a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
