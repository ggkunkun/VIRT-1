# -*- coding: utf-8 -*-
"""tests/test_agent_toolchain_full.py — End-to-End Validation of CAD/CAM Agent Toolchain Interfaces.

Validates all 6 desktop applications referenced by user:
1. c:\\Users\\Public\\Desktop\\SOLIDWORKS 2021.lnk
2. c:\\Users\\Public\\Desktop\\AutoCAD 2026 - 简体中文 (Simplified Chinese).lnk
3. c:\\Users\\Public\\Desktop\\斯沃数控仿真软件.lnk
4. c:\\Users\\Public\\Desktop\\Vericut 9.6.lnk
5. c:\\Users\\Public\\Desktop\\CIMCO Edit 2026.lnk
6. c:\\Users\\Administrator\\Desktop\\中文版NX12.0.lnk

Validates all 5 access modalities:
- Mode 1: Python SDK (Local in-process CADCAMToolchainClient)
- Mode 2: REST HTTP Microservice (Remote CADCAMToolchainClient via HTTP REST)
- Mode 3: Unified CLI (cadcam_cli.py)
- Mode 4: Model Context Protocol (MCP JSON-RPC 2.0 stdio)
- Mode 5: LLM Tool Calling (OpenAI/Claude JSON schema + dispatcher)
- Mode 6: Desktop GUI Perception (DesktopController)
"""

import os
import sys
import json
import time
import threading
import subprocess
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.software_registry import (
    DESKTOP_SHORTCUTS,
    SOFTWARE_SPECS,
    diagnose_all,
    entry_candidates,
    resolve_entry,
    resolve_shortcut,
    normalize_software_key
)
from bridges.toolchain_client import CADCAMToolchainClient
from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call
from bridges.cadcam_mcp_server import handle_request
from bridges.cadcam_rest_server import ThreadingHTTPServer, CADCAMRESTHandler
from bridges.desktop_controller import DesktopController


