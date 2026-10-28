"""Fine-Tuning Script for Qwen3-8B on NVIDIA L40S (48GB VRAM).

Reinforces:
1. SOLIDWORKS 2021 (Parametric Equations, Macros, Simulation CAE, Plastics, Motion)
2. Siemens NX 12.0 (NXOpen Python, ExpressionCollection, Multiaxis CAM, Nastran)
3. AutoCAD 2026 (AutoLISP with layer discipline, GD&T, and Parametric Constraints)
4. Vericut 9.6 (Kinematic machine simulation, OptiPath/Force, Auto-Diff)
5. CIMCO Edit 2026 (FANUC Macro B parametric NC code, variable logic)
6. 斯沃数控仿真 SSCNC (FANUC 0i-TF & G54 WCS Setup, Tool Quadrants T1-T9)
7. Wish-Style Intent-to-Parametric CAD/CAM/CAE Blind-Testing Engine
"""

import json
import os
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

BASE_MODEL_PATH = "/root/public-storage/model/Qwen/Qwen3-8B"
DATASET_PATH = "/root/cad_cam_finetune/comprehensive_wish_cad_cam_sft_1200.jsonl"
OUTPUT_DIR = "/root/cad_cam_finetune/output_checkpoints"


def load_dataset(data_path, tokenizer, max_length=2048):
    print(f"Loading SFT data from: {data_path}")
    samples = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} instruction samples.")

    formatted_data = []
    for item in samples:
        if "messages" in item:
            msgs = item["messages"]
            sys_msg = next((m["content"] for m in msgs if m["role"] == "system"), "你是一个资深的工业级 CAD/CAM/CAE 智能体与参数化建模专家。")
            user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
            asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
        else:
            inst = item.get("instruction", "")
            inp = item.get("input", "")
            asst_msg = item.get("output", "")
            sys_msg = "你是一个资深的工业级 CAD/CAM/CNC 智能体与参数化建模专家，精通 SOLIDWORKS、Siemens NX、AutoCAD、Vericut、CIMCO Edit 以及斯沃数控仿真软件的底层脚本开发、方程式驱动建模与高精数控代码编程。"
            user_msg = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst

        # Apply Qwen ChatML formatting
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

        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
        if len(labels) > max_length:
            labels = labels[:max_length]

        formatted_data.append({
            "input_ids": full_ids,
            "labels": labels,
            "attention_mask": [1] * len(full_ids),
        })

    return Dataset.from_list(formatted_data)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")

    # 1. Load Tokenizer
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Load Model in bfloat16
    print(f"Loading Base Model from {BASE_MODEL_PATH} ...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.enable_input_require_grads()

    # 3. Configure LoRA for 48GB L40S
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 4. Prepare Dataset
    dataset = load_dataset(DATASET_PATH, tokenizer)

    # 5. Training Arguments (Optimized for L40S throughput)
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=1e-4,
        weight_decay=0.01,
        warmup_steps=15,
        num_train_epochs=2,
        logging_steps=10,
        save_steps=50,
        save_total_limit=2,
        bf16=True,
        gradient_checkpointing=True,
        report_to="none",
        dataloader_num_workers=2,
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer,
        pad_to_multiple_of=8,
        return_tensors="pt",
        padding=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
    )

    print("\n================ STARTING COMPREHENSIVE TRAINING ON NVIDIA L40S ================")
    train_result = trainer.train()
    print("================ TRAINING COMPLETE ================")
    print(train_result)

    # 6. Save final LoRA Adapter
    final_adapter_dir = os.path.join(OUTPUT_DIR, "cad_cam_six_software_lora_final")
    model.save_pretrained(final_adapter_dir)
    tokenizer.save_pretrained(final_adapter_dir)
    print(f"\n[SUCCESS] Final LoRA Adapter saved to: {final_adapter_dir}")

    # Write training log receipt
    with open(os.path.join(final_adapter_dir, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump({
            "status": "COMPLETED",
            "global_step": trainer.state.global_step,
            "train_loss": train_result.training_loss,
            "gpu": torch.cuda.get_device_name(0),
            "adapter_dir": final_adapter_dir,
            "num_samples": len(dataset),
            "software_enhanced": [
                "SOLIDWORKS 2021",
                "Siemens NX 12.0",
                "AutoCAD 2026",
                "Vericut 9.6",
                "CIMCO Edit 2026",
                "斯沃数控仿真软件 (SSCNC)"
            ]
        }, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
