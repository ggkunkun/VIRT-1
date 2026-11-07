import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S

local = os.path.dirname(os.path.abspath(__file__))
remote_dir = "/root/virtu_train/scripts"
for fn in ["train_qwen3_8b_qlora.py", "cloud_launch.sh"]:
    S.put(os.path.join(local, fn), f"{remote_dir}/{fn}")
    print(f"uploaded {fn}")

# 后台重拉起（云端已有基座+数据，launch 会跳过重装/重下，先 selftest 再训练）
pid = S.run_bg("bash scripts/cloud_launch.sh", "/root/virtu_train", "/root/virtu_train/launch.log")
print("bg launch:", pid)
time.sleep(5)

# 验证进程是否起来 + 看 launch.log 前若干行
out, err, rc = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
    "echo '=== launch.log head ==='; head -n 30 /root/virtu_train/launch.log 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip(): print("STDERR:", err[:1500])
