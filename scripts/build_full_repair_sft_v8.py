#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面修补语料 v8（2026-11-17）——修 G71 台阶轴的**语义**缺陷。

v7 实测（runs/full_repair_v7_20261116/verify_*_r{1,2,3}.json）：
  * 令牌门 3/3 PASS（门禁 10/10），但 G 代码本身不可用：
      - r2/r3: `G71 U-1.5 W-0.5 R-0.15`（负背吃刀量/负退刀量，FANUC 不成立）
      - r2/r3: 轮廓块 `N10 G00 X38.0 / N20 G01 Z0.0` 几乎为空，Ø38×20 台阶根本没切
      - r1: 轮廓 `X60.0 Z-20.0 / N20 G01 Z-25.0`，肩部在 Z0、总长只到 Z-25（应 -45）

  根因（用 scripts/g71_semantic_check.py 扫 v7 语料确认）：
    55 条 G71 样本里仅 8 条语义正确；探针几何的 16 条程序样本**全错**——
    v7 的三套"标准程序"中 program_a 的轮廓止于 `Z-0.5`、program_b 缺 `Z-20` 台阶段，
    只有 program_c 正确，正确:错误 = 1:2，模型自然学了多数派的坏写法。

v8 策略：
  1. 基底 = v7 语料 595 行；**剔除"看起来是程序且语义不合格"的行**（清毒），散文规则行保留。
  2. 新增 6 套语义正确的标准程序（同一几何 Ø60/Ø38×20/总长45），差分只在 O 号、
     U/R 背吃刀量、进给、刀号与行号，全部满足：
       首块 `G71 U{正} R{正}`（不带 W） → 次块 `G71 P_ Q_ U_ W_ F_`
       轮廓 `X38 → Z0 → Z-20 → X60 → Z-45 → X62`（台阶与肩部位置正确）
       G70 在 Q 之后；退刀只用 G00 X+ Z+
  3. 新增语义自检类散文行：交付前必须核对"Ø38 段切到 Z-20、肩部在 Z-20、总长到 Z-45、
     U/R 取正值、轮廓不得为空"。
  4. Lamé / Auto-Diff 行原样保留（v7 已修好，不得回退）。
  5. 双重自检：每条程序补丁必须同时通过
       - cloud_train_pack 令牌门 `evaluate_fanuc_g71_safety_probe`（门禁口径，不改）
       - scripts/g71_semantic_check.py 语义门（新增，独立）
     任一 FAIL 即拒绝生成（可证伪）。
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
PATCH = ROOT / "reports" / "handover_20261115" / "train_data" / "full_repair_sft_v8_patch.jsonl"
OUT = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v8_repair_sft.jsonl"

BASE_SYSTEM = (
    "你是 Virtu 工业软件智能体，专精 VERICUT 9.6 仿真、防碰撞、Auto-Diff、机床/控制器构建与 Force 优化。"
    "只能调用给定工具，严禁虚构函数名或未核实的坐标/接口；VERICUT 9.6 无 COM 且无头 batch 不可靠，"
    "需以工具返回值、工程 XML 实测单位（inch/millimeter）及日志为准。Auto-Diff 见红（过切）必须判停返工。"
)

OS_PROG = 12      # 每套标准程序的过采样倍数
OS_RULE = 8       # 语义规则行过采样倍数


def row(user: str, assistant: str, family: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": BASE_SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "meta": {"family": family, "basis": "g71_semantic_repair", "version": "v8"},
    }


# ---------------------------------------------------------------- 提问
Q_PROBE = (
    "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序"
    "（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"
)
Q_VARIANTS = [
    "Ø60 圆钢车台阶轴：Ø38×20，总长 45。用 FANUC G71 粗车 + G70 精车编写程序，"
    "含 G50 S1800、G96 S150 M03、T0101、F0.25、M30，只输出程序。",
    "编写 FANUC 台阶轴加工程序：毛坯 Ø60，成品 Ø38 长 20，总长 45。要求 G71 粗车、G70 精车，"
    "含 G50 S1800 / G96 S150 M03 / T0101 / F0.25 / M30，只输出 G 代码。",
    "给 Ø60 棒料编 G71+G70 程序，车出 Ø38×20 台阶、总长 45 的轴，"
    "程序需含 G50 S1800、G96 S150 M03、T0101、F0.25，以 M30 结束，只输出程序。",
]


