#!/usr/bin/env python3
"""
humanoid_controller.py - Ultra-fast, high-precision, human-like desktop automation engine.
Grounded in SOTA GitHub projects:
  - bytedance/UI-TARS: Multimodal GUI Agent perception & action protocol
  - microsoft/UFO: Windows UIAutomation (UIA) deterministic tree grounding
  - patrikoss/pyclick & windmouse: Physics-based WindMouse & Minimum Jerk Bezier kinematics
  - mss: Sub-5ms DXGI/GDI screen capture
  - Direct Win32 SendInput (ctypes): Sub-0.1ms hardware event dispatch
"""

import os
import sys
import time
import math
import random
import ctypes
from ctypes import wintypes
from typing import Tuple, List, Optional, Union, Dict, Any

# Ensure desktop attachment & DPI awareness
def attach_interactive_desktop():
    """Ensure calling thread is attached to interactive desktop with Per-Monitor DPI awareness."""
    if sys.platform != 'win32':
        return None
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        user32 = ctypes.windll.user32
        user32.OpenInputDesktop.restype = wintypes.HANDLE
        user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]

        # DESKTOP_ALL_ACCESS = 0x01FF
        hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            return hdesk
    except Exception:
        pass
    return None

attach_interactive_desktop()

# Win32 SendInput Structures
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ---------------------------------------------------------------------------
# 输入闸门（fail-closed）
# ---------------------------------------------------------------------------
# 本模块是全仓最容易"抢鼠标"的一条通道：默认 human 模式，一次移动会以 120Hz
# 连发几十个绝对坐标事件。两个 agent 同时进来，光标就在两条轨迹之间来回抽动。
# 因此这里必须经过统一仲裁器：默认拒绝、并发排队、执行中有人介入就让位。
_GUARD = None
_GUARD_ERROR = None


def _guard():
    """懒加载 input_guard；加载失败时返回 None，调用方必须按 fail-closed 处理。"""
    global _GUARD, _GUARD_ERROR
    if _GUARD is not None or _GUARD_ERROR is not None:
        return _GUARD
    try:
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from virtu_omni.computer_use import input_guard as g
        _GUARD = g
    except Exception as exc:      # pragma: no cover - 仅在环境残缺时触发
        _GUARD_ERROR = str(exc)
    return _GUARD


def _deny_no_guard(action: str) -> dict:
    return {"ok": False, "status": "blocked", "action": action,
            "verdict_code": "INPUT_GUARD_UNAVAILABLE",
            "detail": "输入闸门不可用（%s），按 fail-closed 拒绝发送键鼠事件" % _GUARD_ERROR,
            "input_sent": False}


ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION)
    ]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

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

# Keyboard flags
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

SM_CXSCREEN = 0
SM_CYSCREEN = 1

def get_screen_size() -> Tuple[int, int]:
    """Get primary monitor physical resolution."""
    return user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN)

def get_cursor_pos() -> Tuple[int, int]:
    """Get current cursor position."""
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def send_inputs(inputs: List[INPUT]):
    """Execute raw Win32 SendInput array with zero latency."""
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    user32.SendInput(n, arr, ctypes.sizeof(INPUT))


