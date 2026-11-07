import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S
# 上传修正后的 launch 脚本（便于未来在新实例一键复跑），当前训练不受影响
S.put(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_launch.sh"), "/root/virtu_train/scripts/cloud_launch.sh")
print("uploaded corrected cloud_launch.sh (accelerate==1.15.0)")
# 确认训练仍在跑
out, err, rc = S.run(
    "ps -o pid,etime,pcpu,rss,cmd -p 24723 2>/dev/null | head; "
    "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null; "
    "tail -n 3 /root/virtu_train/train.log 2>/dev/null | tr '\\r' '\\n' | tail -3",
    timeout=60,
)
print(out)
