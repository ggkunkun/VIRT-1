#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Train the Virtu text LoRA on a Tesla V100-SXM2-32GB.

Hardware constraints handled explicitly:
  * V100 (sm_70) has no bf16 -> fp16 compute + QLoRA 4-bit NF4.
  * V100 has no FlashAttention-2 -> sdpa (math fallback) or eager.
  * 32GB VRAM -> batch 1, grad-accum 32, max_len 2048 by default.
  * Optional --no-4bit fallback if bitsandbytes 4-bit misbehaves on sm_70.

Recommended flow:
  python scripts/train_virtu_v100.py --preflight
  python scripts/train_virtu_v100.py --smoke
  python scripts/train_virtu_v100.py

The data directory must contain exactly ONE *.jsonl. Use:
  --data data/train/virtu_v3/train
Never point it at the parent directory containing reports/.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]


def _print_versions():
    import transformers
    import peft
    try:
        import bitsandbytes as bnb
        bnb_ver = bnb.__version__
    except Exception as exc:  # noqa: BLE001
        bnb_ver = f"unavailable: {exc}"
    print(f"[env] torch={torch.__version__} cuda={torch.version.cuda} "
          f"transformers={transformers.__version__} peft={peft.__version__} "
          f"bitsandbytes={bnb_ver}")


def _gpu_info():
    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] CUDA unavailable; V100 training requires a GPU")
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    total = torch.cuda.get_device_properties(0).total_memory / 1e9
    free = torch.cuda.mem_get_info(0)[0] / 1e9
    print(f"[gpu] {name} capability={cap} total={total:.1f}G free={free:.1f}G")
    print(f"[gpu] bf16_supported={torch.cuda.is_bf16_supported()} "
          f"(V100 expected False; script uses fp16)")
    return name, cap, total


def _data_files(data_dir: str):
    files = sorted(glob.glob(os.path.join(data_dir, "*.jsonl")))
    if len(files) != 1:
        raise SystemExit(
            f"[FATAL] expected exactly one *.jsonl in {data_dir}, found {len(files)}: {files}. "
            f"Use data/train/virtu_v3/train, not the parent with reports/.")
    path = files[0]
    rows = sum(1 for _ in open(path, encoding="utf-8"))
    manifest_path = Path(data_dir).parent / "manifest.json"
    if not manifest_path.exists():
        manifest_path = Path(data_dir).parent / "virtu_fix_text_sft_v1.manifest.json"
    if manifest_path.exists():
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if manifest.get("sha256") and manifest["sha256"] != actual:
            raise SystemExit(
                f"[FATAL] training file sha256 mismatch: {actual} != "
                f"{manifest['sha256']} (manifest {manifest_path}). Rebuild the corpus.")
        print(f"[data] sha256 verified against {manifest_path.name}")
    else:
        print(f"[warn] no manifest next to {data_dir}; sha256 check skipped")
    print(f"[data] {path} rows={rows}")
    return path, rows


def _preflight(args):
    _print_versions()
    name, cap, total = _gpu_info()
    if total < 30:
        print("[WARN] less than 30GB VRAM; reduce --max-len/--batch or use --no-4bit check")
    if cap[0] < 7:
        raise SystemExit(f"[FATAL] unsupported compute capability {cap}")
    data_file, rows = _data_files(args.data)
    if not os.path.isdir(args.base):
        if os.path.isabs(args.base):
            raise SystemExit(
                f"[FATAL] local base missing: {args.base}. Download it first, e.g. "
                f"modelscope download --model Qwen/Qwen3-8B --local_dir {args.base}")
        print(f"[warn] base is not a local dir: {args.base} (treated as HF/ModelScope repo id)")
    else:
        if not os.path.exists(os.path.join(args.base, "config.json")):
            raise SystemExit(f"[FATAL] base config.json missing: {args.base}")
        print(f"[base] local dir {args.base}")
    du = shutil.disk_usage(ROOT)
    print(f"[disk] root={ROOT} free={du.free/1e9:.1f}G (need >20G)")
    if du.free < 20e9:
        print("[WARN] less than 20GB free disk; checkpoints/Q4 export may fail")
    try:
        import transformers
        major = int(transformers.__version__.split(".")[0])
        if major >= 5:
            print("[WARN] transformers>=5 detected. This script is validated on 4.51.x; "
                  "pin transformers==4.51.3 if Trainer/peft errors appear.")
    except Exception:
        pass
    print(f"[preflight] OK data={data_file} rows={rows} gpu={name}")
    print("[hint] V100 has no bf16/FlashAttention-2. Default is fp16 QLoRA, sdpa, batch=1, "
          "grad-accum=32, max_len=2048. If paged_adamw_8bit fails on sm70, retry with "
          "--optim adamw_torch; if 4-bit NF4 fails, retry with --no-4bit.")
    return data_file, rows


