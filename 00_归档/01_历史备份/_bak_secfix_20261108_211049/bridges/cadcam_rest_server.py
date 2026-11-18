# -*- coding: utf-8 -*-
"""bridges/cadcam_rest_server.py — High-Performance RESTful HTTP Server for CAD/CAM Agent Toolchain.

Exposes the 6-software toolchain as standard HTTP REST endpoints for any Agent framework:
- GET  /health                   -> Health status
- GET  /v1/cadcam/preflight      -> System & software readiness diagnostics
- POST /v1/cadcam/dispatch       -> Direct software dispatch {"target_software", "action", "parameters"}
- GET  /v1/cadcam/tools          -> Export OpenAI/Claude tool calling JSON schemas
- POST /v1/cadcam/tools/call     -> Execute LLM tool call {"name", "arguments"}
- POST /v1/chain/run             -> Execute full 6-software manufacturing pipeline {"wish", "out_root", "skip"}
- POST /v1/cadcam/gui            -> Desktop GUI perception and control {"action", ...}

Zero external dependencies: uses Python standard library `http.server` with multithreading.
"""

import os
import sys
import json
import time
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.software_registry import diagnose_all, SOFTWARE_SPECS
from bridges.six_software_orchestrator import SixSoftwareOrchestrator
from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call
from bridges.desktop_controller import DesktopController

_GLOBAL_ORCHESTRATOR = None
_GLOBAL_DESKTOP_CTL = None


def get_orchestrator() -> SixSoftwareOrchestrator:
    global _GLOBAL_ORCHESTRATOR
    if _GLOBAL_ORCHESTRATOR is None:
        _GLOBAL_ORCHESTRATOR = SixSoftwareOrchestrator()
    return _GLOBAL_ORCHESTRATOR


def get_desktop_ctl() -> DesktopController:
    global _GLOBAL_DESKTOP_CTL
    if _GLOBAL_DESKTOP_CTL is None:
        _GLOBAL_DESKTOP_CTL = DesktopController()
    return _GLOBAL_DESKTOP_CTL


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class CADCAMRESTHandler(BaseHTTPRequestHandler):
    server_version = "CADCAMToolchainREST/1.0"

    def _send_json(self, status_code: int, data: Any):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception as e:
            return {"_parse_error": str(e)}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if not path or path == "/health":
            self._send_json(200, {
                "status": "ok",
                "service": "cadcam-toolchain-rest",
                "version": "1.0.0",
                "supported_software": list(SOFTWARE_SPECS.keys()),
            })
            return

        elif path in ("/v1/cadcam/preflight", "/api/preflight"):
            diag = diagnose_all()
            self._send_json(200, diag)
            return

        elif path in ("/v1/cadcam/tools", "/api/tools"):
            tools = get_cadcam_tool_definitions()
            self._send_json(200, {"tools": tools, "count": len(tools)})
            return

        self._send_json(404, {"status": "error", "message": f"Endpoint not found: {self.path}"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        payload = self._read_json()
        if "_parse_error" in payload:
            self._send_json(400, {"status": "error", "message": f"Invalid JSON: {payload['_parse_error']}"})
            return

        orch = get_orchestrator()

        # 1. Dispatch action to specific software
        if path in ("/v1/cadcam/dispatch", "/api/dispatch"):
            software = payload.get("target_software") or payload.get("software")
            action = payload.get("action")
            params = payload.get("parameters") or payload.get("params") or {}
            if not software or not action:
                self._send_json(400, {"status": "error", "message": "Missing 'target_software' or 'action'"})
                return
            t0 = time.time()
            res = orch.dispatch(software, action, params)
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            if isinstance(res, dict):
                res.setdefault("elapsed_ms", elapsed_ms)
            self._send_json(200, res)
            return

        # 2. LLM Tool Call standard execution
        elif path in ("/v1/cadcam/tools/call", "/api/tools/call"):
            tool_name = payload.get("name") or payload.get("tool_name")
            args = payload.get("arguments") or payload.get("args") or {}
            if not tool_name:
                self._send_json(400, {"status": "error", "message": "Missing 'name' in tool call"})
                return
            res = execute_tool_call(tool_name, args)
            self._send_json(200, res)
            return

        # 3. Full manufacturing pipeline chain
        elif path in ("/v1/chain/run", "/api/chain"):
            wish = payload.get("wish", "")
            if not wish:
                self._send_json(400, {"status": "error", "message": "Missing 'wish' string"})
                return
            out_root = payload.get("out_root")
            skip = tuple(payload.get("skip", ()))
            res = orch.run_full_chain(wish, out_root=out_root, skip=skip)
            self._send_json(200, res)
            return

        # 4. Desktop GUI perception and control
        elif path in ("/v1/cadcam/gui", "/api/gui"):
            action = payload.get("action", "capture")
            ctl = get_desktop_ctl()
            if action == "capture":
                res = ctl.capture(output_path=payload.get("output_path"), software=payload.get("software"))
            elif action == "focus":
                res = ctl.focus(payload.get("software", ""))
            elif action == "click":
                res = ctl.click(payload.get("x", 0), payload.get("y", 0),
                                button=payload.get("button", "left"),
                                double=payload.get("double", False))
            elif action == "type":
                res = ctl.type_text(payload.get("text", ""))
            elif action == "hotkey":
                res = ctl.hotkey(payload.get("keys", ""))
            elif action in ("dismiss", "dismiss_dialogs"):
                res = ctl.dismiss_all_dialogs()
            else:
                res = {"status": "error", "message": f"Unknown GUI action: {action}"}
            self._send_json(200, res)
            return

        self._send_json(404, {"status": "error", "message": f"Endpoint not found: {self.path}"})

    def log_message(self, format, *args):
        # Clean logging format
        sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [REST API] {format % args}\n")


def start_rest_server(host: str = "127.0.0.1", port: int = 8000):
    server = ThreadingHTTPServer((host, port), CADCAMRESTHandler)
    print("=" * 70)
    print(f" CAD/CAM Agent Toolchain HTTP REST Microservice Started")
    print(f" Listening on: http://{host}:{port}")
    print(f" Preflight:    http://{host}:{port}/v1/cadcam/preflight")
    print(f" Tools Schema: http://{host}:{port}/v1/cadcam/tools")
    print(f" Dispatch:     POST http://{host}:{port}/v1/cadcam/dispatch")
    print("=" * 70)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Industrial CAD/CAM Toolchain REST Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    args = parser.parse_args()
    start_rest_server(args.host, args.port)
