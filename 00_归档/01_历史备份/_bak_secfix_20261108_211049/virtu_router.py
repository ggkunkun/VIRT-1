#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 路由网关 —— 3B 快通道 + 8B 工业深度推理
================================================
默认走 qwen2.5:3b（100% GPU，约 78 tok/s，丝滑）；遇到复杂工业/深度推理类问题，
自动切换到 virtu-comprehensive:latest（8B，约 17 tok/s，质量优先）。

用法:
  python virtu_router.py "你的问题"            # CLI 直接问（自动选模型）
  python virtu_router.py --pro  "复杂问题"     # 强制 8B 工业模型
  python virtu_router.py --fast "简单问题"     # 强制 3B 快通道
  python virtu_router.py --serve               # 启动 OpenAI 兼容网关（默认 :11435）

前端（如 Open WebUI / Chatbox）把 API base 指向 http://127.0.0.1:11435 即可，
网关会按内容自动选模型；也可以显式把 model 设为 "virtu-fast" / "virtu-pro" / "virtu-auto"。

环境变量:
  OLLAMA_HOST   后端 Ollama 地址（默认 http://127.0.0.1:11434）
  ROUTER_PORT   网关端口（默认 11435）
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

_ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
if _ollama_host and not _ollama_host.lower().startswith(("http://", "https://")):
    _ollama_host = "http://" + _ollama_host
OLLAMA_HOST = _ollama_host.rstrip("/")
ROUTER_PORT = int(os.environ.get("ROUTER_PORT", "11435"))

FAST_MODEL = "qwen2.5:3b"
PRO_MODEL = "virtu-comprehensive:latest"
MOE_MODEL = "virtu-moe-14b:latest"

# 复杂工业 / 深度推理关键词（命中任一即走 8B）
PRO_KEYWORDS = [
    "solidworks", "sw ", "数控", "cnc", "加工中心", "加工工艺", "工艺路线",
    "公差", "装配", "图纸", "工程图", "二维图", "三维模型",
    "有限元", "有限元分析", "fea", "仿真", "注塑", "冲压", "铣削", "车削",
    "夹具", "工装", "g代码", "g-code", "gcode", "刀路", "走刀",
    "机器人", "工业机器人", "制造", "智能制造", "拓扑优化", "应力", "应变",
    "材料力学", "热处理", "焊接", "钣金", "cad", "cam", "cae", "plm",
    "深度学习", "神经网络", "训练", "微调", "sft", "lora", "推理",
    "详细分析", "设计方案", "优化方案", "多步", "计算", "为什么", "原理",
    "推导", "架构设计", "系统架构", "agent", "智能体", "编队", "调度",
    "伺服", "plc", "pid", "控制算法", "故障诊断", "根因",
]

# 显式模型别名
MODEL_ALIAS = {
    "virtu-fast": FAST_MODEL,
    "virtu-pro": PRO_MODEL,
    "virtu-moe": MOE_MODEL,
    "virtu-moe-14b": MOE_MODEL,
    "virtu-13.63b": "virtu-13.63b:latest",
    "virtu-13b": "virtu-13.63b:latest",
    "13.63b": "virtu-13.63b:latest",
    "13b": "virtu-13.63b:latest",
    "virtu-auto": "AUTO",
    "fast": FAST_MODEL,
    "pro": PRO_MODEL,
    "moe": MOE_MODEL,
    "moe-14b": MOE_MODEL,
    "semantic": MOE_MODEL,
    "auto": "AUTO",
}


def is_pro(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in PRO_KEYWORDS)


def pick_model(prompt: str, force=None) -> str:
    # 显式指定了真实模型名（非别名），原样透传
    if force and force not in MODEL_ALIAS:
        return force
    # 自动模式：AUTO / virtu-auto / auto / None -> 按关键词选择
    if force in (None, "AUTO", "auto", "virtu-auto"):
        return PRO_MODEL if is_pro(prompt) else FAST_MODEL
    # 显式别名
    return MODEL_ALIAS.get(force, FAST_MODEL)


def ollama_generate(model, prompt, system=None, stream=True, keep_alive="10m",
                    temperature=0.7, num_predict=2048, format=None, options_override=None):
    """调用 Ollama /api/generate。
    stream=False 时返回完整文本字符串；stream=True 时返回一个流式迭代器。
    注意：流式迭代器必须在 with 块保持打开期间迭代，因此用内部闭包实现。
    """
    opts = {"num_predict": num_predict, "temperature": temperature}
    # MoE / 13.63B 工业深度架构安全生产参数锁与 RSI 策略动态注入
    if any(k in model.lower() for k in ("moe", "13.63b", "13b")) or model == MOE_MODEL:
        opts.update({
            "num_ctx": 4096,
            "num_gpu": 20,
            "repeat_penalty": 1.15,
            "presence_penalty": 0.3,
            "temperature": min(temperature, 0.2),
        })
        try:
            from virtu_omni.rsi import get_active_rsi_strategy
            rsi_strategy = get_active_rsi_strategy(ROOT, model_id=model)
            if rsi_strategy:
                rsi_block = f"\n\n[Virtu 13.63B RSI 递归优化推理准则]\n{rsi_strategy}"
                system = (system + rsi_block) if system else rsi_block.strip()
        except Exception:
            pass
    if options_override:
        opts.update(options_override)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "keep_alive": keep_alive,
        "options": opts,
    }
    if format:
        payload["format"] = format
    if system:
        payload["system"] = system
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    if not stream:
        with urllib.request.urlopen(req, timeout=600) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
            return obj.get("response", "")
    def _gen():
        with urllib.request.urlopen(req, timeout=600) as resp:
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "response" in obj:
                    yield obj["response"]
                if obj.get("done"):
                    break
    return _gen()


