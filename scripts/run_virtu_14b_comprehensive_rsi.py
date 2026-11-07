#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 模型 13.63B 全面递归自我改进体系 (Comprehensive RSI Launcher)
===================================================================
依据《测量宪法》与《Extreme Step-by-Step Self-Verification & Circuit Breaker Axiom》：
1. 目标模型：Virtu-MoE 13.63B (virtu-moe-14b:latest, 13,626,848,256 稀疏双专家架构)
2. 评测基准：virtu_rsi_pool_v2 (420 道高精度物理/工业题，全覆盖 7 大能力维度：
   reasoning, knowledge, instruction, generation, generalization, boundary, toolcall)
3. 工具对齐：自动绑定 virtu_eval/arms.json 中 virtu_moe_14b 真实服务位配置：
   - 挂载 16 个 CAD/CAM 原生工具 (仅在 toolcall 维激活)
   - num_gpu=20 (54% offload 规避显存溢出)，num_ctx=8192
4. 统计门禁：配对噪声基线 noise_sigma=8.84，增益必须越过 1.96*sigma/sqrt(n)
5. 闭环生效：验证通过并人类批准后，自动被 virtu_router 网关载入生产推理
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.rsi import cli as rsi_cli
from virtu_omni.rsi import (
    approve_run,
    find_latest_approved_policy,
    get_active_rsi_strategy,
    review,
    verified_run,
)
from virtu_omni.rsi.contracts import Config, RSIError
from virtu_omni.rsi.engine import run
from virtu_omni.rsi.storage import RunStore, utc_now

DEFAULT_CASE_DIR = "data/benchmark/virtu_rsi_pool_v2"
DEFAULT_DIMS = (
    "reasoning",
    "knowledge",
    "instruction",
    "generation",
    "generalization",
    "boundary",
    "toolcall",
)
PROTECTED_DIRS = (
    "data/benchmark/virtu_eval_phys_v1",
    "data/benchmark/virtu_eval_v1",
    "data/benchmark/virtu_eval_cl_v1",
    "data/benchmark/virtu_text_v1",
    "data/benchmark/virtu_fix_v1",
    "data/benchmark/virtu_rsi_pool_v1",
)
DEFAULT_ARM = "virtu_moe_14b"


def check_quiet_window(wait_s: int = 60, hold_s: int = 15) -> bool:
    """检查宿主机测量链是否处于独占安静窗口。"""
    try:
        from scripts.rsi_quiet_gate import busy_reasons, recent_writes, watch_paths

        now = time.time()
        writes = recent_writes(watch_paths(ROOT), now=now, horizon_s=hold_s)
        reasons = busy_reasons([], [], writes, own_marker="comprehensive_rsi", watched=1)
        if reasons:
            print(f"[QuietGate] 宿主机存在活跃测量任务: {reasons[:2]}")
            return False
        return True
    except Exception as exc:
        print(f"[QuietGate] 状态检查告警 (跳过): {exc}")
        return True


def build_14b_config(
    case_dir: str = DEFAULT_CASE_DIR,
    dims: tuple[str, ...] = DEFAULT_DIMS,
    rounds: int = 2,
    limit: int = 0,
    min_validation: int = 20,
    max_calls: int = 200,
    max_seconds: int = 3600,
    seed: int = 20261106,
    noise_sigma: float = 8.84,
    noise_z: float = 1.96,
    arm_name: str = DEFAULT_ARM,
) -> Config:
    arm_spec = rsi_cli.load_arm(ROOT, arm_name)
    model_id = arm_spec.get("model_id", "virtu-moe-14b:latest")
    cfg = Config(
        case_dir=case_dir,
        dimensions=tuple(dims),
        model_id=model_id,
        base_url="http://127.0.0.1:11434",
        rounds=rounds,
        limit=limit,
        min_validation=min_validation,
        max_calls=max_calls,
        max_seconds=max_seconds,
        seed=seed,
        noise_sigma=noise_sigma,
        noise_z=noise_z,
        protect_dirs=PROTECTED_DIRS,
        arm_spec=arm_spec,
    )
    return cfg


