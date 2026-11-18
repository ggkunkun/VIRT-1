#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云端一次性 QLoRA 训练（可移植版，无本机 Windows/offload 依赖）。

与本地 scripts/train_vericut_local_qlora.py 的训练目标一致（4-bit NF4 主干 + LoRA r32/alpha64、
chat 模板、prompt 掩码、AdamW8bit、cosine+warmup、按步存盘与断点续训），但去掉了本机的
分块 CE / 激活 offload / pinned lm_head 等显存技巧——云端 24GB+ 显卡不需要，反而容易出驱动问题。

用法：
  python train_qlora.py --base Qwen/Qwen2.5-7B-Instruct \
      --data six_software_v9_repair_sft.jsonl --out ./out/lora \
      --epochs 1 --max-length 640 --grad-accum 4 --lr 8e-5 --save-every 30

产物：<out>/adapter_model.safetensors、adapter_config.json、training_receipt.json（含 sha256 与 dev_loss）
断点：<out>/_ckpt_latest（--resume 时自动读取并校验 dataset_sha256/seed/max_length/grad_accum/epochs）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import sys
import time
from pathlib import Path


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            msgs = r.get("messages") or []
            if len(msgs) < 2:
                continue
            if msgs[-1].get("role") != "assistant" or not msgs[-1].get("content"):
                continue
            rows.append(r)
    return rows


def encode(tokenizer, messages: list[dict], max_length: int):
    """整段对话编码；prompt 部分 label 置 -100（只学 assistant）。

    关键：max_length 可能把 assistant 段整段截掉，此时 labels 全为 -100，
    cross_entropy 会返回 NaN 并污染权重。这里改为「截断时优先保住 assistant 尾部」，
    仍无监督 token 则返回 None（由调用方跳过并计数）。
    """
    full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    prompt_msgs = messages[:-1]
    prompt = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
    full_ids = tokenizer(full, add_special_tokens=False).input_ids
    prompt_len = len(tokenizer(prompt, add_special_tokens=False).input_ids)

    n = len(full_ids)
    if n > max_length:
        if prompt_len >= n - 1:
            return None  # 截断后没有任何 assistant token
        full_ids = full_ids[-max_length:]
        prompt_len = max(0, prompt_len - (n - len(full_ids)))

    labels = list(full_ids)
    for i in range(min(prompt_len, len(labels))):
        labels[i] = -100

    if all(x == -100 for x in labels):
        return None
    return {"input_ids": full_ids, "labels": labels, "attention_mask": [1] * len(full_ids)}


