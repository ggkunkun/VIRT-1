#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/train_dpo_cloud.py — Virtu 世界模型「反幻觉」云端 DPO 训练引擎
===================================================================================
目标：用 132 条「带标签错误」偏好对（build_dpo_dataset.py 产出）做 DPO 回灌，
让模型学会「在给定物理 prompt 时，输出正确的 world_state 而非幻觉数值」。

与 train_turnkey.py（SFT）的关系：
  - 复用其云端约定：base 路径自动探测、显存分档（>=36GB bf16-LoRA / <36GB QLoRA 4-bit）、
    TARGET_MODULES、assistant 段掩码思想、deliverable 打包。
  - 差异：训练目标是「偏好」而非「模仿」。DPO 不需要逐 token 标签，直接用
    (prompt, chosen=正确 world_state, rejected=错误 world_state) 三元组。
  - 继承能力：--resume-adapter 加载 v3 adapter 并 merge 进 base，再在其上训练新 LoRA，
    避免 DPO 把已学会的能力冲掉（ catastrophic forgetting 防护）。

云端执行（run_dpo.sh 会处理依赖与启动）：
  python train_dpo_cloud.py --data dataset/dpo_phys_rejects.jsonl \
      --out output/virtu_dpo_antihallu --epochs 2 --lr 5e-6 --beta 0.1

环境变量覆盖（与 train_turnkey 一致）：
  BASE / DATA / OUT / LR / EPOCHS / BS / ACCUM / MAX_LEN / SEED / RESUME_ADAPTER /
  WANDB_PROJECT / PUSH_TO / GPU_ID
