#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/register_dense_ties.py — 把合成好的稠密 HF 目录注册成 Ollama 模型。

做法：从 virtu-comprehensive:latest 的 Modelfile 里原样继承 TEMPLATE（ChatML + tools 分支），
只替换 FROM 指向新的 safetensors 目录、替换 SYSTEM、追加服务参数。这样 chat 行为与既有
Virtu 模型完全一致，避免"新模型换了模板导致对比不公平"。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF_DIR = "D:/Virtu模型/checkpoints/virtu_dense_ties_hf"
OUT_MF = ROOT / "Modelfile_virtu_dense_ties_q4"

SYSTEM = (
    "你是 Virtu 工业工程助手，服务数控加工与机械设计。\n"
    "回答规则：\n"
    "1. 直接给结论与可执行步骤；禁止描述你的「内部专家」「分工」「推理过程」或模拟调用过程。\n"
    "2. 涉及 G 代码或软件 API 时给出完整可运行片段，并标注控制器方言（FANUC / Siemens）。\n"
    "3. 不确定就说不确定，不要编造数值、标准号或 API 名称。\n"
    "4. 默认中文回答，代码与代号保留原文。"
)

PARAMS = [
    ("num_ctx", "4096"),
    ("num_gpu", "99"),
    ("temperature", "0.1"),
    ("top_p", "0.9"),
    ("repeat_penalty", "1.15"),
    ("repeat_last_n", "256"),
    ("stop", "<|im_start|>"),
    ("stop", "<|im_end|>"),
]


def main():
    src = subprocess.run(["ollama", "show", "virtu-comprehensive:latest", "--modelfile"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    if "TEMPLATE" not in src:
        print("FATAL: 源 Modelfile 里没有 TEMPLATE，无法继承", file=sys.stderr)
        sys.exit(1)

    # 取 TEMPLATE 块（从 TEMPLATE 起到下一个顶层关键字前）
    m = re.search(r'(TEMPLATE\s+"""(?:.|\n)*?""")', src)
    if not m:
        m = re.search(r'(TEMPLATE\s+.*?)(?=\n[A-Z]+ |\Z)', src, re.S)
    template_block = m.group(1)

    lines = [f"FROM {HF_DIR}", template_block, f'SYSTEM """{SYSTEM}"""']
    lines += [f"PARAMETER {k} {v}" for k, v in PARAMS]
    OUT_MF.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"written {OUT_MF} ({OUT_MF.stat().st_size} bytes)")
    print(f"template bytes kept: {len(template_block)}")
    print(json.dumps({"hf_dir": HF_DIR, "params": PARAMS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
