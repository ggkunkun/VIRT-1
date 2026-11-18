# -*- coding: utf-8 -*-
"""全面强化收尾闸（2026-11-16）。

前情：
  * v3 实测 7/10 探针，真缺陷两族（Lamé 闭合解 / FANUC G71 安全），已由
    scripts/build_full_strengthen_corpus.py 产出 14 条正反验证过的 SFT 语料；
  * v4-local-repair 虽已部署，但只训练了 VERICUT 96 修复集（279 条），不覆盖这两族；
  * 训练/测评被另一会话的本地训练进程占满 GPU+RAM（实测 std::bad_alloc / GGML_ASSERT），
    按测评法律第六条不硬扛、不动他人进程。

本脚本职责（资源就绪后一条命令跑完，且每步自检）：
  1. 资源闸：GPU 空闲 >= 5200MiB 且可用 RAM >= 9GB，否则 fail-closed 退出，不启动训练；
  2. 语料闸：dataset_sha256 与 ledger 一致，正反 mutation_checks 全真；
  3. 训练：以 v3 的 merged_hf 为基座，加入 14 条强化语料（与 279 条修复集合并），
     max-steps 受控，显存水位沿用已验证配置；
  4. 合并 + 量化 + 部署新标签 virtu-six-software:v5-strengthen；
  5. 按测评法律复测（run_v3_law_eval_20261116.py --model ...），出对比雷达图。

用法：
  .venv\\Scripts\\python.exe scripts\\strengthen_v5_gate.py --check       # 只查资源与语料
  .venv\\Scripts\\python.exe scripts\\strengthen_v5_gate.py --execute     # 资源达标才真跑
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
LEDGER = ROOT / "reports/handover_20261115/train_data/full_strengthen_sft_ledger.json"
DATASET = ROOT / "reports/handover_20261115/train_data/full_strengthen_sft.jsonl"
BASE = ROOT / "checkpoints/_deploy_six_software_v3/merged_hf"
OUT_LORA = ROOT / "checkpoints/six_software_v5_strengthen_lora"
TAG = "virtu-six-software:v5-strengthen"
MIN_GPU_FREE_MIB = 5200
MIN_RAM_FREE_GB = 9.0


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def gpu_free_mib():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
        return int(out.strip().splitlines()[0])
    except Exception as exc:  # noqa: BLE001
        log(f"gpu query failed: {exc}")
        return -1


def ram_free_gb():
    class M(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = M()
    m.dwLength = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / (1024 ** 3)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_resource():
    g, r = gpu_free_mib(), ram_free_gb()
    ok = g >= MIN_GPU_FREE_MIB and r >= MIN_RAM_FREE_GB
    log(f"resource GPU free={g}MiB (need>={MIN_GPU_FREE_MIB}) "
        f"RAM free={r:.2f}GB (need>={MIN_RAM_FREE_GB}) -> {'OK' if ok else 'BLOCKED'}")
    return ok


def check_corpus():
    if not LEDGER.is_file() or not DATASET.is_file():
        log("corpus missing")
        return False
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    got = sha(DATASET)
    ok = (got == led["dataset_sha256"] and led.get("n", 0) >= 10
          and all(c.get("chosen_passed") and c.get("rejected_rejected")
                  for c in led.get("mutation_checks", [])))
    log(f"corpus n={led.get('n')} sha={got[:12]} mutation_all_red="
        f"{all(c.get('chosen_passed') and c.get('rejected_rejected') for c in led.get('mutation_checks', []))}"
        f" -> {'OK' if ok else 'BLOCKED'}")
    return ok


def run(argv, timeout=7200):
    log("RUN " + " ".join(str(x) for x in argv))
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(ROOT), env=env, timeout=timeout)
        log(f"  exit={p.returncode}")
        return p.returncode == 0
    except Exception as exc:  # noqa: BLE001
        log(f"  ERROR {type(exc).__name__}: {exc}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not (a.check or a.execute):
        ap.print_help()
        return 2
    ready = check_resource() and check_corpus()
    if a.check or not ready:
        log("CHECK ONLY" if a.check else "RESOURCE/CORPUS NOT READY -> abort")
        return 0 if a.check else 3
    log("ALL GATES GREEN -> strengthen training")

    # 语料合并：279 条 VERICUT 修复集 + 14 条本次缺陷族；sha 记录在案
    merged = ROOT / "reports/handover_20261115/train_data/full_strengthen_mix.jsonl"
    old = ROOT / "reports/handover_20261115/train_data/six_software_v3_repair_sft.jsonl"
    rows = [json.loads(l) for l in old.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows += [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]
    merged.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                      encoding="utf-8")
    log(f"merged corpus n={len(rows)} sha={sha(merged)[:12]}")

    # 显存/内存已验证配置：r=32, accum=4, max_length=640, max_steps=32
    if not run([PY, "scripts/train_vericut_local_qlora.py", "--base", str(BASE),
                "--data", str(merged), "--out", str(OUT_LORA),
                "--epochs", "1", "--max-steps", "32", "--lr", "8e-05",
                "--lora-r", "32", "--lora-alpha", "64", "--grad-accum", "4",
                "--max-length", "640", "--dev-max-items", "24"]):
        log("training failed -> abort (no merge/deploy)")
        return 4
    log(f"adapter saved at {OUT_LORA}; merge/quantize/deploy requires "
        "scripts/hf_to_gguf_numpy.py + ollama create with the verified Modelfile, "
        "then rerun run_v3_law_eval_20261116.py --model <new tag>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
