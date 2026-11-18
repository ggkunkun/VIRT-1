"""内置示例工件（也用作测试夹具与 CLI 演示）。"""
from __future__ import annotations

from typing import Any, Dict

STEPPED_SHAFT: Dict[str, Any] = {
    "part_id": "SHAFT-001",
    "material": {"name": "C45", "hardness_hb": 200},
    "envelope": {"type": "cylindrical", "diameter": 40, "length": 80},
    "stock": {"type": "bar", "diameter": 45, "length": 140},
    "features": [
        {"id": "F1", "type": "face", "params": {}, "ra_um": 3.2},
        {"id": "F2", "type": "od_cylinder", "params": {"diameter": 30, "z_start": 0, "z_end": -30},
         "tolerance_mm": 0.021, "ra_um": 1.6},
        {"id": "F3", "type": "od_cylinder", "params": {"diameter": 40, "z_start": -30, "z_end": -80}, "ra_um": 3.2},
        {"id": "F4", "type": "chamfer_od", "params": {"size": 1.0, "z": 0}},
        {"id": "F5", "type": "groove_od", "params": {"diameter": 26, "width": 3, "z": -28.5}},
    ],
    "general_tolerance_mm": 0.1, "general_ra_um": 3.2, "batch_size": 50,
}

KEYED_SHAFT: Dict[str, Any] = {
    "part_id": "SHAFT-KEY-002",
    "material": {"name": "42CrMo", "hardness_hb": 280},
    "envelope": {"type": "cylindrical", "diameter": 50, "length": 100},
    "stock": {"type": "bar", "diameter": 55, "length": 170},
    "features": [
        {"id": "F1", "type": "face", "params": {}},
        {"id": "F2", "type": "od_cylinder", "params": {"diameter": 35, "z_start": 0, "z_end": -45},
         "tolerance_mm": 0.016, "ra_um": 1.6},
        {"id": "F3", "type": "od_cylinder", "params": {"diameter": 50, "z_start": -45, "z_end": -100}},
        {"id": "F4", "type": "keyway", "params": {"length": 30, "width": 10, "depth": 5, "z_center": -22, "angle": 0},
         "tolerance_mm": 0.036},
        {"id": "F5", "type": "cross_hole", "params": {"diameter": 6, "z": -70, "angle": 90, "through": 1}},
        {"id": "F6", "type": "thread_od", "params": {"diameter": 35, "pitch": 1.5, "z_start": 0, "z_end": -12}},
    ],
    "general_tolerance_mm": 0.1, "general_ra_um": 3.2, "batch_size": 20,
}

MILLED_BLOCK: Dict[str, Any] = {
    "part_id": "BLOCK-003",
    "material": {"name": "6061-T6", "hardness_hb": 95},
    "envelope": {"type": "prismatic", "x": 120, "y": 80, "z": 30},
    "stock": {"type": "block", "x": 124, "y": 84, "z": 40},
    "features": [
        {"id": "F1", "type": "planar_face", "params": {"depth": 0.0}, "ra_um": 1.6},
        {"id": "F2", "type": "pocket", "params": {"x": 45, "y": 40, "length": 50, "width": 30, "depth": 8,
                                                     "corner_radius": 5}, "tolerance_mm": 0.04, "ra_um": 1.6},
        {"id": "F3", "type": "hole", "params": {"x": 100, "y": 20, "diameter": 8, "depth": 20}},
        {"id": "F4", "type": "hole", "params": {"x": 100, "y": 60, "diameter": 8, "depth": 20}},
        {"id": "F5", "type": "thread_hole", "params": {"x": 10, "y": 10, "diameter": 6, "depth": 12, "pitch": 1.0}},
        {"id": "F6", "type": "slot", "params": {"x1": 85, "y1": 30, "x2": 85, "y2": 50, "width": 10, "depth": 5}},
        {"id": "F7", "type": "hole", "params": {"x": 10, "y": 70, "diameter": 10, "depth": 15},
         "tolerance_mm": 0.015, "ra_um": 0.8},
    ],
    "general_tolerance_mm": 0.1, "general_ra_um": 3.2, "batch_size": 10,
}

FLANGE_PCD: Dict[str, Any] = {
    "part_id": "FLANGE-004",
    "material": {"name": "SUS304", "hardness_hb": 180},
    "envelope": {"type": "cylindrical", "diameter": 100, "length": 20},
    "stock": {"type": "bar", "diameter": 105, "length": 60},
    "features": [
        {"id": "F1", "type": "face", "params": {}, "ra_um": 1.6},
        {"id": "F2", "type": "od_cylinder", "params": {"diameter": 100, "z_start": 0, "z_end": -20}},
        {"id": "F3", "type": "bore_axial", "params": {"diameter": 30, "depth": 20}, "on_axis": True,
         "tolerance_mm": 0.025, "ra_um": 1.6},
        *[{"id": f"H{k}", "type": "hole", "on_axis": False,
           "params": {"radius": 40, "angle": k * 90.0, "diameter": 9, "depth": 20}} for k in range(4)],
    ],
    "general_tolerance_mm": 0.1, "general_ra_um": 3.2, "batch_size": 30,
}

EXAMPLES = {"shaft": STEPPED_SHAFT, "keyed_shaft": KEYED_SHAFT, "block": MILLED_BLOCK, "flange": FLANGE_PCD}
