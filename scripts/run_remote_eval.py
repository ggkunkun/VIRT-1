"""Run the capability evaluation on the cloud GPU instance and pull results back.

Why this exists: the local box (RTX 4050 6GB) can only host the 8B model at ~1-2 tok/s
with 10+ minute weight loads, which makes a 240-case x 3-arm sweep a multi-hour job.
On the L40S the same model runs in bf16 with no quantisation at tens of tok/s, so the
whole sweep is an minutes-to-one-hour job instead.

Everything is env-driven; the password is never written into the repo.

    DAMODEL_HOST / DAMODEL_PORT / DAMODEL_USER / DAMODEL_PASS   (required)
    REMOTE_BASE_PATH   default /root/public-storage/model/Qwen/Qwen3-8B
    REMOTE_PYTHON      default /opt/conda/bin/python

    python scripts/run_remote_eval.py probe
    python scripts/run_remote_eval.py sync
    python scripts/run_remote_eval.py run --arm virtu_lora_cadcam --dims all
    python scripts/run_remote_eval.py fetch --arm virtu_lora_cadcam
    python scripts/run_remote_eval.py status
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import shlex
import sys
import time

import paramiko

HOST = os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com")
PORT = int(os.environ.get("DAMODEL_PORT", "0") or 0)
USER = os.environ.get("DAMODEL_USER", "root")
PASS = os.environ.get("DAMODEL_PASS", "")
REMOTE_ROOT = os.environ.get("REMOTE_WORKDIR", "/root/virtu_eval")
REMOTE_BASE = os.environ.get("REMOTE_BASE_PATH", "/root/public-storage/model/Qwen/Qwen3-8B")
REMOTE_PY = os.environ.get("REMOTE_PYTHON", "/opt/conda/bin/python")

LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_DIMS = ["reasoning", "knowledge", "instruction", "generation",
             "generalization", "boundary", "toolcall"]

# arms the instance can serve without quantisation (45 GiB is plenty for 8B bf16)
REMOTE_ARMS = {
    "virtu_lora_cadcam": {
        "kind": "hf_local", "model_path": f"{REMOTE_BASE}",
        "adapter_path": f"{REMOTE_ROOT}/adapters/cad_cam_six_software_lora",
        "quant": "none", "device": "cuda", "dtype": "bfloat16",
        "merge_adapter": False, "attn": "sdpa"},
    "qwen3_8b_base": {
        "kind": "hf_local", "model_path": f"{REMOTE_BASE}",
        "quant": "none", "device": "cuda", "dtype": "bfloat16", "attn": "sdpa"},
    "virtu_merged_v3": {
        "kind": "hf_local", "model_path": f"{REMOTE_ROOT}/models/virtu_cad_cam_merged_v3",
        "quant": "none", "device": "cuda", "dtype": "bfloat16", "attn": "sdpa"},
}


def client():
    if not PASS or not PORT:
        sys.exit("[FATAL] 需要 DAMODEL_HOST/PORT/USER/PASS 环境变量（口令不落仓库）")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, port=PORT, username=USER, password=PASS,
              timeout=40, allow_agent=False, look_for_keys=False)
    return c


def run(c, cmd, timeout=900, quiet=False):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    if not quiet:
        print(out[-4000:])
        if err.strip():
            print("STDERR:", err[-1500:])
    return rc, out, err


def put_dir(sftp, local_dir, remote_dir):
    sftp.mkdir(remote_dir) if False else None
    run_sftp_mkdir(sftp, remote_dir)
    for name in sorted(os.listdir(local_dir)):
        lp = os.path.join(local_dir, name)
        rp = posixpath.join(remote_dir, name)
        if os.path.isdir(lp):
            put_dir(sftp, lp, rp)
        elif os.path.isfile(lp) and not any(x in name for x in ("__pycache__", ".pyc")):
            sftp.put(lp, rp)


def run_sftp_mkdir(sftp, remote_dir):
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = cur + "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass


def cmd_probe(c):
    print(f"[probe] {USER}@{HOST}:{PORT} workdir={REMOTE_ROOT}")
    run(c, f"nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv && "
           f"df -h /root | tail -1 && free -g | head -2 && {REMOTE_PY} -V")
    rc, out, _ = run(c, f"{REMOTE_PY} -c \"import torch,transformers,peft;"
                        f"print(torch.__version__, transformers.__version__, peft.__version__,"
                        f"torch.cuda.get_device_name(0))\"", quiet=True)
    print("[env]", out.strip() or f"rc={rc}")
    rc, out, _ = run(c, f"ls -la {REMOTE_BASE}/config.json 2>&1 | head -2", quiet=True)
    print("[base]", out.strip())
    rc, out, _ = run(c, f"df -B1G --output=avail /root | tail -1", quiet=True)
    print("[disk_free_GB]", out.strip())


def cmd_sync(c):
    sftp = c.open_sftp()
    run(c, f"mkdir -p {REMOTE_ROOT}", quiet=True)
    for f in sorted(os.listdir(os.path.join(LOCAL_ROOT, "virtu_eval"))):
        if f.endswith((".py", ".json", ".md")):
            sftp.put(os.path.join(LOCAL_ROOT, "virtu_eval", f), posixpath.join(REMOTE_ROOT, "virtu_eval", f)) \
                if False else None
    put_dir(sftp, os.path.join(LOCAL_ROOT, "virtu_eval"), posixpath.join(REMOTE_ROOT, "virtu_eval"))
    put_dir(sftp, os.path.join(LOCAL_ROOT, "data", "benchmark", "virtu_eval_v1"),
            posixpath.join(REMOTE_ROOT, "data", "benchmark", "virtu_eval_v1"))
    adapter = os.path.join(LOCAL_ROOT, "checkpoints", "cad_cam_six_software_lora")
    put_dir(sftp, adapter, posixpath.join(REMOTE_ROOT, "adapters", "cad_cam_six_software_lora"))
    with sftp.open(posixpath.join(REMOTE_ROOT, "virtu_eval", "arms.json"), "w") as fh:
        fh.write(json.dumps(REMOTE_ARMS, ensure_ascii=False, indent=2))
    # exclude nothing from multimodal: the instance has no VL weights unless uploaded
    run(c, f"cd {REMOTE_ROOT} && ls virtu_eval && du -sh data adapters && "
           f"wc -l data/benchmark/virtu_eval_v1/*.jsonl")
    sftp.close()


def cmd_run(c, arm, dims, sample, cap, extra):
    dim_arg = ",".join(dims) if dims and dims != ["all"] else ""
    out_dir = posixpath.join(REMOTE_ROOT, "runs", arm)
    log = posixpath.join(REMOTE_ROOT, "runs", f"{arm}.log")
    pidf = posixpath.join(REMOTE_ROOT, "runs", f"{arm}.pid")
    cmd = (f"cd {REMOTE_ROOT} && mkdir -p runs && "
           f"PYTHONPATH={REMOTE_ROOT} nohup {REMOTE_PY} -u virtu_eval/runner.py "
           f"--arm {shlex.quote(arm)} --out-dir {REMOTE_ROOT}/runs/{arm} --case-dir {REMOTE_ROOT}/data/benchmark/virtu_eval_v1 "
           f"--arms-config {REMOTE_ROOT}/virtu_eval/arms.json "
           + (f"--dims {dim_arg} " if dim_arg else "")
           + (f'--sample-per-tier "{sample}" ' if sample else "")
           + (f'--cap-by-tier "{cap}" ' if cap else "")
           + (extra + " " if extra else "")
           + f"> {log} 2>&1 & echo $! > {pidf}")
    rc, out, err = run(c, cmd, timeout=120, quiet=True)
    pid = run(c, f"cat {pidf} 2>/dev/null", quiet=True)[1].strip()
    # nohup over paramiko can silently fail to start: prove the pid is alive AND the log grows
    time.sleep(20)
    alive = run(c, f"ps -p {pid} -o pid=,etime=,cmd= 2>/dev/null", quiet=True)[1].strip()
    size1 = run(c, f"stat -c %s {log} 2>/dev/null", quiet=True)[1].strip()
    time.sleep(25)
    size2 = run(c, f"stat -c %s {log} 2>/dev/null", quiet=True)[1].strip()
    print(f"[launch] pid={pid} alive={bool(alive)} log_bytes {size1}->{size2}")
    print(f"[tail]\n{run(c, f'tail -c 1200 {log} 2>/dev/null', quiet=True)[1]}")
    if not alive:
        print("[WARN] 进程未存活，先看上面的日志尾部再重跑（不要盲启第二个实例）")


def cmd_status(c, arm):
    out_dir = posixpath.join(REMOTE_ROOT, "runs", arm)
    rc, out, _ = run(c, f"wc -l {out_dir}/raw.jsonl 2>/dev/null; "
                       f"tail -c 900 {out_dir}.log 2>/dev/null; "
                       f"nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv | tail -1",
                     quiet=True)
    print(out)


def cmd_fetch(c, arm, dest_root):
    sftp = c.open_sftp()
    local_dir = os.path.join(LOCAL_ROOT, dest_root, arm)
    os.makedirs(local_dir, exist_ok=True)
    for name in ("raw.jsonl", "manifest.json"):
        rp = posixpath.join(REMOTE_ROOT, "runs", arm, name)
        try:
            sftp.get(rp, os.path.join(local_dir, name))
            print("fetched", rp, "->", local_dir)
        except IOError:
            print("missing on remote:", rp)
    try:
        sftp.get(posixpath.join(REMOTE_ROOT, f"runs/{arm}.log"),
                 os.path.join(local_dir, "remote_step.log"))
        print("fetched remote_step.log")
    except IOError:
        pass
    sftp.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["probe", "sync", "run", "status", "fetch"])
    ap.add_argument("--arm", default="virtu_lora_cadcam")
    ap.add_argument("--dims", default="all")
    ap.add_argument("--sample-per-tier", default="")
    ap.add_argument("--cap-by-tier", default="easy=128,medium=320,hard=640")
    ap.add_argument("--extra", default="")
    ap.add_argument("--dest", default="benchmarks/virtu_capability_v1")
    a = ap.parse_args()
    c = client()
    try:
        {"probe": lambda: cmd_probe(c),
         "sync": lambda: cmd_sync(c),
         "run": lambda: cmd_run(c, a.arm, a.dims.split(","), a.sample_per_tier, a.cap_by_tier, a.extra),
         "status": lambda: cmd_status(c, a.arm),
         "fetch": lambda: cmd_fetch(c, a.arm, a.dest)}[a.action]()
    finally:
        c.close()


if __name__ == "__main__":
    main()
