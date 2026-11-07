#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""train_dpo.py — 阶段 2：偏好优化（DPO），把"物理合规且最快"压过"违规/更慢/瞎猜"。

为什么手写 DPO 而不引入 trl：
  * 工作区 peft 版本在 0.13.2 / 0.14 / 0.21.2 / 0.28 之间漂移，
    add_weighted_adapter 与 Trainer 子类语义不一致；trl 会再叠一层版本耦合。
  * 本实现只用 transformers + peft 的公开 API，且用
    `with model.disable_adapter():` 复用同一份 4bit 基座得到 reference logp，
    无需再加载一份基座（显存减半），这是 PEFT 官方推荐的 LoRA-DPO 做法。

损失：
  L = -logsigmoid( beta * ( (logp_pi_chosen - logp_ref_chosen)
                            - (logp_pi_rejected - logp_ref_rejected) ) )
  logp 为 completion 段的平均 token log-prob（prompt 段 mask 为 -100）。

输入：dpo_pairs.jsonl，每行 {prompt:[messages], chosen:str, rejected:str, category:str}
输出：adapter + training_receipt.json（SMOKE_ONLY 的 receipt 不得进入合并流程）

用法：
  python train_dpo.py --smoke            # 2 步快速验链路，产 SMOKE_ONLY receipt
  python train_dpo.py                   # 正式训练
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ect_common import (atomic_write_json, iter_jsonl, load_config, log, now_iso,
                        resolve, seed_everything, sha256_file, verify_manifest)


def _import_stack():
    try:
        import torch
        import torch.nn.functional as F
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel, prepare_model_for_kbit_training
    except ImportError as exc:
        raise SystemExit(f"[train_dpo] 缺少训练依赖: {exc}") from exc
    return locals()


def encode_completion(tokenizer, prompt_text: str, completion: str,
                      max_length: int, max_prompt_length: int):
    """拼 prompt + completion；label 只在 completion 段，prompt 段 -100。"""
    p_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
    if len(p_ids) > max_prompt_length:
        p_ids = p_ids[:max_prompt_length]  # 保留开头的 system，丢过长的中间内容
    im_end = "<|im_end|>"
    c_ids = tokenizer(completion + im_end, add_special_tokens=False)["input_ids"]
    budget = max(1, max_length - len(p_ids))
    c_ids = c_ids[:budget]
    ids = p_ids + c_ids
    labels = [-100] * len(p_ids) + c_ids
    return ids, labels


