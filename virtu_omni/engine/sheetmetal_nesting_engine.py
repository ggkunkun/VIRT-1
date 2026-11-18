# -*- coding: utf-8 -*-
"""sheetmetal_nesting_engine.py — 二维真形状排样优化与激光/等离子下料利用率计算引擎.

算法体系（shapely 多边形几何，非矩形包络近似）：
1. 零件几何：显式轮廓多边形（contour）优先；无轮廓时退化为长×宽矩形。
2. 标准板料库与余料管理 (SheetStock: 1000x2000, 1250x2500, 1500x3000 mm)。
3. 底左填充 (Bottom-Left-Fill)：候选位置取自板边与已 placement 顶点 + 割缝偏移，
   支持 0/90/180/270 四向旋转，碰撞判定用多边形距离（含 kerf 间隙）与重叠面积双重检查。
4. 利用率按零件真实轮廓面积计算（不是包络矩形面积）。
5. verify_nesting_layout：独立 oracle，复算重叠/间隙/包含/利用率，空集判红。
6. 自动导出排样 DXF 工程图 (ezdxf)，绘制真实轮廓。
"""

from __future__ import annotations
import os
import math
import time
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict

import ezdxf
from shapely.geometry import Polygon
from shapely.affinity import rotate as sh_rotate, translate as sh_translate

_EPS = 1e-9


@dataclass
class NestingPart:
    """待排样零件规格。contour 为真形状轮廓（mm，任意简单多边形）；缺省用长×宽矩形。"""
    part_id: str
    length: float                      # 外形长 (mm)
    width: float                       # 外形宽 (mm)
    quantity: int = 1                  # 需求数量
    material: str = "SS304"
    thickness: float = 2.0
    contour: Optional[List[Tuple[float, float]]] = None
    placed_positions: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, rotation_deg)

    def polygon(self) -> Polygon:
        if self.contour and len(self.contour) >= 3:
            poly = Polygon(self.contour)
            if not poly.is_valid or poly.area <= _EPS:
                raise ValueError(f"零件 {self.part_id} 轮廓非法（自交或零面积）")
        else:
            poly = Polygon([(0, 0), (self.length, 0),
                            (self.length, self.width), (0, self.width)])
        minx, miny = poly.bounds[0], poly.bounds[1]
        return sh_translate(poly, -minx, -miny)

    @property
    def unit_area(self) -> float:
        if self.contour and len(self.contour) >= 3:
            return float(Polygon(self.contour).area)
        return self.length * self.width

    @property
    def total_area(self) -> float:
        return self.unit_area * self.quantity


@dataclass
class SheetStock:
    """原材料母板规格。"""
    sheet_id: str = "Stock_1000x2000"
    length: float = 2000.0             # 板长 X (mm)
    width: float = 1000.0              # 板宽 Y (mm)
    thickness: float = 2.0
    material: str = "SS304"
    edge_margin: float = 10.0          # 板边不切割余量 (mm)
    kerf_spacing: float = 5.0          # 割缝与零件间最小间隙 (mm)

    @property
    def total_area(self) -> float:
        return self.length * self.width

    @property
    def usable_length(self) -> float:
        return self.length - 2 * self.edge_margin

    @property
    def usable_width(self) -> float:
        return self.width - 2 * self.edge_margin


def _orientations(poly: Polygon, allow_rotation: bool) -> List[Tuple[float, Polygon]]:
    angles = [0.0, 90.0, 180.0, 270.0] if allow_rotation else [0.0]
    out: List[Tuple[float, Polygon]] = []
    seen = set()
    for ang in angles:
        p = sh_rotate(poly, ang, origin=(0, 0)) if ang else poly
        minx, miny = p.bounds[0], p.bounds[1]
        p = sh_translate(p, -minx, -miny)
        # Dedup by actual vertex set: bounds+area collide for L-shapes whose
        # four rotations share the same envelope, silently dropping interlock.
        key = tuple(sorted((round(x, 6), round(y, 6)) for x, y in p.exterior.coords))
        if key in seen:
            continue
        seen.add(key)
        out.append((ang, p))
    return out


