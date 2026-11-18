# -*- coding: utf-8 -*-
"""bridges/agent_desktop_bridge.py — Agent-Desktop (Vercel Labs) Multi-Model Integration Bridge.

Integrates the official open-source `agent-desktop` project (https://github.com/vercel-labs/agent-desktop)
into the Virtu CAD/CAM/Engineering autonomous agent ecosystem and connects it to all models in the workspace:

Capabilities:
1. Native OS Accessibility Tree perception (`snapshot`, `find`, `get`, `is`) without coordinate guessing.
2. Stable element referencing (`@ref`) for reliable semantic desktop operations (`click`, `type`, `press`).
3. Multi-surface & window management (`list-apps`, `list-windows`, `focus-window`, `launch`, `close-app`).
4. Display & System status introspection (`status`, `permissions`, `list-displays`, `skills`).
5. Dual protocol execution: Direct CLI JSON interface + stdio Model Context Protocol (MCP) server.
6. Unified Model Connection Loop: Seamlessly connects Ollama models (Virtu-13.63B, Virtu-MoE-14B, Virtu-V3, Qwen3)
   and HF/local models to desktop computer-use tools with full provenance and trace recording.
"""

from __future__ import annotations

import os
import sys
import json
import time
import shutil
import queue
import threading
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import win32gui
    import win32process
    import win32con
    import win32service
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = "virtu-13.63b:hardened"
_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _attach_interactive_desktop():
    """Ensure process and current thread are attached to WinSta0\\default for GUI operations."""
    if not HAS_WIN32:
        return False
    try:
        user32 = win32gui
        # Attach Window Station
        try:
            hwinsta = win32service.OpenWindowStation("WinSta0", False, win32con.MAXIMUM_ALLOWED)
            hwinsta.SetProcessWindowStation()
        except Exception:
            pass
        # Attach Desktop
        try:
            hdesk = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
            hdesk.SetThreadDesktop()
        except Exception:
            pass
        return True
    except Exception:
        return False


def find_agent_desktop_binary() -> Optional[Path]:
    """Locate the agent-desktop binary across npm global paths, source build targets, and PATH."""
    candidates = [
        # 1. npm global module binary
        Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "agent-desktop" / "bin" / "agent-desktop-win32-x64.exe",
        # 2. Workspace external build targets
        ROOT / "external" / "agent-desktop" / "target" / "release" / "agent-desktop.exe",
        ROOT / "external" / "agent-desktop" / "target" / "debug" / "agent-desktop.exe",
        ROOT / "external" / "agent-desktop" / "bin" / "agent-desktop-win32-x64.exe",
    ]
    for c in candidates:
        if c.is_file():
            return c

    # 3. Check system PATH
    which_bin = shutil.which("agent-desktop")
    if which_bin:
        return Path(which_bin)
    which_exe = shutil.which("agent-desktop-win32-x64.exe")
    if which_exe:
        return Path(which_exe)

    return None


AGENT_DESKTOP_EXE = find_agent_desktop_binary()


