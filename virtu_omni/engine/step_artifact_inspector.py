"""Read-only STEP artifact inspection backed by Open Cascade.

This is an integrity check for an already exported STEP file. It does not
infer design intent or replace the CAD, CAE, CAM, or VERICUT acceptance gates.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Dict, List


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count(shape: Any, shape_type: Any, explorer_type: Any) -> int:
    explorer = explorer_type(shape, shape_type)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def inspect_step_artifact(step_path: str) -> Dict[str, Any]:
    """Measure and validate one STEP file without executing user code.

    The result is ``PASS`` only when Open Cascade reads the file, reports a
    valid B-Rep containing at least one solid with positive finite volume, and
    the STEP file declares millimetre length units. This does not prove the
    geometry matches a drawing or is production-ready.
    """
    result: Dict[str, Any] = {
        "tool": "inspect_step_artifact",
        "status": "FAIL",
        "passed": False,
        "verified": False,
        "evidence_status": "insufficient",
        "failures": [],
    }

    try:
        path = Path(str(step_path)).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        result["failures"].append({"code": "STEP_PATH_UNREADABLE", "detail": str(exc)})
        return result

    result["file"] = {"path": str(path)}
    if not path.is_file() or path.suffix.lower() not in {".step", ".stp"}:
        result["failures"].append({
            "code": "STEP_FILE_REQUIRED",
            "detail": "输入必须是现存的 .step 或 .stp 文件。",
        })
        return result

    try:
        before_stat = path.stat()
        before_hash = _sha256(path)
    except OSError as exc:
        result["failures"].append({"code": "STEP_FILE_UNREADABLE", "detail": str(exc)})
        return result

    result["file"].update({
        "size_bytes": before_stat.st_size,
        "sha256": before_hash,
    })
    if before_stat.st_size == 0:
        result["failures"].append({"code": "STEP_FILE_EMPTY", "detail": "文件长度为 0。"})
        return result

    try:
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.BRepGProp import BRepGProp
        from OCP.Bnd import Bnd_Box
        from OCP.GProp import GProp_GProps
        from OCP.IFSelect import IFSelect_ReturnStatus
        from OCP.OCP.collections import Sequence_TCollection_AsciiString
        from OCP.STEPControl import STEPControl_Reader
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
    except Exception as exc:
        result["failures"].append({
            "code": "STEP_INSPECTOR_DEPENDENCY_MISSING",
            "detail": f"工业几何依赖不可用：{type(exc).__name__}: {exc}",
        })
        return result

    try:
        reader = STEPControl_Reader()
        read_status = reader.ReadFile(str(path))
        if read_status != IFSelect_ReturnStatus.IFSelect_RetDone:
            result["failures"].append({
                "code": "STEP_READ_FAILED",
                "detail": f"Open Cascade ReadFile 返回 {read_status}。",
            })
            return result
        transferred_roots = int(reader.TransferRoots())
        if transferred_roots <= 0:
            result["failures"].append({
                "code": "STEP_TRANSFER_FAILED",
                "detail": "STEP 文件没有可转入的几何根节点。",
            })
            return result

        length_units = Sequence_TCollection_AsciiString()
        angle_units = Sequence_TCollection_AsciiString()
        solid_angle_units = Sequence_TCollection_AsciiString()
        reader.FileUnits(length_units, angle_units, solid_angle_units)
        source_length_units = [value.ToCString() for value in length_units]

        shape = reader.OneShape()
        valid_brep = bool(BRepCheck_Analyzer(shape).IsValid())
        solid_count = _count(shape, TopAbs_SOLID, TopExp_Explorer)
        face_count = _count(shape, TopAbs_FACE, TopExp_Explorer)
        edge_count = _count(shape, TopAbs_EDGE, TopExp_Explorer)

        volume_props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, volume_props)
        volume_mm3 = float(volume_props.Mass())

        bounds = Bnd_Box()
        BRepBndLib.Add_s(shape, bounds)
        bbox_mm = {
            "x": float(bounds.GetXMax() - bounds.GetXMin()),
            "y": float(bounds.GetYMax() - bounds.GetYMin()),
            "z": float(bounds.GetZMax() - bounds.GetZMin()),
        }
        if bounds.IsVoid():
            bbox_mm = {"x": 0.0, "y": 0.0, "z": 0.0}
    except Exception as exc:
        result["failures"].append({
            "code": "STEP_GEOMETRY_UNREADABLE",
            "detail": f"几何量测失败：{type(exc).__name__}: {exc}",
        })
        return result

    try:
        after_stat = path.stat()
        after_hash = _sha256(path)
    except OSError as exc:
        result["failures"].append({"code": "STEP_FILE_DRIFT", "detail": str(exc)})
        return result
    if before_hash != after_hash or before_stat.st_size != after_stat.st_size:
        result["failures"].append({
            "code": "STEP_FILE_DRIFT",
            "detail": "量测期间文件内容发生变化，本次结果作废。",
        })
        return result

    mm_units = {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}
    units_verified = bool(source_length_units) and all(
        unit.strip().lower() in mm_units for unit in source_length_units
    )
    finite_geometry = math.isfinite(volume_mm3) and all(
        math.isfinite(value) for value in bbox_mm.values()
    )
    result.update({
        "verified": True,
        "evidence_status": "measured",
        "geometry": {
            "valid_brep": valid_brep,
            "solid_count": solid_count,
            "face_count": face_count,
            "edge_count": edge_count,
            "volume_mm3": (
                round(volume_mm3, 6) if units_verified and math.isfinite(volume_mm3) else None
            ),
            "bbox_mm": (
                {axis: round(value, 6) for axis, value in bbox_mm.items()}
                if units_verified else None
            ),
            "volume_model_units3": round(volume_mm3, 6) if math.isfinite(volume_mm3) else None,
            "bbox_model_units": {
                axis: round(value, 6) for axis, value in bbox_mm.items()
            },
        },
        "units": {
            "source_length_units": source_length_units,
            "verified_millimetres": units_verified,
        },
    })

    if not valid_brep:
        result["failures"].append({"code": "BREP_INVALID", "detail": "Open Cascade B-Rep 校验未通过。"})
    if solid_count < 1:
        result["failures"].append({"code": "NO_SOLID", "detail": "文件中没有封闭实体。"})
    if not finite_geometry or volume_mm3 <= 0:
        result["failures"].append({"code": "NONPOSITIVE_OR_NONFINITE_VOLUME", "detail": "实体体积不是正的有限值。"})
    if not units_verified:
        result["failures"].append({
            "code": "LENGTH_UNIT_NOT_MM",
            "detail": "STEP 未明确声明毫米长度单位；本仓库的尺寸门禁要求 mm。",
        })

    result["passed"] = not result["failures"]
    result["status"] = "PASS" if result["passed"] else "FAIL"
    return result
