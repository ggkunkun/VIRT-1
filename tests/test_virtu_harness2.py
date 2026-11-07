from __future__ import annotations
import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""Unit and Integration Tests for Virtu Model Harness 2 Integration.

Verifies:
1. VIRTU_SURFACE specification and 8 editable components.
2. VirtuSubstrate materialization, execution, and trajectory parsing.
3. VirtuHarnessAdapter benchmark tasks and scoring rules.
4. VirtuProposer Propose–Probe–Compose and experience extraction.
5. End-to-end recursion run (run_pipeline).
"""

import json
import tempfile
import unittest
from pathlib import Path

from harness2.core import tree as HT
from harness2.core.spec import ChannelSpec
from virtu_omni.harness2 import (
    VIRTU_SURFACE,
    VIRTU_BENCH_TASKS,
    VirtuHarnessAdapter,
    VirtuProposer,
    VirtuSubstrate,
    build_default_virtu_harness,
)
from scripts.run_virtu_harness2 import run_pipeline


class TestVirtuHarness2(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_surface_and_default_components(self):
        """Test VIRTU_SURFACE definition and default 8 components."""
        self.assertEqual(VIRTU_SURFACE.name, "virtu")
        self.assertIn("systemprompt.md", VIRTU_SURFACE.always_on)
        self.assertIn("guardrails.md", VIRTU_SURFACE.always_on)
        self.assertIn("LongTermMEMORY.md", VIRTU_SURFACE.always_on)
        self.assertIn("tool_descriptions/tool_guidance.md", VIRTU_SURFACE.always_on)

        tree = build_default_virtu_harness()
        self.assertIn("systemprompt.md", tree)
        self.assertIn("guardrails.md", tree)
        self.assertIn("LongTermMEMORY.md", tree)
        self.assertIn("tool_descriptions/tool_guidance.md", tree)
        self.assertIn("hooks.json", tree)
        self.assertIn("scripts/validate_geometry.py", tree)
        self.assertIn("sub_agents/modeler/AGENT.md", tree)
        self.assertIn("skills/cad_cam_feature_tree/SKILL.md", tree)

        # Invariant validations
        self.assertIn("壁厚", tree["guardrails.md"])
        self.assertIn("SS304", tree["LongTermMEMORY.md"])
        self.assertIn("cad.parse_wish_intent", tree["tool_descriptions/tool_guidance.md"])

    def test_02_substrate_materialise_and_execute(self):
        """Test VirtuSubstrate staging and execution."""
        substrate = VirtuSubstrate()
        tree_dir = self.root / "base_tree"
        tree_dir.mkdir(parents=True, exist_ok=True)
        tree = build_default_virtu_harness()
        HT.write_tree(VIRTU_SURFACE, tree, tree_dir, stubs=True)

        install = substrate.materialise(tree_dir, None, {})
        self.assertTrue(install.staging_dir.is_dir())
        self.assertTrue(len(install.fingerprint) > 0)
        self.assertTrue((install.staging_dir / "systemprompt.md").is_file())
        self.assertTrue((install.staging_dir / "harness_manifest.json").is_file())

        # Execute test rollout
        prompt = "我想要一个材质为SS304的回转模具套筒，外径110mm，内孔30mm，总长30mm"
        run_ids = ["run_test_01"]
        out_dirs = substrate.execute(prompt, install, run_ids, timeout=10)
        self.assertEqual(len(out_dirs), 1)
        run_dir = out_dirs[0]

        self.assertTrue((run_dir / "answer.txt").is_file())
        self.assertTrue((run_dir / "trajectory.jsonl").is_file())
        self.assertTrue((run_dir / "execution.meta").is_file())

        answer = (run_dir / "answer.txt").read_text(encoding="utf-8")
        self.assertIn("110.0", answer)
        self.assertIn("30.0", answer)

        # Test trajectory rendering
        traj_text = substrate.read_trajectory(run_dir / "trajectory.jsonl", obs_trunc=200, max_chars=1000)
        self.assertIn("[SYSTEM]", traj_text)
        self.assertIn("[CALL]", traj_text)
        self.assertIn("cad.parse_wish_intent", traj_text)

    def test_03_adapter_tasks_and_scoring(self):
        """Test VirtuHarnessAdapter task loading, domain lookup, and scoring."""
        adapter = VirtuHarnessAdapter(root=self.root / "bench")
        tasks = adapter.tasks()
        self.assertGreaterEqual(len(tasks), 4)
        self.assertIn("cad-sleeve-01", tasks)
        self.assertIn("impeller-ti64-02", tasks)

        self.assertEqual(adapter.domain_of("cad-sleeve-01"), "die_and_mold")
        self.assertEqual(adapter.domain_of("impeller-ti64-02"), "aerospace_cam")

        # Execute and score
        run_dir = adapter.execute("cad-sleeve-01", None, "test_eval_run")
        self.assertTrue(adapter.delivered(run_dir))

        score_res = adapter.score(run_dir, "cad-sleeve-01")
        self.assertIsNotNone(score_res)
        self.assertTrue(score_res["passed"])
        self.assertGreaterEqual(score_res["score"], 0.7)

    def test_04_proposer_phases(self):
        """Test VirtuProposer propose, select, and experience extraction."""
        proposer = VirtuProposer(ChannelSpec("virtu", "virtu-cad-cam-10b"))
        ctx_dir = self.root / "context"
        ctx_dir.mkdir(parents=True, exist_ok=True)
        harness_dir = ctx_dir / "harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        base_dir = ctx_dir / "base_harness"
        base_dir.mkdir(parents=True, exist_ok=True)

        tree = build_default_virtu_harness()
        HT.write_tree(VIRTU_SURFACE, tree, harness_dir, stubs=False)
        HT.write_tree(VIRTU_SURFACE, tree, base_dir, stubs=False)

        # 1. Propose edits
        prop_rep = proposer.call("propose tighter safety guardrails", ctx_dir, "propose.inv1")
        self.assertTrue(prop_rep.ok)
        self.assertIn("<notes>", prop_rep.text)

        # 2. Select winning candidate
        cand_dir = ctx_dir / "candidates"
        cand_dir.mkdir(parents=True, exist_ok=True)
        (cand_dir / "inv1.md").write_text("Passed guardrail validation and swEqnMgr verified", encoding="utf-8")
        sel_rep = proposer.call("select best candidate", ctx_dir, "select.agg1")
        self.assertTrue(sel_rep.ok)
        self.assertIn("```choice\ninv1\n```", sel_rep.text)

        # 3. Experience extraction
        exp_rep = proposer.call("extract experience lessons", ctx_dir, "experience.agg1")
        self.assertTrue(exp_rep.ok)
        self.assertIn("<experience>", exp_rep.text)

    def test_05_end_to_end_pipeline(self):
        """Test running complete Harness 2 sweep across tasks."""
        out_runs = self.root / "pipeline_runs"
        summary = run_pipeline(
            output_dir=out_runs,
            k=1,
            mode="parallel",
            tasks=["cad-sleeve-01", "shaft-cr12mov-04"],
        )
        self.assertEqual(summary["total_tasks"], 2)
        self.assertEqual(summary["passed_tasks"], 2)
        self.assertEqual(summary["pass_rate"], 100.0)

        # Verify reports generated
        rep_md = Path(r"D:\Virtu模型\benchmarks\virtu_harness2_report.md")
        rep_json = Path(r"D:\Virtu模型\benchmarks\virtu_harness2_results.json")
        self.assertTrue(rep_md.is_file())
        self.assertTrue(rep_json.is_file())


if __name__ == "__main__":
    unittest.main()
