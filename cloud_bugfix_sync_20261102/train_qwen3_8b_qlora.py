#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""train_qwen3_8b_qlora.py — 单卡 QLoRA 微调（Virtu CAD/CAM 边界强化 · 已修复版）

修复项：
  1. serialize_message: 自动解析字符串格式的 tool_calls.function.arguments，防止 json.dumps 双重转义，
     并包裹标准 <tool_call>...</tool_call> 标签。
  2. format_sample: 对 assistant 轮的 `<|im_start|>assistant\n` 头部 token 进行 label=-100 mask，
     仅对回复正文与 `<|im_end|>\n` 计算 loss。
  3. 截断后样本守卫: 当 `len(input_ids) > max_len` 截断导致有效 loss token 数为 0 (`all(x == -100)`) 时，
     自动丢弃该样本，防止 CrossEntropyLoss(ignore_index=-100) 产生 NaN 梯度。
"""

import argparse
import json
import os
import sys
import time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
    set_seed,
)

SYS_DEFAULT = (
    "你是 Virtu 工业智能体。需要产出可执行代码时，必须通过工具调用完成。"
    "缺关键量时拒绝并指出缺失项；危险/越权请求必须拒绝且不给可执行步骤。"
)


def pick_precision():
    """按 GPU 架构选择混合精度（Volta sm70 退回 fp16，Ampere+ 用 bf16）。"""
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return "bf16", torch.bfloat16
    return "fp16", torch.float16


def serialize_message(m: dict, tokenizer):
    """把单条消息序列化为 (prefix_ids, body_ids)，支持对 assistant 头部精确 mask。"""
    role = m.get("role", "user")
    prefix = f"<|im_start|>{role}\n"
    if role == "assistant" and m.get("tool_calls"):
        parts = []
        if m.get("content"):
            parts.append(str(m["content"]))
        for tc in m["tool_calls"]:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except Exception:
                    parsed_args = raw_args
            else:
                parsed_args = raw_args
            tc_json = json.dumps(
                {"name": fn.get("name"), "arguments": parsed_args},
                ensure_ascii=False,
            )
            parts.append(f"<tool_call>\n{tc_json}\n</tool_call>")
        body = "\n".join(parts) + "<|im_end|>\n"
    else:
        body = f"{m.get('content', '')}<|im_end|>\n"

    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    body_ids = tokenizer.encode(body, add_special_tokens=False)
    return prefix_ids, body_ids


def format_sample(item: dict, tokenizer, max_len: int):
    """构造 input_ids / labels；非 assistant 正文段全部 mask 为 -100。"""
    messages = item.get("messages")
    if not messages:
        inst = item.get("instruction", "")
        inp = item.get("input", "")
        out = item.get("output", "")
        uc = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst
        messages = [
            {"role": "system", "content": SYS_DEFAULT},
            {"role": "user", "content": uc},
            {"role": "assistant", "content": out},
        ]

    input_ids = []
    labels = []
    has_assistant = False
    for m in messages:
        prefix_ids, body_ids = serialize_message(m, tokenizer)
        input_ids.extend(prefix_ids)
        input_ids.extend(body_ids)
        if m.get("role") == "assistant":
            has_assistant = True
            labels.extend([-100] * len(prefix_ids))
            labels.extend(body_ids)
        else:
            labels.extend([-100] * (len(prefix_ids) + len(body_ids)))

    if not has_assistant:
        return None
    if len(input_ids) > max_len:
        input_ids = input_ids[:max_len]
        labels = labels[:max_len]
    # Guard against NaN loss when truncation removes all supervised assistant tokens
    if not any(x != -100 for x in labels):
        return None
    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }


def load_dataset(path: str, tokenizer, max_len: int) -> "Dataset":
    from datasets import Dataset

    print(f"[Dataset] reading {path}")
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    out = []
    dropped = 0
    for it in items:
        s = format_sample(it, tokenizer, max_len)
        if s is None:
            dropped += 1
            continue
        out.append(s)
    print(
        f"[Dataset] raw={len(items)} usable={len(out)} dropped={dropped} "
        f"(dropped=无有效监督 token 或超长截断)"
    )
    return Dataset.from_list(out)


def selftest(args, tokenizer):
    print("=================== SELFTEST ===================")
    samples = []
    with open(args.data, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 5:
                break
            if line.strip():
                samples.append(json.loads(line))
    for i, s in enumerate(samples):
        msgs = s.get("messages", [])
        fs = format_sample(s, tokenizer, args.max_len)
        if fs is None:
            print(f"  sample[{i}] skipped (no loss tokens within max_len={args.max_len})")
            continue
        n_loss = sum(1 for x in fs["labels"] if x != -100)
        print(
            f"  sample[{i}] roles={[m['role'] for m in msgs]} "
            f"tokens={len(fs['input_ids'])} loss_tokens={n_loss}"
        )
    print(f"  tokenizer vocab_size={tokenizer.vocab_size}")
    print("=================== SELFTEST OK ===================")


def find_latest_checkpoint(out_dir: str):
    if not os.path.isdir(out_dir):
        return None
    ckpts = [d for d in os.listdir(out_dir) if d.startswith("checkpoint-")]
    if not ckpts:
        return None
    ckpts.sort(key=lambda x: int(x.split("-")[-1]))
    return os.path.join(out_dir, ckpts[-1])


def write_receipt(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser(description="Virtu Qwen3-8B single-GPU QLoRA")
    ap.add_argument("--base", default="Qwen/Qwen3-8B", help="本地路径或 HF 模型 id")
    ap.add_argument("--data", default="data/sft/virtu_capability_sft_v6.jsonl")
    ap.add_argument("--out", default="checkpoints/cad_cam_boundary_lora")
    ap.add_argument("--lora_r", type=int, default=32)
    ap.add_argument("--lora_alpha", type=int, default=64)
    ap.add_argument("--lora_dropout", type=float, default=0.05)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--bs", type=int, default=4)
    ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--max_len", type=int, default=3072)
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--val_ratio", type=float, default=0.05)
    ap.add_argument("--selftest", action="store_true", help="只校验数据与分词，不训练")
    ap.add_argument("--merge", action="store_true", help="训练后合并 LoRA 进 bf16 基座")
    ap.add_argument("--merge_out", default="checkpoints/virtu_sft_merged")
    args = ap.parse_args()

    set_seed(args.seed)
    os.makedirs(args.out, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if args.selftest:
        selftest(args, tokenizer)
        return

    from transformers import BitsAndBytesConfig

    prec_name, prec_dtype = pick_precision()
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=prec_dtype,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base,
        torch_dtype=prec_dtype,
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = load_dataset(args.data, tokenizer, args.max_len)
    if args.val_ratio > 0:
        split = dataset.train_test_split(test_size=args.val_ratio, seed=args.seed)
        train_ds, val_ds = split["train"], split["test"]
    else:
        train_ds, val_ds = dataset, None

    training_args = TrainingArguments(
        output_dir=args.out,
        per_device_train_batch_size=args.bs,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.01,
        num_train_epochs=args.epochs,
        logging_steps=10,
        save_strategy="steps",
        save_steps=300,
        save_total_limit=2,
        bf16=(prec_name == "bf16"),
        fp16=(prec_name == "fp16"),
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        report_to="none",
        dataloader_num_workers=2,
        seed=args.seed,
        logging_dir=os.path.join(args.out, "logs"),
    )
    data_collator = DataCollatorForSeq2Seq(
        tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=data_collator,
    )

    resume = find_latest_checkpoint(args.out)
    t0 = time.time()
    try:
        result = trainer.train(resume_from_checkpoint=resume)
        elapsed = time.time() - t0
        train_loss = result.training_loss
    except Exception as e:
        elapsed = time.time() - t0
        write_receipt(
            os.path.join(args.out, "training_receipt.json"),
            {
                "status": "FAILED",
                "error": repr(e),
                "runtime_seconds": elapsed,
                "base": args.base,
                "data": args.data,
            },
        )
        sys.exit(1)

    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)

    device_names = [
        torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())
    ]
    receipt = {
        "status": "COMPLETED",
        "task": "Virtu CAD/CAM boundary reinforcement (QLoRA)",
        "base": args.base,
        "data": args.data,
        "num_samples": len(dataset),
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "learning_rate": args.lr,
        "epochs": args.epochs,
        "global_step": trainer.state.global_step,
        "train_loss": train_loss,
        "runtime_seconds": elapsed,
        "gpus": device_names,
        "adapter_dir": os.path.abspath(args.out),
    }
    write_receipt(os.path.join(args.out, "training_receipt.json"), receipt)

    if args.merge:
        m_prec_name, m_prec_dtype = pick_precision()
        from peft import PeftModel

        base_model = AutoModelForCausalLM.from_pretrained(
            args.base, torch_dtype=m_prec_dtype, device_map="auto",
            trust_remote_code=True,
        )
        merged = PeftModel.from_pretrained(base_model, args.out)
        merged = merged.merge_and_unload()
        os.makedirs(args.merge_out, exist_ok=True)
        merged.save_pretrained(args.merge_out)
        tokenizer.save_pretrained(args.merge_out)


if __name__ == "__main__":
    main()
