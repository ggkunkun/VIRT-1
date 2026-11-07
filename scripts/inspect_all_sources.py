# -*- coding: utf-8 -*-
import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

sources = [
    r'e:\迅雷下载\分享数模20-77套UG夹具图档',
    r'e:\迅雷下载\工程图',
    r'e:\迅雷下载\工程图(1)',
    r'e:\迅雷下载\机械设计手册 第六版  PDF(高清)',
    r'e:\迅雷下载\建模练习图纸',
    r'e:\迅雷下载\青沐清晨宏命令',
    r'e:\迅雷下载\自动化设备动画源文件',
    r'e:\迅雷下载\【0基础软件试听课程】',
    r'e:\迅雷下载\100台3C、锂电自动化设备量产图纸',
    r'e:\迅雷下载\A研发设计库',
    r'e:\迅雷下载\GB型材库',
    r'e:\迅雷下载\NX基于特征自动编程',
    r'e:\迅雷下载\SolidWorks软件建模视频讲解',
    r'e:\新建文件夹 (3)',
    r'e:\迅雷下载\UG画图建模练习图'
]

print("="*70)
print("INSPECTING ALL 15 SPECIFIED PATHS")
print("="*70)

summary = {}

for p in sources:
    name = os.path.basename(p)
    if not os.path.exists(p):
        print(f"[MISSING] {name} ({p})")
        summary[name] = {"status": "missing", "path": p}
        continue
    
    if os.path.isfile(p):
        sz = os.path.getsize(p)
        print(f"[FILE] {name} | Size: {sz/(1024*1024):.2f} MB")
        summary[name] = {"type": "file", "path": p, "size_mb": sz/(1024*1024)}
    else:
        file_list = []
        ext_counts = {}
        total_size = 0
        for root, dirs, files in os.walk(p):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    fsz = os.path.getsize(fp)
                except:
                    fsz = 0
                total_size += fsz
                ext = os.path.splitext(f)[1].lower()
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                file_list.append(fp)
        
        sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
        print(f"[DIR] {name}")
        print(f"      Total Files: {len(file_list)} | Total Size: {total_size/(1024*1024):.1f} MB")
        print(f"      Top Extensions: {sorted_exts[:8]}")
        summary[name] = {
            "type": "directory",
            "path": p,
            "total_files": len(file_list),
            "size_mb": total_size/(1024*1024),
            "extensions": ext_counts
        }

print("\nAll inspection complete.")
