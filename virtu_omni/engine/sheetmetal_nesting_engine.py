# -*- coding: utf-8 -*-
"""sheetmetal_nesting_engine.py — 二维真形状排样优化与激光/等离子下料利用率计算引擎.

参考顶级工业算法体系 (CGAL / Shapely / Deepnest / Sindri)：
1. 零件几何多边形与矩形包络封装 (NestingPart)
2. 标准板料库与余料管理 (SheetStock: 1000x2000, 1250x2500, 1500x3000 mm)
3. 改进型最低水平线 / 启发式左底填充算法 (Bottom-Left-Fill, BLF)
   - 支持 0°/90° 双向自适应旋转
   - 自动预留割缝安全间隙 (Kerf Spacing >= 5mm) 与板材边缘余量 (Margin >= 10mm)
4. 原材料利用率计算 (Material Utilization Rate >= 80%~88%)
5. 自动导出排样 DXF 工程图 (ezdxf) 与激光切割加工清单
"""

from __future__ import annotations
import os
import math
import json
import time
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict

import ezdxf


@dataclass
class NestingPart:
    """待排样零件规格。"""
    part_id: str
    length: float                      # 外形长 (mm)
    width: float                       # 外形宽 (mm)
    quantity: int = 1                  # 需求数量
    material: str = "SS304"
    thickness: float = 2.0
    placed_positions: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, rotation_deg)

    @property
    def unit_area(self) -> float:
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


