#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""03_merge_local.py — 本机合并 ECT 的两个 adapter 为可上线的 HF 模型。

为什么需要这一步（而上云只产 adapter）：
  * SFT adapter 是相对基座的 delta。
  * DPO adapter 是「叠在 SFT 之上的」delta（DPO 训练时 base+SFT 处于激活态，
    参考模型才是裸基座，见 train_dpo.py 的 disable_adapter()）。
  * 因此正确合并顺序是两步 delta：
        base(全精度) + SFT  -> merge_and_unload => M1
        M1          + DPO  -> merge_and_unload => M2  (最终模型)
    若把两个 adapter 直接叠到裸基座上（一次性合并），DPO 的 delta 会错位，
    导致偏好优化失效甚至乱码。

硬性约束（与 train.json[merge] 一致）：
  * 仅支持 delta 合并；TIES 见 README（用 mergekit，避免本项目历史上 peft_linear
    产生的乱码/死循环，peft_linear 一律禁用）。
  * 两个 receipt 必须都是 COMPLETED，且非 SMOKE_ONLY。
  * lora_r 必须一致（否则 delta 张量形状对不齐，合并会炸）。
  * SFT 与 DPO 必须基于同一基座（receipt.base 一致）。

内存策略：默认在 CPU 上以 bf16 完成合并（约 16GB RAM，覆盖绝大多数开发机）；
  若本机有充足显存的 GPU，可 --device cuda 加速。绝不做 4bit 合并（无法得到可用全精度权重）。

用法：
  python 03_merge_local.py --out checkpoints/ect_merged
  python 03_merge_local.py --sft-adapter .../ect_sft_adapter \
        --dpo-adapter .../ect_dpo_adapter --out checkpoints/ect_merged --device cpu
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from ect_common import load_config, log, resolve


def _import_stack():
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit(
            f"[merge] 缺少依赖: {exc}\n"
            "请在本机安装: pip install torch transformers peft safetensors"
        ) from exc
    return torch, AutoModelForCausalLM, AutoTokenizer, PeftModel


def _check_receipt(adapter_dir: Path, stage: str, expect_completed: bool) -> Dict[str, Any]:
    rp = adapter_dir / "training_receipt.json"
    if not adapter_dir.is_dir() or not (adapter_dir / "adapter_config.json").is_file():
        raise SystemExit(f"缺少 {stage} adapter: {adapter_dir}（请先在云端跑完训练）")
    if not rp.is_file():
        raise SystemExit(f"{stage} adapter 无 receipt: {rp}")
    r = json.loads(rp.read_text(encoding="utf-8"))
    status = r.get("status")
    if expect_completed and status != "COMPLETED":
        raise SystemExit(f"{stage} receipt 状态={status}，必须 COMPLETED 才能合并")
    if status == "SMOKE_ONLY":
        raise SystemExit(f"{stage} 是 SMOKE_ONLY 产物，禁止进入合并/上线流程")
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力训练 - 本地合并 adapter")
    ap.add_argument("--base", default=None, help="基座路径/HF id（缺省读 VIRTU_BASE / config）")
    ap.add_argument("--sft-adapter", default=None)
    ap.add_argument("--dpo-adapter", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--skip-dpo", action="store_true",
                    help="只合并 SFT（未跑 DPO 时）")
    args = ap.parse_args()

    cfg = load_config("pipeline")
    train_cfg = load_config("train")
    base = args.base or os.environ.get(cfg["base_model_env"]) or cfg["base_model"]
    sft = resolve(args.sft_adapter or cfg["paths"]["adapter_out"])
    dpo = resolve(args.dpo_adapter or cfg["paths"]["dpo_adapter_out"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sft_r = _check_receipt(sft, "SFT", expect_completed=True)
    dpo_r: Dict[str, Any] = {}
    if not args.skip_dpo:
        dpo_r = _check_receipt(dpo, "DPO", expect_completed=True)

    # 一致性断言
    if int(sft_r.get("lora_r", 0)) != int(train_cfg["sft"]["lora_r"]):
        raise SystemExit(
            f"SFT lora_r={sft_r.get('lora_r')} 与配置 {train_cfg['sft']['lora_r']} 不一致")
    if dpo_r:
        if sft_r.get("base") != dpo_r.get("base"):
            raise SystemExit(
                f"SFT 与 DPO 基座不一致: {sft_r.get('base')} vs {dpo_r.get('base')}")
        if int(dpo_r.get("lora_r", 0)) != int(train_cfg["sft"]["lora_r"]):
            raise SystemExit(f"DPO lora_r 与 SFT 不一致，合并会失败")

    torch, AutoModel, AutoTok, PeftModel = _import_stack()
    if args.device == "cuda" and torch.cuda.is_available():
        device = "cuda:0"
        cap = torch.cuda.get_device_capability(0)[0]
        dtype = torch.bfloat16 if cap >= 8 else torch.float16
    else:
        device = "cpu"
        dtype = torch.bfloat16  # 在 CPU 上 bf16 即可把内存压到 ~16GB
    log("merge", f"base={base} device={device} dtype={dtype} skip_dpo={args.skip_dpo}")

    base_model = AutoModel.from_pretrained(
        base, torch_dtype=dtype, trust_remote_code=True).to(device)
    # 第一步：SFT delta 合入基座
    model = PeftModel.from_pretrained(base_model, str(sft))
    model = model.merge_and_unload()
    log("merge", "SFT 已合入 -> M1")

    # 第二步：DPO delta 合入 M1（DPO 的 delta 正是相对 SFT 微调后权重的）
    if dpo_r:
        model = PeftModel.from_pretrained(model, str(dpo))
        model = model.merge_and_unload()
        log("merge", "DPO 已合入 -> M2")

    model.save_pretrained(str(out))
    tok = AutoTok.from_pretrained(base, trust_remote_code=True)
    tok.save_pretrained(str(out))

    receipt = {
        "status": "MERGED", "stage": "merge",
        "mode": "delta_two_step", "forbidden": ["peft_linear"],
        "base": str(base), "sft_adapter": str(sft),
        "dpo_adapter": (str(dpo) if dpo_r else None),
        "sft_loss": sft_r.get("train_loss"),
        "dpo_loss_mean": dpo_r.get("loss_mean"),
        "lora_r": train_cfg["sft"]["lora_r"],
        "device": device, "dtype": str(dtype),
        "merged_dir": str(out), "created_at": __import__("ect_common").now_iso(),
        "next": "GGUF 转换（llama.cpp / hf_to_gguf_numpy.py）-> Ollama 注册 -> 真实 GUI 评测",
    }
    (out / "merge_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    log("merge", f"完成 -> {out}")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
