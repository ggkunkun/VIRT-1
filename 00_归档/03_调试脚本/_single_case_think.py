# -*- coding: utf-8 -*-
"""单案例思考：模型只面对一个 SW 实例/一个文档的原生特征树，输出结构化理解并验收。"""
import datetime
import json
import os
import sys
import time
import urllib.request

ROOT = r"D:\Virtu模型"
sys.path.insert(0, ROOT)
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
MODEL = os.environ.get("VIRTU_SELF_MODEL", "virtu-master:latest")
CTX = os.path.join(ROOT, "runs", "single_case_context.json")
ctx = json.load(open(CTX, encoding="utf-8"))

# 只保留模型需要的事实，不放任何「标准答案」
feed = {
    "single_case_rule": ctx["single_case_rule"],
    "sldworks_process_count": ctx.get("sldworks_process_count"),
    "open_document_count": ctx.get("open_document_count"),
    "active_document": ctx.get("active_document"),
    "active_document_type": ctx.get("active_document_type"),
    "body_count": ctx.get("body_count"),
    "native_feature_tree": ctx.get("native_feature_tree"),
    "mass_properties": ctx.get("mass_properties"),
    "bbox_mm": ctx.get("bbox_mm"),
    "reference_revolve_volume_mm3": 37404.5875,
}

SYS = ("你只面对一个 SolidWorks 案例：一个进程、一个活动文档、一个实体。"
       "请认真读下面的原生特征树和质量属性，输出且只输出一个 JSON 对象，字段为：\n"
       "document, single_case(布尔), key_features(可编辑建模特征名数组，不含基准面/文件夹), "
       "forming_method(成形方法), feature_order(建模顺序数组), "
       "volume_mm3, bbox_mm, cut_volume_mm3(用 reference_revolve_volume_mm3 减当前体积算出来), "
       "what_to_do_next(基于这个单一案例，下一步最该做什么)。\n"
       "数值照抄或按给定数据计算，不要编造；不要输出 JSON 以外的文字。")


def llm(fmt="json"):
    p = {"model": MODEL,
         "messages": [{"role": "system", "content": SYS},
                      {"role": "user", "content": "单案例数据：\n" +
                       json.dumps(feed, ensure_ascii=False)}],
         "stream": False, "format": fmt,
         "options": {"temperature": 0.1, "num_predict": 1000}}
    q = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                               data=json.dumps(p, ensure_ascii=False).encode("utf-8"),
                               headers={"Content-Type": "application/json"}, method="POST")
    with OPENER.open(q, timeout=300) as r:
        return json.loads(r.read().decode())


def get_obj(text):
    dec = json.JSONDecoder()
    for i, c in enumerate(text or ""):
        if c == "{":
            try:
                o, _ = dec.raw_decode(text[i:])
                if isinstance(o, dict):
                    return o
            except Exception:
                pass
    return None


t0 = time.time()
raw, ans, err = "", None, None
try:
    d = llm()
    raw = d.get("message", {}).get("content") or ""
    ans = get_obj(raw)
except Exception as e:
    err = type(e).__name__ + ": " + str(e)[:120]
print("RAW", raw[:900].replace("\n", " "), flush=True)
if err:
    print("ERR", err, flush=True)

TRUTH_V = 36019.1452
TRUTH_CUT = 37404.5875 - TRUTH_V
checks = {}
a = ans or {}
try:
    checks["document"] = a.get("document") == ctx.get("active_document")
except Exception:
    checks["document"] = False
checks["single_case"] = a.get("single_case") is True
kf = a.get("key_features") or []
checks["has_revolve_feature"] = any("旋转" in str(x) for x in kf)
checks["has_cut_feature"] = any("切除" in str(x) for x in kf)
try:
    checks["volume"] = abs(float(a.get("volume_mm3")) - TRUTH_V) < 0.01
except Exception:
    checks["volume"] = False
try:
    checks["cut_volume_computed"] = abs(float(a.get("cut_volume_mm3")) - TRUTH_CUT) < 0.01
except Exception:
    checks["cut_volume_computed"] = False
try:
    checks["bbox"] = all(abs(float(x) - float(y)) < 0.01
                         for x, y in zip(a.get("bbox_mm") or [], ctx.get("bbox_mm") or [])) and len(a.get("bbox_mm") or []) == 3
except Exception:
    checks["bbox"] = False
fm = str(a.get("forming_method") or "")
checks["forming_method"] = any(k in fm for k in ("旋转", "回转", "revolve"))
score = sum(checks.values())
print("\nSINGLE_CASE_THINKING_SCORE %d/%d = %.1f%%" %
      (score, len(checks), 100.0 * score / len(checks)), flush=True)
for k, v in checks.items():
    print("  %-24s %s" % (k, "PASS" if v else "FAIL"), flush=True)
print("WHAT_NEXT", str(a.get("what_to_do_next") or "")[:260], flush=True)

out = {"stamp": datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
       "model": MODEL, "elapsed_s": round(time.time() - t0, 2),
       "context": feed, "raw_model_output": raw, "model_json": ans,
       "acceptance": checks, "score": score, "total": len(checks),
       "percent": round(100.0 * score / len(checks), 1), "error": err}
p = os.path.join(ROOT, "runs", "single_case_think_" + out["stamp"] + ".json")
json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("TRACE", p, flush=True)
