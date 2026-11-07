"""Virtu Computer Use: Action Execution Engine.

Simulates mouse clicks, cursor movement, smooth drags, scrolling, keyboard input,
hotkeys (Ctrl+S, Alt+F4, Win+R), and window activation via Windows Win32 API.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import time
from typing import Any, Dict, List, Optional, Union

from virtu_omni.computer_use.perception import enable_dpi_awareness

logger = logging.getLogger("virtu_omni.computer_use.action")

# Ensure process is DPI-aware so SetCursorPos & mouse_event map to physical pixels
enable_dpi_awareness()

user32 = ctypes.windll.user32

# Mouse flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

# Virtual-Key codes
VK_MAP = {
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "menu": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "win": 0x5B,
    "windows": 0x5B,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "backspace": 0x08,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}


class ActionEngine:
    """Dispatches mouse, keyboard, and window state actions on Windows desktop."""

    def __init__(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
        work_height: int = 1020,
        dpi_scale: float = 1.25,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.work_height = work_height
        self.dpi_scale = dpi_scale
        self._refresh_screen_bounds()

    def _refresh_screen_bounds(self) -> None:
        """Dynamically detect current screen resolution and work area bounds."""
        try:
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            if w > 0 and h > 0:
                self.screen_width = w
                self.screen_height = h

            rect = wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030
            if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                self.work_height = rect.bottom - rect.top
        except Exception:
            pass

    def adapt_coordinates(
        self,
        x: Union[int, float],
        y: Union[int, float],
        normalized: bool = False,
        is_logical: bool = False,
        inside_work_area: bool = False,
    ) -> Tuple[int, int]:
        """Convert logical, normalized, or unscaled inputs into physical desktop pixels."""
        if normalized:
            # Check 0~1 vs 0~1000 scale
            is_1000 = (float(x) > 1.0 or float(y) > 1.0)
            fx = float(x) / 1000.0 if is_1000 else float(x)
            fy = float(y) / 1000.0 if is_1000 else float(y)
            target_h = self.work_height if inside_work_area else self.screen_height
            px = int(round(fx * self.screen_width))
            py = int(round(fy * target_h))
        elif is_logical:
            # Scale from DPI-unaware logical resolution (e.g. 1536x864) to physical (1920x1080)
            px = int(round(float(x) * self.dpi_scale))
            py = int(round(float(y) * self.dpi_scale))
        else:
            px = int(x)
            py = int(y)

        # Clamp within screen bounds
        max_y = (self.work_height - 1) if inside_work_area else (self.screen_height - 1)
        clamped_x = max(0, min(self.screen_width - 1, px))
        clamped_y = max(0, min(max_y, py))
        return clamped_x, clamped_y

    def mouse_move(
        self,
        x: Union[int, float],
        y: Union[int, float],
        normalized: bool = False,
        is_logical: bool = False,
    ) -> Dict[str, Any]:
        """Move mouse cursor to adapted coordinates (x, y)."""
        px, py = self.adapt_coordinates(x, y, normalized=normalized, is_logical=is_logical)
        user32.SetCursorPos(px, py)
        return {"action": "mouse_move", "x": px, "y": py, "raw_x": x, "raw_y": y, "ok": True}

    def click(
        self,
        x: Union[int, float],
        y: Union[int, float],
        button: str = "left",
        double: bool = False,
        hwnd: Optional[int] = None,
        normalized: bool = False,
        is_logical: bool = False,
        allow_taskbar: bool = True,
    ) -> Dict[str, Any]:
        """Perform mouse click (left, right, middle) at adapted coordinates (x, y)."""
        if hwnd:
            self.activate_window(hwnd)

        px, py = self.adapt_coordinates(x, y, normalized=normalized, is_logical=is_logical)
        is_taskbar = (py >= self.work_height)

        if is_taskbar and not allow_taskbar:
            logger.warning(f"Prevented accidental click on Windows Taskbar at ({px}, {py})")
            return {
                "action": "click",
                "x": px,
                "y": py,
                "ok": False,
                "error": "Click prevented: coordinate lands inside protected Windows taskbar area",
            }

        self.mouse_move(px, py)
        time.sleep(0.02)

        btn_lower = button.lower()
        if btn_lower == "right":
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif btn_lower == "middle":
            down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        else:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

        clicks = 2 if double else 1
        for _ in range(clicks):
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.01)
            user32.mouse_event(up_flag, 0, 0, 0, 0)
            if double:
                time.sleep(0.05)

        return {
            "action": "click",
            "x": px,
            "y": py,
            "button": button,
            "double": double,
            "target_region": "taskbar" if is_taskbar else "work_area",
            "ok": True,
        }

    def drag(
        self,
        start_x: Union[int, float],
        start_y: Union[int, float],
        end_x: Union[int, float],
        end_y: Union[int, float],
        steps: int = 10,
        button: str = "left",
        normalized: bool = False,
        is_logical: bool = False,
    ) -> Dict[str, Any]:
        """Click and drag from (start_x, start_y) to (end_x, end_y)."""
        sx, sy = self.adapt_coordinates(start_x, start_y, normalized=normalized, is_logical=is_logical)
        ex, ey = self.adapt_coordinates(end_x, end_y, normalized=normalized, is_logical=is_logical)

        self.mouse_move(sx, sy)
        time.sleep(0.02)

        down_flag = MOUSEEVENTF_RIGHTDOWN if button.lower() == "right" else MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP if button.lower() == "right" else MOUSEEVENTF_LEFTUP

        user32.mouse_event(down_flag, 0, 0, 0, 0)
        time.sleep(0.02)

        for i in range(1, steps + 1):
            curr_x = int(sx + (ex - sx) * (i / steps))
            curr_y = int(sy + (ey - sy) * (i / steps))
            user32.SetCursorPos(curr_x, curr_y)
            time.sleep(0.01)

        user32.mouse_event(up_flag, 0, 0, 0, 0)
        return {
            "action": "drag",
            "start_x": sx,
            "start_y": sy,
            "end_x": ex,
            "end_y": ey,
            "steps": steps,
            "ok": True,
        }

        user32.mouse_event(up_flag, 0, 0, 0, 0)
        return {
            "action": "drag",
            "start": (start_x, start_y),
            "end": (end_x, end_y),
            "ok": True,
        }

    def scroll(
        self,
        clicks: int,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Scroll mouse wheel vertically. Positive = up, negative = down."""
        if x is not None and y is not None:
            self.mouse_move(x, y)

        # WHEEL_DELTA is 120
        delta = clicks * 120
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        return {"action": "scroll", "clicks": clicks, "delta": delta, "ok": True}

    def type_text(self, text: str, delay_ms: int = 5) -> Dict[str, Any]:
        """Type characters sequentially into the currently active control."""
        for char in text:
            # Send character via SendInput or keybd_event with scan code
            vk = user32.VkKeyScanW(ord(char))
            key_code = vk & 0xFF
            shift = bool((vk >> 8) & 1)

            if shift:
                user32.keybd_event(VK_MAP["shift"], 0, 0, 0)

            user32.keybd_event(key_code, 0, 0, 0)
            user32.keybd_event(key_code, 0, 2, 0)  # KEYEVENTF_KEYUP = 2

            if shift:
                user32.keybd_event(VK_MAP["shift"], 0, 2, 0)

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

        return {"action": "type_text", "length": len(text), "ok": True}

    def hotkey(self, keys: List[str]) -> Dict[str, Any]:
        """Trigger keyboard key combination (e.g. ['ctrl', 's'], ['alt', 'tab'])."""
        vk_codes: List[int] = []
        for k in keys:
            k_lower = k.lower().strip()
            if k_lower in VK_MAP:
                vk_codes.append(VK_MAP[k_lower])
            elif len(k_lower) == 1:
                vk_codes.append(ord(k_lower.upper()))
            else:
                logger.warning(f"Unknown key: {k}")

        # Press down in order
        for vk in vk_codes:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)

        # Release in reverse order
        for vk in reversed(vk_codes):
            user32.keybd_event(vk, 0, 2, 0)
            time.sleep(0.01)

        return {"action": "hotkey", "keys": keys, "ok": True}

    def activate_window(self, hwnd_or_title: Union[int, str]) -> Dict[str, Any]:
        """Bring target window to foreground and set focus."""
        hwnd = 0
        if isinstance(hwnd_or_title, int):
            hwnd = hwnd_or_title
        else:
            # Find window by title
            title_q = hwnd_or_title.lower()
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def enum_cb(h, lparam):
                nonlocal hwnd
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buff, length + 1)
                    if title_q in buff.value.lower():
                        hwnd = h
                        return False
                return True

            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        if not hwnd or not user32.IsWindow(hwnd):
            return {"ok": False, "error": f"Window '{hwnd_or_title}' not found"}

        # SW_RESTORE = 9, SW_SHOW = 5
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return {"ok": True, "action": "activate_window", "hwnd": hwnd}
