#!/usr/bin/env python3
"""
inspect_windows.py - Enumerate and inspect top-level desktop windows on Windows.
"""

import os
import sys
import json
import argparse
import ctypes
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desktop_util
desktop_util.attach_default_desktop()

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_process_name(pid):
    """Get executable process name from PID."""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        # QueryFullProcessImageNameW
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        kernel32.CloseHandle(h_proc)
    return ""

def get_window_info(hwnd):
    """Retrieve full metadata for a window."""
    length = user32.GetWindowTextLengthW(hwnd)
    title = ""
    if length > 0:
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    is_visible = bool(user32.IsWindowVisible(hwnd))
    is_iconic = bool(user32.IsIconic(hwnd)) # minimized
    is_zoomed = bool(user32.IsZoomed(hwnd)) # maximized

    w = max(0, rect.right - rect.left)
    h = max(0, rect.bottom - rect.top)

    return {
        "hwnd": hex(hwnd),
        "title": title,
        "pid": pid.value,
        "process": get_process_name(pid.value),
        "visible": is_visible,
        "minimized": is_iconic,
        "maximized": is_zoomed,
        "rect": {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
            "width": w,
            "height": h
        }
    }

def main():
    parser = argparse.ArgumentParser(description="Inspect desktop windows")
    parser.add_argument("--filter", "-f", help="Filter windows by title substring (case-insensitive)")
    parser.add_argument("--visible-only", "-v", action="store_true", default=True, help="List only visible windows")
    parser.add_argument("--no-minimized", action="store_true", help="Exclude minimized windows")
    parser.add_argument("--all", action="store_true", help="Include invisible windows")
    parser.add_argument("--active", "-a", action="store_true", help="Get only the active/foreground window")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    desktop_util.attach_default_desktop()

    if args.active:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            data = {"success": False, "error": "No foreground window found"}
        else:
            win = get_window_info(hwnd)
            data = {"success": True, "active_window": win}

        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            if data.get("success", False):
                w = data["active_window"]
                print(f"Active Window: [{w['hwnd']}] {w['title']} (Process: {w['process']}, PID: {w['pid']})")
                print(f"Bounds: ({w['rect']['left']}, {w['rect']['top']}) - {w['rect']['width']}x{w['rect']['height']}")
            else:
                print(data["error"], file=sys.stderr)
        return

    windows = []
    def enum_cb(hwnd, _):
        is_vis = bool(user32.IsWindowVisible(hwnd))
        if not args.all and not is_vis:
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        # Skip empty titled invisible windows
        if not args.all and length == 0:
            return True

        win = get_window_info(hwnd)
        if args.filter:
            if args.filter.lower() not in win["title"].lower() and args.filter.lower() not in win["process"].lower():
                return True

        # Skip zero-size utility helper windows unless --all
        if not args.all and (win["rect"]["width"] == 0 or win["rect"]["height"] == 0):
            return True

        if args.no_minimized and win["minimized"]:
            return True

        windows.append(win)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    if args.json:
        print(json.dumps({"success": True, "count": len(windows), "windows": windows}, ensure_ascii=False, indent=2))
    else:
        print(f"Found {len(windows)} matching windows:\n")
        print(f"{'HWND':<10} {'PID':<8} {'PROCESS':<20} {'BOUNDS / STATE':<22} {'TITLE'}")
        print("-" * 85)
        for w in windows:
            r = w["rect"]
            if w["minimized"]:
                b_str = "[Minimized]"
            else:
                b_str = f"{r['left']},{r['top']} {r['width']}x{r['height']}"
            title = w['title'][:40] + ("..." if len(w['title']) > 40 else "")
            print(f"{w['hwnd']:<10} {w['pid']:<8} {w['process']:<20} {b_str:<22} {title}")

if __name__ == "__main__":
    main()
