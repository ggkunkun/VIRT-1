"""Patch bridges/tool_calling_specs.py, bridges/solidworks_bridge.py,
bridges/autocad_bridge.py, and bridges/nx_bridge.py with security gates.
"""
from pathlib import Path
import re

ROOT = Path(r"D:\Virtu模型")

def patch_tool_calling_specs():
    target_file = ROOT / "bridges" / "tool_calling_specs.py"
    text = target_file.read_text(encoding="utf-8")
    
    # We want to replace execute_tool_call start
    old_block = '''    args = arguments or {}

    # 桌面输入闸门排在最前：被拒绝的调用不得构造任何 bridge（bridge 构造会尝试
    # 挂载 SOLIDWORKS/NX/AutoCAD 的 COM），也不得读进程表。零副作用才是拒绝。
    if tool_name == "cadcam_desktop_gui":
        from bridges.desktop_gate import gate
        blocked = gate(tool_name, args)
        if blocked is not None:
            return blocked

    orch = get_orchestrator()

    # Compatibility layer: Map legacy training corpora tool names and args to canonical tools
    legacy_aliases = {
        "solidworks.create_parametric_part": ("cadcam_solidworks_model", {
            "action": "create_parametric_part",
            "part_name": args.get("part_name", "part"),
            "dimensions": args.get("spec", args.get("dimensions", {})),
            "vba_code": args.get("vba_code", ""),
        }),
        "nx.create_nxopen_script": ("cadcam_nx_journal", {
            "action": "create_parametric_model",
            "part_name": args.get("part_name", "nx_part"),
            "expressions": args.get("spec", args.get("expressions", {})),
            "script_path": args.get("script_path", ""),
        }),
        "autocad.create_autolisp": ("cadcam_autocad_draw", {
            "action": "send_lisp",
            "code": args.get("code", ""),
            "drawing_name": args.get("drawing_name", "drawing"),
            "entities": args.get("entities", []),
            "script_path": args.get("script_path", ""),
        }),
        "cimco.create_macro_b": ("cadcam_cimco_validate", {
            "action": "validate_macro",
            "code": args.get("code", args.get("macro_code", "")),
            "nc_file_path": args.get("nc_file_path", ""),
        }),
        "vericut.create_project_config": ("cadcam_vericut_simulate", {
            "action": "run_simulation",
            "project_path": args.get("project_path", ""),
            "log_path": args.get("log_path", ""),
        }),
        "sscnc.create_setup_guide": ("cadcam_sscnc_control", {
            "action": "calculate_offsets",
            "tools": args.get("tools", []),
        }),
        "cad.parse_wish_intent": ("cadcam_run_full_chain", {
            "wish": args.get("wish", args.get("intent", "")),
            "out_root": args.get("out_root"),
            "skip": tuple(args.get("skip", [])),
        }),
    }

    if tool_name in legacy_aliases:
        canonical_name, adapted_args = legacy_aliases[tool_name]
        tool_name = canonical_name
        args = adapted_args'''

    new_block = '''    args = arguments or {}

    # Compatibility layer: Map legacy training corpora tool names and args to canonical tools
    legacy_aliases = {
        "solidworks.create_parametric_part": ("cadcam_solidworks_model", {
            "action": "create_parametric_part",
            "part_name": args.get("part_name", "part"),
            "dimensions": args.get("spec", args.get("dimensions", {})),
            "vba_code": args.get("vba_code", ""),
        }),
        "nx.create_nxopen_script": ("cadcam_nx_journal", {
            "action": "create_parametric_model",
            "part_name": args.get("part_name", "nx_part"),
            "expressions": args.get("spec", args.get("expressions", {})),
            "script_path": args.get("script_path", ""),
        }),
        "autocad.create_autolisp": ("cadcam_autocad_draw", {
            "action": "send_lisp",
            "code": args.get("code", ""),
            "drawing_name": args.get("drawing_name", "drawing"),
            "entities": args.get("entities", []),
            "script_path": args.get("script_path", ""),
        }),
        "cimco.create_macro_b": ("cadcam_cimco_validate", {
            "action": "validate_macro",
            "code": args.get("code", args.get("macro_code", "")),
            "nc_file_path": args.get("nc_file_path", ""),
        }),
        "vericut.create_project_config": ("cadcam_vericut_simulate", {
            "action": "run_simulation",
            "project_path": args.get("project_path", ""),
            "log_path": args.get("log_path", ""),
        }),
        "sscnc.create_setup_guide": ("cadcam_sscnc_control", {
            "action": "calculate_offsets",
            "tools": args.get("tools", []),
        }),
        "cad.parse_wish_intent": ("cadcam_run_full_chain", {
            "wish": args.get("wish", args.get("intent", "")),
            "out_root": args.get("out_root"),
            "skip": tuple(args.get("skip", [])),
        }),
    }

    if tool_name in legacy_aliases:
        canonical_name, adapted_args = legacy_aliases[tool_name]
        tool_name = canonical_name
        args = adapted_args

    # 1. 桌面输入闸门排在最前：被拒绝的调用不得构造任何 bridge（零副作用拦截）
    if tool_name == "cadcam_desktop_gui":
        from bridges.desktop_gate import gate
        blocked = gate(tool_name, args)
        if blocked is not None:
            return blocked

    # 2. 路径穿越防护：确保所有路径参数严格位于工作区内
    from bridges.bridge_security import path_allowed
    path_param_keys = (
        "script_path", "output_dir", "out_root", "nc_file_path",
        "project_path", "log_path", "output_path", "output_dxf", "file_path", "target_path"
    )
    for pk in path_param_keys:
        if pk in args and args[pk]:
            val = str(args[pk])
            if not path_allowed(val, _ROOT):
                return {
                    "status": "blocked",
                    "verdict_code": "PATH_TRAVERSAL_BLOCKED",
                    "detail": f"Field '{pk}' with path '{val}' escapes authorized workspace '{_ROOT}'",
                    "channel": "repo_execute_tool_call",
                    "input_sent": False,
                }

    # 3. 参数安全与代码注入审计（VBA Shell, AutoLISP startapp, 几何超差, 撞机下刀）
    from virtu_omni.security.auditor import ModelSecurityAuditor
    sec_auditor = ModelSecurityAuditor(workspace_root=_ROOT)
    audit_res = sec_auditor.audit_tool_arguments(tool_name, args)
    if not audit_res["passed"]:
        return {
            "status": "blocked",
            "verdict_code": "SECURITY_AUDIT_VIOLATION",
            "violations": audit_res["violations"],
            "detail": "; ".join(audit_res["violations"]),
            "channel": "repo_execute_tool_call",
            "input_sent": False,
        }

    orch = get_orchestrator()'''

    norm_text = text.replace("\r\n", "\n")
    norm_old = old_block.replace("\r\n", "\n")
    if norm_old in norm_text:
        new_text = norm_text.replace(norm_old, new_block.replace("\r\n", "\n"))
        target_file.write_text(new_text.replace("\n", "\r\n"), encoding="utf-8")
        print("tool_calling_specs.py patched successfully!")
    else:
        print("ERROR: old_block not found in tool_calling_specs.py")

