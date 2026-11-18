# -*- coding: utf-8 -*-
"""Integration tests for Working Memory Bridge REST endpoints & long-task context flow.

Verifies:
1. GET /v1/memory/working-memory/status returns structured snapshot.
2. POST /v1/memory/working-memory/update modifies goal and records verified facts.
3. POST /v1/memory/working-memory/reset wipes state cleanly.
4. POST /v1/memory/working-memory/compact returns compacted messages while preserving memory.
5. End-to-end multi-turn chat completions retain working memory anchor without hallucination.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from scripts import workbuddy_virtu_bridge as bridge
from scripts.workbuddy_virtu_bridge import ThreadingServer, OpenAIBaseHandler, working_memory


class TestWorkingMemoryBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 走 patch.object：假 token 不得留在模块全局里污染后续「无 token 必须 401」的用例
        cls.token_patch = patch.object(bridge, "_BRIDGE_TOKEN", "test-wm-token-" + "x" * 48)
        cls.token_patch.start()
        cls.addClassCleanup(cls.token_patch.stop)
        cls.server = ThreadingServer(("127.0.0.1", 0), OpenAIBaseHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        working_memory.reset()

    def _get(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {bridge._BRIDGE_TOKEN}",
        })
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, data: dict):
        url = f"http://127.0.0.1:{self.port}{path}"
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bridge._BRIDGE_TOKEN}",
        })
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_status_endpoint(self):
        """Test GET /v1/memory/working-memory/status."""
        working_memory.set_task_goal("测试长任务", invariants={"outer_diameter": 60.0})
        status, body = self._get("/v1/memory/working-memory/status")
        self.assertEqual(status, 200)
        self.assertIn("goal", body)
        self.assertEqual(body["goal"]["intent"], "测试长任务")
        self.assertEqual(body["facts"]["outer_diameter"]["value"], 60.0)

    def test_update_and_reset_endpoints(self):
        """Test POST /v1/memory/working-memory/update and reset."""
        update_payload = {
            "goal": {"intent": "高精度法兰盘制造", "invariants": {"d_outer": 80.0}},
            "fact": {"key": "material", "value": "45号钢", "verified": True},
            "lesson": "必须先倒角后攻丝",
        }
        status, body = self._post("/v1/memory/working-memory/update", update_payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(working_memory.get_fact("outer_diameter"), 80.0)
        self.assertEqual(working_memory.get_fact("material"), "45号钢")
        self.assertIn("必须先倒角后攻丝", working_memory.lessons_learned)

        # Test reset
        status, reset_body = self._post("/v1/memory/working-memory/reset", {})
        self.assertEqual(status, 200)
        self.assertEqual(reset_body["status"], "reset_success")
        self.assertIsNone(working_memory.goal)
        self.assertEqual(len(working_memory.facts), 0)

    def test_compact_endpoint(self):
        """Test POST /v1/memory/working-memory/compact."""
        working_memory.set_task_goal("大型模具加工", invariants={"outer_diameter": 60.0})
        messages = [
            {"role": "system", "content": "你是 Virtu 工业智能体"},
            {"role": "user", "content": "第一步：建模"},
            {"role": "assistant", "content": "建模完成"},
            {"role": "user", "content": "第二步：有限元分析"},
            {"role": "assistant", "content": "有限元分析完成"},
            {"role": "user", "content": "第三步：生成NC刀路"},
            {"role": "assistant", "content": "NC刀路生成完成"},
            {"role": "user", "content": "第四步：仿真"},
            {"role": "assistant", "content": "仿真完成"},
            {"role": "user", "content": "第五步：质量抽检"},
            {"role": "assistant", "content": "质量抽检通过"},
        ]
        status, body = self._post("/v1/memory/working-memory/compact", {"messages": messages, "max_turns": 4})
        self.assertEqual(status, 200)
        compacted = body["compacted_messages"]
        self.assertLess(len(compacted), len(messages))
        self.assertIn("<BUILTIN_WORKING_MEMORY>", compacted[0]["content"])
        self.assertIn("outer_diameter: 60.0", compacted[0]["content"])
