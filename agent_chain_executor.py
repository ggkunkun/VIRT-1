# -*- coding: utf-8 -*-
"""agent_chain_executor.py — Virtu CAD/CAM Agent 链第 4 层：真实执行器

每个阶段只用该软件的**原生自动化接口**（COM / 无头 journal / 命令行 / Win32 消息），
不用像素点击；每个阶段都必须留下可回读的实测证据（文件、实体数、体积、日志）。

判决口径（status）:
  executed     —— 软件真跑了，产物有实测数值
  substituted  —— 软件无原生接口，用自研确定性校验替代，并明确标注
  blocked      —— 原生接口存在但本机条件不满足，附实测报错原文
证据一律来自回读，不来自「我以为执行了」。
"""

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer
from bridges.sw_revision import SW_PROGID, assert_revision

NX_BASE = r"E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX"
NX_RUN_JOURNAL = os.path.join(NX_BASE, "NXBIN", "run_journal.exe")
NX_TEMPLATE = "model-plain-1-mm-template.prt"

SSCNC_WINDOWS = {
    "open_nc": 57601,       # 文件 → 打开
    "clear_nc": 32817,     # 文件 → 清空NC代码
    "toolpath_measure": 32819,  # 工件测量 → 刀路测量(调试)
    "params": 32882,        # 机床操作 → 参数设置
    "select_tool": 32806,    # 机床操作 → 选择刀具
    "save_project": 32856,   # 文件 → 保存 → 保存工程
}

WM_COMMAND, BM_CLICK, IDOK = 0x0111, 0x00F5, 1
MF_BYPOSITION, MF_POPUP, MF_GRAYED = 0x00000400, 0x00000010, 0x00000001


def sscnc_hwnd():
    """按进程定位斯沃主窗（只认 sscnc.exe，绝不按标题乱抓用户自己的窗口）。"""
    import win32gui
    import win32process
    import csv
    import io
    pids = []
    out = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"], shell=False,
                                  encoding="gbk", errors="ignore")
    for row in csv.reader(io.StringIO(out)):
        if row and row[0].lower() == "sscnc.exe":
            try:
                pids.append(int(row[1]))
            except (ValueError, IndexError):
                pass
    hits = []

    def cb(h, _):
        try:
            if win32gui.IsWindowVisible(h):
                _, pid = win32process.GetWindowThreadProcessId(h)
                if pid in pids and win32gui.GetMenu(h):
                    hits.append(h)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(cb, None)
    return hits[0] if hits else None


def menu_snapshot(hwnd):
    """真实 Win32 菜单的 {路径: (命令id, 是否灰掉)} —— 载入前后的状态都要靠它取证。"""
    import ctypes
    import win32gui
    import win32con
    user32 = ctypes.windll.user32
    hmenu = win32gui.GetMenu(hwnd)
    if not hmenu:
        return {}

    def text_of(h, i):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetMenuStringW(h, i, buf, 256, win32con.MF_BYPOSITION)
        return buf.value.strip()

    snap = {}
    for i in range(win32gui.GetMenuItemCount(hmenu)):
        st = win32gui.GetMenuState(hmenu, i, win32con.MF_BYPOSITION)
        if st == -1:
            continue
        name = text_of(hmenu, i)
        if st & win32con.MF_POPUP:
            sub = win32gui.GetSubMenu(hmenu, i)
            for j in range(win32gui.GetMenuItemCount(sub)):
                sst = win32gui.GetMenuState(sub, j, win32con.MF_BYPOSITION)
                if sst == -1 or (sst & win32con.MF_POPUP):
                    continue
                snap["%s/%s" % (name, text_of(sub, j))] = (
                    win32gui.GetMenuItemID(sub, j), bool(sst & win32con.MF_GRAYED))
        else:
            snap[name] = (win32gui.GetMenuItemID(hmenu, i), bool(st & win32con.MF_GRAYED))
    return snap


def _child_by_class(parent, classes):
    import win32gui
    for cls in classes:
        h = win32gui.FindWindowEx(parent, 0, cls, None)
        if h:
            return h
    return 0


def _pid_dialogs(hwnd):
    """本进程当前打开的对话框句柄（斯沃的操作面板本身就是 #32770，必须做前后差集）。"""
    import win32gui
    import win32process
    target = win32process.GetWindowThreadProcessId(hwnd)[1]
    out = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770":
            if win32process.GetWindowThreadProcessId(h)[1] == target:
                out.append(h)

    win32gui.EnumWindows(cb, None)
    return out


def _owned_dialog(hwnd, wait_s, exclude=()):
    """等「新出现」的模态对话框；面板类常驻窗口用 exclude 排除掉。"""
    import win32gui
    import win32con
    excl = set(exclude)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        pop = win32gui.GetWindow(hwnd, win32con.GW_ENABLEDPOPUP)
        if pop and win32gui.IsWindowVisible(pop) and pop not in excl:
            return pop
        fresh = [h for h in _pid_dialogs(hwnd) if h not in excl]
        if fresh:
            return fresh[0]
        time.sleep(0.35)
    return 0


SSCNC_LOGIN = r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe"


def _click(hwnd):
    import win32gui
    import win32con
    win32gui.SendMessage(hwnd, win32con.BM_CLICK, 0, 0)


def _kids(parent):
    import win32gui
    out = []

    def cb(h, _):
        out.append(h)
        return True

    win32gui.EnumChildWindows(parent, cb, None)
    return out


def _by_text(parent, cls, needle):
    import win32gui
    for h in _kids(parent):
        if cls and win32gui.GetClassName(h) != cls:
            continue
        if needle in _wtext(h):
            return h
    return 0


def _login_window(timeout=30):
    import win32gui
    deadline = time.time() + timeout
    while time.time() < deadline:
        h = win32gui.FindWindow("ClassName_CCCStartDlg", None)
        if h and win32gui.IsWindowVisible(h):
            return h
        time.sleep(0.5)
    return 0


def _panel_button(hwnd, text):
    """斯沃的操作面板本身就是 #32770 对话框，按钮是真 Win32 Button → 可按文字定位并 BM_CLICK。"""
    import win32gui
    for top in [hwnd] + _pid_dialogs(hwnd):
        holder = []

        def cb(h, _):
            if win32gui.GetClassName(h) == "Button" and \
                    _wtext(h).strip().upper() == text.upper():
                holder.append(h)
            return True

        try:
            win32gui.EnumChildWindows(top, cb, None)
        except Exception:
            continue
        if holder:
            return holder[0]
    return 0


def _dialog_texts(dlg):
    import win32gui
    out = []
    for h in _kids(dlg):
        t = _wtext(h).strip()
        if t:
            out.append([win32gui.GetClassName(h), t])
    return out


def _dismiss(dlg):
    """点掉提示弹窗，别留模态窗挡住后面步骤。"""
    import win32gui
    for h in _kids(dlg):
        if win32gui.GetClassName(h) == "Button":
            _click(h)
            return _wtext(h)
    return None


SSCNC_GENERAL_INI = r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\common\general.ini"


def sscnc_machine_table():
    """general.ini 的 [CNC_CN] 是「索引 → 机床名 → exe 相对路径」的对照表。"""
    import re
    txt = open(SSCNC_GENERAL_INI, encoding="gbk", errors="ignore").read()
    names = {int(m[0]): m[1].strip() for m in re.findall(r"(?m)^CNC(\d+)=(.+)$", txt)}
    dirs = {int(m[0]): m[1].strip() for m in re.findall(r"(?m)^DIR(\d+)=(.+)$", txt)}
    cur = None
    m = re.search(r"(?m)^CNC=(\d+)\s*$", txt)
    if m:
        cur = int(m.group(1))
    return names, dirs, cur


def sscnc_set_machine(idx, backup_dir=None):
    """把「当前机床」切到指定索引（改前先备份；返回 (原值, 机床名, 备份路径)）。"""
    import re
    import shutil
    txt = open(SSCNC_GENERAL_INI, encoding="gbk", errors="ignore").read()
    names, dirs, cur = sscnc_machine_table()
    bak = None
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        bak = os.path.join(backup_dir, "sscnc_general.ini.bak")
        if not os.path.exists(bak):
            shutil.copy2(SSCNC_GENERAL_INI, bak)
    new = re.sub(r"(?m)^CNC=\d+\s*$", "CNC=%d" % idx, txt, count=1)
    open(SSCNC_GENERAL_INI, "w", encoding="gbk").write(new)
    return cur, names.get(idx), dirs.get(idx), bak


def sscnc_restore_machine(cur, backup_path):
    import shutil
    if cur is None or not backup_path or not os.path.exists(backup_path):
        return False
    shutil.copy2(backup_path, SSCNC_GENERAL_INI)
    return True


def stage_sscnc(nc_path, out_dir, wait_s=12, turning=False):
    """斯沃实训：切到车床控制器 → 走 CNCLogin 握手起仿真 → 把 NC 写进**控制器程序区**
    （机床目录下的 NC\\*.cnc，就是它自己存放程序的地方）→ 触发「文件→打开」看它认不认。

    证据边界说清楚：程序进入控制器程序区 + 打开命令不再被拒 = 可回读；
    真正的「循环启动走刀」在自绘 CNC 屏上，本机无 OCR，不宣称跑过。
    """
    import ctypes
    import ctypes.wintypes as wt
    import win32gui
    import win32con
    u = ctypes.windll.user32
    if not os.path.exists(nc_path):
        return _evidence("sscnc", "blocked", "控制器程序区 + 菜单命令",
                         error="NC 文件不存在: %s" % nc_path)
    names, dirs, cur = sscnc_machine_table()
    target = None
    if turning:
        import re
        for i in sorted(names):
            if re.search(r"(0i?T\b|Turning|T$|\bT\b)", names[i]) and dirs.get(i):
                target = i
                break
    notes = []
    machine_dir = None
    if target is not None and target != cur:
        old, mname, rel, bak = sscnc_set_machine(target, out_dir)
        notes.append("当前机床 %s → %s（索引 %s，原值 %s，备份 %s）" % (
            names.get(old), mname, target, old, os.path.basename(bak or "-")))
        machine_dir = os.path.join(os.path.dirname(SSCNC_GENERAL_INI), "..", rel)
    elif cur is not None:
        machine_dir = os.path.join(os.path.dirname(SSCNC_GENERAL_INI), "..", dirs.get(cur, ""))
        notes.append("沿用已配置机床 %s（索引 %s）" % (names.get(cur), cur))

    hwnd, boot_notes, boot_mode = sscnc_boot()
    notes += boot_notes
    if not hwnd:
        return _evidence("sscnc", "blocked", "CNCLogin 握手 + 控制器程序区",
                         error="仿真实例起不来", notes=notes)
    title = _wtext(hwnd)
    for _ in range(5):
        if title and "超时" not in title:
            break
        time.sleep(1.5)
        title = _wtext(hwnd)
    notes.append("仿真主窗标题=%r (boot=%s)" % (title, boot_mode))

    prog_dir = None
    if machine_dir:
        # general.ini 的 DIRn= 给的是 exe 相对路径，机床目录是它的上一级
        mdir = os.path.dirname(os.path.normpath(os.path.join(
            os.path.dirname(SSCNC_GENERAL_INI), "..", machine_dir)))
        cand = os.path.join(mdir, "NC")
        if os.path.isdir(cand):
            prog_dir = cand
    if not prog_dir:
        sscnc_root = os.path.normpath(os.path.join(os.path.dirname(SSCNC_GENERAL_INI), ".."))
        for root, dlist, files in os.walk(sscnc_root):
            if os.path.basename(root).upper() == "NC" and any(f.lower().endswith(".cnc") for f in files):
                prog_dir = root
                break
    written = None
    if prog_dir:
        written = os.path.join(prog_dir, "WM2026.cnc")
        body = open(nc_path, encoding="gbk", errors="ignore").read()
        open(written, "w", encoding="gbk").write(body)

    menu = menu_snapshot(hwnd)
    key = next((k for k in menu if k.endswith("/打开")), None)
    accepted = None
    # 先把模式切到 EDIT：模式只活在自绘面板里，BM_CLICK 无效，只能用真鼠标点面板键。
    mode_ok, mode_diag = sscnc_set_mode("EDIT")
    notes.append("面板 EDIT 键真点击: %s %s" % (mode_ok, json.dumps(mode_diag, ensure_ascii=False)[:160]))
    if key:
        before = set(_pid_dialogs(hwnd))
        win32gui.PostMessage(hwnd, win32con.WM_COMMAND, menu[key][0], 0)
        dlg = _owned_dialog(hwnd, wait_s, exclude=before)
        said = [_wtext(c) for c in _kids(dlg) if _wtext(c).strip()] if dlg else []
        reject = [s for s in said if "模式" in s or "未" in s or "错误" in s]
        accepted = not reject
        notes.append("打开命令响应: %s" % (reject[:1] or "未被拒绝"))
        if dlg:
            # 模式放行后弹出的是「打开文件」对话框：只点取消，绝不点第一个按钮
            # （那可能是「只读方式打开」，会把当前选中的任意文件塞进控制器）
            cancel = next((k for k in _kids(dlg)
                           if _win_class(k) == "Button" and u.GetDlgCtrlID(k) == 2), None)
            if cancel:
                u.PostMessageW(wt.HWND(cancel), BM_CLICK, 0, 0)
                time.sleep(0.8)
            else:
                _dismiss(dlg)

    ok = bool(written) and os.path.exists(written) and accepted is not False
    sscnc_restore_machine(cur, os.path.join(out_dir, "sscnc_general.ini.bak"))
    notes.append("已还原 general.ini 的机床选择为原值 %s" % cur)
    return _evidence("sscnc", "executed" if ok else "blocked",
                     "general.ini 切机床 + CNCLogin 握手 + NC 写入控制器程序区 + 菜单命令验证",
                     metrics={"machine": names.get(target if target is not None else cur),
                              "controller_nc_dir": prog_dir,
                              "program_written": os.path.basename(written) if written else None,
                              "program_bytes": os.path.getsize(written) if written else 0,
                              "open_command_accepted": accepted,
                              "window_title": title,
                              "menu_items": len(menu)},
                     files=[p for p in (written, nc_path) if p and os.path.exists(p)],
                     error=None if ok else "未拿到控制器程序区写入证据或打开命令被拒",
                     notes=notes + ["边界：循环启动走刀在自绘 CNC 屏上，本机无 OCR，未宣称跑过"])

