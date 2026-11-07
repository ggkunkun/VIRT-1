import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S
out, err, rc = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen|python3.11' | grep -v grep | head; "
    "echo '=== launch.log tail ==='; tail -n 40 /root/virtu_train/launch.log 2>/dev/null; "
    "echo '=== nvidia-smi ==='; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip(): print("STDERR:", err[:1200])
