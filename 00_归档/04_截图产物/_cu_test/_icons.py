# -*- coding: utf-8 -*-
"""Read desktop icon names + real screen positions via SysListView32 LVM messages."""
import ctypes
import json
import sys
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMPOSITION = LVM_FIRST + 16
LVM_GETITEMTEXTW = LVM_FIRST + 115
LVM_GETITEMRECT = LVM_FIRST + 14
LVIR_ICON = 1

PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

LVIF_TEXT = 0x0001


class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", wintypes.UINT),
        ("iItem", ctypes.c_int),
        ("iSubItem", ctypes.c_int),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", ctypes.c_void_p),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("lParam", ctypes.c_ssize_t),
        ("iIndent", ctypes.c_int),
        ("iGroupId", ctypes.c_int),
        ("cColumns", wintypes.UINT),
        ("puColumns", ctypes.c_void_p),
        ("piColFmt", ctypes.c_void_p),
        ("iGroup", ctypes.c_int),
    ]


def find_desktop_listview():
    progman = user32.FindWindowW("Progman", None)
    candidates = []
    if progman:
        dv = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
        if dv:
            lv = user32.FindWindowExW(dv, None, "SysListView32", None)
            if lv:
                return lv
    # enumerate WorkerW
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    found = []

    def cb(h, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        if cls.value == "WorkerW":
            dv = user32.FindWindowExW(h, None, "SHELLDLL_DefView", None)
            if dv:
                lv = user32.FindWindowExW(dv, None, "SysListView32", None)
                if lv:
                    found.append(lv)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def main():
    lv = find_desktop_listview()
    if not lv:
        print(json.dumps({"ok": False, "err": "desktop listview not found"}))
        return

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(lv, ctypes.byref(pid))
    hproc = kernel32.OpenProcess(PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE, False, pid.value)
    if not hproc:
        print(json.dumps({"ok": False, "err": "OpenProcess failed", "pid": pid.value, "lasterr": ctypes.get_last_error()}))
        return

    count = user32.SendMessageW(lv, LVM_GETITEMCOUNT, 0, 0)

    # remote buffer: LVITEM (say 256) + text 520 + POINT 8
    lv_size = ctypes.sizeof(LVITEMW)
    text_off = lv_size
    text_len = 520
    pt_off = text_off + text_len
    total = pt_off + 8
    remote = kernel32.VirtualAllocEx(hproc, None, total, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not remote:
        print(json.dumps({"ok": False, "err": "VirtualAllocEx failed"}))
        return

    # listview client origin on screen
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(lv, ctypes.byref(origin))

    items = []
    for i in range(count):
        li = LVITEMW()
        li.mask = LVIF_TEXT
        li.iItem = i
        li.iSubItem = 0
        li.pszText = ctypes.c_void_p(remote + text_off)
        li.cchTextMax = 260
        kernel32.WriteProcessMemory(hproc, ctypes.c_void_p(remote), ctypes.byref(li), lv_size, None)
        user32.SendMessageW(lv, LVM_GETITEMTEXTW, i, remote)
        buf = ctypes.create_unicode_buffer(260)
        kernel32.ReadProcessMemory(hproc, ctypes.c_void_p(remote + text_off), buf, 520, None)
        name = buf.value

        user32.SendMessageW(lv, LVM_GETITEMPOSITION, i, remote + pt_off)
        pt = wintypes.POINT()
        kernel32.ReadProcessMemory(hproc, ctypes.c_void_p(remote + pt_off), ctypes.byref(pt), 8, None)
        sx = origin.x + pt.x
        sy = origin.y + pt.y

        # icon image rect (LVIR_ICON)
        rc = wintypes.RECT()
        rc.left = LVIR_ICON
        kernel32.WriteProcessMemory(hproc, ctypes.c_void_p(remote + pt_off), ctypes.byref(rc), 16, None)
        user32.SendMessageW(lv, LVM_GETITEMRECT, i, remote + pt_off)
        kernel32.ReadProcessMemory(hproc, ctypes.c_void_p(remote + pt_off), ctypes.byref(rc), 16, None)
        cx = origin.x + (rc.left + rc.right) // 2
        cy = origin.y + (rc.top + rc.bottom) // 2
        items.append({"i": i, "name": name, "x": sx, "y": sy,
                      "cx": cx, "cy": cy,
                      "irect": [rc.left, rc.top, rc.right, rc.bottom]})

    kernel32.VirtualFreeEx(hproc, ctypes.c_void_p(remote), 0, MEM_RELEASE)
    kernel32.CloseHandle(hproc)
    print(json.dumps({"ok": True, "count": count, "origin": [origin.x, origin.y],
                      "items": items}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
