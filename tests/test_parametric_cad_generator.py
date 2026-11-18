# -*- coding: utf-8 -*-
"""P0 回归：参数化 CAD 生成器 + SWARM 消费生成 CAD（不再样本回放）。

覆盖：
  A. 四族 BRep 体积守恒（vs 解析参照，误差 <= 1%）。
  B. 可证伪：改规格 → 体积/包络必须变；非法槽/无规格/自由曲面必须拒绝或如实返回 None。
  C. SWARM 集成：带 spec 的任务 → design_source=generated_cad，几何实测打在生成 STL 上，
     端到端 success=True；无规格 → 样本兜底且 design_source 如实标注；坏规格 → generation_failed。
"""
import os
import sys
import json
import math
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from virtu_omni.engine.parametric_cad_generator import (
    generate_design_assets, build_solid, analytic_volume, classify_family,
)
from virtu_omni.agent.swarm_orchestrator import SwarmCommander
from swarm_test_support import swarm_workspace  # noqa: F401


def test_shaft_volume_conservation_with_groove(tmp_path):
    spec = {"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0, "groove_radii": [3.0]}
    r = generate_design_assets({"spec": spec}, str(tmp_path))
    assert r is not None and r["design_source"] == "generated_cad"
    assert r["volume_error_pct"] <= 1.0, r
    # 解析参照独立复算：圆柱-孔-环槽（Pappus）
    ro, ri, L, rr = 26.5, 7.0, 45.0, 3.0
    groove = math.pi ** 2 * ro * rr ** 2 - (4.0 * math.pi / 3.0) * rr ** 3
    expect = math.pi * (ro ** 2 - ri ** 2) * L - groove
    assert abs(r["volume_mm3"] - expect) / expect < 0.01
    assert Path(r["design_stl"]).is_file()


def test_spec_sensitivity_falsifiable(tmp_path):
    base = {"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0}
    r1 = generate_design_assets({"spec": base}, str(tmp_path / "a"))
    r2 = generate_design_assets({"spec": {**base, "d_outer": 80.0}}, str(tmp_path / "b"))
    assert r2["volume_mm3"] > r1["volume_mm3"], "改外径体积不变=生成器没消费规格"
    assert r2["bbox_mm"]["dx"] == pytest.approx(80.0, abs=0.1)
    assert r1["bbox_mm"]["dx"] == pytest.approx(53.0, abs=0.1)


def test_flange_bolt_holes_volume(tmp_path):
    spec = {"d_outer": 120.0, "d_inner": 40.0, "thickness": 18.0,
            "pcd": 90.0, "bolt_hole_count": 4, "bolt_hole_dia": 11.0}
    r = generate_design_assets({"spec": spec}, str(tmp_path))
    expect = (math.pi * (60.0 ** 2 - 20.0 ** 2) * 18.0
              - 4 * math.pi * 5.5 ** 2 * 18.0)
    assert abs(r["volume_mm3"] - expect) / expect < 0.01
    assert r["family"] == "FLANGE_PLATE"


def test_bracket_and_sheet_families(tmp_path):
    rb = generate_design_assets({"spec": {"base_width": 60.0, "center_height": 50.0}}, str(tmp_path / "b"))
    rs = generate_design_assets({"spec": {"sheet_thickness": 2.0, "length": 200.0, "width": 100.0}}, str(tmp_path / "s"))
    assert rb["family"] == "BEARING_BRACKET" and rb["volume_error_pct"] <= 1.0
    assert rs["family"] == "SHEET_METAL_BEND"
    assert rs["volume_mm3"] == pytest.approx(200.0 * 100.0 * 2.0, rel=1e-6)


def test_invalid_groove_rejected():
    with pytest.raises(ValueError):
        build_solid("ROTATIONAL_SHAFT",
                    {"d_outer": 20.0, "d_inner": 14.0, "overall_len": 45.0, "groove_radii": [5.0]})
    with pytest.raises(ValueError):
        build_solid("ROTATIONAL_SHAFT", {"d_outer": 20.0, "d_inner": 30.0, "overall_len": 45.0})


def test_no_spec_and_freeform_return_none(tmp_path):
    assert generate_design_assets({}, str(tmp_path)) is None
    assert generate_design_assets({"wish": "封闭式叶轮 五轴联动"}, str(tmp_path)) is None
    assert generate_design_assets({"wish": "做个零件"}, str(tmp_path)) is None


def test_wish_with_explicit_dims_generates(tmp_path):
    r = generate_design_assets({"wish": "45号钢轴 外径80 内径20 总长120"}, str(tmp_path))
    assert r is not None
    assert r["spec"]["d_outer"] == 80.0 and r["spec"]["overall_len"] == 120.0


def test_swarm_consumes_generated_cad(swarm_workspace):
    task = {
        "spec": {"d_outer": 80.0, "d_inner": 20.0, "overall_len": 120.0},
        "part_type": "45号钢阶梯轴",
        "material": "Steel45",
        "surface_finish": "Ra1.6",
        "tolerance": "IT8",
        "spindle_axis": "Z",
        "tool_radius_mm": 3.0,
        "allowance_mm": 0.05,
    }
    out = str(swarm_workspace.root / "runs" / "swarm" / "p0_generated")
    res = SwarmCommander().solve(task, output_dir=out)
    vr = res["verification_report"]
    assert vr["design_source"] == "generated_cad", vr
    assert vr["cad_generation"]["volume_error_pct"] <= 1.0
    assert vr["geometry_evidence_status"] == "measured", vr
    # 几何证据必须打在生成的 STL 上，而不是样本库
    geom_mesh = Path(res["results"]["geometry"]["mesh"])
    assert geom_mesh.parent.name == "cad", geom_mesh
    assert geom_mesh.is_file()
    assert res["success"] is True, vr
    assert vr["stock_basis"] == "measured_from_product_mesh", vr
    snap = json.loads(Path(res["artifact_blackboard"]).read_text(encoding="utf-8"))
    assert snap["design_provenance"]["value"]["design_source"] == "generated_cad"
    assert snap["design_provenance"]["meta"]["basis"] == "measured"


def test_swarm_sample_fallback_is_labeled(swarm_workspace):
    task = {"part_type": "闭式叶轮", "allowance_mm": 0.01, "tool_radius_mm": 3.0}
    out = str(swarm_workspace.root / "runs" / "swarm" / "p0_fallback")
    res = SwarmCommander().solve(task, output_dir=out)
    vr = res["verification_report"]
    assert vr["design_source"] == "fallback_nasa1975", vr
    assert vr["cad_generation"] == {}


def test_swarm_bad_spec_reports_generation_failed(swarm_workspace):
    task = {"spec": {"d_outer": 20.0, "d_inner": 30.0, "overall_len": 45.0},
            "part_type": "轴", "allowance_mm": 0.05}
    out = str(swarm_workspace.root / "runs" / "swarm" / "p0_badspec")
    res = SwarmCommander().solve(task, output_dir=out)
    vr = res["verification_report"]
    assert vr["design_source"] == "generation_failed", vr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))