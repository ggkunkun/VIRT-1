"""Runtime lookup and fail-closed validation for six-software observations."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .frames import (
    CoordinateContractError, CoordinateFrame, FrameGraph, convert_length,
    identity4, inverse_rigid, multiply4, unit_scale_to_mm,
)

_PROFILE_PATH = Path(__file__).resolve().parents[2] / "knowledge_base" / "six_software" / "coordinate_contracts.json"
_ALIASES = {
    "solidworks": "solidworks_2021", "sw": "solidworks_2021", "solidworks_2021": "solidworks_2021",
    "autocad": "autocad_2026", "autocad_2026": "autocad_2026",
    "nx": "siemens_nx_12", "nx12": "siemens_nx_12", "siemens_nx_12": "siemens_nx_12",
    "cimco": "cimco_edit_2026", "cimco_edit_2026": "cimco_edit_2026",
    "vericut": "vericut_9_6", "vericut_9_6": "vericut_9_6",
    "sscnc": "sscnc_7_2", "sscnc_7_2": "sscnc_7_2",
}


def _profiles() -> Dict[str, Any]:
    return json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))


def get_coordinate_profile(software: str) -> Dict[str, Any]:
    key = _ALIASES.get(str(software or "").strip().lower())
    if not key:
        return {"status": "unknown_software", "software": software,
                "issues": ["software_must_be_one_of_the_six_supported_profiles"]}
    profile = _profiles()["software"].get(key)
    if not profile:
        return {"status": "profile_missing", "software": software, "issues": ["coordinate_profile_missing"]}
    return {"status": "profile_loaded", "profile_id": key,
            "canonical_length_unit": "mm", "profile": profile,
            "basis": "documented_or_asserted_contract_not_live_state"}


def _verify_file(path: str, expected: str) -> bool:
    target = Path(path)
    if not target.is_absolute() or not target.is_file() or len(str(expected or "")) != 64:
        return False
    digest = hashlib.sha256()
    try:
        with target.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return False
    return digest.hexdigest().lower() == str(expected).lower()


def _vector3_values(value: Any) -> Optional[List[float]]:
    if isinstance(value, dict):
        keyed = {str(key).upper(): item for key, item in value.items()}
        value = [keyed.get(axis) for axis in ("X", "Y", "Z")]
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        result = [float(item) for item in value]
        return result if all(math.isfinite(item) for item in result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _finite_vector3(value: Any) -> bool:
    return _vector3_values(value) is not None


def _matrix4_shape(value: Any) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    try:
        return all(isinstance(row, (list, tuple)) and len(row) == 4
                   and all(math.isfinite(float(item)) for item in row) for row in value)
    except (TypeError, ValueError, OverflowError):
        return False


def _matrix3_or4_shape(value: Any) -> bool:
    if _matrix4_shape(value):
        return True
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return False
    try:
        return all(isinstance(row, (list, tuple)) and len(row) == 3
                   and all(math.isfinite(float(item)) for item in row) for row in value)
    except (TypeError, ValueError, OverflowError):
        return False


def _sha256_shape(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def _frame_ref_exists(value: Any, frames: Sequence[Any]) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    ref = value.strip().casefold()
    return any(isinstance(frame, dict)
               and ref in {str(frame.get("frame_id") or "").casefold(),
                           str(frame.get("name") or "").casefold()}
               for frame in frames)


def _frame_id_for_ref(value: Any, frames: Sequence[CoordinateFrame]) -> str:
    ref = str(value or "").strip().casefold()
    for frame in frames:
        if ref in {frame.frame_id.casefold(), frame.name.casefold()}:
            return frame.frame_id
    raise CoordinateContractError(f"frame reference not found: {value!r}")


def _matrix_close(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]], tol: float = 1e-5) -> bool:
    try:
        return all(abs(float(left[r][c]) - float(right[r][c])) <= tol
                   for r in range(4) for c in range(4))
    except (IndexError, TypeError, ValueError, OverflowError):
        return False


def _native_frame_cross_check_issues(
    profile_id: str, snapshot: Dict[str, Any], frames: Sequence[CoordinateFrame], graph: FrameGraph
) -> List[str]:
    issues: List[str] = []
    try:
        if profile_id == "solidworks_2021":
            active = _frame_id_for_ref(snapshot.get("active_coordinate_system"), frames)
            if not _matrix_close(snapshot["transform_to_model"], graph.global_from(active)):
                issues.append("transform_to_model_disagrees_with_frame_graph")
        elif profile_id == "autocad_2026":
            wcs = _frame_id_for_ref("WCS", frames)
            ucs = _frame_id_for_ref("UCS", frames)
            wcs_from_ucs = multiply4(inverse_rigid(graph.global_from(wcs)), graph.global_from(ucs))
            code = int(snapshot["INSUNITS"])
            scale_by_code = {1: 25.4, 2: 304.8, 3: 1609344.0, 4: 1.0, 5: 10.0,
                             6: 1000.0, 7: 1000000.0, 8: 0.0000254, 9: 0.0254,
                             10: 914.4, 11: 0.0000001, 12: 0.000001, 13: 0.001,
                             14: 100.0, 15: 10000.0, 16: 100000.0, 17: 1000000000000.0,
                             18: 149597870700000.0, 19: 9460730472580800000.0,
                             20: 30856775814913673000.0, 21: 304.8006096}
            scale = scale_by_code[code]
            x = _vector3_values(snapshot["UCSXDIR"])
            y = _vector3_values(snapshot["UCSYDIR"])
            origin_native = _vector3_values(snapshot["UCSORG"])
            if x is None or y is None or origin_native is None:
                raise CoordinateContractError("AutoCAD UCS vectors are malformed")
            z = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2],
                 x[0] * y[1] - x[1] * y[0]]
            origin = [float(v) * scale for v in origin_native]
            expected = ((x[0], y[0], z[0], origin[0]),
                        (x[1], y[1], z[1], origin[1]),
                        (x[2], y[2], z[2], origin[2]),
                        (0.0, 0.0, 0.0, 1.0))
            if not _matrix_close(expected, wcs_from_ucs):
                issues.append("UCS_native_values_disagree_with_frame_graph")
        elif profile_id == "siemens_nx_12":
            absolute = _frame_id_for_ref(snapshot.get("absolute_frame"), frames)
            wcs = _frame_id_for_ref("WCS", frames)
            absolute_from_wcs = multiply4(inverse_rigid(graph.global_from(absolute)), graph.global_from(wcs))
            origin_native = _vector3_values(snapshot["WCS_origin"])
            if origin_native is None:
                raise CoordinateContractError("NX WCS origin is malformed")
            origin = [convert_length(v, str(snapshot["part_units"])) for v in origin_native]
            orientation = snapshot["WCS_orientation"]
            expected = [list(row) for row in identity4()]
            for r in range(3):
                for c in range(3):
                    expected[r][c] = float(orientation[r][c])
                expected[r][3] = origin[r]
            if not _matrix_close(expected, absolute_from_wcs):
                issues.append("WCS_native_values_disagree_with_frame_graph")
    except (KeyError, TypeError, ValueError, OverflowError, CoordinateContractError) as exc:
        issues.append(f"native_frame_cross_check_failed:{exc}")
    return issues


def _app_structure_issues(profile_id: str, snapshot: Dict[str, Any], frames: Sequence[Any]) -> List[str]:
    """Validate the native fields that give each application's frame names meaning."""
    issues: List[str] = []
    names = {str(f.get("name") or "").strip().casefold()
             for f in frames if isinstance(f, dict)}
    ids = {str(f.get("frame_id") or "").strip().casefold()
           for f in frames if isinstance(f, dict)}

    def require_frames(*required: str) -> None:
        for name in required:
            if name.casefold() not in names and name.casefold() not in ids:
                issues.append(f"native_frame_missing:{name}")

    if profile_id == "solidworks_2021":
        if not _matrix4_shape(snapshot.get("transform_to_model")):
            issues.append("transform_to_model_must_be_4x4")
        if not _frame_ref_exists(snapshot.get("active_coordinate_system"), frames):
            issues.append("active_coordinate_system_not_in_frame_graph")
    elif profile_id == "autocad_2026":
        code = snapshot.get("INSUNITS")
        try:
            code_int = int(code)
        except (TypeError, ValueError, OverflowError):
            code_int = 0
        insunits_mm = {
            1: 25.4, 2: 304.8, 3: 1609344.0, 4: 1.0, 5: 10.0,
            6: 1000.0, 7: 1000000.0, 8: 0.0000254, 9: 0.0254,
            10: 914.4, 11: 0.0000001, 12: 0.000001, 13: 0.001,
            14: 100.0, 15: 10000.0, 16: 100000.0, 17: 1000000000000.0,
            18: 149597870700000.0, 19: 9460730472580800000.0,
            20: 30856775814913673000.0, 21: 304.8006096,
        }
        if code_int not in insunits_mm:
            issues.append("INSUNITS_missing_or_unitless")
        if not _finite_vector3(snapshot.get("UCSORG")):
            issues.append("UCSORG_must_be_finite_vector3")
        x = snapshot.get("UCSXDIR")
        y = snapshot.get("UCSYDIR")
        if not _finite_vector3(x):
            issues.append("UCSXDIR_must_be_finite_vector3")
        if not _finite_vector3(y):
            issues.append("UCSYDIR_must_be_finite_vector3")
        if _finite_vector3(x) and _finite_vector3(y):
            xv, yv = [float(n) for n in x], [float(n) for n in y]
            xn = math.sqrt(sum(n * n for n in xv))
            yn = math.sqrt(sum(n * n for n in yv))
            dot = sum(xv[i] * yv[i] for i in range(3))
            if abs(xn - 1.0) > 1e-5 or abs(yn - 1.0) > 1e-5 or abs(dot) > 1e-5:
                issues.append("UCS_axes_must_be_unit_and_orthogonal")
        for frame in frames:
            if not isinstance(frame, dict) or str(frame.get("name") or "").casefold() not in {"wcs", "ucs"}:
                continue
            try:
                frame_scale = unit_scale_to_mm(str(frame.get("units") or ""))
                if abs(frame_scale - insunits_mm.get(code_int, float("nan"))) > max(1e-8, frame_scale * 1e-8):
                    issues.append(f"INSUNITS_frame_unit_mismatch:{frame.get('name')}")
            except CoordinateContractError:
                issues.append(f"INSUNITS_frame_unit_unsupported:{frame.get('name')}")
        require_frames("WCS", "UCS")
    elif profile_id == "siemens_nx_12":
        try:
            unit_scale_to_mm(str(snapshot.get("part_units") or ""))
        except CoordinateContractError:
            issues.append("part_units_unsupported_or_missing")
        if not _finite_vector3(snapshot.get("WCS_origin")):
            issues.append("WCS_origin_must_be_finite_vector3")
        if not _matrix3_or4_shape(snapshot.get("WCS_orientation")):
            issues.append("WCS_orientation_must_be_3x3_or_4x4")
        for key in ("absolute_frame", "CAM_MCS", "workpiece_frame"):
            if not _frame_ref_exists(snapshot.get(key), frames):
                issues.append(f"{key}_not_in_frame_graph")
    elif profile_id == "cimco_edit_2026":
        if not _sha256_shape(snapshot.get("nc_sha256")):
            issues.append("nc_sha256_invalid")
        if str(snapshot.get("units") or "").upper() not in {"MM", "INCH", "G20", "G21"}:
            issues.append("nc_units_unrecognized")
        if str(snapshot.get("G90_G91") or "").upper() not in {"G90", "G91"}:
            issues.append("absolute_incremental_mode_unrecognized")
        if str(snapshot.get("plane") or "").upper() not in {"G17", "G18", "G19"}:
            issues.append("nc_plane_unrecognized")
        if not re.fullmatch(r"G54(?:\.1\s*P?\d+)?|G5[5-9]", str(snapshot.get("work_offset") or "").upper()):
            issues.append("work_offset_unrecognized")
        if not _finite_vector3(snapshot.get("stock_origin")):
            issues.append("stock_origin_must_be_finite_vector3")
        require_frames("NC_program_position", "machine_setup", "stock_work_origin")
    elif profile_id == "vericut_9_6":
        for key in ("project_sha256", "machine_file_sha256", "control_file_sha256",
                    "simulation_log_sha256"):
            if not _sha256_shape(snapshot.get(key)):
                issues.append(f"{key}_invalid")
        transforms = snapshot.get("component_transforms")
        if not isinstance(transforms, (dict, list)) or not transforms:
            issues.append("component_transforms_missing")
        if not isinstance(snapshot.get("work_offset"), (dict, list)) or not snapshot.get("work_offset"):
            issues.append("work_offset_transform_missing")
        try:
            collisions = int(snapshot.get("collision_count"))
            if collisions < 0:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            issues.append("collision_count_must_be_nonnegative_integer")
        if str(snapshot.get("autodiff_verdict") or "").upper() not in {
                "GREEN", "BLUE", "RED", "PASS", "FAIL", "INSUFFICIENT_EVIDENCE"}:
            issues.append("autodiff_verdict_unrecognized")
        require_frames("machine_root", "NC_work_offset")
    elif profile_id == "sscnc_7_2":
        if str(snapshot.get("mode") or "").upper() not in {"AUTO", "EDIT", "MDI", "JOG"}:
            issues.append("controller_mode_unrecognized")
        for key in ("MACHINE", "RELATIVE", "ABSOLUTE", "G54"):
            if not _finite_vector3(snapshot.get(key)):
                issues.append(f"{key}_must_be_finite_vector3")
        if not isinstance(snapshot.get("tool_offset"), (dict, list)) or not snapshot.get("tool_offset"):
            issues.append("tool_offset_evidence_missing")
        if not _sha256_shape(snapshot.get("program_sha256")):
            issues.append("program_sha256_invalid")
        require_frames("MACHINE", "RELATIVE", "ABSOLUTE_G54")
    return issues