class Collator:
    def __init__(self, pad_id: int):
        self.pad_id = pad_id

    def __call__(self, batch: list[dict]) -> dict:
        import torch
        L = max(len(b["input_ids"]) for b in batch)
        ids, labels, attn = [], [], []
        for b in batch:
            pad = L - len(b["input_ids"])
            ids.append(b["input_ids"] + [self.pad_id] * pad)
            labels.append(b["labels"] + [-100] * pad)
            attn.append(b["attention_mask"] + [0] * pad)
        return {
            "input_ids": torch.tensor(ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "attention_mask": torch.tensor(attn, dtype=torch.long),
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="HF repo id 或本地目录")
    ap.add_argument("--data", required=True, help="SFT jsonl（messages 格式）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--max-length", type=int, default=640)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--lr", type=float, default=8e-5)
    ap.add_argument("--save-every", type=int, default=30)
    ap.add_argument("--val-ratio", type=float, default=0.08)
    ap.add_argument("--seed", type=int, default=20261117)
    ap.add_argument("--lora-r", type=int, default=32)
    ap.add_argument("--lora-alpha", type=int, default=64)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"],
                    help="cpu 仅用于冒烟自测（全精度、不量化）")
    ap.add_argument("--no-4bit", action="store_true", help="禁用 4-bit 量化（自测/无 bitsandbytes 环境）")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              get_cosine_schedule_with_warmup)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data_path = Path(args.data)
    data_sha = sha256_file(data_path)

    rows = load_rows(data_path)
    if not rows:
        print("[FATAL] 语料无有效样本", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    rng.shuffle(rows)
    n_dev = max(1, int(len(rows) * args.val_ratio))
    dev_rows, train_rows = rows[:n_dev], rows[n_dev:]
    print(f"[Data] rows={len(rows)} train={len(train_rows)} dev={n_dev} sha={data_sha[:16]}", flush=True)

    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    bnb = None
    use_4bit = (args.device == "cuda" and not args.no_4bit)
    if use_4bit:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    t0 = time.time()
    load_kwargs = dict(trust_remote_code=True)
    if use_4bit:
        load_kwargs.update(quantization_config=bnb, device_map={"": 0})
    else:
        load_kwargs.update(torch_dtype=torch.float32 if args.device == "cpu" else torch.bfloat16,
                           device_map={"": "cpu" if args.device == "cpu" else 0})
    model = AutoModelForCausalLM.from_pretrained(args.base, **load_kwargs)
    model.config.use_cache = False
    if use_4bit:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model.gradient_checkpointing_enable()

    targets = sorted({n.split(".")[-1] for n, _ in model.named_modules()
                      if n.split(".")[-1] in {"q_proj", "k_proj", "v_proj", "o_proj",
                                              "gate_proj", "up_proj", "down_proj"}})
    lcfg = LoraConfig(r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
                      bias="none", task_type="CAUSAL_LM", target_modules=targets)
    model = get_peft_model(model, lcfg)
    model.print_trainable_parameters()
    print(f"[Model] loaded in {time.time()-t0:.0f}s targets={targets}", flush=True)

    collate = Collator(tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id)

    # 预编码并过滤掉「无监督 token」的样本（否则 cross_entropy 全 -100 会返回 NaN）
    skipped = 0
    enc_train: list[dict] = []
    for r in train_rows:
        e = encode(tok, r["messages"], args.max_length)
        if e is None:
            skipped += 1
            continue
        enc_train.append(e)
    enc_dev: list[dict] = []
    for r in dev_rows:
        e = encode(tok, r["messages"], args.max_length)
        if e is None:
            skipped += 1
            continue
        enc_dev.append(e)
    if skipped:
        print(f"[Data] 跳过 {skipped} 条（max_length={args.max_length} 下无 assistant token）", flush=True)
    if not enc_train:
        print("[FATAL] 没有可训练样本：请提高 --max-length 或检查语料", file=sys.stderr)
        return 2
    print(f"[Data] encoded train={len(enc_train)} dev={len(enc_dev)} "
          f"tok_max={max(len(e['input_ids']) for e in enc_train)}", flush=True)

    def dev_loss() -> float:
        if not enc_dev:
            return float("nan")
        model.eval()
        tot, n = 0.0, 0
        with torch.no_grad():
            for enc in enc_dev:
                batch = collate([enc])
                batch = {k: v.to(args.device) for k, v in batch.items()}
                out_ = model(**batch)
                v = float(out_.loss)
                if not math.isfinite(v):
                    continue
                tot += v
                n += 1
        model.train()
        return tot / max(n, 1)

    start_upd = 0
    micro_done = 0
    prev_end = None
    ckpt_dir = out / "_ckpt_latest"
    meta = {"dataset_sha256": data_sha, "seed": args.seed, "max_length": args.max_length,
            "grad_accum": args.grad_accum, "epochs": args.epochs}
    if args.resume and (ckpt_dir / "ckpt_state.json").exists():
        state = json.loads((ckpt_dir / "ckpt_state.json").read_text(encoding="utf-8"))
        mismatch = [k for k, v in meta.items() if state.get(k) != v]
        if mismatch:
            print(f"[FATAL] 断点元数据不一致: {mismatch}", file=sys.stderr)
            return 3
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(ckpt_dir), is_trainable=True)
        start_upd, micro_done = int(state["upd"]), int(state["micro"])
        prev_end = state.get("dev_loss_end")
        print(f"[Resume] step={start_upd} micro={micro_done}", flush=True)

    dev_start = prev_end if prev_end is not None else dev_loss()
    print(f"[Eval@Start] dev_loss_start={dev_start:.4f}", flush=True)

    steps_per_epoch = math.ceil(len(enc_train) / args.grad_accum)
    total_upd = int(math.ceil(steps_per_epoch * args.epochs))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=args.lr, betas=(0.9, 0.999), weight_decay=0.0, eps=1e-8)
    sched = get_cosine_schedule_with_warmup(opt, int(total_upd * 0.03), total_upd)

    model.train()
    t0 = time.time()
    idx = micro_done % len(train_rows)
    upd = start_upd
    opt.zero_grad(set_to_none=True)
    while upd < total_upd:
        enc = enc_train[idx % len(enc_train)]
        batch = {k: v.to(args.device) for k, v in collate([enc]).items()}
        loss = model(**batch).loss / args.grad_accum
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"loss 非有限值（step={upd}）——已中止，避免写出 NaN 权重。"
                f"请检查数据/学习率/max_length；日志见上方 [Train] 行")
        loss.backward()
        idx += 1
        if idx % args.grad_accum == 0:
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            upd += 1
            if upd % 10 == 0 or upd == total_upd:
                el = time.time() - t0
                print(f"[Train] step={upd}/{total_upd} loss={float(loss)*args.grad_accum:.4f} "
                      f"lr={sched.get_last_lr()[0]:.2e} vram={(torch.cuda.max_memory_allocated()/1e6 if args.device=="cuda" else 0):.0f}MB "
                      f"elapsed={el:.0f}s eta={el/max(upd-start_upd,1)*(total_upd-upd):.0f}s", flush=True)
            if upd % args.save_every == 0:
                _save_ckpt(model, tok, ckpt_dir, {**meta, "upd": upd, "micro": idx,
                                                  "dev_loss_start": dev_start, "dev_loss_end": None})
                print(f"[Ckpt] saved step={upd}/{total_upd}", flush=True)
        if idx >= len(enc_train) * args.epochs:
            break

    dev_end = dev_loss()
    if not math.isfinite(dev_end):
        print("[FATAL] 最终 dev_loss 非有限值，拒绝写凭证", file=sys.stderr)
        return 4
    print(f"[Eval@End] dev_loss_end={dev_end:.4f} (delta={dev_end-dev_start:+.4f})", flush=True)
    if dev_end > dev_start:
        print(f"[WARN] dev_loss 变差（{dev_start:.4f} → {dev_end:.4f}），"
              f"该 adapter 很可能不可用，请勿直接部署", file=sys.stderr)

    model.save_pretrained(out)
    tok.save_pretrained(out)
    adapter = out / "adapter_model.safetensors"
    receipt = {
        "status": "COMPLETED",
        "base": args.base,
        "dataset": str(data_path),
        "dataset_sha256": data_sha,
        "rows": {"train": len(train_rows), "dev": n_dev},
        "config": {"epochs": args.epochs, "max_length": args.max_length, "grad_accum": args.grad_accum,
                   "lr": args.lr, "lora_r": args.lora_r, "lora_alpha": args.lora_alpha, "seed": args.seed},
        "dev_loss_start": round(dev_start, 6),
        "dev_loss_end": round(dev_end, 6),
        "total_updates": upd,
        "adapter_sha256": sha256_file(adapter) if adapter.exists() else None,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out / "training_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    if ckpt_dir.exists():
        shutil.rmtree(ckpt_dir, ignore_errors=True)
    print(f"[SAVED] {out} | adapter_sha={receipt['adapter_sha256'][:16] if receipt['adapter_sha256'] else 'NA'}",
          flush=True)
    return 0


def _save_ckpt(model, tok, ckpt_dir: Path, state: dict) -> None:
    tmp = ckpt_dir.with_name("_ckpt_tmp")
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(tmp)
    tok.save_pretrained(tmp)
    (tmp / "ckpt_state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    if ckpt_dir.exists():
        shutil.rmtree(ckpt_dir, ignore_errors=True)
    tmp.rename(ckpt_dir)


if __name__ == "__main__":
    raise SystemExit(main())
