# -*- coding: utf-8 -*-
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

nx_dir = r'e:\迅雷下载\NX基于特征自动编程'
for root, dirs, files in os.walk(nx_dir):
    for f in files:
        if f in ['machining_data.tcl', 'dbc_tool_ascii.tcl', 'feeds_speeds.tcl', '使用说明.txt']:
            fp = os.path.join(root, f)
            print(f"=== {fp} ===")
            with open(fp, 'r', encoding='utf-8', errors='ignore') as fl:
                lines = [fl.readline() for _ in range(15)]
            print("".join(lines[:10]))
