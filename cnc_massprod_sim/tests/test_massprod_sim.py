# -*- coding: utf-8 -*-
"""反证测试：植入坏样本 ⇒ 门必须为红（测量宪法 §8.4）。

每个安全/质量门都配一个可证伪用例：
  * 撞机（铣刀进入虎钳钳口）
  * 钻头偏离声明孔位进入牺牲背板（豁免越界）
  * 非钻头进入牺牲背板
  * 软限位超程
  * 快移低空横向穿越
  * 主轴停转切削
  * 配置越界（安全高度 / 余量分层）
  * 断点重启失败
  * 正常程序必须 PASS（防止全红假门）
"""
from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

import pytest

SIM_ROOT = Path(__file__).resolve().parents[1]
ROOT = SIM_ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SIM_ROOT / "src"))

from cnc_massprod_sim import geometry  # noqa: E402
from cnc_massprod_sim.agent import MassProductionCNCSimAgent  # noqa: E402


def _ko(name, xmin, xmax, ymin, ymax, zmin, zmax, kind="fixture_clamp"):
    return geometry.KeepOut(name, (xmin, ymin, zmin), (xmax, ymax, zmax), kind)


def _frame(x, y, z, *, rapid=False, tool=1, rpm=1000, direction="M03", feed=100):
    return geometry.Frame(idx=0, line=1, op=10, x=x, y=y, z=z, b=0.0, c=0.0,
                          is_rapid=rapid, feed=feed, spindle_rpm=rpm,
                          spindle_dir=direction, comp_length="G43",
                          comp_radius="G40", tool_id=tool, tool_category="",
                          machine_xyz=(x, y, z - 250.0))


def _scan(frames, keepouts, *, family="milling", safe_z=60.0, r_plane=3.0,
          decel=5.0, sacrificial=None, tools=None, soft=None):
    soft = soft or {"X": (-500, 500), "Y": (-500, 500), "Z": (-600, 0)}
    tools = tools or {"T1": {"diameter": 10.0, "gauge_length": 40.0,
                             "holder_radius": 15.0, "holder_length": 40.0}}
    for f in frames:
        t = tools.get(f"T{f.tool_id}", next(iter(tools.values())))
        f.tool_category = t.get("category", "end_mill")
    return geometry.scan("TEST", "FANUC", tools, keepouts, frames,
                         process_family=family, soft_limits=soft,
                         safe_z=safe_z, r_plane_mm=r_plane,
                         rapid_decel_zone_mm=decel,
                         sacrificial_backings=sacrificial)


def _gate(res, name):
    return next((c for c in res.checks if c["gate"] == name), None)


# ---------------------------------------------------------------- 正例
def test_clean_program_passes_all_gates():
    ko = [_ko("jaw", -75, 75, 48, 85, -45, -14)]
    frames = [_frame(0, 0, 60), _frame(0, 0, 8, rapid=True),
              _frame(0, 0, -5), _frame(0, 0, 60)]
    res = _scan(frames, ko, safe_z=60.0)
    assert res.summary()["verdict"] == "PASS", res.checks


# ---------------------------------------------------------------- 反例
def test_fixture_collision_detected():
    """刀具进入虎钳钳口 ⇒ FIXTURE-COLLISION 必红。"""
    ko = [_ko("jaw", -75, 75, 48, 85, -45, -14)]
    frames = [_frame(0, 60, 60), _frame(0, 60, -20)]   # Y=60 落在钳口内
    res = _scan(frames, ko)
    g = _gate(res, "FIXTURE-COLLISION")
    assert g and g["status"] == "FAIL"
    assert any(v["type"] == "FIXTURE_COLLISION" for v in res.violations)


def test_sacrificial_exemption_is_bounded_wrong_tool_still_red():
    """同一穿透点换成铣刀 ⇒ 豁免不适用，必须判红（豁免可证伪）。"""
    backing = [_ko("subplate", -95, 95, -75, 75, -75, -45, "fixture_pin")]
    sac = [{"keepout": "subplate", "tool_ids": ["T2"],
            "through_holes": [{"x": -45, "y": -38, "radius_mm": 6.0}],
            "max_penetration_mm": 5.0, "approach_band_mm": 10.0}]
    tools = {"T1": {"diameter": 10.0, "gauge_length": 40.0, "holder_radius": 15.0,
                    "holder_length": 40.0, "category": "end_mill"},
             "T2": {"diameter": 11.0, "gauge_length": 60.0, "holder_radius": 16.0,
                    "holder_length": 40.0, "category": "drill"}}
    # 用 T1 铣刀在孔位穿透
    frames = [_frame(-45, -38, -48, tool=1)]
    res = _scan(frames, backing, sacrificial=sac, tools=tools)
    assert _gate(res, "FIXTURE-COLLISION")["status"] == "FAIL"


def test_sacrificial_exemption_off_center_still_red():
    """钻头偏离声明孔位进入背板 ⇒ 必红。"""
    backing = [_ko("subplate", -95, 95, -75, 75, -75, -45, "fixture_pin")]
    sac = [{"keepout": "subplate", "tool_ids": ["T2"],
            "through_holes": [{"x": -45, "y": -38, "radius_mm": 6.0}],
            "max_penetration_mm": 5.0, "approach_band_mm": 10.0}]
    tools = {"T2": {"diameter": 11.0, "gauge_length": 60.0, "holder_radius": 16.0,
                    "holder_length": 40.0, "category": "drill"}}
    frames = [_frame(0, 0, -48, tool=2)]   # 远离声明孔位
    res = _scan(frames, backing, sacrificial=sac, tools=tools)
    assert _gate(res, "FIXTURE-COLLISION")["status"] == "FAIL"


