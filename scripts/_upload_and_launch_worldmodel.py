#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传「世界模型」训练套件到 DamoModel 实例并后台开训（virtu-wm-all90）。
- 基座 = 云端本地 Qwen3-8B（免下载，零基座上传）。
- 在 v3 adapter 之上「继续微调」（RESUME_ADAPTER=checkpoints/virtu_v3_all90）：
  继承 v3 全部 CNC 能力（generation 已破 90），叠加世界状态预测能力。
- 数据 = virtu_worldmodel.jsonl（670 条：第一性原理可复算世界状态 + 鲁棒性负样本）。
- 小 lr + 多 epoch 温和注入世界模型表征，避免遗忘。
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
DATA_LOCAL = os.path.join(ROOT, "data", "sft", "virtu_worldmodel.jsonl")
DATA_REMOTE = f"{REMOTE}/data/sft/virtu_worldmodel.jsonl"
ADAPTER_LOCAL = os.path.join(ROOT, "checkpoints", "virtu_v3_all90")

# 1) 建远程目录
S.run(
    f"mkdir -p {REMOTE}/scripts {REMOTE}/data/sft "
    f"{REMOTE}/checkpoints/virtu_v3_all90 {REMOTE}/checkpoints/virtu_wm_all90",
    timeout=60,
)
print("[ok] remote dirs created")

# 2) 上传训练器/启动脚本
for fn in ["train_qwen3_8b_qlora.py", "cloud_launch.sh"]:
    S.put(os.path.join(LOCAL, fn), f"{REMOTE}/scripts/{fn}")
    print("[ok] uploaded", fn)

# 3) 上传世界模型数据（670 条，几百 KB）
S.put(DATA_LOCAL, DATA_REMOTE)
print("[ok] uploaded world-model data (670)")

# 4) 上传 v3 adapter 核心文件（续训基座，~349MB；tokenizer 复用云端 Qwen3-8B）
for fn in ["adapter_config.json", "adapter_model.safetensors"]:
    S.put(os.path.join(ADAPTER_LOCAL, fn), f"{REMOTE}/checkpoints/virtu_v3_all90/{fn}")
    print("[ok] uploaded v3 adapter", fn)

# 5) 后台开训：在 v3 之上续训世界模型
cmd = (
    f"BASE_DIR={BASE_DIR} OUT=checkpoints/virtu_wm_all90 "
    f"DATA=data/sft/virtu_worldmodel.jsonl "
    f"RESUME_ADAPTER=checkpoints/virtu_v3_all90 "
    f"LR=8e-5 EPOCHS=4 BS=4 ACCUM=4 LORA_R=32 LORA_ALPHA=64 SEED=20261103 "
    f"bash scripts/cloud_launch.sh"
)
pid = S.run_bg(cmd, REMOTE, f"{REMOTE}/launch_wm.log")
print("[ok] background launch:", pid)
time.sleep(10)

# 6) 验证进程起来
out, err, rc = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
    "echo '=== launch_wm.log head ==='; head -n 40 /root/virtu_train/launch_wm.log 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip():
    print("STDERR:", err[:1500])
print("\n[done] 世界模型训练已在云端后台启动（v3 基座续训）；完成后 adapter 在",
      REMOTE + "/checkpoints/virtu_wm_all90")
