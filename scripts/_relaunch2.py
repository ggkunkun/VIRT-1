import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S

local = os.path.dirname(os.path.abspath(__file__))
S.put(os.path.join(local, "cloud_launch.sh"), "/root/virtu_train/scripts/cloud_launch.sh")
print("uploaded cloud_launch.sh")

pid = S.run_bg("bash scripts/cloud_launch.sh", "/root/virtu_train", "/root/virtu_train/launch.log")
print("bg launch returned:", pid)

# 给云端一点时间升级 accelerate + selftest + 开训
for wait in [40, 60]:
    time.sleep(wait)
    out, err, rc = S.run(
        "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
        "echo '=== gpu ==='; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null; "
        "echo '=== launch.log tail ==='; tail -n 25 /root/virtu_train/launch.log 2>/dev/null",
        timeout=60,
    )
    print(f"--- check after {sum([40,60][:len([40,60]) if wait==60 else 1])}s ---")
    print(out)
    if "LAUNCHING TRAINING" in out and "ERROR" not in out:
        break
