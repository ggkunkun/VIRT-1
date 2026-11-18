#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu P1-3 路由层 —— 生产化 HTTP 服务 (零依赖, 仅用标准库)
============================================================
把 virtu_router 的 route/ask 暴露为 HTTP API, 支持并发请求, 内置可观测指标。
设计原则: 不引入任何第三方依赖 (本机 DNS 被拦截, 无法 pip 安装 fastapi/uvicorn),
          直接基于有界线程池的 http.server。

端点:
  GET  /health   健康检查 + 后端模型就绪状态
  GET  /stats    累计请求统计 (路由分布 / 平均延迟 / 平均 tok/s / 错误数)
  GET  /help     端点与配置说明
  POST /route    {prompt}            仅路由判定 (不进生成), 返回完整决策证据
  POST /ask      {prompt,max_tokens} 路由 + 生成 (非流式), 返回回答与决策

启动:
  python router_server.py                      # 默认 127.0.0.1:8800，需要 Bearer token
  ROUTER_PORT=8801 python router_server.py
  ROUTER_MAX_CONCURRENT=4 python router_server.py   # 限制同时进 Ollama 的请求数

宪法合规: 决策对象 (后端模型/嵌入模型) 在 /health 中显式声明; 每次 /ask 的决策证据
          (target/kind/basis/margin/kw_hits) 随响应一并返回, 可审计、可复现。
"""
import os
import sys
import json
import time
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 同名模块冲突修复（2026-11-13）：
# 仓库里存在两个 virtu_router.py —— 根目录的完整版（含 ollama_generate / 联网增强）
# 与 scripts/router/ 下的轻量路由版（含 route/ask）。此前这里用
# ``sys.path.insert(0, HERE); import virtu_router`` 会把**轻量版**注册进全局
# ``sys.modules["virtu_router"]``，于是同进程内后续 ``import virtu_router`` 的代码
# （如 tests/test_internet_augmentation.py、根目录完整版的调用方）拿到的是轻量版，
# 表现为 ``module 'virtu_router' has no attribute 'ollama_generate'``。
# 现改为按文件路径以私有名加载，不再占用公共模块名。
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "_virtu_router_lite", os.path.join(HERE, "virtu_router.py"))
R = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(R)

from bridges.bridge_security import bearer_authorized, ensure_service_token, service_token_path

HOST = os.environ.get("ROUTER_HOST", "127.0.0.1")
PORT = int(os.environ.get("ROUTER_PORT", "8800"))


def _bounded_env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


# These bounds protect JSON parsing, prompt embedding and Ollama generation.
MAX_BODY_BYTES = _bounded_env_int("ROUTER_MAX_BODY_BYTES", 256 * 1024, 1024, 8 * 1024 * 1024)
MAX_PROMPT_CHARS = _bounded_env_int("ROUTER_MAX_PROMPT_CHARS", 32768, 1, 131072)
MAX_TOKENS = _bounded_env_int("ROUTER_MAX_TOKENS", 4096, 1, 8192)
MAX_CONCURRENT = _bounded_env_int("ROUTER_MAX_CONCURRENT", 4, 1, 32)
MAX_HTTP_WORKERS = _bounded_env_int("ROUTER_MAX_HTTP_WORKERS", 16, 1, 64)
_ROUTER_TOKEN = None


# ---------- 可观测指标 ----------
stats_lock = threading.Lock()
stats = {
    "started_at": time.time(),
    "total": 0,
    "by_kind": {},          # FAST(dense) / HARD(moe) 计数
    "by_basis": {},         # keyword / semantic 计数
    "lat_sum": 0.0,         # 累计端到端延迟 (秒, 仅成功请求)
    "tok_sum": 0,           # 累计生成 token
    "err": 0,
    "max_concurrent_seen": 0,
}
sem = threading.BoundedSemaphore(MAX_CONCURRENT)
_active = 0


class BoundedThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server with a hard cap on accepted handler threads."""
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, server_address, request_handler_class):
        self._worker_slots = threading.BoundedSemaphore(MAX_HTTP_WORKERS)
        super().__init__(server_address, request_handler_class)

    def process_request(self, request, client_address):
        if not self._worker_slots.acquire(blocking=False):
            # 容量耗尽：明确回 503，而不是把连接晾着。
            # Windows 细节：若带着未读的请求数据直接 close()，内核会发 RST，
            # 客户端只能看到 ConnectionAbortedError（WinError 10053）而读不到 503。
            # 因此先写响应 -> half-close 让对端读到 EOF -> 排空残留请求数据再关闭。
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Length: 0\r\nConnection: close\r\n\r\n"
                )
                try:
                    request.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                try:
                    request.settimeout(0.05)
                    while request.recv(4096):
                        pass
                except OSError:
                    pass
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def _expected_token():
    return _ROUTER_TOKEN or os.environ.get("ROUTER_AUTH_TOKEN", "")


