# -*- coding: utf-8 -*-
"""bridges/cadcam_mcp_server.py — Model Context Protocol (MCP) Server for CAD/CAM Toolchain.

Implements standard Anthropic/Antigravity MCP stdio server protocol:
- JSON-RPC 2.0 message handling over stdin / stdout
- tools/list: Exposes the 6 industrial software tools + full manufacturing chain + GUI
- tools/call: Dispatches calls and returns structured markdown/JSON observations

Can be registered in any MCP client config (e.g. claude_desktop_config.json, antigravity settings, cursor):
{
  "mcpServers": {
    "industrial-cadcam": {
      "command": "python",
      "args": ["D:/Virtu模型/bridges/cadcam_mcp_server.py"]
    }
  }
}
"""

import os
import sys
import json
import traceback

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call


def _mcp_tool_schema(openai_tool: dict) -> dict:
    """Convert OpenAI tool schema to MCP tool schema."""
    fn = openai_tool.get("function", {})
    return {
        "name": fn.get("name"),
        "description": fn.get("description"),
        "inputSchema": fn.get("parameters", {"type": "object", "properties": {}}),
    }


def handle_request(req: dict) -> dict:
    """Handle incoming JSON-RPC request."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "industrial-cadcam-mcp-server",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "notifications/initialized":
        return None

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    elif method == "tools/list":
        defs = get_cadcam_tool_definitions()
        tools = [_mcp_tool_schema(d) for d in defs]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools}
        }

    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        try:
            res = execute_tool_call(name, arguments)
            text_out = json.dumps(res, ensure_ascii=False, indent=2)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": text_out}
                    ],
                    "isError": res.get("status") == "error"
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"Tool execution failed: {e}\n{traceback.format_exc()}"}
                    ],
                    "isError": True
                }
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method [{method}] not found"
            }
        }


def run_stdio_server():
    """Main loop reading JSON-RPC lines from stdin and outputting to stdout."""
    if sys.platform == "win32":
        import io
        if hasattr(sys.stdin, "buffer"):
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            req = json.loads(line)
            resp = handle_request(req)
            if resp is not None:
                out_line = json.dumps(resp, ensure_ascii=False)
                sys.stdout.write(out_line + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"MCP Server error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    run_stdio_server()
