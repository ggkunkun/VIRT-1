"""Runtime Plugin Registry and Command Dispatcher for Claude Code Plugins.

Manages installed plugins, registers slash commands (/code-review, /feature-dev,
/commit, /new-sdk-app), exposes MCP server configurations, and routes execution.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from virtu_omni.claude_plugins.catalog import PluginCatalog, PluginManifest

logger = logging.getLogger("virtu_omni.claude_plugins.registry")


class PluginRegistry:
    """Manages active Claude Code plugins, commands, and MCP servers."""

    DEFAULT_ENABLED_PLUGINS = [
        "code-review",
        "feature-dev",
        "commit-commands",
        "security-guidance",
        "code-simplifier",
        "code-modernization",
        "project-artifact",
        "mcp-server-dev",
        "skill-creator",
        "github",
        "playwright",
    ]

    def __init__(self, catalog: Optional[PluginCatalog] = None) -> None:
        self.catalog = catalog or PluginCatalog()
        self.enabled_plugins: Set[str] = set()
        self.installed_plugins: Set[str] = set()
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Mark local plugins as installed and activate default essential plugins."""
        for name, manifest in self.catalog.plugins.items():
            if manifest.is_local_installed:
                self.installed_plugins.add(name)

        # Enable defaults if available
        for name in self.DEFAULT_ENABLED_PLUGINS:
            if name in self.installed_plugins:
                self.enabled_plugins.add(name)

    def install(self, plugin_name: str) -> Dict[str, Any]:
        """Install/activate a plugin from the marketplace catalog."""
        clean_name = plugin_name.lower().replace("@claude-plugins-official", "").strip()
        manifest = self.catalog.get_plugin(clean_name)
        if not manifest:
            return {
                "ok": False,
                "error": f"Plugin '{plugin_name}' not found in official catalog.",
            }

        self.installed_plugins.add(manifest.name)
        self.enabled_plugins.add(manifest.name)

        return {
            "ok": True,
            "plugin": manifest.name,
            "version": manifest.version,
            "commands": [c["name"] for c in manifest.commands],
            "mcp_servers": list(manifest.mcp_servers.keys()),
            "agents": [a["name"] for a in manifest.agents],
            "message": f"Plugin '{manifest.name}' successfully activated in Virtu Model.",
        }

    def uninstall(self, plugin_name: str) -> Dict[str, Any]:
        """Deactivate and remove plugin from active registry."""
        clean_name = plugin_name.lower().replace("@claude-plugins-official", "").strip()
        if clean_name in self.enabled_plugins:
            self.enabled_plugins.remove(clean_name)
        if clean_name in self.installed_plugins:
            self.installed_plugins.remove(clean_name)

        return {
            "ok": True,
            "plugin": clean_name,
            "message": f"Plugin '{clean_name}' uninstalled.",
        }

    def enable(self, plugin_name: str) -> Dict[str, Any]:
        """Enable an installed plugin."""
        clean_name = plugin_name.lower().replace("@claude-plugins-official", "").strip()
        manifest = self.catalog.get_plugin(clean_name)
        if not manifest:
            return {"ok": False, "error": f"Plugin '{plugin_name}' not found."}
        self.enabled_plugins.add(manifest.name)
        return {"ok": True, "plugin": manifest.name, "status": "ENABLED"}

    def disable(self, plugin_name: str) -> Dict[str, Any]:
        """Disable an active plugin."""
        clean_name = plugin_name.lower().replace("@claude-plugins-official", "").strip()
        if clean_name in self.enabled_plugins:
            self.enabled_plugins.remove(clean_name)
        return {"ok": True, "plugin": clean_name, "status": "DISABLED"}

    def get_active_commands(self) -> Dict[str, Dict[str, Any]]:
        """Collect all slash commands provided by currently enabled plugins."""
        active_cmds: Dict[str, Dict[str, Any]] = {}
        for p_name in self.enabled_plugins:
            manifest = self.catalog.get_plugin(p_name)
            if not manifest:
                continue
            for cmd in manifest.commands:
                cmd_name = cmd["name"]
                active_cmds[cmd_name] = {
                    "plugin": manifest.name,
                    "slash_command": f"/{cmd_name}",
                    "file_path": cmd["file_path"],
                }
        return active_cmds

    def get_active_mcp_servers(self) -> Dict[str, Any]:
        """Collect all active MCP servers provided by enabled plugins."""
        active_mcps: Dict[str, Any] = {}
        for p_name in self.enabled_plugins:
            manifest = self.catalog.get_plugin(p_name)
            if not manifest:
                continue
            for srv_name, srv_conf in manifest.mcp_servers.items():
                active_mcps[srv_name] = {
                    "plugin": manifest.name,
                    "config": srv_conf,
                }
        return active_mcps

    def dispatch_command(
        self,
        command_name: str,
        context: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute or render instructions for a plugin slash command."""
        cmd_clean = command_name.lstrip("/").strip().lower()
        active_cmds = self.get_active_commands()

        cmd_info = active_cmds.get(cmd_clean)
        if not cmd_info:
            # Check if available in any installed plugin and auto-enable
            for manifest in self.catalog.plugins.values():
                for c in manifest.commands:
                    if c["name"].lower() == cmd_clean:
                        cmd_info = {
                            "plugin": manifest.name,
                            "slash_command": f"/{c['name']}",
                            "file_path": c["file_path"],
                        }
                        self.enabled_plugins.add(manifest.name)
                        break
                if cmd_info:
                    break

        if not cmd_info:
            return {
                "ok": False,
                "command": command_name,
                "error": f"Slash command '{command_name}' is not registered by any active plugin.",
                "available_commands": list(active_cmds.keys())[:20],
            }

        # Load command specification markdown
        cmd_path = Path(cmd_info["file_path"])
        cmd_content = ""
        if cmd_path.is_file():
            try:
                cmd_content = cmd_path.read_text(encoding="utf-8")
            except Exception as e:
                cmd_content = f"# Error reading {cmd_path}: {e}"

        return {
            "ok": True,
            "command": f"/{cmd_clean}",
            "plugin": cmd_info["plugin"],
            "file_path": str(cmd_path),
            "instructions": cmd_content,
            "context_injected": context or "",
            "args": args or {},
            "status": "DISPATCHED",
        }
