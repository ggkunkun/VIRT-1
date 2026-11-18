#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/train_vericut_dpo.py — 独立云端 DPO 偏好优化脚本 (r=32 / alpha=64)。

延续 train_turnkey.py 产出的 SFT LoRA (必须 r=32, lora_alpha=64)，做低漂移轻量 DPO 对齐。
默认使用冻结 SFT 副本 `sft_ref` (`adapter_name="sft_ref"`) 作为 KL 参考策略（兼容旧版
`--ref-mode base` 禁用适配器对照），配合梯度累积防止过拟合与 Q4_0 量化崩塌。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()


def _verify_dpo_ledger(data_path: Path, ledger_path: Path | None) -> str:
    actual = _sha256_file(data_path)
    if not ledger_path:
        return actual
    meta = json.loads(ledger_path.read_text(encoding="utf-8"))
    bname = data_path.name
    expected = None
    if isinstance(meta.get("files"), dict) and bname in meta["files"]:
        entry = meta["files"][bname]
        expected = entry.get("sha256") if isinstance(entry, dict) else entry
    elif meta.get("output_sha256"):
        expected = meta["output_sha256"]
    if expected and expected.lower() != actual.lower():
        raise SystemExit(f"[FATAL] DPO ledger SHA256 mismatch: expected={expected[:16]} actual={actual[:16]}")
    return actual


def _assert_sft_rank(sft_adapter: Path, expected_r: int = 32, expected_alpha: int = 64) -> dict:
    cfg_p = sft_adapter / "adapter_config.json"
    if not cfg_p.is_file():
        raise SystemExit(f"[FATAL] Missing SFT adapter_config.json: {cfg_p}")
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    if int(cfg.get("r", -1)) != expected_r or int(cfg.get("lora_alpha", -1)) != expected_alpha:
        raise SystemExit(
            f"[FATAL] SFT adapter rank mismatch: r={cfg.get('r')}, alpha={cfg.get('lora_alpha')} "
            f"(expected r={expected_r}, alpha={expected_alpha})"
        )
    receipt_p = sft_adapter / "training_receipt.json"
    if receipt_p.is_file():
        rec = json.loads(receipt_p.read_text(encoding="utf-8"))
        if rec.get("status") not in ("COMPLETED", "TIME_BUDGET_STOPPED"):
            raise SystemExit(f"[FATAL] SFT receipt status not ready for DPO: {rec.get('status')}")
    return cfg


def encode_completion(tokenizer, prompt_text: str, completion: str, max_length: int, max_prompt_length: int):
    p_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
    if len(p_ids) > max_prompt_length:
        p_ids = p_ids[:max_prompt_length]
    c_ids = tokenizer(completion + "<|im_end|>", add_special_tokens=False)["input_ids"]
    c_ids = c_ids[: max(1, max_length - len(p_ids))]
    ids = p_ids + c_ids
    labels = [-100] * len(p_ids) + c_ids
    return ids, labels


def sequence_logp(model, input_ids: List[int], labels: List[int], device: str):
    import torch

    ids = torch.tensor([input_ids], dtype=torch.long, device=device)
    lab = torch.tensor([labels], dtype=torch.long, device=device)
    out = model(input_ids=ids, attention_mask=torch.ones_like(ids))
    logits = out.logits[:, :-1, :]
    shift = lab[:, 1:]
    mask = shift != -100
    safe = shift.clamp(min=0)
    logp = torch.log_softmax(logits.float(), dim=-1).gather(-1, safe.unsqueeze(-1)).squeeze(-1)
    return (logp * mask).sum() / mask.sum().clamp(min=1)


def _select_trainable_params(model) -> List[Any]:
    """Return trainable parameters excluding the frozen `sft_ref` reference adapter."""
    return [
        p for n, p in model.named_parameters()
        if getattr(p, "requires_grad", False) and "sft_ref" not in str(n)
    ]


