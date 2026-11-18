# -*- coding: utf-8 -*-
"""单案例环境：只保留一个 SLDWORKS 实例、只打开一个文档，输出原生特征树上下文。"""
import json
import os
import sys
import time

sys.path.insert(0, r"D:\Virtu模型")
import win32com.client as w
import pythoncom
from bridges.feature_ops import _connect, single_case

ROOT = r"D:\Virtu模型"
PART = os.path.join(ROOT, "works", "model_supervised", "model_part.SLDPRT")
CTX = os.path.join(ROOT, "runs", "single_case_context.json")

pythoncom.CoInitialize()
# 冷启动可能瞬时报「服务器运行失败」，最多重试 3 次，且不新增实例
sw = None
for i in range(3):
    try:
        sw = _connect()
        _ = sw.RevisionNumber
        break
    except Exception as e:
        print("connect retry", i + 1, str(e)[:70], flush=True)
        time.sleep(2)
if sw is None:
    raise SystemExit("NO_SINGLE_SW_INSTANCE")
sw.Visible = True

# 清空所有已打开文档，保证「一个案例」
try:
    sw.CloseAllDocuments(True)
except Exception as e:
    print("close_all note", str(e)[:70], flush=True)
time.sleep(0.8)


def ev():
    return w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


doc = sw.OpenDoc6(PART, 1, 0, "", ev(), ev())
if not doc:
    raise SystemExit("OPEN_SINGLE_CASE_FAILED")
try:
    doc.ShowNamedView2("*Isometric", 7)
    doc.ViewZoomtofit2()
except Exception:
    pass
time.sleep(1.0)

ctx = single_case()
ctx["case_file"] = PART
ctx["single_case_rule"] = "只允许一个 SLDWORKS 实例 + 一个活动文档"
print(json.dumps({k: v for k, v in ctx.items() if k != "native_feature_tree"},
                 ensure_ascii=False, indent=2), flush=True)
print("NATIVE_FEATURE_TREE", flush=True)
for f in ctx.get("native_feature_tree", []):
    print("   %-22s %s" % (f["name"], f["type"]), flush=True)
json.dump(ctx, open(CTX, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("CONTEXT", CTX, flush=True)
print("SINGLE_CASE_ASSERT", "PASS" if ctx.get("single_case_ok") else "FAIL", flush=True)
