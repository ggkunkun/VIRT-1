# -*- coding: utf-8 -*-
"""探针3：窗口枚举诊断 + preflight_apps 单独计时 + 系统 PowerShell 健康检查。"""
import os, sys, io, time, subprocess, traceback

OUT = r"D:\Virtu模型\_probe3_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

os.chdir(r"D:\Virtu模型")
sys.path.insert(0, r"D:\Virtu模型")

if os.path.exists(OUT):
    os.remove(OUT)

def probe(name, fn, timeout=20):
    t0 = time.time()
    try:
        r = fn()
        dt = time.time() - t0
        if isinstance(r, dict):
            log(name, "OK", f"{dt:.1f}s", "status=", r.get("status"), "keys=", list(r.keys())[:10])
        else:
            log(name, "OK", f"{dt:.1f}s", "repr=", str(r)[:300])
    except Exception as e:
        dt = time.time() - t0
        log(name, "EXC", f"{dt:.1f}s", type(e).__name__, str(e)[:300])
        log("  TRACE", traceback.format_exc().splitlines()[-1][:300])

# 1. 系统 PowerShell 健康（subprocess 通道）
def ps_test():
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "Write-Output 'PS_OK'"],
                       capture_output=True, timeout=15)
    return {"rc": r.returncode, "out": r.stdout.decode("utf-8", "ignore").strip()[:100],
            "err": r.stderr.decode("utf-8", "ignore").strip()[:200]}
probe("system_powershell_subprocess", ps_test)

# 2. 枚举全部可见窗口（找 SOLIDWORKS 窗口为什么找不到）
def enum_windows():
    try:
        import win32gui
    except Exception as e:
        return {"err": str(e)}
    found = []
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            text = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            if text.strip():
                found.append((hwnd, text[:60], cls))
        return True
    win32gui.EnumWindows(cb, None)
    sw = [w for w in found if "solid" in w[1].lower() or "sld" in w[1].lower() or "SOLID" in w[1]]
    log("  total_visible_windows=", len(found))
    for w in sw[:10]:
        log("  SW_WINDOW", w)
    return {"sw_windows": len(sw), "total": len(found)}
probe("enum_windows", enum_windows)

# 3. desktop_controller find_software_window 详细测试
from bridges.desktop_controller import DesktopController
ctl = DesktopController()
probe("find_software_window(solidworks)", lambda: ctl.find_software_window("solidworks"))

# 4. agent_chain_executor.preflight_apps 单独计时
try:
    import agent_chain_executor as ace
    log("import agent_chain_executor OK has_preflight_apps=", hasattr(ace, "preflight_apps"))
    probe("preflight_apps_timed", lambda: ace.preflight_apps(), timeout=30)
except Exception as e:
    log("import agent_chain_executor EXC", type(e).__name__, str(e)[:300])

log("DONE")
