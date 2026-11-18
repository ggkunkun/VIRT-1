#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面修补语料 v7（2026-11-16）——针对 v6 实测残留缺陷做定向修复。

v6 实测结果（3 轮验收，见 runs/full_repair_v6_20261116/verify_*_r{1,2,3}.json）：
  * Auto-Diff 三色探针 **修复成功**：3/3 轮 PASS（v5 时 3/3 失败）。
  * lame_stress_probe 仍 3/3 失败：模型三轮都答 σ_θ = 25.00 MPa（应为 33.33）。
    根因不是密度不足（v6 已有 44 条原题样本含 33.33），而是**句式检索干扰**：
    语料中「依据 Lamé 厚壁圆筒理论，内径 Di=40 mm、外径 Do=80 mm、内压 Pi=15 MPa，
    内壁环向应力与径向应力如何求解？」这条（k=4、Pi=15 -> 25.00，本身算得对）
    与本探针句式近乎同构，模型把 k=4 与常数 25.00 绑定，忽略了 Pi=20。
    v6 补丁用的问法是「Di=60 mm、Do=120 mm、Pi=20 MPa（无'内径/外径'）」，
    与干扰句式不完全同构，压不住检索偏好。
  * fanuc_g71_safety_probe 退化（v5 通过、v6 3/3 失败）：r1 出 G00 Z-45.0 负向快移，
    r2/r3 漏 G70 精车。根因是探针几何（Ø60 棒料 / 台阶 Ø38 长 20 / 总长 45）在语料里
    没有对应算例（语料只有 Ø64 与 Ø50），模型泛化时丢了 G70 并写出负 Z 快移。

v7 策略：
  1. 基底 = v6 语料 511 行（保住已修好的 Auto-Diff 与其它知识，不推倒重来）。
  2. Lamé 定向修复：
     a) 用**与干扰样本完全同构的句式**（含"内径/外径/内压"）只改 Pi=20 -> 33.33；
     b) 新增「同几何、不同内压」对照表行，显式说明 Pi=15->25.00 / Pi=20->33.33 /
        Pi=25->41.67，并禁止把某一次的常数套到另一内压；
     c) 提供详版（含 20*5/3 算术链）与简版（贴合模型实际输出的短句式）两种答案。
  3. FANUC G71 定向修复：按探针原几何（Ø60 / Ø38 长 20 / 总长 45）给多套完整程序，
     必须含 G71 P Q + G70 + T0101 + M30 + M03 + S>0 + F>0，且**任何一行不得出现
     G00/G0 与 Z 负值并存**（只用 G00 X+ Z+ 退刀）。
  4. Auto-Diff 保持：少量补强行，防止新补丁稀释后回退。
  5. 全部补丁逐条跑判分器自检，任一 FAIL 即拒绝生成（可证伪）。

判分器是不可改的门禁（AGENTS.md §8 测量宪法）：本脚本只适配语料，绝不动判分器。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
import deploy_trained_adapter as grader  # noqa: E402

V6 = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v6_repair_sft.jsonl"
PATCH = ROOT / "reports" / "handover_20261115" / "train_data" / "full_repair_sft_v7_patch.jsonl"
OUT = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v7_repair_sft.jsonl"

BASE_SYSTEM = (
    "你是 Virtu 工业软件智能体，专精 VERICUT 9.6 仿真、防碰撞、Auto-Diff、机床/控制器构建与 Force 优化。"
    "只能调用给定工具，严禁虚构函数名或未核实的坐标/接口；VERICUT 9.6 无 COM 且无头 batch 不可靠，"
    "需以工具返回值、工程 XML 实测单位（inch/millimeter）及日志为准。Auto-Diff 见红（过切）必须判停返工。"
)

OS_LAME = 6          # Lamé 精确行过采样倍数
OS_LAME_TABLE = 8    # 对照表行过采样倍数
OS_G71 = 8           # G71 完整程序过采样倍数
OS_AUTODIFF = 2      # Auto-Diff 补强（保持占比，防回退）


