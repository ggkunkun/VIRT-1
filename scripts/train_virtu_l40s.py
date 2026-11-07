#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Train the Virtu text LoRA on a single NVIDIA L40S (48GB, Ada sm_89).

Route A of CLOUD_FINETUNE_PLAN_2026-11-01_v2.md. Unlike the V100 script this is
NOT QLoRA: 48GB holds Qwen3-8B in bf16, so the base stays unquantized. The 2026-11-01
length audit (work/corpus_len_distribution.json) found the long tail sits at ~5,000
tokens, not ~2,100: max_len 4096 still truncates 300 of 5,991 rows, while 5120
truncates none. So the default is 5120 -- that is the whole reason to pay for route A.

  python scripts/train_virtu_l40s.py --preflight
  python scripts/train_virtu_l40s.py --smoke
  python scripts/train_virtu_l40s.py

The data directory must contain exactly ONE *.jsonl:
  --data data/train/virtu_v3/train
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
ATTN_CANDIDATES = ["flash_attention_2", "sdpa", "eager"]
IM_START = "<" + "|im_start" + "|>"
IM_END = "<" + "|im_end" + "|>"


def _flash_attn_present() -> bool:
    try:
        import flash_attn  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _print_versions():
    import peft
    import transformers
    print(f"[env] torch={torch.__version__} cuda={torch.version.cuda} "
          f"transformers={transformers.__version__} peft={peft.__version__} "
          f"flash_attn={'yes' if _flash_attn_present() else 'no'}")


def _gpu_info():
    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] CUDA unavailable; the L40S script needs a GPU")
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    total = torch.cuda.get_device_properties(0).total_memory / 1e9
    free = torch.cuda.mem_get_info(0)[0] / 1e9
    print(f"[gpu] {name} capability={cap} total={total:.1f}G free={free:.1f}G "
          f"bf16_supported={torch.cuda.is_bf16_supported()}")
    if not torch.cuda.is_bf16_supported():
        raise SystemExit(
            f"[FATAL] {name} has no bf16. Use scripts/train_virtu_v100.py (fp16 QLoRA) instead.")
    if total < 40:
        print(f"[WARN] {total:.1f}GB VRAM: drop --max-len to 2048 or pass --load-4bit")
    if cap[0] < 8:
        print(f"[WARN] compute capability {cap} predates Ada; flash-attn may not build; "
              "sdpa is selected automatically")
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


def _chatml(item):
    msgs = item.get("messages") or []
    # Default system text must match train_virtu.load_and_tokenize or the audit lies.
    sys_msg = next((m["content"] for m in msgs if m["role"] == "system"),
                   "你是 Virtu 工业级 CAD/CAM/CAE 与数控编程专家，也能像人一样自然交流。")
    user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
    asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
    if not user_msg or not asst_msg:
        return None
    prompt = (f"{IM_START}system\n{sys_msg}{IM_END}\n"
              f"{IM_START}user\n{user_msg}{IM_END}\n"
              f"{IM_START}assistant\n")
    return prompt, prompt + asst_msg + IM_END


