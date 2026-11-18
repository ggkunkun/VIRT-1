# -*- coding: utf-8 -*-
"""stock_derivation.py — 从成品几何程序化派生毛坯，杜绝"超长圆柱" fallback。

核心原则（成品优先 / product-first）：
    毛坯 = 成品包络 + 加工余量，绝不允许脱离成品几何硬编码。

规则：
    * 非回转体  -> 方块料(box)：各边 = 成品 bbox 边长 + 2*侧面余量
    * 回转体    -> 圆柱料(cylinder)：
                    直径 = 2 * 垂直轴平面的最大径向包络半径 + 2*径向余量
                    长度 = 轴向跨度 + 2*端面余量
                  —— 直径取"径向包络"，长度只取"轴向"，
                     绝不用包围盒最大对角线当作圆柱（这是超长圆柱的根因）。
    * 合理性熔断（呼应 AGENTS.md 第6节单步自查/熔断）：
                    方块体积比、圆柱体积比 / 长径比 超限 -> StockSanityError。

用法：
    from stock_derivation import derive_stock_strict, BBox
    stock = derive_stock_strict(product_bbox, is_revolution=True, axis="Z")
    # stock.dims == {"diameter": ..., "height": ...}
"""

from __future__ import annotations

import math
import os
import re
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

Axis = Literal["X", "Y", "Z"]

# ---- 默认加工余量（mm，每面/每端）------------------------------------------------
DEFAULT_SIDE_ALLOWANCE = 3.0    # 非回转体：每个侧面余量
DEFAULT_RADIAL_ALLOWANCE = 3.0  # 回转体：径向余量
DEFAULT_END_ALLOWANCE = 4.0     # 回转体：每个端面余量

# ---- 熔断阈值 -------------------------------------------------------------------
MAX_BOX_RATIO = 4.0     # 方块毛坯体积 / 成品体积 上限
MAX_CYL_RATIO = 5.0     # 圆柱毛坯体积 / 成品体积 上限
MAX_CYL_ASPECT = 10.0   # 圆柱 长径比(h/d) 上限（超过即"超长圆柱"）


@dataclass
class BBox:
    """成品零件的轴对齐包围盒（单位 mm）。"""
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float

    @property
    def size(self) -> Tuple[float, float, float]:
        return (self.xmax - self.xmin, self.ymax - self.ymin, self.zmax - self.zmin)

    @property
    def volume(self) -> float:
        sx, sy, sz = self.size
        return sx * sy * sz

    @property
    def center(self) -> Tuple[float, float, float]:
        return (
            (self.xmin + self.xmax) / 2,
            (self.ymin + self.ymax) / 2,
            (self.zmin + self.zmax) / 2,
        )


@dataclass
class StockSpec:
    shape: Literal["box", "cylinder"]
    dims: Dict[str, float]          # box: {dx,dy,dz} ; cylinder: {diameter,height}
    origin: Tuple[float, float, float]
    product_bbox: BBox
    sanity: Dict[str, object] = field(default_factory=dict)

    def describe(self) -> str:
        if self.shape == "box":
            d = self.dims
            return f"BOX {d['dx']:.1f}x{d['dy']:.1f}x{d['dz']:.1f}mm @ {tuple(round(v,1) for v in self.origin)}"
        d = self.dims
        return f"CYL Ø{d['diameter']:.1f} x {d['height']:.1f}mm @ {tuple(round(v,1) for v in self.origin)}"


class StockSanityError(ValueError):
    """毛坯合理性熔断：体积比 / 长径比异常，疑似误判回转体或尺寸算错。"""


