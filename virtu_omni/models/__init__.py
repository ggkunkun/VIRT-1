# -*- coding: utf-8 -*-
"""virtu_omni models package.

Public names are resolved lazily (PEP 562). Every submodule of this package
(architecture, loop, expander, operator_optimizer, geometry_token_bridge,
deepseek_moe_architecture) imports PyTorch at module scope, so an eager
re-export here made ``import virtu_omni.models.<anything>`` fail on hosts
without torch — including inference-only toolchain paths that never touch a
tensor. Lazy resolution keeps ``from virtu_omni.models import X`` working while
paying the import cost only for the submodule that actually defines ``X``.
"""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    # .architecture
    "VirtuOmni10B": ".architecture",
    "VirtuRMSNorm": ".architecture",
    "VirtuSwiGLU": ".architecture",
    "UniRoPE": ".architecture",
    "VirtuAttention": ".architecture",
    "MultiTokenPredictionModule": ".architecture",
    "PRMValueHead": ".architecture",
    # .deepseek_moe_architecture
    "VirtuDeepSeekMoELayer": ".deepseek_moe_architecture",
    # .operator_optimizer
    "VirtuOperatorOptimizer": ".operator_optimizer",
    "OperatorOptimizationReport": ".operator_optimizer",
    # .loop
    "LoopRMSNorm": ".loop",
    "LoopStateGate": ".loop",
    "LoopStepController": ".loop",
    "LoopConvergenceCriterion": ".loop",
    "LoopStateCache": ".loop",
    # .expander
    "BaseParameterExpander": ".expander",
    # .geometry_token_bridge
    "GeometryTokenBridge": ".geometry_token_bridge",
    "GeometryFeatureProjector": ".geometry_token_bridge",
    "GEOMETRY_SPECIAL_TOKENS": ".geometry_token_bridge",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is not None:
        value = getattr(import_module(module_name, __name__), name)
        globals()[name] = value  # cache so later lookups skip __getattr__
        return value
    # Backwards compatibility: ``virtu_omni.models.architecture`` style access
    # used to work because __init__ imported the submodules eagerly.
    if not name.startswith("_"):
        try:
            module = import_module(f".{name}", __name__)
        except ModuleNotFoundError:
            module = None
        if module is not None:
            globals()[name] = module
            return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
