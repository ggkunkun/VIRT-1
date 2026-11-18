#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/build_vericut96_cloud_datasets.py — 构建 VERICUT 9.6 云端直训防遗忘混合语料 (SFT + DPO)

遵循 AGENTS.md §8 测量宪法与 fail-closed 门禁：
  1. 验明源文件真实 SHA256（vericut_e_training_agent_sft.jsonl / vericut_e_training_dpo.jsonl 等）；
  2. 将 VERICUT 9.6 专项语料与无泄漏通用六软件 Agent / 物理公式 / 安全简洁回放按可控权重混合：
     - SFT Mix: 2x VERICUT (990) + 分层抽样 virtu_engine_agent_v1 (900) + 分层抽样 virtu_v3_text_sft (300) = 2,190 条
     - 对含 OpenAI `tool_calls` 但缺 `tools` 字段的回放行，自动挂载经 sanitize_tool_defs 处理的运行时工具子集，
       使 `cloud_train_pack/train_turnkey.py` 与 `scripts/validate_render_dataset.py` (Qwen3 chat_template) 渲染 100% 一致；
     - DPO Mix: VERICUT DPO (104) + dpo_concise_pairs (30) + safety_boundary_dpo_pairs (28) = 162 对（零基准泄漏）；
  3. 对产物执行三重硬门禁：
     - `assert_no_leak` 对齐 virtu_eval_v1 / virtu_eval_phys_v1 / virtu_eval_cl_v1 / VERICUT 两套 holdout 均为 0 硬泄漏；
     - `assert_units_clean` (inertia_unit_bad == 0)；
     - `validate_dpo_pairs` 与 system prompt <= 702B 全通过；
  4. 写入 `.sha256` 与 `*_ledger.json` 供 `run_vericut96.sh` 与 `train_turnkey.py` 强制验真。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
