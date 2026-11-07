# -*- coding: utf-8 -*-
r"""
merge_and_export_v3.py — canonical production merge (TIES-delta 4x recipe).

1. Merges the four r=32 LoRA adapters that produced the validated
   checkpoints/virtu_ties_v1 artifact (30-case toolcall score 88.89, no mojibake):
   - checkpoints/turing_conversational_lora (0.25)
   - checkpoints/cad_cam_six_software_lora (0.25)
   - checkpoints/virtu_toolcall_lora (0.35)
   - checkpoints/ug_teacher_guided_agent_lora (0.15)
   into checkpoints/virtu_cad_cam_merged_v3 using pure streaming numpy
   (--mode delta --normalize-weights; Σw = 1.0).
2. Quantizes and converts the merged model to GGUF format:
   checkpoints/virtu-production-v3-q4_0.gguf
3. Mirrors the resulting GGUF model and receipts to:
   e:\新建文件夹 (3)\TRAINED_MODEL_LORA\

The previous v3 recipe (six LoRAs, Σw=5.7, peft_linear) collapsed the model to
mojibake; its artifacts are preserved under checkpoints/_broken/ for forensics.
"""

import os
import sys
import shutil
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"d:\Virtu模型"
PYTHON = sys.executable

MERGE_SCRIPT = os.path.join(ROOT, "scripts", "merge_numpy.py")
GGUF_SCRIPT = os.path.join(ROOT, "scripts", "hf_to_gguf_numpy.py")

BASE_MODEL = os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")
OUT_MERGED = os.path.join(ROOT, "checkpoints", "virtu_cad_cam_merged_v3")
OUT_GGUF = os.path.join(ROOT, "checkpoints", "virtu-production-v3-q4_0.gguf")

MIRROR_DIR = r"e:\新建文件夹 (3)\TRAINED_MODEL_LORA"
os.makedirs(MIRROR_DIR, exist_ok=True)

# 1. Execute LoRA Merge
print("="*70)
print("PHASE 1: Merging validated 4-adapter TIES-delta recipe ...")
print("="*70)

loras = [
    os.path.join(ROOT, "checkpoints", "turing_conversational_lora"),
    os.path.join(ROOT, "checkpoints", "cad_cam_six_software_lora"),
    os.path.join(ROOT, "checkpoints", "virtu_toolcall_lora"),
    os.path.join(ROOT, "checkpoints", "ug_teacher_guided_agent_lora"),
]
weights = [0.25, 0.25, 0.35, 0.15]
assert abs(sum(weights) - 1.0) < 1e-9, weights

merge_cmd = [
    PYTHON, MERGE_SCRIPT,
    "--base", BASE_MODEL,
    "--out", OUT_MERGED,
    "--mode", "delta",
    "--normalize-weights"
]
for l, w in zip(loras, weights):
    merge_cmd.extend(["--lora", l, "--weight", str(w)])

print("Running command:")
print(" ".join(merge_cmd))

res_merge = subprocess.run(merge_cmd, cwd=ROOT)
if res_merge.returncode != 0:
    print(f"[ERROR] Merge failed with returncode {res_merge.returncode}")
    sys.exit(res_merge.returncode)

print("\n" + "="*70)
print("PHASE 2: Quantizing merged model to Q4_0 GGUF ...")
print("="*70)

gguf_cmd = [
    PYTHON, GGUF_SCRIPT,
    "--model", OUT_MERGED,
    "--out", OUT_GGUF
]
print("Running command:")
print(" ".join(gguf_cmd))

res_gguf = subprocess.run(gguf_cmd, cwd=ROOT)
if res_gguf.returncode != 0:
    print(f"[ERROR] GGUF conversion failed with returncode {res_gguf.returncode}")
    sys.exit(res_gguf.returncode)

print("\n" + "="*70)
print("PHASE 3: Mirroring GGUF model and receipts to e:\\新建文件夹 (3) ...")
print("="*70)

dst_gguf = os.path.join(MIRROR_DIR, os.path.basename(OUT_GGUF))
print(f"Copying {OUT_GGUF} -> {dst_gguf} ...")
shutil.copyfile(OUT_GGUF, dst_gguf)

receipt_gguf = OUT_GGUF.replace(".gguf", ".gguf.receipt.json")
if os.path.exists(receipt_gguf):
    dst_rcpt = os.path.join(MIRROR_DIR, os.path.basename(receipt_gguf))
    shutil.copyfile(receipt_gguf, dst_rcpt)
    print(f"Copying {receipt_gguf} -> {dst_rcpt} ...")

merge_rcpt = os.path.join(OUT_MERGED, "merge_receipt.json")
if os.path.exists(merge_rcpt):
    dst_mrcpt = os.path.join(MIRROR_DIR, "v3_merge_receipt.json")
    shutil.copyfile(merge_rcpt, dst_mrcpt)
    print(f"Copying {merge_rcpt} -> {dst_mrcpt} ...")

sz_gb = os.path.getsize(dst_gguf) / (1024**3)
print(f"\n[DONE] Successfully created and verified GGUF model: {dst_gguf} ({sz_gb:.2f} GB)")
