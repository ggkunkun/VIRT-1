# -*- coding: utf-8 -*-
"""显卡调度探针：设置 SLDWORKS.exe 的 GPU 偏好后，测文档打开后的 CPU 空转与消息响应。

用法: python gen/sw_gpu_probe.py 2   # 2=高性能独显, 1=省电/核显
"""
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPU_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"
TPL = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates\gb_part.prtdot"
u = ctypes.windll.user32


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
    return bool(u.SendMessageTimeoutW(hwnd, 0, 0, 0, 0x0002, 1200, ctypes.byref(res)))


def cpu(pid):
    out = subprocess.run(["powershell", "-NoProfile", "-c", f"(Get-Process -Id {pid}).CPU"],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except Exception:
        return None


def delta(pid, sec=6):
    a = cpu(pid)
    time.sleep(sec)
    b = cpu(pid)
    return None if a is None or b is None else round(b - a, 2)


def main():
    pref = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    import winreg
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, GPU_KEY)
    try:
        old = winreg.QueryValueEx(k, EXE)[0]
    except FileNotFoundError:
        old = None
    winreg.SetValueEx(k, EXE, 0, winreg.REG_SZ, f"GpuPreference={pref};")
    k.Close()
    log = {"gpu_pref": pref, "old": old, "steps": []}

    for p in pids():
        subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)
    time.sleep(5)
    subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    for _ in range(36):
        time.sleep(5)
        if pids():
            break
    if not pids():
        log["verdict"] = "launch_failed"
        print(json.dumps(log, ensure_ascii=False))
        return
    pid = pids()[0]
    time.sleep(40)
    hwnd = main_hwnd(pid)
    log["idle_responsive"] = responsive(hwnd)
    log["idle_cpu_delta"] = delta(pid)

    import win32com.client
    sw = None
    for _ in range(6):
        try:
            sw = win32com.client.GetActiveObject("SldWorks.Application.29")
            break
        except Exception:
            time.sleep(5)
    if sw is None:
        log["verdict"] = "attach_failed"
    else:
        rev = sw.RevisionNumber
        log["revision"] = str(rev() if callable(rev) else rev)
        t = time.time()
        model = sw.NewDocument(TPL, 0, 0, 0)
        log["newdoc_s"] = round(time.time() - t, 1)
        log["model"] = bool(model)
        time.sleep(2)
        hwnd = main_hwnd(pid)
        if hwnd:
            u.ShowWindow(hwnd, 9)      # SW_RESTORE
            u.SetForegroundWindow(hwnd)
            log["foreground"] = True
        time.sleep(6)
        hwnd = main_hwnd(pid)
        log["doc_responsive"] = responsive(hwnd)
        log["doc_cpu_delta"] = delta(pid)
        log["verdict"] = "ok" if (log["doc_responsive"] and (log["doc_cpu_delta"] or 0) < 1.0) else "spinning"

    print(json.dumps(log, ensure_ascii=False))
    os.makedirs(os.path.join(BASE, "work"), exist_ok=True)
    with open(os.path.join(BASE, "work", f"gpu_probe_{pref}.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
