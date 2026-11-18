# -*- coding: utf-8 -*-
"""工具链实弹验证：调用各 bridge 关键动作，记录成功/失败/异常。"""
import os, sys, io, json, traceback

OUT = r"D:\Virtu模型\_bridge_probe_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

os.chdir(r"D:\Virtu模型")
sys.path.insert(0, r"D:\Virtu模型")

if os.path.exists(OUT):
    os.remove(OUT)

def probe(name, fn):
    try:
        r = fn()
        if isinstance(r, dict):
            log(name, "OK", "status=", r.get("status"), "keys=", list(r.keys())[:8])
        else:
            log(name, "OK", "type=", type(r).__name__, "repr=", str(r)[:200])
    except Exception as e:
        log(name, "EXC", type(e).__name__, str(e)[:300])
        log("  TRACE", traceback.format_exc().splitlines()[-1][:300])

# 1. CIMCO Macro B 校验（纯 Python）
from bridges.cimco_bridge import CIMCOBridge
cimco = CIMCOBridge()
probe("cimco.validate_macro", lambda: cimco.validate_fanuc_macro_b("#100=53.0\nWHILE [#100 GT 0] DO 1\n#100=#100-1\nEND 1\nM30"))

# 2. SSCNC 刀偏计算（纯 Python）
from bridges.sscnc_bridge import SSCNCBridge
sscnc = SSCNCBridge()
probe("sscnc.calculate_offsets", lambda: sscnc.calculate_tool_offsets([
    {"tool_num": 1, "type": "turning_rough", "x": 120.5, "z": 45.2, "r": 0.8, "quadrant": 3}]))

# 3. AutoCAD 无头 DXF（ezdxf 或 COM）
from bridges.autocad_bridge import AutoCADBridge
cad = AutoCADBridge()
probe("autocad.create_dxf", lambda: cad.create_headless_dxf(
    "shaft_drawing",
    [{"type": "circle", "center": [0, 0], "radius": 26.5},
     {"type": "line", "start": [-30, 0], "end": [30, 0]}],
    output_path=r"D:\Virtu模型\_probe_shaft.dxf"))

# 4. SolidWorks 连接探测
from bridges.solidworks_bridge import SolidWorksBridge
sw = SolidWorksBridge()
probe("solidworks.connect", lambda: sw.connect())

# 5. NX journal 运行（无头）
from bridges.nx_bridge import SiemensNXBridge
nx = SiemensNXBridge()
probe("nx.run_journal_missing", lambda: nx.run_python_journal(r"D:\Virtu模型\_no_such_script.py"))

# 6. VERICUT 批处理仿真（无工程文件路径时）
from bridges.vericut_bridge import VericutBridge
vc = VericutBridge()
probe("vericut.run_simulation_missing", lambda: vc.run_batch_simulation(r"D:\Virtu模型\_no_such.vcproject"))

# 7. 编排器整体初始化
from bridges.six_software_orchestrator import SixSoftwareOrchestrator
orch = SixSoftwareOrchestrator()
probe("orchestrator.preflight", lambda: orch.preflight())

# 8. 工具定义导出
from bridges.tool_calling_specs import get_cadcam_tool_definitions
try:
    tools = get_cadcam_tool_definitions()
    log("tool_defs", "OK", "count=", len(tools))
except Exception as e:
    log("tool_defs", "EXC", type(e).__name__, str(e)[:300])

log("DONE")
