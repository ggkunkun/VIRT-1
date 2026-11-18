# -*- coding: utf-8 -*-
"""cadcam_cli.py — Unified Command Line Interface for Industrial CAD/CAM Agent Toolchain.

Supports the 6 desktop industrial software applications:
1. SOLIDWORKS 2021
2. 斯沃数控仿真软件 SSCNC 7.2
3. CIMCO Edit 2026
4. AutoCAD 2026
5. Vericut 9.6
6. Siemens NX 12.0

Usage Examples:
    # 1. System & software preflight health check:
    python cadcam_cli.py preflight
    python cadcam_cli.py preflight --json

    # 2. Dispatch action to specific software:
    python cadcam_cli.py dispatch --software cimco --action validate_macro --code "#100=50\nM30"
    python cadcam_cli.py dispatch --software autocad --action create_dxf --params "{\"drawing_name\": \"shaft\", \"entities\": []}"
    python cadcam_cli.py dispatch --software solidworks --action connect

    # 3. Execute full 6-software manufacturing chain:
    python cadcam_cli.py chain --wish "精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm"

    # 4. Start Model Context Protocol (MCP) server:
    python cadcam_cli.py mcp

    # 5. Desktop GUI perception and control:
    python cadcam_cli.py gui capture --software solidworks --output sw_screen.png
    python cadcam_cli.py gui focus --software autocad
    python cadcam_cli.py gui dismiss-dialogs

    # 6. Export LLM tool calling JSON schemas:
    python cadcam_cli.py tools
"""

import os
import sys
import json
import time
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bridges.software_registry import (
    diagnose_all, SOFTWARE_SPECS, DISPATCH_SOFTWARE_TOOL,
)
from bridges.six_software_orchestrator import SixSoftwareOrchestrator
from bridges.tool_calling_specs import (
    get_cadcam_tool_definitions, execute_tool_call, approval_gate,
)
from bridges.desktop_controller import DesktopController


def cmd_preflight(args):
    report = diagnose_all()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=" * 75)
    print(" Industrial CAD/CAM Agent Toolchain Preflight Diagnostics")
    print(f" Summary: {report['ready_count']}/{report['total_software']} Software Ready | {report['running_count']} Currently Running")
    print("=" * 75)

    for key, info in report["software"].items():
        st = "[READY]" if info["is_ready"] else "[NOT FOUND]"
        run = f"RUNNING (PID: {info['running_pids']})" if info["is_running"] else "STOPPED"
        sc_st = "LNK OK" if info["shortcut_present"] else "NO LNK"
        print(f" {st:<11s} {info['display_name']:<30s} | {run:<22s} | {sc_st}")
        if info.get("binary_found"):
            print(f"             Binary: {info['binary_found']}")
        if info.get("shortcut_path"):
            print(f"             Shortcut: {info['shortcut_path']}")

    print("=" * 75)
    return 0 if report["all_ready"] else 1


def cmd_dispatch(args):
    orch = SixSoftwareOrchestrator()
    params = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except Exception as e:
            print(f"Error parsing --params JSON: {e}", file=sys.stderr)
            return 1

    # Convenience shortcut for code/script_path flags
    if args.code:
        params["code"] = args.code
    if args.script:
        params["script_path"] = args.script

    # Consent gate: CLI 直派必须与 REST /v1/cadcam/dispatch 落在同一道闸门上。
    # 之前这里直接 orch.dispatch()，是全工具链唯一能绕过审批的入口。
    dispatch_tool = DISPATCH_SOFTWARE_TOOL.get(
        str(args.software).strip().lower(), "cadcam_dispatch"
    )
    gate_payload = dict(params)
    gate_payload.update({"action": args.action, "software": args.software})
    blocked = approval_gate(dispatch_tool, gate_payload)
    if blocked is not None:
        print(json.dumps(blocked, ensure_ascii=False, indent=2))
        return 2

    t0 = time.perf_counter()
    res = orch.dispatch(args.software, args.action, params)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    if isinstance(res, dict):
        res.setdefault("execution_time_ms", elapsed_ms)
        if "data" not in res:
            res["data"] = {k: v for k, v in res.items()
                           if k not in ("status", "data", "execution_time_ms",
                                        "verdict_code", "detail", "note")}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("status") not in ("error", "failed", "blocked") else 1


def cmd_chain(args):
    orch = SixSoftwareOrchestrator()
    skip = tuple(args.skip.split(",")) if args.skip else ()
    # 与 REST /v1/chain/run 同一道闸门：全流水线会驱动软件并写盘，默认需显式授权。
    gate_payload = {"wish": args.wish, "out_root": args.output, "skip": list(skip)}
    blocked = approval_gate("cadcam_run_full_chain", gate_payload)
    if blocked is not None:
        print(json.dumps(blocked, ensure_ascii=False, indent=2))
        return 2
    print(f"Starting full CAD/CAM manufacturing chain for wish: {args.wish}")
    res = orch.run_full_chain(args.wish, out_root=args.output, skip=skip)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("status") == "success":
        print(f"\nChain Run Completed Successfully. Report: {res.get('report_md')}")
        return 0
    return 1


def cmd_mcp(args):
    from bridges.cadcam_mcp_server import run_stdio_server
    run_stdio_server()
    return 0


GUI_ACTION_ALIASES = {
    "type": "type_text",
    "dismiss": "dismiss_dialogs",
    "dismiss-dialogs": "dismiss_dialogs",
    "inspect-window": "inspect_window",
}


