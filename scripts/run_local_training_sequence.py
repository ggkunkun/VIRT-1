#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地开训守候编排（2026-11-15）。

用户指令：两者依次都做 —— 先跑通本地 6GB SFT 链路，再用修复集训 six-software:v3。

安全约束：
  1. 等 A/B 评测（另一会话）让出 GPU：检测 eval_vericut_e_training.py 进程消失 +
     Ollama 已加载模型为空 + 显存 free >= 空闲阈值，连续 N 次满足才开跑。
  2. 第一步永远先 --probe（5 条最长样本探显存），probe 失败立即停止，不做正式训练。
  3. 每步独立子进程 + 超时 + 日志落盘；任一步失败即停，不伪造成功。
  4. 不覆盖任何已部署模型/凭证；产物落独立目录。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
LOG_DIR = ROOT / "runs" / "local_training_20261115"
TRAINER = ROOT / "scripts" / "train_vericut_local_qlora.py"

BASE_DEFAULT = ROOT / "checkpoints" / "virtu_cad_cam_merged_v3"
DATA_DEFAULT = ROOT / "data" / "sft" / "vericut_e_training" / "vericut_e_train_mix.jsonl"
BASE_V3 = ROOT / "checkpoints" / "_deploy_six_software_v3" / "merged_hf"
DATA_REPAIR = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v3_repair_sft.jsonl"

OUT_PROBE = ROOT / "checkpoints" / "local_probe_check"
OUT_R1 = ROOT / "checkpoints" / "local_sft_link_check"
OUT_R2 = ROOT / "checkpoints" / "six_software_v3_local_repair_lora"


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (LOG_DIR / "sequence.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def gpu_free_mb() -> int:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            text=True, timeout=20,
        )
        return int(out.strip().splitlines()[0].strip())
    except Exception as e:
        log(f"gpu query failed: {e}")
        return 0


def eval_running() -> bool:
    # 2026-11-15 22:44 修复：原实现经 powershell 子进程查命令行，在沙箱/受限会话里
    # 会被拦截并抛异常，except 保守返回 True ⇒ 即使 GPU 已空也永远判忙、训练永远不启动。
    # 改为 psutil 直查（本机 7.2.2 可用），保留"查不到就当忙"的兜底语义。
    keys = ("eval_vericut_e_training.py", "eval_full_board")
    try:
        import psutil

        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                name = (proc.info["name"] or "").lower()
                if not name.startswith("python"):
                    continue
                cmd = " ".join(proc.info["cmdline"] or [])
                # 排除自匹配：查询/grep/bash 命令行里含关键字但不是真评测进程
                if "bash" in cmd or "-c" in cmd or "grep" in cmd:
                    continue
                if any(k in cmd for k in keys):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except Exception:
        return True  # 查不到就当忙，保守


def ollama_loaded() -> int:
    try:
        import urllib.request
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        d = json.loads(op.open("http://127.0.0.1:11434/api/ps", timeout=10).read())
        return len(d.get("models", []))
    except Exception:
        return -1


def wait_for_gpu(timeout_s=1800, need=3, interval=20):
    log("waiting for GPU to be free (A/B must finish)...")
    deadline = time.time() + timeout_s
    ok = 0
    while time.time() < deadline:
        busy_eval = eval_running()
        loaded = ollama_loaded()
        free = gpu_free_mb()
        if (not busy_eval) and loaded == 0 and free >= 4800:
            ok += 1
            log(f"GPU idle candidate {ok}/{need}: eval={busy_eval} ollama_loaded={loaded} free={free}MB")
            if ok >= need:
                log("GPU confirmed idle -> start training")
                return True
        else:
            ok = 0
            log(f"GPU busy: eval={busy_eval} ollama_loaded={loaded} free={free}MB")
        time.sleep(interval)
    log("TIMEOUT waiting GPU; abort (no training started)")
    return False


def run_step(name: str, args: list, logfile: str, timeout_s: int) -> bool:
    log(f"STEP START {name}: {' '.join(str(a) for a in args)}")
    t0 = time.time()
    with (LOG_DIR / logfile).open("w", encoding="utf-8") as lf:
        try:
            p = subprocess.run(
                [str(PY), str(TRAINER)] + [str(a) for a in args],
                stdout=lf, stderr=subprocess.STDOUT,
                timeout=timeout_s, cwd=str(ROOT),
            )
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = -99
            lf.write(f"\n[SEQUENCE] TIMEOUT after {timeout_s}s\n")
    ok = rc == 0
    log(f"STEP END {name}: rc={rc} elapsed={time.time()-t0:.1f}s ok={ok} log={logfile}")
    return ok


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log("=== local training sequence start ===")
    if not wait_for_gpu():
        return 2

    # Step 0: probe default data (链路验证第一步，5 条最长样本 forward+backward)
    if not run_step(
        "probe_default",
        ["--base", BASE_DEFAULT, "--data", DATA_DEFAULT, "--out", OUT_PROBE,
         "--probe", "--max-length", "1536", "--grad-accum", "8"],
        "probe_default.log", 1800,
    ):
        log("probe failed -> abort all training (6GB link not safe)")
        return 3

    # Step 1: 第一轮——本地 SFT 链路实跑（小规模 max-steps 验证可训练+可落盘）
    # 2026-11-15 修复：首次实跑在 dev 全量 124 条评估阶段原生崩溃（rc=0xC0000005，无栈）。
    # 现限制 dev 评估条数到 24（链路验证不需要全量 dev），并靠 [eval n/m] / [micro n/m] 心跳定位。
    if not run_step(
        "r1_sft_link",
        ["--base", BASE_DEFAULT, "--data", DATA_DEFAULT, "--out", OUT_R1,
         "--max-steps", "20", "--epochs", "1", "--max-length", "1536",
         "--grad-accum", "8", "--save-every", "10", "--dev-max-items", "24"],
        "r1_sft_link.log", 5400,
    ):
        log("round1 SFT failed -> abort round2")
        return 4

    # Step 2: probe v3 底模 + 修复集（换底模需重新探显存）
    if not run_step(
        "probe_v3_repair",
        ["--base", BASE_V3, "--data", DATA_REPAIR, "--out", OUT_PROBE,
         "--probe", "--max-length", "1536", "--grad-accum", "8"],
        "probe_v3_repair.log", 1800,
    ):
        log("v3 probe failed -> abort round2")
        return 5

    # Step 3: 第二轮——six-software:v3 修复集增量训练
    if not run_step(
        "r2_v3_repair",
        ["--base", BASE_V3, "--data", DATA_REPAIR, "--out", OUT_R2,
         "--epochs", "1", "--max-length", "1536", "--grad-accum", "8",
         "--lr", "8e-5", "--save-every", "10"],
        "r2_v3_repair.log", 7200,
    ):
        log("round2 repair failed")
        return 6

    log("=== ALL STEPS DONE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