def run_selftest() -> int:
    """Offline zero-GPU gate check for DPO ledger validation, rank lock, ref isolation, and masking."""
    with tempfile.TemporaryDirectory(prefix="vericut_dpo_selftest_") as td:
        tmp = Path(td)
        dpo_file = tmp / "vericut_e_training_dpo.jsonl"
        dpo_file.write_text('{"prompt":[],"chosen":"ok","rejected":"bad"}\n', encoding="utf-8")
        digest = _sha256_file(dpo_file)
        good_ledger = tmp / "ledger.json"
        good_ledger.write_text(json.dumps({"files": {dpo_file.name: {"sha256": digest}}}), encoding="utf-8")
        assert _verify_dpo_ledger(dpo_file, good_ledger) == digest

        bad_ledger = tmp / "bad_ledger.json"
        bad_ledger.write_text(json.dumps({"files": {dpo_file.name: {"sha256": "0" * 64}}}), encoding="utf-8")
        try:
            _verify_dpo_ledger(dpo_file, bad_ledger)
            raise AssertionError("Bad ledger not rejected")
        except SystemExit:
            pass

        sft_dir = tmp / "sft"
        sft_dir.mkdir()
        (sft_dir / "adapter_config.json").write_text(json.dumps({"r": 32, "lora_alpha": 64}), encoding="utf-8")
        assert _assert_sft_rank(sft_dir)["r"] == 32

        bad_sft = tmp / "bad_sft"
        bad_sft.mkdir()
        (bad_sft / "adapter_config.json").write_text(json.dumps({"r": 16, "lora_alpha": 32}), encoding="utf-8")
        try:
            _assert_sft_rank(bad_sft)
            raise AssertionError("Wrong rank not rejected")
        except SystemExit:
            pass

        class _FakeTok:
            def __call__(self, text, add_special_tokens=False):
                return {"input_ids": [ord(c) for c in text]}

        ids, lab = encode_completion(_FakeTok(), "PROMPT", "ANS", max_length=64, max_prompt_length=32)
        assert lab[:6] == [-100] * 6 and all(x != -100 for x in lab[6:]) and len(ids) == len(lab)

        class _FakeParam:
            def __init__(self, requires_grad: bool):
                self.requires_grad = requires_grad

        class _FakeModel:
            def named_parameters(self):
                return [
                    ("base_model.model.q_proj.lora_A.default.weight", _FakeParam(True)),
                    ("base_model.model.q_proj.lora_A.sft_ref.weight", _FakeParam(True)),
                    ("base_model.model.q_proj.base_layer.weight", _FakeParam(False)),
                ]

        sel = _select_trainable_params(_FakeModel())
        assert len(sel) == 1, f"Expected 1 trainable non-ref param, got {len(sel)}"

        # Fail-closed sanity: SFT dir missing adapter_config must abort
        empty_sft = tmp / "empty_sft"
        empty_sft.mkdir()
        try:
            _assert_sft_rank(empty_sft)
            raise AssertionError("Empty SFT dir not rejected")
        except SystemExit:
            pass

    print("[DPO_SELFTEST] PASS: ledger / rank_r32_alpha64 / sft_ref_filter / prompt_mask / fail_closed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="VERICUT / Six-Software 云端 DPO 对齐训练 (r=32/alpha=64)")
    ap.add_argument("--base", default=None)
    ap.add_argument("--sft-adapter", default="output/vericut_e_training_sft/final_adapter")
    ap.add_argument("--data", default="dataset/vericut_e_training_dpo.jsonl")
    ap.add_argument("--ledger", default="dataset/vericut_e_training_sft_ledger.json")
    ap.add_argument("--out", default="output/vericut_e_training_dpo")
    ap.add_argument("--beta", type=float, default=0.2)
    ap.add_argument("--lr", type=float, default=5e-6)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--ref-mode", choices=("sft", "base"), default="sft")
    ap.add_argument("--max-length", type=int, default=1536)
    ap.add_argument("--max-prompt-length", type=int, default=1024)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--max-hours", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--qlora", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return run_selftest()

    data_p = Path(args.data)
    if not data_p.is_file():
        raise SystemExit(f"[FATAL] Missing DPO dataset: {data_p}")
    ledger_p = Path(args.ledger) if args.ledger and Path(args.ledger).is_file() else None
    data_sha = _verify_dpo_ledger(data_p, ledger_p)

    sft_dir = Path(args.sft_adapter)
    _assert_sft_rank(sft_dir, 32, 64)

    import torch
    import torch.nn.functional as F
    from peft import PeftModel, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    from train_turnkey import assert_base_identity, find_or_download_base  # noqa: E402

    base = find_or_download_base(args.base)
    assert_base_identity(base)
    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] CUDA unavailable for DPO training")

    major, _ = torch.cuda.get_device_capability(0)
    dtype = torch.bfloat16 if major >= 8 else torch.float16
    use_qlora = bool(args.qlora) or (torch.cuda.get_device_properties(0).total_memory / (1024**3) < 22.0)

    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    mkw: Dict[str, Any] = {"trust_remote_code": True, "device_map": {"": 0}, "attn_implementation": "sdpa"}
    if use_qlora:
        mkw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True
        )
    else:
        mkw["torch_dtype"] = dtype

    model = AutoModelForCausalLM.from_pretrained(base, **mkw)
    if hasattr(model, "config"):
        model.config.use_cache = False
    if use_qlora:
        model = prepare_model_for_kbit_training(model)
    else:
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
    model.gradient_checkpointing_enable()
    model = PeftModel.from_pretrained(model, str(sft_dir), adapter_name="default", is_trainable=True)
    if args.ref_mode == "sft":
        model.load_adapter(str(sft_dir), adapter_name="sft_ref", is_trainable=False)
        for pname, param in model.named_parameters():
            if "sft_ref" in str(pname):
                param.requires_grad_(False)
        model.set_adapter("default")
    model.train()

    pairs = [json.loads(ln) for ln in data_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not pairs:
        raise SystemExit(f"[FATAL] Empty DPO dataset: {data_p}")
    params = _select_trainable_params(model)
    if not params:
        raise SystemExit("[FATAL] No trainable parameters found for active DPO adapter")
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    grad_accum = max(1, int(args.grad_accum))
    total_steps = len(pairs) * args.epochs
    if args.max_steps > 0:
        total_steps = min(total_steps, args.max_steps)
    total_opt_steps = max(1, math.ceil(total_steps / grad_accum))
    warmup = max(1, int(total_opt_steps * 0.1))

    def _lr(opt_st: int) -> float:
        if opt_st < warmup:
            return args.lr * (opt_st + 1) / warmup
        prog = (opt_st - warmup) / max(1, total_opt_steps - warmup)
        return args.lr * 0.5 * (1.0 + math.cos(math.pi * min(1.0, prog)))

    t0, step, opt_step, micro_in_accum, skipped = time.time(), 0, 0, 0, 0
    losses, margins = [], []
    time_budget_s = args.max_hours * 3600.0 if args.max_hours > 0 else 0.0
    stopped_by_budget = False
    print(
        f"[DPO] Starting alignment: pairs={len(pairs)} epochs={args.epochs} total_steps={total_steps} "
        f"grad_accum={grad_accum} total_opt_steps={total_opt_steps} ref_mode={args.ref_mode} "
        f"max_len={args.max_length} beta={args.beta} lr={args.lr} qlora={use_qlora}",
        flush=True,
    )
    for ep in range(args.epochs):
        ep_pairs = list(pairs)
        random.Random(args.seed + ep).shuffle(ep_pairs)
        for pair in ep_pairs:
            if step >= total_steps:
                break
            if time_budget_s > 0 and (time.time() - t0) >= time_budget_s:
                stopped_by_budget = True
                print(f"[DPO] Time budget reached ({args.max_hours}h) at step={step}/{total_steps}", flush=True)
                break
            for g in opt.param_groups:
                g["lr"] = _lr(opt_step)
            try:
                pt = tokenizer.apply_chat_template(pair["prompt"], tokenize=False, add_generation_prompt=True)
            except Exception:
                skipped += 1
                continue
            ec = encode_completion(tokenizer, pt, pair["chosen"], args.max_length, args.max_prompt_length)
            er = encode_completion(tokenizer, pt, pair["rejected"], args.max_length, args.max_prompt_length)
            pi_c = sequence_logp(model, *ec, "cuda:0")
            pi_r = sequence_logp(model, *er, "cuda:0")
            with torch.no_grad():
                if args.ref_mode == "sft":
                    try:
                        model.set_adapter("sft_ref")
                        ref_c = sequence_logp(model, *ec, "cuda:0")
                        ref_r = sequence_logp(model, *er, "cuda:0")
                    finally:
                        model.set_adapter("default")
                else:
                    with model.disable_adapter():
                        ref_c = sequence_logp(model, *ec, "cuda:0")
                        ref_r = sequence_logp(model, *er, "cuda:0")
            margin = (pi_c - ref_c) - (pi_r - ref_r)
            loss = -F.logsigmoid(args.beta * margin)
            if not torch.isfinite(loss):
                skipped += 1
                opt.zero_grad(set_to_none=True)
                micro_in_accum = 0
                continue
            (loss / grad_accum).backward()
            micro_in_accum += 1
            loss_val = float(loss.detach().cpu())
            margin_val = float(margin.detach().cpu())
            losses.append(loss_val)
            margins.append(margin_val)
            step += 1
            if micro_in_accum >= grad_accum or step >= total_steps:
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                micro_in_accum = 0
                opt_step += 1
            if step == 1 or step % 10 == 0 or step == total_steps:
                print(
                    f"[DPO] step={step}/{total_steps} opt={opt_step}/{total_opt_steps} "
                    f"loss={loss_val:.4f} margin={margin_val:.4f} "
                    f"lr={opt.param_groups[0]['lr']:.2e} elapsed={time.time() - t0:.1f}s",
                    flush=True,
                )
        if stopped_by_budget or step >= total_steps:
            break

    if micro_in_accum > 0:
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        opt_step += 1

    if step <= 0:
        raise SystemExit(f"[FATAL] DPO executed 0 valid steps (skipped={skipped}/{len(pairs)})")

    if args.ref_mode == "sft" and "sft_ref" in getattr(model, "peft_config", {}):
        model.delete_adapter("sft_ref")
        model.set_adapter("default")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    st_file = out_dir / "adapter_model.safetensors"
    adapter_sha = _sha256_file(st_file) if st_file.is_file() else ""
    status = "TIME_BUDGET_STOPPED" if stopped_by_budget else "COMPLETED"
    receipt = {
        "status": status,
        "stage": "dpo",
        "base": str(base),
        "base_model": str(base),
        "sft_adapter": str(sft_dir),
        "ref_mode": args.ref_mode,
        "grad_accum": grad_accum,
        "opt_steps": opt_step,
        "data_sha256": data_sha,
        "dataset_sha256": data_sha,
        "adapter_sha256": adapter_sha,
        "pairs_total": len(pairs),
        "steps": step,
        "skipped": skipped,
        "lora_r": 32,
        "lora_alpha": 64,
        "beta": args.beta,
        "loss_mean": round(sum(losses) / len(losses), 6) if losses else None,
        "loss_first": round(losses[0], 6) if losses else None,
        "loss_last": round(losses[-1], 6) if losses else None,
        "margin_mean": round(sum(margins) / len(margins), 6) if margins else None,
        "margin_last": round(margins[-1], 6) if margins else None,
        "runtime_seconds": round(time.time() - t0, 2),
    }
    (out_dir / "training_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
