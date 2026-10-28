"""WorkBuddy OpenAI-Compatible Bridge Server for Virtu-CAD-CAM-10B.

Provides standard OpenAI REST API endpoints (/v1/models, /v1/chat/completions)
enabling WorkBuddy to seamlessly select and converse with the Virtu-CAD-CAM-10B
fine-tuned model. Zero third-party dependencies (pure standard library).
"""

import sys
import os
import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Add workspace to path
WORKSPACE_DIR = r"D:\Virtu模型"
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY

MODEL_ID = "virtu-cad-cam-10b"
MODEL_NAME = "Virtu-CAD-CAM-10B (工业六大软件强化模型)"
PORT = 8000
HOST = "127.0.0.1"

engine = WishCADCAMEngine()


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class OpenAIBaseHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path in ["/v1/models", "/models"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()

            resp = {
                "object": "list",
                "data": [
                    {
                        "id": MODEL_ID,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "Virtu-Omni",
                        "permission": [],
                        "root": MODEL_ID,
                        "parent": None
                    }
                ]
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
        elif self.path in ["/", "/health", "/status"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "model": MODEL_ID, "software_count": 6}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path in ["/v1/chat/completions", "/chat/completions"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            
            try:
                data = json.loads(body_bytes.decode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON: {str(e)}"}).encode("utf-8"))
                return

            messages = data.get("messages", [])
            stream = data.get("stream", False)
            requested_model = data.get("model", MODEL_ID)

            # Extract user prompt
            user_prompt = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_prompt = m.get("content", "")
                    break

            if not user_prompt and messages:
                user_prompt = messages[-1].get("content", "")

            # Generate expert response using WishCADCAMEngine
            response_text = self._synthesize_response(user_prompt)

            if stream:
                self._handle_streaming_response(response_text)
            else:
                self._handle_json_response(response_text)
        else:
            self.send_response(404)
            self.end_headers()

    def _synthesize_response(self, prompt: str) -> str:
        """Process intent and return full CAD/CAM engineering report."""
        if not prompt:
            return "【Virtu-CAD-CAM-10B】请提供您的许愿式制造意图、零件规格或六大软件工程需求。"
        
        # Check if user asks for specific ontology info
        if any(w in prompt for w in ["功能", "插件", "菜单", "体系", "支持哪些软件"]):
            summary = ["### Virtu-CAD-CAM-10B 六大工业软件全功能知识库\n"]
            for s_name, s_info in SOFTWARE_ONTOLOGY.items():
                summary.append(f"#### {s_name} ({s_info.get('vendor', '')})")
                summary.append(f"- **API/宏支持**: {', '.join(s_info.get('api_types', []))}")
                plugins = list(s_info.get('plugins_and_addins', {}).keys())
                summary.append(f"- **官方插件支持**: {', '.join(plugins) if plugins else '内建系统模块'}")
                summary.append("")
            summary.append("支持对任意零件（如整体叶轮、精密齿轮、注塑模具、微型机轮模）进行“许愿式”全流程参数化建模与代码合成。")
            return "\n".join(summary)

        # Decompose intent and synthesize engineering outputs across all 6 packages
        return engine.synthesize_all_six(prompt)

    def _handle_json_response(self, text: str):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()

        created = int(time.time())
        resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": created,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 64,
                "completion_tokens": len(text) // 2,
                "total_tokens": 64 + len(text) // 2
            }
        }
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

    def _handle_streaming_response(self, text: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._send_cors_headers()
        self.end_headers()

        req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        # Chunk response into small parts
        chunk_size = 40
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            payload = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None
                    }
                ]
            }
            self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

        # End chunk
        end_payload = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }
            ]
        }
        self.wfile.write(f"data: {json.dumps(end_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    def log_message(self, format, *args):
        # Concise logging
        print(f"[WorkBuddy-Bridge] {args[0]} {args[1]} -> {args[2]}")


def run_server():
    server = ThreadingServer((HOST, PORT), OpenAIBaseHandler)
    print(f"============================================================")
    print(f"  Virtu-CAD-CAM-10B WorkBuddy Bridge Server Running")
    print(f"  URL: http://{HOST}:{PORT}/v1")
    print(f"  Model ID: {MODEL_ID}")
    print(f"  Endpoints: /v1/models, /v1/chat/completions")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    run_server()
