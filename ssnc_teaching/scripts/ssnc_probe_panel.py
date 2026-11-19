# -*- coding: utf-8 -*-
"""探测 SSCNC FANUC 面板 Button1 网格各键的功能：BM_CLICK 后读取 CRT 静态文本差异。"""
import time, json
import win32gui, win32con

CRT = 1312486
RIGHT = 919760

def statics(root):
    out = {}
    def cb(h, _):
        if win32gui.GetClassName(h) == "Static":
            t = win32gui.GetWindowText(h)
            if t.strip():
                out[h] = t
        return True
    win32gui.EnumChildWindows(root, cb, None)
    return out

def listview_texts(root):
    out = []
    def cb(h, _):
        if win32gui.GetClassName(h) == "SysListView32":
            n = win32gui.SendMessage(h, win32con.LVM_GETITEMCOUNT, 0, 0)
            out.append((h, n))
        return True
    win32gui.EnumChildWindows(root, cb, None)
    return out

def buttons(root):
    out = []
    def cb(h, _):
        if win32gui.GetClassName(h) == "Button":
            out.append((h, win32gui.GetDlgCtrlID(h), win32gui.GetWindowText(h), win32gui.GetWindowRect(h)))
        return True
    win32gui.EnumChildWindows(root, cb, None)
    return out

def snapshot():
    s = {}
    s.update(statics(CRT))
    s.update(statics(RIGHT))
    return s

base = snapshot()
btns = [b for b in buttons(RIGHT) if b[2] == "Button1"]
btns.sort(key=lambda b: (b[3][1], b[3][0]))
print("Button1 count:", len(btns))

results = []
for h, cid, _, r in btns:
    win32gui.SendMessage(h, win32con.BM_CLICK, 0, 0)
    time.sleep(0.5)
    now = snapshot()
    diff = {k: v for k, v in now.items() if base.get(k) != v}
    # 也记录消失的
    gone = {k: base[k] for k in base if k not in now}
    desc = {k: (base.get(k), now.get(k)) for k in set(diff) | set(gone)}
    results.append({"btn": h, "id": cid, "rect": r, "diff": {str(k): v for k, v in desc.items()}})
    print("btn id=%s rect=%s -> %d text changes" % (cid, r, len(desc)))
    for k, v in list(desc.items())[:8]:
        print("    ", v)
    base = now  # 逐键累积状态

time.sleep(1)
json.dump(results, open("ssnc_teaching/evidence/panel_probe_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved evidence/panel_probe_results.json")