class HumanoidKinematics:
    """
    Simulates human motor control based on:
    1. Flash & Hogan (1985) Minimum Jerk Theory: s(t) = 10t^3 - 15t^4 + 6t^5
    2. Fitts's Law: MT = a + b * log2(1 + D/W)
    3. Physics WindMouse model (gravity, turbulence, damping)
    4. Biological physiological tremor (Gaussian micro-jitter)
    5. Terminal overshoot and sub-movement micro-correction
    """

    @staticmethod
    def fitts_duration(distance: float, target_width: float = 30.0, speed_multiplier: float = 1.0) -> float:
        """Calculate human travel time via Fitts's Law."""
        if distance <= 1:
            return 0.02
        a = 0.08  # Reaction / minimum initiation time
        b = 0.065 # Slope parameter
        id_index = math.log2(1.0 + distance / max(5.0, target_width))
        raw_duration = (a + b * id_index) * speed_multiplier
        # Bound between 80ms and 450ms for realistic yet lightning-fast responsiveness
        return max(0.08, min(0.48, raw_duration))

    @staticmethod
    def generate_minimum_jerk_path(
        start: Tuple[int, int],
        end: Tuple[int, int],
        duration: float,
        hz: int = 120,
        tremor_sigma: float = 0.7,
        overshoot: bool = True
    ) -> List[Tuple[int, int, float]]:
        """
        Generate trajectory using Minimum Jerk 5th-order polynomial with cubic Bezier arc,
        biological tremor, and realistic terminal deceleration.
        Returns list of (x, y, timestamp_delta).
        """
        x0, y0 = start
        x1, y1 = end
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist < 2:
            return [(x1, y1, duration)]

        steps = max(8, int(duration * hz))
        
        # Perpendicular control points for human wrist/arm curvature
        angle = math.atan2(y1 - y0, x1 - x0)
        perp_angle = angle + math.pi / 2.0
        
        # Human natural curve offset
        curve_sign = random.choice([-1, 1]) if random.random() < 0.65 else 0
        curve_magnitude = min(dist * 0.18, 60.0) * random.uniform(0.3, 1.0) * curve_sign
        
        # Cubic Bezier control points
        ctrl1_dist = dist * random.uniform(0.25, 0.40)
        ctrl2_dist = dist * random.uniform(0.60, 0.75)
        
        c1x = x0 + math.cos(angle) * ctrl1_dist + math.cos(perp_angle) * curve_magnitude
        c1y = y0 + math.sin(angle) * ctrl1_dist + math.sin(perp_angle) * curve_magnitude
        
        c2x = x0 + math.cos(angle) * ctrl2_dist + math.cos(perp_angle) * (curve_magnitude * 0.7)
        c2y = y0 + math.sin(angle) * ctrl2_dist + math.sin(perp_angle) * (curve_magnitude * 0.7)

        # Micro-overshoot target if moving fast over long distance
        do_overshoot = overshoot and (dist > 120) and (random.random() < 0.45)
        overshoot_x = x1 + math.cos(angle) * random.uniform(2.0, 5.0) if do_overshoot else x1
        overshoot_y = y1 + math.sin(angle) * random.uniform(2.0, 5.0) if do_overshoot else y1

        points = []
        dt = duration / steps

        for i in range(1, steps + 1):
            tau = i / float(steps)
            # Minimum Jerk velocity integration: s(tau) = 10*tau^3 - 15*tau^4 + 6*tau^5
            s = 10.0 * (tau ** 3) - 15.0 * (tau ** 4) + 6.0 * (tau ** 5)
            
            # Bezier formula
            t = s
            target_pt_x = overshoot_x if (do_overshoot and tau < 0.88) else x1
            target_pt_y = overshoot_y if (do_overshoot and tau < 0.88) else y1
            
            bx = ((1 - t)**3 * x0 +
                  3 * (1 - t)**2 * t * c1x +
                  3 * (1 - t) * (t**2) * c2x +
                  (t**3) * target_pt_x)
                  
            by = ((1 - t)**3 * y0 +
                  3 * (1 - t)**2 * t * c1y +
                  3 * (1 - t) * (t**2) * c2y +
                  (t**3) * target_pt_y)

            # Biological micro-tremor (damping down near end)
            tremor_decay = 1.0 - (0.8 * tau)
            jitter_x = random.gauss(0, tremor_sigma * tremor_decay)
            jitter_y = random.gauss(0, tremor_sigma * tremor_decay)

            px = int(round(bx + jitter_x))
            py = int(round(by + jitter_y))
            points.append((px, py, dt))

        # Guarantee final point is exact destination
        points[-1] = (x1, y1, dt)
        return points

    @staticmethod
    def generate_windmouse_path(
        start: Tuple[int, int],
        end: Tuple[int, int],
        max_step: float = 18.0
    ) -> List[Tuple[int, int]]:
        """Physics WindMouse algorithm using gravity, wind vector, and damping."""
        try:
            from windmouse.core import wind_mouse
            pts = list(wind_mouse(start[0], start[1], end[0], end[1], max_step=max_step))
            return [(int(p[0]), int(p[1])) for p in pts]
        except Exception:
            # Fallback simple physics
            return [(end[0], end[1])]


