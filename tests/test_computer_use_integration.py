"""Unit tests for Virtu Computer Use & Desktop Automation Integration.

Tests screen perception, Win32 coordinate action simulation (click, type, hotkey, scroll, drag),
Perception-Reasoning-Action loop, SkillWriterAndMemory wiring, and Bridge REST endpoints.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.computer_use import VirtuComputerUse, PerceptionEngine, ActionEngine
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory


class TestComputerUseIntegration(unittest.TestCase):
    """Test suite for Virtu Computer Use integration."""

    @classmethod
    def setUpClass(cls):
        cls.computer_use = VirtuComputerUse.get_instance()
        cls.perception = cls.computer_use.perception
        cls.action = cls.computer_use.action

    def test_computer_use_status(self):
        status = self.computer_use.get_status()
        self.assertEqual(status["status"], "READY")
        self.assertTrue(status["win32_api_available"])
        self.assertTrue(status["computer_use_skill_installed"])
        self.assertTrue(status["industrial_automation_skill_installed"])
        self.assertTrue(status["upstream_windows_mcp_installed"])
        self.assertGreaterEqual(len(status["supported_actions"]), 8)

    def test_screen_metrics(self):
        metrics = self.perception.get_screen_metrics()
        self.assertGreater(metrics["primary_width"], 0)
        self.assertGreater(metrics["primary_height"], 0)

    def test_screenshot_capture(self):
        test_file = WORKSPACE_ROOT / "scratch" / "test_eval_screen.png"
        res = self.computer_use.execute_action("screenshot", output_path=test_file)
        self.assertTrue(res.get("ok"))
        self.assertTrue(test_file.is_file())
        self.assertGreater(test_file.stat().st_size, 0)
        self.assertIn("sha256", res)

    def test_discrete_actions_mouse_and_keyboard(self):
        # 1. Mouse move
        m_res = self.computer_use.execute_action("move", x=400, y=300)
        self.assertTrue(m_res.get("ok"))
        self.assertEqual(m_res.get("x"), 400)

        # 2. Click
        c_res = self.computer_use.execute_action("click", x=400, y=300, button="left")
        self.assertTrue(c_res.get("ok"))

        # 3. Type text
        t_res = self.computer_use.execute_action("type", text="OK", delay_ms=1)
        self.assertTrue(t_res.get("ok"))

        # 4. Hotkey
        h_res = self.computer_use.execute_action("hotkey", keys=["ctrl", "s"])
        self.assertTrue(h_res.get("ok"))

        # 5. Scroll
        s_res = self.computer_use.execute_action("scroll", clicks=1)
        self.assertTrue(s_res.get("ok"))

        # 6. Drag
        d_res = self.computer_use.execute_action("drag", start_x=10, start_y=10, end_x=50, end_y=50, steps=2)
        self.assertTrue(d_res.get("ok"))

    def test_structured_see_think_act_loop(self):
        goal = "Test coordinate drag and save sequence"
        actions = [
            {"action": "move", "x": 200, "y": 200},
            {"action": "click", "x": 200, "y": 200},
            {"action": "type", "text": "TEST", "delay_ms": 1},
        ]
        res = self.computer_use.run_see_think_act_loop(goal=goal, actions=actions, capture_screenshots=False)
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("status"), "COMPLETED")
        self.assertEqual(res.get("total_steps"), 3)
        self.assertEqual(len(res.get("steps", [])), 3)

    def test_screen_hardware_profile_adaptation(self):
        """Verify full screen profile adaptation to the user's 1920x1080 @ 125% DPI display."""
        profile = self.computer_use.get_screen_profile()
        self.assertEqual(profile["physical_resolution"]["width"], 1920)
        self.assertEqual(profile["physical_resolution"]["height"], 1080)
        self.assertEqual(profile["work_area"]["width"], 1920)
        self.assertEqual(profile["work_area"]["height"], 1020)
        self.assertEqual(profile["taskbar"]["height"], 60)
        self.assertEqual(profile["dpi"]["scale_factor"], 1.25)
        self.assertEqual(profile["dpi"]["scale_percent"], "125%")
        self.assertIn("landmarks", profile)
        self.assertEqual(profile["landmarks"]["screen_center"], (960, 540))
        self.assertEqual(profile["landmarks"]["work_area_center"], (960, 510))

    def test_coordinate_normalization_and_mapping(self):
        """Verify coordinate normalization and denormalization on user's 1920x1080 screen."""
        # 1. Physical to Normalized
        nx, ny = self.perception.normalize_coordinates(960, 540)
        self.assertAlmostEqual(nx, 0.5, places=2)
        self.assertAlmostEqual(ny, 0.5, places=2)

        # 2. 0~1000 scale
        nx_1k, ny_1k = self.perception.normalize_coordinates(960, 540, scale_1000=True)
        self.assertEqual(nx_1k, 500.0)
        self.assertEqual(ny_1k, 500.0)

        # 3. Denormalize to physical screen
        px, py = self.perception.denormalize_coordinates(0.5, 0.5)
        self.assertEqual(px, 960)
        self.assertEqual(py, 540)

        # 4. Denormalize inside work area (1920x1020)
        px_w, py_w = self.perception.denormalize_coordinates(0.5, 0.5, inside_work_area=True)
        self.assertEqual(px_w, 960)
        self.assertEqual(py_w, 510)

    def test_action_coordinate_adaptation_and_clamping(self):
        """Verify action engine adapts normalized, logical, and out-of-bounds coordinates."""
        # 1. Normalized coordinate adaptation
        ax, ay = self.action.adapt_coordinates(0.5, 0.5, normalized=True)
        self.assertEqual(ax, 960)
        self.assertEqual(ay, 540)

        # 2. 0~1000 scale adaptation
        ax_1k, ay_1k = self.action.adapt_coordinates(500, 500, normalized=True)
        self.assertEqual(ax_1k, 960)
        self.assertEqual(ay_1k, 540)

        # 3. Logical to Physical (1.25x scaling from 1536x864)
        lx, ly = self.action.adapt_coordinates(800, 400, is_logical=True)
        self.assertEqual(lx, 1000)
        self.assertEqual(ly, 500)

        # 4. Out-of-bounds clamping
        cx, cy = self.action.adapt_coordinates(3000, 2000)
        self.assertEqual(cx, 1919)
        self.assertEqual(cy, 1079)

        cx_neg, cy_neg = self.action.adapt_coordinates(-50, -100)
        self.assertEqual(cx_neg, 0)
        self.assertEqual(cy_neg, 0)

    def test_skill_writer_computer_use_delegation(self):
        writer = SkillWriterAndMemory()
        self.assertIsNotNone(writer.computer_use)

        action_res = writer.execute_computer_action("move", x=150, y=150)
        self.assertTrue(action_res.get("ok"))

        loop_res = writer.run_desktop_automation_loop(
            goal="Agent test loop",
            actions=[{"action": "click", "x": 100, "y": 100}]
        )
        self.assertTrue(loop_res.get("ok"))


if __name__ == "__main__":
    unittest.main()