class SheetMetalNestingEngine:
    """钣金排样与利用率优化引擎（真形状多边形 BLF）。"""

    def __init__(self, stock: Optional[SheetStock] = None):
        self.stock = stock or SheetStock()

    def optimize_nesting(self, parts: List[NestingPart], allow_rotation: bool = True) -> Dict[str, Any]:
        """执行二维排样布局优化。"""
        t0 = time.perf_counter()
        stock = self.stock

        flat_instances: List[Dict[str, Any]] = []
        for p in parts:
            poly = p.polygon()
            for i in range(p.quantity):
                flat_instances.append({
                    "part_id": p.part_id,
                    "inst_id": f"{p.part_id}_{i+1}",
                    "poly": poly,
                    "area": float(poly.area),
                })
        flat_instances.sort(key=lambda x: x["area"], reverse=True)

        placed_items: List[Dict[str, Any]] = []
        unplaced_items: List[Dict[str, Any]] = []
        placed_polys: List[Polygon] = []

        kerf = stock.kerf_spacing
        margin = stock.edge_margin
        max_x = stock.length - margin
        max_y = stock.width - margin

        for inst in flat_instances:
            orientations = _orientations(inst["poly"], allow_rotation)
            best = None  # (y, x, orient_idx, angle, poly)
            candidate_xs = {margin}
            candidate_ys = {margin}
            for pp in placed_polys:
                for vx, vy in pp.exterior.coords:
                    if vx + kerf < max_x:
                        candidate_xs.add(round(vx + kerf, 6))
                    if vy + kerf < max_y:
                        candidate_ys.add(round(vy + kerf, 6))
            xs = sorted(candidate_xs)
            ys = sorted(candidate_ys)

            for cur_y in ys:
                for cur_x in xs:
                    for oi, (ang, opoly) in enumerate(orientations):
                        w_cand, h_cand = opoly.bounds[2], opoly.bounds[3]
                        if cur_x + w_cand > max_x + _EPS or cur_y + h_cand > max_y + _EPS:
                            continue
                        cand = sh_translate(opoly, cur_x, cur_y)
                        collision = False
                        for pp in placed_polys:
                            if cand.distance(pp) < kerf - 1e-6:
                                collision = True
                                break
                            if cand.intersection(pp).area > 1e-6:
                                collision = True
                                break
                        if collision:
                            continue
                        score = (cur_y, cur_x, oi)
                        if best is None or score < best[0]:
                            best = (score, ang, cand)
                    if best is not None and best[0][0] <= margin + _EPS:
                        break
                if best is not None and best[0][0] <= margin + _EPS:
                    break

            if best is not None:
                (by, bx, _), brot, cand = best
                placed_polys.append(cand)
                minx, miny, maxx, maxy = cand.bounds
                placed_items.append({
                    "part_id": inst["part_id"],
                    "inst_id": inst["inst_id"],
                    "x": round(bx, 2),
                    "y": round(by, 2),
                    "width": round(maxx - minx, 2),
                    "height": round(maxy - miny, 2),
                    "rotation_deg": brot,
                    "area": inst["area"],
                    "contour": [(round(px, 4), round(py, 4))
                                for px, py in cand.exterior.coords[:-1]],
                })
            else:
                unplaced_items.append({k: inst[k] for k in ("part_id", "inst_id", "area")})

        net_part_area = sum(item["area"] for item in placed_items)
        utilization_rate = (net_part_area / stock.total_area) * 100.0

        bounding_length = max((item["x"] + item["width"] for item in placed_items), default=0.0)
        bounding_width = max((item["y"] + item["height"] for item in placed_items), default=0.0)
        local_nesting_area = max(1.0, bounding_length * bounding_width)
        local_utilization = (net_part_area / local_nesting_area) * 100.0

        dt_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "status": "success" if not unplaced_items else "partial",
            "nesting_mode": "true_shape" if any(p.contour for p in parts) else "rectangular",
            "stock_spec": asdict(stock),
            "total_requested_parts": len(flat_instances),
            "placed_count": len(placed_items),
            "unplaced_count": len(unplaced_items),
            "net_parts_area_mm2": round(net_part_area, 2),
            "stock_area_mm2": round(stock.total_area, 2),
            "overall_utilization_rate": round(utilization_rate, 2),
            "local_bounding_utilization": round(local_utilization, 2),
            "bounding_envelope_mm": (round(bounding_length, 1), round(bounding_width, 1)),
            "placed_items": placed_items,
            "unplaced_items": unplaced_items,
            "execution_ms": round(dt_ms, 2)
        }

    def export_nesting_dxf(self, nesting_result: Dict[str, Any], output_path: str) -> str:
        """导出排样工程图 DXF 文件（真实轮廓）。"""
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()

        doc.layers.add("STOCK_FRAME", color=1, linetype="CONTINUOUS")
        doc.layers.add("PARTS_CUT", color=7, linetype="CONTINUOUS")
        doc.layers.add("PART_TEXT", color=3, linetype="CONTINUOUS")
        doc.layers.add("DIM_INFO", color=4, linetype="CONTINUOUS")

        stock = nesting_result["stock_spec"]
        sl = stock["length"]
        sw = stock["width"]

        msp.add_lwpolyline([(0, 0), (sl, 0), (sl, sw), (0, sw)], close=True, dxfattribs={"layer": "STOCK_FRAME"})

        for item in nesting_result.get("placed_items", []):
            x = item["x"]
            y = item["y"]
            w = item["width"]
            h = item["height"]
            pts = item.get("contour") or [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "PARTS_CUT"})
            msp.add_text(f"{item['inst_id']}", dxfattribs={"layer": "PART_TEXT", "height": min(12.0, h * 0.3)}).set_placement((x + 2, y + 2))

        rate = nesting_result.get("overall_utilization_rate", 0.0)
        local_rate = nesting_result.get("local_bounding_utilization", 0.0)
        placed_n = nesting_result.get("placed_count", 0)
        info_str = f"钣金排样方案 | 母板: {sl:.0f}x{sw:.0f}mm | 零件数: {placed_n} | 全板利用率: {rate:.1f}% | 局部利用率: {local_rate:.1f}%"
        msp.add_text(info_str, dxfattribs={"layer": "DIM_INFO", "height": 18.0}).set_placement((20, sw + 25))

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc.saveas(output_path)
        return output_path


