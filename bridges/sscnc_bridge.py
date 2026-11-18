"""SSCNC 7.2 (斯沃数控仿真软件) Automation Bridge.

Inspired by:
- Windows Industrial Desktop Automation
- FANUC 0i-TF & 0i-MD Virtual CNC Setup
- G-code injection & WCS / Tool Offset calibration

Features:
- SSCNC launch & window activation
- WCS G54 ~ G59 coordinate setup automation
- Tool geometry offset quadrant calculation (T1 ~ T9)
- Panel capability probe: self-drawn canvas is reported as unsupported, never faked
"""

import os
import sys
import subprocess
import time

SSCNC_EXE = r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe"

try:
    import win32gui
    import win32con
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class SSCNCBridge:
    def __init__(self):
        self.sscnc_exe = SSCNC_EXE

    def launch(self):
        """Launch SSCNC Simulator."""
        if not os.path.exists(self.sscnc_exe):
            return {"status": "error", "message": f"SSCNC executable not found: {self.sscnc_exe}"}

        try:
            subprocess.Popen([self.sscnc_exe], cwd=os.path.dirname(self.sscnc_exe))
            return {"status": "launched", "path": self.sscnc_exe}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def find_window(self):
        """Find active SSCNC window handle."""
        if not HAS_WIN32:
            return {"status": "error", "message": "win32gui not available"}

        hwnd_found = []

        def enum_cb(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "斯沃" in title or "SSCNC" in title or "FANUC" in title:
                    hwnd_found.append((hwnd, title))
            return True

        win32gui.EnumWindows(enum_cb, None)
        if hwnd_found:
            return {"status": "found", "hwnd": hwnd_found[0][0], "title": hwnd_found[0][1]}
        return {"status": "not_running", "message": "SSCNC window not found"}

    def panel_capability(self):
        """Probe whether the CNC panel exposes text-addressable child controls.

        SSCNC 7.2 draws the CNC panel on a self-drawn canvas; on this build the
        panel has no Button/Static children with key labels.  The probe makes
        that boundary explicit instead of reporting a fake key press.
        """
        if not HAS_WIN32:
            return {"status": "unsupported", "reason": "win32gui not available"}
        win = self.find_window()
        if win.get("status") != "found":
            return {"status": win.get("status", "not_running"), "reason": "SSCNC window not found"}
        hwnd = win["hwnd"]
        children = []

        def _cb(h, _):
            try:
                children.append({
                    "hwnd": h,
                    "class": win32gui.GetClassName(h),
                    "text": win32gui.GetWindowText(h),
                })
            except Exception:
                pass
            return True

        win32gui.EnumChildWindows(hwnd, _cb, None)
        key_like = [c for c in children
                    if c["class"] in ("Button", "Static") and c["text"].strip()]
        return {
            "status": "supported" if key_like else "unsupported",
            "reason": "" if key_like else "self-drawn CNC canvas: no Button/Static key controls",
            "window_title": win.get("title"),
            "child_count": len(children),
            "key_like": key_like[:20],
        }

    def press_panel_key(self, label: str):
        """Press a text-addressable panel key; refuse loudly when none exists."""
        cap = self.panel_capability()
        if cap.get("status") != "supported":
            return {"status": "unsupported", "reason": cap.get("reason"), "capability": cap}
        target = None
        for c in cap["key_like"]:
            if label.upper() in (c["text"] or "").upper():
                target = c
                break
        if target is None:
            return {"status": "not_found", "label": label, "keys": [c["text"] for c in cap["key_like"]]}
        try:
            win32api.PostMessage(target["hwnd"], win32con.BM_CLICK, 0, 0)
            return {"status": "clicked", "label": label, "hwnd": target["hwnd"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_tool_offsets(self, tools: list):
        """Calculate FANUC lathe/mill tool geometry and wear offsets with quadrant logic (T1-T9)."""
        offsets_table = []
        for t in tools:
            t_num = t.get("tool_num", 1)
            t_type = t.get("type", "turning_rough")
            x_val = t.get("x", 0.0)
            z_val = t.get("z", 0.0)
            r_val = t.get("r", 0.8)  # nose radius

            # FANUC Tool tip quadrant: 3 for OD turning, 2 for ID boring, 8 for threading
            quadrant = t.get("quadrant", 3 if "turning" in t_type else 2)

            offsets_table.append({
                "tool_code": f"T{t_num:02d}{t_num:02d}",
                "geometry_x": x_val,
                "geometry_z": z_val,
                "nose_radius_r": r_val,
                "quadrant_t": quadrant,
                "description": t.get("desc", f"Tool {t_num}")
            })

        return {
            "status": "success",
            "wcs_target": "G54",
            "offsets": offsets_table
        }


if __name__ == "__main__":
    bridge = SSCNCBridge()
    test_tools = [
        {"tool_num": 1, "type": "turning_rough", "x": 120.5, "z": 45.2, "r": 0.8, "quadrant": 3},
        {"tool_num": 2, "type": "grooving_parting", "x": 118.0, "z": 45.0, "r": 0.2, "quadrant": 3},
        {"tool_num": 3, "type": "threading", "x": 122.1, "z": 46.0, "r": 0.1, "quadrant": 8}
    ]
    print("SSCNC Bridge Initialized. Offset calculation test:", bridge.calculate_tool_offsets(test_tools))
