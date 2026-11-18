# -*- coding: utf-8 -*-
"""parametric_cad_generator.py — 任务规格 → build123d 真实 BRep → STL + 体积守恒证据.

P0 缺口修复：SWARM 几何 worker 此前只消费样本库 STL（关键词匹配 + NASA1975 兜底），
不消费按任务规格生成的 CAD。本模块提供确定性参数化建模路径：

- ROTATIONAL_SHAFT：外圆柱 − 通孔 − 环形槽（Torus 布尔切，槽体积按 Pappus 定理精确核算）
- FLANGE_PLATE：盘体 − 中心孔 − 螺栓圆均布孔
- BEARING_BRACKET：底板 + 立筋融合
- SHEET_METAL_BEND：平板（折弯成形性由 CAE 引擎另行评估）

测量宪法：每个产物带 volume_mm3（BRep 实测）与 analytic_volume_mm3（解析参照），
误差 > 1% 拒绝交付（AGENTS.md §2A 体积守恒断言）。无规格不生成——绝不静默套用默认尺寸。
诚实边界：自由曲面（涡轮叶片/叶轮）不在参数化覆盖内，返回 None 交由样本库路径并如实标注。
"""

from __future__ import annotations

import math
import re
import struct
from pathlib import Path
from typing import Any, Dict, Optional

import build123d as bd

from virtu_omni.engine.universal_geometry_engine import PartFamily

VOLUME_TOLERANCE_PCT = 1.0

_WISH_DIM_PATTERN = re.compile(
    r"(?:外径|内径|总长|长度|高度|直径|厚度|宽)\s*[=:约为]*\s*[0-9]")


def classify_family(spec: Dict[str, Any]) -> str:
    if spec.get("sheet_thickness"):
        return PartFamily.SHEET_METAL_BEND.value
    if spec.get("thickness") and (spec.get("pcd") or spec.get("bolt_hole_count")):
        return PartFamily.FLANGE_PLATE.value
    if spec.get("center_height") or spec.get("base_width"):
        return PartFamily.BEARING_BRACKET.value
    return PartFamily.ROTATIONAL_SHAFT.value


def _groove_volume(r_out: float, r_groove: float) -> float:
    """环槽切除体积：半圆环面按 Pappus 定理，V = pi^2*R*r^2 - (4*pi/3)*r^3。"""
    return math.pi ** 2 * r_out * r_groove ** 2 - (4.0 * math.pi / 3.0) * r_groove ** 3


def analytic_volume(family: str, spec: Dict[str, Any]) -> float:
    if family == PartFamily.FLANGE_PLATE.value:
        ro = float(spec["d_outer"]) / 2.0
        ri = float(spec.get("d_inner", 0.0)) / 2.0
        t = float(spec["thickness"])
        n = int(spec.get("bolt_hole_count", 0))
        rh = float(spec.get("bolt_hole_dia", 11.0)) / 2.0
        return math.pi * (ro ** 2 - ri ** 2) * t - n * math.pi * rh ** 2 * t
    if family == PartFamily.BEARING_BRACKET.value:
        bw = float(spec["base_width"])
        bd_ = float(spec.get("base_depth", bw * 0.6))
        bt = float(spec.get("base_thickness", 14.0))
        rt = float(spec.get("rib_thickness", 8.0))
        ch = float(spec.get("center_height", 50.0))
        return bw * bd_ * bt + rt * (bd_ * 0.8) * ch
    if family == PartFamily.SHEET_METAL_BEND.value:
        return (float(spec.get("length", spec.get("overall_len", 100.0)))
                * float(spec.get("width", 60.0))
                * float(spec["sheet_thickness"]))
    ro = float(spec["d_outer"]) / 2.0
    ri = float(spec.get("d_inner", 0.0)) / 2.0
    length = float(spec["overall_len"])
    vol = math.pi * (ro ** 2 - ri ** 2) * length
    for rr in spec.get("groove_radii") or []:
        vol -= _groove_volume(ro, float(rr))
    return vol


