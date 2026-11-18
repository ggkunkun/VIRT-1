"""6GB 显存能否训 8B QLoRA —— 60 秒探针（不做训练，只回答"能不能"）。

判据：
  A. 4bit 加载后显存占用 < 5.4GB  —— 否则连模型都装不下，直接放弃本机训练
  B. seq=768 / batch=1 前向+反向峰值 < 5.9GB —— 否则一步都跑不了

不做的事：不训练、不写 checkpoint、不改任何文件。
"""

from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

BASE = os.environ.get("BASE_MODEL", r"D:\Virtu模型\checkpoints\_base_qwen3_8b")


def gb(x: float) -> float:
    return round(x / (1024 ** 3), 2)


def main() -> int:
    out = {"base": BASE, "cuda": torch.cuda.is_available()}
    if not torch.cuda.is_available():
        print(json.dumps({**out, "verdict": "NO_CUDA"}, ensure_ascii=False))
        return 2
    torch.cuda.reset_peak_memory_stats()
    total = torch.cuda.get_device_properties(0).total_memory
    out["vram_total_gb"] = gb(total)

    t0 = time.time()
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, device_map={"": 0}, trust_remote_code=True
    )
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    load_s = round(time.time() - t0, 1)
    after_load = torch.cuda.memory_allocated()
    out.update({"load_s": load_s, "alloc_after_load_gb": gb(after_load)})
    print(json.dumps({**out, "stage": "loaded"}, ensure_ascii=False), flush=True)

    # 一步前向+反向：seq=768，模拟真实训练步
    seq = int(os.environ.get("PROBE_SEQ", "768"))
    ids = torch.randint(1000, 20000, (1, seq), device=0)
    labels = ids.clone()
    try:
        loss = model(input_ids=ids, labels=labels).loss
        loss.backward()
        peak = torch.cuda.max_memory_allocated()
        out.update({
            "stage": "fwd_bwd_ok",
            "seq": seq,
            "loss": round(float(loss.detach()), 4),
            "peak_gb": gb(peak),
            "reserved_gb": gb(torch.cuda.max_memory_reserved()),
        })
        out["verdict"] = "FITS" if out["peak_gb"] < 5.9 else "TOO_TIGHT"
    except torch.cuda.OutOfMemoryError as exc:
        out.update({"stage": "oom", "verdict": "OOM", "error": str(exc)[:300],
                    "peak_gb": gb(torch.cuda.max_memory_allocated())})
    except Exception as exc:                                    # noqa: BLE001
        out.update({"stage": "error", "verdict": "ERROR",
                    "error": f"{type(exc).__name__}: {exc}"[:400]})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("verdict") == "FITS" else 1


if __name__ == "__main__":
    sys.exit(main())
