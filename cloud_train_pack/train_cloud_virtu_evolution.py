#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/train_cloud_virtu_evolution.py — Virtu 全面进化版云端全流程极速训练与闭环交付总引擎

设计目标：云端（AutoDL / 丹摩 Damodel / 恒源云 / RunPod / 阿里云等）一键极速自举训练、对齐与交付。

核心改进（针对 2026-11-05 真实测评 RCFA 与《测量宪法》要求）：
1. 语料全面升级：
   - 融合 6,099 条强化训练集（基础全流程 + 5x 物理/推导弱项靶向强化 + 5x 多语言代码防御性规训）；
   - 前置防污染审查门禁（virtu_eval.contamination_check），确保与 240 道评测题 0 hard leak；
2. 严苛 Loss 掩码纪律：
   - 基于 scripts/virtu_tokenize.py 字符级 offset-mapping，仅 assistant 输出与工具调用参计入梯度；
   - 严禁对 system、user 及工具返回结果计算 loss，杜绝伪造工具返回值；
3. 彻底修复 Ollama 原生工具调用模版缺陷：
   - 导出 Modelfile 时注入官方完整的 1723 字符工具调用 Chat Template（包含 .Tools 与 <tool_call> 分支）；
   - 彻底解决上一代模型遭遇 HTTP 400 "does not support tools" 的历史架构断裂；
4. 算力普适与显存优化：
   - 自动探测 GPU 架构：Volta (V100) 强制 fp16，Ampere/Ada/Hopper (3090/4090/L40S/A100/H100) 开启 bf16；
   - 4-bit NF4 双重量化 + LoRA (r=32 / alpha=64)，gradient_checkpointing 锁定 use_reentrant=False；
5. DPO 偏好对齐阶段：
   - 针对假阳性 CAD 审计、VBA 宏幻觉、切削负质量、漏除圆周率分母、C 空指针段错误等 850 对偏好对进行直接偏好优化；
   - 利用 PEFT disable_adapter 实现 0 显存额外开销复用基座作为 Reference Model；
6. 闭环交付与测量合规：
   - 标准 merge_and_unload Delta 权重合并（绝无暴力破坏性相加）；
   - 纯 NumPy 导出 GGUF (Q4_0) 量化格式，输出带 SHA-256 账本的交付压缩包。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = ROOT / "cloud_train_pack"
DATASET_DIR = PACK_DIR / "dataset"
OUTPUT_DIR = PACK_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

try:
    import bitsandbytes.backends.cuda.ops as bnb_ops
    bnb_ops._gemm_4bit_use_custom_fn = lambda *args, **kwargs: True
except Exception:
    pass


def log(msg: str) -> None:
    t_str = time.strftime("%H:%M:%S")
    print(f"[{t_str}] {msg}", flush=True)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# 官方标准 1723 字符 Qwen3/Qwen2.5 工具调用 Chat Template
OFFICIAL_QWEN_TOOL_TEMPLATE = """{{- $lastUserIdx := -1 -}}
{{- range $idx, $msg := .Messages -}}
{{- if eq $msg.Role "user" }}{{ $lastUserIdx = $idx }}{{ end -}}
{{- end }}
{{- if or .System .Tools }}<|im_start|>system
{{ if .System }}
{{ .System }}
{{- end }}
{{- if .Tools }}

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{{- range .Tools }}
{"type": "function", "function": {{ .Function }}}
{{- end }}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
{{- end -}}
<|im_end|>
{{ end }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}
{{- if and $.IsThinkSet (eq $i $lastUserIdx) }}
   {{- if $.Think -}}
      {{- " "}}/think
   {{- else -}}
      {{- " "}}/no_think
   {{- end -}}
{{- end }}<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ if (and $.IsThinkSet (and .Thinking (or $last (gt $i $lastUserIdx)))) -}}
<think>{{ .Thinking }}</think>
{{ end -}}
{{ if .Content }}{{ .Content }}
{{- else if .ToolCalls }}<tool_call>
{{ range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}
{{ end }}</tool_call>
{{- end }}{{ if not $last }}<|im_end|>
{{ end }}
{{- else if eq .Role "tool" }}<|im_start|>user
<tool_response>
{{ .Content }}
</tool_response><|im_end|>
{{ end }}
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
{{ if and $.IsThinkSet (not $.Think) -}}
<think>

</think>

{{ end -}}
{{ end }}
{{- end }}"""


