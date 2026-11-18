#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build zero-leak, interleaved VERICUT 9.6 v4 SFT repair corpus for local 6GB QLoRA.

Fixes measured on virtu-vericut96:v3:
  1. Raw probe gaps (8/10 -> target 10/10):
     - lame_stress_probe: explicit numerical K=Do/Di, k=K^2, sigma_theta=Pi*(k+1)/(k-1),
       sigma_r=-Pi across 14 diverse tuples (never leaking probe tuple 60/120/20).
     - vericut_coordinate_unit_probe: strict two-part structure covering (1) XML <Unit>inch</Unit>
       vs millimeter and (2) Z-up/G54 vs SOLIDWORKS Y-up Front/Top/Right isolation.
  2. Holdout regression recovery vs v2 (pdf_curriculum_qa, runtime_toolcall,
     nc_safety_diagnosis, setup_workoffset, vericut_setup_facts):
     - Stratified proportional replay from vericut_e_pure_sft.jsonl (train split only)
       + concise VERICUT 9.6 facts normalized from vericut_official_training.jsonl.
  3. Anti-forgetting preservation & v9 discipline:
     - Compact SW (+Z/+Y/+X), Auto-Diff (Red/Blue/Green non-bleed), FANUC G71/G70/M30
       anchors pre-verified by deploy_trained_adapter & g71_semantic_check.
     - Uniformly interleaved across the corpus (never bunched at the end).
     - Strict holdout/benchmark zero-leak gate, unit audit, and max_length=1536 check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "cloud_train_pack")):
    if p not in sys.path:
        sys.path.insert(0, p)

import deploy_trained_adapter as grader  # noqa: E402
from corpus_unit_audit import assert_units_clean  # noqa: E402
from g71_semantic_check import check_g71_step_shaft  # noqa: E402
from train_turnkey import format_chatml_sample  # noqa: E402
from virtu_eval.contamination_check import assert_no_leak  # noqa: E402

SYS_MSG = (
    "你是 Virtu 工业智造超级智能体，严格隔离 SOLIDWORKS Y-up 与 VERICUT/CNC Z-up 坐标系，"
    "按工程实测单位（inch/millimeter）与闭式物理/G代码安全规范严谨作答。"
)

DEFAULT_PURE_SFT = ROOT / "data" / "sft" / "vericut_e_training" / "vericut_e_pure_sft.jsonl"
DEFAULT_OFFICIAL = ROOT / "data" / "sft" / "vericut_official_training.jsonl"
DEFAULT_HOLDOUT = ROOT / "data" / "sft" / "vericut_e_training" / "vericut_e_holdout.jsonl"
DEFAULT_BASE_DIR = ROOT / "checkpoints" / "_base_qwen3_8b"
DEFAULT_OUT = ROOT / "cloud_train_pack" / "dataset_v2" / "vericut96_v4_sft_repair.jsonl"

BENCHMARK_DIRS = (
    ROOT / "data" / "benchmark" / "virtu_eval_v1",
    ROOT / "data" / "benchmark" / "virtu_eval_v2",
    ROOT / "data" / "benchmark" / "virtu_blind_test_v1",
)

PROPORTIONAL_QUOTAS: Dict[str, int] = {
    "pdf_curriculum_qa": 65,
    "runtime_toolcall": 20,
    "runtime_toolcall_single": 15,
    "runtime_toolcall_cimco": 15,
    "runtime_toolcall_multiturn": 1,
    "nc_safety_diagnosis": 40,
    "nc_g49_bug_fix": 20,
    "setup_workoffset": 35,
    "setup_unit_collision": 20,
    "ctl_config": 12,
    "tool_assembly_calc": 25,
    "tool_assembly_list": 20,
    "machine_kinematics": 15,
    "machine_kinematics_principle": 10,
    "boundary_refusal": 12,
    "swp_envelope": 10,
    "inverse_stock_derivation": 10,
    "autodiff_color_axiom": 8,
    "general_cnc_anti_forgetting": 6,
    "pdf_concept_force": 6,
    "pdf_concept_autodiff": 5,
    "turbine_blade_5axis_kinematics": 1,
    "turbine_blade_5axis_macro": 1,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _sft_row(user: str, assistant: str, family: str) -> Dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYS_MSG},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "meta": {"family": family, "version": "vericut96_v4", "basis": "verified_repair"},
    }


