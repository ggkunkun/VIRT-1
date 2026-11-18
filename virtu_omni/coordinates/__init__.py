"""Shared, evidence-aware coordinate frame utilities."""

from .frames import (
    CoordinateContractError,
    CoordinateFrame,
    FrameGraph,
    apply_point,
    convert_length,
    identity4,
    inverse_rigid,
    multiply4,
    unit_scale_to_mm,
)
from .runtime import get_coordinate_profile, transform_snapshot_points, validate_coordinate_snapshot

__all__ = [
    "CoordinateContractError", "CoordinateFrame", "FrameGraph",
    "apply_point", "convert_length", "identity4", "inverse_rigid",
    "multiply4", "unit_scale_to_mm", "get_coordinate_profile",
    "transform_snapshot_points", "validate_coordinate_snapshot",
]