def derive_stock(
    product: BBox,
    is_revolution: bool,
    axis: Axis = "Z",
    *,
    side_allowance: float = DEFAULT_SIDE_ALLOWANCE,
    radial_allowance: float = DEFAULT_RADIAL_ALLOWANCE,
    end_allowance: float = DEFAULT_END_ALLOWANCE,
) -> StockSpec:
    """从成品包围盒派生毛坯。

    is_revolution=False -> 方块料；is_revolution=True -> 圆柱料（必须显式给出回转轴）。
    """
    if not is_revolution:
        sx, sy, sz = product.size
        dx = sx + 2 * side_allowance
        dy = sy + 2 * side_allowance
        dz = sz + 2 * side_allowance
        cx, cy, cz = product.center
        origin = (cx - dx / 2, cy - dy / 2, product.zmin - side_allowance)
        stock = StockSpec(
            "box", {"dx": dx, "dy": dy, "dz": dz}, origin, product
        )
    else:
        sx, sy, sz = product.size
        cx, cy, cz = product.center
        if axis == "Z":
            length = sz
            radial_max = 0.5 * max(sx, sy)          # 垂直于 Z 的平面最大半边长 = 包络半径
            origin = (cx, cy, product.zmin - end_allowance)
        elif axis == "Y":
            length = sy
            radial_max = 0.5 * max(sx, sz)
            origin = (cx, product.ymin - end_allowance, cz)
        else:  # X
            length = sx
            radial_max = 0.5 * max(sy, sz)
            origin = (product.xmin - end_allowance, cy, cz)
        diameter = 2 * radial_max + 2 * radial_allowance
        height = length + 2 * end_allowance
        stock = StockSpec(
            "cylinder",
            {"diameter": diameter, "height": height},
            origin,
            product,
        )
    stock.sanity = check_stock_sanity(stock)
    return stock


def check_stock_sanity(
    stock: StockSpec,
    *,
    max_box_ratio: float = MAX_BOX_RATIO,
    max_cyl_ratio: float = MAX_CYL_RATIO,
    max_cyl_aspect: float = MAX_CYL_ASPECT,
) -> Dict[str, object]:
    pvol = stock.product_bbox.volume
    if stock.shape == "box":
        d = stock.dims
        svol = d["dx"] * d["dy"] * d["dz"]
        ratio = svol / pvol if pvol > 0 else float("inf")
        ok = ratio <= max_box_ratio
        return {
            "ratio": round(ratio, 3), "threshold": max_box_ratio, "ok": ok,
            "reason": "" if ok else f"方块毛坯体积比 {ratio:.2f} 超阈值 {max_box_ratio}",
        }
    d = stock.dims
    svol = 3.141592653589793 * (d["diameter"] / 2) ** 2 * d["height"]
    ratio = svol / pvol if pvol > 0 else float("inf")
    aspect = d["height"] / d["diameter"]
    ok = (ratio <= max_cyl_ratio) and (aspect <= max_cyl_aspect)
    reason = ""
    if ratio > max_cyl_ratio:
        reason = (f"圆柱毛坯体积比 {ratio:.2f} 超阈值 {max_cyl_ratio}"
                  f"（疑似把非回转体误判为回转体 / 尺寸算错）")
    elif aspect > max_cyl_aspect:
        reason = f"圆柱长径比 {aspect:.2f} 超阈值 {max_cyl_aspect}（疑似超长圆柱）"
    return {
        "ratio": round(ratio, 3), "aspect": round(aspect, 3),
        "threshold_ratio": max_cyl_ratio, "threshold_aspect": max_cyl_aspect,
        "ok": ok, "reason": reason,
    }


def derive_stock_strict(product: BBox, is_revolution: bool, axis: Axis = "Z", **kw) -> StockSpec:
    """派生毛坯并在不合理时熔断（直接替换硬编码 STOCK_R/STOCK_H 的安全入口）。"""
    stock = derive_stock(product, is_revolution, axis, **kw)
    if not stock.sanity["ok"]:
        raise StockSanityError(stock.sanity["reason"])
    return stock


_VERTEX_RE = re.compile(
    rb"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)"
)