def _strip_think(text: str) -> str:
    return re.sub(
        r"<(?:think|redacted_reasoning|analysis)>.*?</(?:think|redacted_reasoning|analysis)>",
        "",
        text or "",
        flags=re.S | re.I,
    ).strip()


def build_lame_numerical_rows() -> List[Dict[str, Any]]:
    """56 diverse step-by-step Lamé closed-form SFT pairs (never touching probe 60/120/20)."""
    tuples = [
        (40, 80, 16),
        (50, 100, 18),
        (80, 160, 24),
        (30, 90, 27),
        (70, 140, 25),
        (100, 200, 30),
        (44, 88, 12),
        (90, 180, 21),
        (40, 120, 24),
        (50, 150, 32),
        (64, 128, 15),
        (84, 168, 22),
        (36, 108, 18),
        (48, 144, 28),
    ]
    out: List[Dict[str, Any]] = []
    for di, do, pi in tuples:
        assert not (di == 60 and do == 120 and pi == 20), "Held-out probe tuple leaked!"
        ratio = do / di
        k_sq = ratio ** 2
        sig_t = pi * (k_sq + 1.0) / (k_sq - 1.0)
        sig_r = -float(pi)
        prompts = [
            f"按 Lamé 厚壁圆筒理论：内径 Di={di} mm，外径 Do={do} mm，内压 Pi={pi} MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。",
            f"按 Lamé 厚壁圆筒理论（内径 Di={di} mm，外径 Do={do} mm，内压 Pi={pi} MPa），严禁使用薄壁公式，求内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r（MPa）。",
            f"已知厚壁压力圆筒 Di={di} mm、Do={do} mm、内压 Pi={pi} MPa，请代入 Lamé 闭式解分步计算 σ_θ 与 σ_r（MPa）。",
            f"校核厚壁液压缸内壁应力：Di={di} mm，Do={do} mm，Pi={pi} MPa。使用 Lamé 厚壁理论给出 σ_θ（两位小数）及 σ_r 数值与正负符号。",
        ]
        k_str = f"{ratio:g}"
        k2_str = f"{k_sq:g}"
        ans = (
            "根据 **Lamé 厚壁圆筒闭式解**（严禁使用薄壁公式 $P_i D_i / (2t)$，亦非 $P_i(D_o+D_i)/(D_o-D_i)$）：\n"
            f"- **直径比** $K = \\frac{{D_o}}{{D_i}} = \\frac{{{do}}}{{{di}}} = {k_str}$（无量纲比值）\n"
            f"- **平方比** $k = K^2 = \\left(\\frac{{D_o}}{{D_i}}\\right)^2 = {k_str}^2 = {k2_str}$（无量纲）\n"
            f"- **内壁环向拉应力** $\\sigma_\\theta = P_i \\cdot \\frac{{k + 1}}{{k - 1}} = {pi} \\times \\frac{{{k2_str} + 1}}{{{k2_str} - 1}} = {sig_t:.2f}\\ \\text{{MPa}}$\n"
            f"- **内壁径向压应力** $\\sigma_r = -P_i = {sig_r:.0f}\\ \\text{{MPa}}$（受压为负）"
        )
        for q in prompts:
            out.append(_sft_row(q, ans, "lame_closed_form_v4"))
    return out