def test_sacrificial_exemption_too_deep_still_red():
    """钻头穿透超过深度上限 ⇒ 必红。"""
    backing = [_ko("subplate", -95, 95, -75, 75, -75, -45, "fixture_pin")]
    sac = [{"keepout": "subplate", "tool_ids": ["T2"],
            "through_holes": [{"x": -45, "y": -38, "radius_mm": 6.0}],
            "max_penetration_mm": 5.0, "approach_band_mm": 10.0}]
    tools = {"T2": {"diameter": 11.0, "gauge_length": 60.0, "holder_radius": 16.0,
                    "holder_length": 40.0, "category": "drill"}}
    frames = [_frame(-45, -38, -70, tool=2)]   # 穿透 25mm，远超 5mm
    res = _scan(frames, backing, sacrificial=sac, tools=tools)
    assert _gate(res, "FIXTURE-COLLISION")["status"] == "FAIL"


def test_overtravel_detected():
    soft = {"X": (-50, 50), "Y": (-50, 50), "Z": (-100, 0)}
    frames = [_frame(0, 0, 60), _frame(0, 0, 10), _frame(999, 0, -5)]
    res = _scan(frames, [], soft=soft)
    assert _gate(res, "MACHINE-OVERTRAVEL")["status"] == "FAIL"


def test_rapid_low_lateral_detected():
    """G00 在快移减速区间以下横向移动 ⇒ 必红。"""
    frames = [_frame(0, 0, 2.0, rapid=True), _frame(50, 0, 2.0, rapid=True)]
    res = _scan(frames, [])
    assert _gate(res, "RAPID-SAFE-HEIGHT")["status"] == "FAIL"


def test_spindle_off_in_cut_detected():
    frames = [_frame(0, 0, -5, direction="M05", feed=200)]
    res = _scan(frames, [])
    assert _gate(res, "SPINDLE-ON-IN-CUT")["status"] == "FAIL"


def test_empty_frames_red():
    res = _scan([], [])
    assert res.summary()["verdict"] == "FAIL"


# ---------------------------------------------------------------- 配置门反证
def test_config_gate_flags_unsafe_safe_z():
    a = MassProductionCNCSimAgent()
    cfg = a.build_process_config("WP-SHAFT-3JAW")
    bad = copy.deepcopy(cfg)
    bad["motion_safety"]["z_safe_global_mm"] = 10.0
    g = a.ps.validate_process_plan(bad)
    assert not g["passed"]
    assert any("UNSAFE_Z_HEIGHT" in v for v in g["violations"])


def test_config_gate_flags_allowance_stratification():
    from virtu_omni.manufacturing import process_standards as ps
    plan = ps.compute_allowance_plan("40Cr", "turning", "three_jaw_chuck",
                                     rough_mm=0.1, semi_finish_mm=0.2,
                                     finish_mm=0.3, corner_mm=0.4, end_face_mm=2.0)
    assert not plan.within_handbook_bounds


# ---------------------------------------------------------------- 运行时反证
def test_audit_detects_turning_code_corruption():
    a = MassProductionCNCSimAgent()
    nc = a.generate_nc("WP-SHAFT-3JAW", "fanuc")["code"]
    bad = nc.replace("G96 S135 M03", "G96 S0 M03", 1)
    res = a.audit_nc("WP-SHAFT-3JAW", "fanuc", bad)
    assert not res["passed"]
    assert any(i["code"] == "ZERO_SPINDLE_SPEED" for i in res["issues"])


def test_instruction_set_all_nine_match():
    """正例：9 套程序使用的 G/M 全部落在对应控制器支持清单内。"""
    a = MassProductionCNCSimAgent()
    for wid in ["WP-SHAFT-3JAW", "WP-MANIFOLD-VISE", "WP-HOUSING-FIXTURE"]:
        for dia in ["fanuc", "siemens", "hnc"]:
            nc = a.generate_nc(wid, dia)
            res = a.check_instruction_set(nc["controller_id"], nc["code"])
            assert res["passed"], (wid, dia, res["issues"])


def test_instruction_set_detects_unsupported_code():
    """反例：植入控制器不支持的 G/M ⇒ 必红（规范化后仍识别）。"""
    a = MassProductionCNCSimAgent()
    nc = a.generate_nc("WP-SHAFT-3JAW", "fanuc")["code"]
    # G83 钻孔循环不在 fanuc_0i_tf 车削 profile 的支持清单内
    bad = nc.replace("G28 U0. W0.", "G83 U0. W0.", 1)
    res = a.check_instruction_set("fanuc_0i_tf", bad)
    assert not res["passed"]
    assert "G83" in res["unsupported_g"]

    # M06 自动换刀不在 fanuc_0i_tf 支持清单（车床无刀库 ATC）
    bad2 = nc.replace("M05", "M06", 1)
    res2 = a.check_instruction_set("fanuc_0i_tf", bad2)
    assert not res2["passed"]
    assert "M06" in res2["unsupported_m"]


def test_full_pipeline_clean_nine_combinations():
    """正例：9 组合全绿，防止‘全红假门’蒙混。"""
    a = MassProductionCNCSimAgent()
    for wid in ["WP-SHAFT-3JAW", "WP-MANIFOLD-VISE", "WP-HOUSING-FIXTURE"]:
        for dia in ["fanuc", "siemens", "hnc"]:
            r = a.run_one(wid, dia, step_mm=3.0)
            assert r["status"] == "PASS", (wid, dia, r["gates"])