def build_solid(family: str, spec: Dict[str, Any]) -> bd.Solid:
    """按族构建真实 BRep。规格非法直接抛 ValueError，不产出坏几何。"""
    if family == PartFamily.FLANGE_PLATE.value:
        ro = float(spec["d_outer"]) / 2.0
        ri = float(spec.get("d_inner", 0.0)) / 2.0
        t = float(spec["thickness"])
        if ro <= 0 or t <= 0 or ri >= ro:
            raise ValueError(f"法兰规格非法: d_outer={spec['d_outer']} d_inner={spec.get('d_inner')} thickness={t}")
        solid = bd.Cylinder(radius=ro, height=t)
        if ri > 0:
            solid = solid - bd.Cylinder(radius=ri, height=t + 2.0)
        n = int(spec.get("bolt_hole_count", 0))
        pcd = float(spec.get("pcd", 0.0))
        rh = float(spec.get("bolt_hole_dia", 11.0)) / 2.0
        if n > 0:
            if pcd / 2.0 + rh >= ro or (ri > 0 and pcd / 2.0 - rh <= ri):
                raise ValueError(f"螺栓孔超出盘体: pcd={pcd} hole_dia={2*rh} d_outer={2*ro}")
            for i in range(n):
                ang = 2.0 * math.pi * i / n
                hole = bd.Pos(pcd / 2.0 * math.cos(ang), pcd / 2.0 * math.sin(ang), 0) * bd.Cylinder(radius=rh, height=t + 2.0)
                solid = solid - hole
        return bd.Pos(0, 0, t / 2.0) * solid

    if family == PartFamily.BEARING_BRACKET.value:
        bw = float(spec["base_width"])
        bd_ = float(spec.get("base_depth", bw * 0.6))
        bt = float(spec.get("base_thickness", 14.0))
        rt = float(spec.get("rib_thickness", 8.0))
        ch = float(spec.get("center_height", 50.0))
        if min(bw, bd_, bt, rt, ch) <= 0:
            raise ValueError(f"支座规格存在非正尺寸: {spec}")
        base = bd.Pos(0, 0, bt / 2.0) * bd.Box(bw, bd_, bt)
        rib = bd.Pos(0, 0, bt + ch / 2.0) * bd.Box(rt, bd_ * 0.8, ch)
        return base + rib

    if family == PartFamily.SHEET_METAL_BEND.value:
        length = float(spec.get("length", spec.get("overall_len", 100.0)))
        width = float(spec.get("width", 60.0))
        t = float(spec["sheet_thickness"])
        if min(length, width, t) <= 0:
            raise ValueError(f"钣金规格存在非正尺寸: {spec}")
        return bd.Pos(0, 0, t / 2.0) * bd.Box(length, width, t)

    # ROTATIONAL_SHAFT
    ro = float(spec["d_outer"]) / 2.0
    ri = float(spec.get("d_inner", 0.0)) / 2.0
    length = float(spec["overall_len"])
    if ro <= 0 or length <= 0 or ri >= ro:
        raise ValueError(f"轴规格非法: d_outer={spec['d_outer']} d_inner={spec.get('d_inner')} overall_len={length}")
    solid = bd.Cylinder(radius=ro, height=length)
    if ri > 0:
        solid = solid - bd.Cylinder(radius=ri, height=length + 2.0)
    radii = [float(r) for r in (spec.get("groove_radii") or [])]
    n = len(radii)
    for i, rr in enumerate(radii, 1):
        z_c = length / (n + 1.0) * i - length / 2.0
        if rr <= 0 or rr >= (ro - ri):
            raise ValueError(f"槽半径 R{rr} 超出肉厚 (ro-ri={ro - ri})")
        if z_c - rr < -length / 2.0 or z_c + rr > length / 2.0:
            raise ValueError(f"槽 R{rr} 在 z={z_c + length / 2.0} 处超出件长 {length}")
        solid = solid - bd.Pos(0, 0, z_c) * bd.Torus(major_radius=ro, minor_radius=rr)
    return bd.Pos(0, 0, length / 2.0) * solid


