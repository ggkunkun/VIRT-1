"""双重校验单元测试：正常程序全部通过 + 植入过切/撞刀/夹具碰撞/超行程/不支持指令必须判红。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cam_autogen.contracts import Move, OptimizationRequest, WorkpieceSpec
from cam_autogen.examples import EXAMPLES
from cam_autogen.machine_config import configure_machine
from cam_autogen.optimization import optimize
from cam_autogen.process_recognition import recognize
from cam_autogen.program_generation import generate
from cam_autogen.stock_positioning import compute_stock_setup
from cam_autogen.verification import verify_all
from cam_autogen.verification.api import app


def _build_bundle(key: str, dialect: str = "FANUC"):
    wp = WorkpieceSpec.model_validate(EXAMPLES[key])
    rec = recognize(wp)
    ss = compute_stock_setup(wp, rec.process_type)
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=rec.process_type))
    draft = generate(plan, ss, dialect=dialect)
    setup = configure_machine(draft, preferred_dialect=dialect)
    final = generate(plan, ss, post_profile=setup.post_profile, dialect=setup.machine.dialect)
    return wp, ss, plan, final, setup


def test_clean_programs_pass_and_write_html_reports(tmp_path):
    for key in ("shaft", "keyed_shaft", "block", "flange"):
        _, ss, plan, prog, setup = _build_bundle(key)
        rep = verify_all(prog, setup, plan=plan, stock_setup=ss, output_dir=tmp_path)
        assert rep.passed is True, f"{key} 意外校验失败: {rep.risks}"
        assert rep.html_path and Path(rep.html_path).is_file()
        html_txt = Path(rep.html_path).read_text(encoding="utf-8")
        assert "<svg" in html_txt and "PASSED" in html_txt


def test_path_falsification_rapid_plunge_gouge_and_fixture_collision(tmp_path):
    _, ss, plan, prog, setup = _build_bundle("block")

    # 1. 注入铣削快进扎刀（G00 Z-10）
    bad_ir = list(prog.ir)
    idx_cut = next(i for i, m in enumerate(bad_ir) if m.kind == "linear" and m.op_id == "OP030")
    bad_ir.insert(idx_cut, Move(kind="rapid", x=45.0, y=40.0, z=-10.0, op_id="OP030"))
    rep_plunge = verify_all(prog.model_copy(update={"ir": bad_ir}), setup, plan=plan, stock_setup=ss, output_dir=tmp_path)
    assert rep_plunge.passed is False
    assert any(r.code == "RAPID_PLUNGE" and r.level == "CRITICAL" for r in rep_plunge.risks)
    assert "<circle" in Path(rep_plunge.html_path).read_text(encoding="utf-8")

    # 2. 注入铣削型腔深度过切
    bad_gouge = list(prog.ir)
    bad_gouge.insert(idx_cut + 1, Move(kind="linear", x=45.0, y=40.0, z=-25.0, f=500.0, op_id="OP030"))
    rep_gouge = verify_all(prog.model_copy(update={"ir": bad_gouge}), setup, plan=plan, stock_setup=ss)
    assert rep_gouge.passed is False
    assert any(r.code == "GOUGE" and r.level == "CRITICAL" for r in rep_gouge.risks)

    # 3. 注入撞虎钳钳口
    bad_fix = list(prog.ir)
    bad_fix.insert(idx_cut + 1, Move(kind="linear", x=45.0, y=-15.0, z=-35.0, f=500.0, op_id="OP010"))
    rep_fix = verify_all(prog.model_copy(update={"ir": bad_fix}), setup, plan=plan, stock_setup=ss)
    assert rep_fix.passed is False
    assert any(r.code == "FIXTURE_COLLISION" and r.level == "CRITICAL" for r in rep_fix.risks)

    # 4. 注入车削外圆过切 & 撞卡盘
    _, ss_t, plan_t, prog_t, setup_t = _build_bundle("shaft")
    idx_t = next(i for i, m in enumerate(prog_t.ir) if m.kind == "linear" and m.op_id == "OP030")
    ir_tg = list(prog_t.ir)
    ir_tg.insert(idx_t, Move(kind="linear", x=20.0, z=-15.0, f=0.15, op_id="OP030"))  # 成品为 Ø30
    rep_tg = verify_all(prog_t.model_copy(update={"ir": ir_tg}), setup_t, plan=plan_t, stock_setup=ss_t)
    assert rep_tg.passed is False and any(r.code == "GOUGE" for r in rep_tg.risks)

    ir_tc = list(prog_t.ir)
    ir_tc.insert(idx_t, Move(kind="linear", x=40.0, z=-120.0, f=0.15, op_id="OP030"))  # 撞三爪卡盘
    rep_tc = verify_all(prog_t.model_copy(update={"ir": ir_tc}), setup_t, plan=plan_t, stock_setup=ss_t)
    assert rep_tc.passed is False and any(r.code == "FIXTURE_COLLISION" for r in rep_tc.risks)


def test_compat_falsification_overtravel_rpm_and_unsupported_code():
    _, ss, plan, prog, setup = _build_bundle("shaft")

    # 1. 超行程
    bad_ot = list(prog.ir)
    bad_ot.insert(10, Move(kind="linear", x=9999.0, z=-10.0, f=0.2, op_id="OP020"))
    rep_ot = verify_all(prog.model_copy(update={"ir": bad_ot}), setup, plan=plan, stock_setup=ss)
    assert rep_ot.passed is False and any(r.code == "OVER_TRAVEL" for r in rep_ot.risks)

    # 2. 超转速
    bad_rpm = list(prog.ir)
    bad_rpm.insert(5, Move(kind="spindle", s=99999.0))
    rep_rpm = verify_all(prog.model_copy(update={"ir": bad_rpm}), setup, plan=plan, stock_setup=ss)
    assert rep_rpm.passed is False and any(r.code == "RPM_EXCEEDED" for r in rep_rpm.risks)

    # 3. 注入不支持 G 代码与 M 代码
    bad_txt = prog.program_text + "\nN9999 G999 M99 X10.\n"
    rep_gc = verify_all(prog.model_copy(update={"program_text": bad_txt}), setup, plan=plan, stock_setup=ss)
    assert rep_gc.passed is False
    assert any(r.code == "UNSUPPORTED_GCODE" for r in rep_gc.risks)
    assert any(r.code == "UNSUPPORTED_MCODE" for r in rep_gc.risks)

    # 4. 进给超限 / 功率超限 / 刀库容量超限 / 缺动力刀与C轴 / 方言语法错误
    bad_feed_ir = list(prog.ir)
    bad_feed_ir.insert(12, Move(kind="linear", x=30.0, z=-5.0, f=50.0, op_id="OP020"))  # mm/rev*rpm >> max_feed
    rep_feed = verify_all(prog.model_copy(update={"ir": bad_feed_ir}), setup, plan=plan, stock_setup=ss)
    assert rep_feed.passed is False and any(r.code == "FEED_EXCEEDED" for r in rep_feed.risks)

    weak_machine = setup.machine.model_copy(update={
        "spindle_power_kw": 0.5, "tool_capacity": 1, "max_tool_diameter": 5.0, "max_tool_length": 10.0,
    })
    rep_cap = verify_all(prog, setup.model_copy(update={"machine": weak_machine}), plan=plan, stock_setup=ss)
    codes = {r.code for r in rep_cap.risks}
    assert {"POWER_EXCEEDED", "TOOL_CAPACITY_EXCEEDED", "TOOL_DIAMETER_EXCEEDED", "TOOL_LENGTH_EXCEEDED"}.issubset(codes)

    rep_syn = verify_all(prog.model_copy(update={"program_text": prog.program_text + "\n; illegal siemens comment\n"}),
                         setup, plan=plan, stock_setup=ss)
    assert any(r.code == "DIALECT_SYNTAX_ERROR" for r in rep_syn.risks)

    _, ss_km, plan_km, prog_km, setup_km = _build_bundle("keyed_shaft")
    stripped_m = setup_km.machine.model_copy(update={"has_c_axis": False, "live_tooling": False})
    rep_ax = verify_all(prog_km, setup_km.model_copy(update={"machine": stripped_m}), plan=plan_km, stock_setup=ss_km)
    ax_codes = {r.code for r in rep_ax.risks}
    assert {"AXIS_CAPABILITY_MISSING", "LIVE_TOOL_MISSING"}.issubset(ax_codes)

    # 5. 覆盖铣削多维度过切 / 换刀安全 / 空IR / 缺失M30 / 西门子与华中语法校验 / 铣削超行程
    _, ss_b, plan_b, prog_b, setup_b = _build_bundle("block")
    # 铣削 XYZ 超行程
    bad_mill_ot = list(prog_b.ir)
    idx_b = next(i for i, m in enumerate(bad_mill_ot) if m.kind == "linear" and m.op_id == "OP030")
    bad_mill_ot.insert(idx_b, Move(kind="linear", x=5000.0, y=5000.0, z=-5000.0, f=500.0, op_id="OP030"))
    rep_mot = verify_all(prog_b.model_copy(update={"ir": bad_mill_ot}), setup_b, plan=plan_b, stock_setup=ss_b)
    assert any(r.code == "OVER_TRAVEL" for r in rep_mot.risks)

    # 面铣/槽/钻孔过切 + 换刀时主轴未停 + 缺少 M30
    idx_face = next(i for i, m in enumerate(prog_b.ir) if m.kind == "linear" and m.op_id == "OP010")
    bad_g = list(prog_b.ir)
    bad_g.insert(idx_face + 1, Move(kind="linear", x=20.0, y=20.0, z=-5.0, f=500.0, op_id="OP010"))  # 面铣过深
    idx_slot = next(i for i, m in enumerate(bad_g) if m.kind == "linear" and m.op_id == "OP050")
    bad_g.insert(idx_slot + 1, Move(kind="linear", x=85.0, y=40.0, z=-30.0, f=500.0, op_id="OP050"))  # 槽过深
    idx_drill = next(i for i, m in enumerate(bad_g) if m.kind == "linear" and m.op_id == "OP080")
    bad_g.insert(idx_drill + 1, Move(kind="linear", x=99.0, y=99.0, z=-50.0, f=500.0, op_id="OP080"))  # 错孔位+过深
    bad_g.insert(idx_face + 2, Move(kind="tool_change", tool=2))  # 主轴未停即换刀
    bad_g = [m for m in bad_g if m.kind != "program_end"]
    rep_multi = verify_all(prog_b.model_copy(update={"ir": bad_g}), setup_b, plan=plan_b, stock_setup=ss_b)
    mcodes = {r.code for r in rep_multi.risks}
    assert {"GOUGE", "UNSAFE_TOOL_CHANGE", "MISSING_PROGRAM_END"}.issubset(mcodes)

    # 空 IR 校验
    rep_empty = verify_all(prog_b.model_copy(update={"ir": []}), setup_b)
    assert rep_empty.passed is False and any(r.code == "EMPTY_IR" for r in rep_empty.risks)

    # 方言冲突与机种冲突 + 动力刀超转速
    bad_live = list(prog_km.ir)
    idx_live = next(i for i, m in enumerate(bad_live) if m.kind == "live_spindle")
    bad_live.insert(idx_live + 1, Move(kind="live_spindle", s=99999.0))
    rep_live = verify_all(prog_km.model_copy(update={"ir": bad_live, "dialect": "SIEMENS"}), setup_km, plan=plan_km, stock_setup=ss_km)
    assert any(r.code == "DIALECT_MISMATCH" for r in rep_live.risks)
    assert any(r.code == "RPM_EXCEEDED" for r in rep_live.risks)

    _, ss_bs, plan_bs, prog_bs, setup_bs = _build_bundle("block", dialect="SIEMENS")
    rep_siem = verify_all(prog_bs.model_copy(update={"program_text": prog_bs.program_text + "\n(bad paren comment)\n"}),
                          setup_bs, plan=plan_bs, stock_setup=ss_bs)
    assert any(r.code == "DIALECT_SYNTAX_ERROR" for r in rep_siem.risks)


def test_verification_rest_api(tmp_path):
    _, ss, plan, prog, setup = _build_bundle("shaft")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    r = client.post("/v1/verify", json={
        "program": prog.model_dump(mode="json"),
        "machine_setup": setup.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "stock_setup": ss.model_dump(mode="json"),
        "output_dir": str(tmp_path),
    })
    assert r.status_code == 200 and r.json()["passed"] is True
