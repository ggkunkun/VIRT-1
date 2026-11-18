#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FANUC G71/G70 台阶轴程序的**语义**校验（独立层，不改动 cloud_train_pack 判分器）。

存在理由：现有令牌门 `evaluate_fanuc_g71_safety_probe` 只校验
  - 令牌齐全（G71/G70/T01/M30/M03/S>0/F>0/G71 P Q）
  - 无 `G00` 与负 Z 同行
它查不出下列**语义**错误，而 v7 实测确实出现了：
  - `G71 U-1.5 W-0.5 R-0.15`：背吃刀量/退刀量取负值，FANUC 语义不成立；
  - `N10 G00 X38.0` / `N20 G01 Z0.0`：轮廓块里没有实际切削，台阶根本没加工；
  - 只切到 Z-25 / Z-0.5：总长 45 的零件长度不足；
  - G70 前未退回安全点，精车从轮廓终点直接起刀。

本模块只做只读判定，供语料自检与部署后复核使用。
语义门是**附加**证据，门禁口径仍以 cloud_train_pack 判分器为准（AGENTS.md §8）。
"""
from __future__ import annotations

import re

# 探针几何：Ø60 棒料，第一台阶 Ø38×20，总长 45
STOCK_D = 60.0
STEP_D = 38.0
STEP_LEN = 20.0
TOTAL_LEN = 45.0

TOL_D = 2.0      # 直径容差 mm
TOL_LEN = 1.5    # 长度容差 mm


def _strip_think(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"<(?:think|redacted_reasoning|analysis)>.*?</(?:think|redacted_reasoning|analysis)>",
               "", text, flags=re.S | re.I)
    t = re.sub(r"^\s*Thinking\.\.\..*?\.\.\.done thinking\.\s*", "", t, flags=re.S | re.I)
    return t


def _clean_lines(text: str) -> list[str]:
    """去掉括号注释与行号噪声，按行/分号切分，统一大写。"""
    visible = _strip_think(text)
    # 括号注释（FANUC 注释）整体删掉，避免注释里的 G71/G00 干扰
    visible = re.sub(r"\([^)]*\)", " ", visible)
    out: list[str] = []
    for raw in re.split(r"[\r\n;]+", visible):
        line = raw.strip().upper()
        if not line:
            continue
        # 只保留像 G 代码的行（含字母+数字的指令）；说明性中文行会被自然过滤
        if re.search(r"\b[GMTXZSF]\s*-?\d", line):
            out.append(line)
    return out


def _parse_word(line: str, letter: str) -> list[float]:
    return [float(m) for m in re.findall(rf"(?<![A-Z]){letter}\s*(-?\d+(?:\.\d+)?)", line)]


def check_g71_step_shaft(text: str) -> dict:
    """返回 {passed, violations[], evidence{}}。violations 为空才通过。"""
    lines = _clean_lines(text)
    v: list[str] = []
    ev: dict = {}

    if not lines:
        return {"passed": False, "violations": ["no_gcode_lines"], "evidence": {}}

    up = "\n".join(lines)

    # ---- 1. 令牌齐备（与令牌门同口径，便于交叉核对） -------------------
    for tok, label in (("G71", "G71"), ("G70", "G70"), ("M30", "M30")):
        if tok not in up:
            v.append(f"missing_{label}")
    if not re.search(r"\bT0?1(?:01)?\b|\bT0101\b", up):
        v.append("missing_T01")
    if not re.search(r"\bM0?3\b", up):
        v.append("missing_M03")
    if not re.search(r"\bG71\b[^\n]*\bP\d+[^\n]*\bQ\d+", up):
        v.append("missing_G71_PQ")
    if not re.search(r"\bG9?6\b", up):
        v.append("missing_G96_constant_surface_speed")
    if not re.search(r"\bG5?0\b", up):
        v.append("missing_G50_spindle_clamp")

    # ---- 2. G71 第一块：U/R 必须为正，不得带 W -------------------------
    first_block = None
    second_block = None
    for ln in lines:
        if not re.search(r"\bG7?1\b", ln):
            continue
        if re.search(r"\bP\d+", ln) and re.search(r"\bQ\d+", ln):
            second_block = second_block or ln
        else:
            first_block = first_block or ln

    if first_block is None:
        v.append("missing_G71_first_block_U_R")
    else:
        ev["first_block"] = first_block
        for letter in ("U", "R", "W"):
            vals = _parse_word(first_block, letter)
            if any(x < 0 for x in vals):
                v.append(f"G71_first_block_negative_{letter}")
        if not _parse_word(first_block, "U") or all(x == 0 for x in _parse_word(first_block, "U")):
            v.append("G71_first_block_U_missing_or_zero")
        if not _parse_word(first_block, "R") or all(x == 0 for x in _parse_word(first_block, "R")):
            v.append("G71_first_block_R_missing_or_zero")
        if _parse_word(first_block, "W"):
            v.append("G71_first_block_has_W_invalid")

    # ---- 3. 轮廓块（N{P}..N{Q}）几何 -----------------------------------
    pnum = qnum = None
    m = re.search(r"\bP(\d+)\b[^\n]*\bQ(\d+)\b", up)
    if m:
        pnum, qnum = m.group(1), m.group(2)
        try:
            pidx = next(i for i, ln in enumerate(lines) if re.search(rf"\bN0*{int(pnum)}\b", ln))
            qidx = next(i for i, ln in enumerate(lines) if re.search(rf"\bN0*{int(qnum)}\b", ln))
        except StopIteration:
            v.append("profile_block_markers_not_found")
            pidx = qidx = None
        if pidx is not None and qidx is not None:
            if qidx <= pidx:
                v.append("profile_block_Q_before_P")
            profile = lines[pidx:qidx + 1]
            ev["profile"] = profile
            # 模态坐标行（只给 X/Z 而没有 G）也属于运动块
            motion = [ln for ln in profile if re.search(r"\bG0?[0-3]\b", ln)
                      or _parse_word(ln, "X") or _parse_word(ln, "Z")]
            ev["profile_motion_blocks"] = len(motion)
            if len(motion) < 5:
                v.append(f"profile_too_short({len(motion)}<5)")

            # ---- 刀路仿真：按顺序累积 X/Z，还原实际加工出的几何 ----
            x = z = None
            seen_step_d = False
            z_min_at_step = None      # 在 Ø38 段上切到的最深 Z
            shoulder_z = None         # X 首次跨到 Ø60 时的 Z（应为 -20）
            z_min_after_shoulder = None
            for ln in profile:
                xs, zs = _parse_word(ln, "X"), _parse_word(ln, "Z")
                if xs:
                    x = xs[-1]
                if zs:
                    z = zs[-1]
                if x is not None and abs(x - STEP_D) <= TOL_D:
                    seen_step_d = True
                    if z is not None:
                        z_min_at_step = z if z_min_at_step is None else min(z_min_at_step, z)
                if x is not None and x >= STOCK_D - TOL_D and shoulder_z is None:
                    shoulder_z = z if z is not None else 0.0
                if shoulder_z is not None and z is not None:
                    z_min_after_shoulder = z if z_min_after_shoulder is None else min(z_min_after_shoulder, z)

            ev["z_min_at_step"] = z_min_at_step
            ev["shoulder_z"] = shoulder_z
            ev["z_min_after_shoulder"] = z_min_after_shoulder
            ev["profile_end_X"] = x

            if not seen_step_d:
                v.append("profile_missing_step_diameter_38")
            if z_min_at_step is None or z_min_at_step > -(STEP_LEN - TOL_LEN):
                v.append("profile_step_too_short(need Z~-20)")
            if shoulder_z is None:
                v.append("profile_missing_shoulder_X60")
            elif shoulder_z > -(STEP_LEN - TOL_LEN):
                v.append(f"profile_shoulder_at_wrong_Z({shoulder_z:g},need~-20)")
            if z_min_after_shoulder is None or z_min_after_shoulder > -(TOTAL_LEN - TOL_LEN):
                v.append("profile_total_too_short(need Z~-45)")

            # ---- 4. G70 必须在 Q 之后；起刀点不得在毛坯内部 --------------
            g70_idx = next((i for i, ln in enumerate(lines) if re.search(r"\bG7?0\b", ln) and i > qidx), None)
            if g70_idx is None:
                v.append("G70_not_after_profile_Q")
            else:
                between = lines[qidx:g70_idx]
                safe_retract = any(
                    re.search(r"\bG0?0\b", ln) and any(zz >= 1.0 for zz in _parse_word(ln, "Z"))
                    and any(xx >= STOCK_D - TOL_D for xx in _parse_word(ln, "X") or [STOCK_D])
                    for ln in between
                )
                # FANUC 粗车循环结束会自动回到循环起点；只要轮廓终点已径向退出毛坯即算安全
                end_outside = x is not None and x >= STOCK_D - TOL_D
                if not (safe_retract or end_outside):
                    v.append("G70_starts_inside_stock")

    # ---- 5. 任何一行不得出现 G00 与负 Z 并存 ---------------------------
    for ln in lines:
        if re.search(r"\bG0?0\b", ln) and any(z < 0 for z in _parse_word(ln, "Z")):
            v.append("unsafe_G00_negative_Z_plunge")
            break

    # ---- 6. 主轴/进给为正 --------------------------------------------
    for ln in lines:
        if any(s <= 0 for s in _parse_word(ln, "S")):
            v.append("non_positive_S")
            break
    for ln in lines:
        if any(f <= 0 for f in _parse_word(ln, "F")):
            v.append("non_positive_F")
            break

    # 去重保序
    seen = set()
    uniq = [x for x in v if not (x in seen or seen.add(x))]
    return {"passed": not uniq, "violations": uniq, "evidence": ev}


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        txt = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    else:
        txt = sys.stdin.read()
    print(json.dumps(check_g71_step_shaft(txt), ensure_ascii=False, indent=2))
