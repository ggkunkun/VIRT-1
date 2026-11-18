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
import secrets
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.memory import VirtuHindsightMemory, MemoryType
from virtu_omni.agent import agent_team
from scripts import workbuddy_virtu_bridge as bridge


class TestHindsightIntegration(unittest.TestCase):
    """Test suite for Virtu Hindsight Memory integration."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = Path(temp_dir.name)
        memory_env = patch.dict(os.environ, {
            "VIRTU_MEMORY_PATH": str(self.temp_root / "skill_memory.json"),
            "VIRTU_SKILLS_ROOT": str(self.temp_root / "skills"),
            "HINDSIGHT_API_URL": "",
            "HINDSIGHT_BASE_URL": "",
            "HINDSIGHT_API_KEY": "",
        })
        self.addCleanup(memory_env.stop)
        memory_env.start()
        self.mem = VirtuHindsightMemory(storage_path=self.temp_root / "hindsight.json")
        for memory_patch in (
            patch.object(bridge, "hindsight_memory", self.mem),
            patch.object(agent_team, "VirtuHindsightMemory", return_value=self.mem),
        ):
            self.addCleanup(memory_patch.stop)
            memory_patch.start()

    def _start_bridge(self):
        self.test_token = secrets.token_urlsafe(32)
        token_patch = patch.object(bridge, "_BRIDGE_TOKEN", self.test_token)
        self.addCleanup(token_patch.stop)
        token_patch.start()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.server = bridge.ThreadingServer(("127.0.0.1", 0), bridge.OpenAIBaseHandler)
        self.addCleanup(self.server.server_close)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self.server_thread.start()
        self.addCleanup(self._stop_server)

    def _stop_server(self):
        self.server.shutdown()
        self.server_thread.join(timeout=5)
        self.assertFalse(self.server_thread.is_alive(), "Test bridge thread did not stop")

    def _open(self, request, *, authenticate=True):
        self.assertTrue(request.full_url.startswith(f"{self.base_url}/"))
        if authenticate:
            # Do not forward the test credential if a response redirects elsewhere.
            request.add_unredirected_header("Authorization", f"Bearer {self.test_token}")
        return self.opener.open(request, timeout=10)

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
        agent = agent_team.EvolutionAndMemoryAgent()
        # Verify Hindsight instance is attached
        self.assertTrue(hasattr(agent, "hindsight"))
        self.assertIs(agent.hindsight, self.mem)

        # Verify recall & reflect
        context = agent.retrieve_context("AL7075 铝合金精密轴套车削")
        self.assertIsInstance(context, list)

        reflection = agent.reflect_on_intent("AL7075 铝合金精密轴套车削")
        self.assertEqual(reflection["status"], "reflected")

    def _post(self, path, payload, *, authenticate=True):
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return self._open(req, authenticate=authenticate)

    def test_bridge_hindsight_requires_authentication(self):
        """Missing and invalid credentials must still fail for GET and POST."""
        self._start_bridge()
        for path, payload in (("/v1/hindsight/status", None), ("/v1/hindsight/retain", b"{}")):
            for authorization in (None, f"Bearer {self.test_token}-invalid"):
                with self.subTest(path=path, credentials="missing" if authorization is None else "invalid"):
                    headers = {"Content-Type": "application/json"}
                    if authorization is not None:
                        headers["Authorization"] = authorization
                    req = urllib.request.Request(f"{self.base_url}{path}", data=payload, headers=headers)
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        with self._open(req, authenticate=False):
                            pass
                    with caught.exception as response:
                        self.assertEqual(response.code, 401)

    def test_bridge_hindsight_endpoints(self):
        """Verify bridge HTTP endpoints /v1/hindsight/*."""
        self._start_bridge()

        with self._open(urllib.request.Request(f"{self.base_url}/v1/hindsight/status")) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "active")
            self.assertIn("banks", data)

        with self._post("/v1/hindsight/retain", {
            "bank_id": "virtu_cad_cam",
            "content": "API Bridge Test Retain Content",
            "context": "testing",
            "tags": ["api_test"],
        }) as resp:
            self.assertEqual(json.loads(resp.read().decode("utf-8"))["status"], "retained")

        with self._post("/v1/hindsight/recall", {
            "bank_id": "virtu_cad_cam",
            "query": "API Bridge Test",
            "max_results": 2,
        }) as resp:
            rec_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(rec_data["status"], "recalled")
            self.assertGreaterEqual(rec_data["count"], 1)

        with self._post("/v1/hindsight/reflect", {
            "bank_id": "virtu_cad_cam",
            "query": "API Bridge Test",
        }) as resp:
            self.assertEqual(json.loads(resp.read().decode("utf-8"))["status"], "reflected")

        # The bridge must have written to the temporary bank, not the user's store.
        self.assertTrue(any("API Bridge Test" in u["content"]
                            for u in self.mem.banks["virtu_cad_cam"]["units"].values()))


if __name__ == "__main__":
    unittest.main()
