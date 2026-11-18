#!/usr/bin/env python3
"""
cad_viewport_controller.py - 3D CAD/CAM Spatial Viewport Navigation & Humanoid Gesture Controller.
Grounded in SOTA CAD Automation:
  - raylanlin/Millwright: SolidWorks 2021 Viewport Navigation & Camera Control
  - skyf0l/siemens-nx-mcp: Siemens NX 12.0 UF_VIEW & 3D Orbit Navigation
  - Autodesk AutoCAD 2026: 3D Orbit, Pan, and Zoom Extents Protocol
"""

import os
import sys
import time
import json
import argparse
from typing import Optional, Dict, Any, Tuple

# humanoid_controller 解析顺序：包内同源副本 → 环境变量 VIRTU_HUMANOID_SCRIPTS → 历史私有 skill 目录
try:  # 作为 virtu_omni.engine 子模块导入时优先使用包内副本（与私有副本 SHA-256 完全一致）
    from . import humanoid_controller as hc
except ImportError:  # 脚本直跑（无包上下文）时回退外部路径
    HUMANOID_SCRIPTS = os.environ.get(
        "VIRTU_HUMANOID_SCRIPTS",
        r"C:\Users\Administrator\.gemini\config\skills\humanoid-computer-control\scripts",
    )
    if HUMANOID_SCRIPTS not in sys.path:
        sys.path.insert(0, HUMANOID_SCRIPTS)
    import humanoid_controller as hc  # noqa: E402


class CADViewportNavigator:
    """Simulates realistic human hand gestures in 3D CAD/CAM viewports."""

    CAD_HOTKEYS = {
        "solidworks": {
            "iso": ["ctrl", "7"],
            "front": ["ctrl", "1"],
            "back": ["ctrl", "2"],
            "left": ["ctrl", "3"],
            "right": ["ctrl", "4"],
            "top": ["ctrl", "5"],
            "bottom": ["ctrl", "6"],
            "normal_to": ["ctrl", "8"],
            "fit": ["f"]
        },
        "nx": {
            "iso": ["ctrl", "alt", "i"],
            "front": ["ctrl", "alt", "f"],
            "right": ["ctrl", "alt", "r"],
            "top": ["ctrl", "alt", "t"],
            "normal_to": ["f8"],
            "fit": ["ctrl", "f"]
        },
        "autocad": {
            "fit": ["z", "enter", "e", "enter"]
        }
    }

    def __init__(self, software: str = "solidworks"):
        self.software = software.lower()
        self.mouse = hc.HumanoidMouse(mode="human")
        self.kb = hc.HumanoidKeyboard(mode="human")

    def orbit(self, dx: int, dy: int, center_x: Optional[int] = None, center_y: Optional[int] = None, duration: float = 0.35) -> Dict[str, Any]:
        """
        Execute 3D rotation / orbit via Middle Mouse Button (MMB) drag with momentum.
        In SolidWorks / NX / Vericut / SSCNC, MMB drag orbits the 3D model.
        """
        if center_x is None or center_y is None:
            sw, sh = hc.get_screen_size()
            center_x, center_y = sw // 2, sh // 2

        start_x, start_y = center_x, center_y
        end_x, end_y = center_x + dx, center_y + dy

        # Execute smooth MMB drag
        self.mouse.drag(start_x, start_y, end_x, end_y, button="middle", duration=duration)
        return {"success": True, "gesture": "orbit", "delta": [dx, dy], "center": [start_x, start_y]}

    def pan(self, dx: int, dy: int, center_x: Optional[int] = None, center_y: Optional[int] = None, duration: float = 0.30) -> Dict[str, Any]:
        """
        Execute 2D/3D pan:
        - SolidWorks: Ctrl + MMB (or Shift + MMB)
        - NX: Shift + MMB
        - AutoCAD: MMB direct drag
        """
        if center_x is None or center_y is None:
            sw, sh = hc.get_screen_size()
            center_x, center_y = sw // 2, sh // 2

        start_x, start_y = center_x, center_y
        end_x, end_y = center_x + dx, center_y + dy

        if self.software in ["solidworks", "nx"]:
            # Hold Shift / Ctrl modifier
            self.kb.key_down(hc.HumanoidKeyboard.VK_MAP['shift'])
            time.sleep(0.03)
            self.mouse.drag(start_x, start_y, end_x, end_y, button="middle", duration=duration)
            time.sleep(0.02)
            self.kb.key_up(hc.HumanoidKeyboard.VK_MAP['shift'])
        else:
            self.mouse.drag(start_x, start_y, end_x, end_y, button="middle", duration=duration)

        return {"success": True, "gesture": "pan", "delta": [dx, dy]}

    def zoom(self, clicks: int, focus_x: Optional[int] = None, focus_y: Optional[int] = None) -> Dict[str, Any]:
        """Smoothly zoom in (+clicks) or out (-clicks) centered at target 3D feature."""
        self.mouse.scroll(clicks, x=focus_x, y=focus_y)
        return {"success": True, "gesture": "zoom", "clicks": clicks, "focus": [focus_x, focus_y]}

    def align_view(self, view_name: str) -> Dict[str, Any]:
        """Set standard CAD camera projection (iso, front, top, right, normal_to, fit)."""
        v = view_name.lower().replace("-", "_")
        keys_map = self.CAD_HOTKEYS.get(self.software, self.CAD_HOTKEYS["solidworks"])
        
        if v not in keys_map:
            return {"success": False, "error": f"Unknown view '{view_name}' for software '{self.software}'"}

        keys = keys_map[v]
        self.kb.hotkey(*keys)
        return {"success": True, "action": "align_view", "view": view_name, "software": self.software, "hotkey": keys}


