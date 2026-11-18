#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import wm_contract as C

def build_v3():
    system = C.build_router_system(with_fewshot=True)
    gguf = os.path.join(ROOT, "checkpoints", "virtu-v3-all90-q4_0.gguf")
    template = """{{ if .System }}system
{{ .System }}
{{ end }}{{ if .Prompt }}user
{{ .Prompt }}
{{ end }}assistant
{{ .Response }}"""
    modelfile = os.path.join(ROOT, "checkpoints", "virtu-v3-hardened.Modelfile")
    content = f"""FROM {gguf}

TEMPLATE \"\"\"{template}\"\"\"

SYSTEM \"\"\"{system}\"\"\"

PARAMETER num_ctx 8192
PARAMETER num_gpu 99
PARAMETER temperature 0
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.15
"""
    with open(modelfile, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Wrote {modelfile}")
    print("[RUN] ollama create virtu-v3:hardened...")
    res = subprocess.run(["ollama", "create", "virtu-v3:hardened", "-f", modelfile], capture_output=True, text=True)
    print("v3 status:", res.stdout.strip() or res.stderr.strip())

def build_13b():
    system = C.build_router_system(with_fewshot=True)
    gguf = os.path.join(ROOT, "models", "virtu-13b", "virtu-13.63b-asym-q3km.gguf")
    template = """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""
    modelfile = os.path.join(ROOT, "models", "virtu-13b", "Modelfile_virtu_13b_hardened")
    content = f"""FROM {gguf}

PARAMETER num_ctx 8192
PARAMETER num_gpu 14
PARAMETER temperature 0
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.15
PARAMETER stop "<|im_end|>"

TEMPLATE \"\"\"{template}\"\"\"

SYSTEM \"\"\"{system}\"\"\"
"""
    with open(modelfile, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Wrote {modelfile}")
    print("[RUN] ollama create virtu-13.63b:hardened...")
    res = subprocess.run(["ollama", "create", "virtu-13.63b:hardened", "-f", modelfile], capture_output=True, text=True)
    print("13b status:", res.stdout.strip() or res.stderr.strip())

def build_moe():
    system = C.build_router_system(with_fewshot=True)
    blob = r"E:\ollama\models\blobs\sha256-a2103c68d9e881ac3655ce271902997cdc8eb5c35da3803261f25f5364e52d7a"
    template = """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""
    modelfile = os.path.join(ROOT, "checkpoints", "Modelfile.virtu_moe_14b_hardened")
    content = f"""FROM {blob}

PARAMETER num_ctx 8192
PARAMETER num_gpu 14
PARAMETER temperature 0
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.15
PARAMETER stop "<|im_end|>"

TEMPLATE \"\"\"{template}\"\"\"

SYSTEM \"\"\"{system}\"\"\"
"""
    with open(modelfile, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Wrote {modelfile}")
    print("[RUN] ollama create virtu-moe-14b:hardened...")
    res = subprocess.run(["ollama", "create", "virtu-moe-14b:hardened", "-f", modelfile], capture_output=True, text=True)
    print("moe status:", res.stdout.strip() or res.stderr.strip())

if __name__ == "__main__":
    build_v3()
    build_13b()
    build_moe()
