"""Industrial-Grade Fine-Tuning Script for Qwen3-8B on NVIDIA L40S (Wish-Style Parametric Modeling)."""

import json
import os
import sys
import time
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
TRAIN_DATA_PATH = "/root/workspace/Virtu/damodel_cad_cam_tuning/dataset/wish_parametric_train.jsonl"
OUTPUT_DIR = "/root/workspace/Virtu/checkpoints/cad_cam_six_software_lora_training"
FINAL_ADAPTER_DIR = "/root/workspace/Virtu/checkpoints/cad_cam_six_software_lora"


def load_wish_dataset(data_path, tokenizer, max_length=1280):
    print(f"[Dataset] Loading Wish-Parametric SFT data from: {data_path}")
    samples = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"[Dataset] Loaded {len(samples)} diverse instruction samples.")

    formatted_data = []
    system_prompt = (
        "你是一位工业级顶级 CAD/CAM/CNC 专家与智能制造算法工程师，精通 SOLIDWORKS 2021 (VBA API / 全局变量方程式)、"
        "Siemens NX 12.0 (NXOpen Python / 参数化表达式)、AutoCAD 2026 (AutoLISP / 国标工程图)、Vericut 9.6 (数控切削仿真 / 刀库配置 / 过切干涉容差)、"
        "CIMCO Edit 2026 (Macro B 参数化宏程序 / Backplot 背绘校验) 以及 斯沃数控仿真软件 (SSCNC / FANUC 0i-TF 工件坐标系 G54 对刀 / 刀尖方位代号 T / 刀尖圆角 R 防过切补偿)。"
        "对于用户的许愿式或高层设计意图，你能一键输出 100% 语法严谨、可直接运行、全参数化解耦绑定的工业级脚本、宏代码与操作手册。"
    )

    for item in samples:
        inst = item["instruction"]
        inp = item.get("input", "")
        out = item["output"]

        user_content = f"{inst}\n【背景与规格】: {inp}" if inp else inst

        # Qwen ChatML standard format
        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{user_content}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        full_text = prompt + out + "<|im_end|>"

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
    os.makedirs(FINAL_ADAPTER_DIR, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None"
    print("==================================================================")
    print("  Virtu: Comprehensive Wish-Parametric Training on NVIDIA L40S")
    print(f"  Device: {device} | GPU: {gpu_name}")
    print("==================================================================")

    # 1. Tokenizer
    print("[1/5] Loading AutoTokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Base Model in BF16
    print(f"[2/5] Loading Base Model from {BASE_MODEL_PATH} ...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.enable_input_require_grads()

    # 3. LoRA Configuration
    print("[3/5] Injecting Parameter-Efficient LoRA Adapter...")
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
    print("[4/5] Preprocessing and Tokenizing Training Data...")
    dataset = load_wish_dataset(TRAIN_DATA_PATH, tokenizer)

    # 5. Training Arguments
    print("[5/5] Configuring Training Engine and Optimizer...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=1.5e-4,
        lr_scheduler_type="cosine",
        warmup_steps=20,
        weight_decay=0.01,
        max_steps=200,
        logging_steps=5,
        save_steps=50,
        save_total_limit=2,
        bf16=True,
        gradient_checkpointing=True,
        report_to="none",
        dataloader_num_workers=4,
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

    print("\n================== LAUNCHING INTENSIVE TRAINING ==================")
    t_start = time.time()
    train_result = trainer.train()
    t_elapsed = time.time() - t_start
    print(f"================== TRAINING FINISHED ({t_elapsed:.1f}s) ==================")
    print(train_result)

    # 6. Save final LoRA Adapter
    print(f"\n[Artifacts] Saving final LoRA Adapter to: {FINAL_ADAPTER_DIR}")
    model.save_pretrained(FINAL_ADAPTER_DIR)
    tokenizer.save_pretrained(FINAL_ADAPTER_DIR)

    receipt = {
        "status": "COMPLETED",
        "task": "Wish-Style Parametric Modeling SFT",
        "global_step": trainer.state.global_step,
        "train_loss": train_result.training_loss,
        "runtime_seconds": t_elapsed,
        "gpu": gpu_name,
        "adapter_dir": FINAL_ADAPTER_DIR,
        "num_samples": len(dataset),
        "target_software": [
            "SOLIDWORKS 2021",
            "Siemens NX 12.0",
            "AutoCAD 2026",
            "Vericut 9.6",
            "CIMCO Edit 2026",
            "斯沃数控仿真软件 (SSCNC)"
        ]
    }
    with open(os.path.join(FINAL_ADAPTER_DIR, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Training receipt generated at: {os.path.join(FINAL_ADAPTER_DIR, 'training_receipt.json')}")

    # 7. Automatically trigger Blind Test benchmark
    print("\n[Evaluation] Automatically launching Blind-Test Benchmark Suite...")
    import subprocess
    cmd = ["python3", "scripts/run_blind_test_evaluator.py"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("[Eval Stderr]:", res.stderr)
    print("\n[ALL PIPELINES COMPLETE - READY FOR DOWNLOAD]")


if __name__ == "__main__":
    main()
