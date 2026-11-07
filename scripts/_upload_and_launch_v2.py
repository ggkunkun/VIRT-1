#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传训练套件到 DamoModel 39473 实例并后台开训（v2，全部90计划）。
- 复用成熟训练器 train_qwen3_8b_qlora.py + cloud_launch.sh。
- BASE_DIR 指向云端本地基座 /root/public-storage/model/Qwen/Qwen3-8B，省去下载。
- 训练以 setsid 脱离会话启动，SSH 断开也不被杀；日志落 /root/virtu_train/launch.log。
- 训练完产物在 /root/virtu_train/checkpoints/virtu_v2_all90。
SSH 密码只从 DAMODEL_PW 环境变量读取，不打印。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S

LOCAL = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LOCAL)
REMOTE = "/root/virtu_train"
BASE_DIR = "/root/public-storage/model/Qwen/Qwen3-8B"
DATA_LOCAL = os.path.join(ROOT, "data", "sft", "virtu_capability_sft_v6.jsonl")
DATA_REMOTE = f"{REMOTE}/data/sft/virtu_capability_sft_v6.jsonl"

# 1) 建远程目录
S.run(f"mkdir -p {REMOTE}/scripts {REMOTE}/data/sft {REMOTE}/checkpoints", timeout=60)
print("[ok] remote dirs created")

# 2) 上传脚本
for fn in ["train_qwen3_8b_qlora.py", "cloud_launch.sh", "train_virtu_v2.sh"]:
    S.put(os.path.join(LOCAL, fn), f"{REMOTE}/scripts/{fn}")
    print("[ok] uploaded", fn)

# 3) 上传数据（11MB）
S.put(DATA_LOCAL, DATA_REMOTE)
print("[ok] uploaded data")

# 4) 后台开训：用云端本地基座，2 epoch，低 lr 防过拟合
cmd = (
    f"BASE_DIR={BASE_DIR} OUT=checkpoints/virtu_v2_all90 "
    f"LR=1.5e-4 EPOCHS=2 BS=4 ACCUM=4 LORA_R=32 LORA_ALPHA=64 SEED=20261102 "
    f"bash scripts/cloud_launch.sh"
)
pid = S.run_bg(cmd, REMOTE, f"{REMOTE}/launch.log")
print("[ok] background launch:", pid)
time.sleep(8)

# 5) 验证进程起来 + 看 launch.log 前若干行
out, err, rc = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
    "echo '=== launch.log head ==='; head -n 45 /root/virtu_train/launch.log 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip():
    print("STDERR:", err[:1500])
print("\n[done] 训练已在云端后台启动；完成后 adapter 在", REMOTE + "/checkpoints/virtu_v2_all90")
