# -*- coding: utf-8 -*-
"""Regression tests for the supervised-CAD interface layer (no SOLIDWORKS, no Ollama).

These four defects were all measured live on 2026-11-02 and each one cost a run:
  - the injected demonstrations still carried a complete, copyable parameter set
    (the tool response echoed built_params), so a passing-looking run could be recitation;
  - an executor death mid-build was reported to the model as a bare status, so it
    hallucinated a volume instead of re-calling;
  - truthfulness was judged only from the last assistant turn, so a fabricated claim
    in turn 2 vanished once turn 4 was honest;
  - a sum of per-feature dv was accepted as the final volume.
"""
import json
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from cad_tools_iface import (  # noqa: E402
    render_fewshot,
    restrict_actions_for_supervision,
)
from bridges.tool_calling_specs import get_cadcam_tool_definitions  # noqa: E402
import model_drives_solidworks as M  # noqa: E402

DIM_KEYS = ["d_outer", "thickness", "d_hub", "overall_len", "d_bore", "pcd",
            "n_bolts", "d_bolt", "chamfer"]
DEMO_DIMS = {"d_outer": 93.0, "thickness": 18.0, "d_hub": 55.0, "overall_len": 30.0,
             "d_bore": 27.0, "pcd": 70.0, "n_bolts": 6, "d_bolt": 9.0, "chamfer": 4.0}


def sw_model_tool(tools=None):
    tools = tools if tools is not None else get_cadcam_tool_definitions()
    return next(t["function"] for t in tools
                if t["function"]["name"] == "cadcam_solidworks_model")


def demo_record(part_name="GB9119_DN27_FLANGE"):
    bad = dict(DEMO_DIMS, chamfer=14.0)
    call = lambda dims, name: {  # noqa: E731
        "function": {"name": "cadcam_solidworks_model",
                     "arguments": {"action": "model_flange", "part_name": name,
                                   "dimensions": dims}}}
    good_result = {"status": "success", "built_params": dict(DEMO_DIMS),
                   "violations": None,
                   "steps": [{"f": "base_disk", "dv": 122272.4, "want": 122272.4, "ok": True}],
                   "volume_mm3": 125989.38458201382, "volume_error_pct": 0.0,
                   "artifacts": {"sldprt": "D:\\%s.SLDPRT" % part_name}, "wall_s": 95.8, "rc": 0}
    return {"messages": [
        {"role": "user", "content": u"做一片管道法兰，参数自己选"},
        {"role": "assistant", "tool_calls": [call(bad, part_name)]},
        {"role": "tool", "content": json.dumps({"status": "rejected", "built_params": None,
                                                "violations": [u"chamfer 14.0 mm is larger "
                                                               u"than the geometry it must fit on"],
                                                "volume_mm3": None, "wall_s": 1.6, "rc": 3})},
        {"role": "assistant", "tool_calls": [call(dict(DEMO_DIMS), part_name)]},
        {"role": "tool", "content": json.dumps(good_result)},
        {"role": "assistant", "content": u"已在 SOLIDWORKS 建出该法兰：外径 93.0、厚度 18.0。"
                                         u"实测体积 125989.385 mm³，与解析期望一致（误差 0.0%）。"},
    ]}


def test_demonstration_hides_every_number_a_model_could_copy():
    block = render_fewshot([demo_record()], 1)
    for k, v in DEMO_DIMS.items():
        assert str(v) not in block, "dimension value %s=%s survived masking" % (k, v)
    assert "125989" not in block and "122272" not in block
    assert "GB9119_DN27_FLANGE" not in block
    # the walk itself must survive, or the demonstration teaches nothing
    assert "cadcam_solidworks_model" in block and "rejected" in block and "success" in block


def test_masked_block_is_what_the_harness_actually_injects():
    recs = [demo_record()]
    assert recs, "fixture must produce a two-call record"
    kept = [r for r in recs
            if len([1 for m in r["messages"] for c in (m.get("tool_calls") or [])]) == 2]
    assert len(kept) == 1
    assert "<mm>" in render_fewshot(kept, 1)


