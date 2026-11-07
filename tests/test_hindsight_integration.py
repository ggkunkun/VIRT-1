"""Unit Tests for Virtu Model x Hindsight Memory Architecture Integration.

Verifies:
1. Hindsight initialization, bank creation, and bank listing.
2. Multi-tiered retention across the 4 memory types (world_facts, agent_experiences, entity_summaries, mental_models).
3. Hybrid semantic + lexical recall.
4. Cross-session reflection and directive synthesis.
5. Multi-Agent Team (EvolutionAndMemoryAgent) Hindsight integration.
6. WorkBuddy Bridge REST API endpoints (/v1/hindsight/*).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.memory import VirtuHindsightMemory, MemoryType
from virtu_omni.agent.agent_team import EvolutionAndMemoryAgent, IndustrialAgentTeam
from scripts.workbuddy_virtu_bridge import ThreadingServer, OpenAIBaseHandler


class TestHindsightIntegration(unittest.TestCase):
    """Test suite for Virtu Hindsight Memory integration."""

    def setUp(self):
        self.temp_storage = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.temp_storage.close()
        self.mem = VirtuHindsightMemory(storage_path=self.temp_storage.name)

    def tearDown(self):
        if os.path.exists(self.temp_storage.name):
            try:
                os.unlink(self.temp_storage.name)
            except Exception:
                pass

    def test_hindsight_initialization_and_banks(self):
        """Verify banks initialization and creation."""
        status = self.mem.get_status()
        self.assertEqual(status["framework"], "Vectorize Hindsight (arXiv:2512.12818)")
        self.assertGreaterEqual(status["total_banks"], 4)

        bank_ids = [b["bank_id"] for b in status["banks"]]
        self.assertIn("default", bank_ids)
        self.assertIn("virtu_cad_cam", bank_ids)
        self.assertIn("virtu_cnc_machining", bank_ids)
        self.assertIn("virtu_quality_audit", bank_ids)

        # Create new custom bank
        res = self.mem.create_bank("custom_mold_bank", "Plastic injection tooling bank")
        self.assertEqual(res["status"], "created")
        self.assertEqual(res["bank_id"], "custom_mold_bank")

    def test_hindsight_retain_four_memory_types(self):
        """Verify retaining across 4 distinct memory types."""
        types_to_test = [
            (MemoryType.WORLD_FACTS, "AL7075-T6 屈服强度 503MPa 密度 2.81g/cm3"),
            (MemoryType.AGENT_EXPERIENCES, "执行端面铣削仿真，切深 2.0mm，走刀平稳无振刀"),
            (MemoryType.ENTITY_SUMMARIES, "SOLIDWORKS 2021 是具备全局参数化方程式控制的 CAD 平台"),
            (MemoryType.MENTAL_MODELS, "粗车前必须先用 G00 定位至安全高度 Z5.0 以上并开启切削液 M08"),
        ]

        for m_type, content in types_to_test:
            res = self.mem.retain(
                bank_id="virtu_cad_cam",
                content=content,
                context="testing",
                tags=["unit_test"],
                memory_type=m_type,
            )
            self.assertEqual(res["status"], "retained")
            self.assertEqual(res["memory_type"], m_type)
            self.assertIn(res["id"], self.mem.banks["virtu_cad_cam"]["units"])

    def test_hindsight_recall_hybrid_scoring(self):
        """Verify multi-channel hybrid recall retrieves most relevant entry."""
        self.mem.retain(
            bank_id="virtu_cad_cam",
            content="SOLIDWORKS EquationMgr 变量命名必须用英文字符并正确转义双引号",
            context="learnings",
            tags=["solidworks", "equations"],
            memory_type=MemoryType.MENTAL_MODELS,
        )
        self.mem.retain(
            bank_id="virtu_cad_cam",
            content="AutoCAD 2026 AutoLISP 绘制回转轴截面与中心对称线",
            context="autocad",
            tags=["autocad", "lisp"],
            memory_type=MemoryType.AGENT_EXPERIENCES,
        )

        hits = self.mem.recall(bank_id="virtu_cad_cam", query="SOLIDWORKS 方程式 双引号", max_results=2)
        self.assertGreater(len(hits), 0)
        top = hits[0]
        self.assertIn("SOLIDWORKS", top["content"])
        self.assertGreater(top["score"], 0.1)

    def test_hindsight_reflect_synthesis(self):
        """Verify reflection synthesizes directives from historical memories."""
        self.mem.retain(
            bank_id="virtu_cnc_machining",
            content="Ti-6Al-4V 钛合金切速高于 60 m/min 会导致刀具急剧磨损，切削液压力必须大于 1.5MPa",
            context="learnings",
            tags=["ti6al4v", "tool_wear"],
            memory_type=MemoryType.MENTAL_MODELS,
        )

        reflected = self.mem.reflect(
            bank_id="virtu_cnc_machining",
            query="钛合金切速设定准则",
            budget="high",
        )
        self.assertEqual(reflected["status"], "reflected")
        self.assertIn("synthesis", reflected)
        self.assertIsInstance(reflected["directives"], list)

    def test_agent_team_hindsight_integration(self):
        """Verify EvolutionAndMemoryAgent and IndustrialAgentTeam interact with Hindsight."""
        agent = EvolutionAndMemoryAgent()
        # Verify Hindsight instance is attached
        self.assertTrue(hasattr(agent, "hindsight"))
        self.assertIsInstance(agent.hindsight, VirtuHindsightMemory)

        # Verify recall & reflect
        context = agent.retrieve_context("AL7075 铝合金精密轴套车削")
        self.assertIsInstance(context, list)

        reflection = agent.reflect_on_intent("AL7075 铝合金精密轴套车削")
        self.assertEqual(reflection["status"], "reflected")

    def test_bridge_hindsight_endpoints(self):
        """Verify bridge HTTP endpoints /v1/hindsight/*."""
        test_port = 8011
        server = ThreadingServer(("127.0.0.1", test_port), OpenAIBaseHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.4)

        try:
            # 1. GET /v1/hindsight/status
            with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/v1/hindsight/status") as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "active")
                self.assertIn("banks", data)

            # 2. POST /v1/hindsight/retain
            retain_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/v1/hindsight/retain",
                data=json.dumps({
                    "bank_id": "virtu_cad_cam",
                    "content": "API Bridge Test Retain Content",
                    "context": "testing",
                    "tags": ["api_test"],
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(retain_req) as resp:
                ret_data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(ret_data["status"], "retained")

            # 3. POST /v1/hindsight/recall
            recall_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/v1/hindsight/recall",
                data=json.dumps({
                    "bank_id": "virtu_cad_cam",
                    "query": "API Bridge Test",
                    "max_results": 2,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(recall_req) as resp:
                rec_data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(rec_data["status"], "recalled")
                self.assertGreaterEqual(rec_data["count"], 1)

            # 4. POST /v1/hindsight/reflect
            reflect_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/v1/hindsight/reflect",
                data=json.dumps({
                    "bank_id": "virtu_cad_cam",
                    "query": "API Bridge Test",
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(reflect_req) as resp:
                ref_data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(ref_data["status"], "reflected")

        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
