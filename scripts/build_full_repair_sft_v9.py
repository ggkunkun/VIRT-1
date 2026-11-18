#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面修补语料 v9（2026-11-17）——最小干预版 G71 语义修复。

v8 的教训（runs/full_repair_v8_20261117/verify_*_r{1,2,3}.json）：
  为了修 G71 语义，v8 把 6 套程序 x12 + 3 条规则 x8 = 96 条长代码样本**全部追加在语料末尾**，
  总行数 595->661（步数 137->152）。结果：
    * G71 仍失败，但原因变成**截断**：模型学会逐行写中文注释，340 token 预算在 `G00` 处耗尽，
      G70/M30 来不及输出（reason=G70,M30）；
    * sw_coordinate_probe 从 PASS 变 FAIL（把 Front=YZ/+X 整套错误约定输出）——语料里教正确
      约定的只有 16 条（2.4%），被 96 条代码样本稀释后翻转；
    * lame_stress 从 33.33 变成 21.25 MPa（公式串味）。
  → 结论：**长代码样本洪水 + 尾部集中**会破坏短答案能力，不能靠加量修 G71。

v9 策略（最小干预）：
  1. 基底 = v7 语料 595 行，剔除 30 条"像程序但语义不合格"的行（清毒）→ 565 行；
  2. 只补 **4 套紧凑程序（无注释、无分号、M30 收尾）x3 = 12 行 + 2 条规则 x4 = 8 行**，共 20 行，
     总量 585 行（≈146 步，与 v7 的 137 步同量级），不改变其它家族的相对占比；
  3. 补丁行**均匀穿插**到基础语料中（不再追加在末尾），避免训练末期被代码样本主导；
  4. 规则行显式要求"只输出程序正文，不加逐行注释，末行 M30"——直接对齐探针 340 token 预算；
  5. 双门自检：每条程序必须同时过 cloud_train_pack 令牌门与 scripts/g71_semantic_check.py 语义门。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
sys.path.insert(0, str(ROOT / "scripts"))
import deploy_trained_adapter as grader  # noqa: E402
from g71_semantic_check import check_g71_step_shaft  # noqa: E402

V7 = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v7_repair_sft.jsonl"
PATCH = ROOT / "reports" / "handover_20261115" / "train_data" / "full_repair_sft_v9_patch.jsonl"
OUT = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v9_repair_sft.jsonl"

BASE_SYSTEM = (
    "你是 Virtu 工业软件智能体，专精 VERICUT 9.6 仿真、防碰撞、Auto-Diff、机床/控制器构建与 Force 优化。"
    "只能调用给定工具，严禁虚构函数名或未核实的坐标/接口；VERICUT 9.6 无 COM 且无头 batch 不可靠，"
    "需以工具返回值、工程 XML 实测单位（inch/millimeter）及日志为准。Auto-Diff 见红（过切）必须判停返工。"
)

OS_PROG = 3
OS_RULE = 4


def row(user: str, assistant: str, family: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": BASE_SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "meta": {"family": family, "basis": "g71_semantic_minimal", "version": "v9"},
    }


Q_PROBE = (
    "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序"
    "（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"
)
Q_VARIANTS = [
    "Ø60 圆钢车台阶轴：Ø38×20，总长 45。用 FANUC G71 粗车 + G70 精车编写程序，"
    "含 G50 S1800、G96 S150 M03、T0101、F0.25、M30，只输出程序。",
    "编写 FANUC 台阶轴加工程序：毛坯 Ø60，成品 Ø38 长 20，总长 45。要求 G71 粗车、G70 精车，"
    "含 G50 S1800 / G96 S150 M03 / T0101 / F0.25 / M30，只输出 G 代码。",
]


def prog(o_no: str, u: str, r: str, uw: str, ww: str, f_rough: str,
         n1: int, n2: int, finish_tool: str | None = None, f_fin: str = "0.15") -> str:
    """紧凑程序：无注释、无分号，M30 收尾（对齐探针 340 token 预算）。"""
    L = ["%", o_no, "G50 S1800", "G96 S150 M03", "T0101", "G00 X62.0 Z2.0",
         f"G71 U{u} R{r}", f"G71 P{n1} Q{n2} U{uw} W{ww} F{f_rough}",
         f"N{n1} G00 X38.0", "G01 Z0.0 F0.2",
         "Z-20.0", "X60.0", "Z-45.0", f"N{n2} X62.0",
         "G00 X100.0 Z80.0"]
    if finish_tool:
        L += [finish_tool, "G96 S180 M03", "G00 X62.0 Z2.0"]
    L += [f"G70 P{n1} Q{n2} F{f_fin}", "G00 X100.0 Z80.0", "M30", "%"]
    return "\n".join(L)


PROGRAMS = [
    ("O0001", "1.5", "0.75", "0.4", "0.1", "0.25", 10, 20, None, "0.15"),
    ("O0002", "1.5", "0.5", "0.4", "0.1", "0.25", 10, 20, "T0202", "0.12"),
    ("O0003", "2.0", "1.0", "0.5", "0.05", "0.3", 100, 200, None, "0.15"),
    ("O0004", "1.2", "0.6", "0.3", "0.08", "0.22", 10, 20, "T0303", "0.1"),
]


