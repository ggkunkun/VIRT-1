#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_corpus_tool_names.py — 校验训练语料里的工具名在运行时是否可达。

审计 §4-6 缺陷：语料 60 个 vendor.action 工具名中大多数没有运行时映射，
模型学到的调用名在真机上只会落到 `Unknown tool name`。本脚本把这件事变成
可回归的门禁：

  1. 扫描 knowledge_base/six_software/training/datasets/*.jsonl 里所有
     tool_calls[].function.name；
  2. 逐个查询 virtu_omni.knowledge.corpus_tool_map 的裁决结果；
  3. 任何 unmapped（既不在可执行映射、也不在 knowledge_only）即判失败；
  4. 另外校验映射目标工具确实存在于运行时工具面，防止映射表自己写错。

退出码：0 全绿；1 存在 unmapped；2 映射目标不存在于运行时工具面。

用法：
  python scripts/lint_corpus_tool_names.py
  python scripts/lint_corpus_tool_names.py --json-out runs/corpus_tool_coverage.json
"""

import argparse
import glob
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_omni.knowledge.corpus_tool_map import (  # noqa: E402
    CORPUS_TOOL_NAMES,
    DISPATCH_ONLY_TOOLS,
    coverage,
    describe,
)


def collect_corpus_names(datasets_dir):
    names = {}
    files = sorted(glob.glob(os.path.join(datasets_dir, "*.jsonl")))
    for fp in files:
        for lineno, line in enumerate(open(fp, encoding="utf-8", errors="ignore"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            for msg in rec.get("messages", []) or []:
                for call in msg.get("tool_calls") or []:
                    fn = (call.get("function") or {}).get("name")
                    if fn:
                        names.setdefault(fn, []).append(
                            "%s:%d" % (os.path.basename(fp), lineno)
                        )
    return files, names


def runtime_tool_names():
    from bridges.tool_calling_specs import get_cadcam_tool_definitions

    return {d["function"]["name"] for d in get_cadcam_tool_definitions()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--datasets-dir",
        default=os.path.join(ROOT, "knowledge_base", "six_software", "training", "datasets"),
    )
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    files, corpus = collect_corpus_names(args.datasets_dir)
    if not files:
        print("[lint] 未找到语料文件：%s" % args.datasets_dir)
        return 2

    names = sorted(corpus)
    report = coverage(names)

    # 1) 映射目标必须在运行时可达（宣告面 ∪ 内部可调用入口）
    rt = runtime_tool_names() | set(DISPATCH_ONLY_TOOLS)
    bad_targets = []
    for name in names:
        d = describe(name)
        if d["kind"] == "executable" and d["canonical_tool"] not in rt:
            bad_targets.append((name, d["canonical_tool"]))

    # 2) knowledge_only 里登记的名字也必须来自语料（防止表比现实更大）
    stale = sorted(set(CORPUS_TOOL_NAMES) - set(names))

    if not args.quiet:
        print("[lint] 语料文件 %d 个，distinct 工具名 %d 个" % (len(files), len(names)))
        print(
            "[lint] 可执行映射 %d / 仅知识 %d / 未映射 %d"
            % (report["executable"], report["knowledge_only"], len(report["unmapped"]))
        )
        if report["unmapped"]:
            print("[lint] 未映射（运行时会 Unknown tool）：")
            for name in report["unmapped"]:
                occ = corpus.get(name, [])[:3]
                print("   - %s   例: %s" % (name, ", ".join(occ)))
        if bad_targets:
            print("[lint] 映射目标不在运行时工具面：")
            for src, tgt in bad_targets:
                print("   - %s -> %s" % (src, tgt))
        if stale:
            print("[lint] 提示：映射表里登记但语料未出现的名字 %d 个" % len(stale))

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        payload = {
            "datasets": [os.path.basename(f) for f in files],
            "distinct_tools": len(names),
            "coverage": {k: v for k, v in report.items() if k != "rows"},
            "rows": report["rows"],
            "mapping_targets_missing": bad_targets,
            "registry_only_names": stale,
            "occurrences": {k: v[:5] for k, v in corpus.items()},
        }
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        if not args.quiet:
            print("[lint] 报告写入 %s" % args.json_out)

    if report["unmapped"]:
        return 1
    if bad_targets:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
