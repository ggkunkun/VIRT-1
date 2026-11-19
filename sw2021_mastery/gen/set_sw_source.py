# -*- coding: utf-8 -*-
"""提权：把 SOLIDWORKS 2021 core 的 net 安装源改为本地展开目录（先备份）。"""
import json, traceback, winreg

SQ = "1752A0C9EAA4EEF46B3730B8838BE5CF"
NEW = r"D:\SW2021_SRC\swwi\data\"
OUT = r"D:\Virtu模型\sw2021_mastery\work\sourcelist_change.json"
BK = r"D:\Virtu模型\sw2021_mastery\work\sourcelist_backup.json"

out = {"ok": False, "trace": None}
try:
    base = rf"SOFTWARE\Classes\Installer\Products\{SQ}\SourceList"
    k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0, winreg.KEY_READ | winreg.KEY_WRITE)
    # 备份
    old_net = winreg.QueryValueEx(k, "net\\1") if False else None
    kn = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + r"\net", 0, winreg.KEY_READ | winreg.KEY_WRITE)
    old_net_val, old_net_type = winreg.QueryValueEx(kn, "1")
    last = winreg.QueryValueEx(k, "LastUsedSource")
    json.dump({"net1": [old_net_val, old_net_type], "lastused": list(last)},
              open(BK, "w", encoding="utf-8"), ensure_ascii=False)
    # 写新源
    winreg.SetValueEx(kn, "1", 0, winreg.REG_SZ, NEW)
    winreg.SetValueEx(k, "LastUsedSource", 0, winreg.REG_EXPAND_SZ, "n;1;" + NEW)
    kn.Close(); k.Close()
    # 复核
    kn = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + r"\net")
    out["verify_net1"] = winreg.QueryValueEx(kn, "1")[0]
    kn.Close()
    out["ok"] = True
except Exception:
    out["trace"] = traceback.format_exc()
finally:
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
print("DONE", out["ok"])
