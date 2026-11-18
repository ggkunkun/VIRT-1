from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from virtu_omni.coordinates import (
    CoordinateContractError,
    CoordinateFrame,
    FrameGraph,
    convert_length,
    identity4,
)
from virtu_omni.coordinates.runtime import (
    get_coordinate_profile,
    transform_snapshot_points,
    validate_coordinate_snapshot,
)
from virtu_omni.manufacturing.machine_selection import (
    load_training_machine_profiles,
    requirements_from_features,
    select_machine_and_stock,
)
from virtu_omni.manufacturing.nc_audit import audit_nc_capability


def _base_request(features, shape="box"):
    stock = ({"shape": "box", "allowance_mm": {"side": 2}}
             if shape == "box" else
             {"shape": "cylinder", "axis": "Z", "allowance_mm": {"radial": 2, "end": 3}})
    bbox = ({"xmin": 0, "xmax": 100, "ymin": 0, "ymax": 80, "zmin": 0, "zmax": 60}
            if shape == "box" else
            {"xmin": -10, "xmax": 10, "ymin": -10, "ymax": 10, "zmin": 0, "zmax": 50})
    return {"features": features, "material": "Steel45",
            "product_bbox_mm": bbox, "stock": stock}


def _ready_machine(tmp_path, *, machine_class="milling_5axis", post="FANUC Macro B"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    evidence = {}
    for role in ("machine", "control", "post", "simulation"):
        path = tmp_path / f"{role}.evidence"
        path.write_text(role, encoding="utf-8")
        evidence[role] = {"path": str(path),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {
        "machine_id": "verified-5x",
        "machine_class": machine_class,
        "linear_axes": ["X", "Y", "Z"],
        "rotary_axes": ["A", "B"],
        "max_simultaneous_axes": 5,
        "indexing_supported": True,
        "turning_spindle": False,
        "live_tooling": False,
        "subspindle": False,
        "travel_mm": {axis: {"min": -500, "max": 500} for axis in "XYZ"},
        "controller": "FANUC 31i",
        "post_dialect": post,
        "verified_features": ["milling_5axis_simultaneous"],
        "production_evidence": {**evidence, "collision_free": True, "autodiff_passed": True},
        "setup_count": 1,
    }


def test_units_and_coordinate_graph_transform_roundtrip():
    assert convert_length(1, "inch") == pytest.approx(25.4)
    base = CoordinateFrame("machine", "NX", "12.0", "Machine", "mm", None, identity4())
    work = CoordinateFrame(
        "work", "NX", "12.0", "MCS", "mm", "machine",
        ((1, 0, 0, 10), (0, 1, 0, 20), (0, 0, 1, 30), (0, 0, 0, 1)),
    )
    graph = FrameGraph([base, work])
    assert graph.validate()["passed"]
    assert graph.transform((1, 2, 3), "work", "machine") == pytest.approx((11, 22, 33))
    assert graph.roundtrip_error_mm((1, 2, 3), "work", "machine") == pytest.approx(0)


def test_coordinate_graph_rejects_bad_axes_missing_parent_and_cycles():
    with pytest.raises(CoordinateContractError, match="perpendicular"):
        CoordinateFrame("bad", "NX", "12.0", "bad", "mm", None,
                        ((1, 1, 0, 0), (0, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
    child = CoordinateFrame("child", "NX", "12.0", "child", "mm", "missing", identity4())
    assert not FrameGraph([child]).validate()["passed"]
    left = CoordinateFrame("left", "NX", "12.0", "left", "mm", "right", identity4())
    right = CoordinateFrame("right", "NX", "12.0", "right", "mm", "left", identity4())
    assert not FrameGraph([left, right]).validate()["passed"]
    world_a = CoordinateFrame("world_a", "NX", "12.0", "world_a", "mm", None, identity4())
    world_b = CoordinateFrame("world_b", "NX", "12.0", "world_b", "mm", None, identity4())
    disconnected = FrameGraph([world_a, world_b])
    assert not disconnected.validate()["passed"]
    with pytest.raises(CoordinateContractError, match="one connected root"):
        disconnected.transform((0, 0, 0), "world_a", "world_b")


def test_six_coordinate_profiles_are_available_but_not_live_claims():
    for app in ("solidworks", "autocad", "nx", "cimco", "vericut", "sscnc"):
        result = get_coordinate_profile(app)
        assert result["status"] == "profile_loaded"
        assert result["basis"] == "documented_or_asserted_contract_not_live_state"
        assert result["profile"]["probe"]["live_status"] != "passed"


def test_measured_coordinate_snapshot_requires_hashed_file_and_valid_frames(tmp_path):
    artifact = tmp_path / "native-state.json"
    artifact.write_text("captured from read-only API", encoding="utf-8")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    snapshot = {
        "version": "SOLIDWORKS 2021 SP5",
        "transform_unit": "mm",
        "captured_at": "2026-11-18T09:00:00+08:00",
        "source": "read-only COM probe",
        "active_document_path": "part.sldprt",
        "document_units": "mm",
        "active_coordinate_system": "model_default",
        "transform_to_model": identity4(),
        "active_frame": "model_default",
        "frames": [{"frame_id": "model_default", "name": "model_default", "units": "mm",
                    "parent_frame": None, "transform_parent_from_frame": identity4()}],
        "evidence": {"basis": "measured", "path": str(artifact), "sha256": sha},
    }
    verdict = validate_coordinate_snapshot("solidworks", snapshot)
    assert verdict["passed"]
    assert verdict["status"] == "coordinate_snapshot_hash_verified"
    mapped = transform_snapshot_points("solidworks", snapshot, "model_default", "model_default", [[1, 2, 3]])
    assert mapped["passed"] and mapped["points_mm"] == [[1.0, 2.0, 3.0]]
    snapshot["transform_to_model"] = ((1, 0, 0, 1), (0, 1, 0, 0),
                                       (0, 0, 1, 0), (0, 0, 0, 1))
    mismatched = validate_coordinate_snapshot("solidworks", snapshot)
    assert not mismatched["passed"]
    assert "transform_to_model_disagrees_with_frame_graph" in mismatched["issues"]
    snapshot["transform_to_model"] = identity4()
    snapshot["transform_unit"] = "m"
    wrong_units = validate_coordinate_snapshot("solidworks", snapshot)
    assert not wrong_units["passed"]
    assert "transform_unit_must_be_mm" in wrong_units["issues"]
    snapshot["transform_unit"] = "mm"
    artifact.write_text("changed", encoding="utf-8")
    assert not validate_coordinate_snapshot("solidworks", snapshot)["passed"]


def test_coordinate_snapshot_does_not_pass_with_missing_or_timezone_free_evidence():
    missing = validate_coordinate_snapshot("nx", {})
    assert not missing["passed"]
    profile = get_coordinate_profile("nx")["profile"]
    snapshot = {key: "present" for key in profile["probe"]["required_fields"]}
    snapshot.update({"version": "NX 12.0", "captured_at": "2026-11-18T09:00:00",
                    "source": "claimed API", "frames": [], "evidence": {"basis": "measured"}})
    verdict = validate_coordinate_snapshot("nx", snapshot)
    assert not verdict["passed"]
    assert "captured_at_timezone_required" in verdict["issues"]
    assert "evidence_file_missing_or_sha256_mismatch" in verdict["issues"]


@pytest.mark.parametrize("software", ["solidworks", "autocad", "nx", "cimco", "vericut", "sscnc"])
def test_each_software_requires_its_native_coordinate_fields_and_connected_frames(tmp_path, software):
    artifact = tmp_path / f"{software}.json"
    artifact.write_text(f"{software} read-only capture", encoding="utf-8")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    frame_specs = {
        "solidworks": [("model_default", None)],
        "autocad": [("WCS", None), ("UCS", "WCS")],
        "nx": [("absolute", None), ("WCS", "absolute"),
               ("CAM_MCS", "WCS"), ("workpiece_frame", "CAM_MCS")],
        "cimco": [("NC_program_position", None), ("machine_setup", "NC_program_position"),
                  ("stock_work_origin", "machine_setup")],
        "vericut": [("machine_root", None), ("NC_work_offset", "machine_root")],
        "sscnc": [("MACHINE", None), ("RELATIVE", "MACHINE"),
                  ("ABSOLUTE_G54", "MACHINE")],
    }[software]
    frames = [{"frame_id": name, "name": name, "units": "mm", "parent_frame": parent,
               "transform_parent_from_frame": identity4()}
              for name, parent in frame_specs]
    snapshot = {
        "version": {"solidworks": "SOLIDWORKS 2021", "autocad": "AutoCAD 2026",
                    "nx": "NX 12.0", "cimco": "CIMCO Edit 2026",
                    "vericut": "VERICUT 9.6", "sscnc": "SSCNC 7.2"}[software],
        "transform_unit": "mm",
        "captured_at": "2026-11-18T09:00:00+08:00",
        "source": "read-only native API or project capture",
        "active_frame": frame_specs[0][0],
        "frames": frames,
        "evidence": {"basis": "measured", "path": str(artifact), "sha256": sha},
    }
    if software == "solidworks":
        snapshot.update({"active_document_path": "part.sldprt", "document_units": "mm",
                         "active_coordinate_system": "model_default", "transform_to_model": identity4()})
    elif software == "autocad":
        snapshot.update({"drawing_path": "part.dwg", "INSUNITS": 4, "UCSNAME": "UCS",
                         "UCSORG": [0, 0, 0], "UCSXDIR": [1, 0, 0], "UCSYDIR": [0, 1, 0],
                         "active_viewport": 1})
    elif software == "nx":
        snapshot.update({"part_path": "part.prt", "part_units": "mm", "absolute_frame": "absolute",
                         "WCS_origin": [0, 0, 0], "WCS_orientation": identity4(),
                         "CAM_MCS": "CAM_MCS", "workpiece_frame": "workpiece_frame"})
    elif software == "cimco":
        snapshot.update({"nc_sha256": sha, "control_type": "FANUC 31i", "machine_setup": "VMC",
                         "units": "G21", "G90_G91": "G90", "plane": "G17",
                         "work_offset": "G54", "stock_origin": [0, 0, 0]})
    elif software == "vericut":
        snapshot.update({"project_sha256": sha, "machine_file_sha256": sha,
                         "control_file_sha256": sha, "component_transforms": {"stock": identity4()},
                         "work_offset": {"frame_id": "NC_work_offset", "transform": identity4()},
                         "simulation_log_sha256": sha, "collision_count": 0,
                         "autodiff_verdict": "GREEN"})
    else:
        snapshot.update({"controller_model": "FANUC 0iM", "machine_model": "VMC", "mode": "EDIT",
                         "MACHINE": [0, 0, 0], "RELATIVE": [0, 0, 0], "ABSOLUTE": [0, 0, 0],
                         "G54": [0, 0, 0], "tool_offset": {"T1": [0, 0, 0]},
                         "program_sha256": sha})
    assert get_coordinate_profile(software)["profile"]["probe"]["required_fields"]
    verdict = validate_coordinate_snapshot(software, snapshot)
    assert verdict["passed"], verdict["issues"]
    expected_cross_check = {
        "autocad": ("UCSORG", [1, 0, 0], "UCS_native_values_disagree_with_frame_graph"),
        "nx": ("WCS_origin", [1, 0, 0], "WCS_native_values_disagree_with_frame_graph"),
    }.get(software)
    if expected_cross_check:
        key, wrong_value, issue = expected_cross_check
        snapshot[key] = wrong_value
        mismatch = validate_coordinate_snapshot(software, snapshot)
        assert not mismatch["passed"]
        assert issue in mismatch["issues"]


@pytest.mark.parametrize("feature,expected_class", [
    ("milling_3axis", "milling_3axis"),
    ("milling_4axis_indexed", "milling_4axis_indexed"),
    ("milling_4axis_simultaneous", "milling_4axis_simultaneous"),
    ("milling_5axis_3plus2", "milling_5axis_3plus2"),
    ("milling_5axis_simultaneous", "milling_5axis_simultaneous"),
    ("mill_turn_y_axis_milling", "mill_turn"),
    ("subspindle_transfer", "mill_turn"),
    ("turning", "lathe"),
])
def test_feature_rules_distinguish_machine_types(feature, expected_class):
    req = requirements_from_features([feature])
    assert expected_class in req["machine_classes"]
    if feature == "milling_5axis_simultaneous":
        assert req["min_rotary_axes"] == 2
        assert req["min_simultaneous_axes"] == 5
    if feature == "milling_5axis_3plus2":
        assert req["indexing_required"]
    if feature == "mill_turn_y_axis_milling":
        assert req["turning_spindle"] and req["live_tooling"]
        assert req["linear_axes"] == ["X", "Y", "Z"]
        assert req["rotary_axes"] == ["C"]


def test_unverified_simultaneous_5axis_is_only_a_class_recommendation():
    machine = {"machine_id": "training-5x", "machine_class": "milling_5axis",
               "linear_axes": ["X", "Y", "Z"], "rotary_axes": ["A", "B"],
               "max_simultaneous_axes": None, "indexing_supported": None,
               "travel_mm": {axis: {"min": -500, "max": 500} for axis in "XYZ"}}
    result = select_machine_and_stock(
        _base_request(["milling_5axis_simultaneous"]), [machine])
    assert result["status"] == "machine_class_recommended_exact_machine_unverified"
    assert not result["controller_code_generation_allowed"]
    assert "simultaneous_axis_count_unverified" in result["candidates"][0]["reasons"]
    assert result["stock"]["dimensions_mm"] == {"dx": 104.0, "dy": 84.0, "dz": 64.0}
    assert result["travel_check_envelope_mm"] == {"X": 104.0, "Y": 84.0, "Z": 64.0}


def test_three_axis_machine_is_a_hard_mismatch_for_simultaneous_five_axis():
    machine = {"machine_id": "3x", "machine_class": "milling_3axis",
               "linear_axes": ["X", "Y", "Z"], "rotary_axes": [],
               "max_simultaneous_axes": 3, "travel_mm": {axis: {"min": -500, "max": 500}
                                                               for axis in "XYZ"}}
    result = select_machine_and_stock(_base_request(["milling_5axis_simultaneous"]), [machine])
    assert result["status"] == "machine_class_recommended_no_feasible_profile"
    assert any("rotary_axes_insufficient" in reason
               for reason in result["excluded_candidates"][0]["reasons"])
    assert not result["controller_code_generation_allowed"]


def test_three_plus_two_requires_indexing_evidence_and_machine_travel():
    machine = {"machine_id": "unknown-indexing", "machine_class": "milling_5axis",
               "linear_axes": ["X", "Y", "Z"], "rotary_axes": ["A", "B"],
               "max_simultaneous_axes": 3, "indexing_supported": None,
               "travel_mm": {axis: {"min": -50, "max": 50} for axis in "XYZ"}}
    result = select_machine_and_stock(_base_request(["milling_5axis_3plus2"]), [machine])
    candidate = result["excluded_candidates"][0]
    assert "indexing_capability_unverified" in candidate["reasons"]
    assert "travel_exceeded:X" in candidate["reasons"]
    assert not result["controller_code_generation_allowed"]


def test_four_axis_indexed_and_simultaneous_require_separate_proofs():
    indexed = {"machine_id": "4x-index-unknown", "machine_class": "milling_4axis",
               "linear_axes": ["X", "Y", "Z"], "rotary_axes": ["A"],
               "max_simultaneous_axes": 3, "indexing_supported": None,
               "travel_mm": {axis: {"min": -500, "max": 500} for axis in "XYZ"}}
    indexed_result = select_machine_and_stock(
        _base_request(["milling_4axis_indexed"]), [indexed])
    assert "indexing_capability_unverified" in indexed_result["candidates"][0]["reasons"]
    simultaneous = {**indexed, "machine_id": "4x-sim-unknown", "indexing_supported": True,
                    "max_simultaneous_axes": None}
    simultaneous_result = select_machine_and_stock(
        _base_request(["milling_4axis_simultaneous"]), [simultaneous])
    assert "simultaneous_axis_count_unverified" in simultaneous_result["candidates"][0]["reasons"]
    too_few = {**simultaneous, "machine_id": "4x-only-3sim", "max_simultaneous_axes": 3}
    rejected = select_machine_and_stock(
        _base_request(["milling_4axis_simultaneous"]), [too_few])
    assert "simultaneous_axes_insufficient:3<4" in rejected["excluded_candidates"][0]["reasons"]


def test_mill_turn_requires_verified_spindle_live_tool_and_c_axis():
    machine = {"machine_id": "incomplete-millturn", "machine_class": "mill_turn",
               "linear_axes": ["X", "Y", "Z"], "rotary_axes": [],
               "turning_spindle": False, "live_tooling": None,
               "travel_mm": {axis: {"min": -500, "max": 500} for axis in "XYZ"}}
    result = select_machine_and_stock(
        _base_request(["mill_turn_y_axis_milling", "subspindle_transfer"]), [machine])
    candidate = result["excluded_candidates"][0]
    assert any(issue.startswith("required_rotary_axes_missing:C") for issue in candidate["reasons"])
    assert "turning_spindle_missing" in candidate["reasons"]
    assert "live_tooling_unverified" in candidate["reasons"]
    assert "subspindle_unverified" in candidate["reasons"]
    assert not result["controller_code_generation_allowed"]


def test_stock_cylinder_and_invalid_stock_are_explicitly_checked():
    cylinder = select_machine_and_stock(_base_request(["turning"], shape="cylinder"), [])
    assert cylinder["stock"]["passed"]
    assert cylinder["stock"]["axis"] == "Z"
    assert cylinder["stock"]["dimensions_mm"] == {"diameter": 24.0, "height": 56.0}
    x_axis = _base_request(["turning"], shape="cylinder")
    x_axis["product_bbox_mm"] = {"xmin": 0, "xmax": 50, "ymin": -10, "ymax": 10,
                                 "zmin": -10, "zmax": 10}
    x_axis["stock"]["axis"] = "X"
    x_stock = select_machine_and_stock(x_axis, [])
    assert x_stock["travel_check_envelope_mm"] == {"X": 56.0, "Y": 24.0, "Z": 24.0}
    bad = _base_request(["milling_3axis"])
    bad["stock"]["allowance_mm"]["side"] = -1
    rejected = select_machine_and_stock(bad, [])
    assert rejected["status"] == "stock_rejected"
    assert not rejected["stock"]["passed"]


def test_verified_exact_machine_needs_all_four_hashed_artifacts(tmp_path):
    machine = _ready_machine(tmp_path)
    result = select_machine_and_stock(
        _base_request(["milling_5axis_simultaneous"]), [machine])
    assert result["status"] == "selected_verified_machine"
    assert result["controller_code_generation_allowed"]
    machine["production_evidence"]["post"]["sha256"] = "0" * 64
    rejected = select_machine_and_stock(
        _base_request(["milling_5axis_simultaneous"]), [machine])
    assert rejected["status"] == "machine_class_recommended_exact_machine_unverified"
    assert not rejected["controller_code_generation_allowed"]
    assert "post_artifact_missing_or_hash_mismatch" in rejected["candidates"][0]["reasons"]
    compatible_hashes_wrong_feature = _ready_machine(tmp_path / "wrong-feature")
    compatible_hashes_wrong_feature.update({"machine_id": "wrong-post-feature",
                                            "verified_features": ["milling_3axis"]})
    wrong_feature = select_machine_and_stock(
        _base_request(["milling_5axis_simultaneous"]), [compatible_hashes_wrong_feature])
    assert "post_feature_not_verified:milling_5axis_simultaneous" in \
        wrong_feature["candidates"][0]["reasons"]
    assert not wrong_feature["controller_code_generation_allowed"]
    false_green = _ready_machine(tmp_path / "false-green")
    false_green.update({"machine_id": "string-true-is-not-proof"})
    false_green["production_evidence"]["collision_free"] = "true"
    blocked = select_machine_and_stock(
        _base_request(["milling_5axis_simultaneous"]), [false_green])
    assert "collision_free_not_proven" in blocked["candidates"][0]["reasons"]
    assert not blocked["controller_code_generation_allowed"]


def test_machine_ranking_uses_measured_setups_then_axis_excess(tmp_path):
    two_setups = _ready_machine(tmp_path / "two")
    two_setups.update({"machine_id": "two-setups", "setup_count": 2})
    one_setup_extra_axis = _ready_machine(tmp_path / "one")
    one_setup_extra_axis.update({"machine_id": "one-setup-extra-axis", "setup_count": 1,
                                 "rotary_axes": ["A", "B", "C"]})
    one_setup = _ready_machine(tmp_path / "best")
    one_setup.update({"machine_id": "one-setup", "setup_count": 1})
    result = select_machine_and_stock(
        _base_request(["milling_5axis_simultaneous"]),
        [two_setups, one_setup_extra_axis, one_setup],
    )
    assert result["selected_machine"]["machine_id"] == "one-setup"
    assert result["optimality_proven"] is True


def test_missing_objective_evidence_does_not_claim_an_optimal_machine(tmp_path):
    first = _ready_machine(tmp_path / "first")
    first.update({"machine_id": "first", "setup_count": 1})
    second = _ready_machine(tmp_path / "second")
    second.update({"machine_id": "second", "setup_count": None})
    result = select_machine_and_stock(
        _base_request(["milling_5axis_simultaneous"]), [first, second])
    assert result["status"] == "objective_data_missing"
    assert not result["optimality_proven"]
    assert not result["controller_code_generation_allowed"]


def test_milling_machine_with_unknown_three_axis_simultaneous_control_is_unverified():
    machine = {"machine_id": "3x-linear-only", "machine_class": "milling_3axis",
               "linear_axes": ["X", "Y", "Z"], "rotary_axes": [],
               "max_simultaneous_axes": None,
               "travel_mm": {axis: {"min": -500, "max": 500} for axis in "XYZ"}}
    result = select_machine_and_stock(_base_request(["milling_3axis"]), [machine])
    assert result["candidates"][0]["feasible_for_planning"]
    assert not result["candidates"][0]["production_ready"]
    assert "simultaneous_axis_count_unverified" in result["candidates"][0]["reasons"]


def test_training_case_manifest_keeps_all_cases_and_missing_assets_visible():
    path = Path("knowledge_base/machining/training_case_manifest.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 80
    missing = [item for row in rows for item in row["artifacts"] if not item.get("verified")]
    assert len(missing) == 7
    assert {item["path"] for item in missing} == {
        "force_turning_fanuc_sample.nc", "vericutm.eia"
    }
    assert all("not independent proof of production safety" in row["expected_use"] for row in rows)


def test_training_machine_examples_are_hashed_but_not_promoted_to_shop_inventory():
    if not Path("E:/training").is_dir():
        pytest.skip("E:/training is a user-provided local case library")
    result = load_training_machine_profiles()
    assert result["machine_count"] == 49
    assert result["invalid_machine_files"] == []
    assert all(machine["selection_evidence_valid"] for machine in result["machines"])
    assert all(not machine["production_ready"] for machine in result["machines"])
    assert all(machine["live_tooling"] is None and machine["subspindle"] is None
               for machine in result["machines"])


@pytest.mark.parametrize(("program", "feature", "candidate"), [
    ("G0 X0 Y0 Z5\nG1 X10 Y10 Z-1 F100", "milling_3axis", "milling_3axis_candidate"),
    ("G0 X0 Y0 Z5 A90\nG1 X10 Y0 Z-1 F100", "milling_4axis_indexed", "milling_4axis_indexing_candidate"),
    ("G1 X10 Y10 Z-1 A30 F100", "milling_4axis_simultaneous", "milling_4axis_simultaneous_candidate"),
    ("G0 X0 Y0 Z5 A0 B90\nG1 X10 Y10 Z-1 F100", "milling_5axis_3plus2", "milling_5axis_positioning_candidate"),
    ("G1 X10 Y10 Z-1 A30 B45 F100", "milling_5axis_simultaneous", "milling_5axis_simultaneous_candidate"),
])
def test_nc_audit_distinguishes_three_four_five_axis_motion(program, feature, candidate):
    verdict = audit_nc_capability(program, [feature])
    assert verdict["status"] == "static_match", verdict
    assert candidate in verdict["feature_candidates"]
    assert verdict["program_release_allowed"] is False


def test_nc_audit_rejects_rotary_axes_split_across_distinct_feed_blocks_as_5axis_simultaneous():
    program = "G1 X10 Y10 Z-1 A30 F100\nG1 B45"
    verdict = audit_nc_capability(program, ["milling_5axis_simultaneous"])
    assert verdict["status"] == "insufficient_evidence"
    assert "milling_5axis_simultaneous_candidate" not in verdict["feature_candidates"]
    assert any(issue.startswith("required_motion_not_observed") for issue in verdict["issues"])


def test_nc_audit_treats_turning_plus_c_feed_as_mill_turn_candidate_only():
    program = "G71 U2 R1\nG1 X40 Z0 C90 F100\nG70 P10 Q20"
    verdict = audit_nc_capability(program, ["mill_turn_y_axis_milling"])
    assert "turning_cycle_observed" in verdict["feature_candidates"]
    assert "mill_turn_candidate_unverified" in verdict["feature_candidates"]
    assert "live_tooling_spindle_sync_and_transfer_require_controller_specific_review" in verdict["issues"]
    assert verdict["program_release_allowed"] is False


def test_nc_audit_does_not_treat_macro_axis_variables_as_proven_coordinates():
    verdict = audit_nc_capability("G1 X#100 Y2 Z-1 A#101 B#102 F100",
                                  ["milling_5axis_simultaneous"])
    assert verdict["status"] == "insufficient_evidence"
    assert {"A", "B", "X"}.issubset(set(verdict["issues"][-1].split(":")[-1].split(",")))


def test_nc_audit_is_available_in_agent_and_external_tool_registries():
    from bridges.tool_calling_specs import execute_tool_call, known_tool_names, tool_risk_level
    from virtu_omni.agent.super_agent import VirtuSuperAgent

    assert "cadcam_nc_capability_audit" in known_tool_names()
    assert tool_risk_level("cadcam_nc_capability_audit") == "read"
    external = execute_tool_call("cadcam_nc_capability_audit", {
        "program": "G1 X10 Y10 Z-1 A90 F100",
        "required_features": ["milling_4axis_simultaneous"],
    })
    assert external["status"] == "static_match"
    assert external["program_release_allowed"] is False
    agent = VirtuSuperAgent.__new__(VirtuSuperAgent)
    agent._tool_registry = {}
    agent._register_default_tools()
    assert "audit_nc_capability" in agent.tools
    result = agent.call_tool("audit_nc_capability", {"program": "G1 X10 Y10 Z-1 A90 F100"})
    assert "milling_4axis_simultaneous_candidate" in result["feature_candidates"]
    assert result["program_release_allowed"] is False


def test_super_agent_registers_coordinate_and_machine_tools_without_gui_input():
    from virtu_omni.agent.super_agent import VirtuSuperAgent

    agent = VirtuSuperAgent.__new__(VirtuSuperAgent)
    agent._tool_registry = {}
    agent._register_default_tools()
    assert "select_machine_and_stock" in agent.tools
    assert "coordinate_contract" in agent.tools
    profile = agent.call_tool("coordinate_contract", {"software": "nx"})
    assert profile["status"] == "profile_loaded"
    blocked = agent.call_tool("generate_cam_toolpath", {
        "manufacturing_request": _base_request(["milling_5axis_simultaneous"])
    })
    assert blocked["verdict_code"] == "MACHINE_OR_STOCK_GATE_BLOCKED"
    assert blocked["production_nc_allowed"] is False

