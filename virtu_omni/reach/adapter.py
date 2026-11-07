"""Virtu-Omni Agent-Reach Integration Adapter.

Provides unified, zero-API-fee internet access across 13+ platforms for
Virtu Foundation Models, Harness² Scaffolding, and Multi-Agent Teams.
Grounded in open-source Panniantong/Agent-Reach (v1.6.0):
- Channels: GitHub, Bilibili, YouTube, V2EX, Xueqiu, Reddit, Twitter, Web.
- Operations: search, read (auto-detect url), subtitle, quote, hot.
- Zero paid API keys required; native structured JSON output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))


class VirtuAgentReach:
    """Agent-Reach interface for Virtu Foundation Models and Multi-Agent Teams."""

    def __init__(self, cli_path: Optional[str | Path] = None):
        # Locate agent-reach CLI binary or python module
        if cli_path:
            self.cli_path = str(cli_path)
        else:
            venv_cli = WORKSPACE_DIR / ".venv" / "Scripts" / "agent-reach.exe"
            if venv_cli.exists():
                self.cli_path = str(venv_cli)
            else:
                found = shutil.which("agent-reach")
                self.cli_path = found if found else sys.executable

        self._channels_cache: Optional[List[Dict[str, Any]]] = None

    def _run_cli(self, args: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Execute agent-reach CLI and parse standardized JSON output."""
        if self.cli_path.endswith(".exe"):
            cmd = [self.cli_path] + args
        else:
            # Fallback to python -m agent_reach.cli
            cmd = [sys.executable, "-m", "agent_reach.cli"] + args

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            stdout = res.stdout.strip()
            if stdout:
                try:
                    return json.loads(stdout)
                except json.JSONDecodeError:
                    # In case of mixed output, locate first valid JSON object
                    start = stdout.find("{")
                    end = stdout.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        return json.loads(stdout[start : end + 1])

            return {
                "ok": res.returncode == 0,
                "raw_output": stdout,
                "error": {"code": "CLI_ERROR", "message": res.stderr.strip() or stdout},
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": {"code": "TIMEOUT", "message": f"Command timed out after {timeout}s"}}
        except Exception as e:
            return {"ok": False, "error": {"code": "EXECUTION_EXCEPTION", "message": str(e)}}

    def get_channels(self) -> List[Dict[str, Any]]:
        """List all available reach channels with actions and parameter schemas."""
        if self._channels_cache is not None:
            return self._channels_cache

        res = self._run_cli(["channels"])
        if res.get("ok"):
            self._channels_cache = res.get("channels", [])
            return self._channels_cache

        # Safe fallback channel manifest
        return [
            {"name": "github", "description": "GitHub 仓库与工业代码搜索"},
            {"name": "bilibili", "description": "B站数控机床与CAD教学视频及字幕"},
            {"name": "youtube", "description": "YouTube 工业制造加工视频与字幕"},
            {"name": "web", "description": "全网通用搜索引擎与网页提取"},
            {"name": "v2ex", "description": "V2EX 开发者技术社区问答与主题"},
            {"name": "xueqiu", "description": "雪球金属与工业原材料行情报价"},
            {"name": "reddit", "description": "Reddit CNC 与工程制造子版块"},
        ]

    def read(self, url: str, backend: Optional[str] = None) -> Dict[str, Any]:
        """Universal URL reader: automatically selects matching channel and extracts clean content."""
        args = ["read", url]
        if backend:
            args.extend(["--backend", backend])
        return self._run_cli(args, timeout=30)

    def search(self, channel: str, query: str, limit: int = 5, backend: Optional[str] = None) -> Dict[str, Any]:
        """Search a specific channel (github, bilibili, youtube, web, v2ex, xueqiu, etc.)."""
        args = [channel, "search", query, "--limit", str(limit)]
        if backend:
            args.extend(["--backend", backend])
        return self._run_cli(args, timeout=30)

    def search_industrial_repos(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search GitHub for industrial CAD/CAM/CNC open-source repositories and code."""
        res = self.search("github", query, limit=limit)
        if res.get("ok"):
            return res.get("items", [])
        return []

    def get_community_discussions(self, query: str, channel: str = "v2ex", limit: int = 5) -> List[Dict[str, Any]]:
        """Search developer or engineering community discussions."""
        if channel == "v2ex":
            # For V2EX, can search topics or get hot
            res = self._run_cli(["v2ex", "hot", "--limit", str(limit)])
            if res.get("ok"):
                items = res.get("items", [])
                if query:
                    # Filter items by query keywords
                    q_lower = query.lower()
                    filtered = [it for it in items if q_lower in it.get("title", "").lower() or q_lower in it.get("text", "").lower()]
                    return filtered if filtered else items[:limit]
                return items
        else:
            res = self.search(channel, query, limit=limit)
            if res.get("ok"):
                return res.get("items", [])
        return []

    def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """Query real-time stock or commodity quotes via Xueqiu."""
        res = self._run_cli(["xueqiu", "quote", symbol])
        return res

    def doctor(self) -> Dict[str, Any]:
        """Run system diagnostics for all Agent-Reach channels."""
        return self._run_cli(["doctor"])
