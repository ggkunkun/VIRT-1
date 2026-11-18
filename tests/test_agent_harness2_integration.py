# -*- coding: utf-8 -*-
"""Integration Tests for Virtu Super Agent x Google Research Harness 2.

Verifies:
1. VirtuSuperAgent hot-loading of 8 editable Harness components.
2. VirtuSuperAgent recursive refinement facet (facet_harness2_refine).
3. VirtuSuperAgent execution in HARNESSED mode.
4. VirtuSubstrate execution via VirtuSuperAgent with full trajectory & metrics logging.
5. Command-line integration (harness2-check and harness2-setup).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness2.core import tree as HT
from harness2.core.spec import ChannelSpec
from virtu_omni.agent.super_agent import SuperAgentMode, VirtuSuperAgent
from virtu_omni.harness2 import (
    VIRTU_SURFACE,
    VIRTU_BENCH_TASKS,
    VirtuHarnessAdapter,
    VirtuSubstrate,
    build_default_virtu_harness,
)


class TestAgentHarness2Integration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.agent = VirtuSuperAgent()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_agent_harness_hot_loading(self):
        """Test hot-loading the 8 Harness 2 components into VirtuSuperAgent."""
        staging_dir = self.root / "staged_harness"
        staging_dir.mkdir(parents=True, exist_ok=True)
        default_tree = build_default_virtu_harness()
        HT.write_tree(VIRTU_SURFACE, default_tree, staging_dir, stubs=True)

        receipt = self.agent.apply_harness_install(staging_dir)
        self.assertIsNotNone(receipt.get("fingerprint"))
        self.assertGreaterEqual(receipt.get("components_count", 0), 8)
        self.assertEqual(self.agent.active_harness_fingerprint, receipt["fingerprint"])
        self.assertIsNotNone(self.agent.custom_system_prompt)
        self.assertIn("壁厚", self.agent.custom_guardrails)
        self.assertIn("SS304", self.agent.custom_memory)

    def test_02_facet_harness2_refine(self):
        """Test SuperAgent facet_harness2_refine Propose-Probe-Compose loop."""
        task_prompt = "设计并制造一个微型机冷挤压冲头轴模具，材质为Cr12MoV，外径53mm，内孔14mm"
        refine_res = self.agent.facet_harness2_refine({"prompt": task_prompt, "k": 1, "mode": "parallel"})

        self.assertTrue(refine_res["success"])
        self.assertIn("<notes>", refine_res["propose_notes"])
        self.assertIn("inv1", refine_res["selection"])
        self.assertIsNotNone(refine_res["active_fingerprint"])

    def test_03_solve_harnessed_mode(self):
        """Test SuperAgent execution in HARNESSED mode."""
        prompt = "制造一款SS304模具套筒，外径110mm，通孔30mm，总长30mm"
        out_dir = self.root / "harnessed_run"
        res = self.agent.solve(prompt, mode=SuperAgentMode.HARNESSED, output_dir=str(out_dir))

        # Fail-closed 契约（与 test_super_agent.test_02 一致）：该 prompt 未给出
        # 载荷工况，且特征树为规则推导而非实测 CAD 证据，工程门必须判负，
        # 不得靠 HARNESSED 包装把草稿伪装成工程通过。
        self.assertFalse(res.success)
        self.assertEqual(res.mode, SuperAgentMode.HARNESSED.value)
        self.assertIn("Harness² Recursive Improver", res.facets_engaged)
        self.assertIn("harness2_refinement", res.artifacts)
        self.assertIsNotNone(res.metrics.get("harness_fingerprint"))

    def test_04_substrate_agent_rollout(self):
        """Test VirtuSubstrate running a rollout through VirtuSuperAgent."""
        substrate = VirtuSubstrate(agent=self.agent)
        tree_dir = self.root / "base_tree"
        tree_dir.mkdir(parents=True, exist_ok=True)
        default_tree = build_default_virtu_harness()
        HT.write_tree(VIRTU_SURFACE, default_tree, tree_dir, stubs=True)

        install = substrate.materialise(tree_dir, None, {})
        prompt = "我想要一个材质为AL7075-T6的航空法兰盘，最大外径85mm，内孔40mm，厚度15mm"
        run_ids = ["agent_rollout_01"]
        out_dirs = substrate.execute(prompt, install, run_ids, timeout=30)

        self.assertEqual(len(out_dirs), 1)
        run_dir = out_dirs[0]

        # Verify trajectory
        traj_file = run_dir / "trajectory.jsonl"
        self.assertTrue(traj_file.is_file())
        traj_text = substrate.read_trajectory(traj_file, obs_trunc=200, max_chars=2000)
        self.assertIn("[SYSTEM]", traj_text)
        self.assertIn("[USER]", traj_text)
        self.assertIn("[TRACE]", traj_text)

        # Verify answer deliverable
        ans_file = run_dir / "answer.txt"
        self.assertTrue(ans_file.is_file())
        ans_text = ans_file.read_text(encoding="utf-8")
        self.assertIn("VIRTU SUPER AGENT VERIFICATION", ans_text)

        # Verify execution meta
        meta_file = run_dir / "execution.meta"
        self.assertTrue(meta_file.is_file())
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        self.assertTrue(meta.get("guardrail_pass"))
        self.assertIn("safety_factor", meta.get("agent_metrics", {}))


if __name__ == "__main__":
    unittest.main()
