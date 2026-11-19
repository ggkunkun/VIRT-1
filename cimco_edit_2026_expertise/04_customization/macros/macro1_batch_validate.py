#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""宏脚本工具 1：批量 NC 程序校验与质量报告生成器。

用途：对目录下所有 .nc/.NC/.tap 批量执行 FANUC Macro B + 语法哨兵校验，
输出 CSV/JSON 质量报告。基于 D:\\Virtu模型\\bridges\\cimco_bridge.py（已实测 verified-working）。

部署：将本文件与 cimco_bridge.py 置于可 import 路径，命令行：
  python macro1_batch_validate.py --dir <NC目录> --out <报告.json> [--strict]
退出码：0=全部通过；1=存在失败（strict 模式）。
诚实声明：本地静态校验，非 CIMCO 内核、非机床仿真（见 CAPABILITY_BOUNDARIES B-01/B-06）。
"""
import sys, os, json, csv, argparse, glob, time
sys.path.insert(0, r"D:\Virtu模型")
from bridges.cimco_bridge import CIMCOBridge

def batch_validate(nc_dir, recursive=False):
    bridge = CIMCOBridge()
    pattern = os.path.join(nc_dir, "**", "*") if recursive else os.path.join(nc_dir, "*")
    exts = (".nc", ".NC", ".Nc", ".tap", ".TAP", ".txt")
    files = [p for p in glob.glob(pattern, recursive=recursive)
             if p.lower().endswith(tuple(e.lower() for e in exts))]
    rows = []
    for p in sorted(files):
        try:
            code = open(p, encoding="utf-8", errors="ignore").read()
        except Exception as e:
            rows.append({"file": p, "status": "ERROR", "error": str(e)})
            continue
        r = bridge.validate_fanuc_macro_b(code)
        # 与安全门一致：任何非 CHECK_UNAVAILABLE 的 error 都判为需修复
        real_errors = [e for e in r["errors"] if not e.startswith("CHECK_UNAVAILABLE")]
        verdict = "PASS" if (r["status"] == "success" and r["syntax_checked"]
                             and r["is_valid"] and not real_errors) else "FAIL"
        rows.append({
            "file": p, "verdict": verdict, "status": r["status"],
            "is_valid": r["is_valid"], "syntax_checked": r["syntax_checked"],
            "lines": r["line_count"], "vars": len(r["variables"]),
            "errors": r["errors"], "real_errors": real_errors,
        })
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    rows = batch_validate(a.dir, a.recursive)
    passed = sum(1 for r in rows if r.get("verdict") == "PASS")
    report = {
        "tool": "macro1_batch_validate", "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dir": a.dir, "total": len(rows), "passed": passed, "failed": len(rows) - passed,
        "elapsed_sec": round(time.time() - t0, 3),
        "honest_note": "本地静态校验(CIMCO桥接)，非CIMCO内核/非机床仿真",
        "rows": rows,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["file", "verdict", "status", "is_valid",
                                              "syntax_checked", "lines", "vars", "errors"])
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in w.fieldnames})
    print(f"[macro1] total={len(rows)} pass={passed} fail={len(rows)-passed} -> {a.out}")
    return 1 if (a.strict and passed < len(rows)) else 0

if __name__ == "__main__":
    sys.exit(main())
