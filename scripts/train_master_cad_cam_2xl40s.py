"""Full Master Fine-Tuning Script for Qwen3-8B on 2 x NVIDIA L40S.

Reinforcing:
1. SOLIDWORKS 2021 (Parametric Equations, VBA API, FeatureTree, Simulation CAE)
2. Siemens NX 12.0 (NXOpen Python, ExpressionCollection, Multiaxis CAM, Mold Wizard)
3. AutoCAD 2026 (AutoLISP with layer discipline, GD&T, and Parametric Constraints)
4. Vericut 9.6 (Kinematic machine simulation, OptiPath/Force, Auto-Diff)
5. CIMCO Edit 2026 (FANUC Macro B parametric NC code, variable logic)
6. 斯沃数控仿真 SSCNC (FANUC 0i-TF & G54 WCS Setup, Tool Quadrants T1-T9)
7. Multi-turn CAD/CAM/CAE tool calling & Assembly FeatureTree automation
"""

import json
import os
import sys
import time

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

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
TRAIN_DATA_PATH = "/root/workspace/Virtu/damodel_cad_cam_tuning/dataset/master_cad_cam_six_software_train.jsonl"
OUTPUT_DIR = "/root/workspace/Virtu/checkpoints/cad_cam_six_software_lora_training"
FINAL_ADAPTER_DIR = "/root/workspace/Virtu/checkpoints/cad_cam_six_software_lora"


def format_sample(item, tokenizer, max_length=2048):
    """Format single sample into input_ids, labels, and attention_mask with exact assistant masking."""
    system_default = (
        "你是一个资深的工业级 CAD/CAM/CNC 智能体与参数化建模专家，精通 SOLIDWORKS、Siemens NX、AutoCAD、Vericut、CIMCO Edit 以及斯沃数控仿真软件的底层脚本开发、方程式驱动建模与高精数控代码编程。"
    )

    if "messages" in item:
        messages = item["messages"]
    else:
        inst = item.get("instruction", "")
        inp = item.get("input", "")
        out = item.get("output", "")
        user_content = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst
        messages = [
            {"role": "system", "content": system_default},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": out},
        ]

    input_ids = []
    labels = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        prefix = f"<|im_start|>{role}\n"
        suffix = "<|im_end|>\n"
        
        prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
        content_ids = tokenizer.encode(content, add_special_tokens=False)
        suffix_ids = tokenizer.encode(suffix, add_special_tokens=False)

        turn_ids = prefix_ids + content_ids + suffix_ids
        input_ids.extend(turn_ids)

        if role == "assistant":
            # Mask prefix with -100, calculate loss on content + suffix
            labels.extend([-100] * len(prefix_ids) + content_ids + suffix_ids)
        else:
            # Mask entire non-assistant turn with -100
            labels.extend([-100] * len(turn_ids))

    if len(input_ids) > max_length:
        input_ids = input_ids[:max_length]
        labels = labels[:max_length]

    attention_mask = [1] * len(input_ids)

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": attention_mask,
    }


def load_master_dataset(data_path, tokenizer, max_length=2048):
    print(f"[Dataset] Loading Master SFT training data from: {data_path}")
    samples = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"[Dataset] Loaded {len(samples)} diverse multi-software samples.")

    formatted_data = []
    for s in samples:
        formatted_data.append(format_sample(s, tokenizer, max_length=max_length))

    return Dataset.from_list(formatted_data)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FINAL_ADAPTER_DIR, exist_ok=True)

    gpu_count = torch.cuda.device_count()
    device_names = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
    print("==================================================================")
    print("  Virtu: Master CAD/CAM/CAE Training on 2 x NVIDIA L40S")
    print(f"  Available GPUs ({gpu_count}): {device_names}")
    print("==================================================================")

    # 1. Load Tokenizer
    print("[1/5] Loading AutoTokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Load Model in bfloat16
    print(f"[2/5] Loading Base Model from {BASE_MODEL_PATH} (BF16, dedicated GPU placement) ...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
        trust_remote_code=True,
    )
    model.enable_input_require_grads()

    # 3. LoRA Configuration (Rank 32, Alpha 64 for deep expressive capacity)
    print("[3/5] Injecting LoRA Adapter (r=32, alpha=64)...")
    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 4. Prepare Dataset
    print("[4/5] Tokenizing and formatting Master Dataset...")
    dataset = load_master_dataset(TRAIN_DATA_PATH, tokenizer, max_length=2048)

    # 5. Training Arguments
    # With 2 x 46GB L40S, per_device_train_batch_size=2, grad_accum=2 -> effective batch=8
    # 1632 samples / 8 = 204 steps per epoch. 2 epochs = 408 steps.
    print("[5/5] Configuring Training Engine and Optimizer...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=1.2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=20,
        weight_decay=0.01,
        num_train_epochs=2,
        logging_steps=10,
        save_steps=100,
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

    print("\n================== LAUNCHING MASTER TRAINING ON 2xL40S ==================")
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
        "task": "Master CAD/CAM/CAE 6-Software Comprehensive Fine-Tuning",
        "global_step": trainer.state.global_step,
        "train_loss": train_result.training_loss,
        "runtime_seconds": t_elapsed,
        "gpus": device_names,
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
    receipt_path = os.path.join(FINAL_ADAPTER_DIR, "training_receipt.json")
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Training receipt generated at: {receipt_path}")

    # 7. Automatically launch Blind-Test Benchmark Suite
    print("\n[Evaluation] Automatically launching Blind-Test Benchmark Suite...")
    import subprocess
    cmd = ["python3", "/root/workspace/Virtu/scripts/run_blind_test_evaluator.py"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("[Eval Stderr]:", res.stderr)
    print("\n[ALL PIPELINES COMPLETE - READY FOR DOWNLOAD]")


if __name__ == "__main__":
    main()