def cmd_gui(args):
    """一律经 execute_tool_call 走，好让桌面输入闸门对 CLI 通道同样生效。"""
    action = GUI_ACTION_ALIASES.get(args.gui_action, args.gui_action)
    payload = {"action": action}
    if args.software:
        payload["software"] = args.software
    if args.output:
        payload["output_path"] = args.output
    if args.x is not None:
        payload["x"] = int(args.x)
    if args.y is not None:
        payload["y"] = int(args.y)
    if args.button:
        payload["button"] = args.button
    if args.double:
        payload["double"] = True
    if args.text is not None:
        payload["text"] = args.text
    if args.keys:
        payload["keys"] = args.keys

    res = execute_tool_call("cadcam_desktop_gui", payload)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("status") not in ("error", "failed", "blocked") else 1


def cmd_tools(args):
    tools = get_cadcam_tool_definitions()
    print(json.dumps(tools, ensure_ascii=False, indent=2))
    return 0


def cmd_server(args):
    from bridges.cadcam_rest_server import start_rest_server
    start_rest_server(host=args.host, port=args.port)
    return 0


def cmd_agent(args):
    from virtu_omni.agent.cadcam_autonomous_agent import CADCAMAutonomousAgent
    agent = CADCAMAutonomousAgent()
    prompt = args.prompt
    modality = args.modality or "FUNCTION_CALLING"

    if args.explain:
        print(agent.explain_decision(prompt, modality=modality))
        return 0

    print(f"Agent Executing [{modality}]: {prompt}")
    rep = agent.solve(prompt, modality=modality)
    if args.json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(rep.summary_markdown())
        print("Data:\n", json.dumps(rep.result_data, ensure_ascii=False, indent=2))
    return 0 if rep.success else 1


def main():
    parser = argparse.ArgumentParser(
        description="Unified CLI for Industrial CAD/CAM Six-Software Agent Toolchain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # 1. preflight
    p_pf = sub.add_parser("preflight", help="Health check for all 6 industrial tools")
    p_pf.add_argument("--json", action="store_true", help="Output pure JSON")

    # 2. dispatch
    p_disp = sub.add_parser("dispatch", help="Dispatch an action to a specific CAD/CAM tool")
    p_disp.add_argument("-s", "--software", required=True, help="Target software (sw, nx, autocad, cimco, vericut, sscnc)")
    p_disp.add_argument("-a", "--action", required=True, help="Action name")
    p_disp.add_argument("-p", "--params", default="{}", help="JSON string of parameters")
    p_disp.add_argument("--code", help="Shortcut for code parameter")
    p_disp.add_argument("--script", help="Shortcut for script_path parameter")

    # 3. chain
    p_chain = sub.add_parser("chain", help="Run full 6-software manufacturing pipeline")
    p_chain.add_argument("-w", "--wish", required=True, help="Manufacturing intent/wish description")
    p_chain.add_argument("-o", "--output", help="Output directory for chain artifacts")
    p_chain.add_argument("--skip", help="Comma-separated stages to skip")

    # 4. mcp
    sub.add_parser("mcp", help="Run Model Context Protocol (MCP) stdio server")

    # 5. gui
    p_gui = sub.add_parser("gui", help="Desktop GUI perception & window automation")
    p_gui.add_argument("gui_action", choices=["capture", "focus", "click", "type", "type_text", "hotkey", "dismiss", "dismiss-dialogs", "dismiss_dialogs", "inspect_window", "inspect-window"])
    p_gui.add_argument("-s", "--software", help="Target software name")
    p_gui.add_argument("-o", "--output", help="Output path for screen capture")
    p_gui.add_argument("-x", type=int, help="X coordinate for click")
    p_gui.add_argument("-y", type=int, help="Y coordinate for click")
    p_gui.add_argument("--button", default="left", choices=["left", "right", "middle"])
    p_gui.add_argument("--double", action="store_true", help="Double click")
    p_gui.add_argument("--text", help="Text to type")
    p_gui.add_argument("--keys", help="Hotkey combination (e.g. ctrl,s)")

    # 6. tools
    sub.add_parser("tools", help="Export OpenAI/Claude tool calling JSON schema")

    # 7. agent (Direct Modality Dispatch)
    p_ag = sub.add_parser("agent", help="Execute task through specified access modality")
    p_ag.add_argument("-p", "--prompt", required=True, help="Task prompt or user manufacturing intent")
    p_ag.add_argument("--modality", default="FUNCTION_CALLING", help="Access modality (PYTHON_SDK, CLI, MCP, FUNCTION_CALLING, REST_API, DESKTOP_GUI, AGENT_CHAIN)")
    p_ag.add_argument("--explain", action="store_true", help="Explain the dispatch plan without executing")
    p_ag.add_argument("--json", action="store_true", help="Output execution report as JSON")

    # 8. server (High-Performance HTTP REST API Service)
    p_srv = sub.add_parser("server", help="Start CAD/CAM Toolchain HTTP REST API server")
    p_srv.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    p_srv.add_argument("--port", type=int, default=8000, help="Port (default 8000)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch_map = {
        "preflight": cmd_preflight,
        "dispatch": cmd_dispatch,
        "chain": cmd_chain,
        "mcp": cmd_mcp,
        "gui": cmd_gui,
        "tools": cmd_tools,
        "agent": cmd_agent,
        "server": cmd_server,
    }
    return dispatch_map[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
