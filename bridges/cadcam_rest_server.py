# -*- coding: utf-8 -*-
"""bridges/cadcam_rest_server.py — High-Performance RESTful HTTP Server for CAD/CAM Agent Toolchain.

Exposes the 6-software toolchain as standard HTTP REST endpoints for any Agent framework:
- GET  /health                   -> Health status (unauthenticated, no sensitive data)
- GET  /v1/cadcam/preflight      -> System & software readiness diagnostics
- POST /v1/cadcam/dispatch       -> Direct software dispatch {"target_software", "action", "parameters"}
- GET  /v1/cadcam/tools          -> Export OpenAI/Claude tool calling JSON schemas
- POST /v1/cadcam/tools/call     -> Execute LLM tool call {"name", "arguments"}
- POST /v1/chain/run             -> Execute full 6-software manufacturing pipeline {"wish", "out_root", "skip"}
- POST /v1/cadcam/gui            -> Desktop GUI perception and control {"action", ...}

Zero external dependencies: uses Python standard library `http.server` with multithreading.

安全模型（V-01 修复）
--------------------
旧版本存在三个叠加问题，等价于把整条 CAM 工具链和本机键鼠暴露给任意网页/进程:

1. ``Access-Control-Allow-Origin: *`` 对任意来源放行；
2. ``do_POST`` 三个端点没有任何 token/API key/来源校验；
3. ``/v1/cadcam/gui`` 直连 ``DesktopController``，完全绕过了仓库里唯一的桌面闸门
   ``bridges.desktop_gate``。

现在：

* 除 ``/health`` 外所有端点强制 Bearer / ``X-Virtu-Token`` 鉴权，令牌来源
  ``VIRTU_REST_TOKEN`` 或 ``runs/rest_server/rest_token.txt``（首次自动生成 32 字节
  随机令牌并落盘）；比较使用 ``hmac.compare_digest``，不做明文 ``==``。
* CORS 只回显白名单来源（默认 localhost / 127.0.0.1 任意端口），不再发 ``*``；
  非浏览器请求（无 Origin 头）不受影响。
* ``/v1/cadcam/gui`` 的所有动作一律先过 ``desktop_gate.gate("cadcam_desktop_gui", ...)``，
  闸门不可用即 fail-closed 拒绝（不再"闸门挂了就放行"）。
* 请求体上限 1 MiB，超限直接 413，避免超大 body 打爆内存。
* 监听地址默认回环；绑定非回环地址必须同时显式设置 ``VIRTU_REST_ALLOW_REMOTE=1``
  且显式配置令牌（不接受自动生成的令牌），否则拒绝启动。
"""

import argparse
import hmac
import json
import os
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.software_registry import (
    diagnose_all, SOFTWARE_SPECS, DISPATCH_SOFTWARE_TOOL,
)
from bridges.six_software_orchestrator import SixSoftwareOrchestrator
from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call
from bridges.desktop_controller import DesktopController

try:  # 复用既有安全工具，避免再造一份鉴权实现
    from bridges.bridge_security import bearer_authorized as _bearer_authorized
except Exception:  # pragma: no cover
    def _bearer_authorized(header_value: str, expected_token: str) -> bool:
        scheme, _, supplied = str(header_value or "").partition(" ")
        return bool(expected_token and supplied.strip() and scheme.lower() == "bearer"
                    and hmac.compare_digest(supplied.strip(), expected_token))

REST_TOKEN_ENV = "VIRTU_REST_TOKEN"
REST_AUTH_ENV = "VIRTU_REST_AUTH"
REST_CORS_ENV = "VIRTU_REST_CORS_ORIGINS"
REST_ALLOW_REMOTE_ENV = "VIRTU_REST_ALLOW_REMOTE"

MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MiB

#: REST 动作名 -> desktop_gate 认识的规范动作名
_GUI_ACTION_ALIASES = {
    "type": "type_text",
    "dismiss": "dismiss_dialogs",
    "text": "type_text",
}

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


# ---------------------------------------------------------------------------
# 鉴权
# ---------------------------------------------------------------------------
def auth_mode() -> str:
    """``enforce``（默认）/ ``off``（显式关闭，仅限回环调试）。"""
    mode = str(os.environ.get(REST_AUTH_ENV) or "").strip().lower()
    return "off" if mode == "off" else "enforce"


