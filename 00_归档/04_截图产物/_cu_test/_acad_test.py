# -*- coding: utf-8 -*-
"""Force-foreground + real SendInput keyboard test: draw a line in AutoCAD."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUT_U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_U)]


INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_MENU = 0x12


def send_inputs(inputs):
    arr = (INPUT * len(inputs))(*inputs)
    return u32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def kbd_unicode(s):
    inputs = []
    for ch in s:
        for flag in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.u.ki.wVk = 0
            inp.u.ki.wScan = ord(ch)
            inp.u.ki.dwFlags = flag
            inputs.append(inp)
    return send_inputs(inputs)


def tap_vk(vk, mods=()):
    seq = []
    for m in mods:
        inp = INPUT(); inp.type = INPUT_KEYBOARD; inp.u.ki.wVk = m; inp.u.ki.dwFlags = 0
        seq.append(inp)
    d = INPUT(); d.type = INPUT_KEYBOARD; d.u.ki.wVk = vk; d.u.ki.dwFlags = 0
    uu = INPUT(); uu.type = INPUT_KEYBOARD; uu.u.ki.wVk = vk; uu.u.ki.dwFlags = KEYEVENTF_KEYUP
    seq += [d, uu]
    for m in reversed(mods):
        inp = INPUT(); inp.type = INPUT_KEYBOARD; inp.u.ki.wVk = m; inp.u.ki.dwFlags = KEYEVENTF_KEYUP
        seq.append(inp)
    send_inputs(seq)


def force_fg(hwnd):
    u32.ShowWindow(hwnd, 9)
    fg = u32.GetForegroundWindow()
    if fg == hwnd:
        return True
    tid_fg = u32.GetWindowThreadProcessId(fg, None) if fg else 0
    tid_me = k32.GetCurrentThreadId()
    attached = False
    if tid_fg and tid_fg != tid_me:
        attached = bool(u32.AttachThreadInput(tid_me, tid_fg, True))
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    if attached:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    if u32.GetForegroundWindow() != hwnd:
        # Alt unlock trick
        u32.keybd_event(VK_MENU, 0, 0, 0)
        u32.keybd_event(VK_MENU, 0, 2, 0)
        u32.SetForegroundWindow(hwnd)
        u32.BringWindowToTop(hwnd)
    time.sleep(0.3)
    return u32.GetForegroundWindow() == hwnd


def find_main_window(pid):
    best = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h):
            ln = u32.GetWindowTextLengthW(h)
            if ln:
                b = ctypes.create_unicode_buffer(ln + 1)
                u32.GetWindowTextW(h, b, ln + 1)
                r = wintypes.RECT()
                u32.GetWindowRect(h, ctypes.byref(r))
                area = (r.right - r.left) * (r.bottom - r.top)
                best.append((area, h, b.value))
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    best.sort(reverse=True)
    return best[0] if best else (0, None, None)


def cap(path):
    import cu_ui
    cu_ui.capture_screen_bmp(path)


def main():
    sys.path.insert(0, r"C:\Users\Administrator\.workbuddy\skills\magic-hand-windows\scripts")
    pid = int(sys.argv[1])
    area, hwnd, title = find_main_window(pid)
    if not hwnd:
        print(json.dumps({"ok": False, "err": "no window for pid", "pid": pid}))
        return
    fok = force_fg(hwnd)
    print(json.dumps({"ok": True, "hwnd": hwnd, "title": title, "foreground": fok}, ensure_ascii=False))
    time.sleep(0.8)

    # Ctrl+N -> new drawing
    tap_vk(ord("N"), mods=(VK_CONTROL,))
    time.sleep(2.5)
    cap(r"D:/Virtu模型/_cu_test/acad_step1_new.bmp")
    # accept template dialog if any
    tap_vk(VK_RETURN)
    time.sleep(2.0)
    cap(r"D:/Virtu模型/_cu_test/acad_step2_dialog.bmp")

    # draw a line via command line
    kbd_unicode("LINE")
    time.sleep(0.2); tap_vk(VK_RETURN); time.sleep(0.4)
    kbd_unicode("100,100")
    time.sleep(0.2); tap_vk(VK_RETURN); time.sleep(0.4)
    kbd_unicode("500,400")
    time.sleep(0.2); tap_vk(VK_RETURN); time.sleep(0.3)
    tap_vk(VK_RETURN)  # end line
    time.sleep(0.5)
    # zoom extents
    kbd_unicode("ZOOM")
    time.sleep(0.2); tap_vk(VK_RETURN); time.sleep(0.3)
    kbd_unicode("E")
    time.sleep(0.2); tap_vk(VK_RETURN); time.sleep(1.0)
    cap(r"D:/Virtu模型/_cu_test/acad_step3_line.bmp")
    print(json.dumps({"ok": True, "done": True}))


if __name__ == "__main__":
    main()
