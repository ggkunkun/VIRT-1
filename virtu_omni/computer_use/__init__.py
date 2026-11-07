"""Virtu Omni x Computer Use Desktop Automation Engine.

Full Perception-Reasoning-Action loop, native Win32 window discovery,
coordinate mouse/keyboard control, and integration with windows-mcp.
"""

from virtu_omni.computer_use.action import ActionEngine
from virtu_omni.computer_use.adapter import VirtuComputerUse
from virtu_omni.computer_use.perception import PerceptionEngine

__all__ = [
    "VirtuComputerUse",
    "PerceptionEngine",
    "ActionEngine",
]
