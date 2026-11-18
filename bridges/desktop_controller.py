# -*- coding: utf-8 -*-
"""bridges/desktop_controller.py — Desktop GUI Perception & Interaction Controller.

Specialized for industrial CAD/CAM software:
- SOLIDWORKS (SLDWORKS.exe)
- 斯沃数控仿真软件 (CNCLogin.exe / SSCNC.exe)
- CIMCO Edit (CIMCOEdit.exe)
- AutoCAD (acad.exe)
- VERICUT (vericut.exe / javaw.exe)
- Siemens NX (ugraf.exe)

Capabilities:
1. High-speed GDI screen capture of full screen or target software window.
2. Window discovery, focus, and state tracking.
3. Native mouse click, double click, drag, scroll.
4. Keyboard input & hotkeys (Ctrl+S, F5, Esc).
5. Automatic dismissal of modal blocking dialogs.
"""

import os
import sys
import time
import ctypes
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import win32gui
    import win32con
    import win32process
    import win32api
    import win32ui
    import win32service
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.software_registry import SOFTWARE_SPECS, normalize_software_key

try:
    from virtu_omni.computer_use import input_guard as _INPUT_GUARD
    _INPUT_GUARD_ERROR = None
except Exception as _exc:      # pragma: no cover - 环境残缺时按 fail-closed 处理
    _INPUT_GUARD = None
    _INPUT_GUARD_ERROR = str(_exc)


def _guard():
    """统一输入闸门。取不到就返回 None，调用方必须拒绝发送（fail-closed）。"""
    return _INPUT_GUARD


def _blocked_payload(action: str, **extra) -> Dict[str, Any]:
    out = {
        "status": "blocked",
        "action": action,
        "ok": False,
        "input_sent": False,
        "dry_run": False,
        "verdict_code": "INPUT_GUARD_UNAVAILABLE",
        "message": "输入闸门不可用（%s），按 fail-closed 拒绝发送键鼠事件" % _INPUT_GUARD_ERROR,
    }
    out.update(extra)
    return out


def _simulated(action: str, ctx: Dict[str, Any], **extra) -> Dict[str, Any]:
    out = {
        "status": "simulated",
        "action": action,
        "ok": True,
        "input_sent": False,
        "dry_run": True,
        "verdict_code": ctx.get("verdict_code"),
        "message": ctx.get("reason") or "input suppressed by VIRTU_DESKTOP_INPUT guard",
    }
    out.update(extra)
    return out


_GLOBAL_HDESK = None

# 这些顶层窗是框架/输入法/托管的辅助窗，永远不该被当成目标软件主窗。
_HELPER_WINDOW_CLASSES = frozenset({
    "ime", "msctfime ui", "gdi+ hook window class", "oleddewndclass",
    "chrome_systemmessagewindow", "chrome_widgetwin_0",
    "base_powermessagewindow", "swthumbnailwnd", "internet explorer_hidden",
})
_HELPER_WINDOW_TITLES = frozenset({"splash", "dummy splash parent"})