# --------------------------------------------------------------------------- Tool Definitions
AGENT_DESKTOP_TOOLS_DEFINITION: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "desktop_status",
            "description": "查看 agent-desktop 桌面适配器运行健康度、系统平台信息与辅助功能权限状态（免截屏结构化感知引擎状态）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_list_displays",
            "description": "列出所有已连接的物理显示器参数，包括分辨率 (width/height)、原点坐标 (x/y)、缩放比 (scale) 与主屏标识。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_list_apps",
            "description": "列出 Windows 系统中所有正在运行的前台/后台图形界面应用程序 (GUI Applications)。可通过 app 参数过滤指定软件（如 SLDWORKS、AutoCAD、CIMCO、VERICUT、ugraf）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "可选过滤条件：进程名或可执行文件名子串（如 'SLDWORKS' 或 'acad'）",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_list_windows",
            "description": "列出当前桌面上所有可见的顶层应用窗口，返回每个窗口的 HWND、标题、所属进程 PID、坐标位置与状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "可选过滤条件：应用名称或进程文件名",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_snapshot",
            "description": "【核心感知】通过操作系统原生辅助功能树 (Accessibility Tree) 截取应用程序的完整结构化 JSON DOM 树。每个交互元素均带有稳定的 @ref 引用 ID（如 @s8f3k2p9:e1），避免像素坐标猜测。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "目标应用程序名或可执行文件名（如 'SLDWORKS', 'notepad', 'AutoCAD'）",
                    },
                    "compact": {
                        "type": "boolean",
                        "description": "是否以紧凑格式输出元素树，减少冗余标记",
                    },
                    "skeleton": {
                        "type": "boolean",
                        "description": "仅提取主要框架与骨架元素",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "最大遍历树深度（默认 8）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_find",
            "description": "在应用程序窗口的辅助功能树中快速搜索特定 UI 控件元素（按角色 role、名称 name、文本 text 或值 value 匹配），返回符合条件的 @ref 节点列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "目标应用程序名称",
                    },
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或文本内容（如 '确定', '文件', '保存', 'FeatureManager'）",
                    },
                    "role": {
                        "type": "string",
                        "description": "可选控件角色（如 'button', 'menuitem', 'edit', 'checkbox'）",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_click",
            "description": "【语义交互】通过 UI 元素稳定的 @ref 引用 ID 或文本选择器执行点击操作。语义点击直接调用底层 UIA 动作接口，无需移动实体光标即可在后台完成。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "目标元素 @ref 引用 ID（必须用单引号包裹，如 '@s8f3k2p9:e5'）或文本选择器",
                    },
                    "headed": {
                        "type": "boolean",
                        "description": "是否使用实体物理光标点击（默认 false 为语义后台静默点击）",
                    },
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_type",
            "description": "向输入框、文本控件或当前聚焦窗口输入文本内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要输入的文本字符串",
                    },
                    "target": {
                        "type": "string",
                        "description": "目标控件的 @ref 引用 ID（可选，留空则向当前焦点输入）",
                    },
                    "clear_first": {
                        "type": "boolean",
                        "description": "输入前是否先清空原有内容",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_press",
            "description": "发送键盘快捷键组合（如 'ctrl+s', 'enter', 'escape', 'alt+f', 'f5'）到当前前台或指定应用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "combo": {
                        "type": "string",
                        "description": "快捷键组合（如 'return', 'escape', 'ctrl+s', 'ctrl+c', 'tab'）",
                    },
                    "app": {
                        "type": "string",
                        "description": "可选目标应用",
                    },
                },
                "required": ["combo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_focus_window",
            "description": "将指定软件窗口激活并带到前台，确认获取操作系统焦点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "应用程序名或可执行文件名（如 'SLDWORKS', 'acad', 'notepad'）",
                    }
                },
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_screenshot",
            "description": "截取指定窗口或整个桌面的物理像素截图，保存为 PNG 图片。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "可选目标应用名称；留空则截取整屏",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出 PNG 图片路径（默认保存至 scratch/agent_desktop_capture.png）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_launch",
            "description": "启动指定的 Windows 桌面应用程序，并等待其窗口就绪。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path_or_name": {
                        "type": "string",
                        "description": "可执行文件绝对路径或系统命令名（如 'notepad.exe', 'calc.exe'）",
                    },
                    "wait_for_window": {
                        "type": "boolean",
                        "description": "是否等待主窗口建立（默认 true）",
                    },
                },
                "required": ["path_or_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_batch",
            "description": "以单批次原子/顺序方式执行一组 agent-desktop 指令，减少多次往返延迟。",
            "parameters": {
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "指令列表，例如 ['status', 'list-displays']",
                    }
                },
                "required": ["commands"],
            },
        },
    },
]


def get_agent_desktop_tool_definitions() -> List[Dict[str, Any]]:
    """Return OpenAI/Ollama compliant tool specifications for agent-desktop."""
    return AGENT_DESKTOP_TOOLS_DEFINITION


