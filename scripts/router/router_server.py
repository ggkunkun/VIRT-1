#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu P1-3 路由层 —— 生产化 HTTP 服务 (零依赖, 仅用标准库)
============================================================
把 virtu_router 的 route/ask 暴露为 HTTP API, 支持并发请求, 内置可观测指标。
设计原则: 不引入任何第三方依赖 (本机 DNS 被拦截, 无法 pip 安装 fastapi/uvicorn),
          直接基于 http.server.ThreadingHTTPServer。

端点:
  GET  /health   健康检查 + 后端模型就绪状态
  GET  /stats    累计请求统计 (路由分布 / 平均延迟 / 平均 tok/s / 错误数)
  GET  /help     端点与配置说明
  POST /route    {prompt}            仅路由判定 (不进生成), 返回完整决策证据
  POST /ask      {prompt,max_tokens} 路由 + 生成 (非流式), 返回回答与决策

启动:
  python router_server.py                      # 默认 0.0.0.0:8800
  ROUTER_PORT=8801 python router_server.py
  ROUTER_MAX_CONCURRENT=4 python router_server.py   # 限制同时进 Ollama 的请求数

宪法合规: 决策对象 (后端模型/嵌入模型) 在 /health 中显式声明; 每次 /ask 的决策证据
          (target/kind/basis/margin/kw_hits) 随响应一并返回, 可审计、可复现。
"""
import os
import sys
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import virtu_router as R

HOST = os.environ.get("ROUTER_HOST", "0.0.0.0")
PORT = int(os.environ.get("ROUTER_PORT", "8800"))
# 服务端并发上限: 防止一次性把 Ollama 的 GPU 显存 / 调度队列打爆。
# Ollama 自身也有请求队列与 KV-cache 上限, 此信号量作为上游保护阀。
MAX_CONCURRENT = int(os.environ.get("ROUTER_MAX_CONCURRENT", "8"))


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


def record(kind, basis, lat, tok, err=False):
    with stats_lock:
        global _active
        stats["total"] += 1
        if not err:
            stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1
            stats["by_basis"][basis] = stats["by_basis"].get(basis, 0) + 1
            stats["lat_sum"] += lat
            stats["tok_sum"] += tok
        else:
            stats["err"] += 1
            _active = max(0, _active - 1)  # 出错时也需释放活跃计数(正常路径在 finally)


def make_handler():
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            try:
                ln = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(ln) if ln else b"{}"
                return json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                return {}

        def log_message(self, fmt, *a):
            sys.stderr.write("[router-srv %s] %s\n" % (datetime.now().strftime("%H:%M:%S"), fmt % a))

        def do_OPTIONS(self):
            self._send(204, {})

        def do_GET(self):
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
            p = urlparse(self.path).path
            data = self._read_json()
            if p == "/route":
                try:
                    self._send(200, R.route(data.get("prompt", "")))
                except Exception as e:
                    self._send(500, {"error": str(e)[:300]})
            elif p == "/ask":
                self.handle_ask(data)
            else:
                self._send(404, {"error": "not found", "path": p, "help": "/help"})

        def handle_ask(self, data):
            global _active
            prompt = (data.get("prompt", "") or "").strip()
            max_tokens = int(data.get("max_tokens", 256))
            if not prompt:
                self._send(400, {"error": "empty prompt"})
                return
            sem.acquire()
            with stats_lock:
                global _active
                _active += 1
                if _active > stats["max_concurrent_seen"]:
                    stats["max_concurrent_seen"] = _active
            t0 = time.perf_counter()
            try:
                res = R.ask(prompt, max_tokens=max_tokens)
                lat = time.perf_counter() - t0
                d = res["decision"]
                record(d["kind"], d["basis"], lat, res["eval_count"])
                self._send(200, {
                    "target": d["target"], "kind": d["kind"], "basis": d["basis"],
                    "margin": d["margin"], "kw_hits": d["kw_hits"], "reason": d["reason"],
                    "model": res["model"], "response": res["response"],
                    "tok_s": res["tok_s"], "eval_count": res["eval_count"],
                    "elapsed_s": res["elapsed_s"],
                })
            except Exception as e:
                record("ERR", "err", 0, 0, err=True)
                self._send(500, {"error": str(e)[:300]})
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
        "GET /health": "后端模型就绪状态 + 配置",
        "GET /stats": "累计请求统计 / 吞吐",
        "GET /help": "本说明",
        "POST /route": {"body": {"prompt": "str"}, "desc": "仅路由判定, 不生成"},
        "POST /ask": {"body": {"prompt": "str", "max_tokens": 256}, "desc": "路由 + 生成"},
    },
    "config_env": {"ROUTER_HOST": HOST, "ROUTER_PORT": PORT,
                   "ROUTER_MAX_CONCURRENT": MAX_CONCURRENT},
    "routing": {"FAST(dense)": R.FAST_MODEL, "HARD(moe)": R.HARD_MODEL},
}


def main():
    # 预热质心 (需连 Ollama 嵌入), 失败不致命, /route 会按需重建
    try:
        R.load_centroids()
        print("[router-srv] centroids warmed (expert/general)")
    except Exception as e:
        print(f"[router-srv] WARN centroid warm failed: {e}")
    srv = ThreadingHTTPServer((HOST, PORT), make_handler())
    print(f"[router-srv] listening http://{HOST}:{PORT}  max_concurrent={MAX_CONCURRENT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[router-srv] shutdown requested")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
