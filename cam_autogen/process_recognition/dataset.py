"""M1 工艺识别精度验证数据集（60 个清晰标注工业零件 + 8 个低置信度边界样本）。"""
from __future__ import annotations

from typing import Any, Dict, List


def _mill(pid: str, mat: str, x: float, y: float, z: float, feats: List[Dict[str, Any]],
          stock_type: str = "block", tol: float = 0.05, ra: float = 3.2) -> Dict[str, Any]:
    return {
        "label": "MILLING",
        "workpiece": {
            "part_id": pid,
            "material": {"name": mat},
            "envelope": {"type": "prismatic", "x": x, "y": y, "z": z},
            "stock": {"type": stock_type, "x": x + 4, "y": y + 4, "z": z + 8},
            "features": feats,
            "general_tolerance_mm": tol,
            "general_ra_um": ra,
        },
    }


def _turn(pid: str, mat: str, d: float, L: float, feats: List[Dict[str, Any]],
          stock_type: str = "bar", tol: float = 0.05, ra: float = 3.2) -> Dict[str, Any]:
    return {
        "label": "TURNING",
        "workpiece": {
            "part_id": pid,
            "material": {"name": mat},
            "envelope": {"type": "cylindrical", "diameter": d, "length": L},
            "stock": {"type": stock_type, "diameter": d + 4, "length": L + 30},
            "features": feats,
            "general_tolerance_mm": tol,
            "general_ra_um": ra,
        },
    }


def _tm(pid: str, mat: str, d: float, L: float, feats: List[Dict[str, Any]],
        tol: float = 0.05, ra: float = 3.2) -> Dict[str, Any]:
    return {
        "label": "TURN_MILL",
        "workpiece": {
            "part_id": pid,
            "material": {"name": mat},
            "envelope": {"type": "cylindrical", "diameter": d, "length": L},
            "stock": {"type": "bar", "diameter": d + 5, "length": L + 35},
            "features": feats,
            "general_tolerance_mm": tol,
            "general_ra_um": ra,
        },
    }


