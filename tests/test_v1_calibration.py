# -*- coding: utf-8 -*-
"""V1 五轴标定契约测试（程序可审查、矢量一致、反算可复现、坏样本必红）。"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_prod import calibration as cal, config, lint, post  # noqa: E402


def _load_v1_script():
    spec = importlib.util.spec_from_file_location(
        "run_v1", ROOT / "scripts" / "run_v1_calibration.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _runtime():
    p = config.load()
    m = p.machines["prod_5ax_fanuc_0imf"]
    return {"label": m.label, "controller": m.controller, "dialect": m.dialect,
            "safe_z": 10.0, "tc_z": m.tool_change_point["z"], "tc_x": 0.0, "tc_y": 0.0,
            "travel_mm": m.travel_mm, "rotary_limits_deg": m.rotary_limits_deg,
            "rotary": m.rotary_limits_deg, "tool_change_s": m.tool_change_s}


def _tools():
    p = config.load()
    return {tid: {"id": tid, "diameter": t.diameter_mm, "gauge_length": t.gauge_length_mm,
                  "holder_length": t.holder_length_mm,
                  "holder_radius": t.holder_diameter_mm / 2.0}
            for tid, t in p.tools.items()}


# ---------------------------------------------------------------- 程序与行程
def test_rtcp_programs_lint_pass():
    v1 = _load_v1_script()
    prog = {"fanuc": v1.gen_fanuc(9101, "FANUC 0i-MF"),
            "hnc": v1.gen_fanuc(9102, "HNC-8"),
            "siemens": v1.gen_siemens()}
    for dialect, text in prog.items():
        res = lint.lint(text, dialect, _runtime(), _tools(), 1, 10.0,
                        require_spindle=False)
        assert res["verdict"] == "PASS", (dialect, res["failed_gates"])
    assert "G43.4" in prog["fanuc"] and "G43.4" in prog["hnc"]
    assert "TRAORI" in prog["siemens"] and "TRAFOOF" in prog["siemens"]


def test_sphere_positions_within_machine_travel():
    p = config.load()
    m = p.machines["prod_5ax_fanuc_0imf"]
    for q in cal.sphere_positions():
        x, y, z = q["machine"]
        assert m.travel_mm["x"][0] <= x <= m.travel_mm["x"][1]
        assert m.travel_mm["y"][0] <= y <= m.travel_mm["y"][1]
        assert m.travel_mm["z"][0] <= z <= m.travel_mm["z"][1]


def test_siemens_orientation_matches_tool_axis():
    v1 = _load_v1_script()
    text = v1.gen_siemens()
    import re
    for i, (b, c) in enumerate(cal.orientations(), 1):
        m = re.search(rf"N{100 + i * 10} G1 A3=([-\d.]+) B3=([-\d.]+) C3=([-\d.]+)", text)
        assert m, f"orientation line {i} missing"
        got = [float(m.group(k)) for k in (1, 2, 3)]
        exp = post.tool_axis(b, c)
        assert max(abs(g - e) for g, e in zip(got, exp)) < 2e-6
        assert abs(math.sqrt(sum(v * v for v in got)) - 1.0) < 1e-5


# ---------------------------------------------------------------- 反算与判据
def _samples(offset, noise=0.0, extra=None, seed=20261118):
    rng = np.random.default_rng(seed)
    out = []
    e = np.asarray(offset, dtype=float)
    for b, c in cal.orientations():
        m = cal.rot_b(b) @ cal.rot_c(c) - np.eye(3)
        d = m @ e + rng.normal(0.0, noise, 3)
        if extra is not None:
            d = d + np.asarray(extra(b, c))
        out.append({"b": b, "c": c, "dx": float(d[0]), "dy": float(d[1]),
                    "dz": float(d[2])})
    return out


def test_estimate_pivot_recovers_known_offset():
    e_true = (0.03, 0.01, -0.02)
    est = cal.estimate_pivot(_samples(e_true, noise=0.0015))
    assert max(abs(a - b) for a, b in zip(est["offset_mm"], e_true)) < 0.003
    assert est["max_residual_mm"] < 0.01


def test_rtcp_pass_on_correctable_offset():
    res = cal.evaluate_rtcp(_samples((0.12, 0.05, -0.08), noise=0.002))
    assert res["status"] == "PASS"          # 纯枢轴偏置可补偿，残差才是 RTCP 误差
    assert res["max_residual_mm"] <= 0.05


def test_rtcp_fails_on_non_rigid_error():
    def extra(b, c):
        return (0.15 * math.sin(math.radians(b)), 0.10 * math.cos(math.radians(c)),
                0.0)
    res = cal.evaluate_rtcp(_samples((0.0, 0.0, 0.0), noise=0.001, extra=extra))
    assert res["status"] == "FAIL"
    assert res["max_residual_mm"] > 0.05


def test_rtcp_pending_on_incomplete_record():
    samples = _samples((0.01, 0.0, 0.0))[:10]
    res = cal.evaluate_rtcp(samples)
    assert res["status"] == "PENDING"


def test_series_and_backlash_gates():
    assert cal.evaluate_series([10.000, 10.003, 10.001, 10.002, 10.001],
                               0.005, "repeat")["status"] == "PASS"
    assert cal.evaluate_series([10.000, 10.020], 0.005, "repeat")["status"] == "FAIL"
    assert cal.evaluate_series([0.0, 0.01, 0.03], 0.020, "thermal")["status"] == "FAIL"
    pairs = [(0.0, 0.004)] * 10
    assert cal.evaluate_backlash(pairs)["status"] == "PASS"
    assert cal.evaluate_backlash([(0.0, 0.03)] * 10)["status"] == "FAIL"


def test_orientation_angle_gate():
    ok = cal.evaluate_orientation([0.030] * 20)      # atan(0.03/50)=0.0344°
    assert ok["status"] == "PASS"
    bad = cal.evaluate_orientation([0.080] * 20)     # 0.0917°
    assert bad["status"] == "FAIL"
    assert cal.evaluate_orientation([0.030] * 10)["status"] == "PENDING"


def test_record_templates_generated_and_pending(tmp_path):
    v1 = _load_v1_script()
    paths = v1.write_evidence_templates(tmp_path)
    names = {p.name for p in paths}
    assert {"U-06_rtcp_record.csv", "U-07_siemens_orientation.csv",
            "U-08_repeatability.csv", "U-08_thermal.csv", "U-08_backlash.csv",
            "SESSION_META.csv", "U-06_U-08_RECORD_GUIDE.md"} <= names
    res = cal.evaluate_evidence(tmp_path)
    assert res["gate"] == "PENDING"
    assert all(v["status"] == "PENDING" for v in res["items"].values())
    import csv
    with (tmp_path / "U-07_siemens_orientation.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 20
    for r in rows[:6]:
        b, c = float(r["B(deg)"]), float(r["C(deg)"])
        exp = post.tool_axis(b, c)
        got = [float(r["A3(期望)"]), float(r["B3(期望)"]), float(r["C3(期望)"])]
        assert max(abs(g - e) for g, e in zip(got, exp)) < 1e-6


def test_filled_evidence_not_overwritten(tmp_path):
    v1 = _load_v1_script()
    v1.write_evidence_templates(tmp_path)
    p = tmp_path / "U-08_repeatability.csv"
    text = p.read_text(encoding="utf-8-sig").replace("1,T1,,", "1,T1,75.001,")
    p.write_text(text, encoding="utf-8-sig")
    assert v1._has_data(p) is True
    assert v1._has_data(tmp_path / "U-08_thermal.csv") is False
    assert v1._has_data(tmp_path / "SESSION_META.csv") is False


def test_evidence_parser_and_gate(tmp_path):
    import csv
    # 完整且合格
    with (tmp_path / "U-06_rtcp_record.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["序号", "B(deg)", "C(deg)", "ΔX(mm)", "ΔY(mm)", "ΔZ(mm)",
                    "球心偏差(mm)", "结论(PASS/FAIL)"])
        for i, s in enumerate(_samples((0.02, 0.0, -0.01), noise=0.001), 1):
            w.writerow([i, s["b"], s["c"], s["dx"], s["dy"], s["dz"], "", ""])
    res = cal.evaluate_evidence(tmp_path)
    assert res["items"]["U-06"]["status"] == "PASS"
    assert res["gate"] in ("PASS", "PENDING")

    # 空模板 => PENDING
    empty = tmp_path / "empty"
    empty.mkdir()
    res2 = cal.evaluate_evidence(empty)
    assert res2["gate"] == "PENDING"
    assert all(v["status"] == "PENDING" for v in res2["items"].values())