PACK_DIR = ROOT / "cloud_train_pack"
for _p in (str(ROOT), str(SCRIPTS_DIR), str(PACK_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from corpus_unit_audit import assert_units_clean  # noqa: E402
from gate_all90_dataset import SYSTEM_PROMPT_MAX_BYTES, load_known_tool_names  # noqa: E402
from train_dpo_all90 import validate_dpo_pairs  # noqa: E402
from virtu_eval.contamination_check import assert_no_leak, normalize  # noqa: E402

DEFAULT_VERICUT_SFT = ROOT / "data" / "train" / "vericut_e_training_v1" / "train" / "vericut_e_training_agent_sft.jsonl"
DEFAULT_VERICUT_DPO = ROOT / "data" / "train" / "vericut_e_training_v1" / "dpo" / "vericut_e_training_dpo.jsonl"
DEFAULT_VERICUT_HOLDOUT = ROOT / "data" / "train" / "vericut_e_training_v1" / "holdout" / "vericut_e_training_holdout.jsonl"
DEFAULT_KB_HOLDOUT = ROOT / "knowledge_base" / "six_software" / "training" / "datasets" / "vericut_holdout.jsonl"

DEFAULT_ENGINE_REPLAY = ROOT / "data" / "train" / "virtu_engine_agent_v1" / "train" / "virtu_engine_agent_v1.jsonl"
DEFAULT_TEXT_REPLAY = ROOT / "data" / "train" / "virtu_v3" / "train" / "virtu_v3_text_sft.jsonl"
DEFAULT_CONCISE_DPO = PACK_DIR / "dataset" / "dpo_concise_pairs.jsonl"
DEFAULT_SAFETY_DPO = PACK_DIR / "dataset" / "safety_boundary_dpo_pairs.jsonl"
DEFAULT_EXTRA_HOLDOUTS = (
    ROOT / "data" / "sft" / "vericut_e_training" / "vericut_e_holdout.jsonl",
    ROOT / "data" / "sft" / "six_software_real_assets" / "cloud_pack" / "vericut_holdout.jsonl",
)

DEFAULT_OUT_DIR = PACK_DIR / "dataset"
DEFAULT_SEED = 20261114
BENCHMARK_DIRS = (
    ROOT / "data" / "benchmark" / "virtu_eval_v1",
    ROOT / "data" / "benchmark" / "virtu_eval_phys_v1",
    ROOT / "data" / "benchmark" / "virtu_eval_cl_v1",
)
CORE_COMPANION_TOOLS = (
    "cadcam_preflight",
    "cadcam_solidworks_model",
    "cadcam_cimco_validate",
    "cadcam_vericut_simulate",
    "cadcam_visual_inspect",
)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                rows.append(json.loads(s))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON parse error in {path}:{idx}: {exc}") from exc
    return rows


def _verify_optional_ledger(data_path: Path) -> None:
    ledger = Path(str(data_path) + ".ledger.json")
    actual = sha256_file(data_path)
    if ledger.exists():
        meta = json.loads(ledger.read_text(encoding="utf-8"))
        exp = str(meta.get("output_sha256") or meta.get("sha256") or "").strip().lower()
        if exp and exp != actual.lower():
            raise SystemExit(
                f"[FATAL] 源语料 {data_path} 与 ledger SHA256 不一致: expected={exp[:16]} actual={actual[:16]}"
            )
    sidecar = Path(str(data_path) + ".sha256")
    if sidecar.exists():
        exp_sc = sidecar.read_text(encoding="utf-8").strip().split()[0].lower()
        if exp_sc and exp_sc != actual.lower():
            raise SystemExit(
                f"[FATAL] 源语料 {data_path} 与 sidecar .sha256 不一致: expected={exp_sc[:16]} actual={actual[:16]}"
            )


def _system_prompt_ok(row: Dict[str, Any]) -> bool:
    msgs = row.get("messages") or row.get("prompt") or []
    if not isinstance(msgs, list):
        return True
    for m in msgs:
        if isinstance(m, dict) and m.get("role") == "system":
            if len(str(m.get("content") or "").encode("utf-8")) > SYSTEM_PROMPT_MAX_BYTES:
                return False
    return True


def _build_sanitized_tool_map() -> Dict[str, Dict[str, Any]]:
    from cad_tools_iface import sanitize_tool_defs
    from virtu_eval.tool_schema import runtime_tools

    sanitized = sanitize_tool_defs(runtime_tools())
    by_name: Dict[str, Dict[str, Any]] = {}
    for t in sanitized:
        fn = t.get("function") or {}
        name = str(fn.get("name") or "").strip()
        if name:
            by_name[name] = t
    return by_name


def _extract_called_tool_names(row: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for m in row.get("messages") or []:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or tc
            nm = str(fn.get("name") or "").strip()
            if nm and nm not in names:
                names.append(nm)
    return names


def normalize_sft_replay_row(
    row: Dict[str, Any],
    tool_map: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """规范化回放行：若含 tool_calls 但缺 tools，挂接 sanitized 运行时工具子集保证 Qwen3 模板一致。"""
    if not _system_prompt_ok(row):
        return None
    msgs = row.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None
    out = json.loads(json.dumps(row, ensure_ascii=False))
    called = _extract_called_tool_names(out)
    has_tool_msg = any(m.get("role") == "tool" for m in msgs)
    if (called or has_tool_msg) and not out.get("tools"):
        selected: List[Dict[str, Any]] = []
        seen = set()
        for nm in list(called) + list(CORE_COMPANION_TOOLS):
            if nm in tool_map and nm not in seen:
                selected.append(tool_map[nm])
                seen.add(nm)
            elif nm in called and nm not in tool_map:
                # 跳过包含未知/已废弃工具的旧回放行，严防污染工具面
                return None
        if selected:
            out["tools"] = selected
    return out


def stratified_sample(
    rows: Sequence[Dict[str, Any]],
    limit: int,
    seed: int,
    key_fn,
) -> List[Dict[str, Any]]:
    if limit <= 0 or not rows:
        return []
    if len(rows) <= limit:
        rng = random.Random(seed)
        copied = list(rows)
        rng.shuffle(copied)
        return copied

    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        buckets[str(key_fn(r))].append(r)

    rng = random.Random(seed)
    bucket_keys = sorted(buckets.keys())
    for k in bucket_keys:
        rng.shuffle(buckets[k])

    selected: List[Dict[str, Any]] = []
    idx_map = {k: 0 for k in bucket_keys}
    while len(selected) < limit:
        progressed = False
        for k in bucket_keys:
            pos = idx_map[k]
            if pos < len(buckets[k]):
                selected.append(buckets[k][pos])
                idx_map[k] = pos + 1
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break
    rng.shuffle(selected)
    return selected


def _collect_user_prompts(paths: Iterable[Path]) -> set[str]:
    prompts: set[str] = set()
    for p in paths:
        if not p.exists():
            continue
        for row in _load_jsonl(p):
            msgs = row.get("messages") or row.get("prompt") or []
            if isinstance(msgs, list):
                for m in msgs:
                    if isinstance(m, dict) and m.get("role") == "user":
                        t = normalize(str(m.get("content") or ""))
                        if t:
                            prompts.add(t)
            else:
                t = normalize(str(msgs))
                if t:
                    prompts.add(t)
    return prompts


def _verify_no_holdout_leak(candidate_rows: Sequence[Dict[str, Any]], holdout_paths: Sequence[Path], label: str) -> None:
    held = _collect_user_prompts(holdout_paths)
    if not held:
        return
    hits = 0
    for r in candidate_rows:
        msgs = r.get("messages") or r.get("prompt") or []
        if isinstance(msgs, list):
            for m in msgs:
                if isinstance(m, dict) and m.get("role") == "user":
                    if normalize(str(m.get("content") or "")) in held:
                        hits += 1
        else:
            if normalize(str(msgs)) in held:
                hits += 1
    if hits:
        raise SystemExit(f"[FATAL] {label} 与 holdout 提示重合 {hits} 条，拒绝写出！")


def build_canonical_anti_regression_rows(seed: int = DEFAULT_SEED, limit: int = 36) -> List[Dict[str, Any]]:
    """Generate verified coordinate-isolation, Lamé, and FANUC G71/G70 anchor SFT rows.

    Prevents catastrophic forgetting across SOLIDWORKS Y-up vs VERICUT/NX/CNC Z-up,
    Lamé thick-cylinder closed-form elasticity, and FANUC turning zero-plunge rules.
    """
    if limit <= 0:
        return []
    sys_msg = "你是 Virtu 工业智造超级智能体，严格隔离不同 CAD/CAM 软件坐标系并遵循工程物理与安全规范。"
    assert len(sys_msg.encode("utf-8")) <= SYSTEM_PROMPT_MAX_BYTES

    candidates: List[Dict[str, Any]] = [
        {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": "说明 SOLIDWORKS 2021 与 VERICUT 9.6 / CNC 坐标系的本质差异，列举 Front/Top/Right 默认基准面法向。"},
                {"role": "assistant", "content": (
                    "两者坐标系定义完全隔离，严禁混用：\n"
                    "1. SOLIDWORKS 2021（Y-up）：默认世界 +Y 朝上；Front Plane（前视基准面）= XY 平面，法向 +Z (0,0,1)；"
                    "Top Plane（上视基准面）= XZ 平面，法向 +Y (0,1,0)；Right Plane（右视基准面）= YZ 平面，法向 +X (1,0,0)。\n"
                    "2. VERICUT 9.6 / CNC（Z-up / G54）：机床默认主轴与视图为 Up=Z+（以 .vcproject Setup/Component 节点实测为准），"
                    "编程零点使用 G54 工件坐标系，XML 中 Unit=\"inch\" 与 \"millimeter\" 必须按实测原样保留。"
                )},
            ],
            "meta": {"software": "cross", "family": "coordinate_isolation", "source": "canonical_anchor"},
        },
        {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": "在 SOLIDWORKS 2021 中执行旋转凸台草图拉伸，为什么不能直接套用机床 CNC 的 Z-up 假设来判断 Top Plane 法向？"},
                {"role": "assistant", "content": (
                    "因为 SOLIDWORKS 2021 采用 Y-up 世界坐标：Top Plane 对应 XZ 平面，法向为 +Y (0,1,0)；"
                    "而 Front Plane 为 XY 平面，法向 +Z (0,0,1)；Right Plane 为 YZ 平面，法向 +X (1,0,0)。"
                    "CNC/VERICUT 的 Z-up（Up=Z+）仅用于机床/CAM/仿真坐标系，跨软件建模前必须显式映射基准轴。"
                )},
            ],
            "meta": {"software": "solidworks", "family": "coordinate_isolation", "source": "canonical_anchor"},
        },
        {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": "读取到 VERICUT .vcproject 包含 <Unit>inch</Unit> 与 Setup 主轴 Up=Z+，与 SOLIDWORKS Y-up 模型对接时要注意什么？"},
                {"role": "assistant", "content": (
                    "第一，单位严格以实测 XML 的 inch（英寸）为准，不得擅自改写为 millimeter（毫米）或混算；"
                    "第二，VERICUT 9.6 仿真遵循 Z-up 与 G54 工件坐标系，而 SOLIDWORKS 2021 默认 Y-up"
                    "（Front=XY/+Z, Top=XZ/+Y, Right=YZ/+X），导入 STEP/STL 装夹至夹具组件时需确认坐标系变换，"
                    "Auto-Diff 红色=过切（致命停机）、蓝色=残料、绿色=公差内合格。"
                )},
            ],
            "meta": {"software": "vericut", "family": "coordinate_isolation", "source": "canonical_anchor"},
        },
    ]

    candidates.extend([
        {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": "VERICUT 9.6 Auto-Diff 比较显示红色、蓝色、绿色三种颜色，各自严格代表什么？分别应采取什么工程处理？"},
                {"role": "assistant", "content": (
                    "VERICUT 9.6 Auto-Diff 颜色定义严格唯一：\n"
                    "- 红色（Red）= 过切（Gouge / 切削侵入设计实体内部）：属致命缺陷，必须立即判停，修正刀路、刀具半径/长度补偿或重新后处理，严禁上机。\n"
                    "- 蓝色（Blue）= 残料（Excess material / 未切净余量）：应增加半精加工/清角精加工走刀或减小步距消除多余余量。\n"
                    "- 绿色（Green）= 公差内合格（In-tolerance）：表面尺寸满足允许偏差并达标通过。"
                )},
            ],
            "meta": {"software": "vericut", "family": "autodiff_triage", "source": "canonical_anchor"},
        },
        {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": "某型腔 VERICUT Auto-Diff 统计：Green=98.4%，Red=0.35%（最大过切 0.18 mm），Blue=1.25%。能否以绿色超过 95% 直接放行？"},
                {"role": "assistant", "content": (
                    "不能放行，必须判红返工。Auto-Diff 中只要存在 Red 过切（Gouge，本例 0.35%、最大过切 0.18 mm）即为致命缺陷，"
                    "不可用绿色高占比掩盖局部过切；需先定位过切区域刀路与补偿后重新仿真至 Red=0%，同时按需清理 Blue 残料。"
                )},
            ],
            "meta": {"software": "vericut", "family": "autodiff_triage", "source": "canonical_anchor"},
        },
        {
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": "VERICUT Auto-Diff 全表面无红色，仅局部圆角区域呈现蓝色（最大残料 +0.25 mm），应判定过切还是残料？"},
                {"role": "assistant", "content": (
                    "判定为蓝色残料（Excess material / 欠切，+0.25 mm），不是过切（Gouge 为红色）。"
                    "处理动作：使用更小半径球头刀/清角刀路补充半精或精加工，无需当作过切报废。"
                )},
            ],
            "meta": {"software": "vericut", "family": "autodiff_triage", "source": "canonical_anchor"},
        },
    ])

    lame_cases = [(40, 80, 15), (50, 100, 18), (50, 150, 24), (70, 140, 20), (80, 160, 25), (60, 180, 30)]
    for di, do, pi_mpa in lame_cases:
        k = (do / di) ** 2
        sig_t = pi_mpa * (k + 1.0) / (k - 1.0)
        sig_r = -float(pi_mpa)
        candidates.append({
            "messages": [
                {"role": "system", "content": sys_msg},
                {
                    "role": "user",
                    "content": (
                        f"按 Lamé 厚壁圆筒理论：内径 Di={di} mm，外径 Do={do} mm，内压 Pi={pi_mpa} MPa。"
                        f"计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        f"采用 Lamé 厚壁圆筒闭式解（严禁使用薄壁公式）：\n"
                        f"- 径比系数 k = (Do / Di)^2 = ({do} / {di})^2 = {k:.4g}\n"
                        f"- 内壁环向应力 σ_θ = Pi * (k + 1) / (k - 1) = {pi_mpa} * ({k:.4g} + 1) / ({k:.4g} - 1) = {sig_t:.2f} MPa\n"
                        f"- 内壁径向应力 σ_r = -Pi = {sig_r:.0f} MPa（受压为负）"
                    ),
                },
            ],
            "meta": {"software": "cae", "family": "lame_closed_form", "source": "canonical_anchor"},
        })

    g71_cases = [(50, 32, 18, 40), (64, 42, 22, 50), (70, 44, 25, 55), (80, 52, 28, 60)]
    for d_stock, d_step, l_step, l_tot in g71_cases:
        d_mid = d_stock - 6
        candidates.append({
            "messages": [
                {"role": "system", "content": sys_msg},
                {
                    "role": "user",
                    "content": (
                        f"用 FANUC ISO/G 格式为 Ø{d_stock} 棒料编写 G71 粗车+G70 精车台阶轴程序"
                        f"（第一台阶 Ø{d_step} 长 {l_step} mm，第二台阶 Ø{d_mid}，总长 {l_tot} mm），"
                        f"含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        f"O1108 (G71_G70_D{d_stock})\n"
                        f"G50 S1800\n"
                        f"G96 S150 M03\n"
                        f"T0101\n"
                        f"G0 X{d_stock + 2:.1f} Z2.0\n"
                        f"G71 U1.5 R0.5\n"
                        f"G71 P10 Q20 U0.4 W0.1 F0.25\n"
                        f"N10 G0 X{d_step:.1f}\n"
                        f"G1 Z0.0 F0.12\n"
                        f"G1 Z-{l_step:.1f}\n"
                        f"G1 X{d_mid:.1f}\n"
                        f"G1 Z-{l_tot:.1f}\n"
                        f"N20 X{d_stock + 2:.1f}\n"
                        f"G70 P10 Q20\n"
                        f"G0 X{d_stock + 20:.1f} Z50.0\n"
                        f"M30"
                    ),
                },
            ],
            "meta": {"software": "cimco", "family": "fanuc_g71_safety", "source": "canonical_anchor"},
        })

    rng = random.Random(seed + 77)
    out: List[Dict[str, Any]] = []
    idx = 0
    while len(out) < limit:
        out.append(json.loads(json.dumps(candidates[idx % len(candidates)], ensure_ascii=False)))
        idx += 1
    rng.shuffle(out)
    return out[:limit]


