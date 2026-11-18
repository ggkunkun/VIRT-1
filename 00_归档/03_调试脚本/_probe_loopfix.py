# -*- coding: utf-8 -*-
"""决定性实验：回喂 tool 结果时带上 tool_name/id 且不带 thinking，模型能否推进到下一步。"""
import json, time, urllib.request, sys
sys.path.insert(0, r'D:\Virtu模型')
from bridges.tool_calling_specs import get_cadcam_tool_definitions
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
tools = get_cadcam_tool_definitions()
SYS = "你是工业智能体。历史里的 tool 结果是已执行完成的步骤，不要重复调用已成功的工具。每一步用 tool_calls 决定下一步。"
USER = "逆向 D:/step 的 STEP 总成，自己找最快方法，在 SOLIDWORKS 2021 建可编辑参数化实体并保存 .SLDPRT。"
RESULT = json.dumps({"all_ready": True, "ready_count": 6,
                     "solidworks": {"is_running": True, "com_registered": True},
                     "note": "预检已完成，勿重复调用"}, ensure_ascii=False)
for variant in ("clean", "with_thinking"):
    for model in ("virtu-toolcall", "virtu-ties-v1"):
        a = {"role":"assistant","content":"","tool_calls":[
              {"id":"call_1","type":"function","function":{"name":"cadcam_preflight","arguments":{}}}]}
        if variant == "with_thinking":
            a["thinking"] = "用户让我逆向 STEP，首先我需要调用预检工具确认软件状态。"
        msgs = [{"role":"system","content":SYS},{"role":"user","content":USER},a,
                {"role":"tool","tool_call_id":"call_1","tool_name":"cadcam_preflight","content":RESULT}]
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
            data=json.dumps({"model":model,"messages":msgs,"tools":tools,"stream":False,
                             "options":{"temperature":0.2,"num_predict":700}},ensure_ascii=False).encode(),
            headers={"Content-Type":"application/json"},method="POST")
        t0=time.time()
        try:
            with OP.open(req,timeout=240) as r: d=json.loads(r.read().decode())
            m=d.get("message",{})
            names=[c.get("function",{}).get("name") for c in (m.get("tool_calls") or [])]
            th=(m.get("thinking") or "")
            import re
            txt=(m.get("content") or "")+"\n"+th
            for x in re.findall(r'"name"\s*:\s*"(cadcam_[a-z_]+)"',txt): names.append("txt:"+x)
            print(f"{variant:14s} {model:20s} {time.time()-t0:5.1f}s calls={names} | {th[:150].replace(chr(10),' ')}")
        except Exception as e:
            print(variant,model,"ERR",type(e).__name__,str(e)[:120])
