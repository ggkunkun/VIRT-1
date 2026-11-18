"""Comprehensive Integration Tests for Virtu Foundation Model x Paperclip Control Plane.

Tests:
1. Enterprise Org Chart & Reporting Lines.
2. Atomic Task Checkout & Lease Collision Prevention.
3. Heartbeat Execution & Run Audit Tracking.
4. Governance Approval Gates & Security Deciders.
5. Budget & Token Spend Accounting.
6. WorkBuddy Bridge REST API endpoints (/v1/paperclip/*).
7. SkillWriter & Memory Paperclip Task Dispatch.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from virtu_omni.paperclip import (
    VirtuPaperclipAdapter,
    TaskStatus,
    TaskPriority,
    ApprovalStatus,
)
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from scripts import workbuddy_virtu_bridge as bridge


class TestPaperclipIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp_dir = tempfile.TemporaryDirectory(prefix="virtu_paperclip_test_")
        cls.addClassCleanup(temp_dir.cleanup)
        env_patch = patch.dict(os.environ, {
            "VIRTU_MEMORY_PATH": str(Path(temp_dir.name) / "skill_memory.json"),
            "VIRTU_SKILLS_ROOT": str(Path(temp_dir.name) / "skills"),
        })
        cls.addClassCleanup(env_patch.stop)
        env_patch.start()

        # Fresh control plane: test tasks must not leak into the shared singleton.
        cls.paperclip = VirtuPaperclipAdapter()
        for p in (
            patch.object(VirtuPaperclipAdapter, "_instance", cls.paperclip),
            patch.object(bridge, "paperclip_adapter", cls.paperclip),
        ):
            cls.addClassCleanup(p.stop)
            p.start()

        cls.test_token = secrets.token_urlsafe(32)
        token_patch = patch.object(bridge, "_BRIDGE_TOKEN", cls.test_token)
        cls.addClassCleanup(token_patch.stop)
        token_patch.start()

        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.server = bridge.ThreadingServer(("127.0.0.1", 0), bridge.OpenAIBaseHandler)
        cls.addClassCleanup(cls.server.server_close)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
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

    def _open(self, request, *, authenticate=True):
        self.assertTrue(request.full_url.startswith(f"{self.base_url}/"))
        if authenticate:
            request.add_unredirected_header("Authorization", f"Bearer {self.test_token}")
        return self.opener.open(request, timeout=30)

    def test_00_bridge_requires_authentication(self):
        """Missing and invalid credentials must still fail for GET and POST."""
        for path, payload in (("/v1/paperclip/dashboard", None), ("/v1/paperclip/task/dispatch", b"{}")):
            for authorization in (None, f"Bearer {self.test_token}-invalid"):
                with self.subTest(path=path, credentials="missing" if authorization is None else "invalid"):
                    headers = {"Content-Type": "application/json"}
                    if authorization is not None:
                        headers["Authorization"] = authorization
                    req = urllib.request.Request(f"{self.base_url}{path}", data=payload, headers=headers)
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        with self._open(req, authenticate=False):
                            pass
                    with caught.exception as response:
                        self.assertEqual(response.code, 401)

    def test_01_org_chart_and_agent_profiles(self):
        """Verify 5 Virtu industrial agents are properly registered with reporting lines."""
        org = self.paperclip.control_plane.get_org_chart()
        self.assertEqual(org["total_agents"], 5)
        self.assertEqual(org["company_id"], "virtu-industrial-corp")

        agent_ids = {a["id"] for a in org["hierarchy"]}
        expected = {
            "virtu-architect",
            "virtu-cad-modeler",
            "virtu-cam-engineer",
            "virtu-security-auditor",
            "virtu-memory-lead",
        }
        self.assertEqual(agent_ids, expected)

        # Chief Architect has no supervisor; others report to architect
        for a in org["hierarchy"]:
            if a["id"] == "virtu-architect":
                self.assertIsNone(a["reports_to"])
            else:
                self.assertEqual(a["reports_to"], "virtu-architect")

    def test_02_task_creation_and_atomic_checkout(self):
        """Verify task lifecycle and lease collision protection."""
        cp = self.paperclip.control_plane
        task = cp.create_task(
            title="Design Bearing Bracket",
            description="Create 3D assembly in SolidWorks",
            assigned_agent_id="virtu-cad-modeler",
            priority=TaskPriority.HIGH,
        )
        self.assertEqual(task.status, TaskStatus.TODO)

        # 1. Primary agent checks out
        chk1 = cp.checkout_task(task.id, agent_id="virtu-cad-modeler", lease_duration_sec=300.0)
        self.assertTrue(chk1["ok"])
        self.assertEqual(cp.tasks[task.id].status, TaskStatus.IN_PROGRESS)
        self.assertEqual(cp.tasks[task.id].checkout_lease_owner, "virtu-cad-modeler")

        # 2. Competing agent attempts collision -> must fail
        chk2 = cp.checkout_task(task.id, agent_id="virtu-cam-engineer")
        self.assertFalse(chk2["ok"])
        self.assertIn("currently leased", chk2["error"])

    def test_03_heartbeat_execution_lifecycle(self):
        """Verify heartbeat triggers, context generation, and document saving."""
        hb = self.paperclip.heartbeat_runner
        cp = self.paperclip.control_plane

        task = cp.create_task(
            title="Generate NC Milling Program",
            description="5-axis contour toolpaths",
            assigned_agent_id="virtu-cam-engineer",
        )

        res = hb.trigger_heartbeat(
            agent_id="virtu-cam-engineer",
            wake_reason="task_assigned",
            task_id=task.id,
            executor_fn=self.paperclip._virtu_agent_executor,
        )
        self.assertTrue(res.ok)
        self.assertGreater(res.tokens_consumed, 0)
        self.assertIn("gcode_macro", res.documents_generated)

        # Task should now be marked DONE
        self.assertEqual(cp.tasks[task.id].status, TaskStatus.DONE)
        self.assertIn("gcode_macro", cp.tasks[task.id].documents)

    def test_04_approval_gate_workflow(self):
        """Verify governance approval request and decision resolution."""
        cp = self.paperclip.control_plane
        task = cp.create_task(title="Deploy Machine Toolpath", description="Direct NC streaming")

        # Request approval
        app_req = cp.request_approval(
            task_id=task.id,
            agent_id="virtu-cam-engineer",
            action_type="stream_to_cnc",
            payload={"port": "COM3", "baud": 115200},
        )
        self.assertEqual(app_req.status, ApprovalStatus.PENDING)
        self.assertEqual(cp.tasks[task.id].status, TaskStatus.IN_REVIEW)

        # Decide approval
        dec_res = cp.decide_approval(
            approval_id=app_req.id,
            approved=True,
            decided_by="virtu-architect",
            rationale="Simulation passed cleanly",
        )
        self.assertTrue(dec_res["ok"])
        self.assertEqual(dec_res["approval"]["status"], "approved")
        self.assertEqual(cp.tasks[task.id].status, TaskStatus.IN_PROGRESS)

    def test_05_budget_and_spend_limits(self):
        """Verify token and dollar spend accounting."""
        summary = self.paperclip.control_plane.get_summary()
        self.assertIn("total_spent_usd", summary)
        self.assertIn("total_tokens_consumed", summary)
        self.assertGreaterEqual(summary["total_tokens_consumed"], 0)

    def test_06_workbuddy_bridge_paperclip_endpoints(self):
        """Verify Bridge HTTP REST API endpoints (/v1/paperclip/*)."""
        # 1. GET /v1/paperclip/dashboard
        req = urllib.request.Request(f"{self.base_url}/v1/paperclip/dashboard")
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertEqual(data["dashboard"]["org_chart"]["total_agents"], 5)

        # 2. GET /v1/paperclip/org
        req = urllib.request.Request(f"{self.base_url}/v1/paperclip/org")
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertEqual(len(data["org"]["hierarchy"]), 5)

        # 3. POST /v1/paperclip/task/dispatch
        post_data = json.dumps(
            {
                "title": "REST Bridge CAD Task",
                "description": "Parametric Shaft",
                "assigned_agent_id": "virtu-cad-modeler",
                "priority": "high",
                "trigger_heartbeat": True,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/paperclip/task/dispatch",
            data=post_data,
            headers={"Content-Type": "application/json"},
        )
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))
            self.assertIsNotNone(data.get("heartbeat"))

        # 4. POST /v1/paperclip/heartbeat/trigger
        hb_data = json.dumps({"agent_id": "virtu-security-auditor", "wake_reason": "scheduled_check"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/paperclip/heartbeat/trigger",
            data=hb_data,
            headers={"Content-Type": "application/json"},
        )
        with self._open(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("ok"))

    def test_07_skill_writer_dispatch_task(self):
        """Verify SkillWriterAndMemory integration with Paperclip."""
        writer = SkillWriterAndMemory()
        res = writer.dispatch_paperclip_task(
            title="Self-Evolution Knowledge Sync",
            description="Commit lessons to Hindsight",
            agent_id="virtu-memory-lead",
        )
        self.assertTrue(res["ok"])
        self.assertIsNotNone(res["heartbeat"])


if __name__ == "__main__":
    unittest.main()
