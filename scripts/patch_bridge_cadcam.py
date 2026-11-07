# -*- coding: utf-8 -*-
"""Patch workbuddy_virtu_bridge.py with CAD/CAM REST endpoints and tool auto-execution."""

import sys
import os

BRIDGE_PATH = r"d:\Virtu模型\scripts\workbuddy_virtu_bridge.py"

with open(BRIDGE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
import_target = "from bridges.six_software_orchestrator import SixSoftwareOrchestrator"
import_replacement = """from bridges.six_software_orchestrator import SixSoftwareOrchestrator
from bridges.software_registry import diagnose_all
from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call"""

if import_replacement not in content:
    assert import_target in content, "import_target not found"
    content = content.replace(import_target, import_replacement, 1)

# 2. GET endpoints for CAD/CAM
get_target = """        else:
            # Default health & model discovery response"""

get_replacement = """        elif clean_path in ["/v1/cadcam/preflight", "/api/preflight", "/cadcam/preflight"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            diag = diagnose_all()
            self.wfile.write(json.dumps(diag, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/cadcam/tools", "/api/tools", "/cadcam/tools"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            tools = get_cadcam_tool_definitions()
            self.wfile.write(json.dumps({"tools": tools, "count": len(tools)}, ensure_ascii=False).encode("utf-8"))
            return
        else:
            # Default health & model discovery response"""

if "/v1/cadcam/preflight" not in content:
    assert get_target in content, "get_target not found"
    content = content.replace(get_target, get_replacement, 1)

# 3. POST endpoints for CAD/CAM
post_target = """    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ["/v1/harness2/apply", "/harness2/apply"]:"""

post_replacement = """    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ["/v1/cadcam/tools/call", "/api/tools/call", "/cadcam/tools/call"]:
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length > 0 else {}
            tool_name = req_data.get("name") or req_data.get("tool_name")
            args = req_data.get("arguments") or req_data.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            res = execute_tool_call(tool_name, args)
            self._send_raw_json(res)
            return
        elif clean_path in ["/v1/cadcam/dispatch", "/api/dispatch", "/cadcam/dispatch"]:
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length > 0 else {}
            sw = req_data.get("target_software") or req_data.get("software")
            act = req_data.get("action")
            params = req_data.get("parameters") or req_data.get("params") or {}
            res = six_orchestrator.dispatch(sw, act, params)
            self._send_raw_json(res)
            return
        elif clean_path in ["/v1/chain/run", "/api/chain", "/chain/run"]:
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length > 0 else {}
            wish = req_data.get("wish", "")
            out_root = req_data.get("out_root")
            skip = tuple(req_data.get("skip", ()))
            res = six_orchestrator.run_full_chain(wish, out_root=out_root, skip=skip)
            self._send_raw_json(res)
            return
        elif clean_path in ["/v1/harness2/apply", "/harness2/apply"]:"""

if "/v1/cadcam/tools/call" not in content:
    assert post_target in content, "post_target not found"
    content = content.replace(post_target, post_replacement, 1)

# 4. Auto-execute support in tool orchestration
orch_call_target = """            if has_tool_context:
                tool_resp = self._handle_tool_orchestration(messages, tools)"""

orch_call_replacement = """            auto_execute = bool(data.get("auto_execute_tools", False) or data.get("auto_execute", False))
            if self.headers.get("X-Auto-Execute-Tools", "").lower() in ("true", "1", "yes"):
                auto_execute = True

            if has_tool_context:
                tool_resp = self._handle_tool_orchestration(messages, tools, auto_execute=auto_execute)"""

if "auto_execute = bool(data.get" not in content:
    assert orch_call_target in content, "orch_call_target not found"
    content = content.replace(orch_call_target, orch_call_replacement, 1)

# 5. Method signature and auto_execute logic in _handle_tool_orchestration
fn_sig_target = "def _handle_tool_orchestration(self, messages: list, tools: list) -> dict:"
fn_sig_replacement = "def _handle_tool_orchestration(self, messages: list, tools: list, auto_execute: bool = False) -> dict:"

if fn_sig_replacement not in content:
    assert fn_sig_target in content, "fn_sig_target not found"
    content = content.replace(fn_sig_target, fn_sig_replacement, 1)

auto_exec_body_target = """        if tool_calls:
            normalized_calls = []
            for tc in tool_calls:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                args = fn.get("arguments", {})
                if not isinstance(args, str):
                    args_str = json.dumps(args, ensure_ascii=False)
                else:
                    args_str = args
                normalized_calls.append({
                    "id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "arguments": args_str,
                    }
                })
            return {
                "id": req_id,
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content_text or "",
                        "tool_calls": normalized_calls
                    },
                    "finish_reason": "tool_calls"
                }],
                "usage": {"prompt_tokens": 128, "completion_tokens": 64, "total_tokens": 192}
            }"""

auto_exec_body_replacement = """        if tool_calls:
            normalized_calls = []
            for tc in tool_calls:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                args = fn.get("arguments", {})
                if not isinstance(args, str):
                    args_str = json.dumps(args, ensure_ascii=False)
                else:
                    args_str = args
                normalized_calls.append({
                    "id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "arguments": args_str,
                    }
                })

            if auto_execute:
                exec_results = []
                for nc in normalized_calls:
                    fn_name = nc["function"]["name"]
                    fn_args = nc["function"]["arguments"]
                    try:
                        args_dict = json.loads(fn_args) if isinstance(fn_args, str) else fn_args
                    except Exception:
                        args_dict = {}
                    print(f"[WorkBuddy-Bridge] Auto-executing {fn_name}({args_dict})")
                    exec_res = execute_tool_call(fn_name, args_dict)
                    exec_results.append(exec_res)
                    conv.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [nc]
                    })
                    conv.append({
                        "role": "tool",
                        "tool_call_id": nc["id"],
                        "name": fn_name,
                        "content": json.dumps(exec_res, ensure_ascii=False)
                    })

                synth_text = backend.generate(conv)
                return {
                    "id": req_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": MODEL_ID,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": synth_text or f"工具已成功执行: {json.dumps(exec_results, ensure_ascii=False)}",
                            "tool_calls": normalized_calls,
                            "tool_results": exec_results,
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {"prompt_tokens": 256, "completion_tokens": 128, "total_tokens": 384}
                }

            return {
                "id": req_id,
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content_text or "",
                        "tool_calls": normalized_calls
                    },
                    "finish_reason": "tool_calls"
                }],
                "usage": {"prompt_tokens": 128, "completion_tokens": 64, "total_tokens": 192}
            }"""

if "if auto_execute:" not in content:
    assert auto_exec_body_target in content, "auto_exec_body_target not found"
    content = content.replace(auto_exec_body_target, auto_exec_body_replacement, 1)

with open(BRIDGE_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: workbuddy_virtu_bridge.py patched successfully!")