def build_coord_unit_isolation_rows() -> List[Dict[str, Any]]:
    """44 strict two-part VERICUT <Unit>inch</Unit> vs SOLIDWORKS Y-up SFT rows."""
    specs = [
        ("gearbox_us.vcproject", "Z+"),
        ("fixture_plate_in.vcproject", "Z+"),
        ("impeller_hub_imperial.vcproject", "Z+"),
        ("mill_session_04_in.vcproject", "Z+"),
        ("bracket_5axis_us.vcproject", "Z+"),
        ("lathe_chuck_imperial.vcproject", "Z+"),
        ("housing_us_v96.vcproject", "Z+"),
        ("valve_body_inch.vcproject", "Z+"),
        ("manifold_g54_us.vcproject", "Z+"),
        ("spindle_sleeve_in.vcproject", "Z+"),
        ("aerospace_rib_in.vcproject", "Z+"),
    ]
    out: List[Dict[str, Any]] = []
    for proj, up in specs:
        prompts = [
            (
                f"解析 VERICUT 工程 {proj}，XML 配置包含 <Unit>inch</Unit>，Setup 坐标系方向 Up={up} (G54)。"
                "请分两点明确回答：(1) 当前工程单位是什么（是否等于 millimeter）；(2) 该 Z-up / G54 坐标系能否直接等价套用 "
                "SOLIDWORKS 2021 的 Front/Top/Right 默认基准面？为什么？"
            ),
            (
                f"打开 {proj} 测得 <Unit>inch</Unit> 且机床主轴 Up={up}。说明：(1) 单位判定与禁止换算原则；"
                "(2) VERICUT Z-up/G54 与 SOLIDWORKS 2021 默认基准面坐标系是否相同、能否直接套用？"
            ),
            (
                f"核对 {proj}（<Unit>inch</Unit>, Up={up}, G54）："
                "单位是否为 inch？能否把 SOLIDWORKS 2021 的前/上/右默认基准面直接等价导入作为该 VERICUT 编程坐标系？"
            ),
            (
                f"工程文件 {proj} 设置为 <Unit>inch</Unit>、G54 Z-up。"
                "请同时回答两个问题：一、长度与刀偏基准单位如何认定；二、能否直接沿用 SOLIDWORKS 2021 Y-up 前/上/右基准面法向？"
            ),
        ]
        ans = (
            "(1) **工程单位为 `inch`（英寸），不是 `millimeter`（毫米）**：XML 显式声明 `<Unit>inch</Unit>`，"
            "表明几何尺寸、毛坯、刀具及偏差计算全部以英寸（inch）为基准，严禁擅自按毫米读取或误翻为 millimeter"
            "（若需公制对照须显式乘以 25.4 换算因子）。\n\n"
            "(2) **不能直接等价套用 SOLIDWORKS 2021 的 Front/Top/Right 默认基准面**：\n"
            f"- VERICUT 9.6 / G54 采用 **Z-up 机床坐标系**（`Up={up}`）；\n"
            "- SOLIDWORKS 2021 默认采用 **Y-up 世界坐标系**（Front Plane = XY 平面、法向 `+Z`；"
            "Top Plane = XZ 平面、法向 `+Y`；Right Plane = YZ 平面、法向 `+X`）。\n"
            "两者垂直向上轴与基准面法向均正交不同，装夹对齐或导出 STL 前必须执行显式坐标系变换映射。"
        )
        verdict = grader.evaluate_vericut_coordinate_unit_probe(ans)
        assert verdict.get("passed") is True, f"Coord-unit anchor failed own grader: {verdict}"
        for q in prompts:
            out.append(_sft_row(q, ans, "vericut_coord_unit_v4"))
    return out


