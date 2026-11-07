#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""train_sft.py — 阶段 1：工程能力 SFT（Qwen3-8B QLoRA, r=32/alpha=64）。

与工作区既有资产的关系：
  * loss mask 复用 scripts/virtu_tokenize.py::build_example（官方 apply_chat_template
    + 整条渲染 + offset_mapping 字符级定位 + assistant-only 掩码）。
    绝不手写 ChatML 前缀拼接（Qwen3 的 <think> 规则会让 startswith 假设失效）。
  * --engine legacy 直接调用 scripts/train_qwen3_8b_qlora.py（v2/v3 实跑过的引擎）。
  * 超参、精度策略、profile 全部来自 configs/train.json，命令行只做覆盖并记入 receipt。

硬约束：
  * r=32 / alpha=64：与工作区 7 个同源 LoRA 保持 rank 一致，否则无法 delta/TIES 合并
  * 4bit NF4 + double quant；V100(sm70) 用 fp16，Ampere+ 用 bf16
  * 开训前必须 manifest sha256 校验通过，且训练目录恰好 1 个 jsonl
  * 只产 adapter，不合并（合并/GGUF 在本机做，GPU 机只负责训练）

用法：
  python train_sft.py --selftest                       # 只验分词与掩码，不占显存
  python train_sft.py --profile l40s_48g              # 正式开训
  python train_sft.py --profile v100_32g --engine legacy
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ect_common import (PACKAGE_DIR, atomic_write_json, iter_jsonl, load_config,
                        load_workspace_module, log, now_iso, repo_root, resolve,
                        seed_everything, sha256_file, verify_manifest)
from _ect_rowcheck import assistant_text

TARGET_MODULES_DEFAULT = ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"]


def _import_train_stack():
    """延迟导入重型依赖，保证 --help / 配置检查在无 GPU 机器上也能运行。"""
    try:
        import torch
        from transformers import (AutoModelForCausalLM, AutoTokenizer,
                                  TrainingArguments, Trainer,
                                  DataCollatorForSeq2Seq, set_seed,
                                  BitsAndBytesConfig)
        from peft import (LoraConfig, get_peft_model, TaskType,
                          prepare_model_for_kbit_training, PeftModel)
        from datasets import Dataset
    except ImportError as exc:
        raise SystemExit(
            f"[train_sft] 缺少训练依赖: {exc}\n"
            "请在云端执行: pip install -r engineering_capability_train/requirements-cloud.txt"
        ) from exc
    return {
        "torch": torch, "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer, "TrainingArguments": TrainingArguments,
        "Trainer": Trainer, "DataCollatorForSeq2Seq": DataCollatorForSeq2Seq,
        "set_seed": set_seed, "BitsAndBytesConfig": BitsAndBytesConfig,
        "LoraConfig": LoraConfig, "get_peft_model": get_peft_model,
        "TaskType": TaskType, "prepare_model_for_kbit_training": prepare_model_for_kbit_training,
        "PeftModel": PeftModel, "Dataset": Dataset,
    }


def pick_precision(torch) -> tuple:
    """按算力选精度：V100(sm70)/T4 无 bf16 Tensor Core，必须 fp16。"""
    if not torch.cuda.is_available():
        return "fp16", torch.float16
    major, _ = torch.cuda.get_device_capability(0)
    return ("bf16", torch.bfloat16) if major >= 8 else ("fp16", torch.float16)


def resolve_profile(train_cfg: Dict[str, Any], name: Optional[str], torch=None) -> Dict[str, Any]:
    if name and name != "auto":
        if name not in train_cfg["profiles"]:
            raise SystemExit(f"未知 profile {name}，可选 {list(train_cfg['profiles'])}")
        return dict(train_cfg["profiles"][name], name=name)
    if torch is not None and torch.cuda.is_available():
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        major, _ = torch.cuda.get_device_capability(0)
        if major < 8:
            name = "v100_32g"
        elif total_gb >= 70:
            name = "a100_80g"
        else:
            name = "l40s_48g"
    else:
        name = train_cfg["default_profile"]
    return dict(train_cfg["profiles"][name], name=name)


