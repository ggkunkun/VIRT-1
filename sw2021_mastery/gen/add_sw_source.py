# -*- coding: utf-8 -*-
"""向 SOLIDWORKS 2021 core 产品的机器级源列表注册本地安装源（置顶 net 源）。"""
import ctypes, json

PCODE = "{9C0A2571-4AAE-4FEE-B673-038B38B85EFC}"
SRC = r"D:\SW2021_SRC\swwi\data\"
OUT = r"D:\Virtu模型\sw2021_mastery\work\add_source_result.json"

msi = ctypes.windll.msi
MSIINSTALLCONTEXT_MACHINE = 4
MSISOURCELIST_NETWORK = 1
res = {}

r = msi.MsiSourceListAddSourceExW(PCODE, None, MSIINSTALLCONTEXT_MACHINE,
                                  MSISOURCELIST_NETWORK, SRC, 0)
res["add_net_idx0"] = r

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f)
print("RESULT", json.dumps(res))
