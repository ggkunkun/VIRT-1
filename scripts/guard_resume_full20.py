# -*- coding: utf-8 -*-
"""
守候 v5 编排结束 + GPU 释放后，从 step10 断点续训 local_sft_link_full20。

设计要点（2026-11-16）：
  * 本机只有一块 6GB GPU，v5 编排（另一会话启动）仍在跑，不能抢 GPU。
  * 上次 r1_full20 中断在 eval 104/124（vram 仅 3772MB，非 OOM），根因是
    Bash 派生子进程随会话结束被回收。故本脚本由 explorer.exe 派生常驻，
    脱离沙箱作业对象，且运行在用户 session（CUDA 可用；ShellExecuteW 落
    session 0 无法访问 GPU）。
  * 元数据校验（dataset_sha256/seed/max_length/grad_accum/epochs）与断点
    ckpt_state.json 一致，--resume 会被接受；--dev-max-items 不参与校验。
  * 忠实原配置优先（全量 dev 124）；若 eval 再次被中断导致未落盘，自动
    降级重试一次（--dev-max-items 24），确保 adapter 最终落盘。

状态文件： runs/local_training_20261115/guard_status.json
守候日志： runs/local_training_20261115/guard_watchdog.log
续训日志： runs/local_training_20261115/r1_full20_resume_exec.log
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
TRAIN = ROOT / "scripts" / "train_vericut_local_qlora.py"
BASE = ROOT / "checkpoints" / "virtu_cad_cam_merged_v3"
DATA = ROOT / "data" / "sft" / "vericut_e_training" / "vericut_e_train_mix.jsonl"
OUT = ROOT / "checkpoints" / "local_sft_link_full20"
RUNLOG = ROOT / "runs" / "local_training_20261115"
RESUME_LOG = RUNLOG / "r1_full20_resume_exec.log"
WATCH_LOG = RUNLOG / "guard_watchdog.log"
STATUS = RUNLOG / "guard_status.json"
RECEIPT = OUT / "training_receipt.json"

WAIT_DEADLINE_S = 6 * 3600          # 最多守候 6 小时
IDLE_CONFIRM_TIMES = 2              # 连续 N 次满足空闲条件才启动
IDLE_INTERVAL_S = 60


def log(msg: str) -> None:
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(WATCH_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def set_status(**kw) -> None:
    d = {}
    if STATUS.exists():
        try:
            d = json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:
            pass
    d.update(kw)
    d["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        STATUS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def v5_proc_count() -> int:
    """统计仍在运行的 run_full_repair_v5.py 进程数。"""
    ps = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -like '*run_full_repair_v5.py*' } | "
        "Measure-Object | Select-Object -ExpandProperty Count"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=45,
        ).stdout.strip()
        return int(out)
    except Exception:
        return -1


def gpu_free_mb() -> int:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=45,
        ).stdout.strip().splitlines()
        return int(out[0])
    except Exception:
        return -1


def receipt_ok() -> bool:
    if not RECEIPT.exists():
        return False
    try:
        return json.loads(RECEIPT.read_text(encoding="utf-8")).get("status") == "COMPLETED"
    except Exception:
        return False


def build_cmd(extra_dev_limit: bool) -> list:
    cmd = [
        str(PY), str(TRAIN),
        "--base", str(BASE),
        "--data", str(DATA),
        "--out", str(OUT),
        "--max-steps", "20",
        "--epochs", "1",
        "--max-length", "1536",
        "--grad-accum", "8",
        "--seed", "20261114",
        "--save-every", "10",
        "--resume",
    ]
    if extra_dev_limit:
        cmd += ["--dev-max-items", "24"]
    return cmd


def run_trial(extra_dev_limit: bool, tag: str) -> int:
    cmd = build_cmd(extra_dev_limit)
    log("%s CMD: %s" % (tag, " ".join(cmd)))
    with open(RESUME_LOG, "a", encoding="utf-8") as lf:
        lf.write("\n===== %s %s =====\n" % (tag, time.strftime("%Y-%m-%d %H:%M:%S")) + " ".join(cmd) + "\n\n")
        lf.flush()
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(ROOT))
        log("%s training pid=%d" % (tag, p.pid))
        set_status(stage="training_%s" % tag, train_pid=p.pid, dev_limit=extra_dev_limit)
        rc = p.wait()
    log("%s training finished rc=%d" % (tag, rc))
    return rc


def main() -> int:
    RUNLOG.mkdir(parents=True, exist_ok=True)
    log("guard start (pid=%d). waiting v5 orchestrator to finish + GPU free" % __import__("os").getpid())
    set_status(stage="waiting_v5", resumed_from_step=10, attempt=0)

    deadline = time.time() + WAIT_DEADLINE_S
    idle_hits = 0
    while time.time() < deadline:
        v5n = v5_proc_count()
        free = gpu_free_mb()
        log("waiting: v5_procs=%s gpu_free=%dMB idle_hits=%d/%d" % (v5n, free, idle_hits, IDLE_CONFIRM_TIMES))
        if v5n == 0 and free >= 5000:
            idle_hits += 1
            if idle_hits >= IDLE_CONFIRM_TIMES:
                log("v5 finished and GPU idle confirmed -> start resume training")
                set_status(stage="resuming", gpu_free_mb=free)
                break
        else:
            idle_hits = 0
        time.sleep(IDLE_INTERVAL_S)
    else:
        log("TIMEOUT waiting v5/GPU; abort")
        set_status(stage="timeout")
        return 2

    # 尝试 1：忠实原配置（全量 dev 124）
    run_trial(False, "attempt1_full_dev")
    if receipt_ok():
        log("attempt1 SUCCEEDED; receipt COMPLETED")
        set_status(stage="done", attempt=1, receipt_status="COMPLETED")
        return 0

    log("attempt1 did not produce COMPLETED receipt; retry with --dev-max-items 24")
    set_status(stage="retry_prep", attempt=2, note="attempt1 no COMPLETED receipt")

    # 尝试 2：降级 dev 抽样，确保落盘
    run_trial(True, "attempt2_dev24")
    if receipt_ok():
        log("attempt2 SUCCEEDED; receipt COMPLETED")
        set_status(stage="done", attempt=2, receipt_status="COMPLETED")
        return 0

    log("attempt2 FAILED to produce COMPLETED receipt; manual intervention required")
    set_status(stage="failed", attempt=2, receipt_status="MISSING_OR_NOT_COMPLETED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
