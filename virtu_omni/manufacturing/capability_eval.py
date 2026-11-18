"""Executable multi-axis and mill-turn Agent capability evaluation suite.

Covers 3-axis, 4-axis (indexed & simultaneous), 5-axis (3+2 tilted plane & simultaneous
RTCP/TRAORI/TCPM across AC/BC/AB), turning, and mill-turn (C-axis polar/cylindrical,
Y-axis, B-axis head, and subspindle transfer) across FANUC, Siemens 840D, and
Heidenhain TNC dialects, plus 16 falsifiable negative gates (planted defects must turn red).
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from virtu_omni.engine.cnc_post_processor import (
    CLCoolant,
    CLMove,
    CLProgram,
    CLRTCP,
    CLRotaryIndex,
    CLSpindle,
    CLTurningCycle,
    CLWorkplaneTilt,
    SUPPORTED_DIALECTS,
    build_canonical_cl_program,
    generate_capability_nc,
    post_process,
    validate_dialect,
    validate_program,
    verify_pose_consistency,
)
from virtu_omni.manufacturing.machine_selection import select_machine_and_stock
from virtu_omni.manufacturing.nc_audit import audit_nc_capability

CODE_CAPABILITY_CASES: Tuple[Dict[str, Any], ...] = (
    {
        "id": "code_mill_3axis_fanuc",
        "capability": "milling_3axis",
        "dialect": "fanuc",
        "rotary_axes": (),
        "variant": "default",
        "expected_tokens": ("G21", "G90", "G83", "M30"),
        "expected_candidates": ("milling_3axis_candidate",),
    },
    {
        "id": "code_mill_3axis_siemens",
        "capability": "milling_3axis",
        "dialect": "siemens",
        "rotary_axes": (),
        "variant": "default",
        "expected_tokens": ("G71", "G90", "CYCLE83(", "M30"),
        "expected_candidates": ("milling_3axis_candidate",),
    },
    {
        "id": "code_mill_3axis_heidenhain",
        "capability": "milling_3axis",
        "dialect": "heidenhain",
        "rotary_axes": (),
        "variant": "default",
        "expected_tokens": ("BEGIN PGM", "CYCL DEF 203", "END PGM"),
        "expected_candidates": ("milling_3axis_candidate",),
    },
    {
        "id": "code_mill_4axis_indexed_a",
        "capability": "milling_4axis_indexed",
        "dialect": "fanuc",
        "rotary_axes": ("A",),
        "variant": "default",
        "expected_tokens": ("M11", "M10", "A90", "M30"),
        "expected_candidates": ("milling_4axis_indexing_candidate",),
    },
    {
        "id": "code_mill_4axis_sim_a_fanuc",
        "capability": "milling_4axis_simultaneous",
        "dialect": "fanuc",
        "rotary_axes": ("A",),
        "variant": "default",
        "expected_tokens": ("G01", "A30", "A90", "M30"),
        "expected_candidates": ("milling_4axis_simultaneous_candidate",),
    },
    {
        "id": "code_mill_4axis_sim_b_siemens",
        "capability": "milling_4axis_simultaneous",
        "dialect": "siemens",
        "rotary_axes": ("B",),
        "variant": "default",
        "expected_tokens": ("G1", "B=30", "B=90", "M30"),
        "expected_candidates": ("milling_4axis_simultaneous_candidate",),
    },
    {
        "id": "code_mill_5axis_3plus2_fanuc_ac",
        "capability": "milling_5axis_3plus2",
        "dialect": "fanuc",
        "rotary_axes": ("A", "C"),
        "variant": "default",
        "expected_tokens": ("G68.2", "G53.1", "G69", "G81"),
        "expected_candidates": ("milling_5axis_positioning_candidate", "tilted_workplane_3plus2_observed"),
    },
    {
        "id": "code_mill_5axis_3plus2_siemens_bc",
        "capability": "milling_5axis_3plus2",
        "dialect": "siemens",
        "rotary_axes": ("B", "C"),
        "variant": "default",
        "expected_tokens": ("CYCLE800(", "CYCLE800()", "CYCLE81("),
        "expected_candidates": ("milling_5axis_positioning_candidate", "tilted_workplane_3plus2_observed"),
    },
    {
        "id": "code_mill_5axis_3plus2_heidenhain_ac",
        "capability": "milling_5axis_3plus2",
        "dialect": "heidenhain",
        "rotary_axes": ("A", "C"),
        "variant": "default",
        "expected_tokens": ("PLANE SPATIAL", "PLANE RESET STAY", "CYCL DEF 200"),
        "expected_candidates": ("milling_5axis_positioning_candidate", "tilted_workplane_3plus2_observed"),
    },
    {
        "id": "code_mill_5axis_sim_fanuc_ac",
        "capability": "milling_5axis_simultaneous",
        "dialect": "fanuc",
        "rotary_axes": ("A", "C"),
        "variant": "default",
        "expected_tokens": ("G43.4", "G49", "A15", "C45"),
        "expected_candidates": ("milling_5axis_simultaneous_candidate", "rtcp_5axis_observed"),
    },
    {
        "id": "code_mill_5axis_sim_fanuc_bc",
        "capability": "milling_5axis_simultaneous",
        "dialect": "fanuc",
        "rotary_axes": ("B", "C"),
        "variant": "default",
        "expected_tokens": ("G43.4", "G49", "B15", "C45"),
        "expected_candidates": ("milling_5axis_simultaneous_candidate", "rtcp_5axis_observed"),
    },
    {
        "id": "code_mill_5axis_sim_siemens_traori",
        "capability": "milling_5axis_simultaneous",
        "dialect": "siemens",
        "rotary_axes": ("A", "C"),
        "variant": "default",
        "expected_tokens": ("TRAORI", "TRAFOOF", "A=15", "C=45"),
        "expected_candidates": ("milling_5axis_simultaneous_candidate", "rtcp_5axis_observed"),
    },
    {
        "id": "code_mill_5axis_sim_heidenhain_tcpm",
        "capability": "milling_5axis_simultaneous",
        "dialect": "heidenhain",
        "rotary_axes": ("A", "C"),
        "variant": "default",
        "expected_tokens": ("FUNCTION TCPM", "FUNCTION RESET TCPM", "A+15.000", "C+45.000"),
        "expected_candidates": ("milling_5axis_simultaneous_candidate", "rtcp_5axis_observed"),
    },
    {
        "id": "code_lathe_turning_fanuc",
        "capability": "turning",
        "dialect": "fanuc",
        "rotary_axes": (),
        "variant": "default",
        "expected_tokens": ("G99", "G71", "G70", "M30"),
        "expected_candidates": ("turning_cycle_observed",),
    },
    {
        "id": "code_mill_turn_c_polar_fanuc",
        "capability": "mill_turn_off_axis_milling",
        "dialect": "fanuc",
        "rotary_axes": ("C",),
        "variant": "polar",
        "expected_tokens": ("G71", "M200", "G12.1", "G13.1"),
        "expected_candidates": ("mill_turn_c_axis_candidate", "polar_interpolation_observed"),
    },
    {
        "id": "code_mill_turn_c_polar_siemens",
        "capability": "mill_turn_off_axis_milling",
        "dialect": "siemens",
        "rotary_axes": ("C",),
        "variant": "polar",
        "expected_tokens": ("CYCLE95(", "SETMS(2)", "TRANSMIT", "TRAFOOF"),
        "expected_candidates": ("mill_turn_c_axis_candidate", "polar_interpolation_observed"),
    },
    {
        "id": "code_mill_turn_c_cylindrical_fanuc",
        "capability": "mill_turn_off_axis_milling",
        "dialect": "fanuc",
        "rotary_axes": ("C",),
        "variant": "cylindrical",
        "expected_tokens": ("G71", "G07.1 C", "G07.1 C0"),
        "expected_candidates": ("mill_turn_c_axis_candidate", "cylindrical_interpolation_observed"),
    },
    {
        "id": "code_mill_turn_y_axis_fanuc",
        "capability": "mill_turn_y_axis_milling",
        "dialect": "fanuc",
        "rotary_axes": ("C",),
        "variant": "default",
        "expected_tokens": ("G71", "M200", "Y12", "C45"),
        "expected_candidates": ("mill_turn_y_axis_candidate", "mill_turn_c_axis_candidate"),
    },
    {
        "id": "code_mill_turn_b_axis_head_siemens",
        "capability": "mill_turn_y_axis_milling",
        "dialect": "siemens",
        "rotary_axes": ("B", "C"),
        "variant": "b_head",
        "expected_tokens": ("CYCLE95(", "B=45", "SETMS(2)", "Y=12"),
        "expected_candidates": ("mill_turn_y_axis_candidate", "mill_turn_b_axis_head_candidate"),
    },
    {
        "id": "code_mill_turn_subspindle_transfer",
        "capability": "subspindle_transfer",
        "dialect": "fanuc",
        "rotary_axes": ("C",),
        "variant": "default",
        "expected_tokens": ("M269", "W-140", "M268", "M69", "G55"),
        "expected_candidates": ("subspindle_transfer_candidate", "mill_turn_y_axis_candidate"),
    },
)


def _base_machine_request(features: List[str], shape: str = "box") -> Dict[str, Any]:
    if shape == "box":
        return {
            "features": features,
            "material": "Steel45",
            "product_bbox_mm": {"xmin": 0, "xmax": 100, "ymin": 0, "ymax": 80, "zmin": 0, "zmax": 40},
            "stock": {"shape": "box", "allowance_mm": {"side": 2.0}},
        }
    return {
        "features": features,
        "material": "Steel45",
        "product_bbox_mm": {"xmin": -25, "xmax": 25, "ymin": -25, "ymax": 25, "zmin": 0, "zmax": 50},
        "stock": {"shape": "cylinder", "axis": "Z", "allowance_mm": {"radial": 2.0, "end": 3.0}},
    }


def _verified_machine(tmp_root: Path, machine_id: str, **overrides: Any) -> Dict[str, Any]:
    mdir = tmp_root / machine_id
    mdir.mkdir(parents=True, exist_ok=True)
    evidence: Dict[str, Any] = {}
    for role in ("machine", "control", "post", "simulation"):
        path = mdir / f"{role}.evidence"
        path.write_text(f"{machine_id}:{role}", encoding="utf-8")
        evidence[role] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
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


def run_negative_falsification_gates() -> List[Dict[str, Any]]:
    """Run all 16 planted-defect gates; every bad sample must be rejected."""
    results: List[Dict[str, Any]] = []

    def record(gate_id: str, rejected: bool, detail: Any) -> None:
        results.append({"id": gate_id, "planted_defect_rejected": bool(rejected), "detail": detail})

    # 1. Five-axis simultaneous without RTCP
    bad_5x_cl = CLProgram(
        name="NO_RTCP", five_axis=True, machine_type="milling_5axis_simultaneous",
        rotary_axes=("B", "C"),
        ops=[
            CLSpindle(4000, "cw"),
            CLMove("rapid", x=0.0, y=0.0, z=20.0, b=0.0, c=0.0),
            CLMove("feed", x=10.0, y=5.0, z=-2.0, b=15.0, c=45.0, f=200.0),
            CLSpindle(0, "stop"),
        ],
    )
    cl_v = validate_program(bad_5x_cl)
    record("five_axis_sim_missing_rtcp", not cl_v["passed"], cl_v["violations"])

    # 2. Uncanceled RTCP (G43.4 without G49)
    good_5x = generate_capability_nc("milling_5axis_simultaneous", dialect="fanuc", rotary_axes=("B", "C"))
    bad_nc = good_5x["nc"].replace("G49", "")
    d_v = validate_dialect("fanuc", bad_nc, build_canonical_cl_program("milling_5axis_simultaneous", rotary_axes=("B", "C")))
    a_v = audit_nc_capability(bad_nc, ["milling_5axis_simultaneous"], strict_feature_check=True)
    record("five_axis_rtcp_uncanceled", (not d_v["passed"]) and (not a_v["passed"]), {
        "dialect": d_v["violations"], "audit": a_v["issues"]
    })

    # 3. 3-axis program misusing TRAORI
    good_3x_s = generate_capability_nc("milling_3axis", dialect="siemens")
    bad_3x_s = good_3x_s["nc"].replace("G71", "TRAORI\nG71", 1)
    d_v = validate_dialect("siemens", bad_3x_s, build_canonical_cl_program("milling_3axis"))
    a_v = audit_nc_capability(bad_3x_s, ["milling_3axis"], strict_feature_check=True)
    record("three_axis_misusing_traori", (not d_v["passed"]) and (not a_v["passed"]), {
        "dialect": d_v["violations"], "audit": a_v["issues"]
    })

    # 4. Rotary axes split across separate feed blocks claiming 5-axis simultaneous
    a_v = audit_nc_capability("G1 X10 Y10 Z-1 A30 F100\nG1 B45", ["milling_5axis_simultaneous"], strict_feature_check=True)
    record("split_rotary_axes_not_5axis_simultaneous", not a_v["passed"], a_v["issues"])

    # 5. Uncanceled 3+2 tilted plane (G68.2 without G69)
    good_3p2 = generate_capability_nc("milling_5axis_3plus2", dialect="fanuc", rotary_axes=("A", "C"))
    bad_3p2 = good_3p2["nc"].replace("G69", "")
    d_v = validate_dialect("fanuc", bad_3p2, build_canonical_cl_program("milling_5axis_3plus2", rotary_axes=("A", "C")))
    a_v = audit_nc_capability(bad_3p2, ["milling_5axis_3plus2"], strict_feature_check=True)
    record("five_axis_3plus2_uncanceled_tilt", (not d_v["passed"]) and (not a_v["passed"]), {
        "dialect": d_v["violations"], "audit": a_v["issues"]
    })

    # 6. Rotary feed while clamped (M10 active)
    bad_clamped = CLProgram(
        name="CLAMP_FEED", machine_type="milling_4axis_indexed", rotary_axes=("A",),
        ops=[
            CLSpindle(2000, "cw"),
            CLRotaryIndex(a=0.0, clamp=True),
            CLMove("rapid", x=0.0, y=0.0, z=10.0),
            CLMove("feed", x=10.0, y=0.0, z=-2.0, a=45.0, f=150.0),
            CLSpindle(0, "stop"),
        ],
    )
    cl_v = validate_program(bad_clamped)
    a_v = audit_nc_capability("G0 X0 Y0 Z10\nM11\nG0 A0\nM10\nG1 X10 Y0 Z-2 A45 F150\nM30",
                              ["milling_4axis_simultaneous"], strict_feature_check=True)
    record("four_axis_clamped_rotary_feed", (not cl_v["passed"]) and (not a_v["passed"]), {
        "cl": cl_v["violations"], "audit": a_v["issues"]
    })

    # 7. Macro variable axes not resolved
    a_v = audit_nc_capability("G1 X#100 Y2 Z-1 A#101 B#102 F100", ["milling_5axis_simultaneous"])
    record("macro_variable_axes_not_verified", not a_v["passed"], a_v["issues"])

    # 8. Mill-turn live tooling conflict (turning spindle active during C/Y feed without mode switch)
    bad_mt = CLProgram(
        name="MT_CONFLICT", machine_type="mill_turn_y_axis_milling", rotary_axes=("C",), has_y_axis=True,
        ops=[
            CLSpindle(1500, "cw"),
            CLTurningCycle(stock_d=60.0, steps=[(40.0, 20.0)], total_len=45.0),
            CLMove("feed", x=40.0, y=12.0, z=-5.0, c=45.0, f=150.0),
            CLSpindle(0, "stop"),
        ],
    )
    cl_v = validate_program(bad_mt)
    record("mill_turn_spindle_mode_conflict", not cl_v["passed"], cl_v["violations"])

    # 9. Polar interpolation G12.1 uncanceled
    good_pol = generate_capability_nc("mill_turn_off_axis_milling", dialect="fanuc", rotary_axes=("C",), variant="polar")
    bad_pol = good_pol["nc"].replace("G13.1", "")
    d_v = validate_dialect("fanuc", bad_pol, build_canonical_cl_program("mill_turn_off_axis_milling", rotary_axes=("C",), variant="polar"))
    a_v = audit_nc_capability(bad_pol, ["mill_turn_off_axis_milling"], strict_feature_check=True)
    record("polar_interpolation_uncanceled", (not d_v["passed"]) and (not a_v["passed"]), {
        "dialect": d_v["violations"], "audit": a_v["issues"]
    })

    # 10. Mill-turn C-axis only NC cannot satisfy Y-axis mill-turn under strict check
    a_v = audit_nc_capability("G71 U2 R1\nG1 X40 Z0 C90 F100\nG70 P10 Q20",
                              ["mill_turn_y_axis_milling"], strict_feature_check=True)
    record("mill_turn_y_axis_missing_y_axis", not a_v["passed"], a_v["issues"])

    # 11. Subspindle main chuck unclamp M69 before subspindle clamp M268
    good_sub = generate_capability_nc("subspindle_transfer", dialect="fanuc", rotary_axes=("C",))
    bad_sub = good_sub["nc"].replace("M268 (SUBSPINDLE CLAMP)", "M69_TEMP").replace(
        "M69 (MAIN CHUCK UNCLAMP)", "M268 (SUBSPINDLE CLAMP)"
    ).replace("M69_TEMP", "M69 (MAIN CHUCK UNCLAMP)")
    d_v = validate_dialect("fanuc", bad_sub, build_canonical_cl_program("subspindle_transfer", rotary_axes=("C",)))
    a_v = audit_nc_capability(bad_sub, ["subspindle_transfer"], strict_feature_check=True)
    record("subspindle_unclamp_before_clamp", (not d_v["passed"]) and (not a_v["passed"]), {
        "dialect": d_v["violations"], "audit": a_v["issues"]
    })

    # 12. Rapid G00 negative Z plunge
    bad_plunge = CLProgram(
        name="RAPID_Z_NEG", machine_type="milling_3axis",
        ops=[CLSpindle(2000, "cw"), CLMove("rapid", x=0.0, y=0.0, z=-10.0), CLSpindle(0, "stop")],
    )
    cl_v = validate_program(bad_plunge)
    a_v = audit_nc_capability("G00 X0 Y0 Z-10.0\nM30", ["milling_3axis"], strict_feature_check=True)
    record("rapid_negative_z_plunge", (not cl_v["passed"]) and (not a_v["passed"]), {
        "cl": cl_v["violations"], "audit": a_v["issues"]
    })

    # 13-16. Machine-selection and artifact evidence negative gates
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_root = Path(tmp_str)
        m3 = _verified_machine(tmp_root, "vmc-3x", machine_class="milling_3axis", rotary_axes=[],
                               max_simultaneous_axes=3, verified_features=["milling_3axis"])
        r13 = select_machine_and_stock(_base_machine_request(["milling_5axis_simultaneous"]), [m3])
        record("three_axis_machine_rejected_for_five_axis_job",
               not r13["controller_code_generation_allowed"] and r13["status"] == "machine_class_recommended_no_feasible_profile",
               r13["status"])

        m_unknown_sim = _verified_machine(tmp_root, "unk-5x", max_simultaneous_axes=None)
        r14 = select_machine_and_stock(_base_machine_request(["milling_5axis_simultaneous"]), [m_unknown_sim])
        record("unknown_simultaneous_axes_blocks_release",
               not r14["controller_code_generation_allowed"],
               r14["candidates"][0]["reasons"])

        m_short = _verified_machine(tmp_root, "short-5x", travel_mm={"X": {"min": -20, "max": 20},
                                                                     "Y": {"min": -500, "max": 500},
                                                                     "Z": {"min": -500, "max": 500}})
        r15 = select_machine_and_stock(_base_machine_request(["milling_5axis_simultaneous"]), [m_short])
        record("travel_shorter_than_stock_blocks_machine",
               not r15["controller_code_generation_allowed"] and len(r15["excluded_candidates"]) == 1,
               r15["excluded_candidates"][0]["reasons"])

        m_bad_hash = _verified_machine(tmp_root, "bad-hash-5x")
        m_bad_hash["production_evidence"]["post"]["sha256"] = "0" * 64
        r16 = select_machine_and_stock(_base_machine_request(["milling_5axis_simultaneous"]), [m_bad_hash])
        record("artifact_hash_mismatch_blocks_release",
               not r16["controller_code_generation_allowed"],
               r16["candidates"][0]["reasons"])

    return results


def run_agent_machining_capability_eval(agent: Any = None) -> Dict[str, Any]:
    """Run full positive + negative machining & code capability evaluation."""
    positive_rows: List[Dict[str, Any]] = []
    for case in CODE_CAPABILITY_CASES:
        cap = case["capability"]
        dialect = case["dialect"]
        rotary = case["rotary_axes"]
        variant = case["variant"]
        gen = generate_capability_nc(cap, dialect=dialect, rotary_axes=rotary or None, variant=variant)
        nc = gen.get("nc") or ""
        audit = audit_nc_capability(nc, [cap], strict_feature_check=True)
        tokens_ok = all(tok in nc for tok in case["expected_tokens"])
        candidates_ok = all(cand in audit.get("feature_candidates", []) for cand in case["expected_candidates"])
        dialect_ok = audit.get("detected_dialect") == dialect

        agent_ok = True
        agent_detail: Optional[Dict[str, Any]] = None
        if agent is not None:
            cam_res = agent.facet_generate_cam({
                "machining_capability": cap,
                "dialect": dialect,
                "rotary_axes": list(rotary),
                "variant": variant,
            })
            agent_ok = bool(
                cam_res.get("static_gate_passed")
                and cam_res.get("production_nc_allowed") is False
                and cam_res.get("nc_capability_audit", {}).get("passed")
            )
            agent_detail = {
                "static_gate_passed": cam_res.get("static_gate_passed"),
                "production_nc_allowed": cam_res.get("production_nc_allowed"),
                "audit_passed": cam_res.get("nc_capability_audit", {}).get("passed"),
            }

        passed = bool(
            gen.get("status") == "passed"
            and gen.get("pose_gate", {}).get("passed")
            and audit.get("passed")
            and audit.get("program_release_allowed") is False
            and tokens_ok
            and candidates_ok
            and dialect_ok
            and agent_ok
        )
        positive_rows.append({
            "id": case["id"],
            "capability": cap,
            "dialect": dialect,
            "rotary_axes": list(rotary),
            "variant": variant,
            "passed": passed,
            "tokens_ok": tokens_ok,
            "candidates_ok": candidates_ok,
            "dialect_ok": dialect_ok,
            "pose_consistency_passed": bool(gen.get("pose_gate", {}).get("passed")),
            "audit_passed": bool(audit.get("passed")),
            "agent_checked": agent is not None,
            "agent_detail": agent_detail,
        })

    negative_rows = run_negative_falsification_gates()

    # Cross-dialect pose consistency check across all major canonical capabilities
    pose_rows = []
    for cap, rot, var in (
        ("milling_3axis", (), "default"),
        ("milling_4axis_indexed", ("A",), "default"),
        ("milling_4axis_simultaneous", ("A",), "default"),
        ("milling_5axis_3plus2", ("A", "C"), "default"),
        ("milling_5axis_simultaneous", ("B", "C"), "default"),
        ("turning", (), "default"),
        ("mill_turn_off_axis_milling", ("C",), "polar"),
        ("mill_turn_y_axis_milling", ("B", "C"), "b_head"),
        ("subspindle_transfer", ("C",), "default"),
    ):
        prog = build_canonical_cl_program(cap, rotary_axes=rot or None, variant=var)
        p_res = verify_pose_consistency(prog, dialects=SUPPORTED_DIALECTS)
        pose_rows.append({"capability": cap, "variant": var, "passed": p_res["passed"], "per_dialect": p_res["per_dialect"]})

    # Verify machine class selection + stock derivation across all 9 feature types
    machine_feature_rows = []
    for feature, shape in (
        ("milling_3axis", "box"),
        ("milling_4axis_indexed", "box"),
        ("milling_4axis_simultaneous", "box"),
        ("milling_5axis_3plus2", "box"),
        ("milling_5axis_simultaneous", "box"),
        ("turning", "cylinder"),
        ("mill_turn_off_axis_milling", "cylinder"),
        ("mill_turn_y_axis_milling", "cylinder"),
        ("subspindle_transfer", "cylinder"),
    ):
        sel = select_machine_and_stock(_base_machine_request([feature], shape=shape), [])
        ok = (
            sel.get("stock", {}).get("passed") is True
            and sel.get("controller_code_generation_allowed") is False
            and bool(sel.get("recommended_machine_classes"))
        )
        machine_feature_rows.append({"feature": feature, "passed": ok, "classes": sel.get("recommended_machine_classes")})

    all_passed = (
        all(r["passed"] for r in positive_rows)
        and all(r["planted_defect_rejected"] for r in negative_rows)
        and all(r["passed"] for r in pose_rows)
        and all(r["passed"] for r in machine_feature_rows)
    )
    return {
        "all_passed": all_passed,
        "positive_case_count": len(positive_rows),
        "positive_passed_count": sum(1 for r in positive_rows if r["passed"]),
        "negative_gate_count": len(negative_rows),
        "negative_rejected_count": sum(1 for r in negative_rows if r["planted_defect_rejected"]),
        "pose_check_count": len(pose_rows),
        "machine_feature_count": len(machine_feature_rows),
        "positive_cases": positive_rows,
        "negative_gates": negative_rows,
        "pose_checks": pose_rows,
        "machine_feature_cases": machine_feature_rows,
        "basis": "measured",
        "limitation": (
            "Measures deterministic CL postprocessing, 6-DOF coordinate/pose consistency, "
            "multi-dialect static NC audit, machine-class/stock selection, and planted-defect rejection. "
            "Does not substitute for machine-specific post hash or VERICUT Auto-Diff simulation."
        ),
    }


NEGATIVE_CODE_AND_MACHINE_GATES: Tuple[str, ...] = (
    "five_axis_sim_missing_rtcp",
    "five_axis_rtcp_uncanceled",
    "three_axis_misusing_traori",
    "split_rotary_axes_not_5axis_simultaneous",
    "five_axis_3plus2_uncanceled_tilt",
    "four_axis_clamped_rotary_feed",
    "macro_variable_axes_not_verified",
    "mill_turn_spindle_mode_conflict",
    "polar_interpolation_uncanceled",
    "mill_turn_y_axis_missing_y_axis",
    "subspindle_unclamp_before_clamp",
    "rapid_negative_z_plunge",
    "three_axis_machine_rejected_for_five_axis_job",
    "unknown_simultaneous_axes_blocks_release",
    "travel_shorter_than_stock_blocks_machine",
    "artifact_hash_mismatch_blocks_release",
)
