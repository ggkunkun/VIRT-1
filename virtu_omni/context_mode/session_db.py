"""Context-Mode Session Database with SQLite FTS5 & BM25 Ranking.

Tracks session events, file modifications, tool receipts, and task milestones.
Preserves session memory across LLM conversation compactions with zero amnesia.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("virtu_omni.context_mode.session_db")

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "memory" / "context_mode_session.db"


@dataclass
class SessionEvent:
    id: Optional[int] = None
    session_id: str = "default_session"
    event_type: str = "tool_receipt"  # tool_receipt, file_edit, task_milestone, error_log
    title: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens_saved: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "tokens_saved": self.tokens_saved,
            "created_at": self.created_at,
        }


class ContextModeSessionDB:
    """SQLite FTS5 backed session continuity database."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Create tables and FTS5 full text index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    tokens_saved INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )

            # Try initializing FTS5 index for BM25 ranking
            try:
                cursor.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS session_events_fts USING fts5(
                        title,
                        content,
                        content='session_events',
                        content_rowid='id'
                    )
                    """
                )
                # Create triggers to sync FTS5
                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS session_events_ai AFTER INSERT ON session_events BEGIN
                        INSERT INTO session_events_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                    END;
                    """
                )
                cursor.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS session_events_ad AFTER DELETE ON session_events BEGIN
                        INSERT INTO session_events_fts(session_events_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
                    END;
                    """
                )
            except Exception as err:
                logger.warning("FTS5 table initialization skipped/fallback: %s", err)

            conn.commit()

    def record_event(
        self,
        event_type: str,
        title: str,
        content: str,
        session_id: str = "default_session",
        metadata: Optional[Dict[str, Any]] = None,
        tokens_saved: int = 0,
    ) -> int:
        """Record an event into the session continuity database."""
        meta_str = json.dumps(metadata or {}, ensure_ascii=False)
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO session_events (session_id, event_type, title, content, metadata_json, tokens_saved, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, event_type, title, content, meta_str, tokens_saved, now),
            )
            event_id = cursor.lastrowid or 0
            conn.commit()
            return event_id

    def search_events(self, query: str, session_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search past session events using FTS5 BM25 or LIKE fallback."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            results = []

            # Try FTS5 MATCH with BM25 ranking
            try:
                # Sanitize query for FTS5
                clean_q = '"' + query.replace('"', '""') + '"'
                if session_id:
                    cursor.execute(
                        """
                        SELECT e.id, e.session_id, e.event_type, e.title, e.content, e.metadata_json, e.tokens_saved, e.created_at,
                               bm25(session_events_fts) AS rank
                        FROM session_events_fts f
                        JOIN session_events e ON f.rowid = e.id
                        WHERE session_events_fts MATCH ? AND e.session_id = ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (clean_q, session_id, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT e.id, e.session_id, e.event_type, e.title, e.content, e.metadata_json, e.tokens_saved, e.created_at,
                               bm25(session_events_fts) AS rank
                        FROM session_events_fts f
                        JOIN session_events e ON f.rowid = e.id
                        WHERE session_events_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (clean_q, limit),
                    )
                rows = cursor.fetchall()
                for r in rows:
                    results.append(
                        {
                            "id": r["id"],
                            "session_id": r["session_id"],
                            "event_type": r["event_type"],
                            "title": r["title"],
                            "content": r["content"],
                            "metadata": json.loads(r["metadata_json"] or "{}"),
                            "tokens_saved": r["tokens_saved"],
                            "score": float(r["rank"]),
                        }
                    )
            except Exception:
                # Fallback to LIKE query
                pattern = f"%{query}%"
                if session_id:
                    cursor.execute(
                        """
                        SELECT id, session_id, event_type, title, content, metadata_json, tokens_saved, created_at
                        FROM session_events
                        WHERE (title LIKE ? OR content LIKE ?) AND session_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (pattern, pattern, session_id, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id, session_id, event_type, title, content, metadata_json, tokens_saved, created_at
                        FROM session_events
                        WHERE title LIKE ? OR content LIKE ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (pattern, pattern, limit),
                    )
                for r in cursor.fetchall():
                    results.append(
                        {
                            "id": r["id"],
                            "session_id": r["session_id"],
                            "event_type": r["event_type"],
                            "title": r["title"],
                            "content": r["content"],
                            "metadata": json.loads(r["metadata_json"] or "{}"),
                            "tokens_saved": r["tokens_saved"],
                            "score": 1.0,
                        }
                    )

            return results

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate total events recorded and tokens saved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total, SUM(tokens_saved) AS tokens FROM session_events")
            row = cursor.fetchone()
            total = row["total"] if row else 0
            tokens = row["tokens"] if row and row["tokens"] else 0

            cursor.execute("SELECT event_type, COUNT(*) AS cnt FROM session_events GROUP BY event_type")
            breakdown = {r["event_type"]: r["cnt"] for r in cursor.fetchall()}

            return {
                "total_events": total,
                "total_tokens_saved": tokens,
                "event_type_breakdown": breakdown,
            }
