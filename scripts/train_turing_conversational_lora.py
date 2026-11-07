# -*- coding: utf-8 -*-
"""
Turing Test Conversational Model LoRA Fine-Tuning Script.
Trains Qwen3-8B to speak like a genuine, warm, witty, high-EQ human partner.
Completely removes all AI boilerplate, robot templates, bullet-point lists, and formal disclaimers.
Target: Passing the Turing Test under blind evaluation and third-party LLM scrutiny.
"""

import os
import sys
import json
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
DATA_PATH = "/root/workspace/Virtu/turing_conversational/data/turing_master_train.jsonl"
OUTPUT_DIR = "/root/workspace/Virtu/checkpoints/turing_conversational_lora"

def main():
    print("=" * 70)
    print("  LAUNCHING TURING TEST CONVERSATIONAL MODEL TRAINING")
    print("  Goal: Genuine Human Authenticity, High EQ & Zero AI Clichés")
    print("=" * 70)

    # 1. Device check
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[DEVICE] Available: {device} | Count: {torch.cuda.device_count()}")
    if device == "cuda":
        for i in range(torch.cuda.device_count()):
            print(f"  GPU {i}: {torch.cuda.get_device_name(i)} | VRAM: {torch.cuda.get_device_properties(i).total_memory / (1024**3):.1f} GB")

    # 2. Tokenizer
    print(f"\n[1/5] Loading Tokenizer from: {BASE_MODEL_PATH} ...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    print(f"[TOKENIZER] Vocab size: {len(tokenizer):,}")

    # 3. Base Model
    print(f"\n[2/5] Loading Qwen3-8B Base Model in bfloat16 ...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.enable_input_require_grads()

    # 4. LoRA Setup
    print("\n[3/5] Configuring LoRA Adapter (r=32, alpha=64) ...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 5. Load & Tokenize Turing Dataset
    print(f"\n[4/5] Loading and formatting Turing Master Dataset from: {DATA_PATH} ...")
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Training dataset not found: {DATA_PATH}")

    raw_data = []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw_data.append(json.loads(line))
    print(f"[DATASET] Loaded {len(raw_data)} high-quality human conversational dialogues.")

    def preprocess_conversations(batch):
        input_ids_list = []
        labels_list = []
        attention_mask_list = []

        for msgs in batch["messages"]:
            # Format using Jinja chat template
            full_prompt = tokenizer.apply_chat_template(msgs, tokenize=False)
            tokenized = tokenizer(full_prompt, max_length=2048, truncation=True)
            
            input_ids = tokenized["input_ids"]
            attention_mask = tokenized["attention_mask"]
            labels = list(input_ids)

            # Mask out user input tokens in labels so loss is only calculated on assistant turns
            # In Qwen template, assistant turn starts after <|im_start|>assistant\n
            im_start_id = tokenizer.convert_tokens_to_ids("<|im_start|>")
            im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
            
            i = 0
            while i < len(labels):
                if labels[i] == im_start_id:
                    # Check next tokens
                    header = tokenizer.decode(labels[i:i+4])
                    if "assistant" in header:
                        # Find end of header line
                        j = i + 1
                        while j < len(labels) and labels[j] != 198: # \n token in Qwen
                            labels[j] = -100
                            j += 1
                        if j < len(labels):
                            labels[j] = -100 # mask newline as well
                            j += 1
                        # From j until im_end_id is assistant generation -> keep labels!
                        while j < len(labels) and labels[j] != im_end_id:
                            j += 1
                        i = j
                    else:
                        # User or system turn: mask everything until im_end_id
                        j = i
                        while j < len(labels) and labels[j] != im_end_id:
                            labels[j] = -100
                            j += 1
                        if j < len(labels):
                            labels[j] = -100 # mask im_end_id
                        i = j + 1
                else:
                    labels[i] = -100
                    i += 1

            input_ids_list.append(input_ids)
            labels_list.append(labels)
            attention_mask_list.append(attention_mask)

        return {
            "input_ids": input_ids_list,
            "labels": labels_list,
            "attention_mask": attention_mask_list,
        }

    dataset = Dataset.from_list(raw_data)
    tokenized_dataset = dataset.map(
        preprocess_conversations,
        batched=True,
        batch_size=128,
        remove_columns=dataset.column_names,
    )
    print(f"[DATASET] Tokenized {len(tokenized_dataset)} samples successfully.")

    # 6. Training Arguments
    print("\n[5/5] Configuring Trainer ...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Calculate optimal steps
    # batch_size=4, grad_accum=4 -> effective batch size 16
    steps_per_epoch = max(10, len(tokenized_dataset) // 16)
    total_steps = steps_per_epoch * 3 # 3 epochs
    print(f"[TRAINER] Steps per epoch: {steps_per_epoch} | Total planned steps: {total_steps}")

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=1.5e-4,
        warmup_steps=45,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="steps",
        save_steps=steps_per_epoch,
        save_total_limit=2,
        num_train_epochs=3,
        bf16=True,
        dataloader_num_workers=4,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True),
    )

    print("\n" + "=" * 70)
    print("  STARTING TURING MODEL FINE-TUNING")
    print("=" * 70)
    start_time = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start_time

    print(f"\n[COMPLETE] Training finished in {elapsed:.1f}s.")
    print(f"[METRICS] Final Training Loss: {train_result.training_loss:.4f}")

    # Save final model
    print(f"[SAVE] Saving fine-tuned LoRA weights and tokenizer to: {OUTPUT_DIR} ...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    # Save training receipt
    receipt = {
        "status": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_model": BASE_MODEL_PATH,
        "training_loss": train_result.training_loss,
        "epochs": 3,
        "total_samples": len(raw_data),
        "target": "Turing Test Conversational Model (De-AI-fied, High-EQ, Grounded)",
        "output_dir": OUTPUT_DIR,
    }
    with open(os.path.join(OUTPUT_DIR, "turing_training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] All files and receipt saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