def _audit_lengths(args, tokenizer):
    """Report exactly how many rows the chosen --max-len would truncate."""
    data_file, _ = _data_files(args.data)
    lens = []
    for line in open(data_file, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        pair = _chatml(json.loads(line))
        if pair is None:
            continue
        _, full = pair
        lens.append(len(tokenizer.encode(full, add_special_tokens=False)))
    lens.sort()
    n = len(lens)
    print(f"[audit] usable rows={n} p50={lens[n // 2]} p90={lens[int(.90 * n)]} "
          f"p99={lens[int(.99 * n)]} max={lens[-1]}")
    for cap in (1024, 1536, 2048, 3072, 4096, 5120):
        over = sum(1 for x in lens if x > cap)
        kept = sum(min(x, cap) for x in lens)
        mark = "  <-- current --max-len" if cap == args.max_len else ""
        print(f"[audit] max_len={cap:>5}: truncated_rows={over:>4} "
              f"tokens_per_epoch={kept:,}{mark}")


def _preflight(args):
    _print_versions()
    name, cap, total = _gpu_info()
    _data_files(args.data)
    if not os.path.isdir(args.base):
        if os.path.isabs(args.base):
            raise SystemExit(
                f"[FATAL] local base missing: {args.base}. Download it first, e.g. "
                f"modelscope download --model Qwen/Qwen3-8B --local_dir {args.base}")
        print(f"[warn] base is not a local dir: {args.base} (treated as repo id)")
    elif not os.path.exists(os.path.join(args.base, "config.json")):
        raise SystemExit(f"[FATAL] base config.json missing: {args.base}")
    else:
        print(f"[base] local dir {args.base}")
    du = shutil.disk_usage(ROOT)
    print(f"[disk] root={ROOT} free={du.free / 1e9:.1f}G (need >25G)")
    if du.free < 25e9:
        print("[WARN] less than 25GB free; checkpoints and the Q4 export may fail")
    if not _flash_attn_present():
        print("[note] flash_attn not installed -> sdpa. On Ada sdpa is adequate; "
              "installing flash-attn is optional and can waste an hour on the wheel build")
    eff = args.batch * args.grad_accum
    print(f"[plan] mode={'qlora-4bit' if args.load_4bit else 'bf16-lora'} "
          f"max_len={args.max_len} batch={args.batch} grad_accum={args.grad_accum} "
          f"effective_batch={eff} lr={args.lr} epochs={args.epochs} "
          f"group_by_length={args.group_by_length}")
    print(f"[preflight] OK gpu={name}")
    return name


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
    kwargs = dict(trust_remote_code=args.trust_remote_code,
                  device_map={"": 0}, torch_dtype=torch.bfloat16)
    if args.load_4bit:
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    order = ATTN_CANDIDATES if _flash_attn_present() else ATTN_CANDIDATES[1:]
    last = None
    for impl in order:
        attempt = dict(kwargs, attn_implementation=impl)
        print(f"[model] loading {args.base} dtype=bfloat16 "
              f"mode={'qlora-nf4' if args.load_4bit else 'bf16-lora'} attn={impl}")
        try:
            model = AutoModelForCausalLM.from_pretrained(args.base, **attempt)
            args.attn_used = impl
            print(f"[model] attn_implementation in use: {impl}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {impl} unavailable: {type(exc).__name__}: {str(exc)[:160]}")
            last = exc
    else:
        raise SystemExit(f"[FATAL] no attention implementation worked; last={last}")
    model.config.use_cache = False
    return model


def _attach_lora(args, model):
    from peft import LoraConfig, get_peft_model
    if args.load_4bit:
        from peft import prepare_model_for_kbit_training
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=args.gradient_checkpointing)
    elif args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    model = get_peft_model(LoraConfig(
        r=args.r, lora_alpha=args.alpha, lora_dropout=args.dropout,
        bias="none", task_type="CAUSAL_LM", target_modules=TARGET_MODULES), model)
    model.print_trainable_parameters()
    return model


