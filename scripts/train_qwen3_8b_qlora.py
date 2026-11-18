#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""train_qwen3_8b_qlora.py — 单卡 QLoRA 微调（Virtu CAD/CAM 边界强化）

设计目标：云端零值守上线即开训。
  * 手写 Qwen3 消息序列化，正确处理 system/user/assistant/tool 四类角色，
    以及 OpenAI 格式的 tool_calls（不再依赖 apply_chat_template，避免下载 tokenizer 才能验证）。
  * 仅对 assistant 段（含其 tool_calls JSON）计算 loss；system/user/tool 段全 mask。
  * 4bit NF4 基座 + LoRA(r=32)，24G 单卡（4090/A10/L40S）即可。
  * --selftest 只加载 tokenizer + 数据，先验证格式/分词再开训。
  * 断点自动续训（output_dir 下最近的 checkpoint-*）。
  * 训练完保存 LoRA adapter（数十 MB）并写 training_receipt.json。
  * 可选 --merge 把 LoRA 合并进 bf16 基座（需额外 ~16G 显存，建议本地做）。

用法：
  python scripts/train_qwen3_8b_qlora.py --selftest            # 上线上线先自检
  python scripts/train_qwen3_8b_qlora.py --base Qwen/Qwen3-8B \
      --data data/sft/virtu_capability_sft_v6.jsonl \
      --out checkpoints/cad_cam_boundary_lora \
      --lora_r 32 --lora_alpha 64 --lr 2e-4 --epochs 3 --bs 4 --accum 4