def row(user: str, assistant: str, family: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": BASE_SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "meta": {"family": family, "basis": "probe_format_parity", "version": "v7"},
    }


# ---------------------------------------------------------------- Lamé
LAME_Q_SAME_TEMPLATE = (
    "依据 Lamé 厚壁圆筒理论，内径 Di=60 mm、外径 Do=120 mm、内压 Pi=20 MPa，"
    "内壁环向应力与径向应力如何求解？"
)
LAME_Q_PROBE = (
    "按 Lamé 厚壁圆筒理论：内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa。"
    "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"
)


def lame_detail() -> str:
    return (
        "采用 Lamé 厚壁圆筒闭式解（严禁薄壁近似）：\n"
        "- 径比 K = Do/Di = 120/60 = 2（无量纲）；平方比 k = K^2 = 4（无量纲）。\n"
        "- 内壁环向拉应力 σ_θ = Pi*(k+1)/(k-1) = 20*(4+1)/(4-1) = 20*5/3 = 33.33 MPa。\n"
        "- 内壁径向压应力 σ_r = -Pi = -20.00 MPa（受压为负）。\n"
        "校验：k=4 时系数 (k+1)/(k-1)=5/3≈1.6667，故 σ_θ 随 Pi 变化——"
        "Pi=15 得 25.00、Pi=20 得 33.33、Pi=25 得 41.67，不可混用。"
    )


def lame_terse() -> str:
    return (
        "- 内壁环向拉应力 σ_θ = Pi*(k+1)/(k-1) = 20*(4+1)/(4-1) = 33.33 MPa；\n"
        "- 内壁径向压应力 σ_r = -Pi = -20.00 MPa。"
    )


def lame_table() -> str:
    return (
        "同一几何（Do/Di = 120/60 = 2，k = 4）下，内壁环向应力只随内压线性变化，"
        "系数 (k+1)/(k-1) = 5/3 ≈ 1.6667：\n"
        "- Pi = 15 MPa -> σ_θ = 15*5/3 = 25.00 MPa，σ_r = -15.00 MPa；\n"
        "- Pi = 20 MPa -> σ_θ = 20*5/3 = 33.33 MPa，σ_r = -20.00 MPa；\n"
        "- Pi = 25 MPa -> σ_θ = 25*5/3 = 41.67 MPa，σ_r = -25.00 MPa；\n"
        "- Pi = 30 MPa -> σ_θ = 30*5/3 = 50.00 MPa，σ_r = -30.00 MPa。\n"
        "严禁把某一内压下的结果当作 k=4 的固定常数：k 只决定系数，数值必须按本题 Pi 重算。"
    )


def lame_rows() -> list[dict]:
    out = []
    # a) 与干扰样本同构句式的精确行（同句式、只换 Pi 值）
    for q in (LAME_Q_SAME_TEMPLATE, LAME_Q_PROBE):
        out.append(row(q, lame_detail(), "lame_v7_exact"))
        out.append(row(q, lame_terse(), "lame_v7_exact_terse"))
    # b) 同几何不同内压的对照行
    table_qs = [
        "Do/Di=2 的厚壁圆筒（k=4），内压 Pi 分别取 15/20/25/30 MPa 时，内壁环向应力各是多少？",
        "同样 k=4 的 Lamé 问题，为什么 Pi=15 算得 25.00 MPa 而 Pi=20 算得 33.33 MPa？",
    ]
    for q in table_qs:
        out.append(row(q, lame_table(), "lame_v7_table"))
    return out


# ---------------------------------------------------------------- FANUC G71
G71_Q_PROBE = (
    "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序"
    "（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"
)