def build_canonical_anti_regression_dpo_rows(seed: int = DEFAULT_SEED, limit: int = 36) -> List[Dict[str, Any]]:
    """Build concise chosen/rejected DPO pairs blocking VERICUT Auto-Diff, Y-up/Z-up, unit, Lamé, and G71 regressions."""
    if limit <= 0:
        return []
    sys_msg = "你是 Virtu 工业智造超级智能体，严格隔离不同 CAD/CAM 软件坐标系并遵循工程物理与安全规范。"
    assert len(sys_msg.encode("utf-8")) <= SYSTEM_PROMPT_MAX_BYTES

    candidates: List[Dict[str, Any]] = []
    for gouge_mm, pct_green in ((0.12, 99.1), (0.25, 97.8), (0.08, 99.5), (0.35, 96.4)):
        candidates.append({
            "software": "vericut",
            "family": "autodiff_triage",
            "source": "canonical_dpo_anchor",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"VERICUT Auto-Diff 结果显示绿色 {pct_green}%，但存在局部红色区域（偏差 -{gouge_mm:.2f} mm），应如何判定与处置？"},
            ],
            "chosen": (
                f"必须立即判停返工：Auto-Diff 红色（Red）明确代表过切（Gouge，本次局部过切 {gouge_mm:.2f} mm），"
                f"属于致命制造缺陷，不能因绿色占比 {pct_green}% 较高而放行；应立即停机排查对应刀路、刀具半径补偿与毛坯定位，"
                "修正后重新仿真直至红色过切归零。"
            ),
            "rejected": (
                f"绿色占比已达 {pct_green}%，总体精度满足要求；局部红色区域属于少量残料（Excess Material Removed），"
                "可在后道人工打磨或继续执行下一工序，无需修改 NC 程序。"
            ),
        })

    for excess_mm in (0.18, 0.30, 0.45):
        candidates.append({
            "software": "vericut",
            "family": "autodiff_triage",
            "source": "canonical_dpo_anchor",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"VERICUT Auto-Diff 检测出转角区显示蓝色（正偏差 +{excess_mm:.2f} mm），无红色像素，如何处理？"},
            ],
            "chosen": (
                f"蓝色（Blue）代表残料/欠切（Excess material，剩余余量 +{excess_mm:.2f} mm），并非过切（Gouge 为红色）。"
                "应补充半精或清角精加工刀路清除残料，不要误判为过切停机报废。"
            ),
            "rejected": (
                f"蓝色区域表示严重过切 +{excess_mm:.2f} mm，零件已报废，需立即按过切事故停机更换毛坯。"
            ),
        })

    sw_prompts = [
        "在 SOLIDWORKS 2021 中创建拉伸基准草图，Front、Top、Right 三个默认基准面对应的平面与法向矢量是什么？",
        "将 SOLIDWORKS 2021 零件导入 VERICUT 9.6 / CNC 机床仿真前，如何区分两者的世界向上轴与基准面定义？",
    ]
    for q in sw_prompts:
        candidates.append({
            "software": "cross",
            "family": "coordinate_isolation",
            "source": "canonical_dpo_anchor",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": q},
            ],
            "chosen": (
                "必须严格隔离 SOLIDWORKS 2021（Y-up）与 VERICUT/CNC（Z-up）："
                "SOLIDWORKS 默认 +Y 朝上，Front=XY 平面（法向 +Z [0,0,1]）、Top=XZ 平面（法向 +Y [0,1,0]）、Right=YZ 平面（法向 +X [1,0,0]）；"
                "而 VERICUT 9.6 / NX / CNC 默认 Z-up 并以 G54 工件坐标系对刀，两者基准面不得互相套用。"
            ),
            "rejected": (
                "SOLIDWORKS 2021 与 CNC 机床一致均采用 Z-up 世界坐标：Top 为 XY 平面（法向 +Z）、Front 为 XZ 平面（法向 +Y），可直接按同一坐标系建模加工。"
            ),
        })

    for proj_name in ("aero_housing_in.vcproject", "manifold_block_us.vcproject"):
        candidates.append({
            "software": "vericut",
            "family": "unit_preservation",
            "source": "canonical_dpo_anchor",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"解析 {proj_name} 时发现 XML <Unit>inch</Unit> 且需要调用仿真验证，应该如何执行？"},
            ],
            "chosen": (
                '<tool_call>\n'
                f'{{"name": "cadcam_vericut_simulate", "arguments": {{"action": "run_simulation", "project_path": "{proj_name}", "unit": "inch"}}}}\n'
                '</tool_call>'
            ),
            "rejected": (
                f"通过 win32com.client.Dispatch('Vericut.Application') 打开 {proj_name}，"
                "并统一按 millimeter（mm）与 G21 口径读取坐标。"
            ),
        })

    for di, do, pi_mpa in ((40, 80, 15), (50, 100, 20), (60, 120, 25)):
        k = (do / di) ** 2
        sig_t = pi_mpa * (k + 1.0) / (k - 1.0)
        sig_r = -float(pi_mpa)
        candidates.append({
            "software": "cae",
            "family": "lame_closed_form",
            "source": "canonical_dpo_anchor",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"依据 Lamé 厚壁圆筒理论，内径 Di={di} mm、外径 Do={do} mm、内压 Pi={pi_mpa} MPa，内壁环向应力与径向应力如何求解？"},
            ],
            "chosen": (
                f"由 Lamé 闭式解：径比系数 k=(Do/Di)^2={k:.4g}；"
                f"内壁环向拉应力 sigma_theta = Pi*(k+1)/(k-1) = {sig_t:.2f} MPa；"
                f"内壁径向压应力 sigma_r = -Pi = {sig_r:.0f} MPa（受压为负），不可与薄壁公式混淆。"
            ),
            "rejected": (
                f"按简化公式计算：sigma_theta = Pi*(k-1)/(k+1) = {pi_mpa*(k-1)/(k+1):.2f} MPa，"
                f"sigma_r = +{pi_mpa} MPa（正值）。"
            ),
        })

    for d_stock, d_step, l_step, l_tot in ((50, 32, 18, 40), (64, 42, 22, 50)):
        candidates.append({
            "software": "cimco",
            "family": "fanuc_g71_safety",
            "source": "canonical_dpo_anchor",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"对 Ø{d_stock} 棒料编写 FANUC 外圆粗精车台阶轴（Ø{d_step} 长 {l_step} mm，总长 {l_tot} mm），关键安全循环如何组织？"},
            ],
            "chosen": (
                f"O1208\nG50 S1800\nG96 S150 M03\nT0101\nG0 X{d_stock + 2:.1f} Z2.0\n"
                f"G71 U1.5 R0.5\nG71 P10 Q20 U0.4 W0.1 F0.25\n"
                f"N10 G0 X{d_step:.1f}\nG1 Z0.0 F0.12\nG1 Z-{l_step:.1f}\nG1 X{d_stock - 4:.1f}\nG1 Z-{l_tot:.1f}\nN20 X{d_stock + 2:.1f}\n"
                f"G70 P10 Q20\nG0 X{d_stock + 20:.1f} Z50.0\nM30"
            ),
            "rejected": (
                f"O1208\nT0101\nG96 S150 M03\nG0 X{d_step:.1f} Z-10.0\n"
                f"G71 P10 Q20 U0.4 W0.1 F0.25\nN10 G1 Z-{l_tot:.1f}\nN20 X{d_stock:.1f}\nM30"
            ),
        })

    rng = random.Random(seed + 177)
    out: List[Dict[str, Any]] = []
    idx = 0
    while len(out) < limit:
        out.append(json.loads(json.dumps(candidates[idx % len(candidates)], ensure_ascii=False)))
        idx += 1
    rng.shuffle(out)
    return out[:limit]


