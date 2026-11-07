# -*- coding: utf-8 -*-
"""装配门禁反证：每个判据被破坏时必须判红（空集合不得当通过）。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bridges.assembly_pipeline import evaluate_gates  # noqa: E402


def _good():
    build = {
        "steps": {
            "import": [{"volume_match": True}, {"volume_match": True}],
            "components": [{"placement_ok": True}, {"placement_ok": True}],
            "contact_mates": [{"ok": True}, {"ok": True}],
        },
        "assembly": {"volume_match": True},
        "transform_drift": [],
        "reopen": {"components": [{"mates": ["m1"]}, {"mates": ["m1", "m2"]}]},
    }
    draw = {"view_count": 5, "reopen_view_count": 5}
    occ = {"parts": [{"roundtrip_ok": True, "face_match": True},
                     {"roundtrip_ok": True, "face_match": True}]}
    return build, draw, occ


def test_good_inputs_all_green():
    b, d, o = _good()
    gates = evaluate_gates(b, d, o, bom_parts=4, with_drawing=True)
    assert all(gates.values()), gates


def test_missing_contact_mate_goes_red():
    b, d, o = _good()
    b["steps"]["contact_mates"] = []
    assert evaluate_gates(b, d, o, 4, True)["contact_mates_ge_1"] is False


def test_unpersisted_mate_goes_red():
    b, d, o = _good()
    b["reopen"]["components"] = [{"mates": []}, {"mates": []}]
    assert evaluate_gates(b, d, o, 4, True)["mate_persisted"] is False


def test_empty_reopen_cannot_pass_as_zero_mates():
    b, d, o = _good()
    b["steps"]["contact_mates"] = []
    b["reopen"]["components"] = []
    assert evaluate_gates(b, d, o, 4, True)["mate_persisted"] is False


def test_volume_mismatch_goes_red():
    b, d, o = _good()
    b["steps"]["import"][1]["volume_match"] = False
    assert evaluate_gates(b, d, o, 4, True)["sw_import_volume"] is False


def test_placement_drift_goes_red():
    b, d, o = _good()
    b["transform_drift"] = [{"index": 2, "after": [0, 0, 0], "expected": [1, 1, 1]}]
    assert evaluate_gates(b, d, o, 4, True)["no_transform_drift"] is False


def test_volume_conservation_goes_red():
    b, d, o = _good()
    b["assembly"]["volume_match"] = False
    assert evaluate_gates(b, d, o, 4, True)["volume_conservation"] is False


def test_drawing_views_go_red():
    b, d, o = _good()
    d["reopen_view_count"] = 3
    assert evaluate_gates(b, d, o, 4, True)["drawing_views"] is False


def test_extract_roundtrip_goes_red():
    b, d, o = _good()
    o["parts"][0]["roundtrip_ok"] = False
    assert evaluate_gates(b, d, o, 4, True)["extract_volumes"] is False


def test_without_drawing_skips_drawing_gate_only():
    b, d, o = _good()
    d = {"status": "error"}
    gates = evaluate_gates(b, d, o, 4, with_drawing=False)
    assert gates["drawing_views"] is True
    assert all(gates.values())
