"""Unit tests for Claude Code Official Plugins Integration in Virtu Model.

Tests catalog indexing (316 plugins), marketplace search, manifest inspection,
slash command dispatch (/code-review, /feature-dev, /commit), MCP server configs,
and autonomous agent integration.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.claude_plugins import VirtuClaudePlugins, PluginCatalog, PluginRegistry
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory


class TestClaudePluginsIntegration(unittest.TestCase):
    """Test suite for Claude Code official plugins integration."""

    @classmethod
    def setUpClass(cls):
        cls.plugins = VirtuClaudePlugins.get_instance()
        cls.catalog = cls.plugins.catalog
        cls.registry = cls.plugins.registry

    def test_catalog_indexing(self):
        summary = self.catalog.get_summary()
        self.assertGreaterEqual(summary["total_catalog_plugins"], 300)
        self.assertGreaterEqual(summary["locally_installed_plugins"], 40)
        self.assertGreaterEqual(summary["total_slash_commands"], 15)

    def test_marketplace_search(self):
        # Search by keyword
        review_hits = self.plugins.search_marketplace(query="review", limit=5)
        self.assertGreaterEqual(len(review_hits), 1)

        sec_hits = self.plugins.search_marketplace(query="security", limit=5)
        self.assertGreaterEqual(len(sec_hits), 1)

        # Search by tag
        db_hits = self.plugins.search_marketplace(tag="database", limit=5)
        self.assertGreaterEqual(len(db_hits), 1)

    def test_plugin_inspect_manifest(self):
        # Inspect code-review
        info = self.plugins.inspect_plugin("code-review")
        self.assertTrue(info.get("ok"))
        self.assertEqual(info.get("name"), "code-review")
        self.assertEqual(info.get("author"), "Anthropic")
        self.assertGreaterEqual(info.get("command_count"), 1)

        # Inspect feature-dev
        feat_info = self.plugins.inspect_plugin("feature-dev")
        self.assertTrue(feat_info.get("ok"))
        self.assertEqual(feat_info.get("name"), "feature-dev")
        self.assertGreaterEqual(feat_info.get("agent_count"), 2)

    def test_slash_commands_discovery_and_dispatch(self):
        cmds = self.plugins.list_slash_commands()
        self.assertGreaterEqual(len(cmds), 10)
        cmd_names = [c["slash_command"] for c in cmds]
        self.assertIn("/code-review", cmd_names)
        self.assertIn("/feature-dev", cmd_names)

        # Test dispatch
        res = self.plugins.execute_command("/code-review", context="Reviewing PR changes")
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("command"), "/code-review")
        self.assertEqual(res.get("status"), "DISPATCHED")
        self.assertIn("Reviewing PR changes", res.get("context_injected"))

    def test_plugin_install_and_lifecycle(self):
        # Install an external plugin (e.g. asana)
        res = self.plugins.install_plugin("asana")
        self.assertTrue(res.get("ok"))
        self.assertIn("asana", self.registry.enabled_plugins)

        # Disable
        dis_res = self.plugins.disable_plugin("asana")
        self.assertTrue(dis_res.get("ok"))
        self.assertNotIn("asana", self.registry.enabled_plugins)

        # Enable
        en_res = self.plugins.enable_plugin("asana")
        self.assertTrue(en_res.get("ok"))
        self.assertIn("asana", self.registry.enabled_plugins)

    def test_mcp_servers_configuration(self):
        mcps = self.plugins.list_mcp_servers()
        self.assertIn("github", mcps)
        self.assertIn("playwright", mcps)

    def test_skill_writer_claude_plugins_integration(self):
        writer = SkillWriterAndMemory()
        self.assertIsNotNone(writer.claude_plugins)

        search_res = writer.search_marketplace_plugins(query="review", limit=3)
        self.assertGreaterEqual(len(search_res), 1)

        cmd_res = writer.execute_plugin_command("/feature-dev")
        self.assertTrue(cmd_res.get("ok"))
        self.assertEqual(cmd_res.get("command"), "/feature-dev")


if __name__ == "__main__":
    unittest.main()