def patch_solidworks_bridge():
    target_file = ROOT / "bridges" / "solidworks_bridge.py"
    text = target_file.read_text(encoding="utf-8")
    
    old_frag = '''        os.makedirs(os.path.dirname(temp_swp_path), exist_ok=True)
        bas_path = temp_swp_path.replace(".swp", ".bas")
        with open(bas_path, "w", encoding="gbk", errors="ignore") as f:
            f.write(vba_code)'''
            
    new_frag = '''        # Security sanitizer: block dangerous VBA execution
        import re
        if re.search(r"(?i)\\b(Shell|CreateObject\\s*\\(\\s*[\"']WScript\\.Shell|cmd\\.exe|powershell|FileSystemObject|Kill\\b|RmDir\\b|Environ\\b)", vba_code or ""):
            return {
                "status": "blocked",
                "verdict_code": "VBA_SECURITY_VIOLATION",
                "message": "VBA macro contains disallowed system execution or shell escape commands.",
            }

        os.makedirs(os.path.dirname(temp_swp_path), exist_ok=True)
        bas_path = temp_swp_path.replace(".swp", ".bas")
        with open(bas_path, "w", encoding="gbk", errors="ignore") as f:
            f.write(vba_code)'''
            
    norm_text = text.replace("\r\n", "\n")
    norm_old = old_frag.replace("\r\n", "\n")
    if norm_old in norm_text:
        new_text = norm_text.replace(norm_old, new_frag.replace("\r\n", "\n"))
        target_file.write_text(new_text.replace("\n", "\r\n"), encoding="utf-8")
        print("solidworks_bridge.py patched successfully!")
    else:
        print("ERROR: old_frag not found in solidworks_bridge.py")