class TestAgentToolchainFull(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Start background REST API server on dedicated test port
        cls.test_port = 8999
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.test_port), CADCAMRESTHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
            cls.httpd.server_close()

    def test_01_all_six_desktop_shortcuts(self):
        """6 大软件的桌面入口必须可解析 —— .lnk 与直连 .exe 同等有效。

        入口形态会漂移（本机 NX 的桌面入口就已被换成 中文版NX12.0.exe），
        因此断言"能解析到一个真实存在的入口"，而不是钉死某一个 .lnk 路径。
        """
        for sw_key in DESKTOP_SHORTCUTS:
            info = resolve_entry(sw_key)
            self.assertTrue(
                info["exists"],
                f"[{sw_key}] 桌面入口缺失，候选={entry_candidates(sw_key)}",
            )
            self.assertIsNotNone(
                info["target_path"], f"[{sw_key}] 入口无法解析出目标：{info.get('entry_path')}"
            )
            self.assertTrue(
                info["target_exists"],
                f"[{sw_key}] 入口目标不存在：{info['target_path']}",
            )

        diag = diagnose_all()
        self.assertEqual(diag["total_software"], 6)
        self.assertEqual(diag["ready_count"], 6, "All 6 CAD/CAM tools must report is_ready=True")

    def test_02_python_sdk_local_mode(self):
        """Test Mode 1: Python SDK (In-Process CADCAMToolchainClient)."""
        client = CADCAMToolchainClient()
        pf = client.preflight()
        self.assertEqual(pf["ready_count"], 6)

        # 1. CIMCO Macro B variable validation
        res_cimco = client.cimco.validate("#100=53.0\n#101=14.0\n#102=45.0\nWHILE [#102 GT 0] DO 1\n#102=#102-1\nEND 1\nM30")
        self.assertTrue(res_cimco["is_valid"])
        self.assertIn("#100", res_cimco["variables"])
        self.assertIn("#101", res_cimco["variables"])

        # 2. SSCNC tool offset quadrant calculation
        res_sscnc = client.sscnc.calculate_offsets([
            {"tool_num": 1, "type": "turning_rough", "x": 120.5, "z": 45.2, "r": 0.8, "quadrant": 3},
            {"tool_num": 2, "type": "threading", "x": 122.1, "z": 46.0, "r": 0.1, "quadrant": 8}
        ])
        self.assertEqual(res_sscnc["status"], "success")
        self.assertEqual(len(res_sscnc["offsets"]), 2)
        self.assertEqual(res_sscnc["offsets"][0]["quadrant_t"], 3)
        self.assertEqual(res_sscnc["offsets"][1]["quadrant_t"], 8)

        # 3. AutoCAD headless DXF creation
        dxf_res = client.autocad.create_dxf("sdk_shaft", [
            {"type": "circle", "center": [0, 0], "radius": 26.5},
            {"type": "line", "start": [-26.5, 0], "end": [26.5, 0]}
        ])
        self.assertEqual(dxf_res["status"], "success")
        self.assertTrue(os.path.exists(dxf_res["dxf_path"]))

        # 4. Desktop GUI sub-client capture
        cap_file = os.path.join(_ROOT, "scratch", "sdk_test_capture.png")
        cap_res = client.gui.capture(output_path=cap_file)
        self.assertEqual(cap_res["status"], "captured")
        self.assertTrue(os.path.exists(cap_file))

    def test_03_rest_api_remote_mode(self):
        """Test Mode 2: REST HTTP Microservice (Remote CADCAMToolchainClient)."""
        remote_client = CADCAMToolchainClient(base_url=f"http://127.0.0.1:{self.test_port}")

        # 1. Preflight via HTTP GET
        pf = remote_client.preflight()
        self.assertEqual(pf["ready_count"], 6)

        # 2. Dispatch via HTTP POST
        res_cimco = remote_client.cimco.validate("#500=42.0\nM30")
        self.assertTrue(res_cimco.get("is_valid"))
        self.assertIn("#500", res_cimco.get("variables", {}))

        # 3. SSCNC calculate offsets via HTTP POST
        res_sscnc = remote_client.sscnc.calculate_offsets([
            {"tool_num": 1, "type": "turning_rough", "x": 50.0, "z": 20.0, "r": 0.4, "quadrant": 3}
        ])
        self.assertEqual(res_sscnc.get("status"), "success")

    def test_04_mcp_server_protocol(self):
        """Test Mode 4: Model Context Protocol (MCP JSON-RPC 2.0)."""
        # 1. tools/list
        list_req = {"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}}
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
        self.assertIn("cadcam_desktop_gui", tool_names)

        # 2. tools/call
        call_req = {
            "jsonrpc": "2.0", "id": 11, "method": "tools/call",
            "params": {
                "name": "cadcam_preflight",
                "arguments": {}
            }
        }
        call_resp = handle_request(call_req)
        self.assertFalse(call_resp["result"]["isError"])
        text = call_resp["result"]["content"][0]["text"]
        data = json.loads(text)
        self.assertEqual(data["ready_count"], 6)

    def test_05_llm_tool_calling_specs(self):
        """Test Mode 5: LLM Function Calling Schemas."""
        defs = get_cadcam_tool_definitions()
        self.assertGreaterEqual(len(defs), 8)
        for d in defs:
            self.assertEqual(d["type"], "function")
            fn = d["function"]
            # 工具名分两个已注册族：cadcam_*（六软件执行链）与 desktop_*（桌面控制族，
            # 由 bridges/desktop_gate.py 单独审批）。原来只断言 cadcam_ 前缀，新增
            # desktop_* 族后会把合法工具判红；此处放宽为"属于已注册族"，同时补上
            # 原先缺失的 schema 完整性检查（缺 properties 的工具等于没法定参数）。
            self.assertTrue(fn["name"].startswith(("cadcam_", "desktop_")),
                            "未注册的工具名前缀: %s" % fn["name"])
            self.assertIn("description", fn)
            self.assertIn("parameters", fn)
            self.assertEqual(fn["parameters"].get("type"), "object")
            self.assertIsInstance(fn["parameters"].get("properties"), dict)

        # Execute tool call
        res = execute_tool_call("cadcam_sscnc_control", {
            "action": "calculate_offsets",
            "tools": [{"tool_num": 1, "type": "boring_bar", "x": 30.0, "z": 10.0, "r": 0.2, "quadrant": 2}]
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["offsets"][0]["quadrant_t"], 2)

    def test_06_cli_interface(self):
        """Test Mode 3: Unified Command Line Interface (cadcam_cli.py)."""
        # Preflight CLI
        p_pf = subprocess.run([sys.executable, "cadcam_cli.py", "preflight", "--json"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=_ROOT)
        self.assertEqual(p_pf.returncode, 0)
        data = json.loads(p_pf.stdout)
        self.assertEqual(data["ready_count"], 6)

        # Dispatch CLI
        p_disp = subprocess.run([
            sys.executable, "cadcam_cli.py", "dispatch",
            "-s", "cimco", "-a", "validate_macro", "--code", "#100=1\nM30"
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=_ROOT)
        self.assertEqual(p_disp.returncode, 0)
        disp_data = json.loads(p_disp.stdout)
        self.assertTrue(disp_data["is_valid"])


if __name__ == "__main__":
    unittest.main()