def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", help="Output JSON format")
    common_parser.add_argument("--software", choices=["solidworks", "nx", "autocad"], default="solidworks")

    parser = argparse.ArgumentParser(description="3D CAD Viewport Gesture & Camera Controller", parents=[common_parser])
    sub = parser.add_subparsers(dest="command")

    # orbit
    p_orbit = sub.add_parser("orbit", parents=[common_parser])
    p_orbit.add_argument("--dx", type=int, required=True, help="Horizontal rotation delta in pixels")
    p_orbit.add_argument("--dy", type=int, required=True, help="Vertical rotation delta in pixels")
    p_orbit.add_argument("--cx", type=int, help="Center X")
    p_orbit.add_argument("--cy", type=int, help="Center Y")

    # pan
    p_pan = sub.add_parser("pan", parents=[common_parser])
    p_pan.add_argument("--dx", type=int, required=True)
    p_pan.add_argument("--dy", type=int, required=True)
    p_pan.add_argument("--cx", type=int)
    p_pan.add_argument("--cy", type=int)

    # zoom
    p_zoom = sub.add_parser("zoom", parents=[common_parser])
    p_zoom.add_argument("--clicks", type=int, required=True, help="+ for zoom in, - for zoom out")
    p_zoom.add_argument("--x", type=int)
    p_zoom.add_argument("--y", type=int)

    # view
    p_view = sub.add_parser("view", parents=[common_parser])
    p_view.add_argument("--name", required=True, choices=["iso", "front", "back", "left", "right", "top", "bottom", "normal_to", "fit"])

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    nav = CADViewportNavigator(software=args.software)

    if args.command == "orbit":
        res = nav.orbit(args.dx, args.dy, center_x=args.cx, center_y=args.cy)
    elif args.command == "pan":
        res = nav.pan(args.dx, args.dy, center_x=args.cx, center_y=args.cy)
    elif args.command == "zoom":
        res = nav.zoom(args.clicks, focus_x=args.x, focus_y=args.y)
    elif args.command == "view":
        res = nav.align_view(args.name)

    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"Executed CAD Viewport {args.command}: {res}")


if __name__ == "__main__":
    main()
