# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ug_dir = r'e:\迅雷下载\工程图(1)\UG\SVG源文件'
if os.path.exists(ug_dir):
    files = [f for f in os.listdir(ug_dir) if f.endswith('.svg')]
    print(f"SVG files count: {len(files)}")
    for f in sorted(files)[:25]:
        print("  ", f)