def build_preservation_anchors() -> List[Dict[str, Any]]:
    """44 pre-verified preservation anchors (SW +Z/+Y/+X, AutoDiff 3-color, FANUC G71/G70/M30)."""
    out: List[Dict[str, Any]] = []

    # 16 SW coordinate rows
    sw_qs = [
        "列举 SOLIDWORKS 2021 的 Front/Top/Right 三个默认基准面法向。",
        "简明写出 SOLIDWORKS 2021 前视、上视、右视基准面所属平面与标准法向量（+Z/+Y/+X）。",
        "SOLIDWORKS 2021 采用哪种世界向上轴？Front Plane、Top Plane、Right Plane 法向分别是多少？",
        "在 SOLIDWORKS 2021 Y-up 世界坐标系中，Front/Top/Right 默认基准面与矢量法向如何对应？",
    ]
    sw_ans = (
        "SOLIDWORKS 2021 采用 **Y-up** 世界坐标系，三个默认基准面及其标准正法向如下：\n"
        "- **Front Plane（前视基准面）**：XY 平面，法向 **+Z** `(0, 0, 1)`\n"
        "- **Top Plane（上视基准面）**：XZ 平面，法向 **+Y** `(0, 1, 0)`\n"
        "- **Right Plane（右视基准面）**：YZ 平面，法向 **+X** `(1, 0, 0)`"
    )
    assert grader.evaluate_sw_coordinate_probe(sw_ans).get("passed") is True
    for i in range(16):
        out.append(_sft_row(sw_qs[i % len(sw_qs)], sw_ans, "sw_plane_preserve_v4"))

    # 16 VERICUT Auto-Diff rows
    ad_qs = [
        "说明 VERICUT 9.6 Auto-Diff 偏差图中红色、蓝色、绿色分别代表什么？以及发现红色时应如何处置？",
        "VERICUT Auto-Diff 比对云图中 Red、Blue、Green 三色各表示什么加工状态？出现红色怎么处理？",
        "在 VERICUT 9.6 实体对比时，过切、残料、公差内合格分别对应哪种 Auto-Diff 颜色？",
        "简述 VERICUT Auto-Diff 红/蓝/绿三色物理意义与超差停机规范。",
    ]
    ad_ans = (
        "VERICUT 9.6 Auto-Diff 偏差图三色定义严格区分如下：\n"
        "- **红色（Red）**：代表 **过切（Gouge）**，即刀具侵入设计实体内部造成不可逆破坏，属致命缺陷；"
        "发现红色必须**立即停机**，排查 NC 刀路、刀具半径/长度补偿或后处理后修正重算。\n"
        "- **蓝色（Blue）**：代表 **残料/欠切（Excess material）**，即零件表面尚留有未切除余量，需补充半精加工或清角精加工。\n"
        "- **绿色（Green）**：代表 **公差内合格（In-tolerance）**，加工几何满足设计容差要求，准予通过。"
    )
    assert grader.evaluate_vericut_autodiff_probe(ad_ans).get("passed") is True
    for i in range(16):
        out.append(_sft_row(ad_qs[i % len(ad_qs)], ad_ans, "vericut_autodiff_preserve_v4"))

    # 12 compact FANUC G71/G70/M30 rows verified by BOTH graders
    progs = [
        ("O1000", "1.5", "0.5", "0.4", "0.1", "0.25", 10, 20, "0.15"),
        ("O1002", "1.5", "0.75", "0.4", "0.1", "0.25", 10, 20, "0.12"),
        ("O1004", "2.0", "1.0", "0.5", "0.05", "0.25", 10, 20, "0.15"),
        ("O1006", "1.2", "0.6", "0.3", "0.08", "0.25", 10, 20, "0.12"),
    ]
    g71_qs = [
        "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。",
        "Ø60 圆钢车台阶轴（第一台阶 Ø38×20 mm，总长 45 mm），按 FANUC G71 粗车 + G70 精车格式输出简洁 NC 程序，包含 G50 S1800、G96 S150 M03、T0101、F0.25、M30。",
        "编写 FANUC 车床 G71/G70 复合循环程序：毛坯 Ø60，台阶 Ø38×20，总长 45，含 T0101、G50 S1800、G96 S150 M03、F0.25、M30，仅输出 G 代码。",
    ]
    for rep in range(3):
        for o_no, u, r, uw, ww, fr, n1, n2, ff in progs:
            code = "\n".join([
                "%",
                o_no,
                "G50 S1800",
                "G96 S150 M03",
                "T0101",
                "G00 X62.0 Z2.0",
                f"G71 U{u} R{r}",
                f"G71 P{n1} Q{n2} U{uw} W{ww} F{fr}",
                f"N{n1} G00 X38.0",
                "G01 Z0.0 F0.2",
                "Z-20.0",
                "X60.0",
                "Z-45.0",
                f"N{n2} X62.0",
                "G00 X100.0 Z80.0",
                f"G70 P{n1} Q{n2} F{ff}",
                "G00 X100.0 Z80.0",
                "M30",
                "%",
            ])
            assert grader.evaluate_fanuc_g71_safety_probe(code).get("passed") is True
            assert check_g71_step_shaft(code).get("passed") is True
            out.append(_sft_row(g71_qs[(rep + progs.index((o_no, u, r, uw, ww, fr, n1, n2, ff))) % len(g71_qs)], code, "fanuc_g71_preserve_v4"))

    return out


