"""Training Script for Omni Autonomous Industrial Agent on NVIDIA L40S.

Capabilities reinforced:
1. Windows Desktop & MCP Computer Use (Mouse, keyboard, screen capture, CAD focus)
2. Unknown Blueprint Inverse Deduction & FeatureTree Planning
3. Self-Reflection & Iterative Industrial Code Optimization
4. Autonomous Skill Synthesis (Writing SKILL.md) & Long-Term Memory Evolution
5. Web Search & Documentation Retrieval Fallback
"""

import os
import sys
import json
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

BASE_MODEL_PATH = os.environ.get("BASE_MODEL_PATH", "/root/public-storage/model/Qwen/Qwen3-8B")
DATASET_PATH = os.environ.get(
    "DATASET_PATH",
    "/root/workspace/Virtu/damodel_cad_cam_tuning/dataset/omni_autonomous_industrial_agent_train.jsonl"
)
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR",
    "/root/workspace/Virtu/checkpoints/omni_autonomous_agent_lora"
)


def format_qwen3_tool_chat(messages, tools, tokenizer, max_length=4096):
    """Tokenize multi-turn conversation with strict loss masking."""
    tools_str = json.dumps(tools, ensure_ascii=False) if tools else ""

    input_ids = []
    labels = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if role == "system":
            text = f"<|im_start|>system\n{content}\n# Available Tools:\n{tools_str}<|im_end|>\n"
            t_ids = tokenizer.encode(text, add_special_tokens=False)
            input_ids.extend(t_ids)
            labels.extend([-100] * len(t_ids))

        elif role == "user":
            text = f"<|im_start|>user\n{content}<|im_end|>\n"
            t_ids = tokenizer.encode(text, add_special_tokens=False)
            input_ids.extend(t_ids)
            labels.extend([-100] * len(t_ids))

        elif role == "tool":
            tool_id = msg.get("tool_call_id", "")
            name = msg.get("name", "")
            text = f"<|im_start|>tool name={name} id={tool_id}\n{content}<|im_end|>\n"
            t_ids = tokenizer.encode(text, add_special_tokens=False)
            input_ids.extend(t_ids)
            # NEVER compute loss on tool/environment observations!
            labels.extend([-100] * len(t_ids))

        elif role == "assistant":
            prefix = "<|im_start|>assistant\n"
            p_ids = tokenizer.encode(prefix, add_special_tokens=False)
            input_ids.extend(p_ids)
            labels.extend([-100] * len(p_ids))

            asst_body = ""
            if content:
                asst_body += content
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = fn.get("arguments", "{}")
                    call_id = tc.get("id", "")
                    asst_body += f"\n<tool_call id=\"{call_id}\">\n{{\"name\": \"{fn_name}\", \"arguments\": {fn_args}}}\n</tool_call>"

            asst_body += "<|im_end|>\n"
            b_ids = tokenizer.encode(asst_body, add_special_tokens=False)
            input_ids.extend(b_ids)
            # Assistant content and tool calls MUST compute loss!
            labels.extend(b_ids)

    if len(input_ids) > max_length:
        input_ids = input_ids[:max_length]
        labels = labels[:max_length]

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids)
    }


def load_dataset(data_path, tokenizer, max_length=4096):
    print(f"[DATA] Loading dataset from: {data_path}")
    raw_records = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw_records.append(json.loads(line))

    print(f"[DATA] Total raw trajectory records: {len(raw_records)}")
    formatted = []
    for item in raw_records:
        tools = item.get("tools", [])
        msgs = item.get("messages", [])
        ex = format_qwen3_tool_chat(msgs, tools, tokenizer, max_length)
        if len(ex["input_ids"]) > 10:
            formatted.append(ex)

    print(f"[DATA] Formatted {len(formatted)} valid training examples.")
    return Dataset.from_list(formatted)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None"
    print("==================================================================")
    print("  Virtu: Training Omni Autonomous Industrial Agent")
    print(f"  Device: {device} | GPU: {gpu_name}")
    print("==================================================================")

    # 1. Tokenizer
    print(f"[1/5] Loading Tokenizer from {BASE_MODEL_PATH} ...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Dataset
    print(f"[2/5] Preparing Omni Agent Dataset ...")
    train_dataset = load_dataset(DATASET_PATH, tokenizer)

    # 3. Model
    print(f"[3/5] Loading Base Model in bfloat16: {BASE_MODEL_PATH} ...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.enable_input_require_grads()

    # 4. LoRA Setup (r=32, alpha=64 on all attention + MLP projection layers)
    print(f"[4/5] Injecting High-Capacity LoRA (r=32, alpha=64) ...")
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 5. Training Engine
    # 280 samples / effective batch size 8 = 35 steps per epoch. 2 epochs = 70 steps.
    print(f"[5/5] Configuring Training Engine ...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=1.2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=10,
        weight_decay=0.01,
        num_train_epochs=2,
        logging_steps=5,
        save_strategy="steps",
        save_steps=35,
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
        train_dataset=train_dataset,
        data_collator=data_collator,
    )

    print("\n================== LAUNCHING OMNI AGENT TRAINING ==================")
    t_start = time.time()
    train_result = trainer.train()
    t_elapsed = time.time() - t_start
    print(f"================== TRAINING FINISHED ({t_elapsed:.1f}s) ==================")
    print(train_result)

    # Save final LoRA Adapter
    print(f"\n[Artifacts] Saving final LoRA Adapter to: {OUTPUT_DIR}")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    receipt = {
        "status": "COMPLETED",
        "task": "Omni Autonomous Industrial Agent Full-Capability Fine-Tuning",
        "global_step": trainer.state.global_step,
        "train_loss": train_result.training_loss,
        "runtime_seconds": t_elapsed,
        "gpu": gpu_name,
        "adapter_dir": OUTPUT_DIR,
        "num_samples": len(train_dataset),
        "capabilities": [
            "Desktop & MCP Computer Use (Mouse, Keyboard, Screen Capture)",
            "Unknown Blueprint Inverse Deduction & FeatureTree Planning",
            "Self-Reflection & Iterative Industrial Code Optimization",
            "Autonomous Skill Synthesis (Writing SKILL.md)",
            "Episodic Long-Term Memory Evolution",
            "Web Technical Documentation Scraping"
        ]
    }
    receipt_path = os.path.join(OUTPUT_DIR, "training_receipt.json")
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Training receipt generated at: {receipt_path}")


if __name__ == "__main__":
    main()
