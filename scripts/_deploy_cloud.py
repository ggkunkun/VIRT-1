#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把训练包上传到 DamoModel 云端实例并后台启动训练。
依赖 scripts/_ssh_damodel.py（读取 DAMODEL_* 环境变量）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ssh_damodel as ssh  # noqa: E402

ROOT = os.path.dirname(HERE)
REMOTE_ROOT = "/root/virtu_train"

# (本地路径, 远端相对 REMOTE_ROOT 的路径)
FILES = [
    ("scripts/train_qwen3_8b_qlora.py", "scripts/train_qwen3_8b_qlora.py"),
    ("scripts/cloud_launch.sh", "scripts/cloud_launch.sh"),
    ("data/sft/virtu_capability_sft_v6.jsonl", "data/sft/virtu_capability_sft_v6.jsonl"),
    ("scripts/_pkg_README.md", "README_PACKAGE.md"),
    ("CLOUD_FINETUNE_PLAN.md", "CLOUD_FINETUNE_PLAN.md"),
]


def upload_all():
    for local_rel, remote_rel in FILES:
        local = os.path.join(ROOT, local_rel)
        remote = REMOTE_ROOT + "/" + remote_rel
        ssh.put(local, remote)


def main():
    print("===== upload =====")
    upload_all()
    print("===== launch training (detached) =====")
    pid = ssh.run_bg(
        "bash scripts/cloud_launch.sh",
        cwd=REMOTE_ROOT,
        log=REMOTE_ROOT + "/train.log",
    )
    print("launched:", pid)
    print("remote log:", REMOTE_ROOT + "/train.log")
    print("monitor:  python scripts/_ssh_damodel.py \"tail -n 40 /root/virtu_train/train.log\"")


if __name__ == "__main__":
    main()
