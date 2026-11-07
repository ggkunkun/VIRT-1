"""Virtu-Omni-10B Harness² Integration Package.

Provides seamless integration between Virtu Foundation Models and Google Research's Harness²
(Recursive Agent Harnessing for an Open World, arXiv:2610.14224):
- VIRTU_SURFACE: 8 editable harness components schema.
- VirtuSubstrate: Model execution substrate for Harness².
- VirtuHarnessAdapter: Benchmark and evaluation adapter.
- VirtuProposer: Recursive Propose-Probe-Compose and experience accumulation engine.
"""

from .surface import (
    VIRTU_SURFACE,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_GUARDRAILS,
    DEFAULT_LONG_TERM_MEMORY,
    DEFAULT_TOOL_GUIDANCE,
    build_default_virtu_harness,
)
from .substrate import VirtuSubstrate
from .adapter import VirtuHarnessAdapter, VIRTU_BENCH_TASKS
from .proposer import VirtuProposer

__all__ = [
    "VIRTU_SURFACE",
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_GUARDRAILS",
    "DEFAULT_LONG_TERM_MEMORY",
    "DEFAULT_TOOL_GUIDANCE",
    "build_default_virtu_harness",
    "VirtuSubstrate",
    "VirtuHarnessAdapter",
    "VIRTU_BENCH_TASKS",
    "VirtuProposer",
]
