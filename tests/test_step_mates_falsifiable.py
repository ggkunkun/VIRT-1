# -*- coding: utf-8 -*-
"""配合推断反证：真实总成有接触候选；把零件挪开后必须消失。"""
from __future__ import annotations

import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bridges.step_mates import face_inventory, infer_mates  # noqa: E402

WHEEL = os.path.join(ROOT, "assets", "wheel_mold_P0.step")


def test_wheel_has_coaxial_and_plane_mates():
    inv = face_inventory(WHEEL)
    r = infer_mates(inv)
    coax = [m for m in r["mates"] if m["type"] == "coaxial"]
    planes = [m for m in r["mates"] if m["type"] in ("distance", "coincident")]
    assert coax, "no coaxial candidate"
    assert any(abs(m["radius"] - 3.0) < 1e-3 for m in coax)
    assert planes, "no plane contact candidate"
    assert 3 in r["isolated_parts"], "part 3 is exploded in this STEP"


def test_shifted_part_loses_contact():
    inv = face_inventory(WHEEL)
    base = infer_mates(inv)
    assert len(base["mates"]) >= 3
    mut = copy.deepcopy(inv)
    for key in ("cylinders", "planes"):
        for f in mut["parts"][1][key]:
            for field in ("origin", "point"):
                if field in f and f[field] is not None:
                    f[field] = (f[field][0], f[field][1], f[field][2] + 5.0)
            if f.get("select_points"):
                f["select_points"] = [(p[0], p[1], p[2] + 5.0) for p in f["select_points"]]
    shifted = infer_mates(mut)
    assert len(shifted["mates"]) < len(base["mates"]), (
        "moving part 1 by 5mm in Z must destroy at least one contact candidate; "
        "got %d vs %d" % (len(shifted["mates"]), len(base["mates"])))
    assert not any(m["a"] == 0 and m["b"] == 1 and m["type"] == "coaxial"
                   for m in shifted["mates"]), "coaxial survived a 5mm shift"


def test_inference_is_not_vacuous_on_single_parts():
    # 单零件 STEP 没有装配关联，必须返回空候选而不是伪造配合
    solo = os.path.join(ROOT, "assets", "wheel_mold_P0.step")
    inv = face_inventory(solo)
    mut = {"status": "ok", "parts": inv["parts"][:1]}
    r = infer_mates(mut)
    assert r["mates"] == []
    assert r["isolated_parts"] == [0]
