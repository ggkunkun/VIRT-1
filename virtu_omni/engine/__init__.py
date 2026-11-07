"""virtu_omni engine public API.

The bridge only needs :class:`WishCADCAMEngine`. Eagerly importing every engine
here also dragged in torch through the humanoid/vision helpers, making a cold
service start take minutes. Keep those exports lazy and backward compatible.
"""
from __future__ import annotations

import importlib

from .wish_cad_cam_engine import WishCADCAMEngine

__all__ = [
    "WishCADCAMEngine",
    "UniversalGeometryEngine",
    "PartFamily",
    "ShaftGeometrySpec",
    "FlangeGeometrySpec",
    "KeywayGeometrySpec",
    "BearingBracketGeometrySpec",
    "SheetMetalBendSpec",
    "UniversalCAEEngine",
    "MaterialProperties",
    "STANDARD_MATERIALS",
    "SheetMetalNestingEngine",
    "NestingPart",
    "SheetStock",
    "HumanoidMouse",
    "HumanoidKeyboard",
    "FastScreenPerception",
    "DeterministicGrounding",
    "human_mouse",
    "human_keyboard",
    "warp_mouse",
    "VisualGroundingEngine",
    "OCRTextGrounder",
    "SetOfMarksDetector",
    "VisualDiffSentinel",
    "ProcessHangSentinel",
    "DialogAutoDismissal",
    "CADViewportNavigator",
    "StepReverseEngine",
    "StepReverseResult",
]

_LAZY = {
    ".step_reverse_engine": (
        "StepReverseEngine", "StepReverseResult",
    ),
    ".humanoid_controller": (
        "HumanoidMouse", "HumanoidKeyboard", "FastScreenPerception",
        "DeterministicGrounding", "human_mouse", "human_keyboard", "warp_mouse",
    ),
    ".visual_grounding_engine": (
        "VisualGroundingEngine", "OCRTextGrounder", "SetOfMarksDetector",
    ),
    ".closed_loop_sentinel": (
        "VisualDiffSentinel", "ProcessHangSentinel", "DialogAutoDismissal",
    ),
    ".cad_viewport_controller": ("CADViewportNavigator",),
    ".universal_geometry_engine": (
        "UniversalGeometryEngine", "PartFamily", "ShaftGeometrySpec",
        "FlangeGeometrySpec", "KeywayGeometrySpec",
        "BearingBracketGeometrySpec", "SheetMetalBendSpec",
    ),
    ".universal_cae_engine": (
        "UniversalCAEEngine", "MaterialProperties", "STANDARD_MATERIALS",
    ),
    ".sheetmetal_nesting_engine": (
        "SheetMetalNestingEngine", "NestingPart", "SheetStock",
    ),
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
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