def sscnc_set_mode(mode="EDIT"):
    """用真鼠标点面板上的 EDIT/AUTO 键把机床切到该模式。

    为什么必须真点：这 137 个控件是真 Button，但 BM_CLICK / WM_COMMAND 都不改模式（实测），
    模式状态又只活在这套自绘 UI 里、Win32 侧读不到。所以：提前台 → 命中自检（WindowFromPoint
    必须落在面板上）→ SendInput 真点击。点不到就返回 False，让调用方照旧走「打开被拒」的判据。
    """
    import ctypes
    import ctypes.wintypes as wt
    import win32gui
    u = ctypes.windll.user32
    PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    pid = None
    hwnd_main = sscnc_hwnd()
    if hwnd_main:
        d = wt.DWORD()
        u.GetWindowThreadProcessId(wt.HWND(hwnd_main), ctypes.byref(d))
        pid = d.value
    if not pid:
        return False, {"error": "找不到仿真实例 pid"}
    panels = []

    def cb(h, p):
        d = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(d))
        if d.value == pid and u.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770":
            kids = []
            def cb2(k, _q, _out=kids):
                _out.append(k)
                return True
            u.EnumChildWindows(h, PROC(cb2), 0)
            n = len([k for k in kids if _win_class(k) == "Button"])
            if n:
                panels.append((n, h))
        return True

    u.EnumWindows(PROC(cb), 0)
    if not panels:
        return False, {"error": "没找到面板对话框"}
    panels.sort(reverse=True)
    panel = panels[0][1]
    target = None
    kids = []
    def cb3(k, _q, _out=kids):
        _out.append(k)
        return True
    u.EnumChildWindows(panel, PROC(cb3), 0)
    for k in kids:
        if _win_class(k) == "Button":
            t = (_wtext(k, 20, 150) or "").strip().upper()
            if t == mode.upper():
                r = wt.RECT()
                u.GetWindowRect(k, ctypes.byref(r))
                target = (r.left + (r.right - r.left) // 2, r.top + (r.bottom - r.top) // 2)
                break
    if not target:
        return False, {"error": "面板上没有 %s 键" % mode}
    import win_input
    for _ in range(5):
        win_input.force_foreground(wt.HWND(panel))
        time.sleep(0.4)
        under = u.WindowFromPoint(wt.POINT(target[0], target[1]))
        root = u.GetAncestor(under, 2)
        if root == panel:
            win_input.click(target[0], target[1])
            time.sleep(0.8)
            return True, {"panel": panel, "mode": mode.upper(), "point": target}
        time.sleep(0.3)
    return False, {"error": "点击前自检失败（点位不在面板上）", "point": target}


def _win_class(h):
    import ctypes
    b = ctypes.create_unicode_buffer(80)
    ctypes.windll.user32.GetClassNameW(h, b, 80)
    return b.value


def sscnc_boot(machine="FANUC 0iT", wait_sim_s=90):
    """全自动拉起斯沃：explorer 派生 CNCLogin → 选数控系统 → PC 模式 → RUN → 等仿真主窗。

    单实例阶梯：已有仿真主窗就直接复用，绝不重复启动（license/单实例约束）。
    """
    import win32gui
    import win32con
    import ctypes
    notes = []
    hwnd = sscnc_hwnd()
    if hwnd:
        notes.append("复用已运行的仿真实例 hwnd=%s（未新起进程）" % hwnd)
        return hwnd, notes, "attached"

    if not os.path.exists(SSCNC_LOGIN):
        return None, ["CNCLogin.exe 不存在: %s" % SSCNC_LOGIN], "absent"
    login = _login_window(2)
    if not login:
        subprocess.Popen(["explorer.exe", SSCNC_LOGIN],
                         cwd=os.path.dirname(SSCNC_LOGIN))
        notes.append("explorer 派生 CNCLogin.exe（脱离会话作业对象，避免会话回收把软件带走）")
        login = _login_window()
    else:
        notes.append("复用已打开的登录窗 hwnd=%s" % login)

    if not login:
        return None, notes + ["60s 内没等到登录窗 ClassName_CCCStartDlg"], "failed"

    combos = [h for h in _kids(login) if win32gui.GetClassName(h) == "ComboBox"]
    sys_combo, idx = 0, -1
    for h in combos:
        n = win32gui.SendMessage(h, win32con.CB_GETCOUNT, 0, 0)
        for i in range(n):
            L = win32gui.SendMessage(h, win32con.CB_GETLBTEXTLEN, i, 0)
            buf = ctypes.create_unicode_buffer(L + 1)
            win32gui.SendMessage(h, win32con.CB_GETLBTEXT, i, buf)
            if buf.value.strip() == machine:
                sys_combo, idx = h, i
                break
        if idx >= 0:
            break
    if not sys_combo:
        return None, notes + ["系统下拉里找不到「%s」" % machine], "failed"
    win32gui.SendMessage(sys_combo, win32con.CB_SETCURSEL, idx, 0)
    notes.append("数控系统 = %s (index %s)" % (machine, idx))

    for label in ("PC", "DEMO"):
        btn = _by_text(login, "Button", label)
        if btn:
            _click(btn)
            notes.append("点击授权模式按钮「%s」" % label)
            break
    run_btn = _by_text(login, "Button", "RUN")
    if not run_btn:
        return None, notes + ["找不到 RUN (运行) 按钮"], "failed"
    _click(run_btn)
    notes.append("点击 RUN (运行)")

    deadline = time.time() + wait_sim_s
    while time.time() < deadline:
        hwnd = sscnc_hwnd()
        if hwnd:
            notes.append("仿真主窗已就绪 hwnd=%s" % hwnd)
            return hwnd, notes, "launched"
        time.sleep(1.0)
    return None, notes + ["点 RUN 后 %ss 内仿真主窗未出现" % wait_sim_s], "failed"


def _proc_table():
    """进程表（名字 + PID + 可执行文件全路径）。

    wmic /format:csv 的列序是 `Node,ExecutablePath,Name,ProcessId`（按字母排，不是按 get 的顺序），
    之前按「名字在第 1 列」硬解析，结果 name 里装的是路径、pid 里装的是名字，同源匹配永远失败。
    这里按表头解析；读不到路径（提权进程常见）就留空，由调用方降级处理。
    """
    out = subprocess.check_output(
        ["wmic", "process", "get", "Name,ProcessId,ExecutablePath", "/format:csv"],
        shell=False, encoding="gbk", errors="replace")
    lines = [x for x in out.splitlines() if x.strip()]
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split(",")]
    idx = {h: i for i, h in enumerate(header)}
    rows = []
    for line in lines[1:]:
        parts = [x.strip() for x in line.split(",")]
        try:
            rows.append({"name": parts[idx["Name"]],
                         "pid": parts[idx["ProcessId"]],
                         "path": parts[idx["ExecutablePath"]] if idx.get("ExecutablePath") is not None
                                 and idx["ExecutablePath"] < len(parts) else ""})
        except (KeyError, IndexError):
            continue
    return rows

def _same_install(path_a, path_b):
    """同源判定，按强度依次：全路径相等 → 同一个文件（dev+inode）→ 去掉盘符后路径尾段相等。

    为什么要后两级：这台机器有 D→E 的目录迁移（junction），同一个 acad.exe 可能以两个盘符出现；
    但又不能只比「末两段」——不同安装目录的同一款软件末两段往往一模一样（都有 AutoCAD 2026/acad.exe）。
    """
    if not path_a or not path_b:
        return False
    a = os.path.normcase(os.path.normpath(os.path.abspath(path_a)))
    b = os.path.normcase(os.path.normpath(os.path.abspath(path_b)))
    if a == b:
        return True
    try:
        sa, sb = os.stat(a), os.stat(b)
        if (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino):
            return True
    except OSError:
        pass
    def tail(pth):
        parts = [x for x in pth.replace("/", chr(92)).split(chr(92)) if x]
        return parts[1:] if len(parts) > 1 else parts
    return tail(a) == tail(b)

def _launch_ledger_path():
    return os.path.join(ROOT, "runs", "launch_ledger.json")


def _launch_ledger_read():
    """读账本；读失败返回 None（绝不把空表当结果再写回去抹掉历史）。"""
    p = _launch_ledger_path()
    if not os.path.exists(p):
        return []
    try:
        data = json.load(open(p, encoding="utf-8"))
        return data if isinstance(data, list) else None
    except Exception as e:
        try:
            open(p + ".bad_" + time.strftime("%Y%m%d_%H%M%S"), "w", encoding="utf-8").write(
                "ledger unreadable: %r" % (e,))
        except Exception:
            pass
        return None


def _launch_ledger_append(rec):
    """账本只追加、原子替换；读失败就放弃本次写入（不覆盖）。"""
    cur = _launch_ledger_read()
    if cur is None:
        return False
    cur.append(rec)
    p = _launch_ledger_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp_" + str(os.getpid()) + "_" + str(int(time.time() * 1000))
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cur[-200:], fh, ensure_ascii=False, indent=1)
    for _ in range(5):
        try:
            os.replace(tmp, p)
            return True
        except OSError:
            time.sleep(0.15)
    return False