def bbox_from_stl(stl_path: str) -> BBox:
    """纯标准库实测 STL 包围盒（二进制 + ASCII 双格式），无需 build123d / OCP。

    证据宪法优先：直接从成品网格顶点坐标算包围盒，属于可验证的实测证据，
    而非从设计参数断言。二进制 STL: 84 字节头 + n*50 字节三角形记录。
    """
    with open(stl_path, "rb") as f:
        data = f.read()
    if len(data) < 84:
        raise ValueError(f"STL 文件过短 ({len(data)} bytes): {stl_path}")
    n_tri = struct.unpack_from("<I", data, 80)[0]
    mins = [math.inf, math.inf, math.inf]
    maxs = [-math.inf, -math.inf, -math.inf]

    if 84 + 50 * n_tri == len(data):          # ---- 二进制 STL ----
        off = 84
        for _ in range(n_tri):
            base = off + 12                   # 跳过 12 字节法向量
            for k in range(3):
                x, y, z = struct.unpack_from("<fff", data, base + 12 * k)
                for axis, val in enumerate((x, y, z)):
                    if val < mins[axis]:
                        mins[axis] = val
                    if val > maxs[axis]:
                        maxs[axis] = val
            off += 50
    else:                                     # ---- ASCII STL ----
        for m in _VERTEX_RE.finditer(data):
            vals = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            for axis, val in enumerate(vals):
                if val < mins[axis]:
                    mins[axis] = val
                if val > maxs[axis]:
                    maxs[axis] = val

    if mins[0] is math.inf or not (math.isfinite(mins[0]) and
                                   math.isfinite(maxs[0]) and
                                   math.isfinite(mins[1]) and
                                   math.isfinite(mins[2])):
        raise ValueError(f"STL 中未解析到有效顶点: {stl_path}")
    return BBox(mins[0], maxs[0], mins[1], maxs[1], mins[2], maxs[2])


