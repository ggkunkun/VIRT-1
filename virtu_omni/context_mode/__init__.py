"""Virtu Omni x Context Mode.

Context window optimization, sandboxed execution filtering, and SQLite FTS5 session continuity.
"""

from virtu_omni.context_mode.adapter import VirtuContextMode
from virtu_omni.context_mode.optimizer import ContextModeOptimizer, OptimizationResult
from virtu_omni.context_mode.session_db import ContextModeSessionDB, SessionEvent

__all__ = [
    "VirtuContextMode",
    "ContextModeOptimizer",
    "OptimizationResult",
    "ContextModeSessionDB",
    "SessionEvent",
]
