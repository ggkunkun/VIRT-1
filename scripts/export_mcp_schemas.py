# -*- coding: utf-8 -*-
"""export_mcp_schemas.py — Export standard MCP Tool Schemas and Manifests for Industrial CAD/CAM Toolchain."""

import os
import sys
import json

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.software_registry import (
    SOFTWARE_SPECS, DESKTOP_SHORTCUTS, diagnose_all, resolve_entry,
)
from bridges.tool_calling_specs import get_cadcam_tool_definitions

MCP_TARGET_DIR = r"C:\Users\Administrator\.gemini\antigravity\mcp\industrial-cadcam"

INSTRUCTIONS_MD = """# Industrial CAD/CAM Six-Software Toolchain MCP Guidelines

This MCP toolset integrates the 6 core industrial CAD/CAM software suites installed on the Windows desktop:
1. **SOLIDWORKS 2021**: Parametric 3D CAD modeling, EquationMgr global variables, VBA macros (`.swb`), STEP/IGES exports.
2. **AutoCAD 2026**: 2D Drafting & GB Engineering drawings, ActiveX COM, AutoLISP execution (`.lsp`), headless DXF via `ezdxf` / `accoreconsole`.
3. **Siemens NX 12.0 (中文版)**: High-end CAD/CAM, NXOpen Python journal execution via `run_journal.exe`, ExpressionCollection, multi-axis toolpaths.
4. **CIMCO Edit 2026**: CNC G-code & FANUC Macro B variable logic parsing (#100, #500, WHILE/DO/END), modal G-code checking, editor launching.
5. **CGTech VERICUT 9.6**: Batch kinematic machine simulation via `vericut.bat -b`, Auto-Diff 0.003mm gouge/excess material checking, collision log parsing.
6. **斯沃数控仿真 7.2 (SSCNC)**: Virtual shopfloor CNC emulation, FANUC 0i-TF / 0i-MD, G54 ~ G59 work coordinate setup, T1~T9 tool offset quadrant calculations.

## Desktop Shortcuts Grounding (Windows Host)
- SOLIDWORKS 2021: `C:\\Users\\Public\\Desktop\\SOLIDWORKS 2021.lnk`
- AutoCAD 2026: `C:\\Users\\Public\\Desktop\\AutoCAD 2026 - 简体中文 (Simplified Chinese).lnk`
- 斯沃数控仿真软件: `C:\\Users\\Public\\Desktop\\斯沃数控仿真软件.lnk`
- Vericut 9.6: `C:\\Users\\Public\\Desktop\\Vericut 9.6.lnk`
- CIMCO Edit 2026: `C:\\Users\\Public\\Desktop\\CIMCO Edit 2026.lnk`
- 中文版NX12.0: `C:\\Users\\Administrator\\Desktop\\中文版NX12.0.lnk`

## Multi-Modal Access
- **In-process Python SDK**: `from bridges.toolchain_client import CADCAMToolchainClient`
- **CLI**: `python cadcam_cli.py [preflight|dispatch|chain|server|gui|tools]`
- **REST API**: `POST http://127.0.0.1:8000/v1/cadcam/dispatch`
- **MCP stdio**: `python D:\\Virtu模型\\bridges\\cadcam_mcp_server.py`
"""

def export():
    os.makedirs(MCP_TARGET_DIR, exist_ok=True)
    
    # 1. Write instructions.md
    with open(os.path.join(MCP_TARGET_DIR, "instructions.md"), "w", encoding="utf-8") as f:
        f.write(INSTRUCTIONS_MD)
    print(f"Wrote instructions.md to {MCP_TARGET_DIR}")

    # 2. Write tool schema files
    defs = get_cadcam_tool_definitions()
    exported_names = []
    for d in defs:
        fn = d["function"]
        name = fn["name"]
        schema = {
            "name": name,
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {"type": "object", "properties": {}})
        }
        json_path = os.path.join(MCP_TARGET_DIR, f"{name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)
        exported_names.append(name)
    print(f"Exported {len(exported_names)} MCP tool schemas: {exported_names}")

    # 3. Write stdio MCP client config template in workspace
    mcp_config = {
        "mcpServers": {
            "industrial-cadcam": {
                "command": sys.executable,
                "args": [os.path.join(_ROOT, "bridges", "cadcam_mcp_server.py")],
                "env": {
                    "PYTHONIOENCODING": "utf-8"
                }
            }
        }
    }
    config_path = os.path.join(_ROOT, "mcp_cadcam_config.json")
    # 合并写：只更新 industrial-cadcam 条目，保留用户手工加进同一份配置的其它
    # MCP server（例如 external/windows-computer-use-mcp）。整文件覆盖会静默抹掉它们。
    existing_servers: dict = {}
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            prev = json.load(fh)
        if isinstance(prev, dict) and isinstance(prev.get("mcpServers"), dict):
            existing_servers = dict(prev["mcpServers"])
    except (OSError, ValueError):
        existing_servers = {}
    existing_servers["industrial-cadcam"] = mcp_config["mcpServers"]["industrial-cadcam"]
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": existing_servers}, f, ensure_ascii=False, indent=2)
    print(f"Wrote MCP client config: {config_path} ({len(existing_servers)} servers)")

    # 4. Write full Toolchain Manifest
    diag = diagnose_all()
    manifest = {
        "manifest_version": "1.0.0",
        "title": "Industrial CAD/CAM Six-Software Agent Toolchain Manifest",
        "description": "Stable, reusable toolchain invocation interface for AI Agents.",
        "desktop_shortcuts": DESKTOP_SHORTCUTS,
        # 入口形态会漂移（.lnk 可能被换成直连 .exe），显式导出本次实际命中的入口，
        # 避免 manifest 里留下一个已不存在的路径让下游误判。
        "resolved_entries": {
            key: resolve_entry(key).get("entry_path") for key in DESKTOP_SHORTCUTS
        },
        "diagnostics": diag,
        "tools": defs,
        "access_modes": [
            {
                "name": "Python SDK",
                "entrypoint": "bridges.toolchain_client.CADCAMToolchainClient",
                "example": "from bridges.toolchain_client import CADCAMToolchainClient\nclient = CADCAMToolchainClient()\nclient.preflight()"
            },
            {
                "name": "Command-Line Interface (CLI)",
                "entrypoint": "cadcam_cli.py",
                "example": "python cadcam_cli.py preflight"
            },
            {
                "name": "Model Context Protocol (MCP)",
                "entrypoint": "bridges.cadcam_mcp_server.py",
                "config_file": "mcp_cadcam_config.json"
            },
            {
                "name": "HTTP REST API Microservice",
                "entrypoint": "bridges.cadcam_rest_server.py",
                "default_url": "http://127.0.0.1:8000",
                "example": "curl -X POST http://127.0.0.1:8000/v1/cadcam/preflight"
            },
            {
                "name": "LLM Function Calling Schema",
                "entrypoint": "bridges.tool_calling_specs.get_cadcam_tool_definitions()",
                "dispatcher": "bridges.tool_calling_specs.execute_tool_call(name, args)"
            }
        ]
    }
    manifest_path = os.path.join(_ROOT, "cadcam_toolchain_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Wrote Toolchain Manifest: {manifest_path}")

if __name__ == "__main__":
    export()