def get_virtual_bounds() -> Tuple[int, int, int, int]:
    """虚拟桌面矩形 (x0, y0, x1, y1)；多屏时 x0/y0 可能是负数。"""
    x0 = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    y0 = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
    w = user32.GetSystemMetrics(78)    # SM_CXVIRTUALSCREEN
    h = user32.GetSystemMetrics(79)    # SM_CYVIRTUALSCREEN
    if w <= 0 or h <= 0:
        return (0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    return (x0, y0, x0 + w, y0 + h)


class HumanoidMouse:
    """High-speed, human-like mouse controller."""

    def __init__(self, mode: str = "human"):
        self.mode = mode  # "human" or "warp"
        self.sw, self.sh = get_screen_size()

    def _to_normalized_absolute(self, x: int, y: int) -> Tuple[int, int]:
        """Convert pixel coordinates to Win32 SendInput 0..65535 absolute coordinate system.

        分三处修正（旧实现在高分屏/副屏上会稳定偏几像素，点击落到相邻控件）：
        1. 分母是 ``(宽度 - 1)``，不是宽度：65535 对应最后一个像素。
        2. 基准是**虚拟桌面原点**，不是 (0,0)：副屏坐标可能是负数。
        3. 结果夹在 0..65535，避免越界被系统截断到屏幕角落。
        """
        vx0, vy0, vx1, vy1 = get_virtual_bounds()
        w = max(1, (vx1 - vx0) - 1)
        h = max(1, (vy1 - vy0) - 1)
        norm_x = int(round((x - vx0) * 65535 / w))
        norm_y = int(round((y - vy0) * 65535 / h))
        return max(0, min(65535, norm_x)), max(0, min(65535, norm_y))

    @staticmethod
    def _blocked(result: dict) -> dict:
        result.setdefault("input_sent", False)
        result.setdefault("dry_run", False)
        return result

    def move_to(self, target_x: int, target_y: int, duration: Optional[float] = None,
                speed: float = 1.0) -> dict:
        """Move cursor to target coordinates organically or instantly."""
        g = _guard()
        if g is None:
            return _deny_no_guard("move")

        start_x, start_y = get_cursor_pos()
        dist = math.hypot(target_x - start_x, target_y - start_y)
        if dist < 2:
            return {"ok": True, "action": "move", "status": "noop",
                    "reason": "cursor already at target", "input_sent": False}

        with g.input_session("move", x=target_x, y=target_y, require_bounds=True,
                             agent="humanoid") as ctx:
            if ctx["dry_run"]:
                return self._blocked({
                    "ok": True, "action": "move", "status": "simulated",
                    "x": target_x, "y": target_y, "dry_run": True,
                    "verdict_code": ctx.get("verdict_code"),
                    "note": ctx.get("reason"),
                })

            if self.mode == "warp":
                # Sub-0.1ms warp movement
                nx, ny = self._to_normalized_absolute(target_x, target_y)
                send_inputs([INPUT(
                    type=INPUT_MOUSE,
                    u=_INPUT_UNION(mi=MOUSEINPUT(dx=nx, dy=ny, mouseData=0,
                                                 dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                                                 time=0, dwExtraInfo=0))
                )])
                return {"ok": True, "action": "move", "status": "executed",
                        "x": target_x, "y": target_y, "dry_run": False, "input_sent": True}

            # Human organic mode
            if duration is None:
                duration = HumanoidKinematics.fitts_duration(dist, speed_multiplier=speed)
            # 防呆：调用方传 duration=30 时旧代码会生成 3600 个点、连发 30 秒，
            # 期间操作者完全失去鼠标控制权。上限 1.2s。
            duration = max(0.05, min(1.2, float(duration)))

            path = HumanoidKinematics.generate_minimum_jerk_path(
                (start_x, start_y),
                (target_x, target_y),
                duration=duration,
                tremor_sigma=0.65
            )

            t_start = time.perf_counter()
            elapsed = 0.0
            aborted = None

            for px, py, dt in path:
                target_time = elapsed + dt
                nx, ny = self._to_normalized_absolute(px, py)
                send_inputs([INPUT(
                    type=INPUT_MOUSE,
                    u=_INPUT_UNION(mi=MOUSEINPUT(dx=nx, dy=ny, mouseData=0,
                                                 dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                                                 time=0, dwExtraInfo=0))
                )])

                # High-resolution timing sync
                elapsed += dt
                curr_elapsed = time.perf_counter() - t_start
                sleep_needed = target_time - curr_elapsed
                if sleep_needed > 0.001:
                    time.sleep(sleep_needed)

                # 轨迹途中光标偏离我方预期 → 有别的写入者（并发 agent / 操作者真鼠标）。
                # 继续走完只会两边互相拉扯，这里立即让位。
                if g.foreign_motion((px, py)):
                    aborted = "foreign_cursor_writer"
                    print("[humanoid] move aborted: cursor moved by another writer",
                          file=sys.stderr)
                    break

            if aborted is None:
                # Micro-settling dwell (humans decelerate to zero before clicking)
                time.sleep(random.uniform(0.015, 0.035))

        return {"ok": True, "action": "move", "status": "executed",
                "x": target_x, "y": target_y, "aborted": aborted,
                "dry_run": False, "input_sent": True}

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left",
              clicks: int = 1) -> dict:
        """Execute organic mouse click with realistic down-up dwell."""
        if x is not None and y is not None:
            moved = self.move_to(x, y)
            if moved.get("status") == "simulated":
                return moved          # 移动都没发，点击同样不发

        g = _guard()
        if g is None:
            return _deny_no_guard("click")

        with g.input_session("click", x=x, y=y, agent="humanoid") as ctx:
            if ctx["dry_run"]:
                return self._blocked({
                    "ok": True, "action": "click", "status": "simulated",
                    "x": x, "y": y, "button": button, "clicks": clicks,
                    "dry_run": True, "verdict_code": ctx.get("verdict_code"),
                    "note": ctx.get("reason"),
                })

            flag_down = MOUSEEVENTF_LEFTDOWN
            flag_up = MOUSEEVENTF_LEFTUP
            if button == "right":
                flag_down, flag_up = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
            elif button == "middle":
                flag_down, flag_up = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP

            for i in range(max(1, int(clicks))):
                try:
                    send_inputs([INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(
                        mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flag_down,
                                      time=0, dwExtraInfo=0)))])
                    dwell = random.gauss(0.065, 0.010) if self.mode == "human" else 0.005
                    dwell = max(0.035, min(0.095, dwell))
                    time.sleep(dwell)
                finally:
                    # 任何中断都补 UP：否则左键留在按下态，用户一动就是拖选
                    send_inputs([INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(
                        mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flag_up,
                                      time=0, dwExtraInfo=0)))])

                if i < clicks - 1:
                    gap = random.uniform(0.08, 0.14) if self.mode == "human" else 0.01
                    time.sleep(gap)

        return {"ok": True, "action": "click", "status": "executed",
                "x": x, "y": y, "button": button, "clicks": clicks,
                "dry_run": False, "input_sent": True}

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> dict:
        """Perform natural double click."""
        return self.click(x=x, y=y, button="left", clicks=2)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> dict:
        """Perform natural right click."""
        return self.click(x=x, y=y, button="right", clicks=1)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int,
             button: str = "left", duration: Optional[float] = None) -> dict:
        """Execute smooth click-and-drag with drag-load momentum."""
        g = _guard()
        if g is None:
            return _deny_no_guard("drag")

        moved = self.move_to(start_x, start_y)
        if moved.get("status") == "simulated":
            return moved

        with g.input_session("drag", x=end_x, y=end_y, require_bounds=True,
                             agent="humanoid") as ctx:
            if ctx["dry_run"]:
                return self._blocked({
                    "ok": True, "action": "drag", "status": "simulated",
                    "from": [start_x, start_y], "to": [end_x, end_y],
                    "dry_run": True, "verdict_code": ctx.get("verdict_code"),
                    "note": ctx.get("reason"),
                })

            time.sleep(random.uniform(0.02, 0.04))

            flag_down = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
            flag_up = MOUSEEVENTF_LEFTUP if button == "left" else MOUSEEVENTF_RIGHTUP

            # Press down；以下全部用 try/finally 包住，异常/中断必须松手
            send_inputs([INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(
                mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flag_down,
                              time=0, dwExtraInfo=0)))])
            aborted = None
            try:
                time.sleep(random.uniform(0.03, 0.06))

                dist = math.hypot(end_x - start_x, end_y - start_y)
                if duration is None:
                    duration = HumanoidKinematics.fitts_duration(dist, speed_multiplier=1.25)
                duration = max(0.05, min(1.5, float(duration)))

                path = HumanoidKinematics.generate_minimum_jerk_path(
                    (start_x, start_y), (end_x, end_y), duration=duration,
                    tremor_sigma=0.8, overshoot=False
                )

                for px, py, dt in path:
                    nx, ny = self._to_normalized_absolute(px, py)
                    send_inputs([INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(
                        mi=MOUSEINPUT(dx=nx, dy=ny, mouseData=0,
                                      dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                                      time=0, dwExtraInfo=0)))])
                    time.sleep(dt)
                    if g.foreign_motion((px, py)):
                        aborted = "foreign_cursor_writer"
                        break

                time.sleep(random.uniform(0.03, 0.06))
            finally:
                send_inputs([INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(
                    mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flag_up,
                                  time=0, dwExtraInfo=0)))])

        return {"ok": True, "action": "drag", "status": "executed",
                "from": [start_x, start_y], "to": [end_x, end_y], "aborted": aborted,
                "dry_run": False, "input_sent": True}

    def scroll(self, amount: int, x: Optional[int] = None, y: Optional[int] = None) -> dict:
        """Execute realistic mouse wheel scroll with inertia."""
        g = _guard()
        if g is None:
            return _deny_no_guard("scroll")

        if x is not None and y is not None:
            moved = self.move_to(x, y)
            if moved.get("status") == "simulated":
                return moved

        with g.input_session("scroll", x=x, y=y, agent="humanoid") as ctx:
            if ctx["dry_run"]:
                return self._blocked({
                    "ok": True, "action": "scroll", "status": "simulated",
                    "amount": amount, "dry_run": True,
                    "verdict_code": ctx.get("verdict_code"), "note": ctx.get("reason"),
                })

            # In Windows, 1 click = 120 units
            step_dir = 1 if amount > 0 else -1
            total_steps = abs(int(amount))

            if self.mode == "warp":
                send_inputs([INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(
                    mi=MOUSEINPUT(dx=0, dy=0, mouseData=amount * 120,
                                  dwFlags=MOUSEEVENTF_WHEEL, time=0, dwExtraInfo=0)))])
                return {"ok": True, "action": "scroll", "status": "executed",
                        "amount": amount, "dry_run": False, "input_sent": True}

            # Human inertia scrolling: rapid initial pulses followed by gradual decay
            for i in range(total_steps):
                send_inputs([INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(
                    mi=MOUSEINPUT(dx=0, dy=0, mouseData=step_dir * 120,
                                  dwFlags=MOUSEEVENTF_WHEEL, time=0, dwExtraInfo=0)))])
                delay = 0.025 + (i / max(1, total_steps)) * 0.045 + random.uniform(0.005, 0.02)
                time.sleep(delay)

        return {"ok": True, "action": "scroll", "status": "executed",
                "amount": amount, "dry_run": False, "input_sent": True}