def token_file_path() -> str:
    return os.path.join(_ROOT, "runs", "rest_server", "rest_token.txt")


def load_or_create_token() -> Tuple[str, bool]:
    """返回 (token, 是否本次自动生成)。"""
    env_token = str(os.environ.get(REST_TOKEN_ENV) or "").strip()
    if env_token:
        return env_token, False
    path = token_file_path()
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                stored = fh.read().strip()
            if stored:
                return stored, False
    except OSError:
        pass
    token = secrets.token_urlsafe(32)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(token)
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token, True


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
def allowed_origins() -> List[str]:
    raw = str(os.environ.get(REST_CORS_ENV) or "").strip()
    if raw:
        return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    return [
        "http://localhost", "http://127.0.0.1",
        "https://localhost", "https://127.0.0.1",
    ]


def origin_allowed(origin: Optional[str]) -> bool:
    if not origin:
        return False
    candidate = str(origin).strip().rstrip("/")
    for pattern in allowed_origins():
        if candidate == pattern or candidate.startswith(pattern + ":"):
            return True
    return False


# ---------------------------------------------------------------------------
# 桌面闸门
# ---------------------------------------------------------------------------
def canonical_gui_action(action: Any) -> str:
    act = str(action or "capture").strip().lower()
    return _GUI_ACTION_ALIASES.get(act, act)


