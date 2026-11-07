"""Virtu 13.63B <-> Windows-MCP 自动接入桥（官方 stdio 协议）。

接入方式依据 GitHub 官方 README（CursorTouch/Windows-MCP）：
    uvx windows-mcp serve                # stdio, 必须带 serve 子命令
    ANONYMIZED_TELEMETRY=false           # 官方推荐，境外 PostHog 会挂住启动
本机等价命令使用已安装好的源码 venv，避免 uvx 联网：
    <venv>/python.exe -m windows_mcp serve --transport stdio --tools "..."

职责：
  1. 启动 MCP server、initialize(2025-06-18)、tools/list 动态发现工具；
  2. 把 MCP inputSchema 转成 Ollama /api/chat 的 tools 格式（不手抄 schema）；
  3. 模型返回 tool_calls 后自动路由到 tools/call，把 <tool_response> 回喂模型；
  4. 形成 Thought -> Action -> Observation -> 结论 的闭环，逐步留痕。

用法：
    python bridges/windows_mcp_bridge.py --prompt "用 Windows-MCP 查一下 NX 是否在运行" \
        --out runs/mcp_integration_xxx
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT / "external" / "windows-mcp"
SERVER_PY = SERVER_DIR / ".venv" / "Scripts" / "python.exe"
DEFAULT_TOOLS = "ControlStatus,Process,App"   # 只读为主 + 应用启动；不默认放开 PowerShell/Registry
DEFAULT_MODEL = "virtu-moe-14b:a2103c68"
OLLAMA = "http://127.0.0.1:11434"
PROTOCOL_VERSION = "2025-06-18"
_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# --------------------------------------------------------------------------- MCP client
class WindowsMCPClient:
    def __init__(self, tools_whitelist: str = DEFAULT_TOOLS, timeout: int = 150):
        self.whitelist = tools_whitelist
        self.timeout = timeout
        self.p = None
        self.q = queue.Queue()
        self.stderr = []
        self.next_id = 1
        self.server_info = None

    def start(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SERVER_DIR / "src") + os.pathsep + env.get("PYTHONPATH", "")
        env["ANONYMIZED_TELEMETRY"] = "false"
        env["POSTHOG_API_KEY"] = ""
        env["WINDOWS_MCP_CONTROL"] = "false"
        env["WINDOWS_MCP_DISABLE_FLASH"] = "1"
        argv = [str(SERVER_PY), "-m", "windows_mcp", "serve",
                "--transport", "stdio", "--tools", self.whitelist]
        self.p = subprocess.Popen(
            argv, cwd=str(SERVER_DIR), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.argv = argv
        threading.Thread(target=self._stdout_reader, daemon=True).start()
        threading.Thread(target=self._stderr_reader, daemon=True).start()
        init = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "virtu-13b-mcp-bridge", "version": "1.0"}},
            timeout=self.timeout)
        if init.get("error"):
            raise RuntimeError(f"MCP initialize 失败: {init}")
        self.server_info = (init.get("result") or {}).get("serverInfo")
        self.notify("notifications/initialized", {})
        return init

    def _stdout_reader(self):
        for line in self.p.stdout:
            line = line.strip()
            if line.startswith("{"):
                try:
                    self.q.put(json.loads(line))
                except Exception:
                    pass

    def _stderr_reader(self):
        for line in self.p.stderr:
            if len(self.stderr) < 50:
                self.stderr.append(line.rstrip()[:300])

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def notify(self, method, params):
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method, params, timeout=None):
        rid = self.next_id
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            try:
                msg = self.q.get(timeout=1)
            except queue.Empty:
                if self.p.poll() is not None:
                    return {"error": "server exited", "stderr": self.stderr}
                continue
            if msg.get("id") == rid:
                return msg
        return {"error": f"timeout: {method}", "stderr": self.stderr}

    def list_tools(self) -> list[dict]:
        r = self.request("tools/list", {})
        if r.get("error"):
            raise RuntimeError(f"tools/list 失败: {r}")
        return (r.get("result") or {}).get("tools") or []

    def call_tool(self, name: str, arguments: dict) -> dict:
        r = self.request("tools/call", {"name": name, "arguments": arguments}, timeout=150)
        if r.get("error"):
            return {"text": f"[MCP ERROR] {r['error']}", "is_error": True, "raw": r}
        result = r.get("result") or {}
        parts = []
        for c in result.get("content") or []:
            if c.get("type") == "text" and c.get("text"):
                parts.append(c["text"])
            elif c.get("type") == "image":
                parts.append("[image omitted: text-only model]")
        return {"text": "\n".join(parts) or json.dumps(result, ensure_ascii=False)[:2000],
                "is_error": bool(result.get("isError")), "raw": r}

    def close(self):
        if self.p and self.p.poll() is None:
            try:
                self.p.terminate()
                self.p.wait(timeout=8)
            except Exception:
                self.p.kill()


# --------------------------------------------------------------------------- schema adapter
def _simplify(node, depth=0):
    """MCP inputSchema -> Ollama 可接受的精简 JSON Schema（去掉 $defs/anyOf 等）。"""
    if not isinstance(node, dict) or depth > 6:
        return {"type": "string"}
    if "anyOf" in node or "oneOf" in node:
        for sub in (node.get("anyOf") or node.get("oneOf") or []):
            if isinstance(sub, dict) and sub.get("type") != "null":
                return _simplify(sub, depth + 1)
        return {"type": "string"}
    out = {}
    t = node.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "string")
    out["type"] = t or "string"
    if node.get("enum"):
        out["enum"] = [str(x) for x in node["enum"][:20]]
    if node.get("description"):
        out["description"] = str(node["description"])[:220]
    if out["type"] == "object" and isinstance(node.get("properties"), dict):
        out["properties"] = {k: _simplify(v, depth + 1)
                             for k, v in list(node["properties"].items())[:24]}
        if node.get("required"):
            out["required"] = list(node["required"])[:16]
    if out["type"] == "array" and isinstance(node.get("items"), dict):
        out["items"] = _simplify(node["items"], depth + 1)
    return out


def mcp_to_ollama_tools(mcp_tools: list[dict]) -> list[dict]:
    out = []
    for t in mcp_tools:
        name = t.get("name")
        if not name:
            continue
        schema = _simplify(t.get("inputSchema") or {"type": "object", "properties": {}})
        if schema.get("type") != "object":
            schema = {"type": "object", "properties": {}}
        out.append({"type": "function", "function": {
            "name": name,
            "description": str(t.get("description") or t.get("title") or name)[:400],
            "parameters": schema}})
    return out


# --------------------------------------------------------------------------- agent loop
def normalize_calls(calls):
    """统一 tool_calls 形态（arguments 归一为 JSON 字符串）——复用 scripts 层唯一实现。"""
    if not calls:
        return calls
    try:
        import sys as _sys
        from pathlib import Path as _P
        _scripts = str(_P(__file__).resolve().parent.parent / "scripts")
        if _scripts not in _sys.path:
            _sys.path.insert(0, _scripts)
        from ollama_toolcall_client import normalize_tool_calls
        return normalize_tool_calls(calls)
    except Exception:
        return calls


def drop_tool_leg_prose(resp):
    """工具腿：只要有 tool_calls，就把这一轮的正文丢掉，避免下游把套话当结论。"""
    msg = (resp or {}).get("message")
    if not isinstance(msg, dict):
        return resp
    if msg.get("tool_calls"):
        msg["tool_calls"] = normalize_calls(msg["tool_calls"]) or []
        msg["content"] = ""
    return resp


def ollama_chat(model, messages, tools, num_ctx=3072, num_predict=256):
    payload = {"model": model, "stream": False, "think": False, "keep_alive": "10m",
               "options": {"num_ctx": num_ctx, "temperature": 0.1,
                           "num_predict": num_predict, "num_gpu": 30},
               "messages": messages, "tools": tools}
    req = urllib.request.Request(
        OLLAMA + "/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    last = None
    for attempt in range(3):                      # 仅传输层重试：模型冷加载会瞬时 500
        try:
            with _http.open(req, timeout=300) as r:
                resp = json.loads(r.read().decode("utf-8"))
            return drop_tool_leg_prose(resp), round(time.time() - t0, 2)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:200]}"
        time.sleep(5 * (attempt + 1))
    return {"error": f"3 次传输重试失败: {last}"}, round(time.time() - t0, 2)


def run_agent(prompt: str, model: str = DEFAULT_MODEL,
              tools_whitelist: str = DEFAULT_TOOLS,
              max_turns: int = 4, out_dir: Path | None = None) -> dict:
    client = WindowsMCPClient(tools_whitelist)
    trace = {"prompt": prompt, "model": model, "tools_whitelist": tools_whitelist,
             "protocol_version": PROTOCOL_VERSION, "turns": [], "basis": "measured"}
    try:
        init = client.start()
        mcp_tools = client.list_tools()
        tools = mcp_to_ollama_tools(mcp_tools)
        trace["server_argv"] = client.argv
        trace["server_info"] = client.server_info
        trace["mcp_tool_names"] = [t["name"] for t in mcp_tools]
        trace["ollama_tools_count"] = len(tools)
        trace["initialize"] = {"protocolVersion": (init.get("result") or {}).get("protocolVersion")}
        if not tools:
            raise RuntimeError("tools/list 返回空工具集，闸门判红（禁止空匹配集当通过）")

        messages = [{"role": "user", "content": prompt}]
        final = None
        for turn in range(1, max_turns + 1):
            resp, elapsed = ollama_chat(model, messages, tools)
            if resp.get("error"):
                raise RuntimeError(f"Ollama 错误: {resp['error']}")
            msg = resp.get("message") or {}
            calls = msg.get("tool_calls") or []
            entry = {"turn": turn, "elapsed_s": elapsed,
                     "assistant_content": msg.get("content", ""),
                     "tool_calls": calls, "tool_results": []}
            if not calls:
                final = msg.get("content", "")
                entry["final"] = True
                trace["turns"].append(entry)
                break
            messages.append({"role": "assistant", "content": msg.get("content", ""),
                             "tool_calls": calls})
            for c in calls:
                fn = c.get("function") or {}
                name, args = fn.get("name"), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                out = client.call_tool(name, args)
                # Qwen3 模板把 role=tool 渲染成 <tool_response>
                messages.append({"role": "tool", "content": out["text"][:6000], "name": name})
                entry["tool_results"].append({"name": name, "arguments": args,
                                              "text": out["text"][:2000],
                                              "is_error": out["is_error"]})
            trace["turns"].append(entry)
        trace["final_answer"] = final
        trace["loop_completed"] = final is not None
        trace["n_tool_calls"] = sum(len(t["tool_calls"]) for t in trace["turns"])
        return trace
    finally:
        client.close()
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "bridge_trace.json").write_text(
                json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tools", default=DEFAULT_TOOLS)
    ap.add_argument("--max-turns", type=int, default=4)
    ap.add_argument("--out", default=str(ROOT / "runs" / "mcp_integration_last"))
    a = ap.parse_args()
    trace = run_agent(a.prompt, a.model, a.tools, a.max_turns, Path(a.out))
    print(json.dumps({
        "server_info": trace.get("server_info"),
        "mcp_tools": trace.get("mcp_tool_names"),
        "n_tool_calls": trace.get("n_tool_calls"),
        "turns": [{"turn": t["turn"],
                   "calls": [f"{c['function']['name']}({json.dumps(c['function']['arguments'], ensure_ascii=False)[:100]})"
                             for c in t["tool_calls"]],
                   "results": [{"name": r["name"], "text": r["text"][:160], "is_error": r["is_error"]}
                               for r in t["tool_results"]]} for t in trace["turns"]],
        "loop_completed": trace.get("loop_completed"),
        "final_answer": trace.get("final_answer"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
