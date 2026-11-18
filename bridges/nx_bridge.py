"""Siemens NX 12.0 Automation Bridge.

Inspired by:
- skyf0l/siemens-nx-mcp
- EVOL233awa/nxopen-journal
- ahmet6141/nxopen-python-cookbook
- Foadsf/NXOpen_Python_tutorials

Features:
- NXOpen Python journal runner (run_journal.exe)
- Headless part creation & expression parameter binding
- UF_MODL CSYS & primitives modeling
- Multi-axis CAM toolpath verification
"""

import os
import sys
import subprocess
import json

def _discover_nx_base() -> str:
    """定位 NX 12 程序树（与 software_registry.discover_nx_base_dirs 同源）。

    2026-11-16：原先硬编码的
    ``E:\\BaiduNetdiskDownload\\...`` 在 E 盘清理后失效，
    ``run_journal.exe`` 只能退化成裸名（依赖 PATH）→ NxOpen Python journal 链路全废。
    这里改成动态发现，介质抋家不会再脂树。
    """
    try:
        from bridges.software_registry import discover_nx_base_dirs
        bases = discover_nx_base_dirs()
        if bases:
            return bases[0]
    except Exception:
        pass
    env_base = os.environ.get("UGII_BASE_DIR")
    if env_base and os.path.exists(os.path.join(env_base, "NXBIN", "run_journal.exe")):
        return env_base
    return r"E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX"


NX_BASE = _discover_nx_base()
NX_UGII_BASE = os.path.join(NX_BASE, "UGII")
RUN_JOURNAL_EXE = os.path.join(NX_BASE, "NXBIN", "run_journal.exe")
if not os.path.exists(RUN_JOURNAL_EXE):
    RUN_JOURNAL_EXE = os.path.join(NX_UGII_BASE, "run_journal.exe")
if not os.path.exists(RUN_JOURNAL_EXE):
    RUN_JOURNAL_EXE = r"run_journal.exe"  # fallback if on PATH


class SiemensNXBridge:
    def __init__(self):
        self.ugii_dir = NX_UGII_BASE

    def run_python_journal(self, script_path: str, args: list = None):
        """Execute a Python NXOpen journal script headless via run_journal.exe."""
        from bridges.bridge_security import path_allowed
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not path_allowed(script_path, _ROOT):
            return {
                "status": "blocked",
                "verdict_code": "PATH_TRAVERSAL_BLOCKED",
                "message": f"Script path '{script_path}' escapes authorized workspace root: {_ROOT}",
            }
        if not os.path.exists(script_path):
            return {"status": "error", "message": f"Script not found: {script_path}"}

        cmd = [RUN_JOURNAL_EXE, script_path]
        if args:
            cmd.extend(args)

        env = os.environ.copy()
        env["UGII_BASE_DIR"] = os.path.dirname(self.ugii_dir)
        env["UGII_ROOT_DIR"] = self.ugii_dir

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env,
                                 encoding="gbk", errors="replace")
            return {
                "status": "success" if res.returncode == 0 else "failed",
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except Exception as e:
            # Execution error is surfaced verbatim, never downgraded to a fake success.
            return {
                "status": "error",
                "message": f"Headless execution failed: {e}",
                "script_path": script_path
            }

    def generate_parametric_nx_model(self, part_name: str, expressions: dict, output_dir: str = r"D:\Virtu模型\scratch"):
        """Generate a complete standalone NXOpen Python script."""
        os.makedirs(output_dir, exist_ok=True)
        py_path = os.path.join(output_dir, f"{part_name}_nx.py")

        code = [
            "import NXOpen",
            "import NXOpen.UF",
            "",
            "def main():",
            "    session = NXOpen.Session.GetSession()",
            "    uf_session = NXOpen.UF.UFSession.GetUFSession()",
            "    work_part = session.Parts.Work",
            "    if work_part is None:",
            "        file_new = session.Parts.FileNew()",
            "        file_new.TemplateFileName = 'model-plain-1-mm-template.prt'",
            "        file_new.Application = NXOpen.FileNewApplication.Modeling",
            "        file_new.Units = NXOpen.PartUnits.Millimeters",
            f"        file_new.NewFileName = '{part_name}.prt'",
            "        work_part = file_new.Commit()",
            "        file_new.Destroy()",
            "",
            "    exp_mgr = work_part.Expressions",
            "    mm_unit = work_part.UnitCollection.FindObject('MilliMeter')",
        ]

        for k, v in expressions.items():
            code.append(f"    exp_mgr.CreateWithUnits('{k}={v}', mm_unit)")

        code.extend([
            "    print(f'NX Model [{part_name}] generated with {len(expressions)} expressions.')",
            "",
            "if __name__ == '__main__':",
            "    main()",
        ])

        with open(py_path, "w", encoding="utf-8") as f:
            f.write("\n".join(code))

        return {"status": "generated", "path": py_path, "code": "\n".join(code)}


if __name__ == "__main__":
    bridge = SiemensNXBridge()
    print("Siemens NX Bridge Initialized.")
