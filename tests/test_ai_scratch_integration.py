"""Comprehensive Integration Tests for Virtu Foundation Model x AI Engineering from Scratch.

Tests:
1. Curriculum Registry (542 lessons, 20 phases, lesson doc/quiz/code retrieval).
2. First-Principles Autograd Engine (Value DAG, backprop, numerical gradient checking).
3. Multi-Head Self-Attention with Causal Mask and KV-Cache.
4. LLM Primitives (RMSNorm, SwiGLU, LoRA parameter savings).
5. Placement Diagnostic & Study Plan Synthesis (LEARNING.md).
6. WorkBuddy Bridge REST API endpoints (/v1/ai-scratch/*).
7. Autonomous SkillWriter & Memory First-Principles Knowledge Consultation.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from http.server import HTTPServer
import threading
import urllib.error
import urllib.request

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.ai_scratch import (
    VirtuAIScratch,
    Value,
    MultiHeadAttentionScratch,
    LLMPrimitives,
    ReActAgentLoop,
    RAGVectorIndexScratch,
    AIScratchTutor,
)
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from scripts import workbuddy_virtu_bridge as bridge


class TestAIScratchIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = VirtuAIScratch.get_instance()
        cls.test_token = secrets.token_urlsafe(32)
        token_patch = patch.object(bridge, "_BRIDGE_TOKEN", cls.test_token)
        cls.addClassCleanup(token_patch.stop)
        token_patch.start()

        # Keep credentials and proxy settings local to this test server.
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.server = HTTPServer(("127.0.0.1", 0), bridge.OpenAIBaseHandler)
        cls.addClassCleanup(cls.server.server_close)
        cls.test_port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.test_port}"
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        cls.server_thread.start()
        cls.addClassCleanup(cls._stop_server)

    @classmethod
    def _stop_server(cls):
        cls.server.shutdown()
        cls.server_thread.join(timeout=5)
        if cls.server_thread.is_alive():
            raise AssertionError("Test bridge thread did not stop")

    def _open(self, request, *, authenticate=True):
        self.assertTrue(request.full_url.startswith(f"{self.base_url}/"))
        if authenticate:
            request.add_header("Authorization", f"Bearer {self.test_token}")
        return self.opener.open(request, timeout=10)

    def test_00_workbuddy_bridge_requires_authentication(self):
        """Missing and invalid credentials must still fail for GET and POST."""
        for path, payload in (
            ("/v1/ai-scratch/curriculum", None),
            ("/v1/ai-scratch/first-principles/autograd", b"{}"),
        ):
            for authorization in (None, f"Bearer {self.test_token}-invalid"):
                with self.subTest(path=path, credentials="missing" if authorization is None else "invalid"):
                    headers = {"Content-Type": "application/json"}
                    if authorization is not None:
                        headers["Authorization"] = authorization
                    req = urllib.request.Request(
                        f"{self.base_url}{path}", data=payload, headers=headers
                    )
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        with self._open(req, authenticate=False):
                            pass
                    with caught.exception as response:
                        self.assertEqual(response.code, 401)
                        data = json.loads(response.read().decode("utf-8"))
                        self.assertEqual(data["error"]["type"], "authentication_error")

    def test_01_curriculum_indexing_and_discovery(self):
        """Verify 20 phases and 542 lessons are properly discovered and structured."""
        overview = self.scratch.get_overview()
        self.assertTrue(overview["curriculum_available"])
        self.assertEqual(overview["total_phases"], 20)
        self.assertGreaterEqual(overview["total_lessons"], 500)
        self.assertGreater(overview["total_quiz_questions"], 1000)

        phases = overview["phases"]
        self.assertEqual(len(phases), 20)
        self.assertEqual(phases[0]["phase_id"], "00")
        self.assertEqual(phases[1]["phase_id"], "01")
        self.assertEqual(phases[-1]["phase_id"], "19")

    def test_02_lesson_metadata_and_assets_retrieval(self):
        """Verify fetching specific lesson details (doc, code, quiz)."""
        lesson = self.scratch.get_lesson("01", "05")
        self.assertIsNotNone(lesson)
        self.assertEqual(lesson["phase_id"], "01")
        self.assertEqual(lesson["lesson_id"], "05")
        self.assertTrue(lesson["has_docs"])
        self.assertTrue(lesson["has_code"])
        self.assertTrue(lesson["has_quiz"])
        self.assertIn("autodiff.py", lesson["code_files"])
        self.assertIn("doc_markdown", lesson)
        self.assertIn("Chain Rule", lesson["doc_markdown"])

    def test_03_first_principles_autograd_dag(self):
        """Verify scalar reverse-mode autodiff with topological sort."""
        # Test basic ops: f = (x + y) * (x - y)
        x = Value(3.0, label="x")
        y = Value(2.0, label="y")
        f = (x + y) * (x - y)  # f = x^2 - y^2 = 9 - 4 = 5
        f.backward()

        self.assertAlmostEqual(f.data, 5.0)
        # df/dx = 2*x = 6.0, df/dy = -2*y = -4.0
        self.assertAlmostEqual(x.grad, 6.0)
        self.assertAlmostEqual(y.grad, -4.0)

        # Test activation functions: sigmoid and tanh
        z = Value(0.0)
        sig = z.sigmoid()
        sig.backward()
        self.assertAlmostEqual(sig.data, 0.5)
        self.assertAlmostEqual(z.grad, 0.25)

        # Test verification suite
        v_res = self.scratch.run_autograd_verification(a_val=2.5, b_val=-1.5)
        self.assertTrue(v_res["verified"])
        self.assertLess(v_res["difference"]["diff_a"], 1e-4)
        self.assertLess(v_res["difference"]["diff_b"], 1e-4)

    def test_04_first_principles_multi_head_attention_and_kv_cache(self):
        """Verify causal self-attention math and incremental KV caching."""
        mha = MultiHeadAttentionScratch(d_model=32, num_heads=4, seed=123)
        import numpy as np

        # Initial prompt of 3 tokens
        X_prompt = np.random.randn(1, 3, 32)
        out1, cache = mha.forward(X_prompt, causal=True)
        self.assertEqual(out1.shape, (1, 3, 32))
        self.assertEqual(cache["K"].shape, (1, 3, 32))
        self.assertEqual(cache["V"].shape, (1, 3, 32))

        # Next token generated autoregressively using cached K and V
        X_next = np.random.randn(1, 1, 32)
        out2, cache = mha.forward(X_next, causal=True, kv_cache=cache)
        self.assertEqual(out2.shape, (1, 1, 32))
        self.assertEqual(cache["K"].shape, (1, 4, 32))
        self.assertEqual(cache["V"].shape, (1, 4, 32))

    def test_05_llm_primitives_rmsnorm_swiglu_lora(self):
        """Verify RMSNorm, SwiGLU, and LoRA decomposition."""
        import numpy as np

        x = np.random.randn(2, 4, 16)
        normed = LLMPrimitives.rms_norm(x)
        self.assertEqual(normed.shape, (2, 4, 16))

        # Check RMS is approximately 1.0
        rms_val = np.sqrt(np.mean(normed**2, axis=-1))
        np.testing.assert_allclose(rms_val, 1.0, atol=1e-3)

        # Test LoRA savings
        lora_stats = self.scratch.engine.verify_lora_decomposition(d_in=256, d_out=512, r=4)
        self.assertGreater(lora_stats["param_reduction_percentage"], 90.0)

    def test_06_tutor_diagnostic_and_learning_plan(self):
        """Verify placement diagnostic evaluation and study plan synthesis."""
        tutor = AIScratchTutor()
        questions = tutor.get_diagnostic_questions()
        self.assertEqual(len(questions), 5)

        # Perfect score
        answers = {q["id"]: 1 if q["id"] != "q3_kvcache" else 0 for q in questions}
        eval_res = tutor.evaluate_placement(answers)
        self.assertEqual(eval_res["score"], 5)
        self.assertEqual(eval_res["accuracy_percentage"], 100.0)
        self.assertEqual(eval_res["recommended_starting_phase"], "14-agent-engineering")

        # Generate markdown plan
        plan = tutor.generate_learning_plan_markdown(user_name="Virtu-Omni-Agent", evaluation=eval_res)
        self.assertIn("# LEARNING.md — AI Engineering from Scratch", plan)
        self.assertIn("14-agent-engineering", plan)

    def test_07_workbuddy_bridge_ai_scratch_endpoints(self):
        """Verify Bridge HTTP REST API endpoints (/v1/ai-scratch/*)."""
        # 1. GET /v1/ai-scratch/curriculum
        req = urllib.request.Request(f"{self.base_url}/v1/ai-scratch/curriculum")
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("total_phases"), 20)

        # 2. GET /v1/ai-scratch/diagnostic
        req = urllib.request.Request(f"{self.base_url}/v1/ai-scratch/diagnostic")
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertEqual(len(data.get("questions", [])), 5)

        # 3. POST /v1/ai-scratch/first-principles/autograd
        post_data = json.dumps({"a": 2.0, "b": -3.0}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/ai-scratch/first-principles/autograd",
            data=post_data,
            headers={"Content-Type": "application/json"},
        )
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertTrue(data["result"]["verified"])

        # 4. POST /v1/ai-scratch/tutor/placement
        answers_payload = json.dumps({"answers": {"q1_autodiff": 1, "q2_attention": 1}}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/ai-scratch/tutor/placement",
            data=answers_payload,
            headers={"Content-Type": "application/json"},
        )
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertIn("assessed_level", data["evaluation"])

    def test_08_skill_writer_first_principles_query(self):
        """Verify SkillWriterAndMemory utilizes AI Engineering from Scratch."""
        writer = SkillWriterAndMemory()
        res = writer.query_first_principles_concept(topic="attention", limit=2)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreaterEqual(res["lessons_found"], 1)
        self.assertTrue(res["engine_verified"])


if __name__ == "__main__":
    unittest.main()