def verify_nesting_layout(nesting_result: Dict[str, Any]) -> Dict[str, Any]:
    """独立 oracle：从落盘轮廓复算重叠/割缝间隙/板边包含/利用率。空集判红。"""
    violations: List[str] = []
    stock = nesting_result.get("stock_spec") or {}
    sl = float(stock.get("length", 0))
    sw = float(stock.get("width", 0))
    margin = float(stock.get("edge_margin", 0))
    kerf = float(stock.get("kerf_spacing", 0))
    items = nesting_result.get("placed_items") or []
    if not items:
        violations.append("empty_layout: 无已摆放零件，不得判合格")

    polys: List[Polygon] = []
    for item in items:
        pts = item.get("contour")
        if pts and len(pts) >= 3:
            poly = Polygon(pts)
        else:
            x, y, w, h = item["x"], item["y"], item["width"], item["height"]
            poly = Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
        if not poly.is_valid or poly.area <= _EPS:
            violations.append(f"invalid_polygon: {item.get('inst_id')}")
        polys.append(poly)
        minx, miny, maxx, maxy = poly.bounds
        if minx < margin - 1e-6 or miny < margin - 1e-6 or \
                maxx > sl - margin + 1e-6 or maxy > sw - margin + 1e-6:
            violations.append(f"out_of_stock: {item.get('inst_id')} bounds={poly.bounds}")

    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j]).area
            if inter > 1e-6:
                violations.append(f"overlap: {items[i].get('inst_id')} x {items[j].get('inst_id')} area={inter:.4f}")
            elif polys[i].distance(polys[j]) < kerf - 1e-6:
                violations.append(f"kerf_gap: {items[i].get('inst_id')} x {items[j].get('inst_id')} dist={polys[i].distance(polys[j]):.4f} < {kerf}")

    net_area = sum(p.area for p in polys)
    recomputed = (net_area / (sl * sw)) * 100.0 if sl * sw > 0 else 0.0
    reported = float(nesting_result.get("overall_utilization_rate", 0.0))
    if abs(recomputed - reported) > 0.05:
        violations.append(f"utilization_mismatch: reported={reported} recomputed={recomputed:.4f}")

    return {
        "passed": not violations,
        "violations": violations,
        "recomputed_utilization_pct": round(recomputed, 4),
        "checked_parts": len(polys),
        "basis": "measured",
    }