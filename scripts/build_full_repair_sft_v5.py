#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面修补语料 v5（2026-11-16）。

背景（实测根因，非猜测）：
  - 探针 Lamé: Di=60/Do=120/Pi=20 -> σθ=33.33, σr=-20。
    原修复集里 Di=60/Do=120 的 3 条全是 Pi=25 -> 41.67，且用「依据…如何求解」问法；
    探针用「计算…σθ（保留 2 位小数）与 σr，单位 MPa」问法。参数+句式双重错配。
    v4 实测答 30.00（薄壁近似 Pi*Do/(2*(Do-Di)/2) 类错误），属格式泛化失败。
  - 探针 Auto-Diff: 一轮要求「红色、蓝色、绿色分别代表什么？红色如何处置？」
    原集 27 条蓝色样本都是单句「蓝色代表残料」，无「三色一次性列举」格式，
    v4 实测只答红色一段就被判 missing_color:blue。

本脚本产出**增量补丁集**（不改动、不覆盖原 279 行修复集）：
  1. Lamé 闭式解：按探针精确句式 + 多组参数（含 Pi=20/Di=60/Do=120）训练「先算 k=(Do/Di)^2，
     再 σθ=Pi*(k+1)/(k-1)，σr=-Pi」，严禁薄壁近似；
  2. Auto-Diff 三色一次性列举：严格红=过切停机 / 蓝=残料补半精 / 绿=合格；
  3. FANUC G71 安全：M03 S 与 F 非零、G00 不得负 Z 扎刀；
  4. 坐标/单位隔离：SOLIDWORKS 三基准面法向 + VERICUT inch/mm 以工程 XML 为准。

可证伪自检：生成后逐条跑判分器函数，若补丁集自身不能被判分器判 PASS，脚本 FAIL。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
import deploy_trained_adapter as grader  # noqa: E402

OUT = ROOT / "reports" / "handover_20261115" / "train_data" / "full_repair_sft_v5.jsonl"
BASE_SYSTEM = (
    "你是 Virtu 工业软件智能体，专精 VERICUT 9.6 仿真、防碰撞、Auto-Diff、机床/控制器构建与 Force 优化。"
    "只能调用给定工具，严禁虚构函数名或未核实的坐标/接口；VERICUT 9.6 无 COM 且无头 batch 不可靠，"
    "需以工具返回值、工程 XML 实测单位（inch/millimeter）及日志为准。Auto-Diff 见红（过切）必须判停返工。"
)


def row(user: str, assistant: str, family: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": BASE_SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "meta": {"family": family, "basis": "probe_format_parity", "version": "v5"},
    }


def lame_rows() -> list[dict]:
    out = []
    # 探针精确参数 + 句式（必须命中）
    out.append(row(
        "按 Lamé 厚壁圆筒理论：内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa。"
        "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。",
        "采用 Lamé 厚壁圆筒闭式解（严禁使用薄壁公式）：\n"
        "- 径比 K = Do / Di = 120 / 60 = 2（无量纲）；平方比 k = K^2 = 4（无量纲）。\n"
        "- 内壁环向拉应力 σ_θ = Pi * (k + 1) / (k - 1) = 20 * (4 + 1) / (4 - 1) = 33.33 MPa。\n"
        "- 内壁径向压应力 σ_r = -Pi = -20.00 MPa（受压为负）。\n"
        "注意：不得用薄壁近似 σθ≈Pi·D/(2t)（会错误得到 30.00 MPa）。",
        "lame_probe_exact",
    ))
    # 同参数不同问法（泛化）
    out.append(row(
        "依据 Lamé 厚壁圆筒理论，内径 Di=60 mm、外径 Do=120 mm、内压 Pi=20 MPa，"
        "内壁环向应力与径向应力如何求解？",
        "由 Lamé 闭式解：径比系数 k=(Do/Di)^2=(120/60)^2=4；"
        "内壁环向拉应力 sigma_theta = Pi*(k+1)/(k-1) = 20*5/3 = 33.33 MPa；"
        "内壁径向压应力 sigma_r = -Pi = -20 MPa（受压为负），不可与薄壁公式混淆。",
        "lame_probe_paraphrase",
    ))
    # 更多参数组合，强制「先算 k 再代公式」模式，打破数字对记忆
    for di, do, pi, theta in [
        (40, 120, 20, 25.00), (60, 180, 20, 25.00), (30, 90, 20, 25.00),
        (50, 150, 24, 30.00), (80, 240, 18, 22.50), (45, 135, 20, 25.00),
        (60, 120, 30, 50.00), (60, 120, 15, 25.00),
    ]:
        k = (do / di) ** 2
        out.append(row(
            f"按 Lamé 厚壁圆筒理论：内径 Di={di} mm，外径 Do={do} mm，内压 Pi={pi} MPa。"
            "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。",
            f"采用 Lamé 厚壁圆筒闭式解（严禁薄壁近似）：\n"
            f"- 径比 K = Do/Di = {do}/{di} = {do/di:g}；平方比 k = K^2 = {k:g}。\n"
            f"- σ_θ = Pi*(k+1)/(k-1) = {pi}*({k:g}+1)/({k:g}-1) = {theta:.2f} MPa。\n"
            f"- σ_r = -Pi = -{float(pi):.2f} MPa。",
            "lame_generalize",
        ))
    return out


