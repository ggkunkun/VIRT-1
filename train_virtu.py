#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_virtu.py — Virtu 模型统一微调脚本（基于 Qwen3-8B 基座）

这是"做出真 Virtu 模型"的训练环节。它把 damodel_cad_cam_tuning/dataset/ 下
所有 ShareGPT 格式 SFT 数据 ({"messages":[...]}) 喂给 Qwen3-8B，产出 LoRA 适配器。

三种精度档（按你手上的 GPU 选）:
  --mode qlora : 4-bit 量化 + LoRA，单卡 ~24GB（RTX 4090 / 3090 / A10）即可
  --mode lora  : bf16 + LoRA，单卡 48GB（L40S / A100）推荐
  --mode full  : 全参微调，需多卡 + 大显存（~8×A100），一般不推荐

基座(base)说明:
  - 现有 LoRA 的基底是 Qwen3-8B（peft 0.21.2, r=32, alpha=64），base 必须同源，
    否则 peft 加载维度不匹配。
  - 本地无权重时设 --base 为 HF / ModelScope 仓库 id（如 Qwen/Qwen3-8B-Instruct），
    脚本会自动下载（需联网；国内优先 ModelScope）。

运行环境:
  - 需要在 有 torch + GPU + transformers + peft + datasets + (qlora 时)bitsandbytes 的机器执行。
  - 本机(Windows 无 torch / 无 GPU)无法执行，请放到远程 L40S 或本地 GPU 机器跑。

示例:
  python train_virtu.py --base /root/public-storage/model/Qwen/Qwen3-8B --mode qlora
  python train_virtu.py --base Qwen/Qwen3-8B-Instruct --mode lora --epochs 3
  python train_virtu.py --base /root/.../Qwen3-8B --mode qlora --data /path/to/extra_sft
