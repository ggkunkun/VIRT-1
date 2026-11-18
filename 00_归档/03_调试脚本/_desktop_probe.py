# -*- coding: utf-8 -*-
"""探针2：实测 desktop_controller 交互通道 + agent_chain_executor 依赖链。"""
import os, sys, io, traceback

OUT = r"D:\Virtu模型\_desktop_probe_result.txt"

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
            log(name, "OK", "status=", r.get("status"), "keys=", list(r.keys())[:10])
        else:
            log(name, "OK", "repr=", str(r)[:200])
    except Exception as e:
        log(name, "EXC", type(e).__name__, str(e)[:300])
        log("  TRACE", traceback.format_exc().splitlines()[-1][:300])

# 1. DesktopController 初始化
from bridges.desktop_controller import DesktopController
ctl = DesktopController()
probe("desktop_controller.init", lambda: "ok")

# 2. 查找 SOLIDWORKS 窗口
probe("find_software_window(solidworks)", lambda: ctl.find_software_window("solidworks"))

# 3. 截图
probe("capture", lambda: ctl.capture(output_path=r"D:\Virtu模型\scratch\_probe_sw.png", software="solidworks"))

# 4. hotkey esc（依赖 subprocess powershell —— 关键故障路径测试）
probe("hotkey_esc", lambda: ctl.hotkey("esc"))

# 5. type_text（依赖 subprocess powershell —— 关键故障路径测试）
probe("type_text", lambda: ctl.type_text(""))

# 6. dismiss_all_dialogs（依赖 agent_chain_executor.preflight_apps）
probe("dismiss_all_dialogs", lambda: ctl.dismiss_all_dialogs())

# 7. agent_chain_executor 是否存在可导入
try:
    import agent_chain_executor as ace
    log("import agent_chain_executor", "OK", "has_preflight_apps=", hasattr(ace, "preflight_apps"))
except Exception as e:
    log("import agent_chain_executor", "EXC", type(e).__name__, str(e)[:300])

log("DONE")