def validate_coordinate_snapshot(software: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a native API/UI snapshot; documentation alone cannot produce PASS."""
    profile_result = get_coordinate_profile(software)
    if profile_result["status"] != "profile_loaded":
        return {"passed": False, **profile_result}
    profile = profile_result["profile"]
    issues: List[str] = []
    if not isinstance(snapshot, dict):
        return {"passed": False, "status": "invalid_snapshot", "issues": ["snapshot_must_be_object"]}
    if str(snapshot.get("transform_unit") or "").strip().lower() != "mm":
        issues.append("transform_unit_must_be_mm")
    probe = profile.get("probe") or {}
    missing = [key for key in probe.get("required_fields", [])
               if key not in snapshot or snapshot.get(key) is None
               or snapshot.get(key) == "" or snapshot.get(key) == [] or snapshot.get(key) == {}]
    issues.extend(f"snapshot_field_missing:{key}" for key in missing)
    if not str(snapshot.get("version") or "").strip():
        issues.append("software_version_missing")
    elif str(profile.get("version") or "").lower() not in str(snapshot.get("version") or "").lower():
        issues.append(f"software_version_mismatch:expected_{profile.get('version')}")
    captured_at = str(snapshot.get("captured_at") or "").strip()
    if not captured_at:
        issues.append("captured_at_missing")
    else:
        try:
            parsed_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            if parsed_at.tzinfo is None or parsed_at.utcoffset() is None:
                issues.append("captured_at_timezone_required")
        except (TypeError, ValueError):
            issues.append("captured_at_must_be_iso8601")
    if not str(snapshot.get("source") or "").strip():
        issues.append("observation_source_missing")
    evidence = snapshot.get("evidence") if isinstance(snapshot.get("evidence"), dict) else {}
    basis = str(evidence.get("basis") or "unverified")
    if basis != "measured":
        issues.append("live_coordinate_state_requires_measured_evidence")
    if not _verify_file(str(evidence.get("path") or ""), str(evidence.get("sha256") or "")):
        issues.append("evidence_file_missing_or_sha256_mismatch")
    frames_raw = snapshot.get("frames")
    if not isinstance(frames_raw, list) or not frames_raw:
        issues.append("coordinate_frames_missing")
        frames_raw = []
    frames = []
    for item in frames_raw:
        if not isinstance(item, dict):
            issues.append("coordinate_frame_not_object")
            continue
        try:
            frame = CoordinateFrame(
                frame_id=str(item["frame_id"]), software=str(software),
                version=str(snapshot.get("version") or "unknown"),
                name=str(item["name"]), units=str(item["units"]),
                parent_frame=item.get("parent_frame"),
                transform_parent_from_frame=item["transform_parent_from_frame"],
                handedness=str(item.get("handedness") or "right"),
                evidence_basis=basis,
                evidence_source=str(snapshot.get("source") or ""),
                evidence_path=str(evidence.get("path") or ""),
                captured_at=str(snapshot.get("captured_at") or ""),
            )
            frames.append(frame)
        except (KeyError, TypeError, ValueError, CoordinateContractError) as exc:
            issues.append(f"coordinate_frame_invalid:{exc}")
    issues.extend(_app_structure_issues(profile_result["profile_id"], snapshot, frames_raw))
    graph_result = {"passed": False, "issues": ["frame_graph_not_constructed"]}
    if frames:
        try:
            graph = FrameGraph(frames)
            graph_result = graph.validate()
            issues.extend(graph_result["issues"])
            if graph_result["passed"]:
                issues.extend(_native_frame_cross_check_issues(
                    profile_result["profile_id"], snapshot, frames, graph))
            active = snapshot.get("active_frame")
            if not active:
                issues.append("active_frame_missing")
            elif active not in {frame.frame_id for frame in frames}:
                issues.append(f"active_frame_unknown:{active}")
        except CoordinateContractError as exc:
            issues.append(f"frame_graph_invalid:{exc}")
    return {
        "passed": not issues,
        "status": "coordinate_snapshot_hash_verified" if not issues else "insufficient_evidence",
        "software": software,
        "version": snapshot.get("version"),
        "captured_at": snapshot.get("captured_at"),
        "active_frame": snapshot.get("active_frame"),
        "frame_count": len(frames),
        "frame_graph": graph_result,
        "evidence": {"basis": basis, "path": evidence.get("path"),
                     "sha256": evidence.get("sha256"),
                     "source_authenticity": "not_cryptographically_attested_by_runtime"},
        "issues": issues,
    }


def transform_snapshot_points(
    software: str,
    snapshot: Dict[str, Any],
    source_frame: str,
    target_frame: str,
    points_mm: Sequence[Sequence[float]],
) -> Dict[str, Any]:
    verdict = validate_coordinate_snapshot(software, snapshot)
    if not verdict.get("passed"):
        return {"passed": False, "status": "blocked_by_snapshot_gate",
                "snapshot_verdict": verdict, "points": []}
    graph = FrameGraph(
        CoordinateFrame(
            frame_id=str(item["frame_id"]), software=str(software),
            version=str(snapshot["version"]), name=str(item["name"]),
            units=str(item["units"]), parent_frame=item.get("parent_frame"),
            transform_parent_from_frame=item["transform_parent_from_frame"],
            handedness=str(item.get("handedness") or "right"),
            evidence_basis="measured", evidence_source=str(snapshot["source"]),
            evidence_path=str(snapshot["evidence"]["path"]),
            captured_at=str(snapshot["captured_at"]),
        ) for item in snapshot["frames"]
    )
    try:
        mapped = [list(graph.transform(point, source_frame, target_frame)) for point in points_mm]
    except (CoordinateContractError, TypeError, ValueError) as exc:
        return {"passed": False, "status": "transform_rejected", "issues": [str(exc)], "points": []}
    return {"passed": True, "status": "transformed", "source_frame": source_frame,
            "target_frame": target_frame, "points_mm": mapped,
            "roundtrip_max_error_mm": max(
                (graph.roundtrip_error_mm(point, source_frame, target_frame) for point in points_mm),
                default=0.0), "evidence": verdict["evidence"]}