def _authorized(handler):
    return bearer_authorized(handler.headers.get("Authorization", ""), _expected_token())


def record(kind, basis, lat, tok, err=False):
    with stats_lock:
        stats["total"] += 1
        if err:
            stats["err"] += 1
            return
        stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1
        stats["by_basis"][basis] = stats["by_basis"].get(basis, 0) + 1
        stats["lat_sum"] += lat
        stats["tok_sum"] += tok


def make_handler():
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            self.request.settimeout(10)
            super().setup()

        def _send(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            if self.headers.get("Transfer-Encoding"):
                self._send(501, {"error": "transfer encoding is not supported"})
                return None
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._send(415, {"error": "Content-Type must be application/json"})
                return None
            try:
                raw_length = self.headers.get("Content-Length")
                if raw_length is None:
                    self._send(411, {"error": "Content-Length is required"})
                    return None
                length = int(raw_length)
            except (TypeError, ValueError):
                self._send(400, {"error": "Invalid Content-Length"})
                return None
            if length < 0:
                self._send(400, {"error": "Invalid Content-Length"})
                return None
            if length > MAX_BODY_BYTES:
                self._send(413, {"error": "Request body exceeds allowed size"})
                return None
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    self._send(400, {"error": "Incomplete request body"})
                    return None
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send(400, {"error": "Request body must be valid UTF-8 JSON"})
                return None
            if not isinstance(data, dict):
                self._send(400, {"error": "JSON request body must be an object"})
                return None
            return data

        def log_message(self, fmt, *a):
            # Keep request targets (including query values and tokens) out of logs.
            code = a[1] if len(a) > 1 else "-"
            sys.stderr.write("[router-srv %s] %s status=%s\n" % (
                datetime.now().strftime("%H:%M:%S"), self.command, code))

        def do_GET(self):
            if not _authorized(self):
                self._send(401, {"error": "Valid Bearer token required"})
                return
            p = urlparse(self.path).path
            if p == "/health":
                self._send(200, health())
            elif p == "/stats":
                self._send(200, stats_snapshot())
            elif p == "/help":
                self._send(200, HELP)
            else:
                self._send(404, {"error": "not found", "path": p, "help": "/help"})

        def do_POST(self):
            if not _authorized(self):
                self._send(401, {"error": "Valid Bearer token required"})
                return
            p = urlparse(self.path).path
            if p not in {"/route", "/ask"}:
                self._send(404, {"error": "not found", "path": p, "help": "/help"})
                return
            data = self._read_json()
            if data is None:
                return
            prompt = data.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                self._send(400, {"error": "prompt must be non-empty text"})
                return
            if len(prompt) > MAX_PROMPT_CHARS:
                self._send(413, {"error": "prompt exceeds allowed length"})
                return
            max_tokens = data.get("max_tokens", 256)
            if p == "/ask" and (isinstance(max_tokens, bool) or not isinstance(max_tokens, int)
                                 or not 1 <= max_tokens <= MAX_TOKENS):
                self._send(400, {"error": f"max_tokens must be an integer between 1 and {MAX_TOKENS}"})
                return
            if not sem.acquire(blocking=False):
                self._send(503, {"error": "router is busy; retry later"})
                return

            global _active
            with stats_lock:
                _active += 1
                if _active > stats["max_concurrent_seen"]:
                    stats["max_concurrent_seen"] = _active
            started = time.perf_counter()
            try:
                if p == "/route":
                    result = R.route(prompt)
                    self._send(200, result)
                    return
                result = R.ask(prompt, max_tokens=max_tokens)
                decision = result["decision"]
                record(decision["kind"], decision["basis"],
                       time.perf_counter() - started, result.get("eval_count", 0))
                self._send(200, {
                    "target": decision["target"], "kind": decision["kind"],
                    "basis": decision["basis"], "margin": decision["margin"],
                    "kw_hits": decision["kw_hits"], "reason": decision["reason"],
                    "model": result["model"], "response": result["response"],
                    "tok_s": result["tok_s"], "eval_count": result["eval_count"],
                    "elapsed_s": result["elapsed_s"],
                })
            except Exception as exc:
                if p == "/ask":
                    record("ERR", "err", 0, 0, err=True)
                sys.stderr.write(f"[router-srv] request failed: {type(exc).__name__}\n")
                self._send(500, {"error": "router request failed"})
            finally:
                with stats_lock:
                    _active = max(0, _active - 1)
                sem.release()
    return H


def health():
    out = {"service": "virtu-router", "ok": True, "ollama": R.OLLAMA,
           "fast_model": R.FAST_MODEL, "hard_model": R.HARD_MODEL,
           "embedding": R.EMBED_MODEL, "max_concurrent": MAX_CONCURRENT,
           "threshold": R.THRESH}
    import urllib.request
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(k, None)
    try:
        r = json.load(urllib.request.urlopen(f"{R.OLLAMA}/api/tags", timeout=8))
        # /api/tags 返回带 tag 的名字 (如 "nomic-embed-text:latest"), 用前缀匹配基础名
        names = {m["name"] for m in r.get("models", [])}
        has = lambda base: any(n == base or n.startswith(base + ":") for n in names)
        out["fast_ready"] = has(R.FAST_MODEL)
        out["hard_ready"] = has(R.HARD_MODEL)
        out["embed_ready"] = has(R.EMBED_MODEL)
        if not (out["fast_ready"] and out["hard_ready"] and out["embed_ready"]):
            out["ok"] = False
    except Exception as e:
        out["ok"] = False
        out["ollama_error"] = str(e)[:160]
    return out


def stats_snapshot():
    with stats_lock:
        s = dict(stats)
    s["uptime_s"] = round(time.time() - s.pop("started_at"), 1)
    ok = s["total"] - s["err"]
    s["ok_requests"] = ok
    s["avg_latency_s"] = round(s["lat_sum"] / ok, 3) if ok else 0
    s["avg_tok_s"] = round(s["tok_sum"] / s["lat_sum"], 1) if s["lat_sum"] else 0
    s["throughput_req_s"] = round(ok / s["uptime_s"], 3) if s["uptime_s"] else 0
    return s


HELP = {
    "service": "Virtu P1-3 Router HTTP API (zero-dependency, stdlib)",
    "endpoints": {
        "GET /health": "后端模型就绪状态 + 配置 (Bearer token required)",
        "GET /stats": "累计请求统计 / 吞吐 (Bearer token required)",
        "GET /help": "本说明 (Bearer token required)",
        "POST /route": {"body": {"prompt": "str"}, "desc": "仅路由判定, 需要 Bearer token"},
        "POST /ask": {"body": {"prompt": "str", "max_tokens": 256}, "desc": "路由 + 生成, 需要 Bearer token"},
    },
    "config_env": {"ROUTER_HOST": HOST, "ROUTER_PORT": PORT,
                   "ROUTER_MAX_CONCURRENT": MAX_CONCURRENT},
    "routing": {"FAST(dense)": R.FAST_MODEL, "HARD(moe)": R.HARD_MODEL},
}


def main():
    global _ROUTER_TOKEN
    _ROUTER_TOKEN = ensure_service_token("router", "ROUTER_AUTH_TOKEN")
    # 预热质心 (需连 Ollama 嵌入), 失败不致命, /route 会按需重建
    try:
        R.load_centroids()
        print("[router-srv] centroids warmed (expert/general)")
    except Exception as e:
        print(f"[router-srv] WARN centroid warm failed: {e}")
    srv = BoundedThreadingHTTPServer((HOST, PORT), make_handler())
    print(f"[router-srv] listening http://{HOST}:{PORT}  max_concurrent={MAX_CONCURRENT}")
    if not os.environ.get("ROUTER_AUTH_TOKEN"):
        print(f"[router-srv] Bearer token stored in protected file: {service_token_path('router')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[router-srv] shutdown requested")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
