# -*- coding: utf-8 -*-
"""CMM 实测样本导入：把三坐标实测数据转成 basis=measured 的精度报告。

用法：
  python import_cmm.py --csv reports/cmm_samples.csv [--out reports/cmm_precision_report.md]
  python import_cmm.py --template   # 生成空模板 CSV

CSV 列: feature_id,part_id,measured_mm[,controller,dialect]
feature_id 与工件原型 critical_features[].name 一致（如 OD_28h6/BORE_52H7）。
公差带来自 cnc_controller_runtime 工件原型（ISO 286），绝不自造公差。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

_PKG = Path(__file__).resolve()
_ROOT = _PKG.parents[1]
for _p in (str(_ROOT), str(_PKG.parent / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from virtu_omni.manufacturing import cnc_controller_runtime as rt  # noqa: E402

REPORTS = _PKG.parent / "reports"


def feature_index() -> dict:
    idx = {}
    for wid in rt.WORKPIECE_ARCHETYPES:
        for f in rt.get_workpiece_archetype(wid).critical_features:
            idx[f["name"]] = (wid, f)
    return idx


def cp_cpk(values, nominal, tol_up, tol_lo):
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    usl, lsl = nominal + tol_up, nominal + tol_lo
    cp = (usl - lsl) / (6 * sd) if sd > 0 else float("inf")
    cpk = min((usl - mean) / (3 * sd), (mean - lsl) / (3 * sd)) if sd > 0 else float("inf")
    return {"n": n, "mean": round(mean, 4), "sd": round(sd, 5),
            "cp": round(cp, 3), "cpk": round(cpk, 3),
            "min": round(min(values), 4), "max": round(max(values), 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--out", default=str(REPORTS / "cmm_precision_report.md"))
    args = ap.parse_args()

    idx = feature_index()
    if args.template:
        REPORTS.mkdir(exist_ok=True)
        rows = [("feature_id", "part_id", "measured_mm", "controller", "dialect")]
        rows += [(f["name"], wid, "", "", "")
                 for wid in rt.WORKPIECE_ARCHETYPES
                 for f in rt.get_workpiece_archetype(wid).critical_features]
        with open(args.csv or str(REPORTS / "cmm_samples_template.csv"),
                  "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        print(f"template -> {args.csv or REPORTS / 'cmm_samples_template.csv'}")
        return 0
    if not args.csv:
        ap.error("需要 --csv 或 --template")

    groups = {}
    with open(args.csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            fid = (row.get("feature_id") or "").strip()
            if fid not in idx:
                print(f"[WARN] 未知特征 {fid}，跳过")
                continue
            try:
                val = float(row["measured_mm"])
            except (KeyError, ValueError):
                continue
            groups.setdefault(fid, []).append(val)

    lines = ["# CMM 实测精度报告", "",
             "basis=measured（真实三坐标/检具测量值）；公差带源自工件原型 ISO 286。", "",
             "| 特征 | 工件 | n | 均值 | σ | Cp | Cpk | 判定 |",
             "|---|---|---|---|---|---|---|---|"]
    result = {"basis": "measured", "features": {}}
    all_ok = True
    for fid, vals in sorted(groups.items()):
        wid, f = idx[fid]
        r = cp_cpk(vals, f["nominal_mm"], f["tol_upper_mm"], f["tol_lower_mm"])
        tgt = rt.get_workpiece_archetype(wid).target_cpk
        ok = r and r["cpk"] >= tgt
        all_ok &= bool(ok)
        verdict = "PASS" if ok else ("WARN" if r and r["cpk"] >= 1.33 else "FAIL")
        result["features"][fid] = {**r, "workpiece": wid, "target_cpk": tgt,
                                   "verdict": verdict}
        lines.append(f"| {fid} | {wid} | {r['n']} | {r['mean']} | {r['sd']} | "
                     f"{r['cp']} | {r['cpk']} | {verdict} |")
    lines += ["", f"总体判定: {'PASS' if all_ok else '含未达标项'}；"
              "Cpk<1.33 需停线整改，1.33~目标值需工艺改进。"]
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_out = Path(args.out).with_suffix(".json")
    json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"report -> {args.out}  ({'PASS' if all_ok else 'ATTENTION'})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
