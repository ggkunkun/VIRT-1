"""Run the whole capability sweep, one arm at a time, then aggregate.

Why a driver instead of a shell loop:

* only one 8B model fits in this box's 6 GB of VRAM, so the arms must run
  strictly one after another - two clients asking Ollama for different models
  at the same time forces a swap and skews every latency number;
* the multimodal dimension is scored on the vision channel only.  A text
  backbone cannot see an image, so scoring it 0 there would be a category
  error, not a capability measurement;
* every arm must see exactly the same case budget or the comparison is void.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
RUNNER = os.path.join(ROOT, "virtu_eval", "runner.py")

TEXT_DIMS = "reasoning,knowledge,instruction,generation,generalization,boundary,toolcall"


def run(cmd, label):
    print(f"\n{'=' * 80}\n>>> {label}\n{'=' * 80}", flush=True)
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=ROOT)
    print(f"<<< {label} rc={rc} in {time.time() - t0:.0f}s", flush=True)
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--out-root", default="runs/eval/sweep")
    ap.add_argument("--sample", default="easy=3,medium=3,hard=2")
    ap.add_argument("--max-tokens-cap", type=int, default=128)
    ap.add_argument("--include-multimodal", action="store_true")
    ap.add_argument("--vision-arm", default="vision_local_qwen3vl2b")
    ap.add_argument("--skip-vision", action="store_true")
    a = ap.parse_args()

    sample = {}
    for part in a.sample.split(","):
        k, _, v = part.partition("=")
        sample[k.strip()] = int(v)

    os.makedirs(a.out_root, exist_ok=True)
    summary = {"sample_per_tier": sample, "max_tokens_cap": a.max_tokens_cap,
               "text_dims": TEXT_DIMS, "arms": {}, "started": time.strftime("%Y-%m-%d %H:%M:%S")}

    for arm in a.arms:
        out = os.path.join(a.out_root, arm)
        cmd = [PY, RUNNER, "--arm", arm, "--out-dir", out,
               "--dims", TEXT_DIMS,
               "--sample-per-tier", a.sample,
               "--max-tokens-cap", str(a.max_tokens_cap)]
        rc = run(cmd, f"ARM {arm} (text dims)")
        summary["arms"][arm] = {"rc": rc, "out_dir": out, "dims": TEXT_DIMS}

    if not a.skip_vision:
        out = os.path.join(a.out_root, a.vision_arm + "_multimodal")
        cmd = [PY, RUNNER, "--arm", a.vision_arm, "--out-dir", out,
               "--dims", "multimodal",
               "--max-tokens-cap", str(a.max_tokens_cap)]
        rc = run(cmd, f"ARM {a.vision_arm} (multimodal only)")
        summary["arms"][a.vision_arm + "_multimodal"] = {"rc": rc, "out_dir": out,
                                                         "dims": "multimodal"}

    summary["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    path = os.path.join(a.out_root, "sweep_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\nwrote", path)


if __name__ == "__main__":
    sys.exit(main())
