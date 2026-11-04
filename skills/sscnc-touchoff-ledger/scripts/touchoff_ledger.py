#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对刀台账一致性核验：机座标 = 工件坐标系偏置 + 相对座标，逐轴闭环。

用于斯沃 SSCNC 7.2 / 实机面板对刀后的算术复核。退出码 0=自洽 1=不自洽 2=读入失败。
"""
import argparse, json, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

EPS = 1e-6
AXES = ("X", "Y", "Z")


def audit(led, wear_limit):
    problems = []
    axes = led.get("axes", {})
    offs = {(o.get("no"), o.get("axis")): o for o in led.get("wcs", [])}
    active = led.get("active_wcs")
    if not active:
        problems.append({"code": "TOUCH-NO-ACTIVE-WCS", "detail": "未声明生效工件坐标系，循环启动前必须选定 G54 一类", "block": True})
    for a in AXES:
        rec = axes.get(a)
        if not rec:
            continue
        m = float(rec.get("machine")); w = float(rec.get("work", 0.0))
        key = (active, a)
        if key not in offs:
            problems.append({"code": "TOUCH-NO-OFFSET", "detail": "%s 轴缺 %s 偏置记录" % (a, active), "block": True})
            continue
        o = float(offs[key]["offset"])
        expect = m - w
        if abs(o - expect) > EPS:
            sign = abs(o - (w - m)) <= EPS
            problems.append({"code": "TOUCH-SIGN-ERROR" if sign else "TOUCH-ARITH",
                             "detail": "%s 轴偏置不自洽：machine %.4f - work %.4f = %.4f，台账写 %.4f%s" % (
                                 a, m, w, expect, o, "（数值等于反号，典型对刀符号写反）" if sign else ""),
                             "block": True})
        if not offs[key].get("spark_confirmed") and not rec.get("spark_confirmed"):
            problems.append({"code": "TOUCH-NO-SPARK", "detail": "%s 轴无火花/接触确认记录，触控式对刀未证完成" % a, "block": True})

    seen = {}
    for t in led.get("tools", []):
        no = t.get("t")
        if no in seen:
            problems.append({"code": "TOUCH-DUP-TOOL", "detail": "刀号 %s 重复登记（第 %s 与第 %s 条）" % (no, seen[no] + 1, len(seen) + 1), "block": True})
        seen[no] = len(seen)
        for k in ("h", "d"):
            if k not in t:
                problems.append({"code": "TOUCH-MISSING-GEOM", "detail": "刀号 %s 缺 %s 几何值" % (no, k.upper()), "block": True})
        for k in ("wear_h", "wear_d"):
            v = float(t.get(k, 0.0))
            if abs(v) > wear_limit:
                problems.append({"code": "TOUCH-WEAR-LIMIT", "detail": "刀号 %s 的 %s = %.3f 超允许 %.3f，应换刀而非补偿" % (no, k, v, wear_limit), "block": True})
    blocks = [p for p in problems if p.get("block")]
    return {"active_wcs": active, "axes_checked": [a for a in AXES if a in axes],
            "tools_checked": len(led.get("tools", [])), "problems": problems,
            "verdict": "TOUCHOFF_CONSISTENT" if not blocks else "TOUCHOFF_INVALID"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger_json")
    ap.add_argument("--wear-limit", type=float, default=0.5)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    try:
        led = json.load(open(a.ledger_json, encoding="utf-8"))
        rep = audit(led, a.wear_limit)
    except Exception as e:
        sys.stdout.write(json.dumps({"verdict": "READ_FAILED", "error": str(e)}, ensure_ascii=False) + chr(10))
        return 2
    txt = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(txt)
    sys.stdout.write(json.dumps({"verdict": rep["verdict"],
                                 "codes": [p["code"] for p in rep["problems"]]}, ensure_ascii=False) + chr(10))
    return 0 if rep["verdict"] == "TOUCHOFF_CONSISTENT" else 1


if __name__ == "__main__":
    sys.exit(main())
