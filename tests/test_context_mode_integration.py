"""Comprehensive Integration Tests for Virtu Foundation Model x Context-Mode Optimization.

Tests:
1. Context Mode Doctor & SQLite FTS5 Database Health.
2. Sandboxed Subprocess Command Execution & Token Compression (>90%).
3. Custom In-Sandbox Python Script Filtering.
4. Out-of-Context Large File Filtering (ctx_execute_file).
5. Session Continuity & Compaction Survival (FTS5 BM25 Ranking).
6. WorkBuddy Bridge REST API Endpoints (/v1/context-mode/*).
7. Autonomous SkillWriter & Memory Session Continuity Integration.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from http.server import HTTPServer
import threading
import urllib.request

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.context_mode import VirtuContextMode
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from scripts.workbuddy_virtu_bridge import OpenAIBaseHandler


class TestContextModeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context_mode = VirtuContextMode.get_instance()
        # Start Bridge HTTP Server on temporary port
        cls.test_port = 8015
        cls.server = HTTPServer(("127.0.0.1", cls.test_port), OpenAIBaseHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.test_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_01_doctor_and_db_health(self):
        """Verify Context Mode diagnostics and SQLite FTS5 readiness."""
        doc = self.context_mode.run_doctor()
        self.assertTrue(doc["healthy"])
        self.assertTrue(doc["session_db_connected"])
        self.assertTrue(doc["optimizer_ready"])
        self.assertTrue(doc["fts5_enabled"])

    def test_02_sandboxed_command_compression(self):
        """Verify executing heavy commands in sandboxed subprocess with >90% token reduction."""
        cmd = 'python -c "[print(f\'CNC Step {i:04d}: G01 X{i*0.1:.2f} Y{i*0.2:.2f} Z{-i*0.05:.2f}\') for i in range(400)]"'
        res = self.context_mode.execute(cmd)
        self.assertTrue(res["ok"])
        self.assertEqual(res["raw_lines"], 400)
        self.assertLess(res["filtered_lines"], 30)
        self.assertGreater(res["savings_percentage"], 90.0)
        self.assertIn("CONTEXT-MODE COMPRESSION", res["output"])

    def test_03_custom_filter_script_execution(self):
        """Verify running custom Python filter script inside the execution sandbox."""
        cmd = 'python -c "print(\'alpha\'); print(\'TARGET: extraction_value\'); print(\'beta\')"'
        script = "output = '\\n'.join([l for l in lines if 'TARGET:' in l])"
        res = self.context_mode.execute(cmd, filter_script=script)
        self.assertTrue(res["ok"])
        self.assertEqual(res["filter_applied"], "custom_filter_script")
        self.assertEqual(res["output"].strip(), "TARGET: extraction_value")

    def test_04_file_filtering_out_of_context(self):
        """Verify filtering large files without loading entire content into context."""
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
            for i in range(600):
                f.write(f"2026-10-29 17:00:{i%60:02d} [INFO] Routine log entry #{i}\n")
            f.write("2026-10-29 17:01:00 [ERROR] Spindle Overload 115% on Axis A\n")
            tmp_path = f.name

        try:
            res = self.context_mode.execute_file(tmp_path)
            self.assertTrue(res["ok"])
            self.assertEqual(res["raw_lines"], 601)
            self.assertGreater(res["savings_percentage"], 90.0)
            self.assertIn("Spindle Overload", res["output"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_05_session_events_and_bm25_search(self):
        """Verify storing milestones and retrieving via SQLite FTS5 BM25 search."""
        eid = self.context_mode.record_session_event(
            event_type="cad_spec",
            title="Spline Shaft Dimension Specs",
            content="Module 2.5, 18 teeth, pressure angle 20 deg, material 40Cr.",
            metadata={"module": 2.5, "teeth": 18},
        )
        self.assertGreater(eid, 0)

        hits = self.context_mode.search_session(query="Spline Shaft", limit=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Spline Shaft Dimension Specs")
        self.assertIn("40Cr", hits[0]["content"])

    def test_06_workbuddy_bridge_context_mode_endpoints(self):
        """Verify Bridge HTTP REST API endpoints (/v1/context-mode/*)."""
        # 1. GET /v1/context-mode/dashboard
        req = urllib.request.Request(f"{self.base_url}/v1/context-mode/dashboard")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertEqual(data["dashboard"]["status"], "active")

        # 2. GET /v1/context-mode/doctor
        req = urllib.request.Request(f"{self.base_url}/v1/context-mode/doctor")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertTrue(data["doctor"]["healthy"])

        # 3. POST /v1/context-mode/execute
        post_data = json.dumps({"command": "echo Hello from Context Mode"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/context-mode/execute",
            data=post_data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertIn("Hello from Context Mode", data.get("output", ""))

        # 4. POST /v1/context-mode/session/event
        ev_data = json.dumps(
            {
                "event_type": "milestone",
                "title": "REST Bridge Milestone",
                "content": "Verified Bridge Integration",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/context-mode/session/event",
            data=ev_data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertGreater(data.get("event_id", 0), 0)

        # 5. POST /v1/context-mode/session/search
        search_data = json.dumps({"query": "REST Bridge", "limit": 2}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/context-mode/session/search",
            data=search_data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertGreaterEqual(data.get("count", 0), 1)

    def test_07_skill_writer_context_mode_integration(self):
        """Verify SkillWriterAndMemory utilizes Context Mode for command execution and session continuity."""
        writer = SkillWriterAndMemory()
        # Sandboxed command execution
        res = writer.execute_sandboxed_command("echo Sandboxed Output")
        self.assertTrue(res["ok"])
        self.assertIn("Sandboxed Output", res["output"])

        # Session continuity recording & retrieval
        eid = writer.record_session_continuity_event(
            title="Skill Synthesis Milestone",
            content="Synthesized custom lathe parting skill",
        )
        self.assertGreater(eid, 0)

        hits = writer.search_session_continuity("lathe parting", limit=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Skill Synthesis Milestone")


if __name__ == "__main__":
    unittest.main()
