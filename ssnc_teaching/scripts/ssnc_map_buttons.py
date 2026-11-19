# -*- coding: utf-8 -*-
"""证据化面板按键识别 v2：截图模板匹配。
对面板窗口的每个 Button 控件截取屏幕区域，与 SSCNC 命名位图库做归一化互相关匹配。"""
import os, sys, json, glob
import numpy as np
import win32gui
from PIL import Image, ImageGrab

PANEL = 68412          # 底部面板窗口（当前实例）
SHOT = r"D:\Virtu模型\ssnc_teaching\evidence\panel_map_shot.png"
OUT  = r"D:\Virtu模型\ssnc_teaching\evidence\panel_button_map.json"
BMP_DIRS = [
    r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\FANUC\FANUC0iM\btn_nj3_symbol",
    r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\FANUC\FANUC0iM\btn_sy_symbol",
    r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\FANUC\FANUC0iM\btn_wia",
]

# 1) 截全屏
full = ImageGrab.grab()
full.save(SHOT)
fa = np.asarray(full.convert("RGB"), dtype=np.float32)

# 2) 枚举面板全部 Button
btns = []
def cb(h, _):
    if win32gui.GetClassName(h) == "Button":
        btns.append((h, win32gui.GetDlgCtrlID(h), win32gui.GetWindowText(h), win32gui.GetWindowRect(h)))
    return True
win32gui.EnumChildWindows(PANEL, cb, None)
print("buttons:", len(btns))

# 3) 载入位图库 -> 归一化灰度模板
templates = []
for d in BMP_DIRS:
    for fp in glob.glob(os.path.join(d, "*.bmp")):
        name = os.path.splitext(os.path.basename(fp))[0].lower()
        try:
            im = Image.open(fp).convert("RGB")
        except Exception:
            continue
        templates.append((name, d.split("\\")[-1], im))
print("templates:", len(templates))

def crop_arr(r):
    x0, y0, x1, y1 = [int(v) for v in r]
    return fa[y0:y1, x0:x1]

def ncc(a, b):
    # a: 截图crop (H,W,3), b: 模板已resize到同尺寸 -> 返回相关系数
    if a.size == 0:
        return -1
    af = a.reshape(-1, 3).mean(axis=1)
    bf = b.reshape(-1, 3).mean(axis=1)
    af = af - af.mean(); bf = bf - bf.mean()
    denom = np.sqrt((af**2).sum() * (bf**2).sum())
    if denom == 0:
        return -1
    return float((af * bf).sum() / denom)

results = []
for h, cid, txt, r in sorted(btns, key=lambda b: (b[3][1], b[3][0])):
    crop = crop_arr(r)
    H, W = crop.shape[:2]
    if H < 8 or W < 8:
        continue
    best = []
    for name, src, im in templates:
        tw, th = im.size
        # 只比较宽高比接近的模板，resize 到 crop 尺寸
        if abs(tw / th - W / H) > 0.6:
            continue
        t = np.asarray(im.resize((W, H), Image.BILINEAR), dtype=np.float32)
        s = ncc(crop, t)
        best.append((round(s, 3), name, src))
    best.sort(reverse=True)
    results.append({"hwnd": h, "id": cid, "text": txt, "rect": list(r),
                    "top3": best[:3]})
    top = best[0] if best else None
    print("id=%-5d %-22s rect=%s top=%s" % (cid, txt[:20], r, top))

json.dump({"panel_hwnd": PANEL, "shot": SHOT, "results": results},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", OUT)