def patch_autocad_bridge():
    target_file = ROOT / "bridges" / "autocad_bridge.py"
    text = target_file.read_text(encoding="utf-8")
    
    old_frag = '''    def send_lisp_command(self, lisp_code: str):
        """Send AutoLISP expression to active AutoCAD document."""
        conn = self.connect()'''
        
    new_frag = '''    def send_lisp_command(self, lisp_code: str):
        """Send AutoLISP expression to active AutoCAD document."""
        # Security sanitizer: block dangerous AutoLISP execution
        import re
        if re.search(r"(?i)\\b(startapp|vl-file-delete|vl-file-copy|vl-file-rename|command\\s+[\"']sh)\\b", lisp_code or ""):
            return {
                "status": "blocked",
                "verdict_code": "AUTOLISP_SECURITY_VIOLATION",
                "message": "AutoLISP command contains disallowed system execution or file deletion functions.",
            }
        conn = self.connect()'''
        
    norm_text = text.replace("\r\n", "\n")
    norm_old = old_frag.replace("\r\n", "\n")
    if norm_old in norm_text:
        new_text = norm_text.replace(norm_old, new_frag.replace("\r\n", "\n"))
        target_file.write_text(new_text.replace("\n", "\r\n"), encoding="utf-8")
        print("autocad_bridge.py patched successfully!")
    else:
        print("ERROR: old_frag not found in autocad_bridge.py")

def patch_nx_bridge():
    target_file = ROOT / "bridges" / "nx_bridge.py"
    text = target_file.read_text(encoding="utf-8")
    
    old_frag = '''    def run_python_journal(self, script_path: str, args: list = None):
        """Execute a Python NXOpen journal script headless via run_journal.exe."""
        if not os.path.exists(script_path):'''
        
    new_frag = '''    def run_python_journal(self, script_path: str, args: list = None):
        """Execute a Python NXOpen journal script headless via run_journal.exe."""
        from bridges.bridge_security import path_allowed
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not path_allowed(script_path, _ROOT):
            return {
                "status": "blocked",
                "verdict_code": "PATH_TRAVERSAL_BLOCKED",
                "message": f"Script path '{script_path}' escapes authorized workspace root: {_ROOT}",
            }
        if not os.path.exists(script_path):'''
        
    norm_text = text.replace("\r\n", "\n")
    norm_old = old_frag.replace("\r\n", "\n")
    if norm_old in norm_text:
        new_text = norm_text.replace(norm_old, new_frag.replace("\r\n", "\n"))
        target_file.write_text(new_text.replace("\n", "\r\n"), encoding="utf-8")
        print("nx_bridge.py patched successfully!")
    else:
        print("ERROR: old_frag not found in nx_bridge.py")

if __name__ == "__main__":
    patch_tool_calling_specs()
    patch_solidworks_bridge()
    patch_autocad_bridge()
    patch_nx_bridge()