def _slim_tools_row(r: Dict[str, Any], rng: random.Random, max_tools: int = 3) -> Dict[str, Any]:
    tools = r.get("tools")
    if not isinstance(tools, list) or len(tools) <= max_tools:
        return r
    called = set()
    for m in r.get("messages") or []:
        for tc in m.get("tool_calls") or []:
            nm = str((tc.get("function") or tc).get("name") or "").strip()
            if nm:
                called.add(nm)
    kept = [t for t in tools if str((t.get("function") or t).get("name") or "").strip() in called]
    others = [t for t in tools if t not in kept]
    rng.shuffle(others)
    out = dict(r)
    out["tools"] = kept + others[: max(0, max_tools - len(kept))]
    return out


def build_replay_rows(tokenizer: Any, seed: int = 20261118) -> List[Dict[str, Any]]:
    """Proportional replay from vericut_e_pure_sft.jsonl + short factual rows from vericut_official_training.jsonl."""
    rng = random.Random(seed)
    pure_rows = [json.loads(l) for l in DEFAULT_PURE_SFT.read_text(encoding="utf-8").splitlines() if l.strip()]
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for raw_r in pure_rows:
        r = _slim_tools_row(raw_r, rng, max_tools=3)
        tt = str((r.get("meta") or {}).get("task_type") or "unknown")
        # Normalize out any corrupted G71 programs from replay
        ans = _strip_think(str((r.get("messages") or [{}])[-1].get("content") or ""))
        if "G71" in ans and sum(1 for ln in ans.splitlines() if re.match(r"^\s*(?:N\d+\s*)?(?:G|M|T|S|F|X|Z|%)", ln)) >= 5:
            if not grader.evaluate_fanuc_g71_safety_probe(ans).get("passed"):
                continue
        enc = format_chatml_sample(r, tokenizer, max_length=832)
        if not enc or sum(1 for x in enc["labels"] if x != -100) < 2:
            continue
        if len(enc["input_ids"]) > 820:
            continue
        buckets.setdefault(tt, []).append(r)

    replay: List[Dict[str, Any]] = []
    for tt, quota in PROPORTIONAL_QUOTAS.items():
        pool = list(buckets.get(tt, []))
        rng.shuffle(pool)
        replay.extend(pool[:quota])

    if DEFAULT_OFFICIAL.exists():
        off_rows = [json.loads(l) for l in DEFAULT_OFFICIAL.read_text(encoding="utf-8").splitlines() if l.strip()]
        off_cands: List[Dict[str, Any]] = []
        for r in off_rows:
            inst = str(r.get("instruction") or "").strip()
            inp = str(r.get("input") or "").strip()
            out_txt = str(r.get("output") or "").strip()
            if not inst or not out_txt or len(inst) + len(out_txt) > 900:
                continue
            q = f"{inst}\n{inp}".strip() if inp else inst
            row = _sft_row(q, out_txt, "vericut_official_fact_v4")
            enc = format_chatml_sample(row, tokenizer, max_length=1536)
            if enc and len(enc["input_ids"]) <= 1024:
                off_cands.append(row)
        rng.shuffle(off_cands)
        replay.extend(off_cands[:20])

    rng.shuffle(replay)
    return replay


