"""Tiny on-target smoke test for the local text arm (device + dtype + budget).

Run before committing to a full evaluation sweep: it proves the arm loads,
decodes deterministically, and reports real peak VRAM / tok-per-second on the
actual GPU instead of assuming it.
"""
import sys
import time

sys.path.insert(0, "D:/Virtu模型")
from virtu_eval.arms import HFLocalArm  # noqa: E402

model_path = sys.argv[1] if len(sys.argv) > 1 else "D:/Virtu模型/checkpoints/virtu_cad_cam_merged_v3"
adapter = sys.argv[2] if len(sys.argv) > 2 else None

t0 = time.perf_counter()
arm = HFLocalArm(model_path, adapter, quant="nf4", device="cuda")
arm.load()
print(f"[load] {time.perf_counter()-t0:.1f}s arm={arm.label}", flush=True)

import torch  # noqa: E402
print(f"[vram] allocated={torch.cuda.max_memory_allocated()/1024**3:.2f}GB "
      f"reserved={torch.cuda.max_memory_reserved()/1024**3:.2f}GB", flush=True)

probes = [
    ("你好，请用一句话介绍你自己。", 96),
    ("计算 17*23+11 的值，只输出数字。", 32),
    ("某铣削工序使用 Ø20 硬质合金立铣刀，切削速度 Vc=120 m/min，请计算主轴转速 n（r/min，四舍五入取整）。只给数字。", 64),
    ("请用 JSON 输出加工一个 Ø30x50 铝件端面的单道工序，字段为 tool/operation/spindle/feed，不要额外文字。", 200),
]
for text, mt in probes:
    r = arm.generate([{"role": "user", "content": text}], max_tokens=mt, temperature=0.0)
    tps = (r["completion_tokens"] / r["elapsed_s"]) if r["elapsed_s"] else 0
    print(f"\n--- mt={mt} in={r['prompt_tokens']} out={r['completion_tokens']} "
          f"{r['elapsed_s']}s {tps:.1f}tok/s finish={r['finish_reason']} peak={r['peak_vram_gb']}GB", flush=True)
    print(repr(r["text"])[:400], flush=True)

# determinism: same prompt twice at temp 0 must be bit-identical
a = arm.generate([{"role": "user", "content": "列出三种常见刀具材料。"}], max_tokens=64, temperature=0.0)["text"]
b = arm.generate([{"role": "user", "content": "列出三种常见刀具材料。"}], max_tokens=64, temperature=0.0)["text"]
print(f"\n[determinism] identical={a == b}", flush=True)
print(f"[vram-final] peak={torch.cuda.max_memory_allocated()/1024**3:.2f}GB", flush=True)
