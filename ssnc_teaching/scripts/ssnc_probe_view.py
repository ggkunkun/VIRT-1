# -*- coding: utf-8 -*-
"""在 SSCNC 3D 视图窗口('Flashing')上网格探测操作面板热区。
检测：CRT 面板截图差分 + 'SwanSoft CNC' 弹窗（急停等）。JSONL 记录。"""
import os, sys, time, json
os.environ.setdefault("VIRTU_DESKTOP_INPUT", "1")
os.environ.setdefault("VIRTU_DESKTOP_AGENT", "ssnc_verify_view")
sys.path.insert(0, r"D:\Virtu模型")
import win32gui, win32process, subprocess, re, win32con
from PIL import ImageGrab, ImageChops
from virtu_omni.computer_use.action import ActionEngine

eng = ActionEngine()
VIEW = 658968
CRT = 1312486
OUT = r"D:\Virtu模型\ssnc_teaching\evidence\panel_probe_view.jsonl"

def pids():
    out = subprocess.check_output('tasklist /FI "IMAGENAME eq sscnc.exe"', shell=True).decode("mbcs", "ignore")
    return set(int(m.group(1)) for m in re.finditer(r"sscnc\.exe\s+(\d+)", out, re.I))
PIDS = pids()

def find_prompt():
    res = []
    def cb(h, _):
        tid, pid = win32process.GetWindowThreadProcessId(h)
        if pid in PIDS and win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770" and win32gui.GetWindowText(h) == "SwanSoft CNC":
            res.append(h)
        return True
    win32gui.EnumWindows(cb, None)
    return res

def dismiss(dlg):
    kids = []
    def cb(h, _):
        kids.append((h, win32gui.GetClassName(h)))
        return True
    win32gui.EnumChildWindows(dlg, cb, None)
    for h, c in kids:
        if c == "Button":
            win32gui.SendMessage(h, win32con.BM_CLICK, 0, 0)

def crt_shot():
    r = win32gui.GetWindowRect(CRT)
    return ImageGrab.grab(bbox=(max(0,r[0]), max(0,r[1]), min(1920,r[2]), min(1080,r[3])))

def diff_frac(a, b):
    d = ImageChops.difference(a.convert("L"), b.convert("L"))
    hist = d.histogram()
    return sum(hist[24:]) / (a.size[0]*a.size[1])

vr = win32gui.GetWindowRect(VIEW)
print("view rect", vr, flush=True)
x0, y0, x1, y1 = vr[0]+10, vr[1]+10, min(vr[2], 1100), vr[3]-10   # 避开右侧面板区
step = 60
pts = [(x, y) for y in range(y0, y1, step) for x in range(x0, x1, step)]
print("points", len(pts), flush=True)

base = crt_shot()
log = open(OUT, "a", encoding="utf-8")
hits = []
for i, (x, y) in enumerate(pts):
    res = eng.click(x, y)
    if res.get("status") != "executed":
        continue
    time.sleep(0.35)
    p = find_prompt()
    if p:
        log.write(json.dumps({"pt":[x,y],"event":"prompt"}, ensure_ascii=False)+"\n"); log.flush()
        eng.click(x, y); time.sleep(0.4)          # 尝试再次点击释放急停
        for d in find_prompt(): dismiss(d)
        hits.append([x,y,"prompt"])
        continue
    now = crt_shot()
    f = diff_frac(base, now)
    if f > 0.003:
        log.write(json.dumps({"pt":[x,y],"event":"crtdiff","frac":round(f,4)}, ensure_ascii=False)+"\n"); log.flush()
        hits.append([x,y,"diff %.4f"%f])
    base = now
    if i % 25 == 0:
        print("i",i,"hits",len(hits),flush=True)

log.write(json.dumps({"done":True,"hits":hits}, ensure_ascii=False)+"\n"); log.close()
print("DONE", hits, flush=True)