def _bbox_from_triangles(tris, src: str) -> BBox:
    if not tris:
        raise ValueError(f"Empty or unreadable mesh: {src}")
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return BBox(min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def bbox_from_vericut_poly(path: str) -> BBox:
    """实测 VERICUT-model(Version-3.0) / ASCII PLY 网格包围盒。

    E:\\training、E:\\samples 中的 ``*.stl``/``*.ply`` 样本是 VERICUT 原生多边形格式，
    build123d.import_stl 会报 ``unexpected format of facet`` 并返回零包围盒；
    这里按多边形块解析（只取顶点，不把法向量误当顶点）。
    """
    from surface_observability import read_stl_triangles
    return _bbox_from_triangles(read_stl_triangles(str(path)), str(path))


def mesh_triangle_count(path: str) -> int:
    from surface_observability import read_stl_triangles
    return len(read_stl_triangles(str(path)))


def bbox_from_mesh(mesh_path: str) -> BBox:
    """从成品网格读取包围盒（用于替换硬编码毛坯尺寸）。

    - STEP/STP：必须借助 CAD 内核（build123d）。
    - VERICUT-model / PLY：按多边形块实测（样本库原生格式）。
    - STL：优先纯标准库实测（无第三方依赖）；失败再尝试 build123d。
    - 任何路径得到零/空包围盒一律抛错，绝不静默返回 BBox(0,0,0,0,0,0)。
    """
    p = str(mesh_path)
    if not p.lower().endswith((".step", ".stp")):
        with open(p, "rb") as fh:
            head = fh.read(64).lstrip()
        if head.startswith(b"VERICUT-model") or head.lower().startswith(b"ply") \
                or p.lower().endswith(".ply"):
            return bbox_from_vericut_poly(p)
    bb_out = _bbox_from_mesh_std(p)
    sx, sy, sz = bb_out.size
    if sx == 0 and sy == 0 and sz == 0:
        bb_out = bbox_from_vericut_poly(p)   # 兜底；空则抛 ValueError
    return bb_out


def _bbox_from_mesh_std(p: str) -> BBox:
    if p.lower().endswith((".step", ".stp")):
        try:
            from build123d import import_step
        except Exception as exc:
            raise RuntimeError("读取 STEP 需要 build123d：pip install build123d") from exc
        bb = import_step(p).bounding_box()
        return BBox(bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z)

    try:
        return bbox_from_stl(p)
    except Exception as exc_stl:
        try:
            from build123d import import_stl
        except Exception:
            raise RuntimeError(
                f"无法读取 STL 成品包围盒（无 build123d 且纯解析失败）: {exc_stl}"
            ) from exc_stl
        bb = import_stl(p).bounding_box()
        return BBox(bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z)


# =============================================================================
# 零件族推断 + 基于样本的毛坯/五轴工装反推（2026-11-14：修复"乱设毛坯"）
# =============================================================================
_BOX_HINTS = ("包容块", "方料", "方块", "矩形毛坯", "矩形块", "box", "block", "prismatic")
_BLADE_HINTS = ("涡轮叶片", "航空叶片", "工作叶片", "导向叶片", "叶片", "turbine_blade",
                "turbine blade", "airfoil", "榫头", "fir-tree", "firtree")
_IMPELLER_HINTS = ("叶轮", "整体叶盘", "impeller", "blisk")


def infer_is_revolution(product: BBox, part_type: str = "", stock_hint: str = "") -> Tuple[bool, str]:
    """推断毛坯是否为回转体（圆柱料）。返回 (is_revolution, 依据)。

    优先级：显式包容块/方料 > 涡轮叶片(非回转) > 叶轮(回转) > 包围盒径向对称性。
    """
    text = f"{part_type} {stock_hint}".lower()
    if any(t in text for t in _BOX_HINTS):
        return False, "explicit_bounding_block_hint"
    if any(t in text for t in _BLADE_HINTS) and not any(t in text for t in _IMPELLER_HINTS):
        return False, "turbine_blade_prismatic_forging_block"
    if any(t in text for t in _IMPELLER_HINTS):
        return True, "rotational_impeller_bar_stock"
    sx, sy, _ = product.size
    cx, cy, _ = product.center
    m = max(sx, sy)
    if m > 0 and abs(sx - sy) / m <= 0.08 and abs(cx) <= 0.05 * sx and abs(cy) <= 0.05 * sy:
        return True, "bbox_radial_symmetry"
    return False, "bbox_non_axisymmetric_prismatic"


def classify_stock_mesh_shape(mesh_path: str, tol: float = 1e-3) -> str:
    """实测样本毛坯网格形状：'box' / 'cylinder' / 'freeform'。

    box：所有顶点坐标都落在包围盒的 min/max 上；
    cylinder：所有顶点在 XY 上要么在半径 R 圆周上、要么在轴心。
    """
    from surface_observability import read_stl_triangles
    tris = read_stl_triangles(str(mesh_path))
    bb = _bbox_from_triangles(tris, str(mesh_path))
    verts = {v for t in tris for v in t}
    sx, sy, sz = bb.size
    tx, ty, tz = max(tol, sx * 1e-4), max(tol, sy * 1e-4), max(tol, sz * 1e-4)

    def _on(v, lo, hi, t):
        return abs(v - lo) <= t or abs(v - hi) <= t

    if all(_on(x, bb.xmin, bb.xmax, tx) and _on(y, bb.ymin, bb.ymax, ty)
           and _on(z, bb.zmin, bb.zmax, tz) for x, y, z in verts):
        return "box"
    cx, cy, _ = bb.center
    radii = [math.hypot(x - cx, y - cy) for x, y, _ in verts]
    rmax = max(radii) if radii else 0.0
    rt = max(tol, rmax * 5e-3)
    if rmax > 0 and all(abs(r - rmax) <= rt or r <= rt for r in radii) \
            and abs(sx - sy) / max(sx, sy) <= 0.02:
        return "cylinder"
    return "freeform"


def parse_vcproject_setup(vcproject: str, nc_override: Optional[str] = None) -> Dict[str, Any]:
    """从样本 .vcproject 抽取机床/控制系统/坐标系/NC/组件附着与五轴旋转轴（正则，容错）。"""
    text = open(vcproject, "r", encoding="utf-8", errors="ignore").read()
    mch = sorted(set(re.findall(r"[^<>\"\s]+\.mch", text, re.I)))
    ctl = sorted(set(re.findall(r"[^<>\"\s]+\.ctl", text, re.I)))
    csys = sorted(set(re.findall(r"<CSystem\s+Name=\"([^\"]+)\"", text)))
    comp_names = re.findall(r"<Component\s+Name=\"([^\"]+)\"", text)
    rotary = [n for n in ("A", "B", "C") if n in comp_names]
    linear = [n for n in ("X", "Y", "Z") if n in comp_names]
    nc_files = re.findall(r"<NCProgram\b[^>]*>\s*<File>([^<]+)</File>", text)
    stock_files = re.findall(
        r"<Component\s+Name=\"Stock\"[\s\S]*?<File>([^<]+)</File>", text)[:1]
    design_files = re.findall(
        r"<Component\s+Name=\"Design\"[\s\S]*?<File>([^<]+)</File>", text)[:1]
    tls = sorted(set(re.findall(r"<Library>([^<]+\.tls)</Library>", text)))
    rtcp = None
    nc_check = nc_override or (nc_files[0] if nc_files else None)
    if nc_check and not os.path.exists(nc_check):
        base = os.path.dirname(os.path.abspath(vcproject))
        bn = os.path.basename(nc_check.replace("\\", "/"))
        for cand in (os.path.join(base, nc_check), os.path.join(base, bn),
                     os.path.join(os.path.dirname(base), "Support_files", bn)):
            if os.path.exists(cand):
                nc_check = cand
                break
    if nc_check and os.path.exists(nc_check):
        with open(nc_check, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(400_000)
        rtcp = bool(re.search(r"G43\.4|G43\.5|TRAORI|M128|TCPM", head))
    return {
        "vcproject": str(vcproject),
        "machine_files": mch,
        "control_files": ctl,
        "csystems": csys,
        "linear_axes": linear,
        "rotary_axes": rotary,
        "is_5axis": len(rotary) >= 2,
        "kinematics": f"5-Axis {'/'.join(linear + rotary)}" if len(rotary) >= 2 else "3-Axis",
        "nc_programs": nc_files,
        "nc_checked_for_rtcp": nc_check,
        "nc_has_rtcp": rtcp,
        "stock_files": stock_files,
        "design_files": design_files,
        "tool_libraries": tls,
    }


def _margins(product: BBox, stock: BBox) -> Dict[str, float]:
    return {
        "x_minus": round(product.xmin - stock.xmin, 4),
        "x_plus": round(stock.xmax - product.xmax, 4),
        "y_minus": round(product.ymin - stock.ymin, 4),
        "y_plus": round(stock.ymax - product.ymax, 4),
        "z_bottom_clamp": round(product.zmin - stock.zmin, 4),
        "z_top": round(stock.zmax - product.zmax, 4),
    }


def inverse_derive_from_sample(
    design_mesh: str,
    sample_stock_mesh: Optional[str] = None,
    sample_vcproject: Optional[str] = None,
    part_type: str = "",
    stock_hint: str = "",
    sample_design_mesh: Optional[str] = None,
) -> Dict[str, Any]:
    """基于样本反推毛坯（形状 + 逐面余量）与五轴工装，而不是凭空设毛坯。

    - 余量来源：``sample_design_mesh`` 与 ``sample_stock_mesh`` 的逐面差（若未给样本设计件，
      则用 ``design_mesh`` 本身——即该件就是样本件）。
    - 形状来源：样本毛坯网格实测形状（box/cylinder），与零件族语义推断交叉校验；
      语义要求包容块/叶片时强制 box。
    - 毛坯 = 目标成品包围盒 + 样本逐面余量，并过体积比/长径比熔断。
    """
    product = bbox_from_mesh(design_mesh)
    is_rev, reason = infer_is_revolution(product, part_type=part_type, stock_hint=stock_hint)
    evidence: Dict[str, Any] = {
        "design_mesh": str(design_mesh),
        "product_bbox": product.__dict__.copy(),
        "product_size_mm": [round(v, 4) for v in product.size],
        "semantic_is_revolution": is_rev,
        "inference_reason": reason,
        "basis": "measured_from_sample",
    }
    spec: Optional[StockSpec] = None
    if sample_stock_mesh and os.path.exists(sample_stock_mesh):
        sstock = bbox_from_mesh(sample_stock_mesh)
        sdesign_path = sample_design_mesh if (sample_design_mesh and os.path.exists(sample_design_mesh)) \
            else design_mesh
        sdesign = product if sdesign_path == design_mesh else bbox_from_mesh(sdesign_path)
        margins = _margins(sdesign, sstock)
        sample_shape = classify_stock_mesh_shape(sample_stock_mesh)
        evidence.update({
            "sample_stock_mesh": str(sample_stock_mesh),
            "sample_design_mesh": str(sdesign_path),
            "sample_stock_bbox": sstock.__dict__.copy(),
            "sample_stock_size_mm": [round(v, 4) for v in sstock.size],
            "sample_stock_shape": sample_shape,
            "sample_allowances_mm": margins,
        })
        # 形状：语义强制 box 的优先；否则以样本实测为准
        if reason in ("explicit_bounding_block_hint", "turbine_blade_prismatic_forging_block"):
            shape = "box"
        elif sample_shape in ("box", "cylinder"):
            shape = sample_shape
        else:
            shape = "cylinder" if is_rev else "box"
        encloses = all(v >= 0 for v in margins.values())
        evidence["sample_stock_encloses_design"] = encloses
        if encloses:
            if shape == "box":
                xmin = product.xmin - margins["x_minus"]
                xmax = product.xmax + margins["x_plus"]
                ymin = product.ymin - margins["y_minus"]
                ymax = product.ymax + margins["y_plus"]
                zmin = product.zmin - margins["z_bottom_clamp"]
                zmax = product.zmax + margins["z_top"]
                spec = StockSpec(
                    "box",
                    {"dx": round(xmax - xmin, 4), "dy": round(ymax - ymin, 4),
                     "dz": round(zmax - zmin, 4)},
                    (xmin, ymin, zmin), product)
            else:
                radial = min(margins["x_minus"], margins["x_plus"],
                             margins["y_minus"], margins["y_plus"])
                sx, sy, sz = product.size
                cx, cy, _ = product.center
                spec = StockSpec(
                    "cylinder",
                    {"diameter": round(max(sx, sy) + 2 * radial, 4),
                     "height": round(sz + margins["z_bottom_clamp"] + margins["z_top"], 4)},
                    (cx, cy, product.zmin - margins["z_bottom_clamp"]), product)
            spec.sanity = check_stock_sanity(spec)
            if not spec.sanity["ok"]:
                raise StockSanityError(f"样本反推毛坯不合理: {spec.sanity['reason']}")
            evidence["derivation"] = "product_bbox + per-face sample allowances"
    if spec is None:
        spec = derive_stock_strict(product, is_revolution=is_rev)
        evidence["derivation"] = "derive_stock_strict(default allowances; no enclosing sample stock)"
    evidence["inferred_is_revolution"] = spec.shape == "cylinder"
    if sample_vcproject and os.path.exists(sample_vcproject):
        evidence["vcproject_setup"] = parse_vcproject_setup(sample_vcproject)
    return {
        "spec": {"shape": spec.shape, "dims": spec.dims, "origin": list(spec.origin),
                 "sanity": spec.sanity, "describe": spec.describe()},
        "stock_spec": spec,
        **evidence,
    }


if __name__ == "__main__":
    # ---- 自测：证明模块能防止"超长圆柱"，且成品优先派生 -------------------------
    results = []

    # 用例1：闭式叶轮（真实回转体，沿 Z 轴）-> 应得合理圆柱料
    impeller = BBox(-135, 135, -135, 135, 0, 82)
    s1 = derive_stock_strict(impeller, is_revolution=True, axis="Z")
    results.append(("闭式叶轮(回转体)", s1.shape == "cylinder" and s1.sanity["ok"],
                    s1.describe()))

    # 用例2：扁平复杂曲面（非回转体，模具型腔类）-> 必须给方块料，绝不圆柱
    mold = BBox(-100, 100, -100, 100, 0, 20)
    s2 = derive_stock_strict(mold, is_revolution=False)
    results.append(("扁平曲面(非回转体)", s2.shape == "box" and s2.sanity["ok"],
                    s2.describe()))

    # 用例3：细长杆被正确识别为非回转体 -> 方块料，不会超长
    rod = BBox(-10, 10, -10, 10, 0, 400)
    s3 = derive_stock_strict(rod, is_revolution=False)
    results.append(("细长杆(非回转体)", s3.shape == "box" and s3.sanity["ok"],
                    s3.describe()))

    # 用例4：把一个细长杆"误判为回转体" -> 必须熔断（防止超长圆柱）
    try:
        derive_stock_strict(rod, is_revolution=True, axis="Z")
        results.append(("细长杆误判回转体", False, "未熔断（BUG）"))
    except StockSanityError as e:
        results.append(("细长杆误判回转体", True, f"已熔断: {e}"))

    # ---- 打印结果 -----------------------------------------------------------------
    print("=" * 70)
    print("stock_derivation 自测结果")
    print("=" * 70)
    all_ok = True
    for name, ok, desc in results:
        all_ok = all_ok and ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<22} -> {desc}")
    print("=" * 70)
    print("总结:", "ALL PASS" if all_ok else "HAS FAILURE")
    raise SystemExit(0 if all_ok else 1)