# --------------------------------------------------------------------------- Bridge Core
class AgentDesktopBridge:
    """Unified Agent-Desktop Bridge supporting both CLI execution and MCP JSON-RPC protocol."""

    def __init__(self, binary_path: Optional[Path] = None):
        self.binary_path = binary_path or AGENT_DESKTOP_EXE
        _attach_interactive_desktop()

    def run_cli_command(self, args: List[str], timeout_s: float = 30.0) -> Dict[str, Any]:
        """Execute agent-desktop CLI command and return parsed JSON payload."""
        if not self.binary_path or not Path(self.binary_path).exists():
            return {
                "ok": False,
                "error": {
                    "code": "BINARY_NOT_FOUND",
                    "message": f"agent-desktop binary not found at {self.binary_path}. Ensure npm install -g agent-desktop or build is complete.",
                },
            }

        _attach_interactive_desktop()
        si = None
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.lpDesktop = r"WinSta0\Default"

        cmd = [str(self.binary_path)] + args
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                startupinfo=si,
            )
            stdout = p.stdout.strip()
            stderr = p.stderr.strip()

            if stdout.startswith("{"):
                try:
                    data = json.loads(stdout)
                    return data
                except json.JSONDecodeError:
                    pass

            return {
                "ok": p.returncode == 0,
                "returncode": p.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": {"code": "TIMEOUT", "message": f"Command timed out after {timeout_s}s"}}
        except Exception as e:
            return {"ok": False, "error": {"code": "EXEC_ERROR", "message": str(e)}}

    def _fallback_win32_list_apps(self, filter_app: Optional[str] = None) -> Dict[str, Any]:
        """Resilient fallback to enumerate active GUI apps via Win32 if EnumWindows encounters session sandbox."""
        _attach_interactive_desktop()
        apps = []
        if not HAS_WIN32:
            return {"ok": True, "command": "list-apps", "data": {"apps": []}}

        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        import win32api
                        hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
                        exe_name = win32process.GetModuleFileNameEx(hproc, 0)
                        win32api.CloseHandle(hproc)
                        name = Path(exe_name).name
                    except Exception:
                        name = "unknown"

                    if not filter_app or filter_app.lower() in name.lower() or filter_app.lower() in title.lower():
                        rect = win32gui.GetWindowRect(hwnd)
                        apps.append({
                            "hwnd": hwnd,
                            "title": title,
                            "name": name,
                            "pid": pid,
                            "rect": {"x": rect[0], "y": rect[1], "w": rect[2]-rect[0], "h": rect[3]-rect[1]},
                        })
            return True

        try:
            win32gui.EnumWindows(enum_cb, 0)
        except Exception as e:
            pass

        return {
            "ok": True,
            "command": "list-apps",
            "source": "agent-desktop-win32-layer",
            "data": apps,
            "count": len(apps),
        }

    def _fallback_win32_list_windows(self, filter_app: Optional[str] = None) -> Dict[str, Any]:
        return self._fallback_win32_list_apps(filter_app)

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one of the defined desktop_* tools with automatic fallback and error isolation."""
        args = arguments or {}

        if tool_name in ("desktop_status", "agent_desktop_status"):
            res = self.run_cli_command(["status"])
            return res

        elif tool_name in ("desktop_list_displays", "agent_desktop_list_displays"):
            res = self.run_cli_command(["list-displays"])
            return res

        elif tool_name in ("desktop_list_apps", "agent_desktop_list_apps"):
            cmd = ["list-apps"]
            if args.get("app"):
                cmd.extend(["--app", str(args["app"])])
            res = self.run_cli_command(cmd)
            # If internal EnumWindows sandbox error, use resilient win32 layer
            if not res.get("ok") and "EnumWindows" in json.dumps(res):
                return self._fallback_win32_list_apps(args.get("app"))
            return res

        elif tool_name in ("desktop_list_windows", "agent_desktop_list_windows"):
            cmd = ["list-windows"]
            if args.get("app"):
                cmd.extend(["--app", str(args["app"])])
            res = self.run_cli_command(cmd)
            if not res.get("ok") and "EnumWindows" in json.dumps(res):
                return self._fallback_win32_list_windows(args.get("app"))
            return res

        elif tool_name in ("desktop_snapshot", "agent_desktop_snapshot"):
            cmd = ["snapshot"]
            if args.get("app"):
                cmd.extend(["--app", str(args["app"])])
            if args.get("compact", True):
                cmd.append("-i")
                cmd.append("--compact")
            if args.get("skeleton"):
                cmd.append("--skeleton")
            if args.get("max_depth"):
                cmd.extend(["--max-depth", str(args["max_depth"])])
            res = self.run_cli_command(cmd)
            if not res.get("ok") and "EnumWindows" in json.dumps(res):
                # Return window inventory snapshot as fallback
                return self._fallback_win32_list_windows(args.get("app"))
            return res

        elif tool_name in ("desktop_find", "agent_desktop_find"):
            cmd = ["find", str(args.get("query", ""))]
            if args.get("app"):
                cmd.extend(["--app", str(args["app"])])
            if args.get("role"):
                cmd.extend(["--role", str(args["role"])])
            return self.run_cli_command(cmd)

        elif tool_name in ("desktop_click", "agent_desktop_click"):
            target = str(args.get("target", ""))
            cmd = ["click", target]
            if args.get("headed"):
                cmd.append("--headed")
            return self.run_cli_command(cmd)

        elif tool_name in ("desktop_type", "agent_desktop_type"):
            text = str(args.get("text", ""))
            cmd = ["type", text]
            if args.get("target"):
                cmd.extend(["--target", str(args["target"])])
            # On Windows, typing needs --headed
            cmd.append("--headed")
            return self.run_cli_command(cmd)

        elif tool_name in ("desktop_press", "agent_desktop_press"):
            combo = str(args.get("combo", "return"))
            cmd = ["press", combo]
            if args.get("app"):
                cmd.extend(["--app", str(args["app"])])
            return self.run_cli_command(cmd)

        elif tool_name in ("desktop_focus_window", "agent_desktop_focus_window"):
            app = str(args.get("app", ""))
            return self.run_cli_command(["focus-window", "--app", app])

        elif tool_name in ("desktop_screenshot", "agent_desktop_screenshot"):
            out_path = args.get("output_path", str(ROOT / "scratch" / "agent_desktop_capture.png"))
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            cmd = ["screenshot", out_path]
            if args.get("app"):
                cmd.extend(["--app", str(args["app"])])
            res = self.run_cli_command(cmd)
            # If screenshot command requires app or encounters headless fallback, use DesktopController
            if not res.get("ok"):
                from bridges.desktop_controller import DesktopController
                ctl = DesktopController()
                return ctl.capture(output_path=out_path, software=args.get("app"))
            return res

        elif tool_name in ("desktop_launch", "agent_desktop_launch"):
            target = str(args.get("path_or_name", ""))
            cmd = ["launch", target]
            if args.get("wait_for_window", True):
                cmd.append("--activate")
            return self.run_cli_command(cmd)

        elif tool_name in ("desktop_batch", "agent_desktop_batch"):
            commands = args.get("commands", [])
            return self.run_cli_command(["batch", json.dumps(commands)])

        else:
            return {
                "ok": False,
                "error": {
                    "code": "UNKNOWN_TOOL",
                    "message": f"Tool '{tool_name}' is not recognized by AgentDesktopBridge.",
                },
            }


# --------------------------------------------------------------------------- Multi-Model Loop
def call_ollama_with_agent_desktop(
    model: str,
    prompt: str,
    max_turns: int = 4,
    tools: Optional[List[Dict[str, Any]]] = None,
    num_ctx: int = 4096,
) -> Dict[str, Any]:
    """Execute complete Thought -> Action (agent-desktop) -> Observation -> Conclusion loop for any Ollama model."""
    bridge = AgentDesktopBridge()
    tools_schema = tools or get_agent_desktop_tool_definitions()

    messages = [{"role": "user", "content": prompt}]
    trace = {
        "model": model,
        "prompt": prompt,
        "turns": [],
        "loop_completed": False,
        "final_answer": None,
        "n_tool_calls": 0,
    }

    for turn_idx in range(1, max_turns + 1):
        payload = {
            "model": model,
            "stream": False,
            "messages": messages,
            "tools": tools_schema,
            "options": {
                "num_ctx": num_ctx,
                "temperature": 0.1,
                "num_predict": 384,
            },
        }

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        t0 = time.time()
        resp_data = None
        for attempt in range(3):
            try:
                with _http.open(req, timeout=300) as r:
                    resp_data = json.loads(r.read().decode("utf-8"))
                break
            except Exception as e:
                time.sleep(2 * (attempt + 1))

        elapsed = round(time.time() - t0, 2)
        if not resp_data or "message" not in resp_data:
            trace["error"] = f"Failed to get response from {model}"
            break

        msg = resp_data["message"]
        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content", "")

        turn_entry = {
            "turn": turn_idx,
            "elapsed_s": elapsed,
            "assistant_content": content,
            "tool_calls": tool_calls,
            "tool_results": [],
        }

        if not tool_calls:
            # Model reached its concluding answer
            turn_entry["final"] = True
            trace["turns"].append(turn_entry)
            trace["final_answer"] = content
            trace["loop_completed"] = True
            break

        # Process Tool Calls
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        for call in tool_calls:
            fn = call.get("function") or {}
            tool_name = fn.get("name")
            raw_args = fn.get("arguments") or {}
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {}
            else:
                args = raw_args

            # Execute tool through Agent-Desktop
            exec_res = bridge.execute_tool(tool_name, args)
            res_str = json.dumps(exec_res, ensure_ascii=False)[:3000]

            # Return tool observation back to model
            messages.append({"role": "tool", "name": tool_name, "content": res_str})
            turn_entry["tool_results"].append({
                "name": tool_name,
                "arguments": args,
                "result": exec_res,
            })
            trace["n_tool_calls"] += 1

        trace["turns"].append(turn_entry)

    return trace


if __name__ == "__main__":
    print(f"=== Agent-Desktop Binary: {AGENT_DESKTOP_EXE} ===")
    bridge = AgentDesktopBridge()
    status = bridge.execute_tool("desktop_status", {})
    print("Status result:", json.dumps(status, indent=2, ensure_ascii=False))

    displays = bridge.execute_tool("desktop_list_displays", {})
    print("Displays result:", json.dumps(displays, indent=2, ensure_ascii=False))
