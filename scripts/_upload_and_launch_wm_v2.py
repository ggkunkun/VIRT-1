#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传「世界模型 v2（自纠错+设计+工艺+适配）」套件并后台开训 virtu-wm-v2-all90
================================================================================
- 基座 = 云端本地 Qwen3-8B（免下载）
- 在 v3 adapter 之上续训（RESUME_ADAPTER），继承 v3 CNC 能力，叠加世界模型 + 自纠错
- 数据 = data/sft/virtu_worldmodel_v2.jsonl（约 1.2k 条，含自纠错 episode）
- 支持新实例：--host / --port；SSH 密码只从 DAMODEL_PW 环境变量读取
- 开训前做 TCP 预检，离线快速失败（不挂住）

用法：
  DAMODEL_PORT=41858 DAMODEL_PW=xxxx python scripts/_upload_and_launch_wm_v2.py
"""
import os
import sys
import time
import socket
import argparse

LOCAL = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LOCAL)

ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com"))
ap.add_argument("--port", type=int, default=None)
ap.add_argument("--data", default=os.path.join(ROOT, "data", "sft", "virtu_worldmodel_v2.jsonl"))
ap.add_argument("--lr", default="8e-5")
ap.add_argument("--epochs", default="4")
ap.add_argument("--resume", default="checkpoints/virtu_v3_all90")
ap.add_argument("--out", default="checkpoints/virtu_wm_v2_all90")
args = ap.parse_args()

if args.port:
    os.environ["DAMODEL_PORT"] = str(args.port)
os.environ.setdefault("DAMODEL_HOST", args.host)

PORT = int(os.environ.get("DAMODEL_PORT", "41858"))
HOST = os.environ.get("DAMODEL_HOST")
if not os.environ.get("DAMODEL_PW"):
    print("[FATAL] 缺少环境变量 DAMODEL_PW")
    sys.exit(2)

# --- TCP 预检：离线快速失败 ---
s = socket.socket()
s.settimeout(6)
rc = s.connect_ex((HOST, PORT))
s.close()
if rc != 0:
    print(f"[FATAL] 云端不可达 {HOST}:{PORT} (connect_ex={rc})。"
          f"实例可能已被回收，请新开 damodel 实例后设置 DAMODEL_PORT。")
    sys.exit(2)

sys.path.insert(0, LOCAL)
import _ssh_damodel as S  # noqa: E402  (import 后读取上面的环境变量)

REMOTE = "/root/virtu_train"
BASE_DIR = "/root/public-storage/model/Qwen/Qwen3-8B"
DATA_REMOTE = f"{REMOTE}/data/sft/virtu_worldmodel_v2.jsonl"
ADAPTER_LOCAL = os.path.join(ROOT, "checkpoints", "virtu_v3_all90")
DATA_LOCAL = args.data

if not os.path.exists(DATA_LOCAL):
    print(f"[FATAL] 数据不存在：{DATA_LOCAL}（先跑 build_worldmodel_v2.py）")
    sys.exit(2)
if not os.path.exists(os.path.join(ADAPTER_LOCAL, "adapter_model.safetensors")):
    print(f"[FATAL] 缺少 v3 adapter：{ADAPTER_LOCAL}")
    sys.exit(2)

print(f"[preflight] reachable {HOST}:{PORT}")

# 1) 建远程目录
S.run(
    f"mkdir -p {REMOTE}/scripts {REMOTE}/data/sft "
    f"{REMOTE}/checkpoints/virtu_v3_all90 {REMOTE}/{args.out}",
    timeout=60,
)
print("[ok] remote dirs created")

# 2) 上传训练器/启动脚本/校验器
for fn in ["train_qwen3_8b_qlora.py", "cloud_launch.sh", "wm_verifier.py"]:
    src = os.path.join(LOCAL, fn)
    if os.path.exists(src):
        S.put(src, f"{REMOTE}/scripts/{fn}")
        print("[ok] uploaded", fn)

# 3) 上传 v2 数据
S.put(DATA_LOCAL, DATA_REMOTE)
print("[ok] uploaded world-model v2 data")

# 4) 上传 v3 adapter 核心文件（续训基座，~349MB）
for fn in ["adapter_config.json", "adapter_model.safetensors"]:
    S.put(os.path.join(ADAPTER_LOCAL, fn), f"{REMOTE}/checkpoints/virtu_v3_all90/{fn}")
    print("[ok] uploaded v3 adapter", fn)

# 5) 后台开训
cmd = (
    f"BASE_DIR={BASE_DIR} OUT={args.out} "
    f"DATA=data/sft/virtu_worldmodel_v2.jsonl "
    f"RESUME_ADAPTER={args.resume} "
    f"LR={args.lr} EPOCHS={args.epochs} BS=4 ACCUM=4 LORA_R=32 LORA_ALPHA=64 SEED=20261103 "
    f"bash scripts/cloud_launch.sh"
)
pid = S.run_bg(cmd, REMOTE, f"{REMOTE}/launch_wm_v2.log")
print("[ok] background launch:", pid)
time.sleep(10)

out, err, _ = S.run(
    "echo '=== procs ==='; ps aux | grep -E 'cloud_launch|train_qwen' | grep -v grep | head; "
    "echo '=== launch log ==='; head -n 40 /root/virtu_train/launch_wm_v2.log 2>/dev/null",
    timeout=60,
)
print(out)
if err.strip():
    print("STDERR:", err[:1500])
print(f"\n[done] virtu-wm-v2-all90 已在云端后台开训；完成后 adapter 在 {REMOTE}/{args.out}")
