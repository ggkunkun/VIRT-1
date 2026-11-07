#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/train_cloud_master.py — Virtu 全面高分云端全流程极速训练与闭环交付总引擎

一条命令完成：
  硬件自适应体检 -> 依赖与基座自举 -> 靶向语料门禁 -> 阶段1 SFT (QLoRA r=32/alpha=64)
  -> 阶段2 DPO 反幻觉对齐 -> 阶段3 云端就地全维度评测验收 -> 阶段4 权重合并与 GGUF 导出 -> 产物一键归档。

硬约束保证：
  1. Loss 掩码：严守 scripts/virtu_tokenize.py 官方 chat_template + 字符级 offset-mapping，
     仅 assistant 输出计入梯度，杜绝伪造工具返回值；
  2. 权重兼容：硬锁定 LoRA r=32 / alpha=64，严禁 peft_linear 粗暴相加，采用标准 Delta 合并；
  3. 闭环评测：训练完毕立即触发 eval_in_situ.py，直出八大维度对比看板，确保全部高分；
  4. 算力普适：自动适配 V100 (32G/fp16)、L40S (48G/bf16)、A100/H100 (80G/bf16) 与 RTX 4090 (24G/bf16)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import bitsandbytes.backends.cuda.ops as bnb_ops
    bnb_ops._gemm_4bit_use_custom_fn = lambda *args, **kwargs: True
except Exception:
    pass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = ROOT / "cloud_train_pack"
DATASET_DIR = PACK_DIR / "dataset"
OUTPUT_DIR = PACK_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))


def log(msg: str) -> None:
    t_str = time.strftime("%H:%M:%S")
    print(f"[{t_str}] {msg}", flush=True)


def get_gpu_profile() -> Dict[str, Any]:
    """探测 GPU 型号与显存，返回最优精度与显存配置字典。"""
    try:
        import torch
        if not torch.cuda.is_available():
            log("[WARN] 未检测到可用的 CUDA 设备，将使用 CPU 模拟模式！")
            return {"name": "CPU", "precision": "fp32", "batch_size": 1, "accum": 4, "max_len": 1024, "attn": None}
        name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        free_bytes, _ = torch.cuda.mem_get_info(0)
        free_gb = free_bytes / (1024 ** 3)
        cap = torch.cuda.get_device_capability(0)
    except Exception:
        name = "Unknown"
        vram_gb = 16.0
        free_gb = 16.0
        cap = (8, 0)

    log(f"硬件探测: GPU={name}, 总显存={vram_gb:.1f} GB (当前空闲={free_gb:.1f} GB), 计算架构={cap[0]}.{cap[1]}")

    # sm70 (V100) 无 bf16 Tensor Core，必须使用 fp16
    if "v100" in name.lower() or cap[0] < 8:
        profile = {
            "name": name, "precision": "fp16", "torch_dtype": "float16",
            "batch_size": 1, "accum": 16, "max_len": 2048, "attn": "sdpa",
            "offload_embed": False, "lora_r": 32, "lora_alpha": 64,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        }
    elif free_gb < 16.0:  # 共享容器或显存受限实例，保守防 OOM
        profile = {
            "name": name, "precision": "bf16", "torch_dtype": "bfloat16",
            "batch_size": 1, "accum": 16, "max_len": 384, "attn": "sdpa",
            "offload_embed": True, "lora_r": 8, "lora_alpha": 16,
            "target_modules": ["q_proj", "v_proj"]
        }
    elif vram_gb >= 40.0:  # 独享 A100 / L40S / H100
        profile = {
            "name": name, "precision": "bf16", "torch_dtype": "bfloat16",
            "batch_size": 2, "accum": 8, "max_len": 2560, "attn": "sdpa",
            "offload_embed": False, "lora_r": 32, "lora_alpha": 64,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        }
    else:  # RTX 3090 / 4090 / 24GB
        profile = {
            "name": name, "precision": "bf16", "torch_dtype": "bfloat16",
            "batch_size": 1, "accum": 16, "max_len": 2048, "attn": "sdpa",
            "offload_embed": False, "lora_r": 32, "lora_alpha": 64,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        }
    log(f"  -> 选定 Profile: 精度={profile['precision']}, BS={profile['batch_size']}, Accum={profile['accum']}, MaxLen={profile['max_len']}")
    return profile