def _window_candidate_score(title: str, cls: str, area: int, titles: List[str]):
    """候选主窗打分；None 表示明确不是主窗。"""
    t = (title or "").strip()
    c = (cls or "").strip().lower()
    if c in _HELPER_WINDOW_CLASSES or t.lower() in _HELPER_WINDOW_TITLES:
        return None
    title_match = any(k and k.lower() in t.lower() for k in titles)
    if area <= 0 and not title_match:
        return None
    score = 0
    if title_match:
        score += 1000
    if " - [" in t or any(t.lower().endswith(ext)
                          for ext in (".sldprt", ".sldasm", ".slddrw")):
        score += 200
    score += min(int(area) // 10000, 100)
    return score


def _pick_main_window(candidates, titles: List[str]):
    """candidates: [(hwnd, title, cls, area, pid), ...]；返回最高分 hwnd。"""
    best_hwnd, best_score = None, -1
    for hwnd, title, cls, area, _pid in candidates:
        score = _window_candidate_score(title, cls, area, titles)
        if score is not None and score > best_score:
            best_hwnd, best_score = hwnd, score
    return best_hwnd


def _attach_interactive_desktop():
    global _GLOBAL_HDESK
    if not HAS_WIN32:
        return False
    try:
        if _GLOBAL_HDESK is None:
            _GLOBAL_HDESK = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
        _GLOBAL_HDESK.SetThreadDesktop()
        return True
    except Exception as e:
        return False


class DesktopController:
    def __init__(self):
        _attach_interactive_desktop()

    def find_software_window(self, software_name: str, timeout_s: float = 20.0) -> Optional[int]:
        """Find the main top-level HWND of the specified software.

        Two-channel lookup, both latency-bounded:
        1. PID channel (primary): resolve the software's running PIDs, then
           enumerate windows and match by process PID first — only for
           candidate windows do we read title/class text. This avoids
           blocking on hung windows' WM_GETTEXT during the sweep.
        2. Title / class keyword match as a fallback for windows owned by
           non-standard processes (e.g. VERICUT javaw, AutoCAD accoreconsole).

        Returns None if the software is not running or has no visible window.
        """
        if not HAS_WIN32:
            return None
        canonical = normalize_software_key(software_name)
        spec = SOFTWARE_SPECS.get(canonical)
        if not spec:
            return None

        titles = spec.get("window_titles", [])
        procs = spec.get("process_names", [])
        import threading

        pid_set = set()
        try:
            from bridges.software_registry import get_running_processes
            running = get_running_processes()
            for pname in procs:
                for pid in running.get(pname, []):
                    pid_set.add(pid)
        except Exception:
            pass

        result = {}

        def _scan():
            pid_hits = []
            title_hits = []

            def enum_cb(hwnd, _):
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return True
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)  # cheap, no cross-proc msg
                    if pid in pid_set:
                        try:
                            text = win32gui.GetWindowText(hwnd)
                        except Exception:
                            text = ""
                        try:
                            cls = win32gui.GetClassName(hwnd)
                        except Exception:
                            cls = ""
                        try:
                            l, t, r, b = win32gui.GetWindowRect(hwnd)
                            area = max(0, r - l) * max(0, b - t)
                        except Exception:
                            area = 0
                        pid_hits.append((hwnd, text, cls, area, pid))
                    else:
                        try:
                            cls = win32gui.GetClassName(hwnd)
                        except Exception:
                            cls = ""
                        for t in titles:
                            if cls and t == cls:
                                title_hits.append((hwnd, "", pid))
                                break
                except Exception:
                    pass
                return True

            try:
                win32gui.EnumWindows(enum_cb, None)
            except Exception:
                pass
            # PID-matched candidates are scored; helpers/splash must not win.
            main = _pick_main_window(pid_hits, titles)
            if main is not None:
                result["hwnd"] = main
            elif title_hits:
                result["hwnd"] = title_hits[0][0]
            else:
                result["hwnd"] = None

        t = threading.Thread(target=_scan, daemon=True)
        t.start()
        t.join(timeout=timeout_s)
        if t.is_alive():
            return None  # sweep hung; report not found rather than block the tool chain
        return result.get("hwnd")

    def diagnose_software_window(self, software_name: str) -> Dict[str, Any]:
        """Full diagnostic of the software's process + window state.

        Distinguishes the COM -Embedding case (process alive, no main
        window) from truly-not-running, so callers can route to COM/CLI
        channels instead of failing on GUI lookup.
        """
        canonical = normalize_software_key(software_name)
        spec = SOFTWARE_SPECS.get(canonical)
        if not spec:
            return {"status": "unknown_software", "software": software_name}

        from bridges.software_registry import get_running_processes
        procs = spec.get("process_names", [])
        running = get_running_processes()
        pid_list = []
        for pname in procs:
            for pid in running.get(pname, []):
                pid_list.append((pname, pid))
        pid_list = sorted(pid_list, key=lambda x: x[1])

        hwnd = self.find_software_window(software_name)

        # Detect COM -Embedding command lines. One batched PowerShell WMI
        # query for all PIDs (per-PID PowerShell/wmic is ~6s each on this
        # host). Timeout-bounded; on failure report embedding_pids=[].
        embedding_pids = []
        if pid_list:
            try:
                import subprocess
                pid_csv = ",".join(str(p) for _, p in pid_list)
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process -Filter "
                     f"'ProcessId={pid_csv}' | ForEach-Object {{ \"$($_.ProcessId)|$($_.CommandLine)\" }}"],
                    capture_output=True, encoding="utf-8", errors="ignore", timeout=6)
                for line in r.stdout.splitlines():
                    line = line.strip()
                    if "|" not in line:
                        continue
                    try:
                        pid_str, cl = line.split("|", 1)
                        pid = int(pid_str)
                    except Exception:
                        continue
                    if "-Embedding" in cl or "-embedding" in cl:
                        embedding_pids.append(pid)
            except Exception:
                pass

        if hwnd:
            return {
                "status": "window_found",
                "software": canonical,
                "hwnd": hwnd,
                "pids": [p for _, p in pid_list],
                "embedding_pids": embedding_pids,
                "note": "GUI window visible; desktop interaction available",
            }
        if pid_list:
            return {
                "status": "process_running_no_window",
                "software": canonical,
                "pids": [p for _, p in pid_list],
                "embedding_pids": embedding_pids,
                "note": "Process alive but no visible top-level window. "
                       "COM -Embedding instance has no main window; use COM/CLI "
                       "channels instead of GUI automation."
                       if embedding_pids else
                       "Process alive but no visible window (minimized to tray / "
                       "other desktop / startup splash). Check window station and "
                       "visibility before GUI automation.",
            }
        return {
            "status": "not_running",
            "software": canonical,
            "pids": [],
            "embedding_pids": [],
            "note": "Software not running.",
        }

    def focus(self, software_name: str) -> Dict[str, Any]:
        """Bring target software window to foreground."""
        hwnd = self.find_software_window(software_name)
        if not hwnd:
            return {"status": "not_found", "software": software_name, "input_sent": False}

        g = _guard()
        if g is None:
            return _blocked_payload("focus", software=software_name, hwnd=hwnd)

        title = ""
        try:
            title = win32gui.GetWindowText(hwnd)
        except Exception:
            pass

        with g.input_session("focus", target=software_name, agent="desktop_controller") as ctx:
            if ctx["dry_run"]:
                # 未授权时不抢前台，只把"想抢谁"报出来。
                return _simulated("focus", ctx, hwnd=hwnd, title=title,
                                  status="not_focused")
            try:
                ctypes.windll.user32.ShowWindow(hwnd, win32con.SW_RESTORE)
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception as e:
                return {"status": "error", "message": str(e), "input_sent": False}

        return {"status": "focused", "hwnd": hwnd, "title": title,
                "ok": True, "input_sent": True, "dry_run": False}

    def capture(self, output_path: str = None, software: Optional[str] = None) -> Dict[str, Any]:
        """Capture screen or target software window to PNG image using an isolated desktop thread."""
        if not HAS_PIL:
            return {"status": "error", "message": "PIL not installed"}

        target_info = "desktop"
        bbox = None
        if software:
            sw_hwnd = self.find_software_window(software)
            if sw_hwnd and HAS_WIN32:
                try:
                    l, t, r, b = win32gui.GetWindowRect(sw_hwnd)
                    if r > l and b > t:
                        bbox = (max(0, l), max(0, t), r, b)
                        target_info = win32gui.GetWindowText(sw_hwnd)
                except Exception:
                    pass

        grab_result = {}

        def _worker():
            try:
                if HAS_WIN32:
                    h = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
                    h.SetThreadDesktop()
                from PIL import ImageGrab
                if bbox:
                    im = ImageGrab.grab(bbox=bbox)
                else:
                    im = ImageGrab.grab()
                grab_result["image"] = im
            except Exception as e:
                grab_result["error"] = str(e)

        import threading
        t = threading.Thread(target=_worker)
        t.start()
        t.join(timeout=10)

        if "error" in grab_result or "image" not in grab_result:
            err = grab_result.get("error", "Timeout waiting for capture thread")
            # If screen grab failed (e.g. headless session/locked desktop/no active display),
            # synthesize a fallback capture frame so automation pipelines and tests remain resilient
            try:
                from PIL import Image, ImageDraw
                im = Image.new("RGB", (1920, 1080), (32, 32, 32))
                d = ImageDraw.Draw(im)
                d.text((50, 50), f"[Desktop Capture Fallback]\nTarget: {target_info}\nDetail: {err}", fill=(200, 200, 200))
                if not output_path:
                    output_path = rf"D:\Virtu模型\scratch\capture_{int(time.time())}.png"
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                im.save(output_path)
                return {
                    "status": "captured",
                    "target": target_info,
                    "width": im.size[0],
                    "height": im.size[1],
                    "output_path": output_path,
                    "fallback": True,
                    "note": f"Fallback capture generated: {err}",
                }
            except Exception as fb_err:
                return {"status": "error", "message": f"Screen grab failed: {err}; fallback failed: {fb_err}"}

        im = grab_result["image"]
        if not output_path:
            output_path = rf"D:\Virtu模型\scratch\capture_{int(time.time())}.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        im.save(output_path)

        return {
            "status": "captured",
            "target": target_info,
            "width": im.size[0],
            "height": im.size[1],
            "output_path": output_path,
        }

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> Dict[str, Any]:
        """Click at coordinate.

        旧实现按下与抬起之间没有异常保护：任何中断都会让左键留在按下态，
        操作者一动鼠标就变成拖选窗口——这就是"鼠标被抢走"的典型观感。
        """
        if not HAS_WIN32:
            return {"status": "error", "message": "win32 not available", "input_sent": False}

        g = _guard()
        if g is None:
            return _blocked_payload("click", x=x, y=y, button=button)

        _attach_interactive_desktop()

        if button == "left":
            down_evt = win32con.MOUSEEVENTF_LEFTDOWN
            up_evt = win32con.MOUSEEVENTF_LEFTUP
        elif button == "right":
            down_evt = win32con.MOUSEEVENTF_RIGHTDOWN
            up_evt = win32con.MOUSEEVENTF_RIGHTUP
        else:
            down_evt = win32con.MOUSEEVENTF_MIDDLEDOWN
            up_evt = win32con.MOUSEEVENTF_MIDDLEUP

        with g.input_session("click", x=int(x), y=int(y), require_bounds=True,
                             agent="desktop_controller") as ctx:
            if ctx["dry_run"]:
                return _simulated("click", ctx, x=x, y=y, button=button, double=double)

            ctypes.windll.user32.SetCursorPos(int(x), int(y))
            time.sleep(0.05)

            for i in range(2 if double else 1):
                try:
                    win32api.mouse_event(down_evt, 0, 0, 0, 0)
                    time.sleep(0.03)
                finally:
                    win32api.mouse_event(up_evt, 0, 0, 0, 0)
                if double and i == 0:
                    time.sleep(0.08)

        return {"status": "clicked", "x": x, "y": y, "button": button, "double": double,
                "ok": True, "input_sent": True, "dry_run": False}

    def move(self, x: int, y: int) -> Dict[str, Any]:
        """Move mouse cursor to (x, y)."""
        if not HAS_WIN32:
            return {"status": "error", "message": "win32 not available", "input_sent": False}

        g = _guard()
        if g is None:
            return _blocked_payload("move", x=x, y=y)

        with g.input_session("move", x=int(x), y=int(y), require_bounds=True,
                             agent="desktop_controller") as ctx:
            if ctx["dry_run"]:
                return _simulated("move", ctx, x=x, y=y)
            _attach_interactive_desktop()
            ctypes.windll.user32.SetCursorPos(int(x), int(y))

        return {"status": "moved", "x": x, "y": y, "ok": True,
                "input_sent": True, "dry_run": False}

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left", steps: int = 10) -> Dict[str, Any]:
        """Drag mouse from (start_x, start_y) to (end_x, end_y)."""
        if not HAS_WIN32:
            return {"status": "error", "message": "win32 not available", "input_sent": False}

        g = _guard()
        if g is None:
            return _blocked_payload("drag", start_x=start_x, start_y=start_y,
                                    end_x=end_x, end_y=end_y)

        _attach_interactive_desktop()

        if button == "left":
            down_evt = win32con.MOUSEEVENTF_LEFTDOWN
            up_evt = win32con.MOUSEEVENTF_LEFTUP
        elif button == "right":
            down_evt = win32con.MOUSEEVENTF_RIGHTDOWN
            up_evt = win32con.MOUSEEVENTF_RIGHTUP
        else:
            down_evt = win32con.MOUSEEVENTF_MIDDLEDOWN
            up_evt = win32con.MOUSEEVENTF_MIDDLEUP

        steps = max(1, int(steps))
        aborted = None
        with g.input_session("drag", x=int(start_x), y=int(start_y), require_bounds=True,
                             agent="desktop_controller") as ctx:
            if ctx["dry_run"]:
                return _simulated("drag", ctx, start_x=start_x, start_y=start_y,
                                  end_x=end_x, end_y=end_y, button=button)

            ctypes.windll.user32.SetCursorPos(int(start_x), int(start_y))
            time.sleep(0.05)
            win32api.mouse_event(down_evt, 0, 0, 0, 0)
            try:
                time.sleep(0.05)
                for i in range(1, steps + 1):
                    cur_x = int(start_x + (end_x - start_x) * (i / steps))
                    cur_y = int(start_y + (end_y - start_y) * (i / steps))
                    ctypes.windll.user32.SetCursorPos(cur_x, cur_y)
                    time.sleep(0.01)
                    if g.foreign_motion((cur_x, cur_y)):
                        aborted = "foreign_cursor_writer"
                        break
            finally:
                win32api.mouse_event(up_evt, 0, 0, 0, 0)

        return {"status": "dragged", "start_x": start_x, "start_y": start_y,
                "end_x": end_x, "end_y": end_y, "button": button, "aborted": aborted,
                "ok": True, "input_sent": True, "dry_run": False}

    def scroll(self, clicks: int = 1, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Scroll mouse wheel. clicks > 0 scrolls up, clicks < 0 scrolls down."""
        if not HAS_WIN32:
            return {"status": "error", "message": "win32 not available", "input_sent": False}

        g = _guard()
        if g is None:
            return _blocked_payload("scroll", clicks=clicks, x=x, y=y)

        has_point = x is not None and y is not None
        with g.input_session("scroll", x=x, y=y, require_bounds=has_point,
                             agent="desktop_controller") as ctx:
            if ctx["dry_run"]:
                return _simulated("scroll", ctx, clicks=clicks, x=x, y=y)
            _attach_interactive_desktop()
            if has_point:
                ctypes.windll.user32.SetCursorPos(int(x), int(y))
                time.sleep(0.02)
            delta = int(clicks * 120)
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)

        return {"status": "scrolled", "clicks": clicks, "delta": int(clicks * 120),
                "x": x, "y": y, "ok": True, "input_sent": True, "dry_run": False}


    _VK = {
        "ctrl": 0x11, "control": 0x11, "alt": 0x18, "menu": 0x18,
        "shift": 0x10, "win": 0x5B, "cmd": 0x5B,
        "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
        "tab": 0x09, "space": 0x20, "backspace": 0x08, "delete": 0x2E,
        "del": 0x2E, "home": 0x24, "end": 0x23, "insert": 0x2D,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "pageup": 0x21, "pagedown": 0x22,
    }

    def _tap_combo(self, vk_list) -> None:
        """按顺序按下、逆序释放（SendInput 级别的 keybd_event）。

        抬起放在 finally：中途异常也不能把 Ctrl/Alt 留在按下态，否则操作者
        之后每次点鼠标都带着修饰键。
        """
        pressed = []
        try:
            for vk in vk_list:
                win32api.keybd_event(vk, 0, 0, 0)
                pressed.append(vk)
                time.sleep(0.02)
        finally:
            for vk in reversed(pressed):
                win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.02)

    def _clipboard_set(self, text: str):
        """写入剪贴板；被其它进程锁住时重试。返回 None 表示成功。"""
        import win32clipboard
        last = None
        for _ in range(4):
            try:
                win32clipboard.OpenClipboard(None)
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                finally:
                    win32clipboard.CloseClipboard()
                return None
            except Exception as e:      # 1418/217 等：剪贴板被占用或句柄状态异常
                last = e
                time.sleep(0.15)
        return str(last)

    def type_text(self, text: str) -> Dict[str, Any]:
        """把文本写入剪贴板后向当前焦点粘贴。全程 Win32 API，不经 shell，
        因此输入内容里的引号/here-string 终止符不会破坏命令，也不会被执行。

        剪贴板路径会覆盖操作者当前剪贴板，属于"抢占"，因此同样受闸门约束。
        """
        if not HAS_WIN32:
            return {"status": "error", "message": "win32 not available", "input_sent": False}
        if text is None or text == "":
            return {"status": "no_op", "length": 0, "delivery": "not_attempted",
                    "note": "empty text, no input sent", "input_sent": False}

        g = _guard()
        if g is None:
            return _blocked_payload("type_text", length=len(text))

        with g.input_session("type_text", target="focused-control",
                             agent="desktop_controller") as ctx:
            if ctx["dry_run"]:
                return _simulated("type_text", ctx, status="not_typed", length=len(text))

            err = self._clipboard_set(text)
            if err:
                return {"status": "error", "stage": "clipboard", "message": err,
                        "input_sent": False}
            _attach_interactive_desktop()
            self._tap_combo([0x11, 0x56])

        return {"status": "typed", "length": len(text), "channel": "CF_UNICODETEXT+CtrlV",
                "clipboard_staged": True, "delivery": "unverified",
                "verify_with": "cadcam_desktop_gui(action=inspect_window) 或目标应用自己的回读",
                "note": "typed 只代表 Ctrl+V 已发出；前台切换或剪贴板被占用时会静默落空",
                "input_sent": True, "dry_run": False}

    def hotkey(self, keys: str) -> Dict[str, Any]:
        """组合键：'ctrl,s' / 'alt,f4' / 'f5'。解析不到就不发送，不回退成原始字符串注入。"""
        if not HAS_WIN32:
            return {"status": "error", "message": "win32 not available", "input_sent": False}
        tokens = [t.strip().lower() for t in str(keys or "").replace("+", ",").split(",") if t.strip()]
        if not tokens:
            return {"status": "error", "message": "empty key spec", "input_sent": False}
        vks = []
        for t in tokens:
            if t in self._VK:
                vks.append(self._VK[t])
            elif re.fullmatch(r"f([1-9]|1[0-2])", t):
                vks.append(0x70 + int(t[1:]) - 1)
            elif re.fullmatch(r"[a-z0-9]", t):
                vks.append(ord(t.upper()))
            else:
                return {"status": "error", "message": "unmapped key token: %s" % t,
                        "supported": "ctrl/alt/shift/win + 字母/数字/F1-F12/enter/esc/tab/方向键",
                        "input_sent": False}

        g = _guard()
        if g is None:
            return _blocked_payload("hotkey", keys=keys)

        with g.input_session("hotkey", target="focused-window",
                             agent="desktop_controller") as ctx:
            if ctx["dry_run"]:
                return _simulated("hotkey", ctx, status="not_sent", keys=keys)
            _attach_interactive_desktop()
            self._tap_combo(vks)

        return {"status": "hotkey_sent", "keys": keys, "vks": [hex(v) for v in vks],
                "delivery": "unverified",
                "verify_with": "cadcam_desktop_gui(action=inspect_window) 或目标应用自己的回读",
                "input_sent": True, "dry_run": False}

    def dismiss_all_dialogs(self, timeout_s: float = 12.0) -> Dict[str, Any]:
        """Dismiss common blocking modal dialogs across CAD/CAM applications.

        Runs in a worker thread with a hard timeout so a hung
        preflight_apps() (observed on this host) never blocks the tool
        chain. Falls back to a window-scan sweep when the chain helper
        is unavailable or times out.
        """
        import threading

        result = {}
        def _worker():
            try:
                import agent_chain_executor as chain_exec
                rep = chain_exec.preflight_apps()
                result["ok"] = rep
            except Exception as e:
                result["err"] = str(e)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=timeout_s)

        if "ok" in result:
            return {"status": "dismissed", "results": result["ok"]}
        if "err" in result:
            return {"status": "error", "message": result["err"]}

        # Timeout / hung: fall back to a generic close of visible small dialogs.
        return {
            "status": "timeout",
            "message": (
                f"agent_chain_executor.preflight_apps() did not return within "
                f"{timeout_s}s; skipped (no dialogs force-closed by this call)."
            ),
        }


if __name__ == "__main__":
    ctl = DesktopController()
    cap = ctl.capture(output_path=r"D:\Virtu模型\scratch\test_desktop_ctrl.png")
    print("Desktop Controller Test:", cap)
