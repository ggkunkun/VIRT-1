"""
desktop_util.py - Common desktop attachment and DPI utilities for Windows.
Adapted for User Screen: 1920x1080 @ 125% DPI Scale, Work Area: 1920x1020.
"""

import sys
import ctypes
from ctypes import wintypes

_cached_hdesk = None
_cached_profile = None

def enable_dpi_awareness():
    """Enable Per-Monitor DPI Awareness so coordinates match physical screen pixels (1920x1080)."""
    if sys.platform != 'win32':
        return False
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        res = ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        if res:
            return True
    except Exception:
        pass

    try:
        if hasattr(ctypes.windll, "shcore") and hasattr(ctypes.windll.shcore, "SetProcessDpiAwareness"):
            # 2 = PROCESS_PER_MONITOR_DPI_AWARE
            if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
                return True
    except Exception:
        pass

    try:
        return bool(ctypes.windll.user32.SetProcessDPIAware())
    except Exception:
        return False

def attach_default_desktop():
    """
    Ensures the calling thread is attached to the interactive 'default' desktop on Windows.
    Sets DPI awareness so coordinates match physical screen pixels.
    """
    global _cached_hdesk
    if sys.platform != 'win32':
        return None

    try:
        enable_dpi_awareness()

        user32 = ctypes.windll.user32
        user32.OpenDesktopW.restype = wintypes.HANDLE
        user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]

        # DESKTOP_ALL_ACCESS = 0x01FF
        DESKTOP_ALL_ACCESS = 0x01FF
        hdesk = user32.OpenDesktopW('default', 0, False, DESKTOP_ALL_ACCESS)
        if hdesk:
            ok = user32.SetThreadDesktop(hdesk)
            if ok:
                _cached_hdesk = hdesk
                return hdesk
    except Exception as e:
        sys.stderr.write(f"[desktop_util] Warning: attach_default_desktop failed: {e}\n")
    return None

def get_screen_profile():
    """Retrieve full hardware adaptation profile for the user's primary monitor."""
    global _cached_profile
    if _cached_profile:
        return _cached_profile

    enable_dpi_awareness()
    user32 = ctypes.windll.user32

    phys_w = user32.GetSystemMetrics(0) or 1920
    phys_h = user32.GetSystemMetrics(1) or 1080

    class RECT(ctypes.Structure):
        _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG), ('right', wintypes.LONG), ('bottom', wintypes.LONG)]

    work_rect = RECT()
    # SPI_GETWORKAREA = 0x0030
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_rect), 0)
    work_w = work_rect.right - work_rect.left
    work_h = work_rect.bottom - work_rect.top
    if work_w <= 0 or work_h <= 0:
        work_rect.left, work_rect.top, work_rect.right, work_rect.bottom = 0, 0, phys_w, 1020
        work_w, work_h = phys_w, 1020

    dpi_x, dpi_y = 120, 120
    scale_factor = 1.25
    shcore = getattr(ctypes.windll, 'shcore', None)
    if shcore and hasattr(shcore, 'GetDpiForMonitor'):
        h_monitor = user32.MonitorFromPoint(wintypes.POINT(0, 0), 1)
        cx, cy = ctypes.c_uint(), ctypes.c_uint()
        res = shcore.GetDpiForMonitor(h_monitor, 0, ctypes.byref(cx), ctypes.byref(cy))
        if res == 0 and cx.value > 0:
            dpi_x, dpi_y = cx.value, cy.value
            scale_factor = round(dpi_x / 96.0, 2)

    profile = {
        "physical_width": phys_w,
        "physical_height": phys_h,
        "work_area_width": work_w,
        "work_area_height": work_h,
        "taskbar_height": max(0, phys_h - work_h),
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "scale_factor": scale_factor,
        "scale_percent": f"{int(scale_factor * 100)}%",
    }
    _cached_profile = profile
    return profile

