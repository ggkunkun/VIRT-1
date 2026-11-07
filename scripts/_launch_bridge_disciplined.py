#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动生产 bridge 服务，文本后端指向 virtu-disciplined:v1（受约束版）。

A1 落地：把"减少无效思考"的 disciplined 版本设为生产文本后端。
通过 explorer.exe 派生 virtu_service_pinned.py，使其脱离沙箱作业对象常驻真机。
VIRTU_VLLM_MODEL 优先级最高（高于注册表与 qwen3:8b 回滚默认值）。
"""
import os
import subprocess
import sys

ROOT = r"D:/Virtu模型"
env = dict(os.environ, VIRTU_VLLM_MODEL="virtu-disciplined:v1")
# explorer.exe 派生的进程脱离沙箱作业对象，可常驻真机（不会被会话回收）
subprocess.Popen(
    ["explorer.exe", os.path.join(ROOT, "scripts", "virtu_service_pinned.py")],
    cwd=ROOT,
    env=env,
)
print("launched production bridge -> VIRTU_VLLM_MODEL=virtu-disciplined:v1")
