"""Catalog and Indexing Engine for Claude Plugins Official.

Parses Anthropics official plugin marketplace (315 entries), local /plugins (Anthropic official),
and /external_plugins (verified partner integrations: GitHub, GitLab, Playwright, Firebase, Linear).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("virtu_omni.claude_plugins.catalog")


@dataclass
class PluginManifest:
    """Detailed metadata for a Claude Code plugin."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "Anthropic"
    is_official: bool = True
    is_external: bool = False
    is_local_installed: bool = False
    plugin_dir: Optional[str] = None
    homepage: Optional[str] = None
    commands: List[Dict[str, str]] = field(default_factory=list)
    agents: List[Dict[str, str]] = field(default_factory=list)
    skills: List[Dict[str, str]] = field(default_factory=list)
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "is_official": self.is_official,
            "is_external": self.is_external,
            "is_local_installed": self.is_local_installed,
            "plugin_dir": self.plugin_dir,
            "homepage": self.homepage,
            "command_count": len(self.commands),
            "commands": self.commands,
            "agent_count": len(self.agents),
            "agents": self.agents,
            "skill_count": len(self.skills),
            "skills": self.skills,
            "mcp_server_count": len(self.mcp_servers),
            "mcp_servers": list(self.mcp_servers.keys()),
            "tags": self.tags,
        }