def sequence_logp(model, input_ids, labels, device) -> float:
    """completion 段平均 token log-prob（可微）。"""
    import torch
    import torch.nn.functional as F
    ids = torch.tensor([input_ids], dtype=torch.long, device=device)
    lab = torch.tensor([labels], dtype=torch.long, device=device)
    out = model(input_ids=ids, attention_mask=torch.ones_like(ids))
    logits = out.logits[:, :-1, :]
    shift = lab[:, 1:]
    mask = shift != -100
    safe = shift.clamp(min=0)
    logp = torch.log_softmax(logits.float(), dim=-1).gather(
        -1, safe.unsqueeze(-1)).squeeze(-1)
    denom = mask.sum().clamp(min=1)
    return (logp * mask).sum() / denom


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力训练 - 阶段2 DPO")
    ap.add_argument("--base", default=None)
    ap.add_argument("--sft-adapter", default=None)
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--profile", default="auto")
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--smoke", action="store_true", help="只跑 2 步，产 SMOKE_ONLY receipt")
    ap.add_argument("--max-steps", type=int, default=0)
    args = ap.parse_args()

    cfg = load_config("pipeline")
    train_cfg = load_config("train")
    dpo = train_cfg["dpo"]
    seed = args.seed if args.seed is not None else int(cfg["seed"])
    seed_everything(seed)
    base = args.base or os.environ.get(cfg["base_model_env"]) or cfg["base_model"]
    sft_adapter = resolve(args.sft_adapter or cfg["paths"]["adapter_out"])
    data_p = resolve(args.data or cfg["paths"]["dpo_out"])
    out = resolve(args.out or cfg["paths"]["dpo_adapter_out"])
    out.mkdir(parents=True, exist_ok=True)

    if not sft_adapter.is_dir() or not (sft_adapter / "adapter_config.json").is_file():
        raise SystemExit(f"缺少阶段1 SFT adapter: {sft_adapter}，请先运行 train_sft.py")
    sft_receipt_p = sft_adapter / "training_receipt.json"
    if sft_receipt_p.is_file():
        r = json.loads(sft_receipt_p.read_text(encoding="utf-8"))
        if r.get("status") != "COMPLETED":
            raise SystemExit(f"阶段1 receipt 非 COMPLETED ({r.get('status')})，拒绝在其上做 DPO")
        lora_r = r.get("lora_r")
        if lora_r is not None and int(lora_r) != int(train_cfg["sft"]["lora_r"]):
            raise SystemExit("SFT adapter 的 lora_r 与当前配置不一致，合并会失败")
    if not data_p.is_file():
        raise SystemExit(f"缺少 DPO 数据: {data_p}，请先运行 01_prepare_data.py")
    chk = verify_manifest(resolve(cfg["paths"]["manifest_out"]))
    if not chk["ok"]:
        raise SystemExit(f"语料 manifest 校验失败: {chk['mismatches']}")

    st = _import_stack()
    torch = st["torch"]
    F = st["F"]
    if not torch.cuda.is_available():
        raise SystemExit("[train_dpo] DPO 需要 CUDA；本地无 GPU 时请只做 --smoke 链路检查")
    major, _ = torch.cuda.get_device_capability(0)
    dtype = torch.bfloat16 if major >= 8 else torch.float16
    device = "cuda:0"

    tokenizer = st["AutoTokenizer"].from_pretrained(base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    bnb = st["BitsAndBytesConfig"](
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True)
    model = st["AutoModelForCausalLM"].from_pretrained(
        base, torch_dtype=dtype, quantization_config=bnb,
        device_map={"": 0}, trust_remote_code=True)
    model = st["prepare_model_for_kbit_training"](model)
    model = st["PeftModel"].from_pretrained(model, str(sft_adapter), is_trainable=True)
    model.train()

    pairs = list(iter_jsonl(data_p))
    if args.smoke:
        pairs = pairs[:2]
    if not pairs:
        raise SystemExit("DPO 数据为空")
    log("train_dpo", f"pairs={len(pairs)} beta={args.beta or dpo['beta']} "
                     f"lr={args.lr or dpo['learning_rate']} base={base}")

    epochs = args.epochs if args.epochs is not None else int(dpo["num_train_epochs"])
    beta = args.beta if args.beta is not None else float(dpo["beta"])
    lr = args.lr if args.lr is not None else float(dpo["learning_rate"])
    max_length = int(dpo["max_length"])
    max_prompt = int(dpo["max_prompt_length"])
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.0)
    total_steps = len(pairs) * epochs
    if args.max_steps:
        total_steps = min(total_steps, args.max_steps)
    if args.smoke:
        total_steps = min(total_steps, 2)
    warmup = max(1, int(total_steps * float(dpo["warmup_ratio"])))

    def lr_at(step: int) -> float:
        if step < warmup:
            return lr * (step + 1) / warmup
        prog = (step - warmup) / max(1, total_steps - warmup)
        return lr * 0.5 * (1.0 + math.cos(math.pi * min(1.0, prog)))

    t0 = time.time()
    step = 0
    losses: List[float] = []
    skipped = 0
    try:
        for ep in range(epochs):
            for i, pair in enumerate(pairs):
                if step >= total_steps:
                    break
                for g in opt.param_groups:
                    g["lr"] = lr_at(step)
                try:
                    prompt_text = tokenizer.apply_chat_template(
                        pair["prompt"], tokenize=False, add_generation_prompt=True)
                except Exception:
                    skipped += 1
                    continue
                enc_c = encode_completion(tokenizer, prompt_text, pair["chosen"],
                                          max_length, max_prompt)
                enc_r = encode_completion(tokenizer, prompt_text, pair["rejected"],
                                          max_length, max_prompt)
                # policy 侧：chosen / rejected 都要梯度
                pi_c = sequence_logp(model, *enc_c, device)
                pi_r = sequence_logp(model, *enc_r, device)
                # reference 侧：关掉 adapter 即得到基座，无需第二份权重
                with torch.no_grad(), model.disable_adapter():
                    ref_c = sequence_logp(model, *enc_c, device)
                    ref_r = sequence_logp(model, *enc_r, device)
                logits = beta * ((pi_c - ref_c) - (pi_r - ref_r))
                loss = -F.logsigmoid(logits)
                if not torch.isfinite(loss):
                    skipped += 1
                    opt.zero_grad(set_to_none=True)
                    continue
                loss.backward()
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                losses.append(float(loss.detach().cpu()))
                step += 1
                if step % 10 == 0 or step == 1:
                    log("train_dpo", f"step {step}/{total_steps} loss={losses[-1]:.4f} "
                                     f"lr={lr_at(step - 1):.2e}")
    except Exception as exc:  # noqa: BLE001
        atomic_write_json(out / "training_receipt.json", {
            "status": "FAILED", "stage": "dpo", "error": repr(exc),
            "steps_done": step, "runtime_seconds": round(time.time() - t0, 2),
            "created_at": now_iso()})
        log("train_dpo", f"FAILED: {exc!r}")
        raise

    model.save_pretrained(str(out))
    tokenizer.save_pretrained(str(out))
    receipt = {
        "status": "SMOKE_ONLY" if args.smoke else "COMPLETED",
        "stage": "dpo", "base": base, "sft_adapter": str(sft_adapter),
        "data": str(data_p), "data_sha256": sha256_file(data_p),
        "pairs_total": len(list(iter_jsonl(data_p))), "pairs_used": len(pairs),
        "steps": step, "skipped": skipped, "beta": beta, "learning_rate": lr,
        "epochs": epochs, "max_length": max_length, "seed": seed,
        "reference_mode": dpo["reference_mode"], "loss_type": dpo["loss_type"],
        "loss_mean": round(sum(losses) / len(losses), 6) if losses else None,
        "loss_first": round(losses[0], 6) if losses else None,
        "loss_last": round(losses[-1], 6) if losses else None,
        "runtime_seconds": round(time.time() - t0, 2),
        "adapter_dir": str(out), "created_at": now_iso(),
        "note": "SMOKE_ONLY 产物禁止进入合并/上线流程" if args.smoke else
                "只产 adapter；合并一律用 delta/TIES，禁用 peft_linear",
    }
    atomic_write_json(out / "training_receipt.json", receipt)
    log("train_dpo", f"{receipt['status']} steps={step} loss={receipt['loss_mean']} -> {out}")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
