"""Arm diagnostic: device placement, real decode throughput, coherence.

Answers, before any long sweep is committed:
  * did any layer spill to CPU (device_map)
  * steady-state tok/s over a long generation (short probes are warmup-dominated)
  * is the artifact coherent at all (a broken merge looks like a "slow model")
"""
import sys
import time

sys.path.insert(0, "D:/Virtu模型")
from virtu_eval.arms import HFLocalArm  # noqa: E402

BASE = "D:/Virtu模型/checkpoints/_base_qwen3_8b"
CANDIDATES = [
    ("base_only", BASE, None),
    ("base+cad_cam_six_software_lora", BASE, "D:/Virtu模型/checkpoints/cad_cam_six_software_lora"),
]
if len(sys.argv) > 1:
    CANDIDATES = [(sys.argv[1], sys.argv[2] or BASE, sys.argv[3] or None)]

PROMPTS = [
    "计算 17*23+11 的值，只输出数字。",
    "某铣削工序使用 Ø20 硬质合金立铣刀，切削速度 Vc=120 m/min，请计算主轴转速 n（r/min，四舍五入取整）。只给数字。",
    "请用一句话说明什么是形位公差中的位置度。",
    "写一段 120 字左右的中文说明，介绍数控车削中粗车与精车的区别。",
]

for label, model, adapter in CANDIDATES:
    print(f"\n########## {label} ##########", flush=True)
    t0 = time.perf_counter()
    arm = HFLocalArm(model, adapter, quant="nf4", device="cuda")
    arm.load()
    print(f"[load] {time.perf_counter()-t0:.1f}s", flush=True)
    import torch
    dm = getattr(arm._llm, "hf_device_map", None)
    if dm:
        cpul = [k for k, v in dict(dm).items() if v == "cpu"]
        print(f"[device_map] entries={len(dm)} on_cpu={len(cpul)}", flush=True)
    print(f"[vram] peak_after_load={torch.cuda.max_memory_allocated()/1024**3:.2f}GB", flush=True)
    for p in PROMPTS:
        r = arm.generate([{"role": "user", "content": p}], max_tokens=256, temperature=0.0)
        tps = r["completion_tokens"] / r["elapsed_s"] if r["elapsed_s"] else 0
        print(f"  out={r['completion_tokens']} {r['elapsed_s']}s {tps:.1f}tok/s "
              f"finish={r['finish_reason']}", flush=True)
        print("   ", repr(r["text"])[:300], flush=True)
    arm.unload()
    print(f"[vram-after-unload] {torch.cuda.memory_allocated()/1024**3:.2f}GB", flush=True)
