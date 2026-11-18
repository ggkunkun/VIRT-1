# -*- coding: utf-8 -*-
"""结构化核验 FANUC G71/G70 车削程序，不模拟控制器或机床。"""

from __future__ import annotations

import re
from typing import Any


def _program_lines(text: str) -> list[str]:
    text = re.sub(r"\([^)]*\)", " ", str(text or ""))
    return [line.strip().upper() for line in re.split(r"[\r\n;]+", text) if line.strip()]


def _word(line: str, letter: str) -> list[float]:
    return [float(v) for v in re.findall(
        rf"(?<![A-Z]){letter}\s*(-?\d+(?:\.\d+)?)", line
    )]


def validate_g71_program(text: str) -> dict[str, Any]:
    """检查 G71/G70 的基本结构与可直接证明的危险语义。

    该门只核对程序文本，不代表 VERICUT/机床仿真通过。几何尺寸是否符合图纸仍由
    几何和成品完整性门判定。
    """
    lines = _program_lines(text)
    if not any(re.search(r"\bG71\b", line) for line in lines):
        return {"applicable": False, "passed": True, "basis": "static_semantic",
                "violations": [], "evidence": {}}

    violations: list[str] = []
    g71_blocks = [i for i, line in enumerate(lines) if re.search(r"\bG71\b", line)]
    first_i = next((i for i in g71_blocks
                    if not (re.search(r"\bP\d+\b", lines[i]) and
                            re.search(r"\bQ\d+\b", lines[i]))), None)
    cycle_i = next((i for i in g71_blocks
                    if re.search(r"\bP\d+\b", lines[i]) and
                    re.search(r"\bQ\d+\b", lines[i])), None)
    evidence: dict[str, Any] = {"g71_blocks": [lines[i] for i in g71_blocks]}

    if first_i is None:
        violations.append("G71_FIRST_BLOCK_MISSING")
    else:
        first = lines[first_i]
        evidence["first_block"] = first
        u, r, w = _word(first, "U"), _word(first, "R"), _word(first, "W")
        if not u or any(value <= 0 for value in u):
            violations.append("G71_U_MUST_BE_POSITIVE")
        if not r or any(value <= 0 for value in r):
            violations.append("G71_R_MUST_BE_POSITIVE")
        if w:
            violations.append("G71_FIRST_BLOCK_MUST_NOT_CONTAIN_W")

    if cycle_i is None:
        violations.append("G71_PROFILE_BLOCK_PQ_MISSING")
        profile: list[str] = []
        p_idx = q_idx = None
    else:
        cycle = lines[cycle_i]
        p_match = re.search(r"\bP(\d+)\b", cycle)
        q_match = re.search(r"\bQ(\d+)\b", cycle)
        p_idx = next((i for i, line in enumerate(lines)
                      if p_match and re.search(rf"\bN0*{int(p_match.group(1))}\b", line)), None)
        q_idx = next((i for i, line in enumerate(lines)
                      if q_match and re.search(rf"\bN0*{int(q_match.group(1))}\b", line)), None)
        if p_idx is None or q_idx is None:
            violations.append("G71_PROFILE_MARKER_MISSING")
            profile = []
        elif q_idx <= p_idx:
            violations.append("G71_PROFILE_MARKERS_OUT_OF_ORDER")
            profile = []
        else:
            profile = lines[p_idx:q_idx + 1]
            evidence["profile"] = profile

    motion = [line for line in profile if re.search(r"\bG0?[0-3]\b", line)
              or _word(line, "X") or _word(line, "Z")]
    evidence["profile_motion_blocks"] = len(motion)
    if len(motion) < 3:
        violations.append("G71_PROFILE_TOO_SHORT")
    if profile and not any(re.search(r"\bG0?1\b", line) for line in profile):
        violations.append("G71_PROFILE_HAS_NO_FEED_CUT")

    if q_idx is not None:
        g70_idx = next((i for i, line in enumerate(lines)
                        if re.search(r"\bG70\b", line) and i > q_idx), None)
        if g70_idx is None:
            violations.append("G70_MUST_FOLLOW_PROFILE_Q")
    elif not any(re.search(r"\bG70\b", line) for line in lines):
        violations.append("G70_MISSING")

    for line in lines:
        if re.search(r"\bG0?0\b", line) and any(value < 0 for value in _word(line, "Z")):
            violations.append("G00_NEGATIVE_Z_PLUNGE")
            break

    if not any(re.search(r"\bM0?3\b", line) or re.search(r"\bM0?4\b", line)
               for line in lines):
        violations.append("SPINDLE_START_MISSING")
    if not any(value > 0 for line in lines for value in _word(line, "S")):
        violations.append("POSITIVE_SPINDLE_SPEED_MISSING")
    if not any(value > 0 for line in lines for value in _word(line, "F")):
        violations.append("POSITIVE_FEED_MISSING")
    if not any(re.search(r"\bM0?2\b|\bM30\b", line) for line in lines):
        violations.append("PROGRAM_END_MISSING")

    # 稳定且可审计的顺序，避免同一个缺陷被多个检查重复记录。
    violations = list(dict.fromkeys(violations))
    return {"applicable": True, "passed": not violations,
            "basis": "static_semantic", "violations": violations,
            "evidence": evidence}
