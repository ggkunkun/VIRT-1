# -*- coding: utf-8 -*-
"""watch_impeller_train_health.py — 训练健康看门狗：进度跟踪 + 异常即停即报。

异常判据（保守，避免误杀慢速但推进中的训练）：
  A. 日志新增 Traceback/FATAL/CUDA error/OutOfMemory → 异常
  B. 训练进程消失且无交付件 → 异常
  C. 步数停滞 ≥420s 且 进程在 且 GPU util<10%（双边确认）→ 判定真停滞，杀掉训练并报
正常完成：交付件出现 → 报成功退出。
"""
import sys
import json
import re
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
import paramiko  # noqa: E402

STEP_RE = re.compile(r"\|\s*(\d+)/(\d+)\s*\[")


def main():
    cr = json.load(open(ROOT / "cloud_train_pack" / ".cloud_creds.json", encoding="utf-8"))
    cl = paramiko.SSHClient()
    cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cl.connect(cr["host"], port=int(cr["port"]), username=cr["user"], password=cr["password"],
               look_for_keys=False, allow_agent=False, timeout=25)

    def run(cmd):
        _, o, e = cl.exec_command(cmd)
        return o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")[-150:]

    last_step = -1
    last_change = time.time()
    try:
        for i in range(160):  # 最多 160×30s = 80 分钟
            tail = run("tail -c 2500 /root/virtu_train/train.log")
            errs = run("grep -cE 'Traceback|FATAL|CUDA error|OutOfMemory' /root/virtu_train/train.log 2>/dev/null").strip()
            gpu = run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader").strip()
            proc = run("pgrep -f '[t]rain_turnkey_impeller' | head -1 || echo NO").strip()
            deliv = run("ls /root/virtu_train/output/virtu_impeller_fix2_lora/virtu_lora_deliverable.tar.gz /root/virtu_train/output/virtu_impeller_fix_lora/virtu_lora_deliverable.tar.gz 2>/dev/null | head -1 || echo NO").strip()
            steps = STEP_RE.findall(tail)
            cur = int(steps[-1][0]) if steps else last_step
            tot = steps[-1][1] if steps else "?"
            util = 0
            try:
                util = int(gpu.split(",")[0].split()[0])
            except Exception:
                pass
            if cur != last_step:
                last_step = cur
                last_change = time.time()
            stalled = (time.time() - last_change) > 420
            has_deliv = bool(deliv and deliv != "NO")
            print(f"[{i}] step={cur}/{tot} util={util}% errs={errs} proc={'Y' if proc != 'NO' else 'N'} "
                  f"deliv={'Y' if has_deliv else 'N'} stall={int(time.time() - last_change)}s", flush=True)

            if has_deliv:
                print("[SUCCESS] 交付件已生成，训练完成。", flush=True)
                return 0
            if errs not in ("0", ""):
                print(f"[ANOMALY] 日志出现错误(计数={errs})，训练可能已崩。最近日志：\n{tail[-500:]}", flush=True)
                return 2
            if proc == "NO" and not has_deliv:
                print(f"[ANOMALY] 训练进程消失且无交付件。最近日志：\n{tail[-500:]}", flush=True)
                return 2
            if stalled and proc != "NO" and util < 10:
                print(f"[ANOMALY] 真停滞：步数 {cur} 已 {int(time.time() - last_change)}s 未进且 GPU 空闲。停止训练并汇报。", flush=True)
                run("pkill -9 -f '[t]rain_turnkey_impeller'; pkill -9 -f '[r]un_impeller_fix'; echo killed")
                return 3
            time.sleep(30)
        print("[TIMEOUT] 80 分钟监控窗口结束", flush=True)
        return 1
    finally:
        cl.close()


if __name__ == "__main__":
    sys.exit(main())
