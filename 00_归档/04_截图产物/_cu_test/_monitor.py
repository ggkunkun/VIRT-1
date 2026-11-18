# -*- coding: utf-8 -*-
"""Launch an app by double-clicking a desktop icon, then monitor process lifetime."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

sys.path.insert(0, r"C:\Users\Administrator\.workbuddy\skills\magic-hand-windows\scripts")
import cu_ui  # noqa: E402

k32 = ctypes.windll.kernel32
u32 = ctypes.windll.user32

TH32CS_SNAPPROCESS = 0x2


class PE32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def procs():
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PE32()
    pe.dwSize = ctypes.sizeof(PE32)
    out = []
    ok = k32.Process32First(snap, ctypes.byref(pe))
    while ok:
        out.append((pe.th32ProcessID, pe.szExeFile.decode("mbcs", "ignore")))
        ok = k32.Process32Next(snap, ctypes.byref(pe))
    k32.CloseHandle(snap)
    return out


def windows_with_pid(pids):
    res = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        if u32.IsWindowVisible(h):
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value in pids:
                ln = u32.GetWindowTextLengthW(h)
                if ln:
                    b = ctypes.create_unicode_buffer(ln + 1)
                    u32.GetWindowTextW(h, b, ln + 1)
                    res.append({"pid": pid.value, "hwnd": h, "title": b.value})
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    return res


def dblclick(x, y):
    u32.SetCursorPos(x, y)
    time.sleep(0.15)
    for _ in range(2):
        u32.mouse_event(0x0002, 0, 0, 0, 0)
        u32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.04)


def minimize_all():
    SKIP = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
            "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow", "ForegroundStaging",
            "MultitaskingViewFrame", "TaskListThumbnailWnd"}
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        if not u32.IsWindowVisible(h) or u32.IsIconic(h):
            return True
        cls = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(h, cls, 256)
        if cls.value in SKIP:
            return True
        if u32.GetWindowTextLengthW(h) == 0:
            return True
        u32.ShowWindow(h, 6)
        return True

    u32.EnumWindows(EnumProc(cb), 0)


def main():
    x = int(sys.argv[1]); y = int(sys.argv[2])
    kw = sys.argv[3]; dur = int(sys.argv[4])
    minimize_all()
    time.sleep(0.6)
    dblclick(x, y)
    t0 = time.time()
    timeline = []
    last = None
    seen_pids = set()
    while time.time() - t0 < dur:
        cur = [(pid, name) for pid, name in procs() if kw.lower() in name.lower()]
        cur_pids = set(p for p, _ in cur)
        seen_pids |= cur_pids
        state = ",".join(sorted(str(p) for p in cur_pids)) if cur_pids else "GONE"
        if state != last:
            timeline.append({"t": round(time.time() - t0, 1), "state": state})
            last = state
        time.sleep(1.5)
    wins = windows_with_pid(seen_pids)
    print(json.dumps({"ok": True, "keyword": kw, "timeline": timeline,
                      "windows": [w["title"] for w in wins],
                      "pids_seen": sorted(seen_pids)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
