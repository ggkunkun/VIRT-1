# -*- coding: utf-8 -*-
"""tests/test_cnc_post_processor.py — 真实多控制器后处理器（CL->方言）可证伪门。

覆盖：
  A. 三种方言（FANUC / Siemens 840D / Heidenhain TNC）对同一 CL 发射结构合法 NC。
  B. 坐标一致性 oracle：同一 CL 三方言语义回读逐点一致（±1e-3mm）。
  C. CL 安全门可证伪：空程序 / 无主轴切削 / 快速扎刀 必须判红。
  D. 方言结构门可证伪：缺 M30 / 缺主轴 / 缺循环 / 五轴误用 TRAORI 必须判红。
  E. 诚实边界：TRAORI 仅五轴；Heidenhain CYCL DEF 200/203/207；FANUC G81/G83/G84。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from virtu_omni.engine.cnc_post_processor import (
    CLProgram, CLMove, CLToolChange, CLSpindle, CLCoolant, CLCycle,
    SUPPORTED_DIALECTS, emit_fanuc, emit_siemens, emit_heidenhain,
    validate_program, validate_dialect, round_trip_coords,
    verify_coordinate_consistency, post_process,
)


def _sample_program(five_axis: bool = False) -> CLProgram:
    return CLProgram(
        name="VIRTU_DEMO", units="mm", five_axis=five_axis, wcs="G54",
        ops=[
            CLToolChange(tool_id=1, diameter_mm=10.0, length_mm=50.0),
            CLSpindle(rpm=1200, direction="cw"),
            CLCoolant(on=True),
            CLMove(mode="rapid", x=0.0, y=0.0, z=5.0),
            CLMove(mode="feed", x=10.0, y=0.0, z=-2.0, f=100.0),
            CLMove(mode="feed", x=10.0, y=10.0, z=-2.0, f=100.0),
            CLMove(mode="arc_cw", x=20.0, y=10.0, z=-2.0, i=5.0, j=0.0, f=80.0),
            CLMove(mode="rapid", z=5.0),
            CLCycle(kind="drill", x=30.0, y=30.0, z_depth=-10.0, r_plane=2.0, feed=100.0),
            CLCycle(kind="peck", x=40.0, y=30.0, z_depth=-15.0, r_plane=2.0, peck_q=3.0, feed=80.0),
            CLCycle(kind="tap", x=50.0, y=30.0, z_depth=-8.0, r_plane=2.0, feed=60.0),
            CLSpindle(rpm=0, direction="stop"),
            CLCoolant(on=False),
        ],
    )


# ---------------------------------------------------------------------------
# A. 三种方言发射结构合法 NC
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
def test_emit_each_dialect_passes_structural_gate(dialect):
    prog = _sample_program()
    nc = {"fanuc": emit_fanuc, "siemens": emit_siemens, "heidenhain": emit_heidenhain}[dialect](prog)
    gate = validate_dialect(dialect, nc, prog)
    assert gate["passed"] is True, gate["violations"]
    assert gate["basis"] == "measured"


@pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
def test_post_process_full_pipeline_passed(dialect):
    res = post_process(_sample_program(), dialect=dialect)
    assert res["status"] == "passed", res
    assert res["cl_gate"]["passed"] is True
    assert res["dialect_gate"]["passed"] is True
    assert res["coord_gate"]["passed"] is True
    assert res["nc"] and res["basis"] == "measured"


# ---------------------------------------------------------------------------
# B. 坐标一致性 oracle（同一 CL 三方言逐点一致）
# ---------------------------------------------------------------------------
def test_coordinate_consistency_across_dialects():
    prog = _sample_program()
    gate = verify_coordinate_consistency(prog)
    assert gate["passed"] is True, gate["violations"]
    for dialect in SUPPORTED_DIALECTS:
        per = gate["per_dialect"][dialect]
        assert per["matched"] is True, (dialect, per)
        assert per["points"] == 5, (dialect, per)  # 5 个 CLMove
        assert per["max_err_mm"] <= 1e-3


def test_round_trip_point_count_matches_cl():
    prog = _sample_program()
    for dialect, emitter in (("fanuc", emit_fanuc), ("siemens", emit_siemens),
                             ("heidenhain", emit_heidenhain)):
        coords = round_trip_coords(dialect, emitter(prog))
        assert len(coords) == 5, (dialect, coords)
    # 首点 rapid 到 (0,0,5)，末点 rapid 回 (20,10,5)
    fanuc_pts = round_trip_coords("fanuc", emit_fanuc(prog))
    assert fanuc_pts[0] == pytest.approx((0.0, 0.0, 5.0), abs=1e-3)
    assert fanuc_pts[-1] == pytest.approx((20.0, 10.0, 5.0), abs=1e-3)


def test_coordinate_gate_empty_motion_is_red():
    prog = CLProgram(ops=[CLSpindle(rpm=1000), CLToolChange(1)])
    gate = verify_coordinate_consistency(prog)
    assert gate["passed"] is False
    assert any("NO_MOTION" in v for v in gate["violations"])


# ---------------------------------------------------------------------------
# C. CL 安全门可证伪
# ---------------------------------------------------------------------------
def test_cl_gate_empty_program_red():
    gate = validate_program(CLProgram(ops=[]))
    assert gate["passed"] is False
    assert any("EMPTY_PROGRAM" in v for v in gate["violations"])


def test_cl_gate_no_spindle_red():
    prog = CLProgram(ops=[CLMove(mode="feed", x=1.0, y=1.0, z=-1.0, f=100.0)])
    gate = validate_program(prog)
    assert gate["passed"] is False
    assert any("NO_SPINDLE" in v for v in gate["violations"])


def test_cl_gate_rapid_plunge_red():
    prog = CLProgram(ops=[
        CLSpindle(rpm=1000),
        CLCycle(kind="drill", x=0, y=0, z_depth=-10, r_plane=2.0),
        CLMove(mode="rapid", z=-5.0),  # 快速下刀低于参考平面 -> 撞刀
    ])
    gate = validate_program(prog)
    assert gate["passed"] is False
    assert any("RAPID_PLUNGE" in v for v in gate["violations"])


def test_post_process_blocked_on_bad_cl():
    res = post_process(CLProgram(ops=[]), dialect="fanuc")
    assert res["status"] == "blocked"
    assert res["nc"] is None


def test_post_process_unknown_dialect_blocked():
    res = post_process(_sample_program(), dialect="mazak")
    assert res["status"] == "blocked"
    assert "UNKNOWN_DIALECT" in res["error"]


# ---------------------------------------------------------------------------
# D. 方言结构门可证伪（植入坏样本必须判红）
# ---------------------------------------------------------------------------
def test_fanuc_missing_m30_red():
    prog = _sample_program()
    nc = emit_fanuc(prog).replace("M30", "")
    gate = validate_dialect("fanuc", nc, prog)
    assert gate["passed"] is False
    assert any("FANUC_NO_END" in v for v in gate["violations"])


def test_fanuc_missing_spindle_red():
    prog = _sample_program()
    nc = emit_fanuc(prog).replace("M03", "")
    gate = validate_dialect("fanuc", nc, prog)
    assert gate["passed"] is False
    assert any("FANUC_NO_SPINDLE" in v for v in gate["violations"])


def test_siemens_missing_cycle_red():
    prog = _sample_program()
    nc = emit_siemens(prog)
    for c in ("CYCLE81", "CYCLE83", "CYCLE84"):
        nc = nc.replace(c, "G1")
    gate = validate_dialect("siemens", nc, prog)
    assert gate["passed"] is False
    assert any("SIEMENS_NO_CYCLE" in v for v in gate["violations"])


def test_heidenhain_missing_end_pgm_red():
    prog = _sample_program()
    nc = emit_heidenhain(prog)
    nc = "\n".join(l for l in nc.splitlines() if not l.startswith("END PGM"))
    gate = validate_dialect("heidenhain", nc, prog)
    assert gate["passed"] is False
    assert any("HEID_NO_END" in v for v in gate["violations"])


def test_empty_nc_red_all_dialects():
    prog = _sample_program()
    for dialect in SUPPORTED_DIALECTS:
        gate = validate_dialect(dialect, "", prog)
        assert gate["passed"] is False
        assert any("EMPTY_NC" in v for v in gate["violations"])


# ---------------------------------------------------------------------------
# E. 诚实边界：TRAORI 仅五轴 / 循环关键字 / 方言特征
# ---------------------------------------------------------------------------
def test_siemens_traori_only_five_axis():
    three = _sample_program(five_axis=False)
    five = _sample_program(five_axis=True)
    assert "TRAORI" not in emit_siemens(three)
    assert "TRAORI" in emit_siemens(five)
    # 三轴误用 TRAORI 必须判红
    bad_nc = emit_siemens(three).replace("G71 G90", "TRAORI\nG71 G90")
    gate = validate_dialect("siemens", bad_nc, three)
    assert gate["passed"] is False
    assert any("SIEMENS_TRAORI_MISUSE" in v for v in gate["violations"])
    # 五轴缺 TRAORI 必须判红
    gate5 = validate_dialect("siemens", emit_siemens(five).replace("TRAORI", ""), five)
    assert gate5["passed"] is False
    assert any("SIEMENS_NO_TRAORI" in v for v in gate5["violations"])


def test_siemens_cycles_present():
    nc = emit_siemens(_sample_program())
    assert "CYCLE81(" in nc and "CYCLE83(" in nc and "CYCLE84(" in nc


def test_heidenhain_cycles_and_structure():
    nc = emit_heidenhain(_sample_program())
    assert "BEGIN PGM" in nc and "END PGM" in nc
    assert "CYCL DEF 200" in nc and "CYCL DEF 203" in nc and "CYCL DEF 207" in nc
    assert "TOOL CALL" in nc and "FMAX" in nc


def test_fanuc_cycles_and_macro_structure():
    nc = emit_fanuc(_sample_program())
    assert nc.startswith("%") and "M30" in nc
    assert "G81" in nc and "G83" in nc and "G84" in nc
    assert "G21 G90 G54" in nc


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))