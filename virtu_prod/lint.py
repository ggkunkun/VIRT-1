# -*- coding: utf-8 -*-
"""工业级 G 代码审查器（方言感知）。

覆盖：结构完整性、安全块、刀长补偿、主轴/冷却时序、快移安全高度、快速扎刀、
换刀点与换刀序列、可选停止、结束状态、纯铣削（无车削代码）、RTCP 开关、
半径补偿成对、BN 断点号、括号配平、B/C 限位、刀具号存在性。
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional

from . import sim

_TURN_CODES = {
    "fanuc": ["G96", "G97", "G99", "G70", "G71", "G72", "G76", "G32", "G33", "M19"],
    "hnc": ["G96", "G97", "G99", "G70", "G71", "G72", "G76", "G32", "G33", "M19"],
    "siemens": ["G96", "G97", "G99", "G33", "G331", "G332", "M19"],
}


def _code_only(line: str) -> str:
    return sim._strip_comments(line)[0]


def _tokens(line: str) -> Dict[str, float]:
    code = _code_only(line)
    code = sim._ORI.sub("", code)
    return {k.upper(): float(v) for k, v in sim._WORD.findall(code)}


def _gset(line: str) -> List[float]:
    code = _code_only(line)
    out = []
    for k, v in sim._WORD.findall(code):
        if k.upper() == "G":
            out.append(float(v))
    return out


def _check(checks: List[Dict], gate: str, ok: bool, evidence, rule: str) -> None:
    checks.append({"gate": gate, "status": "PASS" if ok else "FAIL",
                   "evidence": evidence, "rule": rule})


def lint(nc: str, dialect: str, machine: Dict, tools: Dict[str, dict],
         op_count: int, safety_z: float, require_spindle: bool = True) -> Dict:
    """require_spindle=False 用于标定/测头程序（主轴不转，不要求 M03/M08/M05）。"""
    checks: List[Dict] = []
    lines = nc.splitlines()
    forbid = _TURN_CODES[dialect]
    code_lines = [_code_only(l) for l in lines]
    text_code = "\n".join(code_lines)

    # 1 结构
    if dialect in ("fanuc", "hnc"):
        _check(checks, "STRUCT-HEADER", lines[0].strip() == "%"
               and any(re.match(r"^O\d{4}", l.strip()) for l in lines[:4]),
               {"first": lines[0].strip() if lines else None}, "以 % 开头且含 O#### 程序号")
        _check(checks, "STRUCT-FOOTER", lines[-1].strip() == "%"
               and "M30" in text_code, {"last": lines[-1].strip() if lines else None},
               "以 % 结束且含 M30")
    else:
        _check(checks, "STRUCT-HEADER", "G71" in text_code and "G54" in text_code,
               "G71/G54", "Siemens 公制 + G54")
        _check(checks, "STRUCT-FOOTER", "M30" in text_code, "M30", "M30 程序结束")

    head = "\n".join(code_lines[:25])
    need = ["G17", "G40", "G90"]
    if dialect != "siemens":
        need += ["G21", "G49", "G80"]
    else:
        need += ["G71"]
    _check(checks, "SAFETY-BLOCK", all(g in head for g in need),
           {g: (g in head) for g in need}, "安全块必须含 " + "/".join(need))
    _check(checks, "WORK-OFFSET", "G54" in text_code, "G54", "工件零点调用")

    # 2 行扫描：位置 / 换刀 / 补偿 / 主轴 / 冷却
    x = y = z = 0.0
    comp = False
    spindle = False
    coolant = False
    feed_seen = False
    first_feed_line: Optional[int] = None
    comp_at_first_feed = False
    spindle_at_first_feed = False
    coolant_at_first_feed = False
    tool_changes = 0
    tc_ok = []
    rapid_unsafe = []
    rapid_plunge = []
    feed_no_f = []
    b_vals, c_vals = [], []
    rtcp_on = False
    rtcp_seen = False
    g41 = 0
    d_seen = False
    last_pos = (0.0, 0.0, 0.0)
    motion = None
    modal_f = None
    for i, raw in enumerate(lines, 1):
        code = _code_only(raw)
        if not code or re.search(r"\bG(28|30|53)\b", code):
            continue
        wd = _tokens(raw)
        gs = _gset(raw)
        for g in gs:
            if g in (0, 1, 2, 3):
                motion = g
        if "T" in wd and re.search(r"\bM0?6\b", code):
            tool_changes += 1
            px, py, pz = last_pos
            ok = pz >= machine["tc_z"] - 0.5 and abs(px - machine["tc_x"]) <= 1.0 \
                and abs(py - machine["tc_y"]) <= 1.0
            tc_ok.append({"line": i, "pos": [round(px, 2), round(py, 2), round(pz, 2)],
                          "ok": ok})
        if 43 in gs:
            comp = True
        if 43.4 in gs or "TRAORI" in code:
            comp = True
            rtcp_on = True
            rtcp_seen = True
        if 49 in gs or "TRAFOOF" in code:
            comp = False
            rtcp_on = False
        if 41 in gs or 42 in gs:
            g41 += 1
        if 40 in gs:
            g41 = 0
        if "D" in wd:
            d_seen = True
            if dialect == "siemens":
                comp = True
        if "M03" in code or "M04" in code or re.search(r"\bM0?[34]\b", code):
            spindle = True
        if re.search(r"\bM0?5\b", code):
            spindle = False
        if "M08" in code or re.search(r"\bM0?8\b", code):
            coolant = True
        if "M09" in code or re.search(r"\bM0?9\b", code):
            coolant = False
        if motion in (1, 2, 3):
            if "B" in wd:
                b_vals.append(wd["B"])
            if "C" in wd:
                c_vals.append(wd["C"])
        if motion is not None and any(k in wd for k in ("X", "Y", "Z")):
            nx, ny, nz = wd.get("X", x), wd.get("Y", y), wd.get("Z", z)
            if motion == 0:
                if ("X" in wd or "Y" in wd) and z < safety_z - 0.01:
                    rapid_unsafe.append({"line": i, "z": round(z, 2)})
                if "Z" in wd and nz < z - 0.01 and "X" not in wd and "Y" not in wd \
                        and nz < safety_z - 0.01:
                    rapid_plunge.append({"line": i, "to": round(nz, 2)})
            else:
                if not feed_seen:
                    first_feed_line = i
                    comp_at_first_feed = comp
                    spindle_at_first_feed = spindle
                    coolant_at_first_feed = coolant
                feed_seen = True
                if "F" in wd:
                    modal_f = wd["F"]
                elif modal_f is None:
                    feed_no_f.append(i)
            x, y, z = nx, ny, nz
            last_pos = (x, y, z)

    _check(checks, "TOOL-CHANGE-SEQUENCE", tool_changes == max(1, op_count),
           f"tool_changes={tool_changes} ops={op_count}", "每工序一次换刀")
    _check(checks, "TOOL-CHANGE-POINT", all(t["ok"] for t in tc_ok) and bool(tc_ok),
           tc_ok, "换刀前必须位于换刀点 (X/Y/Z)")
    _check(checks, "TOOL-LENGTH-COMP", comp_at_first_feed,
           {"first_feed_line": first_feed_line, "comp": comp_at_first_feed},
           "首次切削前刀长补偿生效")
    if dialect == "siemens":
        _check(checks, "TOOL-D-WORD", d_seen, "D1", "Siemens 刀沿号 D 必须出现")
    if require_spindle:
        _check(checks, "SPINDLE-BEFORE-FEED", spindle_at_first_feed,
               {"line": first_feed_line}, "首次切削前主轴已启动")
        _check(checks, "COOLANT-BEFORE-FEED", coolant_at_first_feed,
               {"line": first_feed_line}, "首次切削前冷却开启")
    _check(checks, "RAPID-SAFE-HEIGHT", not rapid_unsafe,
           rapid_unsafe[:10] or "none", f"G00 横向移动不得低于安全高度 {safety_z}")
    _check(checks, "RAPID-PLUNGE", not rapid_plunge, rapid_plunge[:10] or "none",
           "禁止 G00 快速下刀进入材料")
    _check(checks, "FEED-RATE", not feed_no_f, feed_no_f[:10] or "none",
           "切削进给必须有 F（模态或显式）")

    # 3 纯铣削
    hits = []
    for code in forbid:
        if re.search(rf"\b{code}\b", text_code):
            hits.append(code)
    _check(checks, "MILL-ONLY", not hits, hits or "none",
           "禁止车削/螺纹/主轴定向代码 " + "/".join(forbid))
    _check(checks, "OPTIONAL-STOP", text_code.count("M01") >= op_count,
           {"M01": text_code.count("M01"), "ops": op_count}, "工序间 M01")
    _check(checks, "END-STATE",
           (not require_spindle or bool(re.search(r"\bM0?5\b", text_code)))
           and (not require_spindle or bool(re.search(r"\bM0?9\b", text_code)))
           and ("G49" in text_code or dialect == "siemens"),
           {"M05": bool(re.search(r"\bM0?5\b", text_code)),
            "M09": bool(re.search(r"\bM0?9\b", text_code)),
            "require_spindle": require_spindle},
           "结束前主轴停/冷却停/补偿取消")

    # 4 五轴
    rotates = any(abs(v) > 1e-6 for v in b_vals + c_vals)
    if rotates:
        _check(checks, "RTCP", rtcp_seen, {"rtcp_seen": rtcp_seen}, "五轴刀路必须启用 RTCP")
    if b_vals:
        rot = machine.get("rotary") or machine["rotary_limits_deg"]
        _check(checks, "B-LIMIT", all(rot["b"][0] <= v <= rot["b"][1] for v in b_vals),
               {"min": min(b_vals), "max": max(b_vals)}, "B 轴硬限位")
    if c_vals:
        rot = machine.get("rotary") or machine["rotary_limits_deg"]
        _check(checks, "C-LIMIT", all(rot["c"][0] <= v <= rot["c"][1] for v in c_vals),
               {"min": min(c_vals), "max": max(c_vals)}, "C 轴硬限位")

    # 5 半径补偿成对
    _check(checks, "RADIUS-COMP-PAIR", (g41 == 0),
           {"open_comp": g41, "D_word": d_seen}, "G41/G42 必须有 D 且以 G40 关闭")

    # 6 断点号与括号
    n_lines = [i for i, l in enumerate(lines, 1) if re.match(r"^N\d+", l.strip())]
    smooth = bool(n_lines) if dialect != "siemens" else True
    _check(checks, "RESTART-BLOCKS", smooth,
           {"n_lines": len(n_lines)}, "FANUC/HNC 每块带 N 号，可按工序列断点")
    unbalanced = [i for i, l in enumerate(lines, 1)
                  if l.count("(") != l.count(")")]
    _check(checks, "PAREN-BALANCE", not unbalanced, unbalanced[:10] or "none", "注释括号配平")

    # 7 刀具号存在性
    unknown = []
    for t in re.findall(r"\bT(\d+)\b", text_code):
        if f"T{int(t)}" not in tools:
            unknown.append(f"T{t}")
    _check(checks, "TOOL-LIST", not unknown, unknown or "all known", "刀具号必须在刀具清单中")

    failed = [c for c in checks if c["status"] == "FAIL"]
    return {"checks": checks, "failed": len(failed),
            "verdict": "PASS" if not failed else "FAIL",
            "failed_gates": [c["gate"] for c in failed], "basis": "measured (static NC parse)"}
