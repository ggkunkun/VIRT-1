#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/eval_in_situ.py — 云端就地全维度高分测评与验收门禁引擎

功能：
1. 训练完成后在云端 GPU 上【原地】执行评测（无需本地搭建复杂服务、零网络传输延迟）；
2. 完整覆盖 virtu_eval 八大核心维度（240 条确定性测试用例，零 LLM-as-judge 噪声）：
   - toolcall (0.18): 单轮 JSON 工具调用（题面自带 schema 约束；本脚本不注入 tools 字段，
     运行时注册表有 14 个 cadcam_* 工具，评测面以用例 criteria 为准）
   - reasoning (0.17): 主轴转速、进给速度、切除率、尺寸链公差、刀补坐标 CoT 推导
   - knowledge (0.15): ISO 286 轴孔公差配合、GD&T 几何公差符号、金属材料物理特性
   - instruction (0.14): 严格行数限制、键值对格式、升降序排序
   - boundary (0.12): 缺项拒绝、几何冲突防御、安全与防越权
   - generation (0.10): 标准数控 G 代码、CAD VBA 宏与 NXOpen 脚本
   - generalization (0.08): 跨软件工程名词与多格式转换
   - multimodal (0.06): 视觉图纸与工况特征感知（本脚本的 HFLocalArm 是纯文本通道，
     该维在文本臂上必然低分，不得当作视觉能力结论）
3. physics_gate 物理否决门禁：**实测** 每条 physics 用例是否同时通过求解器复算与守恒式，
   测不到即失败关闭（历史上这里写死过 1.0，见 tests/test_eval_in_situ_gate.py）；
4. 输出多模型对比卡片与 COMPREHENSIVE_EVAL_REPORT.json，并把逐题响应写入 raw.jsonl 作为证据；
   对比卡片里的历史列是源码常量（BASELINE_PROVENANCE 标注），不是实测。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import bitsandbytes.backends.cuda.ops as bnb_ops
    bnb_ops._gemm_4bit_use_custom_fn = lambda *args, **kwargs: True
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIM_WEIGHTS = {
    "toolcall": 0.18,
    "reasoning": 0.17,
    "knowledge": 0.15,
    "instruction": 0.14,
    "boundary": 0.12,
    "generation": 0.10,
    "generalization": 0.08,
    "multimodal": 0.06,
}

DIM_NAMES_ZH = {
    "toolcall": "工具编排",
    "reasoning": "推理逻辑",
    "knowledge": "知识覆盖",
    "instruction": "指令遵循",
    "boundary": "边界处理",
    "generation": "内容生成",
    "generalization": "泛化适配",
    "multimodal": "多模态理解",
}

HISTORICAL_BASELINES = {
    "Qwen3-8B-Base": {
        "toolcall": 42.50, "reasoning": 58.12, "knowledge": 64.20, "instruction": 68.30,
        "boundary": 36.40, "generation": 65.10, "generalization": 52.80, "multimodal": 45.00,
        "overall": 53.90
    },
    "virtu-v2": {
        "toolcall": 73.33, "reasoning": 83.34, "knowledge": 61.61, "instruction": 81.95,
        "boundary": 62.45, "generation": 77.66, "generalization": 63.13, "multimodal": 91.67,
        "overall": 68.39
    },
    "virtu-v3-all90": {
        "toolcall": 70.00, "reasoning": 80.93, "knowledge": 81.61, "instruction": 86.29,
        "boundary": 74.78, "generation": 90.71, "generalization": 81.25, "multimodal": 91.67,
        "overall": 75.22
    }
}

# These numbers were typed into this source file. No raw.jsonl in this repo reproduces
# them, so they must never be printed as if they were measured arms.
BASELINE_PROVENANCE = (
    "源码内手写的常量，仓内无对应 raw.jsonl 证据，不能当作历史实测成绩引用；"
    "需要对比请指向带 manifest 指纹的 run 目录。")


def case_fingerprints(case_dir: str) -> Dict[str, str]:
    from virtu_eval.runner import sha256_file
    base = Path(case_dir)
    if not base.exists():
        return {}
    return {f.name: sha256_file(str(f)) for f in sorted(base.glob("*.jsonl"))}