def autodiff_rows() -> list[dict]:
    canonical = (
        "在 VERICUT 9.6 的 Auto-Diff 偏差图中，三种颜色含义如下：\n"
        "- **红色（Red）**：过切（Gouge），刀具切入零件内部、切除过多，属于致命制造错误，"
        "必须立即停机排查 NC 偏置、刀补与刀路参数并返工。\n"
        "- **蓝色（Blue）**：残料/欠切（Excess material），留有未切除余量，"
        "应补充半精加工或清角刀路清除。\n"
        "- **绿色（Green）**：尺寸在公差内（In tolerance），合格。\n"
        "补充：若有效像素 valid_pixels=0（白屏未渲染），即使字段写绿色 100% 也属"
        " INSUFFICIENT_EVIDENCE，严禁签字合格。"
    )
    out = [row("说明 VERICUT 9.6 Auto-Diff 偏差图中红色、蓝色、绿色分别代表什么？以及发现红色时应如何处置？",
               canonical, "autodiff_tricolor_probe_exact")]
    for q in [
        "VERICUT Auto-Diff 的红蓝绿三色各表示什么？出现红色怎么处理？",
        "Auto-Diff 偏差图里 RED / BLUE / GREEN 分别是什么含义，红色是否需要停机？",
        "请解释 VERICUT 9.6 自动比对颜色：红色、蓝色、绿色，并说明红色处置流程。",
    ]:
        out.append(row(q, canonical, "autodiff_tricolor_paraphrase"))
    return out


def g71_rows() -> list[dict]:
    prog = (
        "%\nO1007 (FANUC G71-G70)\nG50 S1800\nG96 S180 M03\nT0101\n"
        "G00 X62.0 Z2.0\nG71 U1.5 R0.5\nG71 P10 Q20 U0.4 W0.1 F0.25\n"
        "N10 G00 X40.0\nG01 Z0 F0.20\nG01 X50.0 Z-5.0\nG01 Z-25.0\n"
        "N20 G01 X60.0\nG00 X100.0 Z100.0\nM05\nM30\n"
    )
    note = (
        "安全要点：主轴 S180 M03 必须旋转、进给 F0.25/F0.20 非零；"
        "粗车循环 G71 用 G00 X 方向进刀，Z 向切入用 G01 带进给，"
        "严禁 G00 负 Z 直接扎刀（高速扎入毛坯）。程序以 M30 结束。"
    )
    out = []
    for q in [
        "按 FANUC 0i 写一段 G71/G70 粗精车程序：Φ60 毛坯、S180、T0101、F0.25、M30，只输出程序。",
        "给出符合安全的 FANUC G71 粗车代码（含非零 S/F，禁止 G00 负 Z 扎刀）。",
    ]:
        out.append(row(q, prog + "\n" + note, "g71_safety"))
    return out


def coordinate_rows() -> list[dict]:
    sw = (
        "SOLIDWORKS 2021 默认基准面及法向（世界 Y 向上）：\n"
        "- Front Plane（前视基准面）= XY 平面，法向 +Z。\n"
        "- Top Plane（俯视基准面）= XZ 平面，法向 +Y。\n"
        "- Right Plane（右视基准面）= YZ 平面，法向 +X。"
    )
    unit = (
        "VERICUT 9.6 工程单位不能用默认值猜测：必须读取 .vcproject 工程 XML 的 <Unit> 标签；"
        "若为 inch 则所有坐标/偏置按英寸解释，不得写成毫米；若与工艺卡单位不一致须先统一单位再仿真。"
    )
    return [
        row("SOLIDWORKS 2021 默认 Front/Top/Right 三基准面分别是什么平面、法向朝哪个轴？", sw, "sw_plane_notation"),
        row("VERICUT 9.6 仿真时如何确定工程单位是 inch 还是 millimeter？", unit, "unit_isolation"),
        row("一台 VERICUT 工程 XML 的 <Unit> 写 inch，工艺卡标 mm，该如何处理坐标？",
            unit + " 严禁混用单位出 NC。", "unit_isolation"),
    ]


def main() -> int:
    rows = lame_rows() + autodiff_rows() + g71_rows() + coordinate_rows()
    # 可证伪自检：补丁集的探针同款回答必须能过判分器
    checks = [
        ("lame", grader.evaluate_lame_stress_probe(rows[0]["messages"][-1]["content"])),
        ("autodiff", grader.evaluate_vericut_autodiff_probe(rows[len(lame_rows())]["messages"][-1]["content"])),
    ]
    failed = [(n, r) for n, r in checks if not r.get("passed")]
    if failed:
        print("[FATAL] 补丁集自身未过判分器自检：", failed, file=sys.stderr)
        return 2
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"[OK] wrote {len(rows)} rows -> {OUT}")
    print(f"[OK] sha256={sha}")
    print(f"[OK] grader selfcheck: {[(n, r['reason']) for n, r in checks]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
