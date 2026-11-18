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


def _f(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _pick(insp, metrics, keys):
    """按优先级取值；先扁平字段，再 metrics 嵌套，兼容旧版红色/蓝色命名。"""
    for src in (insp, metrics):
        for k in keys:
            if isinstance(src, dict) and src.get(k) not in (None, ""):
                return src.get(k), True
    return None, False


def normalize(insp):
    """归一化视觉载荷。

    生产端（bridges/cadcam_vision_bridge.py）历史上有两种形态：
      1. 旧版扁平：red_pixels / blue_pixels / gouge_ratio / verdict
      2. 现行嵌套：metrics.{gouge_pixels,excess_pixels,in_tolerance_percentage} + safety_verdict
    只认第 1 种会让第 2 种恒判 AD-EMPTY-FIELD（审计 §4-4），故此处两种都认，
    并在缺 green_pixels/machined_pixels 时用百分比与像素反解，而不是直接当 0。
    """
    m = insp.get("metrics") if isinstance(insp.get("metrics"), dict) else {}
    red, _ = _pick(insp, m, ("gouge_pixels", "red_pixels", "red_count"))
    blue, _ = _pick(insp, m, ("excess_pixels", "blue_pixels", "blue_count"))
    green, green_explicit = _pick(insp, m, ("green_pixels", "green_count"))
    g_r, _ = _pick(insp, m, ("gouge_percentage", "gouge_ratio"))
    b_r, _ = _pick(insp, m, ("excess_percentage", "excess_ratio"))
    t_r, _ = _pick(insp, m, ("in_tolerance_percentage", "in_tolerance_ratio"))
    mach, _ = _pick(insp, m, ("machined_pixels",))

    red, blue, green = _f(red), _f(blue), _f(green)
    g_r, b_r, t_r, mach = _f(g_r), _f(b_r), _f(t_r), _f(mach)

    if mach <= 0 and t_r > 0 and (red + blue) > 0:
        denom = 1.0 - t_r / 100.0
        if denom > 1e-6:
            mach = (red + blue) / denom
    if mach <= 0:
        mach = red + blue + green
    if green <= 0 and mach > 0 and t_r > 0:
        green = mach * t_r / 100.0

    claimed = ""
    for k in ("safety_verdict", "verdict"):
        if insp.get(k):
            claimed = str(insp.get(k)).upper()
            break
    return {
        "red": red, "blue": blue, "green": green, "machined": mach,
        "gouge_ratio": g_r, "excess_ratio": b_r, "in_tolerance_ratio": t_r,
        "claimed": claimed, "green_explicit": green_explicit,
    }


def audit(insp, log_text=None):
    out = {"checks": [], "escalations": []}
    if str(insp.get("status", "")).lower() == "error":
        out["escalations"].append({"code": "AD-INSPECT-ERROR",
                                   "detail": "视觉桥返回错误：%s" % (insp.get("message") or insp.get("verdict_code")),
                                   "block": True})
        out["verdict"] = "INSUFFICIENT_EVIDENCE"
        out["totals"] = {"red": 0, "blue": 0, "green": 0, "machined": 0}
        return out

    n = normalize(insp)
    red, blue, green, mach = n["red"], n["blue"], n["green"], n["machined"]
    g_r, b_r, t_r, claimed = n["gouge_ratio"], n["excess_ratio"], n["in_tolerance_ratio"], n["claimed"]

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
    if n["green_explicit"]:
        recomputed = 100.0 * green / mach
        if abs(recomputed - t_r) > 2.0 and t_r:
            out["escalations"].append({"code": "AD-RATIO-CHECK",
                                       "detail": "绿色自报 %.2f%% 与按像素重算 %.2f%% 不符" % (t_r, recomputed),
                                       "block": True})
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