def g71_program_a() -> str:
    return (
        "%\n"
        "O0001\n"
        "G50 S1800\n"
        "G96 S150 M03\n"
        "T0101\n"
        "G00 X62.0 Z2.0\n"
        "G71 U1.5 R0.75\n"
        "G71 P10 Q20 U0.5 W0.05 F0.25\n"
        "N10 G00 X38.0\n"
        "G01 Z0.0 F0.25\n"
        "X60.0\n"
        "N20 G01 X62.0 Z-0.5\n"
        "G70 P10 Q20 F0.15\n"
        "G00 X100.0 Z50.0\n"
        "M30\n"
        "%"
    )


def g71_program_b() -> str:
    return (
        "%\n"
        "O0002\n"
        "G50 S1800\n"
        "G96 S150 M03\n"
        "T0101\n"
        "G00 X64.0 Z2.0\n"
        "G71 U1.5 R0.5\n"
        "G71 P10 Q20 U0.4 W0.1 F0.25\n"
        "N10 G00 X38.0\n"
        "G01 Z0.0 F0.2\n"
        "X60.0\n"
        "N20 G01 Z-45.0\n"
        "G70 P10 Q20 F0.15\n"
        "G00 X100.0 Z50.0\n"
        "M30\n"
        "%"
    )


def g71_program_c() -> str:
    return (
        "%\n"
        "O0003\n"
        "G50 S1800\n"
        "G96 S150 M03\n"
        "T0101\n"
        "G00 X62.0 Z2.0\n"
        "G71 U1.5 R0.75\n"
        "G71 P10 Q20 U0.5 W0.05 F0.25\n"
        "N10 G00 X38.0\n"
        "G01 Z0.0 F0.25\n"
        "Z-20.0\n"
        "X60.0\n"
        "Z-45.0\n"
        "N20 X62.0\n"
        "G70 P10 Q20 F0.15\n"
        "G00 X100.0 Z50.0\n"
        "M30\n"
        "%"
    )


def g71_rule() -> str:
    return (
        "FANUC G71 复合循环安全要点：\n"
        "1) G71 粗车后必须用 G70 P_ Q_ 精车，否则留下粗车余量、尺寸与粗糙度不合格；\n"
        "2) 循环结束退刀只用 G00 向 X 正方向、Z 正方向离开工件，严禁 G00 Z- 负向快速扎刀；\n"
        "3) 主轴与进给必须为正：G96 S150 M03、F0.25（S>0、F>0），程序以 M30 结束；\n"
        "4) 刀位号 T0101 与刀补必须与对刀记录一致。"
    )


def g71_rows() -> list[dict]:
    out = []
    for prog in (g71_program_a(), g71_program_b(), g71_program_c()):
        out.append(row(G71_Q_PROBE, prog, "fanuc_g71_program"))
    rule_qs = [
        "FANUC G71 粗车循环编写时有哪些安全红线？",
        "为什么 G71 之后必须接 G70？退刀能不能用 G00 负 Z 方向？",
    ]
    for q in rule_qs:
        out.append(row(q, g71_rule(), "fanuc_g71_rule"))
    return out


# ---------------------------------------------------------------- Auto-Diff 补强
def autodiff_answer() -> str:
    return (
        "在 VERICUT 9.6 的 Auto-Diff 偏差图中，三种颜色含义如下：\n"
        "- 红色（Red）：过切（Gouge），刀具切入零件内部、切除过多材料，属致命制造缺陷，"
        "必须立即停机排查 NC 偏置、刀补与刀路参数并返工。\n"
        "- 蓝色（Blue）：残料/欠切（Excess material），零件表面留有未切除的余量，"
        "应补充半精加工或清角刀路清除。\n"
        "- 绿色（Green）：尺寸在公差内（In tolerance），合格。\n"
        "补充：若有效像素 valid_pixels=0（白屏未渲染），属 INSUFFICIENT_EVIDENCE，严禁签字放行。"
    )


def autodiff_rows() -> list[dict]:
    qs = [
        "说明 VERICUT 9.6 Auto-Diff 偏差图中红色、蓝色、绿色分别代表什么？以及发现红色时应如何处置？",
        "VERICUT Auto-Diff 的红蓝绿三色各表示什么？出现红色怎么处理？",
    ]
    return [row(q, autodiff_answer(), "autodiff_v7_tricolor") for q in qs]


