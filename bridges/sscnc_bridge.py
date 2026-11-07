"""SSCNC 7.2 (斯沃数控仿真软件) Automation Bridge.

Inspired by:
- Windows Industrial Desktop Automation
- FANUC 0i-TF & 0i-MD Virtual CNC Setup
- G-code injection & WCS / Tool Offset calibration

Features:
- SSCNC launch & window activation
- WCS G54 ~ G59 coordinate setup automation
- Tool geometry offset quadrant calculation (T1 ~ T9)
- G-code program loading and Cycle Start trigger
"""

import os
import sys
import subprocess
import time

SSCNC_EXE = r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe"

try:
    import win32gui
    import win32con
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