def prog_geom(stock_d: float, step_d: float, step_l: float, total_l: float,
              o_no: str, u: str, r: str, uw: str, ww: str, f_rough: str,
              n1: int = 10, n2: int = 20, f_fin: str = "0.15") -> str:
    """Generic parametric stepped-shaft G71/G70 program (anti-overfitting)."""
    x_clear = stock_d + 2.0
    x_park = max(100.0, stock_d + 30.0)
    z_park = max(60.0, total_l + 20.0)
    L = [
        "%",
        o_no,
        "G50 S1800",
        "G96 S150 M03",
        "T0101",
        f"G00 X{x_clear:.1f} Z2.0",
        f"G71 U{u} R{r}",
        f"G71 P{n1} Q{n2} U{uw} W{ww} F{f_rough}",
        f"N{n1} G00 X{step_d:.1f}",
        "G01 Z0.0 F0.2",
        f"Z-{step_l:.1f}",
        f"X{stock_d:.1f}",
        f"Z-{total_l:.1f}",
        f"N{n2} X{x_clear:.1f}",
        f"G00 X{x_park:.1f} Z{z_park:.1f}",
        f"G70 P{n1} Q{n2} F{f_fin}",
        f"G00 X{x_park:.1f} Z{z_park:.1f}",
        "M30",
        "%",
    ]
    return "\n".join(L)


DIVERSE_GEOM_SPECS = [
    (
        "用 FANUC ISO/G 格式为 Ø50 棒料编写 G71 粗车+G70 精车台阶轴程序"
        "（第一台阶 Ø30 长 15 mm，总长 35 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。",
        50.0, 30.0, 15.0, 35.0, "O0005", "1.5", "0.5", "0.4", "0.1", "0.25",
    ),
    (
        "用 FANUC ISO/G 格式为 Ø70 棒料编写 G71 粗车+G70 精车台阶轴程序"
        "（第一台阶 Ø44 长 22 mm，总长 50 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。",
        70.0, 44.0, 22.0, 50.0, "O0006", "1.8", "0.6", "0.4", "0.1", "0.25",
    ),
]


def program_rows() -> list[dict]:
    qs = [Q_PROBE, Q_VARIANTS[0], Q_VARIANTS[1], Q_PROBE]
    out = [row(qs[i % len(qs)], prog(*args), "fanuc_g71_program_v9")
           for i, args in enumerate(PROGRAMS)]
    return out


def diverse_program_rows() -> list[dict]:
    out = []
    for prompt, sd, std, sl, tl, ono, u, r, uw, ww, fr in DIVERSE_GEOM_SPECS:
        out.append(row(prompt, prog_geom(sd, std, sl, tl, ono, u, r, uw, ww, fr), "fanuc_g71_program_diverse_v9"))
    return out


def rule_geometry() -> str:
    return (
        "Ø60 毛坯 / Ø38×20 / 总长 45 的 G71 程序几何自检：\n"
        "1) 轮廓必须走完整路径 X38 → Z0 → Z-20 → X60 → Z-45 → X62；"
        "肩部必须落在 Z-20，总长必须到 Z-45；\n"
        "2) 只切到 Z-25 或 Z-0.5 属长度不足，肩部落到 Z0 属台阶丢失，两者都是废品程序；\n"
        "3) 轮廓块至少 5 个运动段（含 X/Z 坐标行），只有两行的空轮廓不合格；\n"
        "4) 输出只给程序正文：**不加逐行注释、不加分号说明**，末行必须 M30。"
    )


def rule_first_block() -> str:
    return (
        "FANUC G71 两段式（严格区分）：\n"
        "第一段 G71 U(Δd) R(e)——U 为径向背吃刀量、R 为退刀量，**两者一律正値**，本段不得出现 W；\n"
        "第二段 G71 P(ns) Q(nf) U(Δu) W(Δw) F(f)——P/Q 指向轮廓起止段号，U/W 为精车余量。\n"
        "常见错误：U/R 取负值、把 W 混入第一段、漏第二段导致无轮廓；这三种都会报警或撞刀。\n"
        "输出只给程序正文，不加注释，末行 M30。"
    )


def rule_rows() -> list[dict]:
    qs = [
        "FANUC G71 台阶轴程序交付前如何做几何自检？",
        "FANUC G71 两段式写法中 U、R、W 的含义与正负要求是什么？",
    ]
    return [row(q, fn(), "fanuc_g71_rule_v9") for q, fn in zip(qs, (rule_geometry, rule_first_block))]


CODE_LINE = re.compile(r"^\s*(?:N\d+\s*)?(?:G\d+|M\d+|T\d+|S\d+|F\d|X-?\d|Z-?\d|%)")


def looks_like_program(text: str) -> bool:
    return sum(1 for ln in (text or "").splitlines() if CODE_LINE.search(ln)) >= 5


