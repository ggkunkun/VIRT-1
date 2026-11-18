# -*- coding: utf-8 -*-
import json, time, urllib.request
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
URL = "http://127.0.0.1:11434/api/chat"
TOOLS = [{
  "type":"function",
  "function":{
    "name":"cadcam_solidworks_model",
    "description":"SOLIDWORKS 2021 参数化建模 / 执行 VBA 宏 / 连接",
    "parameters":{"type":"object","properties":{
        "action":{"type":"string","enum":["model_flange","create_parametric_part","execute_vba","connect"]},
        "vba_code":{"type":"string"},"part_name":{"type":"string"},
        "dimensions":{"type":"object"}},"required":["action"]}
  }
},{
  "type":"function",
  "function":{
    "name":"cadcam_preflight",
    "description":"预检六大工业软件状态",
    "parameters":{"type":"object","properties":{}}
  }
}]
MSG = [{"role":"system","content":"你是工业CAD智能体。需要信息就调用工具，不要只在正文写JSON。"},
       {"role":"user","content":"先检查本机 SolidWorks 是否就绪，然后自行决定下一步。"}]
for model in ["virtu-toolcall","virtu-ties-v1","virtu-disciplined:v1"]:
    payload={"model":model,"messages":MSG,"tools":TOOLS,"stream":False,
             "options":{"temperature":0.2,"num_predict":400}}
    req=urllib.request.Request(URL,data=json.dumps(payload,ensure_ascii=False).encode(),
        headers={"Content-Type":"application/json"},method="POST")
    t0=time.time()
    try:
        with OP.open(req,timeout=240) as r: d=json.loads(r.read().decode())
        m=d.get("message",{})
        print("MODEL",model,"| %.1fs"%(time.time()-t0),
              "| tool_calls",len(m.get("tool_calls") or []),
              "| content:",repr((m.get("content") or "")[:220]))
        for c in (m.get("tool_calls") or []):
            print("    CALL",json.dumps(c,ensure_ascii=False)[:300])
    except Exception as e:
        print("MODEL",model,"ERR",type(e).__name__,str(e)[:160])