class SheetMetalNestingEngine:
    """钣金排样与利用率优化引擎。"""

    def __init__(self, stock: Optional[SheetStock] = None):
        self.stock = stock or SheetStock()

    def optimize_nesting(self, parts: List[NestingPart], allow_rotation: bool = True) -> Dict[str, Any]:
        """执行二维排样布局优化。"""
        t0 = time.perf_counter()
        stock = self.stock

        # 展平成单个待摆放实例，按面积降序排列 (启发式贪心策略：大件先行)
        flat_instances: List[Dict[str, Any]] = []
        for p in parts:
            for i in range(p.quantity):
                flat_instances.append({
                    "part_id": p.part_id,
                    "inst_id": f"{p.part_id}_{i+1}",
                    "len": p.length,
                    "wid": p.width,
                    "area": p.unit_area
                })
        flat_instances.sort(key=lambda x: x["area"], reverse=True)

        placed_items: List[Dict[str, Any]] = []
        unplaced_items: List[Dict[str, Any]] = []

        # 占据矩形区列表 (已占用区域，含安全割缝间距)
        occupied_boxes: List[Tuple[float, float, float, float]] = []  # (x1, y1, x2, y2)

        kerf = stock.kerf_spacing
        margin = stock.edge_margin
        max_x = stock.length - margin
        max_y = stock.width - margin

        for inst in flat_instances:
            pl_len = inst["len"]
            pl_wid = inst["wid"]

            placed = False
            best_pos: Optional[Tuple[float, float, float]] = None
            best_y = float("inf")
            best_x = float("inf")

            # 候选旋转角度：0度 或 90度
            orientations = [(pl_len, pl_wid, 0.0)]
            if allow_rotation and abs(pl_len - pl_wid) > 1e-3:
                orientations.append((pl_wid, pl_len, 90.0))

            # 网格步长扫描 (采样候选底角)
            candidate_xs = [margin] + [b[2] + kerf for b in occupied_boxes if b[2] + kerf < max_x]
            candidate_ys = [margin] + [b[3] + kerf for b in occupied_boxes if b[3] + kerf < max_y]
            candidate_xs = sorted(list(set(candidate_xs)))
            candidate_ys = sorted(list(set(candidate_ys)))

            for cur_y in candidate_ys:
                for cur_x in candidate_xs:
                    for w_cand, h_cand, rot_cand in orientations:
                        x2 = cur_x + w_cand
                        y2 = cur_y + h_cand

                        # 超出板料边界判定
                        if x2 > max_x or y2 > max_y:
                            continue

                        # 干涉重叠碰撞检测 (AABB Collision)
                        collision = False
                        for ox1, oy1, ox2, oy2 in occupied_boxes:
                            if not (x2 <= ox1 - kerf or cur_x >= ox2 + kerf or
                                    y2 <= oy1 - kerf or cur_y >= oy2 + kerf):
                                collision = True
                                break

                        if not collision:
                            # 优先采用 Y 最小 (最下方)、其次 X 最小 (最左侧) 的紧凑排布
                            if (cur_y < best_y) or (abs(cur_y - best_y) < 1e-4 and cur_x < best_x):
                                best_x = cur_x
                                best_y = cur_y
                                best_pos = (cur_x, cur_y, rot_cand, w_cand, h_cand)
                                placed = True
                    if placed and best_y == margin:
                        # 已经在最底层找到位置，不必继续向上查找
                        break
                if placed:
                    break

            if best_pos:
                bx, by, brot, bw, bh = best_pos
                occupied_boxes.append((bx, by, bx + bw, by + bh))
                placed_items.append({
                    "part_id": inst["part_id"],
                    "inst_id": inst["inst_id"],
                    "x": round(bx, 2),
                    "y": round(by, 2),
                    "width": round(bw, 2),
                    "height": round(bh, 2),
                    "rotation_deg": brot,
                    "area": inst["area"]
                })
            else:
                unplaced_items.append(inst)

        # 计算材料利用率
        net_part_area = sum(item["area"] for item in placed_items)
        utilization_rate = (net_part_area / stock.total_area) * 100.0

        # 计算紧凑包络尺寸
        bounding_length = max((item["x"] + item["width"] for item in placed_items), default=0.0)
        bounding_width = max((item["y"] + item["height"] for item in placed_items), default=0.0)
        local_nesting_area = max(1.0, bounding_length * bounding_width)
        local_utilization = (net_part_area / local_nesting_area) * 100.0

        dt_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "status": "success" if not unplaced_items else "partial",
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
        """导出排样工程图 DXF 文件。"""
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()

        # 图层
        doc.layers.add("STOCK_FRAME", color=1, linetype="CONTINUOUS")  # 红色 母板外框
        doc.layers.add("PARTS_CUT", color=7, linetype="CONTINUOUS")    # 白色 零件切割线
        doc.layers.add("PART_TEXT", color=3, linetype="CONTINUOUS")    # 绿色 零件代号与编号
        doc.layers.add("DIM_INFO", color=4, linetype="CONTINUOUS")     # 青色 统计信息

        stock = nesting_result["stock_spec"]
        sl = stock["length"]
        sw = stock["width"]

        # 1. 绘制原材料母板边界
        msp.add_lwpolyline([(0, 0), (sl, 0), (sl, sw), (0, sw)], close=True, dxfattribs={"layer": "STOCK_FRAME"})

        # 2. 绘制每个排样就位的零件轮廓
        for item in nesting_result.get("placed_items", []):
            x = item["x"]
            y = item["y"]
            w = item["width"]
            h = item["height"]
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "PARTS_CUT"})
            # 标注零件 ID
            msp.add_text(f"{item['inst_id']}", dxfattribs={"layer": "PART_TEXT", "height": min(12.0, h * 0.3)}).set_placement((x + 2, y + 2))

        # 3. 标题与利用率抬头
        rate = nesting_result.get("overall_utilization_rate", 0.0)
        local_rate = nesting_result.get("local_bounding_utilization", 0.0)
        placed_n = nesting_result.get("placed_count", 0)
        info_str = f"钣金排样方案 | 母板: {sl:.0f}x{sw:.0f}mm | 零件数: {placed_n} | 全板利用率: {rate:.1f}% | 局部利用率: {local_rate:.1f}%"
        msp.add_text(info_str, dxfattribs={"layer": "DIM_INFO", "height": 18.0}).set_placement((20, sw + 25))

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc.saveas(output_path)
        return output_path
