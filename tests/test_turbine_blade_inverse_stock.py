# -*- coding: utf-8 -*-
"""航空发动机涡轮叶片/包容块基于样本反推毛坯与五轴联动的可证伪验证（AGENTS.md §8）。

覆盖范围：
  1. VERICUT-model Version-3.0 (.ply/.stl) 与 ASCII .ply/.stl 的包围盒与三角面解析；
     涵盖工作区样本与 E:\\training / E:\\samples（若挂载）。
  2. stock_derivation.inverse_derive_from_sample 基于 turbine_blade_design.stl +
     turbine_blade_stock.stl + turbine_blade_vericut.vcproject 反推 box (42×38×126)
     与五轴联动 (B/C, G43.4)。
  3. WishCADCAMEngine + agent_team 五大实算 Agent 对 "加工航空发动机涡轮叶片五轴联动"
     的意图解析、几何族判定（五轴叶片-复杂曲面类）、box 毛坯反推、Inconel718 五轴
     Macro B（含 G43.4 / B / C，禁出 G71 车削）及运动学沙箱 0 致命错误验证。
  4. SwarmCommander.solve 对涡轮叶片任务的闭环输出（stock_shape=box, 42×38×126,
     success=True）以及反证测试：若强行把涡轮叶片毛坯篡改为 cylinder，
     AdversarialCritic 必须判 RED-WRONG-STOCK-SHAPE 并阻断。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import stock_derivation as sd  # noqa: E402
import surface_observability as so  # noqa: E402
from virtu_omni.agent.agent_team import (  # noqa: E402
    AuditorAndSandboxAgent,
    ChiefArchitectAgent,
    FAMILY_TURBINE_BLADE,
    MachiningAndToolpathAgent,
    ParametricModelingAgent,
    StandardsAndGDAgent,
)
from virtu_omni.agent.swarm_orchestrator import (  # noqa: E402
    AdversarialCritic,
    Blackboard,
    SwarmCommander,
    handoff_gate,
)
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine  # noqa: E402

TURBINE_DESIGN = ROOT / "00_归档" / "01_历史备份" / "eval_archive" / "turbine_blade_design.stl"
TURBINE_STOCK = ROOT / "00_归档" / "01_历史备份" / "eval_archive" / "turbine_blade_stock.stl"
TURBINE_VCPROJ = ROOT / "01_CAD交付件" / "turbine_blade_vericut.vcproject"
IMPELLER_BOX_DESIGN = ROOT / "work" / "impeller_box_stock" / "AE-CI-060_BOX_impeller.stl"
IMPELLER_BOX_STOCK = ROOT / "work" / "impeller_box_stock" / "AE-CI-060_BOX_stock_box.stl"


def test_vericut_model_v3_and_workspace_mesh_bbox(tmp_path: Path):
    # 自构造最小 VERICUT-model Version-3.0 四面体（polygon块：nv / nv行顶点 / nv行法向）
    v3_mesh = tmp_path / "synthetic_v3.ply"
    v3_mesh.write_text(
        "VERICUT-model\nVersion-3.0\n1\n1 1 1\n"
        "3\n0 0 0\n40 0 0\n0 30 0\n0 0 -1\n0 0 -1\n0 0 -1\n"
        "3\n0 0 0\n40 0 0\n0 0 100\n0 -1 0\n0 -1 0\n0 -1 0\n"
        "3\n0 0 0\n0 30 0\n0 0 100\n-1 0 0\n-1 0 0\n-1 0 0\n"
        "3\n40 0 0\n0 30 0\n0 0 100\n0.6 0.8 0.3\n0.6 0.8 0.3\n0.6 0.8 0.3\n",
        encoding="utf-8",
    )
    bb_syn = sd.bbox_from_mesh(v3_mesh)
    sx, sy, sz = bb_syn.size
    assert sx == pytest.approx(40.0)
    assert sy == pytest.approx(30.0)
    assert sz == pytest.approx(100.0)
    assert len(so.read_stl_triangles(str(v3_mesh))) == 4

    # 工作区真实涡轮叶片成品与包容块样本
    bx, by, bz = sd.bbox_from_mesh(TURBINE_DESIGN).size
    stx, sty, stz = sd.bbox_from_mesh(TURBINE_STOCK).size
    assert (round(bx, 2), round(by, 2), round(bz, 2)) == (36.0, 32.0, 121.0)
    assert (round(stx, 2), round(sty, 2), round(stz, 2)) == (42.0, 38.0, 126.0)
    assert sd.classify_stock_mesh_shape(TURBINE_STOCK) == "box"
    assert sd.classify_stock_mesh_shape(IMPELLER_BOX_STOCK) == "box"
    assert sd.bbox_from_mesh(IMPELLER_BOX_DESIGN).size[0] == pytest.approx(62.0, abs=0.1)

    # 若外部样本盘挂载，验证 E:\training & E:\samples 的真实 VERICUT-model / ASCII PLY 解析
    e_train_ply = Path(r"E:\training\day1_review_design.ply")
    if e_train_ply.exists():
        ex, _, ez = sd.bbox_from_mesh(e_train_ply).size
        assert ex == pytest.approx(349.25, abs=0.05)
        assert ez == pytest.approx(254.0, abs=0.05)
    e_sample_ply = Path(r"E:\samples\Support_files\force-impeller_design.ply")
    if e_sample_ply.exists():
        fsx, _, fsz = sd.bbox_from_mesh(e_sample_ply).size
        assert fsx == pytest.approx(48.0, abs=0.1)
        assert fsz == pytest.approx(25.0, abs=0.1)


def test_inverse_derive_from_turbine_sample():
    ev = sd.inverse_derive_from_sample(
        design_mesh=TURBINE_DESIGN,
        sample_stock_mesh=TURBINE_STOCK,
        sample_vcproject=TURBINE_VCPROJ,
        part_type="航空发动机涡轮叶片五轴联动",
    )
    assert ev["basis"] == "measured_from_sample"
    assert ev["spec"]["shape"] == "box"
    assert ev["inferred_is_revolution"] is False
    assert ev["spec"]["dims"] == {"dx": 42.0, "dy": 38.0, "dz": 126.0}
    assert ev["sample_allowances_mm"]["x_minus"] == pytest.approx(3.0, abs=0.1)
    assert ev["sample_allowances_mm"]["z_top"] == pytest.approx(3.0, abs=0.1)
    assert ev["sample_allowances_mm"]["z_bottom_clamp"] == pytest.approx(2.0, abs=0.1)
    vc = ev["vcproject_setup"]
    assert vc["is_5axis"] is True
    assert vc["nc_has_rtcp"] is True


def test_wish_and_agent_team_turbine_blade_five_axis():
    prompt = "加工航空发动机涡轮叶片五轴联动"
    intent = WishCADCAMEngine().parse_wish_intent(prompt)
    assert intent["is_turbine_blade"] is True
    assert intent["material"] == "Inconel718"
    assert intent["stock_shape"] == "box"
    assert intent["stock_dims_mm"] == {"dx": 42.0, "dy": 38.0, "dz": 126.0}
    assert "G43.4" in intent["kinematics"]

    arch = ChiefArchitectAgent().run({"user_prompt": prompt})
    assert arch["geometry_family"] == FAMILY_TURBINE_BLADE
    mod_names = [m["module_name"] for m in arch["sub_modules"]]
    assert any("叶身" in n or "包络" in n or "榫" in n for n in mod_names)

    model = ParametricModelingAgent().run({"architecture": arch})
    assert model["stock_derivation"]["stock_shape"] == "box"
    assert model["stock_derivation"]["stock_dims_mm"] == {"dx": 42.0, "dy": 38.0, "dz": 126.0}

    std = StandardsAndGDAgent().run({"architecture": arch})
    mach = MachiningAndToolpathAgent().run({"architecture": arch, "standards": std})
    gcode = mach["macro_b_code"]
    assert "G43.4" in gcode
    assert "B" in gcode and "C" in gcode
    assert "G71" not in gcode

    audit = AuditorAndSandboxAgent().run({"modeling": model, "machining": mach})
    assert audit["passed"] is True
    assert all(audit["audit_breakdown"].values())
    assert audit["sandbox_verification"]["passed"] is True


def test_swarm_turbine_blade_and_critic_falsifies_cylinder_stock(tmp_path: Path):
    prompt = "加工航空发动机涡轮叶片五轴联动"
    out = SwarmCommander().solve(
        {"part_type": prompt, "material": "Inconel718", "tolerance": "IT6", "surface_finish": "Ra0.8"},
        output_dir=str(tmp_path / "swarm_blade"),
    )
    vr = out["verification_report"]
    assert out["success"] is True, f"turbine swarm failed: {vr}"
    assert vr["stock_shape"] == "box"
    assert vr["stock_dims"] == {"dx": 42.0, "dy": 38.0, "dz": 126.0}
    assert vr["stock_basis"] == "measured_from_product_mesh"
    assert out["results"]["process_plan"]["requires_multiaxis"] is True
    assert out["results"]["geometry"]["evidence_status"] == "measured"
    rec_r = out["results"]["geometry"]["recommended_tool_radius_mm"]
    assert isinstance(rec_r, (int, float)) and not math.isinf(rec_r) and rec_r <= 12.0

    # 反证门（§8.4）：把叶片任务的黑板毛坯篡改成 cylinder，AdversarialCritic 必须判 RED-WRONG-STOCK-SHAPE
    bb = Blackboard()
    handoff_gate(bb, "PRD", None, [], {"task": {"part_type": prompt}, "workers": ["GeometryParsing"]},
                 author="t", basis="asserted")
    for k, payload in [
        ("geometry", {"evidence_status": "measured", "recommended_tool_radius_mm": 0.8}),
        ("process_plan", {"expected_stock_shape": "box", "online": False}),
        ("toolpath", {"stock_basis": "measured_from_product_mesh", "stock_shape": "cylinder",
                      "stock_dims": {"diameter": 270.0, "height": 82.0}}),
        ("audit", {"passed": True, "autodiff": {"basis": "not_provided"}}),
    ]:
        lease = bb.acquire("tester", k)
        bb.write(lease, k, payload, basis="measured", evidence="falsification")
        bb.release(lease)

    debate = AdversarialCritic().debate(
        {"success": True, "expected_stock_shape": "box"},
        bb,
    )
    ids = [d["id"] for d in debate["red_team_findings"]]
    assert "RED-WRONG-STOCK-SHAPE" in ids
    assert debate["gate_passed"] is False