def chat_to_prompt(messages):
    """把 OpenAI 风格 messages 拼成单轮 prompt。"""
    sys_parts, conv = [], []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            sys_parts.append(content)
        elif role == "assistant":
            conv.append(f"助手：{content}")
        else:
            conv.append(f"用户：{content}")
    system = "\n".join(sys_parts) if sys_parts else None
    prompt = "\n".join(conv)
    return prompt, system


# ============================ CLI ============================

def cli():
    ap = argparse.ArgumentParser(description="Virtu 路由网关")
    ap.add_argument("prompt", nargs="?", default=None, help="直接提问")
    ap.add_argument("--moe", action="store_true", help="强制 14B MoE 正交门控模型")
    ap.add_argument("--pro", action="store_true", help="强制 8B 工业模型")
    ap.add_argument("--fast", action="store_true", help="强制 3B 快通道")
    ap.add_argument("--serve", action="store_true", help="启动 OpenAI 兼容网关")
    ap.add_argument("--port", type=int, default=ROUTER_PORT)
    ap.add_argument("--model", default=None, help="显式指定模型名")
    args = ap.parse_args()

    if args.serve:
        serve(args.port)
        return

    prompt = args.prompt
    if prompt is None:
        prompt = sys.stdin.read().strip()
    if not prompt:
        print('usage: python virtu_router.py "你的问题" [--moe|--pro|--fast]')
        return

    if args.moe:
        model = MOE_MODEL
    elif args.pro:
        model = PRO_MODEL
    elif args.fast:
        model = FAST_MODEL
    else:
        model = pick_model(prompt, args.model)

    if model == MOE_MODEL:
        tag = "14B-MoE正交门控"
    elif model == PRO_MODEL:
        tag = "8B工业"
    else:
        tag = "3B快通道"
    print(f"[Virtu路由] 选用模型: {model} ({tag})\n", flush=True)
    try:
        out = ollama_generate(model, prompt, stream=True)
        for chunk in out:
            print(chunk, end="", flush=True)
        print()
    except urllib.error.URLError as e:
        print(f"\n[错误] 无法连接 Ollama ({OLLAMA_HOST}): {e}", file=sys.stderr)
        sys.exit(1)


# ============================ Serve (OpenAI 兼容) ============================

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path in ("/", "/health"):
            self._send(200, json.dumps({"status": "ok", "router": "virtu"}))
            return
        if p.path == "/v1/models":
            self._send(200, json.dumps({
                "object": "list",
                "data": [
                    {"id": "virtu-auto", "object": "model"},
                    {"id": "virtu-fast", "object": "model"},
                    {"id": "virtu-pro", "object": "model"},
                    {"id": "virtu-moe", "object": "model"},
                ],
            }))
            return
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        p = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, json.dumps({"error": "bad json"}))
            return

        if p.path == "/v1/chat/completions":
            self.handle_chat(payload)
        elif p.path == "/api/generate":
            self.handle_generate(payload)
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def handle_chat(self, payload):
        messages = payload.get("messages", [])
        prompt, system = chat_to_prompt(messages)
        model_req = payload.get("model", "virtu-auto")
        stream = payload.get("stream", False)
        force = None
        if model_req in MODEL_ALIAS:
            force = model_req
        model = pick_model(prompt, force)
        # 透传 temperature / max_tokens / format
        temperature = payload.get("temperature", 0.7)
        num_predict = payload.get("max_tokens", 2048)
        format_spec = payload.get("format") or payload.get("response_format")

        if not stream:
            try:
                text = ollama_generate(model, prompt, system=system, stream=False,
                                      temperature=temperature, num_predict=num_predict,
                                      format=format_spec)
                try:
                    from virtu_omni.serving.answer_pipeline import clean_served_answer
                    text = clean_served_answer(prompt, text).text
                except Exception:
                    pass
            except Exception as e:
                self._send(502, json.dumps({"error": f"backend error: {e}", "routed_model": model}, ensure_ascii=False))
                return
            resp = {
                "id": "chatcmpl-virtu",
                "object": "chat.completion",
                "model": model_req,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }],
                "routed_model": model,
            }
            self._send(200, json.dumps(resp, ensure_ascii=False))
            return

        # 流式 SSE
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            gen = ollama_generate(model, prompt, system=system, stream=True,
                                 temperature=temperature, num_predict=num_predict,
                                 format=format_spec)
            for chunk in gen:
                data = json.dumps({
                    "id": "chatcmpl-virtu",
                    "object": "chat.completion.chunk",
                    "model": model_req,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None,
                    }],
                }, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(f"data: {err}\n\n".encode("utf-8"))

    def handle_generate(self, payload):
        prompt = payload.get("prompt", "")
        model_req = payload.get("model", "virtu-auto")
        force = model_req if model_req in MODEL_ALIAS else None
        model = pick_model(prompt, force)
        # 直接转发到 Ollama，但把 model 替换为实际选定模型
        payload["model"] = model
        payload.setdefault("keep_alive", "10m")
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp.read())

    def log_message(self, *a):
        pass  # 静默


def serve(port):
    srv = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[Virtu路由] OpenAI 兼容网关已启动: http://127.0.0.1:{port}")
    print(f"[Virtu路由] 后端 Ollama: {OLLAMA_HOST}")
    print(f"[Virtu路由] 默认快通道: {FAST_MODEL} | 工业模型: {PRO_MODEL}")
    print(f"[Virtu路由] 前端 API base 设为 http://127.0.0.1:{port} ，模型选 virtu-auto / virtu-fast / virtu-pro")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[Virtu路由] 已停止")


if __name__ == "__main__":
    cli()
