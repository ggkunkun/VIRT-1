# -*- coding: utf-8 -*-
"""Unit & Integration Tests for Virtu Super Agent Operator Optimization Engine.

Verifies:
1. VirtuOperatorOptimizer bottleneck diagnostics.
2. Micro-benchmarking with numerical equivalence validation (max_diff <= tolerance).
3. Full self-optimization cycle across all 4 core operators (VirtuAttention, UniRoPE, VirtuSwiGLU, VirtuRMSNorm).
4. Provenance report exportation (Markdown & JSON) conforming to Measurement Constitution.
5. VirtuSuperAgent integration: facet_optimize_operators, run_operator_self_optimization, and Hindsight Memory persistence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch

from virtu_omni.agent.super_agent import VirtuSuperAgent
from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import (
    LoopTransformerBlock,
    UniRoPE,
    VirtuAttention,
    VirtuRMSNorm,
    VirtuSwiGLU,
)
from virtu_omni.models.operator_optimizer import (
    OperatorOptimizationReport,
    VirtuOperatorOptimizer,
)


class TestOperatorOptimization(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.optimizer = VirtuOperatorOptimizer(workspace_root=self.root)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_diagnostics(self):
        """Test autonomous bottleneck diagnosis across operators."""
        diags = self.optimizer.diagnose_bottlenecks()
        self.assertGreaterEqual(len(diags), 4)
        ops = [d["operator"] for d in diags]
        self.assertIn("VirtuAttention", ops)
        self.assertIn("UniRoPE", ops)
        self.assertIn("VirtuSwiGLU", ops)
        self.assertIn("VirtuRMSNorm", ops)
        for d in diags:
            self.assertIn("bottleneck_type", d)
            self.assertIn("action", d)

    def test_02_attention_equivalence_and_speedup(self):
        """Test VirtuAttention SDPA vs manual forward numerical equivalence."""
        cfg = ModelConfig(
            hidden_dim=256,
            intermediate_dim=512,
            num_attention_heads=4,
            num_kv_heads=2,
            head_dim=64,
        )
        attn = VirtuAttention(cfg).to(device=self.device)
        attn.eval()
        rope = UniRoPE(dim=64).to(device=self.device)

        batch_size, seq_len = 2, 128
        x = torch.randn(batch_size, seq_len, 256, device=self.device)

        def manual_fwd(x_in):
            return attn._forward_manual(x_in, rope_engine=rope)

        def opt_fwd(x_in):
            return attn.forward(x_in, rope_engine=rope)

        res = self.optimizer.benchmark_operator_pair(
            "VirtuAttention",
            manual_fwd,
            opt_fwd,
            (x,),
            num_warmup=5,
            num_trials=10,
            tolerance=2e-4,
        )
        self.assertTrue(res["precision_pass"])
        self.assertLess(res["max_diff"], 2e-4)
        self.assertGreater(res["speedup"], 0.0)

    def test_03_rope_cache_equivalence(self):
        """Test UniRoPE dynamic cache vs unoptimized recomputation."""
        dim = 64
        rope = UniRoPE(dim=dim).to(device=self.device)
        batch_size, seq_len, num_heads = 2, 64, 4
        q = torch.randn(batch_size, seq_len, num_heads, dim, device=self.device)
        k = torch.randn(batch_size, seq_len, 2, dim, device=self.device)
        pos = torch.arange(seq_len, device=self.device)

        def base_rope(q_in, k_in, p_in):
            return rope._apply_1d_rope_unopt(q_in, k_in, p_in)

        def opt_rope(q_in, k_in, p_in):
            return rope.apply_1d_rope(q_in, k_in, p_in)

        res = self.optimizer.benchmark_operator_pair(
            "UniRoPE",
            base_rope,
            opt_rope,
            (q, k, pos),
            num_warmup=5,
            num_trials=10,
            tolerance=1e-5,
        )
        self.assertTrue(res["precision_pass"])
        self.assertLess(res["max_diff"], 1e-5)

    def test_04_swiglu_inplace_fusion_equivalence(self):
        """Test VirtuSwiGLU in-place fusion equivalence."""
        cfg = ModelConfig(hidden_dim=256, intermediate_dim=512)
        mlp = VirtuSwiGLU(cfg).to(device=self.device)
        mlp.eval()
        x = torch.randn(2, 64, 256, device=self.device)

        def base_swiglu(x_in):
            return mlp._forward_unopt(x_in)

        def opt_swiglu(x_in):
            return mlp.forward(x_in)

        res = self.optimizer.benchmark_operator_pair(
            "VirtuSwiGLU",
            base_swiglu,
            opt_swiglu,
            (x,),
            num_warmup=5,
            num_trials=10,
            tolerance=1e-5,
        )
        self.assertTrue(res["precision_pass"])
        self.assertLess(res["max_diff"], 1e-5)

    def test_05_rmsnorm_equivalence(self):
        """Test VirtuRMSNorm numerical equivalence."""
        norm = VirtuRMSNorm(256).to(device=self.device)
        norm.eval()
        x = torch.randn(2, 64, 256, device=self.device)

        def base_norm(x_in):
            return norm._forward_unopt(x_in)

        def opt_norm(x_in):
            return norm.forward(x_in)

        res = self.optimizer.benchmark_operator_pair(
            "VirtuRMSNorm",
            base_norm,
            opt_norm,
            (x,),
            num_warmup=5,
            num_trials=10,
            tolerance=1e-5,
        )
        self.assertTrue(res["precision_pass"])
        self.assertLess(res["max_diff"], 1e-5)

    def test_06_full_optimization_cycle_and_export(self):
        """Test complete optimization pipeline and report generation."""
        report = self.optimizer.run_full_optimization_cycle(
            batch_size=2,
            seq_lens=[64, 128],
            hidden_dim=128,
            num_heads=4,
            num_kv_heads=2,
            head_dim=32,
            num_warmup=3,
            num_trials=5,
        )
        self.assertIsInstance(report, OperatorOptimizationReport)
        self.assertTrue(report.all_invariants_passed)
        self.assertGreater(report.overall_speedup, 0.0)
        self.assertEqual(len(report.operator_benchmarks), 8)  # 4 ops * 2 seq_lens

        json_path, md_path = self.optimizer.export_report(report, out_dir=self.root / "benchmarks")
        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())

        loaded_json = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded_json["run_id"], report.run_id)
        self.assertTrue(loaded_json["all_invariants_passed"])

    def test_07_agent_self_optimization_integration(self):
        """Test VirtuSuperAgent autonomously invoking operator optimization and retaining memory."""
        agent = VirtuSuperAgent()
        res = agent.run_operator_self_optimization(seq_lens=[64], num_warmup=3, num_trials=5)

        self.assertTrue(
            res["success"],
            f"算子自优化未通过：invalidated_legs={res.get('invalidated_legs')} "
            f"precision_failures={res.get('precision_failures')}",
        )
        self.assertIn("overall_speedup", res)
        self.assertIn("memory_reduction_pct", res)
        self.assertTrue(Path(res["report_md"]).exists())
        self.assertTrue(Path(res["report_json"]).exists())

        # Verify tool registry
        self.assertIn("optimize_operators", agent.tools)
        tool_res = agent.call_tool("optimize_operators", {"seq_lens": [64], "num_warmup": 2, "num_trials": 3})
        self.assertTrue(tool_res["success"])


if __name__ == "__main__":
    unittest.main()
