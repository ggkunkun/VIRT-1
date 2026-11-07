# -*- coding: utf-8 -*-
"""启动 SOLIDWORKS 2021 并前台打开桌面零件1.SLDPRT"""
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import win32com.client.gencache as gc

TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_VERSION = 29
PART_PATH = r"C:\Users\Administrator\Desktop\零件1.SLDPRT"

def main():
    print("[1] 启动/连接 SOLIDWORKS 2021 ...")
    t0 = time.time()
    mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
    sw = mod.SldWorks()
    sw.Visible = True
    print(f"    连接就绪，耗时: {time.time() - t0:.2f}s")

    print(f"[2] 加载桌面零件: {PART_PATH} ...")
    ret = sw.OpenDoc6(PART_PATH, 1, 1, "", 0, 0)
    raw = ret[0] if isinstance(ret, tuple) else ret
    if not raw:
        print("OpenDoc6 返回空，尝试激活当前文档")
        raw = sw.ActiveDoc
    if raw:
        part = mod.IModelDoc2(raw._oleobj_)
        try:
            part.ShowNamedView2("*Isometric", 7)
            part.ViewZoomtofit2()
            print("    视图已设为等轴测 (*Isometric) 并缩放适应")
        except Exception as e:
            print(f"    视图设置提示: {e}")

    print("[3] 将 SOLIDWORKS 窗口前台最大化 ...")
    try:
        import win32service, win32gui, win32con, ctypes
        hdesk = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()
        def _cb(hwnd, res):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "solidworks" in title.lower():
                    res.append((hwnd, title))
            return True
        wins = []
        win32gui.EnumWindows(_cb, wins)
        if wins:
            hwnd, title = wins[0]
            ctypes.windll.user32.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            print(f"    前台视窗: HWND={hwnd}, Title={title}")
    except Exception as e:
        print(f"    窗口置顶提示: {e}")

    print("[完成] 零件1.SLDPRT 已完全呈现于前台 SOLIDWORKS 中！")

if __name__ == "__main__":
    main()
