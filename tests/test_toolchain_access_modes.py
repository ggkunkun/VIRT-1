# -*- coding: utf-8 -*-
"""tests/test_toolchain_access_modes.py — Comprehensive Test Suite for Agent Toolchain Access Modes.

Validates the multiple integration modes:
1. Python SDK Access Mode (CADCAMToolchainClient)
2. Command-Line (CLI) Access Mode (cadcam_cli.py)
3. Model Context Protocol (MCP) Server Access Mode (cadcam_mcp_server.py)
4. LLM Function Calling Schema & Dispatch Mode (tool_calling_specs.py)
5. Desktop GUI & Visual Computer-Use Access Mode (desktop_controller.py)
6. Shortcut & Process Registry Discovery Mode (software_registry.py)
"""

import os
import sys
import json
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bridges.software_registry import diagnose_all, SOFTWARE_SPECS, normalize_software_key
from bridges.toolchain_client import CADCAMToolchainClient
from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call
from bridges.desktop_controller import DesktopController
from bridges.cadcam_mcp_server import handle_request


class TestToolchainAccessModes(unittest.TestCase):

    def test_01_software_registry_diagnosis(self):
        """Test desktop shortcuts, binary discovery, and running process health check."""
        report = diagnose_all()
        self.assertEqual(report["total_software"], 6)
        self.assertEqual(report["ready_count"], 6, "All 6 CAD/CAM tools must be ready")
        for key in ("solidworks", "sscnc", "cimco", "autocad", "vericut", "nx"):
            self.assertIn(key, report["software"])
            sw_info = report["software"][key]
            self.assertTrue(sw_info["is_ready"])
            self.assertTrue(sw_info["shortcut_present"])
            self.assertIsNotNone(sw_info["binary_found"])
            self.assertTrue(os.path.exists(sw_info["binary_found"]), f"Binary not found: {sw_info['binary_found']}")

    def test_02_python_sdk_preflight_and_dispatch(self):
        """Test Python SDK client in-process mode."""
        client = CADCAMToolchainClient()
        pf = client.preflight()
        self.assertEqual(pf["ready_count"], 6)

        # Dispatch CIMCO validation
        res_cimco = client.cimco.validate("#100 = 100.0\n#101 = 20.0\nWHILE [#101 LE #100] DO 1\n#101 = #101 + 5\nEND 1\nM30")
        self.assertTrue(res_cimco["is_valid"])
        self.assertIn("#100", res_cimco["variables"])
        self.assertIn("#101", res_cimco["variables"])

        # Dispatch SSCNC tool offset calculation
        res_sscnc = client.sscnc.calculate_offsets([
            {"tool_num": 1, "type": "turning_rough", "x": 100.0, "z": 50.0, "r": 0.8, "quadrant": 3}
        ])
        self.assertEqual(res_sscnc["status"], "success")
        self.assertEqual(len(res_sscnc["offsets"]), 1)
        self.assertEqual(res_sscnc["offsets"][0]["quadrant_t"], 3)

        # Dispatch AutoCAD headless DXF creation
        res_cad = client.autocad.create_dxf("test_part", [
            {"type": "circle", "center": (0, 0), "radius": 25.0},
            {"type": "line", "start": (-30, 0), "end": (30, 0)},
        ])
        self.assertEqual(res_cad["status"], "success")
        self.assertTrue(os.path.exists(res_cad["dxf_path"]))

    def test_03_cli_execution_mode(self):
        """Test cadcam_cli.py CLI subcommands via subprocess."""
        # Preflight CLI
        res = subprocess.run([sys.executable, "cadcam_cli.py", "preflight", "--json"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["ready_count"], 6)

        # Dispatch CLI
        res_disp = subprocess.run([
            sys.executable, "cadcam_cli.py", "dispatch",
            "-s", "cimco", "-a", "validate_macro", "--code", "#500=1.0\nM30"
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(res_disp.returncode, 0)
        disp_data = json.loads(res_disp.stdout)
        self.assertTrue(disp_data["is_valid"])

        # Tools list CLI
        res_tools = subprocess.run([sys.executable, "cadcam_cli.py", "tools"],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        self.assertEqual(res_tools.returncode, 0)
        tools_data = json.loads(res_tools.stdout)
        self.assertGreaterEqual(len(tools_data), 8)

    def test_04_mcp_server_protocol(self):
        """Test Model Context Protocol (MCP) JSON-RPC handler."""
        # 1. Initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        init_resp = handle_request(init_req)
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "industrial-cadcam-mcp-server")

        # 2. tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        list_resp = handle_request(list_req)
        tools = list_resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("cadcam_preflight", tool_names)
        self.assertIn("cadcam_solidworks_model", tool_names)
        self.assertIn("cadcam_nx_journal", tool_names)
        self.assertIn("cadcam_autocad_draw", tool_names)
        self.assertIn("cadcam_cimco_validate", tool_names)
        self.assertIn("cadcam_vericut_simulate", tool_names)
        self.assertIn("cadcam_sscnc_control", tool_names)
        self.assertIn("cadcam_run_full_chain", tool_names)

        # 3. tools/call
        call_req = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "cadcam_cimco_validate",
                "arguments": {"action": "validate_macro", "code": "#100=42\nM30"}
            }
        }
        call_resp = handle_request(call_req)
        self.assertFalse(call_resp["result"]["isError"])
        content_text = call_resp["result"]["content"][0]["text"]
        payload = json.loads(content_text)
        self.assertTrue(payload["is_valid"])

    def test_05_llm_function_calling_specs(self):
        """Test OpenAI/Claude function definitions and dispatcher."""
        specs = get_cadcam_tool_definitions()
        self.assertGreaterEqual(len(specs), 8)
        for s in specs:
            self.assertEqual(s["type"], "function")
            self.assertTrue(s["function"]["name"].startswith(("cadcam_", "desktop_")))
            self.assertIn("description", s["function"])
            self.assertIn("parameters", s["function"])

        # Execute tool call
        res = execute_tool_call("cadcam_preflight", {})
        self.assertEqual(res["ready_count"], 6)

    def test_06_desktop_gui_controller(self):
        """Test Desktop GUI perception and window discovery."""
        ctl = DesktopController()
        # Full screen capture
        out_cap = os.path.join(ROOT, "scratch", "unittest_capture.png")
        cap_res = ctl.capture(output_path=out_cap)
        self.assertEqual(cap_res["status"], "captured")
        self.assertTrue(os.path.exists(out_cap))
        self.assertGreater(cap_res["width"], 0)
        self.assertGreater(cap_res["height"], 0)


if __name__ == "__main__":
    unittest.main()