def build_benchmark_dataset() -> List[Dict[str, Any]]:
    ds: List[Dict[str, Any]] = []

    # ---- 20 个单一铣削零件 ----
    ds.extend([
        _mill("M01", "6061-T6", 120, 80, 30, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 1.0}},
            {"id": "F2", "type": "pocket", "params": {"x": 60, "y": 40, "length": 50, "width": 30, "depth": 8}},
        ]),
        _mill("M02", "C45", 200, 150, 40, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 0.5}},
            {"id": "F2", "type": "hole", "params": {"x": 30, "y": 30, "diameter": 10, "depth": 20}},
            {"id": "F3", "type": "hole", "params": {"x": 170, "y": 120, "diameter": 10, "depth": 20}},
        ]),
        _mill("M03", "7075-T6", 160, 100, 25, [
            {"id": "F1", "type": "pocket", "params": {"x": 80, "y": 50, "length": 100, "width": 60, "depth": 12, "corner_radius": 8}},
            {"id": "F2", "type": "slot", "params": {"x1": 20, "y1": 20, "x2": 140, "y2": 20, "width": 8, "depth": 5}},
        ]),
        _mill("M04", "SUS304", 100, 100, 20, [
            {"id": "F1", "type": "contour", "params": {"x": 50, "y": 50, "length": 60, "width": 60, "depth": 8}},
            {"id": "F2", "type": "thread_hole", "params": {"x": 20, "y": 20, "diameter": 8, "depth": 15, "pitch": 1.25}},
        ], stock_type="plate"),
        _mill("M05", "HT250", 250, 180, 50, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 2.0}},
            {"id": "F2", "type": "bore_axial", "params": {"x": 125, "y": 90, "diameter": 45, "depth": 35}},
            {"id": "F3", "type": "thread_hole", "params": {"x": 40, "y": 40, "diameter": 10, "depth": 20, "pitch": 1.5}},
        ], stock_type="casting"),
        _mill("M06", "42CrMo", 90, 70, 35, [
            {"id": "F1", "type": "keyway", "params": {"x1": 15, "y1": 35, "x2": 75, "y2": 35, "width": 12, "depth": 6}},
        ]),
        _mill("M07", "6061-T6", 300, 200, 18, [
            {"id": "F1", "type": "pocket", "params": {"x": 150, "y": 100, "length": 220, "width": 140, "depth": 10, "corner_radius": 6}},
            {"id": "F2", "type": "hole", "params": {"x": 20, "y": 20, "diameter": 6, "depth": 18}},
        ], stock_type="plate", ra_um=1.6) if False else _mill("M07", "6061-T6", 300, 200, 18, [
            {"id": "F1", "type": "pocket", "params": {"x": 150, "y": 100, "length": 220, "width": 140, "depth": 10, "corner_radius": 6}},
            {"id": "F2", "type": "hole", "params": {"x": 20, "y": 20, "diameter": 6, "depth": 18}},
        ], stock_type="plate", ra=1.6),
        _mill("M08", "Q235", 140, 90, 28, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 1.0}},
            {"id": "F2", "type": "slot", "params": {"x1": 30, "y1": 45, "x2": 110, "y2": 45, "width": 10, "depth": 8}},
            {"id": "F3", "type": "chamfer_edge", "params": {"size": 1.0}},
        ]),
        _mill("M09", "H62", 80, 60, 15, [
            {"id": "F1", "type": "pocket", "params": {"x": 40, "y": 30, "length": 40, "width": 24, "depth": 5}},
            {"id": "F2", "type": "hole", "params": {"x": 15, "y": 15, "diameter": 4, "depth": 10}},
        ]),
        _mill("M10", "Ti6Al4V", 110, 85, 22, [
            {"id": "F1", "type": "contour", "params": {"x": 55, "y": 42, "length": 80, "width": 55, "depth": 12}},
            {"id": "F2", "type": "hole", "params": {"x": 55, "y": 42, "diameter": 12, "depth": 22}},
        ], tol=0.02, ra=0.8),
        _mill("M11", "C45", 150, 120, 30, [
            {"id": "F1", "type": "hole", "params": {"x": 30, "y": 30, "diameter": 8, "depth": 25}},
            {"id": "F2", "type": "hole", "params": {"x": 120, "y": 30, "diameter": 8, "depth": 25}},
            {"id": "F3", "type": "hole", "params": {"x": 120, "y": 90, "diameter": 8, "depth": 25}},
        ]),
        _mill("M12", "6061-T6", 180, 140, 45, [
            {"id": "F1", "type": "pocket", "params": {"x": 90, "y": 70, "length": 120, "width": 90, "depth": 20}},
        ]),
        _mill("M13", "SUS304", 75, 75, 20, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 1.0}},
            {"id": "F2", "type": "thread_hole", "params": {"x": 37.5, "y": 37.5, "diameter": 10, "depth": 16, "pitch": 1.5}},
        ]),
        _mill("M14", "42CrMo", 210, 130, 55, [
            {"id": "F1", "type": "slot", "params": {"x1": 20, "y1": 65, "x2": 190, "y2": 65, "width": 16, "depth": 10}},
            {"id": "F2", "type": "bore_axial", "params": {"x": 105, "y": 65, "diameter": 32, "depth": 40}},
        ]),
        _mill("M15", "7075-T6", 130, 95, 26, [
            {"id": "F1", "type": "pocket", "params": {"x": 65, "y": 47, "length": 80, "width": 50, "depth": 14, "corner_radius": 6}},
            {"id": "F2", "type": "thread_hole", "params": {"x": 15, "y": 15, "diameter": 5, "depth": 12, "pitch": 0.8}},
        ]),
        _mill("M16", "HT250", 190, 160, 42, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 1.5}},
            {"id": "F2", "type": "hole", "params": {"x": 50, "y": 50, "diameter": 14, "depth": 30}},
        ]),
        _mill("M17", "Q235", 100, 50, 20, [
            {"id": "F1", "type": "slot", "params": {"x1": 10, "y1": 25, "x2": 90, "y2": 25, "width": 12, "depth": 6}},
        ]),
        _mill("M18", "C45", 110, 110, 32, [
            {"id": "F1", "type": "contour", "params": {"x": 55, "y": 55, "length": 70, "width": 70, "depth": 10}},
            {"id": "F2", "type": "hole", "params": {"x": 55, "y": 55, "diameter": 16, "depth": 32}},
        ]),
        _mill("M19", "6061-T6", 60, 40, 15, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 0.5}},
            {"id": "F2", "type": "pocket", "params": {"x": 30, "y": 20, "length": 36, "width": 20, "depth": 6}},
        ]),
        _mill("M20", "42CrMo", 170, 115, 38, [
            {"id": "F1", "type": "planar_face", "params": {"depth": 1.0}},
            {"id": "F2", "type": "slot", "params": {"x1": 30, "y1": 30, "x2": 140, "y2": 30, "width": 10, "depth": 6}},
            {"id": "F3", "type": "hole", "params": {"x": 85, "y": 80, "diameter": 12, "depth": 25}},
        ]),
    ])

    # ---- 20 个单一车削零件 ----
    ds.extend([
        _turn("T01", "C45", 40, 80, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 32, "z_start": 0, "z_end": -40}},
            {"id": "F3", "type": "od_cylinder", "params": {"diameter": 40, "z_start": -40, "z_end": -80}},
        ]),
        _turn("T02", "42CrMo", 50, 110, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 36, "z_start": 0, "z_end": -50}},
            {"id": "F3", "type": "groove_od", "params": {"diameter": 32, "width": 3, "z": -48}},
            {"id": "F4", "type": "thread_od", "params": {"diameter": 36, "pitch": 1.5, "z_start": 0, "z_end": -20}},
        ]),
        _turn("T03", "SUS304", 60, 45, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 58, "z_start": 0, "z_end": -45}},
            {"id": "F3", "type": "bore_axial", "params": {"diameter": 24, "depth": 45}, "on_axis": True},
        ], stock_type="tube"),
        _turn("T04", "6061-T6", 35, 70, [
            {"id": "F1", "type": "od_taper", "params": {"d_start": 20, "d_end": 35, "z_start": 0, "z_end": -35}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 35, "z_start": -35, "z_end": -70}},
        ]),
        _turn("T05", "C45", 80, 30, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 76, "z_start": 0, "z_end": -30}},
            {"id": "F3", "type": "bore_axial", "params": {"diameter": 30, "depth": 30}, "on_axis": True, "ra_um": 1.6},
        ]),
        _turn("T06", "H62", 28, 60, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 22, "z_start": 0, "z_end": -25}},
            {"id": "F2", "type": "thread_od", "params": {"diameter": 22, "pitch": 1.0, "z_start": 0, "z_end": -15}},
            {"id": "F3", "type": "chamfer_od", "params": {"size": 1.0, "z": 0}},
        ]),
        _turn("T07", "42CrMo", 65, 140, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 45, "z_start": 0, "z_end": -60}},
            {"id": "F3", "type": "od_cylinder", "params": {"diameter": 65, "z_start": -60, "z_end": -140}},
            {"id": "F4", "type": "hole", "params": {"diameter": 10, "depth": 25}, "on_axis": True},
        ]),
        _turn("T08", "HT250", 120, 40, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 115, "z_start": 0, "z_end": -40}},
            {"id": "F3", "type": "groove_od", "params": {"diameter": 105, "width": 5, "z": -20}},
        ]),
        _turn("T09", "Ti6Al4V", 30, 55, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 25, "z_start": 0, "z_end": -30}, "tol": 0.02, "ra_um": 0.8}
            if False else {"id": "F1", "type": "od_cylinder", "params": {"diameter": 25, "z_start": 0, "z_end": -30}, "tolerance_mm": 0.02, "ra_um": 0.8},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 30, "z_start": -30, "z_end": -55}},
        ]),
        _turn("T10", "Q235", 45, 90, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 40, "z_start": 0, "z_end": -90}},
            {"id": "F3", "type": "bore_axial", "params": {"diameter": 16, "depth": 50}, "on_axis": True},
        ]),
        _turn("T11", "SUS304", 36, 75, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 30, "z_start": 0, "z_end": -40}},
            {"id": "F2", "type": "groove_od", "params": {"diameter": 25, "width": 3, "z": -35}},
        ]),
        _turn("T12", "C45", 55, 100, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_taper", "params": {"d_start": 30, "d_end": 55, "z_start": 0, "z_end": -50}},
            {"id": "F3", "type": "od_cylinder", "params": {"diameter": 55, "z_start": -50, "z_end": -100}},
        ]),
        _turn("T13", "7075-T6", 42, 65, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 38, "z_start": 0, "z_end": -65}},
            {"id": "F2", "type": "thread_hole", "params": {"diameter": 12, "depth": 20, "pitch": 1.75}, "on_axis": True},
        ]),
        _turn("T14", "42CrMo", 70, 120, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 50, "z_start": 0, "z_end": -55}},
            {"id": "F3", "type": "od_cylinder", "params": {"diameter": 70, "z_start": -55, "z_end": -120}},
            {"id": "F4", "type": "chamfer_od", "params": {"size": 1.5, "z": 0}},
        ]),
        _turn("T15", "C45", 25, 50, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 20, "z_start": 0, "z_end": -30}},
            {"id": "F2", "type": "thread_od", "params": {"diameter": 20, "pitch": 1.5, "z_start": 0, "z_end": -22}},
        ]),
        _turn("T16", "6061-T6", 90, 35, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 85, "z_start": 0, "z_end": -35}},
            {"id": "F3", "type": "bore_axial", "params": {"diameter": 40, "depth": 35}, "on_axis": True},
        ], stock_type="tube"),
        _turn("T17", "H62", 32, 48, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 28, "z_start": 0, "z_end": -48}},
            {"id": "F3", "type": "groove_od", "params": {"diameter": 24, "width": 2.5, "z": -15}},
        ]),
        _turn("T18", "SUS304", 48, 85, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 42, "z_start": 0, "z_end": -45}},
            {"id": "F2", "type": "bore_axial", "params": {"diameter": 18, "depth": 40}, "on_axis": True},
        ]),
        _turn("T19", "Q235", 60, 105, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 52, "z_start": 0, "z_end": -105}},
            {"id": "F3", "type": "chamfer_od", "params": {"size": 1.0, "z": 0}},
        ]),
        _turn("T20", "42CrMo", 38, 72, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 34, "z_start": 0, "z_end": -72}},
            {"id": "F2", "type": "hole", "params": {"diameter": 8, "depth": 20}, "on_axis": True},
        ]),
    ])

    # ---- 20 个车铣复合零件 ----
    ds.extend([
        _tm("TM01", "42CrMo", 50, 100, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 40, "z_start": 0, "z_end": -50}},
            {"id": "F3", "type": "keyway", "params": {"length": 30, "width": 10, "depth": 5, "z_center": -25, "angle": 0}},
        ]),
        _tm("TM02", "SUS304", 100, 25, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 96, "z_start": 0, "z_end": -25}},
            {"id": "F3", "type": "bore_axial", "params": {"diameter": 30, "depth": 25}, "on_axis": True},
            {"id": "F4", "type": "hole", "on_axis": False, "params": {"radius": 38, "angle": 0, "diameter": 9, "depth": 25}},
        ]),
        _tm("TM03", "C45", 45, 90, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 38, "z_start": 0, "z_end": -45}},
            {"id": "F2", "type": "cross_hole", "params": {"diameter": 8, "z": -65, "angle": 90, "through": 1}},
        ]),
        _tm("TM04", "6061-T6", 60, 80, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 55, "z_start": 0, "z_end": -80}},
            {"id": "F2", "type": "polygon", "params": {"sides": 6, "across_flats": 46, "length": 20, "z_center": -15}},
        ]),
        _tm("TM05", "42CrMo", 55, 110, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 42, "z_start": 0, "z_end": -50}},
            {"id": "F3", "type": "flat", "params": {"length": 25, "depth": 3, "z_center": -25, "angle": 0}},
            {"id": "F4", "type": "thread_od", "params": {"diameter": 42, "pitch": 1.5, "z_start": 0, "z_end": -15}},
        ]),
        _tm("TM06", "SUS304", 75, 60, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 70, "z_start": 0, "z_end": -60}},
            {"id": "F2", "type": "slot", "params": {"length": 25, "width": 8, "depth": 4, "z_center": -30, "angle": 0}},
        ]),
        _tm("TM07", "C45", 80, 40, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 76, "z_start": 0, "z_end": -40}},
            {"id": "F3", "type": "thread_hole", "on_axis": False, "params": {"radius": 28, "angle": 45, "diameter": 8, "depth": 15}},
        ]),
        _tm("TM08", "7075-T6", 40, 85, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 34, "z_start": 0, "z_end": -40}},
            {"id": "F2", "type": "keyway", "params": {"length": 20, "width": 8, "depth": 4, "z_center": -20, "angle": 0}},
            {"id": "F3", "type": "cross_hole", "params": {"diameter": 5, "z": -60, "angle": 0, "through": 1}},
        ]),
        _tm("TM09", "Ti6Al4V", 36, 70, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 32, "z_start": 0, "z_end": -70}},
            {"id": "F2", "type": "planar_face", "params": {"depth": 2.0, "length": 20, "z_center": -15}},
        ]),
        _tm("TM10", "H62", 50, 50, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 45, "z_start": 0, "z_end": -50}},
            {"id": "F2", "type": "groove_od", "params": {"diameter": 40, "width": 3, "z": -25}},
            {"id": "F3", "type": "polygon", "params": {"sides": 6, "across_flats": 36, "length": 15, "z_center": -8}},
        ]),
        _tm("TM11", "42CrMo", 64, 120, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 50, "z_start": 0, "z_end": -60}},
            {"id": "F2", "type": "keyway", "params": {"length": 35, "width": 12, "depth": 5, "z_center": -30, "angle": 0}},
        ]),
        _tm("TM12", "C45", 90, 35, [
            {"id": "F1", "type": "face", "params": {}},
            {"id": "F2", "type": "od_cylinder", "params": {"diameter": 88, "z_start": 0, "z_end": -35}},
            {"id": "F3", "type": "hole", "on_axis": False, "params": {"radius": 32, "angle": 0, "diameter": 10, "depth": 35}},
        ]),
        _tm("TM13", "SUS304", 42, 95, [
            {"id": "F1", "type": "od_taper", "params": {"d_start": 28, "d_end": 42, "z_start": 0, "z_end": -45}},
            {"id": "F2", "type": "cross_hole", "params": {"diameter": 6, "z": -70, "angle": 180, "through": 1}},
        ]),
        _tm("TM14", "6061-T6", 70, 55, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 64, "z_start": 0, "z_end": -55}},
            {"id": "F2", "type": "pocket", "params": {"length": 20, "width": 12, "depth": 5, "z_center": -28, "angle": 0}},
        ]),
        _tm("TM15", "Q235", 52, 88, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 46, "z_start": 0, "z_end": -88}},
            {"id": "F2", "type": "flat", "params": {"length": 30, "depth": 3, "z_center": -20, "angle": 0}},
        ]),
        _tm("TM16", "42CrMo", 48, 76, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 40, "z_start": 0, "z_end": -40}},
            {"id": "F2", "type": "thread_od", "params": {"diameter": 40, "pitch": 1.5, "z_start": 0, "z_end": -15}},
            {"id": "F3", "type": "cross_hole", "params": {"diameter": 5, "z": -60, "angle": 90, "through": 0, "depth": 12}},
        ]),
        _tm("TM17", "C45", 110, 30, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 105, "z_start": 0, "z_end": -30}},
            {"id": "F2", "type": "bore_axial", "params": {"diameter": 40, "depth": 30}, "on_axis": True},
            {"id": "F3", "type": "hole", "on_axis": False, "params": {"radius": 42, "angle": 60, "diameter": 11, "depth": 30}},
        ]),
        _tm("TM18", "7075-T6", 38, 68, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 34, "z_start": 0, "z_end": -68}},
            {"id": "F2", "type": "keyway", "params": {"length": 24, "width": 8, "depth": 4, "z_center": -24, "angle": 0}},
        ]),
        _tm("TM19", "SUS304", 58, 82, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 54, "z_start": 0, "z_end": -82}},
            {"id": "F2", "type": "polygon", "params": {"sides": 4, "across_flats": 42, "length": 18, "z_center": -12}},
        ]),
        _tm("TM20", "C45", 66, 94, [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 58, "z_start": 0, "z_end": -50}},
            {"id": "F2", "type": "slot", "params": {"length": 28, "width": 10, "depth": 5, "z_center": -25, "angle": 90}},
        ]),
    ])

    # ---- 8 个低置信度模糊/冲突边界样本（应被 <0.90 门标出并触发异常处理） ----
    ds.extend([
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-01", "material": {"name": "C45"},
                "envelope": {"type": "cylindrical", "diameter": 30, "length": 40},
                "stock": {"type": "block", "x": 35, "y": 35, "z": 45},
                "features": [{"id": "F1", "type": "chamfer_od", "params": {"size": 0.5, "z": 0}},
                             {"id": "F2", "type": "chamfer_edge", "params": {"size": 0.5}}],
            },
        },
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-02", "material": {"name": "6061-T6"},
                "envelope": {"type": "cylindrical", "diameter": 150, "length": 8},
                "stock": {"type": "plate", "x": 160, "y": 160, "z": 10},
                "features": [{"id": "F1", "type": "chamfer_od", "params": {"size": 0.5, "z": 0}},
                             {"id": "F2", "type": "planar_face", "params": {"depth": 0.1}}],
            },
        },
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-03", "material": {"name": "C45"},
                "envelope": {"type": "prismatic", "x": 60, "y": 60, "z": 30},
                "stock": {"type": "bar", "diameter": 85, "length": 35},
                "features": [{"id": "F1", "type": "od_cylinder", "params": {"diameter": 40, "z_start": 0, "z_end": -10}}],
            },
        },
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-04", "material": {"name": "SUS304"},
                "envelope": {"type": "cylindrical", "diameter": 50, "length": 60},
                "stock": {"type": "bar", "diameter": 55, "length": 90},
                "features": [{"id": "F1", "type": "od_cylinder", "params": {"diameter": 48, "z_start": 0, "z_end": -60}},
                             {"id": "F2", "type": "chamfer_edge", "params": {"size": 0.5}}],
            },
        },
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-05", "material": {"name": "42CrMo"},
                "envelope": {"type": "prismatic", "x": 80, "y": 80, "z": 40},
                "stock": {"type": "bar", "diameter": 115, "length": 45},
                "features": [{"id": "F1", "type": "od_taper", "params": {"d_start": 30, "d_end": 50, "z_start": 0, "z_end": -20}}],
            },
        },
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-06", "material": {"name": "6061-T6"},
                "envelope": {"type": "cylindrical", "diameter": 180, "length": 10},
                "stock": {"type": "block", "x": 190, "y": 190, "z": 12},
                "features": [{"id": "F1", "type": "planar_face", "params": {"depth": 0.2}},
                             {"id": "F2", "type": "chamfer_edge", "params": {"size": 0.3}}],
            },
        },
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-07", "material": {"name": "C45"},
                "envelope": {"type": "prismatic", "x": 50, "y": 50, "z": 25},
                "stock": {"type": "block", "x": 55, "y": 55, "z": 30},
                "features": [{"id": "F1", "type": "chamfer_od", "params": {"size": 1.0, "z": 0}},
                             {"id": "F2", "type": "od_cylinder", "params": {"diameter": 30, "z_start": 0, "z_end": -10}}],
            },
        },
        {
            "label": "AMBIGUOUS",
            "workpiece": {
                "part_id": "AMB-08", "material": {"name": "H62"},
                "envelope": {"type": "cylindrical", "diameter": 60, "length": 30},
                "stock": {"type": "block", "x": 65, "y": 65, "z": 35},
                "features": [{"id": "F1", "type": "planar_face", "params": {"depth": 0.2}},
                             {"id": "F2", "type": "chamfer_od", "params": {"size": 0.5, "z": 0}}],
            },
        },
    ])
    return ds
