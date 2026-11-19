# -*- coding: utf-8 -*-
"""在 SSCNC 3D 视图区网格探测可点击热区：截图差分 + 弹窗检测。
所有鼠标动作经 ActionEngine/input_guard。输出 JSONL 到 evidence/panel_probe_3d.jsonl。"""
import os, sys, time, json
os.environ.setdefault("VIRTU_DESKTOP_INPUT", "1")
os.environ.setdefault("VIRTU_DESKTOP_AGENT", "ssnc_verify_3d")
sys.path.insert(0, r"D:\Virtu模型")
import win32gui, win32process, subprocess, re
from PIL import ImageGrab, ImageChops
from virtu_omni.computer_use.action import ActionEngine

eng = ActionEngine()
MAIN = 2297508
CRT = 1312486
OUT = r"D:\Virtu模型\ssnc_teaching\evidence\panel_probe_3d.jsonl"

def sscnc_pids():
    out = subprocess.check_output('tasklist /FI "IMAGENAME eq sscnc.exe"', shell=True).decode("mbcs", "ignore")
    return set(int(m.group(1)) for m in re.finditer(r"sscnc\.exe\s+(\d+)", out, re.I))

PIDS = sscnc_pids()

def find_prompt():
    res = []
    def cb(h, _):
        tid, pid = win32process.GetWindowThreadProcessId(h)
        if pid in PIDS and win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770" and win32gui.GetWindowText(h) == "SwanSoft CNC":
            res.append(h)
        return True
    win32gui.EnumWindows(cb, None)
    return res

def dismiss_prompt(dlg):
    kids = []
    def cb(h, _):
        kids.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h)))
        return True
    win32gui.EnumChildWindows(dlg, cb, None)
    for h, c, t in kids:
        if c == "Button":
            win32gui.SendMessage(h, win32con_BM_CLICK(), 0, 0)

def win32con_BM_CLICK():
    import win32con
    return win32con.BM_CLICK

def crt_shot():
    r = win32gui.GetWindowRect(CRT)
    return ImageGrab.grab(bbox=(max(0,r[0]), max(0,r[1]), r[2], r[3]))

def diff_frac(a, b):
    d = ImageChops.difference(a.convert("L"), b.convert("L"))
    hist = d.histogram()
    changed = sum(hist[16:])
    return changed / (a.size[0]*a.size[1])

# 3D 视图区域 = 主窗口客户区减去左侧 NC 编辑视图
main_r = win32gui.GetWindowRect(MAIN)
# MDIClient 与编辑视图
mdiclient = 2036388
editview = 1379448
mc = win32gui.GetWindowRect(mdiclient)
ev = win32gui.GetWindowRect(editview)
# 3D 区：MDIClient 内 editview 右侧部分
x0, y0 = ev[2] + 8, mc[1] + 8
x1, y1 = mc[2] - 8, mc[3] - 8
print("probe region", (x0,y0,x1,y1), flush=True)

base = crt_shot()
log = open(OUT, "a", encoding="utf-8")
step = 55
pts = []
y = y0
while y < y1:
    x = x0
    while x < x1:
        pts.append((x, y))
        x += step
    y += step
print("points:", len(pts), flush=True)

hits = []
for i, (x, y) in enumerate(pts):
    res = eng.click(x, y)
    if res.get("status") != "executed":
        log.write(json.dumps({"pt": [x,y], "skip": res.get("status")}, ensure_ascii=False)+"\n"); log.flush()
        continue
    time.sleep(0.35)
    p = find_prompt()
    if p:
        # 记录并再次点击同位置尝试释放（急停为点按切换）
        log.write(json.dumps({"pt": [x,y], "event": "prompt", "dlg": p[0]}, ensure_ascii=False)+"\n"); log.flush()
        eng.click(x, y); time.sleep(0.4)
        p2 = find_prompt()
        for d in p2:
            dismiss_prompt(d)
        hits.append((x,y,"prompt"))
        continue
    now = crt_shot()
    f = diff_frac(base, now)
    if f > 0.002:
        log.write(json.dumps({"pt": [x,y], "event": "crtdiff", "frac": round(f,4)}, ensure_ascii=False)+"\n"); log.flush()
        hits.append((x,y,"crtdiff %.4f"%f))
    base = now
    if i % 20 == 0:
        print("i", i, "hits", len(hits), flush=True)

log.write(json.dumps({"done": True, "hits": hits}, ensure_ascii=False)+"\n")
log.close()
print("DONE hits:", hits, flush=True)