"""

import os
import sys
import json
import glob

# ---- 必须在 import torch 之前处理单卡/GPU 选择 ----
def _pre_argv():
    for i, a in enumerate(sys.argv):
        if a == "--single-gpu":
            os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
        elif a == "--gpu-id" and i + 1 < len(sys.argv):
            os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[i + 1]
_pre_argv()

import argparse

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)


# LoRA 目标模块，与现有 Virtu LoRA 保持一致（Qwen3 全线性层）
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]


def load_and_tokenize(data_dir, tokenizer, max_length=2048):
    print(f"[data] 扫描 SFT 数据目录: {data_dir}")
    files = sorted(glob.glob(os.path.join(data_dir, "*.jsonl")))
    if not files:
        raise SystemExit(f"[data] 在 {data_dir} 未找到任何 *.jsonl")
    print(f"[data] 发现 {len(files)} 个 jsonl 文件")

    samples = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    print(f"[data] 合计 {len(samples)} 条样本")

    formatted = []
    for item in samples:
        if "messages" in item and item["messages"]:
            msgs = item["messages"]
            sys_msg = next((m["content"] for m in msgs if m["role"] == "system"),
                           "你是 Virtu 工业级 CAD/CAM/CAE 与数控编程专家，也能像人一样自然交流。")
            user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
            asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
        elif "instruction" in item:
            inst = item.get("instruction", "")
            inp = item.get("input", "")
            asst_msg = item.get("output", "")
            sys_msg = "你是 Virtu 工业级 CAD/CAM/CNC 智能体与参数化建模专家。"
            user_msg = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst
        else:
            continue

        if not user_msg or not asst_msg:
            continue

        # Qwen3 ChatML 格式
        prompt = (
            f"<|im_start|>system\n{sys_msg}<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        full_text = prompt + asst_msg + "<|im_end|>"

        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        full_ids = tokenizer.encode(full_text, add_special_tokens=False)

        if len(full_ids) > max_length:
            full_ids = full_ids[:max_length]
            prompt_ids = prompt_ids[:max_length]

        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
        if len(labels) > max_length:
            labels = labels[:max_length]

        formatted.append({
            "input_ids": full_ids,
            "labels": labels,
            "attention_mask": [1] * len(full_ids),
        })

    print(f"[data] 可用样本 {len(formatted)} 条")
    return Dataset.from_list(formatted)


def build_model(base, mode, r, alpha, lora_dropout, trust_remote):
    print(f"[model] 加载基座: {base}  (mode={mode})")
    if mode == "qlora":
        from transformers import BitsAndBytesConfig
        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            base, quantization_config=quant,
            device_map="auto", trust_remote_code=trust_remote,
        )
        # 4-bit 下需要先做 kbit 准备
        try:
            from peft import prepare_model_for_kbit_training
            model = prepare_model_for_kbit_training(model)
        except Exception as e:
            print(f"[model] prepare_model_for_kbit_training 跳过: {e}")
        lora_config = LoraConfig(
            r=r, lora_alpha=alpha, lora_dropout=lora_dropout,
            target_modules=TARGET_MODULES, bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_config)
    elif mode == "lora":
        model = AutoModelForCausalLM.from_pretrained(
            base, torch_dtype=torch.bfloat16,
            device_map="auto", trust_remote_code=trust_remote,
        )
        model.enable_input_require_grads()
        lora_config = LoraConfig(
            r=r, lora_alpha=alpha, lora_dropout=lora_dropout,
            target_modules=TARGET_MODULES, bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_config)
    elif mode == "full":
        model = AutoModelForCausalLM.from_pretrained(
            base, torch_dtype=torch.bfloat16,
            device_map="auto", trust_remote_code=trust_remote,
        )
    else:
        raise SystemExit(f"[model] 未知 mode: {mode}")
    model.print_trainable_parameters()
    return model


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="Virtu 模型统一微调（Qwen3-8B + LoRA）")
    p.add_argument("--base", required=True, help="Qwen3-8B 基座目录或仓库 id")
    p.add_argument("--data", default=os.path.join(here, "damodel_cad_cam_tuning", "dataset"),
                   help="SFT 数据目录（含 *.jsonl，ShareGPT messages 格式）")
    p.add_argument("--mode", default="qlora", choices=["qlora", "lora", "full"])
    p.add_argument("--output", default=os.path.join(here, "checkpoints", "virtu_lora_trained"))
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--max-len", type=int, default=2048)
    p.add_argument("--r", type=int, default=32, help="LoRA rank（与现有 LoRA 对齐用 32）")
    p.add_argument("--alpha", type=int, default=64)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--resume", default=None, help="从某 checkpoint 续训")
    p.add_argument("--trust-remote-code", action="store_true")
    p.add_argument("--single-gpu", action="store_true",
                   help="单卡训练：自动设 CUDA_VISIBLE_DEVICES=0（须在 import torch 前，此处仅文档；真正生效见文件顶部 _pre_argv）")
    p.add_argument("--gpu-id", default=None, help="指定使用的 GPU 序号，如 0 / 1（覆盖默认）")
    args = p.parse_args()

    os.makedirs(args.output, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[init] device={device} gpu={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=args.trust_remote_code)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dataset = load_and_tokenize(args.data, tokenizer, max_length=args.max_len)

    model = build_model(args.base, args.mode, args.r, args.alpha,
                        args.lora_dropout, args.trust_remote_code)

    training_args = TrainingArguments(
        output_dir=args.output,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=15,
        num_train_epochs=args.epochs,
        logging_steps=10,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=2,
        bf16=True,
        gradient_checkpointing=True,
        report_to="none",
        dataloader_num_workers=2,
        resume_from_checkpoint=args.resume,
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True,
    )

    trainer = Trainer(
        model=model, args=training_args,
        train_dataset=dataset, data_collator=data_collator,
    )

    print("\n================ STARTING VIRTU TRAINING ================")
    result = trainer.train(resume_from_checkpoint=args.resume)
    print("================ TRAINING COMPLETE ================")
    print(result)

    adapter_dir = os.path.join(args.output, "virtu_lora_final")
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    with open(os.path.join(adapter_dir, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump({
            "status": "COMPLETED",
            "base_model": args.base,
            "mode": args.mode,
            "global_step": trainer.state.global_step,
            "train_loss": result.training_loss,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
            "epochs": args.epochs,
            "lora_r": args.r,
            "lora_alpha": args.alpha,
            "num_samples": len(dataset),
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] LoRA 已保存到: {adapter_dir}")
    print(f"[NEXT] 合并为单一模型: python merge_lora.py --base {args.base} "
          f"--conv-lora {adapter_dir} --cad-lora checkpoints/cad_cam_six_software_lora")


if __name__ == "__main__":
    main()
