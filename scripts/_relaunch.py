import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S

local = os.path.dirname(os.path.abspath(__file__))
# 重新上传修正后的 launch 脚本（train 脚本已传过且无需再改）
S.put(os.path.join(local, "cloud_launch.sh"), "/root/virtu_train/scripts/cloud_launch.sh")
print("uploaded cloud_launch.sh")

pid = S.run_bg("bash scripts/cloud_launch.sh", "/root/virtu_train", "/root/virtu_train/launch.log")
print("bg launch pid:", pid)
time.sleep(8)

out, err, rc = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
    "echo '=== launch.log (first 40) ==='; head -n 40 /root/virtu_train/launch.log 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip(): print("STDERR:", err[:1500])
