"""Virtu-Omni-10B: Universal Multimodal Foundation Model.

Public exports are lazy. Importing ``virtu_omni.engine`` must not drag in the
training stack (torch/transformers) just to reach the CAD/CAM engine.
"""

from __future__ import annotations

import importlib

__version__ = "1.0.0"
__author__ = "Virtu Multimodal Architecture Team"
__all__ = [
    "VirtuOmniConfig",
    "VirtuOmni10B",
    "BaseParameterExpander",
    "AlignmentValidator",
    "StreamingMultimodalDataPipeline",
    "Distributed3DTrainer",
    "TrainingHealthMonitor",
    "StandardizedSmeltBundle",
    "StandardizedSmeltTokenizer",
    "load_standardized_bundle",
    "VirtuSuperAgent",
    "SuperAgent",
]

_LAZY = {
    "virtu_omni.config": ("VirtuOmniConfig",),
    "virtu_omni.models.architecture": ("VirtuOmni10B",),
    "virtu_omni.models.expander": ("BaseParameterExpander",),
    "virtu_omni.alignment.aligner": ("AlignmentValidator",),
    "virtu_omni.data.pipeline": ("StreamingMultimodalDataPipeline",),
    "virtu_omni.training.trainer": ("Distributed3DTrainer",),
    "virtu_omni.training.monitor": ("TrainingHealthMonitor",),
    "virtu_omni.models.smelt_loader": (
        "StandardizedSmeltBundle", "StandardizedSmeltTokenizer",
        "load_standardized_bundle",
    ),
    "virtu_omni.agent.super_agent": ("VirtuSuperAgent", "SuperAgent"),
}

_NAME_TO_MODULE = {
    name: module
    for module, names in _LAZY.items()
    for name in names
}


def __getattr__(name):
    module_name = _NAME_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
