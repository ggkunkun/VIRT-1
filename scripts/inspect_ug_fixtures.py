# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

fixture_dir = r'e:\迅雷下载\分享数模20-77套UG夹具图档'
files = [f for f in os.listdir(fixture_dir) if f.endswith('.prt')]
print(f"Total UG fixture .prt files: {len(files)}")
print("Sample files:", files[:20])
