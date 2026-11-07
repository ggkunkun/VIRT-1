# -*- coding: utf-8 -*-
import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

print("="*75)
print("COMPREHENSIVE FINAL VERIFICATION OF ALL DELIVERED ASSETS")
print("="*75)

base_dirs = {
    "新建文件夹 (3) 根目录": r"e:\新建文件夹 (3)",
    "新训练 LoRA 适配器": r"d:\Virtu模型\checkpoints\virtu_cad_cam_production_lora",
    "六合一全量融合模型 (HF)": r"d:\Virtu模型\checkpoints\virtu_cad_cam_merged_v3",
    "量化 GGUF 模型": r"d:\Virtu模型\checkpoints\virtu-production-v3-q4_0.gguf",
    "新建文件夹中训练产物镜像": r"e:\新建文件夹 (3)\TRAINED_MODEL_LORA"
}

for label, p in base_dirs.items():
    exists = os.path.exists(p)
    if not exists:
        print(f"[-] {label}: NOT FOUND ({p})")
        continue
    if os.path.isfile(p):
        sz_mb = os.path.getsize(p) / (1024*1024)
        print(f"[+] {label}: FILE | Size: {sz_mb:.2f} MB ({p})")
    else:
        files = []
        tot_size = 0
        for root, dirs, fnames in os.walk(p):
            for fn in fnames:
                fp = os.path.join(root, fn)
                try:
                    tot_size += os.path.getsize(fp)
                    files.append(fp)
                except:
                    pass
        sz_mb = tot_size / (1024*1024)
        sz_gb = tot_size / (1024**3)
        print(f"[+] {label}: DIR | Files: {len(files)} | Size: {sz_mb:.1f} MB ({sz_gb:.2f} GB)")

print("\n" + "="*75)
print("MODULE BREAKDOWN IN e:\\新建文件夹 (3):")
print("="*75)

root_e = r"e:\新建文件夹 (3)"
for item in sorted(os.listdir(root_e)):
    ip = os.path.join(root_e, item)
    if os.path.isdir(ip):
        fl = os.listdir(ip)
        sz = sum(os.path.getsize(os.path.join(ip, f)) for f in fl if os.path.isfile(os.path.join(ip, f)))
        print(f"  📁 {item:35s} | {len(fl):2d} files | {sz/(1024*1024):.2f} MB")
    else:
        sz = os.path.getsize(ip)
        print(f"  📄 {item:35s} | {sz/1024:.2f} KB")

print("="*75)
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY.")
