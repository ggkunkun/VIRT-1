# -*- coding: utf-8 -*-
"""tests/test_pynite_fea.py — PyNite 真实梁单元 FEA + 解析交叉核验（可证伪）。

覆盖：
  A. 悬臂梁 FEA 挠度/弯矩与解析解 PL^3/3EI、P*L 交叉核验通过（实测）。
  B. solver 路由：pynite 走 FEA，analytic 保持原契约，未知 solver 拒绝。
  C. 诚实边界：非梁族拒绝、PyNite 不可用返回 unmeasured（不静默回退）。
  D. 可证伪：植入坏 FEA（挠度放大 10 倍）交叉核验必须判红。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from virtu_omni.engine.universal_cae_engine import UniversalCAEEngine
from virtu_omni.engine.universal_geometry_engine import PartFamily


def _shaft_intent(material="Steel45", d_outer=53.0, d_inner=14.0, overall_len=1000.0):
    return {"family": PartFamily.ROTATIONAL_SHAFT.value,
            "spec": {"material": material, "d_outer": d_outer,
                     "d_inner": d_inner, "overall_len": overall_len}}


def test_fem_cantilever_matches_analytic():
    eng = UniversalCAEEngine()
    res = eng.analyze_beam_fem(_shaft_intent(), {"radial_load_n": 12000.0})
    assert res["status"] in ("passed", "not_healed"), res
    assert res["solver"] == "pynite"
    assert res["basis"] == "measured"
    assert res["cross_check_passed"] is True, res
    assert res["deflection_error_pct"] <= 2.0
    assert res["moment_error_pct"] <= 2.0
    assert res["deflection_fem_mm"] > 0
    # 弯矩 FEA == P*L（悬臂根部）
    assert res["max_moment_fem_nmm"] == pytest.approx(12000.0 * 1000.0, rel=1e-3)


def test_fem_high_load_not_healed():
    eng = UniversalCAEEngine()
    # 大载荷细长梁 -> 弯曲应力超屈服 -> FOS < 1.5
    res = eng.analyze_beam_fem(_shaft_intent(overall_len=2000.0), {"radial_load_n": 50000.0})
    assert res["cross_check_passed"] is True
    assert res["factor_of_safety"] < 1.5
    assert res["needs_reinforcement"] is True


def test_solver_route_pynite_vs_analytic():
    eng = UniversalCAEEngine()
    intent = _shaft_intent()
    fem = eng.analyze_and_optimize(intent, {"radial_load_n": 1000.0}, solver="pynite")
    assert fem["solver"] == "pynite"
    ana = eng.analyze_and_optimize(intent, {"internal_pressure_mpa": 10.0}, solver="analytic")
    assert ana["status"] in ("passed", "optimized", "not_healed")
    assert "solver" not in ana or ana.get("solver") != "pynite"


def test_unknown_solver_blocked():
    eng = UniversalCAEEngine()
    res = eng.analyze_and_optimize(_shaft_intent(), solver="ansys")
    assert res["status"] == "blocked"
    assert res["verdict_code"] == "UNKNOWN_SOLVER"


def test_non_beam_family_blocked():
    eng = UniversalCAEEngine()
    intent = {"family": PartFamily.FLANGE_PLATE.value, "spec": {"material": "Steel45"}}
    res = eng.analyze_and_optimize(intent, solver="pynite")
    assert res["status"] == "blocked"
    assert res["verdict_code"] == "FEM_FAMILY_UNSUPPORTED"


def test_bad_input_blocked():
    eng = UniversalCAEEngine()
    res = eng.analyze_beam_fem(_shaft_intent(overall_len=-5.0), {"radial_load_n": 100.0})
    assert res["status"] == "blocked"
    assert res["verdict_code"] == "FEM_BAD_INPUT"


def test_unresolved_material_blocked():
    eng = UniversalCAEEngine()
    res = eng.analyze_beam_fem(_shaft_intent(material="Unobtanium"), {"radial_load_n": 100.0})
    assert res["status"] == "blocked"
    assert res["verdict_code"] == "MATERIAL_UNRESOLVED"


def test_pynite_unavailable_is_honest(monkeypatch):
    import sys as _sys
    monkeypatch.setitem(_sys.modules, "Pynite", None)  # 使 from Pynite import ... 失败
    eng = UniversalCAEEngine()
    res = eng.analyze_beam_fem(_shaft_intent(), {"radial_load_n": 100.0})
    assert res["status"] == "unavailable"
    assert res["basis"] == "unmeasured"
    assert res["verdict_code"] == "PYNITE_UNAVAILABLE"


def test_corrupt_fea_cross_check_red(monkeypatch):
    """植入坏 FEA：把挠度放大 10 倍，交叉核验门必须判红（可证伪）。"""
    import Pynite
    real = Pynite.FEModel3D

    class _CorruptFEA(real):
        def analyze(self, *a, **k):
            super().analyze(*a, **k)
            for node in self.nodes.values():
                for key in list(node.DY.keys()):
                    node.DY[key] *= 10.0

    monkeypatch.setattr(Pynite, "FEModel3D", _CorruptFEA)
    eng = UniversalCAEEngine()
    res = eng.analyze_beam_fem(_shaft_intent(), {"radial_load_n": 12000.0})
    assert res["cross_check_passed"] is False
    assert res["status"] == "fem_cross_check_failed"
    assert res["basis"] == "unmeasured"
    assert res["deflection_error_pct"] > 2.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))