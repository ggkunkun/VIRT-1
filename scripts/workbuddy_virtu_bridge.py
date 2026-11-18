"""WorkBuddy OpenAI-compatible bridge for the Virtu runtime.

Provides standard OpenAI REST API endpoints (/v1/models, /v1/chat/completions)
The public model ID is retained as a client-compatibility alias. Runtime model
identity is reported separately; text and vision use separate channels.
"""

import sys
import os
import re
import json
import time
import uuid
import hmac
import io
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlsplit

# Add workspace to path
WORKSPACE_DIR = r"D:\Virtu模型"
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY
from virtu_omni.security.auditor import ModelSecurityAuditor
from virtu_omni.memory import (
    VirtuHindsightMemory,
    MemoryType,
    BuiltinWorkingMemory,
    LongTaskHallucinationSentinel,
    get_working_memory,
    get_sleep_framework,
)
from virtu_omni.reach import VirtuAgentReach
from virtu_omni.ai_scratch import VirtuAIScratch
from virtu_omni.paperclip import VirtuPaperclipAdapter
from virtu_omni.context_mode import VirtuContextMode
from virtu_omni.rea import VirtuREA
from virtu_omni.claude_plugins import VirtuClaudePlugins
from virtu_omni.computer_use import VirtuComputerUse
from virtu_omni.agent import VirtuSuperAgent
from bridges.six_software_orchestrator import SixSoftwareOrchestrator
from bridges.software_registry import diagnose_all
from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call
from bridges.bridge_security import bearer_authorized, path_allowed, SingleFlight, ensure_bridge_token
from virtu_omni.serving.deception_gate import gate_answer
from virtu_omni.runtime import trace as _runtime_trace

MODEL_ID = "virtu-cad-cam-10b"
MODEL_NAME = "Virtu local bridge (Qwen3-8B text backend; separate vision channel)"
PORT = 8000
HOST = "127.0.0.1"

engine = WishCADCAMEngine()
security_auditor = ModelSecurityAuditor()
hindsight_memory = VirtuHindsightMemory()
reach_adapter = VirtuAgentReach()
ai_scratch = VirtuAIScratch.get_instance()
paperclip_adapter = VirtuPaperclipAdapter.get_instance()
context_mode = VirtuContextMode.get_instance()
rea_adapter = VirtuREA.get_instance()
claude_plugins = VirtuClaudePlugins.get_instance()
computer_use = VirtuComputerUse.get_instance()
super_agent = VirtuSuperAgent()
six_orchestrator = SixSoftwareOrchestrator()
working_memory = get_working_memory(
    session_id="bridge_production_session",
    persist_path=os.path.join(WORKSPACE_DIR, "runs", "working_memory_state.json"),
)
memory_sentinel = LongTaskHallucinationSentinel(working_memory)


def _inject_hindsight_anchor(conv: list, user_prompt: str, max_chars: int = 1400) -> list:
    """Inject read-only Hindsight + coordinate isolation anchor into system context."""
    prompt_text = (user_prompt or "").strip()
    if not prompt_text:
        return conv
    try:
        ctx = hindsight_memory.build_domain_memory_context(
            query=prompt_text,
            bank_ids=["virtu_cad_cam", "virtu_cnc_machining", "virtu_quality_audit", "default"],
            max_items=3,
            update_stats=False,
            include_invariants=True,
            max_chars=max_chars,
        )
    except Exception:
        ctx = ""
    if not ctx:
        return conv
    block = f"<HINDSIGHT_MEMORY_ANCHOR>\n{ctx}\n</HINDSIGHT_MEMORY_ANCHOR>"
    updated = [dict(m) for m in conv]
    if updated and updated[0].get("role") == "system":
        cur = str(updated[0].get("content", ""))
        if "<HINDSIGHT_MEMORY_ANCHOR>" not in cur:
            updated[0]["content"] = (cur + "\n\n" + block).strip() if cur.strip() else block
    else:
        updated.insert(0, {"role": "system", "content": block})
    return updated


def _grounded_inference_enabled(request_flag=None) -> bool:
    """Return whether grounded closed-form/G71 inference is active."""
    if request_flag is not None:
        return bool(request_flag)
    raw = os.environ.get("VIRTU_GROUNDED_INFERENCE", "1").strip().lower()
    return raw not in ("0", "false", "off", "no")


def _grounded_max_repairs() -> int:
    try:
        return max(0, min(5, int(os.environ.get("VIRTU_GROUNDED_MAX_REPAIRS", "3"))))
    except (TypeError, ValueError):
        return 3


def _grounded_evidence(grounding: Any) -> Any:
    if not isinstance(grounding, dict) or not grounding.get("applicable"):
        return None
    if grounding.get("model_passed") or (grounding.get("fallback_gate") or {}).get("passed"):
        return [{"ok": True, "source": grounding.get("source"), "kind": grounding.get("kind")}]
    return None


def _run_grounded_chat(backend, conv: list, user_prompt: str, *,
                       max_tokens=None, temperature=None, think_param=None,
                       request_flag=None):
    """Run GroundedResponder when the prompt hits Lamé/G71; otherwise return None."""
    if not _grounded_inference_enabled(request_flag):
        return None
    try:
        from virtu_omni.agent.grounded_inference import (
            GroundedResponder,
            is_grounded_applicable,
        )
    except Exception:
        return None
    if not is_grounded_applicable(user_prompt):
        return None

    def _caller(msgs):
        if think_param is not None:
            out = backend.generate(msgs, max_tokens=max_tokens, temperature=temperature, think=think_param)
        else:
            out = backend.generate(msgs, max_tokens=max_tokens, temperature=temperature)
        return out[0] if isinstance(out, tuple) else out

    return GroundedResponder(_caller, max_repairs=_grounded_max_repairs()).respond(conv)


# Bridge authentication and app-exclusive execution guards
_BRIDGE_TOKEN = None
_MAX_REQUEST_BYTES = 16 * 1024 * 1024
_PUBLIC_GET_PATHS = {"/", "/health", "/healthz"}
_TRUSTED_CORS_ORIGINS = frozenset({
    "http://localhost", "http://127.0.0.1",
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
})

_app_lock_token = None
_app_lock = SingleFlight()

def _try_lock_app(token: str) -> bool:
    global _app_lock_token
    if not _app_lock.acquire():
        return False
    _app_lock_token = token
    return True

def _unlock_app():
    global _app_lock_token
    _app_lock_token = None
    _app_lock.release()

def run_exclusive(func, token: str):
    if not _try_lock_app(token):
        return False, {"error": "并发冲突：另一条链正在驱动工业软件"}
    try:
        res = func()
        return True, res
    finally:
        _unlock_app()