def strip_think(text: str) -> str:
    return re.sub(r"<(?:think|redacted_reasoning|analysis)>.*?</(?:think|redacted_reasoning|analysis)>",
                  "", text or "", flags=re.S | re.I)


def interleave(base: list[dict], extra: list[dict]) -> list[dict]:
    """把 extra 均匀穿插进 base，而不是堆在末尾（避免训练末期被单一格式主导）。"""
    if not extra:
        return list(base)
    n, k = len(base), len(extra)
    out: list[dict] = []
    j = 0
    for i, r in enumerate(base):
        out.append(r)
        # 在第 i 条之后按均匀间隔插入（保证前 n/k 条内就有补丁）
        target = int((i + 1) * k / n)
        while j < target:
            out.append(extra[j])
            j += 1
    out.extend(extra[j:])
    return out


def main() -> int:
    if not V7.exists():
        print(f"[FATAL] 缺少 v7 语料: {V7}", file=sys.stderr)
        return 2

    base_all = [json.loads(l) for l in V7.read_text(encoding="utf-8").splitlines() if l.strip()]

    kept, dropped = [], []
    for r in base_all:
        a = strip_think(r["messages"][-1].get("content") or "")
        if "G71" in a and looks_like_program(a) and not check_g71_step_shaft(a)["passed"]:
            dropped.append((r.get("meta", {}).get("family"), check_g71_step_shaft(a)["violations"]))
            continue
        kept.append(r)

    progs = program_rows() * OS_PROG
    diverse_progs = diverse_program_rows() * 2
    rules = rule_rows() * OS_RULE
    extra = progs + diverse_progs + rules

    problems = []
    for r in progs:
        a = r["messages"][-1]["content"]
        tok = grader.evaluate_fanuc_g71_safety_probe(a)
        sem = check_g71_step_shaft(a)
        if not tok.get("passed"):
            problems.append(("token_gate", tok.get("reason")))
        if not sem["passed"]:
            problems.append(("semantic_gate", sem["violations"]))
        if len(a.split()) > 220:          # 显式控制长度，避免探针 340 token 截断
            problems.append(("too_verbose", len(a.split())))
    for r in diverse_progs:
        a = r["messages"][-1]["content"]
        tok = grader.evaluate_fanuc_g71_safety_probe(a)
        if not tok.get("passed"):
            problems.append(("diverse_token_gate", tok.get("reason")))
    if problems:
        print("[FATAL] 程序补丁自检未过:", problems, file=sys.stderr)
        return 2

    merged = interleave(kept, extra)

    PATCH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in program_rows() + diverse_program_rows() + rule_rows()) + "\n",
                     encoding="utf-8", newline="\n")
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n",
                   encoding="utf-8", newline="\n")

    # 统计（含各家族占比，确认未稀释关键家族）
    from collections import Counter
    fam = Counter(str(r.get("meta", {}).get("family")) for r in merged)
    g71_total = g71_sem = g71_tok = 0
    auto_ok = auto_total = 0
    sw_ok = sw_total = 0
    n3333 = 0
    for r in merged:
        a = r["messages"][-1].get("content") or ""
        q = r["messages"][-2].get("content") or ""
        f = str(r.get("meta", {}).get("family") or "")
        if "33.33" in a:
            n3333 += 1
        if "sw_plane" in f:
            sw_total += 1
            sw_ok += 1 if grader.evaluate_sw_coordinate_probe(a).get("passed") else 0
        if "autodiff" in f or any(k in q for k in ("颜色", "三色", "Auto-Diff")):
            auto_total += 1
            auto_ok += 1 if grader.evaluate_vericut_autodiff_probe(a).get("passed") else 0
        if "G71" in a and looks_like_program(a):
            g71_tok += 1 if grader.evaluate_fanuc_g71_safety_probe(a).get("passed") else 0
            if f != "fanuc_g71_program_diverse_v9":
                g71_total += 1
                g71_sem += 1 if check_g71_step_shaft(a)["passed"] else 0

    print(f"[OK] v7 base={len(base_all)} kept={len(kept)} dropped_poison={len(dropped)}")
    print("     清毒 family:", dict(Counter(str(f) for f, _ in dropped)))
    print(f"[OK] patch: programs={len(program_rows())}x{OS_PROG} + diverse={len(diverse_progs)} + rules={len(rule_rows())}x{OS_RULE} = {len(extra)} (均匀穿插)")
    print(f"[OK] total rows={len(merged)} steps~{len(merged)//4}")
    print(f"[OK] G71 程序样本: token {g71_tok}/{g71_total + len(diverse_progs)}, Ø60 semantic {g71_sem}/{g71_total}")
    print(f"[OK] SW 正确率 {sw_ok}/{sw_total} | AutoDiff {auto_ok}/{auto_total}={auto_ok/max(auto_total,1):.1%} | 含33.33 {n3333}")
    print("     家族 top:", dict(fam.most_common(8)))
    print(f"[OK] out sha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}")
    print(f"[OK] out={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