def build_vericut96_v3_dpo_repair_rows(
    seed: int = DEFAULT_SEED,
    repeat: int = 3,
) -> List[Dict[str, Any]]:
    """Build zero-leak targeted DPO repair pairs for measured v2 deployment probe regressions."""
    sys_msg = "你是 Virtu 工业智造超级智能体，严格隔离不同 CAD/CAM 软件坐标系并遵循工程物理与安全规范。"
    assert len(sys_msg.encode("utf-8")) <= SYSTEM_PROMPT_MAX_BYTES

    base_pairs: List[Dict[str, Any]] = []

    # 1. Auto-Diff 3-color semantic separation (Red=Gouge+Stop FIRST, Blue=Excess, Green=InTol LAST)
    autodiff_prompts = [
        ("汇总 VERICUT 9.6 Auto-Diff 偏差云图红、蓝、绿三类颜色定义及超差停机规范。", "full"),
        ("在 VERICUT 比较结果中，Red、Blue、Green 分别对应什么加工状态？为什么红色严禁写成 excess material？", "term"),
        ("生成 CNC 试切评审表：准确区分 Auto-Diff 红色过切、蓝色残料与绿色合格，并附红色处置流程。", "checklist"),
        ("当 VERICUT Auto-Diff 同时检出红色与蓝色斑块时，红、蓝、绿各代表什么几何误差？应按什么顺序处置？", "mixed"),
        ("解释 VERICUT Auto-Diff 颜色编码边界：如何避免把蓝色 excess material 混入红色 gouge 描述？", "disambig"),
        ("在 VERICUT 9.6 实体比对中，红、蓝、绿三种偏差颜色的物理含义与停机/修刀准则是什么？", "rules"),
    ]
    chosen_autodiff = (
        "VERICUT 9.6 Auto-Diff 偏差图三色定义严格唯一，禁止术语混写：\n"
        "- 红色（Red）= 过切（Gouge）：刀具切除侵入设计实体内部，属致命制造缺陷，必须立即停机排查 NC 刀路、刀具半径/长度补偿或后处理并修正重算（严禁误写为余量或欠切）。\n"
        "- 蓝色（Blue）= 残料/欠切（Excess material）：零件表面仍留有未切除余量，应补充半精加工或清角精加工走刀。\n"
        "- 绿色（Green）= 公差内合格（In-tolerance）：加工几何符合允许偏差范围，表面达标通过。"
    )
    rejected_autodiff_variants = [
        (
            "| 颜色 | 偏差状态 | 处理说明 |\n"
            "| --- | --- | --- |\n"
            "| 红色 (red) | 实际刀路显著偏移（gouge / excess material） | 检查刀路参数 |\n"
            "| 蓝色 (blue) | 未切净余量 | 补充精加工 |\n"
            "| 绿色 (green) | 在设计容差内（合格） | 放行 |"
        ),
        (
            "- 蓝色（Blue）：过切（Gouge），需要立即报废停机。\n"
            "- 红色（Red）：少量残料（Excess Material Removed），人工打磨即可。\n"
            "- 绿色（Green）：公差内合格（in-tolerance）。\n\n"
            "### 发现红色过切时的处置\n发现红色应立即停机排查。"
        ),
    ]
    for idx_ad, (q_ad, _kind) in enumerate(autodiff_prompts):
        base_pairs.append({
            "software": "vericut",
            "family": "autodiff_triage_repair",
            "source": "v3_repair_dpo",
            "prompt": [{"role": "system", "content": sys_msg}, {"role": "user", "content": q_ad}],
            "chosen": chosen_autodiff,
            "rejected": rejected_autodiff_variants[idx_ad % len(rejected_autodiff_variants)],
        })

    # 2. <Unit>inch</Unit> + Z-up/G54 vs SOLIDWORKS Y-up crisp isolation (no off-topic CAD ramble)
    coord_unit_specs = [
        ("gearbox_us.vcproject", "Z+", "inch"),
        ("fixture_plate_in.vcproject", "Z+", "inch"),
        ("impeller_hub_imperial.vcproject", "Z+", "inch"),
        ("mill_session_04_in.vcproject", "Z+", "inch"),
        ("bracket_5axis_us.vcproject", "Z+", "inch"),
    ]
    for proj, up_axis, unit_val in coord_unit_specs:
        base_pairs.append({
            "software": "vericut",
            "family": "coordinate_unit_isolation_repair",
            "source": "v3_repair_dpo",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {
                    "role": "user",
                    "content": (
                        f"读取 {proj} 的 XML 配置为 <Unit>{unit_val}</Unit> 且 Setup 主轴方向 Up={up_axis}。"
                        "请明确：(1) 工程单位是否为 inch；(2) 该 Z-up / G54 坐标系能否直接等价套用 "
                        "SOLIDWORKS 2021 的 Front/Top/Right 默认基准面？为什么？"
                    ),
                },
            ],
            "chosen": (
                f"(1) 工程单位为 `inch`（英寸），不是 `millimeter`（毫米）。XML `<Unit>{unit_val}</Unit>` "
                "明确限定内部尺寸与刀偏均以英寸计算，严禁擅自按毫米读取或改写。\n"
                "(2) **不能直接等价套用 SOLIDWORKS 2021 默认基准面**。原因："
                f"VERICUT / G54 采用 Z-up 机床坐标系（Up={up_axis}），而 SOLIDWORKS 2021 默认采用 Y-up 世界坐标系"
                "（Front=XY/+Z、Top=XZ/+Y、Right=YZ/+X），两者垂直向上轴与基准面法向均正交不同，装夹对齐前必须做坐标系变换映射。"
            ),
            "rejected": (
                f"(1) 工程单位是 `{unit_val}`。\n"
                "(2) 在 AutoCAD、Desing Engineering、VERICUT、Zebra、Virtuoso 等多种软件之间迁移时，"
                "可以直接沿用 SOLIDWORKS 2021 的 Front/Top/Right 原基准面继续仿真，无需坐标系变换映射。"
            ),
        })

    # 3. Lamé thick-cylinder closed-form (dimensionless ratio, never MPa on k, held-out numbers excluded)
    lame_repair_tuples = [
        (40, 80, 16),
        (50, 100, 18),
        (80, 160, 24),
        (30, 90, 27),
        (70, 140, 25),
        (100, 200, 30),
        (44, 88, 12),
        (90, 180, 21),
    ]
    for di, do, pi_mpa in lame_repair_tuples:
        ratio = do / di
        k_sq = ratio ** 2
        sig_t = pi_mpa * (k_sq + 1.0) / (k_sq - 1.0)
        sig_r = -float(pi_mpa)
        thin_err = pi_mpa * (di / 2.0) / ((do - di) / 2.0)
        inv_ratio = di / do
        base_pairs.append({
            "software": "cae",
            "family": "lame_closed_form_repair",
            "source": "v3_repair_dpo",
            "prompt": [
                {"role": "system", "content": sys_msg},
                {
                    "role": "user",
                    "content": (
                        f"按 Lamé 厚壁圆筒理论：内径 Di={di} mm，外径 Do={do} mm，内压 Pi={pi_mpa} MPa。"
                        "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"
                    ),
                },
            ],
            "chosen": (
                "采用 Lamé 厚壁圆筒闭式解（严禁使用薄壁公式）：\n"
                f"- 直径比 K = Do / Di = {do} / {di} = {ratio:.4g}（无量纲比值，无单位，严禁标为 MPa）\n"
                f"- 平方比 k = K^2 = (Do / Di)^2 = {k_sq:.4g}（无量纲）\n"
                f"- 内壁环向拉应力 σ_θ = Pi * (k + 1) / (k - 1) = {pi_mpa} * ({k_sq:.4g} + 1) / ({k_sq:.4g} - 1) = {sig_t:.2f} MPa\n"
                f"- 内壁径向压应力 σ_r = -Pi = {sig_r:.0f} MPa（受压为负）"
            ),
            "rejected": (
                f"- 径比系数 k = Di / Do = {inv_ratio:.4g} MPa\n"
                f"- 内壁环向应力 σ_θ = Pi * (k^2 + 1) / (k^2 - 1) 或薄壁近似 {thin_err:.2f} MPa，σ_r = +{pi_mpa} MPa"
            ),
        })

    # 4. SOLIDWORKS 2021 explicit +Z / +Y / +X vector notation (no Z+ trailing confusion or broken table)
    sw_prompts = [
        "简明列出 SOLIDWORKS 2021 前视、上视、右视三个默认基准面的平面与标准正法向（用 +Z/+Y/+X 表示）。",
        "在 SOLIDWORKS 2021 零件建模中，Front Plane、Top Plane、Right Plane 分别对应哪个平面及法向量？",
        "汇总 SOLIDWORKS 2021 世界坐标系 Y-up 下 Front/Top/Right 默认基准面与 +Z/+Y/+X 法向关系。",
        "为什么在 SOLIDWORKS 2021 中拉伸前视基准面草图时，Front Plane 法向是 +Z 而不是 +Y？请写出三基准面法向。",
    ]
    chosen_sw = (
        "SOLIDWORKS 2021 采用 Y-up 世界坐标系，三个默认基准面及其标准法向为：\n"
        "- Front Plane（前视基准面）：XY 平面，法向 +Z (0, 0, 1)\n"
        "- Top Plane（上视基准面）：XZ 平面，法向 +Y (0, 1, 0)\n"
        "- Right Plane（右视基准面）：YZ 平面，法向 +X (1, 0, 0)"
    )
    # 负样本必须**语义真正错误**才能当 DPO 的可证伪负例。
    # 原实现只在「记法」上与 chosen 不同（表格 + 尾随 Z+），而 2026-11-15 判分器
    # 改用「定义窗口」判定后不再惩罚该记法 ⇒ 负样本被判 passed=True，
    # 训练对退化成 (chosen=正确, rejected=也正确) 的纯噪声对。
    # 现在把法向互换（Front=+Y / Top=+Z），语义层就是错的，判分器必须判 FAIL。
    rejected_sw = (
        "| 基准面 | 方向 | 说明 |\n"
        "| Front Plane | Y+ 向上 | 前视基准面 |\n"
        "| Top Plane | Z+ 朝前 | 上视基准面 |\n"
        "| Right Plane | X+ 朝右 | 右视基准面 |"
    )
    for q_sw in sw_prompts:
        base_pairs.append({
            "software": "solidworks",
            "family": "sw_plane_notation_repair",
            "source": "v3_repair_dpo",
            "prompt": [{"role": "system", "content": sys_msg}, {"role": "user", "content": q_sw}],
            "chosen": chosen_sw,
            "rejected": rejected_sw,
        })

    out: List[Dict[str, Any]] = []
    for _ in range(max(1, repeat)):
        out.extend(json.loads(json.dumps(r, ensure_ascii=False)) for r in base_pairs)
    rng = random.Random(seed + 303)
    rng.shuffle(out)
    return out


