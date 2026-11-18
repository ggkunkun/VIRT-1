#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import wm_contract as C

BLOB_PATH = r"E:\ollama\models\blobs\sha256-a2103c68d9e881ac3655ce271902997cdc8eb5c35da3803261f25f5364e52d7a"
OUT_PATH = os.path.join(ROOT, "checkpoints", "Modelfile.virtu_moe_14b_hardened")

template = """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""

system = C.build_router_system(with_fewshot=True)

lines = [
    f"FROM {BLOB_PATH}",
    "",
    "PARAMETER num_ctx 8192",
    "PARAMETER num_gpu 20",
    "PARAMETER temperature 0",
    "PARAMETER top_p 0.9",
    "PARAMETER repeat_penalty 1.15",
    'PARAMETER stop "<|im_end|>"',
    "",
    'TEMPLATE """' + template + '"""',
    "",
    'SYSTEM """' + system + '"""',
    "",
]

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"[OK] Generated {OUT_PATH} ({len(lines)} lines)")
