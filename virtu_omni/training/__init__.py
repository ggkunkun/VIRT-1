# -*- coding: utf-8 -*-
"""virtu_omni/training — Training, Alignment, and RLVR Optimization Modules."""

from virtu_omni.training.rlvr_grpo_engine import (
    VirtuGRPOEngine,
    PhysicalRewardEnvironment,
    TrajectoryCandidate,
)

__all__ = [
    "VirtuGRPOEngine",
    "PhysicalRewardEnvironment",
    "TrajectoryCandidate",
]
