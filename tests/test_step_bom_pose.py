# -*- coding: utf-8 -*-
"""BOM 位姿解析回归 + 反证：纯平移解析器必须在旋转用例上判红。"""
from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bridges.step_bom import StepBOM  # noqa: E402

WHEEL = os.path.join(ROOT, "assets", "wheel_mold_P0.step")


def _synth_step(child_t, child_axis, child_ref, parent_t, parent_axis, parent_ref):
    def pt(i, xyz):
        return "#%d = CARTESIAN_POINT ( 'NONE', ( %s ) ) ;" % (i, " , ".join(repr(float(v)) for v in xyz))

    def dr(i, xyz):
        return "#%d = DIRECTION ( 'NONE', ( %s ) ) ;" % (i, " , ".join(repr(float(v)) for v in xyz))

    lines = [
        "#1 = PRODUCT ( 'root', 'ROOT', '', ( ) ) ;",
        "#2 = PRODUCT ( 'child', 'CHILD', '', ( ) ) ;",
        "#3 = PRODUCT_DEFINITION_FORMATION ( '', '', #1 ) ;",
        "#4 = PRODUCT_DEFINITION_FORMATION ( '', '', #2 ) ;",
        "#5 = PRODUCT_DEFINITION ( '', '', #3, #13 ) ;",
        "#6 = PRODUCT_DEFINITION ( '', '', #4, #13 ) ;",
        "#7 = PRODUCT_DEFINITION_SHAPE ( '', '', #5 ) ;",
        "#8 = PRODUCT_DEFINITION_SHAPE ( '', '', #6 ) ;",
        "#9 = SHAPE_DEFINITION_REPRESENTATION ( #7, #11 ) ;",
        "#10 = SHAPE_DEFINITION_REPRESENTATION ( #8, #12 ) ;",
        "#11 = SHAPE_REPRESENTATION ( 'ROOTREP', ( ), #13 ) ;",
        "#12 = SHAPE_REPRESENTATION ( 'CHILDREP', ( ), #13 ) ;",
        "#13 = ( GEOMETRIC_REPRESENTATION_CONTEXT ( 3 ) ) ;",
        "#14 = NEXT_ASSEMBLY_USAGE_OCCURRENCE ( '1', '', '', #5, #6, $ ) ;",
        "#20 =( REPRESENTATION_RELATIONSHIP ( 'NONE', 'NONE', #11, #12 ) "
        "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION ( #21 ) "
        "SHAPE_REPRESENTATION_RELATIONSHIP ( ) ) ;",
        "#21 = ITEM_DEFINED_TRANSFORMATION ( 'NONE', 'NONE', #22, #25 ) ;",
        "#22 = AXIS2_PLACEMENT_3D ( 'NONE', #23, #24, #26 ) ;",
        pt(23, child_t), dr(24, child_axis), dr(26, child_ref),
        "#25 = AXIS2_PLACEMENT_3D ( 'NONE', #27, #28, #29 ) ;",
        pt(27, parent_t), dr(28, parent_axis), dr(29, parent_ref),
        "ENDSEC;",
    ]
    return "ISO-10303-21;\nHEADER;\nFILE_SCHEMA ( ( 'CONFIG_CONTROL_DESIGN' ) );\nENDSEC;\nDATA;\n" \
        + "\n".join(lines)


def _load_synth(tmp_path, **kw):
    p = tmp_path / "posed.step"
    p.write_text(_synth_step(**kw), encoding="ascii")
    return StepBOM(str(p)).to_dict()["tree"][0]["children"][0]["placement"]


def _mat4(p):
    m = p["matrix"]
    return [[round(m[i][j], 9) for j in range(3)] for i in range(3)], [round(m[i][3], 6) for i in range(3)]


def test_wheel_mold_placements_are_pure_translation():
    d = StepBOM(WHEEL).to_dict()
    assert d["is_assembly"] and d["component_count"] == 4
    kids = d["tree"][0]["children"]
    got = {tuple(n["placement"]["origin_mm"]) for n in kids}
    assert got == {(0.0, 48.0, 0.0), (0.0, 73.0, -65.3),
                   (-1.0, 73.0, -65.3), (-113.4736, 77.0, -12.0)}
    assert all(n["placement"]["identity_rotation"] for n in kids)


def test_child_rotation_about_z_is_parsed(tmp_path):
    p = _load_synth(tmp_path, child_t=(10, 20, 30), child_axis=(0, 0, 1),
                    child_ref=(0, 1, 0), parent_t=(0, 0, 0),
                    parent_axis=(0, 0, 1), parent_ref=(1, 0, 0))
    r, t = _mat4(p)
    assert r == [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    assert t == [10.0, 20.0, 30.0]
    assert abs(p["rotation_deg"] - 90.0) < 1e-6
    assert p["identity_rotation"] is False


def test_parent_frame_is_inverted_not_ignored(tmp_path):
    p = _load_synth(tmp_path, child_t=(10, 20, 30), child_axis=(0, 0, 1),
                    child_ref=(0, 1, 0), parent_t=(5, 5, 5),
                    parent_axis=(0, 0, 1), parent_ref=(0, 1, 0))
    r, t = _mat4(p)
    assert r == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert t == [15.0, -5.0, 25.0]
    assert p["identity_rotation"] is True


def test_degenerate_ref_direction_still_orthonormal(tmp_path):
    p = _load_synth(tmp_path, child_t=(0, 0, 0), child_axis=(0, 0, 1),
                    child_ref=(0, 0, 1), parent_t=(0, 0, 0),
                    parent_axis=(0, 0, 1), parent_ref=(1, 0, 0))
    r, _ = _mat4(p)
    det = (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
           - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
           + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))
    assert abs(det - 1.0) < 1e-6
    for i in range(3):
        for j in range(i + 1, 3):
            assert abs(sum(r[k][i] * r[k][j] for k in range(3))) < 1e-6
