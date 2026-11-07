# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

drawing_dirs = [
    r'e:\迅雷下载\工程图',
    r'e:\迅雷下载\工程图(1)',
    r'e:\迅雷下载\建模练习图纸',
    r'e:\迅雷下载\UG画图建模练习图'
]

for d in drawing_dirs:
    print(f"\n=== Inspecting {os.path.basename(d)} ===")
    all_files = []
    for root, dirs, files in os.walk(d):
        for f in files:
            all_files.append((f, os.path.relpath(os.path.join(root, f), d)))
    print(f"Total files: {len(all_files)}")
    print("Sample items:")
    for f, rel in all_files[:10]:
        print(f"   {rel}")
