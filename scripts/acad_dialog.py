#!/usr/bin/env python
"""List top-level + child windows of AutoCAD and dismiss modal 'AutoCAD 消息' dialogs.

Usage:
  python scripts/acad_dialog.py list
  python scripts/acad_dialog.py dismiss
"""
from __future__ import annotations

import sys
import time

import win32con
import win32gui
import win32process


def acad_pids():
    import psutil
    pids = []
    for p in psutil.process_iter(["name", "pid"]):
        if (p.info["name"] or "").lower() in ("acad.exe", "acadlt.exe"):
            pids.append(p.info["pid"])
    return pids


def enum_windows():
    out = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            pid = -1
        out.append({"hwnd": hwnd, "title": title, "class": cls, "pid": pid})

    win32gui.EnumWindows(cb, None)
    return out


def children(hwnd):
    out = []

    def cb(h, _):
        out.append({
            "hwnd": h,
            "class": win32gui.GetClassName(h),
            "text": win32gui.GetWindowText(h),
            "visible": bool(win32gui.IsWindowVisible(h)),
        })

    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:
        pass
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    pids = set(acad_pids())
    print(f"acad pids: {sorted(pids)}")
    wins = [w for w in enum_windows() if w["pid"] in pids]
    if mode == "list":
        for w in wins:
            print(f"TOP  hwnd={w['hwnd']} cls={w['class']!r} title={w['title']!r}")
            for c in children(w["hwnd"]):
                print(f"   child cls={c['class']!r} text={c['text']!r} vis={c['visible']}")
        return 0

    # dismiss: click the default button of any AutoCAD message box
    clicked = 0
    for w in wins:
        if w["class"] != "#32770":
            continue
        if "AutoCAD" not in w["title"] and "消息" not in w["title"] and "Message" not in w["title"]:
            continue
        kids = children(w["hwnd"])
        btn = next((c for c in kids if c["class"] == "Button" and c["text"].strip() in ("确定", "OK", "&确定")), None)
        if btn is None:
            btn = next((c for c in kids if c["class"] == "Button" and c["visible"]), None)
        if btn:
            print(f"clicking button {btn['text']!r} on {w['title']!r}")
            win32gui.SendMessage(btn["hwnd"], win32con.BM_CLICK, 0, 0)
            clicked += 1
            time.sleep(0.4)
        else:
            print(f"no button found on {w['title']!r}; sending WM_CLOSE")
            win32gui.PostMessage(w["hwnd"], win32con.WM_CLOSE, 0, 0)
            clicked += 1
    print("dismissed:", clicked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