"""

import argparse
import json
import os
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datasets import Dataset

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
    """按 GPU 架构选择混合精度。

    V100/T4 等 Volta 架构(sm70)没有 bf16 Tensor Core，bf16=True 会直接报错，
    必须退回 fp16。Ampere 及以后(A100/4090/L40S)才用 bf16。
    """
    if not torch.cuda.is_available():
        return "fp16", torch.float16
    # 用算力版本判定更可靠：V100/T4 等 Volta(sm_70)虽被 is_bf16_supported 误报为 True，
    # 但没有 bf16 Tensor Core，bf16 训练既慢又有数值隐患，强制 fp16（fp16 TC 才快）。
    # Ampere 及以后(sm_80+, A100/4090/L40S)才用 bf16。
    major, _minor = torch.cuda.get_device_capability(0)
    if major >= 8:
        return "bf16", torch.bfloat16
    return "fp16", torch.float16


def serialize_message(m: dict, tokenizer) -> list:
    """把单条消息序列化为 Qwen3 的 <|im_start|>/<|im_end|> 文本并 tokenize。"""
    role = m.get("role", "user")
    if role == "assistant" and m.get("tool_calls"):
        parts = []
        if m.get("content"):
            parts.append(m["content"])
        for tc in m["tool_calls"]:
            fn = tc.get("function", {})
            parts.append(
                json.dumps(
                    {"name": fn.get("name"), "arguments": fn.get("arguments")},
                    ensure_ascii=False,
                )
            )
        body = "\n".join(parts)
        seg = f"<|im_start|>assistant\n{body}<|im_end|>\n"
    elif role == "tool":
        seg = f"<|im_start|>tool\n{m.get('content', '')}<|im_end|>\n"
    else:
        seg = f"<|im_start|>{role}\n{m.get('content', '')}<|im_end|>\n"
    return tokenizer.encode(seg, add_special_tokens=False)


def format_sample(item: dict, tokenizer, max_len: int):
    """构造 input_ids / labels；非 assistant 段 label=-100。无 assistant 返回 None。"""
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
        seg_ids = serialize_message(m, tokenizer)
        if m.get("role") == "assistant":
            has_assistant = True
            labels.extend(seg_ids)  # 算 loss
        else:
            labels.extend([-100] * len(seg_ids))
        input_ids.extend(seg_ids)

    if not has_assistant:
        return None
    if len(input_ids) > max_len:
        input_ids = input_ids[:max_len]
        labels = labels[:max_len]
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
        f"(dropped=单样本无 assistant 轮)"
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
    ap.add_argument("--max_len", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--val_ratio", type=float, default=0.05)
    ap.add_argument("--selftest", action="store_true", help="只校验数据与分词，不训练")
    ap.add_argument("--merge", action="store_true", help="训练后合并 LoRA 进 bf16 基座")
    ap.add_argument("--merge_out", default="checkpoints/virtu_sft_merged")
    ap.add_argument("--resume-adapter", default=None,
                    help="已有 LoRA adapter 目录，在其上继续微调（4bit 基座 + PeftModel.from_pretrained）")
    args = ap.parse_args()

    # Refuse to train on a corpus that contains the eval set verbatim: measured
    # 2026-11-05 that data/sft/virtu_evolution_v5.jsonl carries 157 such rows.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from virtu_eval.contamination_check import assert_no_leak
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "scripts"))
    from corpus_unit_audit import assert_units_clean
    assert_no_leak(args.data)
    assert_units_clean(args.data)

    set_seed(args.seed)
    os.makedirs(args.out, exist_ok=True)

    print("=" * 60)
    print("  Virtu QLoRA single-GPU fine-tuning")
    print(f"  base      = {args.base}")
    print(f"  data      = {args.data}")
    print(f"  out       = {args.out}")
    print(f"  lora      = r={args.lora_r} alpha={args.lora_alpha} drop={args.lora_dropout}")
    print(f"  hyper     = lr={args.lr} epochs={args.epochs} bs={args.bs} accum={args.accum}")
    print("=" * 60)

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if args.selftest:
        selftest(args, tokenizer)
        return

    # 1) 4bit 基座
    from transformers import BitsAndBytesConfig

    prec_name, prec_dtype = pick_precision()
    print(f"[1/5] Loading 4bit base model (mixed_precision={prec_name})...")
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

    # 2) LoRA
    if args.resume_adapter:
        print(f"[2/5] Resuming from existing adapter: {args.resume_adapter}")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.resume_adapter)
        model.print_trainable_parameters()
    else:
        print("[2/5] Injecting LoRA adapter...")
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

    # 3) 数据
    print("[3/5] Tokenizing dataset...")
    dataset = load_dataset(args.data, tokenizer, args.max_len)
    if args.val_ratio > 0:
        split = dataset.train_test_split(test_size=args.val_ratio, seed=args.seed)
        train_ds, val_ds = split["train"], split["test"]
        print(f"[Dataset] train={len(train_ds)} val={len(val_ds)}")
    else:
        train_ds, val_ds = dataset, None

    # 4) 训练参数
    print("[4/5] Configuring trainer...")
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
    if resume:
        print(f"[Resume] from {resume}")

    # 5) 开训
    print("\n=================== LAUNCHING TRAINING ===================")
    t0 = time.time()
    try:
        result = trainer.train(resume_from_checkpoint=resume)
        elapsed = time.time() - t0
        train_loss = result.training_loss
        print(f"=================== TRAINING DONE ({elapsed:.1f}s) ===================")
        print(f"global_step={trainer.state.global_step} loss={train_loss:.4f}")
    except Exception as e:  # noqa: BLE001
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
        print(f"[ERROR] training failed: {e}")
        sys.exit(1)

    # 6) 保存 adapter
    print(f"[Artifacts] saving LoRA adapter -> {args.out}")
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
    print(f"[SUCCESS] receipt -> {os.path.join(args.out, 'training_receipt.json')}")

    # 7) 可选合并（默认关，建议本地做以省云端显存）
    if args.merge:
        m_prec_name, m_prec_dtype = pick_precision()
        print(f"[Merge] merging LoRA into {m_prec_name} base (needs extra ~16GB VRAM)...")
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
        print(f"[Merge] merged bf16 -> {args.merge_out}")

    print("\n[ALL PIPELINES COMPLETE]")


if __name__ == "__main__":
    main()
