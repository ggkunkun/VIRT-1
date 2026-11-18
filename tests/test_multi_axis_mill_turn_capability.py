# -*- coding: utf-8 -*-
"""可证伪测试：全机床多轴铣削（三轴/四轴/五轴）与复合加工中心/车铣复合 Agent 代码能力测试。

覆盖范围：
  1. 三轴铣削（FANUC / Siemens 840D / Heidenhain TNC）
  2. 四轴分度（3+1，M11/M10 锁紧）与四轴联动（A/B 轴同步插补）
  3. 五轴 3+2 倾斜工作平面（G68.2+G53.1 / CYCLE800 / PLANE SPATIAL）
  4. 五轴联动（AC/BC/AB 双旋转轴，G43.4/G49、TRAORI/TRAFOOF、FUNCTION TCPM/RESET）
  5. 车削中心（G71/G70 / CYCLE95）
  6. 车铣复合（C 轴端面极坐标 G12.1/TRANSMIT、圆柱插补 G07.1/TRACYL、Y 轴偏心铣、B 轴摆头复合）
  7. 复合加工中心副主轴同步接料与 G55 背加工（W 轴、M269/M268/M69 夹松顺序）
  8. 16 类植入坏样本必红反证 + VirtuSuperAgent 工具链闭环 + Oracle 取证。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from virtu_omni.agent.super_agent import VirtuSuperAgent
from virtu_omni.engine.cnc_post_processor import (
    CLCoolant,
    CLMove,
    CLProgram,
    CLRTCP,
    CLRotaryIndex,
    CLSpindle,
    CLWorkplaneTilt,
    SUPPORTED_DIALECTS,
    build_canonical_cl_program,
    generate_capability_nc,
    post_process,
    validate_dialect,
    validate_program,
    verify_pose_consistency,
)
from virtu_omni.eval.capability_oracles import (
    multi_axis_mill_turn_code_oracle,
    run_all_oracles,
)
from virtu_omni.manufacturing import (
    CODE_CAPABILITY_CASES,
    NEGATIVE_CODE_AND_MACHINE_GATES,
    audit_nc_capability,
    run_agent_machining_capability_eval,
    run_negative_falsification_gates,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolate_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("VIRTU_MEMORY_PATH", str(tmp_path / "test_multi_axis_mem.json"))


def _verified_machine(tmp_path: Path, machine_id: str, **overrides) -> dict:
    mdir = tmp_path / machine_id
    mdir.mkdir(parents=True, exist_ok=True)
    evidence = {}
    for role in ("machine", "control", "post", "simulation"):
        fp = mdir / f"{role}.evidence"
        fp.write_text(f"{machine_id}:{role}", encoding="utf-8")
        evidence[role] = {
            "path": str(fp),
            "sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
        }
    base = {
        "machine_id": machine_id,
        "machine_class": "milling_5axis",
        "linear_axes": ["X", "Y", "Z"],
        "rotary_axes": ["B", "C"],
        "max_simultaneous_axes": 5,
        "indexing_supported": True,
        "turning_spindle": False,
        "live_tooling": False,
        "subspindle": False,
        "travel_mm": {ax: {"min": -500, "max": 500} for ax in "XYZ"},
        "controller": "FANUC 31i-B5",
        "post_dialect": "fanuc",
        "verified_features": ["milling_5axis_simultaneous"],
        "production_evidence": {**evidence, "collision_free": True, "autodiff_passed": True},
        "setup_count": 1,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. 正向全矩阵：三轴 / 四轴 / 五轴 / 车削 / 车铣复合 / 副主轴（三方言一致）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case", CODE_CAPABILITY_CASES, ids=[c["id"] for c in CODE_CAPABILITY_CASES])
def test_all_positive_code_capability_cases_and_strict_audit(case):
    res = generate_capability_nc(
        case["capability"],
        dialect=case["dialect"],
        rotary_axes=case["rotary_axes"] or None,
        variant=case["variant"],
    )
    assert res["status"] == "passed", res
    assert res["cl_gate"]["passed"] is True
    assert res["dialect_gate"]["passed"] is True
    assert res["coord_gate"]["passed"] is True
    assert res["pose_gate"]["passed"] is True
    assert res["program_release_allowed"] is False

    nc = res["nc"]
    for tok in case["expected_tokens"]:
        assert tok in nc, f"{case['id']} missing token {tok!r} in:\n{nc}"

    aud = audit_nc_capability(nc, [case["capability"]], strict_feature_check=True)
    assert aud["passed"] is True, (case["id"], aud)
    assert aud["detected_dialect"] == case["dialect"]
    assert aud["program_release_allowed"] is False
    for cand in case["expected_candidates"]:
        assert cand in aud["feature_candidates"], (case["id"], cand, aud["feature_candidates"])


@pytest.mark.parametrize("rotary_pair", [("A", "C"), ("B", "C"), ("A", "B")])
def test_five_axis_simultaneous_and_3plus2_support_all_kinematic_pairs_across_dialects(rotary_pair):
    for cap in ("milling_5axis_3plus2", "milling_5axis_simultaneous"):
        prog = build_canonical_cl_program(cap, rotary_axes=rotary_pair)
        pose_res = verify_pose_consistency(prog, dialects=SUPPORTED_DIALECTS)
        assert pose_res["passed"] is True, (cap, rotary_pair, pose_res)
        for dialect in SUPPORTED_DIALECTS:
            res = post_process(prog, dialect=dialect)
            assert res["status"] == "passed", (cap, rotary_pair, dialect, res)
            aud = audit_nc_capability(res["nc"], [cap], strict_feature_check=True)
            assert aud["passed"] is True, (cap, rotary_pair, dialect, aud)
            if cap == "milling_5axis_simultaneous":
                assert set(rotary_pair).issubset(set(aud["feed_rotary_axes"]))
                assert aud["max_rotary_axes_in_feed_block"] >= 2


# ---------------------------------------------------------------------------
# 2. 坏样本必红反证（16 类代码与选型安全门）
# ---------------------------------------------------------------------------
def test_all_16_negative_falsification_gates_reject_planted_defects():
    rows = run_negative_falsification_gates()
    assert len(rows) == len(NEGATIVE_CODE_AND_MACHINE_GATES) == 16
    assert {r["id"] for r in rows} == set(NEGATIVE_CODE_AND_MACHINE_GATES)
    for row in rows:
        assert row["planted_defect_rejected"] is True, row


@pytest.mark.parametrize("dialect,rtcp_open,rtcp_close", [
    ("fanuc", "G43.4", "G49"),
    ("siemens", "TRAORI", "TRAFOOF"),
    ("heidenhain", "FUNCTION TCPM F TCP AXIS POS PATHCTRL AXIS", "FUNCTION RESET TCPM"),
])
def test_uncanceled_rtcp_is_rejected_across_all_dialects(dialect, rtcp_open, rtcp_close):
    prog = build_canonical_cl_program("milling_5axis_simultaneous", rotary_axes=("A", "C"))
    res = post_process(prog, dialect=dialect)
    assert res["status"] == "passed"
    broken = res["nc"].replace(rtcp_close, "")
    assert rtcp_open in broken
    d_gate = validate_dialect(dialect, broken, prog)
    a_gate = audit_nc_capability(broken, ["milling_5axis_simultaneous"], strict_feature_check=True)
    assert d_gate["passed"] is False
    assert a_gate["passed"] is False
    assert "rtcp_not_canceled" in a_gate["safety_issues"]


@pytest.mark.parametrize("dialect,tilt_close", [
    ("fanuc", "G69"),
    ("siemens", "CYCLE800()"),
    ("heidenhain", "PLANE RESET STAY"),
])
def test_uncanceled_3plus2_tilt_is_rejected_across_all_dialects(dialect, tilt_close):
    prog = build_canonical_cl_program("milling_5axis_3plus2", rotary_axes=("A", "C"))
    res = post_process(prog, dialect=dialect)
    assert res["status"] == "passed"
    broken = res["nc"].replace(tilt_close, "")
    d_gate = validate_dialect(dialect, broken, prog)
    a_gate = audit_nc_capability(broken, ["milling_5axis_3plus2"], strict_feature_check=True)
    assert d_gate["passed"] is False
    assert a_gate["passed"] is False
    assert "tilted_workplane_not_canceled" in a_gate["safety_issues"]


def test_rtcp_and_tilt_plane_nesting_conflict_is_blocked_at_cl_gate():
    bad = CLProgram(
        name="NEST_CONFLICT", five_axis=True, machine_type="milling_5axis_simultaneous",
        ops=[
            CLSpindle(3000, "cw"),
            CLWorkplaneTilt(euler_a=30.0, active=True),
            CLRTCP(active=True),
            CLMove("feed", x=10.0, y=10.0, z=-2.0, a=15.0, c=45.0, f=200.0),
            CLRTCP(active=False),
            CLWorkplaneTilt(active=False),
            CLSpindle(0, "stop"),
        ],
    )
    gate = validate_program(bad)
    assert gate["passed"] is False
    assert any("RTCP_AND_TILT_PLANE_CONFLICT" in v for v in gate["violations"])


def test_siemens_transmit_polar_does_not_falsely_claim_physical_y_axis():
    res = generate_capability_nc("mill_turn_off_axis_milling", dialect="siemens",
                                 rotary_axes=("C",), variant="polar")
    assert res["status"] == "passed"
    assert "TRANSMIT" in res["nc"]
    aud_c = audit_nc_capability(res["nc"], ["mill_turn_off_axis_milling"], strict_feature_check=True)
    assert aud_c["passed"] is True
    assert "Y" not in aud_c["observed_axes"]
    aud_y = audit_nc_capability(res["nc"], ["mill_turn_y_axis_milling"], strict_feature_check=True)
    assert aud_y["passed"] is False


# ---------------------------------------------------------------------------
# 3. VirtuSuperAgent 闭环集成测试
# ---------------------------------------------------------------------------
def test_super_agent_generates_and_audits_all_machine_classes(tmp_path):
    agent = VirtuSuperAgent()
    ev = run_agent_machining_capability_eval(agent)
    assert ev["all_passed"] is True
    assert ev["positive_passed_count"] == len(CODE_CAPABILITY_CASES)
    assert ev["negative_rejected_count"] == len(NEGATIVE_CODE_AND_MACHINE_GATES)

    # 无哈希证据的五轴请求仍被机器学习/选型门拦截，不允许生产放行
    blocked = agent.call_tool("generate_cam_toolpath", {
        "manufacturing_request": {
            "features": ["milling_5axis_simultaneous"],
            "material": "Ti-6Al-4V",
            "product_bbox_mm": {"xmin": 0, "xmax": 100, "ymin": 0, "ymax": 80, "zmin": 0, "zmax": 40},
            "stock": {"shape": "box", "allowance_mm": {"side": 2.0}},
        }
    })
    assert blocked["verdict_code"] == "MACHINE_OR_STOCK_GATE_BLOCKED"
    assert blocked["production_nc_allowed"] is False

    # 具备四件套 SHA-256 证据 + Auto-Diff 绿灯的车铣复合（含副主轴）选型通过，生成 NC 草案
    mt_machine = _verified_machine(
        tmp_path, "integrex-mt",
        machine_class="mill_turn",
        linear_axes=["X", "Y", "Z"],
        rotary_axes=["B", "C"],
        turning_spindle=True,
        live_tooling=True,
        subspindle=True,
        post_dialect="siemens",
        controller="SINUMERIK 840D sl",
        verified_features=["mill_turn_y_axis_milling", "subspindle_transfer"],
    )
    draft = agent.facet_generate_cam({
        "manufacturing_request": {
            "features": ["mill_turn_y_axis_milling", "subspindle_transfer"],
            "material": "Steel45",
            "product_bbox_mm": {"xmin": -20, "xmax": 20, "ymin": -20, "ymax": 20, "zmin": 0, "zmax": 50},
            "stock": {"shape": "cylinder", "axis": "Z", "allowance_mm": {"radial": 2.0, "end": 3.0}},
        },
        "machine_catalog": [mt_machine],
        "variant": "b_head",
    })
    assert draft["status"] == "COMPLETED"
    assert draft["dialect"] == "siemens"
    assert draft["static_gate_passed"] is True
    assert draft["machine_selection"]["controller_code_generation_allowed"] is True
    assert draft["nc_capability_audit"]["passed"] is True
    # 新生成的程序文本尚未单独跑 VERICUT 碰撞仿真，production_nc_allowed 仍保持 False
    assert draft["production_nc_allowed"] is False


# ---------------------------------------------------------------------------
# 4. 评测配置清单与 Oracle 一致性
# ---------------------------------------------------------------------------
def test_agent_capability_eval_manifest_matches_executable_suite():
    manifest = json.loads(
        (ROOT / "knowledge_base" / "machining" / "agent_capability_eval.json").read_text(encoding="utf-8")
    )
    assert manifest["evaluation_entrypoint"] == "virtu_omni.manufacturing.capability_eval.run_agent_machining_capability_eval"
    assert set(manifest["controller_dialects"]) == set(SUPPORTED_DIALECTS)
    manifest_ids = [c["id"] for c in manifest["code_capability_cases"]]
    code_ids = [c["id"] for c in CODE_CAPABILITY_CASES]
    assert manifest_ids == code_ids
    assert set(manifest["required_code_negative_gates"]).issubset(set(NEGATIVE_CODE_AND_MACHINE_GATES))


def test_capability_oracle_reports_measured_pass():
    oracle = multi_axis_mill_turn_code_oracle()
    assert oracle["passed"] is True
    assert oracle["basis"] == "measured"
    assert oracle["positive_passed"] == oracle["positive_total"] >= 20
    assert oracle["negative_rejected"] == oracle["negative_total"] == 16
    all_orc = run_all_oracles()
    assert all_orc["all_measurable_oracles_passed"] is True
    assert all_orc["oracles"]["multi_axis_mill_turn"]["passed"] is True
