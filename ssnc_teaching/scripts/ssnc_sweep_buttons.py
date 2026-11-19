# -*- coding: utf-8 -*-
"""Sweep the 55 owner-draw panel buttons with BM_CLICK and record observable effects.

Evidence-based identification: for each button we capture before/after screenshots of
the CRT window and the panel window, detect modal prompts, and record which
native statics / CRT pixels changed. No coordinate guessing - every entry is a
real Win32 control with a stable hwnd/id/rect.

Skips id 9506 (verified emergency-stop: clicking re-engages the latch).
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import win32con
import win32gui
import win32process
from PIL import ImageGrab

EV = Path(r"D:\Virtu模型\ssnc_teaching\evidence")
EV.mkdir(parents=True, exist_ok=True)
MAIN = 67042
PANEL = 68412
CRT = 198146
SKIP_IDS = {9506}  # emergency stop - verified, do not re-engage


def sscnc_pids():
    out = subprocess.check_output(
        'tasklist /FI "IMAGENAME eq sscnc.exe"', shell=True
    ).decode("mbcs", "ignore")
    return {int(m.group(1)) for m in re.finditer(r"sscnc\.exe\s+(\d+)", out, re.I)}


def find_prompts():
    pids = sscnc_pids()
    found = []

    def cb(h, _):
        tid, pid = win32process.GetWindowThreadProcessId(h)
        if (
            pid in pids
            and win32gui.IsWindowVisible(h)
            and win32gui.GetWindowText(h) == "SwanSoft CNC"
        ):
            # grab its static text
            txt = []

            def c2(x, _):
                if win32gui.GetClassName(x) == "Static":
                    t = win32gui.GetWindowText(x)
                    if t:
                        txt.append(t)
                return True

            win32gui.EnumChildWindows(h, c2, None)
            found.append({"hwnd": h, "text": "|".join(txt)})
        return True

    win32gui.EnumWindows(cb, None)
    return found


def dismiss_prompts():
    for p in find_prompts():
        kids = []

        def c2(h, _):
            kids.append((h, win32gui.GetClassName(h)))
            return True

        win32gui.EnumChildWindows(p["hwnd"], c2, None)
        for h, c in kids:
            if c == "Button":
                win32gui.SendMessage(h, win32con.BM_CLICK, 0, 0)
    time.sleep(0.4)


def grab_rect(rect):
    return ImageGrab.grab(bbox=rect, all_screens=True)


def diff_frac(a, b):
    import numpy as np

    aa = np.asarray(a.convert("L"), dtype=np.int16)
    bb = np.asarray(b.convert("L"), dtype=np.int16)
    if aa.shape != bb.shape:
        return 1.0
    return float((abs(aa - bb) > 12).mean())


def panel_buttons():
    btns = []

    def cb(h, _):
        if win32gui.GetClassName(h) == "Button":
            btns.append(
                {
                    "hwnd": h,
                    "id": win32gui.GetDlgCtrlID(h),
                    "rect": win32gui.GetWindowRect(h),
                }
            )
        return True

    win32gui.EnumChildWindows(PANEL, cb, None)
    btns.sort(key=lambda b: (b["rect"][1], b["rect"][0]))
    return btns


def crt_statics():
    """Collect static-control texts inside the CRT window as cheap state probe."""
    txt = {}

    def cb(h, _):
        c = win32gui.GetClassName(h)
        if c in ("Static", "SysListView32", "Edit"):
            t = win32gui.GetWindowText(h)
            if t:
                txt["%s:%d" % (c, h)] = t[:80]
        return True

    win32gui.EnumChildWindows(CRT, cb, None)
    return txt


def main():
    dismiss_prompts()
    btns = panel_buttons()
    results = []
    base_crt = crt_statics()
    base_panel_img = grab_rect(win32gui.GetWindowRect(PANEL))
    base_crt_img = grab_rect(win32gui.GetWindowRect(CRT))

    for i, b in enumerate(btns):
        if b["id"] in SKIP_IDS:
            continue
        h = b["hwnd"]
        pre_prompts = find_prompts()
        # PostMessage: non-blocking. SendMessage can deadlock when a click opens
        # a modal dialog (target thread stops dispatching to the sender).
        win32gui.PostMessage(h, win32con.BM_CLICK, 0, 0)
        time.sleep(0.9)
        post_prompts = find_prompts()
        rec = {
            "idx": i,
            "id": b["id"],
            "rect": b["rect"],
            "prompts": [p["text"] for p in post_prompts],
        }
        if post_prompts:
            rec["blocked_by"] = post_prompts[0]["text"]
            dismiss_prompts()
            rec["panel_diff"] = 0.0
            rec["crt_diff"] = 0.0
            rec["statics_changed"] = {}
        else:
            now_panel = grab_rect(win32gui.GetWindowRect(PANEL))
            now_crt = grab_rect(win32gui.GetWindowRect(CRT))
            rec["panel_diff"] = round(diff_frac(base_panel_img, now_panel), 4)
            rec["crt_diff"] = round(diff_frac(base_crt_img, now_crt), 4)
            now_st = crt_statics()
            rec["statics_changed"] = {
                k: now_st.get(k) for k in set(base_crt) | set(now_st)
                if base_crt.get(k) != now_st.get(k)
            }
            base_panel_img = now_panel
            base_crt_img = now_crt
            base_crt = now_st
        results.append(rec)
        print(
            "id=%s rect=%s panel_d=%.3f crt_d=%.3f prompts=%s"
            % (
                b["id"],
                b["rect"],
                rec.get("panel_diff", -1),
                rec.get("crt_diff", -1),
                rec["prompts"],
            )
        )
        sys.stdout.flush()

    out = EV / "panel_sweep_results.json"
    out.write_text(
        json.dumps(
            {"main": MAIN, "panel": PANEL, "crt": CRT, "results": results},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