class VramLogger:
    """TrainerCallback-compatible; built lazily so preflight stays light."""

    def __new__(cls, *a, **k):
        from transformers import TrainerCallback

        class _CB(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                alloc = torch.cuda.memory_allocated() / 1e9
                peak = torch.cuda.max_memory_allocated() / 1e9
                tok_s = (logs or {}).get("train_samples_per_second") or \
                    (logs or {}).get("samples_per_second")
                print(f"[vram] step={state.global_step} alloc={alloc:.2f}G "
                      f"peak={peak:.2f}G free={torch.cuda.mem_get_info(0)[0] / 1e9:.2f}G "
                      f"samples/s={tok_s}", flush=True)
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
        save_total_limit=3,
        bf16=True,
        bf16_full_eval=True,
        fp16=False,
        tf32=True,
        gradient_checkpointing=args.gradient_checkpointing,
        optim=args.optim,
        group_by_length=args.group_by_length,
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
    common = dict(model=model, args=_training_args(args, eval_ds),
                  train_dataset=train_ds, eval_dataset=eval_ds,
                  data_collator=collator, callbacks=callbacks)
    try:
        return Trainer(tokenizer=tokenizer, **common)
    except TypeError:
        return Trainer(processing_class=tokenizer, **common)


def _write_receipt(args, trainer, data_file, rows, train_ds, eval_ds, gpu_name, wall_s):
    state = trainer.state
    history = state.log_history or []
    losses = [h["loss"] for h in history if isinstance(h, dict) and "loss" in h]
    steps = max(1, state.global_step)
    receipt = {
        "status": "SMOKE_ONLY" if args.smoke else "COMPLETED",
        "route": "A-L40S-bf16-lora" if not args.load_4bit else "A-L40S-4bit-fallback",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": args.base,
        "data_file": data_file,
        "data_rows": rows,
        "train_samples": len(train_ds),
        "val_samples": len(eval_ds) if eval_ds is not None else 0,
        "output": args.output,
        "attention": getattr(args, "attn_used", None),
        "lora": {"r": args.r, "alpha": args.alpha, "dropout": args.dropout,
                 "target_modules": TARGET_MODULES},
        "train": {"batch": args.batch, "grad_accum": args.grad_accum,
                  "effective_batch": args.batch * args.grad_accum,
                  "lr": args.lr, "epochs": args.epochs, "max_len": args.max_len,
                  "max_steps": args.max_steps, "optim": args.optim,
                  "seed": args.seed, "group_by_length": args.group_by_length,
                  "gradient_checkpointing": args.gradient_checkpointing},
        "gpu": gpu_name,
        "global_step": state.global_step,
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 3),
        "train_runtime_s": round(getattr(state, "train_runtime", 0) or wall_s, 1),
        "s_per_step": round(wall_s / steps, 3),
        "final_loss": round(losses[-1], 6) if losses else None,
        "versions": {
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
            "peft": __import__("peft").__version__,
            "flash_attn": _flash_attn_present(),
        },
    }
    os.makedirs(args.output, exist_ok=True)
    with open(os.path.join(args.output, "training_receipt.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=2)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=os.environ.get("VIRTU_BASE", "/root/models/Qwen3-8B"))
    p.add_argument("--data", default=str(ROOT / "data/train/virtu_v3/train"))
    p.add_argument("--output", default=str(ROOT / "checkpoints/virtu_hardened_v1_lora"))
    p.add_argument("--max-len", dest="max_len", type=int, default=5120)
    p.add_argument("--batch", type=int, default=2)
    p.add_argument("--grad-accum", dest="grad_accum", type=int, default=16)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--epochs", type=float, default=2)
    p.add_argument("--max-steps", dest="max_steps", type=int, default=0)
    p.add_argument("--warmup-ratio", dest="warmup_ratio", type=float, default=0.03)
    p.add_argument("--logging-steps", dest="logging_steps", type=int, default=10)
    p.add_argument("--save-steps", dest="save_steps", type=int, default=100)
    p.add_argument("--val-samples", dest="val_samples", type=int, default=64)
    p.add_argument("--num-workers", dest="num_workers", type=int, default=4)
    p.add_argument("--r", type=int, default=32)
    p.add_argument("--alpha", type=int, default=64)
    p.add_argument("--dropout", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--optim", default="adamw_torch",
                   choices=["adamw_torch", "paged_adamw_8bit", "adamw_bnb_8bit"])
    p.add_argument("--load-4bit", dest="load_4bit", action="store_true",
                   help="Fallback for <=24GB cards; the L40S default keeps the base in bf16")
    p.add_argument("--group-by-length", dest="group_by_length", action="store_true",
                   default=True, help="Cuts padding waste (p50 is ~180 tokens, max ~5k)")
    p.add_argument("--no-group-by-length", dest="group_by_length", action="store_false")
    p.add_argument("--no-gradient-checkpointing", dest="gradient_checkpointing",
                   action="store_false")
    p.set_defaults(gradient_checkpointing=True)
    p.add_argument("--trust-remote-code", dest="trust_remote_code", action="store_true")
    p.add_argument("--resume", default="")
    p.add_argument("--preflight", action="store_true")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--audit-lengths", dest="audit_lengths", action="store_true")
    args = p.parse_args()

    gpu_name = _preflight(args)
    tokenizer = _load_tokenizer(args)
    if args.audit_lengths:
        _audit_lengths(args, tokenizer)
        return 0
    if args.preflight:
        print("[preflight] done; no model loaded")
        return 0

    data_file, rows = _data_files(args.data)
    train_ds, eval_ds = _load_dataset(args, tokenizer)
    print(f"[data] train={len(train_ds)} val={len(eval_ds) if eval_ds is not None else 0}")

    model = _load_model(args)
    model = _attach_lora(args, model)

    if args.smoke:
        args.max_steps = 20
        args.epochs = 1
        args.logging_steps = 1
        args.save_steps = 20
        if not args.output.rstrip("/\\").endswith("_smoke"):
            args.output = args.output.rstrip("/\\") + "_smoke"
        print(f"[smoke] max_steps={args.max_steps} output={args.output}")

    trainer = _make_trainer(args, model, tokenizer, train_ds, eval_ds, [VramLogger()])
    spe = math.ceil(len(train_ds) / max(1, args.batch * args.grad_accum))
    print(f"[plan] steps/epoch={spe} total~{spe * float(args.epochs):.0f} "
          f"effective_batch={args.batch * args.grad_accum} "
          f"(budget check: at 8 s/step that is {spe * args.epochs * 8 / 3600:.2f} h)")
    if args.max_len < 5012:
        print(f"[warn] --max-len {args.max_len} truncates the tail of the corpus; "
              "run --audit-lengths to count exactly how many rows lose their answer")
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    try:
        trainer.train(resume_from_checkpoint=args.resume or None)
    except torch.cuda.OutOfMemoryError as exc:
        raise SystemExit(
            "[FATAL] CUDA OOM. Retry in this order: 1) --max-len 3072, 2) --batch 1 "
            "(keep --grad-accum so the effective batch stays 32), 3) --load-4bit. "
            "Do not raise --batch above 2 on a 48GB card.") from exc
    wall = time.time() - t0
    print(f"[done] wall={wall:.1f}s peak_vram={torch.cuda.max_memory_allocated() / 1e9:.2f}G")

    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    _write_receipt(args, trainer, data_file, rows, train_ds, eval_ds, gpu_name, wall)
    print(f"[merge] python scripts/merge_numpy.py --base {args.base} "
          f"--out checkpoints/virtu_hardened_v1 --mode delta "
          f"--lora {args.output} --weight 1.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