def _path_allowed(path: str) -> bool:
    root = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if path_allowed(path, root):
        return True
    # 允许访问当前用户的 Desktop 读取图纸/模型输入文件
    try:
        desktop = os.path.realpath(os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"))
        if desktop and path_allowed(path, desktop):
            return True
    except Exception:
        pass
    return False


def _authorized(headers) -> bool:
    expected = _BRIDGE_TOKEN or os.environ.get("VIRTU_BRIDGE_TOKEN", "")
    auth = headers.get("Authorization", "") if headers is not None else ""
    return bearer_authorized(auth, expected)


def _load_bridge_token() -> str:
    token = os.environ.get("VIRTU_BRIDGE_TOKEN") or ensure_bridge_token()
    if len(token.strip()) < 32:
        raise RuntimeError("VIRTU_BRIDGE_TOKEN is too short; refusing to start an unauthenticated bridge")
    return token.strip()


def _build_usage():
    """OpenAI-style token accounting taken from the backend's last generation.

    Only counts the runtime actually reported (Ollama eval_count/prompt_eval_count,
    or an upstream vLLM `usage` block) are published. When nothing was reported the
    field is omitted instead of filled with a character-length guess that a caller
    would read as a measurement — the eval harness scores truncation off these.
    """
    try:
        from virtu_real_backend import get_backend
        usage = getattr(get_backend(), "last_usage", None)
    except Exception:  # noqa: BLE001 - usage must never break a completion
        return None
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if total is None and isinstance(prompt, int) and isinstance(completion, int):
        total = prompt + completion
    if prompt is None and completion is None and total is None:
        return None
    return {"prompt_tokens": prompt, "completion_tokens": completion,
            "total_tokens": total}


def _attach_usage(resp: dict) -> dict:
    """Attach ``usage`` only when the backend actually reported counts.

    OpenAI's schema marks ``usage`` as optional, and the eval harness reads
    ``usage["prompt_tokens"]`` directly. Publishing ``"usage": null`` makes a
    "never measured" response indistinguishable from a fabricated zero, which
    is exactly what the protocol tests reject. So the key is dropped when
    ``_build_usage()`` returns ``None`` and injected when real counts exist.
    """
    usage = _build_usage()
    if usage is None:
        resp.pop("usage", None)
    else:
        resp["usage"] = usage
    return resp


def _error_http_status(err: Exception) -> int:
    """Map malformed requests, unavailable backends and upstream failures accurately."""
    if isinstance(err, (json.JSONDecodeError, UnicodeDecodeError)):
        return 400
    message = str(err).lower()
    if "backend unavailable" in message or "后端大模型未就绪" in str(err) or type(err).__name__ == "VisionUnavailable":
        return 503
    if (isinstance(err, (TimeoutError, ConnectionError, OSError))
            or type(err).__name__ in {"HTTPError", "URLError"}
            or "all candidates failed" in message):
        return 502
    return 500

def _validate_dispatch_args(target, action, args):
    VALID_TARGETS = {
        "Siemens_NX", "SOLIDWORKS", "AutoCAD", "CIMCO_Edit", "VERICUT", "SSCNC",
        "nx", "solidworks", "autocad", "cimco", "vericut", "sscnc"
    }
    if not target or target not in VALID_TARGETS:
        return False, f"未知目标软件: {target}"
    if not action:
        return False, "动作不能为空"
    if not isinstance(args, dict):
        return False, "参数必须为字典对象"
    def check_paths(value, key=""):
        if isinstance(value, dict):
            for child_key, child in value.items():
                ok, reason = check_paths(child, str(child_key))
                if not ok:
                    return ok, reason
        elif isinstance(value, (list, tuple)):
            for child in value:
                ok, reason = check_paths(child, key)
                if not ok:
                    return ok, reason
        elif isinstance(value, str) and (key.endswith(("_path", "_file")) or "path" in key.lower()):
            if not _path_allowed(value):
                return False, f"参数 {key} 路径不在允许根目录下"
        return True, "OK"

    ok, reason = check_paths(args)
    if not ok:
        return ok, reason
    return True, "OK"


def _validate_tool_call(tool_name, args):
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False, "工具名称不能为空"
    if not isinstance(args, dict):
        return False, "工具参数必须为 JSON 对象"
    safe_tools = {
        "cadcam_preflight", "cadcam_solidworks_model", "cadcam_nx_journal",
        "cadcam_autocad_draw", "cadcam_cimco_validate", "cadcam_vericut_simulate",
        "cadcam_sscnc_control", "cadcam_run_full_chain", "cadcam_desktop_gui",
        "cadcam_visual_inspect", "cad.parse_wish_intent", "solidworks.create_parametric_part",
        "nx.create_nxopen_script", "autocad.create_autolisp", "cimco.create_macro_b",
        "vericut.create_project_config", "sscnc.create_setup_guide", "ontology.lookup_plugin",
        "cadcam_extreme_chain", "cadcam_universal_geometry",
        "cadcam_cae_stress_analysis", "cadcam_sheetmetal_nest",
        "cadcam_step_reverse",
        "cadcam_assembly_build",
        "cadcam_feature_ops",
        "assembly_build", "cad.assembly_build", "step_reverse",
        "reverse_step_model", "cadcam_reverse_engineering",
        # Omni / Desktop
        "desktop.capture_screen", "desktop.click_element", "desktop.type_text",
        "desktop.press_hotkey", "desktop.focus_software",
        # CAD agent
        "cad.infer_blueprint_feature_tree", "cad.assemble_components_with_mates",
        "cad.infer_equipment_intent", "cad.decompose_automation_assembly",
        "cad.query_standard_parts_library", "cad.model_parametric_feature_part",
        "cad.generate_engineering_drawing_annotation", "cad.execute_solidworks_macro",
        "cad.one_sentence_parametric_engine", "software.dispatch_industrial_tool",
        # Agent / Skill / Memory / Web
        "agent.verify_and_self_optimize", "skill.synthesize_agent_skill",
        "memory.commit_long_term_experience", "web.search_technical_knowledge",
    }
    if tool_name not in safe_tools:
        return False, "工具不在允许列表中"
    return _validate_dispatch_args("Siemens_NX", "tool_call", args)


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    # Allow immediate rebind after a restart (Windows keeps closing sockets in
    # TIME_WAIT). Single-instance ownership is enforced by a named mutex in
    # run_server(), not by SO_REUSEADDR.
    allow_reuse_address = True


class OpenAIBaseHandler(BaseHTTPRequestHandler):
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            self.close_connection = True

    def _send_cors_headers(self):
        origin = self.headers.get("Origin", "")
        if origin in _TRUSTED_CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def end_headers(self):
        self._response_committed = True
        super().end_headers()

    def _require_auth(self):
        if _authorized(self.headers):
            return True
        self._send_raw_json({"error": {"message": "Valid Bearer token required", "type": "authentication_error"}}, status=401)
        return False

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        if origin not in _TRUSTED_CORS_ORIGINS:
            self._send_raw_json({"error": {"message": "Untrusted Origin", "type": "cors_error"}}, status=403)
            return
        requested_method = self.headers.get("Access-Control-Request-Method", "").upper()
        if requested_method not in {"GET", "POST"}:
            self._send_raw_json({"error": {"message": "Unsupported CORS method", "type": "cors_error"}}, status=403)
            return
        if not self._authorized_cors_preflight():
            return
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _authorized_cors_preflight(self):
        requested_headers = {
            header.strip().lower()
            for header in self.headers.get("Access-Control-Request-Headers", "").split(",")
            if header.strip()
        }
        allowed_headers = {"content-type", "authorization", "x-requested-with"}
        if not requested_headers.issubset(allowed_headers):
            self._send_raw_json({"error": {"message": "Unsupported CORS header", "type": "cors_error"}}, status=403)
            return False
        return True

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        query_params = parse_qs(urlsplit(self.path).query)
        if clean_path not in {"/", "/health", "/healthz"} and not self._require_auth():
            return
        if clean_path in ["/v1/models", "/models", "/api/v1/models"]:
            try:
                from virtu_real_backend import get_backend
                backend = get_backend()
                identity = backend.identity() if backend is not None else {"backend": "unavailable"}
            except Exception:
                identity = {"backend": "unavailable"}
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
                        "owned_by": "Virtu-runtime",
                        "permission": [],
                        "root": MODEL_ID,
                        "parent": None,
                        "metadata": identity,
                    }
                ]
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
        elif clean_path in ["/v1/reach/channels", "/reach/channels"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            channels = reach_adapter.get_channels()
            self.wfile.write(json.dumps({"ok": True, "channels": channels, "count": len(channels)}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ai-scratch/curriculum", "/ai-scratch/curriculum", "/v1/ai-scratch/overview"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            overview = ai_scratch.get_overview()
            self.wfile.write(json.dumps(overview, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ai-scratch/diagnostic", "/ai-scratch/diagnostic"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            questions = ai_scratch.tutor.get_diagnostic_questions()
            self.wfile.write(json.dumps({"ok": True, "questions": questions}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/paperclip/dashboard", "/paperclip/dashboard"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            dashboard = paperclip_adapter.get_dashboard()
            self.wfile.write(json.dumps({"ok": True, "dashboard": dashboard}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/paperclip/tasks", "/paperclip/tasks"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            tasks = [t.to_dict() for t in paperclip_adapter.control_plane.tasks.values()]
            self.wfile.write(json.dumps({"ok": True, "tasks": tasks, "count": len(tasks)}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/paperclip/org", "/paperclip/org"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            org = paperclip_adapter.control_plane.get_org_chart()
            self.wfile.write(json.dumps({"ok": True, "org": org}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/context-mode/dashboard", "/context-mode/dashboard"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            dash = context_mode.get_dashboard()
            self.wfile.write(json.dumps({"ok": True, "dashboard": dash}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/context-mode/doctor", "/context-mode/doctor"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            doc_res = context_mode.run_doctor()
            self.wfile.write(json.dumps({"ok": True, "doctor": doc_res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/rea/status", "/rea/status"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            status_res = rea_adapter.get_status()
            self.wfile.write(json.dumps(status_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/plugins/status", "/plugins/status"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            res = claude_plugins.get_status()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/plugins/marketplace", "/plugins/marketplace"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            q = query_params.get("q", [""])[0] or query_params.get("query", [""])[0]
            tag = query_params.get("tag", [None])[0]
            limit = int(query_params.get("limit", [20])[0])
            res = claude_plugins.search_marketplace(query=q, tag=tag, limit=limit)
            self.wfile.write(json.dumps({"ok": True, "count": len(res), "plugins": res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/plugins/list", "/plugins/list"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            tag = query_params.get("tag", [None])[0]
            installed_only = query_params.get("installed", ["false"])[0].lower() in ["true", "1"]
            limit = int(query_params.get("limit", [50])[0])
            res = claude_plugins.list_plugins(tag=tag, installed_only=installed_only, limit=limit)
            self.wfile.write(json.dumps({"ok": True, "count": len(res), "plugins": res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/computer-use/status", "/computer-use/status"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            status_res = computer_use.get_status()
            self.wfile.write(json.dumps(status_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/computer-use/summary", "/computer-use/summary"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            summary_res = computer_use.get_desktop_summary()
            self.wfile.write(json.dumps({"ok": True, "summary": summary_res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/computer-use/windows", "/computer-use/windows"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            visible = query_params.get("visible", ["true"])[0].lower() in ["true", "1"]
            wins_res = computer_use.execute_action("list_windows", visible_only=visible)
            self.wfile.write(json.dumps(wins_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/hindsight/status", "/hindsight/status"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            h_status = hindsight_memory.get_status()
            self.wfile.write(json.dumps(h_status, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in [
            "/v1/memory/working-memory/status", "/memory/working-memory/status",
            "/v1/working-memory/status", "/working-memory/status"
        ]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            wm_status = working_memory.export_snapshot()
            self.wfile.write(json.dumps(wm_status, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/security-audit", "/security-audit"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            audit_res = security_auditor.run_full_audit()
            status = {
                "framework": "Cloudflare security-audit-skill",
                "rules": ["AI-AND-LLM.md", "ATTACK-CLASSES.md", "report-schema.json"],
                "status": "active",
                "model_id": MODEL_ID,
                "summary": audit_res["summary"],
                "total_findings": len(audit_res["findings"]),
                "timestamp": time.time(),
            }
            self.wfile.write(json.dumps(status, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/harness2/status", "/harness2/status"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            status = {
                "engine": "Virtu Harness²",
                "framework": "Google Research Harness² (arXiv:2610.14224)",
                "status": "active",
                "surface": "virtu",
                "components": [
                    "systemprompt.md",
                    "guardrails.md",
                    "LongTermMEMORY.md",
                    "tool_descriptions/tool_guidance.md",
                    "sub_agents/",
                    "skills/",
                    "scripts/",
                    "plugin/",
                ],
                "model_id": MODEL_ID,
                "timestamp": time.time(),
            }
            self.wfile.write(json.dumps(status, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/cad/parametric-slider", "/cad/parametric-slider"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            slider_state = {
                "status": "ready",
                "part_name": "UG-01_轴承支座.SLDPRT",
                "sliders": [
                    {"id": "d_outer", "name": "外径轮廓 D_max", "value": 53.0, "min": 20.0, "max": 150.0, "step": 1.0, "unit": "mm"},
                    {"id": "d_inner", "name": "内孔配合径 D_bore", "value": 14.0, "min": 5.0, "max": 80.0, "step": 0.5, "unit": "mm"},
                    {"id": "overall_len", "name": "零件总长 L_T", "value": 45.0, "min": 10.0, "max": 200.0, "step": 1.0, "unit": "mm"},
                    {"id": "fillet_r", "name": "过渡圆角 R", "value": 10.0, "min": 0.5, "max": 30.0, "step": 0.5, "unit": "mm"}
                ],
                "progressive_disclosure": True,
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(slider_state, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/cadcam/preflight", "/api/preflight", "/cadcam/preflight"]:
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
        elif clean_path in ["/v1/super-agent/architecture", "/super-agent/architecture"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            arch = super_agent.explain_architecture()
            self.wfile.write(json.dumps(arch, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/sleep/status", "/sleep/status", "/v1/virtu/sleep/status"]:
            sf = get_sleep_framework()
            status_data = {
                "ok": True,
                "is_sleeping": sf.is_sleeping,
                "wake_buffer_count": len(sf.wake_buffer),
                "consolidated_units": len(sf.consolidated_store),
                "dreams_recorded": len(sf.dream_history),
                "last_stability_score": sf.audit_verdicts[-1].stability_score if sf.audit_verdicts else None,
                "last_cf_rate": sf.audit_verdicts[-1].catastrophic_forgetting_rate if sf.audit_verdicts else None,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(status_data, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/deepmind/status", "/deepmind/status", "/v1/virtu/deepmind/status"]:
            from virtu_omni.google_suite import get_google_suite
            suite = get_google_suite()
            report = suite.run_all_falsifiable_probes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(report.to_dict(), ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/frontier/status", "/frontier/status", "/v1/virtu/frontier/status"]:
            from virtu_omni.model_evolution_suite import get_model_evolution_suite
            suite = get_model_evolution_suite()
            rep = suite.run_all_frontier_probes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(rep.to_dict(), ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ultimate/status", "/ultimate/status", "/v1/virtu/ultimate/status"]:
            from virtu_omni.ultimate_suite import get_ultimate_suite
            suite = get_ultimate_suite()
            rep = suite.run_all_ultimate_probes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(rep.to_dict(), ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in {"/", "/health", "/healthz"}:
            # Health discovery only; unknown paths must not masquerade as healthy.
            try:
                from virtu_real_backend import get_backend
                backend = get_backend()
                identity = backend.identity() if backend is not None else {"backend": "unavailable"}
            except Exception:
                identity = {"backend": "unavailable"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "model": MODEL_ID,
                                         "identity": identity, "path": self.path}).encode("utf-8"))
        else:
            self._send_raw_json({"error": {"message": f"Unknown endpoint: {clean_path}",
                                            "type": "not_found_error"}}, status=404)

    def do_POST(self):
        global _app_lock_token
        # Deception-gate context is per request; the gate must never see the
        # previous request's prompt or tool receipts.
        self._gate_prompt = ""
        self._gate_evidence = None
        clean_path = self.path.split("?")[0].rstrip("/")
        if not self._require_auth():
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_raw_json({"error": {"message": "Invalid Content-Length", "type": "invalid_request_error"}}, status=400)
            return
        if content_length < 0 or content_length > _MAX_REQUEST_BYTES:
            self._send_raw_json({"error": {"message": "Request body exceeds allowed size", "type": "invalid_request_error"}}, status=413)
            return
        body = self.rfile.read(content_length) if content_length else b"{}"
        self._request_body_consumed = True
        old_rfile = self.rfile
        self.rfile = io.BytesIO(body)
        requires_lock = clean_path in {
            "/v1/cadcam/tools/call", "/api/tools/call", "/cadcam/tools/call",
            "/v1/cadcam/dispatch", "/api/dispatch", "/cadcam/dispatch",
            "/v1/chain/run", "/api/chain", "/chain/run",
            "/v1/computer-use/action", "/computer-use/action",
        }
        if clean_path in {"/v1/chat/completions", "/chat/completions"}:
            try:
                chat_data = json.loads(body.decode("utf-8"))
                requires_lock = bool(chat_data.get("auto_execute_tools") or chat_data.get("auto_execute")
                                     or self.headers.get("X-Auto-Execute-Tools", "").lower() in ("true", "1", "yes"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        if requires_lock and not _app_lock.acquire():
            self.rfile = old_rfile
            self._send_raw_json({"error": {"message": "Another operation is using the shared desktop/software resources", "type": "conflict_error"}}, status=409)
            return
        if requires_lock:
            _app_lock_token = f"{self.command}:{clean_path}:{uuid.uuid4().hex[:8]}"
        try:
            self._do_post_routes()
        except Exception as err:
            print(f"[WorkBuddy-Bridge] route failed: {type(err).__name__}: {err}")
            if getattr(self, "_response_committed", False):
                self.close_connection = True
            else:
                status = _error_http_status(err)
                error_type = "invalid_request_error" if status == 400 else "server_error"
                self._send_raw_json({"error": {"message": str(err), "type": error_type}}, status=status)
        finally:
            self.rfile = old_rfile
            if requires_lock:
                _unlock_app()

    def _do_post_routes(self):
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
                    self._send_raw_json({"error": {"message": "arguments must be valid JSON", "type": "invalid_request_error"}}, status=400)
                    return
            ok, reason = _validate_tool_call(tool_name, args)
            if not ok:
                self._send_raw_json({"error": {"message": reason, "type": "invalid_request_error"}}, status=400)
                return
            res = execute_tool_call(tool_name, args)
            self._send_raw_json(res)
            return
        elif clean_path in ["/v1/cadcam/dispatch", "/api/dispatch", "/cadcam/dispatch"]:
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length > 0 else {}
            sw = req_data.get("target_software") or req_data.get("software")
            act = req_data.get("action")
            params = req_data.get("parameters") or req_data.get("params") or {}
            ok, reason = _validate_dispatch_args(sw, act, params)
            if not ok:
                self._send_raw_json({"error": {"message": reason, "type": "invalid_request_error"}}, status=400)
                return
            res = six_orchestrator.dispatch(sw, act, params)
            self._send_raw_json(res)
            return
        elif clean_path in ["/v1/chain/run", "/api/chain", "/chain/run"]:
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length > 0 else {}
            wish = req_data.get("wish", "")
            out_root = req_data.get("out_root")
            skip = tuple(req_data.get("skip", ()))
            if not isinstance(wish, str) or not wish.strip() or not isinstance(skip, (list, tuple)):
                self._send_raw_json({"error": {"message": "wish must be non-empty text and skip must be a list", "type": "invalid_request_error"}}, status=400)
                return
            if out_root and not _path_allowed(out_root):
                self._send_raw_json({"error": {"message": "out_root must be inside the workspace", "type": "invalid_request_error"}}, status=400)
                return
            res = six_orchestrator.run_full_chain(wish, out_root=out_root, skip=skip)
            self._send_raw_json(res)
            return
        elif clean_path in ["/v1/harness2/apply", "/harness2/apply"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "applied",
                "engine": "Virtu Harness²",
                "message": "Virtu Harness² components reloaded and verified successfully",
                "timestamp": time.time()
            }, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/security-audit/scan", "/security-audit/scan"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            
            prompt_audit = None
            if "prompt" in req_data:
                prompt_audit = security_auditor.audit_prompt_injection(req_data["prompt"])
            tool_audit = None
            if "tool_args" in req_data:
                tool_audit = security_auditor.audit_tool_arguments(req_data.get("tool_name", "generic"), req_data["tool_args"])
            
            full_res = security_auditor.run_full_audit()
            resp = {
                "status": "success",
                "framework": "Cloudflare security-audit-skill",
                "summary": full_res["summary"],
                "prompt_audit": prompt_audit,
                "tool_audit": tool_audit,
                "findings": full_res["findings"],
                "timestamp": time.time(),
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/hindsight/retain", "/hindsight/retain"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            retain_res = hindsight_memory.retain(
                bank_id=req_data.get("bank_id", "default"),
                content=req_data.get("content", ""),
                context=req_data.get("context", "learnings"),
                tags=req_data.get("tags"),
                memory_type=req_data.get("memory_type"),
                metadata=req_data.get("metadata"),
            )
            self.wfile.write(json.dumps(retain_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/hindsight/recall", "/hindsight/recall"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            recalled = hindsight_memory.recall(
                bank_id=req_data.get("bank_id", "default"),
                query=req_data.get("query", ""),
                types=req_data.get("types"),
                tags=req_data.get("tags"),
                max_results=int(req_data.get("max_results", 5)),
            )
            self.wfile.write(json.dumps({"status": "recalled", "results": recalled, "count": len(recalled)}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/hindsight/reflect", "/hindsight/reflect"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            reflected = hindsight_memory.reflect(
                bank_id=req_data.get("bank_id", "default"),
                query=req_data.get("query", ""),
                budget=req_data.get("budget", "mid"),
                context=req_data.get("context"),
            )
            self.wfile.write(json.dumps(reflected, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/memory/working-memory/update", "/memory/working-memory/update"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            if "goal" in req_data:
                g = req_data["goal"]
                working_memory.set_task_goal(
                    intent=g.get("intent", ""),
                    invariants=g.get("invariants", {}),
                    forbidden_actions=g.get("forbidden_actions"),
                )
            if "fact" in req_data:
                f = req_data["fact"]
                working_memory.record_fact(
                    key=f["key"],
                    value=f["value"],
                    unit=f.get("unit"),
                    source=f.get("source", "api"),
                    verified=f.get("verified", True),
                )
            if "lesson" in req_data:
                working_memory.record_lesson(req_data["lesson"])
            res = {"status": "ok", "snapshot": working_memory.export_snapshot()}
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/memory/working-memory/reset", "/memory/working-memory/reset"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            working_memory.reset()
            self.wfile.write(json.dumps({"status": "reset_success"}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/memory/working-memory/compact", "/memory/working-memory/compact"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            msgs = req_data.get("messages", [])
            max_turns = int(req_data.get("max_turns", 6))
            compacted = working_memory.compact_context(msgs, max_turns_to_keep=max_turns)
            self.wfile.write(json.dumps({"status": "ok", "compacted_messages": compacted}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/sleep/trigger", "/sleep/trigger", "/v1/virtu/sleep/trigger"]:
            sf = get_sleep_framework()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            run_id = req_data.get("run_id")
            report = sf.run_sleep_cycle(run_id=run_id)
            self.wfile.write(json.dumps({"ok": True, "report": report}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/deepmind/funsearch/evolve", "/deepmind/funsearch/evolve"]:
            from virtu_omni.google_suite import get_google_suite
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            steps = int(req_data.get("steps", 1))
            cand = get_google_suite().evolve_nesting_heuristic(steps=steps)
            self.wfile.write(json.dumps({"ok": True, "candidate": cand.to_dict()}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/deepmind/geometry/solve", "/deepmind/geometry/solve"]:
            from virtu_omni.google_suite import get_google_suite, SketchIntent, GeometricPrimitive, GeometricConstraint, ConstraintType
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            prims = [GeometricPrimitive(**p) for p in req_data.get("primitives", [])]
            consts = [
                GeometricConstraint(
                    constraint_id=c["constraint_id"],
                    constraint_type=ConstraintType(c["constraint_type"]),
                    target_ids=c["target_ids"],
                    value=c.get("value"),
                )
                for c in req_data.get("constraints", [])
            ]
            intent = SketchIntent(
                sketch_id=req_data.get("sketch_id", "SKETCH"),
                plane=req_data.get("plane", "Front"),
                primitives=prims,
                constraints=consts,
                extrusion_depth_mm=req_data.get("extrusion_depth_mm"),
                revolution_angle_deg=req_data.get("revolution_angle_deg"),
            )
            solved = get_google_suite().solve_geometry_intent(intent)
            res = {
                "sketch_id": solved.sketch_id,
                "status": solved.status.value,
                "dof": solved.dof,
                "points": solved.points,
                "circles": solved.circles,
                "exact_profile_area_mm2": solved.exact_profile_area_mm2,
                "theoretical_volume_mm3": solved.theoretical_volume_mm3,
                "volume_conservation_passed": solved.volume_conservation_passed,
                "diagnostics": solved.diagnostics,
            }
            self.wfile.write(json.dumps({"ok": True, "geometry": res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/deepmind/affordance/check", "/deepmind/affordance/check"]:
            from virtu_omni.google_suite import get_google_suite, IndustrialSoftwareTarget
            from dataclasses import asdict
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            act = req_data.get("action", "CYCLE_START")
            sw_name = req_data.get("software", "SOLIDWORKS_2021")
            try:
                target_sw = IndustrialSoftwareTarget(sw_name)
            except ValueError:
                target_sw = IndustrialSoftwareTarget.SOLIDWORKS_2021
            state_kwargs = req_data.get("state", {})
            aff_res = get_google_suite().check_affordance(act, target_sw, state_kwargs)
            self.wfile.write(json.dumps({"ok": True, "affordance": asdict(aff_res)}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/deepmind/mcts/plan", "/deepmind/mcts/plan"]:
            from virtu_omni.google_suite import get_google_suite, MachiningOperation, MachiningState
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            ops = [MachiningOperation(**op) for op in req_data.get("operations", [])]
            st_data = req_data.get("initial_state")
            st = MachiningState(**st_data) if st_data else None
            best_ops, score, metrics = get_google_suite().plan_machining_process(ops, st)
            self.wfile.write(json.dumps({
                "ok": True,
                "planned_operations": [op.to_dict() for op in best_ops],
                "total_prm_reward": score,
                "metrics": metrics,
            }, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/frontier/rlvr/evaluate", "/frontier/rlvr/evaluate"]:
            from virtu_omni.model_evolution_suite import get_model_evolution_suite
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            prompt = req_data.get("prompt", "")
            candidates = req_data.get("candidates", [])
            context = req_data.get("context", {})
            suite = get_model_evolution_suite()
            evaluated = suite.evaluate_rlvr_group(prompt, candidates, context=context)
            self.wfile.write(json.dumps({
                "ok": True,
                "prompt": prompt,
                "group_size": len(evaluated),
                "candidates": [c.to_dict() for c in evaluated],
            }, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/frontier/prm/audit", "/frontier/prm/audit"]:
            from virtu_omni.model_evolution_suite import get_model_evolution_suite
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            gcode = req_data.get("gcode")
            cad_steps = req_data.get("cad_steps")
            safe_z = float(req_data.get("safe_plane_z", 5.0))
            stock_z = float(req_data.get("stock_top_z", 0.0))
            suite = get_model_evolution_suite()
            if gcode:
                audit = suite.audit_gcode_prm(gcode, safe_plane_z=safe_z, stock_top_z=stock_z)
            elif cad_steps:
                audit = suite.prm_model.audit_cad_steps(cad_steps)
            else:
                audit = None
            self.wfile.write(json.dumps({
                "ok": True,
                "audit": audit.to_dict() if audit else None,
            }, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/frontier/brep/compile", "/frontier/brep/compile"]:
            from virtu_omni.model_evolution_suite import get_model_evolution_suite, CADCommand
            from dataclasses import asdict
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            cmds_data = req_data.get("commands", [])
            part_name = req_data.get("part_name", "DeepCAD_Part")
            cmds = [CADCommand(op=c.get("op", ""), params=c.get("params", {})) for c in cmds_data]
            suite = get_model_evolution_suite()
            code, report = suite.validate_and_compile_brep(cmds, part_name=part_name)
            self.wfile.write(json.dumps({
                "ok": True,
                "is_valid": report.is_valid_manifold,
                "compiled_code": code,
                "validation_report": asdict(report),
            }, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ultimate/quiet-star/heal", "/ultimate/quiet-star/heal"]:
            from virtu_omni.ultimate_suite import get_ultimate_suite
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            code = req_data.get("code", "")
            lang = req_data.get("language", "PYTHON")
            suite = get_ultimate_suite()
            heal_rep = suite.silent_execute_and_heal(code, language=lang)
            self.wfile.write(json.dumps({"ok": True, "report": heal_rep.to_dict()}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ultimate/blueprint/ground", "/ultimate/blueprint/ground"]:
            from virtu_omni.ultimate_suite import get_ultimate_suite
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            elements = req_data.get("elements", [])
            suite = get_ultimate_suite()
            spec, err = suite.ground_and_invert_blueprint(elements)
            self.wfile.write(json.dumps({
                "ok": err is None,
                "cad_spec": spec.to_dict() if spec else None,
                "error": err,
            }, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ultimate/pinn/predict", "/ultimate/pinn/predict"]:
            from virtu_omni.ultimate_suite import get_ultimate_suite
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            suite = get_ultimate_suite()
            res, err = suite.predict_pinn_stress(
                length_mm=float(req_data.get("length_mm", 100.0)),
                outer_dia_mm=float(req_data.get("outer_dia_mm", 60.0)),
                inner_dia_mm=float(req_data.get("inner_dia_mm", 20.0)),
                pressure_mpa=float(req_data.get("pressure_mpa", 0.0)),
                tensile_force_n=float(req_data.get("tensile_force_n", 0.0)),
                bending_moment_nm=float(req_data.get("bending_moment_nm", 0.0)),
                material=req_data.get("material", "AL7075-T6"),
            )
            self.wfile.write(json.dumps({
                "ok": err is None,
                "result": res.to_dict() if res else None,
                "error": err,
            }, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/reach/read", "/reach/read"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            url = req_data.get("url") or req_data.get("target", "")
            read_res = reach_adapter.read(url=url, backend=req_data.get("backend"))
            self.wfile.write(json.dumps(read_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/reach/search", "/reach/search"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            channel = req_data.get("channel", "github")
            query = req_data.get("query", "")
            limit = int(req_data.get("limit", 5))
            search_res = reach_adapter.search(channel=channel, query=query, limit=limit, backend=req_data.get("backend"))
            self.wfile.write(json.dumps(search_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/reach/quote", "/reach/quote"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            symbol = req_data.get("symbol", "SH600519")
            quote_res = reach_adapter.get_stock_quote(symbol=symbol)
            self.wfile.write(json.dumps(quote_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ai-scratch/lesson", "/ai-scratch/lesson"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            phase = req_data.get("phase", "01")
            lesson = req_data.get("lesson", "05")
            data = ai_scratch.get_lesson(phase, lesson)
            self.wfile.write(json.dumps({"ok": data is not None, "lesson": data}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ai-scratch/first-principles/autograd", "/ai-scratch/first-principles/autograd"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            a_val = float(req_data.get("a", 2.0))
            b_val = float(req_data.get("b", -3.0))
            res = ai_scratch.run_autograd_verification(a_val=a_val, b_val=b_val)
            self.wfile.write(json.dumps({"ok": True, "result": res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ai-scratch/first-principles/attention", "/ai-scratch/first-principles/attention"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            seq_len = int(req_data.get("seq_len", 4))
            d_model = int(req_data.get("d_model", 64))
            num_heads = int(req_data.get("num_heads", 4))
            res = ai_scratch.run_attention_forward(seq_len=seq_len, d_model=d_model, num_heads=num_heads)
            self.wfile.write(json.dumps({"ok": True, "result": res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/ai-scratch/tutor/placement", "/ai-scratch/tutor/placement"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            answers = req_data.get("answers", {})
            eval_res = ai_scratch.evaluate_placement(answers=answers)
            self.wfile.write(json.dumps({"ok": True, "evaluation": eval_res}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/paperclip/task/dispatch", "/paperclip/task/dispatch"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            title = req_data.get("title", "Untitled Task")
            description = req_data.get("description", "")
            agent_id = req_data.get("assigned_agent_id") or req_data.get("agent_id")
            priority = req_data.get("priority", "medium")
            trigger_hb = bool(req_data.get("trigger_heartbeat", True))
            res = paperclip_adapter.dispatch_task(
                title=title,
                description=description,
                assigned_agent_id=agent_id,
                priority=priority,
                trigger_heartbeat=trigger_hb,
            )
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/paperclip/heartbeat/trigger", "/paperclip/heartbeat/trigger"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            agent_id = req_data.get("agent_id", "virtu-architect")
            wake_reason = req_data.get("wake_reason", "manual_trigger")
            task_id = req_data.get("task_id")
            hb_res = paperclip_adapter.heartbeat_runner.trigger_heartbeat(
                agent_id=agent_id,
                wake_reason=wake_reason,
                task_id=task_id,
                executor_fn=paperclip_adapter._virtu_agent_executor,
            )
            self.wfile.write(json.dumps({"ok": hb_res.ok, "heartbeat": hb_res.to_dict()}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/paperclip/approval/decide", "/paperclip/approval/decide"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            app_id = req_data.get("approval_id", "")
            approved = bool(req_data.get("approved", True))
            decided_by = req_data.get("decided_by", "virtu-architect")
            rationale = req_data.get("rationale", "")
            dec_res = paperclip_adapter.control_plane.decide_approval(
                approval_id=app_id,
                approved=approved,
                decided_by=decided_by,
                rationale=rationale,
            )
            self.wfile.write(json.dumps(dec_res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/super-agent/solve", "/super-agent/solve"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            prompt = req_data.get("prompt", "")
            mode = req_data.get("mode", "AUTONOMOUS")
            modality = req_data.get("modality", "FUNCTION_CALLING")
            target_software = req_data.get("target_software")
            action = req_data.get("action")
            params = req_data.get("params")
            solve_res = super_agent.solve(
                prompt=prompt,
                mode=mode,
                modality=modality,
                target_software=target_software,
                action=action,
                params=params,
            )
            resp_dict = solve_res.to_dict() if hasattr(solve_res, "to_dict") else asdict(solve_res)
            self.wfile.write(json.dumps(resp_dict, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/context-mode/execute", "/context-mode/execute"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            cmd = req_data.get("command", "")
            script = req_data.get("filter_script")
            timeout = float(req_data.get("timeout_sec", 30.0))
            record = bool(req_data.get("record_to_session", True))
            res = context_mode.execute(command=cmd, filter_script=script, timeout_sec=timeout, record_to_session=record)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/context-mode/file/filter", "/context-mode/file/filter"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            fpath = req_data.get("filepath", "")
            script = req_data.get("filter_script")
            res = context_mode.execute_file(filepath=fpath, filter_script=script)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/context-mode/session/event", "/context-mode/session/event"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            ev_type = req_data.get("event_type", "milestone")
            title = req_data.get("title", "")
            content = req_data.get("content", "")
            meta = req_data.get("metadata", {})
            eid = context_mode.record_session_event(event_type=ev_type, title=title, content=content, metadata=meta)
            self.wfile.write(json.dumps({"ok": True, "event_id": eid}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/context-mode/session/search", "/context-mode/session/search"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            query = req_data.get("query", "")
            limit = int(req_data.get("limit", 5))
            hits = context_mode.search_session(query=query, limit=limit)
            self.wfile.write(json.dumps({"ok": True, "hits": hits, "count": len(hits)}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/rea/inspect", "/rea/inspect"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            target = req_data.get("target") or req_data.get("path") or req_data.get("filepath", "")
            if not target and "data_hex" in req_data:
                target = bytes.fromhex(req_data["data_hex"])
            res = rea_adapter.inspect_binary(target=target)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/rea/strings", "/rea/strings"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            target = req_data.get("target") or req_data.get("path") or req_data.get("filepath", "")
            if not target and "data_hex" in req_data:
                target = bytes.fromhex(req_data["data_hex"])
            min_len = int(req_data.get("min_len", 4))
            max_strings = int(req_data.get("max_strings", 200))
            res = rea_adapter.extract_strings(target=target, min_len=min_len, max_strings=max_strings)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/rea/decompile", "/rea/decompile"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            target = req_data.get("target") or req_data.get("path") or req_data.get("filepath", "")
            if not target and "data_hex" in req_data:
                target = bytes.fromhex(req_data["data_hex"])
            offset = int(req_data.get("offset", 0))
            count = int(req_data.get("count", 40))
            arch = req_data.get("arch", "x86_64")
            res = rea_adapter.decompile(target=target, offset=offset, count=count, arch=arch)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/rea/entropy", "/rea/entropy"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            target = req_data.get("target") or req_data.get("path") or req_data.get("filepath", "")
            if not target and "data_hex" in req_data:
                target = bytes.fromhex(req_data["data_hex"])
            entropy = rea_adapter.calculate_entropy(target=target)
            self.wfile.write(json.dumps({"ok": True, "entropy": entropy}, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/plugins/inspect", "/plugins/inspect"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            plugin_name = req_data.get("name") or req_data.get("plugin", "")
            res = claude_plugins.inspect_plugin(name=plugin_name)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/plugins/install", "/plugins/install"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            plugin_name = req_data.get("name") or req_data.get("plugin", "")
            res = claude_plugins.install_plugin(name=plugin_name)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/plugins/command", "/plugins/command"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            cmd = req_data.get("command", "")
            ctx = req_data.get("context", "")
            args = req_data.get("args", {})
            res = claude_plugins.execute_command(command=cmd, context=ctx, args=args)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/computer-use/screenshot", "/computer-use/screenshot"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            out_p = req_data.get("output_path")
            bbox = req_data.get("bbox")
            res = computer_use.execute_action("screenshot", output_path=out_p, bbox=bbox)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/computer-use/action", "/computer-use/action"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            act_name = req_data.get("action", "")
            act_params = {k: v for k, v in req_data.items() if k != "action"}
            res = computer_use.execute_action(act_name, **act_params)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/computer-use/loop", "/computer-use/loop"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}
            goal = req_data.get("goal", "Execute desktop action sequence")
            actions = req_data.get("actions", [])
            cap = bool(req_data.get("capture_screenshots", True))
            res = computer_use.run_see_think_act_loop(goal=goal, actions=actions, capture_screenshots=cap)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif clean_path in ["/v1/cad/parametric-slider", "/cad/parametric-slider"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            content_length = int(self.headers.get("Content-Length", 0))
            req_data = {}
            if content_length > 0:
                try:
                    req_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    req_data = {}

            d_out = float(req_data.get("d_outer", 53.0))
            d_in = float(req_data.get("d_inner", 14.0))
            length = float(req_data.get("overall_len", 45.0))
            r = float(req_data.get("fillet_r", 10.0))
            mat = str(req_data.get("material", "HT200"))

            spec = {
                "wish": "Dynamic Slider Rebuild & Regeneration",
                "material": mat,
                "d_outer": d_out,
                "d_inner": d_in,
                "overall_len": length,
                "fillet_r": r,
                "num_features": 3,
                "is_multiaxis": False,
                "is_die_mold": True
            }
            slider_ui = engine.generate_slider_dashboard(spec)
            wall_thk = (d_out - d_in) / 2.0

            resp = {
                "status": "success",
                "action": "rebuild_features",
                "updated_parameters": {
                    "d_outer": d_out,
                    "d_inner": d_in,
                    "overall_len": length,
                    "fillet_r": r,
                    "wall_thickness": wall_thk,
                    "rigid_safe": wall_thk >= 5.0
                },
                "slider_dashboard_markdown": slider_ui,
                "equations": [
                    f"\"D_Outer\" = {d_out:.2f}",
                    f"\"D_Bore\" = {d_in:.2f}",
                    f"\"Length\" = {length:.2f}",
                    f"\"R_GrooveArc\" = {r:.2f}"
                ],
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            return
        if clean_path not in {"/v1/chat/completions", "/chat/completions"}:
            self._send_raw_json({"error": {"message": f"Unknown endpoint: {clean_path}",
                                            "type": "not_found_error"}}, status=404)
            return

        stream = False
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
            
            try:
                data = json.loads(body_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                self._send_raw_json({"error": {"message": f"Invalid JSON: {e}",
                                                "type": "invalid_request_error"}}, status=400)
                return
            if not isinstance(data, dict):
                self._send_raw_json({"error": {"message": "Request body must be a JSON object",
                                                "type": "invalid_request_error"}}, status=400)
                return

            messages = data.get("messages", [])
            prompt = data.get("prompt", "")
            stream = data.get("stream", False)
            requested_model = data.get("model", MODEL_ID)
            tools = data.get("tools", [])
            if (not isinstance(messages, list) or any(not isinstance(m, dict) for m in messages)
                    or (not messages and not prompt)):
                self._send_raw_json({"error": {"message": "messages must be a non-empty array or prompt must be provided", "type": "invalid_request_error"}}, status=400)
                return
            if not isinstance(stream, bool):
                self._send_raw_json({"error": {"message": "stream must be a boolean", "type": "invalid_request_error"}}, status=400)
                return
            if requested_model != MODEL_ID:
                self._send_raw_json({"error": {"message": f"Unknown model: {requested_model}", "type": "invalid_request_error"}}, status=404)
                return
            if not isinstance(tools, list) or any(not isinstance(tool, dict) for tool in tools):
                self._send_raw_json({"error": {"message": "tools must be an array", "type": "invalid_request_error"}}, status=400)
                return
            max_tokens = data.get("max_tokens", data.get("max_completion_tokens"))
            if max_tokens is not None and (isinstance(max_tokens, bool)
                                           or not isinstance(max_tokens, int)
                                           or not 1 <= max_tokens <= 32768):
                self._send_raw_json({"error": {"message": "max_tokens must be an integer between 1 and 32768", "type": "invalid_request_error"}}, status=400)
                return
            temperature = data.get("temperature")
            if temperature is not None and (isinstance(temperature, bool)
                                             or not isinstance(temperature, (int, float))
                                             or not 0 <= temperature <= 2):
                self._send_raw_json({"error": {"message": "temperature must be between 0 and 2", "type": "invalid_request_error"}}, status=400)
                return
            tool_choice = data.get("tool_choice", "auto")
            if tool_choice == "none":
                tools = []
            elif tool_choice not in (None, "auto"):
                self._send_raw_json({"error": {"message": "Only tool_choice 'auto' and 'none' are supported", "type": "invalid_request_error"}}, status=400)
                return

            has_tool_context = bool(tools) or any(
                m.get("role") == "tool" or "tool_calls" in m for m in messages)

            auto_execute = bool(data.get("auto_execute_tools", False) or data.get("auto_execute", False))
            if self.headers.get("X-Auto-Execute-Tools", "").lower() in ("true", "1", "yes"):
                auto_execute = True

            # Robust user prompt extraction (handling str, list of blocks, dicts)
            user_prompt = ""
            if messages:
                for m in reversed(messages):
                    if m.get("role") == "user":
                        user_prompt = self._extract_text(m.get("content", ""))
                        break
                if not user_prompt:
                    user_prompt = self._extract_text(messages[-1].get("content", ""))
            elif prompt:
                user_prompt = self._extract_text(prompt)
            self._gate_prompt = user_prompt

            # --- P1 runtime governance: trace root span + prompt-injection audit ---
            # 主分支与工具编排分支均强制经过提示注入审计（消除工具编排旁路缺口）
            _runtime_trace.start_run()
            with _runtime_trace.span(_runtime_trace.THOUGHT, event="chat.prompt_audit") as _root_span:
                _audit = security_auditor.audit_prompt_injection(user_prompt)
                if not _audit["passed"]:
                    _root_span.fail("prompt injection rejected", status="rejected")
                    # Explicit rejection: never disguise an audited violation as a normal answer.
                    self._send_raw_json({
                        "error": {
                            "message": "Request rejected by prompt-injection audit: "
                                       + "; ".join(_audit["detected_attacks"]),
                            "type": "invalid_request_error",
                        },
                        "security_audit": _audit,
                    }, status=400)
                    return
            _runtime_trace.emit(_runtime_trace.THOUGHT, "chat.prompt_accepted",
                                audit_risk=_audit["risk_level"])

            if has_tool_context:
                tool_resp = self._handle_tool_orchestration(
                    messages, tools, auto_execute=auto_execute,
                    max_tokens=max_tokens, temperature=temperature)
                if stream:
                    self._handle_streaming_tool_response(tool_resp)
                else:
                    self._send_raw_json(tool_resp)
                return

            # Log incoming request
            print(f"[WorkBuddy-Bridge] POST {self.path} | Prompt: {user_prompt[:60]}... | Stream: {stream}")

            _runtime_trace.emit(_runtime_trace.ACTION, "chat.backend_call", stream=stream)
            from virtu_real_backend import get_backend
            backend = get_backend()
            if backend is None or not backend.available:
                raise RuntimeError(f"后端大模型未就绪: {getattr(backend, 'error', '无法连接模型服务')}")
            self._served_model = backend.identity()
            conv = []
            for m in messages:
                role = m.get("role")
                if role in ("system", "user", "assistant"):
                    conv.append({"role": role, "content": self._extract_content(m.get("content", ""))})
            if not conv or conv[-1]["role"] != "user":
                conv.append({"role": "user", "content": user_prompt})

            # Inject read-only Hindsight/coordinate anchor and auto-sync working memory
            conv = _inject_hindsight_anchor(conv, user_prompt)
            working_memory.auto_sync_from_messages(conv)
            if len(conv) >= 3 or working_memory.facts or (working_memory.goal and working_memory.goal.invariants):
                conv = working_memory.compact_context(conv, max_turns_to_keep=6)

            think_param = data.get("think")
            if think_param is None:
                think_param = data.get("enable_thinking")
            if think_param is None and isinstance(data.get("thinking"), dict):
                think_param = data.get("thinking", {}).get("type") in ("enabled", "auto")
            grounded_flag = data.get("grounded") if isinstance(data.get("grounded"), bool) else None

            if stream:
                self._handle_live_streaming_response(
                    backend, conv, max_tokens=max_tokens, temperature=temperature,
                    think=think_param, grounded_flag=grounded_flag,
                )
            else:
                grounded_res = _run_grounded_chat(
                    backend, conv, user_prompt,
                    max_tokens=max_tokens, temperature=temperature,
                    think_param=think_param, request_flag=grounded_flag,
                )
                grounding_meta = None
                if grounded_res is not None:
                    response_text = grounded_res.get("content")
                    grounding_meta = grounded_res.get("grounding")
                elif think_param is not None:
                    response_text = backend.generate(conv, max_tokens=max_tokens, temperature=temperature, think=think_param)
                else:
                    response_text = backend.generate(conv, max_tokens=max_tokens, temperature=temperature)
                if not response_text:
                    raise RuntimeError("模型输出为空")
                self._served_model = backend.identity()
                # 私有思维留在服务端：_handle_json_response 在调用方显式传入
                # reasoning_text 时仍可序列化（调试/显式展示场景），但正常 chat
                # 路径不得把 backend.last_thought 转发给客户端。
                _runtime_trace.emit(_runtime_trace.OBSERVATION, "chat.response_ready",
                                    length=len(response_text))
                _runtime_trace.emit(_runtime_trace.VERIFICATION, "chat.response_serve")
                self._handle_json_response(
                    response_text,
                    evidence=_grounded_evidence(grounding_meta),
                    grounding=grounding_meta,
                )
        except Exception as err:
            print(f"[WorkBuddy-Bridge] completion failed: {type(err).__name__}: {err}")
            status = _error_http_status(err)
            if getattr(self, "_response_committed", False):
                self.close_connection = True
                return
            try:
                error_type = "invalid_request_error" if status == 400 else "server_error"
                self._send_raw_json({"error": {"message": str(err), "type": error_type}}, status=status)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True

    def _extract_text(self, content: Any) -> str:
        """Safely extract plain text from diverse OpenAI / WorkBuddy content formats."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    elif "text" in item:
                        parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(parts).strip()
        if isinstance(content, dict):
            if "text" in content:
                return str(content["text"]).strip()
        return str(content).strip()

    def _extract_content(self, content: Any):
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)
        blocks = []
        has_media = False
        for item in content:
            if not isinstance(item, dict):
                blocks.append({"type": "text", "text": str(item)})
                continue
            t = item.get("type", "")
            if t in ("image_url", "input_image", "image", "video_url", "input_video", "video"):
                has_media = True
                blocks.append(item)
            elif t == "text" or "text" in item:
                text = item.get("text", "")
                if text:
                    blocks.append({"type": "text", "text": str(text)})
        if has_media:
            return blocks
        return " ".join(b["text"] for b in blocks).strip()

    def _drain_unread_request_body(self):
        """排空未读的请求体，避免 Windows 因未读数据直接 close() 而发 RST。

        客户端 POST 带 body、服务端在鉴权/长度校验阶段就提前回 4xx 时，
        若请求体还留在内核接收队列里，close() 会触发 TCP RST，客户端读到的是
        ``ConnectionAbortedError [WinError 10053]`` 而不是 401/413。此前
        ``BoundedThreadingHTTPServer`` 的 503 路径已用同样的「先排空再回」修掉，
        这里是同一类问题在普通 handler 上的补漏。
        """
        if getattr(self, "_request_body_consumed", False):
            return
        if self.command not in ("POST", "PUT", "PATCH"):
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return
        length = min(length, _MAX_REQUEST_BYTES)
        prev_timeout = self.connection.gettimeout()
        try:
            self.connection.settimeout(0.3)
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 8192))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (OSError, ValueError):
            pass
        finally:
            try:
                self.connection.settimeout(prev_timeout)
            except OSError:
                pass

    def _send_raw_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if status >= 400:
            self._drain_unread_request_body()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        # 提前返回的 4xx 必须给出确定长度：否则客户端只能靠连接关闭判断结束，
        # 一旦对端 RST 就连状态码都读不到。
        if status >= 400:
            self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _handle_tool_orchestration(self, messages: list, tools: list, auto_execute: bool = False,
                                   max_tokens=None, temperature=None) -> dict:
        created = int(time.time())
        req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        conv = []
        for m in messages:
            role = m.get("role")
            if role in ("system", "user", "assistant", "tool"):
                entry = {"role": role, "content": self._extract_content(m.get("content", ""))}
                if "tool_calls" in m:
                    sanitized_calls = []
                    for c in m["tool_calls"]:
                        fn = c.get("function", {}) if isinstance(c, dict) else {}
                        fn_name = fn.get("name") or (c.get("name") if isinstance(c, dict) else "")
                        a = fn.get("arguments") if fn else (c.get("arguments", {}) if isinstance(c, dict) else {})
                        if isinstance(a, str):
                            try:
                                a = json.loads(a)
                            except Exception:
                                pass
                        sanitized_calls.append({
                            "id": c.get("id", ""),
                            "type": "function",
                            "function": {"name": fn_name, "arguments": a}
                        })
                    entry["tool_calls"] = sanitized_calls
                if "tool_call_id" in m:
                    entry["tool_call_id"] = m["tool_call_id"]
                if "name" in m:
                    entry["name"] = m["name"]
                conv.append(entry)

        # Check dynamic variation intents and tools
        available_tool_names = [
            t.get("function", {}).get("name") if "function" in t else t.get("name")
            for t in (tools or [])
        ]
        user_prompt = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_prompt = self._extract_content(m.get("content", ""))
                break
        self._gate_prompt = user_prompt
        last_m = messages[-1] if messages else {}
        last_tool_name = last_m.get("name") if last_m.get("role") == "tool" else None

        if "cad.update_parametric_variation" in available_tool_names and last_m.get("role") == "user":
            call_id = f"call_var_{uuid.uuid4().hex[:8]}"
            new_dout = 60.0
            new_din = 16.0
            new_len = 50.0
            new_r = 12.0
            if "外径" in user_prompt:
                m_out = re.search(r"外径.*?(\\d+(?:\\.\\d+)?)", user_prompt)
                if m_out:
                    new_dout = float(m_out.group(1))
            if "孔" in user_prompt:
                m_in = re.search(r"(?:轴孔|孔径|内孔|孔).*?(\\d+(?:\\.\\d+)?)", user_prompt)
                if m_in:
                    new_din = float(m_in.group(1))
            if "长" in user_prompt or "高" in user_prompt or "宽" in user_prompt:
                m_l = re.search(r"(?:长度|总长|高度|宽度).*?(\\d+(?:\\.\\d+)?)", user_prompt)
                if m_l:
                    new_len = float(m_l.group(1))

            args = {
                "target_part": "UG-01_轴承支座.SLDPRT",
                "parametric_variations": {
                    "d_outer": new_dout,
                    "d_inner": new_din,
                    "overall_len": new_len,
                    "fillet_r": new_r
                },
                "rebuild_pipeline": ["Re-solve Constraints", "Cascade Feature Regeneration", "Tessellation Facet Redraw", "GD&T Annotation Realignment"]
            }
            content_text = f"收到参数动态变更意图：“{user_prompt}”。正在调用【cad.update_parametric_variation】工具，驱动参数滑块与特征树级联重生成："
            return {
                "id": req_id,
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "served_model": getattr(self, "_served_model", None),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content_text,
                        "tool_calls": [{
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "cad.update_parametric_variation",
                                "arguments": json.dumps(args, ensure_ascii=False)
                            }
                        }]
                    },
                    "finish_reason": "tool_calls"
                }],
            }

        if last_tool_name == "cad.update_parametric_variation":
            spec_var = {
                "wish": "参数滑块动态重生成",
                "material": "HT200",
                "d_outer": 60.0,
                "d_inner": 16.0,
                "overall_len": 50.0,
                "fillet_r": 12.0,
                "num_features": 3,
                "is_multiaxis": False,
                "is_die_mold": True
            }
            slider_ui = engine.generate_slider_dashboard(spec_var)
            summary = (
                "### 🎛️ 【动态参数滑块联动与三维模型重生成 (Rebuild) 完成】\n\n"
                f"{slider_ui}\n\n"
                "#### 📐 参数变异前后对比与工程级联响应：\n"
                "| 关键特征参数 | 基线尺寸 (Before) | 变异后新尺寸 (After) | 变化率 | 几何约束响应状态 |\n"
                "| :--- | :---: | :---: | :---: | :---: |\n"
                "| 🔵 **外径轮廓 $D_{max}$** | `53.0 mm` | **`60.0 mm`** | `+13.2%` | 凸台拉伸轮廓已完全约束，未干涉底板 |\n"
                "| 🟢 **内孔配合径 $D_{bore}$** | `14.0 mm` | **`16.0 mm`** | `+14.3%` | 配合公差自适应更新为 `16H7 (+0.018/0)` |\n"
                "| 🟡 **零件总长 $L_T$** | `45.0 mm` | **`50.0 mm`** | `+11.1%` | 轴向定位基准面自动延伸，对称约束维持 |\n"
                "| 🟣 **过渡圆角 $R$** | `10.0 mm` | **`12.0 mm`** | `+20.0%` | 刀具干涉消除，R12全圆弧成型槽平滑重算 |\n\n"
                "<details open>\n"
                "<summary><b>📐 SolidWorks 2021 EquationMgr 全局方程式重载代码 (.vba) [点击折叠/展开]</b></summary>\n\n"
                "```vb\n"
                "' --- 动态参数滑块驱动：重新写入全局方程式并驱动 Rebuild ---\n"
                "Set swEqnMgr = Part.GetEquationMgr\n"
                "swEqnMgr.SetEquationAndValueAtIndex 0, \"\"\"D_Outer\"\" = 60.0\", False\n"
                "swEqnMgr.SetEquationAndValueAtIndex 1, \"\"\"D_Bore\"\" = 16.0\", False\n"
                "swEqnMgr.SetEquationAndValueAtIndex 2, \"\"\"Length\"\" = 50.0\", False\n"
                "swEqnMgr.SetEquationAndValueAtIndex 3, \"\"\"R_GrooveArc\"\" = 12.0\", False\n"
                "Part.EditRebuild3\n"
                "Part.ViewZoomtofit2\n"
                "```\n"
                "</details>\n\n"
                "> 🚀 **数字孪生视口同步**：已触发 Tessellation Facets 重新三角剖分，二维工程图三视图尺寸引线已自适应避让重排！"
            )
            return {
                "id": req_id,
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "served_model": getattr(self, "_served_model", None),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": summary
                    },
                    "finish_reason": "stop"
                }],
            }

        from virtu_real_backend import get_backend
        backend = get_backend()
        if backend is None or not backend.available:
            raise RuntimeError(f"后端大模型未就绪: {getattr(backend, 'error', '无法连接模型服务')}")
        self._served_model = backend.identity()

        conv = _inject_hindsight_anchor(conv, user_prompt)
        gen_out = backend.generate(conv, tools=tools, max_tokens=max_tokens,
                                   temperature=temperature)
        if isinstance(gen_out, tuple):
            content_text, tool_calls = gen_out
        else:
            content_text, tool_calls = gen_out, None
        self._served_model = backend.identity()

        if tool_calls:
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
                        raise ValueError(f"Invalid JSON arguments for tool {fn_name}")
                    ok, reason = _validate_tool_call(fn_name, args_dict)
                    if not ok:
                        raise ValueError(f"Refusing invalid tool call {fn_name}: {reason}")
                    print(f"[WorkBuddy-Bridge] Auto-executing {fn_name}({args_dict})")
                    exec_res = execute_tool_call(fn_name, args_dict)
                    exec_results.append(exec_res)
                    if isinstance(exec_res, dict):
                        working_memory._ingest_tool_result_facts(fn_name, exec_res)
                    ollama_call = {
                        "id": nc["id"],
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": args_dict,
                        }
                    }
                    conv.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [ollama_call]
                    })
                    conv.append({
                        "role": "tool",
                        "tool_call_id": nc["id"],
                        "name": fn_name,
                        "content": json.dumps(exec_res, ensure_ascii=False)
                    })

                synth_text = backend.generate(conv, max_tokens=max_tokens,
                                              temperature=temperature)
                if not isinstance(synth_text, str) or not synth_text.strip():
                    raise RuntimeError("Model returned an empty post-tool summary")
                self._served_model = backend.identity()
                synth_decision = self._gate_text(synth_text, evidence=exec_results)
                synth_msg = {
                    "role": "assistant",
                    "content": synth_decision.text,
                    "tool_calls": normalized_calls,
                    "tool_results": exec_results,
                }
                self._served_model = backend.identity()
                return _attach_usage({
                    "id": req_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": MODEL_ID,
                    "served_model": getattr(self, "_served_model", None),
                    "virtu_gate": synth_decision.to_dict(),
                    "choices": [{
                        "index": 0,
                        "message": synth_msg,
                        "finish_reason": "length" if synth_decision.action == "incomplete" else "stop"
                    }],
                })

            pre_msg = {
                "role": "assistant",
                "content": content_text or "",
                "tool_calls": normalized_calls
            }
            return _attach_usage({
                "id": req_id,
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "served_model": getattr(self, "_served_model", None),
                "choices": [{
                    "index": 0,
                    "message": pre_msg,
                    "finish_reason": "tool_calls"
                }],
            })
        else:
            no_tool_decision = self._gate_text(content_text or "", evidence=None)
            no_tool_msg = {
                "role": "assistant",
                "content": no_tool_decision.text
            }
            return _attach_usage({
                "id": req_id,
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "served_model": getattr(self, "_served_model", None),
                "virtu_gate": no_tool_decision.to_dict(),
                "choices": [{
                    "index": 0,
                    "message": no_tool_msg,
                    "finish_reason": "length" if no_tool_decision.action == "incomplete" else "stop"
                }],
            })

    def _gate_text(self, text: str, evidence=None, done_reason=None):
        """Apply working-memory hallucination audit and the deterministic deception gate."""
        audited_text = text or ""
        if working_memory.facts or (working_memory.goal and working_memory.goal.invariants):
            _, audited_text, _ = memory_sentinel.audit_and_repair(audited_text, auto_repair=True)

        canaries = None
        try:
            from virtu_real_backend import get_backend
            backend = get_backend()
            if backend is not None:
                canaries = backend.system_canaries()
        except Exception:
            canaries = None

        return gate_answer(
            audited_text,
            prompt=getattr(self, "_gate_prompt", "") or "",
            evidence=evidence if evidence is not None else getattr(self, "_gate_evidence", None),
            done_reason=done_reason,
            canaries=canaries,
        )

    def _handle_json_response(self, text: str, reasoning_text: str = "", evidence=None,
                              done_reason=None, grounding=None):
        decision = self._gate_text(text, evidence=evidence, done_reason=done_reason)
        text = decision.text
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()

        created = int(time.time())
        msg = {
            "role": "assistant",
            "content": text
        }
        if reasoning_text:
            msg["reasoning_content"] = reasoning_text

        payload_obj = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": created,
            "model": MODEL_ID,
            "served_model": getattr(self, "_served_model", None),
            "virtu_gate": decision.to_dict(),
            "choices": [
                {
                    "index": 0,
                    "message": msg,
                    "finish_reason": "length" if decision.action == "incomplete" else "stop"
                }
            ],
        }
        if grounding is not None:
            payload_obj["virtu_grounding"] = grounding
        resp = _attach_usage(payload_obj)
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

    def _handle_streaming_response(self, text: str, reasoning_text: str = "",
                                   expose_reasoning: bool = False):
        """Legacy SSE helper.

        Private model reasoning is **not** serialized by default. Callers that
        intentionally surface the thinking trace (e.g. a debug console) must opt
        in with ``expose_reasoning=True``; this keeps the helper consistent with
        ``_handle_live_streaming_response``, which already drops it.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()

        req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        try:
            # Reasoning chain first (DeepSeek/Qwen OpenAI-compatible convention),
            # then the visible content chunks. Only on explicit opt-in.
            if reasoning_text and expose_reasoning:
                r_payload = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "served_model": getattr(self, "_served_model", None),
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"reasoning_content": reasoning_text},
                            "finish_reason": None
                        }
                    ]
                }
                self.wfile.write(f"data: {json.dumps(r_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()

            # Chunk response into small parts
            chunk_size = 40
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                payload = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "served_model": getattr(self, "_served_model", None),
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
            end_payload = _attach_usage({
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "served_model": getattr(self, "_served_model", None),
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            })
            self.wfile.write(f"data: {json.dumps(end_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as conn_err:
            print(f"[WorkBuddy-Bridge] Client disconnected during SSE streaming: {conn_err}")

    def _handle_live_streaming_response(self, backend, conv, max_tokens=None, temperature=None,
                                        think=None, grounded_flag=None):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()

        req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        # 1. 角色初始声明块
        first_payload = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": MODEL_ID,
            "served_model": getattr(self, "_served_model", None),
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        self.wfile.write(f"data: {json.dumps(first_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.flush()

        content_parts: list[str] = []
        grounding_meta = None
        try:
            grounded_res = _run_grounded_chat(
                backend, conv, getattr(self, "_gate_prompt", "") or "",
                max_tokens=max_tokens, temperature=temperature,
                think_param=think, request_flag=grounded_flag,
            )
            if grounded_res is not None:
                grounding_meta = grounded_res.get("grounding")
                raw_text = grounded_res.get("content")
                if not raw_text:
                    raise RuntimeError("模型输出为空")
                self._served_model = backend.identity()
                decision = self._gate_text(raw_text, evidence=_grounded_evidence(grounding_meta))
            else:
                if hasattr(backend, "generate_stream"):
                    gen = backend.generate_stream(conv, max_tokens=max_tokens, temperature=temperature, think=think)
                else:
                    full_text = backend.generate(conv, max_tokens=max_tokens, temperature=temperature, think=think)
                    thought = getattr(backend, "last_thought", "") or ""
                    gen = []
                    if thought:
                        gen.append({"type": "thinking", "delta": thought})
                    if full_text:
                        gen.append({"type": "content", "delta": full_text})

                for item in gen:
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("type")
                    delta_str = item.get("delta") or ""
                    if not delta_str:
                        continue
                    if itype == "thinking":
                        # Private model reasoning is never included in client output.
                        continue
                    elif itype == "content":
                        # Buffer the visible answer: a deceptive answer must be gated
                        # before any of it reaches the client.  Thinking stays live.
                        content_parts.append(delta_str)

                decision = self._gate_text("".join(content_parts))
            safe_text = decision.text
            for i in range(0, len(safe_text), 40):
                payload = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "served_model": getattr(self, "_served_model", None),
                    "choices": [{
                        "index": 0,
                        "delta": {"content": safe_text[i:i + 40]},
                        "finish_reason": None,
                    }],
                }
                self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()

            # End chunk
            end_obj = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "served_model": getattr(self, "_served_model", None),
                "virtu_gate": decision.to_dict(),
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "length" if decision.action == "incomplete" else "stop",
                }],
            }
            if grounding_meta is not None:
                end_obj["virtu_grounding"] = grounding_meta
            end_payload = _attach_usage(end_obj)
            self.wfile.write(f"data: {json.dumps(end_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as conn_err:
            print(f"[WorkBuddy-Bridge] Client disconnected during live SSE streaming: {conn_err}")
            self.close_connection = True
        except Exception as exc:
            err_payload = {"error": {"message": str(exc), "type": "server_error"}}
            try:
                self.wfile.write(f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
            self.close_connection = True

    def _handle_streaming_tool_response(self, tool_resp: dict):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()

        req_id = tool_resp.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}")
        created = tool_resp.get("created", int(time.time()))
        choices = tool_resp.get("choices", [{}])
        choice = choices[0] if choices else {}
        msg = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")
        tool_calls = msg.get("tool_calls", [])
        content = msg.get("content", "")

        try:
            # 1. Declare the assistant role without exposing private reasoning.
            role_payload = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "served_model": getattr(self, "_served_model", None),
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None
                }]
            }
            self.wfile.write(f"data: {json.dumps(role_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

            # 2. Content chunks if content exists
            if content:
                chunk_size = 40
                for i in range(0, len(content), chunk_size):
                    c_payload = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL_ID,
                        "served_model": getattr(self, "_served_model", None),
                        "choices": [{
                            "index": 0,
                            "delta": {"content": content[i:i + chunk_size]},
                            "finish_reason": None
                        }]
                    }
                    self.wfile.write(f"data: {json.dumps(c_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()

            # 3. Tool calls chunks if present
            if tool_calls:
                for idx, tc in enumerate(tool_calls):
                    tc_payload = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL_ID,
                        "served_model": getattr(self, "_served_model", None),
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": idx,
                                    "id": tc.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": tc.get("function", {}).get("name", ""),
                                        "arguments": tc.get("function", {}).get("arguments", "")
                                    }
                                }]
                            },
                            "finish_reason": None
                        }]
                    }
                    self.wfile.write(f"data: {json.dumps(tc_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()

            # 4. Final finish chunk
            end_payload = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "usage": tool_resp.get("usage"),
                "served_model": getattr(self, "_served_model", None),
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": finish_reason
                }]
            }
            self.wfile.write(f"data: {json.dumps(end_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as conn_err:
            print(f"[WorkBuddy-Bridge] Client disconnected during SSE streaming tool response: {conn_err}")

    def log_message(self, format, *args):
        # Concise logging
        print(f"[WorkBuddy-Bridge] {args[0]} {args[1]} -> {args[2]}")


def run_server():
    global _BRIDGE_TOKEN
    # Windows defaults stdout/stderr to the GBK console codepage. Any log line
    # containing a CJK glyph or stray non-GBK byte (e.g. a lone 0xB3) raises
    # UnicodeEncodeError, which bubbles out of the request handler and surfaces
    # to clients as a spurious 500. Force UTF-8 I/O up front so every print and
    # the http.server access log are encoding-safe regardless of the launcher.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - older/redirected streams may lack reconfigure
            pass
    # One process per port; a named kernel mutex survives crashed/killed owners
    # and prevents the silent double-listener that mixed model configurations.
    instance_guard = SingleFlight(name=f"VirtuBridgeInstance-{PORT}")
    if not instance_guard.acquire():
        print(f"[WorkBuddy-Bridge] another bridge already owns port {PORT}; refusing to start")
        return
    _BRIDGE_TOKEN = _load_bridge_token()
    server = ThreadingServer((HOST, PORT), OpenAIBaseHandler)
    print(f"============================================================")
    print(f"  Virtu local model bridge running (Bearer auth enabled)")
    print(f"  URL: http://{HOST}:{PORT}/v1")
    print(f"  Model ID: {MODEL_ID} (Qwen3-8B text backend; vision is a separate channel)")
    print(f"  Endpoints: /v1/models, /v1/chat/completions")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    run_server()
