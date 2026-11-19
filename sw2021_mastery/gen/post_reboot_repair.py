# -*- coding: utf-8 -*-
"""重启后一键完成：挂载 ISO -> 提权修复核心产品 -> 校验版本 -> 删除 ISO（回收站）。

用法:
  python gen/post_reboot_repair.py            # 只修复+校验
  python gen/post_reboot_repair.py --delete-iso
"""
import argparse
import ctypes
import glob
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

PCODE = "{9C0A2571-4AAE-4FEE-B673-038B38B85EFC}"
ISO = r"D:\Backup\Downloads\SW2021_SP5_64bit.iso"
EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "work")
LOG = os.path.join(WORK, "post_reboot_repair.log")
RESULT = os.path.join(WORK, "post_reboot_result.json")


def find_media():
    for drive in "DEFGHIJKLMNOPQRSTUVWXYZ":
        p = f"{drive}:\\SW2021_SP5_64bit\\setup.exe"
        if os.path.exists(p):
            return f"{drive}:"
    return None


def mount_iso():
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Mount-DiskImage -ImagePath '{ISO}' | Out-Null"],
                   capture_output=True, text=True, errors="ignore")
    for _ in range(12):
        time.sleep(3)
        d = find_media()
        if d:
            return d
    return None


def elevated_repair(log_path):
    params = (f'/i {PCODE} REINSTALL=ALL REINSTALLMODE=vomus SLDIM=1 REBOOT=ReallySuppress '
              f'/qn /l*v "{log_path}"')
    ctypes.windll.shell32.ShellExecuteW(None, "runas", "msiexec.exe", params, None, 0)


def wait_log(log_path, timeout=2400):
    t0 = time.time()
    last, stable = -1, 0
    while time.time() - t0 < timeout:
        time.sleep(10)
        size = os.path.getsize(log_path) if os.path.exists(log_path) else 0
        running = '"msiexec.exe"' in subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq msiexec.exe", "/NH", "/FO", "CSV"],
            capture_output=True, text=True, errors="ignore").stdout
        stable = stable + 1 if size == last else 0
        last = size
        if not running and size > 0 and stable >= 2:
            break
    if not os.path.exists(log_path):
        return "", 0
    raw = open(log_path, "rb").read()
    txt = ""
    for enc in ("utf-16-le", "utf-8", "gbk"):
        try:
            t = raw.decode(enc)
            if t.count("\x00") < len(t) * 0.05:
                txt = t
                break
        except Exception:
            pass
    return txt, len(raw)


def recycle(path):
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT, FOF_NOERRORUI = 3, 0x0040, 0x0010, 0x0004, 0x0400
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = path + "\0\0"
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return {"rc": rc, "aborted": bool(op.fAnyOperationsAborted), "exists": os.path.exists(path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete-iso", action="store_true")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    res = {"steps": []}

    media = find_media() or mount_iso()
    res["media"] = media
    res["steps"].append({"step": "mount", "ok": bool(media), "detail": media})
    print("media", media, flush=True)
    if not media:
        print("ISO 未挂载，终止")
        return 1

    if os.path.exists(LOG):
        os.remove(LOG)
    elevated_repair(LOG)
    print("repair launched, waiting...", flush=True)
    txt, size = wait_log(LOG)
    ok = "returning 0" in txt or "returning 3010" in txt
    res["steps"].append({"step": "repair", "ok": ok, "log_bytes": size,
                         "tail": [l for l in txt.splitlines() if l.strip()][-5:]})
    print("repair ok", ok, "log", size, flush=True)

    ver = ""
    if os.path.exists(EXE):
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-Item -LiteralPath '{EXE}').VersionInfo.ProductVersion"],
                             capture_output=True, text=True, errors="ignore")
        ver = (out.stdout or "").strip()
    res["version"] = ver
    res["mtime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(EXE))) if os.path.exists(EXE) else None
    res["steps"].append({"step": "verify", "ok": ver.startswith("29.5"), "detail": f"{ver} @ {res['mtime']}"})
    print("version", ver, res["mtime"], flush=True)

    if args.delete_iso and ok:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Dismount-DiskImage -ImagePath '{ISO}' | Out-Null"],
                       capture_output=True, text=True, errors="ignore")
        time.sleep(3)
        r = recycle(ISO)
        res["iso"] = r
        print("iso", r, flush=True)

    with open(RESULT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
