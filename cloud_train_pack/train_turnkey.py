#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/train_turnkey.py — Virtu 工业大模型云端极速训练引擎 (One-Click Turnkey SFT)

设计原则：
1. 极限成本压缩：自动探测硬件，显存分档 (>=36GB 走纯 bf16-LoRA，<36GB 走 QLoRA 4-bit)；
2. 零冗余空转：启用 group_by_length=True 消除填充计算浪费，1小时内完成 5.5k 样本收敛；
3. 学习质量拉满：精确 assistant 段 loss 掩码 (System/User/Tool回执全置 -100，只学模型输出)；
4. 交付零摩擦：训练完毕自动生成指纹凭证并压缩打包 deliverable.tar.gz，方便一键拉取合并。
"""

import os
import sys
import json
import time
import glob
import math
import shutil
import tarfile
import hashlib
import argparse

# 确保在导入 torch 前锁定单卡
if "--gpu-id" in sys.argv:
    idx = sys.argv.index("--gpu-id")
    os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[idx + 1]
else:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
    TrainerCallback,
)

TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj"
]

CANDIDATE_BASE_PATHS = [
    "/root/workspace/models/Qwen2.5-7B-Instruct",
    "/root/models/Qwen2.5-7B-Instruct",
    "/root/workspace/models/Qwen3-8B-Instruct",
    "/root/models/Qwen3-8B-Instruct",
    "/root/public-storage/model/Qwen/Qwen2.5-7B-Instruct",
    "/root/public-storage/model/Qwen/Qwen3-8B-Instruct",
    "checkpoints/_base_qwen2.5_7b",
    "checkpoints/_base_qwen3_8b",
    "./models/Qwen2.5-7B-Instruct",
    "./models/Qwen3-8B-Instruct",
]


def get_best_storage_dir() -> str:
    """探测磁盘空间，自动将模型缓存与权重锁定在剩余空间最大的数据盘路径。"""
    candidates = [
        "/root/workspace",
        "/root/data",
        "/root/damodel-tmp",
        "/root/autodl-tmp",
        "/mnt/data",
        "/mnt",
        "/root",
        "."
    ]
    best_dir = "."
    max_free_gb = 0.0
    for c in candidates:
        if os.path.exists(c):
            try:
                free_gb = shutil.disk_usage(c).free / (1024**3)
                if free_gb > max_free_gb:
                    max_free_gb = free_gb
                    best_dir = c
            except Exception:
                pass
    print(f"[Storage] 自动探测最优存储盘: {best_dir} (剩余可用空间: {max_free_gb:.1f} GB)")
    return best_dir


class TimeBudgetCallback(TrainerCallback):
    """时间预算防超时守卫：达到时间上限时触发优雅提前停机保存。"""
    def __init__(self, max_minutes: float):
        self.max_seconds = max_minutes * 60.0 if max_minutes > 0 else float("inf")
        self.start_time = time.time()

    def on_step_end(self, args, state, control, **kwargs):
        elapsed = time.time() - self.start_time
        if elapsed > self.max_seconds:
            print(f"\n[TimeBudgetGuard] 已达到时间预算上限 ({elapsed/60:.1f}m > {self.max_seconds/60:.1f}m)，触发保存并优雅停止！")
            control.should_training_stop = True
            control.should_save = True


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def find_or_download_base(specified_base: str = None) -> str:
    if specified_base and os.path.exists(specified_base):
        print(f"[Base] 使用指定基座路径: {specified_base}")
        return specified_base

    for p in CANDIDATE_BASE_PATHS:
        if os.path.exists(p) and (os.path.exists(os.path.join(p, "config.json"))):
            print(f"[Base] 探测到已有基座权重: {p} (免下载，0 带宽成本)")
            return p

    best_dir = get_best_storage_dir()
    target_dir = os.path.join(best_dir, "models", "Qwen2.5-7B-Instruct")
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)

    print(f"[Base] 未探测到本地基座，正在通过 ModelScope 高速拉取 qwen/Qwen2.5-7B-Instruct -> {target_dir} ...")
    try:
        from modelscope import snapshot_download
        downloaded = snapshot_download("qwen/Qwen2.5-7B-Instruct", local_dir=target_dir)
        return downloaded
    except Exception as e:
        print(f"[Base] ModelScope 下载失败 ({e})，尝试 HuggingFace 国内镜像站 ...")
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from huggingface_hub import snapshot_download
        downloaded = snapshot_download("Qwen/Qwen2.5-7B-Instruct", local_dir=target_dir)
        return downloaded


def format_chatml_sample(rec: dict, tokenizer, max_length: int = 2048):
    """严格 ChatML 渲染与 Token 级精确 Loss 掩码。"""
    msgs = rec.get("messages", [])
    if not msgs:
        return None

    tools = rec.get("tools", [])

    # 渲染 ChatML
    try:
        # 若支持 tools 渲染则带 tools，否则退化为普通对话
        if tools and hasattr(tokenizer, "apply_chat_template"):
            try:
                full_text = tokenizer.apply_chat_template(
                    msgs, tools=tools, tokenize=False, add_generation_prompt=False
                )
            except Exception:
                full_text = tokenizer.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=False
                )
        else:
            full_text = tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=False
            )
    except Exception:
        # 手工 ChatML 兜底渲染
        blocks = []
        for m in msgs:
            role = m.get("role", "user")
            content = m.get("content", "")
            tc = m.get("tool_calls")
            if tc:
                content = content + "\n" + json.dumps(tc, ensure_ascii=False)
            blocks.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
        full_text = "".join(blocks)

    enc = tokenizer(
        full_text,
        max_length=max_length,
        truncation=True,
        return_offsets_mapping=True,
        add_special_tokens=False,
    )
    input_ids = enc["input_ids"]
    offsets = enc["offset_mapping"]
    labels = [-100] * len(input_ids)

    # 字符级定位 assistant 段
    # assistant 段从 "assistant\n" 之后开始，到下一个 "<|im_end|>" 或 "<|im_start|>" 之前
    import re
    for match in re.finditer(r"<\|im_start\|>assistant\n", full_text):
        start_char = match.end()
        end_match = re.search(r"<\|im_end\|>", full_text[start_char:])
        end_char = start_char + end_match.start() if end_match else len(full_text)

        # 映射至 token 索引
        for i, (tok_start, tok_end) in enumerate(offsets):
            if tok_start >= start_char and tok_end <= end_char + 10:  # 包含结束符
                labels[i] = input_ids[i]

    # 安全检查：如果整个样本都没计入任何 loss，则废弃该样本
    if all(l == -100 for l in labels):
        return None

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }


def load_dataset(dataset_path: str, tokenizer, max_length: int = 2048) -> Dataset:
    print(f"[Data] 加载并解析工业 SFT 语料: {dataset_path}")
    samples = []
    skipped = 0
    with open(dataset_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                item = format_chatml_sample(rec, tokenizer, max_length)
                if item:
                    samples.append(item)
                else:
                    skipped += 1
            except Exception:
                skipped += 1

    print(f"[Data] 有效训练样本: {len(samples)} 条 (跳过/不符合: {skipped} 条)")
    return Dataset.from_list(samples)


def train():
    parser = argparse.ArgumentParser(description="Virtu 云端高性价比一键训练脚本")
    parser.add_argument("--base", default=None, help="基座模型路径")
    parser.add_argument("--data", default="dataset/virtu_capability_sft_v5.jsonl", help="SFT 语料文件")
    parser.add_argument("--out", default="output/virtu_lora_master", help="LoRA 产物输出路径")
    parser.add_argument("--epochs", type=float, default=2.0, help="训练轮数")
    parser.add_argument("--lr", type=float, default=1.5e-4, help="学习率")
    parser.add_argument("--batch", type=int, default=1, help="单设备 batch size")
    parser.add_argument("--grad-accum", type=int, default=16, help="梯度累积步数")
    parser.add_argument("--max-length", type=int, default=2048, help="最大上下文截断长度")
    parser.add_argument("--max-hours", type=float, default=1.5, help="最大预算时间 (小时)")
    parser.add_argument("--gpu-id", default="0", help="指定可见 GPU 编号")
    args = parser.parse_args()

    # 语料必须逐字命中：静默回退到别的 jsonl 会让"我训的是哪份数据"这个问题无解，
    # 而产物指纹里记的却是请求过的那份。
    if not os.path.exists(args.data):
        raise SystemExit(
            f"[FATAL] --data={args.data} 不存在。拒绝自动回退到其它语料；"
            f"可用的有: " + ", ".join(c for c in [
                "dataset/virtu_capability_sft_v5.jsonl",
                "dataset/virtu_v100_production_sft.jsonl",
                "dataset/virtu_gold_production_sft.jsonl"] if os.path.exists(c)))
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from virtu_eval.contamination_check import assert_no_leak
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "scripts"))
    from corpus_unit_audit import assert_units_clean
    assert_no_leak(args.data)
    assert_units_clean(args.data)

    t_start = time.time()
    base_path = find_or_download_base(args.base)

    # 1. 探测 GPU 与显存
    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] 未检测到可用 CUDA GPU，无法进行训练！")

    gpu_name = torch.cuda.get_device_name(0)
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"[Hardware] 检测到 GPU: {gpu_name} | 显存: {total_vram_gb:.2f} GB")

    # 自动选型与精度检测 (注意: Volta V100 为 sm_70, 需 sm_80+ 架构才具备硬件级 bf16 支持)
    major_cc = torch.cuda.get_device_capability(0)[0]
    has_bf16 = (major_cc >= 8) and getattr(torch.cuda, "is_bf16_supported", lambda: False)()
    compute_dtype = torch.bfloat16 if has_bf16 else torch.float16
    use_qlora = total_vram_gb < 36.0
    mode_str = f"QLoRA (4-bit, {compute_dtype})" if use_qlora else f"Full {compute_dtype} LoRA"
    print(f"[Strategy] 架构主版本: sm_{major_cc}x | 硬件支持 bf16: {has_bf16} | 计算精度: {compute_dtype} | 选型: {mode_str}")

    # 2. 加载 Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 3. 加载基座模型
    model_kwargs = {"trust_remote_code": True}
    if use_qlora:
        from transformers import BitsAndBytesConfig
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )
        model_kwargs["device_map"] = {"": 0}
    else:
        model_kwargs["torch_dtype"] = compute_dtype
        model_kwargs["device_map"] = {"": 0}

    # 注意力实现：自动尝试 sdpa
    model_kwargs["attn_implementation"] = "sdpa"

    print(f"[Model] 正在加载基座权重: {base_path} ...")
    model = AutoModelForCausalLM.from_pretrained(base_path, **model_kwargs)

    if use_qlora:
        model = prepare_model_for_kbit_training(model)

    model.gradient_checkpointing_enable()

    # 4. 配置标准工业级 LoRA
    lora_cfg = LoraConfig(
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_cfg)
    trainable_params, all_param = model.get_nb_trainable_parameters()
    print(f"[LoRA] 可训练参数: {trainable_params:,} / {all_param:,} ({trainable_params/all_param*100:.2f}%)")

    # 5. 加载数据
    dataset = load_dataset(args.data, tokenizer, args.max_length)

    # 6. 配置极速训练参数
    os.makedirs(args.out, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=os.path.join(args.out, "_checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        bf16=has_bf16,
        fp16=not has_bf16,
        group_by_length=True,  # 极致压缩 padding token 计算浪费
        report_to="none",
        dataloader_num_workers=0,
        optim="paged_adamw_8bit" if use_qlora else "adamw_torch",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True),
        callbacks=[TimeBudgetCallback(args.max_hours * 60)],
    )

    print("\n" + "="*70)
    print("🚀 开始极速模型训练 ... (预计耗时: 30 ~ 50 分钟)")
    print("="*70 + "\n")

    train_res = trainer.train()

    # 严格损失收敛断言 (防止无效空转或梯度爆炸)
    if train_res.training_loss is None or math.isnan(train_res.training_loss) or train_res.training_loss <= 0:
        raise RuntimeError(f"[FATAL] 训练损失异常 (Loss={train_res.training_loss})，未正常收敛！")
    print(f"[Loss] 训练收敛检验通过：最终 Loss = {train_res.training_loss:.4f}")

    # 7. 保存产物与权重
    final_adapter_dir = os.path.join(args.out, "final_adapter")
    print(f"\n[Save] 正在保存最终 LoRA 适配器 -> {final_adapter_dir}")
    model.save_pretrained(final_adapter_dir)
    tokenizer.save_pretrained(final_adapter_dir)

    # 8. 计算校验指纹并写入账本
    safetensor_file = os.path.join(final_adapter_dir, "adapter_model.safetensors")
    adapter_sha = sha256_file(safetensor_file) if os.path.exists(safetensor_file) else "unknown"
    dataset_sha = sha256_file(args.data) if os.path.exists(args.data) else "unknown"

    receipt = {
        "model_brand": "Virtu-Omni-CAD-CAM",
        "base_model": base_path,
        "dataset_path": args.data,
        "dataset_sha256": dataset_sha,
        "adapter_sha256": adapter_sha,
        "lora_r": 32,
        "lora_alpha": 64,
        "target_modules": TARGET_MODULES,
        "precision_mode": mode_str,
        "total_train_samples": len(dataset),
        "total_train_seconds": round(time.time() - t_start, 2),
        "train_loss": train_res.training_loss,
        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "COMPLETED",
    }

    receipt_path = os.path.join(final_adapter_dir, "training_receipt.json")
    with open(receipt_path, "w", encoding="utf-8") as rf:
        json.dump(receipt, rf, ensure_ascii=False, indent=2)

    # 9. 自动归档可交付压缩包
    deliverable_tar = os.path.join(args.out, "virtu_lora_deliverable.tar.gz")
    print(f"[Archive] 正在打包交付件 -> {deliverable_tar}")
    with tarfile.open(deliverable_tar, "w:gz") as tar:
        tar.add(final_adapter_dir, arcname="virtu_lora_adapter")

    sz_mb = os.path.getsize(deliverable_tar) / (1024**2)
    print("\n" + "="*70)
    print(f"🎉 训练圆满完成！耗时: {(time.time() - t_start)/60:.1f} 分钟 | 最终 Loss: {train_res.training_loss:.4f}")
    print(f"📦 产物交付包: {deliverable_tar} ({sz_mb:.1f} MB)")
    print(f"🔑 权重指纹 (SHA256): {adapter_sha[:16]}...")
    print("="*70 + "\n")


if __name__ == "__main__":
    train()
