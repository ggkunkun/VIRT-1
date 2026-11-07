"""Virtu Context Mode Adapter.

Unifies sandboxed execution filtering with SQLite FTS5 session continuity.
Provides the primary interface for Virtu agents, Harness 2, and the Bridge server.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from virtu_omni.context_mode.optimizer import ContextModeOptimizer, OptimizationResult
from virtu_omni.context_mode.session_db import ContextModeSessionDB

logger = logging.getLogger("virtu_omni.context_mode.adapter")


class VirtuContextMode:
    """Master adapter for Context Mode optimization inside Virtu Foundation Model."""

    _instance: Optional[VirtuContextMode] = None

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.optimizer = ContextModeOptimizer()
        self.session_db = ContextModeSessionDB(db_path=db_path)

    @classmethod
    def get_instance(cls, db_path: Optional[Path | str] = None) -> VirtuContextMode:
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    def execute(
        self,
        command: str,
        filter_script: Optional[str] = None,
        timeout_sec: float = 30.0,
        record_to_session: bool = True,
    ) -> Dict[str, Any]:
        """Execute command in sandboxed subprocess with context compression."""
        res = self.optimizer.execute_sandboxed(command=command, filter_script=filter_script, timeout_sec=timeout_sec)

        # Estimate tokens saved
        tokens_saved = int(max(0, res.raw_bytes - res.filtered_bytes) / 4.0)

        if record_to_session and res.ok:
            self.session_db.record_event(
                event_type="command_execution",
                title=f"CMD: {command[:60]}",
                content=res.output[:500],
                tokens_saved=tokens_saved,
                metadata={"command": command, "filter": res.filter_applied},
            )

        return res.to_dict()

    def execute_file(
        self,
        filepath: Path | str,
        filter_script: Optional[str] = None,
        record_to_session: bool = True,
    ) -> Dict[str, Any]:
        """Filter and process a large file out of core context."""
        res = self.optimizer.filter_file(filepath=filepath, filter_script=filter_script)

        tokens_saved = int(max(0, res.raw_bytes - res.filtered_bytes) / 4.0)
        if record_to_session and res.ok:
            self.session_db.record_event(
                event_type="file_filter",
                title=f"FILE: {Path(filepath).name}",
                content=res.output[:500],
                tokens_saved=tokens_saved,
                metadata={"filepath": str(filepath), "filter": res.filter_applied},
            )

        return res.to_dict()

    def record_session_event(
        self,
        event_type: str,
        title: str,
        content: str,
        session_id: str = "default_session",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Store critical milestones or file modifications in session continuity DB."""
        return self.session_db.record_event(
            event_type=event_type,
            title=title,
            content=content,
            session_id=session_id,
            metadata=metadata,
        )

    def search_session(self, query: str, session_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve past session events using FTS5 and BM25 ranking."""
        return self.session_db.search_events(query=query, session_id=session_id, limit=limit)

    def get_dashboard(self) -> Dict[str, Any]:
        """Return combined metrics on token savings and session events."""
        savings = self.optimizer.get_savings_metrics()
        db_stats = self.session_db.get_stats()
        return {
            "name": "context-mode",
            "status": "active",
            "savings_telemetry": savings,
            "session_continuity_db": db_stats,
        }

    def run_doctor(self) -> Dict[str, Any]:
        """Diagnose system health and database integrity."""
        db_ok = False
        try:
            with self.session_db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                db_ok = cursor.fetchone()[0] == 1
        except Exception:
            db_ok = False

        return {
            "healthy": db_ok,
            "session_db_path": str(self.session_db.db_path),
            "session_db_connected": db_ok,
            "optimizer_ready": True,
            "fts5_enabled": True,
        }
