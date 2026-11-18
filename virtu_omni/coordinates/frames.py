"""Coordinate-frame contracts shared by CAD, CAM, NC and machine runtimes.

All transforms use millimeters, column vectors, and the convention
``T_parent_from_frame @ point_frame -> point_parent``.  A frame's ``units``
records the native units reported by its source API; the transform itself is
always expressed in canonical millimeters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Matrix4 = Tuple[Tuple[float, float, float, float], ...]
Vector3 = Tuple[float, float, float]

_UNIT_TO_MM = {
    "mm": 1.0, "millimeter": 1.0, "millimeters": 1.0,
    "cm": 10.0, "m": 1000.0, "meter": 1000.0, "meters": 1000.0,
    "um": 0.001, "µm": 0.001,
    "in": 25.4, "inch": 25.4, "inches": 25.4,
    "ft": 304.8, "foot": 304.8, "feet": 304.8,
    "yd": 914.4, "yard": 914.4, "yards": 914.4,
    "mi": 1609344.0, "mile": 1609344.0, "miles": 1609344.0,
    "mil": 0.0254, "uin": 0.0000254,
    "nm": 0.000001, "angstrom": 0.0000001,
    "dm": 100.0, "dam": 10000.0, "hm": 100000.0,
    "au": 149597870700000.0,
    "ly": 9460730472580800000.0,
    "pc": 30856775814913673000.0,
}
_EVIDENCE_BASES = {"measured", "documented", "asserted", "inferred", "unverified"}
_EPS = 1e-7


class CoordinateContractError(ValueError):
    """A coordinate observation violates the shared frame contract."""


def _finite_vector(value: Sequence[float], name: str) -> Vector3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise CoordinateContractError(f"{name} must have exactly 3 values")
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise CoordinateContractError(f"{name} contains a non-finite value")
    return result  # type: ignore[return-value]


def _matrix4(value: Sequence[Sequence[float]]) -> Matrix4:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise CoordinateContractError("transform must be a 4x4 matrix")
    rows = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            raise CoordinateContractError("transform must be a 4x4 matrix")
        vals = tuple(float(v) for v in row)
        if not all(math.isfinite(v) for v in vals):
            raise CoordinateContractError("transform contains a non-finite value")
        rows.append(vals)
    result: Matrix4 = tuple(rows)
    if any(abs(result[3][i] - expected) > _EPS
           for i, expected in enumerate((0.0, 0.0, 0.0, 1.0))):
        raise CoordinateContractError("transform must be affine with bottom row [0,0,0,1]")
    return result


def _det3(m: Matrix4) -> float:
    a, b, c = (m[i][:3] for i in range(3))
    return (a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0]))


def _validate_orthonormal(m: Matrix4, handedness: str) -> None:
    # Rotation axes are matrix columns. Scale/shear belongs in an explicit
    # unit conversion, never hidden inside a frame rotation.
    cols = [tuple(m[r][c] for r in range(3)) for c in range(3)]
    for i in range(3):
        norm = sum(v * v for v in cols[i])
        if abs(norm - 1.0) > 1e-5:
            raise CoordinateContractError("frame axes must be unit length")
        for j in range(i):
            dot = sum(cols[i][k] * cols[j][k] for k in range(3))
            if abs(dot) > 1e-5:
                raise CoordinateContractError("frame axes must be perpendicular")
    det = _det3(m)
    expected_sign = 1 if handedness == "right" else -1
    if abs(abs(det) - 1.0) > 1e-5 or det * expected_sign < 0:
        raise CoordinateContractError("frame handedness does not match its axis basis")


def unit_scale_to_mm(unit: str) -> float:
    key = str(unit or "").strip().lower()
    try:
        return _UNIT_TO_MM[key]
    except KeyError as exc:
        raise CoordinateContractError(f"unsupported length unit: {unit!r}") from exc


def convert_length(value: float, from_unit: str, to_unit: str = "mm") -> float:
    number = float(value)
    if not math.isfinite(number):
        raise CoordinateContractError("length must be finite")
    return number * unit_scale_to_mm(from_unit) / unit_scale_to_mm(to_unit)


@dataclass(frozen=True)
class CoordinateFrame:
    frame_id: str
    software: str
    version: str
    name: str
    units: str
    parent_frame: Optional[str]
    transform_parent_from_frame: Matrix4
    handedness: str = "right"
    evidence_basis: str = "unverified"
    evidence_source: str = ""
    evidence_path: str = ""
    captured_at: str = ""

    def __post_init__(self) -> None:
        for key in ("frame_id", "software", "version", "name"):
            if not str(getattr(self, key) or "").strip():
                raise CoordinateContractError(f"{key} is required")
        unit_scale_to_mm(self.units)
        if self.handedness not in ("right", "left"):
            raise CoordinateContractError("handedness must be 'right' or 'left'")
        if self.evidence_basis not in _EVIDENCE_BASES:
            raise CoordinateContractError(f"unknown evidence basis: {self.evidence_basis}")
        matrix = _matrix4(self.transform_parent_from_frame)
        _validate_orthonormal(matrix, self.handedness)
        if self.evidence_basis == "measured":
            if not self.evidence_path or not self.captured_at:
                raise CoordinateContractError(
                    "measured frames require an evidence_path and captured_at timestamp")

    @classmethod
    def from_axes(
        cls,
        *,
        frame_id: str,
        software: str,
        version: str,
        name: str,
        units: str,
        origin_mm: Sequence[float],
        x_axis_in_parent: Sequence[float],
        y_axis_in_parent: Sequence[float],
        z_axis_in_parent: Sequence[float],
        parent_frame: Optional[str] = None,
        handedness: str = "right",
        evidence_basis: str = "unverified",
        evidence_source: str = "",
        evidence_path: str = "",
        captured_at: str = "",
    ) -> "CoordinateFrame":
        origin = _finite_vector(origin_mm, "origin_mm")
        x = _finite_vector(x_axis_in_parent, "x_axis_in_parent")
        y = _finite_vector(y_axis_in_parent, "y_axis_in_parent")
        z = _finite_vector(z_axis_in_parent, "z_axis_in_parent")
        matrix: Matrix4 = (
            (x[0], y[0], z[0], origin[0]),
            (x[1], y[1], z[1], origin[1]),
            (x[2], y[2], z[2], origin[2]),
            (0.0, 0.0, 0.0, 1.0),
        )
        return cls(
            frame_id=frame_id, software=software, version=version, name=name,
            units=units, parent_frame=parent_frame,
            transform_parent_from_frame=matrix, handedness=handedness,
            evidence_basis=evidence_basis, evidence_source=evidence_source,
            evidence_path=evidence_path, captured_at=captured_at,
        )


def identity4() -> Matrix4:
    return ((1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0))


def multiply4(a: Matrix4, b: Matrix4) -> Matrix4:
    return tuple(tuple(sum(a[r][k] * b[k][c] for k in range(4))
                       for c in range(4)) for r in range(4))  # type: ignore[return-value]


def inverse_rigid(m: Matrix4) -> Matrix4:
    """Invert a rigid transform whose 3x3 part may include a reflection."""
    rot_t = tuple(tuple(m[c][r] for c in range(3)) for r in range(3))
    t = tuple(m[r][3] for r in range(3))
    inv_t = tuple(-sum(rot_t[r][c] * t[c] for c in range(3)) for r in range(3))
    return (
        (rot_t[0][0], rot_t[0][1], rot_t[0][2], inv_t[0]),
        (rot_t[1][0], rot_t[1][1], rot_t[1][2], inv_t[1]),
        (rot_t[2][0], rot_t[2][1], rot_t[2][2], inv_t[2]),
        (0.0, 0.0, 0.0, 1.0),
    )


def apply_point(m: Matrix4, point_mm: Sequence[float]) -> Vector3:
    p = _finite_vector(point_mm, "point_mm")
    return tuple(sum(m[r][c] * p[c] for c in range(3)) + m[r][3]
                 for r in range(3))  # type: ignore[return-value]


class FrameGraph:
    """Acyclic frame tree with explicit, unit-normalized transforms."""

    def __init__(self, frames: Iterable[CoordinateFrame] = ()) -> None:
        self._frames: Dict[str, CoordinateFrame] = {}
        for frame in frames:
            self.add(frame)

    def add(self, frame: CoordinateFrame) -> None:
        if frame.frame_id in self._frames:
            raise CoordinateContractError(f"duplicate frame id: {frame.frame_id}")
        self._frames[frame.frame_id] = frame

    def get(self, frame_id: str) -> CoordinateFrame:
        try:
            return self._frames[frame_id]
        except KeyError as exc:
            raise CoordinateContractError(f"unknown frame: {frame_id}") from exc

    def global_from(self, frame_id: str) -> Matrix4:
        visiting = set()

        def walk(current_id: str) -> Matrix4:
            if current_id in visiting:
                raise CoordinateContractError("coordinate frame cycle detected")
            visiting.add(current_id)
            frame = self.get(current_id)
            local = _matrix4(frame.transform_parent_from_frame)
            if frame.parent_frame is None:
                return local
            if frame.parent_frame not in self._frames:
                raise CoordinateContractError(
                    f"missing parent frame {frame.parent_frame!r} for {current_id!r}")
            return multiply4(walk(frame.parent_frame), local)

        return walk(frame_id)

    def transform(self, point_mm: Sequence[float], source: str, target: str) -> Vector3:
        """Transform a point in mm from ``source`` frame to ``target`` frame."""
        roots = {frame.frame_id for frame in self._frames.values()
                 if frame.parent_frame is None}
        if len(roots) != 1:
            raise CoordinateContractError(
                "coordinate transform requires one connected root frame")
        target_from_global = inverse_rigid(self.global_from(target))
        target_from_source = multiply4(target_from_global, self.global_from(source))
        return apply_point(target_from_source, point_mm)

    def roundtrip_error_mm(self, point_mm: Sequence[float], source: str, target: str) -> float:
        moved = self.transform(point_mm, source, target)
        returned = self.transform(moved, target, source)
        original = _finite_vector(point_mm, "point_mm")
        return math.sqrt(sum((returned[i] - original[i]) ** 2 for i in range(3)))

    def validate(self) -> Dict[str, object]:
        issues: List[str] = []
        roots = [frame.frame_id for frame in self._frames.values() if frame.parent_frame is None]
        if self._frames and len(roots) != 1:
            issues.append(f"frame_graph_requires_one_root:found_{len(roots)}")
        for frame_id in self._frames:
            try:
                self.global_from(frame_id)
            except CoordinateContractError as exc:
                issues.append(f"{frame_id}:{exc}")
        return {"passed": not issues, "frame_count": len(self._frames),
                "issues": issues, "basis": "measured_input_validation"}

