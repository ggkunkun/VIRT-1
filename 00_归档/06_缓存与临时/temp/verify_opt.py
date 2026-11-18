# -*- coding: utf-8 -*-
"""重建 13b-q4 并实测全部 opt tag"""
import subprocess, json, urllib.request, time

def create(tag, mf):
    r = subprocess.run(["ollama", "create", tag, "-f", mf], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=r"D:\Virtu模型\deploy")
    ok = "success" in ((r.stdout or "") + (r.stderr or ""))
    print("create", tag, "->", "OK" if ok else "FAIL")
    return ok

def chat(tag, num_ctx=None):
    payload = {
        "model": tag,
        "messages": [{"role": "user", "content": "用一句话说明数控加工中心。"}],
        "stream": False, "keep_alive": "2m",
        "options": {"num_predict": 96, "temperature": 0},
    }
    if num_ctx:
        payload["options"]["num_ctx"] = num_ctx
    t0 = time.time()
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            d = json.loads(r.read().decode())
    except Exception as e:
        return {"tag": tag, "ok": False, "err": str(e)[:150]}
    ec = d.get("eval_count") or 0
    ed = (d.get("eval_duration") or 1) / 1e9
    return {"tag": tag, "ok": True,
            "tok_s": round(ec / ed, 2) if ec and ed else 0,
            "load_s": round((d.get("load_duration") or 0) / 1e9, 1),
            "prefill_s": round((d.get("prompt_eval_duration") or 0) / 1e9, 1),
            "wall_s": round(time.time() - t0, 1)}

create("virtu-opt-13b-q4", "Modelfile.virtu-opt-13b-q4")

tags = ["virtu-opt-8b", "virtu-opt-8b-ties", "virtu-opt-8b-v3",
        "virtu-opt-13b", "virtu-opt-moe14b", "virtu-opt-13b-q4"]
res = []
for t in tags:
    r = chat(t)
    res.append(r)
    print(json.dumps(r, ensure_ascii=False), flush=True)
json.dump(res, open(r"D:\Virtu模型\temp\opt_verify.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
