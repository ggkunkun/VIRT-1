# -*- coding: utf-8 -*-
"""P1a 回归：真形状套料（shapely 多边形 BLF）+ 布局核验 oracle。

覆盖：
  A. L 形零件互锁：真形状能放 2 件，矩形包络只能放 1 件（可证伪的 superiority）。
  B. 利用率按真实轮廓面积计算；旋转开关真实生效。
  C. verify_nesting_layout 反证：植入重叠/间隙不足/越界/空集必须判红。
  D. DXF 导出真实轮廓（6 顶点 L 形，不是 4 顶点矩形）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ezdxf
import pytest

from virtu_omni.engine.sheetmetal_nesting_engine import (
    SheetMetalNestingEngine, SheetStock, NestingPart, verify_nesting_layout,
)

L_CONTOUR = [(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40)]


def _l_stock():
    return SheetStock(sheet_id="S50x70", length=50.0, width=70.0,
                      edge_margin=5.0, kerf_spacing=0.0)


def test_true_shape_interlock_beats_aabb():
    parts = [NestingPart(part_id="L", length=40, width=40, quantity=2, contour=L_CONTOUR)]
    res = SheetMetalNestingEngine(stock=_l_stock()).optimize_nesting(parts)
    assert res["nesting_mode"] == "true_shape"
    assert res["placed_count"] == 2, res
    assert res["net_parts_area_mm2"] == pytest.approx(2400.0, abs=0.1)
    assert verify_nesting_layout(res)["passed"] is True

    rects = [NestingPart(part_id="R", length=40, width=40, quantity=2)]
    res_r = SheetMetalNestingEngine(stock=_l_stock()).optimize_nesting(rects)
    assert res_r["placed_count"] == 1, "矩形包络竟能放下 2 件=测试构造失效"


def test_rotation_switch_is_real():
    parts = [NestingPart(part_id="L", length=40, width=40, quantity=2, contour=L_CONTOUR)]
    res = SheetMetalNestingEngine(stock=_l_stock()).optimize_nesting(parts, allow_rotation=False)
    assert res["placed_count"] == 1, "禁旋转仍互锁=旋转分支没生效"
    assert all(it["rotation_deg"] == 0.0 for it in res["placed_items"])


def test_oracle_rejects_planted_overlap():
    stock = SheetStock(length=200, width=200, edge_margin=5, kerf_spacing=5)
    res = SheetMetalNestingEngine(stock=stock).optimize_nesting(
        [NestingPart(part_id="A", length=60, width=60, quantity=1)])
    assert verify_nesting_layout(res)["passed"] is True
    bad = dict(res)
    item = dict(res["placed_items"][0])
    item["inst_id"] = "GHOST"
    item["contour"] = [(item["x"] + 1, item["y"] + 1), (item["x"] + 40, item["y"] + 1),
                       (item["x"] + 40, item["y"] + 40), (item["x"] + 1, item["y"] + 40)]
    bad["placed_items"] = res["placed_items"] + [item]
    v = verify_nesting_layout(bad)
    assert v["passed"] is False
    assert any(s.startswith("overlap") for s in v["violations"]), v


def test_oracle_rejects_kerf_and_bounds_and_empty():
    stock = SheetStock(length=200, width=200, edge_margin=5, kerf_spacing=5)
    base = SheetMetalNestingEngine(stock=stock).optimize_nesting(
        [NestingPart(part_id="A", length=60, width=60, quantity=1)])
    item = base["placed_items"][0]
    near = dict(item, inst_id="NEAR",
                contour=[(item["x"] + 62, item["y"]), (item["x"] + 102, item["y"]),
                         (item["x"] + 102, item["y"] + 40), (item["x"] + 62, item["y"] + 40)])
    v = verify_nesting_layout(dict(base, placed_items=[item, near]))
    assert v["passed"] is False and any(s.startswith("kerf_gap") for s in v["violations"]), v

    out = dict(item, inst_id="OUT",
               contour=[(190, 190), (230, 190), (230, 230), (190, 230)])
    v2 = verify_nesting_layout(dict(base, placed_items=[out]))
    assert v2["passed"] is False and any(s.startswith("out_of_stock") for s in v2["violations"]), v2

    v3 = verify_nesting_layout(dict(base, placed_items=[]))
    assert v3["passed"] is False and any("empty_layout" in s for s in v3["violations"])


def test_oracle_rejects_utilization_mismatch():
    stock = SheetStock(length=200, width=200, edge_margin=5, kerf_spacing=5)
    res = SheetMetalNestingEngine(stock=stock).optimize_nesting(
        [NestingPart(part_id="A", length=60, width=60, quantity=1)])
    v = verify_nesting_layout(dict(res, overall_utilization_rate=99.9))
    assert v["passed"] is False
    assert any(s.startswith("utilization_mismatch") for s in v["violations"])


def test_dxf_exports_real_contour(tmp_path):
    parts = [NestingPart(part_id="L", length=40, width=40, quantity=1, contour=L_CONTOUR)]
    eng = SheetMetalNestingEngine(stock=_l_stock())
    res = eng.optimize_nesting(parts)
    path = str(tmp_path / "nest.dxf")
    eng.export_nesting_dxf(res, path)
    doc = ezdxf.readfile(path)
    cuts = [e for e in doc.modelspace().query("LWPOLYLINE") if e.dxf.layer == "PARTS_CUT"]
    assert len(cuts) == 1
    assert len(cuts[0].get_points("xy")) == 6, "DXF 画的是矩形包络而非真轮廓"


def test_invalid_contour_rejected():
    bowtie = [(0, 0), (40, 40), (40, 0), (0, 40)]
    with pytest.raises(ValueError):
        NestingPart(part_id="X", length=40, width=40, contour=bowtie).polygon()


def test_rectangular_regression_18_parts():
    stock = SheetStock(length=1000.0, width=800.0, edge_margin=10.0, kerf_spacing=5.0)
    parts = [
        NestingPart(part_id="P1", length=200.0, width=150.0, quantity=4),
        NestingPart(part_id="P2", length=180.0, width=100.0, quantity=6),
        NestingPart(part_id="P3", length=120.0, width=80.0, quantity=8),
    ]
    res = SheetMetalNestingEngine(stock=stock).optimize_nesting(parts, allow_rotation=True)
    assert res["status"] == "success"
    assert res["placed_count"] == 18
    assert res["overall_utilization_rate"] > 35.0
    assert res["local_bounding_utilization"] > 75.0
    assert verify_nesting_layout(res)["passed"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))