class HumanoidKeyboard:
    """Human-like keyboard controller with realistic cadence and Unicode support."""

    VK_MAP = {
        'backspace': 0x08, 'tab': 0x09, 'clear': 0x0C, 'enter': 0x0D, 'return': 0x0D,
        'shift': 0x10, 'ctrl': 0x11, 'control': 0x11, 'alt': 0x12, 'pause': 0x13,
        'caps_lock': 0x14, 'esc': 0x1B, 'escape': 0x1B, 'space': 0x20,
        'page_up': 0x21, 'page_down': 0x22, 'end': 0x23, 'home': 0x24,
        'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
        'insert': 0x2D, 'delete': 0x2E, 'del': 0x2E,
        'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74, 'f6': 0x75,
        'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
        'win': 0x5B, 'super': 0x5B
    }

    def __init__(self, mode: str = "human"):
        self.mode = mode

    def _vk_from_name(self, name: str) -> Optional[int]:
        k = name.strip().lower()
        if k in self.VK_MAP:
            return self.VK_MAP[k]
        if len(k) == 1:
            ch = ord(k.upper())
            if (65 <= ch <= 90) or (48 <= ch <= 57):
                return ch
        return None

    def key_down(self, vk: int):
        inp = INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=0)))
        send_inputs([inp])

    def key_up(self, vk: int):
        inp = INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)))
        send_inputs([inp])

    def press(self, key_name: str) -> dict:
        """Press a single key with realistic hold dwell."""
        vk = self._vk_from_name(key_name)
        if not vk:
            return {"ok": False, "action": "press", "error": "unmapped key: %s" % key_name}

        g = _guard()
        if g is None:
            return _deny_no_guard("press")

        with g.input_session("press", agent="humanoid") as ctx:
            if ctx["dry_run"]:
                return self._blocked({"ok": True, "action": "press", "status": "simulated",
                                      "key": key_name, "dry_run": True,
                                      "verdict_code": ctx.get("verdict_code")})
            try:
                self.key_down(vk)
                dwell = random.uniform(0.035, 0.070) if self.mode == "human" else 0.005
                time.sleep(dwell)
            finally:
                self.key_up(vk)
        return {"ok": True, "action": "press", "status": "executed", "key": key_name,
                "dry_run": False, "input_sent": True}

    @staticmethod
    def _blocked(result: dict) -> dict:
        result.setdefault("input_sent", False)
        result.setdefault("dry_run", False)
        return result

    def hotkey(self, *keys) -> dict:
        """Execute multi-key shortcut with natural key press/release staging."""
        vks = [self._vk_from_name(k) for k in keys if self._vk_from_name(k) is not None]
        if not vks:
            return {"ok": False, "action": "hotkey", "error": "no mappable keys"}

        g = _guard()
        if g is None:
            return _deny_no_guard("hotkey")

        with g.input_session("hotkey", target="focused-window", agent="humanoid") as ctx:
            if ctx["dry_run"]:
                return self._blocked({"ok": True, "action": "hotkey", "status": "simulated",
                                      "keys": list(keys), "dry_run": True,
                                      "verdict_code": ctx.get("verdict_code")})

            # Sequential down；异常也必须逆序抬起，不能把 Ctrl/Alt 留在按下态
            pressed = []
            try:
                for vk in vks:
                    self.key_down(vk)
                    pressed.append(vk)
                    time.sleep(random.uniform(0.015, 0.030) if self.mode == "human" else 0.002)
                time.sleep(random.uniform(0.04, 0.08) if self.mode == "human" else 0.005)
            finally:
                for vk in reversed(pressed):
                    self.key_up(vk)
                    time.sleep(random.uniform(0.010, 0.025) if self.mode == "human" else 0.002)

        return {"ok": True, "action": "hotkey", "status": "executed", "keys": list(keys),
                "dry_run": False, "input_sent": True}

    def type_text(self, text: str) -> dict:
        """
        Type text naturally. Non-ASCII / Chinese strings automatically bridge to
        high-speed Unicode clipboard paste to ensure 100% fidelity without IME dropouts.

        注意：剪贴板路径会**覆盖操作者当前剪贴板内容**，这也是一种"抢夺"。
        未获授权时不执行；执行时先备份，结束后恢复。
        """
        g = _guard()
        if g is None:
            return _deny_no_guard("type_text")

        with g.input_session("type_text", target="focused-control", agent="humanoid") as ctx:
            if ctx["dry_run"]:
                return self._blocked({"ok": True, "action": "type_text", "status": "simulated",
                                      "length": len(text), "dry_run": True,
                                      "verdict_code": ctx.get("verdict_code")})

            has_unicode = any(ord(c) > 127 for c in text)
            if has_unicode or len(text) > 40:
                # Clipboard injection
                backup = self._clipboard_backup()
                try:
                    user32.OpenClipboard(0)
                    user32.EmptyClipboard()
                    text_bytes = (text + '\0').encode('utf-16le')
                    h_mem = kernel32.GlobalAlloc(0x0042, len(text_bytes))
                    ptr = kernel32.GlobalLock(h_mem)
                    ctypes.cdll.msvcrt.memcpy(ctypes.c_void_p(ptr), text_bytes, len(text_bytes))
                    kernel32.GlobalUnlock(h_mem)
                    CF_UNICODETEXT = 13
                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    user32.CloseClipboard()
                    time.sleep(0.03)
                    self.hotkey_nested("ctrl", "v")
                    return {"ok": True, "action": "type_text", "status": "executed",
                            "length": len(text), "channel": "clipboard", "dry_run": False,
                            "input_sent": True}
                except Exception as exc:
                    return {"ok": False, "action": "type_text", "stage": "clipboard",
                            "error": str(exc), "input_sent": False}
                finally:
                    self._clipboard_restore(backup)

            # Direct character typing
            for char in text:
                code = ord(char)
                inp_down = INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0)))
                send_inputs([inp_down])
                dwell = random.uniform(0.025, 0.055) if self.mode == "human" else 0.002
                time.sleep(dwell)
                inp_up = INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)))
                send_inputs([inp_up])

                # Inter-key log-normal cadence
                interval = random.gauss(0.045, 0.015) if self.mode == "human" else 0.002
                interval = max(0.020, min(0.110, interval))
                time.sleep(interval)

        return {"ok": True, "action": "type_text", "status": "executed",
                "length": len(text), "channel": "unicode", "dry_run": False, "input_sent": True}

    def hotkey_nested(self, *keys) -> None:
        """会话内再发组合键（不重新申请租约，避免自锁）。"""
        vks = [self._vk_from_name(k) for k in keys if self._vk_from_name(k) is not None]
        pressed = []
        try:
            for vk in vks:
                self.key_down(vk)
                pressed.append(vk)
                time.sleep(0.01)
            time.sleep(0.02)
        finally:
            for vk in reversed(pressed):
                self.key_up(vk)
                time.sleep(0.01)

    @staticmethod
    def _clipboard_backup():
        """尽力备份文本型剪贴板；失败返回 None（不阻断输入）。"""
        try:
            user32.OpenClipboard(0)
            try:
                CF_UNICODETEXT = 13
                if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                    return None
                h = user32.GetClipboardData(CF_UNICODETEXT)
                if not h:
                    return None
                ptr = kernel32.GlobalLock(h)
                if not ptr:
                    return None
                try:
                    return ctypes.wstring_at(ptr)
                finally:
                    kernel32.GlobalUnlock(h)
            finally:
                user32.CloseClipboard()
        except Exception:
            return None

    @staticmethod
    def _clipboard_restore(text) -> None:
        if text is None:
            return
        try:
            user32.OpenClipboard(0)
            try:
                user32.EmptyClipboard()
                data = (text + '\0').encode('utf-16le')
                h_mem = kernel32.GlobalAlloc(0x0042, len(data))
                ptr = kernel32.GlobalLock(h_mem)
                ctypes.cdll.msvcrt.memcpy(ctypes.c_void_p(ptr), data, len(data))
                kernel32.GlobalUnlock(h_mem)
                user32.SetClipboardData(13, h_mem)
            finally:
                user32.CloseClipboard()
        except Exception:
            pass


