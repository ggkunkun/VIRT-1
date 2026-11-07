"""Virtu Omni x Paperclip Control Plane & Multi-Agent Governance.

Integrates corporate org charts, heartbeat wakeups, atomic task checkouts,
governance approval gates, and token budget management for AI agent fleets.
"""

from virtu_omni.paperclip.adapter import VirtuPaperclipAdapter
from virtu_omni.paperclip.control_plane import (
    AgentProfile,
    ApprovalRequest,
    ApprovalStatus,
    PaperclipControlPlane,
    PaperclipTask,
    TaskDocument,
    TaskPriority,
    TaskStatus,
)
from virtu_omni.paperclip.heartbeat import (
    HeartbeatExecutionResult,
    HeartbeatWakeContext,
    PaperclipHeartbeatRunner,
)

__all__ = [
    "VirtuPaperclipAdapter",
    "PaperclipControlPlane",
    "PaperclipHeartbeatRunner",
    "PaperclipTask",
    "TaskStatus",
    "TaskPriority",
    "AgentProfile",
    "ApprovalRequest",
    "ApprovalStatus",
    "TaskDocument",
    "HeartbeatWakeContext",
    "HeartbeatExecutionResult",
]
