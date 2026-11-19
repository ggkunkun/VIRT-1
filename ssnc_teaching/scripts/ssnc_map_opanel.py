# -*- coding: utf-8 -*-
"""操作面板 55 键实证测绘：逐键 BM_CLICK，记录 CRT 截图差分、静态文本差分、弹窗事件。
不猜功能——每个键的效果用测量数据说话。输出 panel_opanel_probe.jsonl。"""
import os, sys, time, json
os.environ.setdefault("VIRTU_DESKTOP_INPUT", "1")
os.environ.setdefault("VIRTU_DESKTOP_AGENT", "ssnc_opanel_map")
sys.path.insert(0, r"D:\Virtu模型")
import win32gui, win32con, win32process, subprocess, re
from PIL import ImageGrab, ImageChops

PANEL = 68412
CRT = 198146
OUT = r"D:\Virtu模型\ssnc_teaching\evidence\panel_opanel_probe.jsonl"

def pids():
    out = subprocess.check_output('tasklist /FI "IMAGENAME eq sscnc.exe"', shell=True).decode("mbcs", "ignore")
    return set(int(m.group(1)) for m in re.finditer(r"sscnc\.exe\s+(\d+)", out, re.I))
PIDS = pids()

def find_prompt():
    res = []
    def cb(h, _):
        tid, pid = win32process.GetWindowThreadProcessId(h)
        if pid in PIDS and win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770" and win32gui.GetWindowText(h) == "SwanSoft CNC":
            # 读提示文字
            txt = []
            def cc(x, _):
                if win32gui.GetClassName(x) == "Static":
                    t = win32gui.GetWindowText(x)
                    if t.strip(): txt.append(t)
                return True
            win32gui.EnumChildWindows(h, cc, None)
            res.append((h, txt))
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

def crt_rect():
    return win32gui.GetWindowRect(CRT)

def shot():
    r = crt_rect()
    return ImageGrab.grab(bbox=(max(0,r[0]), max(0,r[1]), min(1920,r[2]), min(1080,r[3])))

def difff(a, b):
    d = ImageChops.difference(a.convert("L"), b.convert("L"))
    hist = d.histogram()
    return round(sum(hist[24:]) / (a.size[0]*a.size[1]), 4)

def statics():
    s = {}
    def cb(h, _):
        if win32gui.GetClassName(h) == "Static":
            t = win32gui.GetWindowText(h)
            if t.strip(): s[h] = t
        return True
    win32gui.EnumChildWindows(CRT, cb, None)
    return s

btns = []
def cb(h, _):
    if win32gui.GetClassName(h) == "Button":
        btns.append((h, win32gui.GetDlgCtrlID(h), win32gui.GetWindowRect(h)))
    return True
win32gui.EnumChildWindows(PANEL, cb, None)
btns.sort(key=lambda b: (b[2][1], b[2][0]))
print("buttons", len(btns), flush=True)

base_img = shot()
base_st = statics()
log = open(OUT, "a", encoding="utf-8")
results = []
for i, (h, cid, r) in enumerate(btns):
    # 点击前检查是否有残留弹窗
    for d, _t in find_prompt():
        dismiss(d)
    win32gui.SendMessage(h, win32con.BM_CLICK, 0, 0)
    time.sleep(0.45)
    ev = {"i": i, "id": cid, "rect": list(r)}
    pr = find_prompt()
    if pr:
        ev["prompt"] = pr[0][1]
        for d, _ in pr:
            dismiss(d)
    now_st = statics()
    st_diff = {str(k): [base_st.get(k), now_st.get(k)] for k in set(base_st) | set(now_st)
               if base_st.get(k) != now_st.get(k)}
    if st_diff:
        ev["static_diff"] = st_diff
    now_img = shot()
    f = difff(base_img, now_img)
    ev["crtdiff"] = f
    if f > 0.001:
        now_img.save(r"D:\Virtu模型\ssnc_teaching\evidence\opanel_btn_%02d.png" % i)
    results.append(ev)
    log.write(json.dumps(ev, ensure_ascii=False) + "\n"); log.flush()
    print(i, "id", cid, "diff", f, "prompt" if pr else "", "stch", len(st_diff), flush=True)
    base_img = now_img
    base_st = now_st

log.write(json.dumps({"done": True}) + "\n"); log.close()
print("DONE", flush=True)