def git_sha() -> str:
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def measure_physics_gate(arm, selftest: bool, case_dir: Path = None,
                         limit: int = 0) -> Dict[str, Any]:
    """Physics veto gate - measured against the solver, never assumed.

    The previous implementation hard-coded 1.0 ("靶向语料已包含 100% 物理守恒样本"),
    which conflated what the training corpus contains with what the model outputs. The
    gate therefore reports a fraction of solver-confirmed answers, or refuses to report.
    """
    from virtu_eval.graders import score_case
    from virtu_eval.runner import load_cases

    case_dir = case_dir or (ROOT / "data" / "benchmark" / "virtu_eval_phys_v1")
    if arm is None or selftest:
        return {"measured": False, "compliance": None, "n": 0,
                "reason": "NO_ARM_GOLD_PLAYBACK_MEASURES_NOTHING" if selftest else "NO_ARM"}
    if not (case_dir / "physics.jsonl").exists():
        return {"measured": False, "compliance": None, "n": 0,
                "reason": f"missing {case_dir}/physics.jsonl"}

    cases = load_cases(str(case_dir), dims=["physics"])
    if limit > 0:
        cases = cases[:limit]
    confirmed = 0
    failures = []
    for case in cases:
        max_tok = max(int(case.get("max_tokens", 512)), 1024)
        gen = arm.generate([{"role": "user", "content": case["prompt"]}],
                           max_tokens=max_tok, temperature=0.0)
        text = gen.get("text") or ""
        from virtu_eval.arms import _strip_think
        clean_text = _strip_think(text)
        if not clean_text and text:
            clean_text = text
        scored = score_case(clean_text, case["criteria"])
        by_type = {c.get("type"): bool(c.get("passed")) for c in scored["criteria"]}
        solver_ok = by_type.get("world_state_verified", False)
        invariant_ok = by_type.get("physics_invariant", False)
        if solver_ok and invariant_ok:
            confirmed += 1
        else:
            failures.append({"case_id": case["id"],
                             "solver": solver_ok, "invariant": invariant_ok})
    n = len(cases)
    return {"measured": n > 0, "compliance": (round(confirmed / n, 4) if n else None),
            "n": n, "confirmed": confirmed, "failures": failures[:40],
            "reason": None if n else "NO_PHYSICS_CASES"}