class FastScreenPerception:
    """Sub-5ms screen perception engine powered by mss and DPI-aware cropping."""

    def __init__(self):
        self._sct = None

    def _get_sct(self):
        if self._sct is None:
            import mss
            self._sct = mss.MSS()
        return self._sct

    def capture_fullscreen(self, output_path: Optional[str] = None) -> Any:
        """Capture entire screen in 5-25ms."""
        sct = self._get_sct()
        monitor = sct.monitors[1]  # Primary monitor
        sct_img = sct.grab(monitor)
        
        from PIL import Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        if output_path:
            img.save(output_path)
        return img

    def capture_region(self, left: int, top: int, width: int, height: int, output_path: Optional[str] = None) -> Any:
        """Capture sub-region in sub-10ms."""
        sct = self._get_sct()
        bbox = {"left": left, "top": top, "width": width, "height": height}
        sct_img = sct.grab(bbox)
        from PIL import Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        if output_path:
            img.save(output_path)
        return img


class DeterministicGrounding:
    """
    Sub-3ms Windows UIAutomation deterministic tree resolution.
    Eliminates vision hallucination by querying OS accessibility trees directly.
    """

    @staticmethod
    def find_element_bounds(name: Optional[str] = None, class_name: Optional[str] = None, control_type: Optional[str] = None) -> Optional[Tuple[int, int, int, int]]:
        """
        Find UI element bounding box: (left, top, right, bottom).
        Uses uiautomation COM interfaces.
        """
        try:
            import uiautomation as uia
            root = uia.GetRootControl()
            
            # Build search conditions
            kwargs = {}
            if name:
                kwargs["Name"] = name
            if class_name:
                kwargs["ClassName"] = class_name
                
            ctrl = root.Control(searchDepth=6, **kwargs)
            if ctrl.Exists(maxSearchSeconds=0.5):
                rect = ctrl.BoundingRectangle
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
        return None

    @staticmethod
    def sample_human_target_coordinate(bounds: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """
        Given element bounds (left, top, right, bottom), sample an organic landing coordinate
        within the central 60% of the element, avoiding robotic dead-center repetition.
        """
        left, top, right, bottom = bounds
        w = max(4, right - left)
        h = max(4, bottom - top)
        
        # Center point
        cx = left + w / 2.0
        cy = top + h / 2.0
        
        # Gaussian offset within central 50%
        sigma_x = w * 0.12
        sigma_y = h * 0.12
        
        offset_x = random.gauss(0, sigma_x)
        offset_y = random.gauss(0, sigma_y)
        
        # Clamped inside inner 70% boundary
        target_x = int(round(max(left + w * 0.15, min(right - w * 0.15, cx + offset_x))))
        target_y = int(round(max(top + h * 0.15, min(bottom - h * 0.15, cy + offset_y))))
        
        return target_x, target_y


# Global Singletons
human_mouse = HumanoidMouse(mode="human")
warp_mouse = HumanoidMouse(mode="warp")
human_keyboard = HumanoidKeyboard(mode="human")
perception = FastScreenPerception()
grounding = DeterministicGrounding()


def main():
    import argparse
    import json

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--mode", choices=["human", "warp"], default="human", help="Execution mode (human=organic, warp=sub-0.1ms)")
    common_parser.add_argument("--json", action="store_true", help="Output JSON results")

    parser = argparse.ArgumentParser(description="Humanoid Desktop Controller Engine", parents=[common_parser])
    sub = parser.add_subparsers(dest="command")

    # move
    p_move = sub.add_parser("move", parents=[common_parser])
    p_move.add_argument("--x", type=int, required=True)
    p_move.add_argument("--y", type=int, required=True)
    p_move.add_argument("--duration", type=float)

    # click
    p_click = sub.add_parser("click", parents=[common_parser])
    p_click.add_argument("--x", type=int)
    p_click.add_argument("--y", type=int)
    p_click.add_argument("--button", default="left", choices=["left", "right", "middle"])
    p_click.add_argument("--clicks", type=int, default=1)

    # click-element (UIA deterministic grounding)
    p_celem = sub.add_parser("click-element", parents=[common_parser])
    p_celem.add_argument("--name", help="Element accessible name")
    p_celem.add_argument("--class-name", help="Element window class")
    p_celem.add_argument("--button", default="left")

    # drag
    p_drag = sub.add_parser("drag", parents=[common_parser])
    p_drag.add_argument("--from-x", type=int, required=True)
    p_drag.add_argument("--from-y", type=int, required=True)
    p_drag.add_argument("--to-x", type=int, required=True)
    p_drag.add_argument("--to-y", type=int, required=True)
    p_drag.add_argument("--duration", type=float)

    # scroll
    p_scroll = sub.add_parser("scroll", parents=[common_parser])
    p_scroll.add_argument("--amount", type=int, required=True)
    p_scroll.add_argument("--x", type=int)
    p_scroll.add_argument("--y", type=int)

    # type
    p_type = sub.add_parser("type", parents=[common_parser])
    p_type.add_argument("--text", required=True)

    # hotkey
    p_hotkey = sub.add_parser("hotkey", parents=[common_parser])
    p_hotkey.add_argument("--keys", required=True, help="Comma separated, e.g. ctrl,s")

    # capture
    p_cap = sub.add_parser("capture", parents=[common_parser])
    p_cap.add_argument("--output", required=True)
    p_cap.add_argument("--region", help="left,top,width,height")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    controller_mouse = HumanoidMouse(mode=args.mode)
    controller_kb = HumanoidKeyboard(mode=args.mode)
    res = {"success": True, "command": args.command, "mode": args.mode}

    def _absorb(r):
        """把执行器的 status/input_sent/dry_run 透出到 CLI 结果。

        旧 CLI 只看 ``success``：闸门拒绝时也打印 "Success: True"，脚本侧会
        以为鼠标真的动了。现在 input_sent=False 会被明确标出来。
        """
        if isinstance(r, dict):
            for k in ("status", "input_sent", "dry_run", "verdict_code", "aborted", "error"):
                if r.get(k) is not None:
                    res[k] = r.get(k)
            if r.get("ok") is False:
                res["success"] = False
        return r

    t0 = time.perf_counter()

    try:
        if args.command == "move":
            _absorb(controller_mouse.move_to(args.x, args.y, duration=args.duration))
            res["target"] = [args.x, args.y]

        elif args.command == "click":
            _absorb(controller_mouse.click(x=args.x, y=args.y, button=args.button, clicks=args.clicks))
            res["clicked"] = {"x": args.x, "y": args.y, "button": args.button, "clicks": args.clicks}

        elif args.command == "click-element":
            bounds = grounding.find_element_bounds(name=args.name, class_name=args.class_name)
            if not bounds:
                res["success"] = False
                res["error"] = f"Element not found: name={args.name}, class={args.class_name}"
            else:
                tx, ty = grounding.sample_human_target_coordinate(bounds)
                _absorb(controller_mouse.click(x=tx, y=ty, button=args.button))
                res["element_bounds"] = bounds
                res["sampled_target"] = [tx, ty]

        elif args.command == "drag":
            _absorb(controller_mouse.drag(args.from_x, args.from_y, args.to_x, args.to_y, duration=args.duration))
            res["dragged"] = {"from": [args.from_x, args.from_y], "to": [args.to_x, args.to_y]}

        elif args.command == "scroll":
            _absorb(controller_mouse.scroll(args.amount, x=args.x, y=args.y))
            res["scrolled"] = args.amount

        elif args.command == "type":
            _absorb(controller_kb.type_text(args.text))
            res["typed"] = args.text

        elif args.command == "hotkey":
            keys = [k.strip() for k in args.keys.split(",")]
            _absorb(controller_kb.hotkey(*keys))
            res["hotkey"] = keys

        elif args.command == "capture":
            if args.region:
                l, t, w, h = [int(p.strip()) for p in args.region.split(",")]
                perception.capture_region(l, t, w, h, output_path=args.output)
            else:
                perception.capture_fullscreen(output_path=args.output)
            res["output"] = args.output

        res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    except Exception as e:
        res["success"] = False
        res["error"] = str(e)

    if res.get("input_sent") is False:
        res["note"] = ("键鼠事件未发送：%s。设 VIRTU_DESKTOP_INPUT=1 才允许真实输入。"
                       % (res.get("verdict_code") or res.get("status") or "suppressed"))

    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"Executed {args.command} in {res.get('latency_ms', 0)}ms. "
              f"Success: {res['success']}, input_sent: {res.get('input_sent', True)}")
        if res.get("note"):
            print("  " + res["note"], file=sys.stderr)


if __name__ == "__main__":
    main()