class PluginCatalog:
    """Indexes official Anthropic Claude Code plugins and marketplace metadata."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        if repo_root:
            self.repo_root = Path(repo_root).resolve()
        else:
            self.repo_root = Path("d:/Virtu模型/external/claude-plugins-official").resolve()

        self.marketplace_json_path = self.repo_root / ".claude-plugin" / "marketplace.json"
        self.internal_plugins_dir = self.repo_root / "plugins"
        self.external_plugins_dir = self.repo_root / "external_plugins"

        self.plugins: Dict[str, PluginManifest] = {}
        self.marketplace_entries: List[Dict[str, Any]] = []
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Parse marketplace.json and scan internal and external plugin directories."""
        # 1. Load marketplace.json
        if self.marketplace_json_path.is_file():
            try:
                with open(self.marketplace_json_path, "r", encoding="utf-8") as f:
                    market_data = json.load(f)
                    if isinstance(market_data, dict):
                        self.marketplace_entries = market_data.get("plugins", [])
                    elif isinstance(market_data, list):
                        self.marketplace_entries = market_data
            except Exception as e:
                logger.warning(f"Failed to load marketplace.json: {e}")

        # Index marketplace entries as manifests
        for entry in self.marketplace_entries:
            name = entry.get("name", "")
            if not name:
                continue
            desc = entry.get("description", "")
            ver = entry.get("version", "1.0.0") or "1.0.0"
            author_data = entry.get("author") or {}
            author_name = author_data.get("name", "Unknown") if isinstance(author_data, dict) else str(author_data)

            manifest = PluginManifest(
                name=name,
                version=ver,
                description=desc,
                author=author_name,
                is_official="anthropic" in author_name.lower(),
                is_external=not ("anthropic" in author_name.lower()),
                homepage=entry.get("homepage"),
                tags=self._infer_tags(name, desc),
            )
            self.plugins[name] = manifest

        # 2. Scan internal plugins (/plugins)
        if self.internal_plugins_dir.is_dir():
            for pdir in self.internal_plugins_dir.iterdir():
                if pdir.is_dir():
                    self._ingest_local_plugin(pdir, is_official=True, is_external=False)

        # 3. Scan external plugins (/external_plugins)
        if self.external_plugins_dir.is_dir():
            for pdir in self.external_plugins_dir.iterdir():
                if pdir.is_dir():
                    self._ingest_local_plugin(pdir, is_official=False, is_external=True)

    def _ingest_local_plugin(self, plugin_dir: Path, is_official: bool, is_external: bool) -> None:
        """Scan a local plugin directory for manifests, commands, agents, skills, and MCPs."""
        name = plugin_dir.name
        plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"

        ver = "1.0.0"
        desc = ""
        author = "Anthropic" if is_official else "Partner"

        if plugin_json.is_file():
            try:
                with open(plugin_json, "r", encoding="utf-8") as f:
                    pj = json.load(f)
                    name = pj.get("name", name)
                    ver = pj.get("version", ver)
                    desc = pj.get("description", desc)
                    if "author" in pj and isinstance(pj["author"], dict):
                        author = pj["author"].get("name", author)
            except Exception:
                pass

        # Scan commands (*.md)
        commands: List[Dict[str, str]] = []
        cmd_dir = plugin_dir / "commands"
        if cmd_dir.is_dir():
            for cmd_file in cmd_dir.glob("*.md"):
                cmd_name = cmd_file.stem
                commands.append({
                    "name": cmd_name,
                    "slash_command": f"/{cmd_name}",
                    "file_path": str(cmd_file),
                })

        # Scan agents (*.md)
        agents: List[Dict[str, str]] = []
        agent_dir = plugin_dir / "agents"
        if agent_dir.is_dir():
            for agent_file in agent_dir.glob("*.md"):
                agents.append({
                    "name": agent_file.stem,
                    "file_path": str(agent_file),
                })

        # Scan skills (**/SKILL.md)
        skills: List[Dict[str, str]] = []
        skill_dir = plugin_dir / "skills"
        if skill_dir.is_dir():
            for sk in skill_dir.glob("**/SKILL.md"):
                skills.append({
                    "name": sk.parent.name,
                    "file_path": str(sk),
                })

        # Scan .mcp.json
        mcp_servers: Dict[str, Any] = {}
        mcp_file = plugin_dir / ".mcp.json"
        if mcp_file.is_file():
            try:
                with open(mcp_file, "r", encoding="utf-8") as f:
                    mcp_data = json.load(f)
                    mcp_servers = mcp_data.get("mcpServers", mcp_data)
            except Exception:
                pass

        existing = self.plugins.get(name)
        if existing:
            existing.version = ver or existing.version
            existing.description = desc or existing.description
            existing.author = author or existing.author
            existing.is_official = is_official
            existing.is_external = is_external
            existing.is_local_installed = True
            existing.plugin_dir = str(plugin_dir)
            existing.commands = commands
            existing.agents = agents
            existing.skills = skills
            existing.mcp_servers = mcp_servers
            existing.tags = list(set(existing.tags + self._infer_tags(name, desc)))
        else:
            manifest = PluginManifest(
                name=name,
                version=ver,
                description=desc,
                author=author,
                is_official=is_official,
                is_external=is_external,
                is_local_installed=True,
                plugin_dir=str(plugin_dir),
                commands=commands,
                agents=agents,
                skills=skills,
                mcp_servers=mcp_servers,
                tags=self._infer_tags(name, desc),
            )
            self.plugins[name] = manifest

    @staticmethod
    def _infer_tags(name: str, desc: str) -> List[str]:
        """Categorize plugins by keyword heuristics."""
        tags = set()
        text = f"{name} {desc}".lower()
        if any(w in text for w in ["lsp", "language", "clangd", "pyright", "rust", "gopls", "typescript"]):
            tags.add("lsp")
        if any(w in text for w in ["security", "audit", "sast", "scanning", "vulnerability"]):
            tags.add("security")
        if any(w in text for w in ["github", "gitlab", "pr", "review", "commit", "git"]):
            tags.add("version_control")
        if any(w in text for w in ["database", "sql", "postgres", "alloydb", "airtable"]):
            tags.add("database")
        if any(w in text for w in ["chat", "discord", "telegram", "imessage", "fakechat"]):
            tags.add("messaging")
        if any(w in text for w in ["browser", "playwright", "puppeteer", "web"]):
            tags.add("web_automation")
        if any(w in text for w in ["cloud", "firebase", "aws", "terraform", "aiven"]):
            tags.add("cloud_infra")
        if any(w in text for w in ["math", "proof", "olympiad"]):
            tags.add("mathematics")
        if any(w in text for w in ["mcp", "agent", "sdk", "plugin"]):
            tags.add("agent_developer")
        return list(tags)

    def search(
        self,
        query: str = "",
        tag: Optional[str] = None,
        official_only: bool = False,
        local_only: bool = False,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Search catalog by text query, tag, or installation status."""
        q = query.lower().strip()
        results: List[Dict[str, Any]] = []

        for p in self.plugins.values():
            if official_only and not p.is_official:
                continue
            if local_only and not p.is_local_installed:
                continue
            if tag and tag.lower() not in [t.lower() for t in p.tags]:
                continue

            # Query match
            if q:
                match = (
                    q in p.name.lower()
                    or q in p.description.lower()
                    or any(q in c["name"].lower() for c in p.commands)
                    or any(q in t.lower() for t in p.tags)
                )
                if not match:
                    continue

            results.append(p.to_dict())
            if len(results) >= limit:
                break

        return results

    def get_plugin(self, name: str) -> Optional[PluginManifest]:
        """Get plugin by exact or normalized name."""
        clean_name = name.lower().replace("@claude-plugins-official", "").strip()
        return self.plugins.get(clean_name) or self.plugins.get(name)

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate catalog metrics."""
        local_count = sum(1 for p in self.plugins.values() if p.is_local_installed)
        total_commands = sum(len(p.commands) for p in self.plugins.values())
        total_agents = sum(len(p.agents) for p in self.plugins.values())
        total_mcps = sum(len(p.mcp_servers) for p in self.plugins.values())
        total_skills = sum(len(p.skills) for p in self.plugins.values())

        return {
            "total_catalog_plugins": len(self.plugins),
            "marketplace_entries_indexed": len(self.marketplace_entries),
            "locally_installed_plugins": local_count,
            "total_slash_commands": total_commands,
            "total_subagents": total_agents,
            "total_mcp_servers": total_mcps,
            "total_skills": total_skills,
            "repo_root": str(self.repo_root),
        }
