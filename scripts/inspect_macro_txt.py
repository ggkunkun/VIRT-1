# -*- coding: utf-8 -*-
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

macro_dir = r'e:\迅雷下载\青沐清晨宏命令'
for root, dirs, files in os.walk(macro_dir):
    for f in files:
        if f.endswith('.txt'):
            fp = os.path.join(root, f)
            print(f"=== {f} ({fp}) ===")
            with open(fp, 'r', encoding='gbk', errors='ignore') as fl:
                print(fl.read()[:500])
