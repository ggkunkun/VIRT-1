# -*- coding: utf-8 -*-
"""本地 GPU 监督微调（SFT）—— 不依赖 trl / datasets，仅用 transformers+peft+bitsandbytes+torch。

目标（A3+B 合并落地）
--------------------
1. A3「简洁偏好」：把 dpo_concise_pairs.jsonl 的 chosen（简洁正确回答）作为 SFT 目标，
   把"精简且答对"直接烘焙进权重，比仅靠系统提示更鲁棒。
2. B「弱维度」：把 sft_weak_dims.jsonl（reasoning/generalization/hard 范例）作为 SFT 目标，
   针对性补强评测里 27%/40%/25% 的弱项。

基座
----
RTX 4050 6GB -> 4-bit QLoRA；基座用本地 HF 合并模型（默认 virtu_cad_cam_merged_v3，
即 comprehensive GGUF 的底层权重）。

用法
----
    .venv/Scripts/python train_sft_local.py \
        --base checkpoints/virtu_cad_cam_merged_v3 \
        --a3  cloud_train_pack/dataset/dpo_concise_pairs.jsonl \
        --b   cloud_train_pack/dataset/sft_weak_dims.jsonl \
        --out output/sft_disciplined_v1 --epochs 4 --lr 2e-5 --steps 400
"""
from __future__ import annotations

import os
import json
import argparse
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
from peft import (LoraConfig, get_peft_model, prepare_model_for_kbit_training,
                  TaskType)


TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]


def load_samples(a3_path, b_path):
    samples = []  # each: list of {role, content}
    # A3: prompt -> chosen 作为 SFT 目标
    if a3_path and os.path.exists(a3_path):
        with open(a3_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                p, c = d.get("prompt"), d.get("chosen")
                if p and c:
                    samples.append([
                        {"role": "user", "content": p},
                        {"role": "assistant", "content": c},
                    ])
    # B: 已是 messages 格式
    if b_path and os.path.exists(b_path):
        with open(b_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                msgs = d.get("messages")
                if msgs and len(msgs) >= 2:
                    samples.append(msgs)
    return samples


class SFTDataset(Dataset):
    def __init__(self, samples, tokenizer, max_length):
        self.tok = tokenizer
        self.max_length = max_length
        self.enc = []
        for msgs in samples:
            try:
                text = tokenizer.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=False)
            except Exception:
                # 退回纯文本拼接
                text = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
            ids = tokenizer(text, truncation=True,
                           max_length=max_length)["input_ids"]
            if len(ids) < 4:
                continue
            self.enc.append(torch.tensor(ids, dtype=torch.long))

    def __len__(self):
        return len(self.enc)

    def __getitem__(self, i):
        return self.enc[i]


def collate(batch):
    max_len = max(len(x) for x in batch)
    pad = 0  # pad token id (eos)
    ids, mask, labels = [], [], []
    for x in batch:
        n = len(x)
        ids.append(torch.cat([x, torch.full((max_len - n,), pad, dtype=torch.long)]))
        mask.append(torch.cat([torch.ones(n, dtype=torch.long),
                              torch.zeros(max_len - n, dtype=torch.long)]))
        labels.append(torch.cat([x, torch.full((max_len - n,), -100, dtype=torch.long)]))
    return (torch.stack(ids), torch.stack(mask), torch.stack(labels))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="checkpoints/virtu_cad_cam_merged_v3")
    ap.add_argument("--a3", default="cloud_train_pack/dataset/dpo_concise_pairs.jsonl")
    ap.add_argument("--b", default="cloud_train_pack/dataset/sft_weak_dims.jsonl")
    ap.add_argument("--out", default="output/sft_disciplined_v1")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-length", type=int, default=768)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    set_seed(args.seed)

    samples = load_samples(args.a3, args.b)
    print(f"[SFT] 样本数={len(samples)} base={args.base}")
    assert samples, "无可用训练样本"

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    from transformers import BitsAndBytesConfig
    # 绕过 transformers 5.22 在 4-bit 加载期的 caching_allocator_warmup 缺陷：
    # 它会对 8B 模型额外申请 ~4.8GB fp16 缓冲，6GB 笔记本显卡直接 OOM。该缓冲对
    # 纯 GPU 加载毫无用处，置为空操作即可让 4-bit 权重（~4.2GB）直接落显存。
    try:
        import transformers.modeling_utils as _mu
        _mu.caching_allocator_warmup = lambda *a, **k: None
    except Exception:
        pass
    quant = {"quantization_config": BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True)}
    model_kwargs = dict(torch_dtype=torch.bfloat16, **quant)
    model_kwargs["device_map"] = {"": 0}
    model = AutoModelForCausalLM.from_pretrained(
        args.base, attn_implementation="sdpa", **model_kwargs)
    model = prepare_model_for_kbit_training(model)
    lora = LoraConfig(task_type=TaskType.CAUSAL_LM, r=args.lora_r,
                      lora_alpha=args.lora_alpha, lora_dropout=0.05,
                      target_modules=TARGET_MODULES, bias="none")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    ds = SFTDataset(samples, tokenizer, args.max_length)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True, collate_fn=collate)

    from bitsandbytes.optim import AdamW8bit
    opt = AdamW8bit(model.parameters(), lr=args.lr)
    model.train()
    device = next(model.parameters()).device
    step = 0
    acc_loss = 0.0
    opt.zero_grad()
    for epoch in range(args.epochs):
        for ids, mask, labels in dl:
            if step >= args.steps:
                break
            ids, mask, labels = ids.to(device), mask.to(device), labels.to(device)
            out = model(input_ids=ids, attention_mask=mask, labels=labels)
            loss = out.loss / args.grad_accum
            loss.backward()
            acc_loss += loss.item() * args.grad_accum
            step += 1
            if step % args.grad_accum == 0:
                opt.step()
                opt.zero_grad()
            if step % 20 == 0:
                print(f"[SFT] step={step} loss={acc_loss/20:.4f}")
                acc_loss = 0.0
        if step >= args.steps:
            break

    os.makedirs(args.out, exist_ok=True)
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    # 同时写 merge_receipt 便于后续 merge 脚本识别
    with open(os.path.join(args.out, "sft_receipt.json"), "w", encoding="utf-8") as f:
        json.dump({"base": os.path.abspath(args.base),
                   "samples": len(samples), "steps": step, "lr": args.lr}, f, ensure_ascii=False, indent=2)
    print(f"[SFT] 完成，adapter -> {args.out}")


if __name__ == "__main__":
    main()