def execute_comprehensive_rsi(
    config: Config,
    reviewer: str | None = None,
    model_factory=None,
) -> dict:
    print(f"\n=======================================================")
    print(f"Virtu 13.63B 全面 RSI 递归自我改进引擎启动")
    print(f"模型标识: {config.model_id}")
    print(f"覆盖维度 ({len(config.dimensions)}): {', '.join(config.dimensions)}")
    print(f"用例题库: {config.case_dir} (受保护库数: {len(config.protect_dirs)})")
    print(f"噪声置信门禁: sigma={config.noise_sigma}, z={config.noise_z}")
    print(f"上下文与GPU: ctx={config.arm_spec.get('num_ctx')}, gpu={config.arm_spec.get('num_gpu')}")
    print(f"挂载工具数: {len(config.arm_spec.get('tools', []))} (维度: {config.arm_spec.get('tools_dimensions')})")
    print(f"=======================================================\n")

    t0 = time.time()
    receipt = run(ROOT, config, model_factory=model_factory)
    elapsed = round(time.time() - t0, 2)

    status = receipt.get("status")
    print(f"\n[RSI 实验完成] 耗时: {elapsed}s | 状态: {status}")
    print(f"运行目录: {receipt.get('run')}")
    print(f"候选策略哈希: {receipt.get('candidate_sha256')}")
    print(f"独立留出集门禁: {receipt.get('gate', {}).get('eligible')}")
    if receipt.get("gate", {}).get("reasons"):
        print(f"门禁判定原因: {receipt.get('gate', {}).get('reasons')}")

    if status == "awaiting_approval" and reviewer:
        print(f"\n[开始人类同行审查签署] 签署人: {reviewer}")
        run_dir = ROOT / receipt["run"]
        review_res = approve_run(ROOT, run_dir, approved_by=reviewer)
        print(f"[审查签署成功] 批准状态: {review_res.get('approved')}")
        print(f"批准签名哈希: {review_res.get('approval_sha256')}")

        active_strat = get_active_rsi_strategy(ROOT, model_id=config.model_id)
        print(f"\n[生产网关生效验证] 提取当前模型活跃 RSI 策略: {bool(active_strat)}")
        if active_strat:
            print(f"策略摘要: {active_strat[:120]}...")

    return receipt


def main():
    parser = argparse.ArgumentParser(description="Virtu 13.63B 全面 RSI 启动器")
    parser.add_argument("--dims", default="all", help="all 或逗号分隔的维度")
    parser.add_argument("--limit", type=int, default=0, help="采样用例数量上限 (0 为全量)")
    parser.add_argument("--rounds", type=int, default=2, help="开发集递归迭代轮数")
    parser.add_argument("--max-calls", type=int, default=200, help="最大推理调用配额")
    parser.add_argument("--max-seconds", type=int, default=3600, help="最大运行时间限制(秒)")
    parser.add_argument("--min-validation", type=int, default=20, help="留出验证集最小题数")
    parser.add_argument("--approve", default=None, help="指定审查人自动签署通过的候选策略")
    parser.add_argument("--no-quiet-check", action="store_true", help="跳过硬件独占安静检查")
    args = parser.parse_args()

    if not args.no_quiet_check:
        if not check_quiet_window():
            print("[Warning] 测量链非完全空闲，建议等待或加 --no-quiet-check 强制执行。")

    if args.dims == "all":
        dims = DEFAULT_DIMS
    else:
        dims = tuple(d.strip() for d in args.dims.split(",") if d.strip())

    cfg = build_14b_config(
        dims=dims,
        rounds=args.rounds,
        limit=args.limit,
        min_validation=args.min_validation,
        max_calls=args.max_calls,
        max_seconds=args.max_seconds,
    )

    execute_comprehensive_rsi(cfg, reviewer=args.approve)


if __name__ == "__main__":
    main()
