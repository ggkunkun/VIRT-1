# -*- coding: utf-8 -*-
"""验证关闭 CEF 后 SW2021 是否还空转：空载 -> 建件 -> 测量 CPU 与消息响应。"""
import ctypes
import subprocess
import time
from ctypes import wintypes

u = ctypes.windll.user32
WM_NULL = 0x0000
SMTO_ABORTIFHUNG = 0x0002


def pids():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True, errors="ignore").stdout
    return [int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"SLDWORKS.exe"')]


def main_hwnd(pid):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 600 and r.bottom - r.top > 400:
                found.append(h)
        return True

    u.EnumWindows(cb, 0)
    return found[0] if found else None


def responsive(hwnd):
    if not hwnd:
        return None
    res = ctypes.c_size_t()
    ok = u.SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, 1200, ctypes.byref(res))
    return bool(ok)


def cpu(pid):
    out = subprocess.run(["powershell", "-NoProfile", "-c",
                          f"(Get-Process -Id {pid}).CPU"], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except Exception:
        return None


def cpu_delta(pid, sec=6):
    a = cpu(pid)
    time.sleep(sec)
    b = cpu(pid)
    return None if a is None or b is None else round(b - a, 2)


def main():
    for p in pids():
        subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)
    time.sleep(5)
    subprocess.Popen(["explorer.exe", r"D:\SOLIDWORKS (2)\SLDWORKS.exe"])
    for _ in range(30):
        time.sleep(5)
        if pids():
            break
    pid = pids()[0]
    print("pid", pid)
    time.sleep(45)
    hwnd = main_hwnd(pid)
    print("idle: hwnd", hwnd, "responsive", responsive(hwnd), "cpu_delta", cpu_delta(pid))

    import win32com.client
    sw = win32com.client.GetActiveObject("SldWorks.Application.29")
    rev = sw.RevisionNumber
    rev = rev() if callable(rev) else rev
    print("attach rev", rev)
    tpl = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates\gb_part.prtdot"
    t = time.time()
    model = sw.NewDocument(tpl, 0, 0, 0)
    print("newdoc", round(time.time() - t, 1), "s model", type(model).__name__ if model else None)
    time.sleep(3)
    hwnd = main_hwnd(pid)
    print("after doc: responsive", responsive(hwnd), "cpu_delta", cpu_delta(pid))
    if model:
        model.ClearSelection2(True)
        print("ClearSelection2 ok")
        model.SketchManager.InsertSketch(True)
        model.SketchManager.CreateCenterRectangle(0, 0, 0, 0.06, 0.04, 0)
        model.SketchManager.InsertSketch(True)
        feats = model.FeatureManager.GetFeatures(False)
        print("feats", len(feats), [f.Name for f in feats][:3])
        print("after sketch: responsive", responsive(main_hwnd(pid)), "cpu_delta", cpu_delta(pid))


if __name__ == "__main__":
    main()
