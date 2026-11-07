"""Master Adapter for Claude Code Plugins in Virtu Foundation Model.

Unifies catalog search across 315 official marketplace entries, local Anthropic
plugins (/plugins), external partner plugins (/external_plugins), slash command
execution (/code-review, /feature-dev, /commit-commands), and MCP servers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from virtu_omni.claude_plugins.catalog import PluginCatalog, PluginManifest
from virtu_omni.claude_plugins.registry import PluginRegistry

logger = logging.getLogger("virtu_omni.claude_plugins.adapter")


class VirtuClaudePlugins:
    """Master adapter for Claude Code Official Plugins inside Virtu Foundation Model."""

    _instance: Optional[VirtuClaudePlugins] = None

    def __init__(self, repo_root: Optional[Union[Path, str]] = None) -> None:
        self.workspace_root = Path("d:/Virtu模型").resolve()
        if repo_root:
            self.repo_root = Path(repo_root).resolve()
        else:
            self.repo_root = self.workspace_root / "external" / "claude-plugins-official"

        self.catalog = PluginCatalog(repo_root=self.repo_root)
        self.registry = PluginRegistry(catalog=self.catalog)
        self.skill_path = self.workspace_root / "skills" / "claude-plugins" / "SKILL.md"

    @classmethod
    def get_instance(cls, repo_root: Optional[Union[Path, str]] = None) -> VirtuClaudePlugins:
        if cls._instance is None:
            cls._instance = cls(repo_root=repo_root)
        return cls._instance

    def search_marketplace(
        self,
        query: str = "",
        tag: Optional[str] = None,
        official_only: bool = False,
        local_only: bool = False,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Search across official plugin marketplace."""
        return self.catalog.search(
            query=query,
            tag=tag,
            official_only=official_only,
            local_only=local_only,
            limit=limit,
        )

    def list_plugins(
        self,
        tag: Optional[str] = None,
        installed_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List plugins in the catalog with installation and active status."""
        results: List[Dict[str, Any]] = []
        for p in self.catalog.plugins.values():
            if installed_only and not p.is_local_installed:
                continue
            if tag and tag.lower() not in [t.lower() for t in p.tags]:
                continue
            d = p.to_dict()
            d["is_enabled"] = p.name in self.registry.enabled_plugins
            results.append(d)
            if len(results) >= limit:
                break
        return results

    def inspect_plugin(self, name: str) -> Dict[str, Any]:
        """Retrieve complete manifest, slash commands, agents, and MCP servers for a plugin."""
        manifest = self.catalog.get_plugin(name)
        if not manifest:
            return {"ok": False, "error": f"Plugin '{name}' not found in catalog."}
        res = manifest.to_dict()
        res["ok"] = True
        res["is_enabled"] = manifest.name in self.registry.enabled_plugins
        return res

    def install_plugin(self, name: str) -> Dict[str, Any]:
        """Install and activate a plugin in Virtu Model."""
        return self.registry.install(name)

    def enable_plugin(self, name: str) -> Dict[str, Any]:
        """Enable an installed plugin."""
        return self.registry.enable(name)

    def disable_plugin(self, name: str) -> Dict[str, Any]:
        """Disable an active plugin."""
        return self.registry.disable(name)

    def execute_command(
        self,
        command: str,
        context: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatch a plugin slash command (e.g. /code-review, /feature-dev, /commit-commands)."""
        return self.registry.dispatch_command(command_name=command, context=context, args=args)

    def list_slash_commands(self) -> List[Dict[str, Any]]:
        """List all active slash commands across enabled plugins."""
        active = self.registry.get_active_commands()
        return list(active.values())

    def list_mcp_servers(self) -> Dict[str, Any]:
        """List all MCP servers provided by enabled plugins."""
        return self.registry.get_active_mcp_servers()

    def get_status(self) -> Dict[str, Any]:
        """Report catalog status, active commands, and official plugins availability."""
        summary = self.catalog.get_summary()
        active_cmds = self.registry.get_active_commands()
        active_mcps = self.registry.get_active_mcp_servers()

        return {
            "status": "READY",
            "repo_path": str(self.repo_root),
            "marketplace_total": summary["total_catalog_plugins"],
            "locally_installed_plugins": summary["locally_installed_plugins"],
            "enabled_plugins_count": len(self.registry.enabled_plugins),
            "enabled_plugins": sorted(list(self.registry.enabled_plugins)),
            "active_slash_commands_count": len(active_cmds),
            "sample_slash_commands": [f"/{c}" for c in list(active_cmds.keys())[:10]],
            "active_mcp_servers_count": len(active_mcps),
            "active_mcp_servers": list(active_mcps.keys()),
            "skill_installed": self.skill_path.is_file(),
            "skill_path": str(self.skill_path) if self.skill_path.is_file() else None,
        }