def detect_gpu_hardware() -> Dict[str, Any]:
    """自适应探测硬件环境，输出最优超参数配置字典。"""
    try:
        import torch
        if not torch.cuda.is_available():
            log("[WARN] 未检测到可用的 CUDA 设备，将以 CPU 自检模式运行！")
            return {
                "name": "CPU", "precision": "fp32", "torch_dtype": "float32",
                "batch_size": 1, "accum": 4, "max_len": 512, "attn": None,
                "lora_r": 16, "lora_alpha": 32, "target_modules": ["q_proj", "v_proj"]
            }
        name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        free_bytes, _ = torch.cuda.mem_get_info(0)
        free_gb = free_bytes / (1024 ** 3)
        major, minor = torch.cuda.get_device_capability(0)
    except Exception as e:
        log(f"[WARN] 探测 GPU 异常: {e}，使用保底配置")
        name, vram_gb, free_gb, major, minor = "Unknown", 16.0, 16.0, 8, 0

    log(f"硬件自检: GPU={name}, 总显存={vram_gb:.1f} GB (空闲={free_gb:.1f} GB), 架构 sm_{major}{minor}")

    # sm_70 (Tesla V100 / T4) 无原生 bf16 Tensor Core，强制使用 fp16
    if major < 8 or "v100" in name.lower():
        profile = {
            "name": name, "precision": "fp16", "torch_dtype": "float16",
            "batch_size": 1, "accum": 16, "max_len": 2048, "attn": "sdpa",
            "lora_r": 32, "lora_alpha": 64,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        }
    elif free_gb < 15.0:  # 显存受限实例 (RTX 4070 / 16G 显存)
        profile = {
            "name": name, "precision": "bf16", "torch_dtype": "bfloat16",
            "batch_size": 1, "accum": 16, "max_len": 1536, "attn": "sdpa",
            "lora_r": 16, "lora_alpha": 32,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"]
        }
    elif vram_gb >= 40.0:  # A100 / L40S / H100 (48G-80G 大显存)
        profile = {
            "name": name, "precision": "bf16", "torch_dtype": "bfloat16",
            "batch_size": 4, "accum": 4, "max_len": 3072, "attn": "sdpa",
            "lora_r": 32, "lora_alpha": 64,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        }
    else:  # RTX 3090 / 4090 (24G 甜点显卡，安全稳定基线 BS=2, Accum=8)
        profile = {
            "name": name, "precision": "bf16", "torch_dtype": "bfloat16",
            "batch_size": 2, "accum": 8, "max_len": 2048, "attn": "sdpa",
            "lora_r": 32, "lora_alpha": 64,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        }

    log(f"  -> Profile 选定: 精度={profile['precision']}, BS={profile['batch_size']}, Accum={profile['accum']}, MaxLen={profile['max_len']}")
    return profile


def resolve_base_model(specified: Optional[str] = None) -> str:
    """定位或自动下载 Qwen3-8B 工业基座模型。"""
    search_paths = [
        specified,
        str(ROOT / "checkpoints" / "_base_qwen3_8b"),
        "/root/public-storage/model/Qwen/Qwen3-8B",
        "/root/models/Qwen3-8B",
        "/root/autodl-tmp/models/Qwen3-8B",
        "/mnt/models/Qwen3-8B",
        "Qwen/Qwen3-8B"
    ]
    for p in search_paths:
        if p and os.path.exists(p) and os.path.exists(os.path.join(p, "config.json")):
            log(f"基座模型已定位: {p}")
            return p

    # 云端未找到预置模型时，通过 ModelScope 国内极速通道下载
    target_dir = str(ROOT / "checkpoints" / "_base_qwen3_8b")
    log(f"本地未发现基座，正在通过 ModelScope 下载 Qwen/Qwen3-8B 至: {target_dir} ...")
    os.makedirs(target_dir, exist_ok=True)
    try:
        from modelscope import snapshot_download
        downloaded = snapshot_download("Qwen/Qwen3-8B", local_dir=target_dir)
        log(f"基座下载完成: {downloaded}")
        return downloaded
    except Exception as e:
        log(f"ModelScope 下载失败: {e}，尝试使用 Hugging Face 镜像通道...")
        try:
            from huggingface_hub import snapshot_download
            downloaded = snapshot_download(
                "Qwen/Qwen3-8B",
                local_dir=target_dir,
                endpoint="https://hf-mirror.com"
            )
            return downloaded
        except Exception as e2:
            raise RuntimeError(f"基座下载彻底失败: {e2}。请在云端上传 Qwen3-8B 或通过 --base 指定路径。") from e2