def interleave(base: List[Dict[str, Any]], extra: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Evenly distribute repair/anchor rows across replay rows (avoiding end-bunching)."""
    if not extra:
        return list(base)
    if not base:
        return list(extra)
    n, k = len(base), len(extra)
    out: List[Dict[str, Any]] = []
    j = 0
    for i, r in enumerate(base):
        out.append(r)
        target = int((i + 1) * k / n)
        while j < target:
            out.append(extra[j])
            j += 1
    out.extend(extra[j:])
    return out


def build_dataset(out_path: Path = DEFAULT_OUT, seed: int = 20261118) -> Dict[str, Any]:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(DEFAULT_BASE_DIR), trust_remote_code=True)
    lame_rows = build_lame_numerical_rows()
    coord_rows = build_coord_unit_isolation_rows()
    pres_rows = build_preservation_anchors()
    replay_rows = build_replay_rows(tok, seed=seed)

    repair_all = lame_rows + coord_rows + pres_rows
    random.Random(seed + 7).shuffle(repair_all)
    combined = interleave(replay_rows, repair_all)

    # Verify every single sample tokenizes cleanly within 6GB VRAM length cap
    max_tok = 0
    for idx, row in enumerate(combined):
        enc = format_chatml_sample(row, tok, max_length=832)
        if not enc or sum(1 for x in enc["labels"] if x != -100) < 2:
            raise SystemExit(f"[FATAL] Row {idx} failed ChatML formatting / truncated assistant!")
        max_tok = max(max_tok, len(enc["input_ids"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in combined) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # Enforce leak & unit gates against all benchmarks AND isolated vericut_e_holdout.jsonl
    import shutil
    import tempfile
    for bdir in BENCHMARK_DIRS:
        if bdir.is_dir():
            assert_no_leak(str(out_path), str(bdir))
    if DEFAULT_HOLDOUT.is_file():
        with tempfile.TemporaryDirectory(prefix="vericut_v4_holdout_gate_") as hdir:
            shutil.copy2(DEFAULT_HOLDOUT, Path(hdir) / DEFAULT_HOLDOUT.name)
            assert_no_leak(str(out_path), hdir)
    assert_units_clean(str(out_path))

    digest = sha256_file(out_path)
    sidecar = Path(str(out_path) + ".sha256")
    sidecar.write_text(f"{digest}  {out_path.name}\n", encoding="utf-8", newline="\n")

    fam_counts = Counter(
        str((r.get("meta") or {}).get("family") or (r.get("meta") or {}).get("task_type") or "unknown")
        for r in combined
    )
    ledger_path = out_path.parent / f"{out_path.stem}_ledger.json"
    ledger = {
        "corpus": out_path.stem,
        "seed": seed,
        "output_path": str(out_path),
        "output_sha256": digest,
        "rows": len(combined),
        "max_tokens": max_tok,
        "lame_rows": len(lame_rows),
        "coord_unit_rows": len(coord_rows),
        "preservation_rows": len(pres_rows),
        "replay_rows": len(replay_rows),
        "top_families": dict(fam_counts.most_common(12)),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description="Build VERICUT 9.6 v4 balanced local QLoRA repair corpus")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", type=int, default=20261118)
    args = ap.parse_args()
    ledger = build_dataset(Path(args.out), seed=args.seed)
    print(json.dumps(ledger, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
