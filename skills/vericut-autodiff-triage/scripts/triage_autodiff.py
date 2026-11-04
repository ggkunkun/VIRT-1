#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto-Diff 结论审计：判"合格"之前先证明这张图真的有东西可判。

输入是 cadcam_visual_inspect(task=autodiff_inspection) 与 cadcam_vericut_simulate
(check_collision) 的返回 JSON。退出码 0=可进入下一步 1=必须停机整改 2=证据不足。
"""
import argparse, json, re, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def load(p):
    return json.load(open(p, encoding="utf-8", errors="replace"))


def audit(insp, log_text=None):
    out = {"checks": [], "escalations": []}
    red = float(insp.get("red_pixels", insp.get("red_count", 0)) or 0)
    blue = float(insp.get("blue_pixels", insp.get("blue_count", 0)) or 0)
    green = float(insp.get("green_pixels", insp.get("green_count", 0)) or 0)
    mach = float(insp.get("machined_pixels") or (red + blue + green))
    g_r = float(insp.get("gouge_ratio", 0) or 0)
    b_r = float(insp.get("excess_ratio", 0) or 0)
    t_r = float(insp.get("in_tolerance_ratio", 0) or 0)

    if mach <= 0 or (red + blue + green) <= 0:
        out["escalations"].append({"code": "AD-EMPTY-FIELD",
                                   "detail": "识别到的有效像素为 0：空白/未渲染/取错窗口的截图不能判绿色合格",
                                   "block": True})
        out["verdict"] = "INSUFFICIENT_EVIDENCE"
        out["totals"] = {"red": red, "blue": blue, "green": green, "machined": mach}
        return out
    out["checks"].append({"code": "AD-NONEMPTY", "detail": "有效像素 %d" % int(mach), "ok": True})

    s = g_r + b_r + t_r
    if abs(s - 100.0) > 1.0:
        out["escalations"].append({"code": "AD-RATIO-SUM",
                                   "detail": "三类占比之和 %.2f%% 不为 100%%，分类器口径不一致" % s, "block": True})
    recomputed = 100.0 * green / mach
    if abs(recomputed - t_r) > 2.0 and t_r:
        out["escalations"].append({"code": "AD-RATIO-CHECK",
                                   "detail": "绿色自报 %.2f%% 与按像素重算 %.2f%% 不符" % (t_r, recomputed),
                                   "block": True})
    claimed = str(insp.get("verdict", "")).upper()
    if red > 100 and "PASS" in claimed and "GOUGE" not in claimed:
        out["escalations"].append({"code": "AD-RED-BUT-PASS",
                                   "detail": "存在 %d 个过切像素却给出合格结论" % int(red), "block": True})

    if log_text:
        col = len(re.findall(r"(?i)(collision|gouge|\u8fc7\u5207|\u78b0\u649e)", log_text))
        err = len(re.findall(r"(?i)(error|\u9519\u8bef)", log_text))
        out["log"] = {"collision_lines": col, "error_lines": err}
        if col and not red:
            out["escalations"].append({"code": "AD-LOG-VS-IMAGE",
                                       "detail": "日志报 %d 条碰撞但图像判 0 过切，两路证据冲突" % col, "block": True})
        if err and claimed and "PASS" in claimed:
            out["escalations"].append({"code": "AD-LOG-ERRORS",
                                       "detail": "日志含 %d 条 error，仿真未完整收敛" % err, "block": True})

    blocks = [e for e in out["escalations"] if e.get("block")]
    if blocks:
        out["verdict"] = "STOP_AND_FIX"
    elif red > 0:
        out["verdict"] = "REVIEW_GOUGE"
    elif b_r > 5.0:
        out["verdict"] = "ADD_SEMI_FINISHING"
    else:
        out["verdict"] = "AUTODIFF_ACCEPTED"
    out["totals"] = {"red": int(red), "blue": int(blue), "green": int(green), "machined": int(mach)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspection-json", required=True)
    ap.add_argument("--sim-log", default=None)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    try:
        insp = load(a.inspection_json)
    except Exception as e:
        sys.stdout.write(json.dumps({"verdict": "INSUFFICIENT_EVIDENCE", "error": str(e)}, ensure_ascii=False) + chr(10))
        return 2
    log_text = None
    if a.sim_log:
        log_text = open(a.sim_log, encoding="utf-8", errors="replace").read()
    rep = audit(insp, log_text)
    txt = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(txt)
    sys.stdout.write(json.dumps({"verdict": rep["verdict"],
                                 "codes": [e["code"] for e in rep["escalations"]]}, ensure_ascii=False) + chr(10))
    return 2 if rep["verdict"] == "INSUFFICIENT_EVIDENCE" else (0 if rep["verdict"] == "AUTODIFF_ACCEPTED" else 1)


if __name__ == "__main__":
    sys.exit(main())