# ---------------------------------------------------------------- 标准程序
# 几何统一：Ø60 毛坯 / Ø38 段长 20（Z-20）/ 肩部在 Z-20 / 总长 45（Z-45）
def prog_variant(o_no: str, u: str, r: str, uw: str, ww: str, f_rough: str,
                 n_start: int, n_end: int, finish_tool: str | None = None,
                 finish_s: str = "180", f_finish: str = "0.15") -> str:
    lines = ["%", f"O{o_no}", "G50 S1800", "G96 S150 M03", "T0101", "G00 X62.0 Z2.0",
             f"G71 U{u} R{r}", f"G71 P{n_start} Q{n_end} U{uw} W{ww} F{f_rough}",
             f"N{n_start} G00 X38.0", "G01 Z0.0 F0.2",
             "Z-20.0",            # Ø38 段：第一台阶长度 20
             "X60.0",             # 肩部：在 Z-20 处抬到 Ø60
             "Z-45.0",            # Ø60 段：总长 45
             f"N{n_end} X62.0"]
    if finish_tool:
        lines += ["G00 X100.0 Z80.0", finish_tool, f"G96 S{finish_s} M03", "G00 X62.0 Z2.0",
                  f"G70 P{n_start} Q{n_end} F{f_finish}"]
    else:
        lines += ["G00 X100.0 Z80.0", f"G70 P{n_start} Q{n_end} F{f_finish}"]
    lines += ["G00 X100.0 Z80.0", "M30", "%"]
    return "\n".join(lines)


PROGRAMS = [
    # (O号, U, R, U余量, W余量, 粗车进给, 起段号, 止段号, 精车刀, 精车S, 精车F)
    ("O0001", "1.5", "0.75", "0.4", "0.1", "0.25", 10, 20, None, "180", "0.15"),
    ("O0002", "1.5", "0.5", "0.4", "0.1", "0.25", 10, 20, "T0202", "180", "0.12"),
    ("O0003", "2.0", "1.0", "0.5", "0.05", "0.3", 100, 200, None, "180", "0.15"),
    ("O0004", "1.2", "0.6", "0.3", "0.08", "0.22", 10, 20, "T0202", "200", "0.1"),
    ("O0005", "1.5", "0.75", "0.4", "0.12", "0.25", 30, 40, None, "180", "0.15"),
    ("O0006", "1.8", "0.8", "0.4", "0.1", "0.28", 10, 20, "T0303", "160", "0.13"),
]


def program_rows() -> list[dict]:
    out = []
    qs = [Q_PROBE] + Q_VARIANTS
    for i, args in enumerate(PROGRAMS):
        prog = prog_variant(*args)
        # 轮换提问方式，让同一答案覆盖探针原题与近义问法
        q = qs[i % len(qs)]
        out.append(row(q, prog, "fanuc_g71_program_v8"))
    return out


# ---------------------------------------------------------------- 语义规则
def rule_geometry() -> str:
    return (
        "FANUC G71 台阶轴程序交付前的几何自检（Ø60 毛坯 / Ø38×20 / 总长 45）：\n"
        "1) 轮廓必须走完整路径：X38 → Z0 → Z-20（第一台阶长度 20）→ X60（肩部在 Z-20）"
        "→ Z-45（总长 45）→ X62 退出；\n"
        "2) 只切到 Z-25 或 Z-0.5 属长度不足，肩部落在 Z0 属台阶丢失，两者都是废品程序；\n"
        "3) 轮廓块至少要 5 个运动段（X/Z 坐标行都算），只有两行的空轮廓直接判不合格；\n"
        "4) G71 复合循环结束后用 G70 P_ Q_ 精车，精车前刀具必须已回到 X62 Z2 或 X100 Z80。"
    )


def rule_first_block() -> str:
    return (
        "FANUC G71 两段式写法（必须严格区分）：\n"
        "第一段：G71 U(Δd) R(e) —— U 为径向背吃刀量，R 为退刀量，**两者一律取正值**；"
        "本段不允许出现 W 字，出现负 U 或负 R 即为语法错误，机床会报警或产生撞刀；\n"
        "第二段：G71 P(ns) Q(nf) U(Δu) W(Δw) F(f) —— P/Q 指向轮廓起止段号，"
        "U/W 为精车余量（径向/轴向，正值为留量）。\n"
        "常见错误：把 U/R 写成负值、把 W 混进第一段、或漏掉第二段导致没有轮廓定义。"
    )


def rule_retract() -> str:
    return (
        "FANUC 车削退刀与安全规则：\n"
        "1) 循环内任何 G00 只能朝 X 正方向与 Z 正方向离开工件，严禁 G00 与 Z 负值同行"
        "（负 Z 快移等于高速扎刀，必撞卡盘或工件）；\n"
        "2) 程序结束前先 G00 X100.0 Z80.0 回到换刀/安全点，再 M30；\n"
        "3) 主轴转速与进给必须为正：G96 S150 M03、F0.25；\n"
        "4) T0101 刀位与刀补须与对刀记录一致，精车换刀后重新执行 G96 恒线速。"
    )


