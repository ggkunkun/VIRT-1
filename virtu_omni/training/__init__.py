# -*- coding: utf-8 -*-
"""virtu_omni/training — Training, Alignment, and RLVR Optimization Modules.

Public names are resolved lazily (PEP 562) so that importing any leaf module of
this package does not drag the PyTorch-dependent GRPO engine into the import
graph. Before this change, an inference-only interpreter (no torch) could not
import anything that merely passed through ``virtu_omni.training``.
"""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "VirtuGRPOEngine": ".rlvr_grpo_engine",
    "PhysicalRewardEnvironment": ".rlvr_grpo_engine",
    "TrajectoryCandidate": ".rlvr_grpo_engine",
    "TORCH_AVAILABLE": ".rlvr_grpo_engine",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value  # cache so later lookups skip __getattr__
    return value


def __dir__():
    return sorted(__all__)