"""
from __future__ import annotations

import os
import sys
import json
import time
import glob
import shutil
import tarfile
import hashlib
import argparse

# 锁定单卡（必须在 import torch 之前）
if "--gpu-id" in sys.argv:
    _i = sys.argv.index("--gpu-id")
    os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[_i + 1]
else:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model, PeftModel, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

# ---- 与 train_turnkey 对齐的约定 -------------------------------------------
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]
CANDIDATE_BASE_PATHS = [
    "/root/workspace/models/Qwen3-8B-Instruct",
    "/root/models/Qwen3-8B-Instruct",
    "/root/public-storage/model/Qwen/Qwen3-8B-Instruct",
    "checkpoints/_base_qwen3_8b",
    "./models/Qwen3-8B-Instruct",
]
CANDIDATE_DATA_FILES = [
    "dataset/dpo_phys_rejects.jsonl",
    "dataset/dpo_antihallucination.jsonl",
]


def _best_storage_dir() -> str:
    cands = ["/root/workspace", "/root/data", "/root/damodel-tmp",
             "/root/autodl-tmp", "/mnt/data", "/mnt", "/root", "."]
    best, mx = ".", 0.0
    for c in cands:
        if os.path.exists(c):
            try:
                free = shutil.disk_usage(c).free / (1024 ** 3)
                if free > mx:
                    mx, best = free, c
            except Exception:
                pass
    return best


def _detect_base() -> str:
    for p in CANDIDATE_BASE_PATHS:
        if os.path.exists(p) and os.path.isdir(p):
            return p
    # 退而求其次：扫描常见父目录
    for parent in ["/root/workspace/models", "/root/models", "/root/public-storage/model/Qwen"]:
        if os.path.isdir(parent):
            hits = sorted(glob.glob(os.path.join(parent, "*Qwen3-8B*")))
            if hits:
                return hits[0]
    raise FileNotFoundError("未找到 Qwen3-8B 基座，请在云端实例确认模型已挂载到 CANDIDATE_BASE_PATHS 之一")


def _detect_data() -> str:
    for f in CANDIDATE_DATA_FILES:
        if os.path.exists(f):
            return f
    raise FileNotFoundError("未找到 DPO 数据集，请先运行 build_dpo_dataset.py 生成")


def _gpu_mem_gb() -> float:
    try:
        out = torch.cuda.get_device_properties(0).total_memory
        return out / (1024 ** 3)
    except Exception:
        return 0.0


def _fingerprint(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("DATA", ""))
    ap.add_argument("--out", default=os.environ.get("OUT", "output/virtu_dpo_antihallu"))
    ap.add_argument("--base", default=os.environ.get("BASE", ""))
    ap.add_argument("--resume-adapter", default=os.environ.get("RESUME_ADAPTER", ""),
                    help="v3 adapter 路径，merge 进 base 后再 DPO（继承能力，防遗忘）")
    ap.add_argument("--epochs", type=float, default=float(os.environ.get("EPOCHS", "2.0")))
    ap.add_argument("--lr", type=float, default=float(os.environ.get("LR", "5e-6")), help="DPO 学习率通常比 SFT 小一个量级")
    ap.add_argument("--beta", type=float, default=0.1, help="DPO 偏好强度")
    ap.add_argument("--batch", type=int, default=int(os.environ.get("BS", "2")))
    ap.add_argument("--grad-accum", type=int, default=int(os.environ.get("ACCUM", "8")))
    ap.add_argument("--max-length", type=int, default=int(os.environ.get("MAX_LEN", "1536")))
    ap.add_argument("--lora-r", type=int, default=int(os.environ.get("LORA_R", "16")))
    ap.add_argument("--lora-alpha", type=int, default=int(os.environ.get("LORA_ALPHA", "32")))
    ap.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "42")))
    ap.add_argument("--max-hours", type=float, default=1.5, help="超时自动保存退出（云端按机时计费）")
    ap.add_argument("--wandb-project", default=os.environ.get("WANDB_PROJECT", ""))
    ap.add_argument("--push-to", default=os.environ.get("PUSH_TO", ""),
                    help="训练完把 deliverable 拷贝到该目录（云盘/对象存储挂载点）")
    args = ap.parse_args()

    set_seed(args.seed)
    base = args.base or _detect_base()
    data = args.data or _detect_data()
    print(f"[DPO] base={base}\n[DPO] data={data}\n[DPO] out={args.out}\n"
          f"[DPO] epochs={args.epochs} lr={args.lr} beta={args.beta} "
          f"bs={args.batch} accum={args.grad_accum} lora_r={args.lora_r}")

    # ---- 1) 载入数据集 -----------------------------------------------------
    samples = []
    with open(data, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("prompt") and d.get("chosen") and d.get("rejected"):
                samples.append(d)
    print(f"[DPO] 载入偏好对 {len(samples)} 条")
    assert samples, "数据集为空，请检查 build_dpo_dataset.py 产物"
    ds = Dataset.from_list(samples)

    # ---- 2) 载入基座 + 显存分档 ------------------------------------------
    mem = _gpu_mem_gb()
    use_4bit = mem > 0 and mem < 36
    print(f"[DPO] 显存 {mem:.1f}GB -> {'QLoRA 4-bit' if use_4bit else 'bf16 LoRA'}")
    quant = {}
    if use_4bit:
        from transformers import BitsAndBytesConfig
        quant = {"quantization_config": BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True)}
    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=torch.bfloat16 if not use_4bit else torch.float32,
        attn_implementation="sdpa", **quant)
    if use_4bit:
        model = prepare_model_for_kbit_training(model)

    # 继承 v3 能力：merge 进 base 再训新 LoRA
    if args.resume_adapter and os.path.exists(args.resume_adapter):
        print(f"[DPO] 继承能力：merge resume-adapter={args.resume_adapter}")
        model = PeftModel.from_pretrained(model, args.resume_adapter)
        model = model.merge_and_unload()

    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ---- 3) 套 LoRA ------------------------------------------------------
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r, lora_alpha=args.lora_alpha,
        lora_dropout=0.05, target_modules=TARGET_MODULES,
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # ---- 4) DPO 训练 -----------------------------------------------------
    if args.wandb_project:
        os.environ["WANDB_PROJECT"] = args.wandb_project
        os.environ["WANDB_MODE"] = os.environ.get("WANDB_MODE", "online")

    try:
        from trl import DPOTrainer, DPOConfig
        dpo_args = DPOConfig(
            output_dir=args.out,
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            beta=args.beta,
            max_length=args.max_length,
            max_prompt_length=args.max_length // 2,
            bf16=not use_4bit,
            logging_steps=5,
            save_strategy="no",
            report_to="wandb" if args.wandb_project else "none",
            seed=args.seed,
            optim="adamw_torch",
        )
        trainer = DPOTrainer(
            model=model, ref_model=None,  # ref_model=None 时自动用 base 副本作参考
            args=dpo_args, train_dataset=ds, tokenizer=tokenizer,
        )
    except ImportError:
        # 老版本 trl 回退
        from trl import DPOTrainer
        from transformers import TrainingArguments
        dpo_args = TrainingArguments(
            output_dir=args.out,
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            bf16=not use_4bit,
            logging_steps=5,
            save_strategy="no",
            report_to="wandb" if args.wandb_project else "none",
            seed=args.seed,
        )
        trainer = DPOTrainer(
            model=model, train_dataset=ds, tokenizer=tokenizer,
            args=dpo_args, beta=args.beta, max_length=args.max_length,
            max_prompt_length=args.max_length // 2,
        )
    print("[DPO] 开始训练 ...")
    t0 = time.time()
    trainer.train()
    print(f"[DPO] 训练完成，耗时 {time.time()-t0:.1f}s")

    # ---- 5) 保存 + 打包 deliverable --------------------------------------
    os.makedirs(args.out, exist_ok=True)
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    # 指纹凭证
    fp = _fingerprint(data)
    meta = {
        "type": "virtu_dpo_antihallucination",
        "base": base,
        "resume_adapter": args.resume_adapter,
        "n_pairs": len(samples),
        "epochs": args.epochs, "lr": args.lr, "beta": args.beta,
        "lora_r": args.lora_r, "lora_alpha": args.lora_alpha,
        "data_fingerprint": fp, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(args.out, "dpo_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    tar_path = os.path.join(args.out, "virtu_dpo_deliverable.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in ["adapter_model", "adapter_config.json", "tokenizer",
                     "dpo_metadata.json"]:
            full = os.path.join(args.out, name)
            if os.path.exists(full):
                tar.add(full, arcname=os.path.basename(args.out) + "/" + name)
    print(f"[DPO] deliverable -> {tar_path}")

    if args.push_to:
        dst = os.path.join(args.push_to, os.path.basename(args.out) + "_dpo")
        shutil.copytree(args.out, dst, dirs_exist_ok=True)
        print(f"[DPO] 已拷贝到 PUSH_TO: {dst}")
    print("[DPO] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