def _load_tokenizer(args):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=args.trust_remote_code)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"
    return tok


def _load_dataset(args, tokenizer):
    sys.path.insert(0, str(ROOT))
    try:
        from train_virtu import load_and_tokenize
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"[FATAL] cannot import train_virtu.load_and_tokenize: {exc}. "
            f"Upload train_virtu.py next to the repo root.") from exc
    ds = load_and_tokenize(args.data, tokenizer, max_length=args.max_len)
    if len(ds) == 0:
        raise SystemExit("[FATAL] no usable samples after ChatML conversion")
    if args.val_samples > 0 and len(ds) > args.val_samples + 8:
        split = ds.train_test_split(test_size=args.val_samples, seed=args.seed)
        return split["train"], split["test"]
    return ds, None


def _load_model(args):
    from transformers import AutoModelForCausalLM
    kwargs = dict(
        trust_remote_code=args.trust_remote_code,
        device_map={"": 0},
        torch_dtype=torch.float16,
        attn_implementation=args.attn,
    )
    if not args.no_4bit:
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    print(f"[model] loading {args.base} mode={'fp16-lora' if args.no_4bit else 'qlora-nf4'} "
          f"attn={args.attn}")
    try:
        model = AutoModelForCausalLM.from_pretrained(args.base, **kwargs)
    except (TypeError, ValueError) as exc:
        print(f"[warn] load with attn_implementation failed ({exc}); retry eager")
        kwargs["attn_implementation"] = "eager"
        model = AutoModelForCausalLM.from_pretrained(args.base, **kwargs)
    model.config.use_cache = False
    return model


def _attach_lora(args, model):
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    if not args.no_4bit:
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=args.gradient_checkpointing)
    else:
        if args.gradient_checkpointing:
            model.gradient_checkpointing_enable()
            model.enable_input_require_grads()
    cfg = LoraConfig(
        r=args.r,
        lora_alpha=args.alpha,
        lora_dropout=args.dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=TARGET_MODULES,
    )
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    return model