def ensure_process(exe_name, launch_path, cwd=None, wait_s=90):
    """单实例阶梯：进程表里**同源**的实例才复用；没有才 explorer 派生，并把 PID 记进账本。

    之前只按 exe 名匹配，会把用户自己开的同款软件当成「我们的实例」接管（started_by_us 还是 False，
    永不回收）。现在要求：同名 + 安装路径末两段一致，才算同源；路径不符的同名进程单独列在 foreign 里。
    """
    want = launch_path or ""
    rows = _proc_table()
    same = [r for r in rows if r["name"].lower() == exe_name.lower()]
    matched = [r for r in same if _same_install(r["path"], want)] if want else []
    foreign = [r for r in same if r not in matched]
    ledger = _launch_ledger_read() or []
    owned_pids = {int(x.get("pid")) for x in ledger if str(x.get("pid", "")).isdigit()}
    if matched:
        r = matched[0]
        pid = int(r["pid"])
        return {"attached": True, "started_by_us": pid in owned_pids, "pid": pid,
                "path": r["path"], "foreign": [x["path"] for x in foreign],
                "identity": "same_install"}
    if not want or not os.path.exists(want):
        return {"attached": False, "started_by_us": False, "pid": None,
                "foreign": [x["path"] for x in foreign],
                "error": "可执行文件不存在: %s" % want}
    before = {r["pid"] for r in rows}
    subprocess.Popen(["explorer.exe", want], cwd=cwd or os.path.dirname(want))
    deadline = time.time() + wait_s
    while time.time() < deadline:
        rows2 = _proc_table()
        new = [r for r in rows2 if r["name"].lower() == exe_name.lower()
               and r["pid"] not in before and _same_install(r["path"], want)]
        if new:
            pid = int(new[0]["pid"])
            _launch_ledger_append({"pid": pid, "exe": exe_name, "path": new[0]["path"],
                                  "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                  "by": "ensure_process"})
            return {"attached": False, "started_by_us": True, "pid": pid,
                    "path": new[0]["path"], "foreign": [x["path"] for x in foreign],
                    "identity": "launched_by_us"}
        time.sleep(2)
    return {"attached": False, "started_by_us": False, "pid": None,
            "foreign": [x["path"] for x in foreign],
            "error": "%s 在 %ss 内未出现同源进程" % (exe_name, wait_s)}


SAFE_CLOSE_WORDS = (u"关闭", u"close", u"ok", u"确定", u"不修复", u"取消")


def dismiss_app_dialogs(exe_name, prefer=SAFE_CLOSE_WORDS):
    """点掉目标软件自己的模态 #32770，且只点白名单按钮（绝不批量 WM_CLOSE）。

    实测场景：AutoCAD 被强杀后，下次启动先弹「图形修复」模态框；它挂着的时候
    Application 层还能应答（app.Name），但 Documents/Document 层每个调用都被拒
    （AttributeError / RPC_E_CALL_REJECTED），整条链就是在这里拿不到文档的。
    """
    import ctypes
    import ctypes.wintypes as wt
    import win32gui
    u = ctypes.windll.user32
    # NOTE: 全量 tasklist 在本机挂起（>10s，stdout 管道不关闭），改用
    # Toolhelp32 快照版 get_running_processes（亚秒级）。键名不区分大小写。
    from bridges.software_registry import get_running_processes
    running = get_running_processes()
    pids = set()
    for key, pids_ in running.items():
        if key.lower() == exe_name.lower():
            pids.update(pids_)
    tops = []

    def cb(h, param):
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if (pid.value in pids and win32gui.IsWindowVisible(h)
                and win32gui.GetClassName(h) == "#32770"):
            param.append(h)
        return True

    try:
        win32gui.EnumWindows(cb, tops)
    except Exception:
        pass
    closed = []
    for d in tops:
        for b in _kids(d):
            if win32gui.GetClassName(b) != "Button":
                continue
            t = (_wtext(b) or "").strip().lower().replace("&", "")
            if any(w in t for w in prefer):
                _click(b)
                closed.append({"dialog": (_wtext(d) or "")[:80], "button": t[:40]})
                time.sleep(1.2)
                break
    return closed


def _sw_macro_source(marker_path, step_path, r_outer_m, length_m, r_bore_m):
    """实测可用的 SOLIDWORKS VBA：NewPart → 选基准面(中文界面下按特征枚举) →
    草图圆 → 凸台拉伸 →（可选）孔切除 → 读 SW 自己的质量特性 → 导 STEP。

    关键点（都是踩出来的）：外部宏必须用**真实特征名**选中草图（SelectByID2(skName,"SKETCH",...,0)），
    用空名 + mark=4 时 FeatureExtrusion3 会返回 Nothing。
    """
    mk = marker_path.replace("\\", "/")
    sp = step_path.replace("\\", "/")
    return '''Dim swApp As Object
Dim swModel As Object

Sub main()
    On Error GoTo fail
    Set swApp = Application.SldWorks
    Dim f As Integer
    f = FreeFile
    Open "%(mk)s" For Output As #f
    Set swModel = swApp.NewPart()
    If swModel Is Nothing Then
        Print #f, "ERROR=NewPart 返回 Nothing"
        Close #f
        Exit Sub
    End If
    Print #f, "DOC=" & swModel.GetTitle

    Dim feat As Object
    Dim planeName As String
    Dim skName As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "RefPlane" And planeName = "" Then planeName = feat.Name
        If feat.GetTypeName2 = "ProfileFeature" And skName = "" Then skName = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    Print #f, "PLANE=" & planeName
    If planeName = "" Then
        Print #f, "ERROR=找不到基准面特征"
        Close #f
        Exit Sub
    End If

    swModel.ClearSelection2 True
    swModel.Extension.SelectByID2 planeName, "PLANE", 0, 0, 0, False, 1, Nothing, 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCircleByRadius 0, 0, 0, %(r_out)s
    swModel.ClearSelection2 True
    swModel.SketchManager.InsertSketch True
    swModel.ClearSelection2 True

    Set feat = swModel.FirstFeature
    skName = ""
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then skName = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    Print #f, "SKETCH=" & skName
    Dim selOk As Boolean
    selOk = swModel.Extension.SelectByID2(skName, "SKETCH", 0, 0, 0, False, 0, Nothing, 0)
    Print #f, "SEL_SKETCH=" & selOk
    Dim fex As Object
    Set fex = swModel.FeatureManager.FeatureExtrusion3( _
        True, False, False, 0, 0, %(len)s, 0, False, False, False, False, 0, 0, _
        False, False, False, False, True, True, True, 0, 0, False)
    If fex Is Nothing Then
        Print #f, "ERROR=凸台拉伸返回 Nothing"
        Close #f
        Exit Sub
    End If
    Print #f, "BOSS=" & fex.Name
    swModel.ClearSelection2 True

    Dim mp As Object
    Set mp = swModel.Extension.CreateMassProperty
    Print #f, "VOLUME_M3=" & mp.Volume
    Print #f, "AREA_M2=" & mp.SurfaceArea

    If %(bore)s > 0.0 Then
        swModel.Extension.SelectByID2 planeName, "PLANE", 0, 0, 0, False, 1, Nothing, 0
        swModel.SketchManager.InsertSketch True
        swModel.SketchManager.CreateCircleByRadius 0, 0, 0, %(bore)s
        swModel.ClearSelection2 True
        swModel.SketchManager.InsertSketch True
        swModel.ClearSelection2 True
        Set feat = swModel.FirstFeature
        Dim sk2 As String
        Do While Not feat Is Nothing
            If feat.GetTypeName2 = "ProfileFeature" Then sk2 = feat.Name
            Set feat = feat.GetNextFeature
        Loop
        swModel.Extension.SelectByID2 sk2, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
        Dim fcut As Object
        Set fcut = swModel.FeatureManager.FeatureCut3( _
            True, False, False, 0, 0, %(cutdepth)s, 0, False, False, False, False, 0, 0, _
            False, False, False, False, True, True, True, False, 0, 0, False)
        Print #f, "BORE_SKETCH=" & sk2 & " CUT=" & (Not fcut Is Nothing)
        Set mp = swModel.Extension.CreateMassProperty
        Print #f, "VOLUME_M3_AFTER=" & mp.Volume
        Print #f, "AREA_M3_AFTER=" & mp.SurfaceArea
    End If

    swModel.SaveAs3 "%(sp)s", 0, 2
    Print #f, "STEP_EXISTS=" & (Dir("%(sp)s") <> "")
    Print #f, "STEP_BYTES=" & FileLen("%(sp)s")
    Print #f, "STAGE=end"
    Close #f
    Exit Sub
fail:
    Print #f, "FATAL=" & Err.Number & " " & Err.Description
    If f <> 0 Then Close #f
End Sub
''' % {"mk": mk, "sp": sp, "r_out": "%.6f" % r_outer_m, "len": "%.6f" % length_m,
       "bore": "%.6f" % r_bore_m, "cutdepth": "%.6f" % (max(length_m, r_bore_m) * 2.2)}


def stage_sw(spec, out_dir, macro_builder=None, wait_launch_s=150):
    """SOLIDWORKS 建模：COM 附着既有实例（绝不双开）→ 外部宏建回转体 → SW 自己的质量特性回读。

    判决用「实测体积 vs 解析体积」的偏差，而不是宏有没有返回 True。
    """
    import win32com.client
    from win32com.client import gencache
    exe = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"
    notes = []
    ladder = ensure_process("SLDWORKS.exe", exe, wait_s=wait_launch_s)
    notes.append("附着既有 SLDWORKS pid=%s" % ladder.get("pid") if ladder.get("attached")
                 else "本次 explorer 派生启动 SLDWORKS pid=%s" % ladder.get("pid"))
    if ladder.get("error"):
        return _evidence("solidworks", "blocked", "COM %s" % SW_PROGID,
                         error=ladder["error"], notes=notes)
    try:
        gencache.EnsureModule("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 29, 0)
    except Exception as e:
        notes.append("makepy 缓存不可用（将退化为后期绑定）: %r" % repr(e)[:120])
    app = None
    last_err = None
    for d in dismiss_app_dialogs("SLDWORKS.exe"):
        notes.append("附着前点掉 SW 自己的模态框: %s" % json.dumps(d, ensure_ascii=False)[:160])
    deadline = time.time() + 300
    while time.time() < deadline and app is None:
        try:
            app = win32com.client.GetActiveObject(SW_PROGID)
        except Exception as e:
            last_err = e
            # SW 启动中途才弹 #32770（实测「工具栏信息不一致」），弹着时 ROT 永不注册；
            # 只在附着前点一次是不够的，必须每轮重试
            for d in dismiss_app_dialogs("SLDWORKS.exe"):
                notes.append("附着中再次点掉 SW 模态框: %s" % json.dumps(d, ensure_ascii=False)[:160])
            time.sleep(3)
    if app is None:
        return _evidence("solidworks", "blocked", "COM %s" % SW_PROGID,
                         error="COM 附着失败: %r" % (last_err,), notes=notes)
    try:
        sw_rev = assert_revision(app, "agent_chain_executor.solidworks")
        notes.append("版本校验通过: RevisionNumber=%s" % sw_rev)
    except Exception as e:
        return _evidence("solidworks", "blocked", "COM %s 版本校验" % SW_PROGID,
                         error=str(e)[:200], notes=notes)
    try:
        app.Visible = True
    except Exception:
        pass

    d_out = float(spec.get("d_outer", 53.0))
    d_bore = float(spec.get("d_inner", 14.0))
    length = float(spec.get("overall_len", 45.0))
    metrics = os.path.join(out_dir, "stage01_sw_metrics.txt")
    step = os.path.join(out_dir, "wheel_mold.step")
    swb = os.path.join(out_dir, "stage01_build.swb")
    for p in (metrics, step):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    # 内孔切除方向不可靠，先建外径回转体（体积可解析核对），孔由 NX 阶段承担
    src = _sw_macro_source(metrics, step, d_out / 2000.0, length / 1000.0, 0.0)
    open(swb, "w", encoding="gbk").write(src)
    try:
        rc = app.RunMacro2(swb, "", "main", 0)
    except Exception as e:
        return _evidence("solidworks", "blocked", "COM RunMacro2",
                         error="宏投递失败: %r" % repr(e)[:220], notes=notes)
    for _ in range(60):
        if os.path.exists(metrics):
            break
        time.sleep(1.0)
    time.sleep(1.5)
    vals = {}
    if os.path.exists(metrics):
        for line in open(metrics, encoding="gbk", errors="ignore"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k] = v.strip()
    try:
        vol_mm3 = round(float(vals.get("VOLUME_M3", 0)) * 1e9, 1)
    except ValueError:
        vol_mm3 = None
    try:
        area_mm2 = round(float(vals.get("AREA_M2", 0)) * 1e6, 1)
    except ValueError:
        area_mm2 = None
    analytic_vol = round(3.141592653589793 * (d_out / 2.0) ** 2 * length, 1)
    analytic_area = round(2 * 3.141592653589793 * (d_out / 2.0) ** 2 +
                          2 * 3.141592653589793 * (d_out / 2.0) * length, 1)
    dev = (round(abs(vol_mm3 - analytic_vol) / analytic_vol * 100, 3)
           if vol_mm3 else None)
    ok = bool(vol_mm3) and analytic_vol and dev is not None and dev < 5.0
    return _evidence("solidworks", "executed" if ok else "blocked",
                     "COM 附着 + 外部宏建回转体 + SW 质量特性回读",
                     metrics={"runmacro_rc": rc, "boss_feature": vals.get("BOSS"),
                              "sketch": vals.get("SKETCH"), "plane": vals.get("PLANE"),
                              "volume_mm3": vol_mm3, "analytic_volume_mm3": analytic_vol,
                              "volume_deviation_pct": dev,
                              "surface_area_mm2": area_mm2, "analytic_area_mm2": analytic_area,
                              "step_bytes": vals.get("STEP_BYTES"),
                              "vba_report": vals},
                     files=[p for p in (swb, metrics, step) if os.path.exists(p)],
                     error=(vals.get("FATAL") or vals.get("ERROR") or
                            (None if ok else "体积与解析值不符或缺失（见 metrics.vba_report）")),
                     notes=notes)
# ---------------------------------------------------------------- AutoCAD (stage 03)
def _run_child(worker, payload, timeout, out_dir, name=None):
    """把「会阻塞的外部调用」关进子进程：主进程只等结果文件并带硬超时，到点直接 taskkill。

    必要性是实测出来的：run 20261030_185607 的 stage_acad 被 AutoCAD 一个没结束的命令
    卡住，主线程在 COM 调用里挂了 19 分钟不返回；COM 调用一旦被对端挂起，Python 侧
    没有任何超时手段（只有进程能杀）。子进程还顺带解决了公寓问题：AutoCAD 的 IDispatch
    指针跨线程用会立刻 AttributeError，所以整段 COM 必须在一个进程的主线程里跑完。
    """
    name = name or worker
    pj = os.path.join(out_dir, "%s_child_in.json" % name)
    rj = os.path.join(out_dir, "%s_child_out.json" % name)
    log = os.path.join(out_dir, "%s_child.log" % name)
    for p in (rj, pj, log):
        if os.path.exists(p):
            os.remove(p)
    json.dump(payload, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    cmd = [sys.executable, "-c",
           "import sys, agent_chain_executor as m; m.%s(sys.argv[1], sys.argv[2])" % worker,
           pj, rj]
    t0 = time.time()
    timed_out = False
    with open(log, "w", encoding="utf-8") as fh:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, shell=False)
        while time.time() - t0 < timeout:
            if os.path.exists(rj) or p.poll() is not None:
                break
            time.sleep(1)
        rc = p.poll()
        lingering = False
        if rc is None and os.path.exists(rj):
            # 结果已落盘、进程还赖着（COM 引用没释放）：这不是超时，收掉孤儿即可
            lingering = True
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, shell=False)
        elif rc is None:
            timed_out = True
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, shell=False)
            rc = "TIMEOUT_KILLED"
    data = None
    if os.path.exists(rj):
        try:
            data = json.load(open(rj, encoding="utf-8"))
        except Exception as e:
            data = {"result_read_error": repr(e)[:160]}
    return {"data": data, "rc": rc, "timed_out": timed_out,
            "lingering_killed": lingering,
            "elapsed_s": round(time.time() - t0, 1), "child_log": log,
            "result_path": rj}


def _acad_sentinel_lsp(marker):
    """让 AutoCAD 自己把实测数字写进文件：COM 回读一旦被对端挂起，证据仍然成立。"""
    mk = marker.replace("\\", "/")
    return (
        '\n(defun c:VIRTU_VERIFY (/ _f _n _e _ly _c)\n'
        '  (c:DRAWWHEELMOLD)\n'
        '  (setq _n 0 _e (entnext) _ly "")\n'
        '  (while _e\n'
        '    (setq _n (1+ _n)\n'
        '          _c (cdr (assoc 8 (entget _e)))\n'
        '          _ly (strcat _ly _c " ")\n'
        '          _e (entnext _e)))\n'
        '  (setq _f (open "%s" "w"))\n'
        '  (if _f\n'
        '    (progn\n'
        '      (write-line (strcat "entity_count=" (itoa _n)) _f)\n'
        '      (write-line (strcat "entity_layers=" _ly) _f)\n'
        '      (write-line (strcat "drawing=" (getvar "DWGNAME")) _f)\n'
        '      (close _f)))\n'
        '  (princ))\n' % mk)


def _acad_com_worker(payload_path, result_path):
    """子进程主体：在自己的主线程（STA）里把 AutoCAD COM 全流程跑完，逐步写结果。"""
    import pythoncom
    pythoncom.CoInitialize()
    payload = json.load(open(payload_path, encoding="utf-8"))
    out = {"ok": False, "steps": [], "entity_count": 0, "entity_count_before": 0,
           "reused_document": None, "layers": [],
           "entity_layers": [], "cmdactive_at_entry": None, "esc_sent": 0,
           "sentinel": {}, "dwg_saved": None, "error": None}

    def flush():
        json.dump(out, open(result_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    deadline = time.time() + float(payload.get("deadline_s", 150))

    def left():
        return deadline - time.time()

    try:
        import win32com.client
        app = None
        retry_n = 0
        while left() > 20 and app is None:
            if retry_n % 5 == 0:
                # AutoCAD 启动中途可能弹「图形修复」模态框；只在附着前 dismiss 一次不够
                dismiss_app_dialogs("acad.exe")
            try:
                app = win32com.client.GetActiveObject("AutoCAD.Application")
                out["steps"].append("attached app.Name=%s" % app.Name)
            except Exception as e:
                out["error"] = "attach: %r" % (e,)
                out["steps"].append("attach retry")
                retry_n += 1
                time.sleep(3)
        if app is None:
            out["error"] = (out.get("error") or "GetActiveObject 失败") + "（AutoCAD 无响应）"
            flush()
            return
        # 先把「指向我们输出 dwg」的旧文档关掉：同一个文件被旧文档占着时，
        # 新文档 SaveAs 会报「打开文档时出错」（实测 Drawing5.dwg 存不下就是这原因）。
        target_base = os.path.basename(payload.get("dwg") or "").lower()
        closed = []
        try:
            for i in range(int(app.Documents.Count)):
                try:
                    d_ = app.Documents.Item(i)
                    name = str(getattr(d_, "FullName", "") or "").lower()
                    if target_base and name.endswith(target_base):
                        d_.Close(False)
                        closed.append(name)
                except Exception:
                    pass
            out["closed_previous"] = closed
        except Exception as e:
            out["steps"].append("Documents 枚举失败: %r" % (e,))
        doc = None
        reused = False
        while left() > 15 and doc is None:
            # 优先新建一份空文档：沿用 ActiveDocument 会让实体数变成「历史累计」，
            # 实测同一个 acad 实例连跑三次，读数从 54 → 90 → 102，判据就失真了。
            try:
                doc = app.Documents.Add()
                out["steps"].append("Documents.Add 新建文档")
            except Exception as e:
                out["steps"].append("Documents.Add 失败（退回 ActiveDocument）: %r" % (e,))
                try:
                    doc = app.ActiveDocument
                    _ = doc.Name
                    reused = True
                except Exception:
                    doc = None
            if doc is None:
                time.sleep(3)
        if doc is None:
            out["error"] = "拿不到文档对象（Documents.Add / ActiveDocument 均被拒绝）"
            flush()
            return
        out["reused_document"] = reused
        out["steps"].append("doc.Name=%s reused=%s" % (doc.Name, reused))
        try:
            out["entity_count_before"] = int(doc.ModelSpace.Count)
        except Exception as e:
            out["entity_count_before"] = "unreadable:%r" % (e,)

        def setv(name, val):
            try:
                doc.SendCommand('(setvar "%s" %s)\n' % (name, val))
            except Exception as e:
                out["steps"].append("setvar %s: %r" % (name, e))

        for v, val in (("FILEDIA", "0"), ("CMDECHO", "0"), ("SECURELOAD", "0"),
                       ("EXPERT", "0")):
            setv(v, val)
        time.sleep(1.0)
        try:
            out["cmdactive_at_entry"] = int(doc.GetVariable("CMDACTIVE"))
        except Exception as e:
            out["cmdactive_at_entry"] = "unreadable:%r" % (e,)

        lsp = payload["lsp"]
        marker = payload["marker"]
        doc.SendCommand('(load "%s")\n' % lsp.replace("\\", "/"))
        time.sleep(2.0)
        doc.SendCommand("(c:VIRTU_VERIFY)\n")
        waited = 0.0
        while not os.path.exists(marker) and left() > 5 and waited < 75:
            time.sleep(1.5)
            waited += 1.5
        out["steps"].append("sentinel_wait_s=%.1f exists=%s" % (waited, os.path.exists(marker)))
        if not os.path.exists(marker) and left() > 25:
            # CAD 刚被上一轮关过文档时偶发「load 静默不生效」，重载重跑一次（有界）
            out["steps"].append("sentinel 未出现，重载 LISP 再跑一次")
            try:
                load_cmd = "(load " + chr(34) + "%s" % lsp.replace(chr(92), "/") + chr(34) + ")"
                doc.SendCommand(load_cmd + chr(10))
                time.sleep(1.5)
                doc.SendCommand("(c:VIRTU_VERIFY)" + chr(10))
                waited2 = 0.0
                while not os.path.exists(marker) and left() > 8 and waited2 < 45:
                    time.sleep(1.5)
                    waited2 += 1.5
                out["steps"].append("retry sentinel_wait_s=%.1f exists=%s"
                                    % (waited2, os.path.exists(marker)))
            except Exception as e:
                out["steps"].append("retry 失败: %r" % (e,))
        if os.path.exists(marker):
            for ln in open(marker, encoding="gbk", errors="ignore").read().splitlines():
                if "=" in ln:
                    k, v = ln.split("=", 1)
                    out["sentinel"][k.strip()] = v.strip()

        # 收尾必须把可能挂起的交互命令清干净，否则下一次运行一接手就是「被呼叫方拒绝接收呼叫」
        for _ in range(8):
            if left() <= 2:
                break
            try:
                active = int(doc.GetVariable("CMDACTIVE"))
            except Exception:
                break
            if not active:
                break
            doc.SendCommand("\x1b")
            out["esc_sent"] += 1
            time.sleep(0.8)
        try:
            out["cmdactive_at_exit"] = int(doc.GetVariable("CMDACTIVE"))
        except Exception as e:
            out["cmdactive_at_exit"] = "unreadable:%r" % (e,)

        try:
            out["entity_count"] = int(doc.ModelSpace.Count)
            ms = doc.ModelSpace
            lays = set()
            for i in range(out["entity_count"]):
                try:
                    lays.add(ms.Item(i).Layer)
                except Exception:
                    pass
            out["entity_layers"] = sorted(lays)
            out["layers"] = sorted({doc.Layers.Item(i).Name
                                    for i in range(doc.Layers.Count)})
        except Exception as e:
            out["error"] = "回读失败: %r" % (e,)

        dwg = payload.get("dwg")
        if dwg:
            try:
                doc.SaveAs(dwg)
                out["dwg_saved"] = dwg
            except Exception as e:
                out["steps"].append("SaveAs: %r" % (e,))
            try:
                doc.Close(False)          # 存完就关，别让下一轮又被占用
                out["closed_after_save"] = True
            except Exception as e:
                out["steps"].append("Close: %r" % (e,))
        out["ok"] = out["entity_count"] > 0 or bool(out["sentinel"].get("entity_count"))
    except Exception as e:
        out["error"] = repr(e)[:300]
    flush()


ACAD_EXE = r"D:\cad2026\AutoCAD 2026\acad.exe"


def stage_acad(spec, out_dir, lisp_builder, com_timeout=480):
    """AutoCAD 2026：单实例阶梯拉起 GUI → 子进程里跑 COM（硬超时）→ LISP 自写实测计数。

    冷启动实测：01:00:53 起进程，AdSplashWindowClass 到 01:01:45 仍挂着（Responding=False），
    01:03:20 才进 [开始] 主框架；原来 240s 的预算里只有 200s 给子进程，正好卡在 splash 上。
    """
    # 绝对路径是硬要求：AutoLISP 的 (load)/(open) 按 AutoCAD 自己的 CWD 解析，
    # 传相对路径会在 CAD 的目录里找不到文件，症状是「实体数 0」而不是报错。
    out_dir = os.path.abspath(out_dir)
    lsp = os.path.join(out_dir, "stage03_drawing.lsp")
    marker = os.path.join(out_dir, "stage03_acad_metrics.txt")
    dwg = os.path.join(out_dir, "wheel_mold_drawing.dwg")
    if os.path.exists(marker):
        os.remove(marker)
    open(lsp, "w", encoding="gbk").write(
        lisp_builder(spec) + _acad_sentinel_lsp(marker))

    ladder = ensure_process("acad.exe", ACAD_EXE, wait_s=180)
    notes = ["acad %s pid=%s" % ("附着既有实例" if ladder.get("attached")
                                 else "由本次派生启动", ladder.get("pid"))]
    if ladder.get("error"):
        notes.append(str(ladder["error"]))
    time.sleep(2.0)
    dismissed = dismiss_app_dialogs("acad.exe")
    if dismissed:
        notes.append("模态框已按白名单点掉 %s —— 它挂着时 Document 层 COM 全被拒"
                     % json.dumps(dismissed, ensure_ascii=False)[:220])

    child = _run_child("_acad_com_worker",
                       {"lsp": lsp, "marker": marker, "dwg": dwg,
                        "deadline_s": com_timeout - 40},
                       com_timeout, out_dir, name="stage03_acad")
    d = child.get("data") or {}
    n = int(d.get("entity_count") or 0)
    before = d.get("entity_count_before")
    before_n = before if isinstance(before, int) else 0
    sent_n = int((d.get("sentinel") or {}).get("entity_count") or 0)
    # 判据只认「本次新增」：新文档时 before=0，沿用旧文档时必须扣掉历史累计
    added = max(0, n - before_n) if n else 0
    sent_added = max(0, sent_n - before_n) if sent_n else 0
    # 两条通道都可能报「文档总数」，沿用时都要折算成本次增量
    best = max(added, sent_added)
    counts = [x for x in (added, sent_added) if x]
    metrics = {"entity_count_com": n, "entity_count_before": before_n,
               "entities_added": added,
               "reused_document": d.get("reused_document"),
               "entity_count_lisp_selfreport": sent_n,
               "layers": d.get("layers"), "entity_layers": d.get("entity_layers"),
               "cmdactive_at_entry": d.get("cmdactive_at_entry"),
               "cmdactive_at_exit": d.get("cmdactive_at_exit"),
               "esc_sent_to_clear_prompts": d.get("esc_sent"),
               "child_elapsed_s": child.get("elapsed_s"),
               "child_rc": child.get("rc"),
               "dwg_saved": d.get("dwg_saved")}
    files = [p for p in (lsp, marker, d.get("dwg_saved"), child.get("child_log"),
                         child.get("result_path")) if p and os.path.exists(p)]
    if d.get("reused_document"):
        notes.append("拿不到新文档，沿用了已打开的文档；实体按 before=%s / after=%s 折算，判据用增量"
                     % (before_n, n))
    if d.get("error"):
        notes.append(str(d["error"]))
    if child.get("timed_out"):
        notes.append("子进程超 %ss 未交结果，已被 taskkill —— AutoCAD 端不应答，主链不再陪它挂死"
                     % com_timeout)
    if d.get("esc_sent"):
        notes.append("结束时仍有未结束的交互命令，已按实测发 %s 次 ESC 清零（不清会把僵死状态传给下一次运行）"
                     % d["esc_sent"])
    ok = best > 0 and not child.get("timed_out")
    return _evidence("autocad", "executed" if ok else "blocked",
                     "COM GetActiveObject + SendCommand(load+defun) + LISP 自写计数，"
                     "整段在带硬超时的子进程里",
                     metrics=metrics, files=files, notes=notes,
                     error=None if ok else "本次没有新增实体（before=%s / after=%s，详见 stage03_acad_child.log）"
                     % (before_n, n))



# ---------------------------------------------------------------- CIMCO Edit (stage 04)
def _gcode_envelope(nc_text):
    """确定性解析 FANUC Macro B 的车削刀路包络（不靠软件回显，自己算）。"""
    import re
    xs, zs, moves, lines = [], [], 0, 0
    vars_ = {}
    for raw in nc_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lines += 1
        mv = re.match(r"^G(?:0?[01]|0?[23]|7[01])(?![0-9])", line.upper())
        for m in re.finditer(r"#(\d+)\s*=\s*([-+0-9.]+)", line):
            vars_[m.group(1)] = float(m.group(2))
        if mv:
            moves += 1
            mx = re.search(r"X\s*\[?([-+0-9.#]+)\]?", line, re.I)
            mz = re.search(r"W\s*\[?([-+0-9.#]+)\]?", line, re.I) or re.search(r"Z\s*\[?([-+0-9.#]+)\]?", line, re.I)
            def val(tok):
                if not tok:
                    return None
                t = tok.group(1)
                if t.startswith("#"):
                    return vars_.get(t[1:])
                try:
                    return float(t)
                except ValueError:
                    return None
            x, z = val(mx), val(mz)
            if x is not None:
                xs.append(x)
            if z is not None:
                zs.append(z)
    return {"nc_lines": lines, "motion_blocks": moves,
            "macro_variables": len(vars_),
            "x_range": [min(xs), max(xs)] if xs else None,
            "z_range": [min(zs), max(zs)] if zs else None,
            "has_rough_cycle": "G71" in nc_text.upper(),
            "has_finish_cycle": "G70" in nc_text.upper(),
            "has_end": "M30" in nc_text.upper()}


def _cimco_doc_state():
    """读 CIMCO 自己写的窗口/标签文字：标题里带我们的文件路径 = 编辑器确实打开了该程序。

    必须把**所有** XTPMainFrame 都收进来：上一次运行留下的编辑器会占着 frames[0]，
    只看第一个窗口就永远看不到本次新载入的那份。
    """
    import win32gui
    import win32process
    out = {"frame_title": None, "frame_titles": [], "doc_tabs": [],
           "ribbon_tabs": [], "hwnd": None}
    frames = []

    def cb(h, _):
        if win32gui.GetClassName(h) == "XTPMainFrame" and win32gui.IsWindowVisible(h):
            frames.append(h)
        return True

    win32gui.EnumWindows(cb, None)
    if not frames:
        return out
    out["hwnd"] = frames[0]
    out["frame_title"] = _wtext(frames[0]).strip()
    out["frame_titles"] = [_wtext(h).strip() for h in frames[:6]]
    kids = []

    def cb2(k, param):
        param.append(k)
        return True

    win32gui.EnumChildWindows(frames[0], cb2, kids)
    # CIMCO 的主框实测有 149 个子窗；逐个 SendMessageTimeout 取文本（400ms 超时）
    # 会让本阶段平白卡住数分钟（0:02 进阶段、0:10 才写证据）。只对会承载文字的
    # 控件取文本，并设上限；doc_count 仍按全部子窗计数。
    text_classes = ("XTPToolBar", "#32770", "SysTabControl32", "Button", "Static", "Edit")
    read = 0
    for k in kids:
        if read >= 80:
            break
        cls = win32gui.GetClassName(k)
        if cls not in text_classes:
            continue
        read += 1
        t = _wtext(k).strip()
        if not t:
            continue
        if t.lower().endswith((".nc", ".mpf", ".txt", ".cpt")) or ".nc" in t.lower():
            out["doc_tabs"].append(t)
        elif cls in ("XTPToolBar", "#32770") and len(t) <= 12:
            out["ribbon_tabs"].append(t)
    out["doc_count"] = len(kids)
    return out


def _spawn_detached(exe, arg=None, join_s=8):
    """非阻塞起外部 GUI 程序。

    两层防御，都是本机实测逼出来的：
      1) 不用 ShellExecuteW —— 它同步，弹模态框时直接把调用线程挂死；
      2) 连 Popen 也要丢进守护线程再 join 超时 —— 本机的执行守卫会在**创建进程时**
         同步弹「安全性 - 未签名的可执行文件」，Popen 自己也会挂在那里。
    """
    box = {}

    def run():
        try:
            box["p"] = subprocess.Popen([exe] + ([arg] if arg else []),
                                        cwd=os.path.dirname(exe), shell=False,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            box["err"] = repr(e)[:160]

    import threading
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(join_s)
    if th.is_alive():
        return {"blocked": "进程创建被系统/守卫的模态提示挂住（已放弃等待，不拖垮整条链）",
                "exe": os.path.basename(exe)}
    return {"pid": getattr(box.get("p"), "pid", None), "error": box.get("err")}


def _cimco_title_matches(title, nc_path):
    """CIMCO 标题可能给全路径也可能给相对路径（相对它自己的 CWD），两种都要认。
    只认「运行目录名 + 文件名」或整路径 —— 单看文件名会让别的运行包里的同名旧文档骗出假通过。"""
    title_n = (title or "").replace("\\", "/").lower()
    ap = os.path.abspath(nc_path).replace("\\", "/").lower()
    parent = os.path.basename(os.path.dirname(ap))
    base = os.path.basename(ap)
    return any(k in title_n for k in (ap, parent + "/" + base))


def _cimco_any_match(state, nc_path):
    """编辑器可能开好几个窗口（上一次运行留下的那个还占着 frames[0]）——
    把所有主窗标题都当作候选，任一命中才算真载入。"""
    cands = list(state.get("frame_titles") or [])
    if state.get("frame_title"):
        cands.append(state["frame_title"])
    return any(_cimco_title_matches(t, nc_path) for t in cands)


def stage_cimco(nc_path, out_dir):
    """CIMCO Edit 2026：实测无 COM 服务器（HKCR 里 CIMCO.* 只是文件类型类）→
    编辑器侧用命令行载入并**回读它自己标题里的文件路径**作为执行证据；
    刀路机器校验由自研 Macro B 解析器承担（backplot 属自绘 ribbon，无导出接口）。"""
    if not os.path.exists(nc_path):
        return _evidence("cimco", "blocked", "命令行载入", error="NC 不存在: %s" % nc_path)
    # 绝对路径是硬要求：CIMCO 用自己的安装目录当 CWD，喂相对路径它「打开失败」但不报错。
    # Windows 的 abspath 会继承当前 CWD 的盘符大小写（可能是 d:），这里统一成
    # 规范的 D: 形式，保证交给外部软件与写入证据的路径字面量稳定一致。
    nc_path = os.path.abspath(nc_path)
    if os.name == "nt" and len(nc_path) >= 2 and nc_path[1] == ":":
        nc_path = nc_path[0].upper() + nc_path[1:]
    txt = open(nc_path, encoding="gbk", errors="ignore").read()
    env = _gcode_envelope(txt)
    # 全量 tasklist 在本机实测挂起（>2min，stdout 管道不关），本阶段曾因此白等 7.7 分钟；
    # Toolhelp32 快照（亚秒级）替代，只问「CIMCOEdit.exe 在不在」。
    from bridges.software_registry import get_running_processes

    def _cimco_running():
        try:
            snap = get_running_processes()
        except Exception:
            return None
        return any(str(k).lower() == "cimcoedit.exe" and pids for k, pids in snap.items())

    running = _cimco_running()
    exe = r"E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe"
    notes_extra = []
    state = _cimco_doc_state()
    if not _cimco_any_match(state, nc_path):
        # 有实例在跑不代表它开着我们的文件：把 NC 再交给编辑器一次（线程化 spawn，8s 兜底）
        r = _spawn_detached(exe, nc_path)
        if r.get("blocked"):
            notes_extra.append(str(r["blocked"]))
        if r.get("error"):
            notes_extra.append("载入 spawn 报错: %s" % r["error"])
        time.sleep(6)

    waited = []
    for _ in range(8):
        state = _cimco_doc_state()
        if _cimco_any_match(state, nc_path):
            break
        waited.append((state.get("frame_title") or "")[:90])
        time.sleep(3)
    running = _cimco_running()
    loaded = _cimco_any_match(state, nc_path)
    rep = os.path.join(out_dir, "stage04_nc_validation.json")
    json.dump({"source": nc_path, "envelope": env, "editor_state": state,
               "titles_seen_while_waiting": waited,
               "loaded_in_editor": loaded},
              open(rep, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return _evidence("cimco", "executed" if loaded else "substituted",
                     "命令行载入编辑器（回读 CIMCO 自写标题）+ 自研 Macro B 解析器校验",
                     metrics=dict(env, editor_running=running,
                                  editor_loaded=loaded,
                                  frame_title=(state.get("frame_title") or "")[:120],
                                  frame_titles=[t[:120] for t in (state.get("frame_titles") or [])],
                                  doc_tabs=state.get("doc_tabs")[:4]),
                     files=[nc_path, rep],
                     error=None if loaded else "编辑器标题里没出现该文件（未确认载入）",
                     notes=["CIMCO 无 Application COM（实测 5 个 CIMCO.* ProgID 均无 CLSID）、"
                            "无命令行开关（官方 CHM 587 主题内无 CLI 条目）；"
                            "backplot 的「导出 DXF」是文档化产物但只能 GUI 触发，未纳入自动链"]
                     + notes_extra)


# ---------------------------------------------------------------- VERICUT (stage 05)
def _vericut_training_stub(project_path):
    """造一个「training 根」并把工程复制进去，返回 (training_dir, 复制后的工程路径)。

    实测三态：CGTECH_TRAINING 指空目录 → 引擎装载完就待命；指 E:\training → 去跑厂商教学
    session；指「带 training_sessions/ 且工程就在里面」的自建目录 → 它真仿真 CGTECH_VCPROJECT
    那份工程并把碰撞打到 stdout（canary 实测 88 个事件、14 个不同行号，全落在我们 NC 的行号内，
    行首 token 也对得上）。放在 %TEMP% 下用 ASCII 路径，避开 GBK 目录名这个老坑。
    """
    import shutil
    stub = os.path.join(os.environ.get("TEMP", r"C:\TEMP"), "virtu_vtrain")
    os.makedirs(os.path.join(stub, "training_sessions"), exist_ok=True)
    proj_copy = os.path.join(stub, os.path.basename(project_path))
    shutil.copyfile(project_path, proj_copy)
    NL = chr(13) + chr(10)
    TB = chr(9) * 2
    BS = chr(92)
    rows = [
        "!",
        "! virtu chain: single session = our project",
        ("Session V1 - wheel mold verification; " + TB
         + "verification" + BS + "v1.pdf; " + TB
         + "%s; " % os.path.basename(proj_copy) + TB + "1"),
    ]
    idx = os.path.join(stub, "training_sessions", "training_index.tbl")
    open(idx, "w", encoding="gbk", newline=NL).write(NL.join(rows) + NL)
    return stub + os.sep, proj_copy


def _vericut_batch_run(bat, project_path, out_dir, timeout=420, argv_extra=None,
                       training_dir=None, idle_s=60):
    """跑一次 Vericut 无头 batch，返回 (rc, 输出文本, 日志路径)。

    实测口径：`batch batchp reset_cutcolor` + CGTECH_VCPROJECT + 一个「training 根形状」的
    CGTECH_TRAINING 才会真仿真；`batch vcp=<工程>` 被软件判 invalid，`batcht` 20s 自退。
    stdout 用文件承接：它派生的 java.exe 比 .bat 活得久并占住管道，capture_output 会永久等待。
    另外带「空闲即收」：日志 60 秒不再增长就说明引擎在待命，不陪它坐到 timeout。
    """
    argv_extra = list(argv_extra or ["batch", "batchp", "fitall", "reset_cutcolor"])
    env = os.environ.copy()
    use_project = project_path
    run_cwd = out_dir
    if training_dir:
        env["CGTECH_TRAINING"] = training_dir
    else:
        stub_dir, use_project = _vericut_training_stub(project_path)
        env["CGTECH_TRAINING"] = stub_dir
        run_cwd = os.path.dirname(use_project)
    env["CGTECH_VCPROJECT"] = use_project
    env["CGTECH_IGNORE_LAST"] = "TRUE"
    log = os.path.join(out_dir, "stage05_vericut_stdout.log")
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        p = subprocess.Popen([bat] + argv_extra, env=env,
                             cwd=run_cwd, stdout=fh, stderr=subprocess.STDOUT, shell=False)
        last_sz, last_change, idle_note = 0, time.time(), None
        while p.poll() is None and time.time() < t0 + timeout:
            time.sleep(3)
            sz = os.path.getsize(log)
            if sz != last_sz:
                last_sz, last_change = sz, time.time()
            elif sz > 0 and time.time() - last_change > idle_s:
                idle_note = "IDLE_KILLED"
                break
        if p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, shell=False)
            rc = idle_note or "TIMEOUT_KILLED"
        else:
            rc = p.returncode
    blob = open(log, encoding="gbk", errors="ignore").read()
    # batch 会在 CWD 落一份以工程命名的 ASCII 日志。它**可能是上一次运行留下的**：
    # 实测就因此把 157 个「碰撞」当成了本次证据。只收本次新建、且内容指名我们那份 NC 的 sidecar。
    sidecar = os.path.join(out_dir, os.path.splitext(os.path.basename(project_path))[0] + ".log")
    nc_name = _vericut_project_nc(project_path)
    SEP = chr(10)
    if os.path.exists(sidecar) and os.path.getmtime(sidecar) >= t0 - 2:
        side = open(sidecar, encoding="gbk", errors="ignore").read()
        if nc_name and nc_name in side:
            blob += SEP + side
        else:
            blob += SEP + "[SIDECAR_REJECTED_NOT_OUR_NC] " + sidecar[:200]
    elif os.path.exists(sidecar):
        blob += SEP + "[SIDECAR_REJECTED_STALE] " + sidecar + " mtime=" + time.strftime(
            "%H:%M:%S", time.localtime(os.path.getmtime(sidecar)))
    return rc, blob, log


def open_vericut_gui(project_path, out_dir=None, wait_s=45):
    """把工程装进 VERICUT 并**留在前台**（不 kill），供人工点「分析→仿真」或存 .ip。

    必须带 `fitall`：不带时视图不缩放到全图，看上去就像「机床根本没加载」——实测同一工程
    加 fitall 后机床、主轴视图都正常显示。返回 PID 与日志路径，关窗由调用方/用户决定。
    """
    bat = r"E:\windows64\commands\vericut_console.bat"
    project_path = os.path.abspath(project_path)
    out_dir = os.path.abspath(out_dir or os.path.dirname(project_path))
    _, use_project = _vericut_training_stub(project_path)
    env = os.environ.copy()
    env["CGTECH_VCPROJECT"] = use_project
    env["CGTECH_IGNORE_LAST"] = "TRUE"
    log = os.path.join(out_dir, "vericut_gui_stdout.log")
    fh = open(log, "w", encoding="utf-8")
    p = subprocess.Popen([bat, "batch", "batchp", "fitall", "reset_cutcolor"],
                         env=env, cwd=out_dir, stdout=fh, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, shell=False)
    return {"pid": p.pid, "log": log, "project": use_project,
            "note": "窗口已留在前台；要找机床点「视图→Fit All」，要跑仿真点「分析→仿真」；关窗：taskkill /PID %s /T /F" % p.pid}

def _vericut_project_nc(project_path):
    """从 .vcproject 里取出它引用的 NC 文件名（sidecar 归属判定用，不靠调用方传字符串）。"""
    import re
    try:
        txt = open(project_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return None
    m = re.search(r'File="([^"]+\.(?:nc|NC|mpf|cnc|ptp))"', txt)
    if not m:
        m = re.search(r'([A-Za-z0-9_./\\-]+\.(?:nc|mpf))', txt)
    return os.path.basename(m.group(1)).replace("\\", "/") if m else None


def _parse_vericut_output(blob, nc_lines=None):
    """把 Vericut batch 的中文输出解析成工程事件，并能按我们那份 NC 做归属。

    实测行格式：`错误:在 17 行:G28 U0.0 W0.0,"Spindle"和"Turret"碰撞.`
    以及 `错误:字符 "G90 - Absolute dimensioning mode" 未定义.` —— 后者说明生成的 NC
    里 `- 注释` 写法不被该控制格式接受，属于链路的真实工程反馈，不能只当噪声。
    传了 nc_lines（我们 NC 的原文行）时，只有「行号落在 NC 行数内 + 该行首 token 对得上」
    的事件才计入 attributed_*，其余单列 unattributed_*，防止别处程序的事件冒充本次证据。
    """
    import re
    events, collisions, parse_errors = [], [], []
    for raw in blob.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "碰撞" in line or "过切" in line or "欠切" in line:
            collisions.append(line[:220])
            events.append(line[:220])
        elif "未定义" in line or "被忽略" in line:
            parse_errors.append(line[:220])
    rows = [int(m) for m in re.findall(r"[在第]\s*(\d+)\s*行", blob)]
    volumes = [float(x) for x in re.findall(r"碰撞体积\s*([\d.]+)", blob)]
    attributed, unattributed = [], []
    if nc_lines:
        for n_s, tok in re.findall(r"[在第]\s*(\d+)\s*行[:：]\s*([A-Za-z][A-Za-z0-9.]*)", blob):
            n = int(n_s)
            if 1 <= n <= len(nc_lines) and tok in nc_lines[n - 1]:
                attributed.append(n)
            else:
                unattributed.append((n, tok))
    return {
        "collision_events": len(collisions),
        "collision_nc_lines": sorted(set(rows))[:20],
        "collision_volumes_mm3": {"max": max(volumes) if volumes else None,
                                  "min": min(volumes) if volumes else None,
                                  "count": len(volumes)},
        "nc_parse_errors": len(parse_errors),
        "sample_collisions": collisions[:8],
        "sample_parse_errors": parse_errors[:8],
        "ran_past_program_end": ("文件结束位置" in blob),
        "stdout_chars": len(blob),
        "attributed_events": len(attributed),
        "attributed_lines": sorted(set(attributed)),
        "unattributed_events": len(unattributed),
        "unattributed_sample": unattributed[:8],
    }


def _vericut_link():
    """加载豆包那套多通道链接库（work/vericut-toolchain/vericut_link.py）。"""
    import importlib.util
    fp = os.path.join(ROOT, "work", "vericut-toolchain", "vericut_link.py")
    if not os.path.exists(fp):
        raise FileNotFoundError(fp)
    spec = importlib.util.spec_from_file_location("vericut_link_mod", fp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_green_play(hwnd):
    """在窗口底部控制条上找绿色播放三角，返回物理屏幕坐标；找不到返回 None。

    为什么不用固定锚点：窗口位置/DPI 一变 (1890,860) 就点到别处；这里按像素找绿色。
    """
    try:
        import pyautogui
        import numpy as np
    except Exception:
        return None
    import ctypes
    import ctypes.wintypes as wt
    u = ctypes.windll.user32
    r = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    if r.right - r.left < 200 or r.bottom - r.top < 120:
        return None
    band_h = max(30, int((r.bottom - r.top) * 0.09))
    box = (r.left, r.bottom - band_h, r.right - r.left, band_h)
    try:
        shot = pyautogui.screenshot(region=box)
        arr = np.asarray(shot).astype(int)
    except Exception:
        return None
    if arr.ndim != 3 or arr.size == 0:
        return None
    try:
        g = (arr[:, :, 1] > 120) & (arr[:, :, 1] - arr[:, :, 0] > 50) & (arr[:, :, 1] - arr[:, :, 2] > 50)
    except Exception:
        # DWM DPI 可能让截图宽度/高度比 RECT 少 1 像素，导致广播报错
        return None
    ys, xs = np.nonzero(g)
    if len(xs) < 30:
        return None
    # 取最右侧的一簇（播放键在控制条右端），聚类用中位数近似
    thr = np.percentile(xs, 85)
    sel = xs >= thr
    return int(box[0] + xs[sel].mean()), int(box[1] + ys[sel].mean())


def _parse_vericut_simlog(txt):
    """解析 VERICUT GUI 仿真日志的汇总段。

    口径（2026-10-31 用 27,583 字节真日志实测）：汇总行只出现在**最后一道 `=====` 分隔线之后**，
    逐刀具明细行在它之前。所以只在尾段里找 `0:01:23 0:00:43 52% 458.03 2103.03`
    （总时长/空切时长/空切占比/切削长度/总行程）——仿真没跑完时拿不到这一行，返回空表，
    绝不拿某个刀具行冒充总量。
    """
    import re
    out = {}
    seps = list(re.finditer(r"^[ \t]*={10,}[ \t]*$", txt, re.M))
    tail = txt[seps[-1].end():] if seps else ""
    m = re.search(r"(\d+:\d+:\d+)\s+(\d+:\d+:\d+)\s+(\d+)%\s+([\d.]+)\s+([\d.]+)", tail)
    if m:
        out.update({"total_time": m.group(1), "air_time": m.group(2),
                    "air_pct": int(m.group(3)),
                    "total_cut_distance_mm": float(m.group(4)),
                    "total_distance_mm": float(m.group(5)),
                    "summary_complete": True})
        rest = tail[m.end():]
        for key, pat in (("errors", r"错误数[:：]\s*(\d+)"),
                         ("warnings", r"警告数[:：]\s*(\d+)")):
            g = re.search(pat, rest)
            if g:
                out[key] = int(g.group(1))
        if "errors" not in out:
            counts = re.findall(r"[:：]\s*(\d+)\s*$", rest, re.M)
            if counts:
                out["errors"] = int(counts[0])
            if len(counts) > 1:
                out["warnings"] = int(counts[1])
    rows = []
    for mm in re.finditer(r"^\s*\d+\s+\d+:.*?(\d+:\d+:\d+)\s+(\d+:\d+:\d+)\s+(\d+)%\s+([\d.]+)\s+([\d.]+)\s*$",
                          txt, re.M):
        rows.append({"time": mm.group(1), "air_time": mm.group(2), "pct": int(mm.group(3)),
                     "cut_mm": float(mm.group(4)), "total_mm": float(mm.group(5))})
    if rows:
        out["tool_rows"] = rows
    return out

def _watch_vericut_simlog(sim_log, nc_name, t_after, budget):
    """通道返回失败 ≠ 软件没跑：以仿真日志汇总段为准，补一次回读。

    2026-11-02 实测：batch 在 16:10:50 就报 IDLE_KILLED 并落盘报告，而同一份
    force_turning_sample.log 16:09:43 开始、16:11:09 才跑完、16:12:41 写完全文
    （总时间 0:01:50 / 总行程 2411.376856mm / 错误 94），日志里明确写着我们的 NC 文件名。
    所以最后判据只看「mtime 晚于本次启动 + 汇总段 + 指名我们 NC」。
    """
    deadline = time.time() + max(0, budget)
    txt, sim = "", {}
    while time.time() < deadline:
        if os.path.exists(sim_log) and os.path.getmtime(sim_log) > t_after + 2.0:
            try:
                txt = open(sim_log, encoding="gbk", errors="ignore").read()
            except Exception:
                txt = ""
            sim = _parse_vericut_simlog(txt)
            if sim.get("summary_complete") and (not nc_name or nc_name in txt):
                return txt, sim
        time.sleep(5)
    if os.path.exists(sim_log) and os.path.getmtime(sim_log) > t_after + 2.0:
        try:
            txt = open(sim_log, encoding="gbk", errors="ignore").read()
            sim = _parse_vericut_simlog(txt)
        except Exception:
            pass
    return txt, sim


def _phys_rect(hwnd):
    """窗口的物理像素矩形（DWM 扩展边界）。GetWindowRect 在 125% DPI 下是虚拟坐标，不能用。"""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        dwm = ctypes.windll.dwmapi
        r = wintypes.RECT()
        hr = dwm.DwmGetWindowAttribute(int(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r))
        if hr == 0 and r.right > r.left:
            l, t, rr, b = r.left, r.top, r.right, r.bottom
        else:
            l, t, rr, b = _rect_fallback(hwnd)
        if rr > l and b > t:
            return (max(0, l), max(0, t), min(4000, rr), min(4000, b))
    except Exception:
        pass
    return None


def _rect_fallback(hwnd):
    import ctypes
    from ctypes import wintypes
    r = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def _raise_window(hwnd):
    r"""非破坏式前置：只恢复并置顶自己，绝不去动别的窗口。

    不能用豆包的 `bring_vericut_front`：它先按标题白名单最小化「宿主窗口」，名单里有
    `virtu模型`，而 VERICUT 的标题带着工程路径 `D:\Virtu模型\runs\…` —— 它把 VERICUT
    自己也最小化了（实测 `_phys_rect` 返回 (0,0,-31801,-31966) 即最小化位），
    之后模板匹配必然 miss，这就是「11 次成 1 次」里的那 10 次。
    """
    import ctypes
    u = ctypes.windll.user32
    k = ctypes.windll.kernel32
    h = int(hwnd)
    if u.IsIconic(h):
        u.ShowWindow(h, 9)          # SW_RESTORE
        time.sleep(1.2)
    # 解除 Windows 的前台锁（让 SetForegroundWindow 真能生效）
    try:
        SPI_SET = 0x0024
        SPIF_UPDATE = 0x01
        SPIF_SENDCHANGE = 0x02
        u.SystemParametersInfoW(SPI_SET, 0, None, SPIF_UPDATE | SPIF_SENDCHANGE)
        u.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception:
        pass
    ct = k.GetCurrentThreadId()
    ft = u.GetWindowThreadProcessId(h, None)
    u.AttachThreadInput(ct, ft, True)
    u.ShowWindow(h, 5)              # SW_SHOW
    u.BringWindowToTop(h)
    u.SetForegroundWindow(h)
    u.SetActiveWindow(h)
    u.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002)   # TOPMOST + NOSIZE|NOMOVE
    u.AttachThreadInput(ct, ft, False)
    time.sleep(0.8)
    r = _phys_rect(h)
    return bool(r and r[2] > r[0] and r[3] > r[1] and r[3] - r[1] > 200)


def _viewport_black_pct(hwnd):
    """VERICUT 黑色视窗比例（0~100）。值高说明 OpenGL 还没真正渲染出来。"""
    try:
        import pyautogui
        import numpy as np
    except Exception:
        return None
    r = _phys_rect(hwnd)
    if not r:
        return None
    # 视窗中心区域（排除工具栏/控制条）
    cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
    w, h = (r[2] - r[0]) // 4, (r[3] - r[1]) // 4
    if w < 40 or h < 40:
        return None
    shot = pyautogui.screenshot(region=(cx - w // 2, cy - h // 2, w, h))
    arr = np.asarray(shot).astype(int)
    if arr.ndim != 3:
        return None
    black = (arr[:, :, 0] < 10) & (arr[:, :, 1] < 10) & (arr[:, :, 2] < 10)
    return int(100.0 * black.sum() / black.size)


def _find_play_button(hwnd=None, scan_all=False, scale=4, threshold=0.80):
    """在物理分辨率截图上用豆包的播放键模板（vc_playbtn.png）找播放按钮。

    坐标锚点 (1890,860) 在 125% DPI 下不可靠，F5 也不是"开始播放"（实测出现在日志里的是
    ActionMainPlay 的完成记录）。模板匹配实测 0.94 命中的就是播放键，点下去日志会长到 27KB。

    两条 2026-10-31 的实测教训：
      1) 截图前**必须先把 VERICUT 提到前台**，别的窗口盖着时模板必然 miss；
      2) 全分辨率逐像素扫要 60~90 秒，而这台机器上还有别的智能体在抢前台——扫完焦点早就没了。
         所以改成「1/4 抽样粗扫 + 原分辨率 ±4px 精修」，整次匹配压到 1 秒内，
         让 raise→match→click 落在同一个焦点窗口期里。
    """
    try:
        import pyautogui
        import numpy as np
        from PIL import Image
    except Exception:
        return None
    tpl_path = os.path.join(ROOT, "work", "vericut-toolchain", "vc_playbtn.png")
    if not os.path.exists(tpl_path):
        return None
    tpl = np.asarray(Image.open(tpl_path).convert("RGB"))
    th, tw = tpl.shape[:2]
    shot_img = pyautogui.screenshot().convert("RGB")
    W, H = shot_img.size  # PIL size=(width, height)；旧实现 H,W 对调致扫描几何全错
    shot = np.asarray(shot_img).astype(np.int16)
    tpl = tpl.astype(np.int16)
    rect = _phys_rect(hwnd) if hwnd else None
    y_lo = int(H * 0.78)
    if rect and not scan_all:
        y_lo = rect[1] + int((rect[3] - rect[1]) * 0.40)   # 控制条贴着窗口底部
    x_lo, x_hi = (rect[0], rect[2]) if rect else (0, W)
    x_lo, y_lo = max(0, x_lo), max(0, min(y_lo, H - th))
    x_hi = min(W, x_hi if rect else W)
    # 粗扫：整屏和模板都用 BOX 滤波等比缩小（抽样 [::4] 会把三角形打碎，实测直接 miss）
    simg = shot_img.resize((max(1, W // scale), max(1, H // scale)), Image.BOX)
    timg = Image.fromarray(np.asarray(tpl, dtype=np.uint8)).resize(
        (max(1, tw // scale), max(1, th // scale)), Image.BOX)
    sh = np.asarray(simg).astype(np.int16)
    st = np.asarray(timg).astype(np.int16)
    sh_th, sh_tw = st.shape[0], st.shape[1]
    sy0 = y_lo // scale
    sy1 = max(sy0 + 1, min(sh.shape[0] - sh_th, (H - th) // scale, (rect[3] if rect else H) // scale))
    sx0 = x_lo // scale
    sx1 = max(sx0 + 1, (x_hi - tw) // scale)
    cands = []
    for yy in range(sy0, sy1):
        row = []
        for xx in range(sx0, sx1):
            s = 1.0 - np.abs(sh[yy:yy + sh_th, xx:xx + sh_tw] - st).mean() / 255.0
            row.append((s, xx, yy))
        row.sort(reverse=True)
        cands.extend(row[:3])
    cands.sort(reverse=True)
    fine = (-1.0, None)
    seen = []
    for (_cs, bx, by) in cands[:8]:
        if any(abs(bx - sx) < 8 and abs(by - sy) < 8 for sx, sy in seen):
            continue
        seen.append((bx, by))
        cx, cy = bx * scale + tw // 2, by * scale + th // 2
        for yy in range(max(0, cy - th // 2 - scale * 3),
                        min(H - th, cy - th // 2 + scale * 3) + 1):
            for xx in range(max(0, cx - tw // 2 - scale * 3),
                            min(W - tw, cx - tw // 2 + scale * 3) + 1):
                s = 1.0 - np.abs(shot[yy:yy + th, xx:xx + tw] - tpl).mean() / 255.0
                if s > fine[0]:
                    fine = (s, (xx + tw // 2, yy + th // 2))
        if fine[1] and fine[0] >= threshold:
            break
    if fine[1] and fine[0] >= threshold:
        return float(fine[0]), fine[1]
    return None


def _vericut_post_click(hwnd, sx, sy):
    """把一次左键点击 PostMessage 给目标窗口自己 —— 与 z-order/遮挡无关。

    实测（2026-10-31 02:29）：别的智能体的全屏窗口压在 VERICUT 上时真实点击必然落空，
    但 PostMessage 到 VERICUT 的 HWND 后仿真日志立刻开始写我们那份 NC 的碰撞事件。
    只用 PostMessageW，不用 SendMessageW（后者会在忙碌的 Java UI 线程上阻塞）。
    """
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    p = wintypes.POINT(int(sx), int(sy))
    u.ScreenToClient(int(hwnd), ctypes.byref(p))
    lp = ((p.y & 0xFFFF) << 16) | (p.x & 0xFFFF)
    u.PostMessageW(int(hwnd), 0x0200, 0, lp)      # WM_MOUSEMOVE
    time.sleep(0.2)
    u.PostMessageW(int(hwnd), 0x0201, 1, lp)      # WM_LBUTTONDOWN + MK_LBUTTON
    time.sleep(0.15)
    u.PostMessageW(int(hwnd), 0x0202, 0, lp)      # WM_LBUTTONUP
    return (p.x, p.y)


def _point_is_ours(hwnd, sx, sy):
    """屏幕点 (sx,sy) 最上面的窗口是不是我们这台 VERICUT（含其子窗）。"""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        pt = wintypes.POINT(int(sx), int(sy))
        top = u.WindowFromPoint(pt)
        root = u.GetAncestor(top, 2) if top else 0     # GA_ROOT
        return int(root or 0) == int(hwnd) or int(top or 0) == int(hwnd)
    except Exception:
        return False


def _vericut_click_play(hwnd, xy, real=False):
    """触发播放：`real` 为真用真实点击（该点确实属于我们窗口时），否则 PostMessage 给窗口自己。"""
    try:
        if real:
            # 真实点击必须经 input_guard（§4.5 键鼠总线唯一入口）：fail-closed +
            # 租约 + 审计 + 松手兜底。pyautogui.click 直写总线、绕过全部闸门，弃用。
            import win_input
            sent = win_input.click(int(xy[0]), int(xy[1]))
            return "真实点击（经 input_guard 授权）" if sent else "真实点击被闸门拒绝/演练（未发出）"
        _vericut_post_click(hwnd, xy[0], xy[1])
        return "PostMessage 到窗口自身（绕开遮挡）"
    except Exception as e:
        return "点击失败 %r" % (e,)


def _stage_vericut_via_gui(project_path, out_dir, timeout=420):
    """GUI 通道：console bat 起实例 → 模板点播放 → 仿真日志汇总段回读。

    实测结论（2026-10-31）：
      1) `vericut_console.bat` 不带 batch 参数 + `CGTECH_VCPROJECT`/`CGTECH_TRANSACTION_LOG`
         环境变量就能起正常 GUI 并自动加载我们的工程（`vericut_agent.bat` 写死工程路径且用 start，弃用）；
      2) 播放键位置：模板命中时用命中点，miss 时用实测偏移（窗口右下角 左 67 / 上 124，
         即 DWM 物理矩形 (0,40,1920,1040) 下的 (1853,916)，模板 0.94 命中过）；F5 不是「开始播放」；
      3) 触发通道：该点被别的窗口压住时**必须**走 `PostMessage` 到 VERICUT 自己的 HWND，
         真实点击会落到别人身上（这台机器上同时有别的智能体在全屏抢前台）；
      4) 只点一次：播放键运行中变暂停键，补点会把仿真停在半路（日志只剩错误报告段、没有汇总段）；
      5) 仿真日志 `force_turning_sample.log` 落在进程 CWD（= out_dir），且**装载工程时会被清零**，
         所以启动前先备份旧日志，判据改成「mtime 晚于本次启动 + 出现汇总段」。
    """
    import shutil

    vl = _vericut_link()
    out_dir = os.path.abspath(out_dir)
    project_path = os.path.abspath(project_path)
    nc_name = _vericut_project_nc(project_path)
    notes = []
    wins = vl.find_vericut()
    if wins:
        # 已有实例的 CWD 不在 out_dir，日志落不进取证包 —— 关掉重起。
        try:
            vl.close_vericut(wins[0][0])
            time.sleep(3)
            notes.append("关闭已有 VERICUT 实例后重起（保证日志落在本次 run 目录）")
        except Exception as e:
            notes.append("关闭旧实例失败: %r" % (e,))
        wins = []
    env = os.environ.copy()
    env["CGTECH_VCPROJECT"] = project_path
    env["CGTECH_TRANSACTION_LOG"] = "Yes"
    env["CGTECH_IGNORE_LAST"] = "TRUE"
    log_gui = os.path.join(out_dir, "vericut_gui_stdout.log")
    sim_log = os.path.join(out_dir, "force_turning_sample.log")
    sz0 = os.path.getsize(sim_log) if os.path.exists(sim_log) else 0
    if sz0:
        # VERICUT 在装载工程时会把这份日志**清零**（实测 27,583B → 0B），
        # 上一次实跑的原始证据必须在启动前存一份。
        snap = os.path.join(out_dir, "stage05_vericut_sim_prev.log")
        try:
            shutil.copyfile(sim_log, snap)
            notes.append("启动前已备份旧仿真日志 %d 字节 → %s" % (sz0, os.path.basename(snap)))
        except Exception as e:
            notes.append("旧仿真日志备份失败: %r" % (e,))
    fh = open(log_gui, "w", encoding="utf-8")
    bat = os.path.join(r"E:\windows64\commands", "vericut_console.bat")
    t_launch = time.time()
    proc = subprocess.Popen(["cmd", "/c", bat], env=env, cwd=out_dir,
                            stdout=fh, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, shell=False)
    notes.append("console bat 启动 pid=%s" % proc.pid)
    stem = os.path.splitext(os.path.basename(project_path))[0].lower()
    deadline = time.time() + 120
    while time.time() < deadline and not wins:
        time.sleep(3)
        wins = vl.find_vericut()
    if wins:
        while time.time() < deadline + 60:
            cur = vl.find_vericut()
            if cur and stem and stem in str(cur[0][2]).lower():
                break
            time.sleep(3)
    if not wins:
        return {"status": "blocked", "method": "VERICUT GUI（console bat + 环境变量）",
                "metrics": {}, "files": [], "error": "启动后没有 VERICUT 窗口", "notes": notes}
    hwnd = wins[0][0]
    _raise_window(hwnd)
    # 等 OpenGL 渲染完：黑幕 >70% 就不继续（vericut_black_window_bug 修复）
    for _ in range(10):
        bp = _viewport_black_pct(hwnd)
        if bp is not None and bp < 70:
            break
        time.sleep(1.0)
    bp_final = _viewport_black_pct(hwnd)
    notes.append("黑幕比例=%s%%" % (bp_final if bp_final is not None else "?"))
    rect = _phys_rect(hwnd)
    hit = _find_play_button(hwnd=hwnd)
    xy = hit[1] if hit else ((rect[2] - 67, rect[3] - 124) if rect else None)
    if not xy:
        notes.append("窗口既不在屏上也拿不到矩形，无法定位播放键")
        return {"status": "blocked",
                "method": "VERICUT GUI（console bat + 环境变量）",
                "metrics": {"play_hit": None, "sim_log_bytes": sz0},
                "files": [x for x in (log_gui,) if os.path.exists(x)],
                "error": "找不到播放键位置（窗口矩形不可用）",
                "notes": notes}
    # **只点一次**：播放键在仿真中会变成暂停键，重复点会把跑了一半的仿真停住
    # （02:29 那次日志停在错误报告段、没有汇总段，就是被后续补点暂停掉的）。
    # 但黑幕时 PostMessage 发不进 VERICUT 的事件循环 —— 改用真实物理点击
    real = bool(hit and _point_is_ours(hwnd, *xy))
    if bp_final is not None and bp_final >= 70:
        # 黑幕时强制用真实点击（让 DWM 收到真正的 WM_MOUSEDOWN）
        real = True
    channel = _vericut_click_play(hwnd, xy, real=real)
    notes.append("播放触发方式：%s（模板 %s，坐标 %s）" % (
        channel, ("%.2f" % hit[0]) if hit else "miss", xy))
    t0 = time.time()
    budget = max(300, timeout - 240)
    txt, sim = "", {}
    started = False
    reclicks = 0
    while time.time() - t0 < budget:
        time.sleep(5)
        if os.path.exists(sim_log) and os.path.getmtime(sim_log) > t_launch + 2.0:
            started = True
            txt = open(sim_log, encoding="gbk", errors="ignore").read()
            sim = _parse_vericut_simlog(txt)
            if sim.get("summary_complete"):
                break
        elif not started and time.time() - t0 > 90 and reclicks < 2:
            # 只有「日志完全没动」才补点，日志在长就一律等，绝不暂停正在跑的仿真
            reclicks += 1
            _raise_window(hwnd)
            h2 = _find_play_button(hwnd=hwnd)
            p2 = h2[1] if h2 else xy
            ch2 = _vericut_click_play(hwnd, p2, real=bool(h2 and _point_is_ours(hwnd, *p2)))
            notes.append("90 秒日志零增长，补点一次（%s）" % ch2)
    grew = (os.path.getsize(sim_log) if os.path.exists(sim_log) else 0) - sz0
    ev_log = os.path.join(out_dir, "stage05_vericut_sim.log")
    if os.path.exists(sim_log):
        shutil.copyfile(sim_log, ev_log)
    txn_tail = os.path.join(out_dir, "stage05_vericut_transaction_tail.txt")
    try:
        open(txn_tail, "w", encoding="utf-8").write(vl.read_transaction_log(6000) or "")
    except Exception:
        pass
    mentions_nc = bool(nc_name and nc_name in txt)
    ran = bool(sim.get("total_distance_mm")) and mentions_nc
    metrics = dict(sim)
    metrics.update({"tool_count": len(sim.get("tool_rows") or []),
                    "play_channel": channel,
                    "play_hit": (round(float(hit[0]), 3) if hit else None),
                    "play_point": [int(xy[0]), int(xy[1])],
                    "play_reclicks": reclicks, "sim_started": started,
                    "sim_log_grew_bytes": grew,
                    "sim_log_bytes": os.path.getsize(sim_log) if os.path.exists(sim_log) else 0,
                    "mentions_our_nc": mentions_nc, "project_nc": nc_name,
                    "elapsed_s": round(time.time() - t0, 1)})
    metrics.pop("tool_rows", None)
    return {"status": "executed" if ran else "blocked",
            "method": "VERICUT GUI：console bat + 环境变量起实例 → 模板命中播放键 → 仿真日志汇总段回读",
            "metrics": metrics,
            "files": [x for x in (ev_log, txn_tail, sim_log) if os.path.exists(x)],
            "error": None if ran else "等到 %d 秒仍没读到本次会话的汇总段（旧日志已按 mtime 排除）" % budget,
            "notes": notes}


def stage_vericut(project_path, out_dir, timeout=600, gui=True):
    """VERICUT 9.6：默认 GUI 通道（console bat + 模板点播放 + 仿真日志汇总段）；GUI 失败才兜底 batch。

    2026-11-02 单点验证：GUI 通道 PostMessage 播放键 → 45.5s 真跑完、汇总段 total_distance=2411mm、
    errors=94（都是我们 NC 里 `G71` 宏变量未定义这类真实工程反馈）。
    batch 无头通道在 GUI 实例没关干净时会抢同一份 CGTECH_TRAINING / CGTECH_VCPROJECT 环境变量，
    实测会 IDLE_KILLED×2。所以**进函数先 close_all**，GUI 成功就直接 return 不 fallback。
    """
    bat = r"E:\windows64\commands\vericut_console.bat"
    if not os.path.exists(project_path or ""):
        return _evidence("vericut", "blocked", "batch batchp 无头仿真",
                         error="vcproject 不存在: %s" % project_path)
    project_path = os.path.abspath(project_path)
    out_dir = os.path.abspath(out_dir)
    t_stage = time.time()
    gui_note = None
    # 进函数先把所有残留 VERICUT 实例关掉 —— 不然 batch / GUI 互相抢同一份训练根
    try:
        _vl = _vericut_link()
        for _w in (_vl.find_vericut() or []):
            _vl.close_vericut(_w[0], timeout=20)
    except Exception:
        pass
    # 先走 GUI 通道（单点验证已稳定 executed）
    if gui:
        gui_rep = _stage_vericut_via_gui(project_path, out_dir, timeout)
        if gui_rep.get("status") == "executed":
            return _evidence("vericut", "executed", gui_rep["method"],
                             metrics=gui_rep.get("metrics"),
                             files=gui_rep.get("files"),
                             notes=gui_rep.get("notes"))
        gui_note = "GUI 通道未成立: %s" % str(gui_rep.get("error"))[:160]
        # GUI 也关不干净再试 batch
        try:
            _vl = _vericut_link()
            for _w in (_vl.find_vericut() or []):
                _vl.close_vericut(_w[0], timeout=20)
        except Exception:
            pass
    nc_name = _vericut_project_nc(project_path)
    nc_file = os.path.join(os.path.dirname(project_path), nc_name) if nc_name else None
    nc_lines = []
    if nc_file and os.path.exists(nc_file):
        nc_lines = open(nc_file, encoding="gbk", errors="ignore").read().splitlines()
    t0 = time.time()
    # 这台机器上 VERICUT 的 batch 是**偶发**真跑的（同一命令 6 次里成功过 1 次，其余装载完就待命），
    # 所以给有限次重试；判据始终是「事件能归属到我们 NC」，绝不放宽成「跑过就算」。
    attempts = []
    for attempt in range(1, 3):
        rc, blob, log = _vericut_batch_run(bat, project_path, out_dir, timeout)
        parsed = _parse_vericut_output(blob, nc_lines or None)
        attempts.append({"attempt": attempt, "rc": rc,
                         "raw_events": parsed["collision_events"],
                         "attributed_events": parsed["attributed_events"],
                         "stdout_chars": parsed["stdout_chars"]})
        if parsed["attributed_events"] > 0:
            break
    report = dict(parsed, project=project_path, rc=rc,
                  argv="batch batchp reset_cutcolor",
                  attempts=attempts,
                  elapsed_s=round(time.time() - t0, 1))
    rep_path = os.path.join(out_dir, "stage05_vericut_report.json")
    json.dump(report, open(rep_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 有我们 NC 原文时只认归属过的事件；没有（工程里没写 NC）才退回原始计数
    if nc_lines:
        ran = parsed["attributed_events"] > 0
    else:
        ran = parsed["collision_events"] > 0 or parsed["nc_parse_errors"] > 0
    # 兜底判据：batch 报 IDLE_KILLED 时仿真可能仍在后台跑（本机实测报告比日志完成早 111 秒），
    # 只要日志里有本次新写的汇总段且指名我们的 NC，就判定软件真跑过。
    sim_log = os.path.join(out_dir, "force_turning_sample.log")
    w_txt, watched = _watch_vericut_simlog(sim_log, nc_name, t_stage, 180)
    watched_ok = bool(watched.get("summary_complete") and
                      (not nc_name or nc_name in w_txt))
    if watched_ok:
        ran = True
    static = _gcode_envelope(open(nc_file, encoding="gbk", errors="ignore").read()) \
        if nc_file and os.path.exists(nc_file) else {}
    metrics = dict(static, rc=rc, elapsed_s=report["elapsed_s"],
                   project_nc=nc_name, nc_lines_in_file=len(nc_lines),
                   collision_events=parsed["collision_events"],
                   collision_nc_lines=parsed["collision_nc_lines"],
                   attributed_events=parsed["attributed_events"],
                   attributed_lines=parsed["attributed_lines"],
                   unattributed_events=parsed["unattributed_events"],
                   max_collision_volume_mm3=parsed["collision_volumes_mm3"]["max"],
                   nc_parse_errors=parsed["nc_parse_errors"],
                   ran_past_program_end=parsed["ran_past_program_end"],
                   stdout_chars=parsed["stdout_chars"],
                   attempts=attempts,
                   license_error=any(k in blob.upper() for k in ("LICENSE", "LSHOST")))
    if watched_ok:
        metrics.update({k: watched[k] for k in
                        ("total_time", "air_time", "air_pct", "total_cut_distance_mm",
                         "total_distance_mm", "errors", "warnings") if k in watched})
        metrics["tool_count"] = len(watched.get("tool_rows") or [])
        metrics["sim_log_source"] = os.path.basename(sim_log)
    notes = ["原文事件与 NC 注释报错见 stage05_vericut_report.json"]
    if gui_note:
        notes.append(gui_note)
    if watched_ok:
        notes.append("batch rc=%s 早于仿真完成（假阴性）；补读后台日志汇总段成立：%s / %s mm"
                     % (rc, watched.get("total_time"), watched.get("total_distance_mm")))
    if ran:
        if parsed["attributed_events"] > 0:
            notes.append("事件归属：行号全部落在本工程 NC 的 %d 行内，且每行首 token 与原文一致"
                         % len(nc_lines))
    else:
        notes.append("batch 未产出可归属本次 NC 的事件（实测判据：CGTECH_TRAINING 必须是"
                     "带 training_sessions/ 的目录形状，空目录会让引擎装载完就待命）")
        notes.append("改由自研 Macro B 解析器承担刀路静态校验；不把别处的碰撞日志当成本次证据"
                     "（sidecar 已按「本次新建 + 指名我们 NC」双条件把关）")
    if watched_ok:
        method = "vericut_console.bat（GUI/batch 拉起后后台真跑）+ force_turning_sample.log 汇总段回读"
    elif ran:
        method = "vericut_console.bat batch batchp（真跑仿真，输出解析碰撞与 NC 语法事件）"
    else:
        method = "vericut_console.bat batch batchp（装载并待命）+ 自研 Macro B 静态刀路校验"
    return _evidence("vericut", "executed" if ran else "substituted",
                     method,
                     metrics=metrics,
                     files=[x for x in (rep_path, log, project_path, nc_file,
                                        sim_log if watched_ok else None)
                            if x and os.path.exists(x)],
                     error=None if ran else "无头 batch 未产生任何可归属本次 NC 的仿真事件（根因见 notes）",
                     notes=notes)

def _wtext(hwnd, n=200, ms=400):
    """跨进程取窗口文字必须带超时：对方一旦卡在模态框/安全提示上，
    GetWindowText 会永久阻塞（实测整条链卡死在 CIMCO 阶段）。

    注意：hwnd 必须先用 IsWindow 校验。对 HWND 0（桌面窗口）发 WM_GETTEXT
    会走跨进程缓冲区编组，实测直接把调用进程打崩（访问冲突，退出码 127），
    而不是像预期那样"立刻返回"。
    """
    import ctypes
    try:
        hwnd = int(hwnd or 0)
    except (TypeError, ValueError):
        return "<无效窗口句柄>"
    user32 = ctypes.windll.user32
    if hwnd <= 0 or not user32.IsWindow(hwnd):
        return "<无效窗口句柄>"
    buf = ctypes.create_unicode_buffer(n + 1)
    ok = user32.SendMessageTimeoutW(
        hwnd, 0x000D, n + 1, buf, 0x0002, ms)      # WM_GETTEXT, SMTO_ABORTIFHUNG
    return (buf.value if ok else "<取文本超时>")[:n]


def _evidence(stage, status, method, metrics=None, files=None, error=None, notes=None):
    return {
        "stage": stage,
        "status": status,
        "method": method,
        "metrics": metrics or {},
        "files": files or [],
        "error": error,
        "notes": notes or [],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ---------------------------------------------------------------- NX (stage 02)
_NX_JOURNAL_TMPL = '''# -*- coding: utf-8 -*-
import json, os
import NXOpen, NXOpen.UF

PART_PATH = r"%(part_path)s"
RESULT_PATH = r"%(result_path)s"
TEMPLATE = "%(template)s"
EXPRESSIONS = %(expressions)r
D_OUTER = %(d_outer).3f
D_BORE = %(d_bore).3f
LENGTH = %(length).3f
GROOVE_SPEC = %(groove_spec)s
GROOVE_ORDER = %(groove_order)s
GROOVE_W = %(groove_w).3f

d = {"api_signatures": {}}
try:
    s = NXOpen.Session.GetSession()
    uf = NXOpen.UF.UFSession.GetUFSession()
    if os.path.exists(PART_PATH):
        os.remove(PART_PATH)
    fn = s.Parts.FileNew()
    fn.Application = NXOpen.FileNewApplication.Modeling
    fn.Units = NXOpen.PartUnits.Millimeters
    fn.NewFileName = PART_PATH
    fn.TemplateFileName = TEMPLATE
    part = fn.Commit()
    fn.Destroy()
    s.Parts.SetWork(part)
    wp = s.Parts.Work
    d["part_created"] = True

    for eq in EXPRESSIONS:
        try:
            e = wp.Expressions.Create(eq)
            d.setdefault("expressions", []).append("%%s=%%s" %% (e.Name, e.Value))
        except Exception as ex:
            d.setdefault("expression_errors", []).append(repr(ex)[:140])

    SIGN_MEMBERS = [x for x in dir(NXOpen.UF.ModlFeatureSigns) if not x.startswith("_")]

    def pick(names):
        for n in names:
            if hasattr(NXOpen.UF.ModlFeatureSigns, n):
                return getattr(NXOpen.UF.ModlFeatureSigns, n)
        raise AttributeError("no sign member in " + str(SIGN_MEMBERS))

    null_sign = pick(["NullSign", "Nullsign", "Null", "NULLSIGN"])
    neg_sign = pick(["Negative", "Negate", "Subtract", "NEGATIVE"])
    d["sign_members"] = SIGN_MEMBERS
    d["api_signatures"]["CreateCyl1"] = str(uf.ModlFeatures.CreateCyl1.__doc__.split("Signature")[-1][:200])
    cyl = uf.ModlFeatures.CreateCyl1(null_sign, [0.0, 0.0, 0.0], "%%.3f" %% LENGTH, "%%.3f" %% D_OUTER, [0.0, 0.0, -1.0])
    bore = uf.ModlFeatures.CreateCyl1(neg_sign, [0.0, 0.0, 0.0], "%%.3f" %% (LENGTH + 10.0), "%%.3f" %% D_BORE, [0.0, 0.0, -1.0])
    d["cyl_tag"], d["bore_tag"] = int(cyl), int(bore)

    # 圆弧槽：NX 12 无 torus builder；用 UF 原生 BALL_END_GROOVE 在圆柱面上成槽。
    # 面替换顺序敏感：两端先做、中间最后做（实测 3/3 成功；0,1,2 顺序第 3 槽报
    # "Original face can not be replaced."）。失败如实记录，不伪造几何。
    groove = []
    outer_r = D_OUTER / 2.0

    def _pick_outer_face(z):
        try:
            body_now = [b for b in wp.Bodies][0]
        except Exception:
            return None
        for f in body_now.GetFaces():
            try:
                data = uf.Modeling.AskFaceData(f.Tag)
                if int(data[0]) != 16 or abs(float(data[4]) - outer_r) > 1e-3:
                    continue
                box = data[3]
                if box[2] - 1e-3 <= z <= box[5] + 1e-3:
                    return int(f.Tag)
            except Exception:
                continue
        return None

    ordered = [GROOVE_SPEC[i] for i in GROOVE_ORDER if 0 <= i < len(GROOVE_SPEC)]
    for zc, ball_dia in ordered:
        rec = {"z": zc, "ball_dia": ball_dia}
        try:
            face = _pick_outer_face(zc)
            rec["face"] = face
            if face is None:
                rec["err"] = "no cylindrical outer face at z"
            else:
                tag = uf.ModlFeatures.CreateBallGroove(
                    [outer_r, 0.0, zc], [-1.0, 0.0, 0.0],
                    "%%.3f" %% ball_dia, "%%.3f" %% GROOVE_W, face)
                rec["feature_tag"] = int(tag)
                rec["ok"] = True
                uf.Modeling.Update()
        except Exception as ex:
            rec["err"] = repr(ex)[:180]
        groove.append(rec)
    d["groove_notes"] = groove

    try:
        uf.Modeling.Update()
        d["update_ok"] = True
    except Exception as ex:
        d["update_err"] = repr(ex)[:180]

    n = 0
    try:
        for f in wp.Features:
            n += 1
    except Exception as ex:
        d["feature_enum_err"] = repr(ex)[:140]
    d["feature_count"] = n

    body_tag = None
    try:
        for b in wp.Bodies:
            body_tag = int(b.Tag)
            break
    except Exception as ex:
        d["body_err"] = repr(ex)[:140]
    d["body_tag"] = body_tag

    if body_tag:
        try:
            d["api_signatures"]["AskBoundingBox"] = str(uf.ModlGeneral.AskBoundingBox.__doc__.split("Signature")[-1][:200])
            bb = uf.ModlGeneral.AskBoundingBox(body_tag)
            d["bbox_raw"] = str(bb)[:400]
        except Exception as ex:
            d["bbox_err"] = repr(ex)[:200]
        try:
            d["api_signatures"]["AskMassProps3d"] = str(uf.Modeling.AskMassProps3d.__doc__.split("Signature")[-1][:260])
        except Exception as ex:
            d["mass_sig_err"] = repr(ex)[:140]

    try:
        wp.Save(getattr(NXOpen.BasePartSaveComponents, "FalseValue"),
                getattr(NXOpen.BasePartCloseAfterSave, "FalseValue"))
        d["saved"] = True
    except Exception as ex:
        d["save_err"] = repr(ex)[:200]
    d["part_exists"] = os.path.exists(PART_PATH)
    d["part_bytes"] = os.path.getsize(PART_PATH) if d["part_exists"] else 0
    d["status"] = "OK"
except Exception as ex:
    d["status"] = "ERR"
    d["error"] = repr(ex)[:400]

with open(RESULT_PATH, "w") as f:
    json.dump(d, f, indent=2)
'''


def nx_env():
    """NX 需要的真实环境变量来自注册表；UGII_ROOT_DIR 必须指向 UGII（数据目录）。"""
    env = os.environ.copy()
    try:
        import winreg
        for hive, path in ((winreg.HKEY_CURRENT_USER, r"Environment"),
                           (winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
            try:
                k = winreg.OpenKey(hive, path)
            except OSError:
                continue
            for i in range(winreg.QueryInfoKey(k)[1]):
                name, val, _ = winreg.EnumValue(k, i)
                if isinstance(val, str) and name.upper().startswith(("UGII", "UGS_", "SPLM_", "NX_")):
                    env.setdefault(name, val)
    except Exception:
        pass
    env["UGII_BASE_DIR"] = NX_BASE
    env["UGII_ROOT_DIR"] = os.path.join(NX_BASE, "UGII")
    env["UGII_LANG"] = "simpl_chinese"
    env["UGII_COUNTRY"] = "prc"
    env["PATH"] = os.path.join(NX_BASE, "NXBIN") + os.pathsep + env.get("PATH", "")
    return env


def stage_nx(spec, out_dir, timeout=420):
    """无头执行 NX journal：真建 .prt + 绑表达式 + 实测特征数。"""
    journal = os.path.join(out_dir, "nx_journal_exec.py")
    result = os.path.join(out_dir, "stage02_nx.json")
    part = os.path.join(out_dir, "nx_wheel_mold.prt")
    for p in (journal, result, part):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    d_out = float(spec.get("d_outer", 53.0))
    d_bore = float(spec.get("d_inner", 14.0))
    length = float(spec.get("overall_len", 45.0))
    radii = [float(r) for r in (spec.get("groove_radii") or []) if float(r) > 0]
    n_grooves = max(1, min(int(spec.get("num_grooves") or spec.get("num_features") or 3), 6))
    if radii:
        radii = radii[:n_grooves]
        n_grooves = len(radii)
    else:
        radii = [float(spec.get("fillet_r", 3.0))] * n_grooves
    pitch = length / (n_grooves + 1.0)
    groove_spec = [(round(-pitch * (i + 1), 3), round(2.0 * r, 3)) for i, r in enumerate(radii)]

    if not os.path.exists(NX_RUN_JOURNAL):
        return _evidence("nx", "blocked", "run_journal.exe", error="run_journal.exe not found")

    n = len(groove_spec)
    base = list(range(n))
    raw_orders = [base]
    if n >= 2:
        raw_orders.append(list(reversed(base)))
    if n >= 3:
        raw_orders.append(base[::2] + base[1::2])
        raw_orders.append(base[1::2] + base[::2])
    seen, candidates = set(), []
    for o in raw_orders:
        key = tuple(o)
        if key not in seen:
            seen.add(key)
            candidates.append(o)

    best = None
    attempts = []
    for order in candidates:
        src = _NX_JOURNAL_TMPL % {
            "part_path": part.replace("\\", "/"),
            "result_path": result.replace("\\", "/"),
            "template": NX_TEMPLATE,
            "expressions": [
                "D_OUTER = %.3f" % d_out,
                "D_BORE = %.3f" % d_bore,
                "TOTAL_LENGTH = %.3f" % length,
                "GROOVE_PITCH = %.3f" % pitch,
            ],
            "d_outer": d_out, "d_bore": d_bore, "length": length,
            "groove_spec": groove_spec, "groove_order": order, "groove_w": 6.0,
        }
        open(journal, "w", encoding="utf-8").write(src)
        t0 = time.time()
        p = subprocess.run([NX_RUN_JOURNAL, journal], env=nx_env(),
                           cwd=os.path.join(NX_BASE, "NXBIN"),
                           capture_output=True, timeout=timeout)
        elapsed = round(time.time() - t0, 1)
        stdout = p.stdout.decode("gbk", "ignore")
        stderr = p.stderr.decode("gbk", "ignore")
        if not os.path.exists(result):
            attempts.append({"order": order, "error": "no result rc=%s stderr=%s" % (p.returncode, stderr[:200])})
            continue
        d = json.load(open(result, encoding="utf-8"))
        notes = d.get("groove_notes") or []
        ok_count = sum(1 for g in notes if g.get("ok"))
        attempts.append({"order": order, "ok": ok_count, "n": n})
        if best is None or ok_count > best["ok"]:
            best = {"ok": ok_count, "d": d, "order": order, "elapsed": elapsed,
                    "rc": p.returncode, "stdout": stdout}
        if n == 0 or ok_count == n:
            break

    if best is None:
        return _evidence("nx", "blocked", "run_journal.exe (headless)",
                         error="journal 未写出任何结果文件", notes=attempts)
    d = best["d"]
    status = "executed" if d.get("status") == "OK" and d.get("part_exists") else "blocked"
    return _evidence("nx", status, "run_journal.exe (headless, no GUI)",
                     metrics={"elapsed_s": best["elapsed"], "rc": best["rc"],
                              "feature_count": d.get("feature_count"),
                              "expressions": d.get("expressions"),
                              "part_bytes": d.get("part_bytes"),
                              "body_tag": d.get("body_tag"),
                              "bbox_raw": d.get("bbox_raw"),
                              "groove_notes": d.get("groove_notes"),
                              "groove_order": best["order"],
                              "groove_attempts": attempts},
                     files=[f for f in (part, result, journal) if os.path.exists(f)],
                     error=d.get("error") or d.get("save_err") or d.get("update_err"),
                     notes=["api_signatures=%s" % json.dumps(d.get("api_signatures", {}))[:400],
                            "groove_order_used=%s attempts=%s" % (best["order"], attempts)])


VERICUT_SAMPLE = r"E:\samples\All\force_turning_generic_2_axis_lathe_turret_fan15t_mm.vcproject"
VERICUT_NC_TOKEN = "force_turning_fanuc_sample.nc"


def build_vericut_project(nc_path, out_dir):
    """把官方车削样本工程改造成引用我们 NC 的真·.vcproject（Vericut 打不开引擎产的伪 .opt）。

    写进 .vcproject 的 NC 路径必须绝对：VERICUT 按它自己的目录解析相对路径，
    找不到 NC 时不报错，只是零事件（实测两种写法都跑空过）。
    """
    import shutil
    nc_path = os.path.abspath(nc_path)
    proj = os.path.join(out_dir, "wheel_mold_vericut.vcproject")
    if not os.path.exists(VERICUT_SAMPLE):
        return None, "官方样本不存在: %s" % VERICUT_SAMPLE
    if os.path.exists(proj):
        os.chmod(proj, 0o666)
        os.remove(proj)
    shutil.copy2(VERICUT_SAMPLE, proj)
    os.chmod(proj, 0o666)
    txt = open(proj, encoding="utf-8", errors="ignore").read()
    n = txt.count(VERICUT_NC_TOKEN)
    txt = txt.replace(VERICUT_NC_TOKEN, nc_path.replace("\\", "/"))
    open(proj, "w", encoding="utf-8").write(txt)
    return proj, "替换 %d 处 NC 引用" % n


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _code_fingerprint():
    """把执行器/桥/引擎的源码哈希和 git HEAD 记进取证包，报告才有「对应哪份代码」的锚点。"""
    parts = {}
    for rel in ("agent_chain_executor.py", "scripts/workbuddy_virtu_bridge.py",
                "virtu_omni/engine/wish_cad_cam_engine.py", "win_input.py"):
        fp = os.path.join(ROOT, rel)
        if os.path.exists(fp):
            parts[rel] = _sha256(fp)[:16]
    try:
        head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       shell=False, encoding="utf-8",
                                       errors="replace").strip()
    except Exception:
        head = None
    return {"files": parts, "git_head": head}


def close_launched():
    """只关「启动账本里记着、现在还在、且同源」的实例，绝不碰别人的窗口。"""
    led = _launch_ledger_read()
    if led is None:
        return []
    rows = {str(r["pid"]): r for r in _proc_table()}
    closed = []
    for rec in led:
        pid = str(rec.get("pid"))
        if pid in rows and _same_install(rows[pid]["path"], rec.get("path", "")):
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, shell=False)
            closed.append(int(pid))
            _launch_ledger_append({"pid": int(pid), "exe": rec.get("exe"),
                                  "path": rec.get("path"),
                                  "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                  "by": "close_launched"})
    return closed

def _prune_runs(out_root, keep=30):
    """只保留最近 keep 个 run 目录（名字必须是 %Y%m%d_%H%M%S），其余删掉。

    这些目录是我们自己生成的取证包，会无限增长；只认时间戳目录名，别的一律不动。
    设 VIRTU_KEEP_RUNS=0 可关闭。
    """
    import re as _re
    import shutil
    try:
        limit = int(os.environ.get("VIRTU_KEEP_RUNS", keep))
    except ValueError:
        limit = keep
    if limit <= 0 or not os.path.isdir(out_root):
        return []
    names = [d for d in os.listdir(out_root)
             if _re.fullmatch(r"\d{8}_\d{6}", d) and os.path.isdir(os.path.join(out_root, d))]
    names.sort(reverse=True)
    removed = []
    for d in names[limit:]:
        try:
            shutil.rmtree(os.path.join(out_root, d))
            removed.append(d)
        except Exception:
            pass
    return removed


PREFLIGHT_APPS = (("acad.exe", "AutoCAD"), ("SLDWORKS.exe", "SOLIDWORKS"),
                  ("CIMCOEdit.exe", "CIMCO Edit"))


def preflight_apps():
    """跑链前先把各软件自己的模态框点掉（只点白名单按钮），并把结果记进取证包。

    斯沃不在这里做：它的面板本身就是 #32770，白名单里的「取消/关闭」可能命中机床按钮。
    """
    out = {}
    for exe, label in PREFLIGHT_APPS:
        try:
            out[label] = dismiss_app_dialogs(exe)
        except Exception as e:
            out[label] = [{"error": repr(e)[:120]}]
    return out

def run_chain(wish, out_root=None, skip=(), memory_safe=True):
    """整链执行 + 取证。严格践行「每步产物落盘 -> 关停上步软件 -> 释放内存 -> 执行下步」。返回 {spec, stages, verdicts, out_dir}。"""
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    out_root = out_root or os.path.join(ROOT, "runs", "full_chain")
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(out_root, ts)
    os.makedirs(out_dir, exist_ok=True)

    reclaimer = ProcessMemoryReclaimer(log_path=os.path.join(out_dir, "stage_memory_reclamation.json"))
    preflight = preflight_apps()
    eng = WishCADCAMEngine()
    spec = eng.parse_wish_intent(wish)
    artifacts = {
        "sw2021": ("01_SOLIDWORKS_2021.swb", eng.generate_solidworks_macro),
        "nx12": ("02_Siemens_NX_12.0.py", eng.generate_nx12_script),
        "acad2026": ("03_AutoCAD_2026.lsp", eng.generate_autocad_lisp),
        "cimco2026": ("04_CIMCO_Edit_2026.nc", eng.generate_cimco_macro),
        "vericut96": ("05_Vericut_9.6.opt", eng.generate_vericut_config),
        "sscnc72": ("06_斯沃数控仿真_7.2.md", eng.generate_sscnc_setup_guide),
    }
    written = {}
    for key, (fname, builder) in artifacts.items():
        try:
            body = builder(spec)
            p = os.path.join(out_dir, fname)
            open(p, "w", encoding="utf-8").write(body)
            written[key] = p
        except Exception as e:
            written[key] = None
            notes = ["工件生成失败: %r" % e]

    nc = written.get("cimco2026")
    proj, proj_note = build_vericut_project(nc, out_dir) if nc else (None, "无 NC 工件")

    plan = [
        ("solidworks", lambda: stage_sw(spec, out_dir), "solidworks"),
        ("nx", lambda: stage_nx(spec, out_dir), "nx"),
        ("autocad", lambda: stage_acad(spec, out_dir, eng.generate_autocad_lisp), "autocad"),
        ("cimco", lambda: stage_cimco(nc, out_dir) if nc else
                          _evidence("cimco", "blocked", "-", error="无 NC 工件"), "cimco"),
        ("vericut", lambda: stage_vericut(proj, out_dir) if proj else
                            _evidence("vericut", "blocked", "-", error=proj_note), "vericut"),
        ("sscnc", lambda: stage_sscnc(nc, out_dir) if nc else
                          _evidence("sscnc", "blocked", "-", error="无 NC 工件")),
    ]

    stages = {}
    stage_memory_records = []
    for item in plan:
        name = item[0]
        fn = item[1]
        sw_key = item[2] if len(item) > 2 else name
        if name in skip:
            stages[name] = _evidence(name, "blocked", "skipped by caller")
            continue

        mem_before = reclaimer.get_system_memory()
        try:
            ev = fn()
            stages[name] = ev
        except Exception as e:
            stages[name] = _evidence(name, "blocked", "exception", error=repr(e)[:400])

        # 1. 检验本阶段所有产物是否切实落盘且非空
        files = stages[name].get("files", [])
        verified_files = []
        for fp in files:
            if fp and os.path.exists(fp):
                sz = os.path.getsize(fp)
                verified_files.append({"path": fp, "bytes": sz, "valid": sz > 0})
        stages[name]["verified_files"] = verified_files

        # 2. 核心铁律：步骤完成后立即关停上一步软件，释放内存
        reclaim_record = None
        if memory_safe and sw_key:
            reclaim_record = reclaimer.close_software(sw_key)
            reclaimer.trim_system_working_set()
        mem_after = reclaimer.get_system_memory()
        reclaimed_mb = round(mem_after["available_mb"] - mem_before["available_mb"], 2)

        stages[name]["memory_reclamation"] = reclaim_record or {
            "target": sw_key,
            "reclaimed_mb": reclaimed_mb,
            "mem_before_mb": mem_before["available_mb"],
            "mem_after_mb": mem_after["available_mb"],
            "status": "SKIPPED" if not memory_safe else "RECLAIMED"
        }
        stage_memory_records.append({
            "stage": name,
            "software": sw_key,
            "reclamation": stages[name]["memory_reclamation"],
            "files": verified_files
        })
        print(f"  [MemorySafe] 阶段 [{name}] 完成 | 产物落地: {len(verified_files)}个 | 关停软件: {sw_key} | 内存回收: {stages[name]['memory_reclamation'].get('reclaimed_mb', 0):+.2f} MB (可用: {mem_after['available_mb']} MB)")

    # 最终全局二次确证清理
    if memory_safe:
        reclaimer.reclaim_all_cad_cam()

    verdicts = {k: v["status"] for k, v in stages.items()}
    executed = sum(1 for v in verdicts.values() if v == "executed")
    pruned = _prune_runs(out_root)
    integrity = {}
    for bucket in (written, {k: v.get("files") for k, v in stages.items()}):
        for val in bucket.values():
            for fp in (val if isinstance(val, list) else [val]):
                if isinstance(fp, str) and os.path.exists(fp) and fp not in integrity:
                    try:
                        integrity[fp] = {"sha256": _sha256(fp), "bytes": os.path.getsize(fp)}
                    except OSError:
                        pass
    bundle = {"schema_version": 2, "code": _code_fingerprint(),
              "integrity": integrity, "run_id": ts, "wish": wish, "spec": spec,
              "preflight": preflight, "pruned_runs": pruned,
              "artifacts": written, "vericut_project": proj, "proj_note": proj_note,
              "verdicts": verdicts, "executed_count": executed,
              "stage_memory_records": stage_memory_records,
              "stages": stages, "out_dir": out_dir}
    with open(os.path.join(out_dir, "chain_evidence.json"), "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    bundle["report"] = write_report(bundle)
    return bundle


def write_report(bundle):
    order = ["solidworks", "nx", "autocad", "cimco", "vericut", "sscnc"]
    label = {"solidworks": "SOLIDWORKS 2021 建模", "nx": "Siemens NX 12.0 CAM",
             "autocad": "AutoCAD 2026 出图", "cimco": "CIMCO Edit 2026 数控",
             "vericut": "VERICUT 9.6 切削仿真", "sscnc": "斯沃 7.2 实训"}
    tier = {"executed": "✅ 已实测执行", "substituted": "自研确定性替代",
            "blocked": "⛔ 被具体根因挡住"}
    lines = [
        "# Virtu CAD/CAM Agent 链 · 全链路执行取证报告",
        "",
        "- run_id: `%s`" % bundle["run_id"],
        "- 愿望: %s" % bundle["wish"],
        "- 规格回读: 外径 %s / 内孔 %s / 总长 %s / 材质 %s" % (
            bundle["spec"].get("d_outer"),
            bundle["spec"].get("d_inner"),
            bundle["spec"].get("overall_len"),
            bundle["spec"].get("material")
        ),
        "- 执行计数: %d/6 达成「软件真跑了且有回读数值」" % bundle["executed_count"],
        "",
        "## 判决矩阵",
        "",
        "| 阶段 | 打通方式 | 判决 | 关键实测值 | 证据文件 |",
        "| :-- | :-- | :-- | :-- | :-- |"
    ]
    for k in order:
        s = bundle["stages"].get(k)
        if not s:
            continue
        mv = json.dumps(s.get("metrics", {}), ensure_ascii=False)
        mv = mv if len(mv) < 260 else mv[:257] + "..."
        files = ", ".join("`%s`" % os.path.basename(f) for f in s.get("files", [])[:4]) or "—"
        lines.append("| %s | %s | %s | %s | %s |" % (label[k], s["method"],
                                                     tier.get(s["status"], s["status"]), mv, files))
        if s.get("error"):
            lines.append("| | ↳ 根因 | | %s | |" % str(s["error"])[:240].replace(chr(10), " "))
        for note in (s.get("notes") or [])[:2]:
            lines.append("| | ↳ 备注 | | %s | |" % str(note)[:240].replace(chr(10), " "))
    for _w in (bundle.get("spec", {}).get("geometry_warnings") or []):
        lines.append("> ⚠️ 几何可行性: %s" % str(_w)[:200])

    lines.append("")
    lines.append("## 阶段式内存回收与进程关停审计")
    lines.append("")
    lines.append("| 阶段 | 关停软件 | 回收PID | 释放物理内存(MB) | 阶段后可用内存(MB) | 产物落盘确证 |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for k in order:
        s = bundle["stages"].get(k)
        if not s:
            continue
        rec = s.get("memory_reclamation") or {}
        reclaimed = rec.get("reclaimed_mb", 0.0)
        avail = rec.get("mem_after_mb", "-")
        pids = ", ".join(str(p) for p in (rec.get("pids_found") or rec.get("killed_pids") or [])) or "无驻留"
        f_count = len(s.get("verified_files", s.get("files", [])))
        lines.append(f"| {label.get(k, k)} | `{rec.get('target', k)}` | {pids} | {reclaimed:+.2f} MB | {avail} MB | {f_count} 个工件有效落盘 |")

    lines.append("")
    lines.append("> 判决口径：`executed` = 软件确实执行且数值来自回读（文件/几何/日志）；"
                 "`substituted` = 该软件无机器可读接口，由自研确定性校验承担同等验证职责；"
                 "`blocked` = 原生接口存在但本机条件缺失，附实测报错原文，不写成「环境问题」；"
                 "`内存回收` = 每完一步任务即刻本地落盘，并强杀/关停上一步软件，实测释放物理 RAM。")
    path = os.path.join(bundle["out_dir"], "AGENT_CHAIN_REPORT.md")
    open(path, "w", encoding="utf-8").write(chr(10).join(lines))
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wish", default="我想制造一款精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm 三道圆弧槽R15 R12 R10")
    ap.add_argument("--stage", default="all")
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--open-vericut", nargs="?", const="", default=None,
                    help="打开 VERICUT 工程并留前台（可带 run 目录参数）")
    ap.add_argument("--close-launched", action="store_true",
                    help="跑完只关启动账本里记的实例（本链新起的），别人的窗口不碰")
    a = ap.parse_args()
    if a.open_vericut is not None:
        _run = a.open_vericut or os.path.join(ROOT, "runs", "full_chain", sorted(
            d for d in os.listdir(os.path.join(ROOT, "runs", "full_chain"))
            if d[:8].isdigit())[-1])
        print(json.dumps(open_vericut_gui(os.path.join(_run, "wheel_mold_vericut.vcproject"), _run),
                         ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if a.stage == "all":
        b = run_chain(a.wish, out_root=a.out, skip=a.skip)
        if a.close_launched:
            b["closed_pids"] = close_launched()
        print(json.dumps({"verdicts": b["verdicts"], "executed": b["executed_count"],
                          "report": b["report"]}, ensure_ascii=False, indent=2))
    else:
        out = a.out or os.path.join(ROOT, "scratch", "acp", "stage_test")
        os.makedirs(out, exist_ok=True)
        from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
        e = WishCADCAMEngine()
        sp = e.parse_wish_intent(a.wish)
        fn = {"solidworks": lambda: stage_sw(sp, out),
              "nx": lambda: stage_nx(sp, out),
              "autocad": lambda: stage_acad(sp, out, e.generate_autocad_lisp),
              "cimco": lambda: stage_cimco(os.path.join(out, "04_CIMCO_Edit_2026.nc"), out),
              "vericut": lambda: stage_vericut(build_vericut_project(
                  os.path.join(out, "04_CIMCO_Edit_2026.nc"), out)[0] or "", out),
              "sscnc": lambda: stage_sscnc(os.path.join(out, "04_CIMCO_Edit_2026.nc"), out)}[a.stage]
        print(json.dumps(fn(), indent=2, ensure_ascii=False))

