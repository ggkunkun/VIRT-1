#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FANUC Macro B NC 静态安全闸：单位/极坐标/模态/包络/未知指令 六类确定性检查。

退出码 0=无阻断项(仍需人工复核) 1=存在阻断项 2=输入不可解析。只读，不执行不上传。
"""
import argparse, json, re, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

CANON_G = set("""G00 G01 G02 G03 G04 G28 G30 G40 G41 G42 G49 G50 G52 G53 G54 G55 G56
G20 G21 G27 G57 G58 G59 G65 G70 G71 G72 G73 G76 G80 G81 G82 G83 G84 G85 G86 G87 G88 G89 G90 G91
G92 G94 G95 G96 G97 G98 G99""".split())
CANON_M = set("""M00 M01 M03 M04 M05 M06 M08 M09 M10 M11 M19 M20 M21 M22 M23 M26 M30
M98 M99 M126 M127""".split())


def strip_comments(line):
    out, in_c = [], False
    for ch in line:
        if ch == "(":
            in_c = True
            continue
        if ch == ")" and in_c:
            in_c = False
            continue
        if not in_c:
            out.append(ch)
    return "".join(out)


def words(body):
    return re.findall(r"([A-Z])(-?[0-9.]+)", body.replace(" ", ""))


def parse_stock(lines):
    for i, l in enumerate(lines, 1):
        m = re.search(r"BLANK:\s*D\s*([0-9.]+)\s*[xX]\s*L\s*([0-9.]+)", l)
        if m:
            return i, float(m.group(1)), float(m.group(2))
    return None, None, None


def macro_vars(lines):
    assigned, used = {}, set()
    for i, l in enumerate(lines, 1):
        body = strip_comments(l)
        m = re.match(r"\s*(#[0-9]+)\s*=", body)
        if m:
            assigned.setdefault(m.group(1), []).append(i)
        for v in re.findall(r"#[0-9]+", body):
            head = re.match(r"\s*" + v + r"\s*=", body)
            if head is None or body.count(v) > 1:
                used.add(v)
    return assigned, used


def var_deps(lines):
    """变量 -> 该变量赋值式里引用的其它变量，逐行传递闭包。"""
    deps = {}
    for l in lines:
        body = strip_comments(l)
        m = re.match(r"\s*(#[0-9]+)\s*=\s*(.+)", body)
        if m:
            deps.setdefault(m.group(1), set()).update(re.findall(r"#[0-9]+", m.group(2)))
    changed = True
    while changed:
        changed = False
        for k in list(deps):
            for d in list(deps[k]):
                if d in deps and not deps[d] <= deps[k]:
                    deps[k] |= deps[d]
                    changed = True
    return deps


def polar_double_transform(lines):
    """C 轴已给极角，X 又(直接或经宏变量)乘进了同一变量的 COS —— 角度被算了两次。"""
    deps = var_deps(lines)
    cos_of, hits = {}, []
    for i, l in enumerate(lines, 1):
        body = strip_comments(l)
        for m in re.finditer(r"#([0-9]+)\s*=.*?(?:COS|SIN)\s*\[?\s*#([0-9]+)", body):
            cos_of.setdefault("#" + m.group(1), set()).add("#" + m.group(2))
    for i, l in enumerate(lines, 1):
        body = strip_comments(l)
        mc = re.search(r"C\s*#([0-9]+)", body)
        if not mc:
            continue
        ang = "#" + mc.group(1)
        for m in re.finditer(r"X\s*(\[[^\]]*\]|[-#0-9.]+)", body):
            used = set(re.findall(r"#[0-9]+", m.group(1)))
            closure = set(used)
            for u in used:
                closure |= deps.get(u, set())
            trig_src = set()
            for u in closure:
                trig_src |= cos_of.get(u, set())
            if ang in trig_src or ang in used:
                hits.append((i, l.strip()))
                break
    return hits


def check(path):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    text = chr(10).join(lines)
    f = []

    def add(sev, ln, code, msg, fix):
        f.append({"line": ln, "code": code, "severity": sev, "issue": msg, "fix": fix})

    mm = bool(re.search(r"\bG21\b", text))
    mi = bool(re.search(r"\bG20\b", text))

    for i, l in enumerate(lines, 1):
        body = strip_comments(l)
        if not re.search(r"\bG(83|73|81|85|76)\b", body):
            continue
        for addr, val in words(body):
            v = float(val)
            if mm and addr == "Q" and v > 200:
                add("FATAL", i, "NC-Q-UNIT",
                    "G21 米制下 Q" + val + " 解析为 " + val + " mm 啄深，物理不可能，固定循环退化为一次全深走刀",
                    "米制按 mm 写 Q5.0；整数脉冲形式只在英寸制或参数缩放控制成立")
            if mm and addr == "R" and v > 500:
                add("BLOCKING", i, "NC-R-PLANE", "R 平面 " + val + " mm 远超安全接近面", "R 取几 mm 级接近面")

    for i, l in polar_double_transform(lines):
        add("FATAL", i, "NC-POLAR",
            "同一角度既驱动 C 又乘进 X 的 COS，孔位不在分布圆上；角度 90 度处 X=0 直接落在主轴中心线",
            "X 固定为分布圆直径，只让 C 承担角度")

    assigned, used = macro_vars(lines)
    for var, lns in sorted(assigned.items()):
        if var not in used:
            add("BLOCKING", lns[0], "NC-DEAD-VAR",
                var + " 被赋值但从未进入任何运动/补偿字，该尺寸实际未生效",
                "接进对应运动的 X/Z 或刀具直径，或删除该参数避免被读成已加工")

    ln_s, sd, sl = parse_stock(lines)
    if sd:
        for i, l in enumerate(lines, 1):
            for addr, val in words(strip_comments(l)):
                v = float(val)
                if addr == "X" and v > sd + 20.0:
                    add("FATAL", i, "NC-ENVELOPE", "X" + val + " 超毛坯直径 " + str(sd) + " mm 加越程", "核对毛坯与安全平面")
                if addr == "Z" and v < -sl - 5.0:
                    add("FATAL", i, "NC-ENVELOPE", "Z" + val + " 深于毛坯长度 " + str(sl) + " mm，将切入卡盘/夹具侧",
                        "孔深改用被加工段厚度变量，越程只留 1 mm")
    else:
        add("BLOCKING", 0, "NC-NO-STOCK", "程序未声明 BLANK 毛坯包络，行程校验被跳过", "补毛坯声明或传入 --stock-d/--stock-l")

    def var_value(var):
        ln = assigned.get(var, [None])[0]
        if not ln:
            return None
        m = re.search(r"=\s*(-?[0-9.]+)", strip_comments(lines[ln - 1]))
        return float(m.group(1)) if m else None

    thick = [v for v in assigned if re.search(r"THICKNESS", lines[assigned[v][0] - 1], re.I)]
    total = [v for v in assigned if re.search(r"TOTAL", lines[assigned[v][0] - 1], re.I)]
    for i, l in enumerate(lines, 1):
        if not re.search(r"DRILL|HOLE", l, re.I):
            continue
        for j in range(i, min(i + 15, len(lines))):
            body = strip_comments(lines[j])
            mz = re.search(r"Z\s*[-+]#([0-9]+)", body)
            if not mz or j + 1 == i:
                continue
            v = "#" + mz.group(1)
            if v in total and thick:
                tv, thv = var_value(v), var_value(thick[0])
                if tv and thv and tv > thv:
                    add("BLOCKING", j + 1, "NC-DEPTH-MISMATCH",
                        "钻孔段 Z 深引用总长变量 " + v + "(" + str(tv) + ")，而程序同时声明盘厚变量 "
                        + thick[0] + "(" + str(thv) + ")，疑似多走 " + str(round(tv - thv, 1)) + " mm 进夹持侧",
                        "按图确认穿透段厚度，孔深改用该段厚度变量并只留 1 mm 越程")

    if re.search(r"\bG96\b", text) and not re.search(r"\bG50\b", text):
        add("BLOCKING", 0, "NC-G50-MISSING", "出现 G96 恒线速但全程无 G50 S 上限，直径趋小时转速飞升", "G96 段前加 G50 S<上限>")

    for i, l in enumerate(lines, 1):
        if re.search(r"IF\s*\[.*\]\s*THEN\s+#[0-9]+\s*=", strip_comments(l)):
            add("WARN", i, "NC-IFTHEN", "IF[..]THEN 单行赋值是控制版本相关写法，部分 0i 代次只认 IF[..]GOTO",
                "改写为 GOTO 形式，或先在斯沃面板 AUTO 模式回放确认")

    wh = len(re.findall(r"\bWHILE\b", text))
    do = len(re.findall(r"\bDO\s*[0-9]+", text))
    en = len(re.findall(r"\bEND\s*[0-9]+", text))
    if not (wh == do == en):
        add("BLOCKING", 0, "NC-LOOP-PAIR", "WHILE=" + str(wh) + " DO=" + str(do) + " END=" + str(en) + " 不配对", "补齐循环标签")

    for i, l in enumerate(lines, 1):
        body = strip_comments(l)
        if re.search(r"\bT[0-9]{2,4}\b", body) and not re.search(r"\b(G28|G30)\b", body):
            add("WARN", i, "NC-TOOL-CHANGE-HOME", "换刀块未先回参考点", "T 之前加 G28 U0 W0")
    if re.search(r"\bM08\b", text) and not re.search(r"\bM09\b", text):
        add("BLOCKING", 0, "NC-MODAL-COOLANT", "开了 M08 却从未 M09 关闭", "程序尾补 M09 M05")
    if re.search(r"\bM0[34]\b", text) and not re.search(r"\bM05\b", text):
        add("BLOCKING", 0, "NC-MODAL-SPINDLE", "主轴启动后无 M05 停止", "程序尾补 M05")
    for cyc in sorted(set(re.findall(r"\bG8[1-9]\b", text))):
        if not re.search(r"\bG80\b", text):
            add("BLOCKING", 0, "NC-MODAL-CANNED", cyc + " 固定循环未用 G80 取消", "换刀与结束前 G80")

    for i, l in enumerate(lines, 1):
        for g, m in re.findall(r"\b([GM])([0-9]{2})\b", strip_comments(l)):
            tok = g + m
            if tok not in (CANON_G if g == "G" else CANON_M):
                add("BLOCKING", i, "NC-UNKNOWN-CMD", "未知指令 " + tok + "，不得臆测其语义", "确认控制器支持或改写为白名单指令")

    blockers = sorted({x["code"] for x in f if x["severity"] in ("FATAL", "BLOCKING")})
    return {"program": path.replace("\\", "/").split("/")[-1], "lines": len(lines),
            "units": "G21 mm" if mm else ("G20 inch" if mi else "未声明"),
            "stock_envelope": {"declared_line": ln_s, "d": sd, "l": sl},
            "findings": f,
            "counts": dict((s, sum(1 for x in f if x["severity"] == s)) for s in ("FATAL", "BLOCKING", "WARN")),
            "blocker_codes": blockers,
            "verdict": "REVIEW_REQUIRED" if blockers else "STATIC_OK_HUMAN_REVIEW",
            "note": "静态闸不批准物理执行，仿真与首件试切仍必须走。"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nc_file")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    try:
        rep = check(a.nc_file)
    except Exception as e:
        sys.stdout.write(json.dumps({"verdict": "INPUT_UNPARSABLE", "error": str(e)}, ensure_ascii=False) + chr(10))
        return 2
    if a.json_out:
        json.dump(rep, open(a.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.stdout.write(json.dumps(rep, ensure_ascii=False)[:400] + chr(10))
    sys.stdout.write("codes=" + ",".join(rep["blocker_codes"]) + chr(10))
    return 1 if rep["verdict"] == "REVIEW_REQUIRED" else 0


if __name__ == "__main__":
    sys.exit(main())
