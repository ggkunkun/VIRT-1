#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传训练套件到 DamoModel 新实例(41858)并后台开训（v3，全部90计划的定向精修轮）。
- 复用成熟训练器 train_qwen3_8b_qlora.py + cloud_launch.sh。
- BASE_DIR 指向云端本地基座 /root/public-storage/model/Qwen/Qwen3-8B（省去下载，零上传成本）。
- 数据用已就绪的定向精标集 data/sft/virtu_v2_curated.jsonl（854 条：
  含 500 条 v6 反遗忘 replay + 354 条弱点定向修复），只上传这个小文件。
- 训练以 setsid 脱离会话启动，SSH 断开也不被杀；日志落 /root/virtu_train/launch_v3.log。
- SSH 密码只从 DAMODEL_PW 环境变量读取，不打印。
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
DATA_LOCAL = os.path.join(ROOT, "data", "sft", "virtu_v2_curated.jsonl")
DATA_REMOTE = f"{REMOTE}/data/sft/virtu_v2_curated.jsonl"

# 1) 建远程目录
S.run(f"mkdir -p {REMOTE}/scripts {REMOTE}/data/sft {REMOTE}/checkpoints", timeout=60)
print("[ok] remote dirs created")

# 2) 上传脚本
for fn in ["train_qwen3_8b_qlora.py", "cloud_launch.sh"]:
    S.put(os.path.join(LOCAL, fn), f"{REMOTE}/scripts/{fn}")
    print("[ok] uploaded", fn)

# 3) 上传定向精标数据（约 1-2MB）
S.put(DATA_LOCAL, DATA_REMOTE)
print("[ok] uploaded curated data (854)")

# 4) 后台开训：用云端本地基座，3 epoch（小数据多过几遍让定向项更稳），低 lr 防过拟合
cmd = (
    f"BASE_DIR={BASE_DIR} OUT=checkpoints/virtu_v3_all90 "
    f"DATA=data/sft/virtu_v2_curated.jsonl "
    f"LR=1.5e-4 EPOCHS=3 BS=4 ACCUM=4 LORA_R=32 LORA_ALPHA=64 SEED=20261103 "
    f"bash scripts/cloud_launch.sh"
)
pid = S.run_bg(cmd, REMOTE, f"{REMOTE}/launch_v3.log")
print("[ok] background launch:", pid)
time.sleep(10)

# 5) 验证进程起来 + 看 launch_v3.log 前若干行
out, err, rc = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
    "echo '=== launch_v3.log head ==='; head -n 40 /root/virtu_train/launch_v3.log 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip():
    print("STDERR:", err[:1500])
print("\n[done] v3 训练已在云端后台启动；完成后 adapter 在", REMOTE + "/checkpoints/virtu_v3_all90")
