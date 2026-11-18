# -*- coding: utf-8 -*-
import json, sys, time, urllib.request
sys.path.insert(0, r'D:\Virtu模型')
from bridges.tool_calling_specs import get_cadcam_tool_definitions
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
tools = get_cadcam_tool_definitions()
print('TOOLS', len(tools), 'json_chars', len(json.dumps(tools, ensure_ascii=False)))
sys.path.insert(0, r'D:\Virtu模型')
import importlib.util
spec = importlib.util.spec_from_file_location('vr', r'D:\Virtu模型\_virtu_run2.py')
vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)
msgs = [{'role':'system','content':vr.SYSTEM_PROMPT},{'role':'user','content':vr.USER_TASK}]
print('PROMPT_CHARS', len(vr.SYSTEM_PROMPT)+len(vr.USER_TASK))
for model in ['virtu-toolcall','virtu-ties-v1']:
    payload={'model':model,'messages':msgs,'tools':tools,'stream':False,'keep_alive':'30m',
             'options':{'temperature':0.2,'num_predict':2048}}
    req=urllib.request.Request('http://127.0.0.1:11434/api/chat',
        data=json.dumps(payload,ensure_ascii=False).encode(),
        headers={'Content-Type':'application/json'},method='POST')
    t0=time.time()
    try:
        with OP.open(req,timeout=300) as r: d=json.loads(r.read().decode())
        print('MODEL',model,'%.1fs'%(time.time()-t0))
        print('  top keys',list(d.keys()))
        m=d.get('message',{})
        print('  msg keys',list(m.keys()))
        for k,v in m.items():
            if k!='tool_calls': print('   ',k,'=',repr(str(v)[:400]))
        print('  tool_calls',json.dumps(m.get('tool_calls') or [],ensure_ascii=False)[:600])
        print('  eval_count',d.get('eval_count'),'prompt_eval_count',d.get('prompt_eval_count'),'done_reason',d.get('done_reason'))
    except Exception as e:
        print('MODEL',model,'ERR',type(e).__name__,str(e)[:200])
