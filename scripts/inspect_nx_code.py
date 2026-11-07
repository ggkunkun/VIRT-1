# -*- coding: utf-8 -*-
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

nx_dir = r'e:\迅雷下载\NX基于特征自动编程'
for fn in ['cut_methods.tcl', 'machining_data.tcl', 'dbc_tool_ascii.tcl', 'feeds_speeds.tcl']:
    fp = os.path.join(nx_dir, fn)
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(25)]
        print(f"=== {fn} ===")
        print("".join(lines[:12]))
