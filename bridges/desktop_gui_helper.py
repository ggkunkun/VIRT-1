"""Desktop GUI Perception and Interaction Helper for Windows.
Operates on the user interactive desktop ('default') from any thread/session.
"""

import sys
import time
import ctypes
import threading
from pathlib import Path
from PIL import Image

try:
    import win32service
    import win32gui
    import win32con
    import win32process
    import win32api
    import win32ui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def switch_to_interactive_desktop():
    """Ensure calling thread is attached to user's interactive 'default' desktop."""
    if not HAS_WIN32:
        return False
    try:
        hdesk = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()
        return True
    except Exception as e:
        return False


def get_solidworks_hwnd():
    """Find the top-level SOLIDWORKS window HWND."""
    hwnds = []
    def enum_cb(h, _):
        if win32gui.IsWindowVisible(h):
            title = win32gui.GetWindowText(h)
            if "SOLIDWORKS" in title:
                hwnds.append(h)
    win32gui.EnumWindows(enum_cb, None)
    return hwnds[0] if hwnds else None


def activate_window(hwnd):
    """Force window to foreground and restore/maximize."""
    if not hwnd:
        return False
    try:
        ctypes.windll.user32.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def capture_desktop(output_path: str = None) -> Image.Image:
    """Capture full desktop on interactive display."""
    switch_to_interactive_desktop()
    hwnd = win32gui.GetDesktopWindow()
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = r - l, b - t

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    im = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), bmpstr, "raw", "BGRX", 0, 1)

    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        im.save(output_path)
    return im


def mouse_click(x: int, y: int, button: str = "left", double: bool = False):
    """Click at screen coordinate."""
    switch_to_interactive_desktop()
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.05)
    
    if button == "left":
        down_evt = win32con.MOUSEEVENTF_LEFTDOWN
        up_evt = win32con.MOUSEEVENTF_LEFTUP
    elif button == "right":
        down_evt = win32con.MOUSEEVENTF_RIGHTDOWN
        up_evt = win32con.MOUSEEVENTF_RIGHTUP
    else:
        down_evt = win32con.MOUSEEVENTF_MIDDLEDOWN
        up_evt = win32con.MOUSEEVENTF_MIDDLEUP

    win32api.mouse_event(down_evt, x, y, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(up_evt, x, y, 0, 0)
    
    if double:
        time.sleep(0.1)
        win32api.mouse_event(down_evt, x, y, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(up_evt, x, y, 0, 0)


def send_keys_combination(*vk_keys):
    """Send key combination like (VK_CONTROL, ord('N'))."""
    switch_to_interactive_desktop()
    for k in vk_keys:
        win32api.keybd_event(k, 0, 0, 0)
    time.sleep(0.05)
    for k in reversed(vk_keys):
        win32api.keybd_event(k, 0, win32con.KEYEVENTF_KEYUP, 0)