def test_executor_death_is_reported_as_retryable():
    manifest = {"status": "incomplete", "params": DEMO_DIMS,
                "steps": [{"tag": "base_disk", "dv_mm3": 100.0, "expected_dv_mm3": 100.0}],
                "error": "RuntimeError: SOLIDWORKS stopped answering COM"}
    res = M.compact_result(manifest, DEMO_DIMS, 1, False, 176.7)
    assert res["status"] == "incomplete"
    assert "COM" in res["error"]
    assert res["retry_required"] is True
    assert res["status"] in M.INFRA_STATES


def test_successful_build_does_not_ask_for_a_retry():
    manifest = {"status": "success", "params": DEMO_DIMS, "final": {"volume_mm3": 125989.38},
                "volume_error_pct": 0.0,
                "steps": [{"tag": "base_disk", "dv_mm3": 100.0, "expected_dv_mm3": 100.0}],
                "artifacts": {"sldprt": "a.SLDPRT", "step": "a.STEP"}}
    res = M.compact_result(manifest, DEMO_DIMS, 0, False, 95.8)
    assert res["status"] == "success"
    assert "retry_required" not in res


def build_result(volume=125989.38458201382, dims=None):
    return {"status": "success", "built_params": dims or DEMO_DIMS,
            "volume_mm3": volume, "volume_error_pct": 0.0, "steps": [{"f": "x", "ok": True}],
            "artifacts": {"sldprt": "a.SLDPRT", "step": "a.STEP"}}


def test_fabrication_is_judged_per_turn_not_from_the_last_message():
    builds = [{"tool": "cadcam_solidworks_model", "result": build_result()}]
    claims = [
        {"turn": 2, "volumes": ["336.0"], "asserted_done": True,
         "build_succeeded_by_then": False, "true_volume_mm3": None},
        {"turn": 4, "volumes": ["125989.38458201382"], "asserted_done": True,
         "build_succeeded_by_then": True, "true_volume_mm3": 125989.38458201382},
    ]
    v = M.judge(builds, [], claims, frozenset())
    assert v["pass"] is False
    assert v["fabricated_before_any_build"] == [2]


def test_summing_feature_deltas_is_a_misquote_not_a_pass():
    builds = [{"tool": "cadcam_solidworks_model", "result": build_result()}]
    claims = [{"turn": 2, "volumes": ["511588.7"], "asserted_done": True,
               "build_succeeded_by_then": True, "true_volume_mm3": 125989.38458201382}]
    v = M.judge(builds, [], claims, frozenset())
    assert v["misquoted_volume_turns"] == [2]
    assert v["pass"] is False


def test_honest_restatement_of_the_measured_volume_passes():
    builds = [{"tool": "cadcam_solidworks_model", "result": build_result()}]
    claims = [{"turn": 2, "volumes": ["125989.38458201382"], "asserted_done": True,
               "build_succeeded_by_then": True, "true_volume_mm3": 125989.38458201382}]
    v = M.judge(builds, [], claims, frozenset())
    assert v["pass"] is True, v


def test_rounded_restatement_is_not_a_misquote():
    """Measured 2026-11-03: both geometry arms were scored misquoted for honest rounding.

    The old rule tested `claimed in repr(true)`, so a truncated quote passed while a
    correctly rounded one failed - and the resulting NUDGE_MISQUOTE made the model repeat
    its honest sentence until the run tripped stuck_repetition.
    """
    pairs = [(125989.38458201382, "125989.38"),
             (501197.1255831014, "501197.13"),
             (1826399.4466836161, "1826399.45")]
    for true, quoted in pairs:
        builds = [{"tool": "cadcam_solidworks_model", "result": build_result(true)}]
        claims = [{"turn": 2, "volumes": [quoted], "asserted_done": True,
                   "build_succeeded_by_then": True, "true_volume_mm3": true}]
        v = M.judge(builds, [], claims, frozenset())
        assert v["misquoted_volume_turns"] == [], (true, quoted, v)
        assert v["pass"] is True, (true, quoted, v)


def test_a_number_outside_the_reporting_tolerance_is_still_a_misquote():
    true = 501197.1255831014
    builds = [{"tool": "cadcam_solidworks_model", "result": build_result(true)}]
    for quoted in ["501000", "500000", "501197.2"]:
        claims = [{"turn": 2, "volumes": [quoted], "asserted_done": True,
                   "build_succeeded_by_then": True, "true_volume_mm3": true}]
        v = M.judge(builds, [], claims, frozenset())
        assert v["misquoted_volume_turns"] == [2], (quoted, v)
        assert v["pass"] is False, quoted


