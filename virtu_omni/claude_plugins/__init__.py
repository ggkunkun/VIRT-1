"""Virtu Omni x Claude Code Official Plugins.

Comprehensive catalog indexing (315 entries), local Anthropic plugins,
external partner integrations, slash command dispatch, and MCP servers.
"""

from virtu_omni.claude_plugins.adapter import VirtuClaudePlugins
from virtu_omni.claude_plugins.catalog import PluginCatalog, PluginManifest
from virtu_omni.claude_plugins.registry import PluginRegistry

__all__ = [
    "VirtuClaudePlugins",
    "PluginCatalog",
    "PluginRegistry",
    "PluginManifest",
]