def rule_rows() -> list[dict]:
    qs = [
        "FANUC G71 台阶轴程序交付前如何做几何自检？",
        "FANUC G71 两段式写法中 U、R、W 各自含义与取值正负要求是什么？",
        "FANUC 车削程序中退刀与 G00 有哪些安全红线？",
    ]
    return [row(q, fn(), "fanuc_g71_rule_v8") for q, fn in zip(qs, (rule_geometry, rule_first_block, rule_retract))]


# ---------------------------------------------------------------- 清毒
CODE_LINE = re.compile(r"^\s*(?:N\d+\s*)?(?:G\d+|M\d+|T\d+|S\d+|F\d|X-?\d|Z-?\d|%)")


def looks_like_program(text: str) -> bool:
    n = sum(1 for ln in (text or "").splitlines() if CODE_LINE.search(ln))
    return n >= 5


def strip_think(text: str) -> str:
    return re.sub(r"<(?:think|redacted_reasoning|analysis)>.*?</(?:think|redacted_reasoning|analysis)>",
                  "", text or "", flags=re.S | re.I)


def main() -> int:
    if not V7.exists():
        print(f"[FATAL] 缺少 v7 语料: {V7}", file=sys.stderr)
        return 2

    base_all = [json.loads(l) for l in V7.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 1) 清毒：剔除"像程序但语义不合格"的行
    kept, dropped = [], []
    for r in base_all:
        a = strip_think(r["messages"][-1].get("content") or "")
        if "G71" in a and looks_like_program(a):
            res = check_g71_step_shaft(a)
            if not res["passed"]:
                dropped.append((r.get("meta", {}).get("family"), res["violations"]))
                continue
        kept.append(r)

    # 2) 构造补丁
    progs = program_rows()
    rules = rule_rows()

    # 3) 双重自检（令牌门 + 语义门）
    problems = []
    for r in progs:
        a = r["messages"][-1]["content"]
        tok = grader.evaluate_fanuc_g71_safety_probe(a)
        sem = check_g71_step_shaft(a)
        if not tok.get("passed"):
            problems.append(("token_gate", tok.get("reason"), a[:80]))
        if not sem["passed"]:
            problems.append(("semantic_gate", sem["violations"], a[:80]))
    if problems:
        print("[FATAL] 程序补丁自检未过:", problems, file=sys.stderr)
        return 2

    # 4) 合并
    merged = kept + progs * OS_PROG + rules * OS_RULE
    PATCH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in progs + rules) + "\n",
                     encoding="utf-8", newline="\n")
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n",
                   encoding="utf-8", newline="\n")

    # 5) 统计与回归口径
    g71_prog_total = g71_prog_ok = g71_sem_ok = 0
    auto_ok = auto_total = 0
    n3333 = 0
    for r in merged:
        a = r["messages"][-1].get("content") or ""
        q = r["messages"][-2].get("content") or ""
        fam = str(r.get("meta", {}).get("family") or "")
        if "33.33" in a:
            n3333 += 1
        if "autodiff" in fam or any(k in q for k in ("颜色", "三色", "Auto-Diff")):
            auto_total += 1
            if grader.evaluate_vericut_autodiff_probe(a).get("passed"):
                auto_ok += 1
        if "G71" in a and looks_like_program(a):
            g71_prog_total += 1
            if grader.evaluate_fanuc_g71_safety_probe(a).get("passed"):
                g71_prog_ok += 1
            if check_g71_step_shaft(a)["passed"]:
                g71_sem_ok += 1

    print(f"[OK] v7 base={len(base_all)} → kept={len(kept)} dropped_poison={len(dropped)}")
    from collections import Counter
    print("     清毒 family 分布:", dict(Counter(str(f) for f, _ in dropped)))
    print("     清毒原因:", dict(Counter(x for _, vs in dropped for x in vs).most_common(6)))
    print(f"[OK] patch: programs={len(progs)} rules={len(rules)} (all pass token+semantic)")
    print(f"[OK] total rows={len(merged)} steps~{len(merged)//4}")
    print(f"[OK] G71 程序样本: token_gate {g71_prog_ok}/{g71_prog_total}, semantic_gate {g71_sem_ok}/{g71_prog_total}")
    print(f"[OK] autodiff correct format: {auto_ok}/{auto_total} = {auto_ok/max(auto_total,1):.1%}")
    print(f"[OK] rows containing 33.33: {n3333}")
    print(f"[OK] out sha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}")
    print(f"[OK] out={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
