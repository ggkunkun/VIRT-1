# -*- coding: utf-8 -*-
"""对候选热区逐点复测：快照 CRT 全部静态文本，点击后 diff。"""
import os, sys, time, json
os.environ.setdefault("VIRTU_DESKTOP_INPUT", "1")
os.environ.setdefault("VIRTU_DESKTOP_AGENT", "ssnc_verify_hits")
sys.path.insert(0, r"D:\Virtu模型")
import win32gui, win32con
from virtu_omni.computer_use.action import ActionEngine

eng = ActionEngine()
CRT = 1312486
POINTS = [(970,970),(1030,970),(850,1030),(910,1030),(10,1030),(130,1030)]

def snapshot():
    s = {}
    def cb(h, _):
        if win32gui.GetClassName(h) == "Static":
            s[h] = win32gui.GetWindowText(h)
        return True
    win32gui.EnumChildWindows(CRT, cb, None)
    return s

def buttons_state():
    s = {}
    def cb(h, _):
        if win32gui.GetClassName(h) == "Button":
            s[h] = win32gui.GetWindowText(h)
    win32gui.EnumChildWindows(CRT, cb, None)
    return s

out = open(r"D:\Virtu模型\ssnc_teaching\evidence\hit_reprobe.jsonl", "a", encoding="utf-8")
for pt in POINTS:
    before = snapshot()
    res = eng.click(*pt)
    time.sleep(0.6)
    after = snapshot()
    diff = {h: (before.get(h), after.get(h)) for h in set(before) | set(after) if before.get(h) != after.get(h)}
    # 过滤全空->空
    diff = {h: v for h, v in diff.items() if v[0] != v[1]}
    out.write(json.dumps({"pt": list(pt), "status": res.get("status"), "diff": {str(k): v for k, v in diff.items()}}, ensure_ascii=False) + "\n")
    out.flush()
    print("pt", pt, "changes", len(diff))
    for h, v in list(diff.items())[:15]:
        print("   ", v)
out.close()
