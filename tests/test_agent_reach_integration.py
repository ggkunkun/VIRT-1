"""Unit Tests for Virtu Model x Agent-Reach Integration.

Verifies:
1. VirtuAgentReach channel inspection and discovery.
2. Search across channels (GitHub, V2EX, Web).
3. SkillWriterAndMemory integration with Agent-Reach for technical research.
4. WorkBuddy Bridge REST API endpoints (/v1/reach/channels, /v1/reach/search).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.reach import VirtuAgentReach
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from bridges.bridge_security import ensure_bridge_token
from scripts import workbuddy_virtu_bridge as bridge
from scripts.workbuddy_virtu_bridge import ThreadingServer, OpenAIBaseHandler


class TestAgentReachIntegration(unittest.TestCase):
    """Test suite for Virtu Agent-Reach integration."""

    @classmethod
    def setUpClass(cls):
        cls.reach = VirtuAgentReach()

    def test_reach_channels_and_capabilities(self):
        """Verify channels discovery across platforms."""
        channels = self.reach.get_channels()
        self.assertGreaterEqual(len(channels), 7)
        channel_names = [ch.get("name") for ch in channels]
        self.assertIn("github", channel_names)
        self.assertIn("v2ex", channel_names)
        self.assertIn("web", channel_names)
        self.assertIn("youtube", channel_names)
        self.assertIn("bilibili", channel_names)

    def test_reach_search_repos(self):
        """Verify searching industrial code repositories via Agent-Reach."""
        repos = self.reach.search_industrial_repos("cad-cam", limit=2)
        self.assertIsInstance(repos, list)
        if repos:
            repo = repos[0]
            self.assertIn("title", repo)
            self.assertIn("url", repo)

    def test_reach_community_discussions(self):
        """Verify community discussions extraction (e.g. V2EX)."""
        discussions = self.reach.get_community_discussions("python", channel="v2ex", limit=2)
        self.assertIsInstance(discussions, list)

    def test_skill_writer_search_web_integration(self):
        """Verify SkillWriterAndMemory utilizes Agent-Reach for external queries."""
        curator = SkillWriterAndMemory()
        self.assertIsNotNone(curator.reach)
        self.assertIsInstance(curator.reach, VirtuAgentReach)

        # 用受控的真实分支载荷做 hermetic 验证：旧实现离线时伪造 "Technical
        # Reference" 条目并谎报 SUCCESS，本用例曾依赖那份假证据。现固定 reach.search
        # 返回 ok+items，确定性地走真实 SUCCESS 分支（不依赖 live GitHub / 不依赖伪造）。
        canned = {"ok": True, "backend": "github-api", "items": [
            {"title": "ros/solidworks_urdf_exporter",
             "url": "https://github.com/ros/solidworks_urdf_exporter"}]}
        with patch.object(curator.reach, "search", return_value=canned):
            res = curator.search_web_knowledge("solidworks", channel="github", limit=2)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["query"], "solidworks")
        self.assertIn("findings", res)
        self.assertEqual(res["findings"], canned["items"])
        self.assertEqual(res["backend"], "github-api")

    def test_bridge_reach_endpoints(self):
        """Verify WorkBuddy Bridge REST API endpoints (/v1/reach/*)."""
        # patch.object 而非直接赋值：假 token 不能留在模块全局里，否则后续
        # 「无 token 必须 401」的用例会被它污染（2026-11-13 全量跑实测过一次）
        token_patch = patch.object(bridge, "_BRIDGE_TOKEN", "test-token-" + "x" * 48)
        token_patch.start()
        self.addCleanup(token_patch.stop)
        server = ThreadingServer(("127.0.0.1", 0), OpenAIBaseHandler)
        test_port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.1)

        try:
            token = bridge._BRIDGE_TOKEN or ensure_bridge_token()
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

            # 1. GET /v1/reach/channels
            ch_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/v1/reach/channels",
                headers=headers,
            )
            with urllib.request.urlopen(ch_req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data.get("ok"))
                self.assertGreaterEqual(data.get("count", 0), 7)

            # 2. POST /v1/reach/search
            search_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/v1/reach/search",
                data=json.dumps({
                    "channel": "github",
                    "query": "solidworks",
                    "limit": 2
                }).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(search_req) as resp:
                s_data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("ok", s_data)
                if s_data.get("ok"):
                    self.assertIn("items", s_data)
                else:
                    self.assertIn("error", s_data)

            # 3. POST /v1/reach/read
            read_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/v1/reach/read",
                data=json.dumps({
                    "url": "https://www.v2ex.com/t/1252878"
                }).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(read_req) as resp:
                r_data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("ok", r_data)

        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
