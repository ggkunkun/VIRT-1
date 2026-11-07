import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S
out, err, rc = S.run(
    "echo '=== 进程 ==='; ps -o pid,etime,pcpu,rss,cmd -C python3.11 2>/dev/null | grep train_qwen | head; "
    "echo '=== GPU ==='; nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null; "
    "echo '=== 训练进度（实时最后一行）==='; tail -c 400 /root/virtu_train/train.log 2>/dev/null | tr '\\r' '\\n' | grep -E '%\\|' | tail -2; "
    "echo '=== 已训练时长 ==='; ps -o etime= -C python3.11 2>/dev/null | head -1",
    timeout=60,
)
print(out)
if err.strip(): print("STDERR:", err[:600])