def build_examples(corpus: Path, tokenizer, helper, max_len: int,
                   limit: Optional[int] = None):
    """返回 (samples, diagnostics)。"""
    """整条渲染 + assistant-only 掩码；逐条记录截断与 loss 段，便于体检。"""
    out: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    for i, row in enumerate(iter_jsonl(corpus)):
        if limit and i >= limit:
            break
        msgs = row.get("messages")
        if not msgs:
            continue
        try:
            ids, labels, meta = helper.build_example(
                msgs, row.get("tools") or [], tokenizer, max_length=max_len)
        except Exception as exc:  # noqa: BLE001
            diagnostics.append({"line": i + 1, "error": repr(exc)})
            continue
        if meta["n_loss"] <= 0:
            diagnostics.append({"line": i + 1, "error": "no assistant loss tokens"})
            continue
        out.append({"input_ids": ids, "labels": labels,
                    "attention_mask": [1] * len(ids)})
        diagnostics.append({"line": i + 1, **meta})
    return out, diagnostics


def selftest(cfg: Dict[str, Any], train_cfg: Dict[str, Any], args) -> int:
    """分词/掩码/截断率体检：只需要 tokenizer，不需要 torch / peft / GPU。

    这样无 CUDA 的本机也能在上传语料前完成与云端完全同构的预检，
    避免把"分词错位 / 大量截断"这类问题带到付费 GPU 机上才发现。
    """
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            f"[train_sft] --selftest 需要 transformers（仅 tokenizer）：{exc}\n"
            "pip install transformers tokenizers"
        ) from exc
    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    helper = load_workspace_module("scripts/virtu_tokenize.py")
    corpus = resolve(cfg["paths"]["corpus_out"])
    limit = None if args.selftest_limit == 0 else args.selftest_limit
    rows, diag = build_examples(corpus, tokenizer, helper, args.max_len, limit=limit)
    bad = [d for d in diag if d.get("error")]
    trunc = [d for d in diag if d.get("truncated")]
    ratios = [d["loss_ratio"] for d in diag if "loss_ratio" in d]
    toks = sorted(d["n_tok"] for d in diag if "n_tok" in d)
    trunc_rate = len(trunc) / max(1, len(diag))
    warnings = []
    if trunc_rate > 0.05:
        warnings.append(f"截断率 {trunc_rate:.1%} > 5%，建议提高 max_seq_len 或精简长样本")
    if ratios and min(ratios) < 0.01:
        warnings.append("存在 loss 占比 <1% 的样本，检查 assistant 段是否被 mask 吃掉")
    print(json.dumps({
        "selftest": "PASS" if rows and not bad else "FAIL",
        "base": args.base, "corpus": str(corpus),
        "corpus_sha256": sha256_file(corpus),
        "max_len": args.max_len, "checked_rows": len(diag), "usable": len(rows),
        "bad": bad[:5], "truncated": len(trunc),
        "truncated_rate": round(trunc_rate, 4),
        "loss_ratio_mean": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "loss_ratio_min": round(min(ratios), 4) if ratios else None,
        "tokens_max": toks[-1] if toks else 0,
        "tokens_p99": toks[min(len(toks) - 1, int(len(toks) * 0.99))] if toks else 0,
        "mask_helper": "scripts/virtu_tokenize.py::build_example",
        "requires_gpu": False, "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if rows and not bad else 1


def write_receipt(path: Path, data: Dict[str, Any]) -> None:
    atomic_write_json(path, data)


def run_legacy(cfg: Dict[str, Any], train_cfg: Dict[str, Any], args,
               profile: Dict[str, Any]) -> int:
    """回退到工作区已实跑过的 train_qwen3_8b_qlora.py（不重写训练器原则）。"""
    script = resolve(train_cfg["sft"]["engine_legacy_entry"])
    if not script.is_file():
        raise SystemExit(f"legacy engine missing: {script}")
    sft = train_cfg["sft"]
    cmd = [sys.executable, str(script),
           "--base", args.base,
           "--data", str(resolve(cfg["paths"]["corpus_out"])),
           "--out", str(resolve(cfg["paths"]["adapter_out"])),
           "--lora_r", str(sft["lora_r"]), "--lora_alpha", str(sft["lora_alpha"]),
           "--lora_dropout", str(sft["lora_dropout"]),
           "--lr", str(args.lr or sft["learning_rate"]),
           "--epochs", str(args.epochs or sft["num_train_epochs"]),
           "--bs", str(profile["per_device_train_batch_size"]),
           "--accum", str(profile["gradient_accumulation_steps"]),
           "--max_len", str(args.max_len or profile["max_seq_len"]),
           "--seed", str(args.seed)]
    if args.extra:
        cmd += args.extra.split()
    log("train_sft", "legacy engine: " + " ".join(cmd))
    return subprocess.call(cmd, cwd=str(repo_root()))


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力训练 - 阶段1 SFT")
    ap.add_argument("--base", default=None, help="基座路径/HF id，缺省读 VIRTU_BASE")
    ap.add_argument("--profile", default="auto", help="v100_32g / l40s_48g / a100_80g / auto")
    ap.add_argument("--engine", default="native", choices=["native", "legacy"])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--selftest-limit", type=int, default=1000,
                    dest="selftest_limit", help="分词自检样本数，0=全量")
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--max-len", type=int, default=None, dest="max_len")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--resume-adapter", default=None)
    ap.add_argument("--extra", default="", help="legacy 引擎附加参数")
    ap.add_argument("--skip-manifest-check", action="store_true")
    args = ap.parse_args()

    cfg = load_config("pipeline")
    train_cfg = load_config("train")
    seed = args.seed if args.seed is not None else int(cfg["seed"])
    seed_everything(seed)
    args.seed = seed
    args.base = args.base or os.environ.get(cfg["base_model_env"]) or cfg["base_model"]
    if not args.max_len:
        args.max_len = int(cfg["max_seq_len"])

    corpus = resolve(cfg["paths"]["corpus_out"])
    manifest = resolve(cfg["paths"]["manifest_out"])
    if not corpus.is_file():
        raise SystemExit(f"缺少训练语料，请先运行 01_prepare_data.py: {corpus}")
    if not args.skip_manifest_check:
        chk = verify_manifest(manifest)
        if not chk["ok"]:
            raise SystemExit(f"语料 manifest 校验失败，拒绝开训: {chk['mismatches']}")
        log("train_sft", f"manifest OK ({chk['checked']} files)")

    st = _import_train_stack() if not args.selftest else None
    profile = resolve_profile(train_cfg, args.profile,
                              st["torch"] if st else None)
    if args.selftest:
        return selftest(cfg, train_cfg, args)
    if args.engine == "legacy":
        return run_legacy(cfg, train_cfg, args, profile)

    torch = st["torch"]
    sft = train_cfg["sft"]
    lr = args.lr if args.lr is not None else float(sft["learning_rate"])
    epochs = args.epochs if args.epochs is not None else int(sft["num_train_epochs"])
    max_len = args.max_len or int(profile["max_seq_len"])
    out = resolve(cfg["paths"]["adapter_out"])
    out.mkdir(parents=True, exist_ok=True)

    log("train_sft", f"base={args.base} profile={profile['name']} "
                     f"lr={lr} epochs={epochs} max_len={max_len} seed={seed}")
    tokenizer = st["AutoTokenizer"].from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    helper = load_workspace_module("scripts/virtu_tokenize.py")

    rows, diag = build_examples(corpus, tokenizer, helper, max_len)
    bad = [d for d in diag if d.get("error")]
    trunc = sum(1 for d in diag if d.get("truncated"))
    if bad:
        raise SystemExit(f"语料分词自检失败 {len(bad)} 条，示例: {bad[:3]}")
    log("train_sft", f"usable={len(rows)} truncated={trunc} "
                     f"({trunc / max(1, len(rows)):.1%})")
    if trunc / max(1, len(rows)) > 0.05:
        log("train_sft", "[WARN] 截断率 >5%，建议提高 max_seq_len 或精简长样本")

    prec_name, prec_dtype = pick_precision(torch)
    use_bf16 = profile.get("bf16", prec_name == "bf16") and prec_name == "bf16"
    use_fp16 = not use_bf16
    bnb = st["BitsAndBytesConfig"](
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=prec_dtype, bnb_4bit_use_double_quant=True)
    model = st["AutoModelForCausalLM"].from_pretrained(
        args.base, torch_dtype=prec_dtype, quantization_config=bnb,
        device_map="auto", trust_remote_code=True)
    model = st["prepare_model_for_kbit_training"](model)

    if args.resume_adapter:
        model = st["PeftModel"].from_pretrained(model, args.resume_adapter)
        log("train_sft", f"从已有 adapter 续训: {args.resume_adapter}")
    else:
        lora = st["LoraConfig"](
            r=sft["lora_r"], lora_alpha=sft["lora_alpha"],
            lora_dropout=sft["lora_dropout"],
            target_modules=sft["target_modules"] or TARGET_MODULES_DEFAULT,
            bias="none", task_type=st["TaskType"].CAUSAL_LM)
        model = st["get_peft_model"](model, lora)
    model.print_trainable_parameters()

    ds = st["Dataset"].from_list(rows)
    split = ds.train_test_split(test_size=sft["val_ratio"], seed=seed)
    targs = st["TrainingArguments"](
        output_dir=str(out),
        per_device_train_batch_size=profile["per_device_train_batch_size"],
        gradient_accumulation_steps=profile["gradient_accumulation_steps"],
        learning_rate=lr, lr_scheduler_type=sft["lr_scheduler_type"],
        warmup_ratio=sft["warmup_ratio"], weight_decay=sft["weight_decay"],
        num_train_epochs=epochs, max_grad_norm=sft["max_grad_norm"],
        logging_steps=sft["logging_steps"], save_strategy="steps",
        save_steps=sft["save_steps"], save_total_limit=sft["save_total_limit"],
        bf16=use_bf16, fp16=use_fp16,
        gradient_checkpointing=profile["gradient_checkpointing"],
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim=profile["optim"], report_to="none",
        group_by_length=sft["group_by_length"],
        dataloader_num_workers=2, seed=seed,
    )
    collator = st["DataCollatorForSeq2Seq"](
        tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True)
    trainer = st["Trainer"](model=model, args=targs,
                            train_dataset=split["train"], eval_dataset=split["test"],
                            data_collator=collator)
    ckpts = sorted(out.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
    resume = str(ckpts[-1]) if ckpts else None

    t0 = time.time()
    try:
        result = trainer.train(resume_from_checkpoint=resume)
        elapsed = time.time() - t0
        train_loss = float(result.training_loss)
    except Exception as exc:  # noqa: BLE001
        write_receipt(out / "training_receipt.json", {
            "status": "FAILED", "stage": "sft", "error": repr(exc),
            "runtime_seconds": round(time.time() - t0, 2), "base": args.base,
            "created_at": now_iso()})
        log("train_sft", f"FAILED: {exc!r}")
        raise

    model.save_pretrained(str(out))
    tokenizer.save_pretrained(str(out))
    receipt = {
        "status": "COMPLETED", "stage": "sft", "engine": "native",
        "base": args.base, "profile": profile["name"],
        "corpus": str(corpus), "corpus_sha256": sha256_file(corpus),
        "num_samples": len(rows), "truncated_samples": trunc,
        "lora_r": sft["lora_r"], "lora_alpha": sft["lora_alpha"],
        "target_modules": sft["target_modules"],
        "learning_rate": lr, "epochs": epochs, "max_seq_len": max_len,
        "seed": seed, "precision": prec_name,
        "per_device_batch": profile["per_device_train_batch_size"],
        "grad_accum": profile["gradient_accumulation_steps"],
        "global_step": trainer.state.global_step, "train_loss": train_loss,
        "runtime_seconds": round(elapsed, 2),
        "gpus": [torch.cuda.get_device_name(i)
                 for i in range(torch.cuda.device_count())],
        "mask_helper": "scripts/virtu_tokenize.py::build_example",
        "adapter_dir": str(out), "created_at": now_iso(),
    }
    write_receipt(out / "training_receipt.json", receipt)
    log("train_sft", f"COMPLETED loss={train_loss:.4f} step={trainer.state.global_step} "
                     f"elapsed={elapsed:.1f}s -> {out}")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
