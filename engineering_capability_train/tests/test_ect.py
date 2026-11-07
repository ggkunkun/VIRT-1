#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_ect.py — 无需 GPU / 无需模型权重的链路自检。

运行：
  cd engineering_capability_train
  python -m unittest discover -s tests -v
或：
  python tests/test_ect.py
"""
from __future__ import annotations

import json
import math
import random
import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))

from ect_common import load_config, repo_root, resolve, sha256_text  # noqa: E402
from physics_gate import (best_candidate, candidate_cost, check_parametric_model,  # noqa: E402
                          check_process, check_tolerance_fit, check_toolpath,
                          gate_decision, selftest as physics_selftest)
from _ect_rowcheck import (check_tool_calls, normalize_messages,  # noqa: E402
                           tool_spec_index)
from data_builders import (build_gui_trajectories, build_toolchain,  # noqa: E402
                           build_vision_decisions, GUI_ACTION_SPACE, SCREEN,
                           _make_candidates, _TOOLSETS)
from gui_task_runner import run_task, validate_action  # noqa: E402
from evaluate import aggregate, grade_vision, self_test as metrics_self_test  # noqa: E402


class TestConfig(unittest.TestCase):
    def test_configs_parse_and_mix_sums_to_one(self):
        cfg = load_config("pipeline")
        tr = load_config("train")
        mt = load_config("metrics")
        self.assertAlmostEqual(sum(cfg["data_mix"].values()), 1.0)
        self.assertEqual(tr["sft"]["lora_r"], 32)
        self.assertEqual(tr["sft"]["lora_alpha"], 64)
        self.assertNotIn("peft_linear", tr["merge"]["modes_allowed"])
        self.assertEqual(mt["acceptance_gates"]["physics_compliance_rate_min"], 1.0)
        self.assertTrue(mt["metrics"]["physics_compliance_rate"]["veto"])

    def test_profiles_present(self):
        tr = load_config("train")
        for name in ("v100_32g", "l40s_48g", "a100_80g"):
            self.assertIn(name, tr["profiles"])
        self.assertFalse(tr["profiles"]["v100_32g"]["bf16"])
        self.assertFalse(tr["profiles"]["v100_32g"]["flash_attention_2"])


class TestPhysicsGate(unittest.TestCase):
    def test_full_selftest(self):
        self.assertEqual(physics_selftest(), 0)

    def test_volume_conservation_and_geometry(self):
        spec = {"dimensions": {"d_outer": 53.0, "d_inner": 14.0,
                               "overall_len": 45.0, "material": "Cr12MoV"}}
        self.assertTrue(check_parametric_model(spec).ok)
        bad = {"dimensions": {"d_outer": 14.0, "d_inner": 53.0}}
        self.assertFalse(check_parametric_model(bad).ok)
        broken = dict(spec, before_volume_mm3=1000.0, delta_volume_mm3=-100.0,
                      after_volume_mm3=12345.0, operation="cut")
        self.assertFalse(check_parametric_model(broken).ok)

    def test_material_not_silently_defaulted(self):
        from physics_gate import check_material
        self.assertFalse(check_material("Unobtainium").ok)
        self.assertTrue(check_material("Cr12MoV").ok)

    def test_fos_and_cutting_formula(self):
        v = check_parametric_model({"dimensions": {"material": "Steel45"},
                                    "sigma_von_mises_mpa": 300.0})
        self.assertFalse(v.ok)  # 355/300 = 1.18 < 1.5
        p = check_process({"D": 20.0, "vc": 100.0, "fz": 0.1, "ap": 2.0,
                           "r_eps": 0.8})
        self.assertTrue(p.ok)
        self.assertAlmostEqual(p.reference["spindle_rpm"],
                               1000 * 100 / (math.pi * 20), places=6)

    def test_iso_fit_and_dimension_chain(self):
        v = check_tolerance_fit({"nominal_d_mm": 40.0, "hole": "H7", "shaft": "g6",
                                 "chain_tolerances_mm": [0.1, 0.2, 0.15]})
        self.assertTrue(v.ok)
        self.assertGreaterEqual(v.reference["worstcase_mm"], v.reference["rss_mm"])
        self.assertGreater(v.reference["min_clearance_um"], 0)
        over = check_tolerance_fit({"nominal_d_mm": 40.0, "hole": "H7",
                                    "shaft": "p6"})
        self.assertLess(over.reference["min_clearance_um"], 0)

    def test_g00_and_autodiff(self):
        self.assertFalse(check_toolpath({"safe_plane_z_mm": 5.0,
                                         "rapid_min_z_mm": -1.0,
                                         "stock_top_z_mm": 0.0}).ok)
        self.assertFalse(check_toolpath({"safe_plane_z_mm": 5.0,
                                         "rapid_min_z_mm": 6.0,
                                         "stock_top_z_mm": 0.0,
                                         "autodiff": "red"}).ok)

    def test_cost_model_prefers_feasible_fastest(self):
        cands = [{"id": "slow", "estimated_time_s": 120.0, "risk": 0.1},
                 {"id": "fast", "estimated_time_s": 45.0, "risk": 0.1},
                 {"id": "bad", "estimated_time_s": 1.0, "risk": 0.0,
                  "physics_ok": False}]
        self.assertEqual(best_candidate(cands, {}), "fast")
        self.assertTrue(math.isinf(candidate_cost(cands[2], {})))


class TestCorpusRules(unittest.TestCase):
    def test_tool_whitelist_has_14(self):
        idx = tool_spec_index()
        self.assertEqual(len(idx), 14)
        self.assertTrue(all(n.startswith("cadcam_") for n in idx))

    def test_tool_call_validation(self):
        idx = tool_spec_index()
        self.assertEqual(check_tool_calls(
            json.dumps({"tool": "cadcam_preflight", "arguments": {}}), idx), [])
        self.assertTrue(check_tool_calls(
            json.dumps({"tool": "not_a_tool", "arguments": {}}), idx))
        self.assertTrue(check_tool_calls(
            json.dumps({"tool": "cadcam_visual_inspect",
                        "arguments": {"action": "blueprint_analysis"}}), idx))
        self.assertTrue(check_tool_calls(
            json.dumps({"name": "cadcam_preflight", "arguments": {}}), idx))

    def test_normalize_messages(self):
        msgs = [{"role": "system", "content": "s"},
                {"role": "user", "content": None},
                {"role": "assistant", "content": None,
                 "tool_calls": [{"function": {"name": "cadcam_preflight",
                                              "arguments": "{}"}}]},
                {"role": "tool", "content": {"ok": True}}]
        out = normalize_messages(msgs)
        self.assertTrue(all(isinstance(m["content"], str) for m in out))
        self.assertIn("cadcam_preflight", out[2]["content"])
        self.assertIn('"tool"', out[2]["content"])

    def test_generators_are_deterministic(self):
        a = build_toolchain(20, random.Random(7), {})
        b = build_toolchain(20, random.Random(7), {})
        self.assertEqual([r["meta"]["id"] for r in a], [r["meta"]["id"] for r in b])
        c1, e1 = build_vision_decisions(30, random.Random(11), {})
        c2, e2 = build_vision_decisions(30, random.Random(11), {})
        self.assertEqual([x["task_id"] for x in e1], [x["task_id"] for x in e2])
        self.assertEqual([json.loads(r["messages"][2]["content"]).get("selected")
                          for r in c1],
                         [json.loads(r["messages"][2]["content"]).get("selected")
                          for r in c2])

    def test_vision_candidates_have_diverse_optima(self):
        rows, evals = build_vision_decisions(90, random.Random(2026), {})
        chosen = [json.loads(r["messages"][2]["content"]).get("selected")
                  for r in rows if not r["meta"].get("boundary")]
        self.assertGreater(len(set(chosen)), 2, "最优解分布过于集中，模型可靠猜测蒙对")
        for e in evals:
            self.assertIsNotNone(e["expected_chosen"])
            cand = next(c for c in e["candidates"] if c["id"] == e["expected_chosen"])
            self.assertTrue(cand["physics_ok"])

    def test_gui_actions_within_whitelist_and_screen(self):
        rows = build_gui_trajectories(5, random.Random(3), {})
        for r in rows:
            out = json.loads(r["messages"][2]["content"])
            for a in out["actions"]:
                self.assertIn(a["action"], GUI_ACTION_SPACE)
                self.assertIsNone(validate_action(a["action"], a["args"]))
            v = out["verification"]
            self.assertAlmostEqual(v["after_volume_mm3"],
                                   v["before_volume_mm3"] + v["delta_volume_mm3"],
                                   places=2)


class TestMetrics(unittest.TestCase):
    def test_metrics_selftest(self):
        self.assertEqual(metrics_self_test(), 0)

    def test_physics_veto_blocks_acceptance(self):
        mcfg = load_config("metrics")
        recs = [{"task_id": str(i), "verdict": "pass", "criteria_passed": True,
                 "physics_ok": True, "elapsed_s": 1.0,
                 "decision_optimality": 1.0, "semantic_grounding": 1.0,
                 "tool_valid": 1.0, "model_valid": 1.0, "gui_action_valid": 1.0,
                 "errors": []} for i in range(40)]
        r = aggregate(recs, mcfg)
        self.assertTrue(all(c["pass"] for c in r["gate_checks"]))
        recs[0] = dict(recs[0], physics_ok=False, verdict="physics_violation")
        r2 = aggregate(recs, mcfg)
        self.assertFalse(r2["physics_veto_passed"])
        self.assertFalse(r2["accepted"])

    def test_transport_excluded_from_denominator(self):
        mcfg = load_config("metrics")
        recs = [{"task_id": "a", "verdict": "pass", "criteria_passed": True,
                 "physics_ok": True, "elapsed_s": 1.0, "errors": []},
                {"task_id": "b", "verdict": "transport_error",
                 "transport_error": True, "elapsed_s": 0.1, "errors": ["x"]}]
        r = aggregate(recs, mcfg)
        self.assertEqual(r["n_valid_tasks"], 1)
        self.assertAlmostEqual(r["metrics"]["task_success_rate"], 1.0)

    def test_optimality_and_grounding_grading(self):
        task = {
            "task_id": "v1", "capability": "vision_decision",
            "condition": {"bore_d_mm": 25.0, "fit": "H7/g6",
                          "material": "Steel45", "ra_required_um": 1.6,
                          "spindle_max_rpm": 3000, "batch_size": 10,
                          "tool_available": _TOOLSETS[0]},
            "required_grounding_fields": ["bore_d_mm", "fit", "material",
                                          "ra_required_um", "spindle_max_rpm",
                                          "tool_available", "batch_size"],
        }
        task["candidates"] = _make_candidates(task["condition"])
        task["expected_chosen"] = best_candidate(task["candidates"], {})
        self.assertIsNotNone(task["expected_chosen"])
        good = json.dumps({
            "selected": task["expected_chosen"],
            "reason": " ".join(f"{k}={task['condition'][k]}"
                               for k in task["required_grounding_fields"]),
            "physics_basis": "ok"}, ensure_ascii=False)
        g = grade_vision(task, good)
        self.assertEqual(g["decision_optimality"], 1.0)
        self.assertAlmostEqual(g["semantic_grounding"], 1.0)
        self.assertTrue(g["physics_ok"])
        bad_cand = next((c for c in task["candidates"]
                         if not c["physics_ok"]), None)
        if bad_cand:
            gb = grade_vision(task, json.dumps({"selected": bad_cand["id"],
                                                "reason": "随便选"}))
            self.assertFalse(gb["physics_ok"])


class TestGuiRunner(unittest.TestCase):
    def test_action_validation(self):
        self.assertIsNone(validate_action("click", {"x": 100, "y": 100}))
        self.assertIsNotNone(validate_action("click", {"x": SCREEN["w"] + 1, "y": 0}))
        self.assertIsNotNone(validate_action("unknown_action", {}))
        self.assertIsNotNone(validate_action("type_text", {"text": 123}))

    def test_non_real_backend_is_not_counted(self):
        task = {"task_id": "g1", "capability": "gui_trajectory",
                "expected_actions": [
                    {"action": "capture", "args": {}},
                    {"action": "click", "args": {"x": 10, "y": 10}}],
                "expected_verification": {
                    "before_volume_mm3": 1000.0, "delta_volume_mm3": -100.0,
                    "after_volume_mm3": 900.0}}
        resp = json.dumps({"reason": "replay", "actions": task["expected_actions"]})
        r = run_task(task, resp, "recorded")
        self.assertFalse(r.evaluation_valid)
        self.assertFalse(r.success)
        self.assertTrue(r.physics_ok)
        self.assertEqual(r.verdict, "not_evaluated_non_real_backend")


class TestMergeGuards(unittest.TestCase):
    """03_merge_local.py 的门禁：这些校验在 import torch 之前触发，无需 GPU 可测。"""

    def _write_adapter(self, d: Path, status: str, lora_r: int = 32,
                       base: str = "Qwen/Qwen3-8B") -> None:
        d.mkdir(parents=True, exist_ok=True)
        (d / "adapter_config.json").write_text("{}", encoding="utf-8")
        (d / "training_receipt.json").write_text(
            json.dumps({"status": status, "lora_r": lora_r, "base": base}),
            encoding="utf-8")

    @staticmethod
    def _run_merge(argv: list) -> None:
        import importlib
        sys.argv = ["03_merge_local"] + argv
        mod = importlib.import_module("03_merge_local")
        mod.main()

    def test_smoke_only_rejected(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        sft = tmp / "sft"
        self._write_adapter(sft, "SMOKE_ONLY")
        with self.assertRaises(SystemExit):
            self._run_merge(['--sft-adapter', str(sft), '--out', str(tmp / 'out')])

    def test_missing_dpo_rejected(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        sft = tmp / "sft"
        self._write_adapter(sft, "COMPLETED")
        with self.assertRaises(SystemExit):
            self._run_merge(['--sft-adapter', str(sft), '--out', str(tmp / 'out')])

    def test_lora_r_mismatch_rejected(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        sft = tmp / "sft"
        dpo = tmp / "dpo"
        self._write_adapter(sft, "COMPLETED", lora_r=16)
        self._write_adapter(dpo, "COMPLETED", lora_r=16)
        with self.assertRaises(SystemExit):
            self._run_merge(['--sft-adapter', str(sft), '--dpo-adapter', str(dpo),
                             '--out', str(tmp / 'out')])


if __name__ == "__main__":
    unittest.main(verbosity=2)
