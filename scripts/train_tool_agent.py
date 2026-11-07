"""Qwen3-8B Industrial Tool-Calling Agent Fine-Tuning Script.

Optimized for NVIDIA L40S (48GB VRAM) / A800 (80GB VRAM) on DAMODEL.
Features:
1. Multi-turn OpenAI function-calling / tool_calls tokenization
2. Precise Loss Masking:
   - System prompt: masked (-100)
   - User instructions: masked (-100)
   - Assistant dialogue & tool_calls: TRAINED (valid token ids)
   - Tool execution returns (role='tool'): MASKED (-100, preventing hallucinations)
3. LoRA configuration targeting attention & MLP projection layers
4. Saves LoRA adapter, tokenizer, receipt, and tools schema.
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
DATASET_PATH = os.environ.get("DATASET_PATH", "/root/cad_cam_finetune/toolcall_full_cad_cam_agent_sft.jsonl")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/root/cad_cam_finetune/output_checkpoints/tool_agent_lora_final")
TOOLS_SCHEMA_PATH = os.environ.get("TOOLS_SCHEMA_PATH", "/root/cad_cam_finetune/industrial_agent_tools.json")


def format_qwen3_tool_chat(messages, tools, tokenizer, max_length=4096):
    """Render multi-turn messages and tools into token IDs and loss labels."""
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
            # NEVER compute loss on environment/tool returns!
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
            # Assistant content and tool_calls MUST compute loss!
            labels.extend(b_ids)

    if len(input_ids) > max_length:
        input_ids = input_ids[:max_length]
        labels = labels[:max_length]

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids)
    }


def load_toolcall_dataset(data_path, tokenizer, max_length=4096):
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


def train():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[HARDWARE] Device: {device} | Device Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")

    # 1. Tokenizer
    print(f"[TOKENIZER] Loading from {BASE_MODEL_PATH} ...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Dataset
    dataset = load_toolcall_dataset(DATASET_PATH, tokenizer)

    # 3. Model
    print(f"[MODEL] Loading Base Model in bfloat16: {BASE_MODEL_PATH} ...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.enable_input_require_grads()

    # 4. LoRA Config
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 5. Training Arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=1e-4,
        weight_decay=0.01,
        num_train_epochs=3,
        logging_steps=10,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=2,
        bf16=True,
        gradient_checkpointing=True,
        dataloader_pin_memory=True,
        warmup_steps=15,
        optim="adamw_torch",
        report_to="none",
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

    start_time = time.time()
    print("[TRAINING] Starting LoRA Training Loop ...")
    train_result = trainer.train()
    elapsed = time.time() - start_time

    print(f"[SUCCESS] Training completed in {elapsed:.2f} seconds ({elapsed/60:.2f} min).")

    # 6. Save Adapter & Artifacts
    print(f"[SAVE] Saving fine-tuned LoRA adapter to {OUTPUT_DIR} ...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    receipt = {
        "status": "completed",
        "base_model": BASE_MODEL_PATH,
        "dataset": DATASET_PATH,
        "num_samples": len(dataset),
        "runtime_seconds": elapsed,
        "train_loss": train_result.training_loss,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join(OUTPUT_DIR, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)

    # Copy tools schema into adapter dir for seamless inference deployment
    if os.path.exists(TOOLS_SCHEMA_PATH):
        import shutil
        shutil.copy(TOOLS_SCHEMA_PATH, os.path.join(OUTPUT_DIR, "industrial_agent_tools.json"))

    print(f"[RECEIPT] Receipt and tool schemas recorded in {OUTPUT_DIR}")


if __name__ == "__main__":
    train()
