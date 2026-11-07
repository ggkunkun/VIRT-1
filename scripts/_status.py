import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S
out, err, rc = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
    "echo '=== gpu ==='; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null; "
    "echo '=== launch.log tail ==='; tail -n 30 /root/virtu_train/launch.log 2>/dev/null; "
    "echo '=== train.log tail ==='; tail -n 20 /root/virtu_train/train.log 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip(): print("STDERR:", err[:1000])