def ensure_datasets(force_rebuild: bool = False) -> Tuple[str, str]:
    """确保进化版训练集与 DPO 偏好对就绪并完成防污染审计。"""
    sft_path = DATASET_DIR / "train_corpus_evolution_v6.jsonl"
    dpo_path = DATASET_DIR / "dpo_evolution_pairs_v6.jsonl"

    if force_rebuild or not sft_path.exists() or not dpo_path.exists():
        log("训练集不存在或触发强制构建，启动 build_evolution_corpus.py ...")
        from cloud_train_pack.build_evolution_corpus import build_unified_corpus
        build_unified_corpus(
            output_sft_path=sft_path,
            output_dpo_path=dpo_path,
            upsample_weak=5
        )
    else:
        log(f"发现已就绪进化版 SFT 训练集: {sft_path.name} (大小: {sft_path.stat().st_size / (1024**2):.1f} MB)")
        log(f"发现已就绪进化版 DPO 偏好对: {dpo_path.name}")

    # 二次防污染校验
    from virtu_eval.contamination_check import scan_corpus
    audit = scan_corpus(str(sft_path))
    if audit.get("hard_leaks", 0) > 0 or audit.get("blocking", 0) > 0:
        raise RuntimeError(f"训练集未通过防污染审查: {audit}")
    log(f"  [OK] 数据集防污染门禁验证通过: hard_leaks=0, blocking=0")
    return str(sft_path), str(dpo_path)


