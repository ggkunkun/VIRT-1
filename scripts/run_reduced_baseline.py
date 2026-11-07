#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_reduced_baseline.py — 等合并链结束后，对"能正常出话"的两个 arm 跑真实可复现的能力基线。

为什么只跑两个 arm：
  virtu-production:v3 的实测回答是退化刷屏（证据 work/_prod_v3_degenerate.txt），
  把它当"被评模型"打分等于给一个坏产物编分数；它只作为失败证据单列。
  bridge_deployed 的底座模型身份未核实，不纳入基线。

口径：
  dimens = 7 个文本维度；每维 6 条（--limit-per-dim 6）；--max-tokens-cap 256；
  temperature=0，seed=1234；单测分数=权重命中率×100（virtu_eval.graders 固定口径）。
  原始记录、manifest、聚合报告全部落盘，可逐条复核。

用法：
  python scripts/run_reduced_baseline.py            # 等 CHAIN_END 后跑
  python scripts/run_reduced_baseline.py --now      # 不等，直接跑（合并已结束）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
CHAIN_LOG = os.path.join(ROOT, "work", "_eval_merge_chain.log")
LOG = os.path.join(ROOT, "work", "_eval_baseline.log")
OUT_ROOT = os.path.join(ROOT, "benchmarks", "virtu_capability_v1")
DIMS = "reasoning,knowledge,instruction,generation,generalization,boundary,toolcall"
ARMS = ["ollama_virtu_toolcall", "ollama_qwen3_8b_base"]


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def wait_chain(max_wait=4 * 3600):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        txt = open(CHAIN_LOG, encoding="utf-8", errors="replace").read() if os.path.exists(CHAIN_LOG) else ""
        if "CHAIN_END" in txt:
            log("merge chain done")
            return True
        time.sleep(120)
    log("TIMEOUT waiting CHAIN_END")
    return False


def run(cmd):
    return subprocess.call(cmd, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true")
    a = ap.parse_args()
    if not a.now and not wait_chain():
        return 1

    for arm in ARMS:
        out_dir = os.path.join("benchmarks", "virtu_capability_v1", arm)
        cmd = [PY, "-u", os.path.join(ROOT, "virtu_eval", "runner.py"),
               "--arm", arm, "--out-dir", out_dir, "--dims", DIMS,
               "--limit-per-dim", "6", "--max-tokens-cap", "256",
               "--temperature", "0.0", "--seed", "1234"]
        log(f"START {arm}")
        t0 = time.time()
        rc = run(cmd)
        log(f"DONE {arm} rc={rc} wall={(time.time()-t0)/60:.1f}min")
        if rc != 0:
            log(f"[WARN] {arm} 退出码非 0，产物仍需完整性闸门复核")

    labels = ",".join(f"{a}:{os.path.join('benchmarks', 'virtu_capability_v1', a)}" for a in ARMS)
    log("aggregating")
    run([PY, "-u", os.path.join(ROOT, "virtu_eval", "report.py"), "--runs", labels])
    log("BASELINE_END")
    return 0


if __name__ == "__main__":
    sys.exit(main())
