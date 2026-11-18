# -*- coding: utf-8 -*-
"""量产仿真系统契约测试（植入坏样本必须红）。"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_prod import assurance, config, lint, post, programs, sim  # noqa: E402

PROJ = Path(r"E:\vericut_impeller_run\proj.vcproject")
STOCK_TOP = 152.85


def _runtime(key="prod_5ax_fanuc_0imf"):
    p = config.load()
    m = p.machines[key]
    return {
        "label": m.label, "dialect": m.dialect, "safe_z": 10.0,
        "tc_z": m.tool_change_point["z"], "tc_x": 0.0, "tc_y": 0.0,
        "travel_mm": m.travel_mm, "rotary_limits_deg": m.rotary_limits_deg,
        "rotary": m.rotary_limits_deg, "tool_change_s": m.tool_change_s,
    }


def _tools():
    p = config.load()
    return {tid: {"id": tid, "diameter": t.diameter_mm, "gauge_length": t.gauge_length_mm,
                  "holder_length": t.holder_length_mm,
                  "holder_radius": t.holder_diameter_mm / 2.0,
                  "taylor_c": t.taylor_c, "taylor_n": t.taylor_n}
            for tid, t in p.tools.items()}


def _stock():
    p = config.load()
    return {"material": p.part["material"], "size": p.stock["size_mm"]}


def _emitted(prog, dialect="fanuc", key=None):
    p = config.load()
    k = key or {"fanuc": "prod_5ax_fanuc_0imf", "siemens": "prod_5ax_siemens_840dsl",
                "hnc": "prod_5ax_hnc8"}[dialect]
    m = p.machines[k]
    mach = _runtime(k)
    return post.emit(prog, mach, _stock())["nc"], mach


# ---------------------------------------------------------------- 配置门
def test_config_passes_on_repo_config():
    p = config.load()
    checks = config.validate(p, programs.design_bbox(p.part["design_file"]))
    assert config.summary(checks)["failed"] == 0


def test_config_flags_out_of_range_safe_z():
    p = config.load()
    p2 = copy.deepcopy(p)
    p2.safety["safe_z_work_mm"] = 2.0
    checks = config.validate(p2)
    assert any(c["gate"] == "SAFE-Z" and c["status"] == "FAIL" for c in checks)


def test_config_flags_out_of_range_cutting_speed():
    p = config.load()
    p2 = copy.deepcopy(p)
    p2.operations[0]["rpm"] = 5000        # Vc 超 TC11 粗加工上限
    checks = config.validate(p2)
    assert any(c["gate"] == "OP1-VC" and c["status"] == "FAIL" for c in checks)


# ---------------------------------------------------------------- 审查器（反证）
def test_lint_detects_rapid_plunge():
    nc, mach = _emitted(programs.build_op3(config.load()))
    bad = nc.replace("G01 Z-5", "G00 Z-5", 1)
    res = lint.lint(bad, "fanuc", mach, _tools(), 2, 10.0)
    assert res["verdict"] == "FAIL"
    assert "RAPID-PLUNGE" in res["failed_gates"] or "RAPID-SAFE-HEIGHT" in res["failed_gates"]


def test_lint_detects_missing_tool_length_comp():
    nc, mach = _emitted(programs.build_op1(config.load()))
    bad = nc.replace("G43 H1 Z10", "").replace("G43.4 H1", "")
    res = lint.lint(bad, "fanuc", mach, _tools(), 1, 10.0)
    assert "TOOL-LENGTH-COMP" in res["failed_gates"]


def test_lint_detects_turning_code():
    nc, mach = _emitted(programs.build_op1(config.load()))
    bad = nc.replace("S700 M03", "G96 S180 M03", 1)
    res = lint.lint(bad, "fanuc", mach, _tools(), 1, 10.0)
    assert "MILL-ONLY" in res["failed_gates"]


def test_lint_detects_tool_change_point_violation():
    nc, mach = _emitted(programs.build_op1(config.load()))
    bad = nc.replace("Z240", "Z-40", 1)
    res = lint.lint(bad, "fanuc", mach, _tools(), 1, 10.0)
    assert "TOOL-CHANGE-POINT" in res["failed_gates"]


# ---------------------------------------------------------------- 多方言一致性
@pytest.mark.parametrize("dialect", ["fanuc", "siemens", "hnc"])
def test_three_dialects_lint_pass(dialect):
    p = config.load()
    prog = programs.build_op3(p)
    nc, mach = _emitted(prog, dialect)
    res = lint.lint(nc, dialect, mach, _tools(), len(prog.operations), 10.0)
    assert res["verdict"] == "PASS", res["failed_gates"]


def test_roundtrip_detects_coordinate_drift():
    p = config.load()
    prog = programs.build_op3(p)
    nc, _ = _emitted(prog, "siemens")
    parsed = sim.parse(nc, "siemens")
    good = [(m.x, m.y, m.z) for m in parsed.moves if m.kind != "rapid"]
    assert good, "Siemens 解析应至少产生一条进给"
    bad_text = nc.replace("X=124", "X=125", 1)
    parsed_bad = sim.parse(bad_text, "siemens")
    bad = [(m.x, m.y, m.z) for m in parsed_bad.moves if m.kind != "rapid"]
    assert bad != good


# ---------------------------------------------------------------- 碰撞/过切反证
def _scene():
    return sim.load_scene(PROJ)


def _audit(nc_text):
    parsed = sim.parse(nc_text, "fanuc")
    return sim.audit(parsed, _scene(), _runtime(), _tools(), STOCK_TOP,
                     {"sample_step_mm": 2.0}, station="OP1")


def test_audit_is_clean_on_generated_op1():
    p = config.load()
    nc, _ = _emitted(programs.build_op1(p))
    res = _audit(nc)
    chk = {c["gate"]: c["status"] for c in res["checks"]}
    assert chk["FIXTURE-CLEARANCE"] == "PASS"
    assert chk["DESIGN-SURFACE"] == "PASS"
    assert chk["MACHINE-TRAVEL"] == "PASS"


def test_audit_detects_gouge_into_design():
    nc = "\n".join([
        "%", "O0001 (GOUGE PROBE)", "G21 G17 G40 G49 G80 G90", "G54",
        "T1 M06", "G00 X0 Y0 Z10", "G43 H1 Z10", "S700 M03", "M08",
        "G01 X100.0 Y0 Z-57.0 F100", "M09", "M05", "G49", "M30", "%",
    ])
    res = _audit(nc)
    chk = {c["gate"]: c["status"] for c in res["checks"]}
    assert chk["DESIGN-SURFACE"] == "FAIL"
    assert any(v["type"] == "DESIGN_GOUGE" for v in res["violations"])


def test_audit_detects_fixture_collision():
    nc = "\n".join([
        "%", "O0002 (FIXTURE PROBE)", "G21 G17 G40 G49 G80 G90", "G54",
        "T1 M06", "G00 X150 Y0 Z10", "G43 H1 Z10", "S700 M03", "M08",
        "G01 Z-75 F100", "M09", "M05", "G49", "M30", "%",
    ])
    res = _audit(nc)
    chk = {c["gate"]: c["status"] for c in res["checks"]}
    assert chk["FIXTURE-CLEARANCE"] == "FAIL"


def test_training_rig_cannot_cover_op1_travel():
    p = config.load()
    prog = programs.build_op1(p)
    m = p.machines["training_rig_nmv1500"]
    nc, _ = _emitted(prog, "fanuc", key="training_rig_nmv1500")
    parsed = sim.parse(nc, "fanuc")
    mach = {"travel_mm": m.travel_mm, "rotary_limits_deg": m.rotary_limits_deg,
            "tool_change_s": m.tool_change_s}
    res = sim.audit(parsed, {}, mach, _tools(), STOCK_TOP, {"sample_step_mm": 5.0})
    chk = {c["gate"]: c["status"] for c in res["checks"]}
    assert chk["MACHINE-TRAVEL"] == "FAIL"      # Y 行程 210 覆盖不了 Ø264 圆周三向预成形


# ---------------------------------------------------------------- SDF 标定
def test_signed_distance_convention():
    scene = _scene()
    design = scene["Design"]
    # 设计局部 z 20.85 -> 世界 95.85；r=100 在轮盘实体内部，r=0 在中心孔（void）
    pts = __import__("numpy").array([[100.0, 0.0, 95.85], [0.0, 0.0, 95.85]])
    gap = sim._sdf(design, pts)
    assert gap[0] < 0        # 实体内部 => 间隙为负
    assert gap[1] > 0        # 中心孔内 => 间隙为正


# ---------------------------------------------------------------- 保障逻辑
def test_spc_flags_bias():
    data = [0.08 + 0.001 * i for i in range(20)]
    res = assurance.spc(data, 0.05, -0.05)
    assert res["verdict"] == "WARN"
    assert res["out_of_tolerance"] > 0


def test_wear_alarm_threshold():
    w = assurance.tool_wear({"id": "T1", "taylor_c": 90.0, "taylor_n": 0.25}, 35.0, 100.0)
    assert w["level"] == "ALARM"
    assert w["parts_per_tool"] < 1.0


def test_collision_risk_levels():
    assert assurance.collision_risk(-0.1)["level"] == "CRITICAL"
    assert assurance.collision_risk(0.3)["level"] == "HIGH"
    assert assurance.collision_risk(10.0)["level"] == "LOW"


def test_opcua_selftest_real_stack():
    res = __import__("virtu_prod.opcua", fromlist=["x"]).selftest(
        "opc.tcp://127.0.0.1:4841/virtu-test/")
    if not res.get("available"):
        pytest.skip(f"asyncua 不可用: {res.get('reason')}")
    assert res["read_back_ok"], res