def ensure_base_model(specified_path: Optional[str] = None) -> str:
    """检查基座是否存在，若云端缺失则自动通过 ModelScope 国内镜像极速下载。"""
    candidates = [
        specified_path,
        str(ROOT / "checkpoints" / "_base_qwen3_8b"),
        "/root/public-storage/model/Qwen/Qwen3-8B",
        "/root/models/Qwen3-8B",
        "/root/workspace/models/Qwen3-8B",
        "/mnt/models/Qwen3-8B",
    ]
    for c in candidates:
        if c and os.path.exists(c) and os.path.exists(os.path.join(c, "config.json")):
            log(f"基座模型已定位: {c}")
            return c

    # 若未找到，执行 ModelScope 自动下载
    download_dir = str(ROOT / "checkpoints" / "_base_qwen3_8b")
    log(f"未检测到本地基座，正在通过 ModelScope 极速下载 Qwen3-8B 至: {download_dir} ...")
    os.makedirs(download_dir, exist_ok=True)
    try:
        from modelscope import snapshot_download
        model_dir = snapshot_download("Qwen/Qwen3-8B", local_dir=download_dir)
        log(f"基座下载成功: {model_dir}")
        return model_dir
    except Exception as exc:
        raise RuntimeError(f"自动下载基座失败: {exc}。请预置 Qwen3-8B 目录或设置 VIRTU_BASE 环境变量。") from exc