def build_vericut96_v3_dpo_repair_dataset(
    *,
    base_dpo_path: Path = PACK_DIR / "dataset_v2" / "vericut96_v2_dpo_mix.jsonl",
    out_path: Path = PACK_DIR / "dataset_v2" / "vericut96_v3_dpo_repair.jsonl",
    repair_repeat: int = 3,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Combine sealed v2 DPO mix + v3 targeted repair pairs with leak, unit, and pair validation gates."""
    if not base_dpo_path.exists():
        raise SystemExit(f"[FATAL] 缺少 v2 DPO 基础语料: {base_dpo_path}")
    _verify_optional_ledger(base_dpo_path)
    base_rows = [json.loads(json.dumps(r, ensure_ascii=False)) for r in _load_jsonl(base_dpo_path)]
    repair_rows = build_vericut96_v3_dpo_repair_rows(seed=seed, repeat=repair_repeat)

    combined = base_rows + repair_rows
    random.Random(seed + 404).shuffle(combined)

    holdouts = [
        p
        for p in (DEFAULT_VERICUT_HOLDOUT, DEFAULT_KB_HOLDOUT, *DEFAULT_EXTRA_HOLDOUTS)
        if p.exists()
    ]
    _verify_no_holdout_leak(combined, holdouts, out_path.stem)

    info = _write_jsonl_with_proof(
        out_path,
        combined,
        {
            "corpus": out_path.stem,
            "seed": seed,
            "base_dpo_path": str(base_dpo_path),
            "base_dpo_sha256": sha256_file(base_dpo_path),
            "base_dpo_rows": len(base_rows),
            "repair_rows": len(repair_rows),
            "repair_repeat": repair_repeat,
            "families": [
                "autodiff_triage_repair",
                "coordinate_unit_isolation_repair",
                "lame_closed_form_repair",
                "sw_plane_notation_repair",
            ],
        },
    )
    _run_release_gates(out_path, is_dpo=True)
    return info


def _write_jsonl_with_proof(
    path: Path,
    rows: Sequence[Dict[str, Any]],
    ledger_meta: Dict[str, Any],
) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    digest = sha256_file(path)
    sidecar = Path(str(path) + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8", newline="\n")

    ledger_path = path.parent / f"{path.stem}_ledger.json"
    ledger = {
        **ledger_meta,
        "output_path": str(path),
        "output_name": path.name,
        "output_sha256": digest,
        "size_bytes": path.stat().st_size,
        "rows": len(rows),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"path": str(path), "sha256": digest, "ledger_path": str(ledger_path), "rows": len(rows)}


def _run_release_gates(target_file: Path, *, is_dpo: bool = False) -> None:
    known_tools = load_known_tool_names()
    rows = _load_jsonl(target_file)
    for idx, row in enumerate(rows):
        if not _system_prompt_ok(row):
            raise SystemExit(f"[FATAL] {target_file.name}:{idx} system prompt 超过 {SYSTEM_PROMPT_MAX_BYTES}B")
        for t in row.get("tools") or []:
            nm = str((t.get("function") or {}).get("name") or "").strip()
            if nm and nm not in known_tools:
                raise SystemExit(f"[FATAL] {target_file.name}:{idx} 包含未知工具定义 {nm!r}")
        for m in row.get("messages") or []:
            for tc in m.get("tool_calls") or []:
                nm = str((tc.get("function") or tc).get("name") or "").strip()
                if nm and nm not in known_tools:
                    raise SystemExit(f"[FATAL] {target_file.name}:{idx} 包含未知 tool_call {nm!r}")

    for bdir in BENCHMARK_DIRS:
        if bdir.is_dir():
            assert_no_leak(str(target_file), str(bdir))
    assert_units_clean(str(target_file))
    if is_dpo:
        pairs = validate_dpo_pairs(target_file)
        if len(pairs) != len(rows):
            raise SystemExit(f"[FATAL] DPO 行数校验不一致: {len(pairs)} != {len(rows)}")


def build_vericut96_cloud_datasets(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    vericut_sft_path: Path = DEFAULT_VERICUT_SFT,
    vericut_dpo_path: Path = DEFAULT_VERICUT_DPO,
    vericut_holdout_path: Path = DEFAULT_VERICUT_HOLDOUT,
    kb_holdout_path: Path = DEFAULT_KB_HOLDOUT,
    engine_replay_path: Path = DEFAULT_ENGINE_REPLAY,
    text_replay_path: Path = DEFAULT_TEXT_REPLAY,
    concise_dpo_path: Path = DEFAULT_CONCISE_DPO,
    safety_dpo_path: Path = DEFAULT_SAFETY_DPO,
    vericut_weight: int = 2,
    engine_replay_limit: int = 900,
    text_replay_limit: int = 300,
    anchor_limit: int = 36,
    dpo_anchor_limit: int = 0,
    prefix: str = "vericut96",
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    if not vericut_sft_path.exists():
        raise SystemExit(f"[FATAL] 缺少 VERICUT SFT 语料: {vericut_sft_path}")
    if not vericut_dpo_path.exists():
        raise SystemExit(f"[FATAL] 缺少 VERICUT DPO 语料: {vericut_dpo_path}")

    _verify_optional_ledger(vericut_sft_path)
    _verify_optional_ledger(vericut_dpo_path)

    tool_map = _build_sanitized_tool_map()
    vericut_sft_raw = _load_jsonl(vericut_sft_path)
    vericut_dpo_raw = _load_jsonl(vericut_dpo_path)

    sources_meta: Dict[str, Any] = {
        "vericut_sft": {"path": str(vericut_sft_path), "sha256": sha256_file(vericut_sft_path), "rows": len(vericut_sft_raw), "weight": vericut_weight},
        "vericut_dpo": {"path": str(vericut_dpo_path), "sha256": sha256_file(vericut_dpo_path), "rows": len(vericut_dpo_raw)},
    }

    sft_rows: List[Dict[str, Any]] = []
    for _ in range(max(1, vericut_weight)):
        sft_rows.extend(json.loads(json.dumps(r, ensure_ascii=False)) for r in vericut_sft_raw)

    engine_kept = 0
    if engine_replay_limit > 0 and engine_replay_path.exists():
        raw_engine = _load_jsonl(engine_replay_path)
        norm_engine = [x for r in raw_engine if (x := normalize_sft_replay_row(r, tool_map)) is not None]
        sampled_engine = stratified_sample(
            norm_engine,
            engine_replay_limit,
            seed + 1,
            lambda r: f"{(r.get('meta') or {}).get('software', 'other')}:{(r.get('meta') or {}).get('family', 'general')}",
        )
        sft_rows.extend(sampled_engine)
        engine_kept = len(sampled_engine)
        sources_meta["engine_replay"] = {"path": str(engine_replay_path), "sha256": sha256_file(engine_replay_path), "rows": engine_kept}

    text_kept = 0
    if text_replay_limit > 0 and text_replay_path.exists():
        raw_text = _load_jsonl(text_replay_path)
        norm_text = [r for r in raw_text if _system_prompt_ok(r) and isinstance(r.get("messages"), list)]
        sampled_text = stratified_sample(
            norm_text,
            text_replay_limit,
            seed + 2,
            lambda r: str((r.get("meta") or {}).get("category") or r.get("_source") or "general"),
        )
        sft_rows.extend(sampled_text)
        text_kept = len(sampled_text)
        sources_meta["text_replay"] = {"path": str(text_replay_path), "sha256": sha256_file(text_replay_path), "rows": text_kept}

    anchor_rows = build_canonical_anti_regression_rows(seed=seed, limit=anchor_limit)
    if anchor_rows:
        sft_rows.extend(anchor_rows)
        sources_meta["canonical_anchors"] = {
            "rows": len(anchor_rows),
            "families": ["coordinate_isolation", "autodiff_triage", "lame_closed_form", "fanuc_g71_safety"],
        }

    rng = random.Random(seed)
    rng.shuffle(sft_rows)

    dpo_rows: List[Dict[str, Any]] = [json.loads(json.dumps(r, ensure_ascii=False)) for r in vericut_dpo_raw]
    for tag, dpath in (("concise_dpo", concise_dpo_path), ("safety_dpo", safety_dpo_path)):
        if dpath.exists():
            extra = [r for r in _load_jsonl(dpath) if _system_prompt_ok(r)]
            dpo_rows.extend(extra)
            sources_meta[tag] = {"path": str(dpath), "sha256": sha256_file(dpath), "rows": len(extra)}

    dpo_anchor_rows = build_canonical_anti_regression_dpo_rows(seed=seed, limit=dpo_anchor_limit)
    if dpo_anchor_rows:
        dpo_rows.extend(dpo_anchor_rows)
        sources_meta["canonical_dpo_anchors"] = {
            "rows": len(dpo_anchor_rows),
            "families": ["autodiff_triage", "coordinate_isolation", "unit_preservation", "lame_closed_form", "fanuc_g71_safety"],
        }
        random.Random(seed + 11).shuffle(dpo_rows)

    sft_stem = f"{prefix}_sft_mix"
    dpo_stem = f"{prefix}_dpo_mix"
    holdouts = [p for p in (vericut_holdout_path, kb_holdout_path) if p.exists()]
    _verify_no_holdout_leak(sft_rows, holdouts, sft_stem)
    _verify_no_holdout_leak(dpo_rows, holdouts, dpo_stem)

    sft_out = out_dir / f"{sft_stem}.jsonl"
    dpo_out = out_dir / f"{dpo_stem}.jsonl"
    sft_info = _write_jsonl_with_proof(
        sft_out,
        sft_rows,
        {
            "corpus": sft_stem,
            "seed": seed,
            "vericut_rows_weighted": len(vericut_sft_raw) * max(1, vericut_weight),
            "engine_replay_rows": engine_kept,
            "text_replay_rows": text_kept,
            "anchor_rows": len(anchor_rows),
            "sources": sources_meta,
        },
    )
    dpo_info = _write_jsonl_with_proof(
        dpo_out,
        dpo_rows,
        {
            "corpus": dpo_stem,
            "seed": seed,
            "vericut_dpo_rows": len(vericut_dpo_raw),
            "dpo_anchor_rows": len(dpo_anchor_rows),
            "sources": sources_meta,
        },
    )

    _run_release_gates(sft_out, is_dpo=False)
    _run_release_gates(dpo_out, is_dpo=True)

    return {"sft": sft_info, "dpo": dpo_info, "sources": sources_meta}


def run_selftest() -> int:
    with tempfile.TemporaryDirectory(prefix="vericut96_mix_selftest_") as td:
        tp = Path(td)
        v_sft = tp / "v_sft.jsonl"
        v_dpo = tp / "v_dpo.jsonl"
        v_hold = tp / "v_hold.jsonl"
        eng = tp / "eng.jsonl"
        txt = tp / "txt.jsonl"

        sft_row = {
            "software": "vericut",
            "split": "train",
            "source_run_id": "selftest:proj:1",
            "evidence_sha256": hashlib.sha256(b"s1").hexdigest(),
            "messages": [
                {"role": "system", "content": "你是 Virtu VERICUT 9.6 智能体。"},
                {"role": "user", "content": "检查测试工程 session1.vcproject 单位与过切。"},
                {"role": "assistant", "content": '<tool_call>\n{"name": "cadcam_vericut_simulate", "arguments": {"action": "run_simulation", "project_path": "E:/training/s1.vcproject"}}\n</tool_call>'},
                {"role": "tool", "content": '{"status": "ok", "units": "millimeter"}'},
                {"role": "assistant", "content": "单位为 millimeter，仿真正常。"},
            ],
        }
        v_sft.write_text(json.dumps(sft_row, ensure_ascii=False) + "\n", encoding="utf-8")

        dpo_row = {
            "prompt": [{"role": "system", "content": "你是 Virtu VERICUT 9.6 智能体。"}, {"role": "user", "content": "运行 s1.vcproject"}],
            "chosen": '<tool_call>\n{"name": "cadcam_vericut_simulate", "arguments": {"action": "run_simulation", "project_path": "E:/training/s1.vcproject"}}\n</tool_call>',
            "rejected": "调用 COM 接口 Vericut.Application 运行。",
        }
        v_dpo.write_text(json.dumps(dpo_row, ensure_ascii=False) + "\n", encoding="utf-8")

        v_hold.write_text(
            json.dumps({"messages": [{"role": "user", "content": "留出课程 session255 探头问题"}, {"role": "assistant", "content": "ok"}]}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        eng_row = {
            "messages": [
                {"role": "system", "content": "你是 Virtu 智能体。"},
                {"role": "user", "content": "回放验证 FANUC 宏程序 O9100"},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "cadcam_cimco_validate", "arguments": "{\"action\":\"validate_macro\",\"code\":\"O9100\\nM30\"}"}}]},
                {"role": "tool", "content": '{"status": "ok"}'},
                {"role": "assistant", "content": "语法通过。"},
            ],
            "meta": {"software": "cimco", "family": "tool_route"},
        }
        eng.write_text(json.dumps(eng_row, ensure_ascii=False) + "\n", encoding="utf-8")
        txt.write_text(
            json.dumps({"messages": [{"role": "system", "content": "你是 Virtu 专家。"}, {"role": "user", "content": "G81 与 G83 区别？"}, {"role": "assistant", "content": "G81 直钻，G83 深孔啄钻。"}], "meta": {"category": "cnc"}}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        res = build_vericut96_cloud_datasets(
            out_dir=tp / "out",
            vericut_sft_path=v_sft,
            vericut_dpo_path=v_dpo,
            vericut_holdout_path=v_hold,
            kb_holdout_path=tp / "missing.jsonl",
            engine_replay_path=eng,
            text_replay_path=txt,
            concise_dpo_path=tp / "no_concise.jsonl",
            safety_dpo_path=tp / "no_safety.jsonl",
            vericut_weight=2,
            engine_replay_limit=1,
            text_replay_limit=1,
            anchor_limit=6,
        )
        assert res["sft"]["rows"] == 10
        assert res["dpo"]["rows"] == 1
        built_rows = _load_jsonl(Path(res["sft"]["path"]))
        assert any(r.get("tools") for r in built_rows if any("tool_calls" in m for m in r["messages"])), "replay tool_calls 未挂接 tools"
        assert any((r.get("meta") or {}).get("family") == "coordinate_isolation" for r in built_rows), "缺少坐标系隔离锚点样本"
        assert Path(res["sft"]["ledger_path"]).exists()
        assert Path(res["dpo"]["ledger_path"]).exists()

    print("[SELFTEST] PASS: build_vericut96_cloud_datasets (mix / anchors / tools_norm / ledger / leak+unit)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="构建 VERICUT 9.6 云端防遗忘 SFT+DPO 混合数据集")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--vericut-weight", type=int, default=2, help="VERICUT SFT 重复权重 (1~3)")
    p.add_argument("--engine-replay-limit", type=int, default=900, help="六软件工具调用回放样本数")
    p.add_argument("--text-replay-limit", type=int, default=300, help="CNC/物理公式回放样本数")
    p.add_argument("--anchor-limit", type=int, default=36, help="坐标系隔离/Auto-Diff/Lamé/G71防遗忘SFT锚点样本数")
    p.add_argument("--dpo-anchor-limit", type=int, default=0, help="Auto-Diff/坐标系/单位/Lamé/G71防遗忘DPO偏好对数量")
    p.add_argument("--prefix", default="vericut96", help="输出文件名前缀 (默认 vericut96，v2 可传 vericut96_v2)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--build-v3-repair", action="store_true", help="构建基于 v2 DPO 的 v3 定向纠偏对齐集 (不改写已封缄 v2 资产)")
    p.add_argument("--repair-repeat", type=int, default=3, help="v3 定向纠偏对重复权重 (1~3)")
    p.add_argument("--selftest", "--self-test", dest="selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        return run_selftest()
    if args.build_v3_repair:
        if not 1 <= args.repair_repeat <= 3:
            raise SystemExit("[FATAL] --repair-repeat 必须位于 [1, 3]")
        res = build_vericut96_v3_dpo_repair_dataset(
            out_path=Path(args.out_dir) / "vericut96_v3_dpo_repair.jsonl",
            repair_repeat=args.repair_repeat,
            seed=args.seed,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if not 1 <= args.vericut_weight <= 3:
        raise SystemExit("[FATAL] --vericut-weight 必须位于 [1, 3]，严禁超出 gate_all90_dataset max_derive_ratio=3 上限")

    res = build_vericut96_cloud_datasets(
        out_dir=Path(args.out_dir),
        vericut_weight=args.vericut_weight,
        engine_replay_limit=args.engine_replay_limit,
        text_replay_limit=args.text_replay_limit,
        anchor_limit=args.anchor_limit,
        dpo_anchor_limit=args.dpo_anchor_limit,
        prefix=args.prefix,
        seed=args.seed,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