class VramLogger:
    """TrainerCallback-compatible logger; imported lazily to keep preflight light."""

    def __new__(cls, *a, **k):
        from transformers import TrainerCallback

        class _CB(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                if torch.cuda.is_available():
                    alloc = torch.cuda.memory_allocated() / 1e9
                    peak = torch.cuda.max_memory_allocated() / 1e9
                    print(f"[vram] step={state.global_step} alloc={alloc:.2f}G peak={peak:.2f}G",
                          flush=True)
        return _CB()


def _training_args(args, eval_ds):
    from transformers import TrainingArguments
    kwargs = dict(
        output_dir=args.output,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps if args.max_steps > 0 else -1,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type="cosine",
        logging_steps=args.logging_steps,
        logging_first_step=True,
        save_steps=args.save_steps,
        save_total_limit=2,
        fp16=True,
        bf16=False,
        tf32=False,
        gradient_checkpointing=args.gradient_checkpointing,
        optim=args.optim,
        group_by_length=False,
        dataloader_num_workers=args.num_workers,
        dataloader_pin_memory=True,
        remove_unused_columns=False,
        report_to=[],
        seed=args.seed,
        data_seed=args.seed,
        save_safetensors=True,
    )
    if eval_ds is not None and args.max_steps <= 0:
        kwargs.update(eval_strategy="steps", eval_steps=args.save_steps,
                      per_device_eval_batch_size=1, prediction_loss_only=True)
    return TrainingArguments(**kwargs)


def _make_trainer(args, model, tokenizer, train_ds, eval_ds, callbacks):
    from transformers import DataCollatorForSeq2Seq, Trainer
    collator = DataCollatorForSeq2Seq(
        tokenizer, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8)
    common = dict(
        model=model,
        args=_training_args(args, eval_ds),
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
        callbacks=callbacks,
    )
    try:
        return Trainer(tokenizer=tokenizer, **common)
    except TypeError:
        return Trainer(processing_class=tokenizer, **common)


def _write_receipt(args, trainer, data_file, rows, train_ds, eval_ds, gpu_name):
    state = trainer.state
    history = state.log_history or []
    losses = [h["loss"] for h in history if isinstance(h, dict) and "loss" in h]
    receipt = {
        "status": "SMOKE_ONLY" if args.smoke else "COMPLETED",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": args.base,
        "data_file": data_file,
        "data_rows": rows,
        "train_samples": len(train_ds),
        "val_samples": len(eval_ds) if eval_ds is not None else 0,
        "output": args.output,
        "mode": "fp16-lora" if args.no_4bit else "qlora-nf4",
        "attention": args.attn,
        "lora": {"r": args.r, "alpha": args.alpha, "dropout": args.dropout},
        "train": {
            "batch": args.batch, "grad_accum": args.grad_accum,
            "lr": args.lr, "epochs": args.epochs, "max_len": args.max_len,
            "max_steps": args.max_steps, "optim": args.optim,
            "seed": args.seed, "gradient_checkpointing": args.gradient_checkpointing,
        },
        "gpu": gpu_name,
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 3)
        if torch.cuda.is_available() else None,
        "train_runtime_s": round(getattr(state, "train_runtime", 0) or 0, 1),
        "final_loss": round(losses[-1], 6) if losses else None,
        "versions": {
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
            "peft": __import__("peft").__version__,
        },
    }
    os.makedirs(args.output, exist_ok=True)
    with open(os.path.join(args.output, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=os.environ.get("VIRTU_BASE", "/root/models/Qwen3-8B"))
    p.add_argument("--data", default=str(ROOT / "data/train/virtu_v3/train"))
    p.add_argument("--output", default=str(ROOT / "checkpoints/virtu_hardened_v1_lora"))
    p.add_argument("--max-len", type=int, default=2048)
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--epochs", type=float, default=2)
    p.add_argument("--max-steps", type=int, default=0)
    p.add_argument("--warmup-ratio", type=float, default=0.03)
    p.add_argument("--logging-steps", type=int, default=10)
    p.add_argument("--save-steps", type=int, default=200)
    p.add_argument("--val-samples", type=int, default=64)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--r", type=int, default=32)
    p.add_argument("--alpha", type=int, default=64)
    p.add_argument("--dropout", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--attn", default="sdpa", choices=["sdpa", "eager"])
    p.add_argument("--optim", default="adamw_torch",
                   choices=["adamw_torch", "paged_adamw_8bit"],
                   help="V100 sm70 default adamw_torch (most stable); paged 8bit optional")
    p.add_argument("--no-4bit", action="store_true",
                   help="Fallback: fp16 LoRA without bitsandbytes 4-bit")
    p.add_argument("--no-gradient-checkpointing", dest="gradient_checkpointing",
                   action="store_false")
    p.set_defaults(gradient_checkpointing=True)
    p.add_argument("--trust-remote-code", action="store_true")
    p.add_argument("--resume", default="")
    p.add_argument("--preflight", action="store_true")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    data_file, rows = _preflight(args)
    if args.preflight:
        print("[preflight] done; no model loaded")
        return 0

    tokenizer = _load_tokenizer(args)
    train_ds, eval_ds = _load_dataset(args, tokenizer)
    print(f"[data] train={len(train_ds)} val={len(eval_ds) if eval_ds is not None else 0}")

    model = _load_model(args)
    model = _attach_lora(args, model)

    if args.smoke:
        args.max_steps = min(args.max_steps or 20, 20)
        args.epochs = 1
        args.logging_steps = 1
        args.save_steps = args.max_steps
        if not args.output.rstrip("/\\").endswith("_smoke"):
            args.output = args.output.rstrip("/\\") + "_smoke"
        print(f"[smoke] max_steps={args.max_steps} output={args.output}")

    callbacks = [VramLogger()]
    trainer = _make_trainer(args, model, tokenizer, train_ds, eval_ds, callbacks)
    steps_per_epoch = math.ceil(len(train_ds) / max(1, args.batch * args.grad_accum))
    total_steps = steps_per_epoch * float(args.epochs)
    print(f"[plan] steps/epoch={steps_per_epoch} total≈{total_steps:.0f} "
          f"effective_batch={args.batch * args.grad_accum}")
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    try:
        trainer.train(resume_from_checkpoint=args.resume or None)
    except torch.cuda.OutOfMemoryError as exc:
        raise SystemExit(
            "[FATAL] CUDA OOM. Retry with --max-len 1536 (and keep --batch 1 / "
            "--grad-accum 32); do not raise --batch on a 32GB V100.") from exc
    print(f"[done] wall={time.time()-t0:.1f}s peak_vram="
          f"{torch.cuda.max_memory_allocated()/1e9:.2f}G")

    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    _write_receipt(args, trainer, data_file, rows, train_ds, eval_ds,
                   torch.cuda.get_device_name(0))
    print(f"[merge] python scripts/merge_numpy.py --base {args.base} "
          f"--out checkpoints/virtu_hardened_v1 --mode delta "
          f"--lora {args.output} --weight 1.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