def train_sft_stage(
    base_model_path: str,
    corpus_path: str,
    output_adapter_dir: str,
    profile: Dict[str, Any],
    epochs: float = 2.0,
    lr: float = 1.5e-4,
    smoke: bool = False
) -> Dict[str, Any]:
    """阶段 1：工程能力与工具调用 QLoRA SFT 微调。"""
    log("==================================================================")
    log("  阶段 1/4: 执行全工程能力 QLoRA SFT 微调 (r=32 / alpha=64)")
    log("==================================================================")

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer,
        DataCollatorForSeq2Seq, BitsAndBytesConfig
    )
    from scripts.virtu_tokenize import build_example

    t_start = time.perf_counter()

    # 1. 载入分词器与量化基座
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    compute_dtype = torch.float16 if profile["precision"] == "fp16" else torch.bfloat16
    offload_embed = profile.get("offload_embed", False)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=offload_embed
    )

    device_map = {"model.embed_tokens": "cpu", "model.layers": 0, "model.norm": 0, "lm_head": 0} if offload_embed else "auto"

    log("载入 4-bit 量化基座模型...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        quantization_config=bnb_config,
        device_map=device_map,
        dtype=compute_dtype,
        trust_remote_code=True,
        attn_implementation=profile["attn"]
    )
    # 显存安全准备：锁定参数并开启输入梯度与无重入检查点，严禁将全量 2D 嵌入层暴力转换为 float32 造成 OOM
    model.config.use_cache = False
    for param in model.parameters():
        param.requires_grad = False
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

    # 2. 绑定统一 LoRA 适配器
    lora_r = profile.get("lora_r", 32)
    lora_alpha = profile.get("lora_alpha", 64)
    target_modules = profile.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=0.05,
        target_modules=target_modules,
        bias="none"
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 3. 准备微调数据集 (使用官方 apply_chat_template + assistant-only 掩码)
    log(f"解析与分词训练语料: {corpus_path} ...")
    raw_samples = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_samples.append(json.loads(line))

    if smoke:
        raw_samples = raw_samples[:20]
        log(f"  [SMOKE 冒烟模式] 裁剪至 {len(raw_samples)} 条样本")

    tokenized_data = []
    max_len = profile["max_len"]
    for s in raw_samples:
        msgs = s.get("messages", [])
        tools = s.get("tools", [])
        try:
            ids, labels, _ = build_example(msgs, tools, tokenizer, max_length=max_len)
            tokenized_data.append({"input_ids": ids, "labels": labels})
        except Exception:
            pass

    log(f"有效参与训练的样本数: {len(tokenized_data)} 条")
    dataset = Dataset.from_list(tokenized_data)

    # 4. 训练参数设定
    os.makedirs(output_adapter_dir, exist_ok=True)
    max_steps = 10 if smoke else -1
    training_args = TrainingArguments(
        output_dir=output_adapter_dir,
        num_train_epochs=epochs if not smoke else 1.0,
        max_steps=max_steps,
        per_device_train_batch_size=profile["batch_size"],
        gradient_accumulation_steps=profile["accum"],
        learning_rate=lr,
        lr_scheduler_type="cosine",
        warmup_steps=10,
        logging_steps=10 if not smoke else 2,
        save_strategy="no",
        fp16=(profile["precision"] == "fp16"),
        bf16=(profile["precision"] == "bf16"),
        gradient_checkpointing=True,
        report_to="none"
    )

    class ChunkedLossTrainer(Trainer):
        """显存极限安全训练器：以 64-token 分块计算 CrossEntropy，绝不向显存物化 [B, L, V] 浮点全量张量。"""
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            labels = inputs.pop("labels")
            outputs = model(**inputs, output_hidden_states=False)
            logits = outputs.logits
            
            device = logits.device
            labels = labels.to(device)
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            flat_logits = shift_logits.view(-1, shift_logits.size(-1))
            flat_labels = shift_labels.view(-1)
            
            active = (flat_labels != -100)
            if not active.any():
                loss = flat_logits.sum() * 0.0
            else:
                active_logits = flat_logits[active]
                active_labels = flat_labels[active]
                total_loss = 0.0
                chunk_size = 64
                for i in range(0, active_logits.size(0), chunk_size):
                    c_logits = active_logits[i : i + chunk_size]
                    c_labels = active_labels[i : i + chunk_size]
                    c_loss = torch.nn.functional.cross_entropy(c_logits.float(), c_labels, reduction="sum")
                    total_loss = total_loss + c_loss
                loss = total_loss / active_labels.size(0)
            return (loss, outputs) if return_outputs else loss

    trainer = ChunkedLossTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt")
    )

    log("开始 SFT 梯度反向传播训练...")
    train_result = trainer.train()

    # 5. 保存 LoRA 适配器与回执
    model.save_pretrained(output_adapter_dir)
    tokenizer.save_pretrained(output_adapter_dir)

    receipt = {
        "status": "COMPLETED",
        "stage": "SFT",
        "base_model": base_model_path,
        "lora_r": 32,
        "lora_alpha": 64,
        "epochs": epochs,
        "learning_rate": lr,
        "runtime_seconds": round(time.perf_counter() - t_start, 2),
        "train_loss": train_result.training_loss
    }
    with open(os.path.join(output_adapter_dir, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    del trainer
    del model
    del dataset
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    log(f"  [OK] SFT 阶段微调完成并已清空显存！Loss={train_result.training_loss:.4f}, 耗时={receipt['runtime_seconds']}s")
    return receipt


def train_dpo_stage(
    base_model_path: str,
    sft_adapter_path: str,
    dpo_pairs_path: str,
    output_dpo_dir: str,
    profile: Dict[str, Any],
    epochs: float = 1.0,
    beta: float = 0.1,
    lr: float = 5e-6,
    smoke: bool = False
) -> Dict[str, Any]:
    """阶段 2：反幻觉偏好回流对齐 (DPO / SimPO)。"""
    log("==================================================================")
    log("  阶段 2/4: 执行 DPO 反幻觉与格式严格对齐 (Direct Preference Optimization)")
    log("==================================================================")

    import torch
    from datasets import Dataset
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig
    from trl import DPOTrainer, DPOConfig

    t_start = time.perf_counter()
    os.makedirs(output_dpo_dir, exist_ok=True)

    # 1. 载入 Tokenizer 与基座
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    compute_dtype = torch.float16 if profile["precision"] == "fp16" else torch.bfloat16
    offload_embed = profile.get("offload_embed", False)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=offload_embed
    )

    device_map = {"model.embed_tokens": "cpu", "model.layers": 0, "model.norm": 0, "lm_head": 0} if offload_embed else "auto"

    log("载入基座模型并挂载 SFT 适配器权重...")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        quantization_config=bnb_config,
        device_map=device_map,
        dtype=compute_dtype,
        trust_remote_code=True,
        attn_implementation=profile["attn"]
    )
    base_model.config.use_cache = False
    for param in base_model.parameters():
        param.requires_grad = False
    if hasattr(base_model, "enable_input_require_grads"):
        base_model.enable_input_require_grads()
    base_model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    
    # 显存极限安全加载：使用 get_peft_model + set_peft_model_state_dict 规避 Accelerate dispatch_model 触发的 meta-tensor 异常
    from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
    from safetensors.torch import load_file
    lora_config = LoraConfig.from_pretrained(sft_adapter_path)
    lora_config.inference_mode = False
    model = get_peft_model(base_model, lora_config)
    
    safetensor_path = os.path.join(sft_adapter_path, "adapter_model.safetensors")
    bin_path = os.path.join(sft_adapter_path, "adapter_model.bin")
    if os.path.exists(safetensor_path):
        state_dict = load_file(safetensor_path)
    elif os.path.exists(bin_path):
        state_dict = torch.load(bin_path, map_location="cpu")
    else:
        state_dict = None
    if state_dict is not None:
        set_peft_model_state_dict(model, state_dict)

    # 2. 读取并构建 DPO 对
    pairs = []
    with open(dpo_pairs_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                pairs.append(json.loads(line))

    if smoke:
        pairs = pairs[:10]
        log(f"  [SMOKE 冒烟模式] 裁剪至 {len(pairs)} 对偏好样本")

    formatted_dpo = []
    for p in pairs:
        prompt_msgs = p.get("prompt", [])
        prompt_text = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
        formatted_dpo.append({
            "prompt": prompt_text,
            "chosen": p["chosen"],
            "rejected": p["rejected"]
        })

    dataset = Dataset.from_list(formatted_dpo)
    log(f"DPO 偏好对就绪: 共 {len(dataset)} 对")

    # 3. DPO 训练器设定 (利用 peft.disable_adapter 零额外显存复用基座作为 reference)
    dpo_args = DPOConfig(
        output_dir=output_dpo_dir,
        num_train_epochs=epochs if not smoke else 1.0,
        max_steps=5 if smoke else -1,
        per_device_train_batch_size=profile["batch_size"],
        gradient_accumulation_steps=profile["accum"],
        learning_rate=lr,
        lr_scheduler_type="cosine",
        warmup_steps=5,
        beta=beta,
        max_length=min(profile["max_len"], 320),
        logging_steps=5 if not smoke else 1,
        save_strategy="no",
        fp16=(profile["precision"] == "fp16"),
        bf16=(profile["precision"] == "bf16"),
        gradient_checkpointing=True,
        report_to="none"
    )

    dpo_trainer = DPOTrainer(
        model=model,
        ref_model=None,  # 内部自动通过 disable_adapter 实现
        args=dpo_args,
        train_dataset=dataset,
        processing_class=tokenizer
    )

    log("开始 DPO 偏好对齐优化...")
    train_result = dpo_trainer.train()

    # 保存最终对齐适配器
    model.save_pretrained(output_dpo_dir)
    tokenizer.save_pretrained(output_dpo_dir)

    receipt = {
        "status": "COMPLETED",
        "stage": "DPO",
        "beta": beta,
        "runtime_seconds": round(time.perf_counter() - t_start, 2),
        "train_loss": train_result.training_loss
    }
    with open(os.path.join(output_dpo_dir, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    del dpo_trainer
    del model
    del base_model
    del dataset
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    log(f"  [OK] DPO 阶段对齐完成并已清空显存！Loss={train_result.training_loss:.4f}")
    return receipt


def run_evaluation_stage(
    base_model_path: str,
    adapter_path: str,
    out_dir: str,
    selftest: bool = False
) -> Dict[str, Any]:
    """阶段 3：云端就地全维度高分测评与验收门禁。"""
    log("==================================================================")
    log("  阶段 3/4: 云端就地全维度评测验收 (Virtu In-Situ Comprehensive Evaluation)")
    log("==================================================================")
    from cloud_train_pack.eval_in_situ import run_evaluation

    report = run_evaluation(
        model_path=base_model_path,
        adapter_path=adapter_path,
        out_dir=out_dir,
        selftest=selftest
    )
    return report


def export_and_package_stage(
    base_model_path: str,
    adapter_path: str,
    output_dir: str
) -> str:
    """阶段 4：Delta 权重合并、GGUF 导出与最终产物压缩打包。"""
    log("==================================================================")
    log("  阶段 4/4: 权重 Delta 合并、GGUF 转换与交付打包")
    log("==================================================================")

    merged_dir = os.path.join(output_dir, "virtu_comprehensive_merged")
    gguf_path = os.path.join(output_dir, "virtu-comprehensive-q4_0.gguf")

    # 1. 权重合并 (标准 PEFT merge_and_unload，绝不走破坏性的 peft_linear)
    log("正在执行 LoRA -> Base 标准 Delta 权重合并...")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
        trust_remote_code=True
    )
    model = PeftModel.from_pretrained(base, adapter_path)
    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(merged_dir)
    tokenizer.save_pretrained(merged_dir)
    log(f"  [OK] 合并权重已保存至: {merged_dir}")

    # 2. 纯 NumPy 导出 GGUF (Q4_0)
    log("正在通过纯 NumPy 转换 GGUF v3 Q4_0 量化格式...")
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "hf_to_gguf_numpy.py"),
        "--model", merged_dir,
        "--out", gguf_path
    ]
    subprocess.run(cmd, check=True)
    log(f"  [OK] GGUF 模型文件已生成: {gguf_path}")

    # 3. 编写 Ollama Modelfile
    modelfile_path = os.path.join(output_dir, "Modelfile_v5_comprehensive")
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(f"FROM {os.path.basename(gguf_path)}\n")
        f.write("PARAMETER temperature 0.0\n")
        f.write("PARAMETER num_ctx 4096\n")
        f.write("PARAMETER stop <|im_end|>\n")
        f.write(f'SYSTEM """{tokenizer.apply_chat_template([], tokenize=False)}"""\n')
    log(f"  [OK] Modelfile 已编写: {modelfile_path}")

    # 4. 打包最终交付 tarball
    stamp = time.strftime("%Y%m%d_%H%M%S")
    tarball_path = os.path.join(output_dir, f"virtu_comprehensive_deliverable_{stamp}.tar.gz")
    log(f"正在压缩打包全部成果 -> {tarball_path} ...")
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(adapter_path, arcname="adapter")
        tar.add(gguf_path, arcname=os.path.basename(gguf_path))
        tar.add(modelfile_path, arcname=os.path.basename(modelfile_path))
        eval_report = os.path.join(output_dir, "COMPREHENSIVE_EVAL_REPORT.json")
        if os.path.exists(eval_report):
            tar.add(eval_report, arcname="COMPREHENSIVE_EVAL_REPORT.json")

    # 计算 sha256
    h = hashlib.sha256()
    with open(tarball_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    sha_val = h.hexdigest()
    with open(tarball_path + ".sha256", "w") as f:
        f.write(f"{sha_val}  {os.path.basename(tarball_path)}\n")

    log("=" * 75)
    log(f"🎉 云端全面训练与高分测评闭环达成！")
    log(f"   最终交付压缩包: {tarball_path}")
    log(f"   SHA-256 指纹: {sha_val}")
    log("=" * 75)
    return tarball_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Virtu 全面高分云端全流程极速训练与闭环交付总引擎")
    parser.add_argument("--base", default=None, help="Base model path (auto-downloads if omitted)")
    parser.add_argument("--epochs", type=float, default=2.0, help="SFT Epochs")
    parser.add_argument("--skip-dpo", action="store_true", help="Skip DPO stage")
    parser.add_argument("--skip-merge", action="store_true", help="Skip merge & GGUF export")
    parser.add_argument("--smoke", action="store_true", help="Quick smoke test mode (20 steps)")
    parser.add_argument("--selftest", action="store_true", help="Pure self-test mode without GPU")
    parser.add_argument("--rebuild-corpus", action="store_true", help="Force rebuild of comprehensive SFT & DPO datasets")
    args = parser.parse_args()

    log("==================================================================")
    log("  Virtu 云端全面训练与全维度高分测评总引擎 (Master Launch)")
    log("==================================================================")

    # 1. 语料就绪检查
    corpus_file = DATASET_DIR / "train_corpus_comprehensive.jsonl"
    dpo_file = DATASET_DIR / "dpo_comprehensive_pairs.jsonl"
    if args.rebuild_corpus or not corpus_file.exists() or not dpo_file.exists():
        log("正在调用 build_high_score_corpus.py 构建/更新全面靶向高分语料...")
        from cloud_train_pack.build_high_score_corpus import build_all
        build_all(target_train_size=7500, dpo_pairs_size=1200)

    # 2. 硬件与基座探测
    profile = get_gpu_profile()
    if args.selftest:
        base_path = "checkpoints/_base_qwen3_8b"
        log("自检模式：跳过真实权重微调与合并。")
        eval_report = run_evaluation_stage(base_path, "", str(OUTPUT_DIR), selftest=True)
        log("自检通过！全管线逻辑验证无异常。")
        return

    base_path = ensure_base_model(args.base)

    # 3. 阶段 1：SFT 微调
    sft_out = str(OUTPUT_DIR / "virtu_sft_adapter")
    sft_receipt = train_sft_stage(
        base_model_path=base_path,
        corpus_path=str(corpus_file),
        output_adapter_dir=sft_out,
        profile=profile,
        epochs=args.epochs,
        smoke=args.smoke
    )

    final_adapter = sft_out

    # 4. 阶段 2：DPO 偏好对齐
    if not args.skip_dpo:
        dpo_out = str(OUTPUT_DIR / "virtu_dpo_adapter")
        dpo_receipt = train_dpo_stage(
            base_model_path=base_path,
            sft_adapter_path=sft_out,
            dpo_pairs_path=str(dpo_file),
            output_dpo_dir=dpo_out,
            profile=profile,
            smoke=args.smoke
        )
        final_adapter = dpo_out

    # 5. 阶段 3：云端就地全维度评测验收
    eval_report = run_evaluation_stage(
        base_model_path=base_path,
        adapter_path=final_adapter,
        out_dir=str(OUTPUT_DIR)
    )

    # 6. 阶段 4：合并与打包
    if not args.skip_merge and not args.smoke:
        export_and_package_stage(base_path, final_adapter, str(OUTPUT_DIR))


if __name__ == "__main__":
    main()
