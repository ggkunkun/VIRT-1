# -*- coding: utf-8 -*-
"""通过菜单'文件->打开'(id=57601)加载官方示例 .cnc，自动化标准文件对话框。"""
import os, sys, time
import win32gui, win32con

MAIN = 2297508
NC = sys.argv[1] if len(sys.argv) > 1 else r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\FANUC\FANUC0iM\FANUC\EX10.cnc"

def find_dialog():
    hits = []
    def cb(h, _):
        cls = win32gui.GetClassName(h)
        if win32gui.IsWindowVisible(h) and cls in ("#32770", "CabinetWClass"):
            hits.append(h)
        return True
    win32gui.EnumWindows(cb, None)
    return hits

def main():
    win32gui.SendMessage(MAIN, win32con.WM_COMMAND, 57601, 0)
    dlg = None
    for i in range(20):
        time.sleep(0.5)
        ds = find_dialog()
        if ds:
            dlg = ds[0]
            break
    if not dlg:
        print("no file dialog appeared")
        return 2
    print("dialog", dlg, win32gui.GetClassName(dlg), win32gui.GetWindowText(dlg), win32gui.GetWindowRect(dlg))

    kids = []
    def cb(h, _):
        kids.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h)))
        return True
    win32gui.EnumChildWindows(dlg, cb, None)
    for k in kids:
        print("  child", k)

    # 找文件名 Edit（一般 id=0x047c 或第一个可写 Edit）与 打开/保存 Button
    edit = ok_btn = None
    for h, cls, t in kids:
        if cls == "Edit" and edit is None:
            edit = h
        if cls == "Button" and ("打开" in t or "Open" in t or "Save" in t):
            ok_btn = h
    if edit is None:
        # ComboBoxEx 里的 Edit
        for h, cls, t in kids:
            if cls == "Edit":
                edit = h
    if edit:
        win32gui.SetWindowText(edit, NC)
        print("set filename:", NC)
    else:
        print("no edit found")
    if ok_btn:
        win32gui.SendMessage(ok_btn, win32con.BM_CLICK, 0, 0)
        print("clicked", ok_btn)
    else:
        # 兜底：IDOK
        win32gui.SendMessage(dlg, win32con.WM_COMMAND, win32con.IDOK, 0)
        print("sent IDOK")
    time.sleep(2)
    # 检查对话框是否关闭
    print("dialog alive?", win32gui.IsWindow(dlg))
    return 0

if __name__ == "__main__":
    sys.exit(main())
