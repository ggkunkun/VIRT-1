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

import gc
import json
import os
import secrets
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from http.server import HTTPServer
import threading
import urllib.error
import urllib.request

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.context_mode import VirtuContextMode
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from scripts import workbuddy_virtu_bridge as bridge


class TestContextModeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="virtu_context_mode_test_")
        cls.addClassCleanup(cls._cleanup_temp_dir)
        cls.context_mode = VirtuContextMode(db_path=Path(cls.temp_dir.name) / "session.db")
        instance_patch = patch.object(VirtuContextMode, "_instance", cls.context_mode)
        cls.addClassCleanup(instance_patch.stop)
        instance_patch.start()
        # The bridge caches its adapter separately from the singleton.
        context_patch = patch.object(bridge, "context_mode", cls.context_mode)
        cls.addClassCleanup(context_patch.stop)
        context_patch.start()

        cls.test_token = secrets.token_urlsafe(32)
        token_patch = patch.object(bridge, "_BRIDGE_TOKEN", cls.test_token)
        cls.addClassCleanup(token_patch.stop)
        token_patch.start()

        # Keep credentials and proxy settings local to this test server.
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.server = HTTPServer(("127.0.0.1", 0), bridge.OpenAIBaseHandler)
        cls.addClassCleanup(cls.server.server_close)
        cls.test_port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.test_port}"
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        cls.server_thread.start()
        cls.addClassCleanup(cls._stop_server)

    @classmethod
    def _stop_server(cls):
        cls.server.shutdown()
        cls.server_thread.join(timeout=5)
        if cls.server_thread.is_alive():
            raise AssertionError("Test bridge thread did not stop")

    @classmethod
    def _cleanup_temp_dir(cls):
        # SQLite context managers do not close connections. Release their cycles
        # after the server stops, before Windows attempts to delete the database.
        gc.collect()
        cls.temp_dir.cleanup()
        if Path(cls.temp_dir.name).exists():
            raise AssertionError("Temporary context database directory was not removed")

    def _open(self, request, *, authenticate=True):
        self.assertTrue(request.full_url.startswith(f"{self.base_url}/"))
        if authenticate:
            request.add_header("Authorization", f"Bearer {self.test_token}")
        return self.opener.open(request, timeout=10)

    def test_00_workbuddy_bridge_requires_authentication(self):
        """Missing and invalid credentials must still fail for GET and POST."""
        for path, payload in (
            ("/v1/context-mode/dashboard", None),
            ("/v1/context-mode/session/event", b"{}"),
        ):
            for authorization in (None, f"Bearer {self.test_token}-invalid"):
                with self.subTest(path=path, credentials="missing" if authorization is None else "invalid"):
                    headers = {"Content-Type": "application/json"}
                    if authorization is not None:
                        headers["Authorization"] = authorization
                    req = urllib.request.Request(
                        f"{self.base_url}{path}", data=payload, headers=headers
                    )
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        with self._open(req, authenticate=False):
                            pass
                    with caught.exception as response:
                        self.assertEqual(response.code, 401)
                        data = json.loads(response.read().decode("utf-8"))
                        self.assertEqual(data["error"]["type"], "authentication_error")

    def test_00b_rejected_post_body_never_resets_connection(self):
        """POST 带 body + 错误凭据必须稳定回 401，不能因未读请求体触发 RST。

        修复前 ``_require_auth`` 直接回 401 并 close，Windows 内核对带未读数据
        的连接发 RST，客户端拿到 ``ConnectionAbortedError [WinError 10053]``
        而不是 ``HTTPError``。该现象偶发，连续多次才能稳定复现，故循环验证。
        """
        for attempt in range(12):
            with self.subTest(attempt=attempt):
                req = urllib.request.Request(
                    f"{self.base_url}/v1/context-mode/session/event",
                    data=b'{"event":"ping"}',
                    headers={"Content-Type": "application/json",
                             "Authorization": "Bearer invalid-token"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    with self._open(req, authenticate=False):
                        pass
                self.assertEqual(caught.exception.code, 401)

    def test_01_doctor_and_db_health(self):
        """Verify Context Mode diagnostics and SQLite FTS5 readiness."""
        self.assertIs(VirtuContextMode.get_instance(), self.context_mode)
        self.assertIs(bridge.context_mode, self.context_mode)
        doc = self.context_mode.run_doctor()
        self.assertEqual(Path(doc["session_db_path"]), Path(self.temp_dir.name) / "session.db")
        self.assertTrue(doc["healthy"])
        self.assertTrue(doc["session_db_connected"])
        self.assertTrue(doc["optimizer_ready"])
        self.assertTrue(doc["fts5_enabled"])

    def test_02_sandboxed_command_compression(self):
        """Verify executing heavy commands in sandboxed subprocess with >90% token reduction."""
        code = "[print(f'CNC Step {i:04d}: G01 X{i*0.1:.2f} Y{i*0.2:.2f} Z{-i*0.05:.2f}') for i in range(400)]"
        # The optimizer uses shlex.split on every platform, then shell=False.
        cmd = shlex.join([sys.executable, "-c", code])
        res = self.context_mode.execute(cmd, timeout_sec=10)
        self.assertTrue(res["ok"], res.get("error"))
        self.assertEqual(res["raw_lines"], 400)
        self.assertLess(res["filtered_lines"], 30)
        self.assertGreater(res["savings_percentage"], 90.0)
        self.assertIn("CONTEXT-MODE COMPRESSION", res["output"])

    def test_03_custom_filter_script_execution(self):
        """Verify running custom Python filter script inside the execution sandbox."""
        code = "print('\\n'.join(['alpha', 'TARGET: extraction_value', 'beta']))"
        cmd = shlex.join([sys.executable, "-c", code])
        script = "output = '\\n'.join([l for l in lines if 'TARGET:' in l])"
        res = self.context_mode.execute(cmd, filter_script=script, timeout_sec=10)
        self.assertTrue(res["ok"], res.get("error"))
        self.assertEqual(res["raw_lines"], 3)
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
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertEqual(data["dashboard"]["status"], "active")

        # 2. GET /v1/context-mode/doctor
        req = urllib.request.Request(f"{self.base_url}/v1/context-mode/doctor")
        with self._open(req) as resp:
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
        with self._open(req) as resp:
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
        with self._open(req) as resp:
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
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertGreaterEqual(data.get("count", 0), 1)

    def test_07_skill_writer_context_mode_integration(self):
        """Verify SkillWriterAndMemory utilizes Context Mode for command execution and session continuity."""
        writer = SkillWriterAndMemory()
        self.assertIs(writer.context_mode, self.context_mode)
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
