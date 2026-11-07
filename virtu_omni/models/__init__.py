# -*- coding: utf-8 -*-
"""virtu_omni models package."""

from .architecture import VirtuOmni10B, VirtuRMSNorm, VirtuSwiGLU, UniRoPE, VirtuAttention
from .operator_optimizer import VirtuOperatorOptimizer, OperatorOptimizationReport
from .loop import (
    LoopRMSNorm,
    LoopStateGate,
    LoopStepController,
    LoopConvergenceCriterion,
    LoopStateCache,
)
from .expander import BaseParameterExpander
from .geometry_token_bridge import (
    GeometryTokenBridge,
    GeometryFeatureProjector,
    GEOMETRY_SPECIAL_TOKENS,
)

__all__ = [
    "VirtuOmni10B",
    "VirtuRMSNorm",
    "VirtuSwiGLU",
    "UniRoPE",
    "LoopRMSNorm",
    "LoopStateGate",
    "LoopStepController",
    "LoopConvergenceCriterion",
    "LoopStateCache",
    "BaseParameterExpander",
    "GeometryTokenBridge",
    "GeometryFeatureProjector",
    "GEOMETRY_SPECIAL_TOKENS",
]
