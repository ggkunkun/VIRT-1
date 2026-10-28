"""Fine-Tuning Script for Qwen3-8B on NVIDIA L40S (48GB VRAM).

Focuses on:
1. SOLIDWORKS 2021 (Parametric Equations & Macros)
2. Siemens NX 12.0 (NXOpen Python & Revolve Modeling)
3. AutoCAD 2026 (AutoLISP & 2D Engineering Drawings)
4. Vericut 9.6 (Simulation Setup & Tool Libraries)
5. CIMCO Edit 2026 (Macro B G-code & Backplot)
6. 斯沃数控仿真软件 (FANUC 0i-TF & G54 WCS Setup)
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
DATASET_PATH = "/root/cad_cam_finetune/six_software_parametric_sft.jsonl"
OUTPUT_DIR = "/root/cad_cam_finetune/output_checkpoints"


def load_dataset(data_path, tokenizer, max_length=2048):
    print(f"Loading SFT data from: {data_path}")
    samples = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} instruction samples.")

    formatted_data = []
    for item in samples:
        inst = item["instruction"]
        inp = item.get("input", "")
        out = item["output"]

        user_content = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst
        
        # Apply Qwen ChatML formatting
        prompt = (
            f"<|im_start|>system\n"
            f"你是一个资深的工业级 CAD/CAM/CNC 智能体与参数化建模专家，精通 SOLIDWORKS、Siemens NX、AutoCAD、Vericut、CIMCO Edit 以及斯沃数控仿真软件的底层脚本开发、方程式驱动建模与高精数控代码编程。<|im_end|>\n"
            f"<|im_start|>user\n"
            f"{user_content}<|im_end|>\n"
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

    # 5. Training Arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=1e-4,
        weight_decay=0.01,
        warmup_steps=10,
        num_train_epochs=3,
        logging_steps=5,
        save_steps=25,
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

    print("\n================ STARTING TRAINING ON NVIDIA L40S ================")
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
