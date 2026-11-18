#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 QLoRA adapter 合进底模，导出可转 GGUF 的 merged HF 目录。

用法：
  python merge_lora.py --base Qwen/Qwen2.5-7B-Instruct --lora ./out/lora --out ./out/merged_hf \
      --dtype bf16

说明：
  * 用 peft 的 merge_and_unload（与本地 scripts/merge_numpy.py 的 delta 合并数学等价，均不缩放）；
  * 默认在 CPU 上以 bf16 载入（7B 需要约 16GB 内存），--dtype fp32 会翻倍；
  * 写出 config.json / tokenizer / safetensors 分片，并写 merge_receipt.json 供审计。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--lora", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dtype", default="bf16", choices=["bf16", "fp16", "fp32"])
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[args.dtype]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print(f"[Merge] loading base={args.base} dtype={args.dtype} (CPU)", flush=True)
    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=dtype,
                                                device_map={"": "cpu"}, trust_remote_code=True)
    print(f"[Merge] loading adapter={args.lora}", flush=True)
    model = PeftModel.from_pretrained(base, args.lora)
    model = model.merge_and_unload()
    model.save_pretrained(out, safe_serialization=True, max_shard_size="4GB")
    tok.save_pretrained(out)

    receipt = {
        "status": "MERGED",
        "mode": "peft_merge_and_unload",
        "base": args.base,
        "lora": args.lora,
        "dtype": args.dtype,
        "elapsed_s": round(time.time() - t0, 1),
        "shards": sorted(p.name for p in out.glob("model-*.safetensors")) or
                  sorted(p.name for p in out.glob("*.safetensors")),
        "merged_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out / "merge_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(f"[Merge] done in {receipt['elapsed_s']}s → {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
