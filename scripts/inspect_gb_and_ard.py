# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

gb_dir = r'e:\迅雷下载\GB型材库'
print("=== INSPECTING GB型材库 ===")
categories = [d for d in os.listdir(gb_dir) if os.path.isdir(os.path.join(gb_dir, d))]
print(f"Total standard categories: {len(categories)}")
for cat in categories:
    cp = os.path.join(gb_dir, cat)
    files = [f for f in os.listdir(cp) if f.endswith('.sldlfp')]
    print(f"  Category: {cat} ({len(files)} specs) -> samples: {files[:3]}")

ard_dir = r'e:\迅雷下载\A研发设计库'
print("\n=== INSPECTING A研发设计库 ===")
ard_subdirs = [d for d in os.listdir(ard_dir) if os.path.isdir(os.path.join(ard_dir, d))]
print(f"Total component categories: {len(ard_subdirs)}")
for sub in ard_subdirs:
    sp = os.path.join(ard_dir, sub)
    files = os.listdir(sp)
    print(f"  Subsystem: {sub} ({len(files)} items) -> samples: {files[:4]}")