def gui_gate(args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """返回 None 表示放行；返回 dict 即"已拒绝"，内容为闸门裁决。"""
    gate_args = dict(args or {})
    gate_args["action"] = canonical_gui_action(gate_args.get("action"))
    try:
        from bridges import desktop_gate
    except Exception as exc:  # 闸门不可用 -> fail-closed
        return {"status": "blocked", "verdict_code": "DESKTOP_GATE_UNAVAILABLE",
                "detail": "桌面闸门不可导入，拒绝执行 GUI 动作：%s" % exc,
                "input_sent": False}
    try:
        return desktop_gate.gate("cadcam_desktop_gui", gate_args)
    except Exception as exc:  # 闸门内部异常同样 fail-closed
        return {"status": "blocked", "verdict_code": "DESKTOP_GATE_ERROR",
                "detail": "桌面闸门判定异常，拒绝执行：%s" % exc,
                "input_sent": False}


_DISPATCH_SOFTWARE_TOOL = DISPATCH_SOFTWARE_TOOL  # 单一真源：bridges/software_registry.py


def _approval_blocked(tool_name: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """REST 直通端点（dispatch / chain）不经过 execute_tool_call，需单独走审批闸门。

    V-05 的闸门寄居在工具层；但 dispatch 与 chain 是直接调 orchestrator 的旁路，
    不接这一层的话，鉴权后的调用方仍可绕过风险分级直接驱动 6 套软件。
    """
    try:
        from bridges.tool_calling_specs import approval_gate, approval_granted
    except Exception as exc:  # 闸门不可用 -> fail-closed
        return {"status": "blocked", "verdict_code": "TOOL_APPROVAL_UNAVAILABLE",
                "detail": "审批闸门不可导入，拒绝执行：%s" % exc, "input_sent": False}
    try:
        args = dict(payload or {})
        verdict = approval_gate(tool_name, args)
        if verdict is not None and tool_name != "cadcam_dispatch":
            if approval_granted("cadcam_dispatch", args)[0]:
                return None
        return verdict
    except Exception as exc:  # 内部异常同样 fail-closed
        return {"status": "blocked", "verdict_code": "TOOL_APPROVAL_ERROR",
                "detail": "审批闸门判定异常，拒绝执行：%s" % exc, "input_sent": False}


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class CADCAMRESTHandler(BaseHTTPRequestHandler):
    server_version = "CADCAMToolchainREST/1.1"

    # -- 公共 ------------------------------------------------------------
    def _cors_headers(self, origin: Optional[str]) -> Dict[str, str]:
        if not origin_allowed(origin):
            return {}
        return {
            "Access-Control-Allow-Origin": str(origin).strip().rstrip("/"),
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Virtu-Token",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }

    def _send_json(self, status_code: int, data: Any):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in self._cors_headers(self.headers.get("Origin")).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _client_token(self) -> str:
        bearer = self.headers.get("Authorization") or ""
        if bearer:
            return bearer
        return str(self.headers.get("X-Virtu-Token") or "")

    def _require_auth(self) -> bool:
        """鉴权失败时直接写 401 并返回 False。"""
        if auth_mode() == "off":
            return True
        expected, _ = self.__class__.server_token()
        supplied = self._client_token()
        ok = False
        if supplied.startswith("Bearer ") or supplied.startswith("bearer "):
            ok = _bearer_authorized(supplied, expected)
        elif supplied:
            ok = hmac.compare_digest(supplied.strip(), expected)
        if ok:
            return True
        self._send_json(401, {
            "status": "error",
            "message": "Unauthorized: 需要 Authorization: Bearer <token> 或 X-Virtu-Token",
            "verdict_code": "REST_UNAUTHORIZED",
        })
        return False

    @classmethod
    def server_token(cls) -> Tuple[str, bool]:
        token = getattr(cls, "_token_cache", None)
        if not token:
            token = load_or_create_token()
            cls._token_cache = token
        return token

    def _read_json(self) -> Dict[str, Any]:
        try:
            content_len = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            return {"_body_error": "Content-Length 非法"}
        if content_len <= 0:
            return {}
        if content_len > MAX_BODY_BYTES:
            return {"_body_error": "请求体超过 %d 字节上限" % MAX_BODY_BYTES}
        raw = self.rfile.read(content_len).decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            return {"_parse_error": str(exc)}
        if not isinstance(parsed, dict):
            return {"_parse_error": "JSON 顶层必须是 object"}
        return parsed

    # -- HTTP 方法 -------------------------------------------------------
    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if not origin_allowed(origin):
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(204)
        for key, value in self._cors_headers(origin).items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if not path or path == "/health":
            self._send_json(200, {
                "status": "ok",
                "service": "cadcam-toolchain-rest",
                "version": "1.1.0",
                "auth": auth_mode(),
                "supported_software": list(SOFTWARE_SPECS.keys()),
            })
            return

        if not self._require_auth():
            return

        if path in ("/v1/cadcam/preflight", "/api/preflight"):
            self._send_json(200, diagnose_all())
            return

        if path in ("/v1/cadcam/tools", "/api/tools"):
            tools = get_cadcam_tool_definitions()
            self._send_json(200, {"tools": tools, "count": len(tools)})
            return

        self._send_json(404, {"status": "error", "message": "Endpoint not found: %s" % self.path})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if not self._require_auth():
            return

        payload = self._read_json()
        if "_body_error" in payload:
            self._send_json(413, {"status": "error", "message": payload["_body_error"],
                                  "verdict_code": "REST_BODY_TOO_LARGE"})
            return
        if "_parse_error" in payload:
            self._send_json(400, {"status": "error",
                                  "message": "Invalid JSON: %s" % payload["_parse_error"]})
            return

        orch = get_orchestrator()

        # 1. Dispatch action to specific software
        if path in ("/v1/cadcam/dispatch", "/api/dispatch"):
            software = payload.get("target_software") or payload.get("software")
            action = payload.get("action")
            params = payload.get("parameters") or payload.get("params") or {}
            if not software or not action:
                self._send_json(400, {"status": "error",
                                      "message": "Missing 'target_software' or 'action'"})
                return
            dispatch_tool = _DISPATCH_SOFTWARE_TOOL.get(
                str(software).strip().lower(), "cadcam_dispatch"
            )
            gate_payload = dict(params) if isinstance(params, dict) else {}
            gate_payload.update(payload)
            gate_payload["action"] = action
            approval = _approval_blocked(dispatch_tool, gate_payload)
            if approval is not None:
                self._send_json(403, approval)
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
            # 被闸门拦下的调用不是"业务失败"，用 403 让调用方/网关一眼可辨
            code = 403 if isinstance(res, dict) and res.get("status") == "blocked" else 200
            self._send_json(code, res)
            return

        # 3. Full manufacturing pipeline chain
        elif path in ("/v1/chain/run", "/api/chain"):
            wish = payload.get("wish", "")
            if not wish:
                self._send_json(400, {"status": "error", "message": "Missing 'wish' string"})
                return
            out_root = payload.get("out_root")
            skip = tuple(payload.get("skip", ()))
            approval = _approval_blocked("cadcam_run_full_chain", payload)
            if approval is not None:
                self._send_json(403, approval)
                return
            res = orch.run_full_chain(wish, out_root=out_root, skip=skip)
            self._send_json(200, res)
            return

        # 4. Desktop GUI perception and control —— 必须过 desktop_gate
        elif path in ("/v1/cadcam/gui", "/api/gui"):
            blocked = gui_gate(payload)
            if blocked:
                self._send_json(403, blocked)
                return
            action = canonical_gui_action(payload.get("action", "capture"))
            ctl = get_desktop_ctl()
            if action == "capture":
                res = ctl.capture(output_path=payload.get("output_path"),
                                  software=payload.get("software"))
            elif action == "focus":
                res = ctl.focus(payload.get("software", ""))
            elif action == "click":
                res = ctl.click(payload.get("x", 0), payload.get("y", 0),
                                button=payload.get("button", "left"),
                                double=payload.get("double", False))
            elif action == "type_text":
                res = ctl.type_text(payload.get("text", ""))
            elif action == "hotkey":
                res = ctl.hotkey(payload.get("keys", ""))
            elif action == "dismiss_dialogs":
                res = ctl.dismiss_all_dialogs()
            else:
                res = {"status": "error", "message": "Unknown GUI action: %s" % action}
            self._send_json(200, res)
            return

        self._send_json(404, {"status": "error", "message": "Endpoint not found: %s" % self.path})

    def log_message(self, format, *args):
        # 只记方法与路径，不记 Authorization 头
        sys.stderr.write("[%s] [REST API] %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), format % args))


def _is_loopback(host: str) -> bool:
    return str(host or "").strip().lower() in ("127.0.0.1", "localhost", "::1")


def validate_bind(host: str) -> Tuple[bool, str]:
    """绑定非回环地址必须显式允许且显式配置令牌。"""
    if _is_loopback(host):
        return True, ""
    allowed = str(os.environ.get(REST_ALLOW_REMOTE_ENV) or "") == "1"
    if not allowed:
        return False, ("拒绝绑定到非回环地址 %s：需要显式设置 %s=1"
                       % (host, REST_ALLOW_REMOTE_ENV))
    token, generated = load_or_create_token()
    if generated or not str(os.environ.get(REST_TOKEN_ENV) or "").strip():
        return False, ("拒绝绑定到非回环地址 %s：必须通过 %s 显式配置令牌，"
                       "不接受自动生成令牌" % (host, REST_TOKEN_ENV))
    return True, ""


def start_rest_server(host: str = "127.0.0.1", port: int = 8000):
    ok, reason = validate_bind(host)
    if not ok:
        print("[FATAL] %s" % reason, file=sys.stderr)
        raise SystemExit(2)
    token, generated = load_or_create_token()
    if auth_mode() == "off":
        print("[WARN] %s=off，REST 端点无鉴权，仅限本机调试使用！" % REST_AUTH_ENV,
              file=sys.stderr)
    server = ThreadingHTTPServer((host, port), CADCAMRESTHandler)
    print("=" * 70)
    print(" CAD/CAM Agent Toolchain HTTP REST Microservice Started")
    print(" Listening on: http://%s:%s" % (host, port))
    print(" Auth:         %s" % auth_mode())
    if auth_mode() != "off":
        print(" Token file:   %s" % token_file_path())
        if generated:
            print(" Token:        %s  (首次自动生成，请妥善保存)" % token)
        print(" 调用示例:     curl -H \"Authorization: Bearer <token>\" ...")
    print(" Preflight:    http://%s:%s/v1/cadcam/preflight" % (host, port))
    print(" Tools Schema: http://%s:%s/v1/cadcam/tools" % (host, port))
    print(" Dispatch:     POST http://%s:%s/v1/cadcam/dispatch" % (host, port))
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
