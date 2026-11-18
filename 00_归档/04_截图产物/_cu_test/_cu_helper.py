# -*- coding: utf-8 -*-
"""Single-process GUI helper for the desktop capability test.
Reuses magic-hand cu_ui.py primitives (ctypes only).
Commands:
  shot <out.bmp>
  minall            minimize every normal top-level window
  restoreall        restore windows minimized by minall (state file)
  click <x> <y>
  dblclick <x> <y>
  move <x> <y>
  fg
  windows
"""
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

SCRIPTS = r"C:\Users\Administrator\.workbuddy\skills\magic-hand-windows\scripts"
sys.path.insert(0, SCRIPTS)
import cu_ui  # noqa: E402

user32 = ctypes.windll.user32
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_min_state.json")

SKIP_CLASSES = {
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
    "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow",
    "TaskListThumbnailWnd", "ForegroundStaging", "MultitaskingViewFrame",
}


def visible_windows():
    out = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        ln = user32.GetWindowTextLengthW(h)
        if ln == 0:
            return True
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        if cls.value in SKIP_CLASSES:
            return True
        buf = ctypes.create_unicode_buffer(ln + 1)
        user32.GetWindowTextW(h, buf, ln + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        r = wintypes.RECT()
        user32.GetWindowRect(h, ctypes.byref(r))
        out.append({
            "hwnd": h, "title": buf.value, "cls": cls.value,
            "pid": pid.value,
            "rect": [r.left, r.top, r.right, r.bottom],
            "iconic": bool(user32.IsIconic(h)),
        })
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return out


def cmd_minall():
    wins = visible_windows()
    stored = []
    for w in wins:
        if w["iconic"]:
            continue
        if user32.ShowWindow(w["hwnd"], 6):  # SW_MINIMIZE
            stored.append({"hwnd": w["hwnd"], "title": w["title"]})
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(stored, f, ensure_ascii=False, indent=1)
    print(json.dumps({"ok": True, "minimized": len(stored),
                      "titles": [s["title"] for s in stored]}, ensure_ascii=False))


def cmd_restoreall():
    if not os.path.exists(STATE):
        print(json.dumps({"ok": False, "err": "no state"}))
        return
    with open(STATE, "r", encoding="utf-8") as f:
        stored = json.load(f)
    n = 0
    for s in stored:
        h = s["hwnd"]
        if user32.IsWindow(h):
            user32.ShowWindow(h, 9)  # SW_RESTORE
            n += 1
    print(json.dumps({"ok": True, "restored": n}, ensure_ascii=False))


def cmd_fg():
    h = user32.GetForegroundWindow()
    ln = user32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(ln + 1)
    user32.GetWindowTextW(h, b, ln + 1)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    print(json.dumps({"hwnd": h, "title": b.value, "pid": pid.value}, ensure_ascii=False))


def cmd_windows():
    print(json.dumps(visible_windows(), ensure_ascii=False, indent=1))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    c = sys.argv[1]
    if c == "shot":
        out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(STATE), "shot.bmp")
        cu_ui.capture_screen_bmp(out)
        print(json.dumps({"ok": True, "path": out}))
    elif c == "minall":
        cmd_minall()
    elif c == "restoreall":
        cmd_restoreall()
    elif c == "fg":
        cmd_fg()
    elif c == "windows":
        cmd_windows()
    elif c == "move":
        x, y = int(sys.argv[2]), int(sys.argv[3])
        user32.SetCursorPos(x, y)
        print(json.dumps({"ok": True, "moved": [x, y]}))
    elif c in ("click", "dblclick"):
        x, y = int(sys.argv[2]), int(sys.argv[3])
        user32.SetCursorPos(x, y)
        time.sleep(0.12)
        if c == "click":
            cu_ui.mouse_click_at(x, y)
        else:
            # two fast left clicks => double click
            for _ in range(2):
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
                time.sleep(0.05)
        print(json.dumps({"ok": True, "clicked": [x, y], "kind": c}))
    else:
        print("unknown command")


if __name__ == "__main__":
    main()