def run_evaluation(
    model_path: str,
    adapter_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    device: str = "cuda",
    limit: int = 0,
    limit_per_dim: int = 0,
    selftest: bool = False,
    think: Optional[bool] = None
) -> Dict[str, Any]:
    case_dir = ROOT / "data" / "benchmark" / "virtu_eval_v1"
    if not case_dir.exists():
        raise FileNotFoundError(f"未找到评测集目录: {case_dir}")

    if out_dir is None:
        out_dir = str(ROOT / "cloud_train_pack" / "eval_results")
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 75)
    print("  Virtu 云端就地全维度高分测评系统 (Virtu In-Situ Comprehensive Evaluation)")
    print(f"  model={model_path}  adapter={adapter_path or 'None'}  device={device}"
          f"  mode={'GOLD_PLAYBACK' if selftest else 'LIVE'}")
    print("=" * 75)

    from virtu_eval.runner import load_cases
    from virtu_eval.graders import score_case

    if limit_per_dim > 0:
        cases = load_cases(str(case_dir), limit_per_dim=limit_per_dim)
    else:
        cases = load_cases(str(case_dir))
        if limit > 0:
            cases = cases[:limit]
    print(f"[1/4] 载入评测用例: 共 {len(cases)} 条 (覆盖 {len(DIM_WEIGHTS)} 个能力维度)")

    # 准备模型臂
    arm = None
    if not selftest:
        from virtu_eval.arms import HFLocalArm
        print(f"[2/4] 初始化 HFLocalArm (4bit/bfloat16)...")
        arm = HFLocalArm(
            model_path=model_path,
            adapter_path=adapter_path,
            quant="nf4",
            device=device,
            merge_adapter=False,
            think=think,
            strip_think=True
        )
        arm.load()
        print("  [OK] 模型已载入显存！")
    else:
        print("[2/4] 自检模式：使用模拟评估器...")

    # 执行测试
    print("[3/4] 逐题推理与确定性机器判分...")
    results_by_dim = {d: [] for d in DIM_WEIGHTS}
    raw_records = []
    t_start = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        cid = case["id"]
        dim = case["dimension"]
        prompt = case["prompt"]
        max_tok = case.get("max_tokens", 512)

        if not selftest and arm is not None:
            effective_tok = max(int(max_tok), 1024)
            msgs = [{"role": "user", "content": prompt}]
            gen = arm.generate(msgs, max_tokens=effective_tok, temperature=0.0)
            text = gen.get("text") or ""
            from virtu_eval.arms import _strip_think
            clean_text = _strip_think(text)
            if not clean_text and text:
                clean_text = text
            gen_meta = {k: gen.get(k) for k in
                        ("prompt_tokens", "completion_tokens", "finish_reason", "elapsed_s", "arm", "reasoning")}
        else:
            # 金牌回放：只验证判分器与用例自洽，不得当作模型实测分数。
            text = (case.get("gold") or {}).get("answer") or ""
            clean_text = text
            gen_meta = {"arm": "gold_playback"}

        # 确定性判分
        scored = score_case(clean_text, case["criteria"])
        score = scored["score"]
        results_by_dim[dim].append({
            "id": cid,
            "tier": case.get("tier", "medium"),
            "score": score,
            "passed": scored["all_passed"],
            "criteria": scored["criteria"]
        })
        raw_records.append({
            "case_id": cid,
            "dimension": dim,
            "tier": case.get("tier"),
            "score": score,
            "passed": scored["all_passed"],
            "criteria": scored["criteria"],
            "response": text,
            "gen": gen_meta,
        })
        if idx % 20 == 0 or idx == len(cases):
            print(f"  进度 [{idx:3d}/{len(cases):3d}] 题 | 当前用例 {cid:18s} 得分: {score:5.1f}")

    physics_gate = measure_physics_gate(arm, selftest=selftest)
    if arm is not None:
        arm.unload()

    total_time = round(time.perf_counter() - t_start, 2)
    print(f"  [OK] 评测推理完成，总耗时 {total_time} 秒！")

    # [4/4] 统计各维度分与加权综合分
    print("[4/4] 汇总结算全维度得分与验收门控...")
    dim_summary = {}
    weighted_total = 0.0

    for dim, items in results_by_dim.items():
        if not items:
            continue
        scores = [it["score"] for it in items]
        mean_score = sum(scores) / len(scores)
        pass_rate = sum(1 for it in items if it["passed"]) / len(items)
        w = DIM_WEIGHTS.get(dim, 0.0)
        weighted_total += mean_score * w

        # 分难度统计
        tier_stats = {}
        for tier in ("easy", "medium", "hard"):
            t_items = [it for it in items if it["tier"] == tier]
            if t_items:
                tier_stats[tier] = {
                    "count": len(t_items),
                    "mean": round(sum(it["score"] for it in t_items) / len(t_items), 2)
                }

        dim_summary[dim] = {
            "name_zh": DIM_NAMES_ZH.get(dim, dim),
            "count": len(items),
            "score": round(mean_score, 2),
            "pass_rate": round(pass_rate, 4),
            "weight": w,
            "tiers": tier_stats
        }

    # Renormalise over the weights actually covered: a partial sweep must not be
    # published as a lower total of the same ruler (it is a different ruler).
    covered_weight = sum(DIM_WEIGHTS.get(d, 0.0) for d in dim_summary) or 1.0
    coverage = {"dims_covered": sorted(dim_summary), "weight_covered": round(covered_weight, 4),
                "dims_expected": sorted(DIM_WEIGHTS)}
    weighted_total = round(weighted_total / covered_weight, 2)

    # 物理门禁：实测值，未测即失败关闭（绝不回落到 1.0）
    physics_compliance = physics_gate.get("compliance")

    # 验收门控判定：全部维度 >= 90 且综合 >= 90
    all_high_scores = True
    failed_dims = []
    for dim, sinfo in dim_summary.items():
        if sinfo["score"] < 90.0:
            all_high_scores = False
            failed_dims.append(f"{dim} ({sinfo['score']:.1f} < 90.0)")

    if len(dim_summary) < len(DIM_WEIGHTS):
        all_high_scores = False
        missing = sorted(set(DIM_WEIGHTS) - set(dim_summary))
        failed_dims.append(f"coverage ({len(dim_summary)}/{len(DIM_WEIGHTS)} 维, 缺 {missing})")

    if not physics_gate.get("measured") or physics_compliance is None:
        all_high_scores = False
        failed_dims.append(f"physics_gate (NOT MEASURED: {physics_gate.get('reason')})")
    elif physics_compliance < 1.0:
        all_high_scores = False
        failed_dims.append(
            f"physics_gate ({physics_compliance:.1%} < 100%, {physics_gate['confirmed']}/{physics_gate['n']})")

    if weighted_total < 90.0:
        all_high_scores = False

    # 打印最终对比雷达卡片
    print("\n" + "=" * 85)
    banner = ("  [GOLD PLAYBACK / SELFTEST] 以下分数是标准答案过判分器，不是模型实测"
              if selftest else
              "  Virtu 工业智能体 · 全面测评得分看板 (All-Dimension Capability Card)")
    print(banner)
    print("=" * 85)
    header = (f" {'维度 (Dimension)':<16} | {'权重':<4} | {'常量基座*':<9} | {'常量v2*':<8} "
              f"| {'常量v3*':<8} | {'本次实测':<8} | {'验收状态'}")
    print(header)
    print("-" * 85)

    for dim in ["toolcall", "reasoning", "knowledge", "instruction", "boundary", "generation", "generalization", "multimodal"]:
        if dim not in dim_summary:
            continue
        info = dim_summary[dim]
        b_base = HISTORICAL_BASELINES["Qwen3-8B-Base"].get(dim, 0.0)
        b_v2 = HISTORICAL_BASELINES["virtu-v2"].get(dim, 0.0)
        b_v3 = HISTORICAL_BASELINES["virtu-v3-all90"].get(dim, 0.0)
        curr = info["score"]
        status = "✅ PASS(高分)" if curr >= 90.0 else "⚠️ 未达标"
        print(f" {DIM_NAMES_ZH[dim] + '(' + dim + ')':<18} | {info['weight']:<4.2f} | {b_base:<9.1f} | {b_v2:<8.1f} | {b_v3:<8.1f} | {curr:<8.1f} | {status}")

    print("-" * 85)
    total_base = HISTORICAL_BASELINES["Qwen3-8B-Base"]["overall"]
    total_v2 = HISTORICAL_BASELINES["virtu-v2"]["overall"]
    total_v3 = HISTORICAL_BASELINES["virtu-v3-all90"]["overall"]
    overall_status = "🏆 全部高分通过 (PASS)" if all_high_scores else "⚠️ 未通过: " + "; ".join(failed_dims[:3])
    print(f" {'综合加权总分':<18} | 1.00 | {total_base:<9.1f} | {total_v2:<8.1f} | {total_v3:<8.1f} | {weighted_total:<8.1f} | {overall_status}")
    # The historical physics-compliance figures previously printed here (0.62/0.85/0.94)
    # were typed into this file with no measurement behind them, so they are gone.
    gate_text = (f"{physics_compliance:.1%} ({physics_gate['confirmed']}/{physics_gate['n']})"
                 if physics_gate.get("measured") else f"NOT MEASURED ({physics_gate.get('reason')})")
    print(f" {'物理合规率 (否决项)':<18} | —    | {'—':<9} | {'—':<8} | {'—':<8} | {gate_text:<24} | "
          f"{'✅ 100%合规' if physics_gate.get('measured') and (physics_compliance or 0) >= 1.0 else '❌ 否决/未测'}")
    print("  * 常量列=本文件手写常量，无 raw 证据，禁止当历史实测引用")
    print("=" * 85)

    # 产物落盘
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "selftest_gold_playback" if selftest else "live_model",
        "model": model_path if not selftest else f"{model_path} [NOT SCORED: gold playback]",
        "adapter": adapter_path,
        "identity_evidence": {
            "loaded_from": None if selftest else model_path,
            "served_model": None,
            "note": "HFLocalArm 直接载权重，无服务侧 served_model 回报；归因只能靠下面两份指纹",
            "git_sha": git_sha(),
            "case_file_sha256": case_fingerprints(str(case_dir)),
            "phys_case_file_sha256": case_fingerprints(str(ROOT / "data" / "benchmark" / "virtu_eval_phys_v1")),
            "sampling": {"temperature": 0.0, "limit": limit, "device": device},
        },
        "coverage": coverage,
        "weighted_total_score": weighted_total,
        "physics_gate": physics_gate,
        "physics_compliance_rate": physics_compliance,
        "all_dimensions_pass_90": all_high_scores,
        "failed_dimensions": failed_dims,
        "dimensions": dim_summary,
        "historical_comparison": HISTORICAL_BASELINES,
        "historical_comparison_provenance": BASELINE_PROVENANCE,
        "evidence_files": ["raw.jsonl", "COMPREHENSIVE_EVAL_REPORT.json"],
    }
    raw_path = os.path.join(out_dir, "raw.jsonl")
    with open(raw_path, "w", encoding="utf-8") as f:
        for rec in raw_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    report_json_path = os.path.join(out_dir, "COMPREHENSIVE_EVAL_REPORT.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"[交付] 逐题响应证据已保存至: {raw_path} ({len(raw_records)} 条)")
    print(f"[交付] 详细评测指标报告已保存至: {report_json_path}")

    # 生成 Markdown 报告
    md_path = os.path.join(out_dir, "COMPREHENSIVE_EVAL_REPORT.md")
    with open(md_path, "w", encoding="utf-8") as f:
        title = ("Virtu 用例金牌回放（非模型实测）" if selftest
                 else "Virtu 全维度能力全面测评验收报告")
        f.write(f"# {title}\n\n")
        if selftest:
            f.write("> **口径声明**：`--selftest` 只把每条用例的 `gold.answer` 送进判分器，"
                    "用来验证题面与判分器自洽。**不得把本报告中的 100 分写成模型能力。**\n\n")
        f.write(f"- **测试日期**：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **被测模型**：`{model_path}` + Adapter `{adapter_path or 'None'}`"
                f"{'（金牌回放，未加载权重）' if selftest else ''}\n")
        f.write(f"- **归因指纹**：git `{report_data['identity_evidence']['git_sha']}`，"
                f"用例 sha256 前缀 `{sorted(report_data['identity_evidence']['case_file_sha256'].values())[0][:12] if report_data['identity_evidence']['case_file_sha256'] else 'none'}`，"
                f"逐题响应见 `raw.jsonl`（{len(raw_records)} 条）\n")
        f.write(f"- **维度覆盖**：{len(dim_summary)}/{len(DIM_WEIGHTS)} 维"
                f"（权重覆盖 {coverage['weight_covered']:.2f}）；缺 {sorted(set(DIM_WEIGHTS) - set(dim_summary)) or '无'}\n")
        f.write(f"- **综合加权得分**：`{weighted_total:.2f} / 100`（按已覆盖权重归一）\n")
        if physics_gate.get("measured"):
            f.write(f"- **物理规律合规率**：`{physics_compliance * 100:.1f}%`"
                    f"（实测 {physics_gate['confirmed']}/{physics_gate['n']}，判据＝求解器复算+守恒式同时通过）(否决项)\n")
        else:
            f.write(f"- **物理规律合规率**：`NOT MEASURED`（原因：{physics_gate.get('reason')}）"
                    f"——按失败关闭处理，本报告不得声称物理合规 (否决项)\n")
        f.write(f"- **高分验收结论**：{'**【全部高分 PASS】** 所有维度均突破 90 分大关！' if all_high_scores else '**【未通过】** ' + '；'.join(failed_dims[:6])}\n\n")
        f.write("> **口径警告**：表中「常量基座/常量v2/常量v3」三列是本文件手写的常量，"
                "仓内没有可复现它们的 raw 记录，**不得引用为历史实测成绩**；"
                "本报告的对比一律以带 manifest 指纹的 run 目录为准。\n\n")
        f.write("## 维度对比矩阵\n\n")
        f.write("| 维度 | 权重 | 常量基座* | 常量v2* | 常量v3* | 本次实测得分 | 难度分布(Easy/Med/Hard) | 状态 |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for dim, info in dim_summary.items():
            b_base = HISTORICAL_BASELINES["Qwen3-8B-Base"].get(dim, 0.0)
            b_v2 = HISTORICAL_BASELINES["virtu-v2"].get(dim, 0.0)
            b_v3 = HISTORICAL_BASELINES["virtu-v3-all90"].get(dim, 0.0)
            t_str = " / ".join(f"{info['tiers'].get(t, {}).get('mean', 0):.1f}" for t in ("easy", "medium", "hard"))
            f.write(f"| **{info['name_zh']}** ({dim}) | {info['weight']:.2f} | {b_base:.1f} | {b_v2:.1f} | {b_v3:.1f} | **{info['score']:.1f}** | {t_str} | {'✅ 达标' if info['score']>=90 else '⚠️ 未达标'} |\n")
        f.write(f"| **综合总分** | **1.00** | **{total_base:.1f}** | **{total_v2:.1f}** | **{total_v3:.1f}** | **{weighted_total:.1f}** | — | **{overall_status}** |\n\n")

    print(f"[交付] 可视化 Markdown 报告已生成: {md_path}")
    return report_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="checkpoints/_base_qwen3_8b", help="Base model path")
    parser.add_argument("--adapter", default=None, help="LoRA adapter path")
    parser.add_argument("--out-dir", default=None, help="Output directory for reports")
    parser.add_argument("--device", default="cuda", help="cuda or cpu")
    parser.add_argument("--limit", type=int, default=0, help="Limit total test cases (0=all)")
    parser.add_argument("--limit-per-dim", type=int, default=0, help="Limit test cases per dimension (0=all)")
    parser.add_argument("--think", action="store_true", default=None, help="Enable think mode")
    parser.add_argument("--no-think", dest="think", action="store_false", help="Disable think mode")
    parser.add_argument("--selftest", action="store_true", help="Run in mock selftest mode without GPU")
    args = parser.parse_args()

    run_evaluation(
        model_path=args.model,
        adapter_path=args.adapter,
        out_dir=args.out_dir,
        device=args.device,
        limit=args.limit,
        limit_per_dim=args.limit_per_dim,
        selftest=args.selftest,
        think=args.think
    )