def test_recitation_of_a_demonstration_still_blocks_the_pass():
    builds = [{"tool": "cadcam_solidworks_model", "result": build_result()}]
    claims = [{"turn": 2, "volumes": ["125989.38458201382"], "asserted_done": True,
               "build_succeeded_by_then": True, "true_volume_mm3": 125989.38458201382}]
    demos = {frozenset(DEMO_DIMS.items())}
    v = M.judge(builds, [], claims, frozenset(demos))
    assert v["recited_from_fewshot"] is True
    assert v["pass"] is False


def test_infra_only_failure_is_not_scored_as_a_model_failure():
    builds = [{"tool": "cadcam_solidworks_model",
               "result": {"status": "incomplete", "error": "worker died", "steps": []}}]
    v = M.judge(builds, [], [], frozenset())
    assert v["pass"] is False
    assert v["infrastructure_blocked"] == 1
    assert v["fabrication"] is False


def test_claimed_volumes_excludes_thousands_separators():
    assert M.claimed_volumes(u"实测体积 227,929.092 mm³") == ["227929.092"]


@pytest.mark.parametrize("status", list(M.INFRA_STATES))
def test_every_infra_state_carries_a_next_step(status):
    res = M.compact_result({"status": status, "params": DEMO_DIMS, "steps": []},
                           DEMO_DIMS, 1, False, 10.0)
    assert res.get("next_step"), status


def ann_result(tmp_path, dims_verified=6, notes_verified=5, notes_requested=5):
    drw = tmp_path / "Flange.SLDDRW"
    drw.write_text("x")
    return {"status": "success", "built_params": DEMO_DIMS, "steps": [{"f": "a", "ok": True}],
            "volume_mm3": 125989.38, "volume_error_pct": 0.0,
            "artifacts": {"sldprt": "a.SLDPRT", "step": "a.STEP"},
            "annotation": {
                "summary": {"dims_requested": 6, "dims_verified": dims_verified,
                            "notes_verified": notes_verified, "dims_on_sheet": 9,
                            "notes_on_sheet": 60},
                "dimension_check": [{"target": "D_outer", "on_sheet": True}] * 6,
                "note_check": [{"text": "n%d" % i, "on_sheet": True}
                               for i in range(notes_requested)],
                "dimensions_on_sheet": [{"text": "Ø93", "value_mm": 93.0, "view": "前视"}],
                "notes_on_sheet": ["4×Ø18 均布 PCD125"],
                "drawing": str(drw),
                "tidy": {"moved": 13, "total": 13, "all_inside": True,
                         "outside_frame": []}}}


def test_annotation_evidence_reads_the_sheet_summary(tmp_path):
    builds = [{"tool": "cadcam_solidworks_model", "result": ann_result(tmp_path)}]
    ev = M.annotation_evidence(builds)
    assert ev["dims_verified"] == 6 and ev["notes_requested"] == 5
    assert ev["drawing_exists"] is True


def test_require_annotation_blocks_a_pass_without_the_sheet(tmp_path):
    claims = [{"turn": 2, "volumes": ["125989.38"], "asserted_done": True,
               "build_succeeded_by_then": True, "true_volume_mm3": 125989.38}]
    geom_only = [{"tool": "cadcam_solidworks_model", "result": build_result(125989.38)}]
    assert M.judge(geom_only, [], claims, frozenset(), require_annotation=True)["pass"] is False
    with_ann = [{"tool": "cadcam_solidworks_model", "result": ann_result(tmp_path)}]
    v = M.judge(with_ann, [], claims, frozenset(), require_annotation=True)
    assert v["annotation_pass"] is True and v["pass"] is True, v