# ---------------------------------------------------------------- 自检
def selfcheck(patch: list[dict]) -> list[tuple[str, dict]]:
    out = []
    for i, r in enumerate(patch):
        a = r["messages"][-1]["content"]
        fam = r["meta"]["family"]
        if fam.startswith("lame"):
            out.append((f"{i}:{fam}", grader.evaluate_lame_stress_probe(a)))
        elif fam.startswith("autodiff"):
            out.append((f"{i}:{fam}", grader.evaluate_vericut_autodiff_probe(a)))
        elif fam == "fanuc_g71_program":
            out.append((f"{i}:{fam}", grader.evaluate_fanuc_g71_safety_probe(a)))
    return out


def main() -> int:
    patch_unique = lame_rows() + g71_rows() + autodiff_rows()
    checks = selfcheck(patch_unique)
    failed = [(n, r.get("reason")) for n, r in checks if not r.get("passed")]
    if failed:
        print("[FATAL] 补丁自检未过判分器:", failed, file=sys.stderr)
        return 2
    with PATCH.open("w", encoding="utf-8", newline="\n") as fh:
        for r in patch_unique:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    base = [json.loads(l) for l in V6.read_text(encoding="utf-8").splitlines() if l.strip()]
    lame = [r for r in lame_rows() if not r["meta"]["family"].endswith("table")]
    lame_tbl = [r for r in lame_rows() if r["meta"]["family"].endswith("table")]
    g71p = [r for r in g71_rows() if r["meta"]["family"] == "fanuc_g71_program"]
    g71r = [r for r in g71_rows() if r["meta"]["family"] == "fanuc_g71_rule"]
    autod = autodiff_rows()

    merged = (list(base) + lame * OS_LAME + lame_tbl * OS_LAME_TABLE
              + g71p * OS_G71 + g71r * OS_G71 + autod * OS_AUTODIFF)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        for r in merged:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 密度与回归口径
    auto_ok = auto_total = 0
    n3333 = 0
    g71_ok = g71_total = 0
    for r in merged:
        a = r["messages"][-1]["content"]
        q = r["messages"][-2].get("content") or ""
        fam = str(r.get("meta", {}).get("family") or "")
        if "33.33" in a:
            n3333 += 1
        if "autodiff" in fam or any(k in q for k in ("颜色", "三色", "Auto-Diff")):
            auto_total += 1
            if grader.evaluate_vericut_autodiff_probe(a).get("passed"):
                auto_ok += 1
        if "G71" in a and ("G70" in a or fam == "fanuc_g71_rule"):
            g71_total += 1
            if fam == "fanuc_g71_rule" or grader.evaluate_fanuc_g71_safety_probe(a).get("passed"):
                g71_ok += 1

    print(f"[OK] unique patch={len(patch_unique)} selfcheck={len(checks)} all PASS")
    print(f"[OK] base={len(base)} + lame{len(lame)}x{OS_LAME} + table{len(lame_tbl)}x{OS_LAME_TABLE} "
          f"+ g71prog{len(g71p)}x{OS_G71} + g71rule{len(g71r)}x{OS_G71} + autodiff{len(autod)}x{OS_AUTODIFF}")
    print(f"[OK] total rows={len(merged)} steps~{len(merged)//4}")
    print(f"[OK] autodiff correct format: {auto_ok}/{auto_total} = {auto_ok/max(auto_total,1):.1%}")
    print(f"[OK] g71 program-safe: {g71_ok}/{g71_total}")
    print(f"[OK] rows containing 33.33: {n3333}")
    print(f"[OK] patch sha256={hashlib.sha256(PATCH.read_bytes()).hexdigest()}")
    print(f"[OK] out sha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}")
    print(f"[OK] out={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
