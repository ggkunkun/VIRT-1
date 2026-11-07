"""Virtu Computer Use: Unified Desktop Automation Adapter.

Provides the primary interface for autonomous AI agents, Harness 2, and the
WorkBuddy Bridge to control Windows GUIs using the Perception-Reasoning-Action loop.
"""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from virtu_omni.computer_use.action import ActionEngine
from virtu_omni.computer_use.perception import PerceptionEngine

logger = logging.getLogger("virtu_omni.computer_use.adapter")


class VirtuComputerUse:
    """Master adapter for Computer Use & Windows Desktop Automation in Virtu Model."""

    _instance: Optional[VirtuComputerUse] = None

    def __init__(self, workspace_root: Optional[Union[Path, str]] = None) -> None:
        self.workspace_root = Path(workspace_root or "d:/Virtu模型").resolve()
        self.perception = PerceptionEngine(workspace_root=self.workspace_root)
        self.action = ActionEngine()

        self.skill_computer_use_path = self.workspace_root / "skills" / "computer-use" / "SKILL.md"
        self.skill_industrial_path = (
            self.workspace_root / "skills" / "windows-industrial-desktop-automation" / "SKILL.md"
        )
        self.windows_mcp_path = self.workspace_root / "external" / "windows-mcp"

    @classmethod
    def get_instance(cls, workspace_root: Optional[Union[Path, str]] = None) -> VirtuComputerUse:
        if cls._instance is None:
            cls._instance = cls(workspace_root=workspace_root)
        return cls._instance

    def get_screen_profile(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Retrieve user monitor adaptation profile (resolution, DPI scale, work area, taskbar)."""
        return self.perception.get_screen_profile(force_refresh=force_refresh)

    def execute_action(self, action_name: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """Dispatch any computer control action."""
        if not action_name:
            action_name = str(kwargs.pop("action", ""))
        act = action_name.lower().strip()

        if act in ("screen_profile", "profile", "display", "screen_metrics"):
            return {
                "ok": True,
                "screen_profile": self.get_screen_profile(force_refresh=kwargs.get("refresh", False)),
            }
        elif act in ("normalize_coords", "to_normalized"):
            nx, ny = self.perception.normalize_coordinates(
                x=kwargs.get("x", 0),
                y=kwargs.get("y", 0),
                scale_1000=bool(kwargs.get("scale_1000", False)),
            )
            return {"ok": True, "normalized": [nx, ny]}
        elif act in ("denormalize_coords", "from_normalized"):
            px, py = self.perception.denormalize_coordinates(
                nx=kwargs.get("nx", kwargs.get("x", 0)),
                ny=kwargs.get("ny", kwargs.get("y", 0)),
                is_1000_scale=kwargs.get("is_1000_scale"),
                inside_work_area=bool(kwargs.get("inside_work_area", False)),
            )
            return {"ok": True, "pixel": [px, py]}
        elif act in ("screenshot", "capture_screen"):
            return self.perception.capture_screen(
                output_path=kwargs.get("output_path"),
                bbox=kwargs.get("bbox"),
            )
        elif act in ("list_windows", "windows"):
            windows = self.perception.list_windows(
                visible_only=kwargs.get("visible_only", True),
                min_width=kwargs.get("min_width", 50),
                min_height=kwargs.get("min_height", 50),
            )
            return {"ok": True, "count": len(windows), "windows": windows}
        elif act in ("find_window", "locate_window"):
            w = self.perception.find_window(kwargs.get("query", ""))
            return {"ok": bool(w), "window": w}
        elif act in ("inspect_elements", "elements", "ui_tree"):
            hwnd = kwargs.get("hwnd")
            return self.perception.inspect_element_tree(hwnd=hwnd)
        elif act in ("click", "mouse_click"):
            return self.action.click(
                x=kwargs.get("x", 0),
                y=kwargs.get("y", 0),
                button=kwargs.get("button", "left"),
                double=bool(kwargs.get("double", False)),
                hwnd=kwargs.get("hwnd"),
                normalized=bool(kwargs.get("normalized", False)),
                is_logical=bool(kwargs.get("is_logical", False)),
                allow_taskbar=bool(kwargs.get("allow_taskbar", True)),
            )
        elif act in ("move", "mouse_move"):
            return self.action.mouse_move(
                x=kwargs.get("x", 0),
                y=kwargs.get("y", 0),
                normalized=bool(kwargs.get("normalized", False)),
                is_logical=bool(kwargs.get("is_logical", False)),
            )
        elif act in ("type", "type_text"):
            return self.action.type_text(
                text=str(kwargs.get("text", "")),
                delay_ms=int(kwargs.get("delay_ms", 5)),
            )
        elif act in ("hotkey", "shortcut"):
            keys = kwargs.get("keys", [])
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split("+")]
            return self.action.hotkey(keys=keys)
        elif act in ("scroll", "wheel"):
            return self.action.scroll(
                clicks=int(kwargs.get("clicks", 1)),
                x=kwargs.get("x"),
                y=kwargs.get("y"),
            )
        elif act in ("drag", "mouse_drag"):
            return self.action.drag(
                start_x=kwargs.get("start_x", 0),
                start_y=kwargs.get("start_y", 0),
                end_x=kwargs.get("end_x", 0),
                end_y=kwargs.get("end_y", 0),
                steps=int(kwargs.get("steps", 10)),
                button=kwargs.get("button", "left"),
                normalized=bool(kwargs.get("normalized", False)),
                is_logical=bool(kwargs.get("is_logical", False)),
            )
        elif act in ("activate_window", "focus_window"):
            return self.action.activate_window(kwargs.get("hwnd_or_title", ""))
        else:
            return {"ok": False, "error": f"Unsupported computer-use action: '{action_name}'"}

    def run_see_think_act_loop(
        self,
        goal: str,
        actions: List[Dict[str, Any]],
        capture_screenshots: bool = True,
    ) -> Dict[str, Any]:
        """Execute a structured Perception-Reasoning-Action loop."""
        step_results: List[Dict[str, Any]] = []

        # 1. Initial Perception
        pre_capture = None
        if capture_screenshots:
            pre_capture = self.perception.capture_screen()

        # 2. Sequential Action Execution
        for idx, act_step in enumerate(actions, 1):
            act_name = act_step.get("action", "")
            act_params = {k: v for k, v in act_step.items() if k != "action"}
            t0 = time.perf_counter()
            res = self.execute_action(act_name, **act_params)
            dur_ms = (time.perf_counter() - t0) * 1000

            step_results.append({
                "step": idx,
                "action": act_name,
                "params": act_params,
                "result": res,
                "latency_ms": round(dur_ms, 2),
            })

        # 3. Final Verification
        post_capture = None
        if capture_screenshots:
            post_capture = self.perception.capture_screen()

        profile = self.get_screen_profile()
        return {
            "ok": all(s["result"].get("ok", False) for s in step_results),
            "goal": goal,
            "total_steps": len(actions),
            "screen_profile": {
                "resolution": f"{profile['physical_resolution']['width']}x{profile['physical_resolution']['height']}",
                "work_area": f"{profile['work_area']['width']}x{profile['work_area']['height']}",
                "dpi_scale": profile["dpi"]["scale_factor"],
            },
            "steps": step_results,
            "pre_action_state": pre_capture,
            "post_action_state": post_capture,
            "status": "COMPLETED",
        }

    def get_desktop_summary(self) -> Dict[str, Any]:
        """Provide real-time desktop overview for Agent reasoning."""
        metrics = self.perception.get_screen_metrics()
        profile = self.get_screen_profile()
        windows = self.perception.list_windows(visible_only=True)
        active_win = next((w for w in windows if w.get("is_active")), None)

        return {
            "screen": metrics,
            "screen_profile": profile,
            "active_window": active_win,
            "visible_window_count": len(windows),
            "top_applications": [w["title"] for w in windows[:8]],
        }

    def get_status(self) -> Dict[str, Any]:
        """Report Computer Use readiness, Win32 API status, and skills paths."""
        metrics = self.perception.get_screen_metrics()
        profile = self.get_screen_profile()

        return {
            "status": "READY",
            "operating_system": "Windows 10/11 x64",
            "screen_resolution": f"{metrics['primary_width']}x{metrics['primary_height']}",
            "work_area": f"{profile['work_area']['width']}x{profile['work_area']['height']}",
            "dpi_scaling": profile["dpi"]["scale_percent"],
            "dpi_scale_factor": profile["dpi"]["scale_factor"],
            "taskbar_height": profile["taskbar"]["height"],
            "virtual_desktop": f"{metrics['virtual_width']}x{metrics['virtual_height']}",
            "win32_api_available": True,
            "computer_use_skill_installed": self.skill_computer_use_path.is_file(),
            "computer_use_skill_path": (
                str(self.skill_computer_use_path) if self.skill_computer_use_path.is_file() else None
            ),
            "industrial_automation_skill_installed": self.skill_industrial_path.is_file(),
            "industrial_automation_skill_path": (
                str(self.skill_industrial_path) if self.skill_industrial_path.is_file() else None
            ),
            "upstream_windows_mcp_installed": self.windows_mcp_path.is_dir(),
            "upstream_windows_mcp_path": (
                str(self.windows_mcp_path) if self.windows_mcp_path.is_dir() else None
            ),
            "screen_profile": profile,
            "supported_actions": [
                "capture_screen (full / bbox)",
                "list_windows (bounds, hwnd, pid)",
                "find_window (query substring)",
                "inspect_elements (UI hierarchy)",
                "click (left / right / double)",
                "mouse_move (coordinates)",
                "type_text (keystroke injection)",
                "hotkey (Ctrl+S, Alt+Tab, Win+R)",
                "scroll (mouse wheel delta)",
                "drag (smooth coordinate drag)",
                "activate_window (focus & restore)",
            ],
        }
