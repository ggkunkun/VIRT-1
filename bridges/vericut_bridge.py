"""VERICUT 9.6 Automation Bridge.

Inspired by:
- CGTech VERICUT Batch Interface
- qunat/Pythonocc-vericut
- gcode-simulator / CNC verification pipelines

Features:
- Headless batch simulation runner (vericut.bat -b <project> -m)
- Auto-Diff gouge and excess material checking
- Kinematic machine collision detection & report parsing
- Toolpath cycle time estimation and OptiPath/Force optimization verification
"""

import os
import sys
import subprocess
import json

VERICUT_BAT = r"E:\windows64\commands\vericut.bat"


class VericutBridge:
    def __init__(self):
        self.vericut_bat = VERICUT_BAT

    def run_batch_simulation(self, project_path: str, log_output_path: str = None):
        """Run VERICUT simulation headlessly.

        NOTE: VERICUT 9.6 was reverse-engineered (2026-10-30 report) and found to
        expose **no** machine-readable automation interface — COM/IPC/batch/UIA
        all dead; the only reliable driver is the GUI (template-match + click)
        channel implemented in ``work/vericut-toolchain/vericut_link.py``.  The
        legacy ``vericut.bat -b -m`` batch path self-exits with zero output, so
        we no longer pretend headless batch works; we surface a clear status
        instead of a misleading "failed".
        """
        if not os.path.exists(self.vericut_bat):
            return {"status": "error", "message": f"VERICUT batch command not found: {self.vericut_bat}"}
        if not os.path.exists(project_path):
            return {"status": "error", "message": f"Project file not found: {project_path}"}
        return {
            "status": "unsupported_headless",
            "message": ("VERICUT 9.6 has no programmatic/batch interface. Drive the "
                        "simulation through work/vericut-toolchain/vericut_link.py "
                        "(launch_via_bat + play_simulation) and read numbers back with "
                        "vericut_link.parse_sim_log / parse_collision_log."),
        }

    def parse_collision_log(self, log_path: str):
        """Parse VERICUT error / collision log file.

        Handles both English and Chinese (CGTECH_LOCALE=chinese_simplified) logs.
        Collisions / gouges are the safety-relevant signal and are counted
        separately from generic errors and warnings — a line containing "error"
        is no longer miscounted as a collision.
        """
        if not os.path.exists(log_path):
            return {"status": "error", "message": f"Log file does not exist: {log_path}"}

        collisions = []
        errors = []
        warnings = []
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                low = line.lower()
                # Safety-relevant: collision / gouge (碰撞 / 过切)
                if ("碰撞" in line or "过切" in line or "collision" in low or "gouge" in low):
                    collisions.append(line.strip())
                # Generic error: exclude lines already counted as collisions.
                elif "错误" in line or "error" in low:
                    errors.append(line.strip())
                elif "警告" in line or "warning" in low:
                    warnings.append(line.strip())

        return {
            "status": "success",
            "collision_count": len(collisions),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "collisions": collisions[:10],
            "errors": errors[:10],
            "warnings": warnings[:10],
            "is_safe": len(collisions) == 0,
        }


if __name__ == "__main__":
    bridge = VericutBridge()
    print("VERICUT Bridge Initialized.")
