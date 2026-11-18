#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/compress_d_models.py — D 盘大模型深度瘦身与空间压缩工具

设计原则（严防能力退化与严重幻觉）：
1. 严禁破坏生产基座与关键 LoRA 资产：
   - 保持 checkpoints/_base_qwen3_8b (纯净基座) 完整
   - 保持 checkpoints/*_lora (8 个核心 LoRA 适配器，共仅 2.5GB) 完整
   - 保持当前正式生效的生产量化模型 virtu-production-v3-q4_0.gguf (4.3GB) 完整
   - 保持本地视觉模型 models/Qwen3-VL-2B-Instruct 完整
2. 彻底释放无用占位与冗余中间分片：
   - 清理无效占位权重：virtu_omni_10b_base.pt (2.16GB, 已知空壳)
   - 清理历史熔炼残余：standardized_smelt_bundle 临时大权重 (2.38GB)
   - 清理已完全被 v3 替代的历史合并 HF 分片与旧版 GGUF (约 60.7GB)
   - 清理盲测 A/B 临时 safetensors 分片 (约 45.8GB, 对应 GGUF 已进入 Ollama)
3. Windows NTFS 原生 LZX 无损透明压缩：
   - 针对保留的 safetensors 与大权重文件，采用系统级 cluster 压缩，浮点数值 100% 逐 bit 无损
"""

import os
import sys
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.path.join(ROOT, "checkpoints")

sys.stdout.reconfigure(encoding="utf-8")


def get_dir_size_gb(path):
    if not os.path.exists(path):
        return 0.0
    total = 0
    if os.path.isfile(path):
        return os.path.getsize(path) / (1024 ** 3)
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except:
                pass
    return total / (1024 ** 3)


def audit_targets():
    """定义清理目标与保留资产名单。"""
    # 必须严格保留的核心生产资产清单
    retained_assets = {
        "Qwen3-8B 原始纯净基座 (HF)": os.path.join(CKPT, "_base_qwen3_8b"),
        "生产版全量融合模型 (HF v3)": os.path.join(CKPT, "virtu_cad_cam_merged_v3"),
        "正式生产量化模型 (Q4_0 GGUF)": os.path.join(CKPT, "virtu-production-v3-q4_0.gguf"),
        "生产级六合一 LoRA 适配器": os.path.join(CKPT, "virtu_cad_cam_production_lora"),
        "工具调用 LoRA 适配器": os.path.join(CKPT, "virtu_toolcall_lora"),
        "图灵通用对话 LoRA 适配器": os.path.join(CKPT, "turing_conversational_lora"),
        "工业六大软件 LoRA 适配器": os.path.join(CKPT, "cad_cam_six_software_lora"),
        "智能体编排 LoRA 适配器": os.path.join(CKPT, "omni_autonomous_agent_lora"),
        "UG 专家指导 LoRA 适配器": os.path.join(CKPT, "ug_teacher_guided_agent_lora"),
        "本地视觉 Qwen3-VL 模型": os.path.join(ROOT, "models", "Qwen3-VL-2B-Instruct"),
    }

    # 第一阶段：确定无效的僵尸/占位文件
    phase1_dead_weights = [
        ("无效占位权重 (已知空壳)", os.path.join(CKPT, "virtu_omni_10b_base.pt")),
        ("历史熔炼包大权重残余", os.path.join(CKPT, "standardized_smelt_bundle", "weights", "standardized_weights.pt")),
    ]

    # 第二阶段：历史被替代的旧版本合并产物 (已由 v3 完全覆盖)
    phase2_obsolete_merges = [
        ("旧版合并分片 v1 (HF)", os.path.join(CKPT, "virtu_merged")),
        ("旧版合并分片 v2 (HF)", os.path.join(CKPT, "virtu_merged_v2")),
        ("旧版纯工具调用合并分片 (HF)", os.path.join(CKPT, "virtu_merged_toolcall")),
        ("旧版 GGUF v1", os.path.join(CKPT, "virtu-q4_0.gguf")),
        ("旧版 GGUF v1 回执", os.path.join(CKPT, "virtu-q4_0.gguf.receipt.json")),
        ("旧版 GGUF v2", os.path.join(CKPT, "virtu-omni-v2-q4_0.gguf")),
        ("旧版 GGUF v2 回执", os.path.join(CKPT, "virtu-omni-v2-q4_0.gguf.receipt.json")),
        ("旧版纯工具 GGUF", os.path.join(CKPT, "virtu-toolcall-q4_0.gguf")),
        ("旧版纯工具 GGUF 回执", os.path.join(CKPT, "virtu-toolcall-q4_0.gguf.receipt.json")),
    ]

    # 第三阶段：盲测临时未量化中间体 (GGUF 与 Ollama 已有对应模型，15GB safetensors 是中间转译体)
    # 保留 _eval_base-q4_0.gguf 等评测 GGUF，确保正在进行的评测流程不受任何干扰
    phase3_eval_intermediates = [
        ("盲测临时分片 single (HF 15GB)", os.path.join(CKPT, "_eval_single")),
        ("盲测临时分片 delta5 (HF 15GB)", os.path.join(CKPT, "_eval_delta5")),
        ("盲测临时分片 lin5 (HF 15GB)", os.path.join(CKPT, "_eval_lin5")),
    ]

    return retained_assets, phase1_dead_weights, phase2_obsolete_merges, phase3_eval_intermediates


def run_cleanup(dry_run=True, apply_lzx=False):
    print("=" * 75)
    print("Virtu-CAD-CAM D 盘模型资产深度压缩与空间优化工具")
    print(f"模式: {'【预演探测 DRY-RUN】(不执行实际删除)' if dry_run else '【正式执行 EXECUTE】'}")
    print("=" * 75)

    retained, p1, p2, p3 = audit_targets()

    # 1. 检查核心资产健康度
    print("\n[1/4] 核心生产资产防退化门禁审计:")
    all_retained_ok = True
    for label, path in retained.items():
        exists = os.path.exists(path)
        size = get_dir_size_gb(path)
        status = "OK" if exists else "MISSING"
        if not exists:
            all_retained_ok = False
        print(f"  [{status:7s}] {label:<32s} : {size:6.2f} GB ({path})")

    if not all_retained_ok:
        print("\n[ERROR] 核心生产资产存在缺失，严禁盲目清理！终止操作。")
        return

    # 2. 统计各阶段预计释放空间
    total_freed = 0.0

    def process_group(group_name, item_list):
        nonlocal total_freed
        print(f"\n[{group_name}]:")
        group_freed = 0.0
        for label, path in item_list:
            if os.path.exists(path):
                sz = get_dir_size_gb(path)
                group_freed += sz
                total_freed += sz
                action = "[WILL REMOVE]" if dry_run else "[REMOVED]"
                print(f"  {action} {label:<30s} : {sz:6.2f} GB -> {path}")
                if not dry_run:
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                    except Exception as e:
                        print(f"    [FAIL] 删除失败: {e}")
            else:
                print(f"  [ALREADY CLEAN] {label:<30s} : 不存在 (已清理)")
        print(f"  --> 本组节省空间: {group_freed:.2f} GB")

    process_group("第一阶段：清理无效占位与僵尸权重 (纯空壳，零风险)", p1)
    process_group("第二阶段：清理已废弃的历史旧版本合并产物 (已由 v3 替代)", p2)
    process_group("第三阶段：清理临时 A/B 盲测 safetensors 中间体 (已转 GGUF)", p3)

    print("\n" + "=" * 75)
    print(f"全流程预计释放磁盘空间: {total_freed:.2f} GB")
    print("=" * 75)

    # 4. 可选的 NTFS LZX 透明压缩
    if apply_lzx:
        print("\n[第四阶段] 执行 Windows NTFS 原生 LZX 级别 cluster 透明压缩 (bit 级无损)...")
        targets = [
            os.path.join(CKPT, "_base_qwen3_8b"),
            os.path.join(CKPT, "virtu_cad_cam_merged_v3"),
            os.path.join(ROOT, "models", "Qwen3-VL-2B-Instruct"),
            os.path.join(CKPT, "virtu-production-v3-q4_0.gguf")
        ]
        for t in targets:
            if os.path.exists(t):
                print(f"  压缩中: {t} ...")
                subprocess.run(["compact", "/c", "/s", "/exe:lzx", str(t)], shell=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D 盘模型空间深度压缩与清理")
    parser.add_argument("--execute", action="store_true", help="执行实际删除操作")
    parser.add_argument("--lzx", action="store_true", help="同时执行 NTFS LZX 透明压缩")
    args = parser.parse_args()

    run_cleanup(dry_run=not args.execute, apply_lzx=args.lzx)