def run_sft_training(
    base_model_path: str,
    sft_data_path: str,
    output_adapter_dir: str,
    profile: Dict[str, Any],
    epochs: float = 2.0,
    lr: float = 1.5e-4,
    smoke: bool = False
) -> Dict[str, Any]:
    """阶段 1: 严格遵循 assistant-only 掩码的 QLoRA SFT 训练。"""
    log("=" * 70)
    log("  阶段 1/4: 执行全工程能力与防御性规训 QLoRA SFT 微调")
    log("=" * 70)

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer,
        DataCollatorForSeq2Seq, BitsAndBytesConfig
    )
    from scripts.virtu_tokenize import build_example

    t0 = time.perf_counter()

    # 1. 载入分词器
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. 4-bit 量化基座载入
    compute_dtype = torch.float16 if profile["precision"] == "fp16" else torch.bfloat16
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True
    )

    log(f"载入基座模型 (精度={profile['precision']})...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        quantization_config=bnb_config,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=compute_dtype,
        trust_remote_code=True,
        attn_implementation=profile["attn"]
    )
    model.config.use_cache = False
    for p in model.parameters():
        p.requires_grad = False
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

    # 3. 注入统一 LoRA 适配器
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=profile.get("lora_r", 32),
        lora_alpha=profile.get("lora_alpha", 64),
        lora_dropout=0.05,
        target_modules=profile.get("target_modules"),
        bias="none"
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 4. 语料分词与掩码 (严守 virtu_tokenize 纪律)
    log(f"正在进行字符级精确掩码分词: {sft_data_path} ...")
    raw_lines = []
    with open(sft_data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_lines.append(json.loads(line))

    if smoke:
        raw_lines = raw_lines[:25]
        log(f"  [SMOKE 模式] 截取前 {len(raw_lines)} 条样本极速验证")

    tokenized_rows = []
    max_len = profile["max_len"]
    dropped = 0
    for sample in raw_lines:
        msgs = sample.get("messages", [])
        tools = sample.get("tools", [])
        try:
            ids, labels, _ = build_example(msgs, tools, tokenizer, max_length=max_len)
            tokenized_rows.append({"input_ids": ids, "labels": labels})
        except Exception:
            dropped += 1

    log(f"分词完成: 有效参与训练样本={len(tokenized_rows)} 条 (格式异常跳过={dropped})")
    train_dataset = Dataset.from_list(tokenized_rows)

    # 5. Trainer 设定与启动
    os.makedirs(output_adapter_dir, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=output_adapter_dir,
        num_train_epochs=epochs if not smoke else 1.0,
        max_steps=12 if smoke else -1,
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
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none"
    )

    collator = DataCollatorForSeq2Seq(
        tokenizer,
        pad_to_multiple_of=8,
        return_tensors="pt",
        padding=True
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=collator
    )

    log("开始执行 QLoRA 梯度下降微调...")
    train_res = trainer.train()

    # 6. 保存适配器与分词器
    model.save_pretrained(output_adapter_dir)
    tokenizer.save_pretrained(output_adapter_dir)

    receipt = {
        "status": "COMPLETED",
        "stage": "SFT",
        "epochs": epochs,
        "runtime_seconds": round(time.perf_counter() - t0, 2),
        "final_loss": train_res.training_loss,
        "train_samples": len(tokenized_rows)
    }
    with open(os.path.join(output_adapter_dir, "sft_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    del trainer
    del model
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    log(f"  [OK] SFT 阶段微调圆满结束！耗时={receipt['runtime_seconds']}s, Final Loss={train_res.training_loss:.4f}")
    return receipt


def run_dpo_training(
    base_model_path: str,
    sft_adapter_path: str,
    dpo_data_path: str,
    output_dpo_dir: str,
    profile: Dict[str, Any],
    epochs: float = 1.0,
    lr: float = 5e-5,
    beta: float = 0.1,
    smoke: bool = False
) -> Dict[str, Any]:
    """阶段 2: DPO 反幻觉与防御性对齐微调 (零额外显存占用)。"""
    log("=" * 70)
    log("  阶段 2/4: 执行 DPO 偏好对齐 (反幻觉、反假阳性、代码防御性)")
    log("=" * 70)

    import torch
    from datasets import Dataset
    from peft import PeftModel, set_peft_model_state_dict
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import DPOTrainer, DPOConfig

    t0 = time.perf_counter()

    # 1. 载入分词器
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    compute_dtype = torch.float16 if profile["precision"] == "fp16" else torch.bfloat16
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True
    )

    log("载入基座并绑定已训练的 SFT LoRA 适配器...")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        quantization_config=bnb_config,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=compute_dtype,
        trust_remote_code=True,
        attn_implementation=profile["attn"]
    )
    base_model.config.use_cache = False
    model = PeftModel.from_pretrained(base_model, sft_adapter_path, is_trainable=True)

    # 2. 格式化 DPO 数据对
    pairs = []
    with open(dpo_data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                pairs.append(json.loads(line))

    if smoke:
        pairs = pairs[:10]
        log(f"  [SMOKE 模式] 截取前 {len(pairs)} 对偏好样本极速验证")

    formatted_dpo = []
    for p in pairs:
        prompt_msgs = p.get("prompt", [])
        prompt_str = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
        formatted_dpo.append({
            "prompt": prompt_str,
            "chosen": p["chosen"],
            "rejected": p["rejected"]
        })

    dpo_dataset = Dataset.from_list(formatted_dpo)
    log(f"DPO 数据对准备就绪: 共 {len(dpo_dataset)} 对")

    # 3. DPO 训练器配置
    os.makedirs(output_dpo_dir, exist_ok=True)
    dpo_args = DPOConfig(
        output_dir=output_dpo_dir,
        num_train_epochs=epochs if not smoke else 1.0,
        max_steps=6 if smoke else -1,
        per_device_train_batch_size=profile["batch_size"],
        gradient_accumulation_steps=profile["accum"],
        learning_rate=lr,
        lr_scheduler_type="cosine",
        warmup_steps=5,
        beta=beta,
        max_length=min(profile["max_len"], 2048),
        logging_steps=5 if not smoke else 1,
        save_strategy="no",
        fp16=(profile["precision"] == "fp16"),
        bf16=(profile["precision"] == "bf16"),
        gradient_checkpointing=True,
        report_to="none"
    )

    dpo_trainer = DPOTrainer(
        model=model,
        ref_model=None,  # 内部通过 peft.disable_adapter 实现，0 额外显存
        args=dpo_args,
        train_dataset=dpo_dataset,
        processing_class=tokenizer
    )

    log("开始执行 DPO 偏好对齐优化...")
    train_res = dpo_trainer.train()

    model.save_pretrained(output_dpo_dir)
    tokenizer.save_pretrained(output_dpo_dir)

    receipt = {
        "status": "COMPLETED",
        "stage": "DPO",
        "beta": beta,
        "runtime_seconds": round(time.perf_counter() - t0, 2),
        "final_loss": train_res.training_loss
    }
    with open(os.path.join(output_dpo_dir, "dpo_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    del dpo_trainer
    del model
    del base_model
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    log(f"  [OK] DPO 对齐阶段圆满结束！耗时={receipt['runtime_seconds']}s, Final Loss={train_res.training_loss:.4f}")
    return receipt


def run_insitu_evaluation(
    base_model_path: str,
    adapter_path: str,
    output_dir: str,
    selftest: bool = False
) -> Dict[str, Any]:
    """阶段 3: 原地运行全维度确定性评测并生成合规验收报告。"""
    log("=" * 70)
    log("  阶段 3/4: 云端原地全维度评测验收 (In-Situ Evaluation)")
    log("=" * 70)
    from cloud_train_pack.eval_in_situ import run_evaluation

    report = run_evaluation(
        model_path=base_model_path,
        adapter_path=adapter_path,
        out_dir=output_dir,
        selftest=selftest
    )
    return report


def merge_export_and_package(
    base_model_path: str,
    adapter_path: str,
    output_dir: str,
    keep_merged: bool = False
) -> str:
    """阶段 4: 标准 Delta 权重合并、GGUF 导出与带官方模版的 Modelfile 编写。"""
    log("=" * 70)
    log("  阶段 4/4: 权重 Delta 合并、GGUF 量化与原生工具模版封装")
    log("=" * 70)

    merged_dir = os.path.join(output_dir, "virtu_evolution_merged")
    gguf_path = os.path.join(output_dir, "virtu-evolution-q4_0.gguf")

    # 1. 权重合并 (标准 PEFT merge_and_unload，绝不走破坏性的直接累加)
    log("正在执行 LoRA -> Base 标准 Delta 权重合并...")
    import gc
    import torch
    import shutil
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="cpu",
        trust_remote_code=True
    )
    model = PeftModel.from_pretrained(base, adapter_path)
    merged = model.merge_and_unload()
    merged.save_pretrained(merged_dir)
    tokenizer.save_pretrained(merged_dir)
    del base, model, merged
    gc.collect()
    log(f"  [OK] 合并权重已保存至: {merged_dir}")

    # 2. 导出 GGUF (Q4_0)
    log("正在通过纯 NumPy 转换 GGUF v3 Q4_0 量化模型...")
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "hf_to_gguf_numpy.py"),
        "--model", merged_dir,
        "--out", gguf_path
    ]
    subprocess.run(cmd, check=True)
    log(f"  [OK] GGUF 量化模型已生成: {gguf_path}")

    # 3. 编写注入官方 1723 字符工具调用模版的 Ollama Modelfile
    modelfile_path = os.path.join(output_dir, "Modelfile_virtu_evolution")
    log("正在生成注入官方原生工具调用模版的 Modelfile...")
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(f"FROM {os.path.basename(gguf_path)}\n")
        f.write("PARAMETER temperature 0.0\n")
        f.write("PARAMETER num_ctx 8192\n")
        f.write("PARAMETER stop <|im_start|>\n")
        f.write("PARAMETER stop <|im_end|>\n")
        f.write(f'TEMPLATE """\n{OFFICIAL_QWEN_TOOL_TEMPLATE}\n"""\n')
        f.write('SYSTEM """你是 Virtu 工业制造多智能体大模型。在执行 CAD 建模、有限元分析、数控切削与工程代码任务时，严格遵守物理定律守恒与防御性编程原则。"""\n')
    log(f"  [OK] Modelfile 封装完成: {modelfile_path}")

    # 4. 生成轻量交付压缩包与 SHA-256 账本 (包含 Adapter + 评测报告 + 验证证据 + Modelfile)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    tarball_path = os.path.join(output_dir, f"virtu_evolution_deliverable_{stamp}.tar.gz")
    log(f"正在打包最终成果物 (Adapter+报告+Modelfile) -> {tarball_path} ...")
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(adapter_path, arcname="adapter")
        tar.add(modelfile_path, arcname=os.path.basename(modelfile_path))
        for extra in ["COMPREHENSIVE_EVAL_REPORT.json", "COMPREHENSIVE_EVAL_REPORT.md", "raw.jsonl"]:
            p = os.path.join(output_dir, extra)
            if os.path.exists(p):
                tar.add(p, arcname=extra)

    sha_val = sha256_file(tarball_path)
    with open(tarball_path + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{sha_val}  {os.path.basename(tarball_path)}\n")

    # 对独立 GGUF 生成专用 sha256 账本
    if os.path.exists(gguf_path):
        gguf_sha = sha256_file(gguf_path)
        with open(gguf_path + ".sha256", "w", encoding="utf-8") as f:
            f.write(f"{gguf_sha}  {os.path.basename(gguf_path)}\n")
        log(f"  [OK] GGUF 专属账本已生成: {gguf_path}.sha256 ({gguf_sha})")

    # 5. 磁盘防护：如未显式要求保留 16GB 合并中间态，自动清理以防磁盘溢出
    if not keep_merged and os.path.exists(merged_dir):
        log(f"正在释放 16GB 中间合并权重目录以释放云端磁盘: {merged_dir} ...")
        shutil.rmtree(merged_dir, ignore_errors=True)
        log("  -> [OK] 16GB 中间权重已释放，磁盘空间充裕！")

    log("=" * 70)
    log(f"🎉 Virtu 进化版云端训练与闭环交付全部达成！")
    log(f"   交付成果包: {tarball_path}")
    log(f"   SHA-256 校验和: {sha_val}")
    log("=" * 70)
    return tarball_path


def main():
    parser = argparse.ArgumentParser(description="Virtu 进化版云端全流程极速训练与闭环交付总引擎")
    parser.add_argument("--base", default=None, help="基座模型路径 (缺省时自动从 ModelScope 下载)")
    parser.add_argument("--epochs", type=float, default=2.0, help="SFT 微调轮数 (默认 2.0)")
    parser.add_argument("--dpo-epochs", type=float, default=1.0, help="DPO 对齐轮数 (默认 1.0)")
    parser.add_argument("--skip-dpo", action="store_true", help="跳过 DPO 对齐阶段")
    parser.add_argument("--skip-merge", action="store_true", help="跳过权重合并与 GGUF 导出")
    parser.add_argument("--smoke", action="store_true", help="冒烟模式 (以极少量样本验证全链路)")
    parser.add_argument("--selftest", action="store_true", help="纯 CPU 自检模式，验证导入与数据通道")
    parser.add_argument("--rebuild-corpus", action="store_true", help="强制重新合成最新防污染语料")
    parser.add_argument("--keep-merged", action="store_true", help="保留 16GB 的中间合并权重目录 (默认转 GGUF 后自动释放以防磁盘满)")
    args = parser.parse_args()

    log("=" * 75)
    log("  🚀 Virtu 工业大模型 · 云端全流程极速训练系统 (Evolution Master)")
    log("=" * 75)

    # 1. 硬件探测
    profile = detect_gpu_hardware()

    if args.selftest:
        log("[SELFTEST] 启动逻辑通道自检，跳过高算力训练...")
        sft_data, dpo_data = ensure_datasets(force_rebuild=False)
        log("自检通过: 数据通道正常，各依赖库与防污染门禁就绪！")
        return

    # 2. 定位基座模型
    base_model = resolve_base_model(args.base)

    # 3. 准备并验证防污染语料
    sft_data, dpo_data = ensure_datasets(force_rebuild=args.rebuild_corpus)

    # 4. SFT 阶段微调
    sft_adapter_dir = str(OUTPUT_DIR / "adapter_evolution_sft")
    sft_receipt = run_sft_training(
        base_model_path=base_model,
        sft_data_path=sft_data,
        output_adapter_dir=sft_adapter_dir,
        profile=profile,
        epochs=args.epochs,
        smoke=args.smoke
    )

    final_adapter_dir = sft_adapter_dir

    # 5. DPO 阶段对齐 (可选)
    if not args.skip_dpo:
        dpo_adapter_dir = str(OUTPUT_DIR / "adapter_evolution_dpo")
        dpo_receipt = run_dpo_training(
            base_model_path=base_model,
            sft_adapter_path=sft_adapter_dir,
            dpo_data_path=dpo_data,
            output_dpo_dir=dpo_adapter_dir,
            profile=profile,
            epochs=args.dpo_epochs,
            smoke=args.smoke
        )
        final_adapter_dir = dpo_adapter_dir

    # 6. 原地评测
    eval_report = run_insitu_evaluation(
        base_model_path=base_model,
        adapter_path=final_adapter_dir,
        output_dir=str(OUTPUT_DIR),
        selftest=args.smoke
    )

    # 7. 合并权重与导出交付包
    if not args.skip_merge:
        tarball = merge_export_and_package(
            base_model_path=base_model,
            adapter_path=final_adapter_dir,
            output_dir=str(OUTPUT_DIR),
            keep_merged=args.keep_merged
        )
    else:
        log("已跳过权重合并与导出步骤 (--skip-merge)。")

    log("🎉 全部云端训练与闭环验证流程执行完毕！")


if __name__ == "__main__":
    main()
