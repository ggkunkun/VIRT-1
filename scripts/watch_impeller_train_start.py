# -*- coding: utf-8 -*-
"""盯着远端叶轮训练：检测「基座下载完成 + 训练真正启动」即退出并通知；兼报失败。

训练启动判据（双证）：train_turnkey_impeller 进程在 + GPU 显存占用 > 2000 MiB（模型已载入）。
失败判据：run_impeller_fix.sh 不在 + 无训练进程 + 无交付件 + 日志出现 FATAL/Traceback/Error。
"""
import sys
import json
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
import paramiko  # noqa: E402

CREDS = ROOT / "cloud_train_pack" / ".cloud_creds.json"
MARKER = ROOT / "runs" / "impeller_train_started.marker"


def main():
    cr = json.load(open(CREDS, encoding="utf-8"))
    cl = paramiko.SSHClient()
    cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cl.connect(cr["host"], port=int(cr["port"]), username=cr["user"], password=cr["password"],
               look_for_keys=False, allow_agent=False, timeout=25)

    def run(cmd):
        _, o, e = cl.exec_command(cmd)
        return o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")[-200:]

    try:
        for i in range(120):  # 最多 120×30s = 60 分钟
            log = run("tail -n 5 /root/virtu_train/train.log")
            gpu = run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader").strip()
            proc = run("pgrep -af '[t]rain_turnkey_impeller' | head -1 || echo NO_TRAIN").strip()
            script = run("pgrep -af '[r]un_impeller_fix.sh' | head -1 || echo NO_SCRIPT").strip()
            cfg = run("ls /root/virtu_train/models/Qwen3-8B/config.json 2>/dev/null && echo HAS_CFG || echo NO_CFG")
            deliv = run("ls /root/virtu_train/output/virtu_impeller_fix2_lora/virtu_lora_deliverable.tar.gz /root/virtu_train/output/virtu_impeller_fix_lora/virtu_lora_deliverable.tar.gz 2>/dev/null | head -1 || echo NO_DELIV").strip()
            mem = 0
            try:
                mem = int(gpu.split(",")[1].split()[0])
            except Exception:
                pass
            print(f"[{i}] gpu={gpu} mem={mem} proc={'Y' if 'train_turnkey_impeller' in proc else 'N'} "
                  f"script={'Y' if 'run_impeller_fix' in script else 'N'} cfg={'Y' if 'HAS_CFG' in cfg else 'N'} deliv={'Y' if 'NO_DELIV' not in deliv and deliv else 'N'}", flush=True)
            if deliv and "NO_DELIV" not in deliv:
                print("[DONE] 交付件已生成\n" + log, flush=True)
                return 0
            if mem > 2000 and "train_turnkey_impeller" in proc:
                MARKER.parent.mkdir(parents=True, exist_ok=True)
                MARKER.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "gpu": gpu,
                                              "base_ready": "HAS_CFG" in cfg, "log_tail": log}, ensure_ascii=False), encoding="utf-8")
                print("[TRAINING_STARTED] 基座已下完 + 训练已载入 GPU\n" + gpu + "\n" + log, flush=True)
                return 0
            if ("NO_SCRIPT" in script) and ("NO_TRAIN" in proc) and ("NO_DELIV" in deliv or not deliv):
                tail = run("tail -n 30 /root/virtu_train/train.log")
                if any(k in tail for k in ("FATAL", "Traceback", "Error", "error")):
                    print("[FAILED] 训练脚本退出且日志报错\n" + tail, flush=True)
                    return 1
            time.sleep(30)
        print("[TIMEOUT] 60 分钟内未检测到训练启动", flush=True)
        return 1
    finally:
        cl.close()


if __name__ == "__main__":
    sys.exit(main())