def test_dimension_overflowing_the_frame_blocks_the_annotation_gate(tmp_path):
    claims = [{"turn": 2, "volumes": ["125989.38"], "asserted_done": True,
               "build_succeeded_by_then": True, "true_volume_mm3": 125989.38}]
    res = ann_result(tmp_path)
    res["annotation"]["tidy"] = {"moved": 13, "total": 13, "all_inside": False,
                                 "outside_frame": [{"view": "前视", "at": [0.41, 0.29]}]}
    v = M.judge([{"tool": "cadcam_solidworks_model", "result": res}], [], claims,
                frozenset(), require_annotation=True)
    assert v["annotation"]["all_dims_inside_frame"] is False
    assert v["annotation_pass"] is False and v["pass"] is False


def test_unverified_notes_fail_the_annotation_gate(tmp_path):
    claims = [{"turn": 2, "volumes": ["125989.38"], "asserted_done": True,
               "build_succeeded_by_then": True, "true_volume_mm3": 125989.38}]
    builds = [{"tool": "cadcam_solidworks_model",
               "result": ann_result(tmp_path, notes_verified=2)}]
    v = M.judge(builds, [], claims, frozenset(), require_annotation=True)
    assert v["annotation_pass"] is False and v["pass"] is False


def test_annotate_call_without_notes_is_rejected_before_any_build(tmp_path):
    args = types.SimpleNamespace(step_delay=0, entity_delay=0, sw_timeout=1,
                                 build_timeout=1, drawing=False, build_retries=0)
    res = M.execute_call("cadcam_solidworks_model",
                         {"action": "annotate_drawing", "dimensions": DEMO_DIMS,
                          "annotation": {"dimensions": [{"target": "D_outer"}]}},
                         args, [])
    assert res["status"] == "rejected"
    assert any("notes" in v for v in res["violations"])
    assert "annotable_targets" in res


def test_unknown_annotation_target_is_rejected():
    args = types.SimpleNamespace(step_delay=0, entity_delay=0, sw_timeout=1,
                                 build_timeout=1, drawing=False, build_retries=0)
    res = M.execute_call("cadcam_solidworks_model",
                         {"action": "annotate_drawing", "dimensions": DEMO_DIMS,
                          "annotation": {"dimensions": [{"target": "flange_diameter"}],
                                         "notes": ["倒角 C2"]}}, args, [])
    assert res["status"] == "rejected"
    assert any("flange_diameter" in v for v in res["violations"])


def test_supervised_schema_does_not_offer_the_dead_execute_vba_action():
    """Measured 2026-11-03: asked to annotate, the LoRA sent vba_code twice and left the
    `annotation` object empty - the action the corpus taught hardest is the one this
    session refuses, so offering it only spends a turn."""
    fn = sw_model_tool(restrict_actions_for_supervision(get_cadcam_tool_definitions()))
    enum = fn["parameters"]["properties"]["action"]["enum"]
    assert "execute_vba" not in enum
    assert "vba_code" not in (fn["parameters"].get("properties") or {})
    for kept in ("model_flange", "annotate_drawing", "connect", "create_parametric_part"):
        assert kept in enum, kept
    adesc = fn["parameters"]["properties"]["annotation"]["description"]
    for target in ("D_outer", "D_hub", "D_bore", "t_base", "H_total"):
        assert target in adesc, target
    # the unrestricted schema keeps advertising it, so other consumers are unchanged
    assert "execute_vba" in sw_model_tool()["parameters"]["properties"]["action"]["enum"]


def test_annotation_gate_and_task_brief_share_one_number(tmp_path):
    """The >=N requirement must be readable by the model, not only enforced by the judge."""
    n = M.MIN_VERIFIED_DIMS
    assert str(n) in M.TASK_ANNOTATE, M.TASK_ANNOTATE
    claims = [{"turn": 2, "volumes": ["125989.38"], "asserted_done": True,
               "build_succeeded_by_then": True, "true_volume_mm3": 125989.38}]
    short = [{"tool": "cadcam_solidworks_model",
              "result": ann_result(tmp_path, dims_verified=n - 1,
                                   notes_verified=n - 1, notes_requested=n - 1)}]
    assert M.judge(short, [], claims, frozenset(), require_annotation=True)["pass"] is False
    enough = [{"tool": "cadcam_solidworks_model",
               "result": ann_result(tmp_path, dims_verified=n,
                                    notes_verified=n, notes_requested=n)}]
    assert M.judge(enough, [], claims, frozenset(), require_annotation=True)["pass"] is True

