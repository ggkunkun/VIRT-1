"""Sequential GPU eval chain: one arm per subprocess, resumable, crash-isolated.

Order is deliberate - the arm whose numbers the report depends on most runs first,
so a partial chain still yields a publishable primary result.

  1. virtu_lora_cadcam   full 210 text cases   -> the measured model
  2. vision_local        30 multimodal cases   -> the vision channel
  3. qwen3_8b_base       84 stratified cases   -> control, for LoRA gain/loss
  4. virtu_merged_v3     21 stratified cases   -> production merge sanity
Each step's own log lives next to its raw.jsonl. A step that fails does not stop
the chain; the aggregate step at the end applies the completeness gate.
"""
import os
import subprocess
import sys
import time

ROOT = "D:/Virtu模型"
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
OUT_ROOT = os.path.join(ROOT, "benchmarks", "virtu_capability_v1")
TEXT_DIMS = "reasoning,knowledge,instruction,generation,generalization,boundary,toolcall"

STEPS = [
    {"name": "virtu_lora_cadcam", "arm": "virtu_lora_cadcam", "dims": TEXT_DIMS,
     "sample": "", "cap": "easy=128,medium=320,hard=640"},
    {"name": "vision_local_qwen3vl2b", "arm": "vision_local_qwen3vl2b", "dims": "multimodal",
     "sample": "", "cap": "easy=128,medium=256,hard=384"},
    {"name": "qwen3_8b_base", "arm": "qwen3_8b_base", "dims": TEXT_DIMS,
     "sample": "easy=3,medium=6,hard=3", "cap": "easy=128,medium=192,hard=320"},
    {"name": "virtu_merged_v3", "arm": "virtu_merged_v3", "dims": TEXT_DIMS,
     "sample": "easy=1,medium=1,hard=1", "cap": "easy=128,medium=192,hard=320"},
]


def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    only = set(sys.argv[1:])
    for step in STEPS:
        if only and step["name"] not in only:
            continue
        out_dir = os.path.join(OUT_ROOT, step["name"])
        os.makedirs(out_dir, exist_ok=True)
        log = open(os.path.join(out_dir, "step.log"), "a", encoding="utf-8")
        cmd = [PY, "-u", os.path.join(ROOT, "virtu_eval", "runner.py"),
               "--arm", step["arm"], "--out-dir", os.path.join("benchmarks", "virtu_capability_v1", step["name"]),
               "--dims", step["dims"]]
        if step["sample"]:
            cmd += ["--sample-per-tier", step["sample"]]
        if step["cap"]:
            cmd += ["--cap-by-tier", step["cap"]]
        t0 = time.time()
        log.write(f"\n===== {time.strftime('%F %T')} {' '.join(cmd[2:])}\n")
        log.flush()
        print(f"[chain] START {step['name']}", flush=True)
        rc = subprocess.call(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        dt = time.time() - t0
        log.write(f"===== exit={rc} wall={dt/60:.1f}min\n")
        log.close()
        print(f"[chain] DONE {step['name']} rc={rc} wall={dt/60:.1f}min", flush=True)

    labels = ",".join(f"{s['name']}:{os.path.join('benchmarks/virtu_capability_v1', s['name'])}"
                      for s in STEPS if os.path.exists(os.path.join(OUT_ROOT, s["name"], "raw.jsonl")))
    if labels:
        print(f"[chain] aggregating {labels}", flush=True)
        subprocess.call([PY, "-u", os.path.join(ROOT, "virtu_eval", "report.py"), "--runs", labels],
                        cwd=ROOT)


if __name__ == "__main__":
    main()
