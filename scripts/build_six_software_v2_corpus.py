#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/build_six_software_v2_corpus.py — Build leakage-free anti-regression v2 SFT/DPO datasets.

Combines the verified v1 corpus (850 SFT + 90 DPO, untouched) with canonical,
non-duplicate anti-regression anchors & DPO contrast pairs targeting the exact
capability regressions observed on `virtu-six-software:v1`:
  1. Lamé thick-walled cylinder closed-form stress derivation (think=False explicit steps);
  2. FANUC two-line G71 + G70 turning cycle safety (G50, M03, P/Q, M30, zero G00 Z- plunge);
  3. VERICUT 9.6 Auto-Diff color triage (Red=Gouge/fatal, Blue=Excess/remill, Green=In-tolerance);
  4. Coordinate/unit isolation (SOLIDWORKS Y-up vs VERICUT Z-up, inch vs mm).

All deploy-probe exact parameters (e.g. Di=60/Do=120/Pi=20 and Ø60/Ø38/L20/L45)
are strictly excluded and checked fail-closed alongside schema, unit, tokenizer
length, and benchmark/holdout anti-leak gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
PACK_DIR = ROOT / "cloud_train_pack"
for _p in (str(ROOT), str(SCRIPTS_DIR), str(PACK_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from build_vericut96_cloud_datasets import (  # noqa: E402
    build_canonical_anti_regression_dpo_rows,
    build_canonical_anti_regression_rows,
)
from corpus_unit_audit import assert_units_clean  # noqa: E402
from gate_all90_dataset import (  # noqa: E402
    gate_schema_and_tools,
    gate_system_prompt_budget_and_leak,
)
from virtu_eval.contamination_check import assert_no_leak  # noqa: E402

DEFAULT_V1_SFT = PACK_DIR / "dataset" / "six_software_real_assets_sft.jsonl"
DEFAULT_V1_DPO = PACK_DIR / "dataset" / "six_software_real_assets_dpo.jsonl"
DEFAULT_OUT_DIR = PACK_DIR / "dataset"
DEFAULT_SEED = 20261115

DEFAULT_HOLDOUT_FILES = (
    ROOT / "data" / "sft" / "six_software_real_assets" / "six_software_holdout.jsonl",
    ROOT / "cloud_train_pack" / "dataset" / "six_software_holdout.jsonl",
    ROOT / "data" / "train" / "vericut_e_training_v1" / "holdout" / "vericut_e_training_holdout.jsonl",
    ROOT / "knowledge_base" / "six_software" / "training" / "datasets" / "vericut_holdout.jsonl",
)

BENCHMARK_DIRS = (
    ROOT / "data" / "benchmark" / "virtu_eval_v1",
    ROOT / "data" / "benchmark" / "virtu_eval_phys_v1",
    ROOT / "data" / "benchmark" / "virtu_eval_cl_v1",
    ROOT / "data" / "benchmark" / "virtu_blind_test_v3",
)

SYSTEM_PROMPT_CONCISE = (
    "你是 Virtu 工业智能体。严格遵守单位制与坐标系规范，未运行真实仿真或实测前严禁编造通过结论，公式推导与安全校验直出精确结果。"
)

SYSTEM_PROMPT_SIX_SW = (
    "你是 Virtu 工业智能体，精通 SOLIDWORKS 2021、Siemens NX 12.0、AutoCAD 2026、"
    "CIMCO Edit 2026、VERICUT 9.6 与 斯沃数控仿真软件 SSCNC 7.2 六大工业软件工程闭环。\n"
    "【硬性规则】1. 严格区分单位（IGES/STEP 用 mm，SolidWorks API 向量用 MKS）；"
    "2. 未运行真实仿真严禁宣称无碰撞通过；3. 数学与力学公式直接给出清晰分步推导。"
)

_G00_PLUNGE_RE = re.compile(r"\bG0*0\b[^\n]*Z-")
_G71_PQ_RE = re.compile(r"\bG71\b[^\n]*P\d+[^\n]*Q\d+")
_G70_PQ_RE = re.compile(r"\bG70\b[^\n]*P\d+[^\n]*Q\d+")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if s:
                rows.append(json.loads(s))
    return rows


def _row_text(row: Dict[str, Any]) -> str:
    if "messages" in row:
        return "\n".join(str(m.get("content") or "") for m in row.get("messages") or [])
    prompt = row.get("prompt") or []
    parts = [str(m.get("content") or "") for m in prompt]
    parts.extend([str(row.get("chosen") or ""), str(row.get("rejected") or "")])
    return "\n".join(parts)


def _sys_prompt(idx: int) -> str:
    return SYSTEM_PROMPT_SIX_SW if (idx % 3 == 0) else SYSTEM_PROMPT_CONCISE


def _sft_row(user_text: str, assistant_text: str, *, family: str, software: str, sys_idx: int) -> Dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": _sys_prompt(sys_idx)},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ],
        "meta": {
            "task_type": "v2_canonical_anti_regression",
            "family": family,
            "software": software,
            "basis": "closed_form_verified",
            "split": "train_v2_anchor",
        },
    }


def _dpo_row(
    user_text: str,
    chosen: str,
    rejected: str,
    *,
    category: str,
    software: str,
    sys_idx: int,
) -> Dict[str, Any]:
    return {
        "prompt": [
            {"role": "system", "content": _sys_prompt(sys_idx)},
            {"role": "user", "content": user_text},
        ],
        "chosen": chosen,
        "rejected": rejected,
        "category": category,
        "software": software,
        "source": "v2_anti_regression_dpo",
        "basis": "closed_form_verified",
    }


def _lame_solve(di: float, do: float, pi: float) -> Dict[str, float]:
    ri = di / 2.0
    ro = do / 2.0
    k = (do / di) ** 2
    a = pi / (k - 1.0)
    b = a * (ro ** 2)
    b_ri2 = b / (ri ** 2)
    sig_t_in = a + b_ri2
    sig_r_in = a - b_ri2
    sig_t_out = a + b / (ro ** 2)
    sig_r_out = a - b / (ro ** 2)
    rmid = (ri + ro) / 2.0
    sig_t_mid = a + b / (rmid ** 2)
    sig_r_mid = a - b / (rmid ** 2)
    return {
        "di": di,
        "do": do,
        "ri": ri,
        "ro": ro,
        "rmid": rmid,
        "pi": pi,
        "k": k,
        "A": a,
        "B": b,
        "B_ri2": b_ri2,
        "sig_t_in": sig_t_in,
        "sig_r_in": sig_r_in,
        "sig_t_out": sig_t_out,
        "sig_r_out": sig_r_out,
        "sig_t_mid": sig_t_mid,
        "sig_r_mid": sig_r_mid,
    }


def _build_v2_lame_sft_rows() -> List[Dict[str, Any]]:
    """Build 26 distinct closed-form Lamé SFT examples (strictly excluding Di=60,Do=120,Pi=20)."""
    specs: List[Tuple[float, float, float]] = [
        (30, 90, 16), (32, 64, 30), (36, 108, 28), (44, 110, 21),
        (48, 120, 14), (56, 112, 22), (64, 160, 26), (72, 144, 19),
        (75, 150, 27), (84, 168, 32), (90, 150, 16), (96, 192, 24),
        (100, 200, 12), (110, 220, 35), (120, 240, 28), (60, 90, 15),
        (80, 120, 18), (50, 75, 12), (42, 126, 24), (66, 132, 17),
        (54, 108, 21), (88, 176, 16), (45, 90, 27), (100, 160, 22),
        (60, 150, 25), (38, 76, 19),
    ]
    rows: List[Dict[str, Any]] = []
    for idx, (di, do, pi) in enumerate(specs):
        if (di, do, pi) == (60, 120, 20):
            raise RuntimeError("Deploy probe geometry (60, 120, 20) must never appear in training")
        v = _lame_solve(di, do, pi)
        mode = idx % 4
        if mode == 0:
            user = (
                f"厚壁圆筒受内压工况（外压 p_o = 0）：内径 D_i = {di} mm，外径 D_o = {do} mm，"
                f"内压 p_i = {pi} MPa。按 Lamé 公式求内壁处的环向应力 σ_θ 与径向应力 σ_r（单位 MPa，保留 2 位小数）。"
            )
            asst = (
                f"由 Lamé 厚壁圆筒理论（p_o = 0，内半径 r_i = {v['ri']:.1f} mm，外半径 r_o = {v['ro']:.1f} mm）：\n"
                f"1. 径比平方：k = (D_o / D_i)^2 = ({do} / {di})^2 = {v['k']:.4f}\n"
                f"2. Lamé 常数：\n"
                f"   A = p_i / (k - 1) = {pi} / ({v['k']:.4f} - 1) = {v['A']:.4f} MPa\n"
                f"   B / r_i^2 = p_i * k / (k - 1) = {pi} * {v['k']:.4f} / ({v['k']:.4f} - 1) = {v['B_ri2']:.4f} MPa\n"
                f"3. 内壁 (r = r_i) 应力（注意 σ_θ = A + B/r^2，σ_r = A - B/r^2）：\n"
                f"   - 环向应力（拉应力）：σ_θ = A + B/r_i^2 = p_i * (k + 1) / (k - 1) = {v['sig_t_in']:.2f} MPa\n"
                f"   - 径向应力（压应力）：σ_r = A - B/r_i^2 = -p_i = {v['sig_r_in']:.2f} MPa"
            )
        elif mode == 1:
            user = (
                f"请用 Lamé 解析解校核压力容器筒体（D_i={di} mm，D_o={do} mm，仅受内压 p_i={pi} MPa）："
                f"写出 Lamé 常数 A、B，并给出内壁 (r={v['ri']:.1f} mm) 与外壁 (r={v['ro']:.1f} mm) 的环向与径向应力。"
            )
            asst = (
                f"已知 r_i = {v['ri']:.1f} mm，r_o = {v['ro']:.1f} mm，k = (r_o/r_i)^2 = {v['k']:.4f}，p_i = {pi} MPa，p_o = 0。\n"
                f"- A = p_i * r_i^2 / (r_o^2 - r_i^2) = p_i / (k - 1) = {v['A']:.2f} MPa\n"
                f"- B = A * r_o^2 = {v['B']:.2f} N（或 MPa·mm^2）\n"
                f"- 内壁 (r = {v['ri']:.1f} mm)：σ_θ = A + B/r_i^2 = {v['sig_t_in']:.2f} MPa，σ_r = A - B/r_i^2 = -p_i = {v['sig_r_in']:.2f} MPa\n"
                f"- 外壁 (r = {v['ro']:.1f} mm)：σ_θ = A + B/r_o^2 = 2A = {v['sig_t_out']:.2f} MPa，σ_r = A - B/r_o^2 = {v['sig_r_out']:.2f} MPa"
            )
        elif mode == 2:
            user = (
                f"计算厚壁圆筒（内径 {di} mm、外径 {do} mm、内压 {pi} MPa）内壁与壁厚中径 r={v['rmid']:.1f} mm 处的 "
                f"σ_θ 和 σ_r（MPa）。"
            )
            asst = (
                f"径比平方 k = ({do}/{di})^2 = {v['k']:.4f}，A = p_i/(k-1) = {v['A']:.4f} MPa，B = A·r_o^2 = {v['B']:.2f} MPa·mm^2。\n"
                f"1. 内壁 r_i = {v['ri']:.1f} mm：σ_θ = p_i*(k+1)/(k-1) = {v['sig_t_in']:.2f} MPa，σ_r = -p_i = {v['sig_r_in']:.2f} MPa；\n"
                f"2. 中径 r = {v['rmid']:.1f} mm：B/r^2 = {v['B'] / (v['rmid']**2):.2f} MPa，"
                f"σ_θ = {v['sig_t_mid']:.2f} MPa，σ_r = {v['sig_r_mid']:.2f} MPa。"
            )
        else:
            user = (
                f"Thick-walled cylinder under internal pressure Pi={pi} MPa (Po=0), "
                f"inner diameter Di={di} mm, outer diameter Do={do} mm. "
                f"Compute inner-wall hoop stress σ_θ and radial stress σ_r in MPa using Lamé equations."
            )
            asst = (
                f"With Di={di} mm (ri={v['ri']:.1f} mm), Do={do} mm (ro={v['ro']:.1f} mm), Pi={pi} MPa:\n"
                f"- Diameter ratio squared: k = (Do/Di)^2 = {v['k']:.4f}\n"
                f"- Lamé constants: A = Pi/(k-1) = {v['A']:.4f} MPa, B/ri^2 = Pi*k/(k-1) = {v['B_ri2']:.4f} MPa\n"
                f"- Inner wall (r = ri): σ_θ = A + B/ri^2 = Pi*(k+1)/(k-1) = {v['sig_t_in']:.2f} MPa; "
                f"σ_r = A - B/ri^2 = -Pi = {v['sig_r_in']:.2f} MPa."
            )
        rows.append(_sft_row(user, asst, family="lame_closed_form", software="cae", sys_idx=idx))
    return rows


def _verify_nc_program_safe(nc_text: str) -> None:
    if not _G71_PQ_RE.search(nc_text):
        raise AssertionError(f"Generated NC missing valid G71 P.. Q..:\n{nc_text}")
    if not _G70_PQ_RE.search(nc_text):
        raise AssertionError(f"Generated NC missing G70 P.. Q..:\n{nc_text}")
    if "G50 S" not in nc_text or "M30" not in nc_text or "M03" not in nc_text:
        raise AssertionError(f"Generated NC missing G50/M03/M30:\n{nc_text}")
    for line in nc_text.splitlines():
        if _G00_PLUNGE_RE.search(line):
            raise AssertionError(f"Generated NC has unsafe G00 negative-Z plunge: {line!r}")


def _build_v2_fanuc_g71_sft_rows() -> List[Dict[str, Any]]:
    """Build 26 distinct FANUC G71+G70 step-turning SFT examples (strictly excluding Ø60/Ø38/L20/L45)."""
    # (bar_d, d1, l1, d2, l2_total, g50, css_s, feed, tool, p_no, q_no, prog_no, chamfer)
    specs: List[Tuple[int, int, int, int, int, int, int, float, str, int, int, str, float]] = [
        (55, 36, 18, 48, 42, 1800, 150, 0.22, "T0101", 10, 20, "O1011", 0.0),
        (68, 40, 24, 58, 52, 2000, 160, 0.25, "T0101", 10, 30, "O1012", 1.0),
        (75, 46, 26, 66, 58, 1600, 140, 0.28, "T0202", 100, 200, "O1013", 0.0),
        (82, 50, 30, 72, 65, 1500, 130, 0.24, "T0101", 10, 20, "O1014", 1.5),
        (48, 28, 16, 42, 36, 2200, 170, 0.20, "T0101", 10, 20, "O1015", 0.0),
        (90, 56, 32, 78, 70, 1500, 135, 0.30, "T0303", 10, 30, "O1016", 2.0),
        (62, 34, 22, 54, 48, 1900, 155, 0.22, "T0101", 10, 20, "O1017", 0.0),
        (52, 30, 15, 45, 38, 2100, 165, 0.18, "T0202", 10, 20, "O1018", 1.0),
        (85, 48, 28, 70, 62, 1700, 145, 0.25, "T0101", 10, 20, "O1019", 0.0),
        (72, 42, 25, 62, 54, 1800, 150, 0.24, "T0101", 10, 30, "O1020", 1.5),
        (44, 24, 14, 36, 32, 2400, 180, 0.18, "T0101", 10, 20, "O1021", 0.0),
        (95, 60, 35, 82, 75, 1400, 125, 0.28, "T0101", 10, 20, "O1022", 0.0),
        (58, 35, 19, 50, 44, 2000, 155, 0.22, "T0101", 10, 20, "O1023", 1.0),
        (66, 38, 21, 56, 49, 1850, 150, 0.25, "T0202", 10, 20, "O1024", 0.0),
        (78, 45, 27, 68, 56, 1650, 145, 0.26, "T0101", 100, 200, "O1025", 1.5),
        (88, 52, 31, 76, 66, 1600, 140, 0.25, "T0101", 10, 20, "O1026", 0.0),
        (46, 26, 16, 38, 34, 2300, 175, 0.20, "T0303", 10, 20, "O1027", 0.0),
        (100, 62, 36, 88, 80, 1400, 120, 0.30, "T0101", 10, 30, "O1028", 2.0),
        (54, 33, 17, 46, 41, 2000, 160, 0.21, "T0101", 10, 20, "O1029", 0.0),
        (63, 40, 23, 55, 51, 1800, 150, 0.24, "T0101", 10, 20, "O1030", 1.0),
        (74, 44, 24, 65, 57, 1700, 145, 0.25, "T0101", 10, 20, "O1031", 0.0),
        (84, 54, 29, 74, 64, 1550, 135, 0.27, "T0202", 100, 200, "O1032", 0.0),
        (49, 30, 18, 41, 39, 2100, 165, 0.19, "T0101", 10, 20, "O1033", 1.0),
        (92, 58, 34, 80, 72, 1500, 130, 0.28, "T0101", 10, 20, "O1034", 0.0),
        (67, 41, 22, 59, 53, 1800, 150, 0.23, "T0101", 10, 20, "O1035", 0.0),
        (76, 47, 26, 67, 59, 1600, 145, 0.26, "T0101", 10, 30, "O1036", 1.5),
    ]
    rows: List[Dict[str, Any]] = []
    for idx, (bar_d, d1, l1, d2, total_l, g50, css_s, feed, tool, p_no, q_no, prog_no, ch) in enumerate(specs):
        if (bar_d, d1, l1, total_l) == (60, 38, 20, 45):
            raise RuntimeError("Deploy probe turning profile must never appear in training")
        fin_tool = "T0202" if tool == "T0101" else "T0404"
        mid_n = (p_no + q_no) // 2
        if ch > 0:
            d1_lead = max(d1 - 2.0 * ch, 6.0)
            contour = (
                f"N{p_no} G00 X{d1_lead:.1f}\n"
                f"G01 Z0.0 F0.12\n"
                f"X{d1:.1f} Z-{ch:.1f}\n"
                f"N{mid_n} G01 Z-{l1:.1f}\n"
                f"X{d2:.1f}\n"
                f"N{q_no} G01 Z-{total_l:.1f}"
            )
        else:
            contour = (
                f"N{p_no} G00 X{d1:.1f}\n"
                f"G01 Z0.0 F0.12\n"
                f"N{mid_n} G01 Z-{l1:.1f}\n"
                f"X{d2:.1f}\n"
                f"N{q_no} G01 Z-{total_l:.1f}"
            )
        nc = (
            f"%\n{prog_no}\n"
            f"G21 G40 G99\n"
            f"G50 S{g50}\n"
            f"{tool}\n"
            f"G96 S{css_s} M03\n"
            f"M08\n"
            f"G00 X{bar_d + 2:.1f} Z2.0\n"
            f"G71 U1.5 R0.5\n"
            f"G71 P{p_no} Q{q_no} U0.4 W0.1 F{feed:.2f}\n"
            f"{contour}\n"
            f"G00 X{bar_d + 30:.1f} Z80.0\n"
            f"{fin_tool}\n"
            f"G96 S{css_s + 30} M03\n"
            f"G00 X{bar_d + 2:.1f} Z2.0\n"
            f"G70 P{p_no} Q{q_no} F0.12\n"
            f"M09\n"
            f"G00 X{bar_d + 40:.1f} Z100.0\n"
            f"M05\n"
            f"M30\n%"
        )
        _verify_nc_program_safe(nc)
        chamfer_note = f"前缘倒角 C{ch:.1f}、" if ch > 0 else ""
        if idx % 3 == 0:
            user = (
                f"为 Ø{bar_d} mm 棒料编写 FANUC 0i-TF 外圆车削程序：{chamfer_note}"
                f"第一台阶 Ø{d1} mm 长 {l1} mm，第二台阶 Ø{d2} mm，总长 {total_l} mm。"
                f"要求用 {tool}、G50 S{g50}、G96 S{css_s} M03、进给 F{feed:.2f} mm/r，"
                f"使用规范两行 G71 粗车+G70 精车并确保无 G00 Z 负向扎刀。"
            )
        elif idx % 3 == 1:
            user = (
                f"FANUC 车床编程：毛坯 Ø{bar_d}，加工两级台阶轴（{chamfer_note}Ø{d1}×{l1} mm + Ø{d2} 总长 {total_l} mm），"
                f"主轴限速 G50 S{g50}，恒线速 G96 S{css_s} M03，{tool} 进给 F{feed:.2f}。请输出完整安全 NC 程序（含 M30）。"
            )
        else:
            user = (
                f"Generate a safe FANUC turning NC program for a Ø{bar_d} mm bar: "
                f"step 1 Ø{d1} mm L={l1} mm, step 2 Ø{d2} mm to total L={total_l} mm "
                f"using {tool}, G50 S{g50}, G96 S{css_s} M03, F{feed:.2f}, two-line G71/G70 cycles, and M30."
            )
        asst = (
            f"完整安全的 FANUC G71/G70 车削程序如下：\n```nc\n{nc}\n```\n"
            f"安全核验要点：\n"
            f"- 恒线速配 `G50 S{g50}` + `G96 S{css_s} M03`，避免小直径超速飞车；\n"
            f"- `G00` 定位与退刀均停留在 `Z+2.0`/`Z+80.0`/`Z+100.0` 安全正值区，轮廓首段 `N{p_no}` 仅做径向定位，杜绝 `G00 Z-` 快速扎刀；\n"
            f"- 两行 `G71` 完整绑定 `P{p_no} Q{q_no}` 并配 `G70 P{p_no} Q{q_no}` 精车与 `M30` 复位。"
        )
        rows.append(_sft_row(user, asst, family="fanuc_g71_safety", software="cimco_sscnc", sys_idx=idx + 1))
    return rows


def _build_v2_autodiff_sft_rows() -> List[Dict[str, Any]]:
    """Build 22 distinct VERICUT 9.6 Auto-Diff color/triage SFT examples."""
    scenarios: List[Tuple[str, str]] = [
        (
            "VERICUT 9.6 Auto-Diff 比较报告出现红色、蓝色、绿色三种颜色，请逐条给出严格物理含义及机床加工现场的对应处置措施。",
            "VERICUT 9.6 Auto-Diff 色谱严格对应以下工程判定（不可颠倒）：\n"
            "1. **红色 (Red) = 过切 / 超切 / 碰撞 (Gouge / Overcut)**：刀具切入设计成品模型内部，属于致命报废缺陷。处置：**必须立即停止**仿真与上机，排查刀偏/长度补偿、夹具干涉与切入路径并**修改刀路 / NC 程序**。\n"
            "2. **蓝色 (Blue) = 残料 / 欠切 / 余量未切净 (Excess Material / Undercut)**：毛坯留有未切除余量。处置：按公差要求**增加半精/精加工刀路**、清根刀路或调小留量。\n"
            "3. **绿色 (Green) = 在公差带内合格 (In-Tolerance / Pass)**：加工表面与设计模型偏差满足公差要求（前提：非空白/未渲染图且无任何红色过切）。",
        ),
        (
            "解释 VERICUT Auto-Diff 偏差云图中 Red、Blue、Green 三色定义与工程结论。",
            "- **红色 (Red)**：过切 (Gouge / Overcut) —— 刀具已侵犯设计模型边界，属**致命缺陷**，必须**立即停机并修改刀路**；\n"
            "- **蓝色 (Blue)**：残料 / 欠切 (Excess Material) —— 存在未切除多余材料，需**补充半精/精加工刀路**或清角；\n"
            "- **绿色 (Green)**：合格 (In-Tolerance) —— 处于允许公差范围内，在有效渲染像素与日志核验均无误后方可放行。",
        ),
        (
            "在 VERICUT Auto-Diff 中，“红色代表残料、蓝色代表过切”这种说法正确吗？为什么？",
            "完全错误，属于致命的工程语义颠倒！在 VERICUT 9.6 Auto-Diff 默认色谱中：\n"
            "- **红色 (Red) = 过切 / 超切 (Gouge)**（负偏差切进零件内部，致命错误，必须立即停止加工并重修刀路）；\n"
            "- **蓝色 (Blue) = 残料 / 欠切 (Excess Material)**（正偏差尚余材料未切，需补充精加工/清根刀路）；\n"
            "- **绿色 (Green) = 合格 (In-Tolerance)**（偏差在设计公差允许区间内）。\n若将红蓝颠倒，会把过切报废件误当成“留有余量”继续精加工，造成严重生产事故。",
        ),
        (
            "某箱体零件 VERICUT Auto-Diff 统计：Green=96.2%，Red=0.6%（侧壁最大 -0.22 mm），Blue=3.2%。是否可凭高绿色占比直接放行？",
            "绝对不可放行！判定为 **FAIL（致命过切拒绝）**：\n"
            "- **红色 (Red=0.6%)** 代表**过切 (Gouge)** 切入设计模型 -0.22 mm，属于一票否决致命缺陷，即使绿色超过 96% 也必须**立即停止并修改对应槽/侧壁精加工刀路或刀补**；\n"
            "- **蓝色 (Blue=3.2%)** 为局部**残料 (Excess)**，修好过切后需顺带补充半精/精加工清角；\n"
            "- 只有 Red = 0 且有效像素完整渲染、Green 处于公差内方可放行。",
        ),
        (
            "VERICUT Auto-Diff 分析得到：Green=82.5%，Red=0.0%，Blue=17.5%（内拐角最大 +0.40 mm）。当前缺陷属于过切还是残料？如何处理？",
            "属于**残料 / 欠切 (Excess Material)**，不存在过切：\n"
            "- **红色 (Red=0.0%)** 为零，未发生过切或碰撞；\n"
            "- **蓝色 (Blue=17.5%, +0.40 mm)** 表示拐角处仍有未切除的**残料 (Excess)**，不可直接出货，需**换用更小直径刀具并增加半精/精加工清根刀路**，切至**绿色 (Green, In-Tolerance)** 后再复核。",
        ),
        (
            "如果 Auto-Diff 截图读取显示有效渲染像素为 0（空白视窗 / 默认底色绿占 100%），能否直接给出 PASS？",
            "绝对不能判 PASS！应返回 `INSUFFICIENT_EVIDENCE`：\n"
            "- VERICUT Auto-Diff **绿色**仅代表实体与设计模型在公差内吻合，前提是已完成真实实体比较并有足够**有效渲染像素**；\n"
            "- 有效像素为 0 的未渲染图绝不能因绿色占 100% 而伪造通过，必须重新导出真实 Auto-Diff 视图并结合 `vericut.log` 交叉复核（Red=过切须停机、Blue=残料须补加工、Green=公差内合格）。",
        ),
        (
            "In VERICUT 9.6 Auto-Diff inspection, what do Red, Blue, and Green colors indicate and what action is required for each?",
            "In VERICUT 9.6 Auto-Diff deviation analysis:\n"
            "- **Red = Gouge / Overcut (过切)**: Tool penetrated inside the design model (negative deviation). **Fatal error — immediately stop and fix/modify the toolpath or tool offsets.**\n"
            "- **Blue = Excess Material / Undercut (残料)**: Stock remains above tolerance (positive deviation). **Add semi-finish / finish or rest-machining passes.**\n"
            "- **Green = In-Tolerance (合格)**: Machined surface meets target tolerance limits with zero red gouges.",
        ),
        (
            "用表格总结 VERICUT 9.6 Auto-Diff 红/蓝/绿三色含义、偏差方向与工程闭环动作。",
            "| 颜色 | 严格含义 | 偏差特征 | 工程处置与门禁 |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| **红色 (Red)** | 过切 / 碰撞 (Gouge) | 切入设计模型（负偏差） | **致命拦截：立即停止，排查刀补并修改刀路** |\n"
            "| **蓝色 (Blue)** | 残料 / 欠切 (Excess) | 表面留有未切余量（正偏差） | **不放行：增加半精/精加工或清角刀路** |\n"
            "| **绿色 (Green)** | 公差内合格 (In-Tolerance) | 位于设定过切/欠切公差带内 | 确认非空白图且零红色过切后放行 |",
        ),
    ]
    # Expand cleanly with 14 unique quantitative Auto-Diff triage scenarios
    quant_cases: List[Tuple[str, float, float, float, float, float, str]] = [
        ("主轴箱体壳体", 94.1, 0.9, 5.0, -0.31, 0.25, "FAIL_RED_GOUGE"),
        ("航空支架肋板", 91.4, 0.0, 8.6, 0.0, 0.38, "EXCESS_BLUE_REMILL"),
        ("伺服电机端盖", 99.6, 0.0, 0.4, 0.0, 0.02, "PASS_IN_TOLERANCE"),
        ("减速器法兰盘", 97.5, 0.45, 2.05, -0.15, 0.12, "FAIL_RED_GOUGE"),
        ("模具动模型腔", 84.8, 0.0, 15.2, 0.0, 0.55, "EXCESS_BLUE_REMILL"),
        ("液压阀块油孔面", 95.3, 1.15, 3.55, -0.42, 0.18, "FAIL_RED_GOUGE"),
        ("联轴器套筒槽", 88.9, 0.0, 11.1, 0.0, 0.29, "EXCESS_BLUE_REMILL"),
        ("涡轮叶盘叶根槽", 98.8, 0.22, 0.98, -0.09, 0.06, "FAIL_RED_GOUGE"),
        ("锂电池托盘加强筋", 86.4, 0.0, 13.6, 0.0, 0.48, "EXCESS_BLUE_REMILL"),
        ("五轴叶轮流道曲面", 93.7, 0.75, 5.55, -0.27, 0.33, "FAIL_RED_GOUGE"),
        ("精密导轨滑块", 99.4, 0.0, 0.6, 0.0, 0.03, "PASS_IN_TOLERANCE"),
        ("机器人关节谐波壳", 89.2, 0.0, 10.8, 0.0, 0.36, "EXCESS_BLUE_REMILL"),
        ("数控车复合夹具座", 96.9, 0.52, 2.58, -0.19, 0.14, "FAIL_RED_GOUGE"),
        ("光学镜筒安装座", 99.7, 0.0, 0.3, 0.0, 0.015, "PASS_IN_TOLERANCE"),
    ]
    rows: List[Dict[str, Any]] = []
    for idx, (usr, ans) in enumerate(scenarios):
        rows.append(_sft_row(usr, ans, family="autodiff_triage", software="vericut", sys_idx=idx + 2))
    for j, (part, g, r, b, r_dev, b_dev, verdict) in enumerate(quant_cases):
        usr = (
            f"对 `{part}` 运行 VERICUT 9.6 Auto-Diff（过切阈值 -0.05 mm，残料阈值 +0.05 mm，有效渲染像素 148,200）："
            f"测量分布 Green={g:.1f}%、Red={r:.2f}%（最大负偏差 {r_dev:+.2f} mm）、Blue={b:.2f}%（最大正偏差 +{b_dev:.3f} mm）。"
            f"请给出三色定义与本件最终处置建议。"
        )
        if verdict == "FAIL_RED_GOUGE":
            conclusion = (
                f"**结论：致命拦截（FAIL — 存在红色过切）**\n"
                f"因红色区 ({r:.2f}%, {r_dev:+.2f} mm) 代表**过切 (Gouge)**，即使 Green={g:.1f}% 也不可放行，"
                f"必须**立即停止**加工并修改过切刀路/刀偏；蓝色区 ({b:.2f}%, +{b_dev:.3f} mm) 属**残料 (Excess)** 需一并补半精/精加工。"
            )
        elif verdict == "EXCESS_BLUE_REMILL":
            conclusion = (
                f"**结论：需补加工（EXCESS — 局部蓝色残料，无过切）**\n"
                f"红色**过切 (Gouge)** 为 0.00%，未破坏设计轮廓；但蓝色区 ({b:.2f}%, +{b_dev:.3f} mm) 代表**残料 (Excess Material)** 超差，"
                f"需**增加半精/精加工刀路**清除余量后重跑 Auto-Diff 复核至**绿色合格 (In-Tolerance)**。"
            )
        else:
            conclusion = (
                f"**结论：公差内合格（PASS — 零红色过切，绿色达标）**\n"
                f"有效渲染像素 148,200 非空，红色**过切 (Gouge)** = 0.00%，蓝色**残料 (Excess)** 最大 +{b_dev:.3f} mm ≤ 0.05 mm，"
                f"主要表面为**绿色公差内合格 (In-Tolerance)**，可进入下一工序。"
            )
        ans = (
            f"VERICUT Auto-Diff 判定基准：红色=过切 (Gouge/致命停机修刀路)、蓝色=残料 (Excess/补精加工)、绿色=公差内合格 (In-Tolerance)。\n"
            f"{conclusion}"
        )
        rows.append(_sft_row(usr, ans, family="autodiff_triage", software="vericut", sys_idx=j))
    return rows


def _build_v2_coord_unit_sft_rows() -> List[Dict[str, Any]]:
    """Build 10 distinct coordinate-system / unit isolation / G00 plunge safety SFT anchors."""
    items: List[Tuple[str, str]] = [
        (
            "将 SOLIDWORKS 2021 的 Y-up 零件导入 VERICUT 9.6（Z-up）铣削夹具时，若未绕 X 轴旋转 +90° 会导致什么后果？如何预防？",
            "SOLIDWORKS 2021 世界向上轴为 **+Y（Top Plane 法向 +Y，Front=XY，Right=YZ）**，而 VERICUT/CNC 机床默认 **+Z 向上**。\n"
            "若直接导入而不对齐坐标系，零件会在机床上横卧 90°，G54 平面与 Z 轴切深方向完全错位并引发撞刀。\n"
            "预防措施：导出 STEP/STL 前在 SOLIDWORKS 新建 Z-up 导出坐标系并在导出选项选中它，或在 VERICUT Stock/Design Attach 节点显式校验轴向旋转。",
        ),
        (
            "阅读到旧 CNC 程序片段 `G00 X32.0 Z-24.0` 时，为什么静态安全审查直接判为高危阻塞项？应该怎么改写？",
            "`G00` 为机床最大速度**快速移动**，同行带有负向 `Z-24.0` 意味刀尖将高速斜插撞入毛坯或卡盘（`unsafe_G00_negative_Z_plunge`）。\n"
            "正确改写：\n"
            "1. 先用 `G00 X32.0 Z2.0` 快速退/进至零件端面前安全正值区（`Z >= 0`）；\n"
            "2. 再切入模态 `G01 Z-24.0 F0.18` 按进给速度稳态切削。",
        ),
        (
            "读取 SolidWorks API `ISolidWorksInformation` / `GetMassProperties` 返回体积 `2.45e-4`、面积 `0.038`，能否直接写为 `245000 mm` 或当成毫米数输出？",
            "不能混算！SolidWorks COM API 内部统一返回 **MKS 国际单位制（m, m², m³, kg）**：\n"
            "- 体积 `2.45e-4 m³ = 2.45e-4 × 10⁹ = 245,000.0 mm³`（切勿错记成 mm）；\n"
            "- 面积 `0.038 m² = 0.038 × 10⁶ = 38,000.0 mm²`；\n"
            "输出工程报告时必须显式标注单位换算关系并保证 `volume_mm3` 与 `surface_area_mm2` 量纲一致。",
        ),
        (
            "VERICUT 工程 `.vcproject` 标明 `<Unit>inch</Unit>` 且刀长 4.250，可否静默乘以 25.4 后改写为 millimeter 且假称文件原本是公制？",
            "严禁静默篡改源单位！必须原样保留 `<Unit>inch</Unit>` 与原始数值 `4.250 inch`；"
            "若下游公制工序确需毫米参考值，须同时双标原值与显式换算 `4.250 inch = 107.95 mm (1 inch = 25.4 mm)`，"
            "并在 CNC 代码端匹配 `G20`（英制）或核实后切换 `G21`（公制）。",
        ),
        (
            "在 NX 12.0 CAM 加工导航器中完成刀路生成准备后处理输出 NC，发现某工序旁存在黄色叹号或红色禁止警告标志，能否直接后处理？",
            "不能直接后处理导出！操作导航器中的警告/叹号表明刀轨过时、未生成或存在几何/余量/干涉校验异常。"
            "必须先重新生成刀轨（Generate Tool Path）、消除全部警告并用 Verify 确认无碰撞后再执行后处理。",
        ),
        (
            "AutoCAD 2026 生成 CNC 用二维底图或工艺蓝图时，哪些标准图层必须严格区分且不得混放尺寸线与轮廓线？",
            "按 GB 制图规范严格分层：`OUTLINE`（粗实线产品轮廓）、`DIM`（尺寸与形位公差标注）、"
            "`HIDDEN`（虚线隐藏轮廓）、`CENTER`（点划线中心线/孔轴线）、`HATCH`（剖面线）、`TITLE_BLOCK`（图框与标题栏）。"
            "导出 DXF 前还须检查视图边界包络并核查文字-尺寸线无重叠。",
        ),
        (
            "在 CIMCO Edit 2026 验证 FANUC Macro B 宏程序（如 `#100`, `#500`, `WHILE [...] DO1 ... END1`）时，重点排查哪三类风险？",
            "1. `WHILE/DO/END` 循环标号配对与退出条件防死循环；\n"
            "2. 公共变量 `#500+` 与局部变量 `#100` 跨刀段覆盖冲突及未初始化空变量计算；\n"
            "3. 三维刀路轨迹反演中 `G00` 快移是否有负向 `Z-` 直接扎入毛坯包络的干涉轨迹。",
        ),
        (
            "斯沃数控仿真 SSCNC 7.2（FANUC 0i-TF）完成 T0101 外圆刀偏输入后，按下循环启动前必须现场确认哪些状态？",
            "1. 面板模式开关已正确切换至 **`AUTO`**（而非 `EDIT`/`JOG`/`MDI`）；\n"
            "2. CRT 屏幕 **`ABSOLUTE / G54`** 工件坐标系与刀偏表 `T0101`（含刀尖半径 `R` 与假想刀尖象限 `T3`）已写入并激活；\n"
            "3. 首刀试切火花对刀边界无异常且单段/低倍率空跑验证 `G00` 无扎刀干涉。",
        ),
        (
            "Why must `G71` Type I rough turning profiles put only an X coordinate (no Z move) on the `N<P>` start block?",
            "In FANUC Type I `G71`, the `N<P>` start block establishes the radial X start of the finished profile (`G00 X<diameter>` without `Z`), "
            "while `N<P+1>` through `N<Q>` sweep axially along Z (`G01 Z-...`). Putting both X and Z on `N<P>` switches into Type II pocket turning "
            "and risks rapid plunge alarms or incorrect stock clearance.",
        ),
        (
            "如何判定惯性矩字段 `inertia_ixx_mm4` 的量纲是否合法？常见把什么错误算成了 mm⁴？",
            "截面对称轴惯性矩必须为长度四次方 `mm⁴`：例如矩形截面对 X 轴 `I_xx = w·h³/12`，"
            "实心圆柱绕中心轴极惯性矩 `I_zz = π·r⁴/2`、径向惯性矩 `I_xx = π·r⁴/4`。"
            "常见错误是把体积 `V (mm³)` 再乘以 `h²/12`，得出 `mm⁵` 量纲却错标成 `inertia_ixx_mm4`。",
        ),
    ]
    return [
        _sft_row(u, a, family="coordinate_unit_safety", software="six_software", sys_idx=i)
        for i, (u, a) in enumerate(items)
    ]


def _build_v2_targeted_dpo_rows() -> List[Dict[str, Any]]:
    """Build 44 distinct DPO contrast pairs directly targeting v1 regressions."""
    pairs: List[Dict[str, Any]] = []

    # 1. Auto-Diff Red vs Blue vs Green (15 pairs)
    autodiff_prompts = [
        ("VERICUT Auto-Diff 图像中红色、蓝色、绿色分别表示什么？", "99.1%绿+0.9%红(-0.22mm)"),
        ("在 VERICUT 9.6 Auto-Diff 偏差色谱检测中，如何精准解读 Red、Blue、Green 三色？", "92.0%绿+8.0%蓝(+0.35mm)"),
        ("VERICUT Auto-Diff 显示绿色 94.5%、红色 1.2%、蓝色 4.3%，各自代表什么及如何处置？", "主特征面过切"),
        ("比较 VERICUT Auto-Diff 中红色区域与蓝色区域的本质区别，并说明能否用绿色比例掩盖红色。", "通用对比"),
        ("Explain what Red, Blue, and Green mean in VERICUT 9.6 Auto-Diff and required actions.", "EN standard"),
        ("如果 VERICUT Auto-Diff 仅显示蓝色正偏差 +0.28 mm 而无任何红色像素，这是过切还是残料？", "纯蓝色"),
        ("若箱体底面在 VERICUT Auto-Diff 呈明显红色（-0.19 mm），现场应继续精加工还是停机修刀路？", "红色过切"),
        ("VERICUT 仿真结束弹出 Auto-Diff 结果，Red/Blue/Green 的一票否决规则是什么？", "门禁规则"),
        ("面对 Auto-Diff 报告：Green=97.0%, Red=0.4%, Blue=2.6%，某同事说红色只是余量没切完可以直接加刀路磨掉，对吗？", "纠偏"),
        ("某空白未渲染的 Auto-Diff 图返回绿色像素占全部视窗背景但有效实体像素=0，能否判合格？", "空图防伪"),
        ("VERICUT Auto-Diff 里为什么蓝色可以补刀路救回，而红色必须立刻停机报废或改程序？", "工程后果"),
        ("请写出 VERICUT Auto-Diff 三色故障定位口诀与规范处置清单。", "清单"),
        ("How do you distinguish Gouge vs Excess Material in VERICUT Auto-Diff color mapping?", "EN distinction"),
        ("在五轴叶轮 VERICUT Auto-Diff 校验中，叶片表面出现局部红色与根部局部蓝色，分别是什么缺陷？", "五轴叶轮"),
        ("审校一段 CNC 后置验证结论时，遇到『Auto-Diff 红=残料、蓝=过切』应如何修正？", "术语纠正"),
    ]
    for idx, (usr, _tag) in enumerate(autodiff_prompts):
        if "空白" in usr or "有效实体像素=0" in usr:
            chosen = (
                "绝对不能判合格！有效实体像素为 0 属于未渲染空白截图，必须判定为 `INSUFFICIENT_EVIDENCE`。"
                "VERICUT Auto-Diff 中：绿色=在公差带内合格（前提为真实有效比较）、红色=致命过切（须立即停止并修刀路）、"
                "蓝色=残料/欠切（须补精加工刀路）。"
            )
            rejected = (
                "绿色占比达到 100% 说明零件表面完全处于设计公差带内，无任何红色过切或蓝色残料，"
                "Auto-Diff 检验直接通过（PASS）。"
            )
        elif idx % 3 == 0:
            chosen = (
                "在 VERICUT 9.6 Auto-Diff 中严格定义为：\n"
                "- **红色 (Red) = 过切 / 超切 (Gouge)**：刀具切入设计模型内部（负偏差），属致命缺陷，**必须立即停止加工并修改刀路/刀补**，绝不能以绿色比例高掩盖；\n"
                "- **蓝色 (Blue) = 残料 / 欠切 (Excess Material)**：留有未切除余量（正偏差），需**增加半精/精加工刀路**清除；\n"
                "- **绿色 (Green) = 公差带内合格 (In-Tolerance)**：加工表面满足设定公差要求（前提为有效渲染图像且零红色过切）。"
            )
            rejected = (
                "VERICUT Auto-Diff 中：红色代表存在未切除的残料（需要再切削余量），"
                "蓝色代表过切（刀具切入过深），绿色代表合格。只要绿色占比超过 95% 即可正常放行。"
            )
        elif idx % 3 == 1:
            chosen = (
                "切勿颠倒红蓝定义：VERICUT Auto-Diff 规定 **红色 = 过切 (Gouge)**（侵入设计实体，致命错误须立即停机修刀路）、"
                "**蓝色 = 残料 (Excess Material)**（尚有余量未切完，须补精加工刀路）、**绿色 = 合格 (In-Tolerance)**。"
                "若存在红色区域则判定整体不通过；若仅存在蓝色则可补充清角/精加工刀路。"
            )
            rejected = (
                "蓝色表示材料已被过早切除造成过切报废，无法通过后续加工挽回；"
                "红色表示表面多出残料未被切除，继续走一刀精加工即可消除红色区域。"
            )
        else:
            chosen = (
                "In VERICUT 9.6 Auto-Diff: **Red = Gouge / Overcut (过切)** — fatal negative deviation inside design geometry, "
                "must **stop immediately and fix the toolpath**; **Blue = Excess Material / Undercut (残料)** — unmachined stock remaining, "
                "requires **adding semi-finish / finish passes**; **Green = In-Tolerance (公差内合格)**."
            )
            rejected = (
                "In VERICUT Auto-Diff, Red means excess stock left untouched (safe to re-cut), "
                "Blue means gouged/overcut below tolerance, and Green means finished."
            )
        pairs.append(_dpo_row(usr, chosen, rejected, category="autodiff_red_blue_dpo", software="vericut", sys_idx=idx))

    # 2. Lamé Thick-Walled Cylinder (15 pairs, excluding Di=60, Do=120, Pi=20)
    lame_specs: List[Tuple[float, float, float]] = [
        (30, 90, 18), (44, 88, 22), (48, 96, 16), (52, 104, 24), (56, 168, 28),
        (64, 128, 19), (72, 180, 25), (76, 152, 15), (84, 168, 27), (90, 180, 30),
        (96, 192, 14), (100, 150, 20), (108, 216, 26), (40, 120, 32), (80, 200, 21),
    ]
    for j, (di, do, pi) in enumerate(lame_specs):
        if (di, do, pi) == (60, 120, 20):
            raise RuntimeError("Deploy probe geometry leaked into DPO")
        v = _lame_solve(di, do, pi)
        usr = (
            f"厚壁圆筒内径 Di={di} mm、外径 Do={do} mm，仅受内压 Pi={pi} MPa（外压 Po=0）。"
            f"用 Lamé 方程求内壁处的环向应力 σ_θ 与径向应力 σ_r（MPa）。"
        )
        chosen = (
            f"按 Lamé 厚壁圆筒理论：径比平方 k = (Do/Di)^2 = ({do}/{di})^2 = {v['k']:.4f}。\n"
            f"Lamé 常数 A = Pi/(k-1) = {v['A']:.4f} MPa，B/ri^2 = Pi·k/(k-1) = {v['B_ri2']:.4f} MPa。\n"
            f"因此内壁处：\n"
            f"- 环向应力：σ_θ = A + B/ri^2 = Pi·(k+1)/(k-1) = **{v['sig_t_in']:.2f} MPa**（拉应力）\n"
            f"- 径向应力：σ_r = A - B/ri^2 = -Pi = **{v['sig_r_in']:.2f} MPa**（压应力）"
        )
        t_wall = (do - di) / 2.0
        thin_val = pi * di / (2.0 * t_wall)
        if j % 3 == 0:
            # Reject exact v1 A^2 - B^2 hallucination
            rejected = (
                f"取 k = {v['k']:.2f}，求得 Lamé 常数 A = B = -{v['A']:.2f} MPa。\n"
                f"内壁环向应力 σ_θ = A^2 - B^2 = 0.00 MPa，径向应力 σ_r = +{pi:.2f} MPa。"
            )
        elif j % 3 == 1:
            # Reject thin-wall confusion & wrong radial sign
            rejected = (
                f"按圆筒环向应力公式 σ_θ = Pi·Di / (2t) = {pi}×{di}/(2×{t_wall:.1f}) = {thin_val:.2f} MPa，"
                f"内壁径向应力 σ_r = +{pi:.2f} MPa（忽略负号与厚壁效应）。"
            )
        else:
            # Reject inverted ratio k=(Di/Do)^2
            k_inv = (di / do) ** 2
            wrong_sig = pi * (k_inv + 1.0) / (k_inv - 1.0)
            rejected = (
                f"令 k = (Di/Do)^2 = {k_inv:.4f}，代入 σ_θ = Pi·(k+1)/(k-1) = {wrong_sig:.2f} MPa，"
                f"σ_r = 0 MPa。"
            )
        pairs.append(_dpo_row(usr, chosen, rejected, category="lame_closed_form_dpo", software="cae", sys_idx=j + 1))

    # 3. FANUC G71/G70 Safety (12 pairs, excluding Ø60/Ø38/L20/L45)
    cnc_specs: List[Tuple[int, int, int, int, int, int, float]] = [
        (55, 34, 18, 42, 1800, 150, 0.22),
        (68, 42, 24, 52, 2000, 160, 0.24),
        (74, 46, 25, 58, 1700, 145, 0.25),
        (82, 50, 28, 64, 1600, 140, 0.26),
        (48, 28, 16, 36, 2200, 170, 0.20),
        (90, 56, 32, 70, 1500, 135, 0.28),
        (62, 36, 21, 47, 1900, 155, 0.22),
        (52, 31, 17, 39, 2100, 165, 0.19),
        (86, 52, 30, 66, 1550, 135, 0.26),
        (72, 44, 23, 54, 1800, 150, 0.24),
        (65, 39, 22, 49, 1850, 150, 0.25),
        (94, 60, 34, 74, 1450, 130, 0.30),
    ]
    for m, (bar_d, d1, l1, total_l, g50, css_s, feed) in enumerate(cnc_specs):
        if (bar_d, d1, l1, total_l) == (60, 38, 20, 45):
            raise RuntimeError("Deploy probe turning profile leaked into DPO")
        usr = (
            f"请为 Ø{bar_d} 棒料编写 FANUC 车削安全程序：加工台阶 Ø{d1} 长 {l1} mm、外圆 Ø{bar_d - 4} 总长 {total_l} mm，"
            f"指定 G50 S{g50}、G96 S{css_s} M03、T0101、F{feed:.2f}、M30，使用标准 G71+G70 循环。"
        )
        chosen_nc = (
            f"O20{m+10}\nG21 G40 G99\nG50 S{g50}\nT0101\nG96 S{css_s} M03\nM08\n"
            f"G00 X{bar_d + 2:.1f} Z2.0\n"
            f"G71 U1.5 R0.5\nG71 P10 Q20 U0.4 W0.1 F{feed:.2f}\n"
            f"N10 G00 X{d1:.1f}\nG01 Z0.0 F0.12\nG01 Z-{l1:.1f}\nX{bar_d - 4:.1f}\nN20 G01 Z-{total_l:.1f}\n"
            f"G00 X120.0 Z80.0\nT0202\nG96 S{css_s + 30} M03\nG00 X{bar_d + 2:.1f} Z2.0\n"
            f"G70 P10 Q20 F0.12\nM09\nG00 X120.0 Z100.0\nM05\nM30"
        )
        _verify_nc_program_safe(chosen_nc)
        chosen = f"```nc\n{chosen_nc}\n```"
        if m % 3 == 0:
            # Reject single-line invalid G71 U-.. W-.. missing P/Q & M30
            rejected = (
                f"```nc\nG21\nT0101\nG96 S{css_s} M03\nG00 X{bar_d + 2:.1f} Z2.0\n"
                f"G71 U-{l1} W-{total_l} V{feed:.2f}\nG00 X120.0 Z100.0\n```"
            )
        elif m % 3 == 1:
            # Reject G00 rapid negative-Z plunge
            rejected = (
                f"```nc\nO20{m+10}\nT0101\nG96 S{css_s} M03\n"
                f"G00 X{d1:.1f} Z-{l1:.1f}\n"
                f"G71 U1.5 R0.5\nG71 P10 Q20 U0.4 W0.1 F{feed:.2f}\n"
                f"N10 G01 X{d1:.1f}\nN20 Z-{total_l:.1f}\nG70 P10 Q20\nM30\n```"
            )
        else:
            # Reject missing G50 and missing G70 finishing
            rejected = (
                f"```nc\nT0101\nG96 S{css_s} M03\nG00 X{bar_d + 2:.1f} Z2.0\n"
                f"G71 U2.0 R1.0\nG71 P10 Q20 U0.3 W0.1 F{feed:.2f}\n"
                f"N10 G00 X{d1:.1f}\nG01 Z-{l1:.1f}\nX{bar_d - 4:.1f}\nN20 Z-{total_l:.1f}\n"
                f"G00 X120.0 Z100.0\n```"
            )
        pairs.append(_dpo_row(usr, chosen, rejected, category="fanuc_g71_safety_dpo", software="cimco_sscnc", sys_idx=m + 2))

    # 4. Coordinate/Unit DPO (2 pairs)
    pairs.append(
        _dpo_row(
            "SOLIDWORKS 2021 通过 COM API `GetMassProperties` 读回体积 `0.000125`，在公制毫米工程报告中该值代表什么？",
            "SOLIDWORKS COM API 默认使用 MKS 单位制，`0.000125` 单位为 `m³`，"
            "换算成毫米立方需乘以 `10⁹`：即 `125,000.0 mm³`（不可直接当成 `0.000125 mm³` 或 `125 mm³`）。",
            "`GetMassProperties` 返回值为毫米制 `0.000125 mm³`，可直接四舍五入为 `0 mm³` 填入 BOM。",
            category="unit_preservation_dpo",
            software="solidworks",
            sys_idx=0,
        )
    )
    pairs.append(
        _dpo_row(
            "在 SOLIDWORKS 2021 新建草图拉伸凸台时，若想让零件高度沿标准 +Y 向上延伸，应选哪个基准面作为草图平面？",
            "SOLIDWORKS 2021 采用 **Y-up** 坐标系：Top Plane（XZ 平面）法向为 **+Y**（世界向上方向），"
            "在此平面草图向法向拉伸即可使高度沿 +Y 增长；Front Plane（XY）法向为 +Z，Right Plane（YZ）法向为 +X。",
            "与 CNC 机床相同，SOLIDWORKS 默认世界向上轴为 +Z，应选 XY 平面向上拉伸表示 +Z 高度。",
            category="coordinate_isolation_dpo",
            software="solidworks",
            sys_idx=1,
        )
    )

    # 5. Anti-Red-Excess confusion (6 pairs): stop appending "Excess Material" / "EXCESS" to Red
    red_excess_prompts = [
        "在 VERICUT 9.6 Auto-Diff 结果中，红色代表过切时能否在红色说明里同时标注为 Excess Material？",
        "请准确区分 VERICUT Auto-Diff 偏差图三色语义（严格区隔 Gouge 与 Excess Material）。",
        "审校报告写着『红色（Red）：过切（Excess Material / Gouge）』，这句话哪里有严重术语冲突？",
        "VERICUT Auto-Diff 偏差检查中，哪些英文术语专属于蓝色，哪些专属于红色与绿色？",
        "Why must Red in VERICUT Auto-Diff never be labeled 'Excess Material' alongside Gouge?",
        "写出 VERICUT Auto-Diff 红色、蓝色、绿色标准术语对照表，确保过切与残料词汇零混用。",
    ]
    for k_re, r_usr in enumerate(red_excess_prompts):
        chosen_re = (
            "严禁混用术语！VERICUT 9.6 Auto-Diff 三色严格分界：\n"
            "- **红色（Red）= 过切 / 超切（Gouge / Overcut）**：刀具切入设计模型内部（负偏差），属致命错误，必须**立即停止仿真/加工并修改刀路**（绝不能写作 Excess / Excess Material）。\n"
            "- **蓝色（Blue）= 残料 / 欠切（Excess Material / Undercut）**：毛坯尚留有未切除余量（正偏差），需**增加半精/精加工刀路**清除。\n"
            "- **绿色（Green）= 公差内合格（In-Tolerance）**：实切轮廓满足设计公差要求。"
        )
        rejected_re = (
            "- **红色（Red）**：表示**过切（Excess Material / Gouge）**，即刀具超切（超差 — EXCESS），须停止加工；\n"
            "- **蓝色（Blue）**：表示**残料（In-Tolerance / 余量）**；\n"
            "- **绿色（Green）**：表示**在公差带内合格**。"
        )
        pairs.append(
            _dpo_row(
                r_usr,
                chosen_re,
                rejected_re,
                category="autodiff_term_separation_dpo",
                software="vericut",
                sys_idx=k_re,
            )
        )

    # 6. Lamé think=False k=4 fraction simplification anchors (4 pairs, disjoint from 60/120/20)
    lame_k4_specs = [
        (40, 80, 15, 22.50),
        (50, 100, 18, 27.00),
        (36, 72, 24, 36.00),
        (70, 140, 21, 31.50),
    ]
    for k4_i, (di4, do4, pi4, bad_hoop) in enumerate(lame_k4_specs):
        hoop4 = pi4 * 5.0 / 3.0
        usr4 = (
            f"厚壁圆筒内径 Di={di4} mm，外径 Do={do4} mm（外径是内径 2 倍），内压 Pi={pi4} MPa。"
            f"直接逐步化简并计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r（MPa）。"
        )
        chosen4 = (
            f"按 Lamé 公式（外压 Po=0）：\n"
            f"1. 径比平方 k = (Do/Di)² = ({do4}/{di4})² = 4；\n"
            f"2. 分步化简系数：(k + 1)/(k - 1) = (4 + 1)/(4 - 1) = 5 / 3；\n"
            f"3. 环向应力：σ_θ = Pi × (5 / 3) = {pi4} × 5 / 3 = {pi4 * 5} / 3 = **{hoop4:.2f} MPa**（切勿误算）；\n"
            f"4. 径向应力：σ_r = -Pi = **-{pi4:.2f} MPa**（负号不可省略）。"
        )
        rejected4 = (
            f"径比平方 k = 4，代入环向应力 σ_θ = Pi·(k+1)/(k-1) = {pi4}·(4+1)/(4-1) = {bad_hoop:.2f} MPa，"
            f"径向应力 σ_r = -{pi4} MPa。"
        )
        pairs.append(
            _dpo_row(
                usr4,
                chosen4,
                rejected4,
                category="lame_fraction_dpo",
                software="cae",
                sys_idx=k4_i + 2,
            )
        )

    # 7. SOLIDWORKS Front/Top/Right explicit +Z/+Y/+X prefix-plus notation (4 pairs)
    sw_fmt_prompts = [
        "写出 SOLIDWORKS 2021 三个默认基准面（Front Plane、Top Plane、Right Plane）对应的平面与带前置正号的法向量。",
        "SOLIDWORKS 2021 的 Front / Top / Right 默认基准面法向矢量应分别记作什么？",
        "在 SOLIDWORKS 坐标系核查中，前视、上视、右视基准面的平面方程与标准 +X/+Y/+Z 法向是什么？",
        "Summarize SOLIDWORKS 2021 Front, Top, and Right default reference plane normals using +X/+Y/+Z.",
    ]
    for sw_i, sw_u in enumerate(sw_fmt_prompts):
        chosen_sw = (
            "SOLIDWORKS 2021 采用 **Y-up 右手坐标系**，三个默认基准面及其标准法线方向如下：\n"
            "- **Front Plane（前视基准面）**：XY 平面，法向为 **`+Z`** `(0, 0, +1)`；\n"
            "- **Top Plane（上视基准面）**：XZ 平面，法向为 **`+Y`** `(0, +1, 0)`（世界向上方向）；\n"
            "- **Right Plane（右视基准面）**：YZ 平面，法向为 **`+X`** `(+1, 0, 0)`。"
        )
        rejected_sw = (
            "SOLIDWORKPart 默认基准面：FrontPlane（Z+），TopPlane（Y+），RightPlane（X+），或采用 Z-up 将 Top 设为 +Z。"
        )
        pairs.append(
            _dpo_row(
                sw_u,
                chosen_sw,
                rejected_sw,
                category="sw_notation_dpo",
                software="solidworks",
                sys_idx=sw_i,
            )
        )
    return pairs


def _has_num(txt: str, val: str) -> bool:
    return bool(re.search(rf"(?<!\d){re.escape(val)}(?![\d.])", txt))


def assert_no_deploy_probe_overlap(rows: Iterable[Dict[str, Any]], label: str) -> None:
    """Fail-closed check ensuring deploy-probe exact parameters never leak into training sets."""
    for idx, r in enumerate(rows):
        txt = _row_text(r)
        # Forbidden probe 1: Lamé Di=60, Do=120, Pi=20
        if (_has_num(txt, "60") and _has_num(txt, "120") and _has_num(txt, "20")
                and ("lam" in txt.lower() or "σ_" in txt or "厚壁" in txt)):
            raise SystemExit(f"[FATAL] Deploy Lamé probe overlap detected in {label}[{idx}]: {txt[:140]}")
        # Forbidden probe 2: FANUC Ø60 / Ø38 / L20 / L45
        if (_has_num(txt, "60") and _has_num(txt, "38") and _has_num(txt, "20") and _has_num(txt, "45")
                and ("g71" in txt.lower() or "fanuc" in txt.lower())):
            raise SystemExit(f"[FATAL] Deploy FANUC G71 probe overlap detected in {label}[{idx}]: {txt[:140]}")


def _write_jsonl_and_sidecar(path: Path, rows: Sequence[Dict[str, Any]]) -> Tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    digest = sha256_file(path)
    Path(str(path) + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8", newline="\n")
    return digest, path.stat().st_size


def _run_tokenizer_audit(
    sft_rows: Sequence[Dict[str, Any]],
    dpo_rows: Sequence[Dict[str, Any]],
    base_dir: Path,
    *,
    sft_max_len: int = 3072,
    dpo_max_len: int = 1536,
    dpo_max_prompt: int = 1024,
) -> Dict[str, Any]:
    if not (base_dir / "config.json").is_file():
        return {"checked": False, "reason": f"base_dir_missing:{base_dir}"}
    from transformers import AutoTokenizer
    from train_turnkey import format_chatml_sample
    from train_vericut_dpo import encode_completion

    tok = AutoTokenizer.from_pretrained(str(base_dir), local_files_only=True, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    sft_lens: List[int] = []
    sft_trunc = 0
    for idx, r in enumerate(sft_rows):
        sample = format_chatml_sample(r, tok, max_length=sft_max_len + 1024)
        if sample is None or not any(lb != -100 for lb in sample["labels"]):
            raise SystemExit(f"[FATAL] SFT[{idx}] produced empty formatted/masked sample")
        tot = len(sample["input_ids"])
        sft_lens.append(tot)
        if tot > sft_max_len:
            sft_trunc += 1

    dpo_lens: List[int] = []
    dpo_prompt_trunc = 0
    dpo_trunc = 0
    for r in dpo_rows:
        prompt_text = tok.apply_chat_template(r["prompt"], tokenize=False, add_generation_prompt=True)
        p_ids = tok(prompt_text, add_special_tokens=False)["input_ids"]
        if len(p_ids) > dpo_max_prompt:
            dpo_prompt_trunc += 1
        c_ids, _ = encode_completion(tok, prompt_text, r["chosen"], dpo_max_len, dpo_max_prompt)
        rj_ids, _ = encode_completion(tok, prompt_text, r["rejected"], dpo_max_len, dpo_max_prompt)
        c_raw = len(p_ids) + len(tok(r["chosen"] + "<|im_end|>", add_special_tokens=False)["input_ids"])
        rj_raw = len(p_ids) + len(tok(r["rejected"] + "<|im_end|>", add_special_tokens=False)["input_ids"])
        mx = max(c_raw, rj_raw)
        dpo_lens.append(mx)
        if mx > dpo_max_len:
            dpo_trunc += 1

    if sft_trunc > 0 or dpo_prompt_trunc > 0 or dpo_trunc > 0:
        raise SystemExit(
            f"[FATAL] Tokenizer truncation detected: sft_trunc={sft_trunc} "
            f"dpo_prompt_trunc={dpo_prompt_trunc} dpo_trunc={dpo_trunc}"
        )
    return {
        "checked": True,
        "base_dir": str(base_dir),
        "sft_max_tokens": max(sft_lens) if sft_lens else 0,
        "sft_p95_tokens": sorted(sft_lens)[int(0.95 * len(sft_lens))] if sft_lens else 0,
        "sft_trunc": sft_trunc,
        "dpo_max_tokens": max(dpo_lens) if dpo_lens else 0,
        "dpo_trunc": dpo_trunc,
    }


def _run_v2_gates(
    sft_path: Path,
    dpo_path: Path,
    sft_rows: Sequence[Dict[str, Any]],
    dpo_rows: Sequence[Dict[str, Any]],
) -> None:
    g1 = gate_schema_and_tools(list(sft_rows))
    if not g1.get("passed"):
        raise SystemExit(f"[FATAL] v2 gate_schema_and_tools failed: {g1.get('errors')}")
    g2 = gate_system_prompt_budget_and_leak(list(sft_rows), max_bytes=1024)
    if not g2.get("passed"):
        raise SystemExit(f"[FATAL] v2 gate_system_prompt_budget failed: {g2.get('errors')}")
    assert_units_clean(str(sft_path))
    assert_units_clean(str(dpo_path))
    for idx, p in enumerate(dpo_rows):
        pr, ch, rj = p.get("prompt"), p.get("chosen"), p.get("rejected")
        if not isinstance(pr, list) or not pr:
            raise SystemExit(f"[FATAL] DPO[{idx}] invalid/empty prompt")
        if not isinstance(ch, str) or not isinstance(rj, str) or not ch.strip() or not rj.strip():
            raise SystemExit(f"[FATAL] DPO[{idx}] chosen/rejected must be non-empty strings")
        if ch.strip() == rj.strip():
            raise SystemExit(f"[FATAL] DPO[{idx}] chosen == rejected")
        max_sb = 702 if p.get("source") == "v2_anti_regression_dpo" else 1024
        for m in pr:
            if m.get("role") == "system":
                sb = len((m.get("content") or "").encode("utf-8"))
                if sb > max_sb:
                    raise SystemExit(f"[FATAL] DPO[{idx}] system prompt {sb}B > {max_sb}B")

    with tempfile.TemporaryDirectory(prefix="virtu_v2_holdout_") as td:
        td_path = Path(td)
        eval_dirs: List[Path] = [d for d in BENCHMARK_DIRS if d.is_dir()]
        for hf in DEFAULT_HOLDOUT_FILES:
            if hf.is_file():
                shutil.copy2(hf, td_path / hf.name)
        if any(td_path.iterdir()):
            eval_dirs.append(td_path)
        for ed in eval_dirs:
            assert_no_leak(str(sft_path), str(ed))
            assert_no_leak(str(dpo_path), str(ed))


def build_six_software_v2_corpus(
    *,
    v1_sft_path: Path = DEFAULT_V1_SFT,
    v1_dpo_path: Path = DEFAULT_V1_DPO,
    out_dir: Path = DEFAULT_OUT_DIR,
    seed: int = DEFAULT_SEED,
    check_tokenizer: bool = True,
) -> Dict[str, Any]:
    """Build v2 SFT + DPO JSONL datasets, run all offline & anti-leak gates, write ledger."""
    if not v1_sft_path.is_file() or not v1_dpo_path.is_file():
        raise SystemExit(f"[FATAL] Missing v1 baseline files: {v1_sft_path}, {v1_dpo_path}")

    v1_sft_rows = _load_jsonl(v1_sft_path)
    v1_dpo_rows = _load_jsonl(v1_dpo_path)
    if len(v1_sft_rows) != 850 or len(v1_dpo_rows) != 90:
        raise SystemExit(
            f"[FATAL] Expected v1 baseline 850 SFT / 90 DPO, got {len(v1_sft_rows)} / {len(v1_dpo_rows)}"
        )

    helper_sft = build_canonical_anti_regression_rows(seed=seed, limit=16)
    helper_dpo = build_canonical_anti_regression_dpo_rows(seed=seed, limit=16)

    extra_sft = (
        _build_v2_lame_sft_rows()
        + _build_v2_fanuc_g71_sft_rows()
        + _build_v2_autodiff_sft_rows()
        + _build_v2_coord_unit_sft_rows()
    )
    anchors_sft = helper_sft + extra_sft
    anchors_dpo = helper_dpo + _build_v2_targeted_dpo_rows()

    # Check uniqueness among all anchors and forbid deploy-probe overlap
    sft_anchor_prompts = [r["messages"][1]["content"] for r in anchors_sft]
    if len(set(sft_anchor_prompts)) != len(sft_anchor_prompts):
        raise SystemExit("[FATAL] Duplicate user prompts detected among v2 SFT anchors")
    dpo_anchor_prompts = [r["prompt"][-1]["content"] for r in anchors_dpo]
    if len(set(dpo_anchor_prompts)) != len(dpo_anchor_prompts):
        raise SystemExit("[FATAL] Duplicate user prompts detected among v2 DPO anchors")

    assert_no_deploy_probe_overlap(anchors_sft, "v2_sft_anchors")
    assert_no_deploy_probe_overlap(anchors_dpo, "v2_dpo_anchors")

    sft_rows = list(v1_sft_rows) + list(anchors_sft)
    dpo_rows = list(v1_dpo_rows) + list(anchors_dpo)
    rng = random.Random(seed)
    rng.shuffle(sft_rows)
    rng.shuffle(dpo_rows)

    sft_out = out_dir / "six_software_v2_sft.jsonl"
    dpo_out = out_dir / "six_software_v2_dpo.jsonl"
    ledger_out = out_dir / "six_software_v2_sft_ledger.json"

    sft_sha, sft_bytes = _write_jsonl_and_sidecar(sft_out, sft_rows)
    dpo_sha, dpo_bytes = _write_jsonl_and_sidecar(dpo_out, dpo_rows)

    _run_v2_gates(sft_out, dpo_out, sft_rows, dpo_rows)

    tok_audit: Dict[str, Any] = {"checked": False, "reason": "skipped"}
    if check_tokenizer:
        tok_audit = _run_tokenizer_audit(sft_rows, dpo_rows, ROOT / "checkpoints" / "_base_qwen3_8b")

    ledger = {
        "schema_version": "1.0",
        "track": "six-software-v2",
        "dataset": sft_out.name,
        "output_path": str(sft_out),
        "output_sha256": sft_sha,
        "size_bytes": sft_bytes,
        "count": len(sft_rows),
        "rows": len(sft_rows),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": {
            sft_out.name: {"sha256": sft_sha, "rows": len(sft_rows), "size_bytes": sft_bytes},
            dpo_out.name: {"sha256": dpo_sha, "rows": len(dpo_rows), "size_bytes": dpo_bytes},
        },
        "v1_baseline": {
            "sft_path": str(v1_sft_path),
            "sft_sha256": sha256_file(v1_sft_path),
            "sft_rows": len(v1_sft_rows),
            "dpo_path": str(v1_dpo_path),
            "dpo_sha256": sha256_file(v1_dpo_path),
            "dpo_rows": len(v1_dpo_rows),
        },
        "v2_anchors": {
            "sft_added": len(anchors_sft),
            "dpo_added": len(anchors_dpo),
            "families": ["lame_closed_form", "fanuc_g71_safety", "autodiff_triage", "coordinate_unit_safety"],
        },
        "token_audit": tok_audit,
        "basis": "measured_corpus_build",
    }
    ledger_out.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {
        "sft_path": str(sft_out),
        "sft_sha256": sft_sha,
        "sft_rows": len(sft_rows),
        "dpo_path": str(dpo_out),
        "dpo_sha256": dpo_sha,
        "dpo_rows": len(dpo_rows),
        "ledger_path": str(ledger_out),
        "token_audit": tok_audit,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build six-software-v2 anti-regression SFT & DPO datasets.")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--skip-tok-check", action="store_true")
    args = ap.parse_args()

    res = build_six_software_v2_corpus(
        out_dir=args.out_dir,
        seed=args.seed,
        check_tokenizer=not args.skip_tok_check,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