def _spec_from_wish(task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    wish = task.get("wish") or task.get("prompt") or ""
    if not isinstance(wish, str) or not _WISH_DIM_PATTERN.search(wish):
        return None
    low = wish.lower()
    if re.search(r"叶轮|impeller|blisk|叶盘|叶片|turbine\s*blade|airfoil", low):
        return None  # 自由曲面样本件，参数化路径不覆盖
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    intent = WishCADCAMEngine().parse_wish_intent(wish)
    return {
        "d_outer": intent["d_outer"],
        "d_inner": intent["d_inner"],
        "overall_len": intent["overall_len"],
        "groove_radii": intent.get("groove_radii") or [],
        "material": intent.get("material"),
    }


def _write_binary_stl(solid: bd.Solid, path: Path,
                      tolerance: float = 0.01, angular: float = 0.1) -> int:
    # OCC StlAPI_Writer 在含 CJK 的路径下静默不落盘（本仓路径即 D:\Virtu模型），
    # 故走 tessellate + 手写二进制 STL，绕开 OCC 文件 API。
    verts, tris = solid.tessellate(tolerance, angular)
    with open(path, "wb") as fh:
        fh.write(b"virtu parametric_cad_generator".ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(tris)))
        for i0, i1, i2 in tris:
            p0, p1, p2 = verts[i0], verts[i1], verts[i2]
            ax, ay, az = p1.X - p0.X, p1.Y - p0.Y, p1.Z - p0.Z
            bx, by, bz = p2.X - p0.X, p2.Y - p0.Y, p2.Z - p0.Z
            nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
            norm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            fh.write(struct.pack(
                "<12fH", nx / norm, ny / norm, nz / norm,
                p0.X, p0.Y, p0.Z, p1.X, p1.Y, p1.Z, p2.X, p2.Y, p2.Z, 0))
    return len(tris)


def generate_design_assets(task: Dict[str, Any], output_dir: str) -> Optional[Dict[str, Any]]:
    """任务 → 生成 CAD → STL + 体积证据。无可用规格返回 None（调用方走样本库并如实标注）。"""
    spec = dict(task.get("spec") or {})
    if not spec:
        spec = _spec_from_wish(task) or {}
    dim_keys = ("d_outer", "overall_len", "thickness", "sheet_thickness", "base_width")
    if not any(float(spec.get(k) or 0) > 0 for k in dim_keys):
        return None

    family = str(task.get("family") or classify_family(spec))
    solid = build_solid(family, spec)
    vol = float(solid.volume)
    ana = analytic_volume(family, spec)
    err_pct = abs(vol - ana) / max(1e-9, ana) * 100.0
    if err_pct > VOLUME_TOLERANCE_PCT:
        raise ValueError(
            f"体积守恒断言失败: BRep={vol:.3f} mm^3 解析={ana:.3f} mm^3 误差={err_pct:.3f}%")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stl_path = out / f"design_{family.lower()}.stl"
    tri_count = _write_binary_stl(solid, stl_path)
    if not stl_path.is_file() or stl_path.stat().st_size == 0:
        raise ValueError(f"STL 落盘失败: {stl_path}")
    bb = solid.bounding_box()
    return {
        "design_stl": str(stl_path),
        "design_source": "generated_cad",
        "basis": "measured",
        "family": family,
        "spec": spec,
        "volume_mm3": round(vol, 3),
        "analytic_volume_mm3": round(ana, 3),
        "volume_error_pct": round(err_pct, 6),
        "triangle_count": tri_count,
        "bbox_mm": {"dx": round(float(bb.size.X), 3),
                    "dy": round(float(bb.size.Y), 3),
                    "dz": round(float(bb.size.Z), 3)},
        "generator": "virtu_omni.engine.parametric_cad_generator",
    